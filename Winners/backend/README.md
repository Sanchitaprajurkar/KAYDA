# Nine Realms Backend Services

The primary backend codebase and test suites are maintained under `/backend`.
For full setup, schemas, agents, tools, memory, and tests, see:
[`/backend/README.md`](../../backend/README.md)

Quick run from root:
```bash
python -m pytest backend/tests
uvicorn backend.app.main:app --reload --port 8000
```
