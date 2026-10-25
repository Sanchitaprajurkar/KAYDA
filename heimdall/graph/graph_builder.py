"""Builds the evidence knowledge graph connecting documents, paragraphs, facts, entities, and contradictions."""

import logging
from typing import List, Optional
from heimdall.graph.client import Neo4jClient
from heimdall.graph.schema import initialize_schema
from heimdall.models.document import ParsedDocument
from heimdall.models.evidence import ExtractedEntity, ExtractedFact, ContradictionItem, ConflictType
from heimdall.models.case_file import KnowledgeGraphSummary

logger = logging.getLogger(__name__)


class Neo4jGraphBuilder:
    """Synchronizes extracted case evidence into a connected Neo4j knowledge graph using high-performance batched Cypher."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()
        self._initialized = False

    def ensure_schema(self):
        if not self._initialized:
            initialize_schema(self.client)
            self._initialized = True

    def build_case_graph(
        self,
        case_id: str,
        documents: List[ParsedDocument],
        entities: List[ExtractedEntity],
        facts: List[ExtractedFact],
        contradictions: List[ContradictionItem],
    ) -> KnowledgeGraphSummary:
        """Construct graph nodes and relationships for the case file with batched UNWIND Cypher."""
        self.ensure_schema()

        # If client is not connected, return mock graph summary
        if not self.client.is_connected:
            return KnowledgeGraphSummary(
                total_nodes=len(documents) + sum(len(d.paragraphs) for d in documents) + len(entities) + len(facts),
                total_relationships=len(facts) + len(entities) + len(contradictions),
                entity_nodes_count=len(entities),
                fact_nodes_count=len(facts),
                contradiction_edges_count=len([c for c in contradictions if c.conflict_type == ConflictType.DIRECT_CONTRADICTION]),
                correction_edges_count=len([c for c in contradictions if c.conflict_type in (ConflictType.CORRECTION, ConflictType.RETRACTION)]),
                graph_status="MOCK_RECORDED",
            )

        # 1. Batch Ingest Documents
        doc_batch = []
        para_batch = []
        for doc in documents:
            meta = doc.manifest_meta
            doc_batch.append({
                "id": doc.doc_id,
                "title": meta.title if meta else doc.file_name,
                "file_name": doc.file_name,
                "format": doc.format.value,
                "pub_date": meta.pub_date if meta else None,
                "tier": meta.reliability_tier if meta else 2,
                "case_id": case_id,
            })
            for p in doc.paragraphs:
                para_batch.append({
                    "id": f"{doc.doc_id}-P{p.paragraph_index}",
                    "doc_id": doc.doc_id,
                    "p_idx": p.paragraph_index,
                    "page_num": p.page_number,
                    "text": p.raw_text[:500],
                })

        if doc_batch:
            self.client.execute_query(
                """
                UNWIND $batch as doc
                MERGE (d:Document {id: doc.id})
                SET d.title = doc.title,
                    d.file_name = doc.file_name,
                    d.format = doc.format,
                    d.pub_date = doc.pub_date,
                    d.reliability_tier = doc.tier,
                    d.case_id = doc.case_id
                """,
                {"batch": doc_batch},
            )

        if para_batch:
            self.client.execute_query(
                """
                UNWIND $batch as p
                MERGE (para:Paragraph {id: p.id})
                SET para.doc_id = p.doc_id,
                    para.paragraph_index = p.p_idx,
                    para.page_number = p.page_num,
                    para.text = p.text
                WITH para, p
                MATCH (d:Document {id: p.doc_id})
                MERGE (d)-[:HAS_PARAGRAPH]->(para)
                """,
                {"batch": para_batch},
            )

        # 2. Batch Ingest Entities & Mentions
        ent_batch = []
        mention_batch = []
        for ent in entities:
            ent_batch.append({
                "name": ent.name,
                "type": ent.type.value,
                "desc": ent.description,
                "mentions": ent.mentions_count,
            })
            for ref in ent.source_refs:
                mention_batch.append({
                    "para_id": f"{ref.doc_id}-P{ref.paragraph_index}",
                    "name": ent.name,
                    "type": ent.type.value,
                })

        if ent_batch:
            self.client.execute_query(
                """
                UNWIND $batch as e
                MERGE (ent:Entity {name: e.name, type: e.type})
                SET ent.description = e.desc,
                    ent.mentions_count = e.mentions
                """,
                {"batch": ent_batch},
            )

        if mention_batch:
            self.client.execute_query(
                """
                UNWIND $batch as m
                MATCH (p:Paragraph {id: m.para_id})
                MATCH (e:Entity {name: m.name, type: m.type})
                MERGE (p)-[:MENTIONS]->(e)
                """,
                {"batch": mention_batch},
            )

        # 3. Batch Ingest Facts & Citations
        fact_batch = []
        for f in facts:
            fact_batch.append({
                "id": f.fact_id,
                "cat": f.category.value,
                "subj": f.subject,
                "stmt": f.statement,
                "date": f.date_mentioned,
                "val": f.numeric_value,
                "unit": f.unit,
                "tier": f.reliability_tier,
                "as_of_valid": f.is_as_of_valid,
                "conf": f.confidence,
                "para_id": f"{f.source_ref.doc_id}-P{f.source_ref.paragraph_index}",
            })

        if fact_batch:
            self.client.execute_query(
                """
                UNWIND $batch as f
                MERGE (fact:Fact {id: f.id})
                SET fact.category = f.cat,
                    fact.subject = f.subj,
                    fact.statement = f.stmt,
                    fact.date_mentioned = f.date,
                    fact.numeric_value = f.val,
                    fact.unit = f.unit,
                    fact.reliability_tier = f.tier,
                    fact.is_as_of_valid = f.as_of_valid,
                    fact.confidence = f.conf
                WITH fact, f
                MATCH (p:Paragraph {id: f.para_id})
                MERGE (fact)-[:SOURCED_FROM]->(p)
                """,
                {"batch": fact_batch},
            )

        # 4. Batch Ingest Contradictions, Corrections, and Retractions
        contra_batch = []
        corr_batch = []
        retract_batch = []
        for c in contradictions:
            if c.fact_a and c.fact_b:
                item = {
                    "id_a": c.fact_a.fact_id,
                    "id_b": c.fact_b.fact_id,
                    "desc": c.description,
                    "rationale": c.resolution_rationale,
                }
                if c.conflict_type == ConflictType.CORRECTION:
                    corr_batch.append(item)
                elif c.conflict_type == ConflictType.RETRACTION:
                    retract_batch.append(item)
                else:
                    contra_batch.append(item)

        if contra_batch:
            self.client.execute_query(
                """
                UNWIND $batch as c
                MATCH (fa:Fact {id: c.id_a}), (fb:Fact {id: c.id_b})
                MERGE (fa)-[:CONTRADICTS {description: c.desc, rationale: c.rationale}]->(fb)
                """,
                {"batch": contra_batch},
            )

        if corr_batch:
            self.client.execute_query(
                """
                UNWIND $batch as c
                MATCH (fa:Fact {id: c.id_a}), (fb:Fact {id: c.id_b})
                MERGE (fa)-[:CORRECTS {description: c.desc, rationale: c.rationale}]->(fb)
                """,
                {"batch": corr_batch},
            )

        if retract_batch:
            self.client.execute_query(
                """
                UNWIND $batch as c
                MATCH (fa:Fact {id: c.id_a}), (fb:Fact {id: c.id_b})
                MERGE (fa)-[:RETRACTS {description: c.desc, rationale: c.rationale}]->(fb)
                """,
                {"batch": retract_batch},
            )

        total_nodes = len(doc_batch) + len(para_batch) + len(ent_batch) + len(fact_batch)
        total_rels = len(para_batch) + len(mention_batch) + len(fact_batch) + len(contra_batch) + len(corr_batch) + len(retract_batch)

        return KnowledgeGraphSummary(
            total_nodes=total_nodes,
            total_relationships=total_rels,
            entity_nodes_count=len(ent_batch),
            fact_nodes_count=len(fact_batch),
            contradiction_edges_count=len(contra_batch),
            correction_edges_count=len(corr_batch) + len(retract_batch),
            graph_status="SYNCHRONIZED",
        )
