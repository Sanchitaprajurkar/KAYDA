"""Odin's briefing, written only from his rulings table (FR4.4, FR8). No LLM: every sentence traces to a ruling."""

from typing import Dict, List

from backend.court.heimdall_bridge import CaseEvidenceReport
from backend.court.display import calculation_lines, cite, fmt_span
from backend.court.models import CellRange, Claim, Evidence, RunRecord
from backend.court.tools import windows


def _cite(e: Evidence) -> str:
    stamp = f"{e.pub_date} {e.pub_time}" if e.pub_time else (e.pub_date or "")
    return f"[{cite(e)} | {stamp}]"


def _span(s) -> str:
    return fmt_span(s)


def _odin_cell(rng) -> str:
    """Format the Odin column of the exposure table.

    Four distinct states:
      * Evidence missing  – status != COVERED; no trade data exists for this flow.
      * No defensible range – status == COVERED but no Odin range was computed (no calculation
        survived or the trade window returned no figures).  This is NOT zero exposure; it means
        the case record does not support a defensible quantitative estimate.
      * Contested range   – Odin computed a range but at least one of the underlying calculation
        rulings is CONTESTED (the parties disagree on a material fact).  The figure is a
        working estimate, not an established finding.
      * Established range – All surviving calculation rulings are ESTABLISHED.
    """
    if rng.status != "COVERED":
        return "evidence missing"
    if rng.odin is None:
        return "no defensible range established"
    tags = (["upper bound; net exposure not established"] if rng.odin[0] is None else []) + \
        (["contested"] if rng.odin_classification == "CONTESTED" else [])
    return _span(rng.odin) + (f" _({'; '.join(tags)})_" if tags else "")


def write_briefing(report: CaseEvidenceReport, runs: List[RunRecord], complete: bool, reasons: List[str]) -> Dict:
    final = runs[-1]
    claims = {c.claim_id: c for c in final.claims}
    groups: Dict[str, List] = {"ESTABLISHED": [], "PARTLY_ESTABLISHED": [], "CONTESTED": [], "UNCONTESTED": [],
                               "CONCEDED": [], "REJECTED": []}
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
            contested_note = (" **(contested range — see findings)**" if rng.odin_classification == "CONTESTED"
                              else "") + \
                (" **(upper bound only: substitution is not measured, so the net loss is not established)**"
                 if rng.odin[0] is None else "")
            lines.append(f"- {rng.country} {rng.sector}: Odin's range **{_span(rng.odin)}**{contested_note} net exposure, "
                         f"% of baseline route value{f' ({rng.period})' if rng.period else ''} "
                         f"(Thor {_span(rng.thor) if rng.thor else rng.positions.get('THOR', '-')}; "
                         f"Loki {_span(rng.loki) if rng.loki else rng.positions.get('LOKI', '-')}).")
        else:
            lines.append(f"- {rng.country} {rng.sector}: no defensible range established; {rng.basis}")
    lines.append(f"- Findings: {len(groups['ESTABLISHED'])} established, {len(groups['PARTLY_ESTABLISHED'])} partly "
                 f"established, {len(groups['CONTESTED'])} contested, {len(groups['CONCEDED'])} conceded, "
                 f"{len(groups['REJECTED'])} rejected.")
    open_gaps = final.open_gaps
    if open_gaps:
        lines.append("- Open gaps (searched for; the record does not answer them): " + "; ".join(open_gaps) + ".")
    lines.append("")

    titles = {"ESTABLISHED": "Established findings",
              "PARTLY_ESTABLISHED": "Partly established findings (the measured fact stands; the conclusion does not)",
              "CONTESTED": "Contested findings",
              "UNCONTESTED": "Unchallenged findings (cannot be Established)", "CONCEDED": "Conceded findings",
              "REJECTED": "Rejected claims"}
    for key, title in titles.items():
        if not groups[key]:
            continue
        lines += [f"## {title}", ""]
        for r, c in groups[key]:
            nature = "Sourced fact" if r.nature == "SOURCED_FACT" else "Inference"
            lines.append(f"- **{c.claim_id}** ({c.side}, {nature}) {c.statement} "
                         + " ".join(_cite(e) for e in c.citations[:3]))
            if c.citations:
                lines.append("  **SUPPORTING EVIDENCE:**")
                for i, e in enumerate(c.citations, 1):
                    lines.append(f"  {i}. `{cite(e)}`")
                    if e.excerpt:
                        lines.append(f'     Supporting excerpt: "{e.excerpt.strip()}"')
            if c.assessment:
                lines += ["", "  ```"] + calculation_lines(c.assessment, c.estimate) + ["  ```"]
            for f in r.findings:
                lines.append(f"  - {'Established' if f.established else 'Not established'}: {f.statement} {f.reason}")
            lines.append(f"  _Ruling: {r.ruling}. {r.reason}_\n")
        lines.append("")

    lines += ["## Exposure table", "", "| Country | Sector | Thor | Loki | Odin | Basis |", "|---|---|---|---|---|---|"]
    for rng in final.ranges:
        thor = _span(rng.thor) if rng.thor else rng.positions.get("THOR", "-")
        loki = _span(rng.loki) if rng.loki else rng.positions.get("LOKI", "-")
        lines.append(f"| {rng.country} | {rng.sector} | {thor} | {loki} | {_odin_cell(rng)} | {rng.basis} |")
    lines += ["", "## Metrics by cell", "",
              "| Country | Sector | Period | Value decline | Volume decline | Share of national imports | "
              "Substitution | Net exposure range |", "|---|---|---|---|---|---|---|---|"]
    for rng in final.ranges:
        def m(key):
            v = rng.metrics.get(key)
            return f"{v:.2f}%" if v is not None else (rng.metric_status.get(key) or "-")
        lines.append(f"| {rng.country} | {rng.sector} | {rng.period or '-'} | {m('route_value_decline')} | "
                     f"{m('route_volume_decline')} | {m('national_import_share')} | "
                     f"{(rng.substitution or '-').split(':')[0]} | {_span(rng.odin)} |")
    lines += ["",
              "> Value and volume declines are on the route itself (lost / baseline route figure). Share of national "
              "imports needs the country's total imports; UNAVAILABLE means no document states it. Net exposure "
              "low = recorded-substitution scenario, high = no-substitution scenario; 'up to' means substitution is "
              "not measured, so no lower bound exists. '-' or UNAVAILABLE is not zero.",
              "",
              "> **Odin column key**: *evidence missing* = no trade data on record for this flow; "
              "*no defensible range established* = data exists but no calculation survived the trial "
              "(this is NOT zero exposure); "
              "*X–Y% (contested)* = range computed but at least one underlying finding is contested; "
              "*up to Y% (upper bound)* = the route decline is established, but substitution is not measured, so "
              "the net loss is not; "
              "*X–Y%* = range computed from established findings.",
              ""]
    wins = windows(report)
    late = wins.get("late")
    lines += ["## Next-quarter outlook", ""]
    if late:
        lines.append(f"If conditions at {report.as_of_date} persist, next quarter's loss stays near the latest "
                     f"months ({late[0][0]}-{late[0][-1]} {late[2]}):")
        for rng in final.ranges:
            if rng.odin:
                lines.append(f"- {rng.country} {rng.sector}: about {_span(rng.odin)}.")
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
                     + (f"; retrieved {', '.join(run.new_evidence)}" if run.run > 1 else "")
                     + (f"; sent back: {'; '.join(run.remand)}" if run.remand else ""))
        for o in run.research:
            lines.append(f"  - Re-search on \"{o.gap}\": {o.explanation}")
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
