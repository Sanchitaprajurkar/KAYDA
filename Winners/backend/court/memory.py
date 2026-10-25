"""Private, lasting memory: one SQLite file per agent (FR6.1). No agent opens another agent's file.

Every read that changes what an agent does is logged by the caller with the influence it had (criterion 9).
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from backend.court.heimdall_bridge import ROOT

MEMORY_DIR = Path(os.getenv("COURT_MEMORY_DIR") or ROOT / "memory")


class AgentMemory:
    def __init__(self, agent: str, directory: Optional[Path] = None):
        self.agent = agent.lower()
        directory = Path(directory or MEMORY_DIR)
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{self.agent}.db"
        with self._conn() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY, category TEXT NOT NULL, value TEXT NOT NULL,
                case_id TEXT, updated_at TEXT NOT NULL)""")

    def _conn(self):
        return sqlite3.connect(self.path)

    def write(self, key: str, category: str, value: Any, case_id: Optional[str] = None) -> None:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO memory VALUES (?, ?, ?, ?, ?)",
                      (key, category, json.dumps(value, ensure_ascii=False), case_id,
                       datetime.now(timezone.utc).isoformat()))

    def read(self, key: str) -> Optional[Any]:
        with self._conn() as c:
            row = c.execute("SELECT value FROM memory WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def by_category(self, category: str, prefix: str = "") -> List[dict]:
        with self._conn() as c:
            rows = c.execute("SELECT key, value, case_id FROM memory WHERE category = ? AND key LIKE ?",
                             (category, f"{prefix}%")).fetchall()
        return [{"key": k, "value": json.loads(v), "case_id": cid} for k, v, cid in rows]
