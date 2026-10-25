import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from tools import search, read_doc, get_trade_series, compute_change, clear_query_ledger

def test_search_rrf_and_ledger():
    clear_query_ledger()
    query = "Orvan wheat sea shipments corridor"

    # First call should succeed
    res1 = search(query=query, filters={"as_of_date": "2027-01-25"}, k=3)
    assert res1["status"] == "SUCCESS", f"Expected SUCCESS, got {res1.get('status')}"
    assert len(res1["results"]) > 0, "Expected search results"
    first_result = res1["results"][0]
    assert "rrf_score" in first_result, "Expected rrf_score in result"
    print(f"[PASS] search() - Retrieved {len(res1['results'])} documents via Hybrid RRF.")
    print(f"       Top match: {first_result['doc_id']} (RRF score: {first_result['rrf_score']})")

    # Second identical call should be rejected by the duplicate query ledger
    res2 = search(query=query, filters={"as_of_date": "2027-01-25"}, k=3)
    assert res2["status"] == "REJECTED_DUPLICATE", f"Expected REJECTED_DUPLICATE, got {res2.get('status')}"
    print("[PASS] search() - Duplicate query rejection ledger correctly rejected repeated call.")

    # Clock cutoff verification: future date should return zero
    res3 = search(query="corridor", filters={"as_of_date": "2023-01-01"}, k=5, allow_duplicate=True)
    assert len(res3["results"]) == 0, f"Clock enforcement leak: found {len(res3['results'])} docs before 2023"
    print("[PASS] search() - Clock enforcement strictly excluded documents past as_of_date.")

def test_read_doc():
    # Test reading specific paragraphs from ORV-0009
    doc = read_doc("ORV-0009", paras=["P2", "P3"])
    assert doc["status"] == "SUCCESS", f"Expected SUCCESS, got {doc.get('status')}"
    assert doc["doc_id"] == "ORV-0009"
    assert len(doc["paragraphs"]) == 2, f"Expected 2 paragraphs, got {len(doc['paragraphs'])}"
    assert "Route: Orvan to Midgard" in doc["paragraphs"][0]["text"]
    assert "250,000 tonnes" in doc["paragraphs"][1]["text"]
    print(f"[PASS] read_doc() - Correctly fetched targeted paragraphs P2 and P3 from ORV-0009.")

    # Test reading full document with None
    doc_full = read_doc("ORV-0013")
    assert doc_full["status"] == "SUCCESS"
    assert doc_full["is_retracted"] is False
    print(f"[PASS] read_doc() - Correctly read full text of ORV-0013 ({len(doc_full['paragraphs'])} paragraphs).")

    # Test missing document graceful handling (NFR3)
    missing = read_doc("NONEXISTENT-9999")
    assert missing["status"] == "NOT_FOUND"
    print("[PASS] read_doc() - Gracefully handled nonexistent document without crashing.")

def test_get_trade_series():
    series = get_trade_series(origin="Orvan", dest="Midgard", sector="Wheat", as_of_date="2027-01-25")
    assert series["status"] == "SUCCESS", f"Expected SUCCESS, got {series.get('status')}"
    assert series["count"] >= 10, f"Expected 10+ trade series rows, got {series['count']}"
    
    # Check first row has expected structure
    first_row = series["data"][0]
    assert "volume_tonnes" in first_row
    assert "value_usd_m" in first_row
    assert "doc_id" in first_row
    print(f"[PASS] get_trade_series() - Retrieved {series['count']} validated trade series points for Orvan -> Midgard (Wheat).")
    print(f"       Total Volume: {series['summary']['total_volume_tonnes']:,.0f} tonnes, Total Value: USD {series['summary']['total_value_usd_m']}M")

def test_compute_change():
    # Orvan to Midgard baseline (July, August 2026: 250k, 267k = 517k tonnes)
    rows_pre = [
        {"period": "2026-07", "volume_tonnes": 250000.0, "value_usd_m": 90.0},
        {"period": "2026-08", "volume_tonnes": 267000.0, "value_usd_m": 96.1}
    ]
    # Post-disruption (Sept, Oct 2026: 93k, 84k = 177k tonnes)
    rows_post = [
        {"period": "2026-09", "volume_tonnes": 93000.0, "value_usd_m": 38.2},
        {"period": "2026-10", "volume_tonnes": 84000.0, "value_usd_m": 34.5}
    ]

    # Gross volume change
    res_pct = compute_change(rows_pre, rows_post, mode="percentage")
    assert res_pct["status"] == "SUCCESS"
    assert -66.0 <= res_pct["percentage_change"] <= -65.0, f"Unexpected pct: {res_pct['percentage_change']}"
    print(f"[PASS] compute_change() - Volume drop computed: {res_pct['percentage_change']}%")

    # Net of mitigation (e.g. +30,000 tonnes shifted by rail)
    res_net = compute_change(rows_pre, rows_post, mode="percentage", net_of=30000.0)
    assert res_net["percentage_change"] > res_pct["percentage_change"]
    print(f"[PASS] compute_change() - Net volume drop with rail mitigation: {res_net['percentage_change']}% (cushioned by 30k tonnes)")

    # Full summary mode
    res_summary = compute_change(rows_pre, rows_post, mode="summary", net_of=15000.0)
    assert "volume" in res_summary and "value" in res_summary
    print(f"[PASS] compute_change() - Full summary calculation: Value delta = USD {res_summary['value']['delta_usd_m']}M")

if __name__ == "__main__":
    print("\n----------------------------------------------")
    print("  DETERMINISTIC TOOLS TEST SUITE (backend/tools/)")
    print("----------------------------------------------\n")
    test_search_rrf_and_ledger()
    test_read_doc()
    test_get_trade_series()
    test_compute_change()
    print("\n----------------------------------------------")
    print("  ALL 4 DETERMINISTIC TOOLS PASSED WITH 100% SUCCESS")
    print("----------------------------------------------\n")
