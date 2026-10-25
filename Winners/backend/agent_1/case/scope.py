"""Spec 1 - Understand the case: map an event ID or natural-language query to a CaseScope."""

import re
from collections import Counter
from datetime import date, datetime
from typing import List, Optional, Set

from agent_1.case.text import MONTHS, contains_term, norm, token_set, tokens
from agent_1.models.case_file import CaseScope
from agent_1.storage.evidence_store import ResolvedEvidenceStore

COMMODITY_SYNONYMS = {"corn": "Maize"}
GENERIC_COMMODITIES = {"grain", "goods", "cargo", "food"}
_DATE_FORMATS = ("%d %B %Y", "%B %d %Y", "%B %d, %Y", "%Y-%m-%d", "%d %b %Y")


def _parse_date(text: str) -> Optional[date]:
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip().rstrip(".,").title(), fmt).date()
        except ValueError:
            continue
    try:
        return datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


class CaseUnderstanding:
    """Gazetteer-based case understanding built from the resolved corpus (deterministic, no LLM)."""

    def __init__(self, store: ResolvedEvidenceStore):
        self.store = store
        self.corpus = store.corpus
        countries: Set[str] = set()
        commodities: dict = {}  # lower-case -> best spelling (prefers capitalised / acronym forms)
        self.sectors: Set[str] = set()
        for did in store.evidence_ids():
            meta = store.document(did).manifest_meta
            if meta and meta.country and meta.country.lower() != "general":
                countries.add(meta.country)
            if meta and meta.sector and meta.sector.lower() != "general":
                self.sectors.add(meta.sector)
            for e in store.entities(did):
                if e.type.value == "NATION":
                    countries.add(e.name.strip())
        for did in store.evidence_ids():
            for e in store.entities(did):
                name = e.name.strip()
                if (e.type.value == "COMMODITY" and name.lower() not in GENERIC_COMMODITIES
                        and not any(c.lower() in name.lower() for c in countries)):
                    best = commodities.get(name.lower())
                    if best is None or (name[0].isupper() and not best[0].isupper()):
                        commodities[name.lower()] = name
        self.countries = sorted(countries)
        self.commodities = sorted({v[0].upper() + v[1:] for v in commodities.values()} | set(self.sectors))

    def understand(self, query: Optional[str] = None, event_id: Optional[str] = None) -> CaseScope:
        if not query and not event_id:
            raise ValueError("Provide a query or an event_id.")
        text = query or ""
        notes: List[str] = []

        corpus_event, corpus_name = self.corpus.get("event_id"), self.corpus.get("name")
        event_identified = False
        if event_id:
            event_identified = event_id.strip().upper() == (corpus_event or "").upper()
            if not event_identified:
                notes.append(f"Event {event_id} is not in the corpus (known: {corpus_event}).")
        else:
            overlap = token_set(text) & token_set(corpus_name or "")
            event_identified = len(overlap) >= 2
            notes.append(f"Event matched on terms {sorted(overlap)}" if event_identified
                         else f"Query does not match the corpus event '{corpus_name}'.")
        if event_identified and not text:
            text = corpus_name or ""

        countries = [c for c in self.countries if contains_term(text, c)]
        event_countries = [c for c in self.countries if corpus_name and contains_term(corpus_name, c)] \
            if event_identified else []
        commodities = [c for c in self.commodities if contains_term(text, c)]
        commodities += [v for k, v in COMMODITY_SYNONYMS.items() if contains_term(text, k) and v not in commodities]
        sectors = [s for s in sorted(self.sectors) if s in commodities]
        if event_identified and not sectors:
            sector_counts = Counter(self.store.document(d).manifest_meta.sector for d in self.store.evidence_ids()
                                    if self.store.document(d).manifest_meta.event_id == corpus_event)
            sectors = [s for s, _ in sector_counts.most_common() if s and s.lower() != "general"][:3]
            notes.append(f"No commodity in query; using the event's main sectors {sectors}.")

        as_of = self._as_of(text) or self.corpus.get("as_of")
        corpus_as_of = self.corpus.get("as_of")
        if corpus_as_of and as_of and as_of > corpus_as_of:
            notes.append(f"Requested as-of {as_of} is after the corpus cut-off {corpus_as_of}; evidence stops there.")
        period_start, period_end = self._period(text)

        terms = list(dict.fromkeys(
            tokens(text) + [t for c in countries + event_countries + commodities for t in tokens(c)]
            + (tokens(corpus_name) if event_identified else [])))
        return CaseScope(
            query=query, event_id=corpus_event if event_identified else event_id,
            event_name=corpus_name if event_identified else None, event_identified=event_identified,
            countries=countries, event_countries=event_countries, commodities=commodities, sectors=sectors,
            period_start=period_start, period_end=period_end or as_of, as_of_date=as_of,
            search_terms=terms, notes=notes,
        )

    @staticmethod
    def _as_of(text: str) -> Optional[str]:
        m = re.search(r"\bas of ([0-9]{1,2} [A-Za-z]+ [0-9]{4}|[A-Za-z]+ [0-9]{1,2},? [0-9]{4}|[0-9]{4}-[0-9]{2}-[0-9]{2})",
                      text, re.I)
        d = _parse_date(m.group(1)) if m else None
        return d.isoformat() if d else None

    @staticmethod
    def _period(text: str):
        t = norm(text)
        m = re.search(r"\bq([1-4]) (\d{4})\b", t)
        if m:
            q, y = int(m.group(1)), int(m.group(2))
            end_month = q * 3
            end_day = 31 if end_month in (3, 12) else 30
            return f"{y}-{end_month - 2:02d}-01", f"{y}-{end_month:02d}-{end_day}"
        months = "|".join(MONTHS)
        m = re.search(rf"\b({months}) (?:to|through|-|until) ({months}) (\d{{4}})\b", t)
        if m:
            y = int(m.group(3))
            start, end = MONTHS.index(m.group(1)) + 1, MONTHS.index(m.group(2)) + 1
            return f"{y}-{start:02d}-01", f"{y}-{end:02d}-28"
        m = re.search(rf"\bsince (\d{{1,2}} (?:{months}) \d{{4}})\b", t)
        if m:
            d = _parse_date(m.group(1))
            return (d.isoformat() if d else None), None
        return None, None
