from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.ingestion.corpus import corpus
from app.routers import trial, corpus as corpus_router, tools as tools_router

from app.db.schema import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load corpus on startup for instantaneous search & streaming
    print("[NineRealms] Starting Tribunal Engine...")
    corpus.load_corpus()
    print(f"[NineRealms] Ready. Documents indexed: {len(corpus.documents)}")

    # Initialize Neon PostgreSQL database
    try:
        init_db()
        print("[NineRealms] Neon PostgreSQL connected and schema verified.")
    except Exception as e:
        print(f"[NineRealms] Neon PostgreSQL warning: {e}")

    yield
    print("[NineRealms] Tribunal Engine shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Adversarial Multi-Agent Courtroom Arbitration System for Supply Chain Disruption Intelligence",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(trial.router, prefix=settings.API_V1_PREFIX)
app.include_router(corpus_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(tools_router.router, prefix=settings.API_V1_PREFIX)

@app.get("/")
async def root():
    return {
        "system": "Trial of the Nine Realms — Adversarial Courtroom Intelligence",
        "status": "OPERATIONAL",
        "version": settings.VERSION,
        "agents": {
            "heimdall": "The Gatekeeper (Case Builder & Verification)",
            "thor": "The Alarm (High Exposure Proponent)",
            "loki": "The Trickster (Limited Exposure & Mitigation Skeptic)",
            "odin": "The Allfather (Supreme Bench & Executive Briefing)"
        },
        "default_as_of_date": settings.DEFAULT_AS_OF_DATE,
        "docs_count": len(corpus.documents),
        "api_docs": "/docs"
    }

@app.get("/api/health")
async def health_check():
    db_status = "connected"
    tables = []
    try:
        from app.db.connection import db_manager
        with db_manager.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema();")
                tables = [r[0] for r in cur.fetchall()]
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status": "healthy",
        "database": db_status,
        "database_provider": "Neon PostgreSQL",
        "tables": tables,
        "corpus_loaded": corpus._is_loaded,
        "total_documents": len(corpus.documents),
        "default_as_of_date": settings.DEFAULT_AS_OF_DATE
    }
