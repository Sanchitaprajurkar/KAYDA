"""Spec 6 - Verify the event: confirmed, disputed, unverified, disproven or still developing.

An LLM labels each event-related fact as SUPPORTS / CONTRADICTS / NEUTRAL. The verdict itself comes from
explicit rules over those labels, source tiers, independence and resolved contradictions, so it is explainable.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from heimdall.models.case_file import (
    CaseScope, EventStatus, EventVerification, EvidenceRef, FactAssessment, RejectedEvidence, SourceAssessment,
)
from heimdall.models.evidence import ContradictionItem, ExtractedFact
from heimdall.reasoning.cache import VerdictCache
from heimdall.reasoning.contradiction_detector import weigh
from heimdall.reasoning.llm import StructuredLLM

EVENT_CATEGORIES = {"TREATY_OR_AGREEMENT", "ROUTE_STATUS", "DISRUPTION_STATUS", "GEOPOLITICAL_EVENT",
                    "RETRACTION_NOTICE", "TRADE_VOLUME", "GRAIN_OR_INVENTORY"}
STRONG = {"CONFIRMED", "CORRECTED"}
CREDIBLE_CONTRARY = {"CONFIRMED", "CORRECTED", "REPORTED"}
MAX_STANCE_FACTS = 120
STANCE_BATCH = 40  # keeps each structured response well inside the output limit

SYSTEM_PROMPT = ("You are Heimdall, the evidence-intake judge. You classify how sourced facts bear on whether an "
                 "event happened. You only use the facts given.")


class Stance(BaseModel):
    fact_id: str
    stance: str = Field(description="SUPPORTS, CONTRADICTS or NEUTRAL")


class StanceResponse(BaseModel):
    stances: List[Stance] = Field(default_factory=list)


def _ref(f: ExtractedFact, a: FactAssessment, s: SourceAssessment) -> EvidenceRef:
    return EvidenceRef(fact_id=f.fact_id, doc_id=f.source_ref.doc_id, citation=a.citation, statement=f.statement,
                       assertion_status=f.assertion_status.value if f.assertion_status else None,
                       reliability_tier=s.reliability_tier)


class EventVerifier:
    def __init__(self, llm: Optional[StructuredLLM] = None):
        self.llm = llm or StructuredLLM()

    def _stances(self, scope: CaseScope, facts: List[ExtractedFact], sources: Dict[str, SourceAssessment]
                 ) -> Dict[str, str]:
        """Stance per fact; cached verdicts are reused and the rest are sent in chunks."""
        cache = VerdictCache("stances", getattr(self.llm, "model_name", None))
        claim_key = f"{scope.event_id or scope.event_name}|{scope.as_of_date}"
        out, todo = {}, []
        for f in facts:
            hit = cache.get(f"{claim_key}|{f.fact_id}")
            if hit:
                out[f.fact_id] = hit
            else:
                todo.append(f)
        for start in range(0, len(todo), STANCE_BATCH):
            chunk = self._stance_chunk(scope, todo[start:start + STANCE_BATCH], sources)
            for fid, stance in chunk.items():
                cache.put(f"{claim_key}|{fid}", stance)
            out.update(chunk)
        cache.save()
        return out

    def _stance_chunk(self, scope: CaseScope, facts: List[ExtractedFact], sources: Dict[str, SourceAssessment]
                      ) -> Dict[str, str]:
        claim = (f"The disruption event '{scope.event_name or scope.query}' has happened and is in effect "
                 f"as of {scope.as_of_date}.")
        lines = [f"[{f.fact_id}] {sources[f.source_ref.doc_id].pub_date} | {f.statement}" for f in facts]
        prompt = (f"Event claim: {claim}\n"
                  f"Case question: {scope.query or '-'}\n\n"
                  "For every fact, give its stance toward the event claim:\n"
                  "- SUPPORTS: the fact shows the disruption happened or is still in effect, including its direct "
                  "effects (reduced shipments, ships held, rerouting, higher costs).\n"
                  "- CONTRADICTS: the fact says the disruption did not happen, was reversed (e.g. the arrangement "
                  "was renewed or restored), or is over (normal operations fully resumed).\n"
                  "- NEUTRAL: background or unrelated detail.\n"
                  "Important: the event is itself a breakdown. Statements that an agreement expired, lapsed, ended "
                  "or was not renewed, that talks failed, or that a route closed describe the event happening and "
                  "are SUPPORTS, not CONTRADICTS. A forecast made before the event that it would not happen is "
                  "CONTRADICTS.\n\n"
                  "Facts:\n" + "\n".join(lines))
        response = self.llm.parse(SYSTEM_PROMPT, prompt, StanceResponse)
        valid = {f.fact_id for f in facts}
        return {s.fact_id: s.stance.strip().upper() for s in response.stances
                if s.fact_id in valid and s.stance.strip().upper() in ("SUPPORTS", "CONTRADICTS", "NEUTRAL")}

    def verify(self, scope: CaseScope, facts: List[ExtractedFact], sources: Dict[str, SourceAssessment],
               assessments: Dict[str, FactAssessment], rejected: List[RejectedEvidence],
               contradictions: List[ContradictionItem]) -> EventVerification:
        candidates = [f for f in facts if f.category.value in EVENT_CATEGORIES
                      and sources[f.source_ref.doc_id].source_type != "atlas"]
        candidates.sort(key=lambda f: -assessments[f.fact_id].credibility)
        candidates = candidates[:MAX_STANCE_FACTS]
        stance = self._stances(scope, candidates, sources) if candidates else {}

        def status_of(f):
            return f.assertion_status.value if f.assertion_status else "REPORTED"

        def tier(f):
            return sources[f.source_ref.doc_id].reliability_tier

        # Conflicts stay open in the Case File; for the event verdict alone, Heimdall weighs each one.
        winners = {id(c): weigh(c, sources, assessments) for c in contradictions}
        losers = {(c.fact_a.fact_id if winners[id(c)] == c.fact_b.fact_id else c.fact_b.fact_id)
                  for c in contradictions if winners[id(c)] and c.fact_a and c.fact_b}
        supports = [f for f in candidates if stance.get(f.fact_id) == "SUPPORTS"]
        contrary = [f for f in candidates if stance.get(f.fact_id) == "CONTRADICTS"]
        strong = [f for f in supports if status_of(f) in STRONG and tier(f) <= 2]
        standing_contrary = [f for f in contrary if tier(f) <= 2 and status_of(f) in CREDIBLE_CONTRARY
                             and f.fact_id not in losers]
        outlets = sorted({sources[f.source_ref.doc_id].source_name for f in strong})
        tier1 = [f for f in strong if tier(f) == 1]
        credible_reports = [f for f in supports if tier(f) <= 2]

        if not supports and standing_contrary:
            status = EventStatus.DISPROVEN
        elif (tier1 or len(outlets) >= 2) and not standing_contrary:
            status = EventStatus.CONFIRMED
        elif tier1 or len(outlets) >= 2:
            status = EventStatus.DISPUTED
        elif credible_reports:
            status = EventStatus.DEVELOPING
        else:
            status = EventStatus.UNVERIFIED

        dated = sorted([f for f in supports + contrary if tier(f) <= 2],
                       key=lambda f: sources[f.source_ref.doc_id].pub_date or "")
        latest = dated[-1] if dated else None
        active = status in (EventStatus.CONFIRMED, EventStatus.DISPUTED) and latest is not None \
            and stance.get(latest.fact_id) == "SUPPORTS"
        onset = min((sources[f.source_ref.doc_id].pub_date for f in strong), default=None)

        confidence = {
            EventStatus.CONFIRMED: min(0.97, 0.8 + 0.05 * min(len(outlets), 3) + (0.03 if tier1 else 0)),
            EventStatus.DISPUTED: 0.5, EventStatus.DEVELOPING: 0.6,
            EventStatus.DISPROVEN: 0.85, EventStatus.UNVERIFIED: 0.3,
        }[status]

        def ref(f):
            return _ref(f, assessments[f.fact_id], sources[f.source_ref.doc_id])

        stance_facts = supports + contrary
        rumours = [EvidenceRef(doc_id=r.doc_id, citation=f"[{r.doc_id}]", statement=c,
                               reliability_tier=r.reliability_tier, assertion_status=r.reason)
                   for r in rejected if r.reason in ("RUMOUR", "TABLOID", "UNRELIABLE_SOURCE") for c in r.claims[:2]]

        reasoning = self._reasoning(status, strong, outlets, tier1, standing_contrary, contrary, losers, rejected,
                                    latest, active, sources, assessments, stance)
        name = scope.event_name or "the reported disruption"
        summary = {
            EventStatus.CONFIRMED: f"{name} is CONFIRMED" + (" and still in effect" if active else "")
                                   + f" as of {scope.as_of_date}: {len(outlets)} independent Tier 1-2 outlet(s) "
                                     f"({', '.join(outlets)}) confirm it and no credible evidence stands against it.",
            EventStatus.DISPUTED: f"{name} is DISPUTED as of {scope.as_of_date}: credible confirmations exist but "
                                  f"{len(standing_contrary)} credible contrary fact(s) remain unresolved.",
            EventStatus.DEVELOPING: f"{name} is DEVELOPING as of {scope.as_of_date}: credible sources report it, "
                                    f"but it is not yet confirmed by an official or two independent outlets.",
            EventStatus.DISPROVEN: f"{name} is DISPROVEN as of {scope.as_of_date}: credible evidence contradicts "
                                   f"it and nothing credible supports it.",
            EventStatus.UNVERIFIED: f"{name} is UNVERIFIED as of {scope.as_of_date}: no credible (Tier 1-2) "
                                    f"evidence was found.",
        }[status]

        return EventVerification(
            event_id=scope.event_id, event_name=scope.event_name, status=status, as_of_date=scope.as_of_date,
            confidence_score=round(confidence, 2), summary=summary, reasoning=reasoning,
            is_real_event=status in (EventStatus.CONFIRMED, EventStatus.DISPUTED),
            is_active_at_as_of=active, onset_date=onset, independent_confirming_sources=outlets,
            supporting_doc_ids=sorted({f.source_ref.doc_id for f in supports}),
            counter_or_decoy_doc_ids=sorted({f.source_ref.doc_id for f in contrary} | {r.doc_id for r in rejected}),
            confirmed_facts=[ref(f) for f in stance_facts if status_of(f) in STRONG and tier(f) <= 2],
            reported_claims=[ref(f) for f in stance_facts
                             if status_of(f) == "REPORTED" or (status_of(f) in STRONG and tier(f) > 2)],
            allegations=[ref(f) for f in stance_facts if status_of(f) in ("ALLEGED", "DENIED")],
            rumours=rumours + [ref(f) for f in stance_facts if status_of(f) == "RUMOURED"],
            projections=[ref(f) for f in stance_facts if status_of(f) in ("PROJECTED", "PROPOSED")],
            contrary_evidence=[ref(f) for f in contrary],
        )

    @staticmethod
    def _reasoning(status, strong, outlets, tier1, standing_contrary, contrary, losers, rejected, latest, active,
                   sources, assessments, stance) -> List[str]:
        out = []
        if tier1:
            f = max(tier1, key=lambda x: (assessments[x.fact_id].independent_source_count,
                                          assessments[x.fact_id].credibility))
            out.append(f"Official (Tier 1) confirmation: {assessments[f.fact_id].citation} "
                       f"{sources[f.source_ref.doc_id].source_name}: \"{f.statement}\"")
        if strong:
            best = sorted(strong, key=lambda f: -assessments[f.fact_id].credibility)[:3]
            out.append(f"{len(outlets)} independent Tier 1-2 outlet(s) confirm the event ({', '.join(outlets)}): "
                       + "; ".join(f"{assessments[f.fact_id].citation} \"{f.statement}\"" for f in best))
        else:
            out.append("No confirmed (CONFIRMED/CORRECTED) Tier 1-2 fact supports the event.")
        if standing_contrary:
            out.append("Credible contrary evidence still standing: " + "; ".join(
                f"{assessments[f.fact_id].citation} \"{f.statement}\"" for f in standing_contrary[:3]))
        elif contrary:
            overridden = [f for f in contrary if f.fact_id in losers]
            weak = [f for f in contrary if f not in overridden]
            parts = []
            if overridden:
                parts.append(f"{len(overridden)} overridden by more credible evidence in cross-examination")
            if weak:
                parts.append(f"{len(weak)} from weaker sources or framed as forecasts/allegations")
            out.append(f"Contrary facts considered ({len(contrary)}): " + ", ".join(parts) + ".")
        else:
            out.append("No credible evidence in the retrieved documents contradicts the event.")
        by_reason: Dict[str, List[RejectedEvidence]] = {}
        for r in rejected:
            by_reason.setdefault(r.reason, []).append(r)
        labels = {"RETRACTED": "retracted", "TAINTED": "relied on a retracted report",
                  "SUPERSEDED": "forecast superseded", "RUMOUR": "rumour from a Tier 4 outlet",
                  "TABLOID": "tabloid (Tier 4)", "CLOCK_EXCLUDED": "published after the as-of date",
                  "UNRELIABLE_SOURCE": "Tier 4 source"}
        for reason, items in by_reason.items():
            out.append(f"Set aside before trial ({labels.get(reason, reason.lower())}): " + "; ".join(
                f"{r.doc_id} '{r.title}'" + (f" -> see {r.related_doc_id}" if r.related_doc_id else "")
                for r in items))
        if latest is not None:
            out.append(f"Most recent credible evidence ({sources[latest.source_ref.doc_id].pub_date}) "
                       f"{'supports' if stance.get(latest.fact_id) == 'SUPPORTS' else 'contradicts'} the event: "
                       f"{assessments[latest.fact_id].citation} \"{latest.statement}\""
                       + (" - the disruption is still in effect." if active else "."))
        return out
