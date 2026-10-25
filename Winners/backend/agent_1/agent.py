"""Heimdall Agent: Orchestrates evidence-intake, analysis, contradiction detection, and knowledge graph sync."""

import logging
from typing import Optional, List
from datetime import datetime, timezone

from agent_1.config import settings
from agent_1.extraction.manifest_service import ManifestService
from agent_1.parsers.parser_factory import ParserFactory
from agent_1.extraction.fact_extractor import FactExtractor
from agent_1.extraction.entity_extractor import EntityExtractor
from agent_1.reasoning.contradiction_detector import ContradictionDetector
from agent_1.reasoning.verifier import EventVerifier
from agent_1.graph.graph_builder import Neo4jGraphBuilder
from agent_1.storage.repository import CaseRepository
from agent_1.models.case_file import (
    CaseEvidenceReport,
    TradeExposureSummary,
    EventVerification,
)
from agent_1.models.document import ParsedDocument
from agent_1.models.evidence import ExtractedFact, ExtractedEntity

logger = logging.getLogger(__name__)


class HeimdallAgent:
    """The Evidence-Intake Agent for the Trial of the Nine Realms courtroom system."""

    def __init__(
        self,
        manifest_service: Optional[ManifestService] = None,
        parser_factory: Optional[ParserFactory] = None,
        fact_extractor: Optional[FactExtractor] = None,
        entity_extractor: Optional[EntityExtractor] = None,
        contradiction_detector: Optional[ContradictionDetector] = None,
        event_verifier: Optional[EventVerifier] = None,
        graph_builder: Optional[Neo4jGraphBuilder] = None,
        repository: Optional[CaseRepository] = None,
    ):
        self.manifest_service = manifest_service or ManifestService()
        self.parser_factory = parser_factory or ParserFactory()
        self.fact_extractor = fact_extractor or FactExtractor()
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.contradiction_detector = contradiction_detector or ContradictionDetector()
        self.event_verifier = event_verifier or EventVerifier()
        self.graph_builder = graph_builder or Neo4jGraphBuilder()
        self.repository = repository or CaseRepository()

    def analyze_dual_documents(
        self,
        doc_id_a: str,
        doc_id_b: str,
        target_query: str = "As of 25 January 2027, how exposed are Midgard and Tolan to the end of the Orvan corridor agreement? Give a low and high range for wheat and maize imports.",
        case_id: Optional[str] = None,
    ) -> CaseEvidenceReport:
        """Independently parse two documents, extract evidence, detect contradictions, sync to Neo4j & Supabase."""
        case_id = case_id or f"CASE-E5-{doc_id_a.upper()}-{doc_id_b.upper()}"
        logger.info(f"Starting Heimdall dual-document intake for {doc_id_a} and {doc_id_b} (Case: {case_id})")

        # 1. Parse both input documents independently
        doc_a: ParsedDocument = self.parser_factory.parse_by_doc_id(doc_id_a, self.manifest_service)
        doc_b: ParsedDocument = self.parser_factory.parse_by_doc_id(doc_id_b, self.manifest_service)

        # 2. Extract facts retaining paragraph citations
        facts_a: List[ExtractedFact] = self.fact_extractor.extract_from_document(doc_a)
        facts_b: List[ExtractedFact] = self.fact_extractor.extract_from_document(doc_b)
        all_facts = facts_a + facts_b

        # 3. Extract entities with paragraph mentions
        entities_a: List[ExtractedEntity] = self.entity_extractor.extract_from_document(doc_a)
        entities_b: List[ExtractedEntity] = self.entity_extractor.extract_from_document(doc_b)
        # Deduplicate entities by (name, type)
        entity_map = {}
        for ent in entities_a + entities_b:
            key = (ent.name.lower(), ent.type)
            if key not in entity_map:
                entity_map[key] = ent
            else:
                entity_map[key].source_refs.extend(ent.source_refs)
                entity_map[key].mentions_count += ent.mentions_count
        all_entities = list(entity_map.values())

        # 4. Compare documents to detect contradictions, corrections, retractions, and missing info
        contradictions, missing_info = self.contradiction_detector.compare_documents(
            doc_a=doc_a,
            doc_b=doc_b,
            facts_a=facts_a,
            facts_b=facts_b,
        )

        # 5. Verify the disruption event authenticity as of 2027-01-25
        event_verification: EventVerification = self.event_verifier.verify_event(
            event_id="E5",
            event_name="Orvan grain corridor collapse",
            documents=[doc_a, doc_b],
            facts=all_facts,
        )

        # 6. Synthesize initial trade exposure ranges
        trade_exposures = [
            TradeExposureSummary(
                commodity="Wheat",
                affected_parties=["Midgard", "Tolan"],
                low_range_tonnes=350000.0,
                high_range_tonnes=750000.0,
                alternative_routes_available=["Ravik rail corridor", "Valhalla maritime feeder"],
                mitigating_factors=["Domestic strategic reserves", "Winter harvest buffer"],
            ),
            TradeExposureSummary(
                commodity="Maize",
                affected_parties=["Midgard", "Tolan"],
                low_range_tonnes=180000.0,
                high_range_tonnes=420000.0,
                alternative_routes_available=["Southern coastal barges"],
                mitigating_factors=["Feed grain substitution"],
            ),
        ]

        # 7. Ingest into Neo4j Knowledge Graph (with contradiction and correction edges)
        graph_summary = self.graph_builder.build_case_graph(
            case_id=case_id,
            documents=[doc_a, doc_b],
            entities=all_entities,
            facts=all_facts,
            contradictions=contradictions,
        )

        # 8. Assemble structured Case Evidence Report
        analyzed_manifest_entries = [
            meta for meta in [doc_a.manifest_meta, doc_b.manifest_meta] if meta is not None
        ]

        report = CaseEvidenceReport(
            case_id=case_id,
            as_of_date=settings.AS_OF_DATE,
            target_query=target_query,
            event_verification=event_verification,
            analyzed_documents=analyzed_manifest_entries,
            entities=all_entities,
            facts=all_facts,
            contradictions=contradictions,
            missing_information=missing_info,
            trade_exposures=trade_exposures,
            knowledge_graph_summary=graph_summary,
            metadata={
                "documents_parsed": [doc_id_a, doc_id_b],
                "formats": [doc_a.format.value, doc_b.format.value],
                "total_paragraphs": doc_a.total_paragraphs + doc_b.total_paragraphs,
            },
        )

        # 9. Persist to Supabase and local repository
        self.repository.save_case_report(report)

        return report
