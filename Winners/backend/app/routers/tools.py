from typing import Optional, List, Dict, Any, Union
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from tools.search import search, clear_query_ledger, get_query_ledger
from tools.reader import read_doc
from tools.trade import get_trade_series
from tools.calculator import compute_change

router = APIRouter(prefix="/tools", tags=["Deterministic Courtroom Tools"])

class SearchRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict)
    k: int = Field(default=5, ge=1, le=50)
    allow_duplicate: bool = False

class ReadDocRequest(BaseModel):
    doc_id: str
    paras: Optional[List[Union[int, str]]] = None

class TradeSeriesRequest(BaseModel):
    origin: str
    dest: str
    sector: str
    as_of_date: Optional[str] = None

class ComputeChangeRequest(BaseModel):
    rows_a: List[Union[Dict[str, Any], float, int]]
    rows_b: List[Union[Dict[str, Any], float, int]]
    mode: str = Field(default="percentage", description="'percentage', 'volume_diff', 'value_diff', 'ratio', or 'summary'")
    net_of: float = Field(default=0.0, description="Mitigation volume or value offset")

@router.post("/search")
async def tool_search(req: SearchRequest):
    """
    Hybrid RRF search with strict pub_date <= as_of_date clock rule
    and duplicate query rejection ledger.
    """
    res = search(
        query=req.query,
        filters=req.filters,
        k=req.k,
        allow_duplicate=req.allow_duplicate
    )
    return res

@router.post("/read_doc")
async def tool_read_doc(req: ReadDocRequest):
    """
    Fetches targeted paragraphs or full text of a specific Runemark document.
    """
    res = read_doc(id=req.doc_id, paras=req.paras)
    if res["status"] == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@router.post("/get_trade_series")
async def tool_get_trade_series(req: TradeSeriesRequest):
    """
    Retrieves validated trade series for a specific route (origin -> dest) and sector.
    """
    res = get_trade_series(
        origin=req.origin,
        dest=req.dest,
        sector=req.sector,
        as_of_date=req.as_of_date
    )
    return res

@router.post("/compute_change")
async def tool_compute_change(req: ComputeChangeRequest):
    """
    Deterministic math calculator for percentage and volume/value changes.
    """
    res = compute_change(
        rows_a=req.rows_a,
        rows_b=req.rows_b,
        mode=req.mode,
        net_of=req.net_of
    )
    if res["status"] == "ERROR":
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.get("/ledger")
async def tool_query_ledger():
    """
    Returns the current state of the duplicate query rejection ledger (NFR5).
    """
    return {
        "status": "SUCCESS",
        "total_queries_recorded": len(get_query_ledger()),
        "ledger": get_query_ledger()
    }

@router.post("/ledger/clear")
async def tool_clear_ledger():
    clear_query_ledger()
    return {"status": "SUCCESS", "message": "Duplicate query rejection ledger cleared."}
