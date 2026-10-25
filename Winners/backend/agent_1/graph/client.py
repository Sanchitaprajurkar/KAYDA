"""Neo4j driver connection and session manager."""

import logging
from typing import Optional, List, Dict, Any
from neo4j import GraphDatabase, Driver, Session

from agent_1.config import settings

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Manages connections and query execution against Neo4j Graph Database."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ):
        self.uri = uri or settings.NEO4J_URI
        self.user = user or settings.NEO4J_USER
        self.password = password or settings.NEO4J_PASSWORD
        self.database = database or settings.NEO4J_DATABASE
        self._driver: Optional[Driver] = None
        self._is_mock = False

    def get_driver(self) -> Driver:
        """Initialize and return driver instance with fallback."""
        if self._driver is not None:
            return self._driver

        if not self.uri or not self.password:
            if settings.NEO4J_MOCK_FALLBACK:
                logger.warning("Neo4j credentials not fully provided; operating in mock graph mode.")
                self._is_mock = True
                return None
            raise ValueError("Neo4j URI and password must be configured.")

        # Attempt connection with configured user
        try:
            driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            with driver.session(database=self.database) as session:
                session.run("RETURN 1 as test")
            self._driver = driver
            return self._driver
        except Exception as e:
            logger.warning(f"Connection with user '{self.user}' failed: {e}. Attempting with 'neo4j' user...")
            try:
                driver = GraphDatabase.driver(self.uri, auth=("neo4j", self.password))
                with driver.session(database=self.database) as session:
                    session.run("RETURN 1 as test")
                self._driver = driver
                return self._driver
            except Exception as e2:
                logger.error(f"Failed to connect to Neo4j: {e2}")
                if settings.NEO4J_MOCK_FALLBACK:
                    self._is_mock = True
                    return None
                raise

    @property
    def is_connected(self) -> bool:
        """Check if active Neo4j connection is established."""
        try:
            d = self.get_driver()
            return d is not None and not self._is_mock
        except Exception:
            return False

    def execute_query(self, cypher: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return list of records."""
        driver = self.get_driver()
        if self._is_mock or not driver:
            logger.debug(f"[MOCK GRAPH] Cypher: {cypher} | params: {parameters}")
            return []

        with driver.session(database=self.database) as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    def close(self):
        """Close driver connections."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
