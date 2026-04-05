"""
Neo4j Graph Patterns - arraz2000 architecture adopted.

Implements:
- Topic-centric bipartite overlay (GraphRAG aligned)
- 5-zone graph separation
- Curated knowledge vs raw events
"""

from .topic_graph import (
    CORE_TOPICS,
    TopicGraph,
    ZonedGraph,
    setup_graph_constraints,
)

__all__ = [
    "TopicGraph",
    "ZonedGraph",
    "CORE_TOPICS",
    "setup_graph_constraints",
]
