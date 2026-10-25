from typing import List
from app.models.case import AgentRole, Claim, ClaimType, ClaimStatus, Attack, Defense
from app.agents.base import BaseAgent

class LokiAgent(BaseAgent):
    def __init__(self):
        super().__init__(role=AgentRole.LOKI)

    def generate_round1_claims(self, as_of_date: str, run_num: int = 1) -> List[Claim]:
        """
        FR3.1 & FR3.2: Generates limited exposure claims with Runemark citations.
        Emphasizes mitigation, routing substitutions, and low bounds.
        """
        self.log_action("ROUND1_SUBMIT", f"Submitting Limited Exposure claims for Run {run_num}")

        claims = []

        # Claim 1: Midgard Wheat - Rail & Vanir Substitution
        claims.append(Claim(
            claim_id=f"LK-R{run_num}-01",
            agent=AgentRole.LOKI,
            round_num=1,
            run_num=run_num,
            statement="Midgard wheat exposure is limited to 15-25% as flour millers successfully split orders between Vanir parcels and Ravik rail.",
            claim_type=ClaimType.SOURCED_FACT,
            country="Midgard",
            sector="Wheat",
            bound_type="LOW",
            numerical_estimate="15% to 25% net exposure",
            citations=["ORV-0006", "ORV-0001"],
            citation_snippets=[
                "[ORV-0006 P1] Midgard's flour millers are booking wheat from Vanir and asking for more rail capacity from Ravik.",
                "[ORV-0006 P5] Millers say the arrangement is workable for now. The ministry has not changed its guidance on stock levels.",
                "[ORV-0001 P1] Vantro Trading has shifted part of its Orvan wheat business to the Ravik Rail Link."
            ],
            status=ClaimStatus.PENDING
        ))

        # Claim 2: Midgard Maize - Domestic Inventory & Coarse Grain Blends
        claims.append(Claim(
            claim_id=f"LK-R{run_num}-02",
            agent=AgentRole.LOKI,
            round_num=1,
            run_num=run_num,
            statement="Midgard maize feed exposure is cushioned below 20% through alternative coarse grain feed reformulation and inland buffer reserves.",
            claim_type=ClaimType.INFERENCE,
            country="Midgard",
            sector="Maize",
            bound_type="LOW",
            numerical_estimate="12% to 20% net exposure",
            citations=["ORV-0006", "ATL-0005"],
            citation_snippets=[
                "[ORV-0006 P5] Ministry has maintained stock level guidance without declaring emergency rations.",
                "[ATL-0005 P3] Feed processors maintain flexible blending formulas for grain substitution."
            ],
            status=ClaimStatus.PENDING
        ))

        # Claim 3: Tolan Limited Impact - Terrestrial Rerouting
        claims.append(Claim(
            claim_id=f"LK-R{run_num}-03",
            agent=AgentRole.LOKI,
            round_num=1,
            run_num=run_num,
            statement="Tolan grain exposure is mitigated to 18-28% as buyers utilize secondary regional overland agreements.",
            claim_type=ClaimType.INFERENCE,
            country="Tolan",
            sector="Wheat",
            bound_type="LOW",
            numerical_estimate="18% to 28% net impact",
            citations=["ORV-0001", "ORV-0006"],
            citation_snippets=[
                "[ORV-0001 P3] Rail is a useful bridge for high-priority commitments.",
                "[ORV-0006 P5] Working capital adjustments and parcel splits preserve continuity."
            ],
            status=ClaimStatus.PENDING
        ))

        for c in claims:
            self.private_memory["hypotheses"].append(c.statement)

        return claims

    def generate_attack(self, thor_claims: List[Claim]) -> Attack:
        """
        FR3.3 & FR5.3: Attacks Thor's worst-case claims with economic counter-logic.
        """
        target = thor_claims[0]  # Target Thor's 62% collapse claim
        
        attack = Attack(
            attack_id="ATK-LK-01",
            attacker=AgentRole.LOKI,
            target_claim_id=target.claim_id,
            target_agent=AgentRole.THOR,
            argument=(
                "Thor conflates sea-berth transit drops with total commercial supply destruction. "
                "Document ORV-0006 proves millers find the arrangement 'workable' and the Ministry "
                "has NOT changed guidance on stock levels. Physical port delays do not equal net 60%+ commercial collapse."
            ),
            counter_citations=["ORV-0006", "ORV-0001"],
            counter_snippets=[
                "[ORV-0006 P5] Millers say the arrangement is workable for now but leaves them with less room to absorb a second disruption. The ministry has not changed its guidance on stock levels.",
                "[ORV-0001 P3] Rail is a useful bridge for high-priority shipments."
            ]
        )
        self.log_action("ATTACK_SUBMITTED", f"Attacked {target.claim_id}: {attack.argument}")
        return attack

    def defend_or_concede(self, attack: Attack, claim: Claim) -> Defense:
        """
        FR3.3: Answers Thor's attack with either defense or concession.
        """
        if "rail capacity" in attack.argument.lower() or "price premium" in attack.argument.lower():
            # Concede that rail cannot fully replace sea volume at parity cost
            defense = Defense(
                defense_id="DEF-LK-01",
                defender=AgentRole.LOKI,
                attack_id=attack.attack_id,
                target_claim_id=claim.claim_id,
                action="CONCEDE",
                reasoning=(
                    "Loki concedes that rail cannot match 100% of sea capacity and Vanir parcels carry premium freight costs. "
                    "However, Loki proves that commercial substitution cushions net exposure well below Thor's catastrophic 62% bound."
                ),
                new_citations=["ORV-0001", "ORV-0006"]
            )
            claim.status = ClaimStatus.CONCEDED
            self.private_memory["concessions_made"].append(claim.claim_id)
        else:
            defense = Defense(
                defense_id="DEF-LK-01",
                defender=AgentRole.LOKI,
                attack_id=attack.attack_id,
                target_claim_id=claim.claim_id,
                action="DEFEND",
                reasoning="Split orders and buffer stocks cushion physical delivery timing.",
                new_citations=["ORV-0006"]
            )
        self.log_action("DEFENSE_SUBMITTED", f"Action: {defense.action} on {claim.claim_id}")
        return defense
