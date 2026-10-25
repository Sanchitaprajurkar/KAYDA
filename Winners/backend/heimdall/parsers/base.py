"""Abstract base class for all Runemark document format parsers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from heimdall.models.document import ParsedDocument, DocumentFormat
from heimdall.models.manifest import ManifestEntry


class AbstractDocumentParser(ABC):
    """Base parser defining the interface for document ingestion with paragraph indexing."""

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        doc_id: str,
        manifest_meta: Optional[ManifestEntry] = None,
    ) -> ParsedDocument:
        """Parse source document into structured ParsedDocument with 1-indexed paragraphs."""
        pass

    @property
    @abstractmethod
    def supported_format(self) -> DocumentFormat:
        """The document format handled by this parser."""
        pass
