import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ingestion.corpus import corpus
from app.court.procedure import CourtProcedure
from app.config import settings

def test_corpus_loading():
    corpus.load_corpus()
    assert len(corpus.documents) >= 70, f"Expected 70+ documents, got {len(corpus.documents)}"
    print(f"[PASS] Corpus Loaded: {len(corpus.documents)} documents indexed.")

def test_clock_enforcement():
    # Searching with an old as_of_date should not return documents published after it
    old_date = "2024-01-01"
    results = corpus.search("profile", as_of_date=old_date)
    for r in results:
        assert r.document.metadata.PUB_DATE <= old_date, f"Clock violation: {r.document.metadata.PUB_DATE} > {old_date}"
    print(f"[PASS] Clock Enforcement: All {len(results)} search results strictly precede as_of_date {old_date}.")

def test_retraction_trap():
    # Verify ORV-0013 retraction is tracked
    assert "CORRIDOR_RENEWED_RUMOR" in corpus.retraction_map
    print("[PASS] Retraction Trap: ORV-0013 correctly identified as official retraction.")

async def test_full_court_procedure():
    query = (
        "As of 25 January 2027, how exposed are Midgard and Tolan to the end of the "
        "Orvan corridor agreement? Give a low and high range for wheat and maize imports."
    )
    case_id = "TEST-CASE-E5"
    procedure = CourtProcedure(case_id=case_id, query=query, as_of_date="2027-01-25")
    
    events = []
    async for event in procedure.run_trial():
        events.append(event)
        step = event.get("step")
        if step in ["EVENT_VERIFICATION", "RUN_1_START", "CLAIMS_RECEIVED", "DEFENSES_RESOLVED", "SUFFICIENCY_ASSESSMENT", "CASE_REMANDED", "RUN_2_START", "CASE_CLOSED"]:
            print(f"  -> Step: {step}")

    assert procedure.is_completed, "Trial procedure did not reach completion"
    assert procedure.case_file is not None, "Case file is None"
    assert procedure.case_file.briefing is not None, "Executive briefing was not compiled"
    
    briefing = procedure.case_file.briefing
    assert len(briefing.exposure_table) == 4, f"Expected 4 exposure rows, got {len(briefing.exposure_table)}"
    assert len(briefing.all_citations) >= 4, f"Expected >= 4 citations, got {len(briefing.all_citations)}"
    
    print("\n[PASS] Full Court Procedure Passed!")
    print(f"  * Established Findings: {len(briefing.established_findings)}")
    print(f"  * Contested Findings: {len(briefing.contested_findings)}")
    print(f"  * Conceded Findings: {len(briefing.conceded_findings)}")
    print(f"  * Exposure Table Rows: {len(briefing.exposure_table)}")
    print(f"  * Total Citations: {len(briefing.all_citations)}")

if __name__ == "__main__":
    print("\n----------------------------------------------")
    print("  TRIAL OF THE NINE REALMS -- BACKEND TEST SUITE")
    print("----------------------------------------------\n")
    test_corpus_loading()
    test_clock_enforcement()
    test_retraction_trap()
    asyncio.run(test_full_court_procedure())
    print("\n----------------------------------------------")
    print("  ALL TESTS PASSED WITH 100% SUCCESS")
    print("----------------------------------------------\n")
