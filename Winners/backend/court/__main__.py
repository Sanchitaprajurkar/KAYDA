"""Open a case and watch the trial in the terminal.

  python -m backend.court "As of 25 January 2027, how exposed are Midgard and Tolan ...?"
  python -m backend.court --offline            # deterministic stand-ins for every LLM call, no API cost
"""

import argparse
import sys

SAMPLE = ("As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? "
          "Give a low and high range for wheat and maize imports.")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description="Trial of the Nine Realms: run one courtroom case")
    p.add_argument("question", nargs="?", default=SAMPLE)
    p.add_argument("--case-id", default=None)
    p.add_argument("--offline", action="store_true", help="scripted LLM stand-ins; no OpenAI, Neon or Neo4j")
    a = p.parse_args()

    from backend.court.procedure import CourtSession
    if a.offline:
        from backend.court.scripted import ScriptedLLM, offline_heimdall
        llm = ScriptedLLM()
        session = CourtSession(heimdall=offline_heimdall(llm), llm_backends={k: llm for k in ("THOR", "LOKI", "ODIN")})
    else:
        session = CourtSession()
    result = session.run(a.question, case_id=a.case_id)
    print(f"\n{result['status']}: {result['dir']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
