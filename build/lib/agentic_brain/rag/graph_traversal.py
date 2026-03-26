# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Neo4j Graph Traversal RAG - Relationship-Aware Retrieval

Extends traditional RAG with knowledge graph traversal:
- Follow relationships to find connected context
- Multi-hop graph queries for deep understanding
- Combine vector similarity with graph structure
- Entity-centric retrieval patterns

Use cases:
- "Who works on Project X?" (follow WORKS_ON relationships)
- "What systems depend on Service Y?" (traverse DEPENDS_ON)
- "Show the deployment chain for Component Z" (multi-hop)
- "Find related tickets to bug #123" (similarity + links)

Advantages over pure vector search:
- Explicit relationship semantics
- Better for entity-centric queries
- Combines text + structure
- Supports reasoning chains
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class TraversalStrategy(Enum):
    """Graph traversal strategies."""

    BREADTH_FIRST = "bfs"  # Explore all neighbors first
    DEPTH_FIRST = "dfs"  # Follow one path deeply
    WEIGHTED = "weighted"  # Prioritize by relationship weight
    SIMILARITY = "similarity"  # Combine with vector similarity
    HYBRID = "hybrid"  # BFS + similarity scoring


class Neo4jDriver(Protocol):
    """Protocol for Neo4j driver."""

    def session(self, **kwargs: Any) -> Any:
        """Get a session for queries."""
        ...


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation."""

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...


@dataclass
class GraphNode:
    """A node from graph traversal."""

    labels: list[str]
    properties: dict[str, Any]
    score: float = 0.0
    depth: int = 0  # How many hops from origin
    path: list[str] = field(default_factory=list)  # Relationship types traversed

    @property
    def content(self) -> str:
        """Get text content from node."""
        # Try common content properties
        for key in ["content", "text", "description", "name", "title", "summary"]:
            if key in self.properties:
                return str(self.properties[key])
        return str(self.properties)

    @property
    def id(self) -> str | int | None:
        """Get node identifier."""
        return self.properties.get("id") or self.properties.get("uuid")


@dataclass
class GraphContext:
    """Context retrieved via graph traversal."""

    query: str
    root_nodes: list[GraphNode]
    related_nodes: list[GraphNode]
    relationships: list[dict[str, Any]]
    total_nodes: int
    max_depth: int

    def as_context_string(self, max_nodes: int = 10) -> str:
        """Format as context for LLM."""
        parts = []

        # Root entities
        if self.root_nodes:
            parts.append("Main entities:")
            for node in self.root_nodes[: max_nodes // 2]:
                parts.append(f"  - [{', '.join(node.labels)}] {node.content[:200]}")

        # Related context
        if self.related_nodes:
            parts.append("\nRelated context:")
            for node in self.related_nodes[: max_nodes // 2]:
                path_str = " → ".join(node.path) if node.path else "direct"
                parts.append(f"  - (via {path_str}) {node.content[:200]}")

        return "\n".join(parts)


class GraphTraversalRetriever:
    """
    RAG retriever using Neo4j graph traversal.

    Combines:
    - Entity matching (find starting nodes)
    - Relationship traversal (expand context)
    - Optional vector similarity (rank results)

    Example:
        retriever = GraphTraversalRetriever(driver)
        context = retriever.retrieve(
            query="deployment process for auth service",
            start_labels=["Service", "Document"],
            relationship_types=["DOCUMENTS", "DEPENDS_ON", "DEPLOYED_TO"],
            max_depth=2
        )
        print(context.as_context_string())
    """

    def __init__(
        self,
        driver: Neo4jDriver,
        embeddings: EmbeddingProvider | None = None,
        default_node_labels: list[str] | None = None,
        default_relationship_types: list[str] | None = None,
    ):
        """
        Initialize graph traversal retriever.

        Args:
            driver: Neo4j driver instance
            embeddings: Optional embedding provider for similarity
            default_node_labels: Default labels to search
            default_relationship_types: Default relationships to traverse
        """
        self.driver = driver
        self.embeddings = embeddings
        self.default_labels = default_node_labels or ["Document", "Entity"]
        self.default_relationships = default_relationship_types or [
            "RELATED_TO",
            "REFERENCES",
            "MENTIONS",
            "PART_OF",
        ]

    def retrieve(
        self,
        query: str,
        start_labels: list[str] | None = None,
        relationship_types: list[str] | None = None,
        max_depth: int = 2,
        limit: int = 20,
        strategy: TraversalStrategy = TraversalStrategy.HYBRID,
    ) -> GraphContext:
        """
        Retrieve context via graph traversal.

        Args:
            query: Search query
            start_labels: Node labels to start from
            relationship_types: Relationship types to traverse
            max_depth: Maximum traversal depth
            limit: Maximum nodes to return
            strategy: Traversal strategy

        Returns:
            GraphContext with traversed nodes
        """
        labels = start_labels or self.default_labels
        relationships = relationship_types or self.default_relationships

        # Step 1: Find root nodes matching query
        root_nodes = self._find_root_nodes(query, labels, limit=limit // 2)

        if not root_nodes:
            return GraphContext(
                query=query,
                root_nodes=[],
                related_nodes=[],
                relationships=[],
                total_nodes=0,
                max_depth=0,
            )

        # Step 2: Traverse from root nodes
        if strategy == TraversalStrategy.BREADTH_FIRST:
            related, rels = self._traverse_bfs(
                root_nodes, relationships, max_depth, limit
            )
        elif strategy == TraversalStrategy.DEPTH_FIRST:
            related, rels = self._traverse_dfs(
                root_nodes, relationships, max_depth, limit
            )
        elif strategy == TraversalStrategy.WEIGHTED:
            related, rels = self._traverse_weighted(
                root_nodes, relationships, max_depth, limit
            )
        elif strategy == TraversalStrategy.SIMILARITY:
            related, rels = self._traverse_similarity(
                query, root_nodes, relationships, max_depth, limit
            )
        else:  # HYBRID
            related, rels = self._traverse_hybrid(
                query, root_nodes, relationships, max_depth, limit
            )

        return GraphContext(
            query=query,
            root_nodes=root_nodes,
            related_nodes=related,
            relationships=rels,
            total_nodes=len(root_nodes) + len(related),
            max_depth=max_depth,
        )

    def _find_root_nodes(
        self, query: str, labels: list[str], limit: int = 10
    ) -> list[GraphNode]:
        """Find starting nodes matching query."""
        # Try vector search first if available
        if self.embeddings:
            nodes = self._vector_search(query, labels, limit)
            if nodes:
                return nodes

        # Fall back to text search
        return self._text_search(query, labels, limit)

    def _vector_search(
        self, query: str, labels: list[str], limit: int
    ) -> list[GraphNode]:
        """Find nodes via vector similarity."""
        try:
            query_embedding = self.embeddings.embed(query)

            # Neo4j vector index search
            # Assumes nodes have 'embedding' property and vector index exists
            label_filter = " OR ".join(f"n:{label}" for label in labels)

            cypher = f"""
            CALL db.index.vector.queryNodes('embedding_index', $limit, $embedding)
            YIELD node, score
            WHERE {label_filter}
            RETURN node, labels(node) as labels, score
            ORDER BY score DESC
            LIMIT $limit
            """

            with self.driver.session() as session:
                result = session.run(cypher, embedding=query_embedding, limit=limit)
                return [
                    GraphNode(
                        labels=record["labels"],
                        properties=dict(record["node"]),
                        score=record["score"],
                        depth=0,
                    )
                    for record in result
                ]

        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

    def _text_search(
        self, query: str, labels: list[str], limit: int
    ) -> list[GraphNode]:
        """Find nodes via text matching."""
        # Extract keywords for matching
        keywords = [w.strip() for w in query.split() if len(w) > 2]

        if not keywords:
            return []

        # Build text search query
        label_filter = " OR ".join(f"n:{label}" for label in labels)
        text_conditions = " OR ".join(
            f"toLower(n.content) CONTAINS toLower('{kw}')" for kw in keywords[:5]
        )

        cypher = f"""
        MATCH (n)
        WHERE ({label_filter}) AND ({text_conditions})
        RETURN n, labels(n) as labels
        LIMIT $limit
        """

        try:
            with self.driver.session() as session:
                result = session.run(cypher, limit=limit)
                return [
                    GraphNode(
                        labels=record["labels"],
                        properties=dict(record["n"]),
                        score=0.5,
                        depth=0,
                    )
                    for record in result
                ]
        except Exception as e:
            logger.warning(f"Text search failed: {e}")
            return []

    def _traverse_bfs(
        self,
        root_nodes: list[GraphNode],
        relationships: list[str],
        max_depth: int,
        limit: int,
    ) -> tuple[list[GraphNode], list[dict[str, Any]]]:
        """Breadth-first traversal from root nodes."""
        rel_filter = "|".join(relationships)

        # Get node IDs or use properties
        root_ids = [
            n.properties.get("id")
            or n.properties.get("uuid")
            or n.properties.get("name")
            for n in root_nodes
            if n.properties
        ]

        if not root_ids:
            return [], []

        cypher = f"""
        MATCH (start)
        WHERE start.id IN $root_ids OR start.uuid IN $root_ids OR start.name IN $root_ids
        CALL apoc.path.expandConfig(start, {{
            relationshipFilter: '{rel_filter}',
            minLevel: 1,
            maxLevel: $max_depth,
            uniqueness: 'NODE_GLOBAL'
        }})
        YIELD path
        WITH last(nodes(path)) as node, length(path) as depth,
             [r in relationships(path) | type(r)] as path_types
        RETURN DISTINCT node, labels(node) as labels, depth, path_types
        LIMIT $limit
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    cypher, root_ids=root_ids, max_depth=max_depth, limit=limit
                )

                nodes = []
                rels = []
                for record in result:
                    nodes.append(
                        GraphNode(
                            labels=record["labels"],
                            properties=dict(record["node"]),
                            depth=record["depth"],
                            path=record["path_types"],
                        )
                    )

                return nodes, rels

        except Exception as e:
            logger.warning(f"BFS traversal failed (APOC may not be installed): {e}")
            # Fallback to simple traversal
            return self._simple_traverse(root_nodes, relationships, max_depth, limit)

    def _traverse_dfs(
        self,
        root_nodes: list[GraphNode],
        relationships: list[str],
        max_depth: int,
        limit: int,
    ) -> tuple[list[GraphNode], list[dict[str, Any]]]:
        """Depth-first traversal."""
        # For now, use same as BFS (Neo4j handles efficiently)
        return self._traverse_bfs(root_nodes, relationships, max_depth, limit)

    def _traverse_weighted(
        self,
        root_nodes: list[GraphNode],
        relationships: list[str],
        max_depth: int,
        limit: int,
    ) -> tuple[list[GraphNode], list[dict[str, Any]]]:
        """Traverse prioritizing weighted relationships."""
        rel_filter = "|".join(relationships)
        root_ids = [
            n.properties.get("id") or n.properties.get("uuid")
            for n in root_nodes
            if n.properties
        ]

        if not root_ids:
            return [], []

        # Use relationship weight property if available
        cypher = f"""
        MATCH (start)-[r:{rel_filter}*1..{max_depth}]->(end)
        WHERE start.id IN $root_ids OR start.uuid IN $root_ids
        WITH end, labels(end) as labels,
             reduce(w = 0, rel in relationships(r) | w + coalesce(rel.weight, 1.0)) as total_weight,
             length(r) as depth
        RETURN DISTINCT end, labels, total_weight, depth
        ORDER BY total_weight DESC
        LIMIT $limit
        """

        try:
            with self.driver.session() as session:
                result = session.run(cypher, root_ids=root_ids, limit=limit)
                return [
                    GraphNode(
                        labels=record["labels"],
                        properties=dict(record["end"]),
                        score=record["total_weight"],
                        depth=record["depth"],
                    )
                    for record in result
                ], []
        except Exception as e:
            logger.warning(f"Weighted traversal failed: {e}")
            return [], []

    def _traverse_similarity(
        self,
        query: str,
        root_nodes: list[GraphNode],
        relationships: list[str],
        max_depth: int,
        limit: int,
    ) -> tuple[list[GraphNode], list[dict[str, Any]]]:
        """Traverse and rank by similarity to query."""
        # First do BFS traversal
        nodes, rels = self._traverse_bfs(
            root_nodes, relationships, max_depth, limit * 2
        )

        if not nodes or not self.embeddings:
            return nodes[:limit], rels

        # Re-rank by similarity
        query_emb = self.embeddings.embed(query)

        for node in nodes:
            content_emb = self.embeddings.embed(node.content[:500])
            node.score = self._cosine_similarity(query_emb, content_emb)

        nodes.sort(key=lambda n: n.score, reverse=True)
        return nodes[:limit], rels

    def _traverse_hybrid(
        self,
        query: str,
        root_nodes: list[GraphNode],
        relationships: list[str],
        max_depth: int,
        limit: int,
    ) -> tuple[list[GraphNode], list[dict[str, Any]]]:
        """Combine BFS traversal with similarity scoring."""
        # BFS for structure
        nodes, rels = self._traverse_bfs(
            root_nodes, relationships, max_depth, limit * 2
        )

        # Score by: depth penalty + similarity bonus
        if self.embeddings:
            query_emb = self.embeddings.embed(query)
            for node in nodes:
                content_emb = self.embeddings.embed(node.content[:500])
                similarity = self._cosine_similarity(query_emb, content_emb)
                # Closer nodes (lower depth) get bonus
                depth_penalty = node.depth * 0.1
                node.score = similarity - depth_penalty
        else:
            # Just use depth
            for node in nodes:
                node.score = 1.0 / (node.depth + 1)

        nodes.sort(key=lambda n: n.score, reverse=True)
        return nodes[:limit], rels

    def _simple_traverse(
        self,
        root_nodes: list[GraphNode],
        relationships: list[str],
        max_depth: int,
        limit: int,
    ) -> tuple[list[GraphNode], list[dict[str, Any]]]:
        """Simple traversal without APOC."""
        rel_filter = "|".join(relationships)
        root_ids = [
            n.properties.get("id")
            or n.properties.get("uuid")
            or n.properties.get("name")
            for n in root_nodes
        ]

        if not root_ids:
            return [], []

        cypher = f"""
        MATCH (start)-[r:{rel_filter}*1..{max_depth}]-(end)
        WHERE start.id IN $root_ids OR start.uuid IN $root_ids OR start.name IN $root_ids
        RETURN DISTINCT end, labels(end) as labels, length(r) as depth
        LIMIT $limit
        """

        try:
            with self.driver.session() as session:
                result = session.run(cypher, root_ids=root_ids, limit=limit)
                return [
                    GraphNode(
                        labels=record["labels"],
                        properties=dict(record["end"]),
                        depth=record["depth"],
                    )
                    for record in result
                ], []
        except Exception as e:
            logger.warning(f"Simple traversal failed: {e}")
            return [], []

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)


class EntityCentricRetriever(GraphTraversalRetriever):
    """
    Specialized retriever for entity-focused queries.

    Best for:
    - "Tell me about [entity]"
    - "What's the status of [entity]?"
    - "Who works on [entity]?"

    Automatically identifies entities and retrieves their context.
    """

    def __init__(
        self,
        driver: Neo4jDriver,
        embeddings: EmbeddingProvider | None = None,
        entity_labels: list[str] | None = None,
    ):
        super().__init__(driver, embeddings)
        self.entity_labels = entity_labels or [
            "Person",
            "Project",
            "Service",
            "Team",
            "Document",
            "Ticket",
        ]

    def retrieve_for_entity(
        self,
        entity_name: str,
        context_depth: int = 2,
        limit: int = 20,
    ) -> GraphContext:
        """
        Retrieve all context for a specific entity.

        Finds the entity node and retrieves its neighborhood.
        """
        # Find entity
        cypher = """
        MATCH (n)
        WHERE n.name = $name OR n.title = $name OR n.id = $name
        RETURN n, labels(n) as labels
        LIMIT 1
        """

        with self.driver.session() as session:
            result = session.run(cypher, name=entity_name)
            record = result.single()

            if not record:
                return GraphContext(
                    query=entity_name,
                    root_nodes=[],
                    related_nodes=[],
                    relationships=[],
                    total_nodes=0,
                    max_depth=0,
                )

            root = GraphNode(
                labels=record["labels"],
                properties=dict(record["n"]),
                depth=0,
            )

        # Get neighborhood
        return self.retrieve(
            query=entity_name,
            start_labels=root.labels,
            max_depth=context_depth,
            limit=limit,
        )
