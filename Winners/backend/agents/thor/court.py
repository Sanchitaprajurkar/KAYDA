"""Thor in the courtroom: the case for high exposure, using Thor's own prompt and spot-premium assumption."""

import re
from typing import List, Optional, Tuple

from backend.agents.advocate import Advocate
from backend.agents.thor.prompts import THOR_SYSTEM_PROMPT
from backend.court.display import fmt_span
from backend.court.models import ROUTE_VALUE_DECLINE, ROUTE_VOLUME_DECLINE, Claim
from backend.court.tools import SearchFilters


class CourtThor(Advocate):
    side = "THOR"
    prefix = "T"
    system_prompt = THOR_SYSTEM_PROMPT
    mandate = "THOR - the strongest supporting case; builds explicit evidence chains and establishes severity/impact"
    off_mandate = re.compile(r"not as severe|less severe|overstat|exaggerat|alternative supply (?:has been|was) found|"
                             r"prices (?:have )?(?:settled|eased|fallen)|loss is (?:limited|small|modest)|"
                             r"fully (?:replaced|offset)|well mitigated", re.I)
    attack_terms = "delays shortage capacity premium shortfall"
    defence_terms = "shortfall delays prices"

    def opening_queries(self, report, run: int, remand: List[str]) -> List[Tuple[str, SearchFilters]]:
        s = report.case_scope
        event = s.event_id
        if run > 1:
            return self.remand_queries(report, remand, "shortfall")
        out = []
        if getattr(report, "investigation", None) and report.investigation.spec.propositions:
            for prop in report.investigation.spec.propositions:
                for q in prop.support_queries[:2]:
                    out.append((q, SearchFilters(event_id=event, max_tier=3)))
        if not out or (getattr(report, "investigation", None) and report.investigation.spec.exposure_applicable):
            origins, goods = " ".join(s.event_countries), " ".join(s.commodities)
            importers = " ".join(c for c in s.countries if c not in s.event_countries)
            out.extend([
                (f"{origins} {goods} exports loss collapse shortfall {importers}", SearchFilters(event_id=event, max_tier=3)),
                (f"capacity limit bottleneck delays congestion {goods}", SearchFilters(event_id=event, max_tier=2)),
                (f"prices rise premium cost {goods} {importers}", SearchFilters(event_id=event, max_tier=3)),
            ])
        return out[:6]

    def _interpretive_challenge(self, claim: Claim) -> Optional[str]:
        a = claim.assessment
        if a.low is None:
            return (f"No trade series measures substitute supply for {a.country} {a.sector} ({a.substitution.note}); "
                    f"any mitigation Loki points to is unquantified and cannot lower the figure.")
        return (f"The recorded-substitution scenario assumes the measured substitute rise ({a.substitution.note}) "
                f"persists; without it the full no-substitution figure applies.")

    def cell_claim(self, report, country: str, sector: str, run: int) -> Optional[Claim]:
        """Thor's reading: the measured fall is large and broad, and nothing on the record shows it replaced."""
        a = self._assessment(report, country, sector)
        if not a or a.high is None:
            return None  # no defensible number: Thor files none
        vd = a.metrics[ROUTE_VALUE_DECLINE].value
        vol = a.metrics[ROUTE_VOLUME_DECLINE].value
        points = [f"On {a.route}, trade value fell by {vd:.2f}% ({a.period})"
                  + (f" and volume by {vol:.2f}%" if vol is not None else "") + "."]
        if vol is not None and vol > vd:
            points.append(f"Volume fell further than value ({vol:.2f}% against {vd:.2f}%), so the physical shortfall "
                          f"is larger than the value figure shows.")
        below, total = self._months_below(a)
        if total > 1 and below == total:
            points.append(f"Every month of the period is below its year-earlier level, so this is a sustained "
                          f"disruption, not a single bad month.")
        sub = a.substitution
        if a.low is None:
            points.append(f"Replacement supply is not measured ({sub.note}), so none of the loss has been shown to be "
                          f"replaced: the potential impact remains up to {a.high:.2f}% of the route's baseline value.")
        elif abs(a.low - a.high) < 0.005:
            points.append(f"Recorded substitutes did not rise ({sub.note}): net exposure is the full {a.high:.2f}% of the "
                          f"route's baseline value.")
        else:
            points.append(f"Even after measured substitute supply ({sub.note}), {a.low:.2f}% of the route's baseline "
                          f"value is still unreplaced, and {a.high:.2f}% if that substitution does not hold.")
        prior = self._prior_calc(country, sector, run) if run > 1 else None
        before = (prior.narrowed_from or prior.estimate) if prior else None  # compare like with like: as filed
        span = fmt_span((a.low, a.high), 2)
        if before and (before.low, before.high) != (a.low, a.high):
            lead = "Following Odin's remand, new data in the Case File changes the assessment, revising net exposure. "
            reasoning = (f"Revised in Run {run}: net exposure moved from "
                         f"{fmt_span((before.low, before.high), 2)} to {span} ({a.range_basis})")
        elif prior:
            lead = "Following Odin's remand, no new data changes the figures, so Thor maintains his reading of them. "
            reasoning = f"Maintained in Run {run} at {span}: the re-search added no data for this cell ({a.range_basis})"
        else:
            lead = ""
            reasoning = f"Shared assessment of {a.route} for {a.period}: {a.range_basis}"
        return self._calc_claim(run, a, lead + " ".join(points), reasoning)
