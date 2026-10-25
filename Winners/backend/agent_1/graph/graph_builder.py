"""Links case runs into the evidence graph built by sync_graph.py (contradictions, corrections, case membership)."""

import logging
from typing import List, Optional
from agent_1.graph.client import Neo4jClient
from agent_1.graph.schema import initialize_schema
from agent_1.models.evidence import ContradictionItem, ConflictType
from agent_1.models.case_file import KnowledgeGraphSummary

logger = logging.getLogger(__name__)

_EDGE_FOR = {ConflictType.CORRECTION: "CORRECTS", ConflictType.RETRACTION: "RETRACTS"}


class Neo4jGraphBuilder:
    """Adds case-level structure on top of the resolved evidence graph.

    Corpus nodes (Document, Paragraph, Fact, Entity) are owned by sync_graph.py and are never created or
    rewritten here, so a case run cannot reintroduce excluded content.
    """

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()
        self._initialized = False

    def ensure_schema(self):
        if not self._initialized:
            initialize_schema(self.client)
            self._initialized = True

    def link_case(
        self,
        case_id: str,
        doc_ids: List[str],
        fact_ids: List[str],
        entity_count: int,
        contradictions: List[ContradictionItem],
    ) -> KnowledgeGraphSummary:
        """MERGE a (:Case) linked to existing evidence documents, plus edges between existing evidence facts."""
        edges = {"CONTRADICTS": [], "CORRECTS": [], "RETRACTS": []}
        for c in contradictions:
            if c.fact_a and c.fact_b:
                edges[_EDGE_FOR.get(c.conflict_type, "CONTRADICTS")].append({
                    "id_a": c.fact_a.fact_id, "id_b": c.fact_b.fact_id, "type": c.conflict_type.value,
                    "desc": c.description, "rationale": c.resolution_rationale,
                })

        def summary(status: str, docs: int, rels: dict) -> KnowledgeGraphSummary:
            correction = rels.get("CORRECTS", 0) + rels.get("RETRACTS", 0)
            return KnowledgeGraphSummary(
                total_nodes=1 + docs,
                total_relationships=docs + sum(rels.values()),
                entity_nodes_count=entity_count,
                fact_nodes_count=len(fact_ids),
                contradiction_edges_count=rels.get("CONTRADICTS", 0),
                correction_edges_count=correction,
                graph_status=status,
            )

        self.ensure_schema()
        if not self.client.is_connected:
            return summary("MOCK_RECORDED", len(doc_ids), {k: len(v) for k, v in edges.items()})

        linked = self.client.execute_query(
            """
            MERGE (c:Case {id: $case_id})
            WITH c
            UNWIND $doc_ids AS did
            MATCH (d:Document {id: did})
            MERGE (c)-[:INCLUDES]->(d)
            RETURN count(d) AS n
            """,
            {"case_id": case_id, "doc_ids": doc_ids},
        )
        docs_linked = linked[0]["n"] if linked else 0

        # Only facts that exist in the resolved graph get edges; synthetic proxies are skipped.
        created = {}
        for rel, batch in edges.items():
            if not batch:
                continue
            rows = self.client.execute_query(
                f"""
                UNWIND $batch AS c
                MATCH (fa:Fact {{id: c.id_a}}), (fb:Fact {{id: c.id_b}})
                MERGE (fa)-[r:{rel} {{case_id: $case_id}}]->(fb)
                SET r.conflict_type = c.type, r.description = c.desc, r.rationale = c.rationale
                RETURN count(r) AS n
                """,
                {"batch": batch, "case_id": case_id},
            )
            created[rel] = rows[0]["n"] if rows else 0

        return summary("SYNCHRONIZED", docs_linked, created)
