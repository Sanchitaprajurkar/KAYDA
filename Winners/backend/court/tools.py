"""Tools shared by the courtroom agents. They read only Heimdall's trap-resolved evidence.

  search(query, filters)        hybrid: BM25 + TF-IDF cosine fused by reciprocal rank, over paragraphs, with
                                metadata filters; pub_date <= as-of is enforced inside the tool. A case-wide
                                ledger rejects a repeated (query, filters) pair.
  facts_for(hits)               the sourced facts extracted from the paragraphs a search returned
  trade_series(dest, sector)    monthly trade series into a country, validated rows only count
  compute_change(...)           the deterministic TradeCalculator; no number in a claim comes from the LLM

Every call counts against the calling agent's per-run tool budget (NFR5).
"""

import math
import re
from collections import Counter
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from backend.court.heimdall_bridge import (CaseEvidenceReport, ExtractedFact, ResolvedEvidenceStore, TradeSeries,
                                           TradeStore)
from backend.court.display import cite
from backend.court.models import Calculation, Evidence
from backend.court.trade_calculator import DisruptionCalculationInput, TradeCalculator, TradeRow

K1, B, RRF_K = 1.2, 0.75, 60
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]
_LABEL = re.compile(r"^\s*\[P(\d+)\]")


class DuplicateQuery(ValueError):
    pass


class ToolLimit(RuntimeError):
    pass


class SearchFilters(BaseModel):
    event_id: Optional[str] = None
    include_reference: bool = True  # background reference sheets (event NONE / atlas) stay searchable
    country: Optional[str] = None
    sector: Optional[str] = None
    source_types: List[str] = Field(default_factory=list)
    max_tier: Optional[int] = None
    date_from: Optional[str] = None

    def count(self) -> int:
        return sum(1 for v in (self.event_id, self.country, self.sector, self.source_types, self.max_tier,
                               self.date_from) if v)


class SearchHit(BaseModel):
    doc_id: str
    paragraph_index: int
    ref: str
    text: str
    score: float
    tier: int
    pub_date: str
    source_type: str
    title: str


def _tokens(text: str) -> List[str]:
    from heimdall.case.text import tokens
    return tokens(text)


class _Index:
    """Paragraph index over resolved evidence, built once per store."""

    def __init__(self, store: ResolvedEvidenceStore):
        self.store = store
        self.rows: List[Tuple[str, int, str, str, List[str]]] = []
        for did in store.evidence_ids():
            raw = {p.paragraph_index: p.raw_text for p in store.document(did).paragraphs}
            for idx, text in store.body_paragraphs(did):
                label = _LABEL.match(raw.get(idx, ""))
                ref = f"{did}#P{label.group(1)}" if label else f"{did}#para{idx}"
                self.rows.append((did, idx, ref, text, _tokens(text)))
        n = len(self.rows)
        self.df = Counter(t for *_, toks in self.rows for t in set(toks))
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in self.df.items()}
        self.avg_len = sum(len(r[4]) for r in self.rows) / max(1, n)
        self.vectors = []
        for *_, toks in self.rows:
            tf = Counter(toks)
            vec = {t: (1 + math.log(c)) * self.idf[t] for t, c in tf.items()}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self.vectors.append({t: v / norm for t, v in vec.items()})


@lru_cache(maxsize=4)
def _index_for(store_id: int, store: ResolvedEvidenceStore) -> _Index:
    return _Index(store)


class RunemarkTools:
    def __init__(self, store: ResolvedEvidenceStore, trade: TradeStore, as_of: str,
                 ledger: Optional[set] = None, budget_per_run: int = 12):
        self.store = store
        self.trade = trade
        self.as_of = as_of
        self.ledger = ledger if ledger is not None else set()
        self.budget_per_run = budget_per_run
        self.calls: Counter = Counter()
        self.index = _index_for(id(store), store)
        self._meta = {did: store.document(did).manifest_meta for did in store.evidence_ids()}

    # -- budget -----------------------------------------------------------------
    def start_run(self) -> None:
        self.calls.clear()

    def spend(self, agent: str) -> None:
        if self.calls[agent] >= self.budget_per_run:
            raise ToolLimit(f"{agent} reached its tool-call limit ({self.budget_per_run}) for this run")
        self.calls[agent] += 1

    _spend = spend

    # -- search -----------------------------------------------------------------
    def _admits(self, did: str, f: SearchFilters) -> bool:
        m = self._meta[did]
        if (m.pub_date or "9999") > self.as_of:
            return False
        is_reference = m.source_type == "atlas" or (m.event_id or "NONE") == "NONE"
        if f.event_id and m.event_id != f.event_id and not (f.include_reference and m.source_type == "atlas"):
            return False
        if f.country and (m.country or "") != f.country and not (f.include_reference and is_reference):
            if f.country.lower() not in (m.title or "").lower():
                return False
        if f.sector and (m.sector or "").lower() not in (f.sector.lower(), "general"):
            if f.sector.lower() not in (m.title or "").lower():
                return False
        if f.source_types and m.source_type not in f.source_types:
            return False
        if f.max_tier and m.reliability_tier > f.max_tier:
            return False
        if f.date_from and (m.pub_date or "") < f.date_from:
            return False
        return True

    def search(self, agent: str, query: str, filters: SearchFilters, k: int = 8) -> List[SearchHit]:
        terms = list(dict.fromkeys(_tokens(query)))
        key = (" ".join(sorted(terms)), filters.model_dump_json())
        if key in self.ledger:
            raise DuplicateQuery(f"DUPLICATE_QUERY: '{query}' with these filters was already run in this case")
        self._spend(agent)
        self.ledger.add(key)
        ix = self.index
        allowed = [i for i, row in enumerate(ix.rows) if self._admits(row[0], filters)]
        qvec = {t: ix.idf.get(t, 0.0) for t in terms}
        qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
        bm25, cosine = {}, {}
        for i in allowed:
            toks = ix.rows[i][4]
            tf = Counter(toks)
            s = sum(ix.idf.get(t, 0.0) * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * len(toks) / ix.avg_len))
                    for t in terms if tf[t])
            if s > 0:
                bm25[i] = s
                cosine[i] = sum(qvec[t] / qnorm * ix.vectors[i].get(t, 0.0) for t in terms)
        rank_b = {i: r for r, i in enumerate(sorted(bm25, key=lambda i: -bm25[i]), 1)}
        rank_c = {i: r for r, i in enumerate(sorted(cosine, key=lambda i: -cosine[i]), 1)}
        fused = sorted(bm25, key=lambda i: -(1 / (RRF_K + rank_b[i]) + 1 / (RRF_K + rank_c[i])))[:k]
        hits = []
        for i in fused:
            did, idx, ref, text, _ = ix.rows[i]
            m = self._meta[did]
            hits.append(SearchHit(doc_id=did, paragraph_index=idx, ref=ref, text=text,
                                  score=round(1 / (RRF_K + rank_b[i]) + 1 / (RRF_K + rank_c[i]), 5),
                                  tier=m.reliability_tier, pub_date=m.pub_date, source_type=m.source_type,
                                  title=m.title or ""))
        return hits

    # -- evidence ---------------------------------------------------------------
    def cite_label(self, doc_id: str, paragraph_no: int) -> str:
        """'DOC_ID | Page N | Paragraph M' for a document's labelled paragraph [P M]."""
        page = 1
        if doc_id in self._meta:
            for p in self.store.document(doc_id).paragraphs:
                label = _LABEL.match(p.raw_text or "")
                if label and int(label.group(1)) == paragraph_no:
                    page = p.page_number or 1
                    break
        return f"{doc_id} | Page {page} | Paragraph {paragraph_no}"

    def ref_for(self, doc_id: str, paragraph_index: int) -> str:
        raw = {p.paragraph_index: p.raw_text for p in self.store.document(doc_id).paragraphs}
        label = _LABEL.match(raw.get(paragraph_index, ""))
        return f"{doc_id}#P{label.group(1)}" if label else f"{doc_id}#para{paragraph_index}"

    def facts_for(self, hits: Iterable[SearchHit]) -> List[ExtractedFact]:
        seen, out = set(), []
        for h in hits:
            for f in self.store.facts(h.doc_id):
                if f.source_ref.paragraph_index == h.paragraph_index and f.fact_id not in seen:
                    seen.add(f.fact_id)
                    out.append(f)
        return out

    def evidence(self, fact: ExtractedFact) -> Evidence:
        m = self._meta[fact.source_ref.doc_id]
        doc = self.store.document(fact.source_ref.doc_id)
        p_idx = fact.source_ref.paragraph_index
        para = next((p for p in doc.paragraphs if p.paragraph_index == p_idx), None)

        page_num = fact.source_ref.page_number
        if page_num is None and para and para.page_number is not None:
            page_num = para.page_number
        if page_num is None:
            page_num = 1

        raw = para.raw_text if para else ""
        label = _LABEL.match(raw)
        if label:
            para_num = int(label.group(1))
        elif para and para.page_number is not None:
            page_paras = [p for p in doc.paragraphs if p.page_number == para.page_number]
            para_num = page_paras.index(para) + 1 if para in page_paras else p_idx
        else:
            para_num = p_idx

        excerpt = (fact.source_ref.text_snippet or _LABEL.sub("", raw)).strip()

        return Evidence(doc_id=fact.source_ref.doc_id, ref=self.ref_for(fact.source_ref.doc_id,
                                                                         fact.source_ref.paragraph_index),
                        kind="paragraph",
                        page_number=page_num,
                        paragraph_number=para_num,
                        pub_date=m.pub_date, pub_time=m.pub_time, tier=m.reliability_tier,
                        source_name=m.source_name, title=m.title, excerpt=excerpt,
                        fact_id=fact.fact_id,
                        assertion=fact.assertion_status.value if fact.assertion_status else "REPORTED",
                        numeric_value=fact.numeric_value, unit=fact.unit)

    def admissible(self, doc_id: str) -> bool:
        return doc_id in self._meta and (self._meta[doc_id].pub_date or "9999") <= self.as_of

    # -- trade ------------------------------------------------------------------
    def trade_series(self, agent: str, dest: str, sector: str) -> List[TradeSeries]:
        self._spend(agent)
        out = []
        for did, m in self._meta.items():
            if (m.pub_date or "9999") > self.as_of:
                continue
            s = self.trade.series(did)
            if s and s.valid_rows and s.dest == dest and (s.sector or "").lower() == sector.lower():
                out.append(s)
        return out

    def series(self, doc_id: str) -> Optional[TradeSeries]:
        return self.trade.series(doc_id) if doc_id in self._meta else None

    def compute_change(self, agent: Optional[str], country: str, sector: str, origins: Sequence[str],
                       primary: Sequence[TradeSeries], substitutes: Sequence[TradeSeries], months: Sequence[str],
                       baseline_year: int, disrupted_year: int, premium_pct: float = 0.0,
                       window: str = "") -> Optional[Calculation]:
        """TradeCalculator over validated rows; flagged rows are reported and never used."""
        if agent:
            self._spend(agent)
        p_rows = [_to_row(r, s) for s in primary for r in s.rows]
        s_rows = [_to_row(r, s) for s in substitutes for r in s.rows]
        try:
            res = TradeCalculator.calculate_disruption(DisruptionCalculationInput(
                country=country, sector=sector, primary_supplier="/".join(origins), primary_rows=p_rows,
                substitute_suppliers=sorted({s.origin for s in substitutes if s.origin}), substitute_rows=s_rows,
                baseline_year=baseline_year, disrupted_year=disrupted_year, disruption_months=list(months),
                spot_price_escalation_pct=premium_pct))
        except ValueError:
            return None
        base = res.baseline_value_usd_m
        breakdown = [{"month": r.month, "year": r.year, "origin": r.country_from, "series": r.doc_id, "role": role,
                      "value_usd_m": r.val_usd_m, "row_id": r.full_id}
                     for role, rows in (("primary", p_rows), ("substitute", s_rows)) for r in rows
                     if not r.is_damaged and r.month in months and r.year in (baseline_year, disrupted_year)]
        sub_base = sum(r.val_usd_m for r in s_rows
                       if not r.is_damaged and r.year == baseline_year and r.month in months)
        imports = base + sub_base
        return Calculation(
            country=country, sector=sector, origins=list(origins), primary_series=[s.doc_id for s in primary],
            substitute_series=[s.doc_id for s in substitutes], months=list(months), baseline_year=baseline_year,
            disrupted_year=disrupted_year, premium_pct=premium_pct, window=window,
            gross_loss_pct=res.gross_value_loss_pct, net_loss_pct=res.net_value_loss_pct,
            net_import_loss_pct=round(res.net_value_loss_usd_m / imports * 100, 2) if imports else 0.0,
            gross_import_loss_pct=round(res.gross_value_loss_usd_m / imports * 100, 2) if imports else 0.0,
            import_baseline_usd_m=round(imports, 2),
            # high_bound_pct is reference only (gross × spot-premium / primary baseline); not a valid claim bound.
            high_bound_pct=round(res.high_exposure_bound_usd_m / base * 100, 2) if base else 0.0,
            baseline_usd_m=base, gross_loss_usd_m=res.gross_value_loss_usd_m, net_loss_usd_m=res.net_value_loss_usd_m,
            substitute_gain_usd_m=res.substitute_value_gain_usd_m,
            rows_used=res.source_row_ids + res.substitute_row_ids,
            rows_flagged=[r.split(":")[0] for r in res.damaged_rows_reported], breakdown=breakdown)

    def row_evidence(self, calc: Calculation) -> List[Evidence]:
        """Every valid trade row the calculation used, so each month of the claim can be checked."""
        out = []
        for did in calc.primary_series + calc.substitute_series:
            s = self.trade.series(did)
            m = self._meta[did]
            doc = self.store.document(did) if did in self._meta else None
            used = [r for r in s.rows if r.valid and r.month in calc.months
                    and r.year in (calc.baseline_year, calc.disrupted_year)]
            for r in used:
                p_idx = r.paragraph_index
                para = next((p for p in doc.paragraphs if p.paragraph_index == p_idx), None) if doc and p_idx else None
                page_num = (para.page_number if para else None) or 1
                raw = para.raw_text if para else ""
                label = _LABEL.match(raw)
                if label:
                    para_num = int(label.group(1))
                elif para and para.page_number is not None:
                    page_paras = [p for p in doc.paragraphs if p.page_number == para.page_number]
                    para_num = page_paras.index(para) + 1 if para in page_paras else (p_idx or 1)
                else:
                    para_num = p_idx or 1
                excerpt = _LABEL.sub("", raw).strip() if raw else (r.text or f"{r.month} {r.year}: USD {r.value_usd_m}M, {r.volume_t} tonnes")
                out.append(Evidence(doc_id=did, ref=r.row_id, kind="trade_row",
                                    page_number=page_num, paragraph_number=para_num,
                                    pub_date=m.pub_date,
                                    pub_time=m.pub_time, tier=m.reliability_tier, source_name=m.source_name,
                                    title=m.title, excerpt=excerpt, numeric_value=r.value_usd_m, unit="USD M"))
        return out


def calculation_defect(tools: "RunemarkTools", claim) -> Optional[Tuple[str, str]]:
    """(reason, argument) if a calculation claim uses the wrong series or does not recompute, else None."""
    for calc in claim.calculations:
        for sid in calc.primary_series + calc.substitute_series:
            s = tools.series(sid)
            if not s or s.dest != claim.country or (s.sector or "").lower() != claim.sector.lower():
                return "wrong_scope", f"{sid} is not a {claim.sector} series into {claim.country}."
        again = tools.compute_change(
            None, calc.country, calc.sector, calc.origins, [tools.series(s) for s in calc.primary_series],
            [tools.series(s) for s in calc.substitute_series], calc.months, calc.baseline_year,
            calc.disrupted_year, calc.premium_pct, calc.window)
        if not again or any(abs(getattr(again, k) - getattr(calc, k)) > 0.05
                            for k in ("gross_loss_pct", "net_import_loss_pct", "high_bound_pct")):
            return "math_error", f"The {calc.window} calculation does not recompute from the trade rows."
    if claim.calculations:
        # Both bounds must use the same denominator: the total import basket (primary + substitute baseline).
        # low  = net_import_loss_pct  — net loss / total imports (best case: substitutes fully absorbed the shortfall).
        # high = gross_import_loss_pct — gross loss / total imports (worst case: no substitution materialises).
        # gross_loss_pct and high_bound_pct (primary-baseline denominator / price-inflated) are reference metrics only.
        low_ok = any(abs(round(claim.estimate.low, 2) - round(c.net_import_loss_pct, 2)) <= 0.05
                     for c in claim.calculations)
        high_ok = any(abs(round(claim.estimate.high, 2) - round(c.gross_import_loss_pct, 2)) <= 0.05
                      for c in claim.calculations)
        if not low_ok:
            nets = ", ".join(f"{c.net_import_loss_pct:.2f}%" for c in claim.calculations)
            return ("math_error",
                    f"estimate.low ({claim.estimate.low:.2f}%) must equal net_import_loss_pct from one of its "
                    f"calculations ({nets}) — net value loss / total import basket (primary + substitute baseline).")
        if not high_ok:
            grosses = ", ".join(f"{c.gross_import_loss_pct:.2f}%" for c in claim.calculations)
            return ("math_error",
                    f"estimate.high ({claim.estimate.high:.2f}%) must equal gross_import_loss_pct from one of its "
                    f"calculations ({grosses}) — gross value loss / total import basket (no substitution scenario).")
    return None


def citation_scope_defect(tools: "RunemarkTools", claim) -> Optional[Tuple[str, str]]:
    """(reason, argument) if a claim's own citations are out of scope for its country/sector.

    Rules (deterministic — no LLM):
    - A trade-series citation must point to the claim's country and sector.
    - A narrative citation must mention the claim's country or sector somewhere in its excerpt.
    """
    country_lc = claim.country.lower()
    sector_lc = claim.sector.lower()
    for e in claim.citations:
        s = tools.series(e.doc_id)
        if s:
            if s.dest and s.dest.lower() != country_lc:
                return ("wrong_scope",
                        f"{cite(e)} is a trade series for {s.dest}, not {claim.country}; "
                        f"it cannot support a claim about {claim.country} {claim.sector}.")
            if s.sector and s.sector.lower() not in (sector_lc, "general"):
                return ("wrong_scope",
                        f"{cite(e)} covers {s.sector} trade, not {claim.sector}; "
                        f"it cannot support a claim about {claim.country} {claim.sector}.")
        else:
            # Narrative doc: require that the cited paragraph excerpt mentions both country and sector.
            text = ((e.excerpt or "") + " " + (e.assertion or "")).lower()
            missing = [w for w in (country_lc, sector_lc) if w not in text]
            if len(missing) == 2:
                return ("wrong_scope",
                        f"{cite(e)} does not mention {claim.country} or {claim.sector} "
                        f"in the cited paragraph; it cannot support this claim.")
    return None


def attack_counter_scope_defect(tools: "RunemarkTools", attack, target_claim) -> Optional[Tuple[str, str]]:
    """(reason, argument) if an attack's counter-evidence is out of scope for the target claim.

    Counter-evidence that concerns a different country or sector cannot rebut the specific claim.
    """
    country_lc = target_claim.country.lower()
    sector_lc = target_claim.sector.lower()
    for e in (attack.counter_evidence or []):
        s = tools.series(e.doc_id)
        if s:
            if s.dest and s.dest.lower() != country_lc:
                return ("wrong_scope",
                        f"Counter-evidence {cite(e)} covers {s.dest}, not {target_claim.country}; "
                        f"it cannot rebut a claim about {target_claim.country} {target_claim.sector}.")
            if s.sector and s.sector.lower() not in (sector_lc, "general"):
                return ("wrong_scope",
                        f"Counter-evidence {cite(e)} covers {s.sector} trade, not {target_claim.sector}.")
        else:
            text = ((e.excerpt or "") + " " + (e.assertion or "")).lower()
            missing = [w for w in (country_lc, sector_lc) if w not in text]
            if len(missing) == 2:
                return ("wrong_scope",
                        f"Counter-evidence {cite(e)} does not mention {target_claim.country} or "
                        f"{target_claim.sector} in the cited paragraph.")
    return None


def _to_row(r, s: TradeSeries) -> TradeRow:
    return TradeRow(doc_id=r.doc_id, row_id=r.row_id.split("#")[-1], full_id=r.row_id, country_from=r.origin,
                    country_to=r.dest, sector=r.sector or s.sector or "general", month=r.month or "UNKNOWN",
                    year=r.year or 0, period=r.period or "INVALID", val_usd_m=max(r.value_usd_m or 0.0, 0.0),
                    vol_tonnes=max(r.volume_t or 0.0, 0.0), is_damaged=not r.valid,
                    damage_reason="; ".join(r.flags) or None)


def windows(report: CaseEvidenceReport) -> Dict[str, Tuple[List[str], int, int]]:
    """Comparison windows derived from the event's onset and the months the trade data covers.

    onset: onset month to the last month with data; full: the full months after onset; late: the last two
    months. Baseline is the same months one year earlier. Nothing here is specific to one event.
    """
    onset = report.event_verification.onset_date or report.case_scope.period_start
    periods = sorted({r.period for s in report.trade_series for r in s.rows if r.valid and r.period
                      and r.period <= report.as_of_date[:7]})
    if not periods:
        return {}
    year = int(periods[-1][:4])
    last_month = int(periods[-1][5:7])
    if onset and onset[:4].isdigit() and int(onset[:4]) == year:
        first = int(onset[5:7])
    else:
        first = max(1, last_month - 3)
    names = lambda a, b: [MONTHS[m - 1] for m in range(a, b + 1)]  # noqa: E731
    out = {"onset": (names(first, last_month), year - 1, year)}
    if first + 1 <= last_month:
        out["full"] = (names(first + 1, last_month), year - 1, year)
    if last_month - 1 >= first:
        out["late"] = (names(last_month - 1, last_month), year - 1, year)
    return out
