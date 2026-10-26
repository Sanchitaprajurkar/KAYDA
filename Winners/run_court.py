"""
Trial of the Nine Realms - Interactive Court Session Runner

This script provides a clean interface to run court sessions with dynamic queries.

Usage:
    python run_court.py
    python run_court.py --query "Your custom query"
    python run_court.py --offline  # Use scripted LLM (no API calls)
    python run_court.py --clear-cache  # Clear all caches before running
"""

import argparse
import json
import shutil
import sys
from pathlib import Path


def clear_caches():
    """Clear all cache files and agent memory databases."""
    backend_dir = Path(__file__).parent / "Winners" / "backend"
    
    # Clear JSON cache files
    cache_dir = backend_dir / "cache"
    if cache_dir.exists():
        print(f"Clearing cache directory: {cache_dir}")
        for file in cache_dir.glob("*.json"):
            print(f"  Removing {file.name}")
            file.unlink()
    
    # Clear agent memory databases
    memory_dir = backend_dir.parent / "memory"
    if memory_dir.exists():
        print(f"Clearing agent memory: {memory_dir}")
        for file in memory_dir.glob("*.db"):
            print(f"  Removing {file.name}")
            file.unlink()
    
    print("All caches cleared.\n")


def print_banner():
    """Print the courtroom session banner."""
    banner = """
======================================================================
              TRIAL OF THE NINE REALMS
                 COURTROOM SESSION
======================================================================
"""
    print(banner)


def print_session_info(query, case_id, offline_mode):
    """Print session initialization information."""
    print("SESSION CONFIGURATION:")
    print(f"  Query: {query}")
    print(f"  Case ID: {case_id or 'Auto-generated'}")
    print(f"  Mode: {'OFFLINE (Scripted LLM)' if offline_mode else 'ONLINE (Real LLM)'}")
    print("=" * 70)
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Trial of the Nine Realms: Interactive Court Session",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_court.py
  python run_court.py --query "As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement?"
  python run_court.py --offline --clear-cache
        """
    )
    
    # Default sample query matching your specification
    default_query = (
        "As of 25 January 2027, how exposed are Midgard and Tolan to the end of "
        "the Orvan corridor agreement? Give low and high ranges for wheat and maize imports."
    )
    
    parser.add_argument(
        "--query",
        default=None,
        help="The legal question to investigate (default: sample query about Midgard/Tolan)"
    )
    parser.add_argument(
        "--case-id",
        default=None,
        help="Specific case ID to use (default: auto-generated)"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use scripted LLM responses (no API calls, deterministic results)"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all caches before running (forces fresh execution)"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt for query interactively"
    )
    
    args = parser.parse_args()
    
    # Handle cache clearing
    if args.clear_cache:
        clear_caches()
    
    # Determine the query
    if args.interactive:
        print_banner()
        print("Enter your legal query (or press Enter for default):")
        user_input = input("> ").strip()
        query = user_input if user_input else default_query
    else:
        query = args.query or default_query
    
    # Print session header
    print_banner()
    print_session_info(query, args.case_id, args.offline)
    
    # Import and run the court session
    sys.path.insert(0, str(Path(__file__).parent / "Winners"))
    
    from backend.court.procedure import CourtSession
    
    if args.offline:
        print("[OFFLINE MODE] Using scripted LLM - no API calls will be made\n")
        from backend.court.scripted import ScriptedLLM, offline_heimdall
        llm = ScriptedLLM()
        session = CourtSession(
            heimdall=offline_heimdall(llm),
            llm_backends={"THOR": llm, "LOKI": llm, "ODIN": llm}
        )
    else:
        print("[ONLINE MODE] Using real LLM - API calls will be made\n")
        session = CourtSession()
    
    # Run the court session
    try:
        result = session.run(query, case_id=args.case_id)
        
        # Print results
        print("\n" + "=" * 70)
        print("COURT SESSION COMPLETE")
        print("=" * 70)
        print(f"Status: {result['status']}")
        print(f"Case ID: {result['case_id']}")
        print(f"Runs: {result.get('runs', 'N/A')}")
        print(f"Results saved to: {result['dir']}")
        
        # Print ranges if available
        if 'ranges' in result and result['ranges']:
            print("\nEXPOSURE RANGES:")
            for r in result['ranges']:
                country = r.get('country', 'Unknown')
                sector = r.get('sector', 'Unknown')
                status = r.get('status', 'Unknown')
                thor = r.get('thor', [None, None])
                loki = r.get('loki', [None, None])
                odin = r.get('odin', [None, None])
                
                print(f"\n  {country} | {sector} ({status})")
                positions = r.get('positions') or {}
                print(f"    Thor:  {_fmt_range(thor) if thor else positions.get('THOR', 'No range established')}")
                print(f"    Loki:  {_fmt_range(loki) if loki else positions.get('LOKI', 'No range established')}")
                print(f"    Odin:  {_fmt_range(odin)}")
        
        print("\n" + "=" * 70)
        return 0
        
    except KeyboardInterrupt:
        print("\n\nSession interrupted by user.")
        return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


def _fmt_range(span):
    """Format a range tuple for display."""
    if span and len(span) == 2 and span[0] is not None and span[1] is not None:
        return f"{span[0]:.1f}% - {span[1]:.1f}%"
    if span and len(span) == 2 and span[1] is not None:
        return f"up to {span[1]:.1f}% (no lower bound on the record)"
    return "No range established"


if __name__ == "__main__":
    sys.exit(main())
