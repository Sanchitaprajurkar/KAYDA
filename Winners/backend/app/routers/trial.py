import json
import asyncio
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.models.case import CaseFile
from app.court.procedure import CourtProcedure
from app.config import settings

router = APIRouter(prefix="/trial", tags=["Trial Courtroom"])

# In-memory storage for active and completed cases
ACTIVE_PROCEDURES: Dict[str, CourtProcedure] = {}
COMPLETED_CASES: Dict[str, CaseFile] = {}

class StartTrialRequest(BaseModel):
    query: str
    as_of_date: Optional[str] = settings.DEFAULT_AS_OF_DATE
    case_id: Optional[str] = None

class StartTrialResponse(BaseModel):
    case_id: str
    status: str
    as_of_date: str
    message: str

@router.post("/start", response_model=StartTrialResponse)
async def start_trial(req: StartTrialRequest):
    case_id = req.case_id or f"CASE-NR-{int(asyncio.get_event_loop().time() * 1000) % 100000:05d}"
    
    procedure = CourtProcedure(
        case_id=case_id,
        query=req.query,
        as_of_date=req.as_of_date or settings.DEFAULT_AS_OF_DATE
    )
    
    ACTIVE_PROCEDURES[case_id] = procedure
    
    return StartTrialResponse(
        case_id=case_id,
        status="INITIALIZED",
        as_of_date=procedure.as_of_date,
        message=f"Tribunal convened for case {case_id}. Connect to /api/trial/case/{case_id}/stream for live court telemetry."
    )

from app.db.repository import case_repo

@router.get("/case/{case_id}")
async def get_case(case_id: str):
    # 1. Check memory cache first
    if case_id in COMPLETED_CASES:
        return COMPLETED_CASES[case_id].model_dump()
    if case_id in ACTIVE_PROCEDURES:
        proc = ACTIVE_PROCEDURES[case_id]
        if proc.case_file:
            return proc.case_file.model_dump()
        return {"case_id": case_id, "status": "PENDING_EXECUTION"}

    # 2. Query Neon PostgreSQL database
    neon_case = case_repo.get_case(case_id)
    if neon_case:
        return neon_case

    raise HTTPException(status_code=404, detail=f"Case {case_id} not found in Neon database or active sessions.")

@router.get("/case/{case_id}/stream")
async def stream_trial(case_id: str):
    """
    Server-Sent Events (SSE) streaming endpoint for live real-time court procedure telemetry.
    """
    if case_id not in ACTIVE_PROCEDURES:
        # If case is already completed, return final event
        if case_id in COMPLETED_CASES:
            case = COMPLETED_CASES[case_id]
            async def single_event():
                yield f"data: {json.dumps({'step': 'CASE_CLOSED', 'case': case.model_dump()})}\n\n"
            return StreamingResponse(single_event(), media_type="text/event-stream")
        raise HTTPException(status_code=404, detail=f"Case {case_id} not initialized.")

    procedure = ACTIVE_PROCEDURES[case_id]

    async def event_generator():
        try:
            async for event in procedure.run_trial():
                yield f"data: {json.dumps(event)}\n\n"
            
            # Archive into completed cases
            if procedure.case_file:
                COMPLETED_CASES[case_id] = procedure.case_file
                
        except Exception as e:
            err_event = {"step": "ERROR", "message": str(e)}
            yield f"data: {json.dumps(err_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/cases")
async def list_cases(limit: int = 20, offset: int = 0):
    # Retrieve persisted cases from Neon PostgreSQL
    neon_cases = case_repo.list_cases(limit=limit, offset=offset)
    active = list(ACTIVE_PROCEDURES.keys())
    return {
        "status": "SUCCESS",
        "active_cases": active,
        "persisted_cases": neon_cases,
        "total_persisted": len(neon_cases)
    }
