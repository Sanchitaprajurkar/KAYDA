"""FastAPI application for Heimdall Agent."""

from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_1.config import settings
from agent_1.agent import MAX_NEW_DOCUMENTS, CaseNotFoundError, HeimdallAgent, RunLimitError
from agent_1.extraction.manifest_service import ManifestService
from agent_1.models.case_file import CaseEvidenceReport
from agent_1.models.document import ParsedDocument
from agent_1.graph.client import Neo4jClient
from agent_1.storage.neon_client import get_neon_client
from agent_1.storage.evidence_store import ExcludedDocumentError

app = FastAPI(
    title="Heimdall Agent API",
    description="Evidence-intake and intelligence analysis service for Trial of the Nine Realms.",
    version="0.1.0",
)

# Enable CORS for frontend and multi-agent interaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
agent = HeimdallAgent()
manifest_service = ManifestService()


class CaseRequest(BaseModel):
    query: Optional[str] = Field(
        default=None, description="Natural-language case question",
        json_schema_extra={"example": "As of 25 January 2027, how exposed are Midgard and Tolan to the end of the "
                                      "Orvan corridor agreement? Give a low and high range for wheat and maize imports."},
    )
    event_id: Optional[str] = Field(default=None, description="Event ID, e.g. E5")
    case_id: Optional[str] = Field(default=None, description="Optional custom case ID")
    max_documents: int = Field(default=40, ge=1, le=100)


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    """Check connectivity and operational readiness of Heimdall Agent components."""
    neo4j_client = Neo4jClient()
    neo4j_connected = neo4j_client.is_connected
    neon_client = get_neon_client()
    neon_status = neon_client.ping()
    openai_ready = bool(settings.OPENAI_API_KEY)

    catalog_summary = manifest_service.get_catalog_summary()

    return {
        "status": "ONLINE",
        "agent": "Heimdall",
        "as_of_date": settings.AS_OF_DATE,
        "environment": settings.ENVIRONMENT,
        "services": {
            "openai_llm": {"configured": openai_ready, "model": settings.OPENAI_MODEL},
            "neo4j_graph": {"connected": neo4j_connected, "uri": settings.NEO4J_URI},
            "neon_postgres": {
                "configured": neon_client.is_configured,
                "connected": neon_status.get("connected", False),
                "database": neon_status.get("database"),
                "latency_ms": neon_status.get("latency_ms"),
            },
        },
        "corpus": {
            "total_documents": catalog_summary["total_documents"],
            "event_id": catalog_summary["event_id"],
            "event_name": catalog_summary["event_name"],
        },
    }


@app.get("/manifest", tags=["Corpus"])
def get_manifest_catalog() -> Dict[str, Any]:
    """Return summary and all document records in the manifest."""
    catalog = manifest_service.catalog
    return {
        "summary": manifest_service.get_catalog_summary(),
        "documents": [doc.model_dump(by_alias=True) for doc in catalog.documents],
    }


def _excluded_detail(e: ExcludedDocumentError) -> Dict[str, Any]:
    return {"error": "document_not_admissible", "doc_id": e.doc_id, "reasons": e.reasons, "message": str(e)}


@app.get("/document/{doc_id}", tags=["Corpus"])
def get_parsed_document(doc_id: str) -> Dict[str, Any]:
    """Return an evidence document (trap-resolved) with paragraph-level structure; duplicates resolve to canonical."""
    try:
        ref = agent.evidence_store.resolve(doc_id)
    except ExcludedDocumentError as e:
        raise HTTPException(status_code=422, detail=_excluded_detail(e))
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    doc: ParsedDocument = agent.evidence_store.document(ref.doc_id)
    return {**doc.model_dump(), "requested_id": ref.requested_id, "alias_kind": ref.alias_kind}


@app.post("/case", response_model=CaseEvidenceReport, tags=["Heimdall Intake"])
def create_case_file(request: CaseRequest) -> CaseEvidenceReport:
    """Build a case file from a query or event ID using trap-resolved evidence."""
    if not request.query and not request.event_id:
        raise HTTPException(status_code=400, detail="Provide a query or an event_id.")
    try:
        return agent.build_case_file(query=request.query, event_id=request.event_id,
                                     case_id=request.case_id, max_documents=request.max_documents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Heimdall case file failed: {e}")


def _require_store() -> None:
    if not agent.case_store.enabled:
        raise HTTPException(status_code=503, detail="Neon is not configured; Case Files are stored there.")


@app.get("/cases", tags=["Case Files"])
def list_cases() -> List[Dict[str, Any]]:
    """List stored Case Files (latest run of each), newest first."""
    _require_store()
    return agent.case_store.list_cases()


@app.get("/case/{case_id}", response_model=CaseEvidenceReport, tags=["Case Files"])
def get_case(case_id: str) -> CaseEvidenceReport:
    """The latest Case File for a case, read from Neon - what Thor, Loki and Odin consume."""
    _require_store()
    report = agent.case_store.load(case_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    return report


class ResearchRequest(BaseModel):
    request: str = Field(description="What Odin wants Heimdall to look for",
                         json_schema_extra={"example": "Tolan maize imports and rail capacity after December"})
    max_new_documents: int = Field(default=MAX_NEW_DOCUMENTS, ge=1, le=40)


@app.post("/case/{case_id}/research", response_model=CaseEvidenceReport, tags=["Heimdall Intake"])
def research_case(case_id: str, body: ResearchRequest) -> CaseEvidenceReport:
    """Odin sends the case back: Heimdall searches again and returns the next run's Case File (FR1.4)."""
    _require_store()
    try:
        return agent.re_search(case_id, body.request, max_new_documents=body.max_new_documents)
    except CaseNotFoundError:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    except RunLimitError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
