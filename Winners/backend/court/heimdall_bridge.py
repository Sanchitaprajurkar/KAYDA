"""Runs Heimdall in-process so a courtroom session needs no second server.

Heimdall lives in Winners/backend (package heimdall); this puts that folder on the import path once.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # → KAYDA/Winners/
HEIMDALL_DIR = ROOT / "backend"
if str(HEIMDALL_DIR) not in sys.path:
    sys.path.insert(0, str(HEIMDALL_DIR))

from heimdall.agent import MAX_RUNS, CaseNotFoundError, HeimdallAgent, RunLimitError  # noqa: E402
from heimdall.case.trade import TradeStore  # noqa: E402
from heimdall.models.case_file import CaseEvidenceReport, EventStatus, TradeRowRecord, TradeSeries  # noqa: E402
from heimdall.models.evidence import ExtractedFact  # noqa: E402
from heimdall.reasoning.llm import StructuredLLM  # noqa: E402
from heimdall.storage.evidence_store import ExcludedDocumentError, ResolvedEvidenceStore  # noqa: E402

TRIAL_STATUSES = {EventStatus.CONFIRMED, EventStatus.DISPUTED}


def goes_to_trial(report: CaseEvidenceReport) -> bool:
    """A verified event goes to trial; so does a developing one, but only when Heimdall matched the question to a
    known event (credible reports exist but are not yet confirmed). A developing verdict with no matched event means
    unrelated documents were scored, not that the alleged event is reported."""
    v = report.event_verification
    return v.status in TRIAL_STATUSES or (v.status == EventStatus.DEVELOPING and bool(report.case_scope.event_id))

__all__ = ["ROOT", "MAX_RUNS", "CaseNotFoundError", "HeimdallAgent", "RunLimitError", "TradeStore",
           "CaseEvidenceReport", "EventStatus", "TradeRowRecord", "TradeSeries", "ExtractedFact", "StructuredLLM",
           "ExcludedDocumentError", "ResolvedEvidenceStore", "TRIAL_STATUSES", "goes_to_trial"]
