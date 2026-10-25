"""Batch parses all 76 Runemark documents (PDF, TXT, DOCX) and caches structured outputs."""

import json
import time
from pathlib import Path
from typing import Dict, Any

from agent_1.extraction.manifest_service import ManifestService
from agent_1.parsers.parser_factory import ParserFactory
from agent_1.graph.client import Neo4jClient
from agent_1.config import settings


def parse_entire_corpus(sync_to_neo4j: bool = True):
    print("=================================================================")
    print(" Runemark Corpus Ingestion: Parsing All 76 Documents")
    print("=================================================================\n")

    manifest_service = ManifestService()
    parser_factory = ParserFactory()
    catalog = manifest_service.catalog

    output_dir = settings.BASE_DIR / "parsed_docs"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Catalog Event: {catalog.name} ({catalog.event_id})")
    print(f"Total Documents to Parse: {len(catalog.documents)}")
    print(f"Destination Cache Directory: {output_dir.resolve()}\n")

    start_time = time.time()
    parsed_records = []
    stats = {
        "total": len(catalog.documents),
        "success": 0,
        "failed": 0,
        "by_format": {"PDF": 0, "TXT": 0, "DOCX": 0},
        "total_paragraphs": 0,
        "clock_violations": 0,
    }

    neo4j_doc_batch = []
    neo4j_para_batch = []

    for idx, doc_meta in enumerate(catalog.documents, start=1):
        doc_id = doc_meta.doc_id
        fmt = doc_meta.format.upper() if doc_meta.format else "UNKNOWN"
        is_valid = doc_meta.is_valid_as_of(settings.AS_OF_DATE)
        if not is_valid:
            stats["clock_violations"] += 1

        print(f"[{idx:02d}/{len(catalog.documents)}] Parsing {doc_id} ({fmt}) - '{doc_meta.title[:40]}...' ", end="", flush=True)

        try:
            parsed = parser_factory.parse_by_doc_id(doc_id, manifest_service)
            doc_dict = parsed.model_dump()

            # Save individual JSON parsed document
            doc_file = output_dir / f"{doc_id}.json"
            with open(doc_file, "w", encoding="utf-8") as f:
                json.dump(doc_dict, f, indent=2)

            parsed_records.append(doc_dict)
            stats["success"] += 1
            stats["by_format"][fmt] = stats["by_format"].get(fmt, 0) + 1
            stats["total_paragraphs"] += parsed.total_paragraphs

            print(f"OK ({parsed.total_paragraphs} ¶s, {parsed.total_pages or 1} pages)")

            if sync_to_neo4j:
                neo4j_doc_batch.append({
                    "id": parsed.doc_id,
                    "title": doc_meta.title,
                    "file_name": parsed.file_name,
                    "format": parsed.format.value,
                    "pub_date": doc_meta.pub_date,
                    "tier": doc_meta.reliability_tier,
                    "sector": doc_meta.sector,
                    "country": doc_meta.country,
                    "is_as_of_valid": is_valid,
                })
                for p in parsed.paragraphs:
                    neo4j_para_batch.append({
                        "id": f"{parsed.doc_id}-P{p.paragraph_index}",
                        "doc_id": parsed.doc_id,
                        "p_idx": p.paragraph_index,
                        "page_num": p.page_number,
                        "text": p.raw_text[:500],
                    })

        except Exception as e:
            stats["failed"] += 1
            print(f"FAILED: {e}")

    # Save complete merged corpus index
    merged_path = output_dir / "_all_parsed_documents.json"
    with open(merged_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "pack": catalog.pack,
                "as_of": catalog.as_of,
                "stats": stats,
                "documents": parsed_records,
            },
            f,
            indent=2,
        )

    # Sync baseline document hierarchy to Neo4j Aura if requested
    if sync_to_neo4j and neo4j_doc_batch:
        print("\n--> Syncing 76 Documents & Paragraphs to Neo4j Aura...")
        try:
            neo4j_client = Neo4jClient()
            if neo4j_client.is_connected:
                # 1. Ingest Documents
                neo4j_client.execute_query(
                    """
                    UNWIND $batch as doc
                    MERGE (d:Document {id: doc.id})
                    SET d.title = doc.title,
                        d.file_name = doc.file_name,
                        d.format = doc.format,
                        d.pub_date = doc.pub_date,
                        d.reliability_tier = doc.tier,
                        d.sector = doc.sector,
                        d.country = doc.country,
                        d.is_as_of_valid = doc.is_as_of_valid
                    """,
                    {"batch": neo4j_doc_batch},
                )
                # 2. Ingest Paragraphs in chunks of 500 for network efficiency
                chunk_size = 500
                for i in range(0, len(neo4j_para_batch), chunk_size):
                    chunk = neo4j_para_batch[i : i + chunk_size]
                    neo4j_client.execute_query(
                        """
                        UNWIND $batch as p
                        MERGE (para:Paragraph {id: p.id})
                        SET para.doc_id = p.doc_id,
                            para.paragraph_index = p.p_idx,
                            para.page_number = p.page_num,
                            para.text = p.text
                        WITH para, p
                        MATCH (d:Document {id: p.doc_id})
                        MERGE (d)-[:HAS_PARAGRAPH]->(para)
                        """,
                        {"batch": chunk},
                    )
                print("--> Neo4j Aura Synchronization Complete!")
            else:
                print("--> Neo4j Aura offline/skipped.")
        except Exception as err:
            print(f"--> Warning: Neo4j sync encountered error: {err}")

    elapsed = time.time() - start_time
    print("\n=================================================================")
    print(" Ingestion Summary")
    print(f"- Total Documents: {stats['total']}")
    print(f"- Successfully Parsed: {stats['success']}/{stats['total']}")
    print(f"- Total Paragraphs Extracted: {stats['total_paragraphs']}")
    print(f"- PDF Files: {stats['by_format'].get('PDF', 0)}")
    print(f"- TXT Files: {stats['by_format'].get('TXT', 0)}")
    print(f"- DOCX Files: {stats['by_format'].get('DOCX', 0)}")
    print(f"- Clock Violations Flagged (> 2027-01-25): {stats['clock_violations']}")
    print(f"- Outputs Saved To: {output_dir}")
    print(f"- Time Taken: {elapsed:.2f} seconds")
    print("=================================================================\n")


if __name__ == "__main__":
    parse_entire_corpus(sync_to_neo4j=True)
