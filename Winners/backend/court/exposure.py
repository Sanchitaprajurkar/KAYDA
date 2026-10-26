"""Exposure methodology. One Assessment per importer-commodity cell, built only from validated Case File rows.

Metrics (each has exactly one numerator and one denominator):
  route_value_decline    lost route value            / route baseline value          (same months, year on year)
  route_volume_decline   lost route tonnes           / route baseline tonnes
  national_import_share  lost route value            / the importer's total imports  (only if a document states it)
  net_exposure           (lost value - substitute gain) / route baseline value       (only if substitution is measured)

A route baseline is never treated as the country's import basket. Missing substitute data is never treated as zero:
substitution is AVAILABLE (measured rise), CONFIRMED_ZERO (measured, no rise), UNKNOWN (reported but not measured) or
UNAVAILABLE (nothing on record). The range is two scenarios of net exposure: high = no substitution (the full route
decline), low = recorded substitution. Without measured substitution there is no low bound. Other observation periods
are reported as sensitivity, never as bounds. Nothing here names a country, commodity or document.
"""

import re
from typing import Dict, List, Optional, Sequence, Tuple

from backend.court.display import cite
from backend.court.models import (METRICS, SOURCE_STATED, AVAILABLE, CONFIRMED_ZERO, NATIONAL_IMPORT_SHARE, NET_EXPOSURE, ROUTE_VALUE_DECLINE,
                                  ROUTE_VOLUME_DECLINE, UNAVAILABLE, UNKNOWN, Assessment, Metric, Quantity)

WINDOW_PREFERENCE = ("full", "onset", "late")  # full months after onset first: the onset month is only partly hit
_LABEL = re.compile(r"^\s*\[P(\d+)\]\s*")
_SUBSTITUTION = re.compile(r"alternativ|substitut|replac|spot purchase|rerout|other suppliers?|new suppliers?|"
                           r"switch(?:ed|ing)? to|shift(?:ed|ing)? to|purchases from|cargoes from|buying [\w ]{0,30}from",
                           re.I)
_NATIONAL = re.compile(r"(?:total|overall|national|all) imports[^.]{0,80}?USD\s*([\d.,]+)\s*(bn|billion|m|million)\b",
                       re.I)
_MONTHLY = re.compile(r"\b(?:a|per) month\b|\bmonthly\b", re.I)
_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def _mentions(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text, re.I) is not None


def _short(months: Sequence[str], year: int) -> str:
    return f"{months[0][:3]}-{months[-1][:3]} {year}" if len(months) > 1 else f"{months[0][:3]} {year}"


class _Rows:
    """Valid rows of several series, one per (origin, month, year). Overlapping notes are de-duplicated."""

    def __init__(self, series: Sequence, notes: List[str]):
        self.rows: Dict[Tuple[str, str, int], object] = {}
        self.series_of: Dict[str, str] = {}
        ranked = sorted([s for s in series if s], key=lambda s: (s.reliability_tier or 9, s.pub_date or ""), reverse=False)
        for s in ranked:
            for r in s.rows:
                if not r.valid or not r.month or not r.year:
                    continue
                key = (r.origin or s.origin or "", r.month, r.year)
                if key in self.rows:
                    notes.append(f"{r.row_id} duplicates {self.rows[key].row_id} for {key[0]} {key[1]} {key[2]}; "
                                 f"the more reliable/earlier-listed row is used")
                    continue
                self.rows[key] = r
                self.series_of[r.row_id] = s.doc_id
        self.origins = sorted({k[0] for k in self.rows})

    def complete(self, months: Sequence[str], years: Sequence[int]) -> List[str]:
        """Months for which every origin has a row in every year."""
        return [m for m in months if self.origins and all((o, m, y) in self.rows for o in self.origins for y in years)]

    def total(self, months: Sequence[str], year: int, field: str) -> Tuple[Optional[float], List[str]]:
        vals, ids = [], []
        for o in self.origins:
            for m in months:
                r = self.rows.get((o, m, year))
                if r is None:
                    return None, ids
                v = getattr(r, field)
                if v is None:
                    return None, ids
                vals.append(v)
                ids.append(r.row_id)
        return round(sum(vals), 2), ids


def _source_label(tools, doc_id: str, paragraph) -> str:
    label = _LABEL.match(paragraph.raw_text or "")
    para = int(label.group(1)) if label else paragraph.paragraph_index
    return f"{doc_id} | Page {paragraph.page_number or 1} | Paragraph {para}"


def _case_paragraphs(tools, report):
    for d in report.retrieved_documents:
        if not tools.admissible(d.doc_id):
            continue
        for p in tools.store.document(d.doc_id).paragraphs:
            yield d.doc_id, p, _LABEL.sub("", p.raw_text or "")


def _substitution_reports(tools, report, country: str, sector: str) -> List[str]:
    """Case File paragraphs that report substitution for this importer and commodity (not measured)."""
    out = []
    for doc_id, p, text in _case_paragraphs(tools, report):
        if _mentions(text, country) and _mentions(text, sector) and _SUBSTITUTION.search(text):
            out.append(_source_label(tools, doc_id, p))
    return list(dict.fromkeys(out))[:5]


_SUPPLIER_NAME = re.compile(r"\bfrom ([A-Z][a-z]+)")
MITIGATION_QUESTIONS = (
    ("volume", "how much the substitute supply amounts to",
     re.compile(r"\d[\d.,]*\s*(?:t\b|tonnes?|kt|cargo(?:es)?|shipments?|%|per ?cent)|\ba (?:third|quarter|fifth|"
                r"sixth|seventh|tenth|half)\b", re.I)),
    ("replacement", "whether it replaces the lost route shipments", _SUBSTITUTION),
    ("timing", "whether it arrives on time", re.compile(r"\bwaits?\b|delay|\blate\b|queue|backlog|transit time|"
                                                       r"congest", re.I)),
    ("cost", "whether it costs more", re.compile(r"price|premium|\bcost|expensive|dearer|freight rate|surcharge|"
                                                 r"pa(?:y|ying|id) more", re.I)),
    ("capacity", "whether the alternative supply can be sustained",
     re.compile(r"capacity|bottleneck|\blimit|constrain|throughput|small base", re.I)),
)


def mitigation_analysis(tools, report, a: Assessment) -> Tuple[List[Dict[str, object]], List[str]]:
    """What the Case File says about each question that decides how much mitigation offsets the route loss.

    Each answer is REPORTED (with its paragraphs), MEASURED (a validated substitute series), or NOT_ON_RECORD. A
    paragraph counts if it names the commodity and either the importer or a reported substitute supplier.
    """
    reported = set(a.substitution.sources)
    suppliers = set()
    paras = list(_case_paragraphs(tools, report))
    for doc_id, p, text in paras:
        if _source_label(tools, doc_id, p) in reported:
            suppliers |= {s for s in _SUPPLIER_NAME.findall(text) if s not in a.origins and s != a.country}
    relevant = []
    for doc_id, p, text in paras:
        if not _LABEL.match(p.raw_text or ""):
            continue  # header and metadata blocks are not evidence
        who = _mentions(text, a.country) or any(_mentions(text, s) for s in suppliers)
        if who and _mentions(text, a.sector):
            relevant.append((_source_label(tools, doc_id, p), text))
    out = []
    for key, question, pattern in MITIGATION_QUESTIONS:
        if key == "volume" and a.substitution.status in (AVAILABLE, CONFIRMED_ZERO):
            out.append({"key": key, "question": question, "status": "MEASURED", "sources": list(a.substitution.rows),
                        "note": a.substitution.note})
            continue
        hits = [(label, text) for label, text in relevant if pattern.search(text)
                and (key != "volume" or any(_mentions(text, s) for s in suppliers) or _SUBSTITUTION.search(text))]
        out.append({"key": key, "question": question, "status": "REPORTED" if hits else "NOT_ON_RECORD",
                    "sources": [h[0] for h in hits[:3]], "note": hits[0][1][:200] if hits else ""})
    return out, sorted(suppliers)


def _national_imports(tools, report, country: str, months: Sequence[str], year: int) -> Quantity:
    """The importer's total imports for the period, only if a Case File document states them."""
    name = "national_total_imports"
    period = _short(months, year)
    for doc_id, p, text in _case_paragraphs(tools, report):
        if not _mentions(text, country):
            continue
        m = _NATIONAL.search(text)
        if not m:
            continue
        years = {int(y.group(0)) for y in _YEAR.finditer(text)}
        if years and year not in years:
            continue
        value = float(m.group(1).replace(",", "")) * (1000.0 if m.group(2).lower().startswith("b") else 1.0)
        monthly = bool(_MONTHLY.search(text))
        scaled = value * len(months) if monthly else value * len(months) / 12.0
        return Quantity(name=name, value=round(scaled, 2), unit="USD M", status=AVAILABLE, period=period,
                        sources=[_source_label(tools, doc_id, p)],
                        note=(f"stated as USD {value:,.1f}M per month, times {len(months)} month(s)" if monthly else
                              f"stated as USD {value:,.1f}M a year, pro-rated to {len(months)} month(s) "
                              f"(assumes even monthly imports)"))
    return Quantity(name=name, unit="USD M", status=UNAVAILABLE, period=period,
                    note=f"no document in the Case File states {country}'s total imports")


def _pct(num: Optional[float], den: Optional[float]) -> Optional[float]:
    return round(num / den * 100, 2) if num is not None and den else None


def assess(tools, report, cell, windows_by_name: Dict[str, Tuple[List[str], int, int]]) -> Optional[Assessment]:
    """The cell's assessment, or None when its trade rows cannot support any metric."""
    if cell.status != "COVERED" or not cell.primary_series:
        return None
    notes: List[str] = []
    primary = _Rows([tools.series(d) for d in cell.primary_series], notes)
    subs = _Rows([tools.series(d) for d in cell.substitute_series], notes)
    usable: Dict[str, Tuple[List[str], int, int, List[str]]] = {}
    for name, (months, base_y, dis_y) in windows_by_name.items():
        ok = primary.complete(months, (base_y, dis_y))
        if ok:
            usable[name] = (ok, base_y, dis_y, [m for m in months if m not in ok])
    order = [w for w in WINDOW_PREFERENCE if w in usable] + [w for w in usable if w not in WINDOW_PREFERENCE]
    if not order:
        return None
    window = order[0]
    months, base_y, dis_y, dropped = usable[window]
    period = f"{_short(months, dis_y)} vs {_short(months, base_y)}"
    assumptions = [f"Baseline is the same months one year earlier ({_short(months, base_y)}), so seasonality is held "
                   f"constant.",
                   "Values are nominal USD as reported; the value metric mixes price and quantity changes, the volume "
                   "metric does not."]
    if dropped:
        assumptions.append(f"{', '.join(dropped)} left out of the {window} period: the route lacks a valid row for it "
                           f"in one of the two years.")
    assumptions += notes

    q: Dict[str, Quantity] = {}

    def put(name, value, unit, year, ids, status=None, note=""):
        q[name] = Quantity(name=name, value=value, unit=unit, period=_short(months, year), rows=ids,
                           status=status or (AVAILABLE if value is not None else UNAVAILABLE), note=note)

    bv, b_ids = primary.total(months, base_y, "value_usd_m")
    dv, d_ids = primary.total(months, dis_y, "value_usd_m")
    bt, bt_ids = primary.total(months, base_y, "volume_t")
    dt, dt_ids = primary.total(months, dis_y, "volume_t")
    put("route_baseline_value", bv, "USD M", base_y, b_ids)
    put("route_disrupted_value", dv, "USD M", dis_y, d_ids)
    put("route_baseline_volume", bt, "tonnes", base_y, bt_ids)
    put("route_disrupted_volume", dt, "tonnes", dis_y, dt_ids)
    gross_v = round(bv - dv, 2) if bv is not None and dv is not None else None
    gross_t = round(bt - dt, 2) if bt is not None and dt is not None else None
    q["route_value_loss"] = Quantity(name="route_value_loss", value=gross_v, unit="USD M", period=period,
                                     status=AVAILABLE if gross_v is not None else UNAVAILABLE,
                                     note="route_baseline_value - route_disrupted_value (negative = increase)")
    q["route_volume_loss"] = Quantity(name="route_volume_loss", value=gross_t, unit="tonnes", period=period,
                                      status=AVAILABLE if gross_t is not None else UNAVAILABLE,
                                      note="route_baseline_volume - route_disrupted_volume (negative = increase)")

    # Substitution: measured only from substitute series that cover every month of the period in both years.
    if cell.substitute_series:
        missing = [m for m in months if m not in subs.complete(months, (base_y, dis_y))]
        if subs.origins and not missing:
            sb, sb_ids = subs.total(months, base_y, "value_usd_m")
            sd, sd_ids = subs.total(months, dis_y, "value_usd_m")
            put("substitute_baseline_value", sb, "USD M", base_y, sb_ids)
            put("substitute_disrupted_value", sd, "USD M", dis_y, sd_ids)
            change = round(sd - sb, 2)
            substitution = Quantity(
                name="substitute_gain", value=max(change, 0.0), unit="USD M", period=period,
                status=AVAILABLE if change > 0 else CONFIRMED_ZERO, rows=sb_ids + sd_ids,
                note=(f"recorded supply from {', '.join(subs.origins)} rose by USD {change:.1f}M" if change > 0 else
                      f"recorded supply from {', '.join(subs.origins)} changed by USD {change:+.1f}M: no rise, so "
                      f"no measured substitution"))
            assumptions.append(f"Only suppliers with a validated trade series in the Case File ({', '.join(subs.origins)}) "
                               f"count as substitution; supply from unrecorded suppliers is unknown.")
        else:
            substitution = Quantity(name="substitute_gain", unit="USD M", status=UNKNOWN, period=period,
                                    note=f"substitute series {', '.join(cell.substitute_series)} lack valid rows for "
                                         f"{', '.join(missing) or 'the period'} in one of the two years")
    else:
        reports = _substitution_reports(tools, report, cell.country, cell.sector)
        substitution = Quantity(
            name="substitute_gain", unit="USD M", period=period, status=UNKNOWN if reports else UNAVAILABLE,
            sources=reports,
            note=("substitution is reported but no trade series measures it" if reports else
                  "the Case File has no data on substitute supply either way"))
    q["substitute_gain"] = substitution
    national = _national_imports(tools, report, cell.country, months, base_y)
    q["national_total_imports"] = national

    route = f"{'/'.join(primary.origins)} -> {cell.country}, {cell.sector}"
    metrics: Dict[str, Metric] = {}
    rv = _pct(gross_v, bv)
    metrics[ROUTE_VALUE_DECLINE] = Metric(
        key=ROUTE_VALUE_DECLINE, label=f"Trade value decline on {route}", value=rv,
        unit="% of baseline route value", status=AVAILABLE if rv is not None else UNAVAILABLE,
        numerator="route_value_loss", denominator="route_baseline_value",
        formula="(route_baseline_value - route_disrupted_value) / route_baseline_value x 100",
        missing_inputs=[] if rv is not None else ["route trade values for both years"])
    rt = _pct(gross_t, bt)
    metrics[ROUTE_VOLUME_DECLINE] = Metric(
        key=ROUTE_VOLUME_DECLINE, label=f"Trade volume decline on {route}", value=rt,
        unit="% of baseline route tonnes", status=AVAILABLE if rt is not None else UNAVAILABLE,
        numerator="route_volume_loss", denominator="route_baseline_volume",
        formula="(route_baseline_volume - route_disrupted_volume) / route_baseline_volume x 100",
        missing_inputs=[] if rt is not None else ["route volumes (tonnes) for both years"])
    ns = _pct(gross_v, national.value) if national.status == AVAILABLE else None
    metrics[NATIONAL_IMPORT_SHARE] = Metric(
        key=NATIONAL_IMPORT_SHARE, label=f"Lost route value as a share of {cell.country}'s total imports", value=ns,
        unit=f"% of {cell.country}'s total imports", status=AVAILABLE if ns is not None else UNAVAILABLE,
        numerator="route_value_loss", denominator="national_total_imports",
        formula="route_value_loss / national_total_imports x 100",
        assumptions=[national.note] if national.status == AVAILABLE else [],
        missing_inputs=[] if ns is not None else
        [f"{cell.country}'s total imports (all goods, all suppliers) for {_short(months, base_y)}"])
    measured = substitution.status in (AVAILABLE, CONFIRMED_ZERO)
    net = None
    net_assumptions = []
    if measured and gross_v is not None and bv:
        raw = gross_v - (substitution.value or 0.0)
        if raw < 0:
            net_assumptions.append("recorded substitute gain exceeds the route loss; net exposure floored at 0")
        net = round(max(raw, 0.0) / bv * 100, 2)
    metrics[NET_EXPOSURE] = Metric(
        key=NET_EXPOSURE, label=f"Net exposure on {route} after recorded substitution", value=net,
        unit="% of baseline route value", status=AVAILABLE if net is not None else substitution.status,
        numerator="route_value_loss - substitute_gain", denominator="route_baseline_value",
        formula="(route_value_loss - substitute_gain) / route_baseline_value x 100",
        assumptions=net_assumptions,
        missing_inputs=[] if net is not None else
        [f"measured substitute supply of {cell.sector.lower()} into {cell.country} for {period}"])

    high = rv
    low = net if net is not None else None
    if high is None:
        basis = "No range: the route's trade values do not cover both years of the period."
    elif low is None:
        basis = (f"Upper bound only: {high:.2f}% is the no-substitution scenario (the full route value decline). "
                 f"Substitution is {substitution.status} ({substitution.note}), so no lower bound is supported.")
    elif abs(low - high) < 0.005:
        basis = (f"Point estimate {high:.2f}%: substitution is {substitution.status} ({substitution.note}), so the "
                 f"recorded-substitution scenario equals the no-substitution scenario.")
    else:
        basis = (f"Low {low:.2f}% = recorded-substitution scenario ({substitution.note}); high {high:.2f}% = "
                 f"no-substitution scenario.")
    sensitivity = []
    for name in order[1:]:
        m2, b2, d2, _ = usable[name]
        v_b, _ = primary.total(m2, b2, "value_usd_m")
        v_d, _ = primary.total(m2, d2, "value_usd_m")
        sensitivity.append({"window": name, "period": f"{_short(m2, d2)} vs {_short(m2, b2)}",
                            ROUTE_VALUE_DECLINE: _pct(round(v_b - v_d, 2) if v_b is not None and v_d is not None
                                                      else None, v_b)})
    breakdown = []
    for role, rows in (("primary", primary), ("substitute", subs)):
        for (o, m, y), r in rows.rows.items():
            if m in months and y in (base_y, dis_y):
                breakdown.append({"role": role, "origin": o, "month": m, "year": y, "series": rows.series_of[r.row_id],
                                  "value_usd_m": r.value_usd_m, "volume_t": r.volume_t, "row_id": r.row_id})
    flagged = [r.row_id for d in cell.primary_series + cell.substitute_series for r in (tools.series(d).rows
               if tools.series(d) else []) if not r.valid]
    return Assessment(
        country=cell.country, sector=cell.sector, origins=primary.origins, route=route,
        primary_series=list(cell.primary_series), substitute_series=list(cell.substitute_series), window=window,
        months=months, baseline_year=base_y, disrupted_year=dis_y, period=period, quantities=q, metrics=metrics,
        substitution=substitution, low=low, high=high, range_basis=basis, sensitivity=sensitivity,
        breakdown=breakdown, rows_flagged=flagged, assumptions=assumptions,
        missing_inputs=[x for m in metrics.values() for x in m.missing_inputs])


def statement_values(a: Assessment) -> List[float]:
    """Every percentage a statement about this assessment may quote."""
    vals = [m.value for m in a.metrics.values() if m.value is not None]
    vals += [s[ROUTE_VALUE_DECLINE] for s in a.sensitivity if s.get(ROUTE_VALUE_DECLINE) is not None]
    return vals


_PERCENT = re.compile(r"(-?\d+(?:\.\d+)?)\s*%")
_NATIONAL_PHRASE = re.compile(r"(?:total|national|overall|all) imports|import basket|share of [\w' ]*imports", re.I)


def _close(a: Optional[float], b: Optional[float], tol: float = 0.05) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs(a - b) <= tol


def numeric_claim_defect(tools, report, claim) -> Optional[Tuple[str, str]]:
    """(reason, argument) when a claim's figure does not mean what the claim says it means, else None.

    Checks scope and meaning, not only arithmetic: the metric must be one the data can produce for this cell, the
    bounds must be the scenarios the data supports, the statement must not relabel the figure, and a percentage
    quoted from a document can stand only for the country and commodity that document measured.
    """
    est = claim.estimate
    if est is None:
        if _PERCENT.search(claim.statement) and claim.kind == "calculation":
            return "math_error", "The statement quotes a percentage but the claim files no estimate for it."
        return None
    if est.metric == SOURCE_STATED:
        figures = [v for v in (est.low, est.high) if v is not None]
        holders = [e for e in claim.citations if any(re.search(rf"(?<![\d.]){re.escape(f'{v:g}')}(?![\d])",
                                                                e.excerpt or "") for v in figures)]
        if not holders:
            return "math_error", f"The figure {'/'.join(f'{v:g}%' for v in figures)} is not in any cited paragraph."
        if not any(_mentions(e.excerpt or "", claim.country) and _mentions(e.excerpt or "", claim.sector)
                   for e in holders):
            return ("wrong_scope", f"{cite(holders[0])} states {figures[0]:g}% for something other than "
                                   f"{claim.country} {claim.sector}: the paragraph does not name both, so the figure "
                                   f"cannot stand for that country and commodity.")
        return None
    if est.metric not in METRICS:
        return "wrong_scope", f"'{est.metric}' is not a metric the trade data can produce."
    cell = next((c for c in report.coverage_map if (c.country, c.sector) == (claim.country, claim.sector)), None)
    fresh = tools.assessment(report, cell) if cell else None
    if fresh is None:
        return "wrong_scope", f"The Case File has no validated trade rows for {claim.country} {claim.sector}."
    if claim.assessment is not None:
        mine = claim.assessment
        if (sorted(r["row_id"] for r in mine.breakdown) != sorted(r["row_id"] for r in fresh.breakdown)
                or not _close(mine.low, fresh.low) or not _close(mine.high, fresh.high)):
            return "math_error", ("The claim's calculation does not match a recomputation from the Case File's trade "
                                  "rows (different rows or figures).")
    metric = fresh.metrics[est.metric]
    if est.metric == NET_EXPOSURE and fresh.high is None:
        return "wrong_scope", f"No net-exposure scenario exists for {fresh.period}: {fresh.range_basis}"
    if est.metric != NET_EXPOSURE and metric.status != AVAILABLE:
        return ("wrong_scope", f"{metric.label} is {metric.status} for {fresh.period}: missing "
                               f"{'; '.join(metric.missing_inputs) or 'inputs'}.")
    want_low, want_high = (fresh.low, fresh.high) if est.metric == NET_EXPOSURE else (metric.value, metric.value)
    if est.metric == NET_EXPOSURE and est.scenario == "recorded_substitution":
        if fresh.low is None:
            return ("math_error", f"The claim argues a recorded-substitution figure but substitution is "
                                  f"{fresh.substitution.status} ({fresh.substitution.note}).")
        want_low = want_high = fresh.low
    if est.metric == NET_EXPOSURE and fresh.low is None and est.low is not None:
        return ("math_error", f"The claim sets a lower bound of {est.low:g}% but substitution is "
                              f"{fresh.substitution.status} ({fresh.substitution.note}); no lower bound is supported.")
    if not _close(est.low, want_low) or not _close(est.high, want_high):
        return ("math_error", f"The estimate {est.low}-{est.high}% does not equal {metric.label} for {fresh.period} "
                              f"({want_low}-{want_high}%).")
    if fresh.metrics[NATIONAL_IMPORT_SHARE].status != AVAILABLE and any(
            _NATIONAL_PHRASE.search(clause) and _PERCENT.search(clause)
            for clause in re.split(r"[.;:](?:\s|$)", claim.statement)):
        return ("wrong_scope", f"The statement presents a figure as a share of {claim.country}'s total imports, "
                               f"but no national import total is on the record.")
    allowed = statement_values(fresh)
    for raw in _PERCENT.findall(claim.statement):
        if not any(abs(float(raw) - v) <= 0.051 for v in allowed):
            return "math_error", f"The statement quotes {raw}%, which no metric on the record for {fresh.period} produces."
    return None
