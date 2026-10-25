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


def calculation_lines(calculations: List[Any], estimate: Any, indent: str = "  ") -> List[str]:
    """The arithmetic behind a calculation claim: per-month rows, totals, and how the low/high bounds are chosen."""
    calcs = [_as_dict(c) for c in calculations]
    if not calcs:
        return []
    est = _as_dict(estimate)
    lines = [f"{indent}CALCULATION (TradeCalculator; every trade row used is listed under SUPPORTING EVIDENCE):"]
    for k in calcs:
        months = k["months"]
        b, d = k["baseline_year"], k["disrupted_year"]
        lines.append(f"{indent}  Window \"{k['window']}\": {', '.join(m[:3] for m in months)} {d} vs the same months of {b}")
        cols: List[str] = []
        table: Dict[str, Dict[str, Any]] = {}
        for row in sorted(k.get("breakdown", []), key=lambda r: (r["role"] != "primary", r["origin"], r["year"])):
            col = f"{row['origin']} {row['year']}"
            if col not in cols:
                cols.append(col)
            table.setdefault(row["month"], {})[col] = row["value_usd_m"]
        if cols:
            lines.append(f"{indent}    {'Month':<10}" + "".join(f"{c:>16}" for c in cols) + "   (USD M)")
            for m in months:
                vals = table.get(m, {})
                lines.append(f"{indent}    {m[:3]:<10}" + "".join(
                    f"{vals[c]:>16.1f}" if c in vals else f"{'-':>16}" for c in cols))
            lines.append(f"{indent}    {'Total':<10}" + "".join(
                f"{sum(table.get(m, {}).get(c, 0.0) for m in months):>16.1f}" for c in cols))
        origins = "/".join(k["origins"])
        base, gross = k["baseline_usd_m"], k["gross_loss_usd_m"]
        sub_gain, net, basket = k["substitute_gain_usd_m"], k["net_loss_usd_m"], k["import_baseline_usd_m"]
        lines += [
            f"{indent}    Gross loss       = {origins} {b} - {origins} {d} = {base:.1f} - {base - gross:.1f} = {gross:.1f}",
            f"{indent}    Substitute gain  = substitutes {d} - substitutes {b} = {sub_gain:.1f}"
            + ("" if k.get("substitute_series") else "  (no substitute series on the record)"),
            f"{indent}    Net loss         = gross - substitute gain = {gross:.1f} - {sub_gain:.1f} = {net:.1f}",
            f"{indent}    Import basket    = all suppliers, {b} = {basket:.1f}",
            f"{indent}    Net / basket     = {net:.1f} / {basket:.1f} = {k['net_import_loss_pct']:.2f}%",
            f"{indent}    Gross / basket   = {gross:.1f} / {basket:.1f} = {k['gross_import_loss_pct']:.2f}%",
            f"{indent}    Gross / {origins} baseline = {gross:.1f} / {base:.1f} = {k['gross_loss_pct']:.2f}%",
        ]
        if k.get("rows_flagged"):
            lines.append(f"{indent}    Flagged rows left out: {', '.join(k['rows_flagged'])}")
    low_src = min(calcs, key=lambda k: abs(k["net_import_loss_pct"] - est["low"]))
    high_src = min(calcs, key=lambda k: abs(k["gross_import_loss_pct"] - est["high"]))
    lines.append(f"{indent}  Range: low {est['low']:.2f}% = net / basket (window \"{low_src['window']}\"); "
                 f"high {est['high']:.2f}% = gross / basket (window \"{high_src['window']}\").")
    premium = max(k.get("premium_pct", 0.0) for k in calcs)
    if premium:
        lines.append(f"{indent}  The {premium:g}% spot-price premium is a separate observation and is in neither bound.")
    return lines
