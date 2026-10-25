<<<<<<< HEAD
# Nine Realms Backend Services

The primary backend codebase and test suites are maintained under `/backend`.
For full setup, schemas, agents, tools, memory, and tests, see:
[`/backend/README.md`](../../backend/README.md)

Quick run from root:
```bash
python -m pytest backend/tests
uvicorn backend.app.main:app --reload --port 8000
=======
# ⚔️ Trial of the Nine Realms — Adversarial Courtroom Backend

Autonomous adversarial multi-agent system analyzing global supply chain disruptions using an adversarial courtroom paradigm over the invented **Runemark** trade world.

---

## 🏛️ Architecture & The Four Norse-Themed Agents

```
                                    ┌──────────────┐
                                    │     USER     │
                                    └──────┬───────┘
                                           │ Question + As-Of Date
                                           ▼
                               ┌───────────────────────┐
                               │       HEIMDALL        │
                               │    The Gatekeeper     │
                               └───────────┬───────────┘
                                           │ Verifies Disruption & Traps
                                           │ Builds Immutable Case File
                                           ▼
                     ┌───────────────────────────────────────────┐
                     │          ADVERSARIAL COURTROOM            │
                     │                                           │
                     │   ┌─────────────────┐ ┌───────────────┐   │
                     │   │      THOR       │ │     LOKI      │   │
                     │   │   (The Alarm)   │ │(The Trickster)│   │
                     │   └────────┬────────┘ └───────┬───────┘   │
                     │            │                  │           │
                     │            └────────┬─────────┘           │
                     │                     │ Cross-Examination   │
                     │                     │ Concessions         │
                     │                     ▼                     │
                     │             ┌───────────────┐             │
                     │             │     ODIN      │             │
                     │             │ (The Judge)   │             │
                     │             └───────┬───────┘             │
                     └─────────────────────┼─────────────────────┘
                                           │
                        ┌──────────────────┴──────────────────┐
                        │                                     │
          [If Insufficient: Coverage < 0.85]          [If Sufficient]
                        ▼                                     ▼
             ┌─────────────────────┐               ┌─────────────────────┐
             │  REMAND TO HEIMDALL │               │ EXECUTIVE BRIEFING  │
             │   (Run 2 Re-search) │               │ • Established Facts │
             └─────────────────────┘               │ • Contested Claims  │
                                                   │ • Conceded Claims   │
                                                   │ • Exposure Table    │
                                                   │ • Inline Citations  │
                                                   └─────────────────────┘
```

### The Agents:
1. **Heimdall (The Gatekeeper / Case Builder):**
   - Ingests documents across PDF, DOCX, and TXT.
   - Enforces the simulated clock (`as-of` date: `2027-01-25`).
   - Verifies event authenticity and resists traps (e.g. catches retraction notice `ORV-0013` debunking false renewal rumors).
   - Re-searches when Odin remands the case. Heimdall does *not* participate in the debate.

2. **Thor (The Alarm / High Exposure):**
   - Builds worst-case claims grounded in high-bound numbers (`ORV-0021` sea shipments down 62%, `ORV-0006` port index collapsed to 40).
   - Attacks Loki's substitution claims.
   - Concedes on counter-evidence when physical starvation is disproven by rail parcels.

3. **Loki (The Trickster / Limited Exposure):**
   - Builds limited-exposure claims highlighting mitigations, substitutions, and low-bound numbers (`ORV-0001` Ravik rail link diversion, Vanir parcel splits).
   - Attacks Thor's catastrophic transit assumptions.
   - Concedes on counter-evidence when rail bottlenecks and freight premiums are proven.

4. **Odin (The Allfather / Judge):**
   - Rules on every claim (SOURCED_FACT vs INFERENCE).
   - Classifies findings into **Established**, **Contested**, and **Conceded**.
   - Enforces sufficiency: remands incomplete cases back to Heimdall for Run 2.
   - Authors the final Executive Intelligence Briefing from his rulings only.
   - *Odin is a judge, never an orchestrator or task assigner.*

---

## ⚡ Technology Stack

- **Python:** 3.11+ / 3.14
- **FastAPI:** 0.139+ with CORS and async lifecycle
- **Pydantic:** v2 (`BaseModel`, `Field`, `computed_field`)
- **AsyncIO:** Concurrent agent claim generation (`asyncio.gather`), state machine execution, and real-time Server-Sent Events (SSE) streaming.
- **Parsers:** `pypdf` for PDF parsing, native XML/Zip parsing for DOCX, and regex-based prompt injection detection.

---

## 🚀 Running the Backend

```bash
cd backend
python run.py
```

The server will start on `http://localhost:8000`.

### Endpoints:
- `GET /` — Service metadata and agent directory
- `GET /api/health` — Corpus readiness and health
- `POST /api/trial/start` — Start a new courtroom trial
- `GET /api/trial/case/{case_id}/stream` — Real-time Server-Sent Events (SSE) live court telemetry
- `GET /api/trial/case/{case_id}` — Complete Case File, claims, rulings, and executive briefing
- `GET /api/corpus/feed` — Chronological document feed filtered by `as_of_date`
- `GET /api/corpus/documents/{doc_id}` — Document click-through inspection
- `GET /api/corpus/verification` — SHA-256 integrity report

### Running Tests:
```bash
python backend/tests/test_trial.py
>>>>>>> dbd7014eec6a20d5aba2587232c69f4c192866f8
```
