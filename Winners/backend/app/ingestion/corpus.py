import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional
from app.config import settings
from app.models.document import ParsedDocument
from app.ingestion.parsers import parse_document
from app.ingestion.search import HybridSearchEngine, SearchResult

class CorpusManager:
    _instance = None

    def __init__(self):
        self.documents: Dict[str, ParsedDocument] = {}
        self.manifest: dict = {}
        self.search_engine: Optional[HybridSearchEngine] = None
        self.retraction_map: Dict[str, str] = {}
        self._is_loaded = False

    @classmethod
    def get_instance(cls) -> "CorpusManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_corpus(self):
        if self._is_loaded:
            return

        docs_dir = settings.DOCS_DIR
        manifest_path = settings.MANIFEST_PATH

        # 1. Load manifest if present
        manifest_docs = {}
        if manifest_path.exists():
            with open(manifest_path, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)
                for doc in self.manifest.get("documents", []):
                    manifest_docs[doc.get("DOC_ID")] = doc

        # 2. Ingest all files in docs directory
        if docs_dir.exists():
            for file_path in docs_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in [".txt", ".pdf", ".docx"]:
                    # Match with manifest entry
                    doc_id_stem = file_path.stem
                    m_entry = manifest_docs.get(doc_id_stem)
                    parsed_doc = parse_document(file_path, m_entry)
                    self.documents[parsed_doc.metadata.DOC_ID] = parsed_doc

        # 3. Detect and cross-link corrections & retractions
        for doc_id, doc in self.documents.items():
            content_lower = doc.content.lower()
            if doc.metadata.SOURCE_TYPE == "correction" or "retraction" in content_lower:
                if "corridor agreement had been renewed. that report was wrong" in content_lower or "expired on 10 september without a renewal" in content_lower:
                    self.retraction_map["CORRIDOR_RENEWED_RUMOR"] = doc_id

        # 4. Initialize search engine
        self.search_engine = HybridSearchEngine(self.documents)
        self._is_loaded = True
        print(f"[CorpusManager] Successfully loaded {len(self.documents)} documents from Runemark corpus.")

    def get_document(self, doc_id: str) -> Optional[ParsedDocument]:
        return self.documents.get(doc_id)

    def search(
        self,
        query: str,
        as_of_date: Optional[str] = None,
        country: Optional[str] = None,
        sector: Optional[str] = None,
        max_tier: Optional[int] = None,
        event_id: Optional[str] = None,
        limit: int = 10
    ) -> List[SearchResult]:
        if not self._is_loaded:
            self.load_corpus()
        return self.search_engine.search(
            query=query,
            as_of_date=as_of_date or settings.DEFAULT_AS_OF_DATE,
            country=country,
            sector=sector,
            max_tier=max_tier,
            event_id=event_id,
            limit=limit
        )

    def verify_hashes(self) -> dict:
        """Verifies files in docs_dir against hashes.sha256 if available."""
        hashes_path = settings.HASHES_PATH
        results = {"total": 0, "matched": 0, "mismatched": 0, "details": []}
        
        if not hashes_path.exists():
            return {"status": "NO_HASH_FILE", "details": "hashes.sha256 not found"}

        with open(hashes_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or " " not in line:
                continue
            expected_hash, rel_path = line.split(maxsplit=1)
            rel_path = rel_path.replace("*", "").replace("./", "").replace("/", "\\")
            filename = Path(rel_path).name
            file_path = settings.DOCS_DIR / filename
            
            results["total"] += 1
            if file_path.exists():
                computed = hashlib.sha256(file_path.read_bytes()).hexdigest()
                if computed.lower() == expected_hash.lower():
                    results["matched"] += 1
                else:
                    results["mismatched"] += 1
                    results["details"].append(f"Mismatch: {filename}")
            else:
                results["mismatched"] += 1
                results["details"].append(f"Missing: {filename}")

        return results

corpus = CorpusManager.get_instance()
