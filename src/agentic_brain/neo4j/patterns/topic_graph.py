"""
Topic-Centric Graph Patterns - Adopted from arraz2000/happy-skies-automation

This implements the bipartite overlay pattern where:
- Domain entities have direct factual edges
- Topics act as semantic hubs for cross-cutting retrieval
- Raw events stay isolated from domain graph

Aligned with: Microsoft GraphRAG, Neo4j GDS best practices
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Controlled topic vocabulary (capped at ~50 for semantic coherence)
CORE_TOPICS = [
    # Brain/AI topics
    "voice",
    "memory",
    "learning",
    "automation",
    "agents",
    "llm",
    "embeddings",
    # Work topics
    "jira",
    "bitbucket",
    "code_review",
    "testing",
    "deployment",
    "ci_cd",
    # Communication
    "teams",
    "email",
    "notifications",
    "calendar",
    # Data
    "neo4j",
    "redis",
    "backup",
    "sync",
    "analytics",
    # Accessibility
    "voiceover",
    "accessibility",
    "audio",
    "speech",
    # Personal
    "health",
    "trading",
    "family",
    "travel",
]


class TopicGraph:
    """Topic-centric semantic overlay for the brain graph."""

    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver

    def ensure_topics_exist(self) -> int:
        """Create core topic nodes if they don't exist."""
        query = """
        UNWIND $topics AS topic_name
        MERGE (t:Topic {name: topic_name})
        ON CREATE SET t.created_at = datetime(), t.source = 'core'
        RETURN count(t) as created
        """
        with self.driver.session() as session:
            result = session.run(query, topics=CORE_TOPICS)
            return result.single()["created"]

    def link_to_topic(
        self,
        node_label: str,
        node_id: str,
        topic: str,
        relationship: str = "RELATES_TO",
    ) -> bool:
        """Link any node to a topic with specified relationship type.

        Relationship types (use consistently):
        - RELATES_TO: General semantic connection
        - DISCUSSES: Session/conversation about topic
        - TAGGED: Explicitly tagged with topic
        - COVERS: Summary/checkpoint covers topic
        - ABOUT: Meta node (benchmark) about topic
        """
        valid_rels = ["RELATES_TO", "DISCUSSES", "TAGGED", "COVERS", "ABOUT"]
        if relationship not in valid_rels:
            relationship = "RELATES_TO"

        query = f"""
        MATCH (n:{node_label} {{id: $node_id}})
        MATCH (t:Topic {{name: $topic}})
        MERGE (n)-[r:{relationship}]->(t)
        ON CREATE SET r.created_at = datetime()
        RETURN n, t
        """
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id, topic=topic)
            return result.single() is not None

    def query_by_topic(self, topic: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Find all nodes related to a topic - core GraphRAG retrieval pattern."""
        query = """
        MATCH (n)-[r:RELATES_TO|DISCUSSES|TAGGED|COVERS|ABOUT]->(t:Topic {name: $topic})
        RETURN labels(n)[0] AS label,
               coalesce(n.name, n.title, n.id, n.key) AS item,
               type(r) AS relationship,
               n.created_at AS created
        ORDER BY n.created_at DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, topic=topic, limit=limit)
            return [dict(r) for r in result]

    def get_topic_health(self) -> Dict[str, Any]:
        """Check topic connectivity - are topics actually acting as semantic hubs?"""
        query = """
        MATCH (t:Topic)<-[r]-()
        WITH t.name AS topic, count(r) AS inbound_links, 
             collect(DISTINCT type(r)) AS rel_types
        RETURN topic, inbound_links, rel_types
        ORDER BY inbound_links DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            topics = [dict(r) for r in result]

        return {
            "total_topics": len(topics),
            "connected_topics": len([t for t in topics if t["inbound_links"] > 0]),
            "orphan_topics": len([t for t in topics if t["inbound_links"] == 0]),
            "top_topics": topics[:10],
            "health_score": len([t for t in topics if t["inbound_links"] > 0])
            / max(len(topics), 1)
            * 100,
        }


class ZonedGraph:
    """Implements the 5-zone graph architecture from arraz2000.

    Zone 1: Hook Layer (raw events, append-only)
    Zone 2: Session & Knowledge Layer (filtered signal)
    Zone 3: Domain Model (structured knowledge)
    Zone 4: Operational Config (email, spam, etc.)
    Zone 5: Meta/Benchmarking (measurement nodes)
    """

    ZONE_LABELS = {
        1: ["HookEvent", "RawMessage", "WebhookPayload"],
        2: ["Session", "Checkpoint", "SessionSummary", "Learning", "Memory"],
        3: [
            "Project",
            "Component",
            "Automation",
            "Agent",
            "Capability",
            "Topic",
            "Person",
            "Contact",
            "JiraTicket",
            "PullRequest",
        ],
        4: ["EmailAccount", "SpamDomain", "WhitelistEntry", "Config"],
        5: ["Benchmark", "HealthCheck", "Metric", "BaselineScore"],
    }

    def __init__(self, neo4j_driver):
        self.driver = neo4j_driver

    def get_zone_stats(self) -> Dict[int, Dict[str, int]]:
        """Get node counts per zone."""
        stats = {}
        for zone, labels in self.ZONE_LABELS.items():
            query = f"""
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN $labels)
            RETURN count(n) as count
            """
            with self.driver.session() as session:
                result = session.run(query, labels=labels)
                stats[zone] = {"node_count": result.single()["count"], "labels": labels}
        return stats

    def check_zone_boundaries(self) -> List[Dict[str, Any]]:
        """Find violations of zone separation (e.g., HookEvent directly linking to Topic)."""
        violations = []

        # Zone 1 should only connect to Zone 2 via PART_OF
        query = """
        MATCH (h:HookEvent)-[r]->(t:Topic)
        RETURN 'HookEvent->Topic' AS violation, count(r) AS count
        UNION
        MATCH (h:HookEvent)-[r]->(p:Project)
        RETURN 'HookEvent->Project' AS violation, count(r) AS count
        UNION
        MATCH (h:HookEvent)-[r]->(c:Component)
        RETURN 'HookEvent->Component' AS violation, count(r) AS count
        """
        with self.driver.session() as session:
            result = session.run(query)
            for r in result:
                if r["count"] > 0:
                    violations.append(dict(r))

        return violations


def setup_graph_constraints(driver) -> List[str]:
    """Create essential constraints and indexes for the topic-centric graph."""
    constraints = [
        "CREATE CONSTRAINT topic_name IF NOT EXISTS FOR (t:Topic) REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT session_id IF NOT EXISTS FOR (s:Session) REQUIRE s.id IS UNIQUE",
        "CREATE CONSTRAINT learning_id IF NOT EXISTS FOR (l:Learning) REQUIRE l.id IS UNIQUE",
        "CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE",
        "CREATE INDEX topic_created IF NOT EXISTS FOR (t:Topic) ON (t.created_at)",
        "CREATE INDEX session_updated IF NOT EXISTS FOR (s:Session) ON (s.updated_at)",
    ]

    created = []
    with driver.session() as session:
        for constraint in constraints:
            try:
                session.run(constraint)
                created.append(constraint.split()[2])
            except Exception as e:
                logger.debug(f"Constraint may already exist: {e}")

    return created
