"""The court procedure: rules of court, not an agent.

It enforces turn order, parallel filing, hard limits and the clock, writes the log and saves every run. It never
chooses a query, a claim or a piece of evidence: each agent decides those itself, and Odin's send-back is a
ruling ("missing: ..."), which Heimdall turns into its own searches.

  USER -> HEIMDALL (Case File + verdict; no trial unless the event is verified)
       -> THOR and LOKI: round 1 claims (in parallel) -> round 2 attacks -> round 3 defend or concede
       -> ODIN: rulings, classification, ranges, sufficiency -> briefing, or send back to HEIMDALL (next run)
"""

import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional

from backend.agents.advocate import MAX_CLAIMS_PER_SIDE
from backend.agents.loki import CourtLoki
from backend.agents.odin import Odin
from backend.agents.thor.court import CourtThor
from backend.court.display import calculation_lines, case_header, cite, fmt_estimate, fmt_span
from backend.court.briefing import write_briefing
from backend.court.heimdall_bridge import MAX_RUNS, ROOT, HeimdallAgent, goes_to_trial
from backend.court.llm import CourtLLM
from backend.court.memory import AgentMemory
from backend.court.models import RunRecord
from backend.court.tools import RunemarkTools

ROUNDS_PER_RUN = 3
MAX_TOOL_CALLS_PER_AGENT_PER_RUN = 16
MAX_TOKENS_PER_AGENT_PER_RUN = 40_000
CASE_WALLCLOCK_S = 600
CASES_DIR = ROOT / "cases"


class CourtLog:
    """One JSON line per event (NFR4) and a readable line on the terminal."""

    def __init__(self, path: Path, printer: Optional[Callable[[str], None]] = print):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.printer = printer
        self.lock = threading.Lock()

    def __call__(self, event: str, **data) -> None:
        record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **data}
        with self.lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            if self.printer:
                line = _render(event, data)
                if line:
                    self.printer(line)


def _format_supporting_evidence(citations: list, title: str = "SUPPORTING EVIDENCE") -> List[str]:
    lines = ["", f"  {title}:"]
    for i, e in enumerate(citations, 1):
        excerpt = (e.get("excerpt") or "").strip()
        lines.append(f"  {i}. {cite(e)}")
        lines.append(f'     Supporting excerpt: "{excerpt}"')
    lines.append("")
    return lines


def _render(event: str, d: dict) -> Optional[str]:
    if event == "phase":
        return f"\n=== {d['title']} ==="
    if event == "note":
        return f"  {d['text']}"
    if event == "query":
        return f"  {d['agent']:<5} search \"{d['query']}\" {d.get('filters', {})} -> {len(d['results'])} hits"
    if event == "query_rejected":
        return f"  {d['agent']:<5} query refused: {d['reason']}"
    if event == "claim":
        c = d["claim"]
        lines = [
            f"  {d['agent']:<5} {c['claim_id']} [{c['country']}|{c['sector']}] "
            f"{fmt_estimate(c.get('estimate'))}  {c['statement']}"
        ]
        if c.get("citations"):
            basis = (c.get("argument") or {}).get("challenge_basis")
            title = {"not_established": "QUALIFYING RECORDS (cited for what they show; not proof of falsity)",
                     "evidence_against": "EVIDENCE AGAINST"}.get(basis, "SUPPORTING EVIDENCE")
            lines.extend(_format_supporting_evidence(c["citations"], title))
        if c.get("assessment"):
            lines.extend(calculation_lines(c["assessment"], c.get("estimate")))
        return "\n".join(lines).rstrip()
    if event == "attack":
        a = d["attack"]
        lines = [
            f"  {d['agent']:<5} attacks {a['target_claim_id']} ({a.get('attack_type') or a['reason']}, {a['grounds']}"
            f"{', ' + a['target_evidence_or_reasoning'] if a.get('target_evidence_or_reasoning') else ''}): {a['argument']}"
        ]
        if a.get("counter_evidence"):
            lines.extend(_format_supporting_evidence(a["counter_evidence"], "COUNTER-EVIDENCE"))
        else:
            lines.append("  [no counter-evidence]")
        return "\n".join(lines).rstrip()
    if event == "defence":
        r = d["response"]
        lines = [
            f"  {d['agent']:<5} DEFENDS {r['claim_id']}: {r['explanation']}"
        ]
        if r.get("new_evidence"):
            lines.extend(_format_supporting_evidence(r["new_evidence"], "NEW EVIDENCE"))
        return "\n".join(lines).rstrip()
    if event == "concession":
        r = d["response"]
        return f"  {d['agent']:<5} CONCEDES {r['claim_id']}: {r['explanation']}"
    if event == "narrowing":
        r = d["response"]
        return f"  {d['agent']:<5} NARROWS {r['claim_id']}: {r['explanation']}"
    if event == "ruling":
        r = d["ruling"]
        line = f"  ODIN  {r['claim_id']}: {r['ruling']} -> {r['classification']} ({r['nature']}) {r['reason']}"
        return line + (f"\n        citations checked: {d['sources']}" if d.get("sources") else "")
    if event == "proposition_ruling":
        r = d["ruling"]
        origin = {"part": f" [part of {r.get('derived_from')}]",
                  "consequence": f" [derived from {r.get('derived_from')}]"}.get(r.get("derivation"), "")
        lines = [f"  ODIN  {r['prop_id']} => {r['classification']} (confidence {r['confidence']['level']}): "
                 f"{r['proposition']}{origin}",
                 f"        {r['reasoning']}"]
        for label, key in (("supporting", "supporting"), ("contradicting", "contradicting"),
                           ("qualifying", "qualifying"), ("set aside", "set_aside")):
            if r.get(key):
                lines.append(f"        {label}: " + "; ".join(
                    f"{x['source_id']} {('Paragraph ' + str(x['locator']['paragraph'])) if x['locator'].get('paragraph') else ''}".strip()
                    for x in r[key][:5]))
        if r.get("attribution"):
            lines.append(f"        attribution: {r['attribution']}")
        if r.get("deception") and r["kind"] != "EXPOSURE":
            lines.append(f"        deception: {r['deception']}")
        if r.get("needs_investigation"):
            lines.append(f"        gap: {r['evidence_gap']} Needed: {r['evidence_needed']}. {r['reinvestigation']}")
        return "\n".join(lines)
    if event == "research_outcome":
        o = d["outcome"]
        return f"  ODIN  re-search on \"{o['gap']}\": {o['explanation']}"
    if event in ("memory_read", "memory_write"):
        return f"  {d['agent']:<5} {event}: {d.get('influenced') or d.get('value')}"
    if event in ("limit_hit", "error", "side_failed"):
        return f"  !! {d.get('agent', '')} {event}: {d.get('detail')}"
    if event == "retrieval":
        return f"  {d['agent']:<5} {d['detail']}"
    return None


class CourtSession:
    def __init__(self, heimdall: Optional[HeimdallAgent] = None, llm_backends: Optional[Dict[str, object]] = None,
                 cases_dir: Optional[Path] = None, memory_dir: Optional[Path] = None,
                 printer: Optional[Callable[[str], None]] = print):
        self.heimdall = heimdall or HeimdallAgent()
        self.backends = llm_backends or {}
        self.cases_dir = Path(cases_dir or CASES_DIR)
        self.memory_dir = memory_dir
        self.printer = printer

    def run(self, query: str, case_id: Optional[str] = None) -> Dict:
        started = time.monotonic()
        report = self.heimdall.build_case_file(query=query, case_id=case_id)
        case_dir = self.cases_dir / report.case_id
        log = CourtLog(case_dir / "log.jsonl", self.printer)
        log("phase", title=f"CASE {report.case_id}: {query}")
        self._log_case_file(log, report)
        heimdall_memory = AgentMemory("heimdall", self.memory_dir)

        v = report.event_verification
        if not goes_to_trial(report):
            log("phase", title="NO TRIAL")
            log("note", text=f"Heimdall could not verify the event ({v.status.value}). {v.summary}")
            for reason in v.reasoning:
                log("note", text=f"- {reason}")
            self._save(case_dir / "run_1" / "case_file.json", report.model_dump(mode="json"))
            self._save(case_dir / "meta.json", self._meta(report, 1, "NO_TRIAL"))
            return {"case_id": report.case_id, "status": "NO_TRIAL", "verdict": v.status.value, "dir": str(case_dir)}

        ledger: set = set()
        tools = RunemarkTools(self.heimdall.evidence_store, self.heimdall.trade, report.as_of_date, ledger,
                              MAX_TOOL_CALLS_PER_AGENT_PER_RUN)
        llms = {a: CourtLLM(a, MAX_TOKENS_PER_AGENT_PER_RUN, self.backends.get(a)) for a in ("THOR", "LOKI", "ODIN")}
        thor = CourtThor(tools, llms["THOR"], AgentMemory("thor", self.memory_dir), log)
        loki = CourtLoki(tools, llms["LOKI"], AgentMemory("loki", self.memory_dir), log)
        odin = Odin(tools, llms["ODIN"], AgentMemory("odin", self.memory_dir), log)

        runs: List[RunRecord] = []
        remand: List[str] = []
        missing: List[str] = []
        for run in range(1, MAX_RUNS + 1):
            tools.start_run()
            for llm in llms.values():
                llm.reset_budget()
            record = RunRecord(run=run, case_file_doc_ids=[d.doc_id for d in report.retrieved_documents],
                               new_evidence=report.new_document_ids if run > 1 else [])
            self._trial_run(log, report, run, remand, thor, loki, odin, record)
            record.llm_usage = {a: {"calls": l.calls, "cache_hits": l.cache_hits, "tokens": l.used_tokens}
                                for a, l in llms.items()}
            runs.append(record)
            self._save_run(case_dir, report, record)

            missing = record.remand
            if not missing:
                break
            if run == MAX_RUNS:
                log("limit_hit", agent="COURT", limit="runs", detail=f"{MAX_RUNS} runs reached with gaps left")
                break
            if time.monotonic() - started > CASE_WALLCLOCK_S:
                log("limit_hit", agent="COURT", limit="wallclock", detail=f"{CASE_WALLCLOCK_S}s reached")
                break
            request = "; ".join(missing)
            key = f"research:{report.case_id}:{request.lower()}"
            if heimdall_memory.read(key):
                log("memory_read", agent="HEIMDALL", key=key,
                    influenced="the same send-back was already searched for this case; not repeated")
                break
            log("phase", title=f"ODIN SENDS THE CASE BACK -> HEIMDALL RE-SEARCH (run {run + 1})")
            report = self.heimdall.re_search(report.case_id, request, prior=report)
            heimdall_memory.write(key, "research", {"new": report.new_document_ids}, report.case_id)
            log("memory_write", agent="HEIMDALL", key=key, value=f"searched: {request[:120]}")
            log("note", text=f"Heimdall run {report.run_number}: retrieved {report.new_document_ids or 'nothing new'}; "
                             f"{report.research_history[-1].note} Whether this answers the send-back is ruled after "
                             f"the run.")
            remand = missing

        complete = not missing
        briefing = write_briefing(report, runs, complete, missing)
        (case_dir / "briefing.md").write_text(briefing["markdown"], encoding="utf-8")
        self._save(case_dir / "briefing.json", briefing)
        self._save(case_dir / "meta.json", self._meta(report, len(runs), briefing["status"], llms))
        log("phase", title=f"BRIEFING (execution {briefing['status']}; analysis {briefing['analytical_status']})")
        for r in runs[-1].ranges:
            side = lambda k, span: _fmt(span) if span else r.positions.get(k, "-")  # noqa: E731
            log("note", text=f"{r.country} {r.sector}: Thor {side('THOR', r.thor)} | Loki {side('LOKI', r.loki)} | "
                             f"Odin {_fmt(r.odin) if r.status == 'COVERED' else 'evidence missing'}"
                             + (f" [net exposure, % of baseline route value, {r.period}]" if r.odin else ""))
        result = briefing["outcome"]
        log("phase", title="VERDICT")
        log("verdict", agent="ODIN", **result)
        log("note", text=f"ODIN  {result['verdict']}")
        log("note", text=f"Saved to {case_dir}")
        return {"case_id": report.case_id, "status": briefing["status"],
                "analytical_status": briefing["analytical_status"], "runs": len(runs), "dir": str(case_dir),
                "ranges": [r.model_dump() for r in runs[-1].ranges], "winner": result["winner"],
                "verdict": result["verdict"]}

    def _trial_run(self, log, report, run, remand, thor, loki, odin, record: RunRecord) -> None:
        sides = {"THOR": thor, "LOKI": loki}

        def parallel(fn_by_side):
            out = {}
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {s: pool.submit(fn) for s, fn in fn_by_side.items() if s not in record.side_failures}
                for s, f in futures.items():
                    try:
                        out[s] = f.result(timeout=CASE_WALLCLOCK_S)
                    except Exception as e:  # one side failing never stops the trial (NFR3)
                        record.side_failures[s] = str(e)[:200]
                        log("side_failed", agent=s, detail=str(e)[:200])
                        out[s] = []
            return out

        log("phase", title=f"RUN {run} - ROUND 1 - CLAIMS (filed in parallel)")
        filed = parallel({s: (lambda a=a: a.open_case(report, run, remand)) for s, a in sides.items()})
        record.claims = [c for s in ("THOR", "LOKI") for c in filed.get(s, [])][:2 * MAX_CLAIMS_PER_SIDE]

        log("phase", title=f"RUN {run} - ROUND 2 - CROSS-EXAMINATION: ATTACKS")
        theirs = {"THOR": filed.get("LOKI", []), "LOKI": filed.get("THOR", [])}
        attacks = parallel({s: (lambda a=a, s=s: a.attack(report, theirs[s], run,
                                                          a.rule_grounds(report, theirs[s], run)))
                            for s, a in sides.items() if theirs[s]})
        record.attacks = [x for s in ("THOR", "LOKI") for x in attacks.get(s, [])]

        log("phase", title=f"RUN {run} - ROUND 3 - DEFEND OR CONCEDE")
        against = {s: [a for a in record.attacks if a.attacker != s] for s in sides}
        answers = parallel({s: (lambda a=a, s=s: a.respond(report, against[s], run))
                            for s, a in sides.items() if against[s]})
        record.responses = [x for s in ("THOR", "LOKI") for x in answers.get(s, [])]

        log("phase", title=f"RUN {run} - ODIN RULES")
        record.propositions = odin.adjudicate(report, record.claims, record.attacks, record.responses)
        record.rulings = odin.rule(report, record.claims, record.attacks, record.responses, record.side_failures,
                                   propositions=record.propositions)
        record.ranges = odin.ranges(report, record.claims, record.rulings)
        odin.adjudicate_exposure(report, record.propositions, record.ranges)
        record.completeness = odin.completeness(report, record.claims, record.propositions, record.ranges)
        for item in record.completeness:
            log("note", text=f"ODIN  completeness: no ruling for {item}")
        record.analytical_status = odin.analytical_status(report, record.propositions, record.ranges,
                                                          record.completeness)
        record.remand, record.open_gaps = odin.sufficiency(report, record.claims, record.rulings,
                                                           record.propositions)
        if run > 1 and remand:
            record.research = odin.research_outcomes(report, remand, record)
            for o in record.research:
                log("research_outcome", agent="ODIN", outcome=o.model_dump())
        for item in record.remand:
            log("remand", agent="ODIN", missing=item)
            log("note", text=f"ODIN  missing: {item}")
        for item in record.open_gaps:
            log("note", text=f"ODIN  open gap (searched for, not on the record; reported, not chased): {item}")
        if not record.remand:
            log("note", text="ODIN  no further search would help" if record.open_gaps else
                "ODIN  no further search needed")
        log("note", text=f"ODIN  analytical status: {record.analytical_status}")

    def _log_case_file(self, log, report) -> None:
        v = report.event_verification
        log("phase", title=f"HEIMDALL - CASE FILE (run {report.run_number})")
        header = case_header(report)
        log("case_header", agent="HEIMDALL", **{k.lower().replace(" ", "_").replace("-", "_"): x
                                               for k, x in header.items()})
        width = max(len(k) for k in header)
        for k, x in header.items():
            log("note", text=f"{k + ':':<{width + 1}} {x}")
        log("note", text=f"Event {report.case_scope.event_id}: {v.status.value} (confidence {v.confidence_score})"
                         f"; active at {report.as_of_date}: {v.is_active_at_as_of}")
        log("note", text=f"{len(report.retrieved_documents)} documents: "
                         + ", ".join(d.doc_id for d in report.retrieved_documents))
        for x in report.rejected_evidence:
            log("doc_health", agent="HEIMDALL", doc_id=x.doc_id, reason=x.reason, related=x.related_doc_id)
        log("note", text="Set aside: " + (", ".join(f"{x.doc_id} ({x.reason})" for x in report.rejected_evidence)
                                          or "none"))
        for c in report.coverage_map:
            log("note", text=f"Coverage {c.country} {c.sector}: {c.status}; {c.note}")
        log("case_file", agent="HEIMDALL", run=report.run_number,
            doc_ids=[d.doc_id for d in report.retrieved_documents], verdict=v.status.value)

    def _save_run(self, case_dir: Path, report, record: RunRecord) -> None:
        run_dir = case_dir / f"run_{record.run}"
        self._save(run_dir / "case_file.json", report.model_dump(mode="json"))
        self._save(run_dir / "transcript.json", {"claims": [c.model_dump() for c in record.claims],
                                                 "attacks": [a.model_dump() for a in record.attacks],
                                                 "responses": [r.model_dump() for r in record.responses],
                                                 "side_failures": record.side_failures})
        self._save(run_dir / "rulings.json", {"rulings": [r.model_dump() for r in record.rulings],
                                              "ranges": [r.model_dump() for r in record.ranges],
                                              "propositions": [p.model_dump() for p in record.propositions],
                                              "analytical_status": record.analytical_status,
                                              "completeness": record.completeness,
                                              "remand": record.remand, "open_gaps": record.open_gaps,
                                              "research": [o.model_dump() for o in record.research],
                                              "llm_usage": record.llm_usage})

    @staticmethod
    def _save(path: Path, data) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    @staticmethod
    def _meta(report, runs: int, status: str, llms: Optional[dict] = None) -> dict:
        try:
            sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        except Exception:
            sha = None
        return {"case_id": report.case_id, "question": report.target_query, "as_of_date": report.as_of_date,
                "runs": runs, "status": status, "git_sha": sha,
                "models": {a: getattr(l.backend, "model_name", None) for a, l in (llms or {}).items()},
                "limits": {"max_runs": MAX_RUNS, "rounds_per_run": ROUNDS_PER_RUN,
                           "max_claims_per_side": MAX_CLAIMS_PER_SIDE,
                           "max_tool_calls_per_agent_per_run": MAX_TOOL_CALLS_PER_AGENT_PER_RUN,
                           "max_tokens_per_agent_per_run": MAX_TOKENS_PER_AGENT_PER_RUN,
                           "case_wallclock_s": CASE_WALLCLOCK_S},
                "saved_at": datetime.now(timezone.utc).isoformat()}


def _fmt(span) -> str:
    return fmt_span(span)
