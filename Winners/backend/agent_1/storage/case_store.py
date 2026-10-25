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

    @property
    def enabled(self) -> bool:
        return self.client.is_configured

    def save(self, report: CaseEvidenceReport, timeline: List[dict]) -> Dict[str, int]:
        """Replace this case's Heimdall rows in one transaction."""
        case_id, v = report.case_id, report.event_verification
        facts = {f.fact_id: f for f in report.facts}
        assess = {a.fact_id: a for a in report.fact_assessments}
        doc_ids = [d.doc_id for d in report.retrieved_documents]
        details = v.summary + "\n" + "\n".join(f"- {r}" for r in v.reasoning)
        verified = event_verified(report)

        claim_rows = []
        for fid in scoped_claim_fact_ids(report):
            f, a = facts[fid], assess[fid]
            claim_rows.append((
                f"{case_id[:40]}:H:{fid}", case_id, AGENT, 1, 1, f.statement, "SOURCED_FACT",
                (a.countries or ["general"])[0], (a.commodities or ["general"])[0], None,
                f"{f.numeric_value:g} {f.unit or ''}".strip() if f.numeric_value is not None else None,
                Json([a.citation]), Json([f.source_ref.text_snippet or ""]), "PENDING",
                f"assertion={f.assertion_status.value if f.assertion_status else 'REPORTED'}; "
                f"tier={f.reliability_tier}; credibility={a.credibility}; "
                f"independent_sources={a.independent_source_count}; category={f.category.value}",
            ))

        with self.client.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO cases (case_id, query, as_of_date, status, event_verified, verification_details,
                                       retrieved_documents, timeline, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (case_id) DO UPDATE SET
                        query = EXCLUDED.query, as_of_date = EXCLUDED.as_of_date, status = EXCLUDED.status,
                        event_verified = EXCLUDED.event_verified,
                        verification_details = EXCLUDED.verification_details,
                        retrieved_documents = EXCLUDED.retrieved_documents, timeline = EXCLUDED.timeline,
                        updated_at = NOW()
                """, (case_id, report.target_query, report.as_of_date,
                      "EVENT_VERIFIED" if verified else "EVENT_REJECTED", verified, details,
                      Json(doc_ids), Json(timeline)))
                cur.execute("DELETE FROM case_documents WHERE case_id = %s", (case_id,))
                execute_values(cur, "INSERT INTO case_documents (case_id, doc_id) VALUES %s "
                                    "ON CONFLICT DO NOTHING", [(case_id, d) for d in doc_ids])
                cur.execute("DELETE FROM claims WHERE case_id = %s AND agent = %s", (case_id, AGENT))
                execute_values(cur, """
                    INSERT INTO claims (claim_id, case_id, agent, round_num, run_num, statement, claim_type,
                                        country, sector, bound_type, numerical_estimate, citations,
                                        citation_snippets, status, ruling_notes) VALUES %s""", claim_rows)
                cur.execute("DELETE FROM audit_log WHERE case_id = %s AND agent = %s", (case_id, AGENT))
                execute_values(cur, "INSERT INTO audit_log (case_id, agent, action, details) VALUES %s", [
                    (case_id, AGENT, t["phase"][:64], json.dumps(t, ensure_ascii=False)) for t in timeline])
            conn.commit()
        return {"cases": 1, "case_documents": len(doc_ids), "claims": len(claim_rows), "audit_log": len(timeline)}
