"""Stub models for backward compatibility with legacy test files."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ParsedDocument(BaseModel):
    doc_id: str
    file_path: str = ""
    format: str = "TXT"
    sector: str = ""
    body_text: str = ""
    paragraphs: List[Any] = []
    metadata: Dict[str, Any] = {}


class DocumentParser:
    """Stub — real parsing lives in heimdall.ingestion."""
    pass


class StructuredThorLogger:
    """Stub — real logging lives in court layer."""
    pass
