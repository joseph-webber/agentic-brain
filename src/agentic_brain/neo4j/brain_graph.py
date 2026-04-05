"""
Brain Graph - Unified interface to the topic-centric Neo4j graph.

This is the main entry point for all Neo4j operations in the brain.
It automatically uses the TopicGraph pattern for semantic queries.
"""

import os
from typing import List, Dict, Any
from neo4j import GraphDatabase
from .patterns import TopicGraph, ZonedGraph, CORE_TOPICS, setup_graph_constraints

# Singleton driver
_driver = None
_topic_graph = None
_zoned_graph = None


def get_driver():
    """Get or create Neo4j driver."""
    global _driver
    if _driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "Brain2026")
        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver


def get_topic_graph() -> TopicGraph:
    """Get the TopicGraph instance for semantic queries."""
    global _topic_graph
    if _topic_graph is None:
        _topic_graph = TopicGraph(get_driver())
    return _topic_graph


def get_zoned_graph() -> ZonedGraph:
    """Get the ZonedGraph instance for zone management."""
    global _zoned_graph
    if _zoned_graph is None:
        _zoned_graph = ZonedGraph(get_driver())
    return _zoned_graph


def query(cypher: str, params: Dict = None) -> List[Dict[str, Any]]:
    """Run a raw Cypher query."""
    with get_driver().session() as session:
        result = session.run(cypher, params or {})
        return [dict(r) for r in result]


def query_by_topic(topic: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Find all nodes related to a topic - GraphRAG retrieval."""
    return get_topic_graph().query_by_topic(topic, limit)


def link_to_topic(node_label: str, node_id: str, topic: str, 
                  relationship: str = "RELATES_TO") -> bool:
    """Link any node to a topic."""
    return get_topic_graph().link_to_topic(node_label, node_id, topic, relationship)


def get_topic_health() -> Dict[str, Any]:
    """Check topic connectivity health."""
    return get_topic_graph().get_topic_health()


def get_zone_stats() -> Dict[int, Dict[str, int]]:
    """Get node counts per zone."""
    return get_zoned_graph().get_zone_stats()


def check_zone_boundaries() -> List[Dict[str, Any]]:
    """Find zone boundary violations."""
    return get_zoned_graph().check_zone_boundaries()


def ensure_topics_exist() -> int:
    """Create core topic nodes if they don't exist."""
    return get_topic_graph().ensure_topics_exist()


def init_graph():
    """Initialize the graph with constraints and topics."""
    setup_graph_constraints(get_driver())
    ensure_topics_exist()
    return True


# Convenience function for RAG context
def get_rag_context(topics: List[str], limit_per_topic: int = 5) -> str:
    """Get RAG context by querying multiple topics.
    
    Returns formatted context string for LLM consumption.
    """
    context_parts = []
    tg = get_topic_graph()
    
    for topic in topics:
        results = tg.query_by_topic(topic, limit_per_topic)
        if results:
            context_parts.append(f"\n## Context for '{topic}':")
            for r in results:
                context_parts.append(f"- [{r['label']}] {r['item']} (via {r['relationship']})")
    
    return "\n".join(context_parts) if context_parts else "No relevant context found."


# Export all
__all__ = [
    "get_driver",
    "get_topic_graph", 
    "get_zoned_graph",
    "query",
    "query_by_topic",
    "link_to_topic",
    "get_topic_health",
    "get_zone_stats",
    "check_zone_boundaries",
    "ensure_topics_exist",
    "init_graph",
    "get_rag_context",
    "CORE_TOPICS",
]
