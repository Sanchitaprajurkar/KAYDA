import re
from typing import List, Dict, Optional, Any
from app.ingestion.corpus import corpus
from app.config import settings

MONTH_ORDER = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12"
}

TRADE_ROW_REGEX = re.compile(
    r"(?:\[(P\d+)\]\s*)?In\s+([A-Za-z]+)\s+(\d{4}),\s+(?:the\s+)?value\s+was\s+USD\s+([\d\.]+)M\s+and\s+(?:the\s+)?volume\s+was\s+([\d,]+)\s+tonnes",
    re.IGNORECASE
)

def get_trade_series(
    origin: str,
    dest: str,
    sector: str,
    as_of_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves validated trade series for a specific route (origin -> dest) and commodity sector.
    
    Args:
        origin: Source country, e.g. 'Orvan', 'Vanir', 'Ravik'
        dest: Destination country, e.g. 'Midgard', 'Tolan', 'Asgard'
        sector: Commodity sector, e.g. 'Wheat', 'Maize'
        as_of_date: Clock date cutoff YYYY-MM-DD
        
    Returns:
        Structured monthly trade series with values (USD M), volumes (tonnes),
        source document citations, and validation status.
    """
    corpus.load_corpus()
    cutoff_date = as_of_date or settings.DEFAULT_AS_OF_DATE

    orig_clean = origin.strip().lower()
    dest_clean = dest.strip().lower()
    sect_clean = sector.strip().lower()

    matched_series = []
    source_docs = set()

    for doc_id, doc in corpus.documents.items():
        meta = doc.metadata

        # Clock enforcement
        if cutoff_date and meta.PUB_DATE > cutoff_date:
            continue

        title_lower = meta.TITLE.lower()
        content_lower = doc.content.lower()

        # Check if document represents this trade route
        route_pattern_1 = f"{orig_clean} to {dest_clean}"
        route_pattern_2 = f"route: {orig_clean} to {dest_clean}"

        is_route_match = (route_pattern_1 in title_lower) or (route_pattern_2 in content_lower)
        is_sector_match = (sect_clean in title_lower) or (sect_clean in meta.SECTOR.lower()) or (sect_clean in content_lower)

        if is_route_match and is_sector_match:
            source_docs.add(doc_id)

            # Parse lines and paragraphs
            for i, p in enumerate(doc.paragraphs):
                para_id = f"P{i+1}"
                matches = TRADE_ROW_REGEX.findall(p)
                for m in matches:
                    p_label = m[0] or para_id
                    month_name = m[1].strip()
                    year_str = m[2].strip()
                    val_str = m[3].strip()
                    vol_str = m[4].replace(",", "").strip()

                    try:
                        val_num = float(val_str)
                        vol_num = float(vol_str)
                    except ValueError:
                        continue

                    month_num = MONTH_ORDER.get(month_name.lower(), "00")
                    period_key = f"{year_str}-{month_num}"

                    matched_series.append({
                        "period": period_key,
                        "year": int(year_str),
                        "month": month_name.capitalize(),
                        "value_usd_m": val_num,
                        "volume_tonnes": vol_num,
                        "doc_id": doc_id,
                        "para_id": p_label,
                        "citation": f"{doc_id} {p_label}"
                    })

    # Deduplicate and sort chronologically
    unique_series = {}
    for row in matched_series:
        unique_series[row["period"]] = row

    sorted_series = sorted(unique_series.values(), key=lambda r: r["period"])

    if not sorted_series:
        return {
            "status": "NO_SERIES_FOUND",
            "route": f"{origin.capitalize()} -> {dest.capitalize()}",
            "sector": sector.capitalize(),
            "as_of_date": cutoff_date,
            "count": 0,
            "data": [],
            "source_documents": []
        }

    # Summary statistics
    total_vol = sum(r["volume_tonnes"] for r in sorted_series)
    total_val = sum(r["value_usd_m"] for r in sorted_series)

    return {
        "status": "SUCCESS",
        "route": f"{origin.capitalize()} -> {dest.capitalize()}",
        "sector": sector.capitalize(),
        "as_of_date": cutoff_date,
        "count": len(sorted_series),
        "source_documents": sorted(list(source_docs)),
        "summary": {
            "earliest_period": sorted_series[0]["period"],
            "latest_period": sorted_series[-1]["period"],
            "total_volume_tonnes": round(total_vol, 2),
            "total_value_usd_m": round(total_val, 2)
        },
        "data": sorted_series
    }
