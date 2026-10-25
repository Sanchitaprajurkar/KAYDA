"""Command-line runner for the Heimdall Evidence-Intake Agent."""

import argparse
import sys
from agent_1.agent import HeimdallAgent


def main():
    parser = argparse.ArgumentParser(
        description="Run Heimdall Evidence Intake Agent on Runemark documents."
    )
    parser.add_argument(
        "--doc-a",
        type=str,
        default="ORV-0033",
        help="First document ID (e.g., ORV-0033)",
    )
    parser.add_argument(
        "--doc-b",
        type=str,
        default="ORV-0034",
        help="Second document ID (e.g., ORV-0034)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? Give a low and high range for wheat and maize imports.",
        help="Target intelligence question",
    )
    parser.add_argument(
        "--case-id",
        type=str,
        default=None,
        help="Custom case ID (optional)",
    )

    args = parser.parse_args()

    print(f"\n=======================================================")
    print(f" Heimdall Agent: Starting Intake Pipeline")
    print(f" Document A: {args.doc_a}")
    print(f" Document B: {args.doc_b}")
    print(f" Target Query: {args.query}")
    print(f"=======================================================\n")

    agent = HeimdallAgent()
    try:
        report = agent.analyze_dual_documents(
            doc_id_a=args.doc_a,
            doc_id_b=args.doc_b,
            target_query=args.query,
            case_id=args.case_id,
        )
    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n[SUCCESS] Intake Analysis Completed Successfully!")
    print(f"- Case ID: {report.case_id}")
    print(f"- Event Status: {report.event_verification.status.value} (Confidence: {report.event_verification.confidence_score})")
    print(f"- Extracted Facts: {len(report.facts)}")
    print(f"- Discovered Entities: {len(report.entities)}")
    print(f"- Contradictions / Discrepancies: {len(report.contradictions)}")
    print(f"- Missing Info Gaps: {len(report.missing_information)}")
    print(f"- Neo4j Graph Status: {report.knowledge_graph_summary.graph_status} ({report.knowledge_graph_summary.total_nodes} nodes, {report.knowledge_graph_summary.total_relationships} edges)")
    print(f"- Report Saved To: reports/{report.case_id}.json\n")


if __name__ == "__main__":
    main()
