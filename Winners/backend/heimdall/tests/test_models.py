"""Unit tests for Pydantic models and schemas."""

from heimdall.models.document import ParagraphRef, DocumentParagraph, ParsedDocument, DocumentFormat
from heimdall.models.evidence import (
    FactCategory,
    ExtractedFact,
    ConflictType,
    ContradictionItem,
    MissingInformation,
)
from heimdall.models.case_file import (
    EventStatus,
    EventVerification,
    CaseEvidenceReport,
    TradeExposureSummary,
)


def test_paragraph_ref_citation_formatting():
    """Verify paragraph references format citation labels correctly."""
    ref_pdf = ParagraphRef(
        doc_id="ORV-0004",
        file_name="ORV-0004.pdf",
        page_number=2,
        paragraph_index=3,
        text_snippet="Corridor operations were suspended on January 18.",
    )
    assert ref_pdf.to_citation_str() == "[ORV-0004 p.2 ¶3]"

    ref_txt = ParagraphRef(
        doc_id="ATL-0002",
        file_name="ATL-0002.txt",
        paragraph_index=5,
    )
    assert ref_txt.to_citation_str() == "[ATL-0002 ¶5]"


def test_extracted_fact_creation():
    """Verify extracted fact validates and retains source reference."""
    ref = ParagraphRef(
        doc_id="ORV-0010",
        file_name="ORV-0010.pdf",
        page_number=1,
        paragraph_index=2,
    )
    fact = ExtractedFact(
        category=FactCategory.TRADE_VOLUME,
        subject="Midgard Wheat Imports",
        statement="Midgard imported 1.2M MT of wheat via the Orvan Corridor in 2026.",
        date_mentioned="2026",
        numeric_value=1.2,
        unit="M MT",
        source_ref=ref,
        reliability_tier=1,
    )
    assert fact.fact_id is not None
    assert fact.source_ref.doc_id == "ORV-0010"
    assert fact.numeric_value == 1.2


def test_contradiction_item_creation():
    """Verify contradiction item records conflicting facts."""
    ref_a = ParagraphRef(doc_id="DOC-A", file_name="DOC-A.txt", paragraph_index=1)
    ref_b = ParagraphRef(doc_id="DOC-B", file_name="DOC-B.txt", paragraph_index=1)

    fact_a = ExtractedFact(
        category=FactCategory.ROUTE_STATUS,
        subject="Orvan Corridor",
        statement="Corridor remains open with minor delays.",
        source_ref=ref_a,
        reliability_tier=3,
    )
    fact_b = ExtractedFact(
        category=FactCategory.ROUTE_STATUS,
        subject="Orvan Corridor",
        statement="Corridor terminated all transit immediately.",
        source_ref=ref_b,
        reliability_tier=1,
    )

    contra = ContradictionItem(
        conflict_type=ConflictType.DIRECT_CONTRADICTION,
        description="Conflicting reports on corridor status",
        fact_a=fact_a,
        fact_b=fact_b,
        resolution_rationale="Official regulatory filing (Tier 1) supersedes industry blog (Tier 3).",
        favored_fact_id=fact_b.fact_id,
    )

    assert contra.conflict_type == ConflictType.DIRECT_CONTRADICTION
    assert contra.favored_fact_id == fact_b.fact_id


def test_case_evidence_report_serialization():
    """Verify CaseEvidenceReport serializes cleanly to JSON."""
    verification = EventVerification(
        event_id="E5",
        event_name="Orvan grain corridor collapse",
        status=EventStatus.CONFIRMED,
        as_of_date="2027-01-25",
        confidence_score=0.98,
        summary="Official customs bulletins and port notices confirm the corridor expired.",
        is_real_event=True,
        is_active_at_as_of=True,
    )

    report = CaseEvidenceReport(
        case_id="CASE-E5-TEST",
        target_query="How exposed are Midgard and Tolan to the end of the Orvan corridor agreement?",
        event_verification=verification,
        trade_exposures=[
            TradeExposureSummary(
                commodity="Wheat",
                affected_parties=["Midgard", "Tolan"],
                low_range_tonnes=400000.0,
                high_range_tonnes=750000.0,
            )
        ],
    )

    json_str = report.to_json_report()
    assert "CASE-E5-TEST" in json_str
    assert "CONFIRMED" in json_str
    assert "Wheat" in json_str
