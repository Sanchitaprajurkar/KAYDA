"""Verdict cache for Heimdall's LLM judgements, keyed by model and the facts judged.

On a send-back Heimdall re-checks the whole Case File; cached pair and stance verdicts mean only the newly added
evidence reaches the LLM. Stand-in LLMs without a model name are never cached.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path(os.getenv("HEIMDALL_CACHE_DIR") or Path(__file__).resolve().parents[2] / "cache")


class VerdictCache:
    _lock = threading.Lock()

    def __init__(self, name: str, model: Optional[str]):
        self.model = None if model in (None, "scripted") else model
        self.path = CACHE_DIR / f"{name}.json"
        self.data = {}
        if model and self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))

    @property
    def enabled(self) -> bool:
        return bool(self.model)

    def get(self, key: str) -> Optional[Any]:
        return self.data.get(f"{self.model}|{key}") if self.enabled else None

    def put(self, key: str, value: Any) -> None:
        if self.enabled:
            self.data[f"{self.model}|{key}"] = value

    def save(self) -> None:
        if self.enabled:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
