"""
Ingest the trap-resolved dataset (output of resolve_traps.py) into Neon PostgreSQL.

Evidence tables hold only clean, citable data:
  documents, paragraphs, facts, fact_sources, entities, entity_aliases, entity_mentions
Everything kept out of evidence stays explainable:
  excluded_documents   documents removed by a trap rule, with reason and responsible document
  flagged_facts        facts that are not citable (unverified, or from an excluded document)
  document_aliases     duplicate / fallback doc IDs -> canonical doc ID
  audit_log            one row per trap action (case_id = 'PREPROCESS', agent = 'heimdall')
  case_documents       which documents belong to a case (filled at case time)

The whole load runs in one transaction: on any error Neon is left unchanged.

Run (from the folder containing .env):
  python -m heimdall.ingest_to_neon [--resolved-dir <path>] [--drop-recreate]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from psycopg2.extras import Json, execute_values

from heimdall.storage.neon_client import get_neon_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("NeonIngest")

DEFAULT_RESOLVED = Path(__file__).resolve().parent.parent / "resolved_data"
PREPROCESS_CASE = "PREPROCESS"

DDL = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id             TEXT PRIMARY KEY,
    event_id           TEXT,
    title              TEXT,
    source_name        TEXT,
    source_type        TEXT,
    pub_date           DATE,
    pub_time           TEXT,
    country            TEXT,
    sector             TEXT,
    sector_original    TEXT,
    reliability_tier   INT,
    file_name          TEXT,
    format             TEXT,
    encoding_repaired  TEXT,
    removed_paragraphs INT[],
    ingested_at        TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paragraphs (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    paragraph_index INT  NOT NULL,
    page_number     INT,
    raw_text        TEXT NOT NULL,
    char_count      INT,
    word_count      INT,
    UNIQUE (doc_id, paragraph_index)
);

CREATE TABLE IF NOT EXISTS facts (
    fact_id          TEXT PRIMARY KEY,
    doc_id           TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    category         TEXT NOT NULL,
    subject          TEXT NOT NULL,
    statement        TEXT NOT NULL,
    date_mentioned   TEXT,
    numeric_value    DOUBLE PRECISION,
    unit             TEXT,
    reliability_tier INT,
    is_as_of_valid   BOOLEAN,
    confidence       DOUBLE PRECISION,
    assertion_status TEXT,
    evidence_status  TEXT NOT NULL,
    validation_notes TEXT[],
    ingested_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_sources (
    id              BIGSERIAL PRIMARY KEY,
    fact_id         TEXT NOT NULL REFERENCES facts(fact_id) ON DELETE CASCADE,
    doc_id          TEXT NOT NULL,
    paragraph_index INT  NOT NULL,
    page_number     INT,
    verbatim_quote  TEXT,
    UNIQUE (fact_id, doc_id, paragraph_index)
);

CREATE TABLE IF NOT EXISTS entities (
    entity_id      TEXT PRIMARY KEY,
    doc_id         TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    type           TEXT NOT NULL,
    description    TEXT,
    mentions_count INT DEFAULT 1,
    ingested_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS entity_aliases (
    id        BIGSERIAL PRIMARY KEY,
    entity_id TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    alias     TEXT NOT NULL,
    UNIQUE (entity_id, alias)
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    id              BIGSERIAL PRIMARY KEY,
    entity_id       TEXT NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    doc_id          TEXT NOT NULL,
    paragraph_index INT  NOT NULL,
    UNIQUE (entity_id, doc_id, paragraph_index)
);

CREATE TABLE IF NOT EXISTS case_documents (
    case_id    VARCHAR(64) NOT NULL,
    doc_id     TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    added_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (case_id, doc_id)
);

CREATE TABLE IF NOT EXISTS document_aliases (
    alias_doc_id     TEXT PRIMARY KEY,
    canonical_doc_id TEXT NOT NULL REFERENCES documents(doc_id) ON DELETE CASCADE,
    kind             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS excluded_documents (
    doc_id          TEXT PRIMARY KEY,
    title           TEXT,
    source_name     TEXT,
    source_type     TEXT,
    reliability     TEXT,
    pub_date        TEXT,
    event_id        TEXT,
    reason          TEXT NOT NULL,
    related_doc_id  TEXT,
    detail          TEXT,
    all_reasons     JSONB
);

CREATE TABLE IF NOT EXISTS flagged_facts (
    fact_id          TEXT PRIMARY KEY,
    doc_id           TEXT NOT NULL,
    category         TEXT,
    subject          TEXT,
    statement        TEXT,
    date_mentioned   TEXT,
    numeric_value    DOUBLE PRECISION,
    unit             TEXT,
    reliability_tier INT,
    is_as_of_valid   BOOLEAN,
    confidence       DOUBLE PRECISION,
    assertion_status TEXT,
    evidence_status  TEXT,
    validation_notes TEXT[],
    paragraph_index  INT,
    page_number      INT,
    verbatim_quote   TEXT,
    quarantine_reason TEXT,
    related_doc_id   TEXT,
    all_reasons      JSONB,
    ingested_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         SERIAL PRIMARY KEY,
    case_id    VARCHAR(64),
    agent      VARCHAR(16) NOT NULL,
    action     VARCHAR(64) NOT NULL,
    details    TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bring tables created by earlier versions of this script up to date.
ALTER TABLE documents ADD COLUMN IF NOT EXISTS event_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pub_time TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS sector_original TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS encoding_repaired TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS removed_paragraphs INT[];
ALTER TABLE flagged_facts DROP CONSTRAINT IF EXISTS flagged_facts_doc_id_fkey;
ALTER TABLE flagged_facts ADD COLUMN IF NOT EXISTS quarantine_reason TEXT;
ALTER TABLE flagged_facts ADD COLUMN IF NOT EXISTS related_doc_id TEXT;
ALTER TABLE flagged_facts ADD COLUMN IF NOT EXISTS all_reasons JSONB;
"""

DROP_DDL = """
DROP TABLE IF EXISTS case_documents, document_aliases, entity_mentions, entity_aliases, entities,
                     fact_sources, facts, paragraphs, documents, excluded_documents, flagged_facts CASCADE;
"""


def _int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _fact_row(f: dict, doc_id: str) -> tuple:
    return (
        f["fact_id"], doc_id, f.get("category", "OTHER"), f.get("subject", ""), f.get("statement", ""),
        f.get("date_mentioned"), f.get("numeric_value"), f.get("unit"), f.get("reliability_tier"),
        f.get("is_as_of_valid"), f.get("confidence"), f.get("assertion_status"),
        f.get("evidence_status", "UNVERIFIED"), f.get("validation_notes") or [],
    )


def load_resolved(resolved: Path) -> dict:
    docs = [_read(p) for p in sorted((resolved / "documents").glob("*.json"))]
    data = {"docs": docs, "facts": {}, "entities": {}}
    for d in docs:
        did = d["doc_id"]
        fp, ep = resolved / "facts" / f"{did}_facts.json", resolved / "entities" / f"{did}_entities.json"
        data["facts"][did] = _read(fp) if fp.exists() else []
        data["entities"][did] = _read(ep) if ep.exists() else []
    data["excluded"] = _read(resolved / "quarantine" / "excluded_documents.json")
    data["rejected"] = _read(resolved / "quarantine" / "rejected_facts.json")
    data["aliases"] = _read(resolved / "document_aliases.json")
    data["trap_log"] = _read(resolved / "trap_log.json")
    return data


def ingest(cur, data: dict) -> dict:
    counts = {k: 0 for k in ("documents", "paragraphs", "facts", "fact_sources", "entities",
                             "entity_aliases", "entity_mentions", "excluded_documents",
                             "flagged_facts", "document_aliases", "audit_log")}
    doc_ids = [d["doc_id"] for d in data["docs"]]

    # Documents no longer in the evidence set are removed (cascades to their children).
    cur.execute("DELETE FROM documents WHERE NOT (doc_id = ANY(%s))", (doc_ids,))

    for d in data["docs"]:
        did, meta, res = d["doc_id"], d.get("manifest_meta") or {}, d.get("resolution") or {}
        # Replace this document's children; the documents row is upserted so case links survive.
        for table in ("paragraphs", "facts", "entities"):
            cur.execute(f"DELETE FROM {table} WHERE doc_id = %s", (did,))
        cur.execute("""
            INSERT INTO documents (doc_id, event_id, title, source_name, source_type, pub_date, pub_time,
                                   country, sector, sector_original, reliability_tier, file_name, format,
                                   encoding_repaired, removed_paragraphs)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (doc_id) DO UPDATE SET
                event_id=EXCLUDED.event_id, title=EXCLUDED.title, source_name=EXCLUDED.source_name,
                source_type=EXCLUDED.source_type, pub_date=EXCLUDED.pub_date, pub_time=EXCLUDED.pub_time,
                country=EXCLUDED.country, sector=EXCLUDED.sector, sector_original=EXCLUDED.sector_original,
                reliability_tier=EXCLUDED.reliability_tier, file_name=EXCLUDED.file_name,
                format=EXCLUDED.format, encoding_repaired=EXCLUDED.encoding_repaired,
                removed_paragraphs=EXCLUDED.removed_paragraphs, ingested_at=NOW()
        """, (
            did, meta.get("event_id"), meta.get("title"), meta.get("source_name"), meta.get("source_type"),
            meta.get("pub_date") or None, meta.get("pub_time"), meta.get("country"), meta.get("sector"),
            res.get("sector_original"), _int(meta.get("reliability"), 2), d.get("file_name"),
            meta.get("format") or d.get("format"), res.get("encoding_repaired"),
            res.get("removed_paragraphs") or [],
        ))
        counts["documents"] += 1

        paras = [(did, p["paragraph_index"], p.get("page_number"), p["raw_text"],
                  p.get("char_count"), p.get("word_count")) for p in d.get("paragraphs", [])]
        execute_values(cur, "INSERT INTO paragraphs (doc_id, paragraph_index, page_number, raw_text, "
                            "char_count, word_count) VALUES %s", paras)
        counts["paragraphs"] += len(paras)

        facts = data["facts"][did]
        execute_values(cur, "INSERT INTO facts (fact_id, doc_id, category, subject, statement, date_mentioned, "
                            "numeric_value, unit, reliability_tier, is_as_of_valid, confidence, "
                            "assertion_status, evidence_status, validation_notes) VALUES %s",
                       [_fact_row(f, did) for f in facts])
        sources = [(f["fact_id"], f["source_ref"].get("doc_id", did), f["source_ref"].get("paragraph_index"),
                    f["source_ref"].get("page_number"), f["source_ref"].get("text_snippet"))
                   for f in facts if f.get("source_ref")]
        execute_values(cur, "INSERT INTO fact_sources (fact_id, doc_id, paragraph_index, page_number, "
                            "verbatim_quote) VALUES %s ON CONFLICT DO NOTHING", sources)
        counts["facts"] += len(facts)
        counts["fact_sources"] += len(sources)

        ents, aliases, mentions = [], set(), set()
        for e in data["entities"][did]:
            eid = uuid.uuid4().hex[:12]
            ents.append((eid, did, e.get("name", ""), e.get("type", "OTHER"), e.get("description"),
                         e.get("mentions_count", 1)))
            aliases |= {(eid, a) for a in e.get("aliases", []) if a}
            mentions |= {(eid, r.get("doc_id", did), r.get("paragraph_index"))
                         for r in e.get("source_refs", []) if r.get("paragraph_index") is not None}
        execute_values(cur, "INSERT INTO entities (entity_id, doc_id, name, type, description, mentions_count) "
                            "VALUES %s", ents)
        execute_values(cur, "INSERT INTO entity_aliases (entity_id, alias) VALUES %s", list(aliases))
        execute_values(cur, "INSERT INTO entity_mentions (entity_id, doc_id, paragraph_index) VALUES %s",
                       list(mentions))
        counts["entities"] += len(ents)
        counts["entity_aliases"] += len(aliases)
        counts["entity_mentions"] += len(mentions)

    # Quarantine and alias tables are rebuilt in full.
    cur.execute("TRUNCATE excluded_documents, flagged_facts, document_aliases")
    execute_values(cur, "INSERT INTO excluded_documents (doc_id, title, source_name, source_type, reliability, "
                        "pub_date, event_id, reason, related_doc_id, detail, all_reasons) VALUES %s", [
        (x["doc_id"], x.get("title"), x.get("source_name"), x.get("source_type"), str(x.get("reliability")),
         x.get("pub_date"), x.get("event_id"), x["reasons"][0]["reason"], x["reasons"][0].get("related_doc_id"),
         x["reasons"][0].get("detail"), Json(x["reasons"]))
        for x in data["excluded"]])
    counts["excluded_documents"] = len(data["excluded"])

    execute_values(cur, "INSERT INTO flagged_facts (fact_id, doc_id, category, subject, statement, date_mentioned, "
                        "numeric_value, unit, reliability_tier, is_as_of_valid, confidence, assertion_status, "
                        "evidence_status, validation_notes, paragraph_index, page_number, verbatim_quote, "
                        "quarantine_reason, related_doc_id, all_reasons) VALUES %s ON CONFLICT (fact_id) DO NOTHING", [
        _fact_row(f, f["doc_id"]) + (
            (f.get("source_ref") or {}).get("paragraph_index"), (f.get("source_ref") or {}).get("page_number"),
            (f.get("source_ref") or {}).get("text_snippet"), f["quarantine_reasons"][0]["reason"],
            f["quarantine_reasons"][0].get("related_doc_id"), Json(f["quarantine_reasons"]))
        for f in data["rejected"]])
    counts["flagged_facts"] = len(data["rejected"])

    execute_values(cur, "INSERT INTO document_aliases (alias_doc_id, canonical_doc_id, kind) VALUES %s",
                   [(a["alias_doc_id"], a["canonical_doc_id"], a["kind"]) for a in data["aliases"]])
    counts["document_aliases"] = len(data["aliases"])

    cur.execute("DELETE FROM audit_log WHERE case_id = %s AND agent = 'heimdall'", (PREPROCESS_CASE,))
    execute_values(cur, "INSERT INTO audit_log (case_id, agent, action, details) VALUES %s", [
        (PREPROCESS_CASE, "heimdall", e["action"][:64], json.dumps(e, ensure_ascii=False))
        for e in data["trap_log"]])
    counts["audit_log"] = len(data["trap_log"])
    return counts


def run(resolved: Path, drop_recreate: bool):
    for required in ("documents", "facts", "quarantine/excluded_documents.json", "trap_log.json"):
        if not (resolved / required).exists():
            log.error("%s not found. Run 'python -m heimdall.resolve_traps' first.", resolved / required)
            sys.exit(1)

    client = get_neon_client()
    if not client.is_configured:
        log.error("NEON_DATABASE_URL is not set. Run from the folder containing .env, or export it.")
        sys.exit(1)
    ping = client.ping()
    if not ping["connected"]:
        log.error("Cannot reach Neon: %s", ping.get("error"))
        sys.exit(1)
    log.info("Connected  db=%s  latency=%.1f ms", ping["database"], ping["latency_ms"])

    data = load_resolved(resolved)
    log.info("Loaded resolved dataset: %d documents, %d excluded, %d trap actions",
             len(data["docs"]), len(data["excluded"]), len(data["trap_log"]))

    with client.get_connection() as conn:
        with conn.cursor() as cur:
            if drop_recreate:
                log.warning("Dropping Heimdall evidence tables ...")
                cur.execute(DROP_DDL)
            cur.execute(DDL)
            counts = ingest(cur, data)
        conn.commit()

    print("\n" + "=" * 60)
    print("  Ingestion complete (single transaction)")
    for k, v in counts.items():
        print(f"  {k:<20}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Ingest the trap-resolved dataset into Neon PostgreSQL")
    p.add_argument("--resolved-dir", default=str(DEFAULT_RESOLVED))
    p.add_argument("--drop-recreate", action="store_true",
                   help="DROP the evidence tables before creating them (audit_log is never dropped)")
    args = p.parse_args()
    run(Path(args.resolved_dir), args.drop_recreate)
