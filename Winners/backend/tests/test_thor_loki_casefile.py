"""Thor and Loki over Heimdall's investigation Case File, end to end on the real corpus (offline: rules path).

Case-specific questions appear only here, as fixtures.
"""

import json
from pathlib import Path

import pytest

from backend.agents.argument import validate_refs
from backend.court.heimdall_bridge import ResolvedEvidenceStore
from backend.court.models import ATTACK_TYPES, Claim
from backend.court.procedure import CourtSession
from backend.court.scripted import ScriptedLLM, offline_heimdall
from backend.court.tools import RunemarkTools

pytestmark = pytest.mark.skipif(not ResolvedEvidenceStore().evidence_ids(), reason="resolved_data not built")

Q1 = ("Evaluate the breaking alert claiming that Orvan Grain Port infrastructure and grain terminal silos were "
      "physically destroyed in military strikes. Conduct event verification to rule whether this disruption is "
      "verified or rejected as a decoy, citing verified port authority and logistics records.")
Q2 = ("Adjudicate the dispute between Ledger Analytics (projecting a -90% grain export wipeout and imminent famine in "
      "importing nations) versus Corvan Grain company statements and customs telemetry. Detail which claims are "
      "Established, Contested, or Conceded during cross-examination.")
Q3 = ("As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? Give a low "
      "and high range for wheat and maize imports.")


def _run(tmp: Path, question: str, case_id: str, memory: Path):
    llm = ScriptedLLM()
    session = CourtSession(heimdall=offline_heimdall(llm), llm_backends={k: llm for k in ("THOR", "LOKI", "ODIN")},
                           cases_dir=tmp / "cases", memory_dir=memory, printer=None)
    session.run(question, case_id=case_id)
    case = tmp / "cases" / case_id
    runs = sorted(p for p in case.iterdir() if p.name.startswith("run_"))
    return {"case": case,
            "events": [json.loads(x) for x in (case / "log.jsonl").read_text(encoding="utf-8").splitlines()],
            "transcripts": [json.loads((r / "transcript.json").read_text(encoding="utf-8")) for r in runs],
            "files": [json.loads((r / "case_file.json").read_text(encoding="utf-8")) for r in runs]}


@pytest.fixture(scope="module")
def trials(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("tlc")
    return {k: _run(tmp, q, f"T-TLC-{k}", tmp / f"mem-{k}") for k, q in (("Q1", Q1), ("Q2", Q2), ("Q3", Q3))}


def _args(t, side):
    return [c for c in t["claims"] if c["side"] == side and c.get("argument")]


# 1. both sides address the identical set of Heimdall claim IDs, and only those
@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3"])
def test_same_claim_ids_on_both_sides(trials, q):
    for t, cf in zip(trials[q]["transcripts"], trials[q]["files"]):
        props = {p["prop_id"] for p in cf["investigation"]["spec"]["propositions"]}
        thor = {c["argument"]["claim_id"] for c in _args(t, "THOR")}
        loki = {c["argument"]["claim_id"] for c in _args(t, "LOKI")}
        print(f"{q} run claim IDs: THOR {sorted(thor)} LOKI {sorted(loki)} Heimdall {sorted(props)}")
        assert thor == loki == props


# 2. every filed citation passes the validator; rejected citations are counted from the audit log
@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3"])
def test_every_citation_validates(trials, q):
    from backend.court.heimdall_bridge import CaseEvidenceReport
    h = offline_heimdall()
    for t, cf in zip(trials[q]["transcripts"], trials[q]["files"]):
        report = CaseEvidenceReport.model_validate(cf)
        tools = RunemarkTools(h.evidence_store, h.trade, report.as_of_date, set(), 99)
        refs = [r for c in t["claims"] if c.get("argument") for r in Claim.model_validate(c).argument.evidence_refs]
        refs += [r for a in t["attacks"] for r in __import__("backend.court.models", fromlist=["Attack"])
                 .Attack.model_validate(a).counter_evidence_refs]
        kept, failed = validate_refs(refs, report, tools, "recheck")
        assert not failed, failed
    rejected = [e for e in trials[q]["events"] if e["event"] == "citation_rejected"]
    print(f"{q}: {len(refs)} filed reference(s) re-validated; {len(rejected)} citation(s) rejected during the trial")


# 3. an event-verification question produces no exposure numbers or ranges
def test_q1_has_no_exposure_numbers(trials):
    for t, cf in zip(trials["Q1"]["transcripts"], trials["Q1"]["files"]):
        assert cf["coverage_map"] == [] and not cf["investigation"]["spec"]["exposure_applicable"]
        for c in t["claims"]:
            assert c["kind"] != "calculation" and c["estimate"] is None and c["assessment"] is None
            assert c["argument"]["numerical_analysis"] is None


# 4. the export forecast and the famine prediction are separate claims
def test_q2_forecast_and_famine_are_separate_claims(trials):
    props = trials["Q2"]["files"][0]["investigation"]["spec"]["propositions"]
    export = [p["prop_id"] for p in props if "export" in p["text"].lower()]
    famine = [p["prop_id"] for p in props if "famine" in p["text"].lower()]
    print("Q2 propositions:", [(p["prop_id"], p["text"]) for p in props])
    assert export and famine and not set(export) & set(famine), "Heimdall did not split the two predictions"


# 5. wrong-scope evidence is challenged with the matching attack type (only where such evidence was cited)
@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3"])
def test_wrong_scope_is_named_as_such(trials, q):
    attacks = [a for t in trials[q]["transcripts"] for a in t["attacks"]]
    assert all(a["attack_type"] in ATTACK_TYPES for a in attacks if a.get("attack_type"))
    scoped = [a for a in attacks if a.get("attack_type") == "wrong_entity_or_geographic_scope"]
    print(f"{q}: attack types {sorted({a.get('attack_type') for a in attacks})}; wrong-scope attacks {len(scoped)}"
          + ("" if scoped else " (not exercised)"))
    for a in scoped:
        assert a["defect"] and a["target_evidence_or_reasoning"]


# 6. a partial concession keeps the claim ID, records a Revision and retains the valid references
@pytest.mark.parametrize("q", ["Q1", "Q2", "Q3"])
def test_partial_concession_keeps_claim(trials, q):
    found = 0
    for t in trials[q]["transcripts"]:
        claims = {c["claim_id"]: c for c in t["claims"]}
        for r in t["responses"]:
            if r.get("revision") and r["action"] in ("accept_point", "narrow_proposition"):
                c = claims[r["claim_id"]]
                rev = c["argument"]["revision_history"][-1]
                assert rev["original_proposition"] == c["argument"]["proposition_text"]
                assert rev["retained_evidence_refs"] and c["argument"]["evidence_refs"] == rev["retained_evidence_refs"]
                assert r["decision"] != "CONCEDED"  # an advocate action, not a withdrawal of the whole claim
                found += 1
    print(f"{q}: partial concessions with retained evidence: {found}" + ("" if found else " (not exercised)"))


# 7. each side searched for targeted evidence or used counter-evidence from the Case File, with a reason
@pytest.mark.parametrize("q", ["Q1", "Q2"])
def test_each_side_requested_or_used_counter_evidence(trials, q):
    ev = trials[q]["events"]
    for side in ("THOR", "LOKI"):
        requests = [e for e in ev if e["event"] == "evidence_request" and e["agent"] == side]
        countered = [a for t in trials[q]["transcripts"] for a in t["attacks"]
                     if a["attacker"] == side and a.get("counter_evidence_refs")]
        print(f"{q} {side}: {len(requests)} evidence request(s), {len(countered)} attack(s) with counter-evidence")
        assert requests or countered
        assert all(e["reason"] for e in requests)


# 8. a concession in one case neither suppresses nor pre-resolves a claim in another case sharing the memory store:
# the second case files and argues exactly as it does on a fresh store.
def _filed(run):
    return {e["claim"]["claim_id"]: (e["claim"]["status"], e["claim"]["argument"]["confidence"]["level"],
                                     [r["source_id"] for r in e["claim"]["argument"]["evidence_refs"]])
            for e in run["events"] if e["event"] == "claim" and e["claim"].get("argument")}


def _outcome(run):
    return [(r["claim_id"], r["action"], r["decision"]) for t in run["transcripts"] for r in t["responses"]]


@pytest.mark.parametrize("first,second", [("Q1", "Q2"), ("Q2", "Q1")])
def test_memory_does_not_cross_cases(tmp_path, first, second):
    qs = {"Q1": Q1, "Q2": Q2}
    mem = tmp_path / "shared-memory"
    a = _run(tmp_path / "shared", qs[first], f"T-MEM-{first}", mem)
    b = _run(tmp_path / "shared", qs[second], f"T-MEM-{second}", mem)
    fresh = _run(tmp_path / "fresh", qs[second], f"T-MEM-{second}", tmp_path / "fresh-memory")
    conceded_first = [r for t in a["transcripts"] for r in t["responses"] if r["decision"] in ("CONCEDED", "NARROWED")]
    reads = [e for e in b["events"] if e["event"] == "memory_read"]
    print(f"{first} -> {second}: {len(conceded_first)} concession/narrowing(s) in {first}; memory reads in {second}: "
          f"{sorted({e['influenced'][:100] for e in reads})}")
    from backend.court.memory import AgentMemory
    written = [r for side in ("thor", "loki") for cat in ("case_specific_concession", "case_specific_proposition")
               for r in AgentMemory(side, mem).by_category(cat) if r["case_id"] == f"T-MEM-{first}"]
    assert written, "the first case left no case-specific memory, so the check would be vacuous"
    assert not any("skipped re-asserting" in e["influenced"] for e in reads)
    assert all("no claim suppressed" in e["influenced"] for e in reads)  # prior-case entries surface only as cautions
    assert _filed(b) == _filed(fresh)      # same claims, statuses, confidence and evidence as on a fresh store
    assert _outcome(b) == _outcome(fresh)  # and the same cross-examination outcome
