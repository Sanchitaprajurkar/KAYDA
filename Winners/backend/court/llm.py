"""LLM access for the courtroom agents: structured output, a prompt-hash cache and a token budget per agent.

The cache makes a replayed case cost nothing and give the same transcript (NFR6). The budget enforces NFR5:
when an agent runs out, the call raises BudgetExceeded and the agent falls back to its deterministic rules.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from backend.court.heimdall_bridge import ROOT, StructuredLLM

T = TypeVar("T", bound=BaseModel)
CACHE_DIR = Path(os.getenv("COURT_LLM_CACHE") or ROOT / "cases" / ".llm_cache")


class BudgetExceeded(RuntimeError):
    pass


class CourtLLM:
    def __init__(self, agent: str, budget_tokens: int, backend=None, cache_dir: Optional[Path] = None):
        self.agent = agent
        self.budget_tokens = budget_tokens
        self.used_tokens = 0
        self.calls = 0
        self.cache_hits = 0
        self._backend = backend
        self.cache_dir = Path(cache_dir or CACHE_DIR)

    @property
    def backend(self):
        if self._backend is None:
            self._backend = StructuredLLM()
        return self._backend

    def reset_budget(self) -> None:
        self.used_tokens = 0

    def ask(self, system: str, user: str, schema: Type[T]) -> T:
        model = getattr(self.backend, "model_name", "scripted")
        key = hashlib.sha256(f"{model}\n{schema.__name__}\n{system}\n{user}".encode("utf-8")).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if path.exists():
            self.cache_hits += 1
            return schema.model_validate_json(path.read_text(encoding="utf-8"))
        estimate = (len(system) + len(user)) // 4
        if self.used_tokens + estimate > self.budget_tokens:
            raise BudgetExceeded(f"{self.agent} token budget ({self.budget_tokens}) reached")
        result = self.backend.parse(system, user, schema)
        self.calls += 1
        self.used_tokens += estimate + len(result.model_dump_json()) // 4
        if model != "scripted":
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(result.model_dump_json(), encoding="utf-8")
        return result


def compact(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
