"""Courtroom records. Everything an agent files is one of these, so Odin and the briefing can trace it."""

from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

ATTACK_REASONS = ("contradicts", "retracted", "low_tier", "wrong_scope", "stale", "math_error")


class Evidence(BaseModel):
    """One citation: a document paragraph or a trade-table row."""
    doc_id: str
    ref: str = Field(description="DOC_ID#P# for a paragraph, DOC_ID#P# or TABLE_ID:row for a trade row")
    kind: str = "paragraph"  # paragraph | trade_row
    pub_date: Optional[str] = None
    pub_time: Optional[str] = None
    tier: int = 4
    source_name: Optional[str] = None
    title: Optional[str] = None
    excerpt: str = ""
    fact_id: Optional[str] = None
    assertion: Optional[str] = None
    numeric_value: Optional[float] = None
    unit: Optional[str] = None


class Calculation(BaseModel):
    """Inputs and outputs of one TradeCalculator run, so Odin can recompute it."""
    country: str
    sector: str
    origins: List[str]
    primary_series: List[str]
    substitute_series: List[str] = Field(default_factory=list)
    months: List[str]
    baseline_year: int
    disrupted_year: int
    premium_pct: float = 0.0
    window: str = ""
    gross_loss_pct: float = 0.0  # disrupted supplier's loss / its own baseline (TradeCalculator)
    net_loss_pct: float = 0.0  # TradeCalculator's net loss / disrupted supplier's baseline
    net_import_loss_pct: float = 0.0  # same net loss / baseline imports from every supplier in the calculation
    import_baseline_usd_m: float = 0.0
    high_bound_pct: float = 0.0
    baseline_usd_m: float = 0.0
    gross_loss_usd_m: float = 0.0
    net_loss_usd_m: float = 0.0
    substitute_gain_usd_m: float = 0.0
    rows_used: List[str] = Field(default_factory=list)
    rows_flagged: List[str] = Field(default_factory=list)


class Estimate(BaseModel):
    low: float
    high: float
    unit: str = "pct_import_value_loss"
    metric: str = "Fall in import value vs the same months a year earlier"
    baseline: str = ""


class Claim(BaseModel):
    claim_id: str
    side: str  # THOR | LOKI
    run: int
    country: str
    sector: str
    kind: str  # calculation | evidence
    statement: str
    estimate: Estimate
    nature: str = "SOURCED_FACT"  # SOURCED_FACT | INFERENCE, as filed by the side; Odin rules on it
    reasoning: str = ""
    citations: List[Evidence] = Field(min_length=1)
    calculations: List[Calculation] = Field(default_factory=list)
    status: str = "ACTIVE"  # ACTIVE | DEFENDED | CONCEDED


class Attack(BaseModel):
    attack_id: str
    run: int
    attacker: str
    target_claim_id: str
    reason: str
    argument: str
    counter_evidence: List[Evidence] = Field(default_factory=list)
    grounds: str = "argued"  # argued | rule (found deterministically)


class Response(BaseModel):
    response_id: str
    run: int
    side: str
    attack_id: str
    claim_id: str
    decision: str  # DEFENDED | CONCEDED
    explanation: str
    new_evidence: List[Evidence] = Field(default_factory=list)


class Ruling(BaseModel):
    claim_id: str
    side: str
    run: int
    ruling: str  # UPHELD | REJECTED | CONTESTED | CONCEDED
    nature: str  # SOURCED_FACT | INFERENCE
    classification: str  # ESTABLISHED | CONTESTED | CONCEDED | REJECTED | UNCONTESTED
    reason: str
    decided_by: str = "rules"  # rules | odin
    failed_checks: List[str] = Field(default_factory=list)


class CellRange(BaseModel):
    country: str
    sector: str
    status: str  # COVERED | EVIDENCE_MISSING
    thor: Optional[Tuple[float, float]] = None
    loki: Optional[Tuple[float, float]] = None
    odin: Optional[Tuple[float, float]] = None
    basis: str = ""


class RunRecord(BaseModel):
    run: int
    case_file_doc_ids: List[str] = Field(default_factory=list)
    new_evidence: List[str] = Field(default_factory=list)
    claims: List[Claim] = Field(default_factory=list)
    attacks: List[Attack] = Field(default_factory=list)
    responses: List[Response] = Field(default_factory=list)
    rulings: List[Ruling] = Field(default_factory=list)
    ranges: List[CellRange] = Field(default_factory=list)
    remand: List[str] = Field(default_factory=list)
    side_failures: Dict[str, str] = Field(default_factory=dict)
    llm_usage: Dict[str, Dict[str, int]] = Field(default_factory=dict)
