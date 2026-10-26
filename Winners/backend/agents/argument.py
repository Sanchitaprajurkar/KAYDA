"""Shared argument interface for Thor and Loki over Heimdall's investigation Case File.

Both sides argue the same Heimdall propositions (claim IDs P1, P2, ...) from Heimdall's own assessment of each
evidence item (its stance, assertion type, reliability and limitations). Arguments and attacks are assembled
deterministically from that assessment: an advocate cannot cite a paragraph for more than Heimdall found it shows, and
cannot restate evidence in words the source does not use. Quotes, locators and reliability notes are copied from the
Case File, and every reference passes validate_refs() before it is filed.

What carries a position:
  Thor (supports)            items Heimdall assessed as SUPPORTING the proposition
  Loki, evidence against     items Heimdall assessed as CONTRADICTING it
  Loki, not established      no supporting item exists; items that QUALIFY it are cited for what they show, and the
                             argument says absence of evidence is not evidence of falsity
Context items never carry a position. A side with nothing to carry it does not press it.

Nothing here names an entity, event or case: behaviour is driven by the investigation spec.
"""

import re
from typing import List, Literal, Optional, Tuple

from pydantic import BaseModel

from backend.court.models import (ATTACK_TYPE_REASON, Attack, ClaimArgument, Confidence, EvidenceRef, Locator,
                                  Revision)

Side = Literal["THOR", "LOKI"]

# How each kind of proposition is argued; chosen from the investigation spec, never from entities.
STRATEGY_NOTES = {
    "INCIDENT": ("Incident verification: only evidence of the incident itself at its location establishes it. "
                 "Operating records there qualify the allegation; they do not by themselves prove nothing happened. "
                 "A set-aside source shows the claim was made, not that it is true."),
    "EVENT": ("Event verification: only evidence of the event itself establishes it. Operating records qualify it; "
              "a set-aside source shows the claim was made, not that it is true."),
    "FORECAST": ("Forecast evaluation: the forecast's own publication shows what was projected, not that it came "
                 "true; observed data for the same period is what tests it."),
    "CLAIM": ("Competing claims: each figure belongs to whoever asserts it; observed records decide how far a "
              "party's claim is borne out."),
    "EXPOSURE": ("Exposure analysis: the figures come from the shared trade calculation; this argument covers only "
                 "what the narrative evidence adds."),
}

_EPISTEMIC = {"OBSERVATION": "observed_fact", "FORECAST": "projection", "OFFICIAL_STATEMENT": "reported_claim",
              "ALLEGATION": "reported_claim", "RUMOUR": "reported_claim", "REPORT": "reported_claim",
              "DENIAL": "reported_claim", "CORRECTION": "reported_claim"}
CARRYING = ("direct", "corroborating")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("’", "'").replace("‘", "'")).strip().lower()


def strategy_label(spec) -> str:
    return "+".join(spec.investigation_types or []) or "UNSPECIFIED"


# -- Case File evidence -> references ---------------------------------------------------------------------------------
def item_ref(item, evidence_type: str) -> EvidenceRef:
    """An EvidenceRef copied from a Heimdall evidence item: quote, locator, reliability and limitations are Heimdall's."""
    note = f"Heimdall: {item.reliability} reliability"
    if item.reliability_reason:
        note += f" - {item.reliability_reason}"
    if not item.admissible:
        note += " (set aside before trial; inadmissible)"
    shows = {"SUPPORTS": "supports", "CONTRADICTS": "contradicts", "QUALIFIES": "qualifies",
             "CONTEXT": "gives context to"}[item.stance]
    return EvidenceRef(
        source_id=item.doc_id,
        locator=Locator(paragraph=item.paragraph_number or None, page=item.page_number or None,
                        paragraph_index=item.paragraph_index if item.paragraph_index else None),
        quote_or_value=item.quote, evidence_type=evidence_type,
        epistemic_status=_EPISTEMIC.get(item.assertion_type, "reported_claim"), reliability_note=note,
        establishes=(f"Heimdall assessed this {item.assertion_type.lower().replace('_', ' ')} by "
                     f"{item.source_name or item.doc_id} as one that {shows} the proposition"),
        does_not_establish="; ".join(item.limitations[:2]))


def _type(item, carries: bool) -> str:
    if not item.admissible:
        return "unsupported_inference"
    if carries:
        return "direct" if item.assertion_type in ("OBSERVATION", "OFFICIAL_STATEMENT", "DENIAL", "CORRECTION") \
            else "corroborating"
    return {"QUALIFIES": "circumstantial", "CONTEXT": "contextual"}.get(item.stance, "contradictory")


# -- citation integrity -----------------------------------------------------------------------------------------------
class CitationFailure(BaseModel):
    where: str
    source_id: str
    locator: str
    reason: str


def validate_refs(refs: List[EvidenceRef], report, tools, where: str) -> Tuple[List[EvidenceRef], List[CitationFailure]]:
    """Keep only references that resolve: the source is in the Case File, the locator exists for it, and the quote
    or value appears in that paragraph or row (whitespace-normalised)."""
    inv = report.investigation
    case_sources = {d.doc_id for d in report.retrieved_documents} | {s.doc_id for s in report.trade_series}
    case_sources |= {e.doc_id for e in (inv.evidence if inv else [])}
    set_aside = {e.doc_id for e in (inv.evidence if inv else []) if not e.admissible}
    kept, failed = [], []
    for r in refs:
        why = None
        if r.source_id not in case_sources:
            why = "source is not in the Case File"
        elif r.locator.row:
            series = tools.series(r.source_id)
            row = next((x for x in (series.rows if series else []) if x.row_id == r.locator.row), None)
            if row is None:
                why = f"row {r.locator.row} does not exist in {r.source_id}"
            elif _norm(r.quote_or_value) not in _norm(row.text) and not _value_matches(r.quote_or_value, row):
                why = "value does not appear in the cited row"
        elif r.source_id in set_aside:
            # Set-aside documents are recorded by Heimdall at document level (no paragraph exists in the Case File);
            # the quote must match Heimdall's record of what the document claimed.
            rec = next((e for e in inv.evidence if e.doc_id == r.source_id and not e.admissible), None)
            if rec is None or _norm(r.quote_or_value) not in _norm(rec.quote):
                why = "quote does not match Heimdall's record of the set-aside claim"
        elif r.locator.paragraph is None and r.locator.paragraph_index is None:
            why = "no paragraph, page or row locator"
        else:
            text = _paragraph_text(tools, r.source_id, r.locator)
            if text is None:
                why = f"paragraph {r.locator.paragraph} does not exist in {r.source_id}"
            elif not r.quote_or_value.strip() or _norm(r.quote_or_value) not in _norm(text):
                why = "quote does not appear in the cited paragraph"
        if why:
            failed.append(CitationFailure(where=where, source_id=r.source_id, locator=r.locator.label(), reason=why))
        else:
            kept.append(r)
    return kept, failed


def _value_matches(value: str, row) -> bool:
    nums = re.findall(r"-?\d+(?:\.\d+)?", value or "")
    return bool(nums) and all(float(n) in (row.value_usd_m, row.volume_t) for n in nums)


def _paragraph_text(tools, doc_id: str, loc: Locator) -> Optional[str]:
    body = dict(tools.store.body_paragraphs(doc_id))
    label = re.compile(r"^\s*\[P(\d+)\]")
    # A labelled [P n] wins over an unlabelled block (e.g. the header) whose index happens to equal n.
    for p in sorted(tools.store.document(doc_id).paragraphs, key=lambda p: not label.match(p.raw_text or "")):
        m = label.match(p.raw_text or "")
        number = int(m.group(1)) if m else p.paragraph_index
        if loc.paragraph_index is not None and p.paragraph_index != loc.paragraph_index:
            continue
        if loc.paragraph is not None and number != loc.paragraph:
            continue
        return body.get(p.paragraph_index, "")
    return None


# -- arguments --------------------------------------------------------------------------------------------------------
def build_arguments(side: Side, report, cautions: List[str]) -> List[ClaimArgument]:
    inv = report.investigation
    return [_argument(side, p, [e for e in inv.evidence if e.prop_id == p.prop_id], inv.spec, cautions)
            for p in inv.spec.propositions]


def _cite(items) -> str:
    return "; ".join(f"{e.citation} ({e.assertion_type.lower().replace('_', ' ')}, {e.source_name or e.doc_id})"
                     for e in items[:3])


def _argument(side: Side, prop, items, spec, cautions: List[str]) -> ClaimArgument:
    adm = [e for e in items if e.admissible]
    sup = [e for e in adm if e.stance == "SUPPORTS"]
    con = [e for e in adm if e.stance == "CONTRADICTS"]
    qual = [e for e in adm if e.stance == "QUALIFIES"]
    ctx = [e for e in adm if e.stance == "CONTEXT"]
    aside = [e for e in items if not e.admissible]
    note = STRATEGY_NOTES.get(prop.kind, "")
    lims = list(dict.fromkeys(x for e in sup + con + qual for x in e.limitations))[:3]
    tally = (f"Case File for {prop.prop_id}: {len(sup)} supporting, {len(con)} contradicting, {len(qual)} qualifying, "
             f"{len(ctx)} context, {len(aside)} set aside.")
    base = dict(claim_id=prop.prop_id, proposition_text=prop.text, strategy=strategy_label(spec),
                limitations_uncertainty=lims,
                assumptions=([f"The proposition is attributed to {prop.attributed_to}; it is argued as their claim."]
                             if prop.attributed_to else []) + (["Prior-case cautions were noted for re-evaluation "
                                                                 "only; they are not evidence."] if cautions else []))
    if side == "THOR":
        refs = [item_ref(e, _type(e, True)) for e in sup[:4]] + [item_ref(e, _type(e, False)) for e in qual[:2]]
        if not sup:
            reasoning = (f"{tally} No admissible item in the Case File supports the proposition, so Thor does not "
                         f"press it. " + (f"The qualifying records ({_cite(qual)}) limit it; they do not establish it. "
                                          if qual else "") + note)
            return ClaimArgument(position="supports", evidence_refs=refs, reasoning=reasoning, challenge_basis=None,
                                 confidence=Confidence(level="LOW", explanation="Nothing in the Case File supports it."),
                                 adverse_evidence_handling=_adverse(con), pressed=False, **base)
        direct = [e for e in sup if _type(e, True) == "direct"]
        sources = {e.source_name or e.doc_id for e in sup}
        level = "HIGH" if direct and len(sources) >= 2 and not con else "MEDIUM" if direct or len(sources) >= 2 \
            else "LOW"
        reasoning = (f"{tally} Supporting: {_cite(sup)}. "
                     + (f"Qualified by {_cite(qual)}. " if qual else "") + note)
        return ClaimArgument(position="supports", evidence_refs=refs, reasoning=reasoning, challenge_basis=None,
                             confidence=Confidence(level=level, explanation=f"{len(direct)} direct item(s) from "
                                                                            f"{len(sources)} source(s); "
                                                                            f"{len(con)} contradicting."),
                             adverse_evidence_handling=_adverse(con), pressed=True, **base)
    # Loki
    origin = [item_ref(e, "unsupported_inference") for e in aside[:2]]
    if con:
        refs = [item_ref(e, _type(e, True)) for e in con[:4]] + origin
        direct = [e for e in con if _type(e, True) == "direct"]
        reasoning = (f"{tally} Evidence against the proposition: {_cite(con)}. "
                     + (f"It is also supported by {_cite(sup)}, so the record holds evidence on both sides. " if sup
                        else "") + note)
        return ClaimArgument(position="challenges", evidence_refs=refs, reasoning=reasoning,
                             challenge_basis="evidence_against", pressed=True,
                             confidence=Confidence(level="MEDIUM" if direct else "LOW",
                                                   explanation=f"{len(direct)} direct contradicting item(s); "
                                                               f"{len(sup)} supporting."),
                             alternative_explanations=[f"{e.citation}: {e.quote[:160]}" for e in qual[:2]], **base)
    if not sup and (qual or origin):
        refs = [item_ref(e, "circumstantial") for e in qual[:4]] + origin
        reasoning = (f"{tally} The proposition is not established: no admissible item supports it. "
                     + (f"Its only sources were set aside before trial ({', '.join(e.doc_id for e in aside[:2])}), "
                        f"which shows the claim was made, not that it is true. " if aside else "")
                     + (f"The records {_cite(qual)} qualify it; they do not show it to be false. " if qual else "")
                     + "Absence of evidence is not evidence of falsity. " + note)
        return ClaimArgument(position="challenges", evidence_refs=refs, reasoning=reasoning,
                             challenge_basis="not_established", pressed=bool(qual),
                             confidence=Confidence(level="MEDIUM" if qual else "LOW",
                                                   explanation="No supporting evidence on the record; the challenge "
                                                               "is that the proposition is unproven, not that it is "
                                                               "false."),
                             alternative_explanations=[f"{e.citation}: {e.quote[:160]}" for e in qual[:2]], **base)
    refs = [item_ref(e, "circumstantial") for e in qual[:2]] + origin
    reasoning = (f"{tally} Loki has no admissible evidence against the proposition"
                 + (f"; it is supported by {_cite(sup)}" if sup else "")
                 + (f" and qualified by {_cite(qual)}" if qual else "") + ". Loki does not press a challenge. " + note)
    return ClaimArgument(position="challenges", evidence_refs=refs, reasoning=reasoning, challenge_basis=None,
                         pressed=False, confidence=Confidence(level="LOW", explanation="Nothing contradicts it."),
                         alternative_explanations=[f"{e.citation}: {e.quote[:160]}" for e in qual[:2]], **base)


def _adverse(con) -> str:
    if not con:
        return "No admissible evidence contradicts the proposition."
    return (f"{len(con)} admissible item(s) contradict it ({_cite(con)}); Thor cannot rebut them from the Case File "
            f"and they stand against the claim.")


# -- attacks ----------------------------------------------------------------------------------------------------------
def build_attacks(side: Side, report, opponent: List, run: int) -> List[Attack]:
    """Attacks on the opponent's pressed arguments, each naming the most specific defect the evidence shows."""
    inv = report.investigation
    out = []
    for claim in opponent:
        a = _attack_for(side, claim, inv, run)
        if a:
            out.append(a)
    return out


def _attack(side, claim, attack_type, target, defect, explanation, counter, run) -> Attack:
    return Attack(attack_id="", run=run, attacker=side, target_claim_id=claim.claim_id,
                  target_proposition_id=claim.argument.claim_id, reason=ATTACK_TYPE_REASON[attack_type],
                  argument=f"{defect} {explanation}".strip(), grounds="argued", attack_type=attack_type,
                  target_evidence_or_reasoning=target, defect=defect, explanation=explanation,
                  counter_evidence_refs=counter)


def _named_subjects(prop) -> List[str]:
    names = [m.group(0) for m in re.finditer(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*", prop.text)
             if m.start() > 0 or len(m.group(0).split()) > 1]
    return [n for n in names if not (prop.attributed_to and n.split()[0] in prop.attributed_to)]


def _attack_for(side, claim, inv, run) -> Optional[Attack]:
    arg = claim.argument
    prop = next(p for p in inv.spec.propositions if p.prop_id == arg.claim_id)
    items = [e for e in inv.evidence if e.prop_id == arg.claim_id and e.admissible]
    carrying = [(i, r) for i, r in enumerate(arg.evidence_refs, 1) if r.evidence_type in CARRYING]
    meta = {e.doc_id: f"{e.source_name or ''} {e.citation}" for e in inv.evidence}
    names = _named_subjects(prop)
    for i, r in carrying:
        where = f"{r.quote_or_value} {meta.get(r.source_id, '')}"
        if names and not any(re.search(rf"\b{re.escape(n)}\b", where) for n in names):
            return _attack(side, claim, "wrong_entity_or_geographic_scope", f"ref {i}",
                           f"{r.source_id} {r.locator.label()} does not name {', '.join(names[:2])}.",
                           "Evidence about another entity or place cannot carry this proposition.", [], run)
        if r.epistemic_status == "projection" and prop.kind != "FORECAST":
            return _attack(side, claim, "forecast_presented_as_observed_fact", f"ref {i}",
                           f"{r.source_id} {r.locator.label()} is a projection.",
                           "A projection is cited as if it were an observed fact.", [], run)
        if prop.kind == "FORECAST" and r.source_id in {e.doc_id for e in items if e.assertion_type == "FORECAST"} \
                and arg.position == "supports":
            return _attack(side, claim, "forecast_presented_as_observed_fact", f"ref {i}",
                           f"{r.source_id} {r.locator.label()} is the forecast itself.",
                           "Publishing a projection shows what was projected, not that it is borne out.", [], run)
    opposing = "CONTRADICTS" if arg.position == "supports" else "SUPPORTS"
    counter = [item_ref(e, "contradictory") for e in items if e.stance == opposing][:2]
    if counter:
        return _attack(side, claim, "contradictory_evidence", "reasoning",
                       f"{len(counter)} admissible item(s) Heimdall assessed as "
                       f"{'contradicting' if opposing == 'CONTRADICTS' else 'supporting'} the proposition "
                       f"are not answered.", "The argument does not account for them.", counter, run)
    if carrying and len({r.source_id for _, r in carrying}) < 2:
        return _attack(side, claim, "missing_corroboration", "reasoning",
                       "The argument rests on a single source.",
                       "Without independent corroboration it is not established.", [], run)
    if arg.challenge_basis == "not_established" and arg.confidence.level != "LOW" and \
            not any(e.stance == "SUPPORTS" for e in items):
        return None  # nothing on the record answers an "unproven" challenge
    if arg.confidence.level == "HIGH" and any(r.evidence_type == "circumstantial" for r in arg.evidence_refs):
        return _attack(side, claim, "overstated_conclusion", "reasoning",
                       "High confidence rests partly on evidence that only qualifies the proposition.",
                       "Qualifying evidence cannot carry a high-confidence conclusion.", [], run)
    return None


# -- responses --------------------------------------------------------------------------------------------------------
def carrying_refs(arg: ClaimArgument) -> List[EvidenceRef]:
    """References that carry the position (circumstantial ones carry only an 'unproven' challenge)."""
    kinds = CARRYING + (("circumstantial",) if arg.challenge_basis == "not_established" else ())
    return [r for r in arg.evidence_refs if r.evidence_type in kinds]


def respond_to(side: Side, claim, attack: Attack, run: int) -> Tuple[str, str, Optional[Revision]]:
    """(action, explanation, revision). Decided by how each reference bears on the proposition (Heimdall's stance),
    never by whether the source reports an observation. A partial concession keeps the claim ID and the references
    that still carry the position; it is the advocate's action, not a finding."""
    arg = claim.argument
    t = attack.attack_type
    target = respond_target(arg, attack) if _ref_index(attack.target_evidence_or_reasoning) is not None else None
    carry = carrying_refs(arg)
    if target is not None and t in ("source_authenticity_failure", "source_reliability_challenge",
                                    "wrong_entity_or_geographic_scope", "temporal_mismatch",
                                    "forecast_presented_as_observed_fact", "unsupported_inference",
                                    "misinterpretation_of_evidence", "overstated_conclusion"):
        retained = [r for r in arg.evidence_refs if r is not target]
        if any(r in carry for r in retained):
            return "accept_point", (f"{side.title()} accepts the point on {target.source_id} "
                                    f"{target.locator.label()} and drops it; the remaining references still carry "
                                    f"the argument."), \
                _revision(run, "accept_point", arg, retained, [f"reliance on {target.source_id} "
                                                               f"{target.locator.label()}"], attack)
        return "withdraw_inference", (f"{side.title()} withdraws the argument: without {target.source_id} "
                                      f"{target.locator.label()} nothing carries it."), \
            _revision(run, "withdraw_inference", arg, [], [arg.reasoning[:200]], attack)
    if t == "contradictory_evidence":
        if any(r.evidence_type == "direct" for r in carry):
            return "maintain_disagreement", (f"{side.title()} maintains the argument on its direct evidence; the "
                                             f"record holds evidence on both sides."), None
        if carry:
            arg.confidence = Confidence(level="LOW", explanation="Narrowed: answered only by corroborating or "
                                                                 "qualifying evidence against direct counter-evidence.")
            return "narrow_proposition", (f"{side.title()} narrows the argument to what its references show; it no "
                                          f"longer claims they outweigh the counter-evidence."), \
                _revision(run, "narrow_proposition", arg, arg.evidence_refs, [arg.reasoning[:200]], attack)
    if t == "missing_corroboration":
        if len({r.source_id for r in carry}) >= 2:
            return "maintain", "Two or more independent sources carry the argument.", None
        if carry:
            arg.confidence = Confidence(level="LOW", explanation="Single-source argument; not independently "
                                                                 "corroborated.")
            return "narrow_proposition", (f"{side.title()} narrows the argument: it rests on one source and is "
                                          f"reported as such, with low confidence."), \
                _revision(run, "narrow_proposition", arg, arg.evidence_refs,
                          ["that the proposition is independently corroborated"], attack)
    if not carry:
        return "withdraw_inference", f"{side.title()} withdraws the argument: no reference carries it.", \
            _revision(run, "withdraw_inference", arg, [], [arg.reasoning[:200]], attack)
    return "maintain", "The attack does not identify a defect in the evidence that carries the argument.", None


def respond_target(arg: ClaimArgument, attack: Attack) -> Optional[EvidenceRef]:
    """The reference an attack aimed at, or the first one for an attack on the reasoning. Call before revising."""
    idx = _ref_index(attack.target_evidence_or_reasoning)
    if idx is not None and idx < len(arg.evidence_refs):
        return arg.evidence_refs[idx]
    return arg.evidence_refs[0] if arg.evidence_refs else None


def _ref_index(target: Optional[str]) -> Optional[int]:
    m = re.match(r"\s*ref\s+(\d+)", target or "", re.I)
    return int(m.group(1)) - 1 if m else None


def _revision(run, action, arg: ClaimArgument, retained: List[EvidenceRef], withdrawn: List[str],
              attack: Attack) -> Revision:
    if action == "withdraw_inference" and not retained:
        revised = f"{arg.position.title()} position withdrawn on {arg.claim_id}; the proposition itself is unchanged."
    else:
        revised = (f"{arg.proposition_text} - argued only to the extent shown by "
                   + ", ".join(f"{r.source_id} {r.locator.label()}" for r in retained if r.evidence_type != "unsupported_inference"))
    return Revision(round=run, action=action, original_proposition=arg.proposition_text, revised_proposition=revised,
                    retained_evidence_refs=retained, withdrawn_inferences=withdrawn,
                    reason=f"{attack.attack_type}: {attack.defect}")
