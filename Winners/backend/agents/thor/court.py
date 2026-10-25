"""Thor in the courtroom: the case for high exposure, using Thor's own prompt and spot-premium assumption."""

from typing import List, Optional, Tuple

from backend.agents.advocate import Advocate
from backend.agents.thor.prompts import THOR_SYSTEM_PROMPT
from backend.court.models import Claim, Estimate
from backend.court.tools import SearchFilters

THOR_SPOT_PREMIUM_PCT = 12.0  # standard spot-price escalation assumption (from problem statement)


class CourtThor(Advocate):
    side = "THOR"
    prefix = "T"
    system_prompt = THOR_SYSTEM_PROMPT
    premium_pct = THOR_SPOT_PREMIUM_PCT

    def opening_queries(self, report, run: int, remand: List[str]) -> List[Tuple[str, SearchFilters]]:
        s = report.case_scope
        if run > 1:
            return self.remand_queries(report, remand, "shortfall")
        origins, goods = " ".join(s.event_countries), " ".join(s.commodities)
        importers = " ".join(c for c in s.countries if c not in s.event_countries)
        event = s.event_id
        return [
            (f"{origins} {goods} exports loss collapse shortfall {importers}", SearchFilters(event_id=event, max_tier=3)),
            (f"capacity limit bottleneck delays congestion {goods}", SearchFilters(event_id=event, max_tier=2)),
            (f"prices rise premium cost {goods} {importers}", SearchFilters(event_id=event, max_tier=3)),
        ]

    def cell_claim(self, report, country: str, sector: str, run: int) -> Optional[Claim]:
        """Thor uses only the substitutes on the record: he does not go looking for mitigation."""
        cell = next(c for c in report.coverage_map if (c.country, c.sector) == (country, sector))
        primary = [self.tools.series(d) for d in cell.primary_series]
        substitutes = [self.tools.series(d) for d in cell.substitute_series]
        calcs = self._calc_windows(report, country, sector, primary, substitutes)
        if not calcs:
            return None
        worst = max(calcs, key=lambda c: c.gross_loss_pct)
        central = next((c for c in calcs if c.window == "full"), worst)
        # Both bounds use the same denominator: the total import basket (primary + substitute baseline).
        # low = net_import_loss_pct  — best case, substitutes fully materialise.
        # high = gross_import_loss_pct — worst case, no substitution.
        # spot premium is a separate observation, not folded into either bound.
        low = central.net_import_loss_pct
        high = max(c.gross_import_loss_pct for c in calcs)
        origins = "/".join(report.case_scope.event_countries)
        subs = sorted({x.origin for x in substitutes if x})
        statement = (f"{country} has lost {worst.gross_loss_pct:.1f}% of its {sector.lower()} imports from {origins} "
                     f"({', '.join(worst.months)} vs a year earlier); "
                     + (f"even after recorded substitutes from {', '.join(subs)}, at least {low:.1f}% "
                        f"of the total import basket is gone" if subs else
                        f"over the full months after onset the loss is {low:.1f}% of the total import basket "
                        f"and no substitute supply is on the record")
                     + f". A spot-price premium of {self.premium_pct:g}% is separately observed.")
        cites = []
        for c in calcs:
            cites += [e for e in self.tools.row_evidence(c) if e.ref not in {x.ref for x in cites}]
        return Claim(claim_id=self._next_id(run), side=self.side, run=run, country=country, sector=sector,
                     kind="calculation", statement=statement,
                     estimate=Estimate(low=round(min(low, high), 2), high=round(max(low, high), 2),
                                       baseline=f"same months of {worst.baseline_year}"),
                     nature="INFERENCE",
                     reasoning=f"TradeCalculator over {', '.join(cell.primary_series + cell.substitute_series)}; "
                               f"low = net_import_loss_pct, high = gross_import_loss_pct (both / total import basket); "
                               f"the {self.premium_pct:g}% spot premium is separately cited, not in either bound.",
                     citations=cites[:12], calculations=calcs)
