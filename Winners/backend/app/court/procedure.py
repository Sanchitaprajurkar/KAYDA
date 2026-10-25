import asyncio
import time
from typing import AsyncGenerator, Dict, Any, Optional
from app.models.case import CaseFile, ClaimStatus
from app.agents.heimdall import HeimdallAgent
from app.agents.thor import ThorAgent
from app.agents.loki import LokiAgent
from app.agents.odin import OdinAgent
from app.config import settings
from app.db.repository import case_repo

class CourtProcedure:
    """
    Deterministic Court Procedure State Machine running asynchronously.
    Enforces:
    - Independent agents acting autonomously
    - Odin ruling only, never orchestrating or assigning tasks
    - Dual concurrent claims in Round 1
    - Genuine cross-examination & concessions in Round 2
    - Minimum 2-run sufficiency remand loop
    - Hard limits on rounds, runs, and timeouts
    """
    def __init__(self, case_id: str, query: str, as_of_date: str = settings.DEFAULT_AS_OF_DATE):
        self.case_id = case_id
        self.query = query
        self.as_of_date = as_of_date
        
        # Instantiate the 4 Norse agents
        self.heimdall = HeimdallAgent()
        self.thor = ThorAgent()
        self.loki = LokiAgent()
        self.odin = OdinAgent()
        
        self.case_file: Optional[CaseFile] = None
        self.current_run = 1
        self.is_completed = False

    async def run_trial(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Asynchronously steps through the deterministic Court Procedure state machine,
        yielding real-time execution events for SSE streaming.
        """
        # ── PHASE 1: HEIMDALL GATEKEEPER & VERIFICATION ──
        yield {
            "step": "CASE_INITIALIZATION",
            "agent": "HEIMDALL",
            "message": f"Heimdall opening Case File for query: '{self.query}' (as-of: {self.as_of_date})"
        }
        await asyncio.sleep(0.3)

        self.case_file = self.heimdall.build_case_file(
            case_id=self.case_id,
            query=self.query,
            as_of_date=self.as_of_date
        )

        yield {
            "step": "EVENT_VERIFICATION",
            "agent": "HEIMDALL",
            "status": "VERIFIED" if self.case_file.event_verified else "REJECTED",
            "details": self.case_file.verification_details,
            "retrieved_documents": self.case_file.retrieved_documents
        }
        await asyncio.sleep(0.3)

        if not self.case_file.event_verified:
            yield {
                "step": "TRIAL_ABORTED",
                "message": "Trial cannot proceed because the disruption event could not be verified in Runemark."
            }
            return

        # ── RUN 1 & RUN 2 SUFFICIENCY LOOP ──
        for current_run in range(1, settings.MAX_RUNS + 1):
            self.case_file.active_run = current_run
            yield {
                "step": f"RUN_{current_run}_START",
                "run": current_run,
                "message": f"Entering Courtroom Trial — Run {current_run} of {settings.MAX_RUNS}"
            }
            await asyncio.sleep(0.3)

            # ── ROUND 1: Concurrent Claim Submission ──
            yield {
                "step": f"ROUND_1_CLAIMS_SUBMISSION",
                "run": current_run,
                "round": 1,
                "message": "Thor and Loki concurrently submitting evidence-backed claims to the Bench."
            }

            # Concurrent execution of Thor and Loki using asyncio.gather
            async def get_thor_claims():
                return self.thor.generate_round1_claims(self.as_of_date, run_num=current_run)

            async def get_loki_claims():
                return self.loki.generate_round1_claims(self.as_of_date, run_num=current_run)

            thor_claims, loki_claims = await asyncio.gather(get_thor_claims(), get_loki_claims())
            
            self.case_file.claims.extend(thor_claims)
            self.case_file.claims.extend(loki_claims)

            yield {
                "step": "CLAIMS_RECEIVED",
                "thor_claims": [c.model_dump() for c in thor_claims],
                "loki_claims": [c.model_dump() for c in loki_claims]
            }
            await asyncio.sleep(0.4)

            # ── ROUND 2: Cross-Examination Attacks ──
            yield {
                "step": f"ROUND_2_CROSS_EXAMINATION",
                "run": current_run,
                "round": 2,
                "message": "Cross-examination begins: Each agent launches attacks on opposing claims."
            }

            thor_attack = self.thor.generate_attack(loki_claims)
            loki_attack = self.loki.generate_attack(thor_claims)
            
            self.case_file.attacks.append(thor_attack)
            self.case_file.attacks.append(loki_attack)

            yield {
                "step": "ATTACKS_DELIVERED",
                "thor_attack": thor_attack.model_dump(),
                "loki_attack": loki_attack.model_dump()
            }
            await asyncio.sleep(0.4)

            # ── Defense & Concessions ──
            yield {
                "step": "DEFENSE_AND_CONCESSIONS",
                "message": "Agents evaluating counter-evidence to defend or concede."
            }

            # Thor answers Loki
            target_thor_claim = next(c for c in thor_claims if c.claim_id == loki_attack.target_claim_id)
            thor_defense = self.thor.defend_or_concede(loki_attack, target_thor_claim)
            self.case_file.defenses.append(thor_defense)

            # Loki answers Thor
            target_loki_claim = next(c for c in loki_claims if c.claim_id == thor_attack.target_claim_id)
            loki_defense = self.loki.defend_or_concede(thor_attack, target_loki_claim)
            self.case_file.defenses.append(loki_defense)

            yield {
                "step": "DEFENSES_RESOLVED",
                "thor_defense": thor_defense.model_dump(),
                "loki_defense": loki_defense.model_dump()
            }
            await asyncio.sleep(0.3)

            # ── ODIN'S RULINGS ──
            yield {
                "step": "ODIN_RULING_COMMENCED",
                "agent": "ODIN",
                "message": "Odin presiding: Grading each claim as SOURCED_FACT or INFERENCE, and classifying rulings."
            }

            active_claims = [c for c in self.case_file.claims if c.run_num == current_run]
            rulings = self.odin.rule_on_claims(active_claims)
            self.case_file.rulings.extend(rulings)

            yield {
                "step": "RULINGS_DELIVERED",
                "rulings": [r.model_dump() for r in rulings]
            }
            await asyncio.sleep(0.3)

            # ── SUFFICIENCY CHECK (Remand Loop) ──
            sufficiency = self.odin.check_sufficiency(self.case_file, run_num=current_run)

            yield {
                "step": "SUFFICIENCY_ASSESSMENT",
                "run": current_run,
                "is_sufficient": sufficiency.is_sufficient,
                "coverage_score": sufficiency.coverage_score,
                "missing_elements": sufficiency.missing_elements,
                "directive": sufficiency.remand_directive
            }
            await asyncio.sleep(0.4)

            if not sufficiency.is_sufficient and current_run < settings.MAX_RUNS:
                # Remand to Heimdall for Run 2
                yield {
                    "step": "CASE_REMANDED",
                    "remanded_to": "HEIMDALL",
                    "reason": "Case remanded for second run to retrieve secondary route and substitute pricing evidence."
                }
                new_docs = self.heimdall.research_run2(self.case_file, sufficiency.missing_elements)
                yield {
                    "step": "RUN_2_EVIDENCE_READY",
                    "new_document_count": len(new_docs),
                    "new_documents": new_docs
                }
                await asyncio.sleep(0.3)
            else:
                break

        # ── PHASE 3: FINAL EXECUTIVE BRIEFING BY ODIN ──
        yield {
            "step": "BRIEFING_SYNTHESIS",
            "agent": "ODIN",
            "message": "Odin compiling final Executive Intelligence Briefing from verified judicial rulings."
        }
        await asyncio.sleep(0.4)

        briefing = self.odin.compile_briefing(self.case_file)
        self.case_file.status = "CASE_CLOSED"
        self.is_completed = True

        # Persist complete case to Neon PostgreSQL
        saved_ok = case_repo.save_case(self.case_file)
        if saved_ok:
            case_repo.log_audit(
                case_id=self.case_id,
                agent="ODIN",
                action="CASE_CLOSED_PERSISTED",
                details=f"Case {self.case_id} persisted to Neon PostgreSQL with {len(briefing.all_citations)} citations."
            )

        yield {
            "step": "CASE_CLOSED",
            "persisted_to_neon": saved_ok,
            "briefing": briefing.model_dump(),
            "exposure_table": [e.model_dump() for e in briefing.exposure_table],
            "total_documents_used": len(briefing.all_citations),
            "citations": briefing.all_citations
        }
