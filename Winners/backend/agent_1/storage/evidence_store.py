"""Read-only access to the trap-resolved evidence (output of resolve_traps.py)."""

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

from agent_1.models.document import ParsedDocument
from agent_1.models.evidence import ExtractedEntity, ExtractedFact

DEFAULT_RESOLVED_DIR = Path(__file__).resolve().parent.parent.parent / "resolved_data"
_HEADER_LINE = re.compile(r"^\s*(DOC_ID|EVENT_ID|TITLE|SOURCE_NAME|SOURCE_TYPE|RELIABILITY|PUB_DATE|PUB_TIME|"
                          r"COUNTRY|SECTOR|LANGUAGE)\s*:")
_LABEL = re.compile(r"^\s*\[P\d+\]\s*")


class ExcludedDocumentError(ValueError):
    """Raised when a case asks for a document that trap resolution kept out of evidence."""

    def __init__(self, doc_id: str, reasons: List[dict]):
        self.doc_id = doc_id
        self.reasons = reasons
        first = reasons[0]
        related = f" (see {first['related_doc_id']})" if first.get("related_doc_id") else ""
        super().__init__(f"{doc_id} is not admissible evidence: {first['reason']} - {first.get('detail', '')}{related}")


@dataclass
class ResolvedRef:
    requested_id: str
    doc_id: str                      # canonical evidence document
    alias_kind: Optional[str] = None  # EXACT / TRUNCATED / EMPTY_FALLBACK when requested_id was a duplicate


class ResolvedEvidenceStore:
    """Serves only clean, citable evidence; duplicates resolve to their canonical document."""

    def __init__(self, resolved_dir: Optional[Path] = None):
        self.dir = Path(resolved_dir or DEFAULT_RESOLVED_DIR)
        if not (self.dir / "documents").exists():
            raise FileNotFoundError(
                f"Resolved evidence not found at {self.dir}. Run 'python -m agent_1.resolve_traps' first.")
        self._aliases: Dict[str, dict] = {
            a["alias_doc_id"]: a for a in self._read(self.dir / "document_aliases.json")}
        self._excluded: Dict[str, dict] = {
            x["doc_id"]: x for x in self._read(self.dir / "quarantine" / "excluded_documents.json")}

    @staticmethod
    def _read(path: Path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def resolve(self, doc_id: str) -> ResolvedRef:
        """Map a requested ID to the evidence document to use, or raise if it is not admissible."""
        requested = doc_id.strip().upper()
        alias = self._aliases.get(requested)
        if alias:
            return ResolvedRef(requested, alias["canonical_doc_id"], alias["kind"])
        if requested in self._excluded:
            raise ExcludedDocumentError(requested, self._excluded[requested]["reasons"])
        if not (self.dir / "documents" / f"{requested}.json").exists():
            raise KeyError(f"Unknown document ID: {requested}")
        return ResolvedRef(requested, requested)

    @lru_cache(maxsize=None)
    def document(self, doc_id: str) -> ParsedDocument:
        return ParsedDocument.model_validate(self._read(self.dir / "documents" / f"{doc_id}.json"))

    @property
    def corpus(self) -> dict:
        return self._read(self.dir / "corpus.json") or {}

    def evidence_ids(self) -> List[str]:
        return sorted(p.stem for p in (self.dir / "documents").glob("*.json"))

    def excluded_documents(self) -> List[dict]:
        return list(self._excluded.values())

    @lru_cache(maxsize=None)
    def _rejected_by_doc(self) -> Dict[str, List[dict]]:
        out: Dict[str, List[dict]] = {}
        for f in self._read(self.dir / "quarantine" / "rejected_facts.json"):
            out.setdefault(f["doc_id"], []).append(f)
        return out

    def rejected_facts(self, doc_id: str) -> List[dict]:
        return self._rejected_by_doc().get(doc_id, [])

    def body_paragraphs(self, doc_id: str) -> List[tuple]:
        """(paragraph_index, text) for content paragraphs, with metadata header lines stripped."""
        out = []
        for p in self.document(doc_id).paragraphs:
            text = p.raw_text
            if "---" in text:
                text = text.split("---", 1)[1]
            elif _HEADER_LINE.match(text):
                continue
            text = _LABEL.sub("", text).strip()
            if text:
                out.append((p.paragraph_index, text))
        return out

    def facts(self, doc_id: str) -> List[ExtractedFact]:
        return [ExtractedFact.model_validate(f) for f in self._read(self.dir / "facts" / f"{doc_id}_facts.json")]

    def entities(self, doc_id: str) -> List[ExtractedEntity]:
        return [ExtractedEntity.model_validate(e)
                for e in self._read(self.dir / "entities" / f"{doc_id}_entities.json")]
