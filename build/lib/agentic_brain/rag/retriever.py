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
Retriever - Fetch relevant documents for RAG.

Supports:
- Neo4j vector search
- File-based search
- Hybrid search (BM25 + vector)

For advanced retrieval (cross-encoder reranking, multi-hop reasoning,
query expansion), see: https://github.com/joseph-webber/brain-core
"""

import logging
import math
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from .embeddings import EmbeddingProvider, get_embeddings

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata."""

    content: str
    source: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def confidence(self) -> str:
        """Human-readable confidence level."""
        if self.score >= 0.8:
            return "high"
        elif self.score >= 0.5:
            return "medium"
        elif self.score >= 0.3:
            return "low"
        return "uncertain"

    def to_context(self) -> str:
        """Format for LLM context."""
        return f"[Source: {self.source}]\n{self.content}"


class Retriever:
    """
    Multi-source document retriever.

    Usage:
        retriever = Retriever(neo4j_uri="bolt://localhost:7687")
        chunks = retriever.search("How do I deploy?", k=5)

        for chunk in chunks:
            print(f"{chunk.source}: {chunk.score:.2f}")
            print(chunk.content[:100])
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        sources: Optional[list[str]] = None,
    ):
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user
        # SECURITY: No default password - must be explicitly configured
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
        if not self.neo4j_password:
            raise ValueError(
                "NEO4J_PASSWORD must be set via environment variable or constructor. "
                "Never use default passwords in production."
            )
        self.embeddings = embedding_provider or get_embeddings()
        self.sources = sources or ["Document", "Memory", "Knowledge"]
        self._driver = None

    def _get_driver(self):
        """Get Neo4j driver (lazy initialization)."""
        if self._driver is None:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
                )
            except ImportError:
                raise ImportError("neo4j package required: pip install neo4j")
        return self._driver

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search_neo4j(
        self,
        query: str,
        k: int = 5,
        labels: Optional[list[str]] = None,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]:
        """
        Search Neo4j using vector similarity.

        Args:
            query: Search query
            k: Number of results
            labels: Node labels to search (default: all sources)
            min_score: Minimum similarity score

        Returns:
            List of RetrievedChunk objects
        """
        labels = labels or self.sources
        query_embedding = self.embeddings.embed(query)

        driver = self._get_driver()
        chunks = []

        with driver.session() as session:
            for label in labels:
                # Try vector index search first
                try:
                    result = session.run(
                        f"""
                        CALL db.index.vector.queryNodes(
                            '{label.lower()}_embedding_index',
                            $k,
                            $embedding
                        ) YIELD node, score
                        WHERE score >= $min_score
                        RETURN node, score, labels(node) as labels
                        ORDER BY score DESC
                        LIMIT $k
                    """,
                        embedding=query_embedding,
                        k=k,
                        min_score=min_score,
                    )

                    for record in result:
                        node = record["node"]
                        chunks.append(
                            RetrievedChunk(
                                content=node.get("content", node.get("text", "")),
                                source=label,
                                score=record["score"],
                                metadata=dict(node),
                            )
                        )
                except (RuntimeError, OSError, KeyError, AttributeError) as e:
                    # RuntimeError: Neo4j query failed
                    # OSError: network/connection error
                    # KeyError: missing expected field
                    # AttributeError: missing property
                    logger.debug(
                        f"Vector index search failed for {label}, falling back: {e}"
                    )
                    # Fallback: get all nodes and compute similarity locally
                    result = session.run(
                        f"""
                        MATCH (n:{label})
                        WHERE n.embedding IS NOT NULL
                        RETURN n, n.embedding as embedding
                        LIMIT 100
                    """
                    )

                    for record in result:
                        node = record["n"]
                        embedding = record["embedding"]
                        if embedding:
                            score = self._cosine_similarity(query_embedding, embedding)
                            if score >= min_score:
                                chunks.append(
                                    RetrievedChunk(
                                        content=node.get(
                                            "content", node.get("text", "")
                                        ),
                                        source=label,
                                        score=score,
                                        metadata=dict(node),
                                    )
                                )

        # Sort by score and limit
        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks[:k]

    def search_files(
        self,
        query: str,
        directory: str,
        k: int = 5,
        extensions: Optional[list[str]] = None,
    ) -> list[RetrievedChunk]:
        """
        Search local files using embeddings.

        Args:
            query: Search query
            directory: Directory to search
            k: Number of results
            extensions: File extensions to include (default: .txt, .md, .py)

        Returns:
            List of RetrievedChunk objects
        """
        from pathlib import Path

        extensions = extensions or [".txt", ".md", ".py", ".json"]
        query_embedding = self.embeddings.embed(query)

        chunks = []
        dir_path = Path(directory)

        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                try:
                    content = file_path.read_text()[:2000]  # First 2000 chars
                    file_embedding = self.embeddings.embed(content)
                    score = self._cosine_similarity(query_embedding, file_embedding)

                    chunks.append(
                        RetrievedChunk(
                            content=content,
                            source=str(file_path),
                            score=score,
                            metadata={"path": str(file_path), "extension": ext},
                        )
                    )
                except (OSError, FileNotFoundError, PermissionError, ValueError) as e:
                    # IOError: file read error
                    # FileNotFoundError: file disappeared
                    # PermissionError: no read permission
                    # ValueError: embedding provider error
                    logger.debug(f"Skipping file {file_path}: {e}")
                    continue

        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks[:k]

    def search(
        self, query: str, k: int = 5, sources: Optional[list[str]] = None, **kwargs
    ) -> list[RetrievedChunk]:
        """
        Search across all configured sources.

        Args:
            query: Search query
            k: Number of results per source
            sources: Override default sources

        Returns:
            Combined and ranked results
        """
        all_chunks = []

        # Neo4j search
        try:
            neo4j_chunks = self.search_neo4j(query, k=k, labels=sources)
            all_chunks.extend(neo4j_chunks)
        except (OSError, RuntimeError, ConnectionError, TimeoutError) as e:
            # OSError/ConnectionError: network error
            # RuntimeError: Neo4j driver error
            # TimeoutError: query timeout
            # Neo4j not available, skip silently
            logger.debug(f"Neo4j search unavailable: {e}")
            pass

        # Sort all by score
        all_chunks.sort(key=lambda x: x.score, reverse=True)
        return all_chunks[:k]

    def close(self):
        """Close Neo4j connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
