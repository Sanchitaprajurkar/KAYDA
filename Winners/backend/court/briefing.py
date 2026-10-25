"""Odin's briefing, written only from his rulings table (FR4.4, FR8). No LLM: every sentence traces to a ruling."""

from typing import Dict, List

from backend.court.heimdall_bridge import CaseEvidenceReport
from backend.court.models import CellRange, Claim, Evidence, RunRecord
from backend.court.tools import windows


def _cite(e: Evidence) -> str:
    stamp = f"{e.pub_date} {e.pub_time}" if e.pub_time else (e.pub_date or "")
    return f"[{e.ref}, {stamp}]"


def _span(s) -> str:
    return f"{s[0]:.1f}-{s[1]:.1f}%" if s else "-"


def write_briefing(report: CaseEvidenceReport, runs: List[RunRecord], complete: bool, reasons: List[str]) -> Dict:
    final = runs[-1]
    claims = {c.claim_id: c for c in final.claims}
    groups: Dict[str, List] = {"ESTABLISHED": [], "CONTESTED": [], "UNCONTESTED": [], "CONCEDED": [], "REJECTED": []}
    for r in final.rulings:
        groups[r.classification].append((r, claims[r.claim_id]))
    v = report.event_verification
    status = "COMPLETE" if complete else "INCOMPLETE"
    lines = [f"# Briefing: {report.target_query}", "",
             f"Case `{report.case_id}` | as of {report.as_of_date} | runs: {len(runs)} | status: **{status}**", ""]
    if not complete:
        lines += ["**This case is not complete:** " + "; ".join(reasons), ""]

    lines += ["## Executive summary", "",
              f"- Event: **{v.status.value}**{', still in effect at the as-of date' if v.is_active_at_as_of else ''}. "
              f"{v.summary}"]
    for rng in final.ranges:
        if rng.status != "COVERED":
            lines.append(f"- {rng.country} {rng.sector}: evidence missing; no range is given.")
        elif rng.odin:
            lines.append(f"- {rng.country} {rng.sector}: Odin's range **{_span(rng.odin)}** fall in import value "
                         f"(Thor {_span(rng.thor)}, Loki {_span(rng.loki)}).")
        else:
            lines.append(f"- {rng.country} {rng.sector}: unresolved; {rng.basis}")
    lines.append(f"- Findings: {len(groups['ESTABLISHED'])} established, {len(groups['CONTESTED'])} contested, "
                 f"{len(groups['CONCEDED'])} conceded, {len(groups['REJECTED'])} rejected.")
    lines.append("")

    titles = {"ESTABLISHED": "Established findings", "CONTESTED": "Contested findings",
              "UNCONTESTED": "Unchallenged findings (cannot be Established)", "CONCEDED": "Conceded findings",
              "REJECTED": "Rejected claims"}
    for key, title in titles.items():
        if not groups[key]:
            continue
        lines += [f"## {title}", ""]
        for r, c in groups[key]:
            nature = "Sourced fact" if r.nature == "SOURCED_FACT" else "Inference"
            lines.append(f"- **{c.claim_id}** ({c.side}, {nature}) {c.statement} "
                         + " ".join(_cite(e) for e in c.citations[:3])
                         + f"  \n  _Ruling: {r.ruling}. {r.reason}_")
        lines.append("")

    lines += ["## Exposure table", "", "| Country | Sector | Thor | Loki | Odin | Basis |", "|---|---|---|---|---|---|"]
    for rng in final.ranges:
        odin = _span(rng.odin) if rng.status == "COVERED" else "evidence missing"
        lines.append(f"| {rng.country} | {rng.sector} | {_span(rng.thor)} | {_span(rng.loki)} | {odin} | {rng.basis} |")
    lines.append("")

    wins = windows(report)
    late = wins.get("late")
    lines += ["## Next-quarter outlook", ""]
    if late:
        lines.append(f"If conditions at {report.as_of_date} persist, next quarter's loss stays near the latest "
                     f"months ({late[0][0]}-{late[0][-1]} {late[2]}):")
        for rng in final.ranges:
            if rng.odin:
                lines.append(f"- {rng.country} {rng.sector}: about {rng.odin[0]:.1f}-{rng.odin[1]:.1f}%.")
    lines += ["", "Assumptions: no new agreement or reopening before the next quarter "
                  f"({'none is reported as of the as-of date' if v.is_active_at_as_of else 'the event is not active'});"
                  " substitute suppliers keep their latest volumes; no document after the as-of date is used.", ""]

    unchallenged = [r for r, _ in groups["UNCONTESTED"]]
    if final.side_failures or unchallenged:
        lines += ["## Unchallenged warnings", ""]
        for side, why in final.side_failures.items():
            other = "Loki" if side == "THOR" else "Thor"
            lines.append(f"- {side.title()} failed ({why}); {other}'s claims went unchallenged.")
        lines.append("")

    lines += ["## Data-quality appendix", ""]
    for x in report.rejected_evidence:
        lines.append(f"- {x.doc_id} set aside before trial: {x.reason}"
                     + (f" (see {x.related_doc_id})" if x.related_doc_id else ""))
    flagged = [(s.doc_id, r.row_id, "; ".join(r.flags)) for s in report.trade_series for r in s.rows if not r.valid]
    for doc_id, row, why in flagged:
        lines.append(f"- Trade row {row} flagged and not used: {why}")
    for run in runs:
        lines.append(f"- Run {run.run}: {len(run.case_file_doc_ids)} documents in the Case File"
                     + (f"; new evidence {', '.join(run.new_evidence)}" if run.run > 1 else "")
                     + (f"; sent back: {'; '.join(run.remand)}" if run.remand else ""))
    lines.append("")

    sources: Dict[str, Evidence] = {}
    for c in final.claims:
        for e in c.citations:
            sources.setdefault(e.doc_id, e)
    lines += ["## Sources", ""]
    for doc_id in sorted(sources):
        e = sources[doc_id]
        lines.append(f"- {doc_id}: {e.title} ({e.source_name}, Tier {e.tier}, {e.pub_date}"
                     f"{' ' + e.pub_time if e.pub_time else ''})")
    return {"status": status, "reasons": reasons, "markdown": "\n".join(lines) + "\n",
            "exposure": [r.model_dump() for r in final.ranges],
            "findings": {k: [r.model_dump() for r, _ in g] for k, g in groups.items()}}
