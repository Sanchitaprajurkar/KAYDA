"""
Complete entity mentions for evidence documents.

The bulk entity pass listed only some of the paragraphs where each entity appears (on long documents it
often stopped after the header), and paragraphs added by fill_extraction_gaps were never sent to it.

  1. LLM pass    - fact-cited paragraphs with no entity mention are sent to the EntityExtractor. Text comes
                   from the resolved documents, so removed content (the injection line) is never sent.
  2. Verify      - a returned mention is kept only if the entity's name or an alias is actually written
                   in that paragraph; entities left with no verified mention are dropped.
  3. Link        - every body paragraph is scanned for every known entity name/alias of that document,
                   adding the literal mentions the LLM skipped. Nothing is inferred: a paragraph that
                   names no entity (e.g. "In July 2026, the value was USD 90.0M") stays unlinked.

Existing entities and mentions are kept; only additions are made. Writes extracted_data/entities.
Afterwards re-run: resolve_traps -> validate_data -> ingest_to_neon -> sync_graph.

Run (from the folder containing .env):
  python -m agent_1.fill_entity_gaps [--doc-id ORV-0009] [--no-llm] [--dry-run]
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Optional

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from agent_1.extraction.entity_extractor import EntityExtractor
from agent_1.storage.evidence_store import ResolvedEvidenceStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("EntityGapFill")

EXTRACTED = Path(__file__).resolve().parent.parent / "extracted_data"
MIN_ALIAS_LEN = 3
SHORT_FORM_TYPES = {"ORGANIZATION", "PERSON"}


def _short_form_of(entity: dict, entities: list) -> Optional[dict]:
    """The multi-word organisation/person in the same document whose first word is this entity's name."""
    name = _key(entity["name"])
    if " " in name:
        return None
    return next((o for o in entities if o is not entity and o.get("type") in SHORT_FORM_TYPES
                 and " " in _key(o["name"]) and _key(o["name"]).split()[0] == name), None)


def corpus_types() -> dict:
    """Majority entity type per name across all documents (the LLM occasionally mistypes a name)."""
    counts: dict = {}
    for p in (EXTRACTED / "entities").glob("*_entities.json"):
        ents = _read(p)
        for e in ents:
            if _short_form_of(e, ents):
                continue
            c = counts.setdefault(_key(e["name"]), {})
            c[e["type"]] = c.get(e["type"], 0) + 1
    return {k: max(c, key=lambda t: (c[t], t)) for k, c in counts.items()}


def _absorb(keep: dict, other: dict) -> None:
    have = {r["paragraph_index"] for r in keep["source_refs"]}
    keep["source_refs"] += [r for r in other.get("source_refs", []) if r["paragraph_index"] not in have]
    keep["aliases"] = sorted((set(keep.get("aliases") or []) | set(other.get("aliases") or [])
                              | {other["name"]}) - {keep["name"]})


def normalise(entities: list, types: dict) -> int:
    """Fold short forms into their full name, apply the corpus-majority type, merge same-name duplicates."""
    changed = 0
    for e in list(entities):
        full = _short_form_of(e, entities)
        if full is not None:
            _absorb(full, e)
            entities.remove(e)
            changed += 1
    merged = {}
    for e in entities:
        t = types.get(_key(e["name"]), e["type"])
        if t != e["type"]:
            e["type"] = t
            changed += 1
        k = _key(e["name"])
        if k in merged:
            _absorb(merged[k], e)
            changed += 1
        else:
            merged[k] = e
    entities[:] = list(merged.values())
    return changed


def _read(path: Path) -> list:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _key(name: str) -> str:
    return re.sub(r"\s+", " ", name or "").strip().lower()


def _terms(entity: dict, reserved: Optional[dict] = None) -> list:
    names = [entity.get("name") or ""] + list(entity.get("aliases") or [])
    words = (entity.get("name") or "").split()
    # "Vantro" for "Vantro Trading", unless that word names something of another type (e.g. the nation Orvan)
    if entity.get("type") in SHORT_FORM_TYPES and len(words) > 1 and len(words[0]) >= 4 \
            and words[0][0].isupper() and (reserved or {}).get(words[0].lower(), entity["type"]) == entity["type"]:
        names.append(words[0])
    return sorted({n.strip() for n in names if len(n.strip()) >= MIN_ALIAS_LEN}, key=len, reverse=True)


def _pattern(entity: dict, reserved: Optional[dict] = None):
    terms = _terms(entity, reserved)
    if not terms:
        return None
    return re.compile(r"(?<![\w])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w])", re.IGNORECASE)


def _ref(doc, para) -> dict:
    return {"doc_id": doc.doc_id, "file_name": doc.file_name, "page_number": para.page_number,
            "paragraph_index": para.paragraph_index, "text_snippet": para.raw_text[:120] + "..."}


def fill(doc_ids, use_llm: bool, dry_run: bool):
    store = ResolvedEvidenceStore()
    extractor = EntityExtractor() if use_llm else None
    totals = {"documents_changed": 0, "llm_paragraphs": 0, "new_entities": 0, "llm_mentions_dropped": 0,
              "mentions_added": 0, "fact_paragraphs_linked_before": 0, "fact_paragraphs_linked_after": 0,
              "fact_paragraphs": 0, "types_normalised": 0}
    types = corpus_types()

    for doc_id in doc_ids:
        path = EXTRACTED / "entities" / f"{doc_id}_entities.json"
        entities = _read(path)
        doc = store.document(doc_id)
        paras = {p.paragraph_index: p for p in doc.paragraphs}
        body = dict(store.body_paragraphs(doc_id))
        fact_paras = {f.source_ref.paragraph_index for f in store.facts(doc_id)} & set(body)

        def covered():
            return {r["paragraph_index"] for e in entities for r in e.get("source_refs", [])}

        before = covered()
        totals["fact_paragraphs"] += len(fact_paras)
        totals["fact_paragraphs_linked_before"] += len(fact_paras & before)
        added = 0

        # 1-2. LLM pass on fact paragraphs that no entity links to, with verification
        gaps = sorted(fact_paras - before)
        if extractor and gaps and not dry_run:
            totals["llm_paragraphs"] += len(gaps)
            sub = doc.model_copy(deep=True)
            sub.paragraphs = [paras[i].model_copy(update={"raw_text": body[i]}) for i in gaps]
            by_key = {_key(e["name"]): e for e in entities}
            for found in extractor.extract_from_document(sub):
                data = found.model_dump(mode="json")
                pat = _pattern(data, types)
                refs = []
                for r in data["source_refs"]:
                    i = r["paragraph_index"]
                    if i in gaps and pat and pat.search(body[i]):
                        refs.append(_ref(doc, paras[i]))
                    else:
                        totals["llm_mentions_dropped"] += 1
                if not refs:
                    continue
                existing = by_key.get(_key(data["name"]))
                if existing is None:
                    data["source_refs"] = refs
                    entities.append(data)
                    by_key[_key(data["name"])] = data
                    totals["new_entities"] += 1
                    added += len(refs)
                else:
                    existing["aliases"] = sorted(set(existing.get("aliases") or []) | set(data["aliases"] or [])
                                                 - {existing["name"]})
                    have = {r["paragraph_index"] for r in existing["source_refs"]}
                    new = [r for r in refs if r["paragraph_index"] not in have]
                    existing["source_refs"] += new
                    added += len(new)

        # 3. Consistent types, then deterministic linking of literal mentions across all body paragraphs
        fixed = normalise(entities, types)
        totals["types_normalised"] += fixed
        added += fixed
        reserved = {**types, **{_key(n): e["type"] for e in entities
                                for n in [e["name"]] + list(e.get("aliases") or [])}}
        for e in entities:
            pat = _pattern(e, reserved)
            if not pat:
                continue
            have = {r["paragraph_index"] for r in e.get("source_refs", [])}
            for i, text in body.items():
                if i not in have and pat.search(text):
                    e.setdefault("source_refs", []).append(_ref(doc, paras[i]))
                    added += 1
            e["source_refs"].sort(key=lambda r: r["paragraph_index"])
            e["mentions_count"] = max(len(e["source_refs"]), 1)

        after = covered()
        totals["fact_paragraphs_linked_after"] += len(fact_paras & after)
        if added:
            totals["documents_changed"] += 1
            totals["mentions_added"] += added
            log.info("%s: +%d mention(s); fact paragraphs linked %d -> %d of %d", doc_id, added,
                     len(fact_paras & before), len(fact_paras & after), len(fact_paras))
            if not dry_run:
                path.write_text(json.dumps(entities, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Complete entity mentions for evidence documents (append-only)")
    p.add_argument("--doc-id", default=None)
    p.add_argument("--no-llm", action="store_true", help="only the deterministic linking pass")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    ids = [a.doc_id.upper()] if a.doc_id else ResolvedEvidenceStore().evidence_ids()
    fill(ids, use_llm=not a.no_llm, dry_run=a.dry_run)
