import re
from typing import Dict, List, Optional, Any
from app.ingestion.corpus import corpus
from app.config import settings

# Global Duplicate Query Rejection Ledger (NFR5 enforcement)
QUERY_LEDGER: Dict[str, int] = {}

def clear_query_ledger():
    """Clears the duplicate query rejection ledger (e.g. for new trials)."""
    global QUERY_LEDGER
    QUERY_LEDGER.clear()

def get_query_ledger() -> Dict[str, int]:
    return dict(QUERY_LEDGER)

def compute_rrf_score(ranks: Dict[str, int], k_const: int = 60) -> float:
    """
    Computes Reciprocal Rank Fusion (RRF) score:
    RRF(d) = sum(1 / (k + rank_i(d)))
    """
    score = 0.0
    for method, rank in ranks.items():
        if rank > 0:
            score += 1.0 / (k_const + rank)
    return score

def search(
    query: str,
    filters: Optional[Dict[str, Any]] = None,
    k: int = 5,
    allow_duplicate: bool = False
) -> Dict[str, Any]:
    """
    Hybrid RRF Search over Runemark corpus with:
    - Strict pub_date <= as_of_date enforcement (Clock Rule NFR2 & FR1.3)
    - Duplicate query rejection ledger (NFR5: Do not send the same search query twice)
    - Reciprocal Rank Fusion over lexical matches, title relevance, and reliability tiers
    
    Args:
        query: Search keywords or question phrase
        filters: Optional metadata filters {
            'as_of_date': 'YYYY-MM-DD',
            'country': 'Midgard',
            'sector': 'Wheat',
            'max_tier': 1-4,
            'event_id': 'E5',
            'exclude_retracted': True
        }
        k: Maximum number of top results to return
        allow_duplicate: If True, bypasses ledger rejection
    """
    filters = filters or {}
    as_of_date = filters.get("as_of_date", settings.DEFAULT_AS_OF_DATE)
    country = filters.get("country")
    sector = filters.get("sector")
    max_tier = filters.get("max_tier")
    event_id = filters.get("event_id")
    exclude_retracted = filters.get("exclude_retracted", True)

    # 1. Query Normalization & Duplicate Rejection Ledger Check
    norm_query = re.sub(r"\s+", " ", query.lower().strip())
    ledger_key = f"{norm_query}|{as_of_date}|{country}|{sector}|{event_id}"

    if not allow_duplicate:
        if ledger_key in QUERY_LEDGER:
            QUERY_LEDGER[ledger_key] += 1
            return {
                "status": "REJECTED_DUPLICATE",
                "error": f"Duplicate query rejected by Court Procedure Ledger (NFR5): '{query}' was already submitted.",
                "query": query,
                "times_attempted": QUERY_LEDGER[ledger_key],
                "results": []
            }
        QUERY_LEDGER[ledger_key] = 1

    # Ensure corpus is loaded
    corpus.load_corpus()

    # Query terms for matching
    query_terms = [t for t in re.findall(r"\w+", norm_query) if len(t) > 2]
    if not query_terms:
        query_terms = [norm_query]

    # 2. Filter Candidate Documents & Score Lists
    candidates = []
    lexical_scores = {}
    title_scores = {}
    tier_scores = {}

    for doc_id, doc in corpus.documents.items():
        meta = doc.metadata

        # Clock enforcement: strictly reject documents published after as_of_date
        if as_of_date and meta.PUB_DATE > as_of_date:
            continue

        # Retraction filter
        if exclude_retracted and doc.is_retracted:
            continue

        # Country filter
        if country and country.lower() != "general":
            if meta.COUNTRY.lower() not in [country.lower(), "general"]:
                if country.lower() not in doc.content.lower():
                    continue

        # Sector filter
        if sector and sector.lower() != "general":
            if meta.SECTOR.lower() not in [sector.lower(), "general"]:
                if sector.lower() not in doc.content.lower():
                    continue

        # Max tier filter
        if max_tier and meta.RELIABILITY > max_tier:
            continue

        # Event ID filter
        if event_id and event_id != "ANY":
            if meta.EVENT_ID != event_id and meta.EVENT_ID != "NONE":
                continue

        content_lower = doc.content.lower()
        title_lower = meta.TITLE.lower()

        # Score 1: Lexical Term Frequency
        term_matches = sum(content_lower.count(t) for t in query_terms)
        lexical_scores[doc_id] = term_matches

        # Score 2: Title Exactness
        title_matches = sum(1 for t in query_terms if t in title_lower)
        title_scores[doc_id] = title_matches

        # Score 3: Reliability Tier (Tier 1 is highest rank)
        tier_scores[doc_id] = 5 - meta.RELIABILITY

        if term_matches > 0 or title_matches > 0:
            candidates.append(doc_id)

    if not candidates:
        return {
            "status": "SUCCESS",
            "query": query,
            "as_of_date": as_of_date,
            "count": 0,
            "results": []
        }

    # 3. Compute Ranks for RRF
    # Rank 1: Lexical rank
    sorted_by_lex = sorted(candidates, key=lambda x: lexical_scores[x], reverse=True)
    lex_ranks = {doc_id: i + 1 for i, doc_id in enumerate(sorted_by_lex)}

    # Rank 2: Title rank
    sorted_by_title = sorted(candidates, key=lambda x: title_scores[x], reverse=True)
    title_ranks = {doc_id: i + 1 for i, doc_id in enumerate(sorted_by_title)}

    # Rank 3: Reliability tier rank
    sorted_by_tier = sorted(candidates, key=lambda x: tier_scores[x], reverse=True)
    tier_ranks = {doc_id: i + 1 for i, doc_id in enumerate(sorted_by_tier)}

    # 4. Calculate Final RRF Scores
    rrf_results = []
    for doc_id in candidates:
        doc = corpus.documents[doc_id]
        rrf = compute_rrf_score({
            "lexical": lex_ranks.get(doc_id, 999),
            "title": title_ranks.get(doc_id, 999),
            "tier": tier_ranks.get(doc_id, 999)
        })

        # Extract relevant paragraph snippets
        matched_snippets = []
        for p in doc.paragraphs:
            p_lower = p.lower()
            if any(t in p_lower for t in query_terms):
                matched_snippets.append(p)
                if len(matched_snippets) >= 2:
                    break

        if not matched_snippets and doc.paragraphs:
            matched_snippets = [doc.paragraphs[0]]

        rrf_results.append({
            "doc_id": doc_id,
            "title": doc.metadata.TITLE,
            "source_name": doc.metadata.SOURCE_NAME,
            "reliability_tier": doc.metadata.RELIABILITY,
            "pub_date": doc.metadata.PUB_DATE,
            "country": doc.metadata.COUNTRY,
            "sector": doc.metadata.SECTOR,
            "rrf_score": round(rrf, 6),
            "matched_snippets": matched_snippets
        })

    # Sort descending by RRF score
    rrf_results.sort(key=lambda x: x["rrf_score"], reverse=True)
    top_results = rrf_results[:k]

    return {
        "status": "SUCCESS",
        "query": query,
        "as_of_date": as_of_date,
        "count": len(top_results),
        "results": top_results
    }
