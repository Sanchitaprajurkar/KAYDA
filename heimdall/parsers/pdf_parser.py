"""PDF parser using PyMuPDF (fitz) with page and paragraph level mapping."""

from pathlib import Path
from typing import Optional, List
import fitz  # PyMuPDF

from heimdall.parsers.base import AbstractDocumentParser
from heimdall.models.document import (
    ParsedDocument,
    DocumentParagraph,
    DocumentFormat,
)
from heimdall.models.manifest import ManifestEntry


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

        doc = fitz.open(str(file_path))
        paragraphs: List[DocumentParagraph] = []
        full_text_chunks: List[str] = []
        global_para_index = 1
        total_pages = len(doc)

        for page_idx in range(total_pages):
            page_num = page_idx + 1
            page = doc[page_idx]

            # get_text("blocks") returns tuples: (x0, y0, x1, y1, "text", block_no, block_type)
            # block_type 0 = text, 1 = image
            blocks = page.get_text("blocks")
            for b in blocks:
                if len(b) >= 7 and b[6] != 0:
                    continue  # skip image blocks
                block_text = b[4].strip() if len(b) > 4 else ""
                if not block_text:
                    continue

                # Clean and normalize newlines inside paragraph
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
