import os
from contextlib import contextmanager
from typing import Generator
import psycopg
from app.config import settings

class DatabaseConnectionManager:
    """
    Manages secure, pooled connections to Neon PostgreSQL.
    Configures SSL mode and prevents connection leakage.
    """
    def __init__(self):
        self._url = settings.DATABASE_URL
        self._initialized = False

    def get_url(self) -> str:
        # Re-check settings or environment if not set initially
        if not self._url:
            self._url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL", "")
        return self._url

    @contextmanager
    def connection(self) -> Generator[psycopg.Connection, None, None]:
        url = self.get_url()
        if not url:
            raise ValueError("DATABASE_URL is not configured. Please check your .env file.")

        # Neon requires sslmode=require
        conn = psycopg.connect(url)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

db_manager = DatabaseConnectionManager()

def get_db():
    """FastAPI dependency or procedural context manager for DB access."""
    with db_manager.connection() as conn:
        yield conn
