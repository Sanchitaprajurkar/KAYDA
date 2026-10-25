import re
from typing import Any, Dict, List, Optional
from backend.schemas.thor_claim import (
    DisruptionCalculationInput,
    DisruptionCalculationResult,
    TradeRow,
)
from backend.services.runemark import ParsedDocument

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

class TradeCalculator:
    """
    Deterministic quantitative trade calculator.
    Keeps all financial and volume calculations strictly outside the LLM.
    Preserves row IDs for judicial auditability and validates input data integrity.
    """

    @classmethod
    def extract_trade_rows(cls, doc: ParsedDocument) -> List[TradeRow]:
        """
        Extracts validated TradeRow objects from a parsed document text or paragraphs.
        Supports both narrative trade note syntax ([P2] In July 2026...) and tabular formats.
        """
        rows: List[TradeRow] = []
        if doc.is_damaged:
            return rows

        text = doc.body_text or doc.full_text
        norm = re.sub(r"\s+", " ", text)
        effective_sector = doc.resolved_sector if doc.has_sector_mismatch else doc.sector

        trade_note_pattern = re.compile(
            r"\[(P\d+)\]\s+In\s+([A-Za-z]+)\s+(\d{4}),\s+the\s+value\s+was\s+USD\s+([\d\.]+)M\s+and\s+the\s+volume\s+was\s+([\d,]+)\s+tonnes",
            re.IGNORECASE,
        )

        for match in trade_note_pattern.finditer(norm):
            pid, month_name, year_str, val_str, vol_str = match.groups()
            row_id = pid
            full_id = f"{doc.doc_id}#{row_id}"

            try:
                val = float(val_str)
                vol = float(vol_str.replace(",", ""))
                year = int(year_str)
                month = month_name.capitalize()
                month_num = MONTH_MAP.get(month.lower(), 1)
                period = f"{year}-{month_num:02d}"

                if val < 0 or vol < 0:
                    rows.append(TradeRow(
                        doc_id=doc.doc_id,
                        row_id=row_id,
                        full_id=full_id,
                        sector=effective_sector,
                        month=month,
                        year=year,
                        period=period,
                        val_usd_m=0.0,
                        vol_tonnes=0.0,
                        is_damaged=True,
                        damage_reason=f"Negative trade values detected: val={val}, vol={vol}",
                    ))
                    continue

                rows.append(TradeRow(
                    doc_id=doc.doc_id,
                    row_id=row_id,
                    full_id=full_id,
                    sector=effective_sector,
                    month=month,
                    year=year,
                    period=period,
                    val_usd_m=val,
                    vol_tonnes=vol,
                    is_damaged=False,
                ))
            except ValueError as e:
                rows.append(TradeRow(
                    doc_id=doc.doc_id,
                    row_id=row_id,
                    full_id=full_id,
                    sector=effective_sector,
                    month=month_name,
                    year=0,
                    period="INVALID",
                    val_usd_m=0.0,
                    vol_tonnes=0.0,
                    is_damaged=True,
                    damage_reason=f"Failed to parse numerical figures: {str(e)}",
                ))

        if not rows:
            rows.extend(cls._extract_tabular_rows(doc))

        return rows

    @classmethod
    def _extract_tabular_rows(cls, doc: ParsedDocument) -> List[TradeRow]:
        rows: List[TradeRow] = []
        lines = (doc.body_text or doc.full_text).splitlines()
        for idx, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or "value" in line.lower() and "volume" in line.lower():
                continue

            parts = [p.strip() for p in re.split(r"[,|\t]+", line)]
            if len(parts) >= 4:
                try:
                    row_id = parts[0]
                    month_part = parts[1]
                    val = float(re.sub(r"[^\d\.]", "", parts[2]))
                    vol = float(re.sub(r"[^\d\.]", "", parts[3]))

                    year = 2026
                    month = month_part
                    ym = re.search(r"(\d{4})", month_part)
                    if ym:
                        year = int(ym.group(1))

                    rows.append(TradeRow(
                        doc_id=doc.doc_id,
                        row_id=f"row-{row_id}",
                        full_id=f"{doc.doc_id}#row-{row_id}",
                        sector=doc.sector,
                        month=month,
                        year=year,
                        period=f"{year}-00",
                        val_usd_m=val,
                        vol_tonnes=vol,
                        is_damaged=False,
                    ))
                except Exception as e:
                    rows.append(TradeRow(
                        doc_id=doc.doc_id,
                        row_id=f"row-{idx}",
                        full_id=f"{doc.doc_id}#row-{idx}",
                        sector=doc.sector,
                        month="UNKNOWN",
                        year=0,
                        period="INVALID",
                        val_usd_m=0.0,
                        vol_tonnes=0.0,
                        is_damaged=True,
                        damage_reason=f"Corrupted table row: {line} ({str(e)})",
                    ))
        return rows

    @classmethod
    def calculate_disruption(cls, inp: DisruptionCalculationInput) -> DisruptionCalculationResult:
        damaged_rows_reported: List[str] = []
        source_row_ids: List[str] = []
        substitute_row_ids: List[str] = []
        calc_notes: List[str] = []

        target_months = [m.lower() for m in inp.disruption_months]

        # 0. Structural comparison validations
        if inp.baseline_year >= inp.disrupted_year:
            raise ValueError(
                f"Reversed comparison or invalid baseline year ({inp.baseline_year}) >= "
                f"disrupted year ({inp.disrupted_year}). Baseline must precede disruption period."
            )

        # Validate sector consistency across input rows
        for r in inp.primary_rows:
            if not r.is_damaged and r.sector.lower() != inp.sector.lower() and r.sector.lower() != "general":
                raise ValueError(
                    f"Inconsistent sector in trade row {r.full_id}: expected {inp.sector}, got {r.sector}."
                )

        # 1. Filter and validate primary supplier rows
        baseline_primary = [
            r for r in inp.primary_rows
            if not r.is_damaged and r.year == inp.baseline_year and r.month.lower() in target_months
        ]
        disrupted_primary = [
            r for r in inp.primary_rows
            if not r.is_damaged and r.year == inp.disrupted_year and r.month.lower() in target_months
        ]

        for r in inp.primary_rows + inp.substitute_rows:
            if r.is_damaged:
                damaged_rows_reported.append(f"{r.full_id}: {r.damage_reason}")

        source_row_ids = [r.full_id for r in baseline_primary + disrupted_primary]

        if not baseline_primary:
            raise ValueError(
                f"Missing baseline ({inp.baseline_year}) trade rows for {inp.country} {inp.sector} "
                f"across target months {inp.disruption_months}."
            )
        if not disrupted_primary:
            raise ValueError(
                f"Missing disrupted period ({inp.disrupted_year}) trade rows for {inp.country} {inp.sector} "
                f"across target months {inp.disruption_months}."
            )

        baseline_val = sum(r.val_usd_m for r in baseline_primary)
        baseline_vol = sum(r.vol_tonnes for r in baseline_primary)

        if baseline_val <= 0 or baseline_vol <= 0:
            raise ValueError(
                f"Invalid baseline values: baseline value ({baseline_val}) and volume ({baseline_vol}) "
                f"must be strictly positive."
            )

        disrupted_val = sum(r.val_usd_m for r in disrupted_primary)
        disrupted_vol = sum(r.vol_tonnes for r in disrupted_primary)

        # Gross Supplier Disruption
        gross_val_loss = max(0.0, baseline_val - disrupted_val)
        gross_vol_loss = max(0.0, baseline_vol - disrupted_vol)

        gross_val_pct = (gross_val_loss / baseline_val * 100.0) if baseline_val > 0 else 0.0
        gross_vol_pct = (gross_vol_loss / baseline_vol * 100.0) if baseline_vol > 0 else 0.0


        calc_notes.append(
            f"Gross supplier loss ({inp.primary_supplier}): USD {gross_val_loss:.2f}M "
            f"({gross_val_pct:.1f}%) and {gross_vol_loss:,.0f} tonnes ({gross_vol_pct:.1f}%)."
        )

        # 2. Evaluate Evidenced Substitute Supply
        sub_val_gain = 0.0
        sub_vol_gain = 0.0

        if inp.substitute_rows:
            baseline_sub = [
                r for r in inp.substitute_rows
                if not r.is_damaged and r.year == inp.baseline_year and r.month.lower() in target_months
            ]
            disrupted_sub = [
                r for r in inp.substitute_rows
                if not r.is_damaged and r.year == inp.disrupted_year and r.month.lower() in target_months
            ]

            substitute_row_ids = [r.full_id for r in baseline_sub + disrupted_sub]

            base_sub_val = sum(r.val_usd_m for r in baseline_sub)
            base_sub_vol = sum(r.vol_tonnes for r in baseline_sub)

            dis_sub_val = sum(r.val_usd_m for r in disrupted_sub)
            dis_sub_vol = sum(r.vol_tonnes for r in disrupted_sub)

            sub_val_gain = max(0.0, dis_sub_val - base_sub_val)
            sub_vol_gain = max(0.0, dis_sub_vol - base_sub_vol)

            calc_notes.append(
                f"Evidenced substitute gain from {', '.join(inp.substitute_suppliers) or 'alternate suppliers'}: "
                f"+USD {sub_val_gain:.2f}M and +{sub_vol_gain:,.0f} tonnes."
            )
        else:
            calc_notes.append("No verified substitute trade rows provided; substitution assumed zero.")

        # 3. Net Disruption Calculation
        net_val_loss = max(0.0, gross_val_loss - sub_val_gain)
        net_vol_loss = max(0.0, gross_vol_loss - sub_vol_gain)

        net_val_pct = (net_val_loss / baseline_val * 100.0) if baseline_val > 0 else 0.0
        net_vol_pct = (net_vol_loss / baseline_vol * 100.0) if baseline_vol > 0 else 0.0


        calc_notes.append(
            f"Net disruption after substitute absorption: USD {net_val_loss:.2f}M "
            f"({net_val_pct:.1f}%) and {net_vol_loss:,.0f} tonnes ({net_vol_pct:.1f}%)."
        )

        low_bound = round(net_val_loss, 2)
        price_escalation_usd_m = gross_val_loss * (inp.spot_price_escalation_pct / 100.0)
        high_bound = round(gross_val_loss + price_escalation_usd_m, 2)

        if inp.spot_price_escalation_pct > 0:
            calc_notes.append(
                f"High-exposure bound incorporates {inp.spot_price_escalation_pct:.1f}% forward/spot "
                f"risk premium (+USD {price_escalation_usd_m:.2f}M)."
            )

        return DisruptionCalculationResult(
            country=inp.country,
            sector=inp.sector,
            baseline_value_usd_m=round(baseline_val, 2),
            baseline_volume_tonnes=round(baseline_vol, 2),
            disrupted_value_usd_m=round(disrupted_val, 2),
            disrupted_volume_tonnes=round(disrupted_vol, 2),
            gross_value_loss_usd_m=round(gross_val_loss, 2),
            gross_volume_loss_tonnes=round(gross_vol_loss, 2),
            gross_value_loss_pct=round(gross_val_pct, 2),
            gross_volume_loss_pct=round(gross_vol_pct, 2),
            substitute_value_gain_usd_m=round(sub_val_gain, 2),
            substitute_volume_gain_tonnes=round(sub_vol_gain, 2),
            net_value_loss_usd_m=round(net_val_loss, 2),
            net_volume_loss_tonnes=round(net_vol_loss, 2),
            net_value_loss_pct=round(net_val_pct, 2),
            net_volume_loss_pct=round(net_vol_pct, 2),
            high_exposure_bound_usd_m=high_bound,
            low_exposure_bound_usd_m=low_bound,
            source_row_ids=source_row_ids,
            substitute_row_ids=substitute_row_ids,
            damaged_rows_reported=damaged_rows_reported,
            calculation_notes=calc_notes,
        )
