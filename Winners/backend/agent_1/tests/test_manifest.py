"""Unit tests for ManifestService and Manifest models."""

import pytest
from pathlib import Path
from agent_1.extraction.manifest_service import ManifestService
from agent_1.config import settings


def test_manifest_loads_successfully():
    """Verify manifest.json parses into 76 document models."""
    service = ManifestService()
    catalog = service.load_catalog()

    assert catalog.pack == "dev_pack_E5"
    assert catalog.event_id == "E5"
    assert catalog.as_of == "2027-01-25"
    assert len(catalog.documents) == 76
    assert catalog.count == 76


def test_manifest_get_by_id():
    """Verify document lookup by ID is case-insensitive and returns correct metadata."""
    service = ManifestService()
    
    doc = service.get_document("ATL-0001")
    assert doc is not None
    assert doc.doc_id == "ATL-0001"
    assert doc.format == "PDF"
    assert doc.reliability_tier == 1
    assert doc.country == "Utgard"

    # Lowercase lookup
    doc_lower = service.get_document("atl-0001")
    assert doc_lower is not None
    assert doc_lower.doc_id == "ATL-0001"


def test_manifest_file_paths_exist():
    """Verify resolved document paths point to existing files on disk."""
    service = ManifestService()
    
    # Check sample documents from atlas and orvan
    for doc_id in ["ATL-0001", "ATL-0002", "ATL-0003", "ORV-0001"]:
        doc_path = service.get_document_file_path(doc_id)
        assert doc_path is not None, f"Path for {doc_id} should not be None"
        assert doc_path.exists(), f"File {doc_path} should exist on disk"


def test_manifest_as_of_filtering():
    """Verify documents are checked against 2027-01-25 temporal cutoff."""
    service = ManifestService()
    valid_docs = service.get_valid_documents("2027-01-25")
    assert len(valid_docs) > 0

    # Ensure all valid docs have pub_date <= 2027-01-25
    for doc in valid_docs:
        assert doc.pub_date <= "2027-01-25"


def test_manifest_summary():
    """Verify catalog summary contains format, tier, and sector breakdown."""
    service = ManifestService()
    summary = service.get_catalog_summary()

    assert summary["total_documents"] == 76
    assert "PDF" in summary["by_format"]
    assert "TXT" in summary["by_format"]
    assert "DOCX" in summary["by_format"]
    assert 1 in summary["by_reliability_tier"]
    assert summary["as_of_date"] == "2027-01-25"
