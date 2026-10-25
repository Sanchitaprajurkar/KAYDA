"""
Extract facts from evidence paragraphs that the bulk extraction left uncovered.

Append-only: existing facts and their IDs are never changed. Paragraphs come from the resolved documents,
so removed content (e.g. the prompt-injection line) is never sent to the extractor. New facts pass the same
four validation layers as the bulk run and land in extracted_data/facts or extracted_data/flagged.

Afterwards re-run: resolve_traps -> validate_data -> ingest_to_neon -> sync_graph.

Run (from the folder containing .env):
  python -m heimdall.fill_extraction_gaps [--min-words 6] [--doc-id ORV-0033] [--dry-run]
"""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from heimdall.case.text import norm
from heimdall.extraction.fact_extractor import FactExtractor
from heimdall.models.document import DocumentParagraph
from heimdall.storage.evidence_store import ResolvedEvidenceStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GapFill")

EXTRACTED = Path(__file__).resolve().parent.parent / "extracted_data"


def _read(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def uncovered_paragraphs(store: ResolvedEvidenceStore, doc_id: str, min_words: int):
    facts, flagged = _read(EXTRACTED / "facts" / f"{doc_id}_facts.json"), _read(
        EXTRACTED / "flagged" / f"{doc_id}_flagged.json")
    cited = {f["source_ref"]["paragraph_index"] for f in facts + flagged}
    title = norm(store.document(doc_id).manifest_meta.title or "")
    return [(i, t) for i, t in store.body_paragraphs(doc_id)
            if i not in cited and len(t.split()) >= min_words and norm(t) != title]


def fill(doc_ids, min_words: int, dry_run: bool):
    store = ResolvedEvidenceStore()
    extractor = FactExtractor()
    all_ids = {f["fact_id"] for p in (EXTRACTED / "facts").glob("*.json") for f in _read(p)} | {
        f["fact_id"] for p in (EXTRACTED / "flagged").glob("*.json") for f in _read(p)}
    totals = {"documents": 0, "paragraphs": 0, "accepted": 0, "flagged": 0, "duplicates_skipped": 0}

    for doc_id in doc_ids:
        gaps = uncovered_paragraphs(store, doc_id, min_words)
        if not gaps:
            continue
        totals["documents"] += 1
        totals["paragraphs"] += len(gaps)
        log.info("%s: %d uncovered paragraph(s) %s", doc_id, len(gaps), [i for i, _ in gaps])
        if dry_run:
            continue

        doc = store.document(doc_id).model_copy(deep=True)
        by_index = {p.paragraph_index: p for p in doc.paragraphs}
        doc.paragraphs = [by_index[i] if i in by_index else DocumentParagraph.create(i, t) for i, t in gaps]
        result = extractor.extract_with_review(doc)

        fpath, gpath = EXTRACTED / "facts" / f"{doc_id}_facts.json", EXTRACTED / "flagged" / f"{doc_id}_flagged.json"
        facts, flagged = _read(fpath), _read(gpath)
        seen = {norm(f["statement"]) for f in facts + flagged}
        added = {"accepted": 0, "flagged": 0}
        for kind, items, target in (("accepted", result.accepted, facts), ("flagged", result.flagged, flagged)):
            for fact in items:
                data = fact.model_dump(mode="json")
                if norm(data["statement"]) in seen:
                    totals["duplicates_skipped"] += 1
                    continue
                while data["fact_id"] in all_ids:
                    data["fact_id"] = uuid.uuid4().hex[:8]
                all_ids.add(data["fact_id"])
                seen.add(norm(data["statement"]))
                target.append(data)
                added[kind] += 1
        fpath.write_text(json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
        gpath.write_text(json.dumps(flagged, indent=2, ensure_ascii=False), encoding="utf-8")
        totals["accepted"] += added["accepted"]
        totals["flagged"] += added["flagged"]
        log.info("  +%d verified, +%d flagged", added["accepted"], added["flagged"])

    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract facts from uncovered evidence paragraphs (append-only)")
    p.add_argument("--min-words", type=int, default=6)
    p.add_argument("--doc-id", default=None)
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    ids = [a.doc_id.upper()] if a.doc_id else ResolvedEvidenceStore().evidence_ids()
    fill(ids, a.min_words, a.dry_run)
