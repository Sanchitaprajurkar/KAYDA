"""Configuration management for Heimdall Agent."""

from pathlib import Path
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    ENVIRONMENT: str = Field(default="development")
    LOG_LEVEL: str = Field(default="INFO")
    AS_OF_DATE: str = Field(
        default="2027-01-25",
        description="Temporal cutoff as-of date for document validity",
    )

    # Paths
    BASE_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    DEV_PACK_DIR: str = Field(
        default="03_Ragnarok Trial of the Nine Realms/dev_pack_E5"
    )

    # OpenAI API
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_MODEL: str = Field(default="gpt-4o")

    # Neon PostgreSQL
    NEON_DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Neon Serverless PostgreSQL database connection URL",
    )

    # Legacy Supabase placeholders (for backwards compatibility until repository transition)
    SUPABASE_URL: Optional[str] = Field(default=None)
    SUPABASE_KEY: Optional[str] = Field(default=None)
    SUPABASE_DB_URL: Optional[str] = Field(default=None)

    # Neo4j
    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j", validation_alias="NEO4J_USERNAME")
    NEO4J_PASSWORD: Optional[str] = Field(default=None)
    NEO4J_DATABASE: Optional[str] = Field(default="neo4j")
    NEO4J_MOCK_FALLBACK: bool = Field(
        default=True,
        description="Fallback to mock/in-memory graph when Neo4j is offline",
    )

    @property
    def dev_pack_path(self) -> Path:
        """Resolve full absolute path to dev_pack directory with fallback."""
        path = Path(self.DEV_PACK_DIR)
        if not path.is_absolute():
            path = (self.BASE_DIR / path).resolve()
        if not path.exists():
            for alt in [
                self.BASE_DIR / "03_Ragnarok Trial of the Nine Realms" / "dev_pack_E5",
                self.BASE_DIR / "dev_pack_E5",
                self.BASE_DIR / "Winners" / "dev_pack_E5",
            ]:
                if alt.exists():
                    return alt
        return path

    @property
    def manifest_path(self) -> Path:
        """Resolve path to manifest.json."""
        return self.dev_pack_path / "manifest.json"

    @property
    def docs_path(self) -> Path:
        """Resolve path to docs directory."""
        return self.dev_pack_path / "docs"


# Global singleton settings instance
settings = Settings()
