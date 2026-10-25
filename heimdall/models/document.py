"""Pydantic schemas for parsed document representations and citations."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from heimdall.models.manifest import ManifestEntry


class DocumentFormat(str, Enum):
    """Supported file formats."""
    PDF = "PDF"
    TXT = "TXT"
    DOCX = "DOCX"


class ParagraphRef(BaseModel):
    """Exact citation reference for evidence traceability."""

    doc_id: str = Field(description="Document identifier e.g. ATL-0001, ORV-0004")
    file_name: str = Field(description="Filename e.g. ORV-0004.pdf")
    page_number: Optional[int] = Field(default=None, description="1-indexed page number if PDF")
    paragraph_index: int = Field(default=1, description="1-indexed paragraph number within the document")
    text_snippet: Optional[str] = Field(default=None, description="Exact quotation or text excerpt")

    def to_citation_str(self) -> str:
        """Render a clean citation label."""
        if self.page_number is not None:
            return f"[{self.doc_id} p.{self.page_number} ¶{self.paragraph_index}]"
        return f"[{self.doc_id} ¶{self.paragraph_index}]"


class DocumentParagraph(BaseModel):
    """A distinct structural paragraph parsed from a source file."""

    paragraph_index: int = Field(description="1-indexed paragraph index")
    page_number: Optional[int] = Field(default=None, description="Page number if applicable")
    raw_text: str = Field(description="Extracted paragraph text")
    char_count: int = Field(default=0)
    word_count: int = Field(default=0)

    @classmethod
    def create(cls, index: int, text: str, page_number: Optional[int] = None) -> "DocumentParagraph":
        clean = text.strip()
        return cls(
            paragraph_index=index,
            page_number=page_number,
            raw_text=clean,
            char_count=len(clean),
            word_count=len(clean.split()),
        )


class ParsedDocument(BaseModel):
    """Unified parsed representation of any Runemark document."""

    doc_id: str
    file_name: str
    file_path: str
    format: DocumentFormat
    manifest_meta: Optional[ManifestEntry] = None
    paragraphs: List[DocumentParagraph] = Field(default_factory=list)
    full_text: str = Field(default="")
    total_paragraphs: int = Field(default=0)
    total_pages: Optional[int] = Field(default=None)

    def get_paragraph(self, index: int) -> Optional[DocumentParagraph]:
        """Fetch paragraph by 1-indexed index."""
        for p in self.paragraphs:
            if p.paragraph_index == index:
                return p
        return None

    def make_citation(self, paragraph_index: int, snippet_len: int = 200) -> ParagraphRef:
        """Create a ParagraphRef citation for a specific paragraph."""
        p = self.get_paragraph(paragraph_index)
        page = p.page_number if p else None
        snippet = (p.raw_text[:snippet_len] + "...") if p and len(p.raw_text) > snippet_len else (p.raw_text if p else None)
        return ParagraphRef(
            doc_id=self.doc_id,
            file_name=self.file_name,
            page_number=page,
            paragraph_index=paragraph_index,
            text_snippet=snippet,
        )
