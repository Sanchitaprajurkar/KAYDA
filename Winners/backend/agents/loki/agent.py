"""Loki in the courtroom: the case for limited exposure. Loki searches for substitute supply himself."""

import re
from typing import Dict, List, Optional, Tuple

from backend.agents.advocate import Advocate
from backend.agents.loki.prompts import LOKI_SYSTEM_PROMPT
from backend.court.display import cite
from backend.court.exposure import mitigation_analysis
from backend.court.models import AVAILABLE, NET_EXPOSURE, ROUTE_VALUE_DECLINE, Claim, Estimate
from backend.court.tools import SearchFilters


_MITIGATION = re.compile(r"alternativ|substitut|spot purchase|replac|rerout|rail|other supplier|stocks|reserve|"
                         r"adjusted|mitigat|bridge|shifted", re.I)
_SUPPLIER = re.compile(r"\bfrom ([A-Z][a-z]+)")


class CourtLoki(Advocate):
    side = "LOKI"
    prefix = "L"
    system_prompt = LOKI_SYSTEM_PROMPT
    mandate = "LOKI - the strongest opposing case; identifies counter-evidence, scope limits, and unverified assumptions"
    off_mandate = re.compile(r"more severe|understat|underestimat|worse than (?:claimed|stated)|no (?:real )?"
                             r"mitigation|mitigation (?:has )?failed|loss is (?:larger|greater)", re.I)
    attack_terms = "substitute alternative supply spot purchases stocks"
    defence_terms = "alternative supply substitute"

    def _evidence_claim(self, p, cell_est: Dict[str, Claim], run: int) -> Optional[Claim]:
        """A mitigation claim must say how much the mitigation replaces, or say that the record cannot tell."""
        claim = super()._evidence_claim(p, cell_est, run)
        if claim is None:
            return None
        text = claim.statement + " " + " ".join(e.excerpt for e in claim.citations)
        calc = cell_est.get(f"{claim.country}|{claim.sector}")
        a = calc.assessment if calc else None
        if not _MITIGATION.search(text) or not a:
            return claim
        sub, loss = a.substitution, a.quantities["route_value_loss"].value
        if sub.status == AVAILABLE and loss:
            claim.statement += (f" Quantified: {sub.note} against USD {loss:.1f}M lost on {a.route} ({a.period}), "
                                f"replacing {sub.value / loss * 100:.1f}% of the loss; this is the recorded-substitution "
                                f"scenario already in the range.")
        else:
            claim.statement += (f" Not quantified: {sub.note}. The evidence shows mitigation is happening but does not "
                                f"establish how much is supplied or what share of the USD {loss:.1f}M lost on "
                                f"{a.route} ({a.period}) it replaces; no lower bound rests on it.")
            claim.nature = "INFERENCE"
        return claim

    def opening_queries(self, report, run: int, remand: List[str]) -> List[Tuple[str, SearchFilters]]:
        s = report.case_scope
        event = s.event_id
        if run > 1:
            return self.remand_queries(report, remand, "alternative")
        out = []
        if getattr(report, "investigation", None) and report.investigation.spec.propositions:
            for prop in report.investigation.spec.propositions:
                for q in prop.contradict_queries[:2]:
                    out.append((q, SearchFilters(event_id=event, max_tier=3)))
        if not out or (getattr(report, "investigation", None) and report.investigation.spec.exposure_applicable):
            goods = " ".join(s.commodities)
            for c in [c for c in s.countries if c not in s.event_countries]:
                out.append((f"{c} {goods} imports alternative supply substitute suppliers",
                            SearchFilters(event_id=event, country=c)))
            out.append((f"stocks reserves rerouted rail road adjusted markets {goods}",
                        SearchFilters(event_id=event, max_tier=3)))
        return out[:6]

    def _interpretive_challenge(self, claim: Claim) -> Optional[str]:
        a = claim.assessment
        if a.substitution.status == "UNKNOWN":
            return (f"The Case File reports substitution for {a.country} {a.sector} "
                    f"({'; '.join(a.substitution.sources) or a.substitution.note}); the no-substitution figure is an "
                    f"upper bound, not the net exposure.")
        if a.low is not None and a.low < a.high:
            return (f"Measured substitute supply ({a.substitution.note}) is on the record; the no-substitution figure "
                    f"overstates the net exposure.")
        return None

    def cell_claim(self, report, country: str, sector: str, run: int) -> Optional[Claim]:
        """Loki's reading: the route decline is not the net loss. Substitute series Loki finds outside the Case File
        are requested, not used: both sides argue from the same validated data."""
        a = self._assessment(report, country, sector)
        if not a or a.high is None:
            return None
        cell = next(c for c in report.coverage_map if (c.country, c.sector) == (country, sector))
        found = [s.doc_id for s in self.tools.trade_series(self.side, country, sector)
                 if s.origin not in a.origins and s.doc_id not in cell.substitute_series]
        if found:
            self.log("retrieval", agent=self.side, detail=f"substitute series for {country} {sector} not in the Case "
                                                          f"File: {found}")
        vd = a.metrics[ROUTE_VALUE_DECLINE]
        sub = a.substitution
        reports = [e for e in (self.tools.paragraph_evidence(x) for x in sub.sources) if e]
        points = [f"The decline on {a.route} is not in dispute: trade value fell by {vd.value:.2f}% ({a.period})."]
        estimate = Estimate(low=vd.value, high=vd.value, metric=ROUTE_VALUE_DECLINE, unit=vd.unit,
                            basis="net exposure not established")
        if a.low is not None and a.low < a.high - 0.005:
            points.append(f"But replacement supply is measured ({sub.note}): on the recorded-substitution scenario net "
                          f"exposure is {a.low:.2f}% of the route's baseline value, and the {a.high:.2f}% headline is "
                          f"the no-substitution case.")
            estimate = Estimate(low=a.low, high=a.low, metric=NET_EXPOSURE, unit=a.metrics[NET_EXPOSURE].unit,
                                basis=a.range_basis, scenario="recorded_substitution")
        elif reports:
            quoted = "; ".join(f'"{e.excerpt}" ({cite(e)})' for e in reports[:2])
            points.append(f"The Case File reports replacement supply: {quoted}.")
            mitigation, extra = self._mitigation_points(report, a)
            points += mitigation
            reports += [e for e in extra if e.ref not in {r.ref for r in reports}]
        elif a.low is not None:
            points.append(f"Recorded substitutes did not rise ({sub.note}), but suppliers without a trade series are not "
                          f"measured; the figure is the loss on this route, not {country}'s loss of {sector.lower()} "
                          f"supply as a whole.")
        else:
            points.append(f"The Case File holds no measurement of replacement supply either way, so the net impact is "
                          f"not established: the {vd.value:.2f}% figure is the loss on one route, not {country}'s loss "
                          f"of {sector.lower()} supply as a whole.")
        if found:
            points.append(f"Loki asks for substitute series {', '.join(found)}, which are not yet in the Case File.")
        prior = self._prior_calc(country, sector, run) if run > 1 else None
        before = (prior.narrowed_from or prior.estimate) if prior else None
        changed = before and (before.metric, before.low, before.high) != (estimate.metric, estimate.low, estimate.high)
        lead = ("Following Odin's remand, new data in the Case File changes Loki's position. " if changed else
                "Following Odin's remand, the position stands. " if prior else "")
        reasoning = f"Run {run}: shared assessment of {a.route} for {a.period}; {a.range_basis}"
        return self._calc_claim(run, a, lead + " ".join(points), reasoning, requests=found, estimate=estimate,
                                extra_citations=reports[:4])

    def _mitigation_points(self, report, a) -> Tuple[List[str], List]:
        """Loki works through what decides the net loss, question by question, and says what the record cannot tell."""
        answers, suppliers = mitigation_analysis(self.tools, report, a)
        who = " and ".join(suppliers) or "other suppliers"
        loss = a.quantities["route_value_loss"].value
        lost_t = a.quantities["route_volume_loss"].value
        self.log("retrieval", agent=self.side, detail=f"mitigation review for {a.country} {a.sector}: " + "; ".join(
            f"{x['key']} {x['status']}" for x in answers))
        cites, said, silent = [], [], []
        for x in answers:
            if x["status"] == "NOT_ON_RECORD":
                silent.append(x["question"])
                continue
            refs = ", ".join(x["sources"][:2]) if x["status"] == "REPORTED" else "the substitute trade rows"
            said.append(f"{x['question']}: {x['status'].lower()} ({refs})")
            cites += [e for e in (self.tools.paragraph_evidence(s) for s in x["sources"][:2])
                      if e and any(w in e.excerpt.lower() for w in (a.country.lower(), a.sector.lower()))]
        out = [f"Mitigation from {who}, question by question."
               + (f" The record speaks to {'; '.join(said)}." if said else "")
               + (f" It is silent on {', '.join(silent)}." if silent else "")]
        lost = f"USD {loss:,.1f}M" + (f" ({lost_t:,.0f} tonnes)" if lost_t is not None else "")
        volume = next(x for x in answers if x["key"] == "volume")
        why = ("the volume figures on the record are reports or projections, not a validated trade series for this "
               "period, so they cannot be netted against the route loss" if volume["status"] == "REPORTED" else
               "nothing on the record measures how much is replaced")
        out.append(f"So the net impact cannot be quantified: of the {lost} lost on {a.route} ({a.period}), the share "
                   f"{who} replaces is unknown, because {why}. The "
                   f"{a.metrics[ROUTE_VALUE_DECLINE].value:.2f}% route decline is an agreed fact; treating it as "
                   f"{a.country}'s net loss of {a.sector.lower()} supply assumes zero replacement, which the record "
                   f"contradicts.")
        return out, cites
