"""Plain text parser with paragraph segmentation and citation coordinates."""

import re
from pathlib import Path
from typing import Optional, List

from heimdall.parsers.base import AbstractDocumentParser
from heimdall.models.document import (
    ParsedDocument,
    DocumentParagraph,
    DocumentFormat,
)
from heimdall.models.manifest import ManifestEntry


_BOMS = [(b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")]


def _decode_single(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _decode(data: bytes) -> str:
    """Decode bytes, handling files whose body switches to UTF-16 after an ASCII header."""
    for bom, encoding in _BOMS:
        pos = data.find(bom)
        if pos != -1:
            head = _decode_single(data[:pos])
            body = data[pos + len(bom):].decode(encoding, errors="replace")
            return (head + body).replace("\r\n", "\n")
    return _decode_single(data).replace("\r\n", "\n")


class TxtParser(AbstractDocumentParser):
    """Parses plain text (.txt) documents into indexed paragraphs."""

    @property
    def supported_format(self) -> DocumentFormat:
        return DocumentFormat.TXT

    def parse(
        self,
        file_path: Path,
        doc_id: str,
        manifest_meta: Optional[ManifestEntry] = None,
    ) -> ParsedDocument:
        if not file_path.exists():
            raise FileNotFoundError(f"TXT file not found: {file_path}")

        raw_content = _decode(file_path.read_bytes())

        paragraphs: List[DocumentParagraph] = []
        full_text_chunks: List[str] = []

        # Split on double line breaks to isolate natural paragraphs
        raw_blocks = re.split(r"\n\s*\n", raw_content)
        para_index = 1

        for block in raw_blocks:
            clean = block.strip()
            if not clean:
                continue
            # Normalize internal single newlines to spaces
            normalized = " ".join([line.strip() for line in clean.splitlines() if line.strip()])
            if not normalized:
                continue

            paragraphs.append(
                DocumentParagraph.create(
                    index=para_index,
                    text=normalized,
                    page_number=None,
                )
            )
            full_text_chunks.append(normalized)
            para_index += 1

        full_text = "\n\n".join(full_text_chunks)
        return ParsedDocument(
            doc_id=doc_id,
            file_name=file_path.name,
            file_path=str(file_path.resolve()),
            format=DocumentFormat.TXT,
            manifest_meta=manifest_meta,
            paragraphs=paragraphs,
            full_text=full_text,
            total_paragraphs=len(paragraphs),
            total_pages=None,
        )
