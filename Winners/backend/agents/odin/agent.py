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
from backend.court.models import Attack, CellRange, Claim, Response, Ruling
from backend.court.tools import RunemarkTools, calculation_defect, windows

ODIN_WINDOWS = ("full", "late")  # the onset month is only partly affected, so Odin's range leaves it out


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
                failed.append(f"{e.ref} is not admissible evidence at {report.as_of_date}")
                continue
            if (e.pub_date or "9999") > report.as_of_date:
                failed.append(f"{e.ref} is dated after the as-of date")
            if e.kind == "trade_row":
                s = self.tools.series(e.doc_id)
                row = next((r for r in (s.rows if s else []) if r.row_id == e.ref), None)
                if not row or not row.valid:
                    failed.append(f"trade row {e.ref} is missing or flagged")
            elif e.excerpt:
                body = " ".join(t for _, t in self.tools.store.body_paragraphs(e.doc_id))
                if _norm(e.excerpt)[:60] not in _norm(body):
                    failed.append(f"quote for {e.ref} is not in the document")
        defect = calculation_defect(self.tools, claim) if claim.kind == "calculation" else None
        if defect:
            failed.append(defect[1])
        return failed

    @staticmethod
    def _default_nature(claim: Claim) -> str:
        if claim.kind == "calculation":
            return "INFERENCE"
        return "SOURCED_FACT" if all(e.assertion in ("CONFIRMED", "REPORTED", "CORRECTED") for e in claim.citations) \
            else "INFERENCE"

    # -- rulings ----------------------------------------------------------------
    def rule(self, report: CaseEvidenceReport, claims: List[Claim], attacks: List[Attack],
             responses: List[Response], side_failures: Dict[str, str]) -> List[Ruling]:
        by_target: Dict[str, List[Attack]] = {}
        for a in attacks:
            by_target.setdefault(a.target_claim_id, []).append(a)
        answers = {r.attack_id: r for r in responses}
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
            if not by_target.get(c.claim_id):
                rulings[c.claim_id] = Ruling(
                    claim_id=c.claim_id, side=c.side, run=c.run, ruling="UPHELD", nature=self._default_nature(c),
                    classification="UNCONTESTED" if opponent_failed else self._classify("UPHELD", c),
                    reason="Verified against its sources" + ("; the other side failed, so it went unchallenged."
                                                             if opponent_failed else " and never credibly countered."))
                continue
            pending.append(c)

        decided = self._llm_rulings(report, pending, by_target, answers) if pending else {}
        for c in pending:
            r = decided.get(c.claim_id) or self._fallback(c, by_target[c.claim_id], answers)
            ruling, nature, reason, by = r
            rulings[c.claim_id] = Ruling(claim_id=c.claim_id, side=c.side, run=c.run, ruling=ruling, nature=nature,
                                         classification=self._classify(ruling, c), reason=reason, decided_by=by)
        out = [rulings[c.claim_id] for c in claims]
        for r in out:
            self.log("ruling", agent="ODIN", ruling=r.model_dump())
        return out

    @staticmethod
    def _classify(ruling: str, claim: Claim) -> str:
        if ruling == "UPHELD":
            return "ESTABLISHED" if all(e.tier <= 2 for e in claim.citations) else "CONTESTED"
        return {"REJECTED": "REJECTED", "CONTESTED": "CONTESTED", "CONCEDED": "CONCEDED"}[ruling]

    def _fallback(self, c: Claim, attacks: List[Attack], answers: Dict[str, Response]) -> Tuple[str, str, str, str]:
        defended = all(answers.get(a.attack_id) and answers[a.attack_id].decision == "DEFENDED" for a in attacks)
        if c.kind == "calculation" and defended and not any(e.kind == "trade_row" for a in attacks
                                                           for e in a.counter_evidence):
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
                     f"{c.estimate.low:g}-{c.estimate.high:g}%): {c.statement}",
                     "  cites: " + "; ".join(f"{e.ref} Tier {e.tier} {e.assertion or ''} \"{e.excerpt[:120]}\""
                                             for e in c.citations[:4])]
            for e in c.citations:
                for other in conflicts.get(e.fact_id or "", [])[:1]:
                    lines.append(f"  Heimdall flagged {e.ref} as contradicted by: \"{other}\"")
            for a in by_target[c.claim_id]:
                lines.append(f"  ATTACK {a.attack_id} by {a.attacker}: {a.reason} - {a.argument} | counter: " +
                             "; ".join(f"{e.ref} Tier {e.tier} \"{e.excerpt[:120]}\"" for e in a.counter_evidence))
                ans = answers.get(a.attack_id)
                if ans:
                    lines.append(f"  ANSWER: {ans.decision} - {ans.explanation} | new: " +
                                 "; ".join(f"{e.ref} Tier {e.tier} \"{e.excerpt[:120]}\"" for e in ans.new_evidence))
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
        ruled = {r.claim_id: r for r in rulings}
        wins = windows(report)
        out = []
        for cell in report.coverage_map:
            r = CellRange(country=cell.country, sector=cell.sector, status=cell.status)
            for c in claims:
                if c.kind == "calculation" and (c.country, c.sector) == (cell.country, cell.sector):
                    span = (c.estimate.low, c.estimate.high)
                    if c.side == "THOR":
                        r.thor = span
                    else:
                        r.loki = span
            if cell.status != "COVERED":
                r.basis = "Evidence missing: no trade series for this flow; no range is given."
                out.append(r)
                continue
            surviving = [c for c in claims if c.kind == "calculation" and (c.country, c.sector) ==
                         (cell.country, cell.sector) and ruled[c.claim_id].ruling in ("UPHELD", "CONTESTED")]
            if not surviving:
                r.basis = "No calculation survived the trial."
                out.append(r)
                continue
            primary = [self.tools.series(d) for d in cell.primary_series]
            subs = [self.tools.series(d) for d in cell.substitute_series]
            figures = []
            for name in ODIN_WINDOWS:
                if name not in wins:
                    continue
                months, base, dis = wins[name]
                k = self.tools.compute_change(None, cell.country, cell.sector, report.case_scope.event_countries,
                                              primary, subs, months, base, dis, 0.0, name)
                if k:
                    # Both bounds use total import basket as denominator (consistent with claim bounds).
                    figures.append((name, months, k.net_import_loss_pct, k.gross_import_loss_pct))
            if figures:
                # low = min net_import_loss across windows; high = max gross_import_loss across windows
                r.odin = (round(min(f[2] for f in figures), 2), round(max(f[3] for f in figures), 2))
                r.basis = (f"Recomputed from the Case File's trade rows ({', '.join(cell.primary_series)}"
                           + (f", net of {', '.join(cell.substitute_series)}" if cell.substitute_series else
                              ", no substitute supply on the record")
                           + "); windows: " + "; ".join(
                               f"{n} {m[0][:3]}-{m[-1][:3]} net {v:.1f}%-gross {g:.1f}%"
                               for n, m, v, g in figures)
                           + ". The onset month is left out because it was only partly affected.")
            out.append(r)
        return out

    # -- sufficiency ------------------------------------------------------------
    def sufficiency(self, report: CaseEvidenceReport, claims: List[Claim], rulings: List[Ruling]) -> List[str]:
        ruled = {r.claim_id: r for r in rulings}
        asked_substitutes = any(re.search(r"substitut", h.request, re.I) for h in report.research_history)
        record_docs = {d.doc_id: d for d in report.retrieved_documents}
        missing = []
        for cell in report.coverage_map:
            label = f"{cell.country} {cell.sector}"
            calcs = [c for c in claims if c.kind == "calculation" and (c.country, c.sector) ==
                     (cell.country, cell.sector)]
            if cell.status == "COVERED":
                if not any(ruled[c.claim_id].classification == "ESTABLISHED" for c in calcs):
                    missing.append(f"{label}: no established trade-row finding")
                if not cell.substitution_evidenced and not asked_substitutes:
                    missing.append(f"{label}: net effect of substitute supply is not in the Case File")
                for c in calcs:
                    if ruled[c.claim_id].ruling in ("UPHELD", "CONTESTED"):
                        extra = sorted({s for k in c.calculations for s in k.substitute_series}
                                       - set(cell.substitute_series))
                        if extra:
                            missing.append(f"{label}: substitute trade series {', '.join(extra)} cited by {c.side} "
                                           f"are not in the Case File")
            else:
                profile = any(d.source_type == "atlas" and cell.country.lower() in (d.title or "").lower()
                              for d in record_docs.values())
                if not profile:
                    missing.append(f"{label}: evidence gap not yet checked against the {cell.country} reference "
                                   f"sheet")
        return list(dict.fromkeys(missing))
