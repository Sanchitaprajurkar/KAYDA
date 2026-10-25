"""Connection tests for Neon Serverless PostgreSQL."""

import pytest
from heimdall.storage.neon_client import get_neon_client, is_neon_reachable, test_neon_connection


def test_neon_connection_reachable():
    """Verify Neon PostgreSQL instance is reachable."""
    reachable = is_neon_reachable()
    assert reachable is True, "Neon PostgreSQL should be reachable and online."


def test_neon_select_1_query():
    """Verify Neon executes 'SELECT 1' query successfully with connection metadata."""
    ping_result = test_neon_connection()
    assert ping_result["status"] == "CONNECTED"
    assert ping_result["connected"] is True
    assert ping_result["query"] == "SELECT 1"
    assert ping_result["ping_result"] == 1
    assert ping_result["database"] == "neondb"
    assert ping_result["latency_ms"] > 0
    assert ping_result["ssl"] is True


def test_neon_pooled_connection():
    """Verify pooled connection checkout, query execution, and return."""
    client = get_neon_client()
    with client.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 + 1 as sum;")
            res = cur.fetchone()
            assert res[0] == 2
