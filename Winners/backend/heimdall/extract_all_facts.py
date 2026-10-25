"""Bulk extraction script: Runs FactExtractor and EntityExtractor across all 76 parsed documents in parsed_docs/."""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, List

# Ensure parent directory (containing 'heimdall') is in sys.path for direct script execution
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from heimdall.config import settings
from heimdall.models.document import ParsedDocument
from heimdall.models.evidence import ExtractedFact, ExtractedEntity
from heimdall.extraction.fact_extractor import FactExtractor
from heimdall.extraction.entity_extractor import EntityExtractor

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BulkExtractor")


def run_bulk_extraction(
    parsed_dir: Path,
    output_dir: Path,
    limit: int = 0,
    skip_existing: bool = True,
    sync_to_neo4j: bool = False,
    single_doc_id: str = None,
):
    print("=================================================================")
    print(" Heimdall Bulk Fact & Entity Extraction Pipeline")
    print("=================================================================\n")

    if not parsed_dir.exists():
        fallback = settings.BASE_DIR / "heimdall" / "parsed_docs"
        if fallback.exists():
            parsed_dir = fallback
        else:
            print(f"[ERROR] parsed_docs directory not found at: {parsed_dir.resolve()}")
            print("Run 'python parse_all_docs.py' first.")
            sys.exit(1)

    facts_dir = output_dir / "facts"
    entities_dir = output_dir / "entities"
    combined_dir = output_dir / "combined"
    flagged_dir = output_dir / "flagged"

    flagged_dir.mkdir(parents=True, exist_ok=True)
    facts_dir.mkdir(parents=True, exist_ok=True)
    entities_dir.mkdir(parents=True, exist_ok=True)
    combined_dir.mkdir(parents=True, exist_ok=True)

    # Collect all parsed document JSON files (ignoring index files like _all_parsed_documents.json)
    doc_files = sorted([f for f in parsed_dir.glob("*.json") if not f.name.startswith("_")])

    if single_doc_id:
        doc_files = [f for f in doc_files if f.stem.upper() == single_doc_id.upper()]
        if not doc_files:
            print(f"[ERROR] Could not find parsed file for document ID: {single_doc_id}")
            sys.exit(1)

    if limit > 0:
        doc_files = doc_files[:limit]

    total_files = len(doc_files)
    print(f"Total Documents to Process: {total_files}")
    print(f"Source Directory: {parsed_dir.resolve()}")
    print(f"Output Directory: {output_dir.resolve()}")
    print(f"Skip Existing: {skip_existing} | Sync to Neo4j: {sync_to_neo4j}\n")

    fact_extractor = FactExtractor()
    entity_extractor = EntityExtractor()

    stats = {
        "total_documents": total_files,
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "total_facts": 0,
        "total_flagged": 0,
        "total_entities": 0,
    }

    all_facts_master: List[Dict[str, Any]] = []
    all_entities_master: List[Dict[str, Any]] = []
    all_flagged_master: List[Dict[str, Any]] = []

    start_time = time.time()

    for idx, filepath in enumerate(doc_files, start=1):
        doc_id = filepath.stem
        fact_out_file = facts_dir / f"{doc_id}_facts.json"
        entity_out_file = entities_dir / f"{doc_id}_entities.json"
        flagged_out_file = flagged_dir / f"{doc_id}_flagged.json"
        comb_out_file = combined_dir / f"{doc_id}_extracted.json"

        # Check if already extracted
        if skip_existing and fact_out_file.exists() and entity_out_file.exists():
            print(f"[{idx:02d}/{total_files}] Skipping {doc_id} (already extracted)")
            stats["skipped"] += 1
            # Load existing into master lists
            with open(fact_out_file, "r", encoding="utf-8") as f:
                existing_facts = json.load(f)
                stats["total_facts"] += len(existing_facts)
                all_facts_master.extend(existing_facts)
            with open(entity_out_file, "r", encoding="utf-8") as f:
                existing_entities = json.load(f)
                stats["total_entities"] += len(existing_entities)
                all_entities_master.extend(existing_entities)
            if flagged_out_file.exists():
                with open(flagged_out_file, "r", encoding="utf-8") as f:
                    existing_flagged = json.load(f)
                    stats["total_flagged"] += len(existing_flagged)
                    all_flagged_master.extend(existing_flagged)
            continue

        print(f"[{idx:02d}/{total_files}] Extracting facts & entities for {doc_id}... ", end="", flush=True)

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            parsed_doc = ParsedDocument.model_validate(raw_data)

            # Retry loop with exponential backoff for LLM API calls
            retries = 3
            facts = []
            flagged = []
            entities = []
            for attempt in range(retries):
                try:
                    # Only VERIFIED facts are accepted; UNCERTAIN/REJECTED are kept separately for review
                    review = fact_extractor.extract_with_review(parsed_doc)
                    facts, flagged = review.accepted, review.flagged
                    entities = entity_extractor.extract_from_document(parsed_doc)
                    break
                except Exception as api_err:
                    if attempt < retries - 1:
                        time.sleep(2 * (attempt + 1))
                    else:
                        raise api_err

            # Serialize outputs
            facts_serialized = [f.model_dump(mode="json") for f in facts]
            flagged_serialized = [f.model_dump(mode="json") for f in flagged]
            entities_serialized = [e.model_dump() for e in entities]

            # 1. Save separate facts file
            with open(fact_out_file, "w", encoding="utf-8") as f:
                json.dump(facts_serialized, f, indent=2)

            # 1b. Save flagged (uncertain/rejected) facts file
            with open(flagged_out_file, "w", encoding="utf-8") as f:
                json.dump(flagged_serialized, f, indent=2)

            # 2. Save separate entities file
            with open(entity_out_file, "w", encoding="utf-8") as f:
                json.dump(entities_serialized, f, indent=2)

            # 3. Save combined file
            with open(comb_out_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "doc_id": doc_id,
                        "title": parsed_doc.manifest_meta.title if parsed_doc.manifest_meta else "",
                        "facts_count": len(facts_serialized),
                        "flagged_count": len(flagged_serialized),
                        "entities_count": len(entities_serialized),
                        "facts": facts_serialized,
                        "flagged_facts": flagged_serialized,
                        "entities": entities_serialized,
                    },
                    f,
                    indent=2,
                )

            stats["processed"] += 1
            stats["total_facts"] += len(facts_serialized)
            stats["total_flagged"] += len(flagged_serialized)
            stats["total_entities"] += len(entities_serialized)
            all_facts_master.extend(facts_serialized)
            all_flagged_master.extend(flagged_serialized)
            all_entities_master.extend(entities_serialized)

            print(f"DONE ({len(facts)} verified facts, {len(flagged)} flagged, {len(entities)} entities)")

        except Exception as e:
            stats["failed"] += 1
            print(f"FAILED: {e}")

    # Save consolidated master datasets
    print("\n--> Writing consolidated master files...")
    all_facts_path = output_dir / "_all_extracted_facts.json"
    with open(all_facts_path, "w", encoding="utf-8") as f:
        json.dump(all_facts_master, f, indent=2)

    all_flagged_path = output_dir / "_all_flagged_facts.json"
    with open(all_flagged_path, "w", encoding="utf-8") as f:
        json.dump(all_flagged_master, f, indent=2)

    all_entities_path = output_dir / "_all_extracted_entities.json"
    with open(all_entities_path, "w", encoding="utf-8") as f:
        json.dump(all_entities_master, f, indent=2)

    if sync_to_neo4j:
        print("\n--> --sync-graph no longer writes raw extractions to Neo4j (they include trapped facts).")
        print("    Run: resolve_traps -> validate_data -> sync_graph")

    elapsed = time.time() - start_time
    print("\n=================================================================")
    print(" Bulk Extraction Summary")
    print(f"- Total Documents Evaluated: {stats['total_documents']}")
    print(f"- Newly Processed: {stats['processed']}")
    print(f"- Skipped (Already Done): {stats['skipped']}")
    print(f"- Failed: {stats['failed']}")
    print(f"- Total Verified Facts: {stats['total_facts']}")
    print(f"- Total Flagged Facts (uncertain/rejected): {stats['total_flagged']}")
    print(f"- Total Entities Extracted: {stats['total_entities']}")
    print(f"- Output Directory: {output_dir.resolve()}")
    print(f"- Time Taken: {elapsed:.2f} seconds")
    print("=================================================================\n")


def main():
    parser = argparse.ArgumentParser(
        description="Bulk extract facts and entities from all parsed Runemark documents."
    )
    parser.add_argument(
        "--parsed-dir",
        type=str,
        default=str(settings.BASE_DIR / "parsed_docs"),
        help="Path to parsed documents JSON directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(settings.BASE_DIR / "extracted_data"),
        help="Path to save extracted facts and entities",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of documents to process (0 = all 76)",
    )
    parser.add_argument(
        "--doc-id",
        type=str,
        default=None,
        help="Extract a single document ID (e.g. ORV-0002)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing extracted files instead of skipping",
    )
    parser.add_argument(
        "--sync-graph",
        action="store_true",
        help="Batch sync extracted facts and entities to Neo4j Aura",
    )

    args = parser.parse_args()

    run_bulk_extraction(
        parsed_dir=Path(args.parsed_dir),
        output_dir=Path(args.output_dir),
        limit=args.limit,
        skip_existing=not args.overwrite,
        sync_to_neo4j=args.sync_graph,
        single_doc_id=args.doc_id,
    )


if __name__ == "__main__":
    main()
