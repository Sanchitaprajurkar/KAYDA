"""
Rebuild the Neo4j evidence graph from the trap-resolved dataset (output of resolve_traps.py).

Evidence labels hold only clean, citable data, so agents can traverse them without filtering:
  (:Document)-[:HAS_PARAGRAPH]->(:Paragraph)<-[:SOURCED_FROM]-(:Fact)
  (:Paragraph)-[:MENTIONS]->(:Entity)

Documents removed by a trap rule become (:ExcludedDocument) nodes with no paragraphs or facts.
The reason is drawn as an edge to the document responsible:
  RETRACTED_BY, TAINTED_BY, SUPERSEDED_BY, CONTRADICTED_BY, DUPLICATE_OF

Everything runs in one write transaction; stale nodes from earlier syncs are removed.
Document.case_id values written by case runs are preserved.

Run (from the folder containing .env):
  python -m heimdall.sync_graph [--resolved-dir <path>]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from heimdall.graph.client import Neo4jClient
from heimdall.ingest_to_neon import DEFAULT_RESOLVED, load_resolved

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GraphSync")

TRAP_EDGES = {
    "RETRACTED": "RETRACTED_BY",
    "TAINTED": "TAINTED_BY",
    "SUPERSEDED": "SUPERSEDED_BY",
    "RUMOUR": "CONTRADICTED_BY",
    "TABLOID": "CONTRADICTED_BY",
    "UNRELIABLE_SOURCE": "CONTRADICTED_BY",
    "DUPLICATE_OF": "DUPLICATE_OF",
}

SCHEMA = [
    "CREATE CONSTRAINT doc_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT para_id_unique IF NOT EXISTS FOR (p:Paragraph) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE",
    "CREATE CONSTRAINT fact_id_unique IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT excluded_doc_id_unique IF NOT EXISTS FOR (x:ExcludedDocument) REQUIRE x.id IS UNIQUE",
    "CREATE INDEX doc_pub_date_idx IF NOT EXISTS FOR (d:Document) ON (d.pub_date)",
    "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
    "CREATE INDEX fact_category_idx IF NOT EXISTS FOR (f:Fact) ON (f.category)",
]


def build_batches(data: dict) -> dict:
    docs, paras, facts, mentions = [], [], [], []
    entities = {}  # (lower name, type) -> entity row; first spelling wins
    for d in data["docs"]:
        did, meta, res = d["doc_id"], d.get("manifest_meta") or {}, d.get("resolution") or {}
        docs.append({
            "id": did, "title": meta.get("title"), "file_name": d.get("file_name"),
            "format": meta.get("format") or d.get("format"), "pub_date": meta.get("pub_date"),
            "pub_time": meta.get("pub_time"), "event_id": meta.get("event_id"),
            "source_name": meta.get("source_name"), "source_type": meta.get("source_type"),
            "reliability_tier": int(meta.get("reliability") or 2), "country": meta.get("country"),
            "sector": meta.get("sector"), "sector_original": res.get("sector_original"),
            "encoding_repaired": res.get("encoding_repaired"),
            "aliases": [a["alias_doc_id"] for a in res.get("aliases", [])],
            "removed_paragraphs": res.get("removed_paragraphs", []),
        })
        for p in d.get("paragraphs", []):
            paras.append({"id": f"{did}-P{p['paragraph_index']}", "doc_id": did,
                          "paragraph_index": p["paragraph_index"], "page_number": p.get("page_number"),
                          "text": p["raw_text"]})
        for f in data["facts"][did]:
            ref = f.get("source_ref") or {}
            facts.append({
                "id": f["fact_id"], "doc_id": did, "category": f.get("category"), "subject": f.get("subject"),
                "statement": f.get("statement"), "date_mentioned": f.get("date_mentioned"),
                "numeric_value": f.get("numeric_value"), "unit": f.get("unit"),
                "reliability_tier": f.get("reliability_tier"), "is_as_of_valid": f.get("is_as_of_valid"),
                "confidence": f.get("confidence"), "assertion_status": f.get("assertion_status"),
                "evidence_status": f.get("evidence_status"), "verbatim_quote": ref.get("text_snippet"),
                "para_id": f"{ref.get('doc_id', did)}-P{ref.get('paragraph_index')}",
            })
        for e in data["entities"][did]:
            key = (e.get("name", "").strip().lower(), e.get("type"))
            if not key[0]:
                continue
            ent = entities.setdefault(key, {"name": e["name"].strip(), "type": e["type"],
                                            "description": e.get("description"), "aliases": set()})
            ent["aliases"] |= {a for a in e.get("aliases", []) if a}
            for r in e.get("source_refs", []):
                if r.get("paragraph_index") is not None:
                    mentions.append({"para_id": f"{r.get('doc_id', did)}-P{r['paragraph_index']}",
                                     "name": ent["name"], "type": ent["type"]})

    excluded, trap_edges = [], []
    for x in data["excluded"]:
        excluded.append({
            "id": x["doc_id"], "title": x.get("title"), "source_name": x.get("source_name"),
            "source_type": x.get("source_type"), "reliability_tier": int(x.get("reliability") or 2),
            "pub_date": x.get("pub_date"), "event_id": x.get("event_id"),
            "reason": x["reasons"][0]["reason"], "detail": x["reasons"][0].get("detail"),
            "all_reasons": json.dumps(x["reasons"], ensure_ascii=False),
        })
        for r in x["reasons"]:
            rel = TRAP_EDGES.get(r["reason"])
            if rel and r.get("related_doc_id"):
                trap_edges.append({"rel": rel, "from": x["doc_id"], "to": r["related_doc_id"],
                                   "reason": r["reason"], "detail": r.get("detail")})
                if r["reason"] in ("RUMOUR", "TABLOID", "UNRELIABLE_SOURCE"):
                    # the detail lists every contradicting document, not just the first
                    for other in sorted(set(_doc_ids(r.get("detail", ""))) - {r["related_doc_id"]}):
                        trap_edges.append({"rel": rel, "from": x["doc_id"], "to": other,
                                           "reason": r["reason"], "detail": r.get("detail")})
    for a in data["aliases"]:
        for e in trap_edges:
            if e["rel"] == "DUPLICATE_OF" and e["from"] == a["alias_doc_id"]:
                e["kind"] = a["kind"]

    for ent in entities.values():
        ent["aliases"] = sorted(ent["aliases"])
    return {"docs": docs, "paras": paras, "facts": facts, "entities": list(entities.values()),
            "mentions": [dict(t) for t in {tuple(sorted(m.items())) for m in mentions}],
            "excluded": excluded, "trap_edges": trap_edges}


def _doc_ids(text: str):
    return re.findall(r"\b[A-Z]{3}-\d{4}\b", text or "")


def sync(tx, b: dict) -> dict:
    doc_ids = [d["id"] for d in b["docs"]]
    para_ids = [p["id"] for p in b["paras"]]
    fact_ids = [f["id"] for f in b["facts"]]
    excluded_ids = [x["id"] for x in b["excluded"]]
    removed = {}

    def run(cypher, **params):
        return tx.run(cypher, **params).data()

    # 1. Remove stale data from earlier syncs.
    removed["documents"] = run("""
        MATCH (d:Document) WHERE NOT d.id IN $ids
        OPTIONAL MATCH (d)-[:HAS_PARAGRAPH]->(p:Paragraph)
        DETACH DELETE p, d RETURN count(DISTINCT d) AS n""", ids=doc_ids)[0]["n"]
    removed["paragraphs"] = run("""
        MATCH (p:Paragraph) WHERE NOT p.id IN $ids DETACH DELETE p RETURN count(p) AS n""",
        ids=para_ids)[0]["n"]
    removed["facts"] = run("""
        MATCH (f:Fact) WHERE NOT f.id IN $ids DETACH DELETE f RETURN count(f) AS n""", ids=fact_ids)[0]["n"]
    run("MATCH (x:ExcludedDocument) WHERE NOT x.id IN $ids DETACH DELETE x", ids=excluded_ids)
    run("MATCH ()-[r:RETRACTED_BY|TAINTED_BY|SUPERSEDED_BY|CONTRADICTED_BY|DUPLICATE_OF]->() DELETE r")
    run("MATCH (:Paragraph)-[m:MENTIONS]->(:Entity) DELETE m")
    run("MATCH (:Fact)-[s:SOURCED_FROM]->() DELETE s")

    # 2. Evidence.
    run("""
        UNWIND $batch AS d
        MERGE (n:Document {id: d.id})
        SET n.title = d.title, n.file_name = d.file_name, n.format = d.format, n.pub_date = d.pub_date,
            n.pub_time = d.pub_time, n.event_id = d.event_id, n.source_name = d.source_name,
            n.source_type = d.source_type, n.reliability_tier = d.reliability_tier, n.country = d.country,
            n.sector = d.sector, n.sector_original = d.sector_original,
            n.encoding_repaired = d.encoding_repaired, n.aliases = d.aliases,
            n.removed_paragraphs = d.removed_paragraphs, n.is_as_of_valid = true""", batch=b["docs"])
    run("""
        UNWIND $batch AS p
        MERGE (n:Paragraph {id: p.id})
        SET n.doc_id = p.doc_id, n.paragraph_index = p.paragraph_index,
            n.page_number = p.page_number, n.text = p.text
        WITH n, p MATCH (d:Document {id: p.doc_id}) MERGE (d)-[:HAS_PARAGRAPH]->(n)""", batch=b["paras"])
    run("""
        UNWIND $batch AS f
        MERGE (n:Fact {id: f.id})
        SET n.doc_id = f.doc_id, n.category = f.category, n.subject = f.subject, n.statement = f.statement,
            n.date_mentioned = f.date_mentioned, n.numeric_value = f.numeric_value, n.unit = f.unit,
            n.reliability_tier = f.reliability_tier, n.is_as_of_valid = f.is_as_of_valid,
            n.confidence = f.confidence, n.assertion_status = f.assertion_status,
            n.evidence_status = f.evidence_status, n.verbatim_quote = f.verbatim_quote
        WITH n, f MATCH (p:Paragraph {id: f.para_id}) MERGE (n)-[:SOURCED_FROM]->(p)""", batch=b["facts"])
    run("""
        UNWIND $batch AS e
        MERGE (n:Entity {name: e.name, type: e.type})
        SET n.description = e.description, n.aliases = e.aliases""", batch=b["entities"])
    run("""
        UNWIND $batch AS m
        MATCH (p:Paragraph {id: m.para_id}), (e:Entity {name: m.name, type: m.type})
        MERGE (p)-[:MENTIONS]->(e)""", batch=b["mentions"])
    removed["entities"] = run("""
        MATCH (e:Entity) WHERE NOT (e)<-[:MENTIONS]-() DETACH DELETE e RETURN count(e) AS n""")[0]["n"]
    run("MATCH (e:Entity) SET e.mentions_count = COUNT { (e)<-[:MENTIONS]-() }")

    # 3. Excluded documents and the trap chains.
    run("""
        UNWIND $batch AS x
        MERGE (n:ExcludedDocument {id: x.id})
        SET n.title = x.title, n.source_name = x.source_name, n.source_type = x.source_type,
            n.reliability_tier = x.reliability_tier, n.pub_date = x.pub_date, n.event_id = x.event_id,
            n.reason = x.reason, n.detail = x.detail, n.all_reasons = x.all_reasons""", batch=b["excluded"])
    for rel in sorted({e["rel"] for e in b["trap_edges"]}):
        run(f"""
            UNWIND $batch AS e
            MATCH (a:ExcludedDocument {{id: e.from}})
            MATCH (t) WHERE t.id = e.to AND (t:Document OR t:ExcludedDocument)
            MERGE (a)-[r:{rel}]->(t)
            SET r.reason = e.reason, r.detail = e.detail, r.kind = e.kind""",
            batch=[e for e in b["trap_edges"] if e["rel"] == rel])
    return removed


def run_sync(resolved: Path):
    if not (resolved / "trap_log.json").exists():
        log.error("%s not found. Run 'python -m heimdall.resolve_traps' first.", resolved)
        sys.exit(1)
    client = Neo4jClient()
    if not client.is_connected:
        log.error("Neo4j is not reachable or not configured (NEO4J_URI / NEO4J_PASSWORD). "
                  "Run from the folder containing .env.")
        sys.exit(1)

    batches = build_batches(load_resolved(resolved))
    driver = client.get_driver()
    for stmt in SCHEMA:
        client.execute_query(stmt)
    with driver.session(database=client.database) as session:
        removed = session.execute_write(sync, batches)

    print("\n" + "=" * 60)
    print("  Neo4j graph rebuilt from resolved data (single transaction)")
    print(f"  removed stale     : {removed}")
    for k in ("docs", "paras", "facts", "entities", "mentions", "excluded", "trap_edges"):
        print(f"  {k:<18}: {len(batches[k])}")
    print("=" * 60)
    client.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Rebuild the Neo4j evidence graph from resolved data")
    p.add_argument("--resolved-dir", default=str(DEFAULT_RESOLVED))
    run_sync(Path(p.parse_args().resolved_dir))
