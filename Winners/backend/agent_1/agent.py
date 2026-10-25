"""Heimdall Agent: builds the case file from trap-resolved evidence.

  1. Understand the case      (query or event ID -> event, countries, commodities, sectors, period)
  2. Retrieve documents       (BM25 over resolved evidence; relevant excluded documents are reported, not used)
  3. Analyse evidence         (facts by category / commodity / country, metrics, timeline - all cited)
  4. Assess source credibility (tier, date, validity at as-of, independence, corroboration)
  5. Detect contradictions    (across all retrieved facts; favoured side decided on credibility and recency)
  6. Verify the event         (CONFIRMED / DISPUTED / UNVERIFIED / DISPROVEN / DEVELOPING, with cited reasoning)

When Odin sends the case back, re_search() starts the next run: it searches for what Odin asked, adds only
admissible documents not already in the Case File, and re-runs steps 3-6 over the combined evidence.

Case runs never parse raw files or extract new facts, so trapped content cannot re-enter.
"""

import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from agent_1.case.analysis import EvidenceAnalyst
from agent_1.case.retrieval import EvidenceRetriever
from agent_1.case.scope import CaseUnderstanding
from agent_1.case.text import contains_term, tokens
from agent_1.config import settings
from agent_1.graph.graph_builder import Neo4jGraphBuilder
from agent_1.models.case_file import (CaseEvidenceReport, CaseScope, RejectedEvidence, ResearchRun,
                                      RetrievedDocument)
from agent_1.models.evidence import ExtractedEntity, MissingInformation
from agent_1.reasoning.contradiction_detector import ContradictionDetector
from agent_1.reasoning.verifier import EventVerifier
from agent_1.storage.case_store import NeonCaseStore
from agent_1.storage.evidence_store import ResolvedEvidenceStore

logger = logging.getLogger(__name__)

MAX_RUNS = 3  # hard limit on send-backs so the trial loop always ends (FR5.4)
MAX_NEW_DOCUMENTS = 10


class CaseNotFoundError(KeyError):
    pass


class RunLimitError(ValueError):
    pass


class HeimdallAgent:
    """The Evidence-Intake Agent for the Trial of the Nine Realms courtroom system."""

    def __init__(
        self,
        evidence_store: Optional[ResolvedEvidenceStore] = None,
        contradiction_detector: Optional[ContradictionDetector] = None,
        event_verifier: Optional[EventVerifier] = None,
        graph_builder: Optional[Neo4jGraphBuilder] = None,
        case_store: Optional[NeonCaseStore] = None,
    ):
        self.evidence_store = evidence_store or ResolvedEvidenceStore()
        self.understanding = CaseUnderstanding(self.evidence_store)
        self.retriever = EvidenceRetriever(self.evidence_store)
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.event_verifier = event_verifier or EventVerifier()
        self.graph_builder = graph_builder or Neo4jGraphBuilder()
        self.case_store = case_store if case_store is not None else NeonCaseStore()

    def build_case_file(
        self,
        query: Optional[str] = None,
        event_id: Optional[str] = None,
        case_id: Optional[str] = None,
        max_documents: int = 40,
    ) -> CaseEvidenceReport:
        timeline, log = self._tracer(run_number=1)

        # 1. Understand the case
        scope = self.understanding.understand(query=query, event_id=event_id)
        case_id = case_id or f"CASE-{scope.event_id or 'ADHOC'}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
        log("UNDERSTAND", f"Event {scope.event_id or 'unidentified'} ({scope.event_name or '-'}); countries "
                          f"{scope.countries}; commodities {scope.commodities}; as of {scope.as_of_date}",
            search_terms=scope.search_terms)

        # 2. Retrieve relevant documents
        retrieved = self.retriever.retrieve(scope, max_documents=max_documents)
        rejected = self.retriever.rejected(scope)
        doc_ids = [d.doc_id for d in retrieved]
        log("RETRIEVE", f"{len(retrieved)} evidence documents retrieved; {len(rejected)} relevant documents "
                        f"were excluded before trial", retrieved_doc_ids=doc_ids,
            excluded_doc_ids=[r.doc_id for r in rejected])

        return self._assemble(case_id, query or scope.event_name or event_id or "", scope, retrieved, rejected,
                              run_number=1, history=[], new_ids=doc_ids, timeline=timeline, log=log)

    def re_search(
        self,
        case_id: str,
        request: str,
        prior: Optional[CaseEvidenceReport] = None,
        max_new_documents: int = MAX_NEW_DOCUMENTS,
    ) -> CaseEvidenceReport:
        """Next run after Odin sends the case back: search for `request`, add new admissible evidence (FR1.4).

        The case mandate (question, event, countries, commodities, as-of date) does not change; the request only
        steers the search. If nothing new is admissible, the run says so rather than padding the Case File.
        """
        if prior is None:
            prior = self.case_store.load(case_id) if self.case_store.enabled else None
        if prior is None:
            raise CaseNotFoundError(case_id)
        run = prior.run_number + 1
        if run > MAX_RUNS:
            raise RunLimitError(f"Case {case_id} has reached the limit of {MAX_RUNS} runs.")
        focus = list(dict.fromkeys(tokens(request)))
        if not focus:
            raise ValueError("The re-search request has no searchable terms.")

        timeline, log = self._tracer(run_number=run)
        scope = prior.case_scope.model_copy(deep=True)
        focus_scope = scope.model_copy(update={"search_terms": focus})
        log("RESEARCH", f"Run {run}: Odin asked for '{request}'", focus_terms=focus)

        asked_countries = [c for c in self.understanding.countries if contains_term(request, c)]
        known = {d.doc_id for d in prior.retrieved_documents}
        found = [d for d in self.retriever.retrieve(focus_scope, max_documents=len(self.evidence_store.evidence_ids()),
                                                    reference_countries=asked_countries, shared_references=True)
                 if d.doc_id not in known][:max_new_documents]
        known_excluded = {r.doc_id for r in prior.rejected_evidence}
        new_rejected = [r for r in self.retriever.rejected(focus_scope) if r.doc_id not in known_excluded]
        new_ids = [d.doc_id for d in found]
        note = (f"{len(new_ids)} new admissible document(s) added." if new_ids
                else "No admissible document beyond those already in the Case File matches this request.")
        log("RETRIEVE", note, new_doc_ids=new_ids, new_excluded_doc_ids=[r.doc_id for r in new_rejected])

        history = prior.research_history + [ResearchRun(
            run_number=run, request=request, focus_terms=focus, new_document_ids=new_ids,
            new_excluded_ids=[r.doc_id for r in new_rejected], note=note)]
        return self._assemble(case_id, prior.target_query, scope, prior.retrieved_documents + found,
                              prior.rejected_evidence + new_rejected, run_number=run, history=history,
                              new_ids=new_ids, timeline=timeline, log=log)

    @staticmethod
    def _tracer(run_number: int) -> Tuple[List[dict], Callable]:
        timeline: List[dict] = []

        def log(phase: str, message: str, **data):
            timeline.append({"timestamp": datetime.now(timezone.utc).isoformat(), "agent": "HEIMDALL",
                             "run_number": run_number, "phase": phase, "message": message, **data})
            logger.info(f"[run {run_number}] [{phase}] {message}")

        return timeline, log

    def _assemble(self, case_id: str, query: str, scope: CaseScope, retrieved: List[RetrievedDocument],
                  rejected: List[RejectedEvidence], run_number: int, history: List[ResearchRun],
                  new_ids: List[str], timeline: List[dict], log: Callable) -> CaseEvidenceReport:
        doc_ids = [d.doc_id for d in retrieved]

        # 3 & 4. Analyse evidence and assess credibility
        analyst = EvidenceAnalyst(self.evidence_store, self.understanding.countries, self.understanding.commodities)
        sources = analyst.assess_sources(doc_ids, scope.as_of_date)
        facts = [f for d in doc_ids for f in self.evidence_store.facts(d)]
        assessments = analyst.assess_facts(facts, sources)
        digest = analyst.digest(facts, assessments, sources)
        log("ANALYSE", f"{len(facts)} cited facts organised: {len(digest.metrics)} metrics, "
                       f"{len(digest.by_category)} categories")
        dependent = {d: s.cites_sources for d, s in sources.items() if s.cites_sources}
        log("ASSESS", f"{len({s.source_name for s in sources.values()})} distinct outlets; "
                      f"{len(dependent)} documents rely on another outlet", dependencies=dependent)

        # 5. Detect contradictions
        titles = {r.doc_id: r.title or "" for r in retrieved}
        contradictions = self.contradiction_detector.detect(facts, sources, assessments, titles)
        log("CONTRADICTIONS", f"{len(contradictions)} conflicts found; "
                              f"{sum(1 for c in contradictions if c.favored_fact_id)} resolved")

        # 6. Verify the event
        verification = self.event_verifier.verify(scope, facts, sources, assessments, rejected, contradictions)
        if verification.onset_date and not scope.period_start:
            scope.period_start = verification.onset_date
        log("VERIFY", verification.summary, status=verification.status.value,
            confidence=verification.confidence_score)

        missing = [MissingInformation(
            topic=f"{country} {commodity} trade data",
            expected_scope=f"A trade note or customs figure for {commodity.lower()} flows into {country}.",
            impact_on_assessment="Evidence missing: no range can be given for this flow without inventing one.",
        ) for country, commodity in analyst.missing_trade_data(scope, assessments, facts)]

        entity_map = {}
        for ent in (e for d in doc_ids for e in self.evidence_store.entities(d)):
            key = (ent.name.lower(), ent.type)
            if key in entity_map:
                entity_map[key].source_refs.extend(ent.source_refs)
                entity_map[key].mentions_count += ent.mentions_count
            else:
                entity_map[key] = ent
        entities: List[ExtractedEntity] = list(entity_map.values())

        graph_summary = self.graph_builder.link_case(
            case_id=case_id, doc_ids=doc_ids, fact_ids=[f.fact_id for f in facts],
            entity_count=len(entities), contradictions=contradictions)

        report = CaseEvidenceReport(
            case_id=case_id,
            run_number=run_number,
            research_history=history,
            new_document_ids=new_ids,
            as_of_date=scope.as_of_date,
            target_query=query,
            case_scope=scope,
            event_verification=verification,
            retrieved_documents=retrieved,
            rejected_evidence=rejected,
            source_assessments=list(sources.values()),
            fact_assessments=list(assessments.values()),
            evidence_digest=digest,
            analyzed_documents=[self.evidence_store.document(d).manifest_meta for d in doc_ids],
            entities=entities,
            facts=facts,
            contradictions=contradictions,
            missing_information=missing,
            # Heimdall reports cited evidence only; exposure ranges are argued downstream from cited facts.
            trade_exposures=[],
            knowledge_graph_summary=graph_summary,
            metadata={"evidence_source": "resolved_data", "corpus_as_of": settings.AS_OF_DATE,
                      "trace": timeline},
        )

        if self.case_store.enabled:
            counts = self.case_store.save(report, timeline)
            report.metadata["neon"] = counts
        return report
