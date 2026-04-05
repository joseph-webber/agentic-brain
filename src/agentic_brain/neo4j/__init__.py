"""
Neo4j integration for agentic-brain.

Uses the arraz2000 topic-centric graph pattern:
- TopicGraph for semantic overlay
- ZonedGraph for 5-zone architecture
- CORE_TOPICS for controlled vocabulary
"""

from .brain_graph import (
    check_zone_boundaries,
    ensure_topics_exist,
    get_driver,
    get_rag_context,
    get_topic_graph,
    get_topic_health,
    get_zone_stats,
    get_zoned_graph,
    init_graph,
    link_to_topic,
    query,
    query_by_topic,
)
from .patterns import CORE_TOPICS, TopicGraph, ZonedGraph, setup_graph_constraints

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
