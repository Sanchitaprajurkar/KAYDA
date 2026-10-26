"""Courtroom records. Everything an agent files is one of these, so Odin and the briefing can trace it."""

from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

ATTACK_REASONS = ("contradicts", "retracted", "low_tier", "wrong_scope", "stale", "math_error")
# Attack taxonomy for proposition-level cross-examination. `reason` (above) stays as the coarse legacy label Odin reads.
ATTACK_TYPES = (
    "source_authenticity_failure", "source_reliability_challenge", "wrong_entity_or_geographic_scope",
    "temporal_mismatch", "contradictory_evidence", "unsupported_inference", "unsupported_causal_relationship",
    "incorrect_calculation", "invalid_baseline_or_denominator", "forecast_presented_as_observed_fact",
    "missing_corroboration", "overstated_conclusion", "misinterpretation_of_evidence",
)
ATTACK_TYPE_REASON = {  # coarse label for Odin's existing prompt and precedent keys
    "source_authenticity_failure": "retracted", "source_reliability_challenge": "low_tier",
    "wrong_entity_or_geographic_scope": "wrong_scope", "temporal_mismatch": "stale",
    "contradictory_evidence": "contradicts", "incorrect_calculation": "math_error",
    "invalid_baseline_or_denominator": "math_error", "unsupported_inference": "wrong_scope",
    "unsupported_causal_relationship": "wrong_scope", "forecast_presented_as_observed_fact": "wrong_scope",
    "missing_corroboration": "low_tier", "overstated_conclusion": "wrong_scope",
    "misinterpretation_of_evidence": "contradicts",
}
RESPONSE_ACTIONS = ("maintain", "withdraw_inference", "narrow_proposition", "accept_point", "maintain_disagreement")
EVIDENCE_TYPES = ("direct", "corroborating", "circumstantial", "contradictory", "contextual", "unsupported_inference")
EPISTEMIC_STATUSES = ("observed_fact", "reported_claim", "projection", "inference")


class Confidence(BaseModel):
    level: Literal["HIGH", "MEDIUM", "LOW"]
    explanation: str = Field(min_length=1, description="Why this level; a bare level is not accepted")


class Locator(BaseModel):
    """Where in the source. A paragraph citation carries Heimdall's paragraph label and its internal index."""
    paragraph: Optional[int] = None
    page: Optional[int] = None
    row: Optional[str] = None
    paragraph_index: Optional[int] = None

    def label(self) -> str:
        if self.row:
            return f"row {self.row}"
        return f"Page {self.page or 1} | Paragraph {self.paragraph}"


class EvidenceRef(BaseModel):
    source_id: str
    locator: Locator
    quote_or_value: str
    evidence_type: Literal["direct", "corroborating", "circumstantial", "contradictory", "contextual",
                           "unsupported_inference"] = "contextual"
    epistemic_status: Literal["observed_fact", "reported_claim", "projection", "inference"] = "reported_claim"
    reliability_note: str = ""
    establishes: str = ""        # what this source actually shows
    does_not_establish: str = ""  # what it does not


class Revision(BaseModel):
    round: int
    action: Literal["maintain", "withdraw_inference", "narrow_proposition", "accept_point", "maintain_disagreement"]
    original_proposition: str
    revised_proposition: str
    retained_evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    withdrawn_inferences: List[str] = Field(default_factory=list)
    reason: str


class ClaimArgument(BaseModel):
    """One side's argument on one Heimdall proposition. claim_id and proposition_text come from the Case File."""
    claim_id: str
    proposition_text: str
    position: Literal["supports", "challenges"]
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    reasoning: str = ""
    assumptions: List[str] = Field(default_factory=list)
    limitations_uncertainty: List[str] = Field(default_factory=list)
    confidence: Confidence
    adverse_evidence_handling: str = ""                              # Thor
    alternative_explanations: List[str] = Field(default_factory=list)  # Loki
    revision_history: List[Revision] = Field(default_factory=list)
    numerical_analysis: Optional[Dict[str, Any]] = None
    strategy: str = ""  # the investigation type(s) that shaped the argument
    # Loki only: "evidence_against" (contradicting evidence) or "not_established" (unproven; not a claim of falsity)
    challenge_basis: Optional[Literal["evidence_against", "not_established"]] = None
    pressed: bool = True  # False when nothing in the Case File carries this side's position
    evidence_requests: List[Dict[str, Any]] = Field(default_factory=list)  # targeted searches and what they found


class Evidence(BaseModel):
    """One citation: a document paragraph or a trade-table row."""
    doc_id: str
    ref: str = Field(description="DOC_ID#P# for a paragraph, DOC_ID#P# or TABLE_ID:row for a trade row")
    kind: str = "paragraph"  # paragraph | trade_row
    page_number: Optional[int] = Field(default=None, description="Page number of the citation")
    paragraph_number: Optional[int] = Field(default=None, description="Paragraph number of the citation")
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


# Data status for every input and metric. Missing data is never treated as zero.
AVAILABLE = "AVAILABLE"            # measured from validated rows or a stated figure
CONFIRMED_ZERO = "CONFIRMED_ZERO"  # measured, and the measurement is zero (e.g. substitutes did not rise)
UNKNOWN = "UNKNOWN"                # the record shows the thing exists but does not measure it
UNAVAILABLE = "UNAVAILABLE"        # nothing on the record either way

# Metric keys. Each has one numerator and one denominator; see backend/court/exposure.py.
ROUTE_VALUE_DECLINE = "route_value_decline"
ROUTE_VOLUME_DECLINE = "route_volume_decline"
NATIONAL_IMPORT_SHARE = "national_import_share"
NET_EXPOSURE = "net_exposure"
SOURCE_STATED = "source_stated"  # a percentage quoted by a document; it measures only what that document measured
METRICS = (ROUTE_VALUE_DECLINE, ROUTE_VOLUME_DECLINE, NATIONAL_IMPORT_SHARE, NET_EXPOSURE)


class Quantity(BaseModel):
    """One input to a metric, with where it came from."""
    name: str
    value: Optional[float] = None
    unit: str
    status: str
    period: str = ""
    rows: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)  # DOC_ID | Page N | Paragraph M
    note: str = ""


class Metric(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    unit: str = "%"
    status: str
    numerator: Optional[str] = None    # Quantity name
    denominator: Optional[str] = None  # Quantity name
    formula: str
    assumptions: List[str] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)


class Assessment(BaseModel):
    """Everything known about one importer-commodity cell over one observation period, from validated rows only."""
    country: str
    sector: str
    origins: List[str]
    route: str
    primary_series: List[str]
    substitute_series: List[str] = Field(default_factory=list)
    window: str
    months: List[str]
    baseline_year: int
    disrupted_year: int
    period: str
    quantities: Dict[str, Quantity] = Field(default_factory=dict)
    metrics: Dict[str, Metric] = Field(default_factory=dict)
    substitution: Quantity
    low: Optional[float] = None   # recorded-substitution scenario; None when substitution is not quantified
    high: Optional[float] = None  # no-substitution scenario
    range_metric: str = NET_EXPOSURE
    range_basis: str = ""
    sensitivity: List[Dict[str, Any]] = Field(default_factory=list)  # other periods: information, never bounds
    breakdown: List[Dict[str, Any]] = Field(default_factory=list)    # every row used
    rows_flagged: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)


class Estimate(BaseModel):
    """A figure a party puts forward. Both bounds are optional: no evidence, no number."""
    low: Optional[float] = None
    high: Optional[float] = None
    metric: str = NET_EXPOSURE
    unit: str = ""
    basis: str = ""
    # "" = every scenario the data supports (low may be None); "recorded_substitution" = the low scenario as a point
    scenario: str = ""


class Claim(BaseModel):
    claim_id: str
    side: str  # THOR | LOKI
    run: int
    country: str = ""
    sector: str = ""
    kind: str = "evidence"  # calculation | evidence
    statement: str
    estimate: Optional[Estimate] = None
    nature: str = "SOURCED_FACT"  # SOURCED_FACT | INFERENCE, as filed by the side; Odin rules on it
    reasoning: str = ""
    citations: List[Evidence] = Field(default_factory=list)
    assessment: Optional[Assessment] = None
    requests: List[str] = Field(default_factory=list)  # evidence the side found that is not yet in the Case File
    status: str = "ACTIVE"  # ACTIVE | DEFENDED | NARROWED | CONCEDED
    narrowed_from: Optional[Estimate] = None  # the estimate as first filed, when the owner narrowed it
    argument: Optional[ClaimArgument] = None


class Attack(BaseModel):
    attack_id: str
    run: int
    attacker: str
    target_claim_id: str
    reason: str
    argument: str
    counter_evidence: List[Evidence] = Field(default_factory=list)
    grounds: str = "argued"  # argued | rule (found deterministically)
    # The metric the attacker says the data does support. The owner may narrow to it instead of conceding.
    narrow_to: Optional[str] = None
    attack_type: Optional[str] = None  # one of ATTACK_TYPES
    target_proposition_id: Optional[str] = None  # Heimdall's claim ID when the target is a proposition argument
    target_evidence_or_reasoning: Optional[str] = None
    defect: Optional[str] = None
    explanation: str = ""
    counter_evidence_refs: List[EvidenceRef] = Field(default_factory=list)


class Response(BaseModel):
    response_id: str
    run: int
    side: str
    attack_id: str
    claim_id: str
    decision: str  # DEFENDED | NARROWED | CONCEDED
    explanation: str
    new_evidence: List[Evidence] = Field(default_factory=list)
    action: Optional[str] = None  # one of RESPONSE_ACTIONS; `decision` stays the legacy label Odin reads
    revision: Optional[Revision] = None
    new_evidence_refs: List[EvidenceRef] = Field(default_factory=list)


class Finding(BaseModel):
    """One conclusion inside a claim, ruled on separately: a fact can stand while the conclusion drawn from it fails."""
    metric: str
    statement: str
    value: Optional[float] = None
    established: bool
    reason: str


class Ruling(BaseModel):
    claim_id: str
    side: str
    run: int
    ruling: str  # UPHELD | REJECTED | CONTESTED | CONCEDED
    nature: str  # SOURCED_FACT | INFERENCE
    # PARTLY_ESTABLISHED: the measured fact stands, the conclusion the claim draws from it does not
    # ... | NOT_PRESSED: the side had nothing in the Case File to carry its position (not a finding)
    classification: str  # ESTABLISHED | PARTLY_ESTABLISHED | CONTESTED | CONCEDED | REJECTED | UNCONTESTED | NOT_PRESSED
    reason: str
    decided_by: str = "rules"  # rules | odin
    failed_checks: List[str] = Field(default_factory=list)
    validation: List[str] = Field(default_factory=list)  # checks the claim passed, whether or not it was attacked
    findings: List[Finding] = Field(default_factory=list)


class PropositionRuling(BaseModel):
    """Odin's own ruling on one proposition of the question, made from the evidence whatever the advocates did.
    CONCEDED and NOT_PRESSED describe advocates' positions (advocate_positions); they are never a proposition's
    classification."""
    prop_id: str
    proposition: str
    kind: str = "CLAIM"
    classification: Literal["ESTABLISHED", "CONTESTED", "REJECTED", "INSUFFICIENT"]
    supporting: List[EvidenceRef] = Field(default_factory=list)
    contradicting: List[EvidenceRef] = Field(default_factory=list)
    qualifying: List[EvidenceRef] = Field(default_factory=list)  # bears on it without establishing either side
    set_aside: List[EvidenceRef] = Field(default_factory=list)   # inadmissible sources of the claim
    limitations: List[str] = Field(default_factory=list)
    reasoning: str
    confidence: Confidence
    attribution: Optional[str] = None  # for a party's claim: whether the party is shown to have made it
    deception: str = ""                # what the record shows about deliberate fabrication (never assumed)
    advocate_positions: Dict[str, str] = Field(default_factory=dict)
    needs_investigation: bool = False
    evidence_gap: str = ""
    evidence_needed: str = ""
    reinvestigation: str = ""          # whether a further search was requested, and why or why not
    derived_from: Optional[str] = None  # the Heimdall proposition this was split or derived from
    derivation: str = ""               # "part" of a compound allegation, its operational "consequence", or "compound"
    research_request: str = ""         # the targeted request for Heimdall, when one applies
    research_requested: bool = False   # sent this run (False once it has been searched)


class ResearchOutcome(BaseModel):
    """Whether a re-search answered the gap Odin sent back. Retrieving documents is not answering the question."""
    gap: str
    resolved: bool
    new_documents: List[str] = Field(default_factory=list)
    used_documents: List[str] = Field(default_factory=list)  # new documents a claim in this run actually cited
    explanation: str


class CellRange(BaseModel):
    country: str
    sector: str
    status: str  # COVERED | EVIDENCE_MISSING
    thor: Optional[Tuple[Optional[float], Optional[float]]] = None
    loki: Optional[Tuple[Optional[float], Optional[float]]] = None
    odin: Optional[Tuple[Optional[float], Optional[float]]] = None  # (low or None, high)
    metrics: Dict[str, Optional[float]] = Field(default_factory=dict)
    metric_status: Dict[str, str] = Field(default_factory=dict)
    substitution: str = ""
    period: str = ""
    positions: Dict[str, str] = Field(default_factory=dict)  # each side's stated position on this cell
    # ESTABLISHED = no surviving calc was CONTESTED; CONTESTED = at least one was. An odin range with no low bound is
    # an upper bound only, whatever the classification: the net loss is not established.
    # None means no Odin range was produced (evidence missing or no calculation survived).
    odin_classification: Optional[str] = None
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
    research: List[ResearchOutcome] = Field(default_factory=list)  # how the re-search before this run answered the remand
    open_gaps: List[str] = Field(default_factory=list)  # gaps searched for and still unresolved; reported, not chased
    propositions: List[PropositionRuling] = Field(default_factory=list)  # Odin's ruling on every proposition
    analytical_status: str = ""  # COMPLETE | PARTIAL | INSUFFICIENT; separate from whether the workflow ran
    completeness: List[str] = Field(default_factory=list)  # requirements without a ruling (should be empty)
    side_failures: Dict[str, str] = Field(default_factory=dict)
    llm_usage: Dict[str, Dict[str, int]] = Field(default_factory=dict)
