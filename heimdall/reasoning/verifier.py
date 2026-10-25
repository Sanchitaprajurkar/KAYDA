"""Event verification engine to validate disruptions and weed out fake decoys."""

from typing import List, Optional
from heimdall.config import settings
from heimdall.models.case_file import EventVerification, EventStatus
from heimdall.models.document import ParsedDocument
from heimdall.models.evidence import ExtractedFact


class EventVerifier:
    """Verifies that a disruption event is active and genuine as of the cutoff date."""

    def __init__(self, as_of_date: Optional[str] = None):
        self.as_of_date = as_of_date or settings.AS_OF_DATE

    def verify_event(
        self,
        event_id: str,
        event_name: str,
        documents: List[ParsedDocument],
        facts: List[ExtractedFact],
    ) -> EventVerification:
        """Inspect evidence to confirm event authenticity and active state."""
        supporting_docs: List[str] = []
        counter_or_decoy_docs: List[str] = []

        # Tally evidence from high-credibility sources (Tiers 1 & 2)
        tier1_2_confirmations = 0
        retractions_found = 0

        for doc in documents:
            meta = doc.manifest_meta
            if not meta:
                continue

            # Check temporal clock validity
            if not meta.is_valid_as_of(self.as_of_date):
                counter_or_decoy_docs.append(doc.doc_id)
                continue

            tier = meta.reliability_tier
            # Search for corridor collapse / closure keywords
            full_lower = doc.full_text.lower()
            if any(term in full_lower for term in ["corridor collapse", "agreement ended", "deal lapsed", "transit halted", "ships turned back", "suspension"]):
                supporting_docs.append(doc.doc_id)
                if tier in [1, 2]:
                    tier1_2_confirmations += 1

            if "retraction" in full_lower or "retracts" in full_lower or "false alarm" in full_lower:
                retractions_found += 1
                counter_or_decoy_docs.append(doc.doc_id)

        # Determine verification status
        if tier1_2_confirmations >= 2 and retractions_found == 0:
            status = EventStatus.VERIFIED_ACTIVE
            confidence = 0.98
            summary = (
                f"Disruption '{event_name}' ({event_id}) is confirmed active as of {self.as_of_date}. "
                f"Verified by {tier1_2_confirmations} Tier 1/2 official and wire documents without valid retractions."
            )
        elif tier1_2_confirmations >= 1:
            status = EventStatus.VERIFIED_ACTIVE
            confidence = 0.88
            summary = (
                f"Disruption '{event_name}' ({event_id}) is verified active based on official gazette / notice filings "
                f"as of {self.as_of_date}."
            )
        else:
            status = EventStatus.DISPUTED
            confidence = 0.60
            summary = f"Disruption evidence is inconclusive or contested as of {self.as_of_date}."

        return EventVerification(
            event_id=event_id,
            event_name=event_name,
            status=status,
            as_of_date=self.as_of_date,
            confidence_score=confidence,
            summary=summary,
            is_real_event=status == EventStatus.VERIFIED_ACTIVE,
            is_active_at_as_of=status == EventStatus.VERIFIED_ACTIVE,
            supporting_doc_ids=supporting_docs[:10],
            counter_or_decoy_doc_ids=counter_or_decoy_docs[:10],
        )
