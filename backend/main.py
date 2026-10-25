from typing import Any, Dict, List, Optional
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.schemas.case_file import CaseFile
from backend.schemas.thor_claim import (
    CrossExamAttack,
    CrossExamResponse,
    EvidenceGapStatus,
    HighExposureClaim,
    MemoryLog,
)
from backend.agents.thor.agent import ThorAgent

app = FastAPI(
    title="Trial of the Nine Realms — Adversarial Courtroom Engine",
    description="Backend services for Heimdall, Thor, Loki, and Odin disruption analysis.",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared singleton agent instance
_agent_instance: Optional[ThorAgent] = None

def get_thor_agent() -> ThorAgent:
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = ThorAgent()
    return _agent_instance

class InitialAnalysisResponse(BaseModel):
    case_id: str
    as_of_date: str
    claims_count: int
    claims: List[HighExposureClaim]
    coverage_gaps_count: int
    coverage_gaps: List[EvidenceGapStatus]

class AttackRequest(BaseModel):
    loki_claims: List[Dict[str, Any]]

class AttackResponse(BaseModel):
    attacks_count: int
    attacks: List[CrossExamAttack]

class RespondRequest(BaseModel):
    attacks: List[CrossExamAttack]

class RespondResponse(BaseModel):
    responses_count: int
    responses: List[CrossExamResponse]

@app.get("/")
def root():
    return {
        "courtroom": "Trial of the Nine Realms",
        "service": "Supply Chain Disruption Impact Analyzer",
        "agents": ["Heimdall (Gatekeeper)", "Thor (The Alarm)", "Loki (The Trickster)", "Odin (The Judge)"],
        "active_module": "Thor (High-Exposure Analyst)",
        "docs_url": "/docs",
    }

@app.post("/api/thor/analyze", response_model=InitialAnalysisResponse, tags=["Thor"])
def run_initial_analysis(case_file: CaseFile, agent: ThorAgent = Depends(get_thor_agent)):
    """
    Ingests a validated Case File and executes Thor's Round 1 initial high-exposure analysis.
    Returns 3-6 structured claims and explicit coverage gaps.
    """
    if not case_file.case_id or not case_file.case_id.strip():
        raise HTTPException(status_code=400, detail="Invalid Case File: case_id must not be empty.")
    if not case_file.countries or not case_file.sectors:
        raise HTTPException(status_code=400, detail="Invalid Case File: countries and sectors must not be empty.")

    try:
        agent.ingest_case_file(case_file)
        claims, gaps = agent.conduct_initial_analysis()
        return InitialAnalysisResponse(
            case_id=case_file.case_id,
            as_of_date=case_file.as_of_date,
            claims_count=len(claims),
            claims=claims,
            coverage_gaps_count=len(gaps),
            coverage_gaps=gaps,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thor analysis failed: {str(e)}")

@app.post("/api/thor/cross-examine/attack", response_model=AttackResponse, tags=["Thor"])
def attack_loki(req: AttackRequest, agent: ThorAgent = Depends(get_thor_agent)):
    """
    Analyzes Loki's claims and generates structured cross-examination attacks
    with specific reasons (contradicts, retracted, low_tier, wrong_scope, stale, math_error).
    """
    try:
        attacks = agent.generate_attacks(req.loki_claims)
        return AttackResponse(
            attacks_count=len(attacks),
            attacks=attacks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Attack generation failed: {str(e)}")

@app.post("/api/thor/cross-examine/respond", response_model=RespondResponse, tags=["Thor"])
def respond_to_attacks(req: RespondRequest, agent: ThorAgent = Depends(get_thor_agent)):
    """
    Responds to attacks from Loki: mounts structured defences with NEW evidence,
    or formally concedes when counter-evidence defeats the claim.
    """
    try:
        responses = agent.respond_to_attacks(req.attacks)
        return RespondResponse(
            responses_count=len(responses),
            responses=responses,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Response evaluation failed: {str(e)}")

@app.get("/api/thor/memory/logs", response_model=List[MemoryLog], tags=["Thor"])
def get_memory_logs(agent: ThorAgent = Depends(get_thor_agent)):
    """
    Retrieves the complete audit trail of Thor's private persistent memory operations,
    explaining how each memory entry directly influenced an analytical decision.
    """
    return agent.memory.get_logs()

@app.get("/api/thor/health", tags=["Thor"])
def health_check(agent: ThorAgent = Depends(get_thor_agent)):
    return {
        "status": "healthy",
        "agent": "THOR",
        "role": "High-Exposure Commercial Analyst (The Alarm)",
        "active_claims_count": len(agent.active_claims),
        "as_of_date": agent.case_file.as_of_date if agent.case_file else "UNSET",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
