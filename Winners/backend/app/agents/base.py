from typing import List, Dict, Any, Set
from app.models.case import AgentRole
from app.ingestion.corpus import corpus, SearchResult

class BaseAgent:
    def __init__(self, role: AgentRole):
        self.role = role
        self.private_memory: Dict[str, Any] = {
            "retrieved_docs": [],
            "hypotheses": [],
            "concessions_made": [],
            "attacks_received": [],
            "action_log": []
        }
        self.executed_queries: Set[str] = set()
        self.total_tokens_used: int = 0

    def query_corpus(
        self,
        query: str,
        as_of_date: str,
        country: str = "general",
        sector: str = "general",
        max_tier: int = 4,
        event_id: str = "E5",
        limit: int = 5
    ) -> List[SearchResult]:
        """
        Executes a corpus search while enforcing NFR5 (no duplicate queries).
        """
        query_sig = f"{query.lower().strip()}|{country}|{sector}|{as_of_date}"
        if query_sig in self.executed_queries:
            # Query deduplication - return cached memory
            self.log_action("QUERY_DEDUPLICATED", f"Skipped duplicate query: '{query}'")
            return []

        self.executed_queries.add(query_sig)
        results = corpus.search(
            query=query,
            as_of_date=as_of_date,
            country=country,
            sector=sector,
            max_tier=max_tier,
            event_id=event_id,
            limit=limit
        )

        doc_ids = [r.document.metadata.DOC_ID for r in results]
        self.private_memory["retrieved_docs"].extend(doc_ids)
        self.log_action("SEARCH_EXECUTED", f"Query '{query}' returned {len(results)} docs: {doc_ids}")
        return results

    def log_action(self, action: str, details: str):
        self.private_memory["action_log"].append({
            "agent": self.role.value,
            "action": action,
            "details": details
        })
