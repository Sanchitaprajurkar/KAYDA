"""Spec 5 - Detect contradictions across all retrieved evidence.

1. Candidate pairs are built in code: facts from different documents, about the same countries/commodities,
   that share distinctive terms (a named speaker, firm, route or metric - not words every document uses).
2. The LLM only judges those pairs (conflict or not, and which type). It cannot invent facts or pairs.
3. Conflicts are handed to the trial open: each side's credentials are stated, but no side is favoured. Thor and
   Loki argue them and Odin rules. weigh() is used only inside Heimdall's own event verdict.
"""

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from heimdall.case.text import token_set
from heimdall.models.case_file import FactAssessment, SourceAssessment
from heimdall.models.evidence import ConflictType, ContradictionItem, ExtractedFact
from heimdall.reasoning.cache import VerdictCache
from heimdall.reasoning.llm import StructuredLLM

LATER_WINS = {ConflictType.CORRECTION, ConflictType.RETRACTION, ConflictType.TEMPORAL_UPDATE}
MAX_PAIRS = 150
MAX_PAIRS_PER_DOC_PAIR = 3  # spread attention across document pairs
PAIR_BATCH = 10  # small batches keep judgements reliable on smaller models
SALIENT_DF_SHARE = 0.08  # a term is distinctive if it appears in at most 8% of facts
SAME_METRIC_DF_SHARE = 0.25
SAME_METRIC_BONUS = 8.0  # two different figures for the same kind of metric are the strongest conflict signal

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
            common = toks[fa.fact_id] & toks[fb.fact_id]
            shared = [t for t in common if df[t] <= cutoff]
            same_metric = (fa.numeric_value is not None and fb.numeric_value is not None
                           and (fa.unit or "").strip().lower() == (fb.unit or "").strip().lower()
                           and fa.numeric_value != fb.numeric_value)
            if same_metric and not shared:
                # two figures for the same kind of metric only need one shared, not-ubiquitous term
                shared = [t for t in common if df[t] <= SAME_METRIC_DF_SHARE * n]
            if len(shared) >= 2 or (same_metric and shared):
                scored.append((sum(idf[t] for t in shared) + (SAME_METRIC_BONUS if same_metric else 0.0),
                               fa, fb, sorted(shared)))
    scored.sort(key=lambda x: -x[0])
    per_doc_pair: Counter = Counter()
    out = []
    for _, fa, fb, shared in scored:
        key = frozenset((fa.source_ref.doc_id, fb.source_ref.doc_id))
        if per_doc_pair[key] >= MAX_PAIRS_PER_DOC_PAIR:
            continue
        per_doc_pair[key] += 1
        out.append((fa, fb, shared))
        if len(out) >= limit:
            break
    return out


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

        # Pairs judged before (e.g. in an earlier run of this case) are not sent to the LLM again.
        cache = VerdictCache("pair_verdicts", getattr(self.llm, "model_name", None))

        def pair_key(fa, fb):
            return "+".join(sorted((fa.fact_id, fb.fact_id)))

        judged: List[Tuple[int, PairVerdict]] = []
        todo = []
        for idx, (fa, fb, _) in enumerate(pairs):
            hit = cache.get(pair_key(fa, fb))
            if hit:
                judged.append((idx, PairVerdict.model_validate(hit)))
            else:
                todo.append(idx)
        for start in range(0, len(todo), PAIR_BATCH):
            batch = todo[start:start + PAIR_BATCH]
            blocks = [f"P{n}:\n  A {line(pairs[idx][0])}\n  B {line(pairs[idx][1])}"
                      for n, idx in enumerate(batch, 1)]
            for v in self.llm.parse(SYSTEM_PROMPT, RULES + "\n\n" + "\n".join(blocks), PairResponse).verdicts:
                try:
                    idx = batch[int(v.pair_id.strip().upper().lstrip("P")) - 1]
                except (ValueError, IndexError):
                    continue
                judged.append((idx, v))
                cache.put(pair_key(pairs[idx][0], pairs[idx][1]), v.model_dump())
        cache.save()

        items, seen = [], set()
        for idx, v in judged:
            if not v.conflicting:
                continue
            fa, fb, _ = pairs[idx]
            key = frozenset((fa.fact_id, fb.fact_id))
            if key in seen:
                continue
            seen.add(key)
            try:
                ctype = ConflictType((v.conflict_type or "").strip().upper())
            except ValueError:
                ctype = ConflictType.DIRECT_CONTRADICTION
            same = sources[fa.source_ref.doc_id].source_name == sources[fb.source_ref.doc_id].source_name
            rationale = (f"Open for cross-examination{' (same source contradicts itself)' if same else ''}: "
                         f"A {_describe(fa, sources, assessments)} vs B {_describe(fb, sources, assessments)}.")
            items.append(ContradictionItem(conflict_type=ctype, description=v.description, fact_a=fa, fact_b=fb,
                                           resolution_rationale=rationale, favored_fact_id=None))
        return items


def _describe(f: ExtractedFact, sources: Dict[str, SourceAssessment], assessments: Dict[str, FactAssessment]) -> str:
    s, a = sources[f.source_ref.doc_id], assessments[f.fact_id]
    return (f"{a.citation} {s.source_name} (Tier {s.reliability_tier}, {s.pub_date}, "
            f"{f.assertion_status.value if f.assertion_status else 'REPORTED'}, "
            f"{a.independent_source_count} independent source(s), credibility {a.credibility})")


def weigh(c: ContradictionItem, sources: Dict[str, SourceAssessment],
          assessments: Dict[str, FactAssessment]) -> Optional[str]:
    """The fact the evidence favours, used only in Heimdall's event verdict; the Case File keeps the conflict open.

    A self-contradicting source is left unresolved unless one statement is independently corroborated; a later
    correction or update from an equally reliable source wins; otherwise credibility plus corroboration decides.
    """
    fa, fb = c.fact_a, c.fact_b
    if fa is None or fb is None or fa.fact_id not in assessments or fb.fact_id not in assessments:
        return None
    sa, sb = sources[fa.source_ref.doc_id], sources[fb.source_ref.doc_id]
    aa, ab = assessments[fa.fact_id], assessments[fb.fact_id]
    if sa.source_name == sb.source_name:
        if aa.independent_source_count == ab.independent_source_count:
            return None
        return fa.fact_id if aa.independent_source_count > ab.independent_source_count else fb.fact_id
    if c.conflict_type in LATER_WINS and sa.pub_date != sb.pub_date:
        later, earlier = (fa, fb) if (sa.pub_date or "") > (sb.pub_date or "") else (fb, fa)
        if sources[later.source_ref.doc_id].reliability_tier <= sources[earlier.source_ref.doc_id].reliability_tier:
            return later.fact_id
    score_a = aa.credibility + 0.05 * (aa.independent_source_count - 1)
    score_b = ab.credibility + 0.05 * (ab.independent_source_count - 1)
    if abs(score_a - score_b) < 0.02:
        return None
    return fa.fact_id if score_a > score_b else fb.fact_id
