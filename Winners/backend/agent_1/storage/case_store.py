"""Persist a Heimdall case file into the courtroom tables in Neon (cases, case_documents, claims, audit_log)."""

import json
from typing import Dict, List, Optional

from psycopg2.extras import Json, execute_values

from agent_1.models.case_file import CaseEvidenceReport, EventStatus
from agent_1.storage.neon_client import NeonClient, get_neon_client

AGENT = "HEIMDALL"


def event_verified(report: CaseEvidenceReport) -> bool:
    v = report.event_verification
    return v.status == EventStatus.CONFIRMED and v.is_active_at_as_of


def scoped_claim_fact_ids(report: CaseEvidenceReport) -> List[str]:
    """Facts handed to downstream agents: those about the case's countries/commodities, plus event evidence."""
    scope = report.case_scope
    names = set(scope.countries + scope.event_countries)
    goods = set(scope.commodities)
    event_docs = set(report.event_verification.supporting_doc_ids)
    return [a.fact_id for a in report.fact_assessments
            if (names & set(a.countries)) or (goods & set(a.commodities)) or a.doc_id in event_docs]


class NeonCaseStore:
    def __init__(self, client: Optional[NeonClient] = None):
        self.client = client or get_neon_client()
        self._schema_ready = False

    @property
    def enabled(self) -> bool:
        return self.client.is_configured

    def _ensure_schema(self, cur) -> None:
        if not self._schema_ready:
            cur.execute("ALTER TABLE cases ADD COLUMN IF NOT EXISTS case_file JSONB")
            self._schema_ready = True

    def load(self, case_id: str) -> Optional[CaseEvidenceReport]:
        """The latest Case File for a case, as Thor, Loki and Odin read it."""
        with self.client.get_connection() as conn:
            with conn.cursor() as cur:
                self._ensure_schema(cur)
                cur.execute("SELECT case_file FROM cases WHERE case_id = %s", (case_id,))
                row = cur.fetchone()
            conn.commit()
        return CaseEvidenceReport.model_validate(row[0]) if row and row[0] else None

    def list_cases(self) -> List[dict]:
        with self.client.get_connection() as conn:
            with conn.cursor() as cur:
                self._ensure_schema(cur)
                cur.execute("""SELECT case_id, query, status, event_verified, active_run, updated_at
                               FROM cases WHERE case_file IS NOT NULL ORDER BY updated_at DESC""")
                rows = cur.fetchall()
            conn.commit()
        return [{"case_id": r[0], "query": r[1], "status": r[2], "event_verified": r[3], "run_number": r[4],
                 "updated_at": r[5].isoformat() if r[5] else None} for r in rows]

    def save(self, report: CaseEvidenceReport, timeline: List[dict]) -> Dict[str, int]:
        """Store the full Case File and replace this run's Heimdall rows, in one transaction."""
        case_id, v, run = report.case_id, report.event_verification, report.run_number
        facts = {f.fact_id: f for f in report.facts}
        assess = {a.fact_id: a for a in report.fact_assessments}
        doc_ids = [d.doc_id for d in report.retrieved_documents]
        details = v.summary + "\n" + "\n".join(f"- {r}" for r in v.reasoning)
        verified = event_verified(report)

        claim_rows = []
        for fid in scoped_claim_fact_ids(report):
            f, a = facts[fid], assess[fid]
            claim_rows.append((
                f"{case_id[:38]}:H{run}:{fid}", case_id, AGENT, 1, run, f.statement, "SOURCED_FACT",
                (a.countries or ["general"])[0], (a.commodities or ["general"])[0], None,
                f"{f.numeric_value:g} {f.unit or ''}".strip() if f.numeric_value is not None else None,
                Json([a.citation]), Json([f.source_ref.text_snippet or ""]), "PENDING",
                f"assertion={f.assertion_status.value if f.assertion_status else 'REPORTED'}; "
                f"tier={f.reliability_tier}; credibility={a.credibility}; "
                f"independent_sources={a.independent_source_count}; category={f.category.value}",
            ))

        with self.client.get_connection() as conn:
            with conn.cursor() as cur:
                self._ensure_schema(cur)
                cur.execute("""
                    INSERT INTO cases (case_id, query, as_of_date, status, event_verified, verification_details,
                                       active_run, retrieved_documents, timeline, case_file, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (case_id) DO UPDATE SET
                        query = EXCLUDED.query, as_of_date = EXCLUDED.as_of_date, status = EXCLUDED.status,
                        event_verified = EXCLUDED.event_verified,
                        verification_details = EXCLUDED.verification_details, active_run = EXCLUDED.active_run,
                        retrieved_documents = EXCLUDED.retrieved_documents, timeline = EXCLUDED.timeline,
                        case_file = EXCLUDED.case_file, updated_at = NOW()
                """, (case_id, report.target_query, report.as_of_date,
                      "EVENT_VERIFIED" if verified else "EVENT_REJECTED", verified, details, run,
                      Json(doc_ids), Json(timeline), Json(report.model_dump(mode="json"))))
                cur.execute("DELETE FROM case_documents WHERE case_id = %s", (case_id,))
                execute_values(cur, "INSERT INTO case_documents (case_id, doc_id) VALUES %s "
                                    "ON CONFLICT DO NOTHING", [(case_id, d) for d in doc_ids])
                cur.execute("DELETE FROM claims WHERE case_id = %s AND agent = %s AND run_num = %s",
                            (case_id, AGENT, run))
                execute_values(cur, """
                    INSERT INTO claims (claim_id, case_id, agent, round_num, run_num, statement, claim_type,
                                        country, sector, bound_type, numerical_estimate, citations,
                                        citation_snippets, status, ruling_notes) VALUES %s""", claim_rows)
                cur.execute("""DELETE FROM audit_log WHERE case_id = %s AND agent = %s
                               AND (details ~ %s OR (%s = 1 AND details !~ '"run_number": '))""",
                            (case_id, AGENT, f'"run_number": {run}[,}}]', run))
                execute_values(cur, "INSERT INTO audit_log (case_id, agent, action, details) VALUES %s", [
                    (case_id, AGENT, t["phase"][:64], json.dumps(t, ensure_ascii=False)) for t in timeline])
            conn.commit()
        return {"cases": 1, "case_documents": len(doc_ids), "claims": len(claim_rows), "audit_log": len(timeline)}
