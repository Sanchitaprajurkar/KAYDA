"""
Resolve dev-pack traps before ingestion.

Reads parsed documents plus extracted facts/entities and writes a resolved dataset in which
only clean, citable evidence remains:

  resolved_data/documents/<DOC_ID>.json          evidence documents (header-corrected, injection removed)
  resolved_data/facts/<DOC_ID>_facts.json        citable facts only
  resolved_data/entities/<DOC_ID>_entities.json
  resolved_data/quarantine/excluded_documents.json   documents kept out of evidence, with reason
  resolved_data/quarantine/rejected_facts.json       facts kept out of evidence, with reason
  resolved_data/document_aliases.json            duplicate / fallback doc IDs -> canonical doc ID
  resolved_data/trap_log.json                    every action taken (also written to audit_log on ingest)

Nothing is deleted: anything removed from the evidence path is quarantined with the rule that
removed it and the document responsible, so a rejection can always be explained.

Run:
  python -m agent_1.resolve_traps [--parsed-dir ...] [--extracted-dir ...] [--dev-pack ...] [--out ...]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import logging
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ResolveTraps")

HERE = Path(__file__).resolve().parent
DEFAULT_PARSED = HERE / "parsed_docs"
DEFAULT_EXTRACTED = HERE.parent / "extracted_data"
DEFAULT_DEV_PACK = HERE.parent.parent / "dev_pack_E5"
DEFAULT_OUT = HERE.parent / "resolved_data"

HEADER_KEYS = ["DOC_ID", "EVENT_ID", "TITLE", "SOURCE_NAME", "SOURCE_TYPE", "RELIABILITY",
               "PUB_DATE", "PUB_TIME", "COUNTRY", "SECTOR", "LANGUAGE"]
_HEADER_RE = re.compile(r"\b(" + "|".join(HEADER_KEYS) + r"):\s*")
_LABEL_RE = re.compile(r"^\s*\[P\d+\]\s*")

COMMODITIES = {"wheat": "Wheat", "maize": "Maize", "corn": "Maize", "barley": "Barley", "rice": "Rice"}
REFERENCE_SOURCE_TYPES = {"atlas"}
RUMOUR_SOURCE_TYPES = {"social_post", "blog", "forum", "chat"}
TABLOID_SOURCE_TYPES = {"tabloid"}
FORECAST_MARKERS = re.compile(r"\b(expected|expects?|on track|base case|forecast|outlook|likely)\b", re.I)
NEGATION_RE = re.compile(r"\b(not renewed|no renewal|without (a )?renewal|expired|was wrong|retract)", re.I)
OPERATING_RE = re.compile(
    r"\b(remains open|not closed|berths (are|is) working|some berths are working|continues? to operate)\b", re.I)
INJECTION_RE = re.compile(
    r"^\s*(\[P\d+\]\s*)?(ASSISTANT|SYSTEM|USER|AI)\s*:"
    r"|ignore (all |any )?(previous|prior|above) instructions"
    r"|approve all claims|skip cross-examination|you are (an ai|chatgpt|claude)"
    r"|disregard (the|all|any) (rules|instructions)",
    re.I,
)
_MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december"]
_STOP = {"with", "that", "this", "from", "have", "been", "were", "will", "into", "after", "before",
         "about", "their", "there", "they", "what", "when", "which", "while", "would", "could",
         "should", "keep", "case", "base", "note", "says", "said", "report", "reported", "reports"}


# ── text helpers ──────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = (t.replace("‘", "'").replace("’", "'").replace("“", '"')
          .replace("”", '"').replace("–", "-").replace("—", "-"))
    return re.sub(r"\s+", " ", t).strip().lower()


def _stems(text: str, exclude: Set[str] = frozenset()) -> Set[str]:
    words = re.findall(r"[a-z]{4,}", _norm(text))
    return {w[:5] for w in words if w not in _STOP and w[:5] not in exclude}


def _pub_dt(meta: dict) -> Optional[datetime]:
    try:
        return datetime.strptime(f"{meta.get('pub_date')} {meta.get('pub_time') or '00:00'}", "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


# ── per-document state ────────────────────────────────────────────────────────

@dataclass
class Doc:
    doc_id: str
    parsed: dict
    meta: dict
    header_end: int                     # paragraph_index containing the '---' separator (0 if none)
    body: str                           # normalized body text after the header
    facts: List[dict]
    flagged: List[dict]
    entities: List[dict]
    reasons: List[dict] = field(default_factory=list)   # exclusion reasons
    aliases: List[dict] = field(default_factory=list)
    removed_paragraphs: Set[int] = field(default_factory=set)
    flags: Dict[str, object] = field(default_factory=dict)

    @property
    def excluded(self) -> bool:
        return bool(self.reasons)

    @property
    def pub(self) -> Optional[datetime]:
        return _pub_dt(self.meta)

    @property
    def tier(self) -> int:
        try:
            return int(self.meta.get("reliability"))
        except (TypeError, ValueError):
            return 2

    @property
    def body_paragraphs(self) -> List[dict]:
        return [p for p in self.parsed.get("paragraphs", [])
                if p["paragraph_index"] > self.header_end and p["paragraph_index"] not in self.removed_paragraphs]

    def text(self) -> str:
        return " ".join(_LABEL_RE.sub("", p["raw_text"]) for p in self.body_paragraphs)


def _split_header(parsed: dict) -> (dict, int, str):
    """Return (header fields, index of the paragraph holding '---', body text)."""
    paras = parsed.get("paragraphs", [])
    head_chunks, body_chunks, header_end = [], [], 0
    for p in paras:
        txt = p["raw_text"]
        if header_end == 0 and "---" in txt:
            before, _, after = txt.partition("---")
            head_chunks.append(before)
            if after.strip():
                body_chunks.append(after)
            header_end = p["paragraph_index"]
        elif header_end == 0:
            head_chunks.append(txt)
        else:
            body_chunks.append(txt)
    if header_end == 0:  # no header separator: everything is body
        return {}, 0, _norm(" ".join(p["raw_text"] for p in paras))

    head = " ".join(head_chunks)
    fields, matches = {}, list(_HEADER_RE.finditer(head))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(head)
        fields[m.group(1)] = head[m.end():end].strip()
    return fields, header_end, _norm(" ".join(body_chunks))


# ── resolver ──────────────────────────────────────────────────────────────────

class TrapResolver:
    def __init__(self, parsed_dir: Path, extracted_dir: Path, dev_pack: Path):
        self.parsed_dir = parsed_dir
        self.extracted_dir = extracted_dir
        self.dev_pack = dev_pack
        self.log: List[dict] = []
        self.docs: Dict[str, Doc] = {}
        manifest = json.loads((dev_pack / "manifest.json").read_text(encoding="utf-8"))
        self.corpus_info = {k: manifest.get(k) for k in ("pack", "event_id", "name", "as_of")}
        self.event_id = manifest.get("event_id")
        self.as_of = datetime.strptime(manifest.get("as_of"), "%Y-%m-%d").replace(hour=23, minute=59)
        self.raw_manifest = {(_upper_keys(e).get("DOC_ID")): e for e in manifest.get("documents", [])}

    def _log(self, trap: str, action: str, doc_id: str, detail: str, related: Optional[str] = None):
        self.log.append({"trap": trap, "action": action, "doc_id": doc_id,
                         "related_doc_id": related, "detail": detail})

    def _exclude(self, doc: Doc, reason: str, detail: str, related: Optional[str] = None):
        doc.reasons.append({"reason": reason, "related_doc_id": related, "detail": detail})

    # ── load + metadata normalisation ────────────────────────────────────────

    def load(self):
        def read_list(kind: str, doc_id: str) -> List[dict]:
            p = self.extracted_dir / kind / f"{doc_id}_{kind}.json"
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

        normalised_keys = filled = 0
        for path in sorted(self.parsed_dir.glob("*.json")):
            if path.name.startswith("_"):
                continue
            parsed = json.loads(path.read_text(encoding="utf-8"))
            doc_id = parsed["doc_id"]
            header, header_end, body = _split_header(parsed)

            raw = self.raw_manifest.get(doc_id, {})
            upper = _upper_keys(raw)
            if any(k != k.upper() and k.upper() in raw for k in raw):
                normalised_keys += 1
            meta = {k.lower(): v for k, v in upper.items() if k in HEADER_KEYS}
            meta["file"] = upper.get("FILE") or parsed.get("file_name")
            meta["format"] = upper.get("FORMAT") or Path(meta["file"]).suffix.lstrip(".").upper()

            doc = Doc(doc_id, parsed, meta, header_end, body,
                      read_list("facts", doc_id), read_list("flagged", doc_id), read_list("entities", doc_id))

            # Trap: inconsistent manifest -> the in-file header wins.
            for key, value in header.items():
                current = str(meta.get(key.lower()) or "").strip()
                if not current:
                    filled += 1
                elif current != value:
                    self._log("inconsistent_manifest", "header_override", doc_id,
                              f"{key}: manifest={current!r} -> header={value!r}")
                meta[key.lower()] = value
            self.docs[doc_id] = doc

        missing_format = sum(1 for e in self.raw_manifest.values() if "FORMAT" not in _upper_keys(e))
        self._log("inconsistent_manifest", "manifest_normalised", "*",
                  f"{normalised_keys} entries had duplicate lower-case keys, {missing_format} lacked FORMAT "
                  f"(derived from file extension), {filled} missing fields filled from the in-file header; "
                  f"header values win on conflict")

    # ── rules ────────────────────────────────────────────────────────────────

    def fix_sector(self):
        """Trap: wrong metadata. A single commodity named in the title overrides SECTOR."""
        for doc in self.docs.values():
            title = _norm(doc.meta.get("title", ""))
            named = {COMMODITIES[w] for w in COMMODITIES if re.search(rf"\b{w}\b", title)}
            if len(named) == 1:
                sector = named.pop()
                if sector != doc.meta.get("sector"):
                    doc.flags["sector_original"] = doc.meta.get("sector")
                    doc.meta["sector"] = sector
                    self._log("wrong_metadata", "sector_corrected", doc.doc_id,
                              f"SECTOR {doc.flags['sector_original']!r} -> {sector!r} (from title)")

    def check_source_integrity(self):
        """Trap: empty / badly encoded files. Verify pack hashes and raw bytes."""
        hashes = {}
        hfile = self.dev_pack / "hashes.sha256"
        if hfile.exists():
            for line in hfile.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) == 2:
                    hashes[Path(parts[1]).name] = parts[0]

        for doc in self.docs.values():
            src = self.dev_pack / "docs" / (doc.meta.get("file") or doc.parsed.get("file_name", ""))
            if not src.exists():
                continue
            data = src.read_bytes()
            expected = hashes.get(src.name)
            # git autocrlf rewrites LF -> CRLF on checkout; the pack hashes are of the LF originals.
            if expected and expected not in (hashlib.sha256(data).hexdigest(),
                                             hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()):
                doc.flags["integrity_mismatch"] = True
                self._log("damaged_file", "integrity_mismatch", doc.doc_id, "sha256 does not match hashes.sha256")
            if not data.strip():
                doc.flags["empty_source"] = True
            if src.suffix.lower() == ".txt":
                problems = []
                if b"\xff\xfe" in data or b"\xfe\xff" in data:
                    problems.append("UTF-16 BOM after an ASCII header")
                if b"\x00" in data:
                    problems.append("NUL bytes")
                try:
                    data.decode("utf-8")
                except UnicodeDecodeError:
                    problems.append("not valid UTF-8")
                if "�" in doc.body:
                    problems.append("undecodable bytes replaced")
                if problems:
                    doc.flags["encoding_repaired"] = "; ".join(problems)
                    self._log("badly_encoded_file", "encoding_repaired", doc.doc_id,
                              "decoded with BOM detection and replacement: " + "; ".join(problems))

    def remove_injections(self):
        """Trap: prompt injection. Documents are data; instruction-like lines are removed and logged."""
        for doc in self.docs.values():
            for p in doc.parsed.get("paragraphs", []):
                if p["paragraph_index"] > doc.header_end and INJECTION_RE.search(p["raw_text"]):
                    doc.removed_paragraphs.add(p["paragraph_index"])
                    self._log("prompt_injection", "injection_removed", doc.doc_id,
                              f"¶{p['paragraph_index']} removed from evidence text: {p['raw_text']!r}")

    def collapse_duplicates(self):
        """Traps: exact duplicates, cut-off duplicate, empty file. Keep one canonical ID."""
        def canonical_rank(d: Doc):
            return (bool(d.flags.get("encoding_repaired")), d.tier, -len(d.body), d.doc_id)

        def merge(dup: Doc, canon: Doc, kind: str, trap: str, action: str):
            self._exclude(dup, "DUPLICATE_OF", f"{kind} duplicate of {canon.doc_id}", canon.doc_id)
            canon.aliases.append({"alias_doc_id": dup.doc_id, "kind": kind})
            self._log(trap, action, dup.doc_id, f"{kind}: cite {canon.doc_id} instead", canon.doc_id)

        # exact content duplicates
        by_hash: Dict[str, List[Doc]] = defaultdict(list)
        for doc in self.docs.values():
            if doc.body:
                by_hash[hashlib.sha256(doc.body.encode()).hexdigest()].append(doc)
        for group in by_hash.values():
            if len(group) > 1:
                group.sort(key=canonical_rank)
                for dup in group[1:]:
                    merge(dup, group[0], "EXACT", "exact_duplicate", "duplicate_merged")

        live = [d for d in self.docs.values() if d.body and not d.excluded]

        # truncated copies: body is a strict prefix of a longer document with the same title
        for short in live:
            for full in live:
                if (short is not full and len(short.body) >= 200 and len(full.body) > len(short.body)
                        and full.body.startswith(short.body)
                        and _norm(short.meta.get("title", "")) == _norm(full.meta.get("title", ""))):
                    merge(short, full, "TRUNCATED", "cutoff_duplicate", "duplicate_merged")
                    break

        # empty documents: fall back to a document with the same title, source and publication time
        for doc in self.docs.values():
            if doc.body or doc.excluded:
                continue
            key = (_norm(doc.meta.get("title", "")), doc.meta.get("source_name"), doc.pub)
            match = next((d for d in self.docs.values() if d is not doc and d.body and not d.excluded and
                          (_norm(d.meta.get("title", "")), d.meta.get("source_name"), d.pub) == key), None)
            if match:
                merge(doc, match, "EMPTY_FALLBACK", "empty_file", "empty_fallback")
            else:
                self._exclude(doc, "EMPTY", "source file is empty and no duplicate was found")
                self._log("empty_file", "empty_excluded", doc.doc_id, "no fallback document found")

    def filter_scope(self):
        """Traps: unrelated lookalikes and documents after the as-of date."""
        for doc in self.docs.values():
            event = (doc.meta.get("event_id") or "").strip()
            if event != self.event_id and doc.meta.get("source_type") not in REFERENCE_SOURCE_TYPES:
                self._exclude(doc, "UNRELATED_EVENT", f"EVENT_ID {event or 'missing'} != {self.event_id}")
                self._log("unrelated_lookalike", "unrelated_event_excluded", doc.doc_id,
                          f"EVENT_ID {event or 'missing'}")
            if doc.pub and doc.pub > self.as_of:
                self._exclude(doc, "CLOCK_EXCLUDED", f"published {doc.pub:%Y-%m-%d} after as-of {self.as_of:%Y-%m-%d}")
                self._log("after_as_of_date", "clock_excluded", doc.doc_id,
                          f"pub_date {doc.pub:%Y-%m-%d} > as_of {self.as_of:%Y-%m-%d}")

    def _place_stems(self) -> Set[str]:
        return {_norm(d.meta.get("country", ""))[:5] for d in self.docs.values()} | {"orvan"}

    def _in_event(self) -> List[Doc]:
        return [d for d in self.docs.values() if (d.meta.get("event_id") or "") == self.event_id and d.body]

    def apply_corrections(self):
        """Traps: retracted report and reports that depend on it (taint through the correction chain)."""
        pool = self._in_event()
        for corr in pool:
            is_correction = (corr.meta.get("source_type") == "correction"
                             or _norm(corr.meta.get("title", "")).startswith("correction"))
            if not is_correction or not corr.pub:
                continue
            m = re.search(r"\b(?:we|it) reported that (.+?)(?:\.|$)", corr.text(), re.I)
            if not m:
                continue
            claim = m.group(1)
            claim_stems = _stems(claim)
            date_m = re.search(r"\bon (\d{1,2}) (" + "|".join(_MONTHS) + r")\b", _norm(corr.text()))

            def score(d: Doc) -> int:
                s = len(claim_stems & _stems(d.meta.get("title", "") + " " + d.text()[:400]))
                if date_m and d.pub and d.pub.day == int(date_m.group(1)) and \
                        d.pub.month == _MONTHS.index(date_m.group(2)) + 1:
                    s += 2
                return s

            candidates = [d for d in pool if d is not corr and d.pub and d.pub < corr.pub
                          and d.meta.get("source_name") == corr.meta.get("source_name")]
            if not candidates:
                continue
            target = max(candidates, key=score)
            if score(target) < 2:
                continue

            self._exclude(target, "RETRACTED", f"retracted by {corr.doc_id}: {claim!r}", corr.doc_id)
            self._log("retracted_report", "retracted", target.doc_id,
                      f"{corr.doc_id} states the report that {claim!r} was wrong", corr.doc_id)

            for d in pool:
                if d in (target, corr) or not d.pub or not (target.pub <= d.pub <= corr.pub):
                    continue
                text = d.text()
                if (claim_stems <= _stems(text) and re.search(r"\breport", text, re.I)
                        and not NEGATION_RE.search(text)):
                    self._exclude(d, "TAINTED", f"repeats the claim retracted by {corr.doc_id} "
                                                f"(originally {target.doc_id})", target.doc_id)
                    self._log("dependent_report", "tainted", d.doc_id,
                              f"relies on {target.doc_id}, retracted by {corr.doc_id}", target.doc_id)

    def apply_supersession(self):
        """Trap: stale forecasts made before the event, superseded by a Tier 1 notice of the outcome."""
        place_stems = self._place_stems()
        pool = [d for d in self._in_event() if d.pub]
        notices = [d for d in pool if d.tier == 1 and d.meta.get("source_type") == "gov_notice"
                   and any(f.get("assertion_status") == "CONFIRMED" for f in d.facts)]
        for notice in sorted(notices, key=lambda d: d.pub):
            topic = _stems(notice.meta.get("title", ""), exclude=place_stems)
            for d in pool:
                if d is notice or d.pub >= notice.pub or d.excluded:
                    continue
                title = d.meta.get("title", "")
                if (FORECAST_MARKERS.search(title) and topic & _stems(title, exclude=place_stems)
                        and any(f.get("assertion_status") == "PROJECTED" for f in d.facts)):
                    self._exclude(d, "SUPERSEDED", f"forecast overtaken by Tier 1 notice {notice.doc_id} "
                                                   f"({notice.meta.get('title')})", notice.doc_id)
                    self._log("stale_forecast", "superseded", d.doc_id,
                              f"superseded by {notice.doc_id}", notice.doc_id)

    def apply_source_tiers(self):
        """Traps: fake sub-events (rumours) and tabloid exaggeration. Tier 4 is never citable."""
        pool = self._in_event()
        generic = self._place_stems() | {"grain", "wheat", "maize", "sourc", "every", "orvan"}
        for doc in self.docs.values():
            if doc.tier < 4:
                continue
            stype = doc.meta.get("source_type")
            if stype in RUMOUR_SOURCE_TYPES:
                reason, trap, action = "RUMOUR", "fake_sub_event", "rumour_rejected"
            elif stype in TABLOID_SOURCE_TYPES:
                reason, trap, action = "TABLOID", "tabloid_exaggeration", "tabloid_rejected"
            else:
                reason, trap, action = "UNRELIABLE_SOURCE", "unreliable_source", "tier4_rejected"

            subject = _stems(doc.meta.get("title", ""), exclude=generic)
            contradicted_by = sorted({
                d.doc_id for d in pool if d.tier <= 2 and not d.excluded
                for p in d.body_paragraphs
                if OPERATING_RE.search(p["raw_text"]) and subject & _stems(p["raw_text"])
            })
            detail = f"Tier 4 {stype}"
            if contradicted_by:
                detail += f"; contradicted by {', '.join(contradicted_by)}"
            self._exclude(doc, reason, detail, contradicted_by[0] if contradicted_by else None)
            self._log(trap, action, doc.doc_id, detail, contradicted_by[0] if contradicted_by else None)

    # ── output ───────────────────────────────────────────────────────────────

    def run(self) -> "TrapResolver":
        self.load()
        self.fix_sector()
        self.check_source_integrity()
        self.remove_injections()
        self.collapse_duplicates()
        self.filter_scope()
        self.apply_corrections()
        self.apply_supersession()
        self.apply_source_tiers()
        return self

    def write(self, out: Path) -> dict:
        for sub in ("documents", "facts", "entities", "quarantine"):
            d = out / sub
            d.mkdir(parents=True, exist_ok=True)
            for old in d.glob("*.json"):
                old.unlink()

        excluded_docs, rejected_facts, aliases = [], [], []
        counts = defaultdict(int)

        for doc in sorted(self.docs.values(), key=lambda d: d.doc_id):
            if doc.excluded:
                excluded_docs.append({
                    "doc_id": doc.doc_id, "title": doc.meta.get("title"),
                    "source_name": doc.meta.get("source_name"), "source_type": doc.meta.get("source_type"),
                    "reliability": doc.meta.get("reliability"), "pub_date": doc.meta.get("pub_date"),
                    "event_id": doc.meta.get("event_id"), "reasons": doc.reasons,
                })
                for f in doc.facts + doc.flagged:
                    rejected_facts.append(_quarantine(f, doc.doc_id, doc.reasons))
                counts["excluded_documents"] += 1
                continue

            parsed = copy.deepcopy(doc.parsed)
            parsed["manifest_meta"] = {**(parsed.get("manifest_meta") or {}), **doc.meta}
            parsed["paragraphs"] = [p for p in parsed["paragraphs"]
                                    if p["paragraph_index"] not in doc.removed_paragraphs]
            parsed["full_text"] = "\n\n".join(p["raw_text"] for p in parsed["paragraphs"])
            parsed["total_paragraphs"] = len(parsed["paragraphs"])
            parsed["resolution"] = {
                "aliases": doc.aliases,
                "removed_paragraphs": sorted(doc.removed_paragraphs),
                **doc.flags,
            }
            (out / "documents" / f"{doc.doc_id}.json").write_text(
                json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
            aliases += [{"alias_doc_id": a["alias_doc_id"], "canonical_doc_id": doc.doc_id, "kind": a["kind"]}
                        for a in doc.aliases]

            citable = []
            for f in doc.facts:
                if f.get("source_ref", {}).get("paragraph_index") in doc.removed_paragraphs:
                    rejected_facts.append(_quarantine(f, doc.doc_id, [{"reason": "INJECTION_PARAGRAPH",
                                                                         "related_doc_id": None,
                                                                         "detail": "cites a removed paragraph"}]))
                elif f.get("evidence_status") != "VERIFIED":
                    rejected_facts.append(_quarantine(f, doc.doc_id, [{"reason": "NOT_VERIFIED",
                                                                         "related_doc_id": None, "detail": ""}]))
                else:
                    citable.append(f)
            for f in doc.flagged:
                rejected_facts.append(_quarantine(f, doc.doc_id, [{
                    "reason": "NOT_VERIFIED", "related_doc_id": None,
                    "detail": "; ".join(f.get("validation_notes") or [])}]))
            (out / "facts" / f"{doc.doc_id}_facts.json").write_text(
                json.dumps(citable, indent=2, ensure_ascii=False), encoding="utf-8")

            entities = []
            for e in doc.entities:
                e = copy.deepcopy(e)
                e["source_refs"] = [r for r in e.get("source_refs", [])
                                    if r.get("paragraph_index") not in doc.removed_paragraphs]
                if e["source_refs"] or not doc.removed_paragraphs:
                    entities.append(e)
            (out / "entities" / f"{doc.doc_id}_entities.json").write_text(
                json.dumps(entities, indent=2, ensure_ascii=False), encoding="utf-8")

            counts["documents"] += 1
            counts["facts"] += len(citable)
            counts["entities"] += len(entities)

        counts["rejected_facts"] = len(rejected_facts)
        (out / "quarantine" / "excluded_documents.json").write_text(
            json.dumps(excluded_docs, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "quarantine" / "rejected_facts.json").write_text(
            json.dumps(rejected_facts, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "document_aliases.json").write_text(json.dumps(aliases, indent=2), encoding="utf-8")
        (out / "trap_log.json").write_text(json.dumps(self.log, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "corpus.json").write_text(json.dumps(self.corpus_info, indent=2), encoding="utf-8")
        return dict(counts)


def _upper_keys(entry: dict) -> dict:
    """Normalise manifest keys; upper-case keys win over lower-case duplicates."""
    out = {}
    for k, v in entry.items():
        if k.upper() not in out or k == k.upper():
            out[k.upper()] = v
    return out


def _quarantine(fact: dict, doc_id: str, reasons: List[dict]) -> dict:
    q = copy.deepcopy(fact)
    q["doc_id"] = doc_id
    q["quarantine_reasons"] = reasons
    return q


def _parse_args():
    p = argparse.ArgumentParser(description="Resolve dev-pack traps before Neon ingestion")
    p.add_argument("--parsed-dir", default=str(DEFAULT_PARSED))
    p.add_argument("--extracted-dir", default=str(DEFAULT_EXTRACTED))
    p.add_argument("--dev-pack", default=str(DEFAULT_DEV_PACK))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    resolver = TrapResolver(Path(args.parsed_dir), Path(args.extracted_dir), Path(args.dev_pack)).run()
    counts = resolver.write(Path(args.out))

    print("\n" + "=" * 70)
    print("  TRAP RESOLUTION")
    print("=" * 70)
    for entry in resolver.log:
        rel = f" -> {entry['related_doc_id']}" if entry.get("related_doc_id") else ""
        print(f"  {entry['action']:<26} {entry['doc_id']:<9}{rel:<13} {entry['detail'][:90]}")
    print("-" * 70)
    for k, v in counts.items():
        print(f"  {k:<20}: {v}")
    print(f"  output              : {Path(args.out).resolve()}")
    print("=" * 70)
