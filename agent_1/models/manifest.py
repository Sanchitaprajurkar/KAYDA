"""Pydantic schemas for Runemark document manifest catalog."""

from datetime import date
from typing import Optional, List, Union
from pathlib import Path
from pydantic import BaseModel, Field, model_validator


class ManifestEntry(BaseModel):
    """Metadata for a single document in the Runemark corpus."""

    doc_id: str = Field(alias="DOC_ID", description="Unique Document identifier e.g. ATL-0001, ORV-0004")
    event_id: str = Field(alias="EVENT_ID", default="NONE", description="Associated disruption event or NONE")
    title: str = Field(alias="TITLE", description="Document title")
    source_name: str = Field(alias="SOURCE_NAME", description="Publishing outlet or authority name")
    source_type: str = Field(alias="SOURCE_TYPE", description="Type of source e.g. atlas, regional_bulletin, newswire")
    reliability: Union[str, int] = Field(
        alias="RELIABILITY",
        default=2,
        description="Credibility tier rating (1=Official/Treaty, 2=Verified Port/Wire, 3=Industry/Local, 4=Tabloid/Rumour)",
    )
    pub_date: str = Field(alias="PUB_DATE", description="Publication date in YYYY-MM-DD")
    pub_time: Optional[str] = Field(alias="PUB_TIME", default=None, description="Publication time HH:MM if available")
    country: Optional[str] = Field(alias="COUNTRY", default=None, description="Associated primary country")
    sector: Optional[str] = Field(alias="SECTOR", default=None, description="Sector e.g. general, agriculture, port")
    language: str = Field(alias="LANGUAGE", default="en")
    file: str = Field(description="Filename within docs/ directory")
    format: Optional[str] = Field(default=None, alias="FORMAT", description="File format PDF, TXT, or DOCX")

    model_config = {
        "populate_by_name": True,
        "extra": "ignore",
    }

    @model_validator(mode="before")
    @classmethod
    def populate_defaults(cls, data: any) -> any:
        if isinstance(data, dict):
            # Fallback for uppercase/lowercase keys
            if "DOC_ID" not in data and "doc_id" in data:
                data["DOC_ID"] = data["doc_id"]
            if "TITLE" not in data and "title" in data:
                data["TITLE"] = data["title"]
            if "SOURCE_NAME" not in data and "source_name" in data:
                data["SOURCE_NAME"] = data["source_name"]
            if "SOURCE_TYPE" not in data and "source_type" in data:
                data["SOURCE_TYPE"] = data["source_type"]
            if "PUB_DATE" not in data and "pub_date" in data:
                data["PUB_DATE"] = data["pub_date"]
            if "PUB_TIME" not in data and "pub_time" in data:
                data["PUB_TIME"] = data["pub_time"]
            if "COUNTRY" not in data and "country" in data:
                data["COUNTRY"] = data["country"]
            if "SECTOR" not in data and "sector" in data:
                data["SECTOR"] = data["sector"]
            if "RELIABILITY" not in data and "reliability" in data:
                data["RELIABILITY"] = data["reliability"]

            # Infer FORMAT from file extension if not provided
            if not data.get("FORMAT") and not data.get("format"):
                filename = data.get("file", "")
                if filename:
                    ext = Path(filename).suffix.lstrip(".").upper()
                    data["FORMAT"] = ext or "TXT"
        return data

    @property
    def reliability_tier(self) -> int:
        """Convert reliability string to integer tier (1-4)."""
        try:
            return int(self.reliability)
        except (ValueError, TypeError):
            return 4

    def is_valid_as_of(self, cutoff_date_str: str = "2027-01-25") -> bool:
        """Return True if published on or before the challenge as-of date (prevents clock violations)."""
        try:
            doc_d = date.fromisoformat(self.pub_date)
            cutoff_d = date.fromisoformat(cutoff_date_str)
            return doc_d <= cutoff_d
        except (ValueError, TypeError):
            return False


class ManifestCatalog(BaseModel):
    """Catalog of all available documents in a dev pack."""

    pack: str = Field(default="dev_pack_E5")
    event_id: str = Field(default="E5")
    name: str = Field(default="Orvan grain corridor collapse")
    as_of: str = Field(default="2027-01-25")
    count: int = Field(default=0)
    documents: List[ManifestEntry] = Field(default_factory=list)

    def get_by_id(self, doc_id: str) -> Optional[ManifestEntry]:
        """Lookup document entry by DOC_ID."""
        normalized = doc_id.strip().upper()
        for doc in self.documents:
            if doc.doc_id.upper() == normalized:
                return doc
        return None

    def filter_valid(self, cutoff_date: Optional[str] = None) -> List[ManifestEntry]:
        """Return documents published on or before the cutoff date."""
        cutoff = cutoff_date or self.as_of
        return [doc for doc in self.documents if doc.is_valid_as_of(cutoff)]
