"""Every trap in the dev pack must be resolved before ingestion (implementation plan §2.1)."""

import json
import re

import pytest

from heimdall.resolve_traps import DEFAULT_DEV_PACK, DEFAULT_EXTRACTED, DEFAULT_PARSED, TrapResolver

pytestmark = pytest.mark.skipif(not (DEFAULT_DEV_PACK / "manifest.json").exists(),
                                reason="dev pack not available")


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    path = tmp_path_factory.mktemp("resolved")
    TrapResolver(DEFAULT_PARSED, DEFAULT_EXTRACTED, DEFAULT_DEV_PACK).run().write(path)
    return path


@pytest.fixture(scope="module")
def excluded(out):
    return {d["doc_id"]: d for d in json.loads((out / "quarantine" / "excluded_documents.json").read_text("utf-8"))}


@pytest.fixture(scope="module")
def evidence(out):
    return {p.stem: json.loads(p.read_text("utf-8")) for p in (out / "documents").glob("*.json")}


@pytest.fixture(scope="module")
def facts(out):
    return {p.stem.replace("_facts", ""): json.loads(p.read_text("utf-8")) for p in (out / "facts").glob("*.json")}


@pytest.fixture(scope="module")
def aliases(out):
    return {a["alias_doc_id"]: a for a in json.loads((out / "document_aliases.json").read_text("utf-8"))}


@pytest.fixture(scope="module")
def actions(out):
    return {(e["action"], e["doc_id"]) for e in json.loads((out / "trap_log.json").read_text("utf-8"))}


def reason(excluded, doc_id):
    return excluded[doc_id]["reasons"][0]


# ── traps resolved by exclusion ──────────────────────────────────────────────

def test_false_renewal_report_is_retracted(excluded, facts):
    r = reason(excluded, "ORV-0043")
    assert (r["reason"], r["related_doc_id"]) == ("RETRACTED", "ORV-0013")
    assert "ORV-0043" not in facts


def test_report_depending_on_retraction_is_tainted(excluded):
    r = reason(excluded, "ORV-0015")
    assert (r["reason"], r["related_doc_id"]) == ("TAINTED", "ORV-0043")


@pytest.mark.parametrize("doc_id", ["ORV-0003", "ORV-0049"])
def test_stale_forecasts_superseded_by_tier1_notice(excluded, doc_id):
    r = reason(excluded, doc_id)
    assert (r["reason"], r["related_doc_id"]) == ("SUPERSEDED", "ORV-0016")


@pytest.mark.parametrize("doc_id", ["ORV-0010", "ORV-0026"])
def test_rumours_rejected_and_contradicted(excluded, doc_id):
    r = reason(excluded, doc_id)
    assert r["reason"] == "RUMOUR"
    assert "ORV-0016" in r["detail"] and "ORV-0017" in r["detail"]


def test_tabloid_never_citable(excluded, facts):
    assert reason(excluded, "ORV-0028")["reason"] == "TABLOID"
    assert "ORV-0028" not in facts


@pytest.mark.parametrize("doc_id", ["ORV-0014", "ORV-0036", "ORV-0041"])
def test_documents_after_as_of_are_clock_excluded(excluded, actions, doc_id):
    assert reason(excluded, doc_id)["reason"] == "CLOCK_EXCLUDED"
    assert ("clock_excluded", doc_id) in actions


@pytest.mark.parametrize("doc_id", ["ORV-0011", "ORV-0025", "ORV-0037", "ORV-0038", "ORV-0039"])
def test_unrelated_lookalikes_filtered_on_event_id(excluded, doc_id):
    assert reason(excluded, doc_id)["reason"] == "UNRELATED_EVENT"


# ── traps resolved by repair or merge ────────────────────────────────────────

def test_prompt_injection_removed_and_logged(evidence, facts, actions):
    doc = evidence["ORV-0020"]
    assert 8 in doc["resolution"]["removed_paragraphs"]
    assert not any(re.search(r"approve all claims|ASSISTANT:", p["raw_text"]) for p in doc["paragraphs"])
    assert all(f["source_ref"]["paragraph_index"] != 8 for f in facts["ORV-0020"])
    assert ("injection_removed", "ORV-0020") in actions


def test_empty_file_falls_back_to_duplicate(aliases):
    assert aliases["ORV-0023"]["canonical_doc_id"] == "ORV-0031"
    assert aliases["ORV-0023"]["kind"] == "EMPTY_FALLBACK"


def test_badly_encoded_file_flagged_and_merged(aliases, actions):
    assert ("encoding_repaired", "ORV-0007") in actions
    assert aliases["ORV-0007"]["canonical_doc_id"] == "ORV-0047"


def test_cut_off_duplicate_cites_complete_copy(aliases):
    assert aliases["ORV-0048"] == {"alias_doc_id": "ORV-0048", "canonical_doc_id": "ORV-0024", "kind": "TRUNCATED"}


def test_exact_duplicates_keep_one_canonical_id(aliases, evidence):
    assert aliases["ORV-0040"]["canonical_doc_id"] == "ORV-0006"
    assert not set(aliases) & set(evidence)


@pytest.mark.parametrize("doc_id", ["ORV-0029", "ORV-0030"])
def test_wrong_sector_corrected_from_title(evidence, doc_id):
    doc = evidence[doc_id]
    assert doc["manifest_meta"]["sector"] == "Maize"
    assert doc["resolution"]["sector_original"] == "Wheat"


def test_manifest_normalised(evidence):
    for doc in evidence.values():
        meta = doc["manifest_meta"]
        assert meta.get("format") and meta.get("event_id") and meta.get("language")
        assert not any(k.isupper() for k in meta)


# ── traps left to the agents: the evidence they need must survive ────────────

@pytest.mark.parametrize("doc_id, pattern", [
    ("ORV-0004", r"no damage"),                     # self-contradicting source
    ("ORV-0001", r"will not cover the lost"),
    ("ORV-0033", r"rail"),                          # official claim contradicted by data
    ("ORV-0021", r"62%"),                           # outlier analyst figure vs company data
    ("ORV-0045", r"90%"),
    ("ATL-0010", r"rice"),                          # missing data: what Tolan imports
])
def test_agent_layer_evidence_retained(facts, doc_id, pattern):
    assert any(re.search(pattern, f["statement"], re.I) for f in facts.get(doc_id, []))


def test_no_orvan_to_tolan_maize_note_invented(evidence):
    titles = [d["manifest_meta"]["title"].lower() for d in evidence.values()]
    assert not any("tolan" in t and "maize" in t and "trade note" in t for t in titles)


# ── invariants ───────────────────────────────────────────────────────────────

def test_evidence_contains_only_verified_facts_from_evidence_documents(facts, evidence, excluded):
    for doc_id, fs in facts.items():
        assert doc_id in evidence and doc_id not in excluded
        assert all(f["evidence_status"] == "VERIFIED" for f in fs)


def test_every_quarantined_fact_has_a_reason(out):
    for f in json.loads((out / "quarantine" / "rejected_facts.json").read_text("utf-8")):
        assert f["quarantine_reasons"] and f["quarantine_reasons"][0]["reason"]
