# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Enhanced Graph RAG with vector similarity and knowledge graph construction.

Highlights (v2.16.0):
- **Native Neo4j vector search** with async driver support and transaction retries.
- **Real MLX embeddings** on Apple Silicon with deterministic fallback only when MLX is unavailable.
- **Batched UNWIND writes** for documents, chunks, entities, and relationships — no more N+1 ingest queries.
- **Hybrid retrieval with reciprocal-rank fusion (RRF)** blending vector, keyword, and graph expansion scores.
- **Community-aware retrieval** with GDS Leiden metadata persisted directly on Entity nodes.

Example:
    >>> from agentic_brain.rag.graph import EnhancedGraphRAG
    >>> rag = EnhancedGraphRAG()
    >>> await rag.index_document("Neural networks learn patterns", doc_id="doc1")
    >>> results = await rag.retrieve("machine learning", strategy="hybrid")
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from agentic_brain.core.neo4j_schema import (
    VECTOR_INDEX_NAME,
    ensure_indexes_sync,
)
from agentic_brain.core.neo4j_utils import resilient_query_sync

from .community import CommunityGraphRAG

logger = logging.getLogger(__name__)

# Lazy-loaded real embeddings (avoids import-time model load)
_mlx_embeddings = None


def _get_mlx_embeddings():
    """Return the GraphRAG embedding provider class, or None if unavailable."""
    global _mlx_embeddings
    if _mlx_embeddings is None:
        try:
            from .mlx_embeddings import MLXEmbeddings

            if MLXEmbeddings.is_available():
                _mlx_embeddings = MLXEmbeddings
                logger.info(
                    "GraphRAG using embedding provider %s",
                    MLXEmbeddings.provider_name(),
                )
        except Exception as exc:
            logger.warning("GraphRAG real embeddings unavailable: %s", exc)
    return _mlx_embeddings


def _embed_text(text: str, fallback_dim: int = 384) -> list[float]:
    """Embed text using real GraphRAG embeddings with deterministic fallback."""
    embedder = _get_mlx_embeddings()
    if embedder is not None:
        return embedder.embed(text)
    # Deterministic fallback when sentence-transformers is not installed
    from .embeddings import _fallback_embedding

    return _fallback_embedding(text, fallback_dim)


def _get_embedding_dimension(default_dim: int = 384) -> int:
    """Return the active GraphRAG embedding dimension."""
    embedder = _get_mlx_embeddings()
    if embedder is not None:
        return int(embedder.dimensions())
    return default_dim


def _validate_embedding(
    embedding: list[float], expected_dim: int, *, context: str
) -> list[float]:
    """Ensure embeddings stored in Neo4j match the configured vector dimension."""
    values = [float(value) for value in embedding]
    if len(values) != expected_dim:
        raise ValueError(
            f"{context} embedding dimension mismatch: "
            f"expected {expected_dim}, got {len(values)}"
        )
    return values


try:
    from neo4j import AsyncGraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncGraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False


class RetrievalStrategy(Enum):
    """Strategy for retrieving information from the graph."""

    VECTOR = "vector"  # Pure vector similarity search
    GRAPH = "graph"  # Graph traversal based on relationships
    HYBRID = "hybrid"  # Combine vector + graph scores
    COMMUNITY = "community"  # Use community detection for broader context


@dataclass
class GraphRAGConfig:
    """Configuration for Enhanced Graph RAG."""

    # Neo4j connection (uses lazy neo4j_pool by default)
    use_pool: bool = True  # Use shared neo4j_pool for connection

    # Vector settings
    embedding_dimension: int = 384
    vector_index_name: str = VECTOR_INDEX_NAME
    similarity_threshold: float = 0.7

    # Entity extraction
    min_entity_length: int = 3
    max_entities_per_doc: int = 50
    entity_types: List[str] = field(
        default_factory=lambda: [
            "PERSON",
            "ORGANIZATION",
            "LOCATION",
            "CONCEPT",
            "TECHNOLOGY",
        ]
    )

    # Graph traversal
    max_hop_depth: int = 3
    max_neighbors: int = 20
    relationship_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "MENTIONS": 0.5,
            "RELATED_TO": 0.7,
            "PART_OF": 0.9,
            "CONTAINS": 1.0,
        }
    )

    # Retrieval
    top_k: int = 10
    include_metadata: bool = True
    rerank: bool = True


EnhancedGraphRAGConfig = GraphRAGConfig
"""Alias exported by __init__.py for backward compatibility."""


class EnhancedGraphRAG:
    """
    Enhanced Graph RAG with Neo4j native vector search and knowledge graph construction.

    Features:
    - Vector similarity search using Neo4j's native vector index
    - Entity extraction with configurable types
    - Relationship mapping between entities
    - Multi-hop graph traversal
    - Hybrid retrieval combining vector + graph signals
    - Hierarchical community detection (Leiden → Louvain → connected components)
    - Community summarization for global search context
    - Entity resolution / deduplication
    - Reciprocal-rank fusion across vector, graph, and keyword signals
    """

    def __init__(self, config: Optional[GraphRAGConfig] = None):
        """
        Initialize Enhanced Graph RAG.

        Args:
            config: Configuration object. Uses defaults if not provided.
        """
        self.config = config or GraphRAGConfig()
        self.config.embedding_dimension = _get_embedding_dimension(
            self.config.embedding_dimension
        )
        self._initialized = False
        self._community_hierarchy = None
        self._community_graph_rag = CommunityGraphRAG(self)

    def _get_session(self):
        """Get Neo4j session using lazy pool."""
        if self.config.use_pool:
            from agentic_brain.core.neo4j_pool import get_session

            return get_session()
        else:
            # Fallback to direct connection if pool disabled
            try:
                from neo4j import GraphDatabase as _graph_db_cls
            except ImportError:
                _graph_db_cls = None
            if not NEO4J_AVAILABLE or _graph_db_cls is None:
                raise ImportError(
                    "neo4j package is required for direct graph connections. Install with: pip install neo4j"
                )

            driver = _graph_db_cls.driver("bolt://localhost:7687", auth=("neo4j", ""))
            return driver.session()

    def _run_query(
        self,
        session: Any,
        query: str,
        **params: Any,
    ) -> List[Dict[str, Any]]:
        """Run a Neo4j query with retry handling."""
        return resilient_query_sync(session, query, params)

    async def execute_query(self, query: str, **params: Any) -> List[Dict[str, Any]]:
        """Async adapter for community-aware helpers."""
        with self._get_session() as session:
            return self._run_query(session, query, **params)

    async def initialize(self) -> None:
        """
        Initialize the graph database schema and vector indexes.

        Creates:
        - Node labels: Document, Entity, Chunk
        - Relationships: CONTAINS, MENTIONS, RELATED_TO
        - Vector index for embeddings
        - Constraints for uniqueness
        """
        if self._initialized:
            return

        with self._get_session() as session:
            # Create constraints for uniqueness
            self._run_query(
                session,
                """
                CREATE CONSTRAINT document_id IF NOT EXISTS
                FOR (d:Document) REQUIRE d.id IS UNIQUE
                """,
            )
            self._run_query(
                session,
                """
                CREATE CONSTRAINT entity_id IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
                """,
            )
            self._run_query(
                session,
                """
                CREATE CONSTRAINT chunk_id IF NOT EXISTS
                FOR (c:Chunk) REQUIRE c.id IS UNIQUE
                """,
            )

            try:
                ensure_indexes_sync(session)
            except Exception as e:
                logger.warning(f"Could not create Neo4j indexes: {e}")
                logger.info("Vector search will be disabled or use fallback")

        self._initialized = True
        logger.info("Enhanced Graph RAG initialized")

    async def index_document(
        self,
        content: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """
        Index a document into the knowledge graph.

        Steps:
        1. Create Document node
        2. Extract entities from content
        3. Create Entity nodes
        4. Create relationships
        5. Chunk content and store embeddings
        6. Link chunks to document and entities

        Args:
            content: Document text content
            doc_id: Optional document ID (generated if not provided)
            metadata: Optional metadata dict
            embedding: Optional pre-computed embedding for the full document

        Returns:
            Document ID
        """
        if not self._initialized:
            await self.initialize()

        # Generate document ID if not provided
        if doc_id is None:
            doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]

        metadata = metadata or {}
        timestamp = datetime.now(UTC).isoformat()

        with self._get_session() as session:
            # 1. Create Document node
            self._run_query(
                session,
                """
                MERGE (d:Document {id: $doc_id})
                SET d.content = $content,
                    d.timestamp = $timestamp,
                    d.metadata = $metadata,
                    d.char_count = $char_count
                """,
                doc_id=doc_id,
                content=content,
                timestamp=timestamp,
                metadata=metadata,
                char_count=len(content),
            )

            # 2. Extract entities (simplified - in production use NER model)
            entities = self._extract_entities(content)

            # 3. Batch-create Entity nodes and link to document (UNWIND)
            if entities:
                entity_params = [
                    {
                        "entity_id": hashlib.sha256(e["name"].encode()).hexdigest()[
                            :16
                        ],
                        "name": e["name"],
                        "type": e["type"],
                        "count": e["count"],
                        "positions": e.get("positions", []),
                    }
                    for e in entities
                ]
                self._run_query(
                    session,
                    """
                    UNWIND $entities AS ent
                    MERGE (e:Entity {id: ent.entity_id})
                    SET e.name = ent.name,
                        e.type = ent.type,
                        e.first_seen = coalesce(e.first_seen, $timestamp),
                        e.last_seen = $timestamp,
                        e.mention_count = coalesce(e.mention_count, 0) + 1
                    WITH e, ent
                    MATCH (d:Document {id: $doc_id})
                    MERGE (d)-[r:MENTIONS]->(e)
                    SET r.count = coalesce(r.count, 0) + ent.count,
                        r.positions = ent.positions
                    """,
                    entities=entity_params,
                    doc_id=doc_id,
                    timestamp=timestamp,
                )

            # 4. Create chunks with embeddings (batched UNWIND)
            chunks = self._chunk_content(content)
            if embedding:
                # Caller provided a single embedding — reuse for all chunks
                validated = _validate_embedding(
                    embedding,
                    self.config.embedding_dimension,
                    context="chunk",
                )
                chunk_embeddings = [validated] * len(chunks)
            else:
                # Compute real embeddings per chunk
                embedder = _get_mlx_embeddings()
                if embedder is not None:
                    chunk_embeddings = embedder.embed_batch(chunks) if chunks else []
                else:
                    from .embeddings import _fallback_embedding

                    chunk_embeddings = [
                        _fallback_embedding(ct, self.config.embedding_dimension)
                        for ct in chunks
                    ]
            chunk_embeddings = [
                _validate_embedding(
                    chunk_embedding,
                    self.config.embedding_dimension,
                    context="chunk",
                )
                for chunk_embedding in chunk_embeddings
            ]
            chunk_params = [
                {
                    "chunk_id": f"{doc_id}_chunk_{i}",
                    "text": chunk_text,
                    "position": i,
                    "embedding": chunk_embeddings[i],
                }
                for i, chunk_text in enumerate(chunks)
            ]
            if chunk_params:
                self._run_query(
                    session,
                    """
                    UNWIND $chunks AS ch
                    MERGE (c:Chunk {id: ch.chunk_id})
                    SET c.text = ch.text,
                        c.content = ch.text,
                        c.position = ch.position,
                        c.document_id = $doc_id,
                        c.embedding = ch.embedding
                    WITH c, ch
                    MATCH (d:Document {id: $doc_id})
                    MERGE (d)-[:CONTAINS]->(c)
                    """,
                    chunks=chunk_params,
                    doc_id=doc_id,
                )

                # 5. Link chunks to entities they mention (batched UNWIND)
                chunk_entity_links = []
                for i, chunk_text in enumerate(chunks):
                    chunk_id = f"{doc_id}_chunk_{i}"
                    chunk_entities = self._extract_entities(chunk_text)
                    for entity in chunk_entities:
                        entity_id = hashlib.sha256(entity["name"].encode()).hexdigest()[
                            :16
                        ]
                        chunk_entity_links.append(
                            {"chunk_id": chunk_id, "entity_id": entity_id}
                        )
                if chunk_entity_links:
                    self._run_query(
                        session,
                        """
                        UNWIND $links AS link
                        MATCH (c:Chunk {id: link.chunk_id})
                        MATCH (e:Entity {id: link.entity_id})
                        MERGE (c)-[:MENTIONS]->(e)
                        """,
                        links=chunk_entity_links,
                    )

        logger.info(
            f"Indexed document {doc_id} with {len(entities)} entities and {len(chunks)} chunks"
        )

        # Run entity resolution to merge duplicates
        try:
            from .community_detection import resolve_entities

            with self._get_session() as session:
                merged = resolve_entities(session)
                if merged:
                    logger.info(
                        f"Entity resolution merged {merged} duplicates after indexing {doc_id}"
                    )
        except Exception as exc:
            logger.debug(f"Entity resolution skipped: {exc}")

        # Invalidate community cache (graph structure changed)
        self._community_hierarchy = None

        return doc_id

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text via :class:`KnowledgeExtractor`.

        ``EnhancedGraphRAG`` stores entities in its own schema, but delegates the
        extraction logic to the GraphRAG `KnowledgeExtractor` so we maintain a
        single source of truth.
        """
        from agentic_brain.rag.graphrag.knowledge_extractor import (
            KnowledgeExtractor,
            KnowledgeExtractorConfig,
        )

        extractor = getattr(self, "_knowledge_extractor", None)
        if extractor is None:
            extractor = KnowledgeExtractor(
                config=KnowledgeExtractorConfig(
                    create_schema=False,
                )
            )
            self._knowledge_extractor = extractor

        result = extractor.extract_graph_only(text, use_graphrag_pipeline=True)

        type_map = {
            "Person": "PERSON",
            "Organization": "ORGANIZATION",
            "Location": "LOCATION",
            "Concept": "CONCEPT",
            "Entity": "CONCEPT",
        }

        entities: list[dict[str, Any]] = []
        for entity in result.entities:
            entity_type = type_map.get(entity.type, str(entity.type).upper())
            if self.config.entity_types and entity_type not in self.config.entity_types:
                continue
            entities.append(
                {
                    "name": entity.name,
                    "type": entity_type,
                    "count": entity.mention_count,
                    "positions": [],
                }
            )

        return entities[: self.config.max_entities_per_doc]

    def _chunk_content(self, content: str, chunk_size: int = 500) -> List[str]:
        """
        Chunk content into smaller pieces for embedding.

        Args:
            content: Full document content
            chunk_size: Characters per chunk

        Returns:
            List of text chunks
        """
        # Simple chunking by character count
        # In production: use semantic chunking, sentence boundaries, etc.
        chunks = []
        start = 0
        while start < len(content):
            end = start + chunk_size
            # Try to break at sentence boundary
            if end < len(content):
                # Look for period followed by space
                last_period = content[start:end].rfind(". ")
                if last_period > chunk_size // 2:
                    end = start + last_period + 1

            chunks.append(content[start:end].strip())
            start = end

        return chunks

    async def retrieve(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant information from the knowledge graph.

        Args:
            query: Query text
            strategy: Retrieval strategy (vector, graph, hybrid, community)
            top_k: Number of results to return
            filters: Optional filters for metadata/entities
            query_embedding: Optional pre-computed query embedding

        Returns:
            List of results with content, score, and metadata
        """
        if not self._initialized:
            await self.initialize()

        top_k = top_k or self.config.top_k
        strategy_enum = RetrievalStrategy(strategy)

        if strategy_enum == RetrievalStrategy.VECTOR:
            return await self._vector_retrieve(query, top_k, query_embedding)
        elif strategy_enum == RetrievalStrategy.GRAPH:
            return await self._graph_retrieve(query, top_k, filters)
        elif strategy_enum == RetrievalStrategy.HYBRID:
            return await self._hybrid_retrieve(query, top_k, query_embedding, filters)
        elif strategy_enum == RetrievalStrategy.COMMUNITY:
            return await self._community_retrieve(query, top_k)

        return []

    async def _vector_retrieve(
        self, query: str, top_k: int, query_embedding: Optional[List[float]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using vector similarity search.

        Args:
            query: Query text
            top_k: Number of results
            query_embedding: Optional pre-computed embedding

        Returns:
            List of results sorted by similarity
        """
        # Use provided embedding or compute real one
        embedding = query_embedding or _embed_text(
            query, self.config.embedding_dimension
        )

        results = []
        with self._get_session() as session:
            # Vector similarity search using Neo4j vector index
            # Note: Requires Neo4j 5.11+ with vector support
            try:
                result = self._run_query(
                    session,
                    """
                    CALL db.index.vector.queryNodes(
                        $index_name,
                        $top_k,
                        $embedding
                    )
                    YIELD node AS chunk, score
                    MATCH (d:Document)-[:CONTAINS]->(chunk)
                    RETURN chunk.id AS chunk_id,
                           coalesce(chunk.content, chunk.text) AS content,
                           chunk.position AS position,
                           d.id AS doc_id,
                           d.metadata AS metadata,
                           score
                    ORDER BY score DESC
                    """,
                    index_name=self.config.vector_index_name,
                    top_k=top_k,
                    embedding=embedding,
                )

                for record in result:
                    results.append(
                        {
                            "chunk_id": record["chunk_id"],
                            "content": record["content"],
                            "position": record["position"],
                            "doc_id": record["doc_id"],
                            "metadata": record["metadata"],
                            "score": record["score"],
                            "strategy": "vector",
                        }
                    )
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
                # Fallback to simple text matching
                results = await self._fallback_text_search(query, top_k)

        return results

    async def _graph_retrieve(
        self, query: str, top_k: int, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using graph traversal.

        Strategy:
        1. Find entities matching query
        2. Traverse relationships to find connected documents
        3. Score by relationship strength and distance
        4. Return top-k results

        Args:
            query: Query text
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of results sorted by graph score
        """
        results = []
        with self._get_session() as session:
            # Find entities matching query terms
            query_words = [w.strip(".,!?;:") for w in query.split()]
            entity_pattern = "|".join(query_words)

            result = self._run_query(
                session,
                """
                MATCH (e:Entity)
                WHERE e.name =~ $pattern
                WITH e
                MATCH path = (e)<-[:MENTIONS]-(c:Chunk)<-[:CONTAINS]-(d:Document)
                WITH d, c, e, length(path) AS distance,
                     e.mention_count AS entity_importance
                RETURN DISTINCT
                       c.id AS chunk_id,
                       coalesce(c.content, c.text) AS content,
                       c.position AS position,
                       d.id AS doc_id,
                       d.metadata AS metadata,
                       distance,
                       entity_importance,
                       collect(e.name) AS entities
                ORDER BY distance ASC, entity_importance DESC
                LIMIT $top_k
                """,
                pattern=f"(?i).*({entity_pattern}).*",
                top_k=top_k,
            )

            for record in result:
                # Calculate graph score based on distance and importance
                distance_score = 1.0 / (record["distance"] + 1)
                importance_score = min(record["entity_importance"] / 10.0, 1.0)
                graph_score = (distance_score + importance_score) / 2

                results.append(
                    {
                        "chunk_id": record["chunk_id"],
                        "content": record["content"],
                        "position": record["position"],
                        "doc_id": record["doc_id"],
                        "metadata": record["metadata"],
                        "score": graph_score,
                        "entities": record["entities"],
                        "strategy": "graph",
                    }
                )

        return results

    async def _hybrid_retrieve(
        self,
        query: str,
        top_k: int,
        query_embedding: Optional[List[float]] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve using hybrid vector + graph approach.

        Strategy:
        1. Get vector results
        2. Get graph results
        3. Merge and rerank with Reciprocal Rank Fusion
        4. Return top-k

        Args:
            query: Query text
            top_k: Number of results
            query_embedding: Optional pre-computed embedding
            filters: Optional filters

        Returns:
            List of results sorted by hybrid score
        """
        # Get both vector and graph results
        from .hybrid import reciprocal_rank_fusion

        vector_results = await self._vector_retrieve(query, top_k * 2, query_embedding)
        graph_results = await self._graph_retrieve(query, top_k * 2, filters)
        fused_results = reciprocal_rank_fusion(
            [{"id": result["chunk_id"], **result} for result in vector_results],
            [{"id": result["chunk_id"], **result} for result in graph_results],
        )

        # Merge results by chunk_id
        merged = {}
        for result in vector_results:
            chunk_id = result["chunk_id"]
            merged[chunk_id] = result.copy()
            merged[chunk_id]["vector_score"] = result["score"]
            merged[chunk_id]["graph_score"] = 0.0

        for result in graph_results:
            chunk_id = result["chunk_id"]
            if chunk_id in merged:
                merged[chunk_id]["graph_score"] = result["score"]
                merged[chunk_id]["entities"] = result.get("entities", [])
            else:
                merged[chunk_id] = result.copy()
                merged[chunk_id]["vector_score"] = 0.0
                merged[chunk_id]["graph_score"] = result["score"]

        ranked_results = []
        for fused in fused_results:
            chunk_id = fused["id"]
            if chunk_id not in merged:
                continue

            result = merged[chunk_id]
            result["rrf_score"] = fused["rrf_score"]
            result["score"] = fused["rrf_score"]
            result["strategy"] = "hybrid"
            result["fusion_method"] = "rrf"
            ranked_results.append(result)

        return ranked_results[:top_k]

    async def _community_retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Retrieve using Microsoft GraphRAG-style community routing."""
        try:
            routed = await self._community_graph_rag.query(query, top_k=top_k)
        except Exception as exc:
            logger.warning("Community retrieval failed: %s", exc)
            return await self._hybrid_retrieve(query, top_k)

        if routed.results:
            return routed.results[:top_k]

        logger.info("Community retrieval returned no results - falling back to hybrid")
        return await self._hybrid_retrieve(query, top_k)

    async def detect_communities(self) -> dict[int, list[str]]:
        """Detect graph communities and persist community nodes."""
        return await self._community_graph_rag.detect_communities()

    async def summarize_communities(self, llm: Any | None = None) -> dict[str, str]:
        """Summarize detected communities for global reasoning."""
        return await self._community_graph_rag.summarize_communities(llm=llm)

    async def build_community_hierarchy(self) -> dict[int, list[dict[str, Any]]]:
        """Build multi-scale community hierarchy."""
        return await self._community_graph_rag.build_hierarchy()

    async def route_query(self, query: str) -> str:
        """Route a query to the correct retrieval scale."""
        return await self._community_graph_rag.route_query(query)

    async def _fallback_text_search(
        self, query: str, top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Fallback text search when vector index is unavailable.

        Args:
            query: Query text
            top_k: Number of results

        Returns:
            List of text-matched results
        """
        results = []
        with self._get_session() as session:
            result = self._run_query(
                session,
                """
                MATCH (c:Chunk)<-[:CONTAINS]-(d:Document)
                WHERE toLower(coalesce(c.content, c.text)) CONTAINS toLower($query)
                RETURN c.id AS chunk_id,
                       coalesce(c.content, c.text) AS content,
                       c.position AS position,
                       d.id AS doc_id,
                       d.metadata AS metadata
                ORDER BY c.position
                LIMIT $top_k
                """,
                query=query,
                top_k=top_k,
            )

            for record in result:
                results.append(
                    {
                        "chunk_id": record["chunk_id"],
                        "content": record["content"],
                        "position": record["position"],
                        "doc_id": record["doc_id"],
                        "metadata": record["metadata"],
                        "score": 0.5,  # Fixed score for text match
                        "strategy": "text_fallback",
                    }
                )

        return results

    async def build_relationships(
        self,
        source_entity: str,
        target_entity: str,
        relationship_type: str,
        weight: float = 1.0,
    ) -> None:
        """
        Build explicit relationships between entities.

        Args:
            source_entity: Source entity name
            target_entity: Target entity name
            relationship_type: Type of relationship
            weight: Relationship weight/strength
        """
        with self._get_session() as session:
            self._run_query(
                session,
                """
                MATCH (s:Entity {name: $source})
                MATCH (t:Entity {name: $target})
                MERGE (s)-[r:RELATED_TO {type: $rel_type}]->(t)
                SET r.weight = $weight,
                    r.last_updated = datetime()
                """,
                source=source_entity,
                target=target_entity,
                rel_type=relationship_type,
                weight=weight,
            )

        logger.info(
            f"Created relationship: {source_entity} -[{relationship_type}]-> {target_entity}"
        )

    async def get_entity_context(
        self, entity_name: str, max_hops: int = 2
    ) -> Dict[str, Any]:
        """
        Get full context around an entity.

        Args:
            entity_name: Entity to explore
            max_hops: Maximum traversal depth

        Returns:
            Dict with entity info, neighbors, documents, and relationships
        """
        with self._get_session() as session:
            result = self._run_query(
                session,
                """
                MATCH (e:Entity {name: $name})
                OPTIONAL MATCH path = (e)-[*1..$max_hops]-(neighbor)
                WITH e,
                     collect(DISTINCT neighbor) AS neighbors,
                     collect(DISTINCT [type(r) for r in relationships(path)]) AS rel_types
                OPTIONAL MATCH (e)<-[:MENTIONS]-(c:Chunk)<-[:CONTAINS]-(d:Document)
                RETURN e.name AS name,
                       e.type AS type,
                       e.mention_count AS mentions,
                       neighbors[0..20] AS neighbors,
                       rel_types[0..20] AS relationships,
                       collect(DISTINCT d.id)[0..10] AS documents
                """,
                name=entity_name,
                max_hops=max_hops,
            )

            record = result[0] if result else None
            if record:
                return {
                    "entity": {
                        "name": record["name"],
                        "type": record["type"],
                        "mentions": record["mentions"],
                    },
                    "neighbors": [
                        n["name"] if hasattr(n, "name") else str(n)
                        for n in record["neighbors"]
                    ],
                    "relationships": record["relationships"],
                    "documents": record["documents"],
                }

        return {"entity": None, "neighbors": [], "relationships": [], "documents": []}

    async def close(self) -> None:
        """Close connections and cleanup."""
        # Connection is managed by the pool
        logger.info("Enhanced Graph RAG closed")
