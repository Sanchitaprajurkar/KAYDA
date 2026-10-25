"""Batch parses all 76 Runemark documents (PDF, TXT, DOCX) and caches structured outputs."""

import json
import time
from pathlib import Path
from typing import Dict, Any

from agent_1.extraction.manifest_service import ManifestService
from agent_1.parsers.parser_factory import ParserFactory
from agent_1.config import settings


def parse_entire_corpus():
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
    print("=================================================================")
    print("Next: extract_all_facts -> resolve_traps -> validate_data -> ingest_to_neon / sync_graph")
    print("(The graph is only built from trap-resolved data, never from raw parses.)\n")


if __name__ == "__main__":
    parse_entire_corpus()
