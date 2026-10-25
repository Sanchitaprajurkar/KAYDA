"""Spec 2 - Retrieve relevant documents: BM25 over resolved evidence paragraphs, scoped to the case."""

import math
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from agent_1.case.text import contains_term, norm, token_set, tokens
from agent_1.models.case_file import CaseScope, RejectedEvidence, RetrievedDocument
from agent_1.storage.evidence_store import ResolvedEvidenceStore

K1, B = 1.2, 0.75
ENTITY_WEIGHT = 1.5        # query terms that name a scoped country or commodity
COUNTRY_BOOST, SECTOR_BOOST, TITLE_BOOST = 1.0, 1.0, 0.5
MIN_RELATIVE_SCORE = 0.15  # drop documents scoring under 15% of the best match
SKIP_REJECTION_REASONS = {"UNRELATED_EVENT", "DUPLICATE_OF"}


class EvidenceRetriever:
    def __init__(self, store: ResolvedEvidenceStore):
        self.store = store
        self.paragraphs: List[Tuple[str, int, List[str]]] = []
        for did in store.evidence_ids():
            for idx, text in store.body_paragraphs(did):
                self.paragraphs.append((did, idx, tokens(text)))
        self.avg_len = sum(len(t) for _, _, t in self.paragraphs) / max(1, len(self.paragraphs))
        df = Counter(term for _, _, toks in self.paragraphs for term in set(toks))
        n = len(self.paragraphs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def _weights(self, scope: CaseScope) -> Dict[str, float]:
        entity_terms = {t for name in scope.countries + scope.event_countries + scope.commodities for t in tokens(name)}
        return {t: (ENTITY_WEIGHT if t in entity_terms else 1.0) for t in scope.search_terms}

    def _bm25(self, toks: List[str], weights: Dict[str, float]) -> Tuple[float, List[str]]:
        tf, score, matched = Counter(toks), 0.0, []
        for term, w in weights.items():
            if tf[term]:
                matched.append(term)
                score += w * self.idf.get(term, 0.0) * tf[term] * (K1 + 1) / (
                    tf[term] + K1 * (1 - B + B * len(toks) / self.avg_len))
        return score, matched

    def _in_scope(self, doc_id: str, scope: CaseScope, reference_countries: Sequence[str] = (),
                  shared_references: bool = False) -> bool:
        meta = self.store.document(doc_id).manifest_meta
        if not scope.event_identified:
            return True
        if meta.event_id == scope.event_id:
            return True
        if meta.source_type != "atlas":
            return False
        # Reference (atlas) documents are in scope when they concern a country in the case, or (on a re-search)
        # a country Odin asked about, or when they are shared references rather than a country profile.
        if shared_references and "profile" not in (meta.title or "").lower():
            return True
        names = scope.countries + scope.event_countries + list(reference_countries)
        return any((meta.country or "") == c or contains_term(meta.title or "", c) for c in names)

    def retrieve(self, scope: CaseScope, max_documents: int = 40, reference_countries: Sequence[str] = (),
                 shared_references: bool = False) -> List[RetrievedDocument]:
        weights = self._weights(scope)
        per_doc: Dict[str, List[Tuple[float, int, List[str]]]] = {}
        for did, idx, toks in self.paragraphs:
            score, matched = self._bm25(toks, weights)
            if score > 0:
                per_doc.setdefault(did, []).append((score, idx, matched))

        results = []
        for did, hits in per_doc.items():
            if not self._in_scope(did, scope, reference_countries, shared_references):
                continue
            hits.sort(reverse=True)
            meta = self.store.document(did).manifest_meta
            score = hits[0][0] + 0.5 * sum(h[0] for h in hits[1:3])
            reasons = []
            if meta.country in scope.countries + scope.event_countries:
                score += COUNTRY_BOOST
                reasons.append(f"country {meta.country}")
            if meta.sector in scope.sectors:
                score += SECTOR_BOOST
                reasons.append(f"sector {meta.sector}")
            title_hits = token_set(meta.title or "") & set(weights)
            if title_hits:
                score += TITLE_BOOST * len(title_hits)
            matched = sorted({t for h in hits for t in h[2]})
            reasons.insert(0, f"matched {', '.join(matched)}")
            if meta.source_type == "atlas":
                reasons.append("reference profile")
            results.append(RetrievedDocument(
                doc_id=did, title=meta.title, source_name=meta.source_name, source_type=meta.source_type,
                reliability_tier=meta.reliability_tier, pub_date=meta.pub_date, relevance_score=round(score, 3),
                matched_terms=matched, top_paragraphs=[h[1] for h in hits[:3]], reason="; ".join(reasons),
            ))

        results.sort(key=lambda r: (-r.relevance_score, r.doc_id))
        if results:
            floor = results[0].relevance_score * MIN_RELATIVE_SCORE
            results = [r for r in results if r.relevance_score >= floor]
        return results[:max_documents]

    def rejected(self, scope: CaseScope, limit: int = 20) -> List[RejectedEvidence]:
        """Relevant documents that trap resolution excluded, so the verdict can explain what was set aside."""
        weights = self._weights(scope)
        out = []
        for x in self.store.excluded_documents():
            reason = x["reasons"][0]
            if reason["reason"] in SKIP_REJECTION_REASONS:
                continue
            if scope.event_identified and x.get("event_id") != scope.event_id:
                continue
            claims = [f["statement"] for f in self.store.rejected_facts(x["doc_id"])]
            toks = tokens((x.get("title") or "") + " " + " ".join(claims))
            score, _ = self._bm25(toks, weights)
            if score <= 0:
                continue
            out.append(RejectedEvidence(
                doc_id=x["doc_id"], title=x.get("title"), source_name=x.get("source_name"),
                reliability_tier=int(x["reliability"]) if str(x.get("reliability", "")).isdigit() else None,
                pub_date=x.get("pub_date"), reason=reason["reason"], related_doc_id=reason.get("related_doc_id"),
                detail=reason.get("detail"), claims=claims[:5], relevance_score=round(score, 3),
            ))
        out.sort(key=lambda r: (-r.relevance_score, r.doc_id))
        return out[:limit]


def doc_text(store: ResolvedEvidenceStore, doc_id: str) -> str:
    return norm(" ".join(t for _, t in store.body_paragraphs(doc_id)))
