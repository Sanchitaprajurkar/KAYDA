"""FastAPI application for Heimdall Agent."""

from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_1.config import settings
from agent_1.agent import HeimdallAgent
from agent_1.extraction.manifest_service import ManifestService
from agent_1.parsers.parser_factory import ParserFactory
from agent_1.models.case_file import CaseEvidenceReport
from agent_1.models.document import ParsedDocument
from agent_1.graph.client import Neo4jClient
from agent_1.storage.neon_client import get_neon_client

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
parser_factory = ParserFactory()


class DualIntakeRequest(BaseModel):
    doc_id_a: str = Field(description="First document ID e.g. ORV-0033", json_schema_extra={"example": "ORV-0033"})
    doc_id_b: str = Field(description="Second document ID e.g. ORV-0034", json_schema_extra={"example": "ORV-0034"})
    target_query: Optional[str] = Field(
        default="As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? Give a low and high range for wheat and maize imports.",
        description="Target intelligence question",
    )
    case_id: Optional[str] = Field(default=None, description="Optional custom case ID")


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


@app.get("/document/{doc_id}", tags=["Corpus"])
def get_parsed_document(doc_id: str) -> Dict[str, Any]:
    """Parse and return a specific document with full paragraph-level structure."""
    try:
        parsed: ParsedDocument = parser_factory.parse_by_doc_id(doc_id, manifest_service)
        return parsed.model_dump()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/intake/dual", response_model=CaseEvidenceReport, tags=["Heimdall Intake"])
def dual_document_intake(request: DualIntakeRequest) -> CaseEvidenceReport:
    """Execute complete Heimdall intake pipeline on two separate documents."""
    try:
        report = agent.analyze_dual_documents(
            doc_id_a=request.doc_id_a,
            doc_id_b=request.doc_id_b,
            target_query=request.target_query,
            case_id=request.case_id,
        )
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Heimdall intake failed: {e}")


@app.get("/cases", tags=["Case Files"])
def list_cases() -> List[str]:
    """List all analyzed case report IDs."""
    return agent.repository.list_cases()


@app.get("/case/{case_id}", response_model=CaseEvidenceReport, tags=["Case Files"])
def get_case(case_id: str) -> CaseEvidenceReport:
    """Retrieve an existing Case Evidence Report by ID."""
    report = agent.repository.get_case_report(case_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Case report '{case_id}' not found.")
    return report
