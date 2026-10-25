from typing import List, Dict, Union, Any, Optional

def extract_metric_total(rows: List[Union[Dict[str, Any], float, int]], key: str = "volume_tonnes") -> float:
    """Helper to sum values or volumes from row dictionaries or raw numbers."""
    total = 0.0
    for r in rows:
        if isinstance(r, (int, float)):
            total += float(r)
        elif isinstance(r, dict):
            val = r.get(key, 0.0)
            try:
                total += float(val)
            except (ValueError, TypeError):
                continue
    return total

def compute_change(
    rows_a: List[Union[Dict[str, Any], float, int]],
    rows_b: List[Union[Dict[str, Any], float, int]],
    mode: str = "percentage",
    net_of: float = 0.0
) -> Dict[str, Any]:
    """
    Deterministic Python math calculator for percentage, volume, and value trade changes.
    Eliminates LLM arithmetic hallucinations.
    
    Args:
        rows_a: Baseline period rows (e.g. pre-disruption months or previous year)
        rows_b: Comparison period rows (e.g. post-disruption months)
        mode: Calculation mode:
              - 'percentage': Volume % change: ((B + net_of) - A) / A * 100
              - 'volume_diff': Net volume delta (tonnes)
              - 'value_diff': Net value delta (USD Millions)
              - 'ratio': (B + net_of) / A
              - 'summary' or 'all': Full comprehensive calculation breakdown
        net_of: Substituted / mitigated volume or value to offset against exposure
        
    Returns:
        Structured deterministic calculation results with baseline, post-disruption,
        mitigation offset, and percentage changes.
    """
    if not rows_a:
        return {
            "status": "ERROR",
            "error": "rows_a (baseline) cannot be empty for change computation."
        }
    if not rows_b:
        return {
            "status": "ERROR",
            "error": "rows_b (comparison) cannot be empty for change computation."
        }

    # Aggregate volumes
    vol_a = extract_metric_total(rows_a, "volume_tonnes")
    vol_b = extract_metric_total(rows_b, "volume_tonnes")
    net_vol_b = vol_b + net_of

    # Aggregate values (USD M)
    val_a = extract_metric_total(rows_a, "value_usd_m")
    val_b = extract_metric_total(rows_b, "value_usd_m")

    # Volume calculations
    vol_diff = net_vol_b - vol_a
    vol_pct = (vol_diff / vol_a * 100.0) if vol_a > 0 else 0.0
    vol_ratio = (net_vol_b / vol_a) if vol_a > 0 else 0.0

    # Value calculations
    val_diff = val_b - val_a
    val_pct = (val_diff / val_a * 100.0) if val_a > 0 else 0.0

    # Average monthly rates
    avg_vol_a = vol_a / len(rows_a) if len(rows_a) > 0 else 0.0
    avg_vol_b = vol_b / len(rows_b) if len(rows_b) > 0 else 0.0
    monthly_vol_pct = ((avg_vol_b - avg_vol_a) / avg_vol_a * 100.0) if avg_vol_a > 0 else 0.0

    res = {
        "status": "SUCCESS",
        "baseline_count": len(rows_a),
        "comparison_count": len(rows_b),
        "net_of_applied": net_of,
        "volume": {
            "baseline_total_tonnes": round(vol_a, 2),
            "comparison_total_tonnes": round(vol_b, 2),
            "net_comparison_tonnes": round(net_vol_b, 2),
            "delta_tonnes": round(vol_diff, 2),
            "percentage_change": round(vol_pct, 2),
            "ratio": round(vol_ratio, 4),
            "monthly_avg_baseline": round(avg_vol_a, 2),
            "monthly_avg_comparison": round(avg_vol_b, 2),
            "monthly_avg_percentage_change": round(monthly_vol_pct, 2)
        },
        "value": {
            "baseline_total_usd_m": round(val_a, 2),
            "comparison_total_usd_m": round(val_b, 2),
            "delta_usd_m": round(val_diff, 2),
            "percentage_change": round(val_pct, 2)
        }
    }

    if mode == "percentage":
        return {
            "status": "SUCCESS",
            "metric": "volume_percentage_change",
            "percentage_change": round(vol_pct, 2),
            "baseline_tonnes": round(vol_a, 2),
            "net_comparison_tonnes": round(net_vol_b, 2),
            "net_of_mitigation": net_of
        }
    elif mode == "volume_diff":
        return {
            "status": "SUCCESS",
            "metric": "volume_tonnes_delta",
            "delta_tonnes": round(vol_diff, 2),
            "baseline_tonnes": round(vol_a, 2),
            "net_comparison_tonnes": round(net_vol_b, 2)
        }
    elif mode == "value_diff":
        return {
            "status": "SUCCESS",
            "metric": "value_usd_m_delta",
            "delta_usd_m": round(val_diff, 2),
            "baseline_usd_m": round(val_a, 2),
            "comparison_usd_m": round(val_b, 2)
        }
    elif mode == "ratio":
        return {
            "status": "SUCCESS",
            "metric": "volume_ratio",
            "ratio": round(vol_ratio, 4)
        }
    else:
        return res
