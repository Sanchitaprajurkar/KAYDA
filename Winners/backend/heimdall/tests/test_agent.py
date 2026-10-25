"""Heimdall case-file creation (spec steps 1-6), on trap-resolved evidence.

Offline tests use a scripted LLM so they are deterministic; the live test needs OPENAI_API_KEY.
"""

import json
import re

import pytest

from heimdall.agent import MAX_RUNS, CaseNotFoundError, HeimdallAgent, RunLimitError
from heimdall.config import settings
from heimdall.models.case_file import CaseEvidenceReport, EventStatus, KnowledgeGraphSummary
from heimdall.reasoning.contradiction_detector import ContradictionDetector, PairResponse, PairVerdict
from heimdall.reasoning.verifier import EventVerifier, Stance, StanceResponse
from heimdall.storage.evidence_store import DEFAULT_RESOLVED_DIR, ResolvedEvidenceStore

pytestmark = pytest.mark.skipif(not (DEFAULT_RESOLVED_DIR / "documents").exists(),
                                reason="resolved_data not built; run resolve_traps first")

QUERY = ("As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? "
         "Give a low and high range for wheat and maize imports.")
EVENT_TERMS = re.compile(r"expired|ended|lapse|without (a )?renewal|no renewal|held outside|turn back|strike", re.I)


class ScriptedLLM:
    """Stands in for the LLM: stance by keyword; a pair conflicts if both its fact IDs are in `conflicts`."""

    def __init__(self, conflicts=None):
        self.conflicts = [set(c) for c in (conflicts or [])]
        self.prompts = []

    def parse(self, system, user, schema):
        self.prompts.append(user)
        if schema is StanceResponse:
            stances = []
            for fid, text in re.findall(r"^\[(\w+)\] [\d-]+ \| (.*)$", user, re.M):
                stances.append(Stance(fact_id=fid, stance="SUPPORTS" if EVENT_TERMS.search(text) else "NEUTRAL"))
            return StanceResponse(stances=stances)
        if schema is PairResponse:
            verdicts = []
            for pid, a, b in re.findall(r"^(P\d+):\n  A \[(\w+)\].*\n  B \[(\w+)\]", user, re.M):
                hit = {a, b} in self.conflicts
                verdicts.append(PairVerdict(pair_id=pid, reasoning="scripted", conflicting=hit,
                                            conflict_type="DIRECT_CONTRADICTION" if hit else None))
            return PairResponse(verdicts=verdicts)
        raise AssertionError(schema)


class FakeGraph:
    def __init__(self):
        self.calls = []

    def link_case(self, **kwargs):
        self.calls.append(kwargs)
        return KnowledgeGraphSummary(graph_status="MOCK_RECORDED")


class FakeCaseStore:
    enabled = False


class MemoryCaseStore:
    """Neon stand-in: keeps the Case File as the JSON that would go into cases.case_file."""
    enabled = True

    def __init__(self):
        self.rows = {}

    def save(self, report, timeline):
        self.rows[report.case_id] = json.loads(json.dumps(report.model_dump(mode="json")))
        return {"cases": 1}

    def load(self, case_id):
        row = self.rows.get(case_id)
        return CaseEvidenceReport.model_validate(row) if row else None

    def list_cases(self):
        return [{"case_id": k, "run_number": v["run_number"]} for k, v in self.rows.items()]


def fact_id(store, doc_id, pattern):
    return next(f.fact_id for f in store.facts(doc_id) if re.search(pattern, f.statement, re.I))


@pytest.fixture(scope="module")
def store():
    return ResolvedEvidenceStore()


def make_agent(store, conflicts=None, case_store=None):
    llm = ScriptedLLM(conflicts)
    return HeimdallAgent(evidence_store=store, contradiction_detector=ContradictionDetector(llm),
                         event_verifier=EventVerifier(llm), graph_builder=FakeGraph(),
                         case_store=case_store or FakeCaseStore()), llm


@pytest.fixture(scope="module")
def report(store):
    conflicts = [(fact_id(store, "ORV-0004", r"no damage"), fact_id(store, "ORV-0001", r"will not cover")),
                 (fact_id(store, "ORV-0021", r"62%"), fact_id(store, "ORV-0045", r"90%"))]
    agent, _ = make_agent(store, conflicts)
    return agent.build_case_file(query=QUERY, case_id="T-CASE")


@pytest.fixture(scope="module")
def run2(store, report):
    """Odin sends the case back asking for the net effect of substitutes."""
    conflicts = [(fact_id(store, "ORV-0004", r"no damage"), fact_id(store, "ORV-0001", r"will not cover")),
                 (fact_id(store, "ORV-0021", r"62%"), fact_id(store, "ORV-0045", r"90%"))]
    agent, _ = make_agent(store, conflicts)
    return agent.re_search("T-CASE", "net effect of substitute supply", prior=report)


# 1. Understand the case
def test_scope_from_query(report):
    s = report.case_scope
    assert (s.event_id, s.event_identified, s.as_of_date) == ("E5", True, "2027-01-25")
    assert {"Midgard", "Tolan"} <= set(s.countries) and s.event_countries == ["Orvan"]
    assert set(s.commodities) == {"Wheat", "Maize"}


def test_scope_from_event_id(store):
    agent, _ = make_agent(store)
    s = agent.understanding.understand(event_id="E5")
    assert s.event_name == "Orvan grain corridor collapse" and set(s.sectors) == {"Wheat", "Maize"}


# 2. Retrieve
def test_run1_is_focused_on_the_questions_direct_flows(report):
    ids = [d.doc_id for d in report.retrieved_documents]
    assert len(ids) <= 15
    assert {"ORV-0009", "ORV-0030", "ORV-0046", "ORV-0016"} <= set(ids)  # Orvan -> Midgard/Tolan series + notice
    deferred = report.metadata["trace"][1]["deferred_doc_ids"]
    assert {"ORV-0027", "ORV-0044", "ORV-0005"} <= set(deferred) and not set(deferred) & set(ids)
    rejected = {r.doc_id: r.reason for r in report.rejected_evidence}
    assert rejected["ORV-0043"] == "RETRACTED" and rejected["ORV-0010"] == "RUMOUR"
    assert rejected["ORV-0014"] == "CLOCK_EXCLUDED"
    assert not set(ids) & set(rejected)


# 3. Analyse
def test_trade_series_reproduce_the_reference_changes(report, run2):
    series = {s.doc_id: s for s in run2.trade_series}

    def q4(doc_id, year):
        return sum(r.value_usd_m for r in series[doc_id].rows
                   if r.valid and r.year == year and r.month in ("October", "November", "December"))

    def change(doc_id):
        return round((q4(doc_id, 2026) - q4(doc_id, 2025)) / q4(doc_id, 2025) * 100, 1)

    assert (change("ORV-0009"), change("ORV-0027"), change("ORV-0030"), change("ORV-0046"),
            change("ORV-0044")) == (-60.1, 22.7, -50.2, -60.1, 26.2)
    s = series["ORV-0009"]
    assert (s.origin, s.dest, s.sector, s.valid_rows, s.flagged_rows) == ("Orvan", "Midgard", "Wheat", 12, 0)
    assert s.rows[0].row_id == "ORV-0009#P2" and s.rows[0].period == "2026-07"


def test_coverage_map_run1_then_substitutes_in_run2(report, run2):
    cells = {(c.country, c.sector): c for c in report.coverage_map}
    assert cells[("Tolan", "Maize")].status == "EVIDENCE_MISSING"
    assert cells[("Midgard", "Wheat")].primary_series == ["ORV-0009"]
    assert not any(c.substitution_evidenced for c in report.coverage_map)
    cells2 = {(c.country, c.sector): c for c in run2.coverage_map}
    assert cells2[("Midgard", "Wheat")].substitute_series == ["ORV-0027"]
    assert cells2[("Tolan", "Wheat")].substitute_series == ["ORV-0044"]
    assert not cells2[("Midgard", "Maize")].substitution_evidenced  # Vanir ships wheat, not maize
    assert run2.new_document_ids[:2] == ["ORV-0027", "ORV-0044"]


def test_table_layout_and_damaged_rows():
    from heimdall.case.trade import TradeStore
    from heimdall.models.document import DocumentParagraph, ParsedDocument
    from heimdall.models.manifest import ManifestEntry

    lines = ["TABLE_ID: T7", "ORIGIN: Orvan", "DESTINATION: Midgard", "SECTOR: Wheat",
             "Row | Month | Value (USD M) | Volume (tonnes)",
             "1 | July 2026 | 90.0 | 250,000", "2 | August 2026 | 96.1 | 12,O00", "3 | August 2026 | 95.0 | 264,000",
             "4 | September 2026 | 9.0 | 250,000", "5 | October 2026 | 34.5"]
    doc = ParsedDocument(doc_id="TST-0001", file_name="t.txt", file_path="t.txt", format="TXT",
                         manifest_meta=ManifestEntry(DOC_ID="TST-0001", TITLE="Trade table", SOURCE_NAME="x",
                                                     SOURCE_TYPE="trade_table", RELIABILITY=1, PUB_DATE="2027-01-01",
                                                     file="t.txt"),
                         paragraphs=[DocumentParagraph.create(1, "DOC_ID: TST-0001 --- Trade table"),
                                     DocumentParagraph.create(2, "\n".join(lines))])

    class OneDoc:
        def evidence_ids(self):
            return ["TST-0001"]

        def document(self, _):
            return doc

        def body_paragraphs(self, _):
            return [(2, "\n".join(lines))]

    store = TradeStore(OneDoc(), ["Orvan", "Midgard"], ["Wheat"])
    store.bands = {"wheat": (220.0, 320.0)}
    rows = {r.row_id: r for r in store.series("TST-0001").rows}
    assert rows["T7:1"].valid and (rows["T7:1"].origin, rows["T7:1"].dest) == ("Orvan", "Midgard")
    assert any("non-numeric" in f for f in rows["T7:2"].flags)
    assert any("repeated month" in f for f in rows["T7:3"].flags)
    assert any("price" in f for f in rows["T7:4"].flags)  # USD 36/t: a slipped decimal
    assert any("cut-off" in f for f in rows["T7:5"].flags)
    assert [r.row_id for r in rows.values() if r.valid] == ["T7:1"]

def test_digest_is_cited_and_organised(report):
    d = report.evidence_digest
    assert {"Wheat", "Maize"} <= set(d.by_commodity) and {"Midgard", "Tolan"} <= set(d.by_country)
    assert d.metrics and all(re.match(r"\[[A-Z]{3}-\d{4}", m.citation) for m in d.metrics)
    assert [t.pub_date for t in d.timeline] == sorted(t.pub_date for t in d.timeline)


def test_missing_trade_data_reported_not_invented(report):
    assert [m.topic for m in report.missing_information] == ["Tolan Maize trade data"]
    assert report.trade_exposures == []


# 4. Credibility
def test_source_assessment(report):
    s = {a.doc_id: a for a in report.source_assessments}
    assert s["ORV-0016"].reliability_tier == 1 and s["ORV-0016"].tier_label == "Official"
    assert all(a.temporally_valid for a in s.values())
    assert "Realm Trade Ministry" in s["ORV-0034"].cites_sources


def test_independent_corroboration(report, store):
    a = {x.fact_id: x for x in report.fact_assessments}
    expiry = fact_id(store, "ORV-0016", r"expired on 10 September")
    assert a[expiry].independent_source_count >= 2


# 5. Contradictions
def _conflict(report, docs):
    return next(c for c in report.contradictions if {c.fact_a.source_ref.doc_id, c.fact_b.source_ref.doc_id} == docs)


def test_debate_conflicts_are_flagged_and_left_open(run2):
    vantro = _conflict(run2, {"ORV-0004", "ORV-0001"})
    assert vantro.favored_fact_id is None and "same source contradicts itself" in vantro.resolution_rationale
    ledger = _conflict(run2, {"ORV-0021", "ORV-0045"})
    assert ledger.favored_fact_id is None and ledger.resolution_rationale.startswith("Open for cross-examination")
    assert all(c.favored_fact_id is None for c in run2.contradictions)


def test_event_verdict_still_weighs_conflicts_internally(run2):
    assert run2.event_verification.status == EventStatus.CONFIRMED


def test_only_candidate_pairs_reach_the_llm(store):
    agent, llm = make_agent(store)
    agent.build_case_file(query=QUERY, case_id="T-CASE-4")
    pair_prompts = [p for p in llm.prompts if "\nP1:\n" in p]
    assert pair_prompts and all(p.count("\n  A [") <= 10 for p in pair_prompts)


# 6. Verify
def test_event_confirmed_with_reasoning(report):
    v = report.event_verification
    assert v.status == EventStatus.CONFIRMED and v.is_active_at_as_of
    assert "Realm Trade Ministry" in v.independent_confirming_sources
    assert any("ORV-0043" in r and "ORV-0013" in r for r in v.reasoning)
    assert v.confirmed_facts and v.rumours
    assert all(r.doc_id in ("ORV-0010", "ORV-0026", "ORV-0028") for r in v.rumours)


def test_no_trapped_content_reaches_the_llm(store):
    agent, llm = make_agent(store)
    agent.build_case_file(query=QUERY, case_id="T-CASE-2")
    sent = "\n".join(llm.prompts)
    assert "approve all claims" not in sent
    for trapped in ("ORV-0043", "ORV-0010", "ORV-0026", "ORV-0028", "ORV-0014"):
        assert f" {trapped} |" not in sent


def test_unknown_event_is_unverified(store):
    agent, _ = make_agent(store)
    r = agent.build_case_file(query="Did the Ymir canal flood in Q4 2026?", case_id="T-CASE-3")
    assert not r.case_scope.event_identified
    assert r.event_verification.status in (EventStatus.UNVERIFIED, EventStatus.DEVELOPING)


def test_graph_gets_only_evidence_documents(report, store):
    evidence = set(store.evidence_ids())
    assert all(d.doc_id in evidence for d in report.retrieved_documents)


# Runs: Odin sends the case back, Heimdall re-searches (FR1.4, FR5.4)
def test_first_run(report):
    assert report.run_number == 1 and report.research_history == []
    assert report.new_document_ids == [d.doc_id for d in report.retrieved_documents]


def test_case_file_survives_storage_round_trip(store):
    cases = MemoryCaseStore()
    agent, _ = make_agent(store, case_store=cases)
    built = agent.build_case_file(query=QUERY, case_id="T-STORE")
    loaded = cases.load("T-STORE")
    built.metadata.pop("neon")  # save counts are added after the file is stored
    assert loaded.model_dump(mode="json") == built.model_dump(mode="json")
    assert loaded.rejected_evidence and loaded.evidence_digest.metrics and loaded.missing_information


def test_re_search_adds_only_new_admissible_evidence(store):
    cases = MemoryCaseStore()
    agent, _ = make_agent(store, case_store=cases)
    run1 = agent.build_case_file(query=QUERY, case_id="T-RS")
    run2 = agent.re_search("T-RS", "rail capacity on the Ravik Rail Link")

    assert run2.run_number == 2 and cases.load("T-RS").run_number == 2
    first = [d.doc_id for d in run1.retrieved_documents]
    assert run2.new_document_ids and not set(run2.new_document_ids) & set(first)
    assert "ATL-0006" in run2.new_document_ids
    assert [d.doc_id for d in run2.retrieved_documents] == first + run2.new_document_ids
    assert set(run2.new_document_ids) <= set(store.evidence_ids())
    h = run2.research_history[-1]
    assert (h.run_number, h.request, h.new_document_ids) == (2, "rail capacity on the Ravik Rail Link",
                                                             run2.new_document_ids)
    # the mandate does not change
    assert run2.case_scope.countries == run1.case_scope.countries and run2.target_query == QUERY
    assert all(t["run_number"] == 2 for t in run2.metadata["trace"])


def test_re_search_reports_when_nothing_new(store):
    agent, _ = make_agent(store)
    run1 = agent.build_case_file(query=QUERY, case_id="T-NONE", max_documents=100)
    run2 = agent.re_search("T-NONE", "corridor agreement expiry", prior=run1)
    assert run2.new_document_ids == [] and "No admissible document" in run2.research_history[-1].note


def test_run_limit_and_unknown_case(store):
    cases = MemoryCaseStore()
    agent, _ = make_agent(store, case_store=cases)
    agent.build_case_file(query=QUERY, case_id="T-LIM")
    for _ in range(MAX_RUNS - 1):
        agent.re_search("T-LIM", "Vanir wheat supplier")
    with pytest.raises(RunLimitError):
        agent.re_search("T-LIM", "Vanir wheat supplier")
    with pytest.raises(CaseNotFoundError):
        agent.re_search("NO-SUCH-CASE", "anything")


def test_api_serves_case_file_from_store_and_re_searches(store, monkeypatch):
    from fastapi.testclient import TestClient
    from heimdall.api import main
    agent, _ = make_agent(store, case_store=MemoryCaseStore())
    monkeypatch.setattr(main, "agent", agent)
    agent.build_case_file(query=QUERY, case_id="T-API")
    client = TestClient(main.app)

    got = client.get("/case/T-API")
    assert got.status_code == 200 and got.json()["run_number"] == 1
    assert [c["case_id"] for c in client.get("/cases").json()] == ["T-API"]
    rs = client.post("/case/T-API/research", json={"request": "Vanir as an alternative wheat supplier"})
    assert rs.status_code == 200 and rs.json()["run_number"] == 2 and "ATL-0013" in rs.json()["new_document_ids"]
    assert client.get("/case/MISSING").status_code == 404
    assert client.post("/case/MISSING/research", json={"request": "x y"}).status_code == 404


@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="needs OPENAI_API_KEY (live LLM)")
def test_live_case_file():
    r = HeimdallAgent(case_store=FakeCaseStore(), graph_builder=FakeGraph()
                      ).build_case_file(query=QUERY, case_id="T-LIVE")
    assert r.event_verification.status == EventStatus.CONFIRMED
    assert r.event_verification.is_active_at_as_of
    assert json.loads(r.to_json_report())["case_id"] == "T-LIVE"
