import json
from typing import Optional, List, Dict, Any
from app.db.connection import db_manager
from app.models.case import CaseFile, Claim, Attack, Defense, Ruling, ExecutiveBriefing

class CaseRepository:
    """
    Data Access Layer for persisting and querying Courtroom Cases in Neon PostgreSQL.
    """
    @staticmethod
    def save_case(case_file: CaseFile) -> bool:
        """Saves or updates a complete CaseFile and all child entities atomically."""
        try:
            with db_manager.connection() as conn:
                with conn.cursor() as cur:
                    # 1. Upsert Case
                    cur.execute("""
                        INSERT INTO cases (
                            case_id, query, as_of_date, status, event_verified,
                            verification_details, active_run, active_round,
                            retrieved_documents, timeline, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (case_id) DO UPDATE SET
                            status = EXCLUDED.status,
                            event_verified = EXCLUDED.event_verified,
                            verification_details = EXCLUDED.verification_details,
                            active_run = EXCLUDED.active_run,
                            active_round = EXCLUDED.active_round,
                            retrieved_documents = EXCLUDED.retrieved_documents,
                            timeline = EXCLUDED.timeline,
                            updated_at = NOW();
                    """, (
                        case_file.case_id,
                        case_file.query,
                        case_file.as_of_date,
                        case_file.status,
                        case_file.event_verified,
                        case_file.verification_details,
                        case_file.active_run,
                        case_file.active_round,
                        json.dumps(case_file.retrieved_documents),
                        json.dumps(case_file.timeline)
                    ))

                    # 2. Upsert Claims
                    for c in case_file.claims:
                        cur.execute("""
                            INSERT INTO claims (
                                claim_id, case_id, agent, round_num, run_num, statement,
                                claim_type, country, sector, bound_type, numerical_estimate,
                                citations, citation_snippets, status, ruling_notes
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (claim_id) DO UPDATE SET
                                status = EXCLUDED.status,
                                ruling_notes = EXCLUDED.ruling_notes;
                        """, (
                            c.claim_id,
                            case_file.case_id,
                            c.agent.value,
                            c.round_num,
                            c.run_num,
                            c.statement,
                            c.claim_type.value,
                            c.country,
                            c.sector,
                            c.bound_type,
                            c.numerical_estimate,
                            json.dumps(c.citations),
                            json.dumps(c.citation_snippets),
                            c.status.value,
                            c.ruling_notes
                        ))

                    # 3. Upsert Attacks
                    for a in case_file.attacks:
                        cur.execute("""
                            INSERT INTO attacks (
                                attack_id, case_id, attacker, target_claim_id, target_agent,
                                argument, counter_citations, counter_snippets
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (attack_id) DO NOTHING;
                        """, (
                            a.attack_id,
                            case_file.case_id,
                            a.attacker.value,
                            a.target_claim_id,
                            a.target_agent.value,
                            a.argument,
                            json.dumps(a.counter_citations),
                            json.dumps(a.counter_snippets)
                        ))

                    # 4. Upsert Defenses
                    for d in case_file.defenses:
                        cur.execute("""
                            INSERT INTO defenses (
                                defense_id, case_id, defender, attack_id, target_claim_id,
                                action, reasoning, new_citations
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (defense_id) DO NOTHING;
                        """, (
                            d.defense_id,
                            case_file.case_id,
                            d.defender.value,
                            d.attack_id,
                            d.target_claim_id,
                            d.action,
                            d.reasoning,
                            json.dumps(d.new_citations)
                        ))

                    # 5. Insert Rulings
                    for r in case_file.rulings:
                        cur.execute("""
                            INSERT INTO rulings (
                                case_id, claim_id, ruling, claim_type, judge_rationale,
                                verified_citations, confidence_score
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """, (
                            case_file.case_id,
                            r.claim_id,
                            r.ruling.value,
                            r.claim_type.value,
                            r.judge_rationale,
                            json.dumps(r.verified_citations),
                            r.confidence_score
                        ))

                    # 6. Upsert Executive Briefing
                    if case_file.briefing:
                        b = case_file.briefing
                        cur.execute("""
                            INSERT INTO executive_briefings (
                                case_id, as_of_date, incident_name, executive_summary,
                                established_findings, contested_findings, conceded_findings,
                                exposure_table, next_quarter_outlook, stated_assumptions,
                                source_hygiene_report, all_citations, author
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (case_id) DO UPDATE SET
                                executive_summary = EXCLUDED.executive_summary,
                                established_findings = EXCLUDED.established_findings,
                                contested_findings = EXCLUDED.contested_findings,
                                conceded_findings = EXCLUDED.conceded_findings,
                                exposure_table = EXCLUDED.exposure_table,
                                next_quarter_outlook = EXCLUDED.next_quarter_outlook,
                                stated_assumptions = EXCLUDED.stated_assumptions,
                                source_hygiene_report = EXCLUDED.source_hygiene_report,
                                all_citations = EXCLUDED.all_citations;
                        """, (
                            case_file.case_id,
                            b.as_of_date,
                            b.incident_name,
                            b.executive_summary,
                            json.dumps(b.established_findings),
                            json.dumps(b.contested_findings),
                            json.dumps(b.conceded_findings),
                            json.dumps([e.model_dump() for e in b.exposure_table]),
                            b.next_quarter_outlook,
                            json.dumps(b.stated_assumptions),
                            json.dumps(b.source_hygiene_report),
                            json.dumps(b.all_citations),
                            b.author
                        ))

            return True
        except Exception as e:
            print(f"[Neon Repository] Error saving case {case_file.case_id}: {e}")
            return False

    @staticmethod
    def get_case(case_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a full case with claims, rulings, and briefing from Neon PostgreSQL."""
        try:
            with db_manager.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT case_id, query, as_of_date, status, event_verified,
                               verification_details, active_run, active_round,
                               retrieved_documents, timeline, created_at, updated_at
                        FROM cases WHERE case_id = %s;
                    """, (case_id,))
                    row = cur.fetchone()
                    if not row:
                        return None

                    case_data = {
                        "case_id": row[0],
                        "query": row[1],
                        "as_of_date": row[2],
                        "status": row[3],
                        "event_verified": row[4],
                        "verification_details": row[5],
                        "active_run": row[6],
                        "active_round": row[7],
                        "retrieved_documents": row[8] or [],
                        "timeline": row[9] or [],
                        "created_at": row[10].isoformat() if row[10] else None,
                        "updated_at": row[11].isoformat() if row[11] else None,
                        "claims": [],
                        "briefing": None
                    }

                    # Fetch claims
                    cur.execute("""
                        SELECT claim_id, agent, round_num, run_num, statement,
                               claim_type, country, sector, bound_type, numerical_estimate,
                               citations, citation_snippets, status, ruling_notes
                        FROM claims WHERE case_id = %s ORDER BY created_at;
                    """, (case_id,))
                    for c in cur.fetchall():
                        case_data["claims"].append({
                            "claim_id": c[0],
                            "agent": c[1],
                            "round_num": c[2],
                            "run_num": c[3],
                            "statement": c[4],
                            "claim_type": c[5],
                            "country": c[6],
                            "sector": c[7],
                            "bound_type": c[8],
                            "numerical_estimate": c[9],
                            "citations": c[10] or [],
                            "citation_snippets": c[11] or [],
                            "status": c[12],
                            "ruling_notes": c[13]
                        })

                    # Fetch briefing
                    cur.execute("""
                        SELECT as_of_date, incident_name, executive_summary,
                               established_findings, contested_findings, conceded_findings,
                               exposure_table, next_quarter_outlook, stated_assumptions,
                               source_hygiene_report, all_citations, author
                        FROM executive_briefings WHERE case_id = %s;
                    """, (case_id,))
                    b_row = cur.fetchone()
                    if b_row:
                        case_data["briefing"] = {
                            "case_id": case_id,
                            "as_of_date": b_row[0],
                            "incident_name": b_row[1],
                            "executive_summary": b_row[2],
                            "established_findings": b_row[3] or [],
                            "contested_findings": b_row[4] or [],
                            "conceded_findings": b_row[5] or [],
                            "exposure_table": b_row[6] or [],
                            "next_quarter_outlook": b_row[7],
                            "stated_assumptions": b_row[8] or [],
                            "source_hygiene_report": b_row[9] or {},
                            "all_citations": b_row[10] or [],
                            "author": b_row[11]
                        }

                    return case_data
        except Exception as e:
            print(f"[Neon Repository] Error fetching case {case_id}: {e}")
            return None

    @staticmethod
    def list_cases(limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """Returns list of recent cases ordered by creation timestamp."""
        try:
            with db_manager.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT case_id, query, as_of_date, status, event_verified, created_at
                        FROM cases ORDER BY created_at DESC LIMIT %s OFFSET %s;
                    """, (limit, offset))
                    return [
                        {
                            "case_id": row[0],
                            "query": row[1],
                            "as_of_date": row[2],
                            "status": row[3],
                            "event_verified": row[4],
                            "created_at": row[5].isoformat() if row[5] else None
                        }
                        for row in cur.fetchall()
                    ]
        except Exception as e:
            print(f"[Neon Repository] Error listing cases: {e}")
            return []

    @staticmethod
    def log_audit(case_id: str, agent: str, action: str, details: str = "") -> bool:
        """Records an agent action to the persistent audit log."""
        try:
            with db_manager.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO audit_log (case_id, agent, action, details)
                        VALUES (%s, %s, %s, %s);
                    """, (case_id, agent, action, details))
            return True
        except Exception as e:
            print(f"[Neon Repository] Audit log error: {e}")
            return False

case_repo = CaseRepository()
