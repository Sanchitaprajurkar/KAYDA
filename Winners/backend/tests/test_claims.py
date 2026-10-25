import pytest
from backend.schemas.thor_claim import (
    Citation,
    ClaimClassification,
    ClaimEstimate,
    ClaimStatus,
    EvidenceGapStatus,
    HighExposureClaim,
    SearchFilter,
)
from backend.services.runemark import DocumentParser, ParsedDocument
from backend.tools.citation_validator import CitationValidator
from backend.tools.search import FakeSearchProvider

@pytest.fixture
def mock_manifest_dict():
    return {
        "pack": "dev_pack_E5",
        "event_id": "E5",
        "as_of": "2027-01-25",
        "documents": [
            {
                "DOC_ID": "ORV-0009",
                "TITLE": "Trade note: Orvan to Midgard, wheat, July to December 2026",
                "PUB_DATE": "2027-01-19",
                "RELIABILITY": 1,
                "COUNTRY": "Midgard",
                "SECTOR": "Wheat",
                "SOURCE_TYPE": "trade_note",
                "SOURCE_NAME": "Realm Trade Ministry",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "ORV-0014",
                "TITLE": "New corridor talks to open after Orvan request",
                "PUB_DATE": "2027-02-11",  # Future relative to 2027-01-25
                "RELIABILITY": 2,
                "COUNTRY": "Orvan",
                "SECTOR": "Wheat",
                "SOURCE_TYPE": "trade_press",
                "SOURCE_NAME": "Raven Wire",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "ORV-0036",
                "TITLE": "Trade note: Orvan to Midgard, wheat, January 2027",
                "PUB_DATE": "2027-02-22",  # Future relative to 2027-01-25
                "RELIABILITY": 2,
                "COUNTRY": "Midgard",
                "SECTOR": "Wheat",
                "SOURCE_TYPE": "trade_note",
                "SOURCE_NAME": "Harbour Review",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "ORV-0041",
                "TITLE": "Spring bookings point to a slow Orvan recovery",
                "PUB_DATE": "2027-04-09",  # Future relative to 2027-01-25
                "RELIABILITY": 3,
                "COUNTRY": "Orvan",
                "SECTOR": "Wheat",
                "SOURCE_TYPE": "analyst_note",
                "SOURCE_NAME": "Grain Line",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "ORV-0043",
                "TITLE": "Orvan corridor agreement renewed for another year",
                "PUB_DATE": "2026-09-09",
                "RELIABILITY": 2,
                "COUNTRY": "Orvan",
                "SECTOR": "Wheat",
                "SOURCE_TYPE": "news",
                "SOURCE_NAME": "Raven Wire",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "ORV-0015",
                "TITLE": "Asgard mediators welcome reported Orvan renewal",
                "PUB_DATE": "2026-09-09",
                "RELIABILITY": 3,
                "COUNTRY": "Asgard",
                "SECTOR": "Wheat",
                "SOURCE_TYPE": "news",
                "SOURCE_NAME": "Asgard Herald",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "ORV-0030",
                "TITLE": "Trade note: Orvan to Midgard, maize, July to December 2026",
                "PUB_DATE": "2027-01-21",
                "RELIABILITY": 1,
                "COUNTRY": "Midgard",
                "SECTOR": "Wheat",  # Metadata mismatch: labeled Wheat, actually Maize
                "SOURCE_TYPE": "trade_note",
                "SOURCE_NAME": "Realm Trade Ministry",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "WLD-0024",
                "TITLE": "Orvan talks: diplomatic source claims deal near - RETRACTED",
                "PUB_DATE": "2027-01-22",
                "RELIABILITY": 4,
                "COUNTRY": "Orvan",
                "SECTOR": "general",
                "SOURCE_TYPE": "correction",
                "SOURCE_NAME": "Raven Wire",
                "EVENT_ID": "E5",
            },
            {
                "DOC_ID": "WLD-0029",
                "TITLE": "Television chef spotted at winter fair",
                "PUB_DATE": "2024-12-19",
                "RELIABILITY": 4,
                "COUNTRY": "general",
                "SECTOR": "general",
                "SOURCE_TYPE": "lifestyle",
                "SOURCE_NAME": "World Post",
                "EVENT_ID": "NONE",
            },
        ],
    }

@pytest.fixture
def citation_validator(mock_manifest_dict):
    return CitationValidator(manifest=mock_manifest_dict)

def test_structured_claim_schema():
    cite = Citation(
        doc_id="ORV-0009",
        paragraph_or_row_id="P2",
        source_name="Realm Trade Ministry",
        reliability_tier=1,
        pub_date="2027-01-19",
        title="Trade note: Orvan to Midgard, wheat",
        excerpt="In July 2026, the value was USD 90.0M",
        verified=True,
    )
    claim = HighExposureClaim(
        claim_id="TH-01",
        country="Midgard",
        sector="Wheat",
        statement="Midgard faces severe commercial disruption in Wheat imports from Orvan.",
        estimate=ClaimEstimate(
            low_bound=197.6,
            high_bound=242.1,
            unit="USD_millions",
            formatted="$197.6M — $242.1M",
        ),
        metric="Trade Value Disruption (USD M)",
        baseline="Pre-disruption Sep-Dec 2025 baseline: USD 358.3M",
        reasoning="Quantitative trade calculation shows gross drop of $216.2M.",
        classification=ClaimClassification.INFERENCE,
        citations=[cite],
        status=ClaimStatus.ACTIVE,
    )
    assert claim.claim_id == "TH-01"
    assert claim.estimate.low_bound == 197.6
    assert claim.classification == ClaimClassification.INFERENCE
    assert len(claim.citations) == 1

def test_valid_citation(citation_validator):
    doc_orv0009 = ParsedDocument(
        doc_id="ORV-0009",
        file_path="mock/ORV-0009.txt",
        format="TXT",
        title="Trade note: Orvan to Midgard, wheat, July to December 2026",
        source_name="Realm Trade Ministry",
        reliability=1,
        pub_date="2027-01-19",
        body_text="[P2] In July 2026, the value was USD 90.0M and the volume was 250,000 tonnes.",
        paragraphs={"P2": "In July 2026, the value was USD 90.0M and the volume was 250,000 tonnes."},
    )
    cite = Citation(
        doc_id="ORV-0009",
        paragraph_or_row_id="P2",
        source_name="Realm Trade Ministry",
        reliability_tier=1,
        pub_date="2027-01-19",
        excerpt="In July 2026, the value was USD 90.0M and the volume was 250,000 tonnes.",
        verified=True,
    )
    report = citation_validator.validate_citation(cite, as_of_date="2027-01-25", doc_parsed=doc_orv0009)
    assert report.is_valid is True
    assert report.exists_in_manifest is True
    assert report.is_clock_compliant is True
    assert report.is_retracted is False
    assert report.content_matched is True

def test_clock_violation_citation(citation_validator):
    doc_future = ParsedDocument(
        doc_id="ORV-0036",
        file_path="mock/ORV-0036.txt",
        format="TXT",
        pub_date="2027-02-22",
        body_text="January 2027 trade arrivals.",
    )
    cite = Citation(
        doc_id="ORV-0036",
        paragraph_or_row_id="P1",
        reliability_tier=2,
        pub_date="2027-02-22",
        excerpt="January 2027 trade arrivals.",
        verified=True,
    )
    report = citation_validator.validate_citation(cite, as_of_date="2027-01-25", doc_parsed=doc_future)
    assert report.is_valid is False
    assert report.is_clock_compliant is False
    assert any("Clock violation" in e for e in report.errors)

def test_retracted_citation(citation_validator):
    doc_retracted = ParsedDocument(
        doc_id="WLD-0024",
        file_path="mock/WLD-0024.docx",
        format="DOCX",
        pub_date="2027-01-22",
        is_retracted=True,
        body_text="RETRACTED - A prior bulletin suggesting resumption has been withdrawn.",
    )
    cite = Citation(
        doc_id="WLD-0024",
        paragraph_or_row_id="P1",
        reliability_tier=4,
        pub_date="2027-01-22",
        excerpt="diplomatic source claims deal near",
        verified=True,
    )
    report = citation_validator.validate_citation(cite, as_of_date="2027-01-25", doc_parsed=doc_retracted)
    assert report.is_valid is False
    assert report.is_retracted is True
    assert any("inadmissible: RETRACTED" in e for e in report.errors)

def test_evidence_gap_anti_fabrication():
    gap = EvidenceGapStatus(
        country="Tolan",
        sector="Maize",
        status="EVIDENCE_GAP",
        statement="Evidence gap declared for Tolan Maize imports.",
        gap_reason="Runemark corpus contains no monthly trade notes for Tolan Maize.",
        impact_on_exposure="Analytical bounds cannot be calculated without fabricating numbers. Exposure classified as UNQUANTIFIED_GAP.",
    )
    assert gap.status == "EVIDENCE_GAP"
    assert "UNQUANTIFIED_GAP" in gap.impact_on_exposure

def test_edge_case_retraction_and_tainted_evidence(citation_validator):
    # ORV-0043 is retracted / superseded by ORV-0013
    doc_orv0043 = ParsedDocument(
        doc_id="ORV-0043",
        file_path="mock/ORV-0043.pdf",
        format="PDF",
        pub_date="2026-09-09",
        body_text="Orvan corridor agreement renewed for another year.",
    )
    cite_orv0043 = Citation(
        doc_id="ORV-0043",
        paragraph_or_row_id="P1",
        reliability_tier=2,
        pub_date="2026-09-09",
        excerpt="Orvan corridor agreement renewed for another year",
        verified=True,
    )
    rep_43 = citation_validator.validate_citation(cite_orv0043, as_of_date="2027-01-25", doc_parsed=doc_orv0043)
    assert rep_43.is_valid is False
    assert rep_43.is_retracted is True
    assert any("SUPERSEDED_BY_CORRECTION" in e or "ORV-0013" in e for e in rep_43.errors)

    # ORV-0015 is tainted (relied on retracted report)
    doc_orv0015 = ParsedDocument(
        doc_id="ORV-0015",
        file_path="mock/ORV-0015.txt",
        format="TXT",
        pub_date="2026-09-09",
        body_text="Asgard mediators welcome reported Orvan renewal.",
    )
    cite_orv0015 = Citation(
        doc_id="ORV-0015",
        paragraph_or_row_id="P1",
        reliability_tier=3,
        pub_date="2026-09-09",
        excerpt="Asgard mediators welcome reported Orvan renewal",
        verified=True,
    )
    rep_15 = citation_validator.validate_citation(cite_orv0015, as_of_date="2027-01-25", doc_parsed=doc_orv0015)
    assert rep_15.is_valid is False
    assert rep_15.is_retracted is True
    assert any("TAINTED_EVIDENCE" in e or "retracted" in e for e in rep_15.errors)

def test_edge_case_future_dated_evidence_all_three_excluded(citation_validator):
    # ORV-0014 (2027-02-11), ORV-0036 (2027-02-22), ORV-0041 (2027-04-09) against cutoff 2027-01-25
    future_docs = [
        ("ORV-0014", "2027-02-11", "New corridor talks to open"),
        ("ORV-0036", "2027-02-22", "Trade note: Orvan to Midgard, wheat, January 2027"),
        ("ORV-0041", "2027-04-09", "Spring bookings point to a slow Orvan recovery"),
    ]
    for doc_id, pdate, title in future_docs:
        cite = Citation(
            doc_id=doc_id,
            paragraph_or_row_id="P1",
            reliability_tier=2,
            pub_date=pdate,
            excerpt=title,
            verified=True,
        )
        rep = citation_validator.validate_citation(cite, as_of_date="2027-01-25")
        assert rep.is_valid is False
        assert rep.is_clock_compliant is False
        assert any("Clock violation" in e for e in rep.errors)

def test_edge_case_bad_citations_rejected(citation_validator):
    doc_valid = ParsedDocument(
        doc_id="ORV-0009",
        file_path="mock/ORV-0009.txt",
        format="TXT",
        pub_date="2027-01-19",
        paragraphs={"P4": "In September 2026, the value was USD 38.2M and the volume was 93,000 tonnes."},
        body_text="In September 2026, the value was USD 38.2M and the volume was 93,000 tonnes.",
    )
    # 1. Non-existent document ID
    cite_bad_doc = Citation(
        doc_id="ORV-9999",
        paragraph_or_row_id="P1",
        reliability_tier=1,
        pub_date="2026-10-01",
        excerpt="Some fake text",
        verified=True,
    )
    rep_bad_doc = citation_validator.validate_citation(cite_bad_doc, as_of_date="2027-01-25")
    assert rep_bad_doc.is_valid is False
    assert rep_bad_doc.exists_in_manifest is False

    # 2. Invalid Paragraph ID
    cite_bad_pid = Citation(
        doc_id="ORV-0009",
        paragraph_or_row_id="P99",  # Does not exist in ORV-0009
        reliability_tier=1,
        pub_date="2027-01-19",
        excerpt="In September 2026, the value was USD 38.2M",
        verified=True,
    )
    rep_bad_pid = citation_validator.validate_citation(cite_bad_pid, as_of_date="2027-01-25", doc_parsed=doc_valid)
    assert rep_bad_pid.is_valid is False
    assert any("not found in ORV-0009" in e for e in rep_bad_pid.errors)

    # 3. Tampered Quote / Excerpt
    cite_tampered = Citation(
        doc_id="ORV-0009",
        paragraph_or_row_id="P4",
        reliability_tier=1,
        pub_date="2027-01-19",
        excerpt="The canal was fully operational with zero disruption detected anywhere",
        verified=True,
    )
    rep_tampered = citation_validator.validate_citation(cite_tampered, as_of_date="2027-01-25", doc_parsed=doc_valid)
    assert rep_tampered.is_valid is False
    assert rep_tampered.content_matched is False

def test_edge_case_wrong_event_and_sector_mismatch_resolved():
    # 1. Sector mismatch resolution in DocumentParser
    raw_text = (
        "DOC_ID: ORV-0030\n"
        "EVENT_ID: E5\n"
        "TITLE: Trade note: Orvan to Midgard, maize, July to December 2026\n"
        "SECTOR: Wheat\n"  # Erroneous metadata header
        "---\n"
        "[P1] Route: Orvan to Midgard, maize.\n"
        "[P2] In July 2026, the value was USD 83.6M and the volume was 220,000 tonnes.\n"
    )
    parsed = DocumentParser._parse_text_content("ORV-0030", "mock.txt", "TXT", raw_text)
    assert parsed.has_sector_mismatch is True
    assert parsed.resolved_sector == "Maize"
    assert parsed.sector == "Wheat"  # Original metadata preserved for auditability
    assert "Metadata labels sector as Wheat, but title/body specifies Maize" in parsed.mismatch_note

    # 2. Exclude unrelated events in search provider
    doc_chef = ParsedDocument(
        doc_id="WLD-0029",
        file_path="mock/WLD-0029.txt",
        format="TXT",
        event_id="NONE",
        title="Television chef spotted at winter fair",
        pub_date="2024-12-19",
        body_text="A celebrity chef visited the culinary winter fair today.",
    )
    search_provider = FakeSearchProvider([parsed, doc_chef])
    # Search for E5 event
    results = search_provider.search(
        query="wheat maize fair",
        filters=SearchFilter(event_id="E5", as_of_date="2027-01-25"),
    )
    retrieved_ids = [r.doc_id for r in results]
    assert "ORV-0030" in retrieved_ids
    assert "WLD-0029" not in retrieved_ids  # Unrelated event excluded!

def test_edge_case_repeated_queries_and_tier_conflicts():
    doc_tier1 = ParsedDocument(
        doc_id="DOC-T1",
        file_path="t1.txt",
        format="TXT",
        event_id="E5",
        title="Official Canal Authority Disruption Notice",
        reliability=1,
        pub_date="2026-10-01",
        body_text="Canal capacity is restricted by 85%.",
    )
    doc_tier4 = ParsedDocument(
        doc_id="DOC-T4",
        file_path="t4.txt",
        format="TXT",
        event_id="E5",
        title="Social blog: Canal is 100% fine",
        reliability=4,
        pub_date="2026-10-01",
        body_text="Canal capacity is 100% fine says anonymous post.",
    )
    search = FakeSearchProvider([doc_tier1, doc_tier4])
    
    # Query 1
    res1 = search.search("canal capacity", filters=SearchFilter(as_of_date="2027-01-25"))
    assert len(res1) == 2
    assert search.query_history.count("canal capacity") == 1

    # Query 2 (Repeated duplicate query)
    res2 = search.search("canal capacity", filters=SearchFilter(as_of_date="2027-01-25"))
    assert len(res2) == 2
    # Verify conflicts remain visible with distinct reliability tiers
    t1_res = next(r for r in res2 if r.doc_id == "DOC-T1")
    t4_res = next(r for r in res2 if r.doc_id == "DOC-T4")
    assert t1_res.reliability == 1
    assert t4_res.reliability == 4
    assert t1_res.reliability != t4_res.reliability  # Conflict clearly visible for cross-exam attacks

