"""Trade series and the coverage map: monthly rows per route, validated, one cell per (importer, sector).

Two layouts are parsed:
  - prose trade notes: "In October 2026, the value was USD 34.5M and the volume was 84,000 tonnes."
  - fixed-layout tables: an optional header block (TABLE_ID / ORIGIN / DESTINATION / SECTOR lines), a column
    line naming month (or period), value and volume, then one row per line. Row IDs are TABLE_ID:row.

Every row is validated: a missing or non-numeric figure, a repeated month, a cut-off row, a negative figure, or a
unit price far outside the atlas price band flags the row. Flagged rows are shown but never counted as evidence.
Routes come from the document's route line or title, so nothing about a particular event is built in.
"""

import re
from typing import Dict, List, Optional, Sequence, Tuple

from heimdall.case.text import MONTHS
from heimdall.models.case_file import CaseScope, CoverageCell, TradeRowRecord, TradeSeries
from heimdall.storage.evidence_store import ResolvedEvidenceStore

# Atlas bands describe ordinary prices, and disruptions push prices well above them (E5 maize: 380-425 USD/t
# against a usual 180-280), so only gross errors such as a slipped decimal or a mistyped digit are flagged.
PRICE_BAND_TOLERANCE = 3.0

_PROSE = re.compile(r"In\s+([A-Za-z]+)\s+(\d{4}),\s+the\s+value\s+was\s+USD\s+(\S+?)\s*M(?:illion)?\s+and\s+the\s+"
                    r"volume\s+was\s+(\S+?)\s+tonnes", re.I)
_ROUTE = re.compile(r"\b([A-Z][\w'-]*(?: [A-Z][\w'-]*)*) to ([A-Z][\w'-]*(?: [A-Z][\w'-]*)*), ([A-Za-z][\w -]*?)"
                    r"(?:[,.]|$)")
_LABEL = re.compile(r"^\s*\[P(\d+)\]\s*")
_BAND = re.compile(r"([A-Z][A-Za-z ]+?) (?:is|are) quoted in USD per tonne[^.]*?usually between ([\d,.]+) and "
                   r"([\d,.]+)")
_HEADER_FIELD = re.compile(r"^\s*(TABLE_ID|TABLE|ORIGIN|FROM|DESTINATION|DEST|TO|SECTOR|COMMODITY)\s*:\s*(.+?)\s*$",
                           re.I)
_DELIMS = ("|", "\t", ";", ",")


def _number(raw: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """(value, problem). Thousands separators are allowed; anything else non-numeric is a problem."""
    if raw is None or not raw.strip():
        return None, "missing value"
    s = raw.strip().upper().replace("USD", "").replace("TONNES", "").replace("TONNE", "").strip()
    s = re.sub(r"(?<=\d)\s*M$", "", s).strip().rstrip(".")
    if not re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?|-?\d+(\.\d+)?", s):
        return None, f"non-numeric value '{raw.strip()}'"
    return float(s.replace(",", "")), None


def _month(raw: str) -> Tuple[Optional[str], Optional[int]]:
    raw = raw.strip()
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", raw)
    if m and 1 <= int(m.group(2)) <= 12:
        return MONTHS[int(m.group(2)) - 1].capitalize(), int(m.group(1))
    m = re.fullmatch(r"([A-Za-z]+)[\s-]+(\d{4})", raw)
    if m:
        name = next((x for x in MONTHS if x.startswith(m.group(1).lower()[:3])), None)
        if name:
            return name.capitalize(), int(m.group(2))
    return None, None


class TradeStore:
    def __init__(self, store: ResolvedEvidenceStore, countries: Sequence[str], commodities: Sequence[str]):
        self.store = store
        self.countries = {c.lower(): c for c in countries}
        self.commodities = {c.lower(): c for c in commodities}
        self.bands = self._price_bands()
        self._cache: Dict[str, Optional[TradeSeries]] = {}

    def _price_bands(self) -> Dict[str, Tuple[float, float]]:
        bands = {}
        for did in self.store.evidence_ids():
            if self.store.document(did).manifest_meta.source_type != "atlas":
                continue
            for _, text in self.store.body_paragraphs(did):
                for name, lo, hi in _BAND.findall(text):
                    bands[name.strip().lower()] = (float(lo.replace(",", "")), float(hi.replace(",", "")))
        return bands

    def route(self, doc_id: str) -> Optional[Tuple[str, str, str]]:
        """(origin, destination, sector) from the route line or the title, if both ends are known countries."""
        title = self.store.document(doc_id).manifest_meta.title or ""
        lines = [t for _, t in self.store.body_paragraphs(doc_id)]
        for text in [t for t in lines if t.lower().startswith("route:")] + [title]:
            for origin, dest, sector in _ROUTE.findall(text.split(":", 1)[-1] if ":" in text else text):
                o, d = self.countries.get(origin.strip().lower()), self.countries.get(dest.strip().lower())
                if o and d:
                    s = sector.strip().lower()
                    return o, d, self.commodities.get(s, s.capitalize())
        return None

    def series(self, doc_id: str) -> Optional[TradeSeries]:
        if doc_id not in self._cache:
            self._cache[doc_id] = self._build(doc_id)
        return self._cache[doc_id]

    def _build(self, doc_id: str) -> Optional[TradeSeries]:
        route = self.route(doc_id)
        paragraphs = list(self.store.body_paragraphs(doc_id))
        raw = {p.paragraph_index: p.raw_text for p in self.store.document(doc_id).paragraphs}
        rows = self._prose_rows(doc_id, paragraphs, raw) + self._table_rows(doc_id, raw)
        if not rows:
            return None
        meta = self.store.document(doc_id).manifest_meta
        origin, dest, sector = route or (None, None, None)
        for r in rows:
            r.origin, r.dest = r.origin or origin, r.dest or dest
            r.sector = r.sector or sector or (meta.sector if meta.sector and meta.sector != "general" else None)
        self._validate(rows)
        valid = sum(1 for r in rows if r.valid)
        return TradeSeries(doc_id=doc_id, title=meta.title, source_name=meta.source_name,
                           reliability_tier=meta.reliability_tier, pub_date=meta.pub_date,
                           origin=rows[0].origin, dest=rows[0].dest, sector=rows[0].sector, rows=rows,
                           valid_rows=valid, flagged_rows=len(rows) - valid)

    @staticmethod
    def _prose_rows(doc_id: str, paragraphs, raw: Dict[int, str]) -> List[TradeRowRecord]:
        rows = []
        for idx, text in paragraphs:
            label = _LABEL.match(raw.get(idx, ""))
            pid = f"P{label.group(1)}" if label else f"para{idx}"
            for n, (month, year, value, volume) in enumerate(_PROSE.findall(text)):
                v, v_err = _number(value)
                t, t_err = _number(volume)
                name = next((x for x in MONTHS if x.startswith(month.lower()[:3])), None)
                rows.append(TradeRowRecord(
                    row_id=f"{doc_id}#{pid}" + (f".{n + 1}" if n else ""), doc_id=doc_id, paragraph_index=idx,
                    year=int(year), month=name.capitalize() if name else month,
                    period=f"{year}-{MONTHS.index(name) + 1:02d}" if name else None,
                    value_usd_m=v, volume_t=t, flags=[e for e in (v_err, t_err) if e] +
                    ([] if name else [f"unknown month '{month}'"]), text=text))
        return rows

    def _table_rows(self, doc_id: str, raw: Dict[int, str]) -> List[TradeRowRecord]:
        lines = [(idx, line) for idx in sorted(raw) for line in raw[idx].splitlines()]
        rows, header, i, n_tables = [], {}, 0, 0
        while i < len(lines):
            idx, line = lines[i]
            field = _HEADER_FIELD.match(_LABEL.sub("", line))
            if field:
                header[field.group(1).upper()] = field.group(2)
                i += 1
                continue
            cols, delim = self._columns(line)
            if not cols:
                i += 1
                continue
            n_tables += 1
            table_id = header.get("TABLE_ID") or header.get("TABLE") or f"{doc_id}-T{n_tables}"
            origin = self.countries.get((header.get("ORIGIN") or header.get("FROM") or "").lower())
            dest = self.countries.get((header.get("DESTINATION") or header.get("DEST") or header.get("TO") or "")
                                      .lower())
            sector_raw = (header.get("SECTOR") or header.get("COMMODITY") or "").strip().lower()
            sector = self.commodities.get(sector_raw, sector_raw.capitalize() or None)
            i += 1
            n = 0
            while i < len(lines) and lines[i][1].strip():
                ridx, rline = lines[i]
                cells = [c.strip() for c in _LABEL.sub("", rline).strip().strip(delim).split(delim)]
                if len(cells) == 1 and delim not in rline:
                    break
                n += 1
                row_no = cells[0] if cols.get("row") == 0 and cells and cells[0].isdigit() else str(n)
                flags = []
                if len(cells) < len(cols["names"]):
                    flags.append(f"cut-off row: {len(cells)} of {len(cols['names'])} columns")

                def cell(key):
                    k = cols.get(key)
                    return cells[k] if k is not None and k < len(cells) else None

                month, year = _month(cell("month") or "")
                if not month:
                    flags.append(f"unreadable month '{cell('month') or ''}'")
                v, v_err = _number(cell("value"))
                t, t_err = _number(cell("volume"))
                flags += [e for e in (v_err, t_err) if e]
                rows.append(TradeRowRecord(
                    row_id=f"{table_id}:{row_no}", doc_id=doc_id, paragraph_index=ridx, origin=origin, dest=dest,
                    sector=sector, year=year, month=month,
                    period=f"{year}-{MONTHS.index(month.lower()) + 1:02d}" if month else None,
                    value_usd_m=v, volume_t=t, flags=flags, text=rline.strip()))
                i += 1
            header = {}
        return rows

    @staticmethod
    def _columns(line: str):
        text = _LABEL.sub("", line).strip()
        for delim in _DELIMS:
            names = [c.strip().lower() for c in text.strip(delim).split(delim)]
            if len(names) < 3:
                continue
            found = {}
            for k, name in enumerate(names):
                if re.search(r"\bmonth\b|\bperiod\b|\bdate\b", name):
                    found.setdefault("month", k)
                elif "value" in name or "usd" in name:
                    found.setdefault("value", k)
                elif "volume" in name or "tonne" in name:
                    found.setdefault("volume", k)
                elif re.fullmatch(r"#|no\.?|row|n", name):
                    found.setdefault("row", k)
            if {"month", "value", "volume"} <= set(found):
                return {**found, "names": names}, delim
        return None, None

    def _validate(self, rows: List[TradeRowRecord]) -> None:
        seen: Dict[Tuple, List[TradeRowRecord]] = {}
        for r in rows:
            if r.period:
                seen.setdefault((r.origin, r.dest, r.sector, r.period), []).append(r)
        for dupes in seen.values():
            if len(dupes) > 1:
                for r in dupes:
                    r.flags.append(f"repeated month {r.period} ({len(dupes)} rows)")
        for r in rows:
            if (r.value_usd_m is not None and r.value_usd_m < 0) or (r.volume_t is not None and r.volume_t < 0):
                r.flags.append("negative figure")
            if r.value_usd_m and r.volume_t:
                r.unit_price_usd_t = round(r.value_usd_m * 1e6 / r.volume_t, 2)
                band = self.bands.get((r.sector or "").lower())
                if band and not band[0] / PRICE_BAND_TOLERANCE <= r.unit_price_usd_t <= band[1] * PRICE_BAND_TOLERANCE:
                    r.flags.append(f"unit price USD {r.unit_price_usd_t:,.0f}/t is far outside the usual "
                                   f"{band[0]:,.0f}-{band[1]:,.0f} band")
            r.valid = not r.flags


def coverage_map(scope: CaseScope, series: List[TradeSeries]) -> List[CoverageCell]:
    origins = set(scope.event_countries)
    importers = [c for c in scope.countries if c not in origins] or list(scope.countries)
    cells = []
    for country in importers:
        for sector in scope.commodities:
            here = [s for s in series if s.dest == country and (s.sector or "").lower() == sector.lower()
                    and s.valid_rows]
            primary = [s for s in here if s.origin in origins]
            substitutes = [s for s in here if s.origin not in origins]
            periods = sorted({r.period for s in primary for r in s.rows if r.valid and r.period})
            if primary:
                note = (f"{len(periods)} month(s) of {'/'.join(sorted(origins))} trade rows"
                        + (f"; substitute supply from {', '.join(sorted({s.origin for s in substitutes}))}"
                           if substitutes else "; no substitute supply evidenced in the Case File"))
            else:
                note = "Evidence missing: no trade series for this flow, so no range can be given without inventing one."
            cells.append(CoverageCell(country=country, sector=sector, status="COVERED" if primary else
                                      "EVIDENCE_MISSING", primary_series=[s.doc_id for s in primary],
                                      substitute_series=[s.doc_id for s in substitutes],
                                      substitution_evidenced=bool(substitutes), periods=periods, note=note))
    return cells
