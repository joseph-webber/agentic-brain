"""
Neo4j integration for agentic-brain.

Uses the arraz2000 topic-centric graph pattern:
- TopicGraph for semantic overlay
- ZonedGraph for 5-zone architecture
- CORE_TOPICS for controlled vocabulary
"""

from .patterns import TopicGraph, ZonedGraph, CORE_TOPICS, setup_graph_constraints
from .brain_graph import (
    get_driver,
    get_topic_graph,
    get_zoned_graph,
    query,
    query_by_topic,
    link_to_topic,
    get_topic_health,
    get_zone_stats,
    check_zone_boundaries,
    ensure_topics_exist,
    init_graph,
    get_rag_context,
)

__all__ = [
    # Classes
    "TopicGraph",
    "ZonedGraph",
    "CORE_TOPICS",
    "setup_graph_constraints",
    # Functions
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
]
