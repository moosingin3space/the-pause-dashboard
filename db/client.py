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

    def get_people_with_stats(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.query("""
            MATCH (p:Person)
            OPTIONAL MATCH (p)-[:PARTICIPATED_IN]->(d:Decision)
            WITH p, count(d) as decision_count
            RETURN p.name as name, p.role as role, decision_count
            ORDER BY decision_count DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_agents_with_stats(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.query("""
            MATCH (a:Agent)
            OPTIONAL MATCH (a)-[:PARTICIPATED_IN]->(d:Decision)
            WITH a, count(d) as decision_count
            RETURN a.name as name, a.description as description, decision_count
            ORDER BY decision_count DESC
            LIMIT $limit
        """, {"limit": limit})

    def get_tasks(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.query("MATCH (t:Task) RETURN t LIMIT $limit", {"limit": limit})

    def get_decisions_by_influence(self, influence_type: str) -> int:
        result = self.query(
            "MATCH (d:Decision) WHERE d.ai_influence = $influenceType RETURN count(d) AS DecisionCount",
            {"influenceType": influence_type}
        )
        return result[0]["DecisionCount"] if result else 0

    def get_decision_influence_stats(self) -> dict[str, Any]:
        high_count = self.get_decisions_by_influence("high")
        low_count = self.get_decisions_by_influence("low")
        total = high_count + low_count
        return {
            "high": high_count,
            "low": low_count,
            "total": total,
            "high_rate": (high_count / total * 100) if total > 0 else 0,
            "low_rate": (low_count / total * 100) if total > 0 else 0,
        }

    def get_dashboard_stats(self) -> dict[str, Any]:
        result = self.query("""
            MATCH (d:Decision)
            WITH count(d) as total_decisions
            
            OPTIONAL MATCH (d2:Decision)-[:LED_TO]->(o:Outcome)
            WHERE o.type = 'good'
            WITH total_decisions, count(DISTINCT d2) as good_outcomes
            
            OPTIONAL MATCH (d3:Decision)-[:LED_TO]->(o2:Outcome)
            WHERE o2.type = 'bad'
            WITH total_decisions, good_outcomes, count(DISTINCT d3) as bad_outcomes
            
            OPTIONAL MATCH (d4:Decision)<-[:CONTRIBUTED_TO]-(p:Person)
            WITH total_decisions, good_outcomes, bad_outcomes, count(DISTINCT d4) as human_decisions
            
            OPTIONAL MATCH (d5:Decision)<-[:CONTRIBUTED_TO]-(a:Agent)
            RETURN total_decisions, good_outcomes, bad_outcomes, human_decisions, count(DISTINCT d5) as ai_decisions
        """)
        
        if result:
            r = result[0]
            total = r["total_decisions"]
            good = r["good_outcomes"]
            bad = r["bad_outcomes"]
            return {
                "total_decisions": total,
                "good_outcomes": good,
                "bad_outcomes": bad,
                "good_rate": (good / (good + bad) * 100) if (good + bad) > 0 else 0,
                "bad_rate": (bad / (good + bad) * 100) if (good + bad) > 0 else 0,
                "human_decisions": r["human_decisions"],
                "ai_decisions": r["ai_decisions"],
            }
        
        return {
            "total_decisions": 0,
            "good_outcomes": 0,
            "bad_outcomes": 0,
            "good_rate": 0,
            "bad_rate": 0,
            "human_decisions": 0,
            "ai_decisions": 0,
        }

    def get_decisions_by_type(self, per_type: int = 4) -> list[dict[str, Any]]:
        return self.query("""
            MATCH (d:Decision)
            WHERE d.name IS NOT NULL
            OPTIONAL MATCH (p:Person)-[:PARTICIPATED_IN]->(d)
            OPTIONAL MATCH (a:Agent)-[:PARTICIPATED_IN]->(d)
            OPTIONAL MATCH (d)-[:CONTRIBUTED_TO*1..2]->(x)<-[:CAUSED_BY]-(o:Outcome)
            WHERE x IS NULL OR x:Task OR x:Event
            WITH d, 
                 collect(DISTINCT p.name) as people, 
                 collect(DISTINCT a.name) as agents,
                 collect(DISTINCT o.name)[0] as outcome,
                 CASE WHEN size(collect(DISTINCT a)) > 0 AND size(collect(DISTINCT p)) > 0 THEN 'both'
                      WHEN size(collect(DISTINCT a)) > 0 THEN 'ai' 
                      WHEN size(collect(DISTINCT p)) > 0 THEN 'human' 
                      ELSE 'unknown' END as influence_type
            WITH d.name as decision, d.description as description, outcome,
                 [x IN people WHERE x IS NOT NULL] as people,
                 [x IN agents WHERE x IS NOT NULL] as agents,
                 influence_type
            ORDER BY CASE influence_type WHEN 'both' THEN 0 WHEN 'human' THEN 1 WHEN 'ai' THEN 2 ELSE 3 END, decision
            WITH influence_type, collect({
                decision: decision,
                description: description,
                outcome: outcome,
                people: people,
                agents: agents,
                influence_type: influence_type
            })[0..$per_type] as decisions
            UNWIND decisions as d
            RETURN d.decision as decision, d.description as description,
                   d.outcome as outcome, d.people as people, d.agents as agents,
                   d.influence_type as influence_type
        """, {"per_type": per_type})

    def get_outcomes_for_summary(self, limit: int = 20) -> list[dict[str, Any]]:
        return self.query("""
            MATCH (o:Outcome)
            OPTIONAL MATCH (o)<-[:CAUSED_BY*1..3]-(x)
            WHERE x:Task OR x:Event OR x:Decision
            OPTIONAL MATCH (d:Decision)-[:CONTRIBUTED_TO*0..2]->(x)
            OPTIONAL MATCH (p:Person)-[:PARTICIPATED_IN]->(d)
            OPTIONAL MATCH (a:Agent)-[:PARTICIPATED_IN]->(d)
            WITH o, collect(DISTINCT d.name) as decisions, 
                 collect(DISTINCT p.name) as people, 
                 collect(DISTINCT a.name) as agents
            RETURN o.name as outcome, o.description as description,
                   decisions, people, agents
            LIMIT $limit
        """, {"limit": limit})

    def get_contribution_split(self) -> dict[str, Any]:
        decision_result = self.query("""
            MATCH (d:Decision)
            OPTIONAL MATCH (p:Person)-[:PARTICIPATED_IN]->(d)
            OPTIONAL MATCH (a:Agent)-[:PARTICIPATED_IN]->(d)
            WITH d,
                 CASE WHEN a IS NOT NULL AND p IS NOT NULL THEN 'both'
                      WHEN a IS NOT NULL THEN 'ai'
                      WHEN p IS NOT NULL THEN 'human'
                      ELSE 'none' END as contributor_type
            RETURN contributor_type, count(DISTINCT d) as count
        """)
        
        outcome_result = self.query("""
            MATCH (o:Outcome)<-[:CAUSED_BY]-(x)<-[:CONTRIBUTED_TO*1..2]-(d:Decision)
            WHERE x:Task OR x:Event
            OPTIONAL MATCH (p:Person)-[:PARTICIPATED_IN]->(d)
            OPTIONAL MATCH (a:Agent)-[:PARTICIPATED_IN]->(d)
            WITH o,
                 CASE WHEN a IS NOT NULL AND p IS NOT NULL THEN 'both'
                      WHEN a IS NOT NULL THEN 'ai'
                      WHEN p IS NOT NULL THEN 'human'
                      ELSE 'none' END as contributor_type
            RETURN contributor_type, count(DISTINCT o) as count
        """)
        
        decisions = {"human": 0, "ai": 0, "both": 0, "none": 0, "total": 0}
        for row in decision_result:
            decisions[row["contributor_type"]] = row["count"]
            decisions["total"] += row["count"]
        
        outcomes = {"human": 0, "ai": 0, "both": 0, "none": 0, "total": 0}
        for row in outcome_result:
            outcomes[row["contributor_type"]] = row["count"]
            outcomes["total"] += row["count"]
        
        total = decisions["total"] or 1
        return {
            "human_only": decisions["human"],
            "ai_only": decisions["ai"],
            "both": decisions["both"],
            "none": decisions["none"],
            "total": decisions["total"],
            "human_only_rate": decisions["human"] / total * 100,
            "ai_only_rate": decisions["ai"] / total * 100,
            "both_rate": decisions["both"] / total * 100,
            "none_rate": decisions["none"] / total * 100,
        }

    def get_dashboard_summary(self) -> dict[str, Any]:
        result = self.query("""
            MATCH (d:Decision) WITH count(d) as total_decisions
            MATCH (o:Outcome) WITH total_decisions, count(o) as total_outcomes
            MATCH (p:Person) WITH total_decisions, total_outcomes, count(p) as total_people
            MATCH (a:Agent) 
            RETURN total_decisions, total_outcomes, total_people, count(a) as total_agents
        """)
        
        t = result[0] if result else {}
        return {
            "total_decisions": t.get("total_decisions", 0),
            "total_outcomes": t.get("total_outcomes", 0),
            "total_people": t.get("total_people", 0),
            "total_agents": t.get("total_agents", 0),
        }

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
