"""Command-line runner for the Heimdall Evidence-Intake Agent."""

import argparse
import sys

from agent_1.agent import HeimdallAgent

SAMPLE_QUERY = ("As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor "
                "agreement? Give a low and high range for wheat and maize imports.")


def main():
    parser = argparse.ArgumentParser(description="Build a Heimdall case file from trap-resolved evidence.")
    parser.add_argument("--query", default=None, help="Case question (default: the dev-pack sample question)")
    parser.add_argument("--event-id", default=None, help="Event ID instead of a query, e.g. E5")
    parser.add_argument("--case-id", default=None, help="Custom case ID (optional)")
    parser.add_argument("--max-documents", type=int, default=40)
    parser.add_argument("--research", default=None, metavar="REQUEST",
                        help="Re-search an existing case (needs --case-id): what Odin asked Heimdall to look for")
    args = parser.parse_args()
    query = args.query or (None if args.event_id else SAMPLE_QUERY)
    if args.research and not args.case_id:
        parser.error("--research needs --case-id")

    try:
        agent = HeimdallAgent()
        report = (agent.re_search(args.case_id, args.research) if args.research else
                  agent.build_case_file(query=query, event_id=args.event_id, case_id=args.case_id,
                                        max_documents=args.max_documents))
    except Exception as e:
        print(f"\n[ERROR] Case file failed: {e}", file=sys.stderr)
        sys.exit(1)

    v, s = report.event_verification, report.case_scope
    print("\n" + "=" * 70)
    print(f" Case {report.case_id}  (run {report.run_number})")
    print("=" * 70)
    for r in report.research_history:
        print(f" Run {r.run_number} re-search: '{r.request}' -> new {r.new_document_ids or 'none'} | {r.note}")
    print(f" Scope        : event {s.event_id} | countries {s.countries} | commodities {s.commodities} | "
          f"as of {s.as_of_date}")
    print(f" Retrieved    : {len(report.retrieved_documents)} documents | excluded relevant: "
          f"{[r.doc_id for r in report.rejected_evidence]}")
    print(f" Facts        : {len(report.facts)} cited | {len(report.evidence_digest.metrics)} metrics | "
          f"{len(report.contradictions)} contradictions")
    print(f" Verdict      : {v.status.value} (confidence {v.confidence_score}) | active at as-of: "
          f"{v.is_active_at_as_of}")
    print(f" Summary      : {v.summary}")
    for r in v.reasoning:
        print(f"   - {r}")
    for m in report.missing_information:
        print(f" Missing      : {m.topic} - {m.impact_on_assessment}")
    if "neon" in report.metadata:
        print(f" Neon         : {report.metadata['neon']}")
    print(f" Graph        : {report.knowledge_graph_summary.graph_status}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
