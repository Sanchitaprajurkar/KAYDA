import json
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.case_file import CaseFile
from backend.schemas.thor_claim import (
    AttackReason,
    ClaimClassification,
    ClaimStatus,
    CrossExamAttack,
    MemoryAction,
    MemoryCategory,
    ResponseDecision,
    SearchFilter,
)
from backend.services.runemark import (
    DOCS_DIR,
    MANIFEST_PATH,
    DocumentParser,
    ParsedDocument,
    StructuredThorLogger,
)
from backend.tools.citation_validator import CitationValidator
from backend.tools.search import FakeSearchProvider, RunemarkCorpusSearchProvider
from backend.agents.thor.agent import ThorAgent
from backend.agents.thor.memory import ThorPersistentMemory

client = TestClient(app)

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "case_file.json"

@pytest.fixture
def sample_case_file() -> CaseFile:
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return CaseFile(**data)

@pytest.fixture
def fake_corpus_docs() -> list[ParsedDocument]:
    doc_orv0009 = ParsedDocument(
        doc_id="ORV-0009",
        file_path="mock/ORV-0009.txt",
        format="TXT",
        event_id="E5",
        title="Trade note: Orvan to Midgard, wheat, July to December 2026",
        source_name="Realm Trade Ministry",
        source_type="trade_note",
        reliability=1,
        pub_date="2027-01-19",
        country="Midgard",
        sector="Wheat",
        body_text=(
            "Route: Orvan to Midgard, wheat.\n"
            "[P4] In September 2026, the value was USD 38.2M and the volume was 93,000 tonnes.\n"
            "[P5] In October 2026, the value was USD 34.5M and the volume was 84,000 tonnes.\n"
            "[P6] In November 2026, the value was USD 35.3M and the volume was 86,000 tonnes.\n"
            "[P7] In December 2026, the value was USD 34.1M and the volume was 83,000 tonnes.\n"
            "[P10] In September 2025, the value was USD 97.9M and the volume was 272,000 tonnes.\n"
            "[P11] In October 2025, the value was USD 86.8M and the volume was 241,000 tonnes.\n"
            "[P12] In November 2025, the value was USD 88.6M and the volume was 246,000 tonnes.\n"
            "[P13] In December 2025, the value was USD 85.0M and the volume was 236,000 tonnes.\n"
        ),
        paragraphs={
            "P4": "In September 2026, the value was USD 38.2M and the volume was 93,000 tonnes.",
            "P5": "In October 2026, the value was USD 34.5M and the volume was 84,000 tonnes.",
            "P6": "In November 2026, the value was USD 35.3M and the volume was 86,000 tonnes.",
            "P7": "In December 2026, the value was USD 34.1M and the volume was 83,000 tonnes.",
            "P10": "In September 2025, the value was USD 97.9M and the volume was 272,000 tonnes.",
            "P11": "In October 2025, the value was USD 86.8M and the volume was 241,000 tonnes.",
            "P12": "In November 2025, the value was USD 88.6M and the volume was 246,000 tonnes.",
            "P13": "In December 2025, the value was USD 85.0M and the volume was 236,000 tonnes.",
        },
    )

    doc_orv0027 = ParsedDocument(
        doc_id="ORV-0027",
        file_path="mock/ORV-0027.txt",
        format="TXT",
        event_id="E5",
        title="Trade note: Vanir to Midgard, wheat, July to December 2026",
        source_name="Realm Trade Ministry",
        source_type="trade_note",
        reliability=1,
        pub_date="2027-01-22",
        country="Midgard",
        sector="Wheat",
        body_text=(
            "Route: Vanir to Midgard, wheat.\n"
            "[P4] In September 2026, the value was USD 31.5M and the volume was 84,000 tonnes.\n"
            "[P5] In October 2026, the value was USD 30.9M and the volume was 77,000 tonnes.\n"
            "[P6] In November 2026, the value was USD 38.5M and the volume was 96,000 tonnes.\n"
            "[P7] In December 2026, the value was USD 36.9M and the volume was 92,000 tonnes.\n"
            "[P10] In September 2025, the value was USD 32.6M and the volume was 87,000 tonnes.\n"
            "[P11] In October 2025, the value was USD 28.9M and the volume was 77,000 tonnes.\n"
            "[P12] In November 2025, the value was USD 29.6M and the volume was 79,000 tonnes.\n"
            "[P13] In December 2025, the value was USD 28.1M and the volume was 75,000 tonnes.\n"
        ),
        paragraphs={
            "P4": "In September 2026, the value was USD 31.5M and the volume was 84,000 tonnes.",
            "P5": "In October 2026, the value was USD 30.9M and the volume was 77,000 tonnes.",
            "P6": "In November 2026, the value was USD 38.5M and the volume was 96,000 tonnes.",
            "P7": "In December 2026, the value was USD 36.9M and the volume was 92,000 tonnes.",
            "P10": "In September 2025, the value was USD 32.6M and the volume was 87,000 tonnes.",
            "P11": "In October 2025, the value was USD 28.9M and the volume was 77,000 tonnes.",
            "P12": "In November 2025, the value was USD 29.6M and the volume was 79,000 tonnes.",
            "P13": "In December 2025, the value was USD 28.1M and the volume was 75,000 tonnes.",
        },
    )

    doc_orv0030 = ParsedDocument(
        doc_id="ORV-0030",
        file_path="mock/ORV-0030.txt",
        format="TXT",
        event_id="E5",
        title="Trade note: Orvan to Midgard, maize, July to December 2026",
        source_name="Realm Trade Ministry",
        source_type="trade_note",
        reliability=1,
        pub_date="2027-01-21",
        country="Midgard",
        sector="Maize",
        body_text=(
            "Route: Orvan to Midgard, maize.\n"
            "[P4] In September 2026, the value was USD 80.2M and the volume was 211,000 tonnes.\n"
            "[P5] In October 2026, the value was USD 62.1M and the volume was 146,000 tonnes.\n"
            "[P6] In November 2026, the value was USD 31.9M and the volume was 75,000 tonnes.\n"
            "[P7] In December 2026, the value was USD 31.5M and the volume was 74,000 tonnes.\n"
            "[P10] In September 2025, the value was USD 82.5M and the volume was 217,000 tonnes.\n"
            "[P11] In October 2025, the value was USD 82.8M and the volume was 218,000 tonnes.\n"
            "[P12] In November 2025, the value was USD 84.7M and the volume was 223,000 tonnes.\n"
            "[P13] In December 2025, the value was USD 84.4M and the volume was 222,000 tonnes.\n"
        ),
        paragraphs={
            "P4": "In September 2026, the value was USD 80.2M and the volume was 211,000 tonnes.",
            "P5": "In October 2026, the value was USD 62.1M and the volume was 146,000 tonnes.",
            "P6": "In November 2026, the value was USD 31.9M and the volume was 75,000 tonnes.",
            "P7": "In December 2026, the value was USD 31.5M and the volume was 74,000 tonnes.",
            "P10": "In September 2025, the value was USD 82.5M and the volume was 217,000 tonnes.",
            "P11": "In October 2025, the value was USD 82.8M and the volume was 218,000 tonnes.",
            "P12": "In November 2025, the value was USD 84.7M and the volume was 223,000 tonnes.",
            "P13": "In December 2025, the value was USD 84.4M and the volume was 222,000 tonnes.",
        },
    )

    doc_orv0046 = ParsedDocument(
        doc_id="ORV-0046",
        file_path="mock/ORV-0046.pdf",
        format="PDF",
        event_id="E5",
        title="Trade note: Orvan to Tolan, wheat, July to December 2026",
        source_name="Harbour Review",
        source_type="trade_note",
        reliability=2,
        pub_date="2027-01-20",
        country="Tolan",
        sector="Wheat",
        body_text=(
            "Route: Orvan to Tolan, wheat.\n"
            "[P4] In September 2026, the value was USD 17.0M and the volume was 43,000 tonnes.\n"
            "[P5] In October 2026, the value was USD 15.4M and the volume was 39,000 tonnes.\n"
            "[P6] In November 2026, the value was USD 15.8M and the volume was 40,000 tonnes.\n"
            "[P7] In December 2026, the value was USD 15.0M and the volume was 38,000 tonnes.\n"
            "[P10] In September 2025, the value was USD 43.4M and the volume was 124,000 tonnes.\n"
            "[P11] In October 2025, the value was USD 38.5M and the volume was 110,000 tonnes.\n"
            "[P12] In November 2025, the value was USD 39.5M and the volume was 113,000 tonnes.\n"
            "[P13] In December 2025, the value was USD 37.8M and the volume was 108,000 tonnes.\n"
        ),
        paragraphs={
            "P4": "In September 2026, the value was USD 17.0M and the volume was 43,000 tonnes.",
            "P5": "In October 2026, the value was USD 15.4M and the volume was 39,000 tonnes.",
            "P6": "In November 2026, the value was USD 15.8M and the volume was 40,000 tonnes.",
            "P7": "In December 2026, the value was USD 15.0M and the volume was 38,000 tonnes.",
            "P10": "In September 2025, the value was USD 43.4M and the volume was 124,000 tonnes.",
            "P11": "In October 2025, the value was USD 38.5M and the volume was 110,000 tonnes.",
            "P12": "In November 2025, the value was USD 39.5M and the volume was 113,000 tonnes.",
            "P13": "In December 2025, the value was USD 37.8M and the volume was 108,000 tonnes.",
        },
    )

    doc_orv0044 = ParsedDocument(
        doc_id="ORV-0044",
        file_path="mock/ORV-0044.docx",
        format="DOCX",
        event_id="E5",
        title="Trade note: Vanir to Tolan, wheat, July to December 2026",
        source_name="Cargo Weekly",
        source_type="trade_note",
        reliability=2,
        pub_date="2027-01-22",
        country="Tolan",
        sector="Wheat",
        body_text=(
            "Route: Vanir to Tolan, wheat.\n"
            "[P4] In September 2026, the value was USD 21.1M and the volume was 57,000 tonnes.\n"
            "[P5] In October 2026, the value was USD 20.6M and the volume was 55,000 tonnes.\n"
            "[P6] In November 2026, the value was USD 26.2M and the volume was 65,000 tonnes.\n"
            "[P7] In December 2026, the value was USD 26.0M and the volume was 64,000 tonnes.\n"
            "[P10] In September 2025, the value was USD 21.8M and the volume was 59,000 tonnes.\n"
            "[P11] In October 2025, the value was USD 19.3M and the volume was 52,000 tonnes.\n"
            "[P12] In November 2025, the value was USD 19.7M and the volume was 53,000 tonnes.\n"
            "[P13] In December 2025, the value was USD 18.7M and the volume was 51,000 tonnes.\n"
        ),
        paragraphs={
            "P4": "In September 2026, the value was USD 21.1M and the volume was 57,000 tonnes.",
            "P5": "In October 2026, the value was USD 20.6M and the volume was 55,000 tonnes.",
            "P6": "In November 2026, the value was USD 26.2M and the volume was 65,000 tonnes.",
            "P7": "In December 2026, the value was USD 26.0M and the volume was 64,000 tonnes.",
            "P10": "In September 2025, the value was USD 21.8M and the volume was 59,000 tonnes.",
            "P11": "In October 2025, the value was USD 19.3M and the volume was 52,000 tonnes.",
            "P12": "In November 2025, the value was USD 19.7M and the volume was 53,000 tonnes.",
            "P13": "In December 2025, the value was USD 18.7M and the volume was 51,000 tonnes.",
        },
    )

    doc_orv0050 = ParsedDocument(
        doc_id="ORV-0050",
        file_path="mock/ORV-0050.txt",
        format="TXT",
        event_id="E5",
        title="Rail takes the strain on the Orvan to Ravik grain run",
        source_name="Harbour Review",
        source_type="trade_press",
        reliability=2,
        pub_date="2026-11-20",
        country="Ravik",
        sector="Wheat",
        body_text="[P5] The rail link was built for transit, not for the grain trade on this scale, and its limits are now visible in the timetable.",
        paragraphs={
            "P5": "The rail link was built for transit, not for the grain trade on this scale, and its limits are now visible in the timetable."
        },
    )

    doc_orv0038 = ParsedDocument(
        doc_id="ORV-0038",
        file_path="mock/ORV-0038.txt",
        format="TXT",
        event_id="E5",
        title="Flour prices and distribution margins after Orvan corridor lapse",
        source_name="Midgard Times",
        source_type="trade_press",
        reliability=2,
        pub_date="2026-11-02",
        country="Midgard",
        sector="Wheat",
        body_text="[P1] Wheat futures surged on anticipated Orvan suspension, commanding an 18% premium.",
        paragraphs={
            "P1": "Wheat futures surged on anticipated Orvan suspension, commanding an 18% premium."
        },
    )

    doc_defence = ParsedDocument(
        doc_id="ORV-0033",
        file_path="mock/ORV-0033.pdf",
        format="PDF",
        event_id="E5",
        title="Ravik statement on rail capacity for Orvan grain",
        source_name="Realm Trade Ministry",
        source_type="gov_notice",
        reliability=1,
        pub_date="2026-11-18",
        country="Ravik",
        sector="Wheat",
        body_text="[P1] The Ministry confirms no extra freight paths will be granted.",
        paragraphs={"P1": "The Ministry confirms no extra freight paths will be granted."},
    )

    return [
        doc_orv0009, doc_orv0027, doc_orv0030, doc_orv0046, doc_orv0044,
        doc_orv0050, doc_orv0038, doc_defence,
    ]

@pytest.fixture
def fake_search(fake_corpus_docs) -> FakeSearchProvider:
    return FakeSearchProvider(documents=fake_corpus_docs)

@pytest.fixture
def memory_temp():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        path = Path(tf.name)
    mem = ThorPersistentMemory(storage_path=path)
    yield mem
    if path.exists():
        path.unlink()

@pytest.fixture
def isolated_agent(fake_search, memory_temp) -> ThorAgent:
    manifest_data = {
        "pack": "dev_pack_E5",
        "documents": [
            {"DOC_ID": d.doc_id, "PUB_DATE": d.pub_date, "RELIABILITY": d.reliability}
            for d in fake_search.docs.values()
        ],
    }
    validator = CitationValidator(manifest=manifest_data)
    return ThorAgent(
        search_provider=fake_search,
        citation_validator=validator,
        memory=memory_temp,
        logger=StructuredThorLogger(),
        spot_price_escalation_pct=12.0,
    )

def test_memory_logging_and_decision_influence(memory_temp):
    memory_temp.write(
        key="test_key",
        category=MemoryCategory.VERIFIED_CORRIDOR_LIMITS,
        value="Ravik rail link capacity ceiling: 25%",
        source="carrier_bulletin",
        context="pre_trial_analysis",
        decision_influence="Caps Thor's substitute offset assumptions at 25%.",
    )
    val = memory_temp.read(
        key="test_key",
        context="evaluating_offset",
        decision_influence="Directly refutes Loki claim that rail absorbs 50% of trade shock.",
    )
    assert val == "Ravik rail link capacity ceiling: 25%"
    logs = memory_temp.get_logs()
    assert len(logs) >= 2
    assert any("Caps Thor's substitute offset" in l.decision_influence for l in logs)
    assert any("Directly refutes Loki claim" in l.decision_influence for l in logs)

def test_thor_agent_round1_claims_and_gap(isolated_agent, sample_case_file):
    isolated_agent.ingest_case_file(sample_case_file)
    claims, gaps = isolated_agent.conduct_initial_analysis()

    # Responsibility 4: 3-6 structured high exposure claims
    assert 3 <= len(claims) <= 6

    # Responsibility 8: Explicit evidence gap for Tolan Maize (anti-fabrication)
    assert len(gaps) == 1
    assert gaps[0].country == "Tolan"
    assert gaps[0].sector == "Maize"
    assert gaps[0].status == "EVIDENCE_GAP"

    for c in claims:
        assert c.claim_id.startswith("TH-")
        assert c.statement
        assert c.estimate.low_bound >= 0
        assert c.estimate.high_bound >= c.estimate.low_bound
        assert c.metric
        assert c.baseline
        assert c.reasoning
        assert c.classification in [ClaimClassification.FACT, ClaimClassification.INFERENCE]
        assert len(c.citations) >= 1

def test_thor_agent_cross_exam_round2(isolated_agent, sample_case_file):
    isolated_agent.ingest_case_file(sample_case_file)
    claims, _ = isolated_agent.conduct_initial_analysis()
    th01 = claims[0]

    # Loki claims to attack
    loki_claims = [
        {"id": "LK-01", "claim": "Tolan 68-day buffer absorbs disruption completely.", "docCitation": "ORV-0031"},
        {"id": "LK-02", "claim": "Diplomatic sources report corridor deal near.", "docCitation": "WLD-0024"},
    ]
    attacks = isolated_agent.generate_attacks(loki_claims)
    assert len(attacks) >= 2
    reasons = [a.reason for a in attacks]
    assert AttackReason.RETRACTED in reasons
    assert AttackReason.MATH_ERROR in reasons

    # Defend claim TH-01 with NEW evidence
    loki_attack = CrossExamAttack(
        attack_id="ATK-LK-01",
        target_claim_id=th01.claim_id,
        attacker_agent="LOKI",
        target_agent="THOR",
        reason=AttackReason.CONTRADICTS,
        argument="Alternate rail corridors mitigate all loss.",
    )
    responses = isolated_agent.respond_to_attacks([loki_attack])
    assert len(responses) == 1
    assert responses[0].decision == ResponseDecision.DEFENDED
    assert len(responses[0].defence_evidence) == 1
    assert responses[0].defence_evidence[0].doc_id == "ORV-0033"

    # Concession when attacked with proof of retracted source
    loki_retract_attack = CrossExamAttack(
        attack_id="ATK-LK-02",
        target_claim_id=th01.claim_id,
        attacker_agent="LOKI",
        target_agent="THOR",
        reason=AttackReason.RETRACTED,
        argument="Supporting bulletin retracted.",
    )
    concessions = isolated_agent.respond_to_attacks([loki_retract_attack])
    assert len(concessions) == 1
    assert concessions[0].decision == ResponseDecision.CONCEDED
    assert isolated_agent.active_claims[th01.claim_id].status == ClaimStatus.CONCEDED

def test_api_endpoints_integration(sample_case_file):
    # Root
    r_root = client.get("/")
    assert r_root.status_code == 200
    assert "Thor (The Alarm)" in r_root.json()["agents"]

    # Health
    r_health = client.get("/api/thor/health")
    assert r_health.status_code == 200
    assert r_health.json()["status"] == "healthy"

    # Analyze
    r_analyze = client.post("/api/thor/analyze", json=sample_case_file.model_dump())
    assert r_analyze.status_code == 200
    data = r_analyze.json()
    assert data["case_id"] == "CASE-E5-001"
    assert data["claims_count"] >= 3
    assert data["coverage_gaps_count"] == 1

    # Cross-exam attack
    r_attack = client.post("/api/thor/cross-examine/attack", json={"loki_claims": [{"id": "LK-01", "claim": "68-day buffer stock cushions market."}]})
    assert r_attack.status_code == 200
    assert r_attack.json()["attacks_count"] >= 1

    # Memory logs
    r_mem = client.get("/api/thor/memory/logs")
    assert r_mem.status_code == 200
    assert len(r_mem.json()) > 0

def test_edge_case_memory_contamination_and_enabled_toggle():
    mem = ThorPersistentMemory(enabled=True)
    # Case 1: Event E5
    mem.set_active_case("CASE-E5-001", "E5")
    mem.write(
        key="e5_specific_finding",
        category=MemoryCategory.DISRUPTION_BASELINES,
        value={"loss": 216.2},
        source="test",
        context="e5_analysis",
        decision_influence="E5 baseline",
    )
    assert mem.read("e5_specific_finding", "test", "lookup") == {"loss": 216.2}

    # Case 2: Switch to Event E6 (Anti-contamination check)
    mem.set_active_case("CASE-E6-001", "E6")
    # Verify E5-specific fact is wiped from active memory to prevent cross-case contamination
    assert mem.read("e5_specific_finding", "test", "lookup") is None
    # Verify permanent seed intelligence is retained
    assert mem.read("known_retractions", "test", "seed_lookup") is not None

    # Memory disabled toggle test
    mem_disabled = ThorPersistentMemory(enabled=False)
    mem_disabled.write(
        key="temp_key",
        category=MemoryCategory.OPPONENT_PROFILE,
        value="data",
        source="test",
        context="disabled_test",
        decision_influence="check disabled",
    )
    assert mem_disabled.read("temp_key", "test", "check") is None
    logs = mem_disabled.get_logs()
    assert any("Memory disabled" in l.decision_influence for l in logs)

def test_edge_case_api_failures_and_concurrency(sample_case_file):
    # 1. Malformed JSON -> 422 Unprocessable Entity
    r_malformed = client.post(
        "/api/thor/analyze",
        content="not-a-valid-json-payload",
        headers={"Content-Type": "application/json"},
    )
    assert r_malformed.status_code == 422

    # 2. Empty / Invalid Case File -> 422 or 400 Controlled Error
    empty_payload = {
        "case_id": "",
        "investigation_question": "",
        "event_id": "",
        "as_of_date": "2027-01-25",
        "countries": [],
        "sectors": [],
        "evidence_references": [],
        "coverage_gaps": [],
    }
    r_empty = client.post("/api/thor/analyze", json=empty_payload)
    assert r_empty.status_code in [400, 422]

    # 3. Concurrent API requests simulation
    from concurrent.futures import ThreadPoolExecutor
    def send_request():
        return client.post("/api/thor/cross-examine/attack", json={"loki_claims": [{"id": "LK-CONC", "claim": "Buffer cushions shock"}]})

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(send_request) for _ in range(8)]
        results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    assert all(r.json()["attacks_count"] >= 1 for r in results)

def test_edge_case_loki_tainted_evidence_attacked(isolated_agent):
    # Loki claim relying on tainted evidence ORV-0015
    loki_claims = [
        {
            "id": "LK-TAINTED-01",
            "claim": "Corridor is renewed as reported in Asgard press.",
            "docCitation": "ORV-0015",
            "citations": [{"doc_id": "ORV-0015"}],
        }
    ]
    attacks = isolated_agent.generate_attacks(loki_claims)
    assert len(attacks) == 1
    assert attacks[0].reason == AttackReason.RETRACTED
    assert "ORV-0015" in attacks[0].argument
    assert "TAINTED_EVIDENCE" in attacks[0].argument or "RETRACTED" in attacks[0].argument

def test_edge_case_search_query_limit_enforced():
    search = RunemarkCorpusSearchProvider()
    search.max_queries = 5  # Set low limit for testing
    filters = SearchFilter(as_of_date="2027-01-25")

    # Issue 5 distinct queries
    for i in range(5):
        search.search(f"query distinct token {i}", filters=filters)

    # 6th query must raise ValueError
    with pytest.raises(ValueError, match="Search query limit exceeded"):
        search.search("sixth query over the limit", filters=filters)

