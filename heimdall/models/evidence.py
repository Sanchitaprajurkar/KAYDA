"""Pydantic schemas for extracted facts, entities, contradictions, and evidence."""

import uuid
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from heimdall.models.document import ParagraphRef


class FactCategory(str, Enum):
    """Classification of extracted intelligence facts."""
    TRADE_VOLUME = "TRADE_VOLUME"
    TARIFF_OR_PRICE = "TARIFF_OR_PRICE"
    ROUTE_STATUS = "ROUTE_STATUS"
    TREATY_OR_AGREEMENT = "TREATY_OR_AGREEMENT"
    GEOPOLITICAL_EVENT = "GEOPOLITICAL_EVENT"
    GRAIN_OR_INVENTORY = "GRAIN_OR_INVENTORY"
    DISRUPTION_STATUS = "DISRUPTION_STATUS"
    RETRACTION_NOTICE = "RETRACTION_NOTICE"
    OTHER = "OTHER"


class EntityType(str, Enum):
    """Entity categorization in the Runemark domain."""
    NATION = "NATION"
    PORT = "PORT"
    COMMODITY = "COMMODITY"
    AGREEMENT = "AGREEMENT"
    CORRIDOR = "CORRIDOR"
    ORGANIZATION = "ORGANIZATION"
    PERSON = "PERSON"
    INFRASTRUCTURE = "INFRASTRUCTURE"


class ExtractedEntity(BaseModel):
    """An entity discovered in case evidence."""

    name: str = Field(description="Canonical entity name e.g. 'Midgard', 'Port of Oakhaven', 'Wheat'")
    type: EntityType = Field(description="Entity type category")
    aliases: List[str] = Field(default_factory=list, description="Alternate names or abbreviations")
    description: Optional[str] = Field(default=None, description="Contextual description")
    mentions_count: int = Field(default=1)
    source_refs: List[ParagraphRef] = Field(default_factory=list, description="Where this entity appears")


class ExtractedFact(BaseModel):
    """A granular sourced assertion extracted from a document paragraph."""

    fact_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: FactCategory = Field(description="Fact classification")
    subject: str = Field(description="Subject of fact e.g. 'Orvan Corridor Agreement'")
    statement: str = Field(description="Precise factual statement extracted")
    date_mentioned: Optional[str] = Field(default=None, description="Date referenced within the statement")
    numeric_value: Optional[float] = Field(default=None, description="Parsed numerical quantity if applicable")
    unit: Optional[str] = Field(default=None, description="Measurement unit (e.g. 'MT', 'tonnes', '%', 'gold marks')")
    source_ref: ParagraphRef = Field(description="Exact document and paragraph citation")
    reliability_tier: int = Field(default=1, description="Outlet reliability tier (1-4)")
    is_as_of_valid: bool = Field(default=True, description="True if pub_date <= 2027-01-25")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class ConflictType(str, Enum):
    """Classification of contradictions and discrepancies between documents."""
    DIRECT_CONTRADICTION = "DIRECT_CONTRADICTION"   # Claim A says X, Claim B says Not X
    CORRECTION = "CORRECTION"                       # Subsequent report explicitly corrects previous report
    RETRACTION = "RETRACTION"                       # Formal retraction of previous article
    TEMPORAL_UPDATE = "TEMPORAL_UPDATE"             # Later event supersedes earlier status
    NUMERICAL_DISCREPANCY = "NUMERICAL_DISCREPANCY" # Different numbers reported for same metric
    CREDIBILITY_CONFLICT = "CREDIBILITY_CONFLICT"   # Tabloid rumor vs official bulletin


class ContradictionItem(BaseModel):
    """Discovered contradiction, correction, or inconsistency between sources."""

    contradiction_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    conflict_type: ConflictType
    description: str = Field(description="Explanation of the discrepancy")
    fact_a: Optional[ExtractedFact] = Field(default=None, description="Fact/assertion from Document A")
    fact_b: Optional[ExtractedFact] = Field(default=None, description="Fact/assertion from Document B")
    resolution_rationale: str = Field(description="Reasoning on why one fact takes precedence or why contested")
    favored_fact_id: Optional[str] = Field(default=None, description="ID of fact with stronger provenance/validity")


class MissingInformation(BaseModel):
    """Identified intelligence gaps or missing data points."""

    gap_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = Field(description="Missing topic e.g. 'Midgard strategic grain reserve capacity'")
    expected_scope: str = Field(description="What was expected or needed to resolve uncertainty")
    impact_on_assessment: str = Field(description="How this gap affects exposure ranges")
