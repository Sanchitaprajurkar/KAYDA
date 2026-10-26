"""Verdict cache for Heimdall's LLM judgements, keyed by model and the facts judged.

On a send-back Heimdall re-checks the whole Case File; cached pair and stance verdicts mean only the newly added
evidence reaches the LLM. Stand-in LLMs without a model name are never cached.
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

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
        if not self.enabled:
            return
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                payload = json.dumps(self.data, ensure_ascii=False)
                # Write to a sibling temp file and atomically replace to avoid Windows
                # file-lock races (antivirus, other processes, concurrent saves).
                fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=self.path.stem, suffix=".tmp")
                try:
                    with os.fdopen(fd, "w", encoding="utf-8") as f:
                        f.write(payload)
                    os.replace(tmp, self.path)
                except Exception:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
                    raise
            except Exception as exc:
                logger.warning("VerdictCache: failed to save %s: %s", self.path.name, exc)
