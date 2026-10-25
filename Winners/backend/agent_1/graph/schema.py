"""Cypher schema definitions, constraints, and indexes for Neo4j."""

from agent_1.graph.client import Neo4jClient


def initialize_schema(client: Neo4jClient) -> None:
    """Create constraints and indexes in Neo4j for fast entity and evidence retrieval."""
    if not client.is_connected:
        return

    statements = [
        # Document constraints
        "CREATE CONSTRAINT doc_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
        # Paragraph constraints
        "CREATE CONSTRAINT para_id_unique IF NOT EXISTS FOR (p:Paragraph) REQUIRE p.id IS UNIQUE",
        # Entity constraints
        "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE",
        # Fact constraints
        "CREATE CONSTRAINT fact_id_unique IF NOT EXISTS FOR (f:Fact) REQUIRE f.id IS UNIQUE",
        "CREATE CONSTRAINT case_id_unique IF NOT EXISTS FOR (c:Case) REQUIRE c.id IS UNIQUE",
        # Indexes for fast lookup
        "CREATE INDEX doc_pub_date_idx IF NOT EXISTS FOR (d:Document) ON (d.pub_date)",
        "CREATE INDEX entity_name_idx IF NOT EXISTS FOR (e:Entity) ON (e.name)",
        "CREATE INDEX fact_category_idx IF NOT EXISTS FOR (f:Fact) ON (f.category)",
    ]

    for stmt in statements:
        try:
            client.execute_query(stmt)
        except Exception as e:
            # Aura may log existing or require certain privilege levels
            pass
