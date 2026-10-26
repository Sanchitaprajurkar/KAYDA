"""Odin, the judge. Rules on every claim, classifies findings, sets the range, checks sufficiency.

Odin has no search tool: he reads the Case File and the record, verifies citations and recomputes numbers.
Deterministic checks rule first; only claims that were attacked and defended reach his one LLM call per run.
"""

import re
from typing import Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel

from backend.agents.odin.judge import Judge, exposure_ruling
from backend.agents.odin.propositions import (DAMAGE, DAMAGE_NEEDED, allegation_parts, composite, damage_request,
                                              is_damage,
                                              is_damage_request, needs_operations, operations_items, place_of,
                                              prior_search, research_parents, route, split, untried_evidence)
from backend.agents.odin.prompts import ODIN_SYSTEM_PROMPT
from backend.court.heimdall_bridge import MAX_RUNS, CaseEvidenceReport
from backend.court.llm import BudgetExceeded, CourtLLM
from backend.court.memory import AgentMemory
from backend.court.display import cite, cite_group, fmt_estimate, position
from backend.court.exposure import numeric_claim_defect
from backend.court.models import (AVAILABLE, CONFIRMED_ZERO, NET_EXPOSURE, ROUTE_VALUE_DECLINE, ROUTE_VOLUME_DECLINE,
                                  Attack, CellRange, Claim, Finding, PropositionRuling, ResearchOutcome, Response,
                                  Ruling, RunRecord)
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
            scope = (f" and naming {claim.country} or {claim.sector}" if claim.country or claim.sector else "")
            out.append(f"{len(paras)} quoted paragraph(s) found verbatim in their documents{scope}")
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
    # -- proposition-level adjudication ------------------------------------------------------------------------
    def adjudicate(self, report: CaseEvidenceReport, claims: List[Claim], attacks: List[Attack],
                   responses: List[Response]) -> List[PropositionRuling]:
        """An independent ruling on every Heimdall proposition and every proposition an advocate argued, made from
        the evidence regardless of what the advocates pressed or conceded. Exposure propositions are decided later
        from the coverage table (adjudicate_exposure)."""
        inv = getattr(report, "investigation", None)
        self._compound: Dict[str, PropositionRuling] = {}
        self._alias: Dict[str, str] = {}
        if inv is None:
            return []
        judge = Judge(self.tools.store)
        plan = inv.spec.propositions
        sendbacks = research_parents(plan, report.research_history)
        for q, parents in sendbacks.items():
            self._alias[q] = parents[0]
        out: List[PropositionRuling] = []
        incident = getattr(inv.spec, "alleged_incident", None)
        first_at_place: Dict[str, str] = {}
        for p in plan:
            if is_damage(p) and place_of(p.text):
                first_at_place.setdefault(place_of(p.text).lower(), p.prop_id)
        for p in plan:
            if p.kind == "EXPOSURE" or p.prop_id in sendbacks:
                continue  # exposure is decided from the coverage table; send-backs are Odin's own search requests
            items = [e for e in inv.evidence if e.prop_id == p.prop_id]
            searched = [e for e in inv.evidence if p.prop_id in sendbacks.get(e.prop_id, [])]
            if is_damage(p):
                parts, n_own = allegation_parts(p, incident, plan,
                                                first_at_place.get((place_of(p.text) or "").lower()) == p.prop_id)
                parts = parts if len(parts) > 1 else []
            else:
                parts = split(p.text) if p.kind in ("INCIDENT", "EVENT") else []
                n_own = len(parts)
            ops = needs_operations(p, plan)
            if not (parts or ops or searched):
                out.append(judge.rule(p, items, claims, attacks, responses, inv.audit, case_items=inv.evidence))
                continue
            pool = items + searched
            if parts:
                subs = [(p.model_copy(update={"prop_id": f"{p.prop_id}.{i}", "text": part.text}), group, part.target)
                        for i, (part, group) in enumerate(zip(parts, route(parts, pool)), 1)]
            else:
                subs = [(p, pool, place_of(p.text) or p.text)]
            batch = []
            for i, (sp, group, target) in enumerate(subs):
                r = judge.rule(sp, group, claims, attacks, responses, inv.audit, case_items=inv.evidence,
                               argued_as=p.prop_id if i < max(n_own, 1) else sp.prop_id)
                if parts:
                    r.derived_from, r.derivation = p.prop_id, "part"
                if parts and i >= n_own:
                    r.reasoning = ("Added by Odin: the question's alleged incident includes this allegation, but no "
                                   "proposition in Heimdall's plan carries it. " + r.reasoning)
                batch.append((r, target))
            if is_damage(p):
                self._targeted_search(report, p, batch, items, searched, inv.audit)
            if parts:
                own = [r for r, _ in batch[:n_own]]
                # An advocate who argued the proposition is answered by the part(s) it actually states.
                self._compound[p.prop_id] = composite(p, own) if len(own) > 1 else own[0]
            if ops:
                batch.append((self._operations(judge, p, pool, len(subs) if parts else 0, claims, attacks,
                                               responses, inv), None))
            out += [r for r, _ in batch]
        for r in out:
            self.log("proposition_ruling", agent="ODIN", ruling=r.model_dump())
        return out

    @staticmethod
    def _operations(judge: Judge, p, pool, n_parts: int, claims, attacks, responses, inv) -> PropositionRuling:
        """The lesser proposition carried by a physical-damage allegation: operations at the site were disrupted.
        Operating records decide it; deciding it says nothing about the physical damage."""
        oid = f"{p.prop_id}.{n_parts + 1}"
        op = p.model_copy(update={"prop_id": oid, "text": f"operations at {place_of(p.text)} were disrupted",
                                  "kind": "EVENT", "attributed_to": None})
        r = judge.rule(op, operations_items(pool, oid), claims, attacks, responses, inv.audit,
                       case_items=inv.evidence)
        r.derived_from, r.derivation = p.prop_id, "consequence"
        r.reasoning = (f"Derived by Odin from {p.prop_id}: operational disruption is a separate question from "
                       f"physical damage, decided by operating records, and does not establish the damage. "
                       + r.reasoning)
        r.limitations = list(dict.fromkeys(r.limitations + [
            "Establishing disruption does not establish physical destruction or its cause."]))
        return r

    def _targeted_search(self, report, p, batch, items, searched, audit) -> None:
        """For damage parts the record cannot decide: request one focused re-investigation if the evidence types that
        could decide physical damage have not been searched yet; otherwise report the precise gap."""
        place = place_of(p.text)
        pending = [(r, t) for r, t in batch if r.classification == "INSUFFICIENT"]
        if not (pending and place):
            return
        queries, searched_run = prior_search(p, audit, report.research_history)
        request = damage_request(place, [t for _, t in pending])
        requested = False
        known = {(e.doc_id, e.paragraph_number) for e in items}
        notes = {}
        if searched_run:
            for r, _ in pending:
                new = sorted({f"{x.source_id} {x.locator.label()}" for x in r.supporting + r.contradicting + r.qualifying
                              if (x.source_id, x.locator.paragraph) not in known})
                notes[r.prop_id] = (
                    f"Targeted re-investigation ran in run {searched_run}: it added {len(new)} admissible record(s) "
                    f"bearing on this part" + (f" ({'; '.join(new[:4])})" if new else "") + ", none of which decides "
                    f"the physical damage. No further search requested: the corpus offers no reasonable prospect of "
                    f"resolving it.")
        else:
            untried = untried_evidence(queries)
            if not untried:
                note = ("Not requested: Heimdall's searches already covered damage assessments, inspection reports, "
                        "condition reports and observations, and kept nothing that decides it.")
            elif report.run_number >= MAX_RUNS:
                note = "Not requested: the case has reached its run limit."
            else:
                requested = True
                note = (f"Requested: a targeted re-investigation through Heimdall for {', '.join(untried)}, which the "
                        f"searches so far did not cover.")
        for r, _ in pending:
            r.reinvestigation = notes.get(r.prop_id) or note
            r.research_request, r.research_requested = request, requested
            r.evidence_needed = DAMAGE_NEEDED

    def _finding(self, findings: Dict[str, PropositionRuling], prop_id: str) -> Optional[PropositionRuling]:
        """Odin's finding on the proposition an advocate argued: a compound allegation is answered by its parts;
        a send-back proposition by the allegation it was searched for."""
        prop_id = getattr(self, "_alias", {}).get(prop_id, prop_id)
        return findings.get(prop_id) or getattr(self, "_compound", {}).get(prop_id)

    def adjudicate_exposure(self, report: CaseEvidenceReport, propositions: List[PropositionRuling],
                            ranges: List[CellRange]) -> List[PropositionRuling]:
        inv = getattr(report, "investigation", None)
        for p in (inv.spec.propositions if inv else []):
            if p.kind == "EXPOSURE" and ranges:
                r = exposure_ruling(p, ranges)
                if r:
                    propositions.append(r)
                    self.log("proposition_ruling", agent="ODIN", ruling=r.model_dump())
        return propositions

    @staticmethod
    def completeness(report: CaseEvidenceReport, claims: List[Claim], propositions: List[PropositionRuling],
                     ranges: List[CellRange]) -> List[str]:
        """Requirements of the question with no ruling. Checked against Heimdall's plan and the advocates' claims."""
        inv = getattr(report, "investigation", None)
        ruled = {p.prop_id for p in propositions} | {p.derived_from for p in propositions if p.derived_from}
        sendbacks = research_parents(inv.spec.propositions, report.research_history) if inv else {}
        ruled |= {q for q, parents in sendbacks.items() if set(parents) & ruled}
        missing = [f"{p.prop_id}: {p.text}" for p in (inv.spec.propositions if inv else [])
                   if p.prop_id not in ruled and not (p.kind == "EXPOSURE" and ranges)]
        missing += [f"{c.claim_id}: argued proposition {c.argument.claim_id} is not in the Case File plan"
                    for c in claims if c.argument and c.argument.claim_id not in ruled
                    and c.argument.claim_id not in {p.prop_id for p in (inv.spec.propositions if inv else [])}]
        return missing

    @staticmethod
    def analytical_status(report: CaseEvidenceReport, propositions: List[PropositionRuling],
                          ranges: List[CellRange], completeness: List[str]) -> str:
        """COMPLETE only when every requirement is decided (ESTABLISHED or REJECTED); PARTIAL when some are;
        INSUFFICIENT when none is. Running the workflow is not the same as answering the question."""
        # Exposure requirements are counted per coverage cell (a proposition spanning several cells is decided
        # cell by cell); every other proposition counts once.
        decided = [p.classification in ("ESTABLISHED", "REJECTED") for p in propositions if p.kind != "EXPOSURE"]
        decided += [r.status == "COVERED" and r.odin is not None for r in ranges]
        decided += [False] * len(completeness)
        if not decided:
            return "INSUFFICIENT"  # nothing was ruled on: an empty record is never sufficient
        return "COMPLETE" if all(decided) else "PARTIAL" if any(decided) else "INSUFFICIENT"

    @staticmethod
    def outcome(rulings: List[Ruling], claims: List[Claim] = (), report: Optional[CaseEvidenceReport] = None) -> Dict:
        """Who won the trial, from Odin's rulings on each side's arguments: +1 for every argument upheld, -1 for
        every argument rejected or withdrawn. Contested arguments and positions not pressed score nothing (not
        pressing is not a loss on the merits, and the opponent's prevailing argument already counts). Arguments on
        Odin's own re-investigation request are the same issue as the allegation it serves, so are not scored twice."""
        inv = getattr(report, "investigation", None)
        sendbacks = research_parents(inv.spec.propositions, report.research_history) if inv else {}
        repeat = {c.claim_id for c in claims if c.argument and c.argument.claim_id in sendbacks}
        tally = {s: {"upheld": 0, "rejected": 0, "conceded": 0, "contested": 0, "not_pressed": 0}
                 for s in ("THOR", "LOKI")}
        for r in rulings:
            if r.claim_id in repeat:
                continue
            t = tally.setdefault(r.side, {"upheld": 0, "rejected": 0, "conceded": 0, "contested": 0,
                                          "not_pressed": 0})
            key = ("not_pressed" if r.classification == "NOT_PRESSED" else
                   {"UPHELD": "upheld", "REJECTED": "rejected", "CONCEDED": "conceded"}.get(r.ruling, "contested"))
            t[key] += 1
        score = {s: t["upheld"] - t["rejected"] - t["conceded"] for s, t in tally.items()}
        thor, loki = score.get("THOR", 0), score.get("LOKI", 0)
        winner = "THOR" if thor > loki else "LOKI" if loki > thor else "DRAW"

        def line(s):
            t = tally[s]
            return (f"{s.title()} {score[s]:+d} ({t['upheld']} upheld, {t['rejected']} rejected, {t['conceded']} "
                    f"withdrawn, {t['contested']} contested, {t['not_pressed']} not pressed)")
        reason = f"{line('THOR')}; {line('LOKI')}." + (
            f" {len(repeat)} argument(s) on Odin's own re-investigation request not scored separately (same issue "
            f"as the allegation it serves)." if repeat else "")
        verdict = (f"{winner.title()} wins" if winner != "DRAW" else "Draw: neither side prevails") + f" - {reason}"
        return {"winner": winner, "score": score, "tally": tally, "verdict": verdict}

    @staticmethod
    def _argument_ruling(c: Claim, finding: PropositionRuling) -> Tuple[str, str]:
        """(whether this advocate's argument prevails, why). The classification is the proposition's finding."""
        cls, arg = finding.classification, c.argument
        if arg.position == "supports":
            prevails = {"ESTABLISHED": "UPHELD", "CONTESTED": "CONTESTED"}.get(cls, "REJECTED")
        elif arg.challenge_basis == "not_established":
            prevails = "REJECTED" if cls == "ESTABLISHED" else "UPHELD"
        else:
            prevails = {"REJECTED": "UPHELD", "CONTESTED": "CONTESTED"}.get(cls, "REJECTED")
        what = {"UPHELD": "prevails", "REJECTED": "does not prevail", "CONTESTED": "is neither upheld nor defeated"}
        return prevails, (f"{c.side.title()}'s argument {what[prevails]}: Odin's ruling on {finding.prop_id} is "
                          f"{cls}. {finding.reasoning}")

    def rule(self, report: CaseEvidenceReport, claims: List[Claim], attacks: List[Attack],
             responses: List[Response], side_failures: Dict[str, str],
             propositions: Optional[List[PropositionRuling]] = None) -> List[Ruling]:
        findings = {p.prop_id: p for p in (propositions or [])}
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
            if c.status == "NOT_PRESSED":
                rulings[c.claim_id] = Ruling(claim_id=c.claim_id, side=c.side, run=c.run, ruling="CONCEDED",
                                             nature="INFERENCE", classification="NOT_PRESSED",
                                             reason="Not pressed: nothing in the Case File carries this side's "
                                                    "position. This is not a finding on the proposition.")
                continue
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
            finding = self._finding(findings, c.argument.claim_id) if c.argument else None
            if finding is not None:
                # An argument on a proposition is ruled by Odin's own finding on that proposition, in its narrowed
                # form if the advocate narrowed it; the advocate's confidence is not taken on trust.
                prevails, why = self._argument_ruling(c, finding)
                if c.status == "NARROWED" and c.argument.revision_history:
                    why = (f"Ruled as narrowed in round {c.argument.revision_history[-1].round} "
                           f"({c.argument.revision_history[-1].action.replace('_', ' ')}). ") + why
                rulings[c.claim_id] = Ruling(claim_id=c.claim_id, side=c.side, run=c.run, ruling=prevails,
                                             nature="INFERENCE", classification=finding.classification,
                                             reason=why, decided_by="odin")
                continue
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
                    rulings: List[Ruling], propositions: Optional[List[PropositionRuling]] = None
                    ) -> Tuple[List[str], List[str]]:
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
        # An unresolved proposition is sent back only when Odin found a targeted search worth running (one request
        # per allegation, never repeated); otherwise it is an open gap, reported with what would resolve it.
        for p in propositions or []:
            if p.research_requested:
                missing.append(p.research_request)
            elif p.needs_investigation and p.kind != "EXPOSURE":
                still_open.append(f"{p.prop_id} ({p.classification}): {p.proposition} - {p.evidence_gap} Needed: "
                                  f"{p.evidence_needed}.")
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
            targets = [p for p in record.propositions if p.research_request == gap] or [
                p for p in record.propositions if p.derivation != "consequence" and DAMAGE.search(p.proposition)
                and is_damage_request(gap, place_of(p.proposition) or "\0")]
            if targets:
                still = [p for p in targets if p.classification == "INSUFFICIENT"]
                fresh = [d for d in new if any(r.source_id == d for p in targets
                                               for r in p.supporting + p.contradicting + p.qualifying)]
                detail = ("; ".join(f"{p.prop_id} is {p.classification}" for p in targets)
                          + (f"; new document(s) bearing on it: {', '.join(fresh)}" if fresh else
                             "; no new document bears on the physical damage" if new else
                             "; the re-search found no new admissible documents"))
                out.append(ResearchOutcome(gap=gap, resolved=not still, new_documents=new, used_documents=fresh,
                                           explanation=f"{'Not resolved' if still else 'Resolved'}: {detail}."))
                continue
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
