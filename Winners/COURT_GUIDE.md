# Trial of the Nine Realms - Court System Guide

## Overview

Your court system is **already designed to accept dynamic queries**. It's not using "stored sessions" - it's using intelligent caching to avoid redundant LLM calls for facts that have already been evaluated.

## How It Works

### 1. Query Input → Heimdall (Case Builder)

```python
session = CourtSession()
result = session.run(query="Your dynamic query here", case_id=None)
```

**Heimdall's Tasks:**
- Parse the user query
- Extract: event, countries, commodities, as-of date
- Search document repository (Runemark)
- Retrieve relevant documents
- Verify the event is real and active
- Build case evidence report

### 2. Event Verification

Heimdall checks:
- Source reliability
- Conflicting reports
- Corrections/retractions
- Whether event is active as of the specified date

**Verdicts:**
- `CONFIRMED` → Proceed to trial
- `DISPUTED` → Proceed to trial
- `UNCONFIRMED`, `DISPROVEN`, `RETRACTED` → No trial

### 3. Trial Rounds (Up to 3 Runs)

Each run consists of:

#### **Round 1: Claims (Parallel)**
- **Thor** files high-exposure claims with evidence citations
- **Loki** files low-exposure claims with evidence citations
- Both agents work in parallel

#### **Round 2: Cross-Examination (Parallel)**
- **Thor** attacks Loki's claims
- **Loki** attacks Thor's claims
- Both provide counter-evidence

#### **Round 3: Defense (Parallel)**
- **Thor** defends his claims or concedes
- **Loki** defends her claims or concedes
- Both can provide new evidence

#### **Odin's Judicial Review**
- Reviews all claims, attacks, defenses
- Validates citations
- Classifies claims: ESTABLISHED, CONTESTED, CONCEDED
- Determines exposure ranges
- **Sufficiency check**: Are there evidence gaps?

### 4. Remand Process

If Odin finds evidence gaps:
- Odin lists missing evidence
- Case is sent back to **Heimdall**
- Heimdall conducts targeted research
- New documents added to case file
- **Next run begins** with updated evidence

This continues until:
- All evidence gaps filled (COMPLETE)
- Max runs reached (3 runs)
- Time limit exceeded (600 seconds)
- No new evidence found

### 5. Final Briefing

Odin generates:
- Exposure ranges for each country-commodity pair
- Classification of each claim
- List of unresolved gaps (if incomplete)
- Full markdown briefing document

## Understanding the Caching

### Two Types of Cache:

1. **Verdict Cache** (`backend/cache/*.json`)
   - Caches LLM judgments on fact stances
   - Caches contradiction detection between fact pairs
   - **Purpose**: Avoid re-evaluating same facts across cases

2. **Agent Memory** (`memory/*.db` SQLite databases)
   - Stores agent decisions per case
   - Prevents duplicate research requests
   - **Purpose**: Avoid redundant work within same case

### Why Caching Exists:

- **Efficiency**: Don't ask LLM same question twice
- **Consistency**: Same facts get same evaluation
- **Cost**: Reduces API calls to OpenAI
- **Speed**: Faster execution

### This is NOT "stored sessions":

Each query is processed fresh:
- Heimdall searches documents dynamically
- Thor and Loki build new arguments
- Odin makes new rulings
- Only fact-level evaluations are cached

## Running Dynamic Queries

### Method 1: Using the new runner script

```bash
# Interactive mode - prompts for query
python run_court.py --interactive

# With specific query
python run_court.py --query "As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement?"

# Clear all caches for completely fresh run
python run_court.py --clear-cache --query "Your query here"

# Offline mode (no API calls, uses scripted responses)
python run_court.py --offline
```

### Method 2: Using the court module directly

```bash
# Default sample query
python -m backend.court

# Custom query
python -m backend.court "Your custom query here"

# With specific case ID
python -m backend.court "Your query" --case-id CASE-E5-001

# Offline mode
python -m backend.court "Your query" --offline
```

### Method 3: Programmatically in Python

```python
from backend.court.procedure import CourtSession

# Create session
session = CourtSession()

# Run with dynamic query
result = session.run(
    query="As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement?",
    case_id=None  # Auto-generate
)

# Check results
print(f"Status: {result['status']}")
print(f"Case saved to: {result['dir']}")
for r in result['ranges']:
    print(f"{r.country} {r.sector}: Thor {r.thor} | Loki {r.loki} | Odin {r.odin}")
```

## Understanding the Output

### Log Files

Each case creates a directory: `cases/CASE-XXXX-NNNN/`

```
cases/CASE-XXXX-0001/
├── log.jsonl              # Event-by-event log (machine-readable)
├── briefing.md            # Final briefing (human-readable)
├── briefing.json          # Final briefing (structured)
├── meta.json              # Case metadata
├── run_1/
│   ├── case_file.json     # Evidence available in run 1
│   ├── transcript.json    # Claims, attacks, defenses
│   └── rulings.json       # Odin's rulings and ranges
├── run_2/                 # If case sent back to Heimdall
│   └── ...
└── run_3/                 # If case sent back again
    └── ...
```

### Terminal Output

The system prints a live view:

```
=== HEIMDALL - CASE FILE (run 1) ===
  Event EVT-001: CONFIRMED (confidence 0.97); active at 2027-01-25: True
  34 documents: ORV-0001, ORV-0002, ...

=== RUN 1 - ROUND 1 - CLAIMS ===
  THOR  T1 [Midgard|Maize] 50.18-70.01%  High exposure due to corridor dependence  (ORV-0005, ATL-0008, ...)
  LOKI  L1 [Midgard|Maize] 30.00-45.00%  Alternative suppliers reduce risk  (ATL-0012, ...)

=== RUN 1 - ROUND 2 - CROSS-EXAMINATION ===
  THOR  attacks L1 (insufficient capacity, INSUFFICIENT_VOLUME): Alternative supply lacks capacity  [ORV-0007]
  LOKI  attacks T1 (overstated, OVERSTATED_BASELINE): Baseline imports are lower  [ATL-0014]

=== RUN 1 - ROUND 3 - DEFEND OR CONCEDE ===
  LOKI  DEFENDS L1: New evidence shows spare capacity  [new: ATL-0015]
  THOR  DEFENDS T1: Baseline calculation is correct  [new: ORV-0009]

=== RUN 1 - ODIN RULES ===
  ODIN  T1: ACCEPT -> CONTESTED (exposure_estimate) Calculation methodology valid but range disputed
  ODIN  L1: ACCEPT -> CONTESTED (exposure_estimate) Alternative supply argument partially supported
  ODIN  missing: Tolan wheat trade data
  ODIN  missing: Midgard wheat alternative suppliers

=== ODIN SENDS THE CASE BACK -> HEIMDALL RE-SEARCH (run 2) ===
  Heimdall run 2: new evidence ['ATL-0017', 'ORV-0011']; Found 2 new documents on Tolan wheat
```

## Clearing Caches

### When to clear caches:

1. **Testing**: You want to see full execution without any cached decisions
2. **Model changes**: You switched to a different LLM model
3. **Logic changes**: You modified agent prompts or reasoning
4. **Debugging**: You suspect cache corruption

### How to clear:

```bash
# Option 1: Use the runner script
python run_court.py --clear-cache

# Option 2: Manual deletion
# Delete cache files
rm backend/cache/*.json

# Delete agent memory
rm memory/*.db

# Option 3: Delete specific agent memory
rm memory/thor.db
rm memory/loki.db
rm memory/odin.db
rm memory/heimdall.db
```

## Configuration

### Environment Variables

```bash
# Override default memory directory
export COURT_MEMORY_DIR=/path/to/custom/memory

# Database connection (for Heimdall document store)
export DATABASE_URL=postgresql://...

# Neo4j connection (if using graph database)
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=your_password
```

### Court Limits (in `procedure.py`)

```python
ROUNDS_PER_RUN = 3                           # Claims, attacks, defense
MAX_RUNS = 3                                 # Maximum remand cycles
MAX_CLAIMS_PER_SIDE = 8                      # Max claims per agent
MAX_TOOL_CALLS_PER_AGENT_PER_RUN = 16        # Max document searches
MAX_TOKENS_PER_AGENT_PER_RUN = 40_000        # LLM token budget
CASE_WALLCLOCK_S = 600                       # 10-minute time limit
```

## Typical Workflow

```
1. User provides query
   ↓
2. Heimdall builds case file
   ↓
3. Event verification
   ↓
4. If confirmed → Trial begins
   ↓
5. Round 1: Thor and Loki file claims
   ↓
6. Round 2: Cross-examination
   ↓
7. Round 3: Defense or concession
   ↓
8. Odin reviews and rules
   ↓
9. Check sufficiency
   ↓
10a. If complete → Final briefing
10b. If gaps → Back to Heimdall (step 2) for run 2
```

## Common Issues

### Issue: "No documents found"
**Cause**: Document repository empty or query terms don't match
**Solution**: Check that extracted documents exist in `extracted_data/combined/`

### Issue: "Event not verified"
**Cause**: Heimdall couldn't confirm the event from documents
**Solution**: Review event verification output; check document content

### Issue: "All claims CONTESTED"
**Cause**: Insufficient evidence to establish ranges
**Solution**: Add more relevant documents or review evidence quality

### Issue: "Same results every time"
**Cause**: Caching working as designed
**Solution**: If you want fresh execution, use `--clear-cache`

## Next Steps

To see your full courtroom session flow:

```bash
# Fresh execution with no cached decisions
python run_court.py --clear-cache --query "As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? Give low and high ranges for wheat and maize imports."
```

This will show:
- ✅ Heimdall building case from scratch
- ✅ Thor filing high-exposure claims with citations
- ✅ Loki filing low-exposure claims with citations
- ✅ Cross-examination with attacks
- ✅ Defense rounds
- ✅ Odin's rulings
- ✅ Remand process if evidence gaps exist
- ✅ Final briefing with exposure ranges
