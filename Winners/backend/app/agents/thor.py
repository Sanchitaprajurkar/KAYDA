from typing import List
from app.models.case import AgentRole, Claim, ClaimType, ClaimStatus, Attack, Defense
from app.agents.base import BaseAgent

class ThorAgent(BaseAgent):
    def __init__(self):
        super().__init__(role=AgentRole.THOR)

    def generate_round1_claims(self, as_of_date: str, run_num: int = 1) -> List[Claim]:
        """
        FR2.1 & FR2.2: Generates worst-case high exposure claims with Runemark citations.
        """
        self.log_action("ROUND1_SUBMIT", f"Submitting High Exposure claims for Run {run_num}")

        claims = []

        # Claim 1: Midgard Wheat - Sea cargo collapse
        claims.append(Claim(
            claim_id=f"TH-R{run_num}-01",
            agent=AgentRole.THOR,
            round_num=1,
            run_num=run_num,
            statement="Midgard faces catastrophic wheat import deficits exceeding 60% due to sea corridor termination.",
            claim_type=ClaimType.SOURCED_FACT,
            country="Midgard",
            sector="Wheat",
            bound_type="HIGH",
            numerical_estimate="55% to 62% shortfall",
            citations=["ORV-0021", "ORV-0006"],
            citation_snippets=[
                "[ORV-0021 P1] Corvan Grain reports that its sea shipments of wheat and maize in October 2026 were 62% below the same month a year earlier.",
                "[ORV-0006 P2] The Realm Trade Ministry put the September port index at 40, against an old normal of 100."
            ],
            status=ClaimStatus.PENDING
        ))

        # Claim 2: Midgard Maize - Chokepoint & Feed Crisis
        claims.append(Claim(
            claim_id=f"TH-R{run_num}-02",
            agent=AgentRole.THOR,
            round_num=1,
            run_num=run_num,
            statement="Midgard livestock feed sector faces acute maize shortages with alternative rail capacity unable to replace bulk maritime volume.",
            claim_type=ClaimType.INFERENCE,
            country="Midgard",
            sector="Maize",
            bound_type="HIGH",
            numerical_estimate="45% to 55% deficit",
            citations=["ORV-0001", "ORV-0021"],
            citation_snippets=[
                "[ORV-0001 P2] The company says the rail link can take only a fraction of the volume that normally leaves Orvan Grain Port by sea.",
                "[ORV-0021 P1] Corvan Grain reports sea shipments of wheat and maize down 62%."
            ],
            status=ClaimStatus.PENDING
        ))

        # Claim 3: Tolan Exposure - Severe Secondary Shortfall
        claims.append(Claim(
            claim_id=f"TH-R{run_num}-03",
            agent=AgentRole.THOR,
            round_num=1,
            run_num=run_num,
            statement="Tolan grain reserves are depleted, leaving import flows exposed to 50%+ supply contraction without maritime access.",
            claim_type=ClaimType.INFERENCE,
            country="Tolan",
            sector="Wheat",
            bound_type="HIGH",
            numerical_estimate="50% to 58% import loss",
            citations=["ORV-0006", "ORV-0012"],
            citation_snippets=[
                "[ORV-0006 P5] Millers say the arrangement leaves them with less room to absorb a second disruption.",
                "[ORV-0012 P3] Regional processors report minimal secondary safety reserves."
            ],
            status=ClaimStatus.PENDING
        ))

        for c in claims:
            self.private_memory["hypotheses"].append(c.statement)

        return claims

    def generate_attack(self, loki_claims: List[Claim]) -> Attack:
        """
        FR2.3 & FR5.3: Cross-examines Loki's weakest claim with counter-evidence.
        """
        # Target Loki's claim on rail substitution
        target = next((c for c in loki_claims if "rail" in c.statement.lower()), loki_claims[0])
        
        attack = Attack(
            attack_id="ATK-TH-01",
            attacker=AgentRole.THOR,
            target_claim_id=target.claim_id,
            target_agent=AgentRole.LOKI,
            argument=(
                "Loki overstates rail mitigation. Vantro Trading explicitly confirmed that the Ravik Rail Link "
                "can handle 'only a fraction' of maritime bulk volumes, and Vanir wheat carries severe price "
                "premiums and limited parcel availability."
            ),
            counter_citations=["ORV-0001", "ORV-0006"],
            counter_snippets=[
                "[ORV-0001 P2] Rail link can take only a fraction of the volume that normally leaves Orvan Grain Port by sea.",
                "[ORV-0006 P7] Vanir wheat offers have been small and priced above Orvan's usual terms."
            ]
        )
        self.log_action("ATTACK_SUBMITTED", f"Attacked {target.claim_id}: {attack.argument}")
        return attack

    def defend_or_concede(self, attack: Attack, claim: Claim) -> Defense:
        """
        FR2.3: Answers Loki's attack with either defense or concession.
        """
        if "total physical cessation" in attack.argument.lower() or "not zero" in attack.argument.lower():
            # Concede physical absolute collapse, but maintain economic exposure
            defense = Defense(
                defense_id="DEF-TH-01",
                defender=AgentRole.THOR,
                attack_id=attack.attack_id,
                target_claim_id=claim.claim_id,
                action="CONCEDE",
                reasoning=(
                    "Thor concedes that emergency rail transport prevents absolute zero-volume physical starvation. "
                    "However, Thor maintains that commercial exposure remains severe due to higher logistics costs and 60%+ sea volume loss."
                ),
                new_citations=["ORV-0006"]
            )
            claim.status = ClaimStatus.CONCEDED
            self.private_memory["concessions_made"].append(claim.claim_id)
        else:
            defense = Defense(
                defense_id="DEF-TH-01",
                defender=AgentRole.THOR,
                attack_id=attack.attack_id,
                target_claim_id=claim.claim_id,
                action="DEFEND",
                reasoning="The official port index drop to 40 confirms that systemic replacement is impossible in the near term.",
                new_citations=["ORV-0021"]
            )
        self.log_action("DEFENSE_SUBMITTED", f"Action: {defense.action} on {claim.claim_id}")
        return defense
