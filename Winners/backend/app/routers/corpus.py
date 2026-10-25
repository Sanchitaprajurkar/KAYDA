from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.ingestion.corpus import corpus
from app.config import settings

router = APIRouter(prefix="/corpus", tags=["Runemark Corpus"])

@router.get("/feed")
async def get_feed(
    as_of_date: Optional[str] = settings.DEFAULT_AS_OF_DATE,
    limit: int = Query(default=25, ge=1, le=100)
):
    """
    FR7.1: Returns chronological news and notice feed up to the specified as-of date.
    Strictly filters out any document published after as_of_date (clock enforcement).
    """
    corpus.load_corpus()
    all_docs = list(corpus.documents.values())

    # Filter by publication date
    valid_docs = [
        d for d in all_docs
        if d.metadata.PUB_DATE <= (as_of_date or settings.DEFAULT_AS_OF_DATE)
    ]

    # Sort reverse chronologically
    valid_docs.sort(key=lambda d: (d.metadata.PUB_DATE, d.metadata.PUB_TIME), reverse=True)

    items = []
    for d in valid_docs[:limit]:
        items.append({
            "doc_id": d.metadata.DOC_ID,
            "title": d.metadata.TITLE,
            "source_name": d.metadata.SOURCE_NAME,
            "source_type": d.metadata.SOURCE_TYPE,
            "reliability": d.metadata.RELIABILITY,
            "pub_date": d.metadata.PUB_DATE,
            "pub_time": d.metadata.PUB_TIME,
            "country": d.metadata.COUNTRY,
            "sector": d.metadata.SECTOR,
            "event_id": d.metadata.EVENT_ID,
            "snippet": d.paragraphs[0] if d.paragraphs else d.content[:180]
        })

    return {
        "as_of_date": as_of_date,
        "total_available": len(valid_docs),
        "feed": items
    }

@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """
    FR7.4: Click-through endpoint returning raw document text, metadata, and paragraphs.
    """
    corpus.load_corpus()
    doc = corpus.get_document(doc_id.upper())
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found in Runemark manifest.")

    return {
        "doc_id": doc.metadata.DOC_ID,
        "title": doc.metadata.TITLE,
        "source_name": doc.metadata.SOURCE_NAME,
        "source_type": doc.metadata.SOURCE_TYPE,
        "reliability": doc.metadata.RELIABILITY,
        "pub_date": doc.metadata.PUB_DATE,
        "pub_time": doc.metadata.PUB_TIME,
        "country": doc.metadata.COUNTRY,
        "sector": doc.metadata.SECTOR,
        "language": doc.metadata.LANGUAGE,
        "format": doc.metadata.FORMAT,
        "word_count": doc.word_count,
        "content": doc.content,
        "paragraphs": doc.paragraphs,
        "is_retracted": doc.is_retracted,
        "has_prompt_injection": doc.has_injection_attempt
    }

@router.get("/search")
async def search_corpus(
    q: str = Query(..., description="Query terms"),
    as_of_date: Optional[str] = settings.DEFAULT_AS_OF_DATE,
    country: Optional[str] = None,
    sector: Optional[str] = None,
    max_tier: Optional[int] = None,
    limit: int = 10
):
    results = corpus.search(
        query=q,
        as_of_date=as_of_date,
        country=country,
        sector=sector,
        max_tier=max_tier,
        limit=limit
    )
    return {
        "query": q,
        "as_of_date": as_of_date,
        "count": len(results),
        "results": [r.to_dict() for r in results]
    }

@router.get("/verification")
async def verify_corpus():
    """
    Returns SHA-256 integrity verification results for all Runemark documents.
    """
    return corpus.verify_hashes()
