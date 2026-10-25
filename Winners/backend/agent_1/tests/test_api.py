"""Unit tests for FastAPI endpoints."""

from fastapi.testclient import TestClient
from agent_1.api.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify health endpoint reports online status and service configurations."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert data["agent"] == "Heimdall"
    assert data["as_of_date"] == "2027-01-25"
    assert data["corpus"]["total_documents"] == 76
    assert data["corpus"]["event_id"] == "E5"
    assert "neon_postgres" in data["services"]
    assert data["services"]["neon_postgres"]["configured"] is True
    assert data["services"]["neon_postgres"]["connected"] is True


def test_manifest_endpoint():
    """Verify manifest endpoint returns 76 catalog entries."""
    response = client.get("/manifest")
    assert response.status_code == 200
    data = response.json()
    assert len(data["documents"]) == 76
    assert data["summary"]["total_documents"] == 76


def test_document_parser_endpoint():
    """Verify /document/{doc_id} parses PDF with paragraph structure."""
    response = client.get("/document/ATL-0001")
    assert response.status_code == 200
    doc = response.json()
    assert doc["doc_id"] == "ATL-0001"
    assert doc["format"] == "PDF"
    assert len(doc["paragraphs"]) > 0
    assert doc["paragraphs"][0]["paragraph_index"] == 1
