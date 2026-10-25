"""Deterministic stand-ins for every LLM call, for tests and free dry runs (`--offline`).

They follow the same contracts as the real model: they only pick IDs that appear in the prompt.
"""

import re

from backend.agents.advocate import Round1, Round2, Round3, PickedAttack, PickedClaim, PickedResponse
from backend.agents.odin.agent import OdinRuling, OdinRulings
from backend.court.heimdall_bridge import HeimdallAgent, ResolvedEvidenceStore

EVENT_TERMS = re.compile(r"expired|ended|lapse|without (a )?renewal|no renewal|held outside|turn back|strike", re.I)
_CANDIDATE = re.compile(r"^\[(\w+)\] (\S+) Tier (\d) \S+ (\S+) \| (.*)$", re.M)


class ScriptedLLM:
    model_name = "scripted"

    def __init__(self, conflicts=None):
        self.conflicts = [set(c) for c in (conflicts or [])]
        self.prompts = []

    def parse(self, system, user, schema):
        from heimdall.reasoning.contradiction_detector import PairResponse, PairVerdict
        from heimdall.reasoning.verifier import Stance, StanceResponse
        self.prompts.append((schema.__name__, user))
        if schema is StanceResponse:
            return StanceResponse(stances=[
                Stance(fact_id=fid, stance="SUPPORTS" if EVENT_TERMS.search(text) else "NEUTRAL")
                for fid, text in re.findall(r"^\[(\w+)\] [\d-]+ \| (.*)$", user, re.M)])
        if schema is PairResponse:
            return PairResponse(verdicts=[
                PairVerdict(pair_id=pid, reasoning="scripted", conflicting={a, b} in self.conflicts,
                            conflict_type="DIRECT_CONTRADICTION" if {a, b} in self.conflicts else None)
                for pid, a, b in re.findall(r"^(P\d+):\n  A \[(\w+)\].*\n  B \[(\w+)\]", user, re.M)])
        if schema is Round1:
            cell = (re.findall(r"^- (\w[\w ]*\|\w+):", user, re.M) or [None])[0]
            picks = [m for m in _CANDIDATE.findall(user) if int(m[2]) <= 3][:2]
            return Round1(claims=[PickedClaim(fact_ids=[fid], cell=cell, statement=text, reasoning="scripted")
                                  for fid, _, _, _, text in picks])
        if schema is Round2:
            targets = re.findall(r"^([TL]\d+-\d+) ", user, re.M)
            cands = [m[0] for m in _CANDIDATE.findall(user)]
            if not targets or not cands:
                return Round2()
            return Round2(attacks=[PickedAttack(target_claim_id=targets[0], reason="contradicts",
                                                counter_fact_ids=[cands[0]],
                                                argument=f"Evidence {cands[0]} contradicts this claim.")])
        if schema is Round3:
            ids = re.findall(r"^(A[TL]\d+-\d+) on", user, re.M)
            cands = [m[0] for m in _CANDIDATE.findall(user)]
            out = []
            for i, aid in enumerate(ids):
                if i == 0 and cands:
                    out.append(PickedResponse(attack_id=aid, decision="DEFEND", new_fact_ids=[cands[0]],
                                              explanation=f"New evidence {cands[0]} answers the attack."))
                else:
                    out.append(PickedResponse(attack_id=aid, decision="CONCEDE",
                                              explanation="The counter-evidence defeats this claim."))
            return Round3(responses=out)
        if schema is OdinRulings:
            out = []
            for block in user.split("CLAIM ")[1:]:
                cid = block.split(" ", 1)[0]
                defended = "ANSWER: DEFENDED" in block
                calc = ", calculation," in block
                ruling = ("UPHELD" if calc else "CONTESTED") if defended else "REJECTED"
                out.append(OdinRuling(claim_id=cid, ruling=ruling, nature="INFERENCE" if calc else "SOURCED_FACT",
                                      reason="scripted ruling"))
            return OdinRulings(rulings=out)
        raise AssertionError(f"no scripted answer for {schema.__name__}")


class _NoGraph:
    def link_case(self, **kwargs):
        from heimdall.models.case_file import KnowledgeGraphSummary
        return KnowledgeGraphSummary(graph_status="OFFLINE")


class _NoStore:
    enabled = False


def offline_heimdall(llm: ScriptedLLM = None) -> HeimdallAgent:
    from heimdall.reasoning.contradiction_detector import ContradictionDetector
    from heimdall.reasoning.verifier import EventVerifier
    llm = llm or ScriptedLLM()
    return HeimdallAgent(evidence_store=ResolvedEvidenceStore(), contradiction_detector=ContradictionDetector(llm),
                         event_verifier=EventVerifier(llm), graph_builder=_NoGraph(), case_store=_NoStore())
