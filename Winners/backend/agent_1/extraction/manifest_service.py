"""Service to load, index, and query the Runemark document manifest."""

import json
from pathlib import Path
from typing import Optional, List, Dict
from agent_1.config import settings
from agent_1.models.manifest import ManifestCatalog, ManifestEntry


class ManifestService:
    """Manages document discovery, metadata indexing, and credibility checks."""

    def __init__(self, manifest_path: Optional[Path] = None, docs_dir: Optional[Path] = None):
        self.manifest_path = manifest_path or settings.manifest_path
        self.docs_dir = docs_dir or settings.docs_path
        self._catalog: Optional[ManifestCatalog] = None
        self._doc_index: Dict[str, ManifestEntry] = {}

    def load_catalog(self) -> ManifestCatalog:
        """Load and parse manifest.json into ManifestCatalog."""
        if self._catalog is not None:
            return self._catalog

        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found at: {self.manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        self._catalog = ManifestCatalog.model_validate(raw_data)
        self._doc_index = {doc.doc_id.upper(): doc for doc in self._catalog.documents}
        return self._catalog

    @property
    def catalog(self) -> ManifestCatalog:
        """Access loaded catalog, auto-loading if necessary."""
        if self._catalog is None:
            return self.load_catalog()
        return self._catalog

    def get_document(self, doc_id: str) -> Optional[ManifestEntry]:
        """Look up metadata for a document ID (case-insensitive)."""
        self.catalog  # Ensure loaded
        return self._doc_index.get(doc_id.strip().upper())

    def get_document_file_path(self, doc_id: str) -> Optional[Path]:
        """Resolve the local filesystem path to a document's file."""
        doc = self.get_document(doc_id)
        if not doc:
            return None
        candidate = self.docs_dir / doc.file
        return candidate if candidate.exists() else None

    def get_valid_documents(self, cutoff_date: Optional[str] = None) -> List[ManifestEntry]:
        """Return documents published on or before the cutoff date (no clock violations)."""
        cutoff = cutoff_date or settings.AS_OF_DATE
        return [doc for doc in self.catalog.documents if doc.is_valid_as_of(cutoff)]

    def get_clock_violations(self, cutoff_date: Optional[str] = None) -> List[ManifestEntry]:
        """Find any documents published AFTER the cutoff date (temporal trap documents)."""
        cutoff = cutoff_date or settings.AS_OF_DATE
        return [doc for doc in self.catalog.documents if not doc.is_valid_as_of(cutoff)]

    def filter_by_sector(self, sector: str) -> List[ManifestEntry]:
        """Filter documents by industry sector e.g. 'agriculture', 'general', 'port'."""
        sec_lower = sector.strip().lower()
        return [
            doc for doc in self.catalog.documents
            if doc.sector and doc.sector.strip().lower() == sec_lower
        ]

    def filter_by_country(self, country: str) -> List[ManifestEntry]:
        """Filter documents by country association."""
        cnt_lower = country.strip().lower()
        return [
            doc for doc in self.catalog.documents
            if doc.country and doc.country.strip().lower() == cnt_lower
        ]

    def filter_by_tier(self, tier: int) -> List[ManifestEntry]:
        """Filter documents by credibility tier (1=Official, 2=Verified Wire/Port, 3=Local, 4=Tabloid)."""
        return [doc for doc in self.catalog.documents if doc.reliability_tier == tier]

    def get_catalog_summary(self) -> Dict[str, any]:
        """Return aggregated summary metrics of the document catalog."""
        docs = self.catalog.documents
        formats: Dict[str, int] = {}
        tiers: Dict[int, int] = {}
        sectors: Dict[str, int] = {}

        for d in docs:
            fmt = d.format.upper()
            formats[fmt] = formats.get(fmt, 0) + 1

            tier = d.reliability_tier
            tiers[tier] = tiers.get(tier, 0) + 1

            sec = d.sector or "unknown"
            sectors[sec] = sectors.get(sec, 0) + 1

        valid_count = len(self.get_valid_documents())
        violation_count = len(self.get_clock_violations())

        return {
            "pack": self.catalog.pack,
            "event_id": self.catalog.event_id,
            "event_name": self.catalog.name,
            "as_of_date": self.catalog.as_of,
            "total_documents": len(docs),
            "valid_as_of_count": valid_count,
            "post_cutoff_violations_count": violation_count,
            "by_format": formats,
            "by_reliability_tier": tiers,
            "by_sector": sectors,
        }
