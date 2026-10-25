"""Spec 3 & 4 - Analyse evidence and assess source credibility.

Organises retrieved facts (by category, commodity, country, metrics, timeline) and scores every source and fact:
  - reliability tier (labels follow the outlet guide in ATL-0012)
  - publication date and validity at the as-of date
  - independence: which other outlets a document relies on, and corroboration across independent outlets
"""

import re
from collections import defaultdict
from datetime import date
from typing import Dict, List, Optional, Tuple

from agent_1.case.text import contains_term, token_set
from agent_1.models.case_file import (
    CaseScope, EvidenceDigest, FactAssessment, MetricRecord, SourceAssessment, TimelineEntry,
)
from agent_1.models.document import ParsedDocument
from agent_1.models.evidence import ExtractedFact
from agent_1.storage.evidence_store import ResolvedEvidenceStore

TIER_LABELS = {1: "Official", 2: "Reputable (wire, business daily, trade press)",
               3: "Regional paper or analyst firm", 4: "Weak (social post, blog, tabloid)"}
TIER_BASE = {1: 0.95, 2: 0.85, 3: 0.6, 4: 0.25}
ASSERTION_WEIGHT = {"CONFIRMED": 1.0, "CORRECTED": 1.0, "RETRACTED": 1.0, "REPORTED": 0.85, "DENIED": 0.6,
                    "PROJECTED": 0.6, "PROPOSED": 0.55, "ALLEGED": 0.5, "RUMOURED": 0.3}
SIMILARITY_THRESHOLD = 0.45
SOURCE_TYPE_NOTES = {
    "analyst_note": "Analyst estimate: check assumptions and whether figures are point estimates.",
    "company_statement": "Company statement: self-interested party.",
    "correction": "Correction notice: supersedes the outlet's earlier report.",
}


def citation(fact: ExtractedFact) -> str:
    return fact.source_ref.to_citation_str()


def _attributes_to(text: str, outlet: str) -> bool:
    """True when the text attributes information to the outlet, not merely mentions it."""
    o = re.escape(outlet)
    return re.search(
        rf"\b(according to|reported by|data from|figures from|citing|cited by|quoted by|told)\s+(the\s+)?{o}\b"
        rf"|\b{o}('s)?\s+(said|says|reported|reports|told|data|figures|estimates?|index|notice|return)\b"
        rf"|\bfollowed the\s+{o}\b",
        text, re.I) is not None


class EvidenceAnalyst:
    def __init__(self, store: ResolvedEvidenceStore, countries: List[str], commodities: List[str]):
        self.store = store
        self.countries = countries
        self.commodities = commodities
        self.outlets = sorted({store.document(d).manifest_meta.source_name for d in store.evidence_ids()
                               if store.document(d).manifest_meta}
                              | {x.get("source_name") for x in store.excluded_documents() if x.get("source_name")})

    # ── annotation ───────────────────────────────────────────────────────────

    def _terms(self, text: str, names: List[str]) -> List[str]:
        return [n for n in names if contains_term(text, n)]

    def annotate(self, fact: ExtractedFact, doc: ParsedDocument) -> Tuple[List[str], List[str]]:
        """Countries and commodities a fact is about; falls back to the document's title and metadata."""
        text = f"{fact.subject} {fact.statement}"
        meta = doc.manifest_meta
        countries = self._terms(text, self.countries) or (
            self._terms(meta.title or "", self.countries) or ([meta.country] if meta.country in self.countries else []))
        commodities = self._terms(text, self.commodities) or (
            self._terms(meta.title or "", self.commodities) or ([meta.sector] if meta.sector in self.commodities else []))
        return countries, commodities

    # ── credibility ──────────────────────────────────────────────────────────

    def assess_sources(self, doc_ids: List[str], as_of: str) -> Dict[str, SourceAssessment]:
        cutoff = date.fromisoformat(as_of)
        out = {}
        for did in doc_ids:
            meta = self.store.document(did).manifest_meta
            text = " ".join(t for _, t in self.store.body_paragraphs(did))
            cites = [o for o in self.outlets if o != meta.source_name and _attributes_to(text, o)]
            try:
                days = (cutoff - date.fromisoformat(meta.pub_date)).days
            except (TypeError, ValueError):
                days = None
            valid = days is not None and days >= 0
            tier = meta.reliability_tier
            notes = [n for k, n in SOURCE_TYPE_NOTES.items() if meta.source_type == k]
            if cites:
                notes.append(f"Relies on {', '.join(cites)}; not independent of {'them' if len(cites) > 1 else 'it'}.")
            out[did] = SourceAssessment(
                doc_id=did, source_name=meta.source_name, source_type=meta.source_type, reliability_tier=tier,
                tier_label=TIER_LABELS.get(tier, "Unknown"), pub_date=meta.pub_date, days_before_as_of=days,
                temporally_valid=valid, cites_sources=cites,
                credibility_score=round(TIER_BASE.get(tier, 0.5) if valid else 0.0, 3), notes=notes,
            )
        return out

    def _independent(self, a: SourceAssessment, b: SourceAssessment) -> bool:
        return (a.source_name != b.source_name and b.source_name not in a.cites_sources
                and a.source_name not in b.cites_sources)

    @staticmethod
    def _similar(fa: ExtractedFact, fb: ExtractedFact, ta: set, tb: set,
                 aa: Tuple[List[str], List[str]], ab: Tuple[List[str], List[str]]) -> bool:
        # Facts about different countries or commodities never corroborate each other.
        for xa, xb in zip(aa, ab):
            if xa and xb and not set(xa) & set(xb):
                return False
        if fa.numeric_value is not None and fb.numeric_value is not None:
            return (fa.numeric_value == fb.numeric_value
                    and (fa.unit or "").lower() == (fb.unit or "").lower() and len(ta & tb) >= 2)
        shared = ta & tb
        return len(shared) >= 3 and len(shared) / len(ta | tb) >= SIMILARITY_THRESHOLD

    def assess_facts(self, facts: List[ExtractedFact], sources: Dict[str, SourceAssessment]
                     ) -> Dict[str, FactAssessment]:
        toks = {f.fact_id: token_set(f"{f.subject} {f.statement}") for f in facts}
        ann = {f.fact_id: self.annotate(f, self.store.document(f.source_ref.doc_id)) for f in facts}
        corroboration: Dict[str, List[str]] = defaultdict(list)
        for i, fa in enumerate(facts):
            for fb in facts[i + 1:]:
                sa, sb = sources[fa.source_ref.doc_id], sources[fb.source_ref.doc_id]
                if self._independent(sa, sb) and self._similar(fa, fb, toks[fa.fact_id], toks[fb.fact_id],
                                                               ann[fa.fact_id], ann[fb.fact_id]):
                    corroboration[fa.fact_id].append(fb.fact_id)
                    corroboration[fb.fact_id].append(fa.fact_id)

        by_id = {f.fact_id: f for f in facts}
        out = {}
        for f in facts:
            src = sources[f.source_ref.doc_id]
            countries, commodities = ann[f.fact_id]
            outlets = {src.source_name} | {sources[by_id[c].source_ref.doc_id].source_name for c in corroboration[f.fact_id]}
            status = f.assertion_status.value if f.assertion_status else "REPORTED"
            score = src.credibility_score * ASSERTION_WEIGHT.get(status, 0.7) * (f.confidence or 1.0)
            score = min(1.0, score + 0.03 * (len(outlets) - 1))
            text = f"{f.subject} {f.statement}"
            out[f.fact_id] = FactAssessment(
                fact_id=f.fact_id, doc_id=f.source_ref.doc_id, citation=citation(f), credibility=round(score, 3),
                corroborated_by=corroboration[f.fact_id], independent_source_count=len(outlets),
                countries=countries, commodities=commodities,
                stated_countries=self._terms(text, self.countries),
                stated_commodities=self._terms(text, self.commodities),
            )
        return out

    # ── organisation ─────────────────────────────────────────────────────────

    def digest(self, facts: List[ExtractedFact], assessments: Dict[str, FactAssessment],
               sources: Dict[str, SourceAssessment]) -> EvidenceDigest:
        d = EvidenceDigest()
        for f in facts:
            a = assessments[f.fact_id]
            d.by_category.setdefault(f.category.value, []).append(f.fact_id)
            for c in a.commodities:
                d.by_commodity.setdefault(c, []).append(f.fact_id)
            for c in a.countries:
                d.by_country.setdefault(c, []).append(f.fact_id)
            pub = sources[f.source_ref.doc_id].pub_date
            if f.numeric_value is not None:
                d.metrics.append(MetricRecord(
                    fact_id=f.fact_id, citation=a.citation, category=f.category.value, subject=f.subject,
                    value=f.numeric_value, unit=f.unit, date_mentioned=f.date_mentioned, pub_date=pub,
                    countries=a.countries, commodities=a.commodities))
            d.timeline.append(TimelineEntry(
                pub_date=pub, date_mentioned=f.date_mentioned, fact_id=f.fact_id, citation=a.citation,
                statement=f.statement, assertion_status=f.assertion_status.value if f.assertion_status else None))
        d.timeline.sort(key=lambda t: (t.pub_date or "", t.citation))
        d.metrics.sort(key=lambda m: (m.category, m.subject.lower(), m.pub_date or ""))
        return d

    def missing_trade_data(self, scope: CaseScope, assessments: Dict[str, FactAssessment],
                           facts: List[ExtractedFact]) -> List[Tuple[str, str]]:
        """(country, commodity) pairs in scope with no trade-flow fact at all; reported, never estimated."""
        trade = {"TRADE_VOLUME", "GRAIN_OR_INVENTORY", "TARIFF_OR_PRICE"}
        covered = {(c, k) for f in facts if f.category.value in trade
                   for c in assessments[f.fact_id].countries for k in assessments[f.fact_id].commodities}
        importers = [c for c in scope.countries if c not in scope.event_countries]
        return [(c, k) for c in importers for k in scope.commodities if (c, k) not in covered]


def source_name_of(sources: Dict[str, SourceAssessment], doc_id: str) -> Optional[str]:
    s = sources.get(doc_id)
    return s.source_name if s else None
