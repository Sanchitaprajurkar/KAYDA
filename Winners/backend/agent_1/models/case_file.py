"""Pydantic schemas for the complete Case Evidence Report."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from agent_1.models.manifest import ManifestEntry
from agent_1.models.evidence import (
    ExtractedEntity,
    ExtractedFact,
    ContradictionItem,
    MissingInformation,
)


class EventStatus(str, Enum):
    """Event verification outcome."""
    CONFIRMED = "CONFIRMED"     # credible, independent confirmation and no standing credible contrary evidence
    DISPUTED = "DISPUTED"       # credible evidence on both sides that is not resolved
    UNVERIFIED = "UNVERIFIED"   # only weak sources, or no evidence about the event
    DISPROVEN = "DISPROVEN"     # credible evidence says the event did not happen (or was retracted)
    DEVELOPING = "DEVELOPING"   # credible reports or projections, not yet confirmed


class CaseScope(BaseModel):
    """What Heimdall understood the case to be about."""

    query: Optional[str] = None
    event_id: Optional[str] = None
    event_name: Optional[str] = None
    event_identified: bool = False
    countries: List[str] = Field(default_factory=list, description="Countries named in the query")
    event_countries: List[str] = Field(default_factory=list, description="Countries where the event originates")
    commodities: List[str] = Field(default_factory=list)
    sectors: List[str] = Field(default_factory=list)
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    as_of_date: str = "2027-01-25"
    search_terms: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class RetrievedDocument(BaseModel):
    doc_id: str
    title: Optional[str] = None
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    reliability_tier: int = 2
    pub_date: Optional[str] = None
    relevance_score: float = 0.0
    matched_terms: List[str] = Field(default_factory=list)
    top_paragraphs: List[int] = Field(default_factory=list)
    reason: str = ""


class RejectedEvidence(BaseModel):
    """A relevant document that trap resolution kept out of evidence."""

    doc_id: str
    title: Optional[str] = None
    source_name: Optional[str] = None
    reliability_tier: Optional[int] = None
    pub_date: Optional[str] = None
    reason: str
    related_doc_id: Optional[str] = None
    detail: Optional[str] = None
    claims: List[str] = Field(default_factory=list, description="What the document claimed (not evidence)")
    relevance_score: float = 0.0


class SourceAssessment(BaseModel):
    doc_id: str
    source_name: Optional[str] = None
    source_type: Optional[str] = None
    reliability_tier: int = 2
    tier_label: str = ""
    pub_date: Optional[str] = None
    days_before_as_of: Optional[int] = None
    temporally_valid: bool = True
    cites_sources: List[str] = Field(default_factory=list, description="Other outlets this document relies on")
    credibility_score: float = 0.0
    notes: List[str] = Field(default_factory=list)


class FactAssessment(BaseModel):
    fact_id: str
    doc_id: str
    citation: str
    credibility: float
    corroborated_by: List[str] = Field(default_factory=list, description="Similar facts from independent sources")
    independent_source_count: int = 1
    countries: List[str] = Field(default_factory=list)
    commodities: List[str] = Field(default_factory=list)
    stated_countries: List[str] = Field(default_factory=list, description="Named in the fact text itself")
    stated_commodities: List[str] = Field(default_factory=list, description="Named in the fact text itself")


class MetricRecord(BaseModel):
    fact_id: str
    citation: str
    category: str
    subject: str
    value: float
    unit: Optional[str] = None
    date_mentioned: Optional[str] = None
    pub_date: Optional[str] = None
    countries: List[str] = Field(default_factory=list)
    commodities: List[str] = Field(default_factory=list)


class TimelineEntry(BaseModel):
    pub_date: Optional[str] = None
    date_mentioned: Optional[str] = None
    fact_id: str
    citation: str
    statement: str
    assertion_status: Optional[str] = None


class EvidenceDigest(BaseModel):
    """Retrieved facts organised for downstream agents (values are fact IDs)."""

    by_category: Dict[str, List[str]] = Field(default_factory=dict)
    by_commodity: Dict[str, List[str]] = Field(default_factory=dict)
    by_country: Dict[str, List[str]] = Field(default_factory=dict)
    metrics: List[MetricRecord] = Field(default_factory=list)
    timeline: List[TimelineEntry] = Field(default_factory=list)


class EvidenceRef(BaseModel):
    fact_id: Optional[str] = None
    doc_id: str
    citation: str
    statement: str
    assertion_status: Optional[str] = None
    reliability_tier: Optional[int] = None


class EventVerification(BaseModel):
    """Verdict on whether the disruption event is real and in effect, with the reasoning behind it."""

    event_id: Optional[str] = None
    event_name: Optional[str] = None
    status: EventStatus = EventStatus.UNVERIFIED
    as_of_date: str = Field(default="2027-01-25")
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = Field(description="One-paragraph verdict")
    reasoning: List[str] = Field(default_factory=list, description="Cited reasoning steps")
    is_real_event: bool = False
    is_active_at_as_of: bool = False
    onset_date: Optional[str] = None
    independent_confirming_sources: List[str] = Field(default_factory=list)
    supporting_doc_ids: List[str] = Field(default_factory=list)
    counter_or_decoy_doc_ids: List[str] = Field(default_factory=list)
    confirmed_facts: List[EvidenceRef] = Field(default_factory=list)
    reported_claims: List[EvidenceRef] = Field(default_factory=list)
    allegations: List[EvidenceRef] = Field(default_factory=list)
    rumours: List[EvidenceRef] = Field(default_factory=list)
    projections: List[EvidenceRef] = Field(default_factory=list)
    contrary_evidence: List[EvidenceRef] = Field(default_factory=list)


class TradeExposureSummary(BaseModel):
    """Extracted commercial trade figures and exposure bounds."""

    commodity: str = Field(description="Commodity name e.g. Wheat, Maize")
    affected_parties: List[str] = Field(default_factory=list, description="e.g. ['Midgard', 'Tolan']")
    low_range_tonnes: Optional[float] = None
    high_range_tonnes: Optional[float] = None
    historical_annual_volume: Optional[float] = None
    alternative_routes_available: List[str] = Field(default_factory=list)
    mitigating_factors: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class KnowledgeGraphSummary(BaseModel):
    """Summary of Neo4j graph nodes and relationships generated for this case."""

    total_nodes: int = Field(default=0)
    total_relationships: int = Field(default=0)
    entity_nodes_count: int = Field(default=0)
    fact_nodes_count: int = Field(default=0)
    contradiction_edges_count: int = Field(default=0)
    correction_edges_count: int = Field(default=0)
    graph_status: str = Field(default="PENDING")


class ResearchRun(BaseModel):
    """One re-search requested by Odin when he sends the case back (FR1.4)."""

    run_number: int
    request: str = Field(description="What Odin asked Heimdall to look for")
    focus_terms: List[str] = Field(default_factory=list)
    new_document_ids: List[str] = Field(default_factory=list, description="Admissible documents first added in this run")
    new_excluded_ids: List[str] = Field(default_factory=list, description="Relevant documents found but set aside")
    note: str = ""
    requested_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CaseEvidenceReport(BaseModel):
    """Structured Case File deliverable generated by Heimdall Agent."""

    case_id: str = Field(description="Unique Case Identifier e.g. CASE-E5-ORVAN-2027")
    run_number: int = Field(default=1, ge=1, description="Trial run; increases each time Odin sends the case back")
    research_history: List[ResearchRun] = Field(default_factory=list)
    new_document_ids: List[str] = Field(default_factory=list,
                                        description="Documents first added in this run (all of them in run 1)")
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    as_of_date: str = Field(default="2027-01-25")
    target_query: str = Field(description="The intelligence query being addressed")
    case_scope: CaseScope = Field(default_factory=CaseScope)
    event_verification: EventVerification
    retrieved_documents: List[RetrievedDocument] = Field(default_factory=list)
    rejected_evidence: List[RejectedEvidence] = Field(default_factory=list)
    source_assessments: List[SourceAssessment] = Field(default_factory=list)
    fact_assessments: List[FactAssessment] = Field(default_factory=list)
    evidence_digest: EvidenceDigest = Field(default_factory=EvidenceDigest)
    analyzed_documents: List[ManifestEntry] = Field(default_factory=list)
    entities: List[ExtractedEntity] = Field(default_factory=list)
    facts: List[ExtractedFact] = Field(default_factory=list)
    contradictions: List[ContradictionItem] = Field(default_factory=list)
    missing_information: List[MissingInformation] = Field(default_factory=list)
    trade_exposures: List[TradeExposureSummary] = Field(default_factory=list)
    knowledge_graph_summary: KnowledgeGraphSummary = Field(default_factory=KnowledgeGraphSummary)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_json_report(self, indent: int = 2) -> str:
        """Export full report to formatted JSON."""
        return self.model_dump_json(indent=indent, by_alias=True)
