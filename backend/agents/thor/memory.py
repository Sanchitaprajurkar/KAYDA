import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from backend.schemas.thor_claim import (
    MemoryAction,
    MemoryCategory,
    MemoryEntry,
    MemoryLog,
)

class ThorPersistentMemory:
    """
    Private, persistent memory system for Thor.
    Keeps Thor's internal state, adversary tactics, verified corridor bottlenecks,
    and concession records strictly isolated from other courtroom agents.
    Every read and write is logged with an explicit decision influence explanation.
    """

    SEED_KEYS = {"known_retractions", "opponent_profile_loki"}

    def __init__(self, storage_path: Optional[Path] = None, enabled: bool = True):
        self.storage_path = storage_path
        self.enabled = enabled
        self.entries: Dict[str, MemoryEntry] = {}
        self.logs: List[MemoryLog] = []
        self.cited_evidence_ids: List[str] = []
        self.active_event_id: Optional[str] = None
        self.active_case_id: Optional[str] = None

        if self.storage_path and Path(self.storage_path).exists() and Path(self.storage_path).stat().st_size > 0:
            self.load()
        else:
            self._initialize_seed_knowledge()

    def set_active_case(self, case_id: str, event_id: str):
        """
        Anti-contamination: when switching to a different event, clear previous case facts
        while retaining permanent seed intelligence.
        """
        if self.active_event_id and self.active_event_id != event_id:
            self.clear_case_facts()
        self.active_case_id = case_id
        self.active_event_id = event_id

    def clear_case_facts(self):
        """
        Clears all non-seed memory entries and cited evidence to prevent memory contamination.
        """
        self.entries = {k: v for k, v in self.entries.items() if k in self.SEED_KEYS}
        self.cited_evidence_ids = []

    def _initialize_seed_knowledge(self):
        self.write(
            key="known_retractions",
            category=MemoryCategory.RETRACTED_SOURCES,
            value=["WLD-0024", "ORV-0043", "ORV-0015"],
            source="atlas_and_manifest_analysis",
            context="initialization",
            decision_influence="Ensures Thor never cites retracted bulletins and attacks opponent if cited.",
        )
        self.write(
            key="opponent_profile_loki",
            category=MemoryCategory.OPPONENT_PROFILE,
            value={
                "core_thesis": "Limited exposure, substitutes absorb shocks, buffer stocks cushion Q1",
                "vulnerabilities": ["Uses unverified route capacity notes", "Ignores rail sidings bottleneck", "Confuses spot forward prices with realized physical deliveries"],
            },
            source="tactical_briefing",
            context="initialization",
            decision_influence="Focuses Thor's cross-examination attacks on unverified substitute capacity and rail bottlenecks.",
        )

    def read(self, key: str, context: str, decision_influence: str) -> Optional[Any]:
        if not self.enabled:
            self.logs.append(MemoryLog(
                action=MemoryAction.READ,
                key=key,
                category=None,
                context=context,
                decision_influence="Memory disabled: lookup bypassed.",
                timestamp=datetime.utcnow().isoformat(),
            ))
            return None

        entry = self.entries.get(key)
        val = entry.value if entry else None

        log = MemoryLog(
            action=MemoryAction.READ,
            key=key,
            category=entry.category.value if entry else None,
            context=context,
            decision_influence=decision_influence,
            timestamp=datetime.utcnow().isoformat(),
        )
        self.logs.append(log)

        if entry:
            entry.last_accessed = datetime.utcnow().isoformat()

        return val

    def write(
        self,
        key: str,
        category: MemoryCategory,
        value: Any,
        source: str,
        context: str,
        decision_influence: str,
        confidence: float = 1.0,
    ):
        if not self.enabled:
            self.logs.append(MemoryLog(
                action=MemoryAction.WRITE,
                key=key,
                category=category.value,
                context=context,
                decision_influence="Memory disabled: write bypassed.",
                timestamp=datetime.utcnow().isoformat(),
            ))
            return

        now = datetime.utcnow().isoformat()
        entry = MemoryEntry(
            key=key,
            category=category,
            value=value,
            source=source,
            confidence=confidence,
            created_at=now,
            last_accessed=now,
        )
        self.entries[key] = entry

        log = MemoryLog(
            action=MemoryAction.WRITE,
            key=key,
            category=category.value,
            context=context,
            decision_influence=decision_influence,
            timestamp=now,
        )
        self.logs.append(log)

        if self.storage_path:
            self.save()

    def record_cited_evidence(self, doc_ids: List[str], claim_id: str):
        new_ids = [d.upper() for d in doc_ids if d.upper() not in self.cited_evidence_ids]
        self.cited_evidence_ids.extend(new_ids)
        self.write(
            key="cited_evidence_inventory",
            category=MemoryCategory.EVIDENCE_INVENTORY,
            value=list(set(self.cited_evidence_ids)),
            source=f"claim_generation_{claim_id}",
            context=f"authoring_claim_{claim_id}",
            decision_influence="Tracks evidence inventory so that future cross-examination defences use brand new documents.",
        )

    def is_previously_cited(self, doc_id: str) -> bool:
        return doc_id.upper() in self.cited_evidence_ids

    def get_logs(self) -> List[MemoryLog]:
        return self.logs

    def save(self):
        if not self.storage_path:
            return
        path = Path(self.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": {k: v.model_dump() for k, v in self.entries.items()},
            "logs": [l.model_dump() for l in self.logs],
            "cited_evidence_ids": self.cited_evidence_ids,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self):
        if not self.storage_path or not Path(self.storage_path).exists():
            return
        with open(self.storage_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.entries = {
                k: MemoryEntry(**v) for k, v in data.get("entries", {}).items()
            }
            self.logs = [MemoryLog(**l) for l in data.get("logs", [])]
            self.cited_evidence_ids = data.get("cited_evidence_ids", [])
