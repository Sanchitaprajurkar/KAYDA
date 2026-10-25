"""Integration test for HeimdallAgent dual-document intake workflow."""

import pytest
from agent_1.agent import HeimdallAgent
from agent_1.models.case_file import CaseEvidenceReport, EventStatus


def test_heimdall_dual_document_intake():
    """Verify Heimdall executes full intake pipeline on two documents (ORV-0033 PDF & ORV-0034 TXT)."""
    agent = HeimdallAgent()

    # Use ORV-0033 (Ravik statement on rail capacity - PDF) and ORV-0034 (Orvan grain ships turn back - TXT)
    report: CaseEvidenceReport = agent.analyze_dual_documents(
        doc_id_a="ORV-0033",
        doc_id_b="ORV-0034",
        target_query="As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement?",
        case_id="TEST-CASE-ORV-33-34",
    )

    # 1. Report structure
    assert report.case_id == "TEST-CASE-ORV-33-34"
    assert report.as_of_date == "2027-01-25"
    assert len(report.analyzed_documents) == 2

    # 2. Event verification
    assert report.event_verification.status == EventStatus.VERIFIED_ACTIVE
    assert report.event_verification.is_real_event is True

    # 3. Facts extraction and citations
    assert len(report.facts) > 0
    for fact in report.facts:
        assert fact.source_ref.doc_id in ["ORV-0033", "ORV-0034"]
        assert fact.source_ref.paragraph_index >= 1

    # 4. Entities extraction
    assert len(report.entities) > 0

    # 5. Knowledge Graph Sync
    assert report.knowledge_graph_summary.total_nodes > 0
    assert report.knowledge_graph_summary.graph_status in ["SYNCHRONIZED", "MOCK_RECORDED"]

    # 6. JSON serialization
    json_output = report.to_json_report()
    assert "TEST-CASE-ORV-33-34" in json_output
    assert "Wheat" in json_output
