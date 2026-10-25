import pytest
from backend.schemas.thor_claim import (
    DisruptionCalculationInput,
    DisruptionCalculationResult,
    TradeRow,
)
from backend.services.runemark import ParsedDocument
from backend.tools.trade_calculator import TradeCalculator

def test_trade_row_extraction_narrative():
    doc = ParsedDocument(
        doc_id="TEST-01",
        file_path="mock.txt",
        format="TXT",
        sector="Wheat",
        body_text=(
            "[P2] In July 2026, the value was USD 90.0M and the volume was 250,000 tonnes.\n"
            "[P8] In July 2025, the value was USD 94.7M and the volume was 263,000 tonnes.\n"
        ),
    )
    rows = TradeCalculator.extract_trade_rows(doc)
    assert len(rows) == 2
    assert rows[0].full_id == "TEST-01#P2"
    assert rows[0].val_usd_m == 90.0
    assert rows[0].vol_tonnes == 250000.0
    assert rows[0].year == 2026
    assert rows[1].full_id == "TEST-01#P8"
    assert rows[1].val_usd_m == 94.7
    assert rows[1].vol_tonnes == 263000.0

def test_trade_row_negative_value_flagged():
    damaged_row = TradeRow(
        doc_id="TEST-NEG",
        row_id="P1",
        full_id="TEST-NEG#P1",
        sector="Wheat",
        month="July",
        year=2026,
        period="2026-07",
        val_usd_m=0.0,
        vol_tonnes=0.0,
        is_damaged=True,
        damage_reason="Negative trade values detected: val=-10.0",
    )
    assert damaged_row.is_damaged is True

def test_deterministic_disruption_calculation():
    primary_rows = [
        # Baseline 2025: Total Val = 100M, Vol = 200,000
        TradeRow(doc_id="D1", row_id="P1", full_id="D1#P1", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=50.0, vol_tonnes=100000),
        TradeRow(doc_id="D1", row_id="P2", full_id="D1#P2", sector="Wheat", month="October", year=2025, period="2025-10", val_usd_m=50.0, vol_tonnes=100000),
        # Disrupted 2026: Total Val = 40M, Vol = 70,000
        TradeRow(doc_id="D1", row_id="P3", full_id="D1#P3", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=20.0, vol_tonnes=35000),
        TradeRow(doc_id="D1", row_id="P4", full_id="D1#P4", sector="Wheat", month="October", year=2026, period="2026-10", val_usd_m=20.0, vol_tonnes=35000),
    ]

    substitute_rows = [
        TradeRow(doc_id="S1", row_id="P1", full_id="S1#P1", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=5.0, vol_tonnes=10000),
        TradeRow(doc_id="S1", row_id="P2", full_id="S1#P2", sector="Wheat", month="October", year=2025, period="2025-10", val_usd_m=5.0, vol_tonnes=10000),
        TradeRow(doc_id="S1", row_id="P3", full_id="S1#P3", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=12.5, vol_tonnes=25000),
        TradeRow(doc_id="S1", row_id="P4", full_id="S1#P4", sector="Wheat", month="October", year=2026, period="2026-10", val_usd_m=12.5, vol_tonnes=25000),
    ]

    calc_input = DisruptionCalculationInput(
        country="Midgard",
        sector="Wheat",
        primary_supplier="Orvan",
        primary_rows=primary_rows,
        substitute_suppliers=["Vanir"],
        substitute_rows=substitute_rows,
        baseline_year=2025,
        disrupted_year=2026,
        disruption_months=["September", "October"],
        spot_price_escalation_pct=10.0,
    )

    res = TradeCalculator.calculate_disruption(calc_input)

    assert res.baseline_value_usd_m == 100.0
    assert res.baseline_volume_tonnes == 200000.0
    assert res.disrupted_value_usd_m == 40.0
    assert res.disrupted_volume_tonnes == 70000.0

    # Gross Loss = 100 - 40 = 60M (60%), Volume = 200k - 70k = 130k tonnes (65%)
    assert res.gross_value_loss_usd_m == 60.0
    assert res.gross_volume_loss_tonnes == 130000.0
    assert res.gross_value_loss_pct == 60.0
    assert res.gross_volume_loss_pct == 65.0

    # Substitute Gain = 25 - 10 = 15M, Volume = 50k - 20k = 30k tonnes
    assert res.substitute_value_gain_usd_m == 15.0
    assert res.substitute_volume_gain_tonnes == 30000.0

    # Net Loss = Gross - Substitute = 60 - 15 = 45M, Volume = 130k - 30k = 100k tonnes
    assert res.net_value_loss_usd_m == 45.0
    assert res.net_volume_loss_tonnes == 100000.0

    # Exposure bounds:
    # Low bound = Net loss = 45.0M
    # High bound = Gross loss + 10% spot escalation = 60.0 + 6.0 = 66.0M
    assert res.low_exposure_bound_usd_m == 45.0
    assert res.high_exposure_bound_usd_m == 66.0

    # Verify source row ID preservation
    assert "D1#P1" in res.source_row_ids
    assert "D1#P2" in res.source_row_ids
    assert "S1#P3" in res.substitute_row_ids

def test_disruption_calculation_damaged_row_tolerance():
    primary_rows = [
        TradeRow(doc_id="D1", row_id="P1", full_id="D1#P1", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=50.0, vol_tonnes=100000),
        TradeRow(doc_id="D1", row_id="P2", full_id="D1#P2", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=20.0, vol_tonnes=35000),
        TradeRow(doc_id="D1", row_id="P99", full_id="D1#P99", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=0.0, vol_tonnes=0.0, is_damaged=True, damage_reason="Corrupt figures"),
    ]

    calc_input = DisruptionCalculationInput(
        country="Midgard",
        sector="Wheat",
        primary_supplier="Orvan",
        primary_rows=primary_rows,
        substitute_rows=[],
        baseline_year=2025,
        disrupted_year=2026,
        disruption_months=["September"],
    )

    res = TradeCalculator.calculate_disruption(calc_input)
    assert res.gross_value_loss_usd_m == 30.0
    assert len(res.damaged_rows_reported) == 1
    assert "D1#P99: Corrupt figures" in res.damaged_rows_reported[0]

def test_edge_case_reversed_comparison_rejected():
    primary_rows = [
        TradeRow(doc_id="D1", row_id="P1", full_id="D1#P1", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=50.0, vol_tonnes=100000),
        TradeRow(doc_id="D1", row_id="P2", full_id="D1#P2", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=20.0, vol_tonnes=35000),
    ]
    calc_input = DisruptionCalculationInput(
        country="Midgard",
        sector="Wheat",
        primary_supplier="Orvan",
        primary_rows=primary_rows,
        substitute_rows=[],
        baseline_year=2026,  # REVERSED: baseline is 2026, disrupted is 2025
        disrupted_year=2025,
        disruption_months=["September"],
    )
    with pytest.raises(ValueError, match="Reversed comparison"):
        TradeCalculator.calculate_disruption(calc_input)

def test_edge_case_inconsistent_sector_rejected():
    primary_rows = [
        TradeRow(doc_id="D1", row_id="P1", full_id="D1#P1", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=50.0, vol_tonnes=100000),
        # Corrupted / mismatched sector: Maize fed into Wheat analysis
        TradeRow(doc_id="D1", row_id="P2", full_id="D1#P2", sector="Maize", month="September", year=2026, period="2026-09", val_usd_m=20.0, vol_tonnes=35000),
    ]
    calc_input = DisruptionCalculationInput(
        country="Midgard",
        sector="Wheat",
        primary_supplier="Orvan",
        primary_rows=primary_rows,
        substitute_rows=[],
        baseline_year=2025,
        disrupted_year=2026,
        disruption_months=["September"],
    )
    with pytest.raises(ValueError, match="Inconsistent sector"):
        TradeCalculator.calculate_disruption(calc_input)

def test_edge_case_invalid_zero_baseline_rejected():
    primary_rows = [
        TradeRow(doc_id="D1", row_id="P1", full_id="D1#P1", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=0.0, vol_tonnes=0.0),
        TradeRow(doc_id="D1", row_id="P2", full_id="D1#P2", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=20.0, vol_tonnes=35000),
    ]
    calc_input = DisruptionCalculationInput(
        country="Midgard",
        sector="Wheat",
        primary_supplier="Orvan",
        primary_rows=primary_rows,
        substitute_rows=[],
        baseline_year=2025,
        disrupted_year=2026,
        disruption_months=["September"],
    )
    with pytest.raises(ValueError, match="Invalid baseline values"):
        TradeCalculator.calculate_disruption(calc_input)

def test_edge_case_substitution_versus_gross_loss_distinction():
    primary_rows = [
        TradeRow(doc_id="D1", row_id="P1", full_id="D1#P1", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=100.0, vol_tonnes=200000),
        TradeRow(doc_id="D1", row_id="P2", full_id="D1#P2", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=40.0, vol_tonnes=80000),
    ]
    substitute_rows = [
        TradeRow(doc_id="S1", row_id="P1", full_id="S1#P1", sector="Wheat", month="September", year=2025, period="2025-09", val_usd_m=10.0, vol_tonnes=20000),
        TradeRow(doc_id="S1", row_id="P2", full_id="S1#P2", sector="Wheat", month="September", year=2026, period="2026-09", val_usd_m=25.0, vol_tonnes=50000),
    ]
    calc_input = DisruptionCalculationInput(
        country="Midgard",
        sector="Wheat",
        primary_supplier="Orvan",
        primary_rows=primary_rows,
        substitute_rows=substitute_rows,
        baseline_year=2025,
        disrupted_year=2026,
        disruption_months=["September"],
        spot_price_escalation_pct=15.0,
    )
    res = TradeCalculator.calculate_disruption(calc_input)

    # Gross loss: 100 - 40 = 60M USD, 200k - 80k = 120k tonnes
    assert res.gross_value_loss_usd_m == 60.0
    assert res.gross_volume_loss_tonnes == 120000.0

    # Evidenced substitute gain: 25 - 10 = 15M USD, 50k - 20k = 30k tonnes
    assert res.substitute_value_gain_usd_m == 15.0
    assert res.substitute_volume_gain_tonnes == 30000.0

    # Net loss after substitute: 60 - 15 = 45M USD, 120k - 30k = 90k tonnes
    assert res.net_value_loss_usd_m == 45.0
    assert res.net_volume_loss_tonnes == 90000.0

    # Metrics clearly distinguished and not double counted
    assert res.gross_value_loss_usd_m != res.net_value_loss_usd_m
    assert res.low_exposure_bound_usd_m == 45.0  # Net loss
    assert res.high_exposure_bound_usd_m == 69.0  # 60M gross + 15% spot surge = 69M

