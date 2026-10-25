"""The courtroom end to end, offline: scripted stand-ins replace every LLM call, all else is real.

Each test names the problem-statement requirement it checks.
"""

import json
import re

import pytest

from backend.court.heimdall_bridge import ResolvedEvidenceStore
from backend.court.procedure import CourtSession
from backend.court.scripted import ScriptedLLM, offline_heimdall

QUERY = ("As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? "
         "Give a low and high range for wheat and maize imports.")
needs_evidence = pytest.mark.skipif(not ResolvedEvidenceStore().evidence_ids(), reason="resolved_data not built")
pytestmark = needs_evidence


def session(tmp_path, llm=None):
    llm = llm or ScriptedLLM()
    return CourtSession(heimdall=offline_heimdall(llm), llm_backends={k: llm for k in ("THOR", "LOKI", "ODIN")},
                        cases_dir=tmp_path / "cases", memory_dir=tmp_path / "memory", printer=None)


@pytest.fixture(scope="module")
def trial(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("court")
    result = session(tmp).run(QUERY, case_id="T-COURT")
    case = tmp / "cases" / "T-COURT"
    events = [json.loads(line) for line in (case / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    runs = sorted(p for p in case.iterdir() if p.name.startswith("run_"))
    return {"result": result, "case": case, "events": events, "runs": runs,
            "transcripts": [json.loads((r / "transcript.json").read_text(encoding="utf-8")) for r in runs],
            "rulings": [json.loads((r / "rulings.json").read_text(encoding="utf-8")) for r in runs]}


def _of(events, kind):
    return [e for e in events if e["event"] == kind]


# FR1.3 / FR5.1: no trial unless Heimdall verifies the event
def test_unverified_event_gets_no_trial(tmp_path):
    out = session(tmp_path).run("Did the Ymir canal flood close all shipping in Q4 2026?", case_id="T-FAKE")
    assert out["status"] == "NO_TRIAL"
    assert not (tmp_path / "cases" / "T-FAKE" / "run_1" / "transcript.json").exists()


# FR5.2 / criterion 3: both sides file evidence-backed claims from their own searches
def test_both_sides_search_and_file_claims(trial):
    queries = _of(trial["events"], "query")
    assert {"THOR", "LOKI"} <= {q["agent"] for q in queries}
    assert all(len(q["filters"]) >= 2 for q in queries if q["filters"])  # criterion 2: >= 2 metadata filters
    claims = trial["transcripts"][0]["claims"]
    for side in ("THOR", "LOKI"):
        mine = [c for c in claims if c["side"] == side]
        assert 1 <= len(mine) <= 6 and all(c["citations"] for c in mine)
        assert all(c["estimate"]["low"] <= c["estimate"]["high"] for c in mine)


# NFR2: every citation resolves to admissible evidence; nothing Heimdall set aside is cited
def test_citations_resolve_and_exclude_trapped_documents(trial):
    store = ResolvedEvidenceStore()
    evidence = set(store.evidence_ids())
    excluded = {x["doc_id"] for x in store.excluded_documents()}
    for t in trial["transcripts"]:
        cited = {e["doc_id"] for c in t["claims"] for e in c["citations"]}
        cited |= {e["doc_id"] for a in t["attacks"] for e in a["counter_evidence"]}
        cited |= {e["doc_id"] for r in t["responses"] for e in r["new_evidence"]}
        assert cited <= evidence and not cited & excluded


# FR5.3 / criterion 4: each side attacks at least one claim of the other in every run
def test_cross_examination_every_run(trial):
    for t in trial["transcripts"]:
        assert {"THOR", "LOKI"} <= {a["attacker"] for a in t["attacks"]}
        assert t["responses"]


# FR4.1 / FR4.2 / criterion 5: Odin rules on every claim and classifies it
def test_odin_rules_on_every_claim(trial):
    for t, r in zip(trial["transcripts"], trial["rulings"]):
        assert {c["claim_id"] for c in t["claims"]} == {x["claim_id"] for x in r["rulings"]}
        assert all(x["nature"] in ("SOURCED_FACT", "INFERENCE") for x in r["rulings"])
        assert all(x["classification"] in ("ESTABLISHED", "CONTESTED", "CONCEDED", "REJECTED", "UNCONTESTED")
                   for x in r["rulings"])


# FR4.3 / FR5.4 / criterion 8: Odin sends the case back and run 2 brings new evidence
def test_remand_and_second_run_with_new_evidence(trial):
    assert len(trial["runs"]) == 2 and trial["rulings"][0]["remand"]
    run2 = json.loads((trial["runs"][1] / "case_file.json").read_text(encoding="utf-8"))
    assert run2["run_number"] == 2 and {"ORV-0027", "ORV-0044"} <= set(run2["new_document_ids"])
    assert trial["result"]["status"] == "COMPLETE"


def test_run2_incorporates_new_evidence_and_explains_positions(trial):
    t1 = trial["transcripts"][0]["claims"]
    t2 = trial["transcripts"][1]["claims"]
    thor_r1 = {f"{c['country']}|{c['sector']}": c for c in t1 if c["side"] == "THOR" and c["kind"] == "calculation"}
    thor_r2 = {f"{c['country']}|{c['sector']}": c for c in t2 if c["side"] == "THOR" and c["kind"] == "calculation"}
    # Midgard Wheat: estimate revised downward because substitute series ORV-0027 was added
    assert thor_r2["Midgard|Wheat"]["estimate"]["low"] < thor_r1["Midgard|Wheat"]["estimate"]["low"]
    assert "revising net exposure" in thor_r2["Midgard|Wheat"]["statement"].lower()
    # Midgard Maize: no substitute series existed; Thor explicitly explains why position is maintained
    assert "following odin's remand" in thor_r2["Midgard|Maize"]["statement"].lower()
    assert "maintains" in thor_r2["Midgard|Maize"]["statement"].lower()
    assert "maintained" in thor_r2["Midgard|Maize"]["reasoning"].lower()


# Range accuracy and calibration: Odin's range sits inside both sides' ranges; the gap cell gets none
def test_ranges(trial):
    cells = {(r["country"], r["sector"]): r for r in trial["rulings"][-1]["ranges"]}
    assert cells[("Tolan", "Maize")]["status"] == "EVIDENCE_MISSING" and cells[("Tolan", "Maize")]["odin"] is None
    for key in [("Midgard", "Wheat"), ("Tolan", "Wheat"), ("Midgard", "Maize")]:
        c = cells[key]
        lo, hi = c["odin"]
        assert c["thor"][0] - 0.01 <= hi and c["loki"][1] + 0.01 >= lo  # overlaps both sides
        assert hi - lo <= 15  # calibrated, not a safe-but-useless range
    assert 30 <= cells[("Midgard", "Wheat")]["odin"][0] <= 45  # net of substitutes, not the 60% gross loss


# FR8 / criterion 6: briefing has the sections, timestamped citations and an outlook with assumptions
def test_briefing(trial):
    md = (trial["case"] / "briefing.md").read_text(encoding="utf-8")
    for heading in ("## Executive summary", "## Established findings", "## Exposure table", "## Next-quarter outlook",
                    "Assumptions:", "## Data-quality appendix", "## Sources"):
        assert heading in md
    assert re.search(r"\[ORV-\d{4} \| P\d+ \| \d{4}-\d{2}-\d{2} \d{2}:\d{2}\]", md)
    assert "ORV-0043 set aside before trial: RETRACTED" in md


# NFR5: a repeated query is refused, never run twice
def test_no_query_runs_twice(trial):
    runs = [(q["query"].lower(), json.dumps(q["filters"], sort_keys=True)) for q in _of(trial["events"], "query")]
    keys = [(" ".join(sorted(set(re.findall(r"[a-z0-9]+", q)))), f) for q, f in runs]
    assert len(keys) == len(set(keys))


# NFR6: every run saves its Case File and rulings, and the case its meta
def test_reproducibility_artifacts(trial):
    for r in trial["runs"]:
        assert {"case_file.json", "transcript.json", "rulings.json"} <= {p.name for p in r.iterdir()}
    meta = json.loads((trial["case"] / "meta.json").read_text(encoding="utf-8"))
    assert meta["as_of_date"] == "2027-01-25" and meta["limits"]["max_runs"] == 3


# FR6.1 / criterion 9: private memory changes what an agent does, and the influence is logged
def test_memory_changes_an_advocates_action(tmp_path):
    from backend.court.memory import AgentMemory
    store = ResolvedEvidenceStore()
    fact = next(f for f in store.facts("ORV-0022") if "direction is clear" in f.statement)
    AgentMemory("loki", tmp_path / "memory").write(f"E5:{fact.fact_id}", "concession",
                                                    {"statement": fact.statement, "fact_ids": [fact.fact_id]},
                                                    "EARLIER-CASE")
    session(tmp_path).run(QUERY, case_id="T-MEM")
    events = [json.loads(x) for x in (tmp_path / "cases" / "T-MEM" / "log.jsonl").read_text(encoding="utf-8")
              .splitlines()]
    reads = [e for e in _of(events, "memory_read") if e["agent"] == "LOKI"]
    assert reads and "skipped re-asserting" in reads[0]["influenced"]
    claims = json.loads((tmp_path / "cases" / "T-MEM" / "run_1" / "transcript.json").read_text(encoding="utf-8"))
    assert not any(e.get("fact_id") == fact.fact_id for c in claims["claims"] if c["side"] == "LOKI"
                   for e in c["citations"])


# FR2.3 / FR3.3: conceding is recorded and remembered; a rule-proven defect cannot be argued away
def test_concession_is_remembered(tmp_path):
    from backend.agents.loki import CourtLoki
    from backend.court.llm import CourtLLM
    from backend.court.memory import AgentMemory
    from backend.court.models import Attack
    from backend.court.procedure import CourtLog
    from backend.court.tools import RunemarkTools
    heimdall = offline_heimdall()
    report = heimdall.build_case_file(query=QUERY, case_id="T-CON")
    log = CourtLog(tmp_path / "log.jsonl", printer=None)
    tools = RunemarkTools(heimdall.evidence_store, heimdall.trade, report.as_of_date, set(), 16)
    memory = AgentMemory("loki", tmp_path / "memory")
    loki = CourtLoki(tools, CourtLLM("LOKI", 40_000, ScriptedLLM()), memory, log)
    claims = loki.open_case(report, 1, [])
    target = next(c for c in claims if c.kind == "evidence")
    answers = loki.respond(report, [Attack(attack_id="ATT-1", run=1, attacker="THOR", target_claim_id=target.claim_id,
                                           reason="math_error", argument="does not add up", grounds="rule")], 1)
    assert answers[0].decision == "CONCEDED" and target.status == "CONCEDED"
    assert memory.by_category("concession")


# NFR3 / NFR5: an exhausted token budget degrades to the rules instead of crashing
def test_token_budget_falls_back_to_rules(tmp_path, monkeypatch):
    import backend.court.procedure as procedure
    monkeypatch.setattr(procedure, "MAX_TOKENS_PER_AGENT_PER_RUN", 10)
    out = session(tmp_path).run(QUERY, case_id="T-BUDGET")
    assert out["status"] in ("COMPLETE", "INCOMPLETE")
    events = [json.loads(x) for x in (tmp_path / "cases" / "T-BUDGET" / "log.jsonl").read_text(encoding="utf-8")
              .splitlines()]
    assert any(e["event"] == "limit_hit" and e.get("limit") == "tokens" for e in events)
    t = json.loads((tmp_path / "cases" / "T-BUDGET" / "run_1" / "transcript.json").read_text(encoding="utf-8"))
    assert t["claims"] and t["attacks"]  # calculations and a rule-based attack still happen


# Problem 4: Odin's final exposure table differentiates contested ranges, missing evidence, and unestablished ranges
def test_problem4_briefing_contested_ranges_and_unestablished_exposure(tmp_path):
    from backend.court.briefing import write_briefing
    from backend.court.heimdall_bridge import CaseEvidenceReport
    from backend.court.models import CellRange, RunRecord, Ruling
    from backend.court.procedure import CourtSession

    from pathlib import Path
    # 1. Verify standard multi-run trial output includes the new legend and states
    res = session(tmp_path).run(QUERY, case_id="T-P4")
    md = (Path(res["dir"]) / "briefing.md").read_text(encoding="utf-8")
    assert "Odin column key" in md
    assert "no defensible range established" in md
    assert "evidence missing" in md

    # 2. Test explicit briefing formatting for both CONTESTED and UNESTABLISHED states
    case_dir = tmp_path / "cases" / "T-P4"
    r2_data = json.loads((case_dir / "run_2" / "rulings.json").read_text(encoding="utf-8"))
    report_data = json.loads((case_dir / "run_2" / "transcript.json").read_text(encoding="utf-8"))
    
    # Simulate a run with a contested cell and a covered cell with no defensible range
    synth_ranges = [
        CellRange(country="Midgard", sector="Maize", status="COVERED",
                  thor=(50.2, 70.0), loki=(38.5, 62.5), odin=(50.2, 62.5),
                  odin_classification="CONTESTED", basis="Contested calculation"),
        CellRange(country="Midgard", sector="Wheat", status="COVERED",
                  thor=(39.4, 67.6), loki=(37.4, 41.4), odin=None,
                  odin_classification=None, basis="No calculation survived"),
        CellRange(country="Tolan", sector="Maize", status="EVIDENCE_MISSING",
                  thor=None, loki=None, odin=None, basis="No trade series"),
        CellRange(country="Tolan", sector="Wheat", status="COVERED",
                  thor=(31.4, 40.2), loki=(28.3, 40.2), odin=(28.3, 40.2),
                  odin_classification="ESTABLISHED", basis="Established findings")
    ]
    
    r2_data["run"] = 2
    r2_data["claims"] = report_data["claims"]
    mock_run = RunRecord.model_validate(r2_data)
    mock_run.ranges = synth_ranges
    
    heimdall = offline_heimdall()
    rep = heimdall.build_case_file(query=QUERY, case_id="T-P4")
    b = write_briefing(rep, [mock_run], complete=True, reasons=[])
    b_md = b["markdown"]
    
    # Executive summary explains contested range
    assert "Midgard Maize: Odin's range **50.2-62.5%** **(contested range — see findings)**" in b_md
    assert "Midgard Wheat: no defensible range established" in b_md
    
    # Exposure table annotations
    assert "| Midgard | Maize | 50.2-70.0% | 38.5-62.5% | 50.2-62.5% _(contested)_ |" in b_md
    assert "| Midgard | Wheat | 39.4-67.6% | 37.4-41.4% | no defensible range established |" in b_md
    assert "| Tolan | Maize | - | - | evidence missing |" in b_md
    assert "| Tolan | Wheat | 31.4-40.2% | 28.3-40.2% | 28.3-40.2% |" in b_md

