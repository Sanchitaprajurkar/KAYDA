from enum import IntEnum
from typing import Optional, List
from pydantic import BaseModel, Field

class ReliabilityTier(IntEnum):
    TIER_1 = 1  # Official notices (Canal Authority, Government) - Most reliable
    TIER_2 = 2  # Wire service, business daily, trade press - Usually reliable
    TIER_3 = 3  # Regional paper, analyst firms - Useful, but potentially biased
    TIER_4 = 4  # Social posts, blogs, tabloids - Weak, often exaggerated

class DocumentMetadata(BaseModel):
    DOC_ID: str = Field(..., description="Permanent document identifier, e.g. ORV-0001")
    EVENT_ID: str = Field(default="NONE", description="Event identifier or NONE")
    TITLE: str = Field(..., description="Document title")
    SOURCE_NAME: str = Field(..., description="Publishing outlet or authority name")
    SOURCE_TYPE: str = Field(default="news", description="news, official, analyst, company_statement, correction, etc.")
    RELIABILITY: int = Field(default=2, ge=1, le=4, description="Reliability tier (1-4)")
    PUB_DATE: str = Field(..., description="Publication date in YYYY-MM-DD format")
    PUB_TIME: Optional[str] = Field(default="00:00", description="Publication time HH:MM")
    COUNTRY: Optional[str] = Field(default="general", description="Primary country or general")
    SECTOR: Optional[str] = Field(default="general", description="Primary commodity or sector")
    LANGUAGE: str = Field(default="en", description="Language code")
    FORMAT: str = Field(default="TXT", description="PDF, TXT, or DOCX")
    file: Optional[str] = Field(default=None, description="Filename on disk")

class ParsedDocument(BaseModel):
    metadata: DocumentMetadata
    content: str = Field(..., description="Full text content of document")
    paragraphs: List[str] = Field(default_factory=list, description="Extracted paragraph blocks")
    word_count: int = 0
    is_retracted: bool = False
    retraction_note: Optional[str] = None
    has_injection_attempt: bool = False
    injection_details: Optional[str] = None
