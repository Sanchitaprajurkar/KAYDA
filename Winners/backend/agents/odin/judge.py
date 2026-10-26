"""Odin's proposition-level adjudication: every proposition of the question gets an independent ruling.

The judge reads each piece of evidence for what it states, taken from Heimdall's per-item assessment of how it bears
on that proposition (one stance per item, so the same paragraph can never count for both sides), then applies its
own tests before letting it count:
  - reliability: only HIGH or MEDIUM reliability evidence can establish or reject;
  - assertion type: a forecast, allegation or rumour cannot establish what actually happened, and cannot refute an
    observation;
  - independence: a party's own publication shows what the party claims, not that the claim is true;
  - place: for an alleged incident, evidence must concern the place where it is alleged;
  - qualifying and context records establish neither the proposition nor its negation.
Absence of evidence is INSUFFICIENT, never a rejection. Nothing is called a hoax or decoy without evidence of
deliberate fabrication. Advocates' concessions and unpressed positions are recorded, not treated as findings.
No LLM is used, so nothing here can be invented. Nothing names an entity, event or case.
"""

import re
from typing import Dict, List, Optional, Tuple

from backend.court.models import Confidence, EvidenceRef, Locator, PropositionRuling

STRONG = ("HIGH", "MEDIUM")
NOT_PROOF_OF_FACT = ("FORECAST", "ALLEGATION", "RUMOUR")
INCIDENT_REFUTERS = ("OBSERVATION", "OFFICIAL_STATEMENT", "DENIAL", "CORRECTION")
_REPORTING = re.compile(r"\b(?:project(?:s|ed|ing)?|claim(?:s|ed|ing)?|state(?:s|d)?|says?|said|dispute(?:s|d)?|"
                        r"assert(?:s|ed)?|report(?:s|ed)?|allege(?:s|d)?|predict(?:s|ed|ing)?|forecast(?:s|ing)?|"
                        r"indicate(?:s|d)?|estimate(?:s|d)?)\b|,\s*\w+ing:", re.I)
_DECEPTION = re.compile(r"fabricat|hoax|\bfake\b|forged|doctored|deliberately false|disinformation|planted", re.I)
EVIDENCE_NEEDED = {
    "INCIDENT": "a direct record of the incident at its location: an official damage assessment, a port or site "
                "authority inspection or operational notice describing physical condition, or independent observation",
    "EVENT": "a direct, independent record that the event occurred, or an official confirmation or denial",
    "FORECAST": "observed data for the period the forecast covers, from a source independent of the forecaster",
    "CLAIM": "an independent record of the asserted fact (official statistics, customs or operational data), not "
             "the claimant's own statement",
}


def _words(text: str) -> List[str]:
    return [w for w in re.findall(r"\b[A-Z][a-z]{3,}\b", text or "")]


def _mentions(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text or "", re.I) is not None


class Judge:
    def __init__(self, store):
        self.store = store

    # -- what a piece of evidence is ------------------------------------------------------------------------------
    def _meta(self, doc_id: str) -> str:
        try:
            m = self.store.document(doc_id).manifest_meta
            return f"{m.source_name or ''} {m.title or ''}"
        except Exception:
            return ""

    def _party_source(self, item, prop) -> bool:
        """The claimant's own publication: it shows what the party claims, not that the claim is true. The party is
        the leading proper name of the attribution, matched in full and case-sensitively (not a common word)."""
        m = re.match(r"\s*((?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+)*)", prop.attributed_to or "")
        if not m:
            return False
        # The publisher, not a title that mentions the party (a rival's report can name it in its headline).
        return re.search(rf"\b{re.escape(m.group(1))}\b", item.source_name or "") is not None

    def _at_place(self, item, prop) -> bool:
        places = [m.group(0) for m in re.finditer(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+", prop.text)]
        if not places:
            return True
        return any(_mentions(f"{item.quote} {self._meta(item.doc_id)}", p) for p in places)

    @staticmethod
    def _ref(item, establishes: str, does_not: str) -> EvidenceRef:
        return EvidenceRef(
            source_id=item.doc_id,
            locator=Locator(paragraph=item.paragraph_number or None, page=item.page_number or None,
                            paragraph_index=item.paragraph_index or None),
            quote_or_value=item.quote,
            evidence_type={"SUPPORTS": "direct", "CONTRADICTS": "contradictory", "QUALIFIES": "circumstantial",
                           "CONTEXT": "contextual"}.get(item.stance, "contextual") if item.admissible
            else "unsupported_inference",
            epistemic_status={"OBSERVATION": "observed_fact", "FORECAST": "projection"}.get(item.assertion_type,
                                                                                          "reported_claim"),
            reliability_note=f"{item.reliability}: {item.reliability_reason}".strip(": "),
            establishes=establishes, does_not_establish=does_not)

    # -- one proposition ------------------------------------------------------------------------------------------
    def rule(self, prop, items, claims, attacks, responses, audit, case_items=(),
             argued_as: Optional[str] = None) -> PropositionRuling:
        uniq: Dict[Tuple, object] = {}
        for e in items:  # one entry per cited location, so a paragraph is never counted twice
            uniq.setdefault((e.doc_id, e.paragraph_number, e.admissible) if e.admissible else (e.doc_id, e.quote), e)
        items = list(uniq.values())
        # A party's claim needs a named claimant (a proper name), not a description such as a data source.
        about_claim = bool(re.match(r"\s*[A-Z][a-z]+", prop.attributed_to or "")) and bool(_REPORTING.search(prop.text))
        incident = prop.kind in ("INCIDENT", "EVENT")
        support, weak_support, contra, weak_contra, qual, aside, limits = [], [], [], [], [], [], []
        claimant_made_it = []
        for e in items:
            label = f"{e.citation} ({e.assertion_type.lower().replace('_', ' ')}, {e.source_name or e.doc_id})"
            if not e.admissible:
                aside.append(self._ref(e, f"that the claim was made ({label})",
                                       "that it is true: the source was set aside before trial"))
                continue
            party = self._party_source(e, prop)
            if party and e.stance == "SUPPORTS":
                claimant_made_it.append(e)
            if incident and e.stance in ("SUPPORTS", "CONTRADICTS") and not self._at_place(e, prop):
                qual.append(self._ref(e, f"something about another place ({label})",
                                      "anything about the place where the incident is alleged"))
                limits.append(f"{e.citation} concerns a different place")
                continue
            if e.stance == "SUPPORTS":
                why_weak = ("the claimant's own publication" if party else
                            f"a {e.assertion_type.lower()}" if e.assertion_type in NOT_PROOF_OF_FACT else
                            f"{e.reliability.lower()} reliability" if e.reliability not in STRONG else "")
                target = weak_support if why_weak else support
                target.append(self._ref(e, f"support for the proposition ({label})",
                                        f"independent proof: it is {why_weak}" if why_weak else
                                        "; ".join(e.limitations[:2])))
                if why_weak:
                    limits.append(f"{e.citation} cannot establish it on its own: {why_weak}")
            elif e.stance == "CONTRADICTS":
                why_weak = (f"a {e.assertion_type.lower()}" if e.assertion_type in NOT_PROOF_OF_FACT else
                            f"{e.reliability.lower()} reliability" if e.reliability not in STRONG else
                            "not a direct record of the incident" if incident and
                            e.assertion_type not in INCIDENT_REFUTERS else "")
                (weak_contra if why_weak else contra).append(
                    self._ref(e, f"evidence against the proposition ({label})",
                              f"a rejection on its own: it is {why_weak}" if why_weak else
                              "; ".join(e.limitations[:2])))
            elif e.stance == "QUALIFIES":
                qual.append(self._ref(e, f"a qualification ({label}): "
                                         + ("; ".join(e.limitations[:1]) or "it limits the proposition"),
                                      "the proposition, or that it is false"))
        classification, reasoning, level = self._decide(prop, support, weak_support, contra, weak_contra, qual)
        positions = self._positions(argued_as or prop.prop_id, claims, attacks, responses)
        if argued_as and argued_as != prop.prop_id:
            positions = {k: f"argued on {argued_as} as a whole: {v}" for k, v in positions.items()}
        attribution = None
        if about_claim:
            own = sorted({e.doc_id for e in list(case_items) + list(items)
                          if e.admissible and self._party_source(e, prop)})  # anywhere in the Case File
            attribution = (f"Established that {prop.attributed_to} made this claim: "
                           + "; ".join(sorted({e.citation for e in claimant_made_it})[:3]) if claimant_made_it else
                           f"{prop.attributed_to}'s own publications are in the record ({'; '.join(own[:3])}) but "
                           f"none was assessed as making this exact claim." if own else
                           f"No admissible publication by {prop.attributed_to} is in the record.")
            reasoning = ("This proposition reports a party's claim. Odin rules on whether what is claimed is borne "
                         "out by the evidence; whether the party made it is the attribution finding. " + reasoning)
        deception = self._deception(items, prop.kind, classification)
        exhausted = self._exhausted(prop, audit)
        needs = classification in ("INSUFFICIENT", "CONTESTED")
        return PropositionRuling(
            prop_id=prop.prop_id, proposition=prop.text, kind=prop.kind, classification=classification,
            supporting=support + weak_support, contradicting=contra + weak_contra, qualifying=qual, set_aside=aside,
            limitations=list(dict.fromkeys(limits))[:6], reasoning=reasoning + (
                f" Advocates: {'; '.join(f'{k}: {v}' for k, v in positions.items())}." if positions else ""),
            confidence=Confidence(level=level, explanation=self._confidence_note(classification, support, contra,
                                                                                 exhausted)),
            attribution=attribution, deception=deception, advocate_positions=positions,
            needs_investigation=needs,
            evidence_gap=(self._gap(classification, support, weak_support, contra, qual) if needs else ""),
            evidence_needed=EVIDENCE_NEEDED.get(prop.kind, EVIDENCE_NEEDED["CLAIM"]) if needs else "",
            reinvestigation=("" if not needs else
                             "Not requested: Heimdall's follow-up search for this proposition found no new admissible "
                             "evidence, so the corpus offers no reasonable prospect of resolving it." if exhausted else
                             "Not requested: Odin has no targeted evidence type for this proposition beyond the "
                             "searches Heimdall already ran; the gap is reported for the record."))

    @staticmethod
    def _decide(prop, support, weak_support, contra, weak_contra, qual) -> Tuple[str, str, str]:
        def sources(refs):
            return {r.source_id for r in refs}

        def strong(refs):
            direct = [r for r in refs if r.epistemic_status == "observed_fact" or "HIGH" in r.reliability_note]
            return len(sources(refs)) >= 2 or bool(direct)

        s_ok, c_ok = strong(support) if support else False, strong(contra) if contra else False
        if support and contra:
            return ("CONTESTED", f"Reliable evidence supports it ({len(sources(support))} source(s)) and reliable "
                                 f"evidence contradicts it ({len(sources(contra))} source(s)); the record does not "
                                 f"resolve the conflict.", "MEDIUM")
        if support and s_ok:
            return ("ESTABLISHED", f"Established by {len(sources(support))} reliable source(s) with no reliable "
                                   f"contradiction" + (f"; {len(sources(weak_contra))} weaker item(s) against it do "
                                                       f"not outweigh that" if weak_contra else "") + ".",
                    "HIGH" if len(sources(support)) >= 2 else "MEDIUM")
        if contra and c_ok:
            return ("REJECTED", f"Contradicted by {len(sources(contra))} reliable source(s) with no reliable support"
                                + (f"; {len(sources(weak_support))} weaker item(s) for it do not outweigh that"
                                   if weak_support else "") + ".",
                    "HIGH" if len(sources(contra)) >= 2 else "MEDIUM")
        parts = []
        if support:
            parts.append(f"one reliable source supports it without corroboration ({', '.join(sources(support))})")
        if contra:
            parts.append(f"one reliable source contradicts it without corroboration ({', '.join(sources(contra))})")
        if weak_support:
            parts.append(f"{len(weak_support)} item(s) for it cannot establish it (claimant's own statements, "
                         f"forecasts, allegations or low-reliability sources)")
        if weak_contra:
            parts.append(f"{len(weak_contra)} item(s) against it cannot reject it")
        if qual:
            parts.append(f"{len(qual)} record(s) qualify it without establishing it or its negation")
        if not parts:
            parts.append("no admissible evidence bears on it")
        return ("INSUFFICIENT", "Not established and not rejected: " + "; ".join(parts) + ". Absence of evidence is "
                                "not evidence that it is false.", "MEDIUM" if qual or weak_support else "LOW")

    @staticmethod
    def _confidence_note(classification, support, contra, exhausted) -> str:
        if classification == "INSUFFICIENT":
            return ("Confident only that the record cannot decide it" + ("; Heimdall's follow-up search found "
                                                                         "nothing more." if exhausted else "."))
        if classification == "CONTESTED":
            return "Both sides have reliable evidence; the conflict is unresolved."
        refs = support if classification == "ESTABLISHED" else contra
        return f"{len({r.source_id for r in refs})} independent reliable source(s) decide it."

    @staticmethod
    def _gap(classification, support, weak_support, contra, qual) -> str:
        if classification == "CONTESTED":
            return "Reliable evidence on both sides; a more authoritative or more direct record would resolve it."
        if support or contra:
            return "Only one reliable source bears on it; independent corroboration is missing."
        if weak_support:
            return "Only the claimant's own statements, forecasts or low-reliability material support it."
        if qual:
            return "Only records that qualify it (e.g. operating conditions); none establishes it or its negation."
        return "No admissible evidence bears on it."

    @staticmethod
    def _deception(items, kind: str, classification: str = "") -> str:
        """What the record shows about deliberate fabrication. A hoax or decoy is never inferred from missing
        evidence or unreliable sources: it needs evidence of deception."""
        hits = [e for e in items if e.admissible and _DECEPTION.search(e.quote or "")]
        if hits:
            return "Evidence bearing on deliberate fabrication: " + "; ".join(e.citation for e in hits[:3])
        if kind not in ("INCIDENT", "EVENT") or classification == "ESTABLISHED":
            return "No evidence of deliberate fabrication in the record."
        aside = sorted({e.doc_id for e in items if not e.admissible})
        return ("No evidence of deliberate fabrication; the allegation is unverified, not shown to be a hoax or decoy"
                + (f" (its only sources, {', '.join(aside)}, were set aside before trial as unreliable)" if aside
                   else "") + ".")

    @staticmethod
    def _exhausted(prop, audit) -> bool:
        rounds = [a for a in audit if a.get("proposition") == prop.prop_id]
        return len(rounds) > 1 and rounds[-1].get("kept", 0) == 0 or (len(rounds) == 1 and rounds[0].get("kept") == 0)

    @staticmethod
    def _positions(prop_id: str, claims, attacks, responses) -> Dict[str, str]:
        out = {}
        for c in claims:
            if not c.argument or c.argument.claim_id != prop_id:
                continue
            a = c.argument
            if c.status == "NOT_PRESSED":
                pos = "not pressed"
            else:
                pos = {"supports": "supports", "challenges": "challenges"}[a.position]
                if a.challenge_basis == "not_established":
                    pos += " as not established"
                elif a.challenge_basis == "evidence_against":
                    pos += " with evidence against"
                pos += f" ({len(a.evidence_refs)} reference(s), confidence {a.confidence.level})"
            hits = [x for x in attacks if x.target_claim_id == c.claim_id]
            acts = [r for r in responses if r.claim_id == c.claim_id]
            if hits:
                pos += "; attacked: " + ", ".join(sorted({x.attack_type or x.reason for x in hits}))
            if acts:
                pos += "; responded: " + ", ".join(r.action or r.decision for r in acts)
            if c.status in ("CONCEDED", "NARROWED"):
                pos += f"; {c.status.lower()} (an advocate action, not a finding)"
            out[c.side] = pos
        return out


def exposure_ruling(prop, ranges) -> Optional[PropositionRuling]:
    """An exposure proposition is decided by the coverage table: its cells' validated trade calculations."""
    cells = [r for r in ranges if _mentions(prop.text, r.country) and _mentions(prop.text, r.sector)] or \
        [r for r in ranges if _mentions(prop.text, r.country)] or list(ranges)
    if not cells:
        return None
    done = [r for r in cells if r.status == "COVERED" and r.odin]
    missing = [r for r in cells if r not in done]
    desc = "; ".join(f"{r.country} {r.sector}: " + (
        f"{'up to ' if r.odin[0] is None else ''}{r.odin[1]:.1f}% route value decline"
        + (" (net exposure not established: substitution unmeasured)" if r.odin[0] is None else "")
        if r in done else ("evidence missing" if r.status != "COVERED" else "no defensible range")) for r in cells)
    if done and not missing:
        cls, level = "ESTABLISHED", "MEDIUM" if any(r.odin[0] is None for r in done) else "HIGH"
    else:
        cls, level = "INSUFFICIENT", "MEDIUM"
    return PropositionRuling(
        prop_id=prop.prop_id, proposition=prop.text, kind=prop.kind, classification=cls,
        reasoning=f"Decided from the validated trade calculation per cell: {desc}.",
        confidence=Confidence(level=level, explanation=f"{len(done)} of {len(cells)} cell(s) have a range from "
                                                       f"validated trade rows."),
        limitations=[f"{r.country} {r.sector}: {r.basis}" for r in missing][:4],
        needs_investigation=bool(missing),
        evidence_gap=("; ".join(f"{r.country} {r.sector}" for r in missing) + ": no usable trade series")
        if missing else "",
        evidence_needed="a trade series for the missing flows" if missing else "",
        reinvestigation="Handled by the exposure send-back rules." if missing else "",
        deception="Not applicable.")
