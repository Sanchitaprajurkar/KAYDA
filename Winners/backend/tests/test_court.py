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
        assert 1 <= len(mine) <= 6
        # every pressed claim cites evidence; a position with nothing admissible behind it is filed as not pressed
        assert all(c["citations"] or c["status"] == "NOT_PRESSED" for c in mine)
        spans = [c["estimate"] for c in mine if c["estimate"] and c["estimate"]["low"] is not None]
        assert all(e["low"] <= e["high"] for e in spans)


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
        assert all(x["classification"] in ("ESTABLISHED", "PARTLY_ESTABLISHED", "CONTESTED", "CONCEDED", "REJECTED",
                                           "UNCONTESTED", "NOT_PRESSED") for x in r["rulings"])
        # independent validation is stated for every claim that survives, attacked or not
        assert all(x["validation"] for x in r["rulings"] if x["ruling"] in ("UPHELD", "CONTESTED"))
        assert not any("never credibly countered" in x["reason"] for x in r["rulings"])


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
    # Midgard Wheat: no measured substitution in run 1 (upper bound only); the substitute series added on remand
    # gives run 2 a recorded-substitution lower bound
    filed = lambda c: c.get("narrowed_from") or c["estimate"]  # noqa: E731
    r1, r2 = filed(thor_r1["Midgard|Wheat"]), filed(thor_r2["Midgard|Wheat"])
    assert r1["low"] is None and r2["low"] is not None and r2["low"] < r2["high"]
    assert "revising net exposure" in thor_r2["Midgard|Wheat"]["statement"].lower()
    # Midgard Maize: no substitute series existed; Thor explicitly explains why position is maintained
    assert "following odin's remand" in thor_r2["Midgard|Maize"]["statement"].lower()
    assert "maintains" in thor_r2["Midgard|Maize"]["statement"].lower()
    assert "maintained" in thor_r2["Midgard|Maize"]["reasoning"].lower()


# Ranges are scenarios of one metric: high = no substitution (the route value decline), low = recorded substitution,
# and a low bound exists only when substitution is measured. Both sides argue from the same numbers.
def test_ranges(trial):
    cells = {(r["country"], r["sector"]): r for r in trial["rulings"][-1]["ranges"]}
    assert cells[("Tolan", "Maize")]["status"] == "EVIDENCE_MISSING" and cells[("Tolan", "Maize")]["odin"] is None
    covered = [c for c in cells.values() if c["status"] == "COVERED"]
    assert covered
    for c in covered:
        lo, hi = c["odin"]
        assert abs(hi - c["metrics"]["route_value_decline"]) < 0.01
        measured = c["substitution"].split(":")[0] in ("AVAILABLE", "CONFIRMED_ZERO")
        assert (lo is not None) == measured
        if measured:
            assert c["thor"] == c["odin"]  # Thor files every scenario the shared data supports
        else:
            # Thor's "up to" net exposure is the route decline under a stronger label: he narrows to the measured
            # fact rather than conceding it, and Odin's range is marked as an upper bound only
            assert c["thor"] is None and "narrowed from" in c["positions"]["THOR"]
            md = (trial["case"] / "briefing.md").read_text(encoding="utf-8")
            assert f"| {c['country']} | {c['sector']} |" in md and "upper bound; net exposure not established" in md
        # Loki reads the same data the other way: the recorded-substitution figure when substitution is measured,
        # otherwise he accepts the route decline and files no net-exposure number at all
        if lo is not None and lo < hi:
            assert c["loki"] == [lo, lo] or tuple(c["loki"]) == (lo, lo)
        else:
            assert c["loki"] is None and "net exposure not established" in c["positions"]["LOKI"]
        if lo is not None:
            assert lo <= hi
        assert c["metric_status"]["national_import_share"] == "UNAVAILABLE"  # no national total in the corpus
    assert any(c["odin"][0] is None for c in covered) and any(c["odin"][0] is not None for c in covered)


# FR8 / criterion 6: briefing has the sections, timestamped citations and an outlook with assumptions
def test_briefing(trial):
    md = (trial["case"] / "briefing.md").read_text(encoding="utf-8")
    for heading in ("## Executive summary", "## Established findings", "## Exposure table", "## Next-quarter outlook",
                    "Assumptions:", "## Data-quality appendix", "## Sources"):
        assert heading in md
    assert re.search(r"\[ORV-\d{4} \| Page \d+ \| Paragraph \d+ \| \d{4}-\d{2}-\d{2} \d{2}:\d{2}\]", md)
    assert "CALCULATION (shared assessment" in md and "Range (net exposure" in md and "## Metrics by cell" in md
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


# FR6.1 / criterion 9: private memory changes what an agent does, and the influence is logged. A concession from an
# earlier case is a labelled caution to re-evaluate; it never suppresses a claim in a new case.
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
    assert reads and any("no claim suppressed" in r["influenced"] for r in reads)
    assert not any("skipped re-asserting" in r["influenced"] for r in reads)


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
    report = report.model_copy(update={"investigation": None})  # the legacy evidence-claim path
    claims = loki.open_case(report, 1, [])
    target = next(c for c in claims if c.kind == "evidence")
    answers = loki.respond(report, [Attack(attack_id="ATT-1", run=1, attacker="THOR", target_claim_id=target.claim_id,
                                           reason="math_error", argument="does not add up", grounds="rule")], 1)
    assert answers[0].decision == "CONCEDED" and target.status == "CONCEDED"
    rows = memory.by_category("case_specific_concession")  # typed memory: the concession belongs to this case
    assert rows and all(r["case_id"] == "T-CON" for r in rows)


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



# -- exposure methodology: generic checks, cells chosen by their data, not by name ---------------------------------
@pytest.fixture(scope="module")
def assessed():
    from backend.court.tools import RunemarkTools
    heimdall = offline_heimdall()
    report = heimdall.build_case_file(query=QUERY, case_id="T-EXPO")
    tools = RunemarkTools(heimdall.evidence_store, heimdall.trade, report.as_of_date, set(), 99)
    return heimdall, report, tools


def _covered(report, tools):
    return [(c, tools.assessment(report, c)) for c in report.coverage_map if c.status == "COVERED"]


def test_metrics_have_their_own_denominators(assessed):
    _, report, tools = assessed
    for cell, a in _covered(report, tools):
        q = a.quantities
        vd = a.metrics["route_value_decline"]
        assert vd.denominator == "route_baseline_value"
        assert abs(vd.value - q["route_value_loss"].value / q["route_baseline_value"].value * 100) < 0.01
        vol = a.metrics["route_volume_decline"]
        assert abs(vol.value - q["route_volume_loss"].value / q["route_baseline_volume"].value * 100) < 0.01
        share = a.metrics["national_import_share"]
        assert share.denominator == "national_total_imports"
        assert share.value is None and share.status == "UNAVAILABLE" and share.missing_inputs
        assert all(r["row_id"] in q["route_baseline_value"].rows + q["route_disrupted_value"].rows
                   + q.get("substitute_baseline_value", q["route_value_loss"]).rows
                   + q.get("substitute_disrupted_value", q["route_value_loss"]).rows for r in a.breakdown)


def test_missing_substitution_is_not_zero(assessed):
    _, report, tools = assessed
    for cell, a in _covered(report, tools):
        if not cell.substitute_series:
            assert a.substitution.status in ("UNKNOWN", "UNAVAILABLE") and a.substitution.value is None
            assert a.low is None and a.metrics["net_exposure"].value is None
            assert a.high == a.metrics["route_value_decline"].value


def test_other_periods_are_sensitivity_not_bounds(assessed):
    _, report, tools = assessed
    for cell, a in _covered(report, tools):
        assert a.sensitivity  # other windows are reported...
        assert a.high == a.metrics["route_value_decline"].value  # ...but the bound is the primary period's figure
        if a.low is None:
            assert all(s["route_value_decline"] != a.low for s in a.sensitivity)


def test_odin_rejects_figures_whose_meaning_the_data_does_not_support(assessed):
    from backend.court.exposure import numeric_claim_defect
    from backend.court.models import Claim, Estimate, Evidence
    heimdall, report, tools = assessed
    cell, a = next((c, a) for c, a in _covered(report, tools) if a.low is None)
    rows = tools.row_evidence(a)
    base = dict(claim_id="X", side="THOR", run=1, country=cell.country, sector=cell.sector, kind="calculation",
                citations=rows, assessment=a)
    ok = Claim(statement=f"Route value fell {a.high:.2f}%.", estimate=Estimate(low=None, high=a.high), **base)
    assert numeric_claim_defect(tools, report, ok) is None
    invented_low = Claim(statement=f"Exposure is {a.high - 10:.2f}-{a.high:.2f}%.",
                         estimate=Estimate(low=a.high - 10, high=a.high), **base)
    assert numeric_claim_defect(tools, report, invented_low)[0] == "math_error"
    relabelled = Claim(statement=f"{cell.country} lost {a.high:.2f}% of its total imports.",
                       estimate=Estimate(low=None, high=a.high), **base)
    assert numeric_claim_defect(tools, report, relabelled)[0] == "wrong_scope"
    other = Evidence(doc_id=rows[0].doc_id, ref=rows[0].ref, excerpt="Shipments by a trading firm fell 62%.")
    quoted = Claim(claim_id="Y", side="THOR", run=1, country=cell.country, sector=cell.sector, kind="evidence",
                   statement="Shipments fell 62%.", citations=[other],
                   estimate=Estimate(low=62, high=62, metric="source_stated"))
    assert numeric_claim_defect(tools, report, quoted)[0] == "wrong_scope"



def test_sides_argue_opposite_readings_of_the_same_data(trial):
    claims = [c for t in trial["transcripts"] for c in t["claims"] if c["kind"] == "calculation"]
    by_cell = {}
    for c in claims:
        by_cell.setdefault((c["run"], c["country"], c["sector"]), {})[c["side"]] = c
    for pair in by_cell.values():
        if len(pair) < 2:
            continue
        thor, loki = pair["THOR"], pair["LOKI"]
        assert thor["assessment"]["breakdown"] == loki["assessment"]["breakdown"]  # same validated rows
        assert thor["statement"] != loki["statement"]
        a = thor["assessment"]
        if a["low"] is None:
            filed = thor["narrowed_from"] or thor["estimate"]
            assert filed["metric"] == "net_exposure" and filed["high"] == a["high"]
            assert loki["estimate"]["metric"] == "route_value_decline"  # no invented low bound
            if a["substitution"]["status"] == "UNKNOWN":
                # Loki argues the implication, question by question, instead of repeating Thor's arithmetic
                assert "cannot be quantified" in loki["statement"] and "question by question" in loki["statement"]
            else:
                assert "not" in loki["statement"] and "established" in loki["statement"]


# -- review fixes: fact vs conclusion, narrowing, mitigation, re-search outcome --------------------------------------
def _court(tmp_path):
    from backend.agents.loki import CourtLoki
    from backend.agents.odin import Odin
    from backend.agents.thor.court import CourtThor
    from backend.court.llm import CourtLLM
    from backend.court.memory import AgentMemory
    from backend.court.procedure import CourtLog
    from backend.court.tools import RunemarkTools
    heimdall = offline_heimdall()
    report = heimdall.build_case_file(query=QUERY, case_id="T-FIX")
    log = CourtLog(tmp_path / "log.jsonl", printer=None)
    tools = RunemarkTools(heimdall.evidence_store, heimdall.trade, report.as_of_date, set(), 99)
    mk = lambda cls, name: cls(tools, CourtLLM(name.upper(), 40_000, ScriptedLLM()),  # noqa: E731
                               AgentMemory(name, tmp_path / "memory"), log)
    return report, tools, mk(CourtThor, "thor"), mk(CourtLoki, "loki"), mk(Odin, "odin")


def _unmeasured_cell(report, tools):
    return next(c for c in report.coverage_map if c.status == "COVERED"
                and tools.assessment(report, c).high is not None and tools.assessment(report, c).low is None)


def test_odin_separates_the_measured_fact_from_the_net_exposure_conclusion(tmp_path):
    report, tools, thor, _, odin = _court(tmp_path)
    cell = _unmeasured_cell(report, tools)
    claim = thor.cell_claim(report, cell.country, cell.sector, 1)
    assert claim.estimate.metric == "net_exposure" and claim.estimate.low is None
    [r] = odin.rule(report, [claim], [], [], {})  # unattacked: still independently validated
    assert r.ruling == "UPHELD" and r.classification == "PARTLY_ESTABLISHED"
    by_metric = {f.metric: f for f in r.findings}
    assert by_metric["route_value_decline"].established
    assert not by_metric["net_exposure"].established and "upper bound" in by_metric["net_exposure"].reason
    assert any("recomputed from the rows" in v for v in r.validation)
    assert "never credibly countered" not in r.reason and "Not established" in r.reason


def test_label_attack_is_answered_by_narrowing_not_conceding(tmp_path):
    report, tools, thor, loki, odin = _court(tmp_path)
    cell = _unmeasured_cell(report, tools)
    t = thor._record(thor.cell_claim(report, cell.country, cell.sector, 1))
    grounds = [g for g in loki.rule_grounds(report, [t], 1) if g.narrow_to]
    assert grounds and grounds[0].narrow_to == "route_value_decline"
    grounds[0].attack_id = "AL1-01"
    [resp] = thor.respond(report, grounds, 1)
    assert resp.decision == "NARROWED" and t.status == "NARROWED"
    assert t.narrowed_from.metric == "net_exposure" and t.estimate.metric == "route_value_decline"
    assert t.estimate.high == t.assessment.metrics["route_value_decline"].value
    [r] = odin.rule(report, [t], grounds, [resp], {})
    assert r.ruling == "UPHELD" and r.classification == "ESTABLISHED" and "Narrowed" in r.reason


def test_a_correct_figure_for_another_metric_is_not_a_contradiction(tmp_path):
    report, tools, thor, loki, _ = _court(tmp_path)
    cell = _unmeasured_cell(report, tools)
    thor._record(thor.cell_claim(report, cell.country, cell.sector, 1))
    l = loki._record(loki.cell_claim(report, cell.country, cell.sector, 1))
    atk = thor._fallback_attack(report, [l], 1)
    # Thor may dispute Loki's reading, but never claims the rows contradict Loki's correct route decline
    assert atk is None or ("not" not in atk.argument[:40] and atk.target_claim_id == l.claim_id
                           and not atk.counter_evidence)


def test_loki_works_through_mitigation_when_substitution_is_unmeasured(tmp_path):
    from backend.court.exposure import MITIGATION_QUESTIONS, mitigation_analysis
    report, tools, _, loki, _ = _court(tmp_path)
    for cell in report.coverage_map:
        a = tools.assessment(report, cell) if cell.status == "COVERED" else None
        if not a or a.substitution.status != "UNKNOWN" or not a.substitution.sources:
            continue
        answers, _ = mitigation_analysis(tools, report, a)
        assert [x["key"] for x in answers] == [k for k, _, _ in MITIGATION_QUESTIONS]
        assert all(x["status"] in ("REPORTED", "NOT_ON_RECORD") for x in answers)
        claim = loki.cell_claim(report, cell.country, cell.sector, 1)
        assert "question by question" in claim.statement and "cannot be quantified" in claim.statement
        if any(x["status"] == "NOT_ON_RECORD" for x in answers):
            assert "silent on" in claim.statement
        volume = next(x for x in answers if x["key"] == "volume")["status"]
        assert ("not a validated trade series" if volume == "REPORTED" else "nothing on the record measures") \
            in claim.statement


def test_research_outcome_reports_unanswered_gaps(tmp_path):
    from backend.court.models import RunRecord
    report, tools, _, _, odin = _court(tmp_path)
    cell = _unmeasured_cell(report, tools)
    gap = f"{cell.country} {cell.sector}: net effect of substitute supply is not in the Case File"
    record = RunRecord(run=2, open_gaps=[gap])
    [o] = odin.research_outcomes(report, [gap], record)
    assert not o.resolved and o.explanation.startswith("Not resolved")
    assert "substitution is still" in o.explanation


# -- live-run fixes: screening, mandate, narrowed wording, attack searches ------------------------------------------
def test_out_of_scope_evidence_never_reaches_a_claim(tmp_path):
    from backend.agents.advocate import PickedClaim
    report, tools, thor, _, _ = _court(tmp_path)
    thor.open_case(report.model_copy(update={"investigation": None}), 1, [])  # the legacy round-1 screen
    cell = f"{_unmeasured_cell(report, tools).country}|{_unmeasured_cell(report, tools).sector}"
    assert thor._eligible and all(cells for cells in thor._eligible.values())
    outside = next(fid for fid, f in thor.pool.items() if fid not in thor._eligible)
    assert thor._evidence_claim(PickedClaim(fact_ids=[outside], cell=cell, statement="x"), {}, 1) is None
    inside, cells = next(iter(thor._eligible.items()))
    assert thor._evidence_claim(PickedClaim(fact_ids=[inside], cell=cells[0], statement="x"), {}, 1) is not None
    other = next((c for c in (f"{x.country}|{x.sector}" for x in report.coverage_map) if c not in cells), None)
    if other:  # the same evidence cannot be pointed at a cell it does not name
        assert thor._evidence_claim(PickedClaim(fact_ids=[inside], cell=other, statement="x"), {}, 1) is None


def test_attacks_that_argue_the_other_side_or_fake_a_math_error_are_refused(tmp_path):
    from backend.court.models import Attack
    report, tools, thor, loki, _ = _court(tmp_path)
    cell = _unmeasured_cell(report, tools)
    l = loki._record(loki.cell_claim(report, cell.country, cell.sector, 1))
    softer = Attack(attack_id="", run=1, attacker="THOR", target_claim_id=l.claim_id, reason="contradicts",
                    argument="Alternative supply has been found and prices have settled, so the loss is not as severe.")
    assert "opponent's case" in thor._off_mandate(softer, l, report)
    fake_math = Attack(attack_id="", run=1, attacker="THOR", target_claim_id=l.claim_id, reason="math_error",
                       argument="The net impact is larger than Loki says.")
    assert "recompute" in thor._off_mandate(fake_math, l, report)
    fair = Attack(attack_id="", run=1, attacker="THOR", target_claim_id=l.claim_id, reason="contradicts",
                  argument="Replacement cargoes arrive late and cost more, so mitigation is unproven.")
    assert thor._off_mandate(fair, l, report) is None


def test_narrowed_statement_reads_as_one_position(tmp_path):
    report, tools, thor, loki, _ = _court(tmp_path)
    cell = _unmeasured_cell(report, tools)
    t = thor._record(thor.cell_claim(report, cell.country, cell.sector, 1))
    [g] = [g for g in loki.rule_grounds(report, [t], 1) if g.narrow_to]
    g.attack_id = "AL1-01"
    thor.respond(report, [g], 1)
    rv = t.assessment.metrics["route_value_decline"].value
    assert f"up to {rv:.2f}%" not in t.statement  # the stronger figure is not asserted any more
    assert t.statement.count(f"{rv:.2f}%") >= 1 and "not claimed as established" in t.statement
    assert "remains" not in t.statement and "maintains up to" not in t.statement


def test_attack_searches_use_the_claims_substance(tmp_path):
    report, tools, thor, loki, _ = _court(tmp_path)
    cell = _unmeasured_cell(report, tools)
    for side, other in ((thor, loki), (loki, thor)):
        c = other.cell_claim(report, cell.country, cell.sector, 1)
        q = side._attack_query(c).lower()
        assert cell.country.lower() in q and cell.sector.lower() in q
        assert not any(w in q for w in ("following", "remand", "maintains", "relies", "page", "paragraph"))


def test_a_statement_may_not_say_more_than_its_source():
    from backend.agents.advocate import Advocate
    src = ["Asgard's long-term wheat contract with Orvan is mostly protected, local buyers say, but maize is bought "
           "on the open market."]
    assert Advocate._supported("Asgard's maize is bought on the open market.", src, "Asgard", "Maize")
    assert not Advocate._supported("The collapse of the Orvan grain corridor has led to a sustained disruption in "
                                   "maize imports for Asgard.", src, "Asgard", "Maize")
    herald = ["Asgard Herald is a regional paper with good local detail and some errors."]
    assert not Advocate._supported("Asgard's wheat imports are affected by the corridor collapse, leading to a "
                                   "notable disruption in supply.", herald, "Asgard", "Wheat")
