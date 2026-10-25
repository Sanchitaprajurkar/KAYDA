"""Loki in the courtroom: the case for limited exposure. Loki searches for substitute supply himself."""

from typing import List, Optional, Tuple

from backend.agents.advocate import Advocate
from backend.agents.loki.prompts import LOKI_SYSTEM_PROMPT
from backend.court.models import Claim, Estimate
from backend.court.tools import SearchFilters


class CourtLoki(Advocate):
    side = "LOKI"
    prefix = "L"
    system_prompt = LOKI_SYSTEM_PROMPT
    premium_pct = 0.0

    def opening_queries(self, report, run: int, remand: List[str]) -> List[Tuple[str, SearchFilters]]:
        s = report.case_scope
        if run > 1:
            return self.remand_queries(report, remand, "alternative")
        goods = " ".join(s.commodities)
        event = s.event_id
        queries = [(f"{c} {goods} imports alternative supply substitute suppliers",
                    SearchFilters(event_id=event, country=c))
                   for c in s.countries if c not in s.event_countries]
        queries.append((f"stocks reserves rerouted rail road adjusted markets {goods}",
                        SearchFilters(event_id=event, max_tier=3)))
        return queries

    def cell_claim(self, report, country: str, sector: str, run: int) -> Optional[Claim]:
        cell = next(c for c in report.coverage_map if (c.country, c.sector) == (country, sector))
        primary = [self.tools.series(d) for d in cell.primary_series]
        origins = set(report.case_scope.event_countries)
        found = [s for s in self.tools.trade_series(self.side, country, sector) if s.origin not in origins]
        substitutes = list({s.doc_id: s for s in [self.tools.series(d) for d in cell.substitute_series] + found}
                           .values())
        if found:
            self.log("retrieval", agent=self.side, detail=f"substitute series for {country} {sector}: "
                                                          f"{[s.doc_id for s in found]}")
        calcs = self._calc_windows(report, country, sector, primary, substitutes)
        if not calcs:
            return None
        # Both bounds use the same denominator: the total import basket (primary + substitute baseline).
        # low = net_import_loss_pct  — best case, substitutes fully materialise.
        # high = gross_import_loss_pct — worst case, no substitution.
        low = min(c.net_import_loss_pct for c in calcs)
        high = max(c.gross_import_loss_pct for c in calcs)
        gross = max(c.gross_loss_pct for c in calcs)
        subs = sorted({s.origin for s in substitutes})
        prior_claim = next((c for c in self.claims.values() if c.kind == "calculation"
                            and (c.country, c.sector) == (country, sector) and c.run == run - 1), None)

        if run > 1 and prior_claim and subs:
            statement = (f"Following Odin's remand, substitute supply from {', '.join(subs)} ({', '.join(s.doc_id for s in substitutes)}) "
                         f"is now verified in the Case File. {country} lost only {low:.1f}-{high:.1f}% of its "
                         f"total recorded {sector.lower()} import basket, well below the {gross:.1f}% headline fall "
                         f"from {'/'.join(sorted(origins))}.")
            reasoning = (f"Run {run}: substitute series verified on remand confirms mitigation from {', '.join(subs)}; "
                         f"low = net_import_loss_pct, high = gross_import_loss_pct (both / total import basket).")
        elif run > 1 and prior_claim:
            statement = (f"Following Odin's remand, no alternative trade series was recorded for {country} {sector}; "
                         f"{country}'s {sector.lower()} import loss is {low:.1f}-{high:.1f}% of the total import basket "
                         f"depending on the window; the worst month is not the trend.")
            reasoning = (f"Run {run}: No substitute trade series on record for {country} {sector}; "
                         f"position maintained at {low:.1f}-{high:.1f}% based on seasonal window adjustment.")
        else:
            statement = (f"Net of substitute supply from {', '.join(subs)}, {country} lost only {low:.1f}-{high:.1f}% of its "
                         f"total recorded {sector.lower()} import basket, well below the {gross:.1f}% headline fall "
                         f"from {'/'.join(sorted(origins))}." if subs else
                         f"{country}'s {sector.lower()} import loss is {low:.1f}-{high:.1f}% of the total import basket "
                         f"depending on the window; the worst month is not the trend.")
            reasoning = (f"TradeCalculator over {', '.join(cell.primary_series)} net of "
                         f"{', '.join(s.doc_id for s in substitutes) or 'no substitutes'}; "
                         f"low = net_import_loss_pct, high = gross_import_loss_pct (both / total import basket).")

        cites = []
        for c in calcs:
            cites += [e for e in self.tools.row_evidence(c) if e.ref not in {x.ref for x in cites}]
        return Claim(claim_id=self._next_id(run), side=self.side, run=run, country=country, sector=sector,
                     kind="calculation", statement=statement,
                     estimate=Estimate(low=round(low, 2), high=round(high, 2),
                                       baseline=f"same months of {calcs[0].baseline_year}"),
                     nature="INFERENCE",
                     reasoning=reasoning,
                     citations=cites[:12], calculations=calcs)
