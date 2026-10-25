import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.schemas.thor_claim import SearchFilter, SearchResult
from backend.services.runemark import (
    DOCS_DIR,
    KNOWN_RETRACTIONS,
    MANIFEST_PATH,
    DocumentParser,
    ParsedDocument,
)

class SearchProvider(ABC):
    """
    Abstract interface for Runemark corpus search.
    Enforces loose coupling so Thor can operate with real or fake providers.
    """

    @abstractmethod
    def search(self, query: str, filters: SearchFilter, limit: int = 10) -> List[SearchResult]:
        pass

    @abstractmethod
    def get_document(self, doc_id: str) -> Optional[ParsedDocument]:
        pass

class RunemarkCorpusSearchProvider(SearchProvider):
    """
    Concrete search provider indexing real Runemark documents and manifest files.
    Enforces simulated clock constraints, query deduplication, and metadata filters.
    """

    def __init__(self, manifest_path: Optional[Path] = None, docs_dir: Optional[Path] = None):
        self.manifest_path = manifest_path or MANIFEST_PATH
        self.docs_dir = docs_dir or DOCS_DIR
        self.manifest_docs: Dict[str, Dict[str, Any]] = {}
        self.parsed_cache: Dict[str, ParsedDocument] = {}
        self.query_history: Set[str] = set()
        self.query_cache: Dict[str, List[SearchResult]] = {}
        self.query_count: int = 0
        self.max_queries: int = 50
        self._load_corpus()

    def _load_corpus(self):
        if not self.manifest_path.exists():
            return

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
            for d in manifest_data.get("documents", []):
                doc_id = (d.get("DOC_ID") or d.get("doc_id") or "").upper()
                if doc_id:
                    self.manifest_docs[doc_id] = d

    def get_document(self, doc_id: str) -> Optional[ParsedDocument]:
        doc_id_clean = doc_id.upper()
        if doc_id_clean in self.parsed_cache:
            return self.parsed_cache[doc_id_clean]

        manifest_entry = self.manifest_docs.get(doc_id_clean)
        if not manifest_entry:
            return None

        file_name = manifest_entry.get("file") or manifest_entry.get("file_name")
        if not file_name:
            file_name = f"{doc_id_clean}.txt"

        file_path = self.docs_dir / file_name
        if not file_path.exists():
            for candidate in self.docs_dir.glob(f"{doc_id_clean}.*"):
                file_path = candidate
                break

        if not file_path.exists():
            return None

        parsed = DocumentParser.parse_file(file_path)
        if manifest_entry.get("TITLE") and not parsed.title:
            parsed.title = manifest_entry.get("TITLE")
        if manifest_entry.get("PUB_DATE"):
            parsed.pub_date = manifest_entry.get("PUB_DATE")
        if manifest_entry.get("RELIABILITY"):
            try:
                parsed.reliability = int(manifest_entry.get("RELIABILITY"))
            except ValueError:
                pass
        if manifest_entry.get("COUNTRY"):
            parsed.country = manifest_entry.get("COUNTRY")
        if manifest_entry.get("SECTOR"):
            parsed.sector = manifest_entry.get("SECTOR")

        self.parsed_cache[doc_id_clean] = parsed
        return parsed

    def search(self, query: str, filters: SearchFilter, limit: int = 10) -> List[SearchResult]:
        cache_key = f"{query.strip().lower()}|{filters.model_dump_json()}"
        if cache_key in self.query_cache:
            return self.query_cache[cache_key][:limit]

        self.query_count += 1
        if self.query_count > self.max_queries:
            raise ValueError(
                f"Search query limit exceeded: maximum {self.max_queries} queries allowed per session (NFR5)."
            )

        self.query_history.add(query.strip().lower())
        as_of_dt = datetime.strptime(filters.as_of_date, "%Y-%m-%d").date()
        query_tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        results: List[Tuple[float, SearchResult]] = []

        for doc_id, meta in self.manifest_docs.items():
            # 1. Simulated Clock Rule: Exclude future documents (Clock Violation Prevention)
            pub_date_str = meta.get("PUB_DATE") or meta.get("pub_date") or "1970-01-01"
            try:
                pub_dt = datetime.strptime(pub_date_str, "%Y-%m-%d").date()
                if pub_dt > as_of_dt:
                    continue
            except ValueError:
                continue

            # 2. Retraction check
            is_retracted = doc_id in KNOWN_RETRACTIONS
            if filters.exclude_retracted and is_retracted:
                continue

            # 3. Event filter (exclude unrelated events and lifestyle/entertainment)
            event_id = meta.get("EVENT_ID") or meta.get("event_id") or "NONE"
            if filters.event_id and filters.event_id.upper() != "NONE":
                if event_id != filters.event_id:
                    if event_id != "NONE":
                        continue
                    t_low = (meta.get("TITLE") or "").lower()
                    if any(unrelated in t_low for unrelated in ["chef", "dance", "fair", "tour", "theatre", "festival"]):
                        continue

            # 4. Country filter
            country = meta.get("COUNTRY") or meta.get("country") or ""
            if filters.country and filters.country.lower() != "all":
                if filters.country.lower() not in country.lower():
                    continue

            # 5. Sector filter with metadata mismatch resolution (e.g. ORV-0029 & ORV-0030)
            doc_parsed = self.get_document(doc_id)
            sector = meta.get("SECTOR") or meta.get("sector") or ""
            effective_sector = doc_parsed.resolved_sector if (doc_parsed and doc_parsed.has_sector_mismatch) else sector

            if filters.sector and filters.sector.lower() != "all" and filters.sector.lower() != "general":
                target_sec = filters.sector.lower()
                if target_sec not in effective_sector.lower() and effective_sector.lower() != "general":
                    continue

            # 6. Source type filter
            source_type = (meta.get("SOURCE_TYPE") or meta.get("source_type") or "").lower()
            if filters.source_type:
                if isinstance(filters.source_type, list):
                    if not any(st.lower() in source_type for st in filters.source_type):
                        continue
                elif filters.source_type.lower() not in source_type:
                    continue

            # 7. Reliability Tier filter
            try:
                rel = int(meta.get("RELIABILITY") or meta.get("reliability") or 4)
            except ValueError:
                rel = 4

            if filters.min_reliability and rel < filters.min_reliability:
                continue
            if filters.max_reliability and rel > filters.max_reliability:
                continue

            # 8. Query match and scoring
            doc_parsed = self.get_document(doc_id)
            title = meta.get("TITLE") or meta.get("title") or ""
            source_name = meta.get("SOURCE_NAME") or meta.get("source_name") or ""
            body_text = doc_parsed.body_text if doc_parsed else ""
            searchable_text = f"{title} {country} {sector} {source_name} {body_text}".lower()

            matched_terms = []
            score = 0.0

            if not query_tokens:
                score = 1.0
            else:
                for token in query_tokens:
                    if token in searchable_text:
                        matched_terms.append(token)
                        weight = 3.0 if (token in title.lower() or token in country.lower() or token in sector.lower()) else 1.0
                        score += weight

            if query_tokens and score == 0.0:
                continue

            excerpt = ""
            if doc_parsed and doc_parsed.paragraphs:
                for pid, ptext in doc_parsed.paragraphs.items():
                    if any(t in ptext.lower() for t in matched_terms) or not matched_terms:
                        excerpt = f"[{pid}] {ptext}"
                        break
            if not excerpt:
                excerpt = (body_text[:280] + "...") if len(body_text) > 280 else body_text

            sr = SearchResult(
                doc_id=doc_id,
                title=title,
                source_name=source_name,
                source_type=source_type,
                reliability=rel,
                pub_date=pub_date_str,
                country=country,
                sector=sector,
                event_id=event_id,
                excerpt=excerpt.strip(),
                score=score,
                is_retracted=is_retracted,
                matched_terms=matched_terms,
            )
            results.append((score, sr))

        results.sort(key=lambda x: x[0], reverse=True)
        deduped: List[SearchResult] = []
        seen_ids = set()
        for _, sr in results:
            if sr.doc_id not in seen_ids:
                seen_ids.add(sr.doc_id)
                deduped.append(sr)

        final_results = deduped[:limit]
        self.query_cache[cache_key] = final_results
        return final_results

class FakeSearchProvider(SearchProvider):
    """
    In-memory mock search provider for 100% deterministic, ultra-fast unit testing.
    Does not require disk IO or real dataset files.
    """

    def __init__(self, documents: Optional[List[ParsedDocument]] = None):
        self.docs: Dict[str, ParsedDocument] = {}
        if documents:
            for d in documents:
                self.docs[d.doc_id.upper()] = d
        self.query_history: List[str] = []

    def add_document(self, doc: ParsedDocument):
        self.docs[doc.doc_id.upper()] = doc

    def get_document(self, doc_id: str) -> Optional[ParsedDocument]:
        return self.docs.get(doc_id.upper())

    def search(self, query: str, filters: SearchFilter, limit: int = 10) -> List[SearchResult]:
        self.query_history.append(query)
        as_of_dt = datetime.strptime(filters.as_of_date, "%Y-%m-%d").date()
        tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
        matches: List[SearchResult] = []

        for doc_id, doc in self.docs.items():
            try:
                pub_dt = datetime.strptime(doc.pub_date, "%Y-%m-%d").date()
                if pub_dt > as_of_dt:
                    continue
            except ValueError:
                continue

            if filters.exclude_retracted and doc.is_retracted:
                continue

            if filters.event_id and filters.event_id != "NONE":
                if doc.event_id != filters.event_id:
                    if doc.event_id != "NONE":
                        continue
                    t_low = doc.title.lower()
                    if any(unrelated in t_low for unrelated in ["chef", "dance", "fair", "tour", "theatre", "festival"]):
                        continue

            if filters.country and filters.country.lower() != "all" and filters.country.lower() not in doc.country.lower():
                continue

            eff_sec = doc.resolved_sector if doc.has_sector_mismatch else doc.sector
            if filters.sector and filters.sector.lower() != "all" and filters.sector.lower() != "general":
                if filters.sector.lower() not in eff_sec.lower() and eff_sec.lower() != "general":
                    continue

            if filters.min_reliability and doc.reliability < filters.min_reliability:
                continue
            if filters.max_reliability and doc.reliability > filters.max_reliability:
                continue

            text = f"{doc.title} {doc.country} {doc.sector} {doc.body_text}".lower()
            matched = [t for t in tokens if t in text]
            if tokens and not matched:
                continue

            excerpt = doc.body_text[:200]
            if doc.paragraphs:
                first_k = next(iter(doc.paragraphs))
                excerpt = f"[{first_k}] {doc.paragraphs[first_k]}"

            matches.append(SearchResult(
                doc_id=doc.doc_id,
                title=doc.title,
                source_name=doc.source_name,
                source_type=doc.source_type,
                reliability=doc.reliability,
                pub_date=doc.pub_date,
                country=doc.country,
                sector=doc.sector,
                event_id=doc.event_id,
                excerpt=excerpt,
                score=float(len(matched) or 1),
                is_retracted=doc.is_retracted,
                matched_terms=matched,
            ))

        matches.sort(key=lambda x: x.score, reverse=True)
        return matches[:limit]
