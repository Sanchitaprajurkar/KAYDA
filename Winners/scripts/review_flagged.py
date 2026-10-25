"""Interactive reviewer for flagged (UNCERTAIN/REJECTED) extracted facts.

Usage:
    python review_flagged.py                         # review all flagged facts
    python review_flagged.py --status UNCERTAIN      # only UNCERTAIN
    python review_flagged.py --status REJECTED       # only REJECTED
    python review_flagged.py --doc ATL-0006          # single document
    python review_flagged.py --auto-reject-all       # reject everything (dry run OK)
    python review_flagged.py --dry-run               # print decisions without saving

Controls while reviewing:
    a  = approve  → move to verified facts, mark VERIFIED, add analyst note
    r  = reject   → discard entirely from flagged list
    s  = skip     → leave in flagged list unchanged
    q  = quit     → save all decisions made so far and exit
"""

import argparse
import io
import json
import os
import sys
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Optional

# Force UTF-8 output on Windows so box-drawing characters print cleanly
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).parent
EXTRACTED_DIR = BASE_DIR / "extracted_data"
FLAGGED_FILE = EXTRACTED_DIR / "_all_flagged_facts.json"
ALL_FACTS_FILE = EXTRACTED_DIR / "_all_extracted_facts.json"
FACTS_DIR = EXTRACTED_DIR / "facts"
FLAGGED_DOC_DIR = EXTRACTED_DIR / "flagged"

# Search for parsed_docs in the script's directory first, then subdirectories.
# This handles the case where the module was moved into a sub-package (e.g. agent_1/).
def _find_parsed_dir() -> Path:
    for candidate in [
        BASE_DIR / "parsed_docs",
        BASE_DIR / "agent_1" / "parsed_docs",
    ]:
        if candidate.is_dir():
            return candidate
    return BASE_DIR / "parsed_docs"  # fallback (will report files as missing)

PARSED_DIR = _find_parsed_dir()

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
CYAN = "\033[36m"
DIM = "\033[2m"


def color(text: str, code: str) -> str:
    return f"{code}{text}{RESET}"


def hr(char: str = "─", width: int = 72) -> str:
    return char * width


def load_json(path: Path) -> list:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class ParaLookup:
    """Result of looking up a paragraph in a parsed doc."""
    __slots__ = ("text", "found", "quote_present", "reason")

    def __init__(self, text: Optional[str], found: bool, quote_present: bool, reason: str = ""):
        self.text = text
        self.found = found          # True when the paragraph itself exists
        self.quote_present = quote_present  # True when the verbatim quote is in the paragraph
        self.reason = reason        # Human-readable note when something is wrong


def get_paragraph(doc_id: str, para_index: int, verbatim_quote: str = "") -> ParaLookup:
    """Resolve doc_id → paragraph_index → check verbatim quote presence."""
    doc_file = PARSED_DIR / f"{doc_id}.json"
    if not doc_file.exists():
        return ParaLookup(None, False, False,
                          f"Parsed file not found: {doc_file}")

    with open(doc_file, encoding="utf-8") as f:
        doc = json.load(f)

    para_text: Optional[str] = None
    for p in doc.get("paragraphs", []):
        if p["paragraph_index"] == para_index:
            para_text = p["raw_text"]
            break

    if para_text is None:
        available = [p["paragraph_index"] for p in doc.get("paragraphs", [])]
        return ParaLookup(None, False, False,
                          f"¶{para_index} not in document (has ¶{min(available)}–¶{max(available)} if {available} else 'none')")

    if not verbatim_quote:
        return ParaLookup(para_text, True, False,
                          "No verbatim quote to check")

    import re as _re
    def _norm(s: str) -> str:
        s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
        return _re.sub(r"\s+", " ", s).strip().lower()

    quote_norm = _norm(verbatim_quote.strip(' "'))
    # Also strip the paragraph's own [Pn] label before comparing
    para_stripped = _re.sub(r"^\s*\[P\d+\]\s*", "", para_text)
    para_norm = _norm(para_stripped)

    if quote_norm and quote_norm in para_norm:
        return ParaLookup(para_text, True, True, "")

    # Try the full paragraph (including label)
    if quote_norm and quote_norm in _norm(para_text):
        return ParaLookup(para_text, True, True, "")

    # Quote is absent
    return ParaLookup(para_text, True, False,
                      f"Verbatim quote not found in ¶{para_index}")


def truncate(text: str, width: int = 70) -> str:
    return text if len(text) <= width else text[:width - 3] + "..."


def print_fact(fact: dict, index: int, total: int) -> ParaLookup:
    """Render the fact card and return the paragraph lookup so prompt_decision can gate approval."""
    ref = fact["source_ref"]
    doc_id = ref["doc_id"]
    para_idx = ref["paragraph_index"]
    quote = ref.get("text_snippet") or ""

    lookup = get_paragraph(doc_id, para_idx, verbatim_quote=quote)

    os.system("cls" if os.name == "nt" else "clear")
    print(color(hr("═"), BOLD))
    print(color(f"  Flagged fact {index} of {total}", BOLD))
    print(color(hr("═"), BOLD))

    status = fact.get("evidence_status", "?")
    status_color = YELLOW if status == "UNCERTAIN" else RED
    print(f"  Status  : {color(status, status_color)}   Confidence: {fact.get('confidence', '?')}")
    print(f"  Doc     : {color(doc_id, CYAN)}   ¶{para_idx}   Tier {fact.get('reliability_tier','?')}")
    print(f"  Category: {fact.get('category','?')}")
    print()

    print(color("  STATEMENT", BOLD))
    print(f"  {fact.get('statement','')}")
    print()

    assertion = fact.get("assertion_status")
    if assertion:
        print(f"  Framing : {assertion}")

    date_val = fact.get("date_mentioned")
    num_val = fact.get("numeric_value")
    unit = fact.get("unit")
    if date_val or num_val is not None:
        parts = []
        if date_val:
            parts.append(f"date={date_val}")
        if num_val is not None:
            parts.append(f"value={num_val} {unit or ''}".strip())
        print(f"  Values  : {', '.join(parts)}")

    print()
    print(color("  VALIDATION NOTES", BOLD))
    for note in fact.get("validation_notes", []):
        note_color = RED if "Verifier" in note or "not found" in note or "not stated" in note else YELLOW
        print(f"  {color('•', note_color)} {note}")

    print()
    print(color("  VERBATIM QUOTE (from extraction)", BOLD))
    print(f"  {color(chr(8220) + quote + chr(8221), DIM)}")

    print()
    print(color("  SOURCE PARAGRAPH (from parsed doc)", BOLD))

    if not lookup.found:
        # Paragraph genuinely doesn't exist — show why and block approval
        print(f"  {color('[' + lookup.reason + ']', RED)}")
    else:
        # Paragraph found — render it, highlighting the quote if present
        import re
        import unicodedata

        def _norm_hi(s: str) -> str:
            s = unicodedata.normalize("NFKC", s)
            s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
            return re.sub(r"\s+", " ", s).strip().lower()

        # Strip the [Pn] label for display only
        para_display = re.sub(r"^\s*\[P\d+\]\s*", "", lookup.text)
        para_lower = _norm_hi(para_display)
        quote_lower = _norm_hi(quote.strip(' "'))

        p_colored = para_display
        if quote_lower and quote_lower in para_lower:
            start = para_lower.index(quote_lower)
            end = start + len(quote_lower)
            p_colored = (para_display[:start]
                         + color(para_display[start:end], GREEN + BOLD)
                         + para_display[end:])
        elif not lookup.quote_present:
            # Quote absent — show paragraph in dim + warn
            p_colored = color(para_display, DIM)
            print(f"  {color('[quote not found in this paragraph]', YELLOW)}")

        # Word-wrap at 68 chars, respecting ANSI escapes (count raw chars only)
        words = p_colored.split(" ")
        lines, line, line_len = [], "", 0
        for word in words:
            raw_len = len(re.sub(r"\033\[[0-9;]*m", "", word))
            if line_len and line_len + 1 + raw_len > 68:
                lines.append(line)
                line, line_len = word, raw_len
            else:
                line = (line + " " + word).lstrip()
                line_len = line_len + 1 + raw_len if line_len else raw_len
        if line:
            lines.append(line)
        for ln in lines:
            print(f"  {ln}")

    # Provenance status banner
    print()
    if not lookup.found:
        print(color(f"  ⚠  CANNOT APPROVE: {lookup.reason}", RED + BOLD))
    elif not lookup.quote_present:
        print(color(f"  ⚠  Quote absent from ¶{para_idx} — approve only if statement is clearly supported above.", YELLOW))
    else:
        print(color(f"  ✓  Quote confirmed in ¶{para_idx}", GREEN))

    # Controls — disable 'a' when paragraph not found
    print()
    print(color(hr(), DIM))
    if lookup.found:
        print(f"  {color('a', GREEN)} approve  |  {color('r', RED)} reject  |  {color('s', DIM)} skip  |  {color('q', BOLD)} quit")
    else:
        print(f"  {color('a', DIM)} approve (blocked)  |  {color('r', RED)} reject  |  {color('s', DIM)} skip  |  {color('q', BOLD)} quit")
    print(color(hr(), DIM))

    return lookup


def prompt_decision(lookup: ParaLookup) -> str:
    while True:
        try:
            ch = input("  Your choice: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "q"
        if ch == "a" and not lookup.found:
            print(f"  {color('✗', RED)} Approval blocked: paragraph could not be verified in parsed_docs.")
            print(f"  {color('  Use r to reject or s to skip.', DIM)}")
            continue
        if ch in ("a", "r", "s", "q"):
            return ch
        print(f"  {color('?', YELLOW)} Please type a, r, s, or q.")


def apply_decisions(
    flagged_all: list,
    decisions: dict,   # fact_id -> "approve" | "reject" | "skip"
    dry_run: bool,
) -> None:
    if not decisions:
        print("No decisions to apply.")
        return

    approved_ids = {fid for fid, d in decisions.items() if d == "approve"}
    rejected_ids = {fid for fid, d in decisions.items() if d == "reject"}

    approved_facts = [f for f in flagged_all if f["fact_id"] in approved_ids]
    remaining_flagged = [f for f in flagged_all if f["fact_id"] not in approved_ids and f["fact_id"] not in rejected_ids]

    if dry_run:
        print(f"\n{color('[DRY RUN]', YELLOW)} Would approve {len(approved_ids)}, reject {len(rejected_ids)}, "
              f"leave {len(remaining_flagged)} in flagged list.")
        return

    # Promote approved facts to VERIFIED
    for fact in approved_facts:
        fact["evidence_status"] = "VERIFIED"
        fact["confidence"] = max(fact.get("confidence", 0.0), 0.7)  # floor for manually approved
        notes = fact.setdefault("validation_notes", [])
        notes.append("Manually approved by analyst during review_flagged.py session")

    # --- Update master verified facts file ---
    verified_all = load_json(ALL_FACTS_FILE)
    existing_ids = {f["fact_id"] for f in verified_all}
    new_verified = [f for f in approved_facts if f["fact_id"] not in existing_ids]
    verified_all.extend(new_verified)
    save_json(ALL_FACTS_FILE, verified_all)

    # --- Update per-document facts files ---
    by_doc = defaultdict(list)
    for fact in new_verified:
        by_doc[fact["source_ref"]["doc_id"]].append(fact)

    for doc_id, new_facts in by_doc.items():
        doc_facts_file = FACTS_DIR / f"{doc_id}_facts.json"
        existing = load_json(doc_facts_file)
        existing_ids_doc = {f["fact_id"] for f in existing}
        existing.extend(f for f in new_facts if f["fact_id"] not in existing_ids_doc)
        save_json(doc_facts_file, existing)

    # --- Update flagged master file (remove approved + rejected) ---
    save_json(FLAGGED_FILE, remaining_flagged)

    # --- Update per-document flagged files ---
    removed_ids = approved_ids | rejected_ids
    by_doc_flagged = defaultdict(list)
    for fact in flagged_all:
        if fact["fact_id"] not in removed_ids:
            by_doc_flagged[fact["source_ref"]["doc_id"]].append(fact)

    all_docs_in_flagged = {f["source_ref"]["doc_id"] for f in flagged_all}
    for doc_id in all_docs_in_flagged:
        doc_flagged_file = FLAGGED_DOC_DIR / f"{doc_id}_flagged.json"
        save_json(doc_flagged_file, by_doc_flagged.get(doc_id, []))

    print(f"\n{color('✓', GREEN)} Saved: {len(new_verified)} approved → verified, "
          f"{len(rejected_ids)} rejected, {len(remaining_flagged)} remain flagged.")


def main():
    parser = argparse.ArgumentParser(description="Review flagged facts interactively.")
    parser.add_argument("--status", choices=["UNCERTAIN", "REJECTED"],
                        help="Only review facts with this evidence status")
    parser.add_argument("--doc", help="Only review facts from this document ID (e.g. ATL-0006)")
    parser.add_argument("--auto-reject-all", action="store_true",
                        help="Reject every flagged fact without prompting")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print decisions without writing any files")
    args = parser.parse_args()

    flagged_all = load_json(FLAGGED_FILE)
    if not flagged_all:
        print("No flagged facts found. Nothing to review.")
        sys.exit(0)

    # Filter to what the user asked for
    subset = flagged_all
    if args.status:
        subset = [f for f in subset if f.get("evidence_status") == args.status]
    if args.doc:
        subset = [f for f in subset if f["source_ref"]["doc_id"].upper() == args.doc.upper()]

    if not subset:
        print(f"No flagged facts match your filters ({len(flagged_all)} total flagged).")
        sys.exit(0)

    total = len(subset)

    # Summary header
    print(color(hr("═"), BOLD))
    print(color(f"  Heimdall Flagged Fact Reviewer  ({total} facts to review)", BOLD))
    print(color(hr("═"), BOLD))
    from collections import Counter
    status_counts = Counter(f.get("evidence_status") for f in subset)
    for s, n in sorted(status_counts.items()):
        col = YELLOW if s == "UNCERTAIN" else RED
        print(f"  {color(s, col)}: {n}")
    print()

    if args.auto_reject_all:
        decisions = {f["fact_id"]: "reject" for f in subset}
        apply_decisions(flagged_all, decisions, dry_run=args.dry_run)
        return

    decisions = {}
    for i, fact in enumerate(subset, start=1):
        lookup = print_fact(fact, i, total)
        choice = prompt_decision(lookup)
        if choice == "q":
            print(f"\n  Quitting after {i - 1} reviewed.")
            break
        decisions[fact["fact_id"]] = {"a": "approve", "r": "reject", "s": "skip"}[choice]
        label = color("APPROVED", GREEN) if choice == "a" else (color("REJECTED", RED) if choice == "r" else color("skipped", DIM))
        print(f"  {label}")

    apply_decisions(flagged_all, decisions, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
