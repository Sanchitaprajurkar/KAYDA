"""Neon Serverless PostgreSQL connection manager with connection pooling and SSL support."""

import logging
import time
from contextlib import contextmanager
from typing import Optional, Dict, Any, Generator
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path for direct CLI script execution
_project_root = str(Path(__file__).resolve().parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from agent_1.config import settings

logger = logging.getLogger(__name__)

_neon_client: Optional["NeonClient"] = None


class NeonClient:
    """Manages thread-safe connection pooling, SSL enforcement, and health verification for Neon PostgreSQL."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        min_conn: int = 1,
        max_conn: int = 10,
    ):
        self.database_url = database_url or settings.NEON_DATABASE_URL
        self.min_conn = min_conn
        self.max_conn = max_conn
        self._pool: Optional[pool.ThreadedConnectionPool] = None
        self._is_initialized = False

    def _get_sanitized_dsn(self) -> str:
        """Ensure connection string includes sslmode=require for Neon."""
        if not self.database_url:
            raise ValueError("NEON_DATABASE_URL is not configured in settings or environment.")
        dsn = self.database_url.strip()
        if "sslmode=" not in dsn:
            sep = "&" if "?" in dsn else "?"
            dsn = f"{dsn}{sep}sslmode=require"
        return dsn

    def init_pool(self) -> pool.ThreadedConnectionPool:
        """Initialize the ThreadedConnectionPool."""
        if self._pool is not None and not self._pool.closed:
            return self._pool

        dsn = self._get_sanitized_dsn()
        try:
            self._pool = pool.ThreadedConnectionPool(
                minconn=self.min_conn,
                maxconn=self.max_conn,
                dsn=dsn,
            )
            self._is_initialized = True
            logger.info("Neon PostgreSQL connection pool initialized successfully.")
            return self._pool
        except Exception as e:
            logger.error(f"Failed to initialize Neon PostgreSQL connection pool: {e}")
            self._pool = None
            raise

    @property
    def is_configured(self) -> bool:
        """Return True if NEON_DATABASE_URL is provided."""
        return bool(self.database_url)

    @contextmanager
    def get_connection(self) -> Generator[psycopg2.extensions.connection, None, None]:
        """Context manager to check out a pooled connection and return it on exit."""
        p = self.init_pool()
        conn = p.getconn()
        try:
            yield conn
        except Exception:
            if conn and not conn.closed:
                conn.rollback()
            raise
        finally:
            if p and not p.closed and conn and not conn.closed:
                p.putconn(conn)

    def is_connected(self) -> bool:
        """Quick boolean probe to check if Neon is reachable and accepts queries."""
        if not self.is_configured:
            return False
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    val = cur.fetchone()
                    return val is not None and val[0] == 1
        except Exception as e:
            logger.warning(f"Neon connectivity check failed: {e}")
            return False

    def ping(self) -> Dict[str, Any]:
        """Execute 'SELECT 1' test query and return detailed connection metadata."""
        if not self.is_configured:
            return {
                "status": "UNCONFIGURED",
                "connected": False,
                "error": "NEON_DATABASE_URL is not set",
            }

        start = time.perf_counter()
        try:
            with self.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT 1 as ping, current_database() as database, version() as version;")
                    row = cur.fetchone()
                    latency_ms = (time.perf_counter() - start) * 1000

                    return {
                        "status": "CONNECTED",
                        "connected": True,
                        "query": "SELECT 1",
                        "ping_result": row["ping"] if row else None,
                        "database": row["database"] if row else None,
                        "version": (row["version"][:50] + "...") if row and row.get("version") else None,
                        "latency_ms": round(latency_ms, 2),
                        "pool_min": self.min_conn,
                        "pool_max": self.max_conn,
                        "ssl": True,
                    }
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            logger.error(f"Error during Neon ping test: {e}")
            return {
                "status": "ERROR",
                "connected": False,
                "query": "SELECT 1",
                "error": str(e),
                "latency_ms": round(latency_ms, 2),
            }

    def close(self):
        """Close all connections in the pool."""
        if self._pool is not None and not self._pool.closed:
            self._pool.closeall()
            self._pool = None
            self._is_initialized = False
            logger.info("Neon connection pool closed.")


def get_neon_client() -> NeonClient:
    """Retrieve or initialize the global singleton NeonClient."""
    global _neon_client
    if _neon_client is None:
        _neon_client = NeonClient()
    return _neon_client


def is_neon_reachable() -> bool:
    """Convenience helper to check if Neon PostgreSQL is online."""
    return get_neon_client().is_connected()


def test_neon_connection() -> Dict[str, Any]:
    """Convenience helper to run 'SELECT 1' probe against Neon."""
    return get_neon_client().ping()


if __name__ == "__main__":
    import json
    print("Testing Neon PostgreSQL connection...")
    res = test_neon_connection()
    print(json.dumps(res, indent=2))

