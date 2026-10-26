"""Odin's independent proposition-level adjudication, through the full courtroom pipeline on the real corpus
(offline: scripted stand-ins for model calls). Case-specific questions appear only here, as fixtures."""

import json
import re
from pathlib import Path

import pytest

from backend.court.heimdall_bridge import ResolvedEvidenceStore
from backend.court.procedure import CourtSession
from backend.court.scripted import ScriptedLLM, offline_heimdall

pytestmark = pytest.mark.skipif(not ResolvedEvidenceStore().evidence_ids(), reason="resolved_data not built")

Q1 = ("Evaluate the breaking alert claiming that Orvan Grain Port infrastructure and grain terminal silos were "
      "physically destroyed in military strikes. Conduct event verification to rule whether this disruption is "
      "verified or rejected as a decoy, citing verified port authority and logistics records.")
Q2 = ("Adjudicate the dispute between Ledger Analytics (projecting a -90% grain export wipeout and imminent famine in "
      "importing nations) versus Corvan Grain company statements and customs telemetry. Detail which claims are "
      "Established, Contested, or Conceded during cross-examination.")
Q3 = ("As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? Give a low "
      "and high range for wheat and maize imports.")


def _run(tmp: Path, q: str, case_id: str):
    llm = ScriptedLLM()
    result = CourtSession(heimdall=offline_heimdall(llm), llm_backends={k: llm for k in ("THOR", "LOKI", "ODIN")},
                          cases_dir=tmp / "cases", memory_dir=tmp / "mem", printer=None).run(q, case_id=case_id)
    case = tmp / "cases" / case_id
    last = sorted(p for p in case.iterdir() if p.name.startswith("run_"))[-1]
    return {"result": result,
            "rulings": json.loads((last / "rulings.json").read_text(encoding="utf-8")),
            "file": json.loads((last / "case_file.json").read_text(encoding="utf-8")),
            "transcript": json.loads((last / "transcript.json").read_text(encoding="utf-8")),
            "briefing": (case / "briefing.md").read_text(encoding="utf-8"),
            "briefing_json": json.loads((case / "briefing.json").read_text(encoding="utf-8"))}


@pytest.fixture(scope="module")
def cases(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("odin")
    return {k: _run(tmp, q, f"T-ODIN-{k}") for k, q in (("Q1", Q1), ("Q2", Q2), ("Q3", Q3))}


def _props(c):
    return {p["prop_id"]: p for p in c["rulings"]["propositions"]}


# Every proposition in Heimdall's plan gets a ruling with every required field; nothing is omitted.
@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3"])
def test_every_proposition_is_ruled_with_required_fields(cases, q):
    c = cases[q]
    asked = {h["request"] for h in c["file"]["research_history"]}
    plan = {p["prop_id"] for p in c["file"]["investigation"]["spec"]["propositions"] if p["text"] not in asked}
    ruled = _props(c)
    covered = set(ruled) | {p["derived_from"] for p in ruled.values() if p["derived_from"]}
    assert plan <= covered and c["rulings"]["completeness"] == []
    # Odin's own damage re-investigation requests are never ruled as new allegations
    assert not {p["proposition"] for p in ruled.values()} & {a for a in asked if a.startswith("Physical damage")}
    for p in ruled.values():
        assert p["classification"] in ("ESTABLISHED", "CONTESTED", "REJECTED", "INSUFFICIENT")
        assert p["proposition"] and p["reasoning"] and p["confidence"]["explanation"]
        if p["needs_investigation"]:
            assert p["evidence_gap"] and p["evidence_needed"] and p["reinvestigation"]
        support = {(r["source_id"], r["locator"].get("paragraph"), r["quote_or_value"]) for r in p["supporting"]}
        against = {(r["source_id"], r["locator"].get("paragraph"), r["quote_or_value"]) for r in p["contradicting"]}
        qual = {(r["source_id"], r["locator"].get("paragraph"), r["quote_or_value"]) for r in p["qualifying"]}
        assert not support & against and not qual & (support | against)  # one role per piece of evidence


def _q1_parts(c):
    props = _props(c).values()
    parts = [p for p in props if p["derivation"] == "part"]
    ops = [p for p in props if p["derivation"] == "consequence"]
    return parts, ops


# Q1: infrastructure destruction, silo destruction and operational disruption are ruled independently, and
# operational disruption neither proves destruction nor proves the infrastructure intact.
def test_q1_compound_allegation_is_split_and_ruled_independently(cases):
    parts, ops = _q1_parts(cases["Q1"])
    assert len(parts) == 2 and len({p["derived_from"] for p in parts}) == 1
    infra = next(p for p in parts if "infrastructure" in p["proposition"])
    silos = next(p for p in parts if "silos" in p["proposition"])
    assert infra["prop_id"] != silos["prop_id"]
    for p in (infra, silos):
        assert p["classification"] == "INSUFFICIENT", p
        assert not p["supporting"] and not p["contradicting"]
        assert "not evidence that it is false" in p["reasoning"]
        assert "not shown to be a hoax or decoy" in p["deception"]
    assert infra["qualifying"], "operating records qualify the site-level allegation"
    # Records about the port as a whole are not evidence about the silos.
    assert not {r["source_id"] for r in silos["qualifying"]} & {r["source_id"] for r in infra["qualifying"]
                                                                 if "silo" not in r["quote_or_value"].lower()}
    assert len(ops) == 1 and ops[0]["classification"] == "ESTABLISHED" and ops[0]["supporting"]
    assert "does not establish the damage" in ops[0]["reasoning"]
    assert cases["Q1"]["rulings"]["analytical_status"] == "PARTIAL"
    assert cases["Q1"]["result"]["status"] == "COMPLETE"
    md = cases["Q1"]["briefing"]
    assert "analysis: **PARTIAL**" in md and "## Proposition rulings" in md and "separate part of the allegation" in md
    assert not re.search(r"\*\*Ruling: (?:HOAX|DECOY)", md)


# Q1: insufficient damage evidence triggers one targeted re-investigation through Heimdall, folded back into the
# allegation and never repeated or ruled as a new proposition.
def test_q1_damage_gap_triggers_one_targeted_reinvestigation(cases, tmp_path_factory):
    c = cases["Q1"]
    history = c["file"]["research_history"]
    assert len(history) == 1
    request = history[0]["request"]
    assert re.search(r"damage assessment", request) and re.search(r"inspection report", request)
    assert "silos" in request and "infrastructure" in request
    assert c["result"]["runs"] == 2
    parts, _ = _q1_parts(c)
    for p in parts:
        assert not p["research_requested"] and f"ran in run {history[0]['run_number']}" in p["reinvestigation"]
    assert c["rulings"]["remand"] == []
    assert c["rulings"]["research"] and not c["rulings"]["research"][0]["resolved"]
    first = json.loads((Path(c["result"]["dir"]) / "run_1" / "rulings.json").read_text(encoding="utf-8"))
    assert first["remand"] == [request]
    assert all(p["research_requested"] for p in first["propositions"] if p["derivation"] == "part")


# Q2: export reduction and famine are ruled separately; a party's own statement is not independent proof.
def test_q2_predictions_are_ruled_separately_and_claimant_statements_are_not_proof(cases):
    props = _props(cases["Q2"])
    export = [p for p in props.values() if re.search(r"export|wipeout", p["proposition"], re.I)]
    famine = [p for p in props.values() if "famine" in p["proposition"].lower()]
    assert export and famine and not {p["prop_id"] for p in export} & {p["prop_id"] for p in famine}
    for p in props.values():
        for r in p["supporting"]:
            if "claimant's own publication" in r["does_not_establish"]:
                assert p["classification"] != "ESTABLISHED" or len(
                    {x["source_id"] for x in p["supporting"] if "claimant" not in x["does_not_establish"]}) >= 1
    assert cases["Q2"]["rulings"]["analytical_status"] in ("PARTIAL", "INSUFFICIENT", "COMPLETE")


# Partial concessions stay advocate actions and keep the claim ID; the proposition still gets its own ruling.
def test_q2_concessions_are_advocate_actions(cases):
    t, r = cases["Q2"]["transcript"], cases["Q2"]["rulings"]
    narrowed = [x for x in t["responses"] if x.get("revision") and x["decision"] == "NARROWED"]
    ruled = {x["claim_id"]: x for x in r["rulings"]}
    for x in narrowed:
        assert ruled[x["claim_id"]]["classification"] in ("ESTABLISHED", "CONTESTED", "REJECTED", "INSUFFICIENT")
        assert "narrowed" in ruled[x["claim_id"]]["reason"].lower()
    print(f"Q2 partial concessions: {len(narrowed)}")


# NOT_PRESSED is never reported as CONCEDED.
@pytest.mark.parametrize("q", ["Q1", "Q2"])
def test_not_pressed_is_not_conceded(cases, q):
    claims = {c["claim_id"]: c for c in cases[q]["transcript"]["claims"]}
    for x in cases[q]["rulings"]["rulings"]:
        if claims[x["claim_id"]]["status"] == "NOT_PRESSED":
            assert x["classification"] == "NOT_PRESSED"


# Briefing counts are computed from the ruling records.
@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3"])
def test_briefing_counts_match_rulings(cases, q):
    props = cases[q]["rulings"]["propositions"]
    n = {k: sum(1 for p in props if p["classification"] == k) for k in ("ESTABLISHED", "REJECTED", "CONTESTED",
                                                                        "INSUFFICIENT")}
    line = (f"Propositions ruled: {len(props)} - {n['ESTABLISHED']} established, {n['REJECTED']} rejected, "
            f"{n['CONTESTED']} contested, {n['INSUFFICIENT']} insufficient.")
    assert line in cases[q]["briefing"]
    assert cases[q]["briefing_json"]["analytical_status"] == cases[q]["rulings"]["analytical_status"]


# If no advocate argues at all, every proposition is still ruled from the evidence.
def test_rulings_do_not_depend_on_advocates(tmp_path):
    from backend.agents.odin import Odin
    from backend.court.llm import CourtLLM
    from backend.court.memory import AgentMemory
    from backend.court.tools import RunemarkTools
    h = offline_heimdall()
    report = h.build_case_file(query=Q1, case_id="T-ODIN-ALONE")
    tools = RunemarkTools(h.evidence_store, h.trade, report.as_of_date, set(), 99)
    odin = Odin(tools, CourtLLM("ODIN", 40_000, ScriptedLLM()), AgentMemory("odin", tmp_path), lambda *a, **k: None)
    alone = odin.adjudicate(report, [], [], [])
    plan = {p.prop_id for p in report.investigation.spec.propositions}
    assert plan <= {p.prop_id for p in alone} | {p.derived_from for p in alone}
    assert all(p.classification == "INSUFFICIENT" for p in alone if p.derivation != "consequence")
    assert odin.analytical_status(report, [], [], []) == "INSUFFICIENT"  # an empty record is never sufficient


# Q3: the exposure workflow is preserved and its propositions are decided from the coverage table.
def test_q3_exposure_adjudication_preserved(cases):
    c = cases["Q3"]
    ranges = {(x["country"], x["sector"]): x for x in c["rulings"]["ranges"]}
    assert ranges[("Tolan", "Maize")]["status"] == "EVIDENCE_MISSING" and ranges[("Tolan", "Maize")]["odin"] is None
    assert any(x["odin"] for x in ranges.values())
    exposure = [p for p in c["rulings"]["propositions"] if p["kind"] == "EXPOSURE"]
    assert exposure and all("validated trade calculation" in p["reasoning"] for p in exposure)
    assert c["result"]["status"] == "COMPLETE"
    assert c["rulings"]["analytical_status"] == "PARTIAL"  # one cell has no trade data


# The splitter works from grammar alone (synthetic names; nothing case-specific).
@pytest.mark.parametrize("text,expected", [
    ("drones destroyed Kell Harbour cranes and fuel depots",
     ["drones destroyed Kell Harbour cranes", "drones destroyed fuel depots at Kell Harbour"]),
    ("Kell Harbour cranes and the fuel depot were badly damaged in shelling",
     ["Kell Harbour cranes were badly damaged in shelling", "the fuel depot at Kell Harbour was badly damaged in shelling"]),
    ("shelling damaged the import and export terminal at Kell Harbour", []),
    ("drones destroyed Kell Harbour", []),
])
def test_split_compound_allegations(text, expected):
    from backend.agents.odin.propositions import split
    assert [p.text for p in split(text)] == expected


# An allegation in the question that the plan dropped is restored as its own part (synthetic names).
def test_allegation_dropped_by_the_plan_is_ruled():
    from types import SimpleNamespace as P
    from backend.agents.odin.propositions import allegation_parts
    prop = P(prop_id="P1", kind="EVENT", text="Kell Harbour cranes were destroyed in shelling.")
    parts, n_own = allegation_parts(prop, "Kell Harbour cranes and fuel depots were destroyed in shelling.", [prop], True)
    assert n_own == 1 and [p.text for p in parts] == [
        "Kell Harbour cranes were destroyed in shelling.", "fuel depots at Kell Harbour were destroyed in shelling."]
    assert allegation_parts(prop, "Kell Harbour cranes were destroyed in shelling.", [prop], True)[0] == parts[:1]


# The winner is computed from Odin's rulings and reported in the result and the briefing.
@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3"])
def test_winner_is_reported_from_rulings(cases, q):
    c = cases[q]
    asked = {h["request"] for h in c["file"]["research_history"] if h["request"].startswith("Physical damage")}
    requests = {p["prop_id"] for p in c["file"]["investigation"]["spec"]["propositions"] if p["text"] in asked}
    repeat = {x["claim_id"] for x in c["transcript"]["claims"] if (x.get("argument") or {}).get("claim_id") in requests}
    score = {"THOR": 0, "LOKI": 0}
    for r in c["rulings"]["rulings"]:
        if r["classification"] != "NOT_PRESSED" and r["claim_id"] not in repeat:
            score[r["side"]] += {"UPHELD": 1, "REJECTED": -1, "CONCEDED": -1}.get(r["ruling"], 0)
    expected = "THOR" if score["THOR"] > score["LOKI"] else "LOKI" if score["LOKI"] > score["THOR"] else "DRAW"
    assert c["result"]["winner"] == expected
    assert c["briefing_json"]["outcome"]["winner"] == expected and "**Verdict:" in c["briefing"]


def test_outcome_scoring():
    from backend.agents.odin import Odin
    from backend.court.models import Ruling

    def r(side, ruling, cls="INSUFFICIENT"):
        return Ruling(claim_id=f"{side}-{ruling}-{cls}", side=side, run=1, ruling=ruling, nature="INFERENCE",
                      classification=cls, reason="-")
    assert Odin.outcome([r("THOR", "CONCEDED", "NOT_PRESSED"), r("LOKI", "UPHELD")])["winner"] == "LOKI"
    assert Odin.outcome([r("THOR", "UPHELD"), r("LOKI", "UPHELD")])["winner"] == "DRAW"
    assert Odin.outcome([r("THOR", "UPHELD"), r("LOKI", "CONCEDED", "CONCEDED")])["winner"] == "THOR"
    assert Odin.outcome([r("THOR", "CONTESTED", "CONTESTED"), r("LOKI", "REJECTED")])["winner"] == "THOR"


# The shared Case File header shows every scope field, empty ones with the reason.
def test_case_file_header(cases):
    keys = ["Event ID", "Origin country", "Importer country", "Commodity", "As-of date"]
    for q in ("Q1", "Q2", "Q3"):
        h = cases[q]["briefing_json"]["case_file"]
        assert list(h) == keys and all(h.values()) and "## Case File" in cases[q]["briefing"]
    q1, q3 = cases["Q1"]["briefing_json"]["case_file"], cases["Q3"]["briefing_json"]["case_file"]
    scope = cases["Q1"]["file"]["case_scope"]
    assert q1["Event ID"].startswith(scope["event_id"]) and q1["Origin country"] == ", ".join(scope["event_countries"])
    assert q1["As-of date"].startswith(cases["Q1"]["file"]["as_of_date"])
    assert set(q3["Importer country"].split(", ")) == {"Midgard", "Tolan"}
