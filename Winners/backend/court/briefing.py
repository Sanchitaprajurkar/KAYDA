"""Odin's briefing, written only from his rulings table (FR4.4, FR8). No LLM: every sentence traces to a ruling."""

from typing import Dict, List

from backend.court.heimdall_bridge import CaseEvidenceReport
from backend.court.display import calculation_lines, case_header, cite, fmt_span
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
                               "CONCEDED": [], "REJECTED": [], "NOT_PRESSED": [], "INSUFFICIENT": []}
    for r in final.rulings:
        groups[r.classification].append((r, claims[r.claim_id]))
    v = report.event_verification
    status = "COMPLETE" if complete else "INCOMPLETE"
    analysis = final.analytical_status or "INSUFFICIENT"
    props = final.propositions
    counts = {k: sum(1 for p in props if p.classification == k)
              for k in ("ESTABLISHED", "REJECTED", "CONTESTED", "INSUFFICIENT")}
    lines = [f"# Briefing: {report.target_query}", "",
             f"Case `{report.case_id}` | as of {report.as_of_date} | runs: {len(runs)} | execution: **{status}** | "
             f"analysis: **{analysis}**", "",
             "> Execution says whether the courtroom workflow ran to the end. Analysis says whether the question is "
             "answered: COMPLETE (every requirement decided), PARTIAL (some decided), INSUFFICIENT (the evidence "
             "cannot answer it).", ""]
    header = case_header(report)
    lines += ["## Case File", "", "| Field | Value |", "|---|---|"]
    lines += [f"| {k} | {x} |" for k, x in header.items()]
    lines.append("")
    if not complete:
        lines += ["**The workflow did not complete:** " + "; ".join(reasons), ""]
    if final.completeness:
        lines += ["**Requirements without a ruling:** " + "; ".join(final.completeness), ""]

    from backend.agents.odin.agent import Odin
    outcome = Odin.outcome(final.rulings, final.claims, report)
    lines += [f"**Verdict: {outcome['verdict']}**", "",
              "> Scored from Odin's rulings on each side's arguments: +1 upheld, -1 rejected or withdrawn; contested "
              "arguments and positions not pressed score nothing.", ""]

    lines += ["## Executive summary", "",
              f"- Broader event: **{v.status.value}**{', still in effect at the as-of date' if v.is_active_at_as_of else ''}. "
              f"{v.summary}"]
    for p in props:
        if p.kind != "EXPOSURE":
            lines.append(f"- {p.prop_id} **{p.classification}**: {p.proposition} {p.reasoning.split(' Advocates:')[0]}")
    if props:
        lines.append(f"- Propositions ruled: {len(props)} - {counts['ESTABLISHED']} established, {counts['REJECTED']} "
                     f"rejected, {counts['CONTESTED']} contested, {counts['INSUFFICIENT']} insufficient.")
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
    lines.append(f"- Advocate claims: {len(final.rulings)} ruled - {len(groups['NOT_PRESSED'])} not pressed, "
                 f"{len(groups['CONCEDED'])} conceded (advocate actions, not findings).")
    open_gaps = final.open_gaps
    if open_gaps:
        lines.append("- Open gaps (searched for; the record does not answer them): " + "; ".join(open_gaps) + ".")
    lines.append("")

    if props:
        lines += ["## Proposition rulings", "",
                  "> Odin's own ruling on each proposition, made from the evidence whatever the advocates pressed or "
                  "conceded. Qualifying records establish neither the proposition nor its negation; absence of "
                  "evidence is INSUFFICIENT, not REJECTED.", ""]
        for p in props:
            origin = {"part": f" (separate part of the allegation in {p.derived_from})",
                      "consequence": f" (operational consequence derived from {p.derived_from})"}.get(p.derivation, "")
            lines += [f"### {p.prop_id}: {p.proposition}{origin}", "",
                      f"- **Ruling: {p.classification}** (confidence {p.confidence.level}: {p.confidence.explanation})",
                      f"- Reasoning: {p.reasoning}"]
            for label, refs in (("Supporting", p.supporting), ("Contradicting", p.contradicting),
                                ("Qualifying (neither side)", p.qualifying), ("Set aside before trial", p.set_aside)):
                if refs:
                    lines.append(f"- {label}:")
                    for r in refs:
                        quote = r.quote_or_value.strip()[:240]
                        lines.append(f"  - `{r.source_id} | {r.locator.label()}` \"{quote}\" - shows "
                                     f"{r.establishes}; does not establish {r.does_not_establish or '-'}")
            if p.limitations:
                lines.append("- Limitations: " + "; ".join(p.limitations))
            if p.attribution:
                lines.append(f"- Attribution: {p.attribution}")
            if p.kind != "EXPOSURE" and p.deception:
                lines.append(f"- Deception: {p.deception}")
            if p.needs_investigation:
                lines.append(f"- Further investigation needed: {p.evidence_gap} Would resolve it: "
                             f"{p.evidence_needed}. {p.reinvestigation}")
            lines.append("")

    titles = {"ESTABLISHED": "Established findings",
              "PARTLY_ESTABLISHED": "Partly established findings (the measured fact stands; the conclusion does not)",
              "CONTESTED": "Contested findings",
              "UNCONTESTED": "Unchallenged findings (cannot be Established)", "CONCEDED": "Conceded findings",
              "REJECTED": "Rejected claims",
              "INSUFFICIENT": "Arguments on propositions the evidence cannot decide",
              "NOT_PRESSED": "Positions not pressed (nothing in the Case File carries them; not a finding)"}
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
    return {"status": status, "analytical_status": analysis, "outcome": outcome, "case_file": header,
            "propositions": [p.model_dump() for p in props],
            "reasons": reasons, "markdown": "\n".join(lines) + "\n",
            "exposure": [r.model_dump() for r in final.ranges],
            "findings": {k: [r.model_dump() for r, _ in g] for k, g in groups.items()}}
