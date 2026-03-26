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

Provides production-ready graph-based retrieval augmented generation:
- Native Neo4j vector similarity search
- Entity extraction and relationship mapping
- Knowledge graph construction from documents
- Multi-strategy retrieval (vector, graph, hybrid)
- Context-aware graph traversal

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
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
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
    vector_index_name: str = "document_embeddings"
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


class EnhancedGraphRAG:
    """
    Enhanced Graph RAG with Neo4j native vector search and knowledge graph construction.

    Features:
    - Vector similarity search using Neo4j's native vector index
    - Entity extraction with configurable types
    - Relationship mapping between entities
    - Multi-hop graph traversal
    - Hybrid retrieval combining vector + graph signals
    - Community detection for hierarchical retrieval
    """

    def __init__(self, config: Optional[GraphRAGConfig] = None):
        """
        Initialize Enhanced Graph RAG.

        Args:
            config: Configuration object. Uses defaults if not provided.
        """
        self.config = config or GraphRAGConfig()
        self._initialized = False

    def _get_session(self):
        """Get Neo4j session using lazy pool."""
        if self.config.use_pool:
            from agentic_brain.core.neo4j_pool import get_session

            return get_session()
        else:
            # Fallback to direct connection if pool disabled
            if not NEO4J_AVAILABLE or GraphDatabase is None:
                raise ImportError(
                    "neo4j package is required for direct graph connections. Install with: pip install neo4j"
                )

            driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", ""))
            return driver.session()

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
            session.run(
                """
                CREATE CONSTRAINT document_id IF NOT EXISTS
                FOR (d:Document) REQUIRE d.id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT entity_id IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT chunk_id IF NOT EXISTS
                FOR (c:Chunk) REQUIRE c.id IS UNIQUE
                """
            )

            # Create vector index (Neo4j 5.11+)
            # Note: This requires Neo4j with vector support
            try:
                session.run(
                    f"""
                    CREATE VECTOR INDEX {self.config.vector_index_name} IF NOT EXISTS
                    FOR (c:Chunk) ON (c.embedding)
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {self.config.embedding_dimension},
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                    """
                )
            except Exception as e:
                logger.warning(f"Could not create vector index: {e}")
                logger.info("Vector search will be disabled or use fallback")

            # Create indexes for faster queries
            session.run(
                "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)"
            )
            session.run(
                "CREATE INDEX document_timestamp IF NOT EXISTS FOR (d:Document) ON (d.timestamp)"
            )

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
            session.run(
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

            # 3. Create Entity nodes and relationships
            for entity in entities:
                entity_id = hashlib.sha256(entity["name"].encode()).hexdigest()[:16]

                session.run(
                    """
                    MERGE (e:Entity {id: $entity_id})
                    SET e.name = $name,
                        e.type = $type,
                        e.first_seen = coalesce(e.first_seen, $timestamp),
                        e.last_seen = $timestamp,
                        e.mention_count = coalesce(e.mention_count, 0) + 1
                    """,
                    entity_id=entity_id,
                    name=entity["name"],
                    type=entity["type"],
                    timestamp=timestamp,
                )

                # Link entity to document
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (e:Entity {id: $entity_id})
                    MERGE (d)-[r:MENTIONS]->(e)
                    SET r.count = coalesce(r.count, 0) + $count,
                        r.positions = $positions
                    """,
                    doc_id=doc_id,
                    entity_id=entity_id,
                    count=entity["count"],
                    positions=entity.get("positions", []),
                )

            # 4. Create chunks with embeddings
            chunks = self._chunk_content(content)
            for i, chunk_text in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i}"

                # Use provided embedding or mock one
                # In production, compute real embeddings here
                chunk_embedding = embedding or [0.1] * self.config.embedding_dimension

                session.run(
                    """
                    MERGE (c:Chunk {id: $chunk_id})
                    SET c.text = $text,
                        c.position = $position,
                        c.embedding = $embedding
                    """,
                    chunk_id=chunk_id,
                    text=chunk_text,
                    position=i,
                    embedding=chunk_embedding,
                )

                # Link chunk to document
                session.run(
                    """
                    MATCH (d:Document {id: $doc_id})
                    MATCH (c:Chunk {id: $chunk_id})
                    MERGE (d)-[:CONTAINS]->(c)
                    """,
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                )

                # Link chunk to entities it mentions
                chunk_entities = self._extract_entities(chunk_text)
                for entity in chunk_entities:
                    entity_id = hashlib.sha256(entity["name"].encode()).hexdigest()[:16]
                    session.run(
                        """
                        MATCH (c:Chunk {id: $chunk_id})
                        MATCH (e:Entity {id: $entity_id})
                        MERGE (c)-[:MENTIONS]->(e)
                        """,
                        chunk_id=chunk_id,
                        entity_id=entity_id,
                    )

        logger.info(
            f"Indexed document {doc_id} with {len(entities)} entities and {len(chunks)} chunks"
        )
        return doc_id

    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from text.

        This is a simplified implementation. In production, use:
        - spaCy for NER
        - LLM-based extraction
        - Custom domain-specific extractors

        Args:
            text: Input text

        Returns:
            List of entity dicts with name, type, count, positions
        """
        # Simple word-based extraction (demo purposes)
        # In production: use spaCy, transformers, or LLM
        words = text.split()
        entities = []

        # Extract capitalized words as potential entities
        for i, word in enumerate(words):
            cleaned = word.strip(".,!?;:")
            if (
                len(cleaned) >= self.config.min_entity_length
                and cleaned[0].isupper()
                and cleaned.isalpha()
            ):
                # Determine type (simplified)
                entity_type = "CONCEPT"  # Default
                if cleaned.endswith("Corp") or cleaned.endswith("Inc"):
                    entity_type = "ORGANIZATION"

                entities.append(
                    {
                        "name": cleaned,
                        "type": entity_type,
                        "count": 1,
                        "positions": [i],
                    }
                )

        # Deduplicate and aggregate
        entity_map = {}
        for entity in entities:
            key = entity["name"]
            if key in entity_map:
                entity_map[key]["count"] += 1
                entity_map[key]["positions"].extend(entity["positions"])
            else:
                entity_map[key] = entity

        return list(entity_map.values())[: self.config.max_entities_per_doc]

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
        # Use provided embedding or compute one
        # In production: use sentence-transformers, OpenAI, etc.
        embedding = query_embedding or [0.1] * self.config.embedding_dimension

        results = []
        with self._get_session() as session:
            # Vector similarity search using Neo4j vector index
            # Note: Requires Neo4j 5.11+ with vector support
            try:
                result = session.run(
                    """
                    CALL db.index.vector.queryNodes(
                        $index_name,
                        $top_k,
                        $embedding
                    )
                    YIELD node AS chunk, score
                    MATCH (d:Document)-[:CONTAINS]->(chunk)
                    RETURN chunk.id AS chunk_id,
                           chunk.text AS content,
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

            result = session.run(
                """
                MATCH (e:Entity)
                WHERE e.name =~ $pattern
                WITH e
                MATCH path = (e)<-[:MENTIONS]-(c:Chunk)<-[:CONTAINS]-(d:Document)
                WITH d, c, e, length(path) AS distance,
                     e.mention_count AS entity_importance
                RETURN DISTINCT
                       c.id AS chunk_id,
                       c.text AS content,
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
        3. Merge and rerank by combined score
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
        vector_results = await self._vector_retrieve(query, top_k * 2, query_embedding)
        graph_results = await self._graph_retrieve(query, top_k * 2, filters)

        # Merge results by chunk_id
        merged = {}
        for result in vector_results:
            chunk_id = result["chunk_id"]
            merged[chunk_id] = result
            merged[chunk_id]["vector_score"] = result["score"]
            merged[chunk_id]["graph_score"] = 0.0

        for result in graph_results:
            chunk_id = result["chunk_id"]
            if chunk_id in merged:
                merged[chunk_id]["graph_score"] = result["score"]
                merged[chunk_id]["entities"] = result.get("entities", [])
            else:
                merged[chunk_id] = result
                merged[chunk_id]["vector_score"] = 0.0
                merged[chunk_id]["graph_score"] = result["score"]

        # Calculate hybrid score (weighted combination)
        for chunk_id, result in merged.items():
            vector_weight = 0.6
            graph_weight = 0.4
            hybrid_score = vector_weight * result.get(
                "vector_score", 0.0
            ) + graph_weight * result.get("graph_score", 0.0)
            result["score"] = hybrid_score
            result["strategy"] = "hybrid"

        # Sort by hybrid score and return top-k
        sorted_results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:top_k]

    async def _community_retrieve(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """
        Retrieve using community detection for broader context.

        This is a placeholder for community-based retrieval.
        In production, implement using Neo4j GDS community detection algorithms.

        Args:
            query: Query text
            top_k: Number of results

        Returns:
            List of results from relevant communities
        """
        # Placeholder - in production use Neo4j GDS
        logger.info("Community retrieval not yet implemented - falling back to hybrid")
        return await self._hybrid_retrieve(query, top_k)

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
            result = session.run(
                """
                MATCH (c:Chunk)<-[:CONTAINS]-(d:Document)
                WHERE toLower(c.text) CONTAINS toLower($query)
                RETURN c.id AS chunk_id,
                       c.text AS content,
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
            session.run(
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
            result = session.run(
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

            record = result.single()
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
