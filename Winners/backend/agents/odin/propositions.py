"""Odin's preparation of propositions before ruling.

- A compound allegation of what happened ("strikes destroyed A and B") is split into separately verifiable parts,
  because each part needs its own evidence; one ruling is never given to several allegations.
- A physical-damage allegation against a site carries a distinct, lesser proposition: that operations there were
  disrupted. Operating records decide that one; they cannot decide the damage.
- When a damage part stays INSUFFICIENT, Odin decides whether a targeted search (damage assessments, inspection
  reports, site condition reports, independent observation) could reasonably find what is missing, and phrases one
  focused request for Heimdall's existing re-search interface.
Grammar and generic vocabulary only: nothing names an entity, place or case.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from backend.court.models import Confidence, PropositionRuling

DAMAGE = re.compile(r"\b(?:destroy\w*|damag\w*|demolish\w*|flatten\w*|level{1,2}ed|burn(?:ed|t)|bomb\w*|"
                    r"shelled|struck|sunk|sank|wreck\w*|ruin\w*|obliterat\w*|razed)\b", re.I)
_AUX = re.compile(r"\b(?:were|was|have been|has been|had been)(?:\s+\w+ly)?\s*$", re.I)
_PLACE = re.compile(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})+")
_TAIL = re.compile(r"\s+(?:at|in|by|during|on|after|last|overnight|amid|following)\b.*$", re.I)
_DET = re.compile(r"^(?:the|a|an|its|their|all|both)\s+", re.I)
_STOP = {"the", "a", "an", "of", "its", "their", "at", "in", "on", "and", "to", "for", "with", "by", "from"}
OPERATIONS = re.compile(r"operat|working|loading|function|open(?:ed|ing)?\b|resum", re.I)
OPS_DISRUPTED = re.compile(
    r"\b(?:closed|closure|shut\w*|halt\w*|suspend\w*|stopp\w*|reduc\w*|slow\w*|delay\w*|disrupt\w*|interrupt\w*|"
    r"idle\w*|poor|curtail\w*)\b|\bbelow (?:normal|capacity)\b"
    r"|\b(?:cannot|can't|not|no)\b[^.]{0,60}\b(?:resume|return|normal)", re.I)
OPS_NORMAL = re.compile(r"\b(?:normal(?:ly)? operat\w*|operating normally|fully operational|full capacity|"
                        r"resumed (?:normal|full)\w*|business as usual|operations (?:are |were )?unaffected)\b", re.I)
# Evidence types that can decide physical damage, each with the search terms that would find it.
DAMAGE_EVIDENCE = (
    ("official damage assessments", r"assess"),
    ("authority inspection reports", r"inspect"),
    ("site or facility condition reports", r"condition"),
    ("independent observations explicitly describing physical damage", r"observ|witness|imagery|photograph"),
)
DAMAGE_NEEDED = ("a record that explicitly describes the physical condition of the site: an official damage "
                 "assessment, an inspection report by the responsible authority, a site or facility condition report, "
                 "or an independent observation describing physical damage")


def _stems(text: str) -> set:
    out = set()
    for w in re.findall(r"[a-z]{3,}", (text or "").lower()):
        if w not in _STOP:
            out.add(w[:-1] if len(w) > 4 and w.endswith("s") else w)
    return out


def place_of(text: str) -> Optional[str]:
    m = _PLACE.search(text or "")
    return m.group(0) if m else None


def is_damage(prop) -> bool:
    return prop.kind in ("INCIDENT", "EVENT") and DAMAGE.search(prop.text or "") is not None


def _conjuncts(np: str) -> List[str]:
    parts = [p.strip(" ,") for p in re.split(r",\s*and\s+|,\s*|\s+and\s+", np) if p.strip(" ,")]
    if len(parts) < 2:
        return []
    first, last = _DET.sub("", parts[0]).split(), _DET.sub("", parts[-1]).split()
    if len(first) == 1 and len(last) == 2 and not first[0].endswith("s"):
        return []  # "import and export terminal": coordinated modifiers of one thing, not two things
    return parts


@dataclass
class Part:
    text: str
    target: str   # what the part is about (the conjunct)
    specific: set = field(default_factory=set)  # its own words, beyond the place name
    site: bool = False                          # the target names the place itself (the site as a whole)


def split(text: str) -> List[Part]:
    """The separately verifiable parts of an allegation whose predicate is shared by coordinated targets
    ("X destroyed A and B", "A and B were destroyed by X"). [] when it is not compound."""
    place = place_of(text)
    verbs = list(DAMAGE.finditer(text)) or [m for m in re.finditer(r"\b\w+ed\b", text) if m.start() > 0]
    for m in verbs:
        left, verb, right = text[:m.start()].rstrip(), m.group(0), text[m.end():]
        aux = _AUX.search(left)
        if aux:  # passive: the coordinated subjects share the predicate
            subjects = _conjuncts(left[:aux.start()].strip())
            if subjects:
                def agree(s, a=aux.group(0).strip()):  # each subject now stands alone
                    plural = s.split()[-1].lower().endswith("s")
                    return re.sub(r"^(?:were|was)\b", "were" if plural else "was",
                                  re.sub(r"^ha(?:ve|s) been\b", "have been" if plural else "has been", a))
                parts = [(s, f"{s} {agree(s)} {verb}{right}") for s in subjects]
                break
        else:
            tail = _TAIL.search(right.split(" and ")[-1])
            tail_text = tail.group(0) if tail else ""
            objects = _conjuncts(right[:len(right) - len(tail_text)].strip())
            if objects:
                parts = [(o, f"{left} {verb} {o}{tail_text}") for o in objects]
                break
    else:
        return []
    out = []
    place_words = _stems(place or "")
    for target, sentence in parts:
        site = bool(place) and place.lower() in target.lower()
        if place and not site:
            sentence = sentence.replace(target, f"{target} at {place}", 1)
        out.append(Part(text=sentence.strip(), target=target, specific=_stems(target) - place_words, site=site))
    return out


def _target(text: str) -> str:
    """What a single allegation says was damaged: the subject of a passive, the object of an active sentence."""
    m = DAMAGE.search(text)
    if not m:
        return place_of(text) or text
    left, right = text[:m.start()].rstrip(), text[m.end():]
    aux = _AUX.search(left)
    if aux:
        return left[:aux.start()].strip()
    tail = _TAIL.search(right)
    return (right[:tail.start()] if tail else right).strip(" .") or place_of(text) or text


def as_part(text: str) -> Part:
    place, target = place_of(text), _target(text)
    site = bool(place) and place.lower() in target.lower()
    return Part(text=text, target=target, specific=_stems(target) - _stems(place or ""), site=site)


def allegation_parts(prop, incident: Optional[str], plan, attach_missing: bool) -> Tuple[List[Part], int]:
    """(the parts Odin rules for this allegation, how many come from the proposition itself). A part of the
    question's alleged incident that no plan proposition carries is added to the allegation about the same place,
    so no allegation of the question goes unruled."""
    own = split(prop.text) or [as_part(prop.text)]
    n_own, place = len(own), place_of(prop.text)
    if not (attach_missing and incident and place and DAMAGE.search(incident)):
        return own, n_own
    carried = [x for q in plan if is_damage(q) for x in (split(q.text) or [as_part(q.text)])]
    for qp in split(incident) or [as_part(incident)]:
        same_place = (place_of(qp.text) or "").lower() == place.lower()
        if same_place and qp.specific and not any(qp.specific <= c.specific for c in carried):
            own.append(qp)
    return own, n_own


def route(parts: Sequence[Part], items) -> List[list]:
    """Each piece of evidence goes to the part(s) it is about: a part's own words decide; a record that names none of
    them is about the site as a whole (the part that names the place), or about all parts if none does. The source of
    an inadmissible allegation goes to every part it may concern."""
    place_parts = [i for i, p in enumerate(parts) if p.site]
    out: List[list] = [[] for _ in parts]
    for e in items:
        words = _stems(e.quote)
        hit = [i for i, p in enumerate(parts) if p.specific & words]
        if not hit:
            hit = list(range(len(parts))) if not e.admissible else (place_parts or list(range(len(parts))))
        for i in hit:
            out[i].append(e)
    return out


def operations_stance(quote: str) -> Optional[str]:
    """How a record bears on 'operations were disrupted', read from what it says (no model involved)."""
    if OPS_DISRUPTED.search(quote or ""):
        return "SUPPORTS"
    if OPS_NORMAL.search(quote or ""):
        return "CONTRADICTS"
    return None


def operations_items(items, prop_id: str) -> list:
    out = []
    for e in items:
        stance = operations_stance(e.quote) if e.admissible else None
        if stance:
            out.append(e.model_copy(update={
                "prop_id": prop_id, "stance": stance,
                "limitations": list(e.limitations) + ["bearing on operations read by Odin from the quoted text"]}))
    return out


def needs_operations(prop, plan) -> bool:
    """Derive the operational proposition only if no proposition in the plan already covers operations there."""
    place = place_of(prop.text)
    if not (place and is_damage(prop)):
        return False
    return not any(q.prop_id != prop.prop_id and OPERATIONS.search(q.text) and place.lower() in q.text.lower()
                   for q in plan)


def damage_request(place: str, targets: Sequence[str]) -> str:
    """One focused request: the site, the specific things alleged damaged, and the evidence types that decide it.
    Its leading terms are what Heimdall searches on."""
    what = " and ".join(t for t in targets)
    where = "" if place.lower() in what.lower() else f" at {place}"
    return (f"Physical damage to {what}{where} is recorded in an official damage assessment, an inspection report "
            f"by the authority responsible for {place}, a site or facility condition report, or an independent "
            f"observation describing physical damage")


def untried_evidence(prior_queries: Sequence[str]) -> List[str]:
    text = " ".join(prior_queries).lower()
    return [label for label, rx in DAMAGE_EVIDENCE if not re.search(rx, text)]


def is_damage_request(text: str, place: str) -> bool:
    return place.lower() in (text or "").lower() and "physical damage" in (text or "").lower() and \
        re.search(DAMAGE_EVIDENCE[0][1], text or "", re.I) is not None


def composite(parent, parts: List[PropositionRuling]) -> PropositionRuling:
    """What the parts mean for an advocate who argued the compound allegation as a whole. Never reported as a
    finding of its own: the parts carry the findings."""
    classes = [p.classification for p in parts]
    cls = ("REJECTED" if "REJECTED" in classes else "ESTABLISHED" if all(c == "ESTABLISHED" for c in classes) else
           "CONTESTED" if "CONTESTED" in classes else "INSUFFICIENT")
    summary = "; ".join(f"{p.prop_id} {p.classification}" for p in parts)
    return PropositionRuling(
        prop_id=parent.prop_id, proposition=parent.text, kind=parent.kind, classification=cls,
        reasoning=(f"{parent.prop_id} is a compound allegation; Odin ruled its parts separately ({summary}). The whole "
                   f"is established only if every part is, and fails if any part is rejected."),
        confidence=Confidence(level=min((p.confidence.level for p in parts),
                                        key=["LOW", "MEDIUM", "HIGH"].index),
                              explanation="The weakest part decides the compound allegation."),
        needs_investigation=any(p.needs_investigation for p in parts),
        derivation="compound")


def research_parents(plan, history) -> Dict[str, List[str]]:
    """Send-back propositions Heimdall added for Odin's damage requests -> the allegation(s) they serve. They are
    Odin's own search requests, not new allegations, so their evidence is folded back into the allegation."""
    asked = {h.request for h in history}
    out: Dict[str, List[str]] = {}
    for q in plan:
        if q.text not in asked:
            continue
        for p in plan:
            place = place_of(p.text)
            if p is not q and place and is_damage(p) and is_damage_request(q.text, place):
                out.setdefault(q.prop_id, []).append(p.prop_id)
    return out


def prior_search(prop, audit, history) -> Tuple[List[str], Optional[int]]:
    """Queries already run for this allegation, and the run in which Odin's damage request (if any) was searched."""
    queries = [q for a in audit if a.get("proposition") == prop.prop_id for q in a.get("queries", [])]
    place = place_of(prop.text) or ""
    run = None
    for h in history:
        if is_damage_request(h.request, place):
            queries.append(h.request)
            run = h.run_number
    return queries, run
