"""Repository for storing and retrieving Case Evidence Reports from Supabase and local storage."""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

from agent_1.config import settings
from agent_1.storage.supabase_client import get_supabase_client
from agent_1.models.case_file import CaseEvidenceReport

logger = logging.getLogger(__name__)


class CaseRepository:
    """Handles structured persistence of CaseEvidenceReports with Supabase and local cache."""

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or (settings.BASE_DIR / "reports")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.supabase = get_supabase_client()

    def save_case_report(self, report: CaseEvidenceReport) -> bool:
        """Persist report to Supabase and write local JSON backup."""
        # 1. Always save local JSON copy
        local_path = self.storage_dir / f"{report.case_id}.json"
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(report.to_json_report(indent=2))
        logger.info(f"Saved local case report to {local_path}")

        # 2. Persist to Supabase if client is available
        if self.supabase:
            try:
                payload = {
                    "case_id": report.case_id,
                    "as_of_date": report.as_of_date,
                    "target_query": report.target_query,
                    "event_status": report.event_verification.status.value,
                    "report_data": json.loads(report.to_json_report()),
                    "generated_at": report.generated_at,
                }
                # Upsert into case_reports table
                res = self.supabase.table("case_reports").upsert(payload).execute()
                logger.info(f"Saved case report to Supabase table 'case_reports': {res}")
                return True
            except Exception as e:
                logger.warning(
                    f"Could not persist report to Supabase table (table may not exist yet): {e}. "
                    f"Local JSON copy preserved at {local_path}."
                )

        return True

    def get_case_report(self, case_id: str) -> Optional[CaseEvidenceReport]:
        """Fetch case report by case_id from Supabase or local cache."""
        # 1. Try Supabase
        if self.supabase:
            try:
                res = self.supabase.table("case_reports").select("*").eq("case_id", case_id).execute()
                if res.data and len(res.data) > 0:
                    report_dict = res.data[0].get("report_data")
                    return CaseEvidenceReport.model_validate(report_dict)
            except Exception as e:
                logger.debug(f"Supabase lookup skipped: {e}")

        # 2. Try local file
        local_path = self.storage_dir / f"{case_id}.json"
        if local_path.exists():
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return CaseEvidenceReport.model_validate(data)

        return None

    def list_cases(self) -> List[str]:
        """List all available case IDs."""
        case_ids = set()
        # From local directory
        for f in self.storage_dir.glob("*.json"):
            case_ids.add(f.stem)

        # From Supabase
        if self.supabase:
            try:
                res = self.supabase.table("case_reports").select("case_id").execute()
                for row in (res.data or []):
                    case_ids.add(row.get("case_id"))
            except Exception:
                pass

        return sorted(list(case_ids))
