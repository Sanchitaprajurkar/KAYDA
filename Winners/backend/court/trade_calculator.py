"""Deterministic trade-disruption calculator. No LLM: every number comes from the ingested rows.

Substitute gain is the NET increase in substitute supply (disrupted year minus baseline year for
the same months), not the raw disrupted-year total, so pre-existing flows don't inflate mitigation.

Result fields
─────────────
baseline_value_usd_m          Primary supply value in disruption months of baseline year.
baseline_volume_tonnes        Same, in volume.
disrupted_value_usd_m         Primary supply value in disruption months of disrupted year.
disrupted_volume_tonnes       Same, in volume.
gross_value_loss_usd_m        baseline − disrupted (floored at 0).
gross_volume_loss_tonnes      Same, in volume.
gross_value_loss_pct          gross / baseline × 100.
gross_volume_loss_pct         gross_vol / baseline_vol × 100.
substitute_value_gain_usd_m   Net substitute increase (disrupted_sub − baseline_sub, floored at 0).
substitute_volume_gain_tonnes Same, in volume.
net_value_loss_usd_m          gross − substitute gain (floored at 0).
net_volume_loss_tonnes        Same, in volume.
net_value_loss_pct            net / baseline × 100.
low_exposure_bound_usd_m      = net_value_loss_usd_m (best-case after substitution).
high_exposure_bound_usd_m     gross × (1 + spot_price_escalation_pct / 100) — worst case: full
                               primary shortfall persists AND a spot premium is paid.
"""

import re
from typing import List, Optional

from pydantic import BaseModel, Field


class TradeRow(BaseModel):
    doc_id: str
    row_id: str
    full_id: str
    country_from: str = ""
    country_to: str = ""
    sector: str = ""
    month: str
    year: int
    period: str
    val_usd_m: float = 0.0
    vol_tonnes: float = 0.0
    is_damaged: bool = False
    damage_reason: Optional[str] = None


class DisruptionCalculationInput(BaseModel):
    country: str
    sector: str
    primary_supplier: str
    primary_rows: List[TradeRow] = Field(default_factory=list)
    substitute_suppliers: List[str] = Field(default_factory=list)
    substitute_rows: List[TradeRow] = Field(default_factory=list)
    baseline_year: int
    disrupted_year: int
    disruption_months: List[str] = Field(default_factory=list)
    spot_price_escalation_pct: float = 0.0


class DisruptionResult(BaseModel):
    baseline_value_usd_m: float
    baseline_volume_tonnes: float = 0.0
    disrupted_value_usd_m: float = 0.0
    disrupted_volume_tonnes: float = 0.0
    gross_value_loss_usd_m: float
    gross_volume_loss_tonnes: float = 0.0
    gross_value_loss_pct: float
    gross_volume_loss_pct: float = 0.0
    substitute_value_gain_usd_m: float
    substitute_volume_gain_tonnes: float = 0.0
    net_value_loss_usd_m: float
    net_volume_loss_tonnes: float = 0.0
    net_value_loss_pct: float
    low_exposure_bound_usd_m: float = 0.0
    high_exposure_bound_usd_m: float
    source_row_ids: List[str] = Field(default_factory=list)
    substitute_row_ids: List[str] = Field(default_factory=list)
    damaged_rows_reported: List[str] = Field(default_factory=list)


# Alias used by older test files
DisruptionCalculationResult = DisruptionResult


_MONTH_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+(\d{4})\b", re.IGNORECASE)
_VAL_RE = re.compile(r"USD\s+([\d,]+(?:\.\d+)?)\s*M", re.IGNORECASE)
_VOL_RE = re.compile(r"([\d,]+(?:\.\d+)?)\s*(?:thousand\s+)?tonnes", re.IGNORECASE)


class TradeCalculator:

    @classmethod
    def extract_trade_rows(cls, doc) -> List[TradeRow]:
        """Parse trade rows from narrative paragraph text in a ParsedDocument."""
        rows: List[TradeRow] = []
        body = getattr(doc, "body_text", "") or ""
        for line in body.splitlines():
            line = line.strip()
            if not line:
                continue
            row_id_m = re.match(r"^\[([A-Z]\d+)\]", line)
            row_id = row_id_m.group(1) if row_id_m else "P0"
            month_m = _MONTH_RE.search(line)
            if not month_m:
                continue
            month, year = month_m.group(1).capitalize(), int(month_m.group(2))
            val_m = _VAL_RE.search(line)
            vol_m = _VOL_RE.search(line)
            val = float(val_m.group(1).replace(",", "")) if val_m else 0.0
            vol = float(vol_m.group(1).replace(",", "")) if vol_m else 0.0
            full_id = f"{doc.doc_id}#{row_id}"
            period = f"{year}-{list(['January','February','March','April','May','June','July','August','September','October','November','December']).index(month)+1:02d}"
            rows.append(TradeRow(
                doc_id=doc.doc_id, row_id=row_id, full_id=full_id,
                sector=getattr(doc, "sector", ""), month=month, year=year, period=period,
                val_usd_m=val, vol_tonnes=vol,
                is_damaged=(val < 0 or vol < 0),
                damage_reason=f"Negative trade values detected: val={val}" if val < 0 else None,
            ))
        return rows

    @classmethod
    def calculate_disruption(cls, inp: DisruptionCalculationInput) -> DisruptionResult:
        # Validation
        if inp.baseline_year >= inp.disrupted_year:
            raise ValueError(
                f"Reversed comparison: baseline_year ({inp.baseline_year}) must be < "
                f"disrupted_year ({inp.disrupted_year})")

        all_rows = inp.primary_rows + inp.substitute_rows
        sectors = {r.sector for r in all_rows if r.sector}
        if len(sectors) > 1:
            raise ValueError(
                f"Inconsistent sector: rows contain {sectors}, expected a single sector")

        months = set(inp.disruption_months)

        def _valid(rows, year):
            return [r for r in rows if not r.is_damaged and r.year == year and r.month in months]

        p_base = _valid(inp.primary_rows, inp.baseline_year)
        p_dis = _valid(inp.primary_rows, inp.disrupted_year)
        s_base = _valid(inp.substitute_rows, inp.baseline_year)
        s_dis = _valid(inp.substitute_rows, inp.disrupted_year)

        baseline_val = sum(r.val_usd_m for r in p_base)
        baseline_vol = sum(r.vol_tonnes for r in p_base)

        if baseline_val <= 0 and baseline_vol <= 0 and p_base:
            raise ValueError(
                f"Invalid baseline values: all primary baseline rows for {inp.baseline_year} "
                f"have zero or negative values")

        disrupted_val = sum(r.val_usd_m for r in p_dis)
        disrupted_vol = sum(r.vol_tonnes for r in p_dis)

        s_base_val = sum(r.val_usd_m for r in s_base)
        s_base_vol = sum(r.vol_tonnes for r in s_base)
        s_dis_val = sum(r.val_usd_m for r in s_dis)
        s_dis_vol = sum(r.vol_tonnes for r in s_dis)

        # Net incremental substitute gain (only new supply counts as mitigation)
        sub_gain_val = max(0.0, s_dis_val - s_base_val)
        sub_gain_vol = max(0.0, s_dis_vol - s_base_vol)

        gross_loss_val = max(0.0, baseline_val - disrupted_val)
        gross_loss_vol = max(0.0, baseline_vol - disrupted_vol)
        net_loss_val = max(0.0, gross_loss_val - sub_gain_val)
        net_loss_vol = max(0.0, gross_loss_vol - sub_gain_vol)

        # High bound: full gross loss still materialises AND a spot premium is paid on it
        high_bound = gross_loss_val * (1.0 + inp.spot_price_escalation_pct / 100.0)

        def _ids(rows):
            return [r.full_id for r in rows]

        damaged = [
            f"{r.full_id}: {r.damage_reason or 'damaged'}"
            for r in inp.primary_rows + inp.substitute_rows if r.is_damaged
        ]

        def _pct(num, denom):
            return round(num / denom * 100, 2) if denom else 0.0

        return DisruptionResult(
            baseline_value_usd_m=round(baseline_val, 2),
            baseline_volume_tonnes=round(baseline_vol, 2),
            disrupted_value_usd_m=round(disrupted_val, 2),
            disrupted_volume_tonnes=round(disrupted_vol, 2),
            gross_value_loss_usd_m=round(gross_loss_val, 2),
            gross_volume_loss_tonnes=round(gross_loss_vol, 2),
            gross_value_loss_pct=_pct(gross_loss_val, baseline_val),
            gross_volume_loss_pct=_pct(gross_loss_vol, baseline_vol),
            substitute_value_gain_usd_m=round(sub_gain_val, 2),
            substitute_volume_gain_tonnes=round(sub_gain_vol, 2),
            net_value_loss_usd_m=round(net_loss_val, 2),
            net_volume_loss_tonnes=round(net_loss_vol, 2),
            net_value_loss_pct=_pct(net_loss_val, baseline_val),
            low_exposure_bound_usd_m=round(net_loss_val, 2),
            high_exposure_bound_usd_m=round(high_bound, 2),
            source_row_ids=_ids(p_base) + _ids(p_dis),
            substitute_row_ids=_ids(s_dis),
            damaged_rows_reported=damaged,
        )
