from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class ClaimType(str, Enum):
    SOURCED_FACT = "SOURCED_FACT"  # Directly stated in verified Runemark document
    INFERENCE = "INFERENCE"        # Derived via multi-step analytical reasoning

class ClaimStatus(str, Enum):
    PENDING = "PENDING"
    ESTABLISHED = "ESTABLISHED"
    CONTESTED = "CONTESTED"
    CONCEDED = "CONCEDED"

class AgentRole(str, Enum):
    HEIMDALL = "HEIMDALL"
    THOR = "THOR"
    LOKI = "LOKI"
    ODIN = "ODIN"

class Claim(BaseModel):
    claim_id: str = Field(..., description="Unique claim identifier, e.g. TH-R1-01")
    agent: AgentRole = Field(..., description="Submitting agent (THOR or LOKI)")
    round_num: int = Field(default=1, description="Round number in the run")
    run_num: int = Field(default=1, description="Run number (1 or 2)")
    statement: str = Field(..., description="Specific, assertive claim statement")
    claim_type: ClaimType = Field(default=ClaimType.SOURCED_FACT)
    country: str = Field(default="general", description="Impacted country")
    sector: str = Field(default="general", description="Impacted sector / commodity")
    bound_type: str = Field(default="HIGH", description="HIGH for Thor, LOW for Loki")
    numerical_estimate: Optional[str] = Field(default=None, description="Quantified bound e.g. '50-62% drop'")
    citations: List[str] = Field(default_factory=list, description="Runemark Document IDs cited")
    citation_snippets: List[str] = Field(default_factory=list, description="Exact quotes from documents")
    status: ClaimStatus = Field(default=ClaimStatus.PENDING)
    ruling_notes: Optional[str] = None

class Attack(BaseModel):
    attack_id: str
    attacker: AgentRole
    target_claim_id: str
    target_agent: AgentRole
    argument: str
    counter_citations: List[str] = Field(default_factory=list)
    counter_snippets: List[str] = Field(default_factory=list)

class Defense(BaseModel):
    defense_id: str
    defender: AgentRole
    attack_id: str
    target_claim_id: str
    action: str = Field(..., description="'DEFEND' with new evidence or 'CONCEDE'")
    reasoning: str
    new_citations: List[str] = Field(default_factory=list)

class Ruling(BaseModel):
    claim_id: str
    ruling: ClaimStatus = Field(..., description="ESTABLISHED, CONTESTED, or CONCEDED")
    claim_type: ClaimType = Field(..., description="SOURCED_FACT or INFERENCE")
    judge_rationale: str
    verified_citations: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.85, ge=0.0, le=1.0)

class SufficiencyCheck(BaseModel):
    run_num: int
    is_sufficient: bool
    coverage_score: float = Field(ge=0.0, le=1.0)
    missing_elements: List[str] = Field(default_factory=list)
    remand_directive: Optional[str] = None

class ExposureRange(BaseModel):
    country: str
    sector: str
    thor_high_exposure: str
    loki_low_exposure: str
    odin_final_assessment: str
    ruling_status: str

class ExecutiveBriefing(BaseModel):
    case_id: str
    as_of_date: str
    incident_name: str
    executive_summary: str
    established_findings: List[str] = Field(default_factory=list)
    contested_findings: List[str] = Field(default_factory=list)
    conceded_findings: List[str] = Field(default_factory=list)
    exposure_table: List[ExposureRange] = Field(default_factory=list)
    next_quarter_outlook: str
    stated_assumptions: List[str] = Field(default_factory=list)
    source_hygiene_report: Dict[str, Any] = Field(default_factory=dict)
    all_citations: List[str] = Field(default_factory=list)
    author: str = "Odin, Supreme Allfather Bench"

class CaseFile(BaseModel):
    case_id: str
    query: str
    as_of_date: str
    status: str = "INITIALIZED"
    event_verified: bool = False
    verification_details: Optional[str] = None
    active_run: int = 1
    active_round: int = 1
    claims: List[Claim] = Field(default_factory=list)
    attacks: List[Attack] = Field(default_factory=list)
    defenses: List[Defense] = Field(default_factory=list)
    rulings: List[Ruling] = Field(default_factory=list)
    sufficiency_history: List[SufficiencyCheck] = Field(default_factory=list)
    briefing: Optional[ExecutiveBriefing] = None
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_documents: List[str] = Field(default_factory=list)
