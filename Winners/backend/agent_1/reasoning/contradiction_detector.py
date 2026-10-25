"""Spec 5 - Detect contradictions across all retrieved evidence.

1. Candidate pairs are built in code: facts from different documents, about the same countries/commodities,
   that share distinctive terms (a named speaker, firm, route or metric - not words every document uses).
2. The LLM only judges those pairs (conflict or not, and which type). It cannot invent facts or pairs.
3. Which side is favoured is decided deterministically from credibility, corroboration and recency.
"""

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from agent_1.case.text import token_set
from agent_1.models.case_file import FactAssessment, SourceAssessment
from agent_1.models.evidence import ConflictType, ContradictionItem, ExtractedFact
from agent_1.reasoning.llm import StructuredLLM

LATER_WINS = {ConflictType.CORRECTION, ConflictType.RETRACTION, ConflictType.TEMPORAL_UPDATE}
MAX_PAIRS = 80
PAIR_BATCH = 10  # small batches keep judgements reliable on smaller models
SALIENT_DF_SHARE = 0.08  # a term is distinctive if it appears in at most 8% of facts

SYSTEM_PROMPT = ("You are Heimdall's cross-examination analyst. You judge whether two sourced facts genuinely "
                 "conflict. You only use the text given.")

RULES = """For each numbered pair, decide whether fact A and fact B genuinely conflict about the same subject.
Conflicting means both cannot be accurate at the same time. Facts that agree, overlap, or add detail to each
other are NOT conflicting. Write your reasoning first, then the verdict. Judge every pair.
Types (use one when conflicting=true):
- DIRECT_CONTRADICTION: they cannot both be true, including a source contradicting its own earlier statement.
- NUMERICAL_DISCREPANCY: different figures for the same metric, place and period.
- CORRECTION / RETRACTION: one explicitly corrects or withdraws the other.
- TEMPORAL_UPDATE: a later fact changes a status reported earlier for the same thing.
- CREDIBILITY_CONFLICT: a sweeping claim (often without figures) that the data in the other fact undermines.
Not conflicts: different months, routes, countries or commodities; a fact that merely adds detail; background
versus an update that does not change it. When unsure, conflicting=false."""


class PairVerdict(BaseModel):
    pair_id: str = Field(description="The pair label, e.g. P3")
    reasoning: str = Field(description="One or two sentences: what each fact asserts and whether both can be true")
    conflicting: bool
    conflict_type: Optional[str] = Field(default=None, description="DIRECT_CONTRADICTION, NUMERICAL_DISCREPANCY, "
                                         "CORRECTION, RETRACTION, TEMPORAL_UPDATE or CREDIBILITY_CONFLICT")
    description: str = ""


class PairResponse(BaseModel):
    verdicts: List[PairVerdict] = Field(default_factory=list)


def _same_subject(a: FactAssessment, b: FactAssessment) -> bool:
    """Facts that name different countries or commodities are different metrics, never a conflict.

    Only names stated in the fact text count; a document's own country says nothing about a quoted remark.
    """
    return all(not (x and y) or set(x) & set(y)
               for x, y in ((a.stated_countries, b.stated_countries),
                            (a.stated_commodities, b.stated_commodities)))


def candidate_pairs(facts: List[ExtractedFact], assessments: Dict[str, FactAssessment],
                    limit: int = MAX_PAIRS) -> List[Tuple[ExtractedFact, ExtractedFact, List[str]]]:
    toks = {f.fact_id: token_set(f"{f.subject} {f.statement}") for f in facts}
    df = Counter(t for f in facts for t in toks[f.fact_id])
    n = len(facts)
    cutoff = max(3, int(SALIENT_DF_SHARE * n))
    idf = {t: math.log(n / c) for t, c in df.items()}
    scored = []
    for i, fa in enumerate(facts):
        for fb in facts[i + 1:]:
            if fa.source_ref.doc_id == fb.source_ref.doc_id:
                continue
            if not _same_subject(assessments[fa.fact_id], assessments[fb.fact_id]):
                continue
            shared = [t for t in toks[fa.fact_id] & toks[fb.fact_id] if df[t] <= cutoff]
            same_metric = (fa.numeric_value is not None and fb.numeric_value is not None
                           and (fa.unit or "").strip().lower() == (fb.unit or "").strip().lower()
                           and fa.numeric_value != fb.numeric_value)
            if len(shared) >= 2 or (same_metric and shared):
                scored.append((sum(idf[t] for t in shared) + (3.0 if same_metric else 0.0), fa, fb, sorted(shared)))
    scored.sort(key=lambda x: -x[0])
    return [(fa, fb, shared) for _, fa, fb, shared in scored[:limit]]


class ContradictionDetector:
    def __init__(self, llm: Optional[StructuredLLM] = None):
        self.llm = llm or StructuredLLM()

    def detect(self, facts: List[ExtractedFact], sources: Dict[str, SourceAssessment],
               assessments: Dict[str, FactAssessment], titles: Optional[Dict[str, str]] = None
               ) -> List[ContradictionItem]:
        titles = titles or {}
        facts = [f for f in facts if sources[f.source_ref.doc_id].source_type != "atlas"]
        pairs = candidate_pairs(facts, assessments)
        if not pairs:
            return []

        def line(f):
            s = sources[f.source_ref.doc_id]
            status = f.assertion_status.value if f.assertion_status else "REPORTED"
            return (f"[{f.fact_id}] {f.source_ref.doc_id} \"{titles.get(f.source_ref.doc_id, '')}\" | "
                    f"{s.source_name} (Tier {s.reliability_tier}, {s.source_type}) | {s.pub_date} | {status} | "
                    f"{f.statement}")

        verdicts: List[PairVerdict] = []
        for start in range(0, len(pairs), PAIR_BATCH):
            blocks = [f"P{i}:\n  A {line(fa)}\n  B {line(fb)}"
                      for i, (fa, fb, _) in enumerate(pairs[start:start + PAIR_BATCH], start + 1)]
            verdicts += self.llm.parse(SYSTEM_PROMPT, RULES + "\n\n" + "\n".join(blocks), PairResponse).verdicts

        items, seen = [], set()
        for v in verdicts:
            if not v.conflicting:
                continue
            try:
                fa, fb, _ = pairs[int(v.pair_id.strip().upper().lstrip("P")) - 1]
            except (ValueError, IndexError):
                continue
            key = frozenset((fa.fact_id, fb.fact_id))
            if key in seen:
                continue
            seen.add(key)
            try:
                ctype = ConflictType((v.conflict_type or "").strip().upper())
            except ValueError:
                ctype = ConflictType.DIRECT_CONTRADICTION
            favored, rationale = self._resolve(fa, fb, ctype, sources, assessments)
            items.append(ContradictionItem(conflict_type=ctype, description=v.description, fact_a=fa, fact_b=fb,
                                           resolution_rationale=rationale, favored_fact_id=favored))
        return items

    @staticmethod
    def _resolve(fa: ExtractedFact, fb: ExtractedFact, ctype: ConflictType,
                 sources: Dict[str, SourceAssessment], assessments: Dict[str, FactAssessment]):
        sa, sb = sources[fa.source_ref.doc_id], sources[fb.source_ref.doc_id]
        aa, ab = assessments[fa.fact_id], assessments[fb.fact_id]

        def describe(f, s, a):
            return (f"{a.citation} {s.source_name} (Tier {s.reliability_tier}, {s.pub_date}, "
                    f"{f.assertion_status.value if f.assertion_status else 'REPORTED'}, "
                    f"{a.independent_source_count} independent source(s), credibility {a.credibility})")

        if sa.source_name == sb.source_name:
            if aa.independent_source_count != ab.independent_source_count:
                win, lose = ((fa, sa, aa), (fb, sb, ab)) if aa.independent_source_count > ab.independent_source_count \
                    else ((fb, sb, ab), (fa, sa, aa))
                return win[0].fact_id, (f"Self-contradicting source ({sa.source_name}); the statement backed by "
                                        f"independent outlets prevails: {describe(*win)} over {describe(*lose)}.")
            return None, (f"Self-contradicting source ({sa.source_name}): {describe(fa, sa, aa)} vs "
                          f"{describe(fb, sb, ab)}. Neither is independently corroborated; left for cross-examination.")

        if ctype in LATER_WINS and sa.pub_date != sb.pub_date:
            later, earlier = (fa, fb) if (sa.pub_date or "") > (sb.pub_date or "") else (fb, fa)
            sl, se = sources[later.source_ref.doc_id], sources[earlier.source_ref.doc_id]
            if sl.reliability_tier <= se.reliability_tier:
                return later.fact_id, (f"Later report from an equally or more reliable source prevails: "
                                       f"{describe(later, sl, assessments[later.fact_id])} over "
                                       f"{describe(earlier, se, assessments[earlier.fact_id])}.")

        score_a = aa.credibility + 0.05 * (aa.independent_source_count - 1)
        score_b = ab.credibility + 0.05 * (ab.independent_source_count - 1)
        if abs(score_a - score_b) < 0.02:
            return None, f"Unresolved: comparable credibility - {describe(fa, sa, aa)} vs {describe(fb, sb, ab)}."
        win, lose = ((fa, sa, aa), (fb, sb, ab)) if score_a > score_b else ((fb, sb, ab), (fa, sa, aa))
        return win[0].fact_id, f"Favoured on credibility and corroboration: {describe(*win)} over {describe(*lose)}."
