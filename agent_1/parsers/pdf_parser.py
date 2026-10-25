"""PDF parser supporting PyMuPDF (fitz) with graceful fallback to pypdf."""

from pathlib import Path
from typing import Optional, List
import logging

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

from agent_1.parsers.base import AbstractDocumentParser
from agent_1.models.document import (
    ParsedDocument,
    DocumentParagraph,
    DocumentFormat,
)
from agent_1.models.manifest import ManifestEntry

logger = logging.getLogger(__name__)


class PDFParser(AbstractDocumentParser):
    """Parses PDF documents into structured paragraphs retaining page and paragraph coordinates."""

    @property
    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.PDF

    def parse(
        self,
        file_path: Path,
        doc_id: str,
        manifest_meta: Optional[ManifestEntry] = None,
    ) -> ParsedDocument:
        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        if HAS_FITZ:
            return self._parse_with_fitz(file_path, doc_id, manifest_meta)
        elif HAS_PYPDF:
            return self._parse_with_pypdf(file_path, doc_id, manifest_meta)
        else:
            raise ImportError("Neither PyMuPDF (fitz) nor pypdf is installed.")

    def _parse_with_fitz(
        self,
        file_path: Path,
        doc_id: str,
        manifest_meta: Optional[ManifestEntry] = None,
    ) -> ParsedDocument:
        doc = fitz.open(str(file_path))
        paragraphs: List[DocumentParagraph] = []
        full_text_chunks: List[str] = []
        global_para_index = 1
        total_pages = len(doc)

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]

            blocks = page.get_text("blocks")
            for b in blocks:
                if len(b) >= 7 and b[6] != 0:
                    continue  # skip image blocks
                block_text = b[4].strip() if len(b) > 4 else ""
                if not block_text:
                    continue

                cleaned_lines = [line.strip() for line in block_text.splitlines() if line.strip()]
                normalized_text = " ".join(cleaned_lines)
                if not normalized_text:
                    continue

                paragraphs.append(
                    DocumentParagraph.create(
                        index=global_para_index,
                        text=normalized_text,
                        page_number=page_num,
                    )
                )
                full_text_chunks.append(normalized_text)
                global_para_index += 1

        doc.close()
        full_text = "\n\n".join(full_text_chunks)
        return ParsedDocument(
            doc_id=doc_id,
            file_name=file_path.name,
            file_path=str(file_path.resolve()),
            format=DocumentFormat.PDF,
            manifest_meta=manifest_meta,
            paragraphs=paragraphs,
            full_text=full_text,
            total_paragraphs=len(paragraphs),
            total_pages=total_pages,
        )

    def _parse_with_pypdf(
        self,
        file_path: Path,
        doc_id: str,
        manifest_meta: Optional[ManifestEntry] = None,
    ) -> ParsedDocument:
        reader = pypdf.PdfReader(str(file_path))
        paragraphs: List[DocumentParagraph] = []
        full_text_chunks: List[str] = []
        global_para_index = 1
        total_pages = len(reader.pages)

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = reader.pages[page_idx]
            page_text = page.extract_text() or ""
            
            raw_blocks = [b.strip() for b in page_text.split("\n\n") if b.strip()]
            for block in raw_blocks:
                cleaned = " ".join(line.strip() for line in block.splitlines() if line.strip())
                if not cleaned:
                    continue
                paragraphs.append(
                    DocumentParagraph.create(
                        index=global_para_index,
                        text=cleaned,
                        page_number=page_num,
                    )
                )
                full_text_chunks.append(cleaned)
                global_para_index += 1

        full_text = "\n\n".join(full_text_chunks)
        return ParsedDocument(
            doc_id=doc_id,
            file_name=file_path.name,
            file_path=str(file_path.resolve()),
            format=DocumentFormat.PDF,
            manifest_meta=manifest_meta,
            paragraphs=paragraphs,
            full_text=full_text,
            total_paragraphs=len(paragraphs),
            total_pages=total_pages,
        )
