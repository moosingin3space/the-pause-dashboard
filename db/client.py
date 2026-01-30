from dataclasses import dataclass
from typing import Any
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

load_dotenv()


@dataclass
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str

    @classmethod
    def from_env(cls) -> "Neo4jConfig":
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )


class Neo4jClient:
    def __init__(self, config: Neo4jConfig | None = None):
        self.config = config or Neo4jConfig.from_env()
        self._driver: Driver | None = None

    @property
    def driver(self) -> Driver:
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
            )
        return self._driver

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None

    def query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.driver.session(database=self.config.database) as session:
            result = session.run(cypher, parameters or {})
            return [record.data() for record in result]

    def get_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.query("MATCH (d:Decision) RETURN d LIMIT $limit", {"limit": limit})

    def get_events(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.query("MATCH (e:Event) RETURN e LIMIT $limit", {"limit": limit})

    def get_outcomes(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.query("MATCH (o:Outcome) RETURN o LIMIT $limit", {"limit": limit})

    def get_people(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.query("MATCH (p:Person) RETURN p LIMIT $limit", {"limit": limit})

    def get_agents(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.query("MATCH (a:Agent) RETURN a LIMIT $limit", {"limit": limit})

    def get_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.query("MATCH (t:Task) RETURN t LIMIT $limit", {"limit": limit})

    def get_topology_stats(self) -> dict[str, int]:
        result = self.query("""
            MATCH (d:Decision) WITH count(d) as decisions
            MATCH (e:Event) WITH decisions, count(e) as events
            MATCH (o:Outcome) WITH decisions, events, count(o) as outcomes
            MATCH (p:Person) WITH decisions, events, outcomes, count(p) as people
            MATCH (a:Agent) WITH decisions, events, outcomes, people, count(a) as agents
            MATCH (t:Task) 
            RETURN decisions, events, outcomes, people, agents, count(t) as tasks
        """)
        return result[0] if result else {
            "decisions": 0, "events": 0, "outcomes": 0,
            "people": 0, "agents": 0, "tasks": 0
        }


_client: Neo4jClient | None = None


def get_client() -> Neo4jClient:
    global _client
    if _client is None:
        _client = Neo4jClient()
    return _client
