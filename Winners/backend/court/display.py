"""One citation format and one calculation layout, shared by claims, attacks, defences, rulings and the briefing."""

import re
from typing import Any, Dict, Iterable, List

from pydantic import BaseModel

_REF_PARA = re.compile(r"#P(\d+)$")


def _get(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _paragraph(e: Any) -> int:
    if _get(e, "paragraph_number"):
        return int(_get(e, "paragraph_number"))
    m = _REF_PARA.search(_get(e, "ref") or "")
    return int(m.group(1)) if m else 1


def cite(e: Any) -> str:
    """DOC_ID | Page N | Paragraph M"""
    return f"{_get(e, 'doc_id')} | Page {_get(e, 'page_number') or 1} | Paragraph {_paragraph(e)}"


def cite_group(evidence: Iterable[Any]) -> str:
    """Compact form for many citations: 'ORV-0029 | Page 1 | Paragraphs 4, 5, 6; ORV-0031 | Page 1 | Paragraph 2'."""
    groups: Dict[tuple, List[int]] = {}
    for e in evidence:
        groups.setdefault((_get(e, "doc_id"), _get(e, "page_number") or 1), []).append(_paragraph(e))
    parts = []
    for (doc, page), paras in groups.items():
        paras = sorted(set(paras))
        word = "Paragraph" if len(paras) == 1 else "Paragraphs"
        parts.append(f"{doc} | Page {page} | {word} {', '.join(map(str, paras))}")
    return "; ".join(parts)


def _as_dict(x: Any) -> dict:
    return x.model_dump() if isinstance(x, BaseModel) else x


def _num(v, unit: str = "") -> str:
    if v is None:
        return "n/a"
    return f"{v:,.2f}{unit}" if unit == "%" else f"{v:,.1f}"


def calculation_lines(assessment: Any, estimate: Any = None, indent: str = "  ") -> List[str]:
    """The full provenance of a cell's figures: rows, inputs, each metric's numerator/denominator/formula, status,
    assumptions, missing inputs, and how the range (if any) was formed."""
    if not assessment:
        return []
    a = _as_dict(assessment)
    months, b, d = a["months"], a["baseline_year"], a["disrupted_year"]
    lines = [f"{indent}CALCULATION (shared assessment; every trade row used is listed under SUPPORTING EVIDENCE):",
             f"{indent}  Route: {a['route']}   Period: {a['period']} ({a['window']} window)",
             f"{indent}  Series: primary {', '.join(a['primary_series'])}; substitute "
             f"{', '.join(a['substitute_series']) or 'none in the Case File'}"]
    table: Dict[str, Dict[str, str]] = {}
    cols: List[str] = []
    for r in sorted(a.get("breakdown", []), key=lambda r: (r["role"] != "primary", r["origin"], r["year"])):
        col = f"{r['origin']} {r['year']}"
        if col not in cols:
            cols.append(col)
        vol = f"{r['volume_t'] / 1000:,.0f}kt" if r.get("volume_t") is not None else "n/a"
        table.setdefault(r["month"], {})[col] = f"{r['value_usd_m']:.1f} / {vol}"
    if cols:
        lines.append(f"{indent}    {'Month':<8}" + "".join(f"{c:>20}" for c in cols) + "   (USD M / tonnes)")
        for m in months:
            lines.append(f"{indent}    {m[:3]:<8}" + "".join(f"{table.get(m, {}).get(c, '-'):>20}" for c in cols))
    lines.append(f"{indent}  Inputs:")
    for q in a["quantities"].values():
        src = f"; rows {', '.join(q['rows'])}" if q.get("rows") else ""
        src += f"; sources {'; '.join(q['sources'])}" if q.get("sources") else ""
        note = f" - {q['note']}" if q.get("note") else ""
        lines.append(f"{indent}    {q['name']:<28} {_num(q['value']):>12} {q['unit']:<7} [{q['status']}] "
                     f"{q.get('period', '')}{note}{src}")
    lines.append(f"{indent}  Metrics:")
    for m in a["metrics"].values():
        value = _num(m["value"], "%") if m["value"] is not None else m["status"]
        lines.append(f"{indent}    {m['label']}: {value}  ({m['unit']})")
        lines.append(f"{indent}      = {m['formula']}   numerator {m['numerator']}, denominator {m['denominator']}")
        for x in m.get("assumptions", []):
            lines.append(f"{indent}      assumption: {x}")
        for x in m.get("missing_inputs", []):
            lines.append(f"{indent}      missing input: {x}")
    sub = a["substitution"]
    lines.append(f"{indent}  Substitution: {sub['status']} - {sub['note']}"
                 + (f" (reported in {'; '.join(sub['sources'])})" if sub.get("sources") else ""))
    lines.append(f"{indent}  Range (net exposure, % of baseline route value): "
                 f"{fmt_span((a['low'], a['high']), 2)}. {a['range_basis']}")
    for x in a.get("sensitivity", []):
        lines.append(f"{indent}  Sensitivity only (not a bound): {x['window']} period {x['period']}: route value "
                     f"decline {_num(x.get('route_value_decline'), '%')}")
    for x in a.get("assumptions", []):
        lines.append(f"{indent}  Assumption: {x}")
    if a.get("rows_flagged"):
        lines.append(f"{indent}  Flagged rows left out: {', '.join(a['rows_flagged'])}")
    if estimate is not None:
        lines.append(f"{indent}  Filed estimate: {fmt_estimate(estimate)}")
    return lines


def fmt_span(span, digits: int = 1) -> str:
    """'a-b%', 'up to b% (no lower bound on the record)', 'b%' for a point, '-' for nothing."""
    if not span or span[1] is None:
        return "-"
    lo, hi = span
    if lo is None:
        return f"up to {hi:.{digits}f}% (no lower bound on the record)"
    if abs(lo - hi) < 0.005:
        return f"{hi:.{digits}f}%"
    return f"{lo:.{digits}f}-{hi:.{digits}f}%"


def fmt_estimate(est) -> str:
    if not est:
        return "no estimate"
    est = _as_dict(est)
    return f"{fmt_span((est.get('low'), est.get('high')), 2)} [{est.get('metric')}]"


def position(est) -> str:
    """A side's position in words: its net-exposure span, its scenario, or the metric it accepts."""
    if not est:
        return "no figure filed"
    e = _as_dict(est)
    if e.get("metric") == "net_exposure":
        if e.get("scenario") == "recorded_substitution":
            return f"{e['low']:.2f}% net exposure (recorded-substitution scenario)"
        return f"{fmt_span((e.get('low'), e.get('high')), 2)} net exposure"
    value = e.get("high") if e.get("high") is not None else e.get("low")
    label = e.get("metric", "").replace("_", " ")
    return f"{label} {value:.2f}% (measured); {e.get('basis') or 'no net figure'}"
