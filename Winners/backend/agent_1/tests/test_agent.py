"""Heimdall case-file creation (spec steps 1-6), on trap-resolved evidence.

Offline tests use a scripted LLM so they are deterministic; the live test needs OPENAI_API_KEY.
"""

import json
import re

import pytest

from agent_1.agent import HeimdallAgent
from agent_1.config import settings
from agent_1.models.case_file import EventStatus, KnowledgeGraphSummary
from agent_1.reasoning.contradiction_detector import ContradictionDetector, PairResponse, PairVerdict
from agent_1.reasoning.verifier import EventVerifier, Stance, StanceResponse
from agent_1.storage.evidence_store import DEFAULT_RESOLVED_DIR, ResolvedEvidenceStore

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


class FakeRepo:
    def save_case_report(self, report):
        return True


class FakeCaseStore:
    enabled = False


def fact_id(store, doc_id, pattern):
    return next(f.fact_id for f in store.facts(doc_id) if re.search(pattern, f.statement, re.I))


@pytest.fixture(scope="module")
def store():
    return ResolvedEvidenceStore()


def make_agent(store, conflicts=None):
    llm = ScriptedLLM(conflicts)
    return HeimdallAgent(evidence_store=store, contradiction_detector=ContradictionDetector(llm),
                         event_verifier=EventVerifier(llm), graph_builder=FakeGraph(), repository=FakeRepo(),
                         case_store=FakeCaseStore()), llm


@pytest.fixture(scope="module")
def report(store):
    conflicts = [(fact_id(store, "ORV-0004", r"no damage"), fact_id(store, "ORV-0001", r"will not cover")),
                 (fact_id(store, "ORV-0021", r"62%"), fact_id(store, "ORV-0045", r"90%"))]
    agent, _ = make_agent(store, conflicts)
    return agent.build_case_file(query=QUERY, case_id="T-CASE")


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
def test_retrieval_covers_key_evidence_and_reports_exclusions(report):
    ids = {d.doc_id for d in report.retrieved_documents}
    assert {"ORV-0016", "ORV-0013", "ORV-0030", "ORV-0009", "ORV-0046", "ORV-0001", "ORV-0004",
            "ORV-0033", "ORV-0045", "ORV-0021", "ATL-0010"} <= ids
    rejected = {r.doc_id: r.reason for r in report.rejected_evidence}
    assert rejected["ORV-0043"] == "RETRACTED" and rejected["ORV-0010"] == "RUMOUR"
    assert rejected["ORV-0014"] == "CLOCK_EXCLUDED"
    assert not ids & set(rejected)


# 3. Analyse
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
    assert "Realm Trade Ministry" in s["ORV-0017"].cites_sources


def test_independent_corroboration(report, store):
    a = {x.fact_id: x for x in report.fact_assessments}
    expiry = fact_id(store, "ORV-0016", r"expired on 10 September")
    assert a[expiry].independent_source_count >= 3


# 5. Contradictions
def _conflict(report, docs):
    return next(c for c in report.contradictions if {c.fact_a.source_ref.doc_id, c.fact_b.source_ref.doc_id} == docs)


def test_self_contradicting_source_left_for_cross_examination(report):
    c = _conflict(report, {"ORV-0004", "ORV-0001"})
    assert c.favored_fact_id is None and "Self-contradicting source (Vantro Trading)" in c.resolution_rationale


def test_outlier_analyst_figure_loses_to_company_data(report):
    c = _conflict(report, {"ORV-0021", "ORV-0045"})
    assert c.favored_fact_id == (c.fact_a if c.fact_a.source_ref.doc_id == "ORV-0021" else c.fact_b).fact_id


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


@pytest.mark.skipif(not settings.OPENAI_API_KEY, reason="needs OPENAI_API_KEY (live LLM)")
def test_live_case_file():
    r = HeimdallAgent(case_store=FakeCaseStore(), graph_builder=FakeGraph(), repository=FakeRepo()
                      ).build_case_file(query=QUERY, case_id="T-LIVE")
    assert r.event_verification.status == EventStatus.CONFIRMED
    assert r.event_verification.is_active_at_as_of
    assert json.loads(r.to_json_report())["case_id"] == "T-LIVE"
