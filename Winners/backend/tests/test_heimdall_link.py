"""Heimdall -> Thor handoff: Case File mapping, shared resolved evidence, exclusions as attack grounds."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agents.thor.agent import ThorAgent
from backend.agents.thor.memory import ThorPersistentMemory
from backend.integrations import heimdall as link
from backend.integrations.heimdall import (
    CaseNotFound,
    EventNotVerified,
    HeimdallClient,
    case_file_from_report,
    ensure_trial_ready,
)
from backend.main import app, get_heimdall_client, get_thor_agent
from backend.schemas.thor_claim import AttackReason
from backend.services.runemark import StructuredThorLogger
from backend.tools.search import ResolvedEvidenceSearchProvider

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "heimdall_case_file.json"
needs_resolved = pytest.mark.skipif(not ResolvedEvidenceSearchProvider.available(),
                                    reason="Heimdall resolved_data not built")


@pytest.fixture
def report() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def case_file(report):
    return case_file_from_report(report)


def thor() -> ThorAgent:
    return ThorAgent(search_provider=ResolvedEvidenceSearchProvider(), memory=ThorPersistentMemory(),
                     logger=StructuredThorLogger(log_dir=None))


# Mapping
def test_case_file_mapping(case_file, report):
    assert case_file.case_id == report["case_id"] and case_file.as_of_date == "2027-01-25"
    assert case_file.investigation_question == report["target_query"]
    assert case_file.countries == ["Midgard", "Tolan"]  # the event's origin, Orvan, is the supplier
    assert set(case_file.sectors) == {"Wheat", "Maize"}
    assert [r.doc_id for r in case_file.evidence_references] == [d["doc_id"] for d in report["retrieved_documents"]]
    ref = next(r for r in case_file.evidence_references if r.doc_id == "ORV-0016")
    assert (ref.reliability, ref.source_name, ref.country) == (1, "Realm Trade Ministry", "Orvan")
    assert {(g.country, g.sector) for g in case_file.coverage_gaps} == {("Tolan", "Maize")}
    reasons = {e.doc_id: e.reason for e in case_file.excluded_evidence}
    assert reasons["ORV-0043"] == "RETRACTED" and reasons["ORV-0010"] == "RUMOUR"
    assert (case_file.event_status, case_file.event_active, case_file.run_number) == ("CONFIRMED", True, 1)


def test_unverified_event_does_not_go_to_trial(report):
    report["event_verification"]["status"] = "UNVERIFIED"
    with pytest.raises(EventNotVerified):
        ensure_trial_ready(case_file_from_report(report))


# Shared evidence
@needs_resolved
def test_resolved_provider_shares_heimdalls_evidence():
    p = ResolvedEvidenceSearchProvider()
    assert p.get_document("ORV-0043") is None and p.inadmissible("ORV-0043")["reason"] == "RETRACTED"
    assert p.get_document("ORV-0013").is_retracted is False  # a correction notice is admissible
    assert p.get_document("ORV-0007").doc_id == "ORV-0047" and p.inadmissible("ORV-0007") is None


@needs_resolved
def test_thor_argues_only_from_admissible_evidence(case_file):
    t = thor()
    t.ingest_case_file(case_file)
    claims, gaps = t.conduct_initial_analysis()
    excluded = {e.doc_id for e in case_file.excluded_evidence}
    assert 3 <= len(claims) <= 6
    assert not {c.doc_id for claim in claims for c in claim.citations} & excluded
    assert [(g.country, g.sector) for g in gaps] == [("Tolan", "Maize")]


@needs_resolved
def test_exclusion_reasons_become_attack_grounds(case_file):
    t = thor()
    t.ingest_case_file(case_file)
    attacks = {a.target_claim_id: a for a in t.generate_attacks([
        {"id": "LK-1", "claim": "Talks on track, keep the base case", "docCitation": "ORV-0049"},
        {"id": "LK-2", "claim": "The port is gone, say sources", "docCitation": "ORV-0010"},
        {"id": "LK-3", "claim": "The corridor was renewed, per ORV-0043"},
        {"id": "LK-4", "claim": "A copy of the trade note shows a small loss", "docCitation": "ORV-0007"},
    ])}
    assert attacks["LK-1"].reason == AttackReason.STALE
    assert attacks["LK-2"].reason == AttackReason.LOW_TIER
    assert attacks["LK-3"].reason == AttackReason.RETRACTED
    assert [c.doc_id for c in attacks["LK-3"].counter_evidence] == ["ORV-0013"]
    assert "LK-4" not in attacks  # a duplicate is the same admissible content


# Transport
class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body, self.text = status, body, json.dumps(body)

    def json(self):
        return self._body


def test_client_fetches_and_maps_case_file(monkeypatch, report):
    seen = []

    def fake_get(url, timeout):
        seen.append(url)
        return _Resp(200, report) if url.endswith(report["case_id"]) else _Resp(404, {})

    monkeypatch.setattr(link.requests, "get", fake_get)
    client = HeimdallClient("http://heimdall:9000/")
    assert client.fetch_case_file(report["case_id"]).countries == ["Midgard", "Tolan"]
    assert seen == [f"http://heimdall:9000/case/{report['case_id']}"]
    with pytest.raises(CaseNotFound):
        client.fetch_case_file("NOPE")


@needs_resolved
def test_analyze_endpoint_pulls_case_from_heimdall(report):
    unverified = json.loads(json.dumps(report))
    unverified["case_id"], unverified["event_verification"]["status"] = "CASE-UNVERIFIED", "UNVERIFIED"

    class StubHeimdall:
        def fetch_case_file(self, case_id):
            reports = {report["case_id"]: report, "CASE-UNVERIFIED": unverified}
            if case_id not in reports:
                raise CaseNotFound(case_id)
            return case_file_from_report(reports[case_id])

    app.dependency_overrides[get_heimdall_client] = StubHeimdall
    app.dependency_overrides[get_thor_agent] = thor
    try:
        client = TestClient(app)
        ok = client.post(f"/api/thor/analyze/{report['case_id']}")
        assert ok.status_code == 200 and ok.json()["claims_count"] >= 3
        assert ok.json()["coverage_gaps"][0]["country"] == "Tolan"
        assert client.post("/api/thor/analyze/CASE-UNVERIFIED").status_code == 409
        assert client.post("/api/thor/analyze/MISSING").status_code == 404
    finally:
        app.dependency_overrides.clear()
