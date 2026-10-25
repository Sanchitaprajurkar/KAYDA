import os
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file from backend root
env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_file)

class Settings(BaseSettings):
    PROJECT_NAME: str = "Trial of the Nine Realms"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api"
    
    # Path configuration
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DEV_PACK_DIR: Path = BASE_DIR / "dev_pack_E5"
    DOCS_DIR: Path = DEV_PACK_DIR / "docs"
    MANIFEST_PATH: Path = DEV_PACK_DIR / "manifest.json"
    HASHES_PATH: Path = DEV_PACK_DIR / "hashes.sha256"
    
    # Database Configuration (Neon PostgreSQL)
    DATABASE_URL: str = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL", "")
    
    # Trial rules & defaults
    DEFAULT_AS_OF_DATE: str = "2027-01-25"
    MAX_RUNS: int = 2
    MAX_ROUNDS_PER_RUN: int = 2
    
    # LLM Settings (optional enhancement, fallback is deterministic offline reasoning engine)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    
    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "*"
    ]

settings = Settings()
