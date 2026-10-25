"""Factory for instantiating document parsers based on format or filename."""

from pathlib import Path
from typing import Optional, Dict

from agent_1.parsers.base import AbstractDocumentParser
from agent_1.parsers.pdf_parser import PDFParser
from agent_1.parsers.docx_parser import DocxParser
from agent_1.parsers.txt_parser import TxtParser
from agent_1.models.document import ParsedDocument, DocumentFormat
from agent_1.models.manifest import ManifestEntry
from agent_1.extraction.manifest_service import ManifestService


class ParserFactory:
    """Dispatches to format-specific parser implementations."""

    def __init__(self):
        self._parsers: Dict[str, AbstractDocumentParser] = {
            "PDF": PDFParser(),
            "DOCX": DocxParser(),
            "TXT": TxtParser(),
        }

    def get_parser(self, format_hint: str) -> AbstractDocumentParser:
        """Get parser by format name or file extension."""
        cleaned = format_hint.strip().lstrip(".").upper()
        if cleaned not in self._parsers:
            raise ValueError(f"Unsupported format '{format_hint}'. Supported: {list(self._parsers.keys())}")
        return self._parsers[cleaned]

    def parse_file(
        self,
        file_path: Path,
        doc_id: str,
        manifest_meta: Optional[ManifestEntry] = None,
    ) -> ParsedDocument:
        """Parse file using appropriate parser based on its file extension."""
        ext = file_path.suffix.lstrip(".").upper()
        parser = self.get_parser(ext)
        return parser.parse(file_path=file_path, doc_id=doc_id, manifest_meta=manifest_meta)

    def parse_by_doc_id(
        self,
        doc_id: str,
        manifest_service: Optional[ManifestService] = None,
    ) -> ParsedDocument:
        """Convenience method to locate and parse a document given its DOC_ID."""
        service = manifest_service or ManifestService()
        doc_meta = service.get_document(doc_id)
        if not doc_meta:
            raise ValueError(f"Document ID '{doc_id}' not found in manifest catalog.")

        file_path = service.get_document_file_path(doc_id)
        if not file_path or not file_path.exists():
            raise FileNotFoundError(f"File for '{doc_id}' not found on disk.")

        return self.parse_file(file_path=file_path, doc_id=doc_meta.doc_id, manifest_meta=doc_meta)
