"""Heimdall's investigation planning and evidence retrieval on the real corpus, offline (rules path; no API calls)."""

import pytest

from backend.court.heimdall_bridge import ResolvedEvidenceStore
from backend.court.scripted import offline_heimdall

pytestmark = pytest.mark.skipif(not ResolvedEvidenceStore().evidence_ids(), reason="resolved_data not built")

Q1 = ("Evaluate the breaking alert claiming that Orvan Grain Port infrastructure and grain terminal silos were "
      "physically destroyed in military strikes. Conduct event verification to rule whether this disruption is "
      "verified or rejected as a decoy, citing verified port authority and logistics records.")
Q2 = ("Adjudicate the dispute between Ledger Analytics (projecting a -90% grain export wipeout and imminent famine in "
      "importing nations) versus Corvan Grain company statements and customs telemetry. Detail which claims are "
      "Established, Contested, or Conceded during cross-examination.")
EXPOSURE = ("As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? "
            "Give a low and high range for wheat and maize imports.")


@pytest.fixture(scope="module")
def cases():
    h = offline_heimdall()
    return {k: h.build_case_file(query=q, case_id=f"T-INV-{k}") for k, q in
            (("Q1", Q1), ("Q2", Q2), ("EXP", EXPOSURE))}


def test_q1_is_event_verification_not_an_exposure_case(cases):
    r = cases["Q1"]
    spec = r.investigation.spec
    assert "EVENT_VERIFICATION" in spec.investigation_types and "EXPOSURE_ANALYSIS" not in spec.investigation_types
    assert not spec.exposure_applicable and spec.cells == [] and r.coverage_map == []
    assert spec.alleged_incident and "destroyed" in spec.alleged_incident


def test_q1_separates_the_allegation_from_the_broader_event(cases):
    r = cases["Q1"]
    assert r.event_verification.status.value == "CONFIRMED"  # the corridor event itself
    assert "covers the broader event" in r.event_verification.summary
    finding = r.investigation.findings[0]
    assert finding.status != "SUPPORTED"  # nothing admissible shows strikes destroyed the port
    set_aside = [e for e in r.investigation.evidence if not e.admissible]
    assert {"ORV-0010", "ORV-0026"} <= {e.doc_id for e in set_aside}  # the alleging sources, kept as rumours
    assert all(e.assertion_type == "RUMOUR" for e in set_aside if e.doc_id in ("ORV-0010", "ORV-0026"))


def test_q1_does_not_treat_a_labour_strike_as_a_military_strike(cases):
    for e in cases["Q1"].investigation.evidence:
        if e.admissible and "strike" in e.quote.lower():
            assert e.stance != "SUPPORTS", e.citation
    assert not any(e.doc_id in ("ORV-0008", "ORV-0032") and e.stance == "SUPPORTS"
                   for e in cases["Q1"].investigation.evidence)


def test_q1_continued_operations_do_not_disprove_damage(cases):
    for e in cases["Q1"].investigation.evidence:
        if e.admissible and e.stance == "CONTRADICTS":
            assert any(w in e.quote.lower() for w in ("deny", "denied", "false", "rumour", "correct", "retract"))


def test_q2_retrieves_forecast_company_statements_and_customs(cases):
    inv = cases["Q2"].investigation
    assert {"COMPETING_CLAIMS", "FORECAST_EVALUATION"} <= set(inv.spec.investigation_types)
    docs = {e.doc_id for e in inv.evidence if e.admissible}
    assert "ORV-0045" in docs  # the analyst's forecast
    assert "ORV-0021" in docs  # the company's own statement
    assert "ORV-0022" in docs  # customs figures
    stances = {e.stance for e in inv.evidence if e.admissible}
    assert "SUPPORTS" in stances and "CONTRADICTS" in stances
    assert cases["Q2"].coverage_map == []


def test_exposure_question_keeps_its_cells_and_trade_evidence(cases):
    r = cases["EXP"]
    spec = r.investigation.spec
    assert spec.exposure_applicable and "EXPOSURE_ANALYSIS" in spec.investigation_types
    assert {(c.country, c.sector) for c in r.coverage_map} == {("Midgard", "Maize"), ("Midgard", "Wheat"),
                                                               ("Tolan", "Maize"), ("Tolan", "Wheat")}
    assert any(c.status == "COVERED" for c in r.coverage_map) and r.trade_series
    assert "covers the broader event" not in r.event_verification.summary
    assert not r.investigation.insufficient


def test_every_evidence_item_keeps_its_provenance(cases):
    store = ResolvedEvidenceStore()
    for r in cases.values():
        for e in r.investigation.evidence:
            if e.admissible:
                body = " ".join(t for _, t in store.body_paragraphs(e.doc_id)).lower()
                assert e.quote.lower()[:60] in body and e.citation.startswith(e.doc_id)


def test_no_relevant_evidence_is_reported_as_insufficient():
    r = offline_heimdall().build_case_file(query="Verify the alert claiming that the Zyx moon base was flooded by "
                                                 "glaciers.", case_id="T-INV-NONE")
    assert r.investigation.insufficient
    assert r.missing_information and r.missing_information[0].topic == "Insufficient evidence for the question"


def test_a_planner_that_drops_a_stated_prediction_is_corrected():
    from heimdall.case.investigation import Investigator, _Plan, _PlannedProp
    h = offline_heimdall()
    inv = Investigator(h.evidence_store, h.retriever, h.understanding, llm=None)
    rules = inv.plan(Q2, h.understanding.understand(query=Q2))
    assert sum("famine" in p.text.lower() for p in rules.propositions) == 1  # split from the export forecast
    dropped = _Plan(investigation_types=["COMPETING_CLAIMS"], propositions=[
        _PlannedProp(text="Ledger Analytics projects a -90% grain export wipeout", kind="CLAIM",
                     attributed_to="Ledger Analytics"),
        _PlannedProp(text="Corvan Grain disputes the projection", kind="CLAIM", attributed_to="Corvan Grain")])
    merged = inv._merge_plan(rules, dropped, [])
    famine = [p for p in merged.propositions if "famine" in p.text.lower()]
    export = [p for p in merged.propositions if "export" in p.text.lower()]
    assert famine and export and not {p.prop_id for p in famine} & {p.prop_id for p in export}
