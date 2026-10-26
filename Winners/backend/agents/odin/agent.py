"""Odin, the judge. Rules on every claim, classifies findings, sets the range, checks sufficiency.

Odin has no search tool: he reads the Case File and the record, verifies citations and recomputes numbers.
Deterministic checks rule first; only claims that were attacked and defended reach his one LLM call per run.
"""

import re
from typing import Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel

from backend.agents.odin.prompts import ODIN_SYSTEM_PROMPT
from backend.court.heimdall_bridge import CaseEvidenceReport
from backend.court.llm import BudgetExceeded, CourtLLM
from backend.court.memory import AgentMemory
from backend.court.display import cite, cite_group, fmt_estimate, position
from backend.court.exposure import numeric_claim_defect
from backend.court.models import (AVAILABLE, CONFIRMED_ZERO, NET_EXPOSURE, ROUTE_VALUE_DECLINE, ROUTE_VOLUME_DECLINE,
                                  Attack, CellRange, Claim, Finding, ResearchOutcome, Response, Ruling, RunRecord)
from backend.court.tools import RunemarkTools, citation_scope_defect, offers_new_trade_rows


class OdinRuling(BaseModel):
    claim_id: str
    ruling: Literal["UPHELD", "REJECTED", "CONTESTED"]
    nature: Literal["SOURCED_FACT", "INFERENCE"]
    reason: str


class OdinRulings(BaseModel):
    rulings: List[OdinRuling]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\.\.\.$|…$", "", (text or "").strip())).lower()


class Odin:
    def __init__(self, tools: RunemarkTools, llm: CourtLLM, memory: AgentMemory, log: Callable[..., None]):
        self.tools = tools
        self.llm = llm
        self.memory = memory
        self.log = log

    # -- deterministic checks ---------------------------------------------------
    def checks(self, claim: Claim, report: CaseEvidenceReport) -> List[str]:
        failed = []
        for e in claim.citations:
            if not self.tools.admissible(e.doc_id):
                failed.append(f"{cite(e)} is not admissible evidence at {report.as_of_date}")
                continue
            if (e.pub_date or "9999") > report.as_of_date:
                failed.append(f"{cite(e)} is dated after the as-of date")
            if e.kind == "trade_row":
                s = self.tools.series(e.doc_id)
                row = next((r for r in (s.rows if s else []) if r.row_id == e.ref), None)
                if not row or not row.valid:
                    failed.append(f"trade row {cite(e)} is missing or flagged")
            elif e.excerpt:
                body = " ".join(t for _, t in self.tools.store.body_paragraphs(e.doc_id))
                if _norm(e.excerpt)[:60] not in _norm(body):
                    failed.append(f"quote for {cite(e)} is not in the document")
        defect = numeric_claim_defect(self.tools, report, claim)
        if defect:
            failed.append(defect[1])
        scope = citation_scope_defect(self.tools, claim)
        if scope:
            failed.append(scope[1])
        return failed

    def validation(self, claim: Claim, report: CaseEvidenceReport) -> List[str]:
        """What Odin checked himself, stated for every claim that passed: being unchallenged proves nothing."""
        rows = [e for e in claim.citations if e.kind == "trade_row"]
        paras = [e for e in claim.citations if e.kind != "trade_row"]
        out = [f"{len(claim.citations)} citation(s) admissible and dated on or before {report.as_of_date}"]
        if rows:
            out.append(f"{len(rows)} trade row(s) present and unflagged in {', '.join(sorted({e.doc_id for e in rows}))}")
        if paras:
            out.append(f"{len(paras)} quoted paragraph(s) found verbatim in their documents and naming "
                       f"{claim.country} or {claim.sector}")
        a = claim.assessment
        if claim.kind == "calculation" and a:
            q = a.quantities
            bv, dv = q["route_baseline_value"].value, q["route_disrupted_value"].value
            rv = a.metrics[ROUTE_VALUE_DECLINE].value
            out.append(f"recomputed from the rows: ({bv:,.1f} - {dv:,.1f}) / {bv:,.1f} = {rv:.2f}% route value decline "
                       f"({a.period})")
        if claim.estimate:
            out.append(f"filed figure {fmt_estimate(claim.estimate)} matches what that metric yields on the record")
        return out

    @staticmethod
    def findings(claim: Claim) -> List[Finding]:
        """A calculation's conclusions, each ruled on its own: the route decline is measured; net exposure is
        established only when substitute supply is measured."""
        a = claim.assessment
        if claim.kind != "calculation" or not a or not claim.estimate:
            return []
        out = []
        rv, rt = a.metrics[ROUTE_VALUE_DECLINE], a.metrics[ROUTE_VOLUME_DECLINE]
        if rv.value is not None:
            out.append(Finding(metric=ROUTE_VALUE_DECLINE, value=rv.value, established=True,
                               statement=f"Trade value on {a.route} fell by {rv.value:.2f}% ({a.period}).",
                               reason="Measured: recomputes exactly from the validated trade rows."))
        if rt.value is not None:
            out.append(Finding(metric=ROUTE_VOLUME_DECLINE, value=rt.value, established=True,
                               statement=f"Trade volume on {a.route} fell by {rt.value:.2f}% ({a.period}).",
                               reason="Measured: recomputes exactly from the validated trade rows."))
        if claim.estimate.metric == NET_EXPOSURE:
            net = a.metrics[NET_EXPOSURE]
            if net.status == AVAILABLE:
                out.append(Finding(metric=NET_EXPOSURE, value=net.value, established=True,
                                   statement=f"Net exposure after recorded substitution is {net.value:.2f}% of the "
                                             f"route's baseline value.",
                                   reason=f"Substitution is measured ({a.substitution.note})."))
            else:
                out.append(Finding(
                    metric=NET_EXPOSURE, value=None, established=False,
                    statement=f"{a.country}'s net loss of {a.sector.lower()} supply after substitution.",
                    reason=f"Not established: substitution is {a.substitution.status} ({a.substitution.note}). The "
                           f"route decline does not show how much of the loss was replaced, so "
                           f"{rv.value:.2f}% stands only as the no-substitution upper bound, not as the net loss."))
        return out

    _new_trade_rows = staticmethod(offers_new_trade_rows)

    @staticmethod
    def _default_nature(claim: Claim) -> str:
        if claim.kind == "calculation":
            return "INFERENCE"
        return "SOURCED_FACT" if all(e.assertion in ("CONFIRMED", "REPORTED", "CORRECTED") for e in claim.citations) \
            else "INFERENCE"

    # -- rulings ----------------------------------------------------------------
    def rule(self, report: CaseEvidenceReport, claims: List[Claim], attacks: List[Attack],
             responses: List[Response], side_failures: Dict[str, str]) -> List[Ruling]:
        answers = {r.attack_id: r for r in responses}
        by_target: Dict[str, List[Attack]] = {}
        for a in attacks:
            # An attack the owner answered by narrowing to exactly what the attacker said the data supports is spent.
            if answers.get(a.attack_id) and answers[a.attack_id].decision == "NARROWED":
                continue
            by_target.setdefault(a.target_claim_id, []).append(a)
        rulings: Dict[str, Ruling] = {}
        pending = []
        for c in claims:
            opponent_failed = ("LOKI" if c.side == "THOR" else "THOR") in side_failures
            if c.status == "CONCEDED":
                rulings[c.claim_id] = Ruling(claim_id=c.claim_id, side=c.side, run=c.run, ruling="CONCEDED",
                                             nature=self._default_nature(c), classification="CONCEDED",
                                             reason="Withdrawn by its owner in cross-examination.")
                continue
            failed = self.checks(c, report)
            if failed:
                rulings[c.claim_id] = Ruling(claim_id=c.claim_id, side=c.side, run=c.run, ruling="REJECTED",
                                             nature=self._default_nature(c), classification="REJECTED",
                                             reason="Failed verification: " + "; ".join(failed[:3]),
                                             failed_checks=failed)
                continue
            narrowed = (f" Narrowed in cross-examination from {fmt_estimate(c.narrowed_from)}; ruled as narrowed."
                        if c.narrowed_from else "")
            if not by_target.get(c.claim_id):
                rulings[c.claim_id] = Ruling(
                    claim_id=c.claim_id, side=c.side, run=c.run, ruling="UPHELD", nature=self._default_nature(c),
                    classification="UNCONTESTED" if opponent_failed else self._classify("UPHELD", c),
                    reason="Passed independent validation" + ("; the other side failed, so it went unchallenged."
                                                              if opponent_failed else "; no live attack.") + narrowed)
                continue
            if c.kind == "calculation" and not any(self._new_trade_rows(a, c) for a in by_target[c.claim_id]):
                # Verified arithmetic over trade rows; only other trade data could overturn the arithmetic.
                rulings[c.claim_id] = Ruling(
                    claim_id=c.claim_id, side=c.side, run=c.run, ruling="UPHELD", nature="INFERENCE",
                    classification=self._classify("UPHELD", c),
                    reason="Arithmetic recomputes exactly from the trade rows; the attacks offered no other trade "
                           "data against it." + narrowed)
                continue
            pending.append(c)

        decided = self._llm_rulings(report, pending, by_target, answers) if pending else {}
        for c in pending:
            r = decided.get(c.claim_id) or self._fallback(c, by_target[c.claim_id], answers)
            ruling, nature, reason, by = r
            rulings[c.claim_id] = Ruling(claim_id=c.claim_id, side=c.side, run=c.run, ruling=ruling, nature=nature,
                                         classification=self._classify(ruling, c), reason=reason, decided_by=by)
        for c in claims:
            r = rulings[c.claim_id]
            if r.ruling not in ("UPHELD", "CONTESTED"):
                continue
            r.validation = self.validation(c, report)
            r.findings = self.findings(c)
            r.reason += " Checked: " + "; ".join(r.validation) + "."
            unproven = [f for f in r.findings if not f.established]
            if unproven:
                # The same test for both sides: arithmetic that recomputes proves the measured fact, not the
                # conclusion drawn from it.
                if r.classification == "ESTABLISHED":
                    r.classification = "PARTLY_ESTABLISHED"
                proven = [f for f in r.findings if f.established]
                r.reason += (" Established: " + " ".join(f.statement for f in proven) if proven else "") + \
                    " Not established: " + " ".join(f"{f.statement} {f.reason}" for f in unproven)
        out = [rulings[c.claim_id] for c in claims]
        for c, r in zip(claims, out):
            self.log("ruling", agent="ODIN", ruling=r.model_dump(), sources=cite_group(c.citations))
        return out

    @staticmethod
    def _classify(ruling: str, claim: Claim) -> str:
        if ruling == "UPHELD":
            return "ESTABLISHED" if all(e.tier <= 2 for e in claim.citations) else "CONTESTED"
        return {"REJECTED": "REJECTED", "CONTESTED": "CONTESTED", "CONCEDED": "CONCEDED"}[ruling]

    def _fallback(self, c: Claim, attacks: List[Attack], answers: Dict[str, Response]) -> Tuple[str, str, str, str]:
        defended = all(answers.get(a.attack_id) and answers[a.attack_id].decision == "DEFENDED" for a in attacks)
        if c.kind == "calculation" and defended and not any(self._new_trade_rows(a, c) for a in attacks):
            return ("UPHELD", "INFERENCE", "Recomputes exactly from the trade rows; the attack offered no trade data "
                                           "against it.", "rules")
        stronger = any(e.tier < min(x.tier for x in c.citations) for a in attacks for e in a.counter_evidence)
        if defended:
            return "CONTESTED", self._default_nature(c), "Attacked and defended with new evidence.", "rules"
        if stronger:
            return "REJECTED", self._default_nature(c), "Countered by a more reliable source.", "rules"
        return "CONTESTED", self._default_nature(c), "Credible evidence on both sides.", "rules"

    def _llm_rulings(self, report, pending: List[Claim], by_target, answers) -> Dict[str, Tuple[str, str, str, str]]:
        precedents = self.memory.by_category("precedent")
        if precedents:
            self.log("memory_read", agent="ODIN", key="precedent:*",
                     influenced=f"{len(precedents)} precedent(s) put before the ruling")
        conflicts = {}
        for k in report.contradictions:
            if k.fact_a and k.fact_b:
                conflicts.setdefault(k.fact_a.fact_id, []).append(k.fact_b.statement[:140])
                conflicts.setdefault(k.fact_b.fact_id, []).append(k.fact_a.statement[:140])
        blocks = []
        for c in pending:
            lines = [f"CLAIM {c.claim_id} ({c.side}, {c.kind}, {c.country}|{c.sector}, "
                     f"{fmt_estimate(c.estimate)}): {c.statement}",
                     "  cites: " + "; ".join(f"{cite(e)} Tier {e.tier} {e.assertion or ''} \"{e.excerpt[:120]}\""
                                             for e in c.citations[:4])]
            for e in c.citations:
                for other in conflicts.get(e.fact_id or "", [])[:1]:
                    lines.append(f"  Heimdall flagged {cite(e)} as contradicted by: \"{other}\"")
            for a in by_target[c.claim_id]:
                lines.append(f"  ATTACK {a.attack_id} by {a.attacker}: {a.reason} - {a.argument} | counter: " +
                             "; ".join(f"{cite(e)} Tier {e.tier} \"{e.excerpt[:120]}\"" for e in a.counter_evidence))
                ans = answers.get(a.attack_id)
                if ans:
                    lines.append(f"  ANSWER: {ans.decision} - {ans.explanation} | new: " +
                                 "; ".join(f"{cite(e)} Tier {e.tier} \"{e.excerpt[:120]}\"" for e in ans.new_evidence))
            blocks.append("\n".join(lines))
        prompt = ("Precedents from earlier rulings:\n" + "\n".join(
            f"- {p['key'].split(':', 1)[1]} -> {p['value']}" for p in precedents[:6]) + "\n\n" if precedents else "") \
            + "All claims below passed the citation and number checks. Rule on each.\n\n<document_data>\n" \
            + "\n\n".join(blocks) + "\n</document_data>"
        try:
            result = self.llm.ask(ODIN_SYSTEM_PROMPT, prompt, OdinRulings)
        except BudgetExceeded as e:
            self.log("limit_hit", agent="ODIN", limit="tokens", detail=str(e))
            return {}
        except Exception as e:
            self.log("error", agent="ODIN", detail=f"LLM ruling failed, rules decide: {e}")
            return {}
        out = {}
        claims = {c.claim_id: c for c in pending}
        for r in result.rulings:
            if r.claim_id in claims:
                out[r.claim_id] = (r.ruling, r.nature, r.reason, "odin")
                c = claims[r.claim_id]
                reasons = sorted({a.reason for a in by_target[c.claim_id]})
                key = f"{'+'.join(reasons)}:{c.kind}:tier{min(e.tier for e in c.citations)}:{r.nature.lower()}"
                self.memory.write(f"precedent:{key}", "precedent", f"{r.ruling} ({r.reason[:120]})",
                                  report.case_id)
        return out

    # -- range ------------------------------------------------------------------
    def ranges(self, report: CaseEvidenceReport, claims: List[Claim], rulings: List[Ruling]) -> List[CellRange]:
        """Odin's own assessment per cell, recomputed from the Case File; given only if a calculation survived."""
        ruled = {r.claim_id: r for r in rulings}
        out = []
        for cell in report.coverage_map:
            r = CellRange(country=cell.country, sector=cell.sector, status=cell.status)
            for c in claims:
                if c.kind == "calculation" and c.estimate and (c.country, c.sector) == (cell.country, cell.sector):
                    r.positions[c.side] = position(c.estimate)
                    if c.estimate.metric != NET_EXPOSURE:
                        continue
                    span = (c.estimate.low, c.estimate.high)
                    if c.side == "THOR":
                        r.thor = span
                    else:
                        r.loki = span
            if cell.status != "COVERED":
                r.basis = "Evidence missing: no trade series for this flow; no figure is given."
                out.append(r)
                continue
            a = self.tools.assessment(report, cell)
            if a:
                r.period = a.period
                r.metrics = {k: m.value for k, m in a.metrics.items()}
                r.metric_status = {k: m.status for k, m in a.metrics.items()}
                r.substitution = f"{a.substitution.status}: {a.substitution.note}"
            surviving = [c for c in claims if c.kind == "calculation" and (c.country, c.sector) ==
                         (cell.country, cell.sector) and ruled[c.claim_id].ruling in ("UPHELD", "CONTESTED")]
            if not surviving or not a or a.high is None:
                r.basis = ("No calculation survived the trial." if a else
                           "The trade rows do not cover both years of any period; no figure is given.")
                out.append(r)
                continue
            classes = [ruled[c.claim_id].classification for c in surviving]
            r.odin = (a.low, a.high)
            r.odin_classification = "CONTESTED" if "CONTESTED" in classes else "ESTABLISHED"
            sens = "; ".join(f"{x['window']} {x['period']}: {x['route_value_decline']}%" for x in a.sensitivity
                             if x.get("route_value_decline") is not None)
            r.basis = (f"Net exposure on {a.route}, {a.period}, % of baseline route value. {a.range_basis}"
                       + (f" Other periods (sensitivity only, not bounds): {sens}." if sens else ""))
            out.append(r)
        return out

    # -- sufficiency ------------------------------------------------------------
    def sufficiency(self, report: CaseEvidenceReport, claims: List[Claim],
                    rulings: List[Ruling]) -> Tuple[List[str], List[str]]:
        """(gaps worth one more search, gaps already searched for and still open). Missing data the corpus may simply
        not hold is reported as an open gap, not chased forever, and never dropped as if it had been answered."""
        ruled = {r.claim_id: r for r in rulings}
        asked_substitutes = any(re.search(r"substitut", h.request, re.I) for h in report.research_history)
        case_docs = {d.doc_id for d in report.retrieved_documents}
        record_docs = {d.doc_id: d for d in report.retrieved_documents}
        missing, still_open = [], []
        for cell in report.coverage_map:
            label = f"{cell.country} {cell.sector}"
            calcs = [c for c in claims if c.kind == "calculation" and (c.country, c.sector) ==
                     (cell.country, cell.sector)]
            if cell.status == "COVERED":
                a = self.tools.assessment(report, cell)
                if a and a.high is not None and not any(
                        ruled[c.claim_id].classification in ("ESTABLISHED", "PARTLY_ESTABLISHED") for c in calcs):
                    missing.append(f"{label}: no established trade-row finding")
                if a and a.substitution.status not in (AVAILABLE, CONFIRMED_ZERO):
                    gap = f"{label}: net effect of substitute supply is not in the Case File"
                    (still_open if asked_substitutes else missing).append(gap)
                for c in calcs:
                    extra = [d for d in c.requests if d not in case_docs]
                    if extra and ruled[c.claim_id].ruling in ("UPHELD", "CONTESTED"):
                        missing.append(f"{label}: substitute trade series {', '.join(extra)} cited by {c.side} "
                                       f"are not in the Case File")
            else:
                profile = any(d.source_type == "atlas" and cell.country.lower() in (d.title or "").lower()
                              for d in record_docs.values())
                if not profile:
                    missing.append(f"{label}: evidence gap not yet checked against the {cell.country} reference "
                                   f"sheet")
        return list(dict.fromkeys(missing)), list(dict.fromkeys(still_open))

    def research_outcomes(self, report: CaseEvidenceReport, asked: List[str], record: RunRecord) -> List[ResearchOutcome]:
        """For each gap sent back, did the re-search answer it? Judged by what the record now shows, not by how many
        documents came back."""
        new = list(report.new_document_ids)
        live = {r.claim_id for r in record.rulings if r.ruling in ("UPHELD", "CONTESTED")}
        cited = {e.doc_id for c in record.claims if c.claim_id in live for e in c.citations}
        cited |= {e.doc_id for x in record.responses if x.decision == "DEFENDED" for e in x.new_evidence}
        used = [d for d in new if d in cited]
        cells = {f"{c.country} {c.sector}": c for c in report.coverage_map}
        out = []
        for gap in asked:
            label, _, need = gap.partition(":")
            unresolved = gap in record.remand or gap in record.open_gaps
            cell = cells.get(label.strip())
            a = self.tools.assessment(report, cell) if cell else None
            if "substitute supply" in need and a:
                bearing = [s.split(" | ")[0] for s in a.substitution.sources if s.split(" | ")[0] in new]
                detail = (f"substitution is still {a.substitution.status} ({a.substitution.note})"
                          + (f"; new document(s) {', '.join(bearing)} report it but give no measurement" if bearing
                             else "; none of the new documents measures or reports substitute supply for this cell")
                          if unresolved else f"substitution is now {a.substitution.status} ({a.substitution.note})")
            elif "trade-row finding" in need:
                detail = ("still no established trade-row finding" if unresolved else
                          "a trade-row finding is now established" + ("" if used else
                          " by ruling on the rows already in the Case File, not because of the new documents"))
            else:
                detail = "the gap is still open" if unresolved else "the gap is closed"
            if not new:
                detail += "; the re-search found no new admissible documents"
            elif not used:
                detail += f"; none of the {len(new)} new document(s) is cited by a surviving claim"
            else:
                detail += f"; new document(s) cited by surviving claims: {', '.join(used)}"
            out.append(ResearchOutcome(gap=gap, resolved=not unresolved, new_documents=new, used_documents=used,
                                       explanation=f"{'Resolved' if not unresolved else 'Not resolved'}: {detail}."))
        return out
