from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class EvidenceReference(BaseModel):
    """
    Evidence reference curated in the Case File by Heimdall.
    """
    doc_id: str = Field(..., description="Runemark Document ID, e.g. ORV-0017")
    title: str = Field(..., description="Document headline or title")
    source_name: str = Field(..., description="Publishing outlet or ministry")
    source_type: str = Field(..., description="atlas, trade_note, news, gov_notice, etc.")
    reliability: int = Field(..., ge=1, le=4, description="Reliability tier (1=Official, 4=Weak)")
    pub_date: str = Field(..., description="Publication date YYYY-MM-DD")
    country: Optional[str] = Field(None, description="Country context")
    sector: Optional[str] = Field(None, description="Sector context, e.g. Wheat, Maize")
    summary: Optional[str] = Field(None, description="Brief summary or excerpt of findings")
    verification_status: str = Field("VERIFIED", description="VERIFIED, FLAGGED, or UNVERIFIED")

class CoverageGap(BaseModel):
    """
    Identified data coverage gap where evidence is missing or unverified.
    """
    country: str = Field(..., description="Country with missing data")
    sector: str = Field(..., description="Sector with missing data")
    status: str = Field("EVIDENCE_GAP", description="Explicit evidence gap status")
    description: str = Field(..., description="Explanation of missing trade or market data")
    impact: str = Field("UNQUANTIFIED_GAP", description="How the gap affects analytical bounds")

class CaseFile(BaseModel):
    """
    Typed Case File representing the shared courtroom state initialized by Heimdall.
    """
    case_id: str = Field(..., description="Unique case identifier, e.g. CASE-E5-001")
    event_id: str = Field(..., description="Disruption event identifier, e.g. E5")
    event_name: str = Field(..., description="Human-readable event name")
    investigation_question: str = Field(..., description="Target query from the user")
    as_of_date: str = Field(..., description="Clock as-of date (YYYY-MM-DD). Strictly enforced.")
    countries: List[str] = Field(..., description="List of target countries under investigation")
    sectors: List[str] = Field(..., description="List of target sectors under investigation")
    evidence_references: List[EvidenceReference] = Field(
        default_factory=list,
        description="Verified evidence references assembled by Heimdall"
    )
    coverage_gaps: List[CoverageGap] = Field(
        default_factory=list,
        description="Documented coverage gaps where data is missing"
    )
    round_number: int = Field(1, ge=1, description="Current trial round number")
    status: str = Field("OPEN", description="OPEN, IN_TRIAL, DELIBERATING, CONCLUDED")
    created_at: Optional[str] = Field(default_factory=lambda: datetime.utcnow().isoformat())
