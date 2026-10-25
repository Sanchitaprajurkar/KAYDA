import re
from typing import List, Dict, Optional, Tuple
from app.models.document import ParsedDocument

class SearchResult:
    def __init__(self, document: ParsedDocument, score: float, matched_snippets: List[str]):
        self.document = document
        self.score = score
        self.matched_snippets = matched_snippets

    def to_dict(self) -> dict:
        return {
            "doc_id": self.document.metadata.DOC_ID,
            "title": self.document.metadata.TITLE,
            "pub_date": self.document.metadata.PUB_DATE,
            "source_name": self.document.metadata.SOURCE_NAME,
            "reliability": self.document.metadata.RELIABILITY,
            "country": self.document.metadata.COUNTRY,
            "sector": self.document.metadata.SECTOR,
            "score": round(self.score, 4),
            "snippets": self.matched_snippets
        }

class HybridSearchEngine:
    def __init__(self, documents: Dict[str, ParsedDocument]):
        self.documents = documents

    def search(
        self,
        query: str,
        as_of_date: Optional[str] = None,
        country: Optional[str] = None,
        sector: Optional[str] = None,
        max_tier: Optional[int] = None,
        event_id: Optional[str] = None,
        limit: int = 10,
        exclude_retracted: bool = True
    ) -> List[SearchResult]:
        """
        Executes hybrid search with strict metadata filtering:
        - Clock Enforcement: Filters out any document where PUB_DATE > as_of_date
        - Source Hygiene: Filters out retracted documents or ranks by reliability
        """
        query_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        results = []

        for doc_id, doc in self.documents.items():
            meta = doc.metadata

            # 1. Clock Violation Check (As-of Date)
            if as_of_date and meta.PUB_DATE > as_of_date:
                continue

            # 2. Retraction Check
            if exclude_retracted and doc.is_retracted:
                continue

            # 3. Country Filter
            if country and country.lower() != "general":
                if meta.COUNTRY.lower() not in [country.lower(), "general"]:
                    # Also check content mention
                    if country.lower() not in doc.content.lower():
                        continue

            # 4. Sector Filter
            if sector and sector.lower() != "general":
                if meta.SECTOR.lower() not in [sector.lower(), "general"]:
                    if sector.lower() not in doc.content.lower():
                        continue

            # 5. Reliability Tier Filter
            if max_tier and meta.RELIABILITY > max_tier:
                continue

            # 6. Event ID Filter
            if event_id and event_id != "ANY":
                if meta.EVENT_ID != event_id and meta.EVENT_ID != "NONE":
                    continue

            # 7. Keyword & Density Scoring
            content_lower = doc.content.lower()
            title_lower = meta.TITLE.lower()
            
            term_matches = 0
            frequency_score = 0
            
            matched_snippets = []
            
            for term in query_terms:
                in_title = term in title_lower
                in_content = term in content_lower
                
                if in_title or in_content:
                    term_matches += 1
                    count = content_lower.count(term)
                    # Title matches get 3x boost
                    frequency_score += (count + (3 if in_title else 0))

            if term_matches == 0 and query_terms:
                continue

            # Find matching snippets from paragraphs
            for p in doc.paragraphs:
                p_lower = p.lower()
                matches = sum(1 for t in query_terms if t in p_lower)
                if matches > 0:
                    matched_snippets.append(p)
                    if len(matched_snippets) >= 2:
                        break

            # Calculate score with tier reliability weighting (Tier 1 is weighted higher)
            tier_multiplier = {1: 1.4, 2: 1.2, 3: 1.0, 4: 0.7}.get(meta.RELIABILITY, 1.0)
            score = (term_matches * 5.0 + frequency_score) * tier_multiplier

            results.append(SearchResult(
                document=doc,
                score=score,
                matched_snippets=matched_snippets or [doc.content[:200]]
            ))

        # Sort descending by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
