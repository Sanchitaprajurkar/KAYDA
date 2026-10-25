"""
Pre-ingestion data validation for the Heimdall evidence pipeline.

Checks all 8 categories:
  1. Completeness      - missing required fields, empty documents/paragraphs
  2. Consistency       - conflicting metadata, invalid dates, inconsistent units
  3. Duplicates        - doc IDs, paragraph indexes, fact IDs, entity names
  4. Numerical quality - impossible percentages, negatives, malformed values
  5. Outliers          - statistically extreme numeric values (flagged, never deleted)
  6. Temporal validity - documents/facts beyond the simulation cutoff (2027-01-25)
  7. Provenance        - paragraph IDs, quotes not found in cited text
  8. Referential integrity - facts/mentions pointing to nonexistent records

Rules:
  - Missing numeric values stay NULL; they are never treated as zero.
  - Outliers are FLAGGED in the report only; no records are removed or modified.

Run:
  python -m agent_1.validate_data [--docs-dir <path>] [--facts-dir <path>]
                                  [--flagged-dir <path>] [--entities-dir <path>]
                                  [--output <report.json>]
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("Validate")

# ── constants ─────────────────────────────────────────────────────────────────

SIMULATION_CUTOFF = date(2027, 1, 25)
REQUIRED_DOC_FIELDS = ["doc_id", "file_name", "format", "paragraphs"]
REQUIRED_FACT_FIELDS = ["fact_id", "category", "subject", "statement", "source_ref", "evidence_status"]
REQUIRED_ENTITY_FIELDS = ["name", "type"]
VALID_CATEGORIES = {
    "TRADE_VOLUME", "TARIFF_OR_PRICE", "ROUTE_STATUS", "TREATY_OR_AGREEMENT",
    "GEOPOLITICAL_EVENT", "GRAIN_OR_INVENTORY", "DISRUPTION_STATUS",
    "RETRACTION_NOTICE", "OTHER",
}
VALID_ENTITY_TYPES = {
    "NATION", "PORT", "COMMODITY", "AGREEMENT", "CORRIDOR",
    "ORGANIZATION", "PERSON", "INFRASTRUCTURE",
}
VALID_EVIDENCE_STATUSES = {"VERIFIED", "UNCERTAIN", "REJECTED", "UNVERIFIED"}
VALID_ASSERTION_STATUSES = {
    "CONFIRMED", "REPORTED", "ALLEGED", "DENIED",
    "RUMOURED", "PROJECTED", "PROPOSED", "CORRECTED", "RETRACTED",
}
# Units implying a percentage — numeric_value must be in [0, 100]
PERCENT_UNITS = {"%", "percent", "per cent", "pct", "percentage"}
# Categories where negative numeric_value makes no sense
NON_NEGATIVE_CATEGORIES = {"TRADE_VOLUME", "GRAIN_OR_INVENTORY"}
# IQR multiplier for outlier detection
OUTLIER_IQR_FACTOR = 3.0
OUTLIER_ZSCORE = 3.5


# ── issue record ──────────────────────────────────────────────────────────────

class Issue:
    __slots__ = ("category", "severity", "doc_id", "fact_id", "entity_name",
                 "paragraph_index", "field", "message")

    def __init__(
        self,
        category: str,
        severity: str,           # ERROR | WARNING | INFO
        message: str,
        doc_id: str = "",
        fact_id: str = "",
        entity_name: str = "",
        paragraph_index: Optional[int] = None,
        field: str = "",
    ):
        self.category = category
        self.severity = severity
        self.message = message
        self.doc_id = doc_id
        self.fact_id = fact_id
        self.entity_name = entity_name
        self.paragraph_index = paragraph_index
        self.field = field

    def to_dict(self) -> dict:
        d = {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
        }
        if self.doc_id:
            d["doc_id"] = self.doc_id
        if self.fact_id:
            d["fact_id"] = self.fact_id
        if self.entity_name:
            d["entity_name"] = self.entity_name
        if self.paragraph_index is not None:
            d["paragraph_index"] = self.paragraph_index
        if self.field:
            d["field"] = self.field
        return d


# ── text helpers ──────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = t.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    t = t.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", t).strip().lower()


def _quote_in_para(quote: str, para_text: str) -> bool:
    """Return True if a normalised version of the quote appears in the paragraph."""
    q = _norm(quote).strip("\"' ").rstrip(".,;: ").strip("\"' ")
    p = _norm(para_text)
    if not q:
        return False
    if q in p:
        return True
    # fuzzy: at least 80 % of words in order
    qw = re.findall(r"[a-z0-9]+", q)
    pw = re.findall(r"[a-z0-9]+", p)
    if not qw:
        return False
    from difflib import SequenceMatcher
    matched = sum(b.size for b in SequenceMatcher(None, qw, pw, autojunk=False).get_matching_blocks())
    return matched / len(qw) >= 0.80


def _parse_date(s: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            pass
    return None


def _is_valid_iso_date(s: str) -> bool:
    return _parse_date(s) is not None


# ── outlier helpers ───────────────────────────────────────────────────────────

def _outlier_bounds(values: List[float]) -> Tuple[float, float]:
    """IQR-based fence: Q1 - k*IQR, Q3 + k*IQR."""
    if len(values) < 4:
        return (-math.inf, math.inf)
    s = sorted(values)
    n = len(s)
    q1 = statistics.median(s[:n // 2])
    q3 = statistics.median(s[n - n // 2:])
    iqr = q3 - q1
    if iqr == 0:
        # fall back to z-score
        mu = statistics.mean(s)
        try:
            sd = statistics.stdev(s)
        except statistics.StatisticsError:
            return (-math.inf, math.inf)
        if sd == 0:
            return (-math.inf, math.inf)
        return (mu - OUTLIER_ZSCORE * sd, mu + OUTLIER_ZSCORE * sd)
    return (q1 - OUTLIER_IQR_FACTOR * iqr, q3 + OUTLIER_IQR_FACTOR * iqr)


# ── loader ────────────────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log.warning("Cannot read %s: %s", path, exc)
        return None


def load_corpus(
    docs_dir: Path,
    facts_dir: Optional[Path],
    flagged_dir: Optional[Path],
    entities_dir: Optional[Path],
) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    """Return (docs, all_facts, all_flagged, all_entities) lists."""
    doc_files = sorted(f for f in docs_dir.glob("*.json") if not f.name.startswith("_"))
    docs, all_facts, all_flagged, all_entities = [], [], [], []

    for path in doc_files:
        doc = _load_json(path)
        if not isinstance(doc, dict):
            continue
        doc_id = doc.get("doc_id", path.stem.upper())
        docs.append(doc)

        if facts_dir:
            fp = facts_dir / f"{doc_id}_facts.json"
            if fp.exists():
                data = _load_json(fp)
                if isinstance(data, list):
                    for f in data:
                        f.setdefault("_doc_id", doc_id)
                    all_facts.extend(data)

        if flagged_dir:
            fp = flagged_dir / f"{doc_id}_flagged.json"
            if fp.exists():
                data = _load_json(fp)
                if isinstance(data, list):
                    for f in data:
                        f.setdefault("_doc_id", doc_id)
                    all_flagged.extend(data)

        if entities_dir:
            fp = entities_dir / f"{doc_id}_entities.json"
            if fp.exists():
                data = _load_json(fp)
                if isinstance(data, list):
                    for e in data:
                        e.setdefault("_doc_id", doc_id)
                    all_entities.extend(data)

    return docs, all_facts, all_flagged, all_entities


# ── validator ─────────────────────────────────────────────────────────────────

class Validator:
    def __init__(
        self,
        docs: List[dict],
        all_facts: List[dict],
        all_flagged: List[dict],
        all_entities: List[dict],
    ):
        self.docs = docs
        self.all_facts = all_facts
        self.all_flagged = all_flagged
        self.all_entities = all_entities
        self.issues: List[Issue] = []

        # Build lookup indexes
        self.doc_by_id: Dict[str, dict] = {d.get("doc_id", ""): d for d in docs}
        self.para_index: Dict[str, Dict[int, dict]] = {}  # doc_id -> {para_index -> para}
        for doc in docs:
            pid = doc.get("doc_id", "")
            self.para_index[pid] = {p["paragraph_index"]: p for p in doc.get("paragraphs", []) if "paragraph_index" in p}

    def _add(self, category: str, severity: str, message: str, **kwargs):
        self.issues.append(Issue(category, severity, message, **kwargs))

    # ── 1. Completeness ───────────────────────────────────────────────────────

    def check_completeness(self):
        for doc in self.docs:
            did = doc.get("doc_id", "<unknown>")
            for field in REQUIRED_DOC_FIELDS:
                if not doc.get(field):
                    self._add("COMPLETENESS", "ERROR", f"Missing required field '{field}'",
                               doc_id=did, field=field)

            meta = doc.get("manifest_meta") or {}
            for mf in ["title", "source_name", "pub_date"]:
                if not meta.get(mf):
                    self._add("COMPLETENESS", "WARNING", f"Missing manifest field '{mf}'",
                               doc_id=did, field=f"manifest_meta.{mf}")

            paras = doc.get("paragraphs", [])
            if not paras:
                full_text = (doc.get("full_text") or "").strip()
                if not full_text:
                    self._add("COMPLETENESS", "ERROR",
                               "Document has no paragraphs and empty full_text — source file is empty",
                               doc_id=did)
                else:
                    self._add("COMPLETENESS", "ERROR",
                               "Document has no paragraphs (full_text present — re-run parser)",
                               doc_id=did)
            else:
                empty = [p.get("paragraph_index") for p in paras if not (p.get("raw_text") or "").strip()]
                for pi in empty:
                    self._add("COMPLETENESS", "WARNING", "Empty paragraph text",
                               doc_id=did, paragraph_index=pi)

        for fact in self.all_facts + self.all_flagged:
            fid = fact.get("fact_id", "<unknown>")
            did = fact.get("_doc_id", "")
            for field in REQUIRED_FACT_FIELDS:
                if not fact.get(field):
                    self._add("COMPLETENESS", "ERROR", f"Fact missing required field '{field}'",
                               doc_id=did, fact_id=fid, field=field)
            src = fact.get("source_ref") or {}
            if not src.get("paragraph_index"):
                self._add("COMPLETENESS", "ERROR", "Fact source_ref missing paragraph_index",
                           doc_id=did, fact_id=fid, field="source_ref.paragraph_index")

        for entity in self.all_entities:
            did = entity.get("_doc_id", "")
            for field in REQUIRED_ENTITY_FIELDS:
                if not entity.get(field):
                    self._add("COMPLETENESS", "WARNING", f"Entity missing field '{field}'",
                               doc_id=did, entity_name=entity.get("name", "<unknown>"), field=field)

    # ── 2. Consistency ────────────────────────────────────────────────────────

    def check_consistency(self):
        for doc in self.docs:
            did = doc.get("doc_id", "<unknown>")
            meta = doc.get("manifest_meta") or {}

            # doc_id matches filename expectation
            fname_stem = doc.get("file_name", "").rsplit(".", 1)[0].upper()
            if fname_stem and did.upper() != fname_stem:
                self._add("CONSISTENCY", "ERROR",
                           f"doc_id '{did}' does not match file_name stem '{fname_stem}'",
                           doc_id=did, field="doc_id")

            # pub_date format
            pub = meta.get("pub_date")
            if pub and not _is_valid_iso_date(str(pub)):
                self._add("CONSISTENCY", "ERROR", f"Invalid pub_date format: '{pub}'",
                           doc_id=did, field="manifest_meta.pub_date")

            # reliability tier
            rel = meta.get("reliability")
            if rel is not None:
                try:
                    r = int(rel)
                    if not 1 <= r <= 4:
                        self._add("CONSISTENCY", "ERROR",
                                  f"reliability tier {r} out of range [1, 4]",
                                  doc_id=did, field="manifest_meta.reliability")
                except (TypeError, ValueError):
                    self._add("CONSISTENCY", "ERROR",
                              f"Non-integer reliability value: '{rel}'",
                              doc_id=did, field="manifest_meta.reliability")

        for fact in self.all_facts + self.all_flagged:
            fid = fact.get("fact_id", "<unknown>")
            did = fact.get("_doc_id", "")

            # category
            cat = (fact.get("category") or "").upper()
            if cat and cat not in VALID_CATEGORIES:
                self._add("CONSISTENCY", "WARNING", f"Unknown category '{cat}'",
                           doc_id=did, fact_id=fid, field="category")

            # evidence_status
            es = (fact.get("evidence_status") or "").upper()
            if es and es not in VALID_EVIDENCE_STATUSES:
                self._add("CONSISTENCY", "ERROR", f"Invalid evidence_status '{es}'",
                           doc_id=did, fact_id=fid, field="evidence_status")

            # assertion_status
            ast = (fact.get("assertion_status") or "").upper()
            if ast and ast not in VALID_ASSERTION_STATUSES:
                self._add("CONSISTENCY", "WARNING", f"Invalid assertion_status '{ast}'",
                           doc_id=did, fact_id=fid, field="assertion_status")

            # confidence range
            conf = fact.get("confidence")
            if conf is not None:
                try:
                    cf = float(conf)
                    if not 0.0 <= cf <= 1.0:
                        self._add("CONSISTENCY", "ERROR",
                                  f"confidence {cf} outside [0.0, 1.0]",
                                  doc_id=did, fact_id=fid, field="confidence")
                except (TypeError, ValueError):
                    self._add("CONSISTENCY", "ERROR",
                              f"Non-numeric confidence: '{conf}'",
                              doc_id=did, fact_id=fid, field="confidence")

            # unit vs category coherence (basic sanity)
            unit = (fact.get("unit") or "").lower()
            nv = fact.get("numeric_value")
            if nv is not None and unit in PERCENT_UNITS:
                try:
                    fv = float(nv)
                    if not 0.0 <= fv <= 100.0:
                        self._add("CONSISTENCY", "ERROR",
                                  f"Percentage value {fv} outside [0, 100] for unit '{unit}'",
                                  doc_id=did, fact_id=fid, field="numeric_value")
                except (TypeError, ValueError):
                    pass

        for entity in self.all_entities:
            did = entity.get("_doc_id", "")
            etype = (entity.get("type") or "").upper()
            if etype and etype not in VALID_ENTITY_TYPES:
                self._add("CONSISTENCY", "WARNING",
                           f"Unknown entity type '{etype}'",
                           doc_id=did, entity_name=entity.get("name", ""), field="type")

    # ── 3. Duplicates ─────────────────────────────────────────────────────────

    def check_duplicates(self):
        # Duplicate doc IDs
        seen_docs: Dict[str, int] = defaultdict(int)
        for doc in self.docs:
            seen_docs[doc.get("doc_id", "")] += 1
        for did, count in seen_docs.items():
            if count > 1:
                self._add("DUPLICATES", "ERROR",
                           f"doc_id '{did}' appears {count} times in parsed_docs/",
                           doc_id=did)

        # Duplicate paragraph indexes within a document
        for doc in self.docs:
            did = doc.get("doc_id", "")
            idx_counts: Dict[int, int] = defaultdict(int)
            for p in doc.get("paragraphs", []):
                idx_counts[p.get("paragraph_index")] += 1
            for pi, cnt in idx_counts.items():
                if cnt > 1:
                    self._add("DUPLICATES", "ERROR",
                               f"paragraph_index {pi} appears {cnt} times",
                               doc_id=did, paragraph_index=pi)

        # Duplicate fact IDs across all facts + flagged
        seen_facts: Dict[str, List[str]] = defaultdict(list)
        for fact in self.all_facts + self.all_flagged:
            fid = fact.get("fact_id", "")
            if fid:
                seen_facts[fid].append(fact.get("_doc_id", ""))
        for fid, sources in seen_facts.items():
            if len(sources) > 1:
                self._add("DUPLICATES", "ERROR",
                           f"fact_id '{fid}' appears {len(sources)} times (docs: {', '.join(set(sources))})",
                           fact_id=fid)

        # Duplicate (doc_id, paragraph_index, statement) combos — logical duplicates
        fact_keys: Dict[tuple, int] = defaultdict(int)
        for fact in self.all_facts + self.all_flagged:
            src = fact.get("source_ref") or {}
            key = (
                src.get("doc_id", ""),
                src.get("paragraph_index"),
                _norm(fact.get("statement", ""))[:120],
            )
            fact_keys[key] += 1
        for key, cnt in fact_keys.items():
            if cnt > 1:
                self._add("DUPLICATES", "WARNING",
                           f"Logically duplicate fact statement ({cnt}x) in {key[0]} ¶{key[1]}",
                           doc_id=key[0], paragraph_index=key[1])

        # Duplicate entity names within same document
        entity_keys: Dict[Tuple[str, str], int] = defaultdict(int)
        for entity in self.all_entities:
            key = (entity.get("_doc_id", ""), _norm(entity.get("name", "")))
            entity_keys[key] += 1
        for (did, name), cnt in entity_keys.items():
            if cnt > 1:
                self._add("DUPLICATES", "WARNING",
                           f"Entity '{name}' appears {cnt} times in document",
                           doc_id=did, entity_name=name)

    # ── 4. Numerical quality ──────────────────────────────────────────────────

    def check_numerical_quality(self):
        for fact in self.all_facts + self.all_flagged:
            fid = fact.get("fact_id", "<unknown>")
            did = fact.get("_doc_id", "")
            nv = fact.get("numeric_value")

            # Explicit zero where value should be absent — warn only if there is no quote support
            if nv == 0 and not (fact.get("source_ref") or {}).get("text_snippet", ""):
                self._add("NUMERICAL", "WARNING",
                           "numeric_value is 0 with no text_snippet; verify it is not a null substitution",
                           doc_id=did, fact_id=fid, field="numeric_value")

            if nv is None:
                continue  # NULL stays NULL — no check needed

            try:
                fv = float(nv)
            except (TypeError, ValueError):
                self._add("NUMERICAL", "ERROR",
                           f"numeric_value '{nv}' is not a valid number",
                           doc_id=did, fact_id=fid, field="numeric_value")
                continue

            if not math.isfinite(fv):
                self._add("NUMERICAL", "ERROR",
                           f"numeric_value is non-finite ({fv})",
                           doc_id=did, fact_id=fid, field="numeric_value")
                continue

            cat = (fact.get("category") or "").upper()
            unit = (fact.get("unit") or "").lower()

            # Negative where invalid
            if fv < 0 and cat in NON_NEGATIVE_CATEGORIES:
                self._add("NUMERICAL", "ERROR",
                           f"Negative numeric_value {fv} for category '{cat}'",
                           doc_id=did, fact_id=fid, field="numeric_value")

            # Impossible percentage (already caught in consistency for unit; here also check category)
            if unit in PERCENT_UNITS and not 0.0 <= fv <= 100.0:
                pass  # already reported in consistency

            # confidence must not be stored as a percentage (> 1.0 but label is "confidence")
            conf = fact.get("confidence")
            if conf is not None:
                try:
                    cf = float(conf)
                    if 1.0 < cf <= 100.0 and unit in PERCENT_UNITS:
                        self._add("NUMERICAL", "WARNING",
                                  f"confidence={cf} looks like a percentage, expected [0, 1]",
                                  doc_id=did, fact_id=fid, field="confidence")
                except (TypeError, ValueError):
                    pass

    # ── 5. Outliers ───────────────────────────────────────────────────────────

    def check_outliers(self):
        """Flag statistically extreme numeric_values per (category, unit). Never delete."""
        by_category: Dict[Tuple[str, str], List[Tuple[float, dict]]] = defaultdict(list)
        for fact in self.all_facts:  # verified facts only for baseline
            nv = fact.get("numeric_value")
            if nv is None:
                continue
            try:
                fv = float(nv)
            except (TypeError, ValueError):
                continue
            if math.isfinite(fv):
                cat = (fact.get("category") or "OTHER").upper()
                unit = (fact.get("unit") or "").strip().lower()
                by_category[(cat, unit)].append((fv, fact))

        for (cat, unit_key), entries in by_category.items():
            if len(entries) < 4:
                continue
            values = [v for v, _ in entries]
            lo, hi = _outlier_bounds(values)
            for fv, fact in entries:
                if fv < lo or fv > hi:
                    did = fact.get("_doc_id", "")
                    fid = fact.get("fact_id", "<unknown>")
                    unit = fact.get("unit") or ""
                    self._add("OUTLIERS", "WARNING",
                               f"Outlier: numeric_value={fv} {unit} for category '{cat}' / unit '{unit_key}' "
                               f"(expected range [{lo:.2g}, {hi:.2g}]) — record kept, flagged for review",
                               doc_id=did, fact_id=fid, field="numeric_value")

    # ── 6. Temporal validity ──────────────────────────────────────────────────

    def check_temporal_validity(self):
        for doc in self.docs:
            did = doc.get("doc_id", "<unknown>")
            meta = doc.get("manifest_meta") or {}
            pub = meta.get("pub_date")
            if pub:
                d = _parse_date(str(pub))
                if d and d > SIMULATION_CUTOFF:
                    # Post-cutoff documents are intentional in this simulation — they show
                    # outcomes after the trial date. Facts from them are already marked
                    # is_as_of_valid=False by the fact extractor. Flag as WARNING only.
                    self._add("TEMPORAL", "WARNING",
                               f"pub_date {pub} is after simulation cutoff {SIMULATION_CUTOFF} "
                               f"— facts will carry is_as_of_valid=False",
                               doc_id=did, field="manifest_meta.pub_date")

        for fact in self.all_facts + self.all_flagged:
            fid = fact.get("fact_id", "<unknown>")
            did = fact.get("_doc_id", "")
            dm = fact.get("date_mentioned")
            if dm:
                d = _parse_date(str(dm))
                if d and d > SIMULATION_CUTOFF:
                    self._add("TEMPORAL", "WARNING",
                               f"date_mentioned '{dm}' is after simulation cutoff {SIMULATION_CUTOFF}",
                               doc_id=did, fact_id=fid, field="date_mentioned")

    # ── 7. Provenance ─────────────────────────────────────────────────────────

    def check_provenance(self):
        for fact in self.all_facts + self.all_flagged:
            fid = fact.get("fact_id", "<unknown>")
            src = fact.get("source_ref") or {}
            src_doc_id = src.get("doc_id", "")
            para_idx = src.get("paragraph_index")
            snippet = src.get("text_snippet") or ""

            did = fact.get("_doc_id", src_doc_id)

            # Paragraph exists in the cited document
            if src_doc_id and para_idx is not None:
                para_map = self.para_index.get(src_doc_id, {})
                if src_doc_id in self.doc_by_id and para_idx not in para_map:
                    self._add("PROVENANCE", "ERROR",
                               f"source_ref points to ¶{para_idx} which does not exist in {src_doc_id}",
                               doc_id=did, fact_id=fid, field="source_ref.paragraph_index",
                               paragraph_index=para_idx)
                elif snippet and src_doc_id in self.para_index and para_idx in self.para_index.get(src_doc_id, {}):
                    para_text = self.para_index[src_doc_id][para_idx].get("raw_text", "")
                    if para_text and not _quote_in_para(snippet, para_text):
                        self._add("PROVENANCE", "WARNING",
                                   f"Verbatim quote not found in cited ¶{para_idx} of {src_doc_id}",
                                   doc_id=did, fact_id=fid, field="source_ref.text_snippet",
                                   paragraph_index=para_idx)

        for entity in self.all_entities:
            did = entity.get("_doc_id", "")
            for ref in entity.get("source_refs", []):
                ref_doc = ref.get("doc_id", "")
                ref_para = ref.get("paragraph_index")
                if ref_doc and ref_para is not None:
                    if ref_doc in self.doc_by_id and ref_para not in self.para_index.get(ref_doc, {}):
                        self._add("PROVENANCE", "WARNING",
                                   f"Entity mention points to ¶{ref_para} which does not exist in {ref_doc}",
                                   doc_id=did, entity_name=entity.get("name", ""),
                                   paragraph_index=ref_para)

    # ── 8. Referential integrity ──────────────────────────────────────────────

    def check_referential_integrity(self):
        known_doc_ids = set(self.doc_by_id.keys())

        for fact in self.all_facts + self.all_flagged:
            fid = fact.get("fact_id", "<unknown>")
            did = fact.get("_doc_id", "")
            src = fact.get("source_ref") or {}
            src_doc = src.get("doc_id", "")
            if src_doc and src_doc not in known_doc_ids:
                self._add("REFERENTIAL", "ERROR",
                           f"source_ref.doc_id '{src_doc}' not found in parsed_docs/",
                           doc_id=did, fact_id=fid, field="source_ref.doc_id")

        for entity in self.all_entities:
            did = entity.get("_doc_id", "")
            for ref in entity.get("source_refs", []):
                ref_doc = ref.get("doc_id", "")
                if ref_doc and ref_doc not in known_doc_ids:
                    self._add("REFERENTIAL", "ERROR",
                               f"Entity mention references unknown doc_id '{ref_doc}'",
                               doc_id=did, entity_name=entity.get("name", ""))

    # ── run all ───────────────────────────────────────────────────────────────

    def run(self) -> List[Issue]:
        log.info("Running COMPLETENESS checks …")
        self.check_completeness()
        log.info("Running CONSISTENCY checks …")
        self.check_consistency()
        log.info("Running DUPLICATES checks …")
        self.check_duplicates()
        log.info("Running NUMERICAL QUALITY checks …")
        self.check_numerical_quality()
        log.info("Running OUTLIER checks …")
        self.check_outliers()
        log.info("Running TEMPORAL VALIDITY checks …")
        self.check_temporal_validity()
        log.info("Running PROVENANCE checks …")
        self.check_provenance()
        log.info("Running REFERENTIAL INTEGRITY checks …")
        self.check_referential_integrity()
        return self.issues


# ── report ────────────────────────────────────────────────────────────────────

def print_report(issues: List[Issue], docs: List[dict], all_facts: List[dict],
                 all_flagged: List[dict], all_entities: List[dict]):
    by_cat: Dict[str, List[Issue]] = defaultdict(list)
    for iss in issues:
        by_cat[iss.category].append(iss)

    errors = sum(1 for i in issues if i.severity == "ERROR")
    warnings = sum(1 for i in issues if i.severity == "WARNING")

    print("\n" + "=" * 70)
    print("  HEIMDALL DATA VALIDATION REPORT")
    print("=" * 70)
    print(f"  Documents  : {len(docs)}")
    print(f"  Facts      : {len(all_facts)}")
    print(f"  Flagged    : {len(all_flagged)}")
    print(f"  Entities   : {len(all_entities)}")
    print(f"  Issues     : {len(issues)}  (errors: {errors}, warnings: {warnings})")
    print("=" * 70)

    order = ["COMPLETENESS", "CONSISTENCY", "DUPLICATES", "NUMERICAL",
             "OUTLIERS", "TEMPORAL", "PROVENANCE", "REFERENTIAL"]
    for cat in order:
        cat_issues = by_cat.get(cat, [])
        if not cat_issues:
            print(f"\n  [{cat}]  ✓  no issues")
            continue
        errs = sum(1 for i in cat_issues if i.severity == "ERROR")
        warns = sum(1 for i in cat_issues if i.severity == "WARNING")
        print(f"\n  [{cat}]  {errs} errors, {warns} warnings")
        for iss in cat_issues:
            tag = "ERR " if iss.severity == "ERROR" else "WARN"
            loc = ""
            if iss.doc_id:
                loc += f" [{iss.doc_id}"
                if iss.paragraph_index is not None:
                    loc += f" ¶{iss.paragraph_index}"
                if iss.fact_id:
                    loc += f" fact:{iss.fact_id}"
                loc += "]"
            print(f"    {tag}{loc}  {iss.message}")

    print("\n" + "=" * 70)
    status = "PASS" if errors == 0 else "FAIL"
    print(f"  RESULT: {status}  (errors={errors}, warnings={warnings})")
    print("=" * 70 + "\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_args():
    p = argparse.ArgumentParser(description="Validate Heimdall data before Neon ingestion")
    p.add_argument("--docs-dir", default=None)
    p.add_argument("--facts-dir", default=None)
    p.add_argument("--flagged-dir", default=None)
    p.add_argument("--entities-dir", default=None)
    p.add_argument("--output", default=None, help="Write JSON report to this file")
    p.add_argument("--errors-only", action="store_true", help="Print only ERROR-severity issues")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    here = Path(__file__).resolve().parent

    docs_dir = Path(args.docs_dir) if args.docs_dir else here / "parsed_docs"
    facts_dir = Path(args.facts_dir) if args.facts_dir else None
    flagged_dir = Path(args.flagged_dir) if args.flagged_dir else None
    entities_dir = Path(args.entities_dir) if args.entities_dir else None

    if not docs_dir.exists():
        print(f"[ERROR] parsed_docs directory not found: {docs_dir}")
        sys.exit(1)

    log.info("Loading corpus from %s …", docs_dir)
    docs, all_facts, all_flagged, all_entities = load_corpus(
        docs_dir, facts_dir, flagged_dir, entities_dir
    )
    log.info("Loaded %d docs, %d facts, %d flagged, %d entities",
             len(docs), len(all_facts), len(all_flagged), len(all_entities))

    validator = Validator(docs, all_facts, all_flagged, all_entities)
    issues = validator.run()

    if args.errors_only:
        issues = [i for i in issues if i.severity == "ERROR"]

    print_report(issues, docs, all_facts, all_flagged, all_entities)

    if args.output:
        out = Path(args.output)
        report = {
            "summary": {
                "documents": len(docs),
                "facts": len(all_facts),
                "flagged": len(all_flagged),
                "entities": len(all_entities),
                "total_issues": len(issues),
                "errors": sum(1 for i in issues if i.severity == "ERROR"),
                "warnings": sum(1 for i in issues if i.severity == "WARNING"),
            },
            "issues": [i.to_dict() for i in issues],
        }
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info("JSON report written to %s", out)

    sys.exit(1 if any(i.severity == "ERROR" for i in issues) else 0)
