# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

from agentic_brain.core.neo4j_pool import (
    configure_pool as configure_neo4j_pool,
)
from agentic_brain.core.neo4j_pool import (
    get_driver as get_shared_neo4j_driver,
)
from agentic_brain.core.exceptions import GraphConnectionError

from .embeddings import EmbeddingProvider, get_embeddings
from .exceptions import EmbeddingError, RetrievalError

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata."""

    content: str
    source: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def confidence(self: "RetrievedChunk") -> str:
        """Human-readable confidence level."""
        if self.score >= 0.8:
            return "high"
        elif self.score >= 0.5:
            return "medium"
        elif self.score >= 0.3:
            return "low"
        return "uncertain"

    def to_context(self: "RetrievedChunk") -> str:
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
        self: "Retriever",
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        sources: Optional[list[str]] = None,
        document_store: Optional[Any] = None,
    ) -> None:
        """Initialize a retriever for Neo4j, files, or in-memory document stores.

        Args:
            neo4j_uri: Neo4j connection URI. Defaults to ``NEO4J_URI`` env var.
            neo4j_user: Username used when authenticating with Neo4j.
            neo4j_password: Neo4j password. Defaults to ``NEO4J_PASSWORD`` env var.
            embedding_provider: Optional embedding provider for similarity scoring.
            sources: Default Neo4j labels to query during retrieval.
            document_store: Optional document-store object exposing ``list``/``search``.

        Returns:
            None: Configures the retriever instance in-place.

        Raises:
            ValueError: If incompatible constructor argument combinations are passed.

        Example:
            >>> retriever = Retriever(sources=["Document"])
            >>> retriever.sources
            ['Document']
        """
        if neo4j_uri is not None and not isinstance(neo4j_uri, str):
            document_store = neo4j_uri
            neo4j_uri = None

        if embedding_provider is None and hasattr(neo4j_user, "embed"):
            embedding_provider = neo4j_user  # type: ignore[assignment]
            neo4j_user = "neo4j"
            neo4j_password = None

        self.document_store = document_store
        self.neo4j_uri = neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = neo4j_user
        # SECURITY: No default password - must be explicitly configured
        self.neo4j_password = neo4j_password or os.getenv("NEO4J_PASSWORD")
        self.embeddings = embedding_provider or get_embeddings()
        self.sources = sources or ["Document", "Memory", "Knowledge"]
        self._driver = None
        self._using_shared_driver = False

    def _get_driver(self: "Retriever") -> Any:
        """Get Neo4j driver (lazy initialization)."""
        if self._driver is None:
            try:
                configure_neo4j_pool(
                    uri=self.neo4j_uri,
                    user=self.neo4j_user,
                    password=self.neo4j_password,
                )
                self._driver = get_shared_neo4j_driver()
                self._using_shared_driver = True
            except ImportError as exc:
                raise ImportError("neo4j package required: pip install neo4j") from exc
            except Exception as exc:
                logger.exception("Failed to initialize Neo4j driver")
                raise GraphConnectionError(
                    "Neo4j",
                    self.neo4j_uri,
                    operation="initialize driver",
                    original_error=exc,
                ) from exc
        return self._driver

    def _cosine_similarity(self: "Retriever", a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def search_neo4j(
        self: "Retriever",
        query: str,
        k: int = 5,
        labels: Optional[list[str]] = None,
        min_score: float = 0.3,
    ) -> list[RetrievedChunk]:
        """Search Neo4j using vector similarity."""
        labels = labels or self.sources
        if not labels:
            logger.info("Neo4j retrieval skipped: no labels configured")
            return []

        try:
            query_embedding = self.embeddings.embed(query)
        except EmbeddingError as exc:
            logger.exception("Failed to embed query for retrieval")
            raise RetrievalError(
                "Failed to embed query for retrieval",
                context={"query": query, "labels": labels},
            ) from exc

        driver = self._get_driver()
        chunks: list[RetrievedChunk] = []

        try:
            session_obj = driver.session()
        except Exception as exc:
            logger.exception("Failed to open Neo4j session")
            raise GraphConnectionError(
                "Neo4j",
                self.neo4j_uri,
                operation="open session",
                original_error=exc,
            ) from exc

        try:
            with session_obj as session:
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
                        logger.debug(
                            "Vector index search failed for %s, falling back: %s",
                            label,
                            e,
                        )

                        try:
                            result = session.run(
                                f"""
                                MATCH (n:{label})
                                WHERE n.embedding IS NOT NULL
                                RETURN n, n.embedding as embedding
                                LIMIT 100
                            """
                            )
                        except Exception as inner_exc:
                            logger.debug(
                                "Neo4j fallback query failed for %s: %s",
                                label,
                                inner_exc,
                            )
                            raise GraphConnectionError(
                                "Neo4j",
                                self.neo4j_uri,
                                operation="fallback query",
                                original_error=inner_exc,
                            ) from inner_exc

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
        except (OSError, TimeoutError) as exc:
            logger.exception("Neo4j retrieval failed")
            raise RetrievalError(
                "Neo4j retrieval failed",
                context={"query": query, "labels": labels, "k": k},
            ) from exc

        chunks.sort(key=lambda x: x.score, reverse=True)
        if not chunks:
            logger.info("No Neo4j results for query=%r labels=%s", query, labels)
        return chunks[:k]

    def search_documents(self: "Retriever", query: str, k: int = 5) -> list[RetrievedChunk]:
        """Search an attached document store using embedding similarity.

        Args:
            query: Query text to embed and compare against documents.
            k: Maximum number of results to return.

        Returns:
            list[RetrievedChunk]: Top matching chunks sorted by descending score.

        Raises:
            RuntimeError: If the embedding provider fails unexpectedly.

        Example:
            >>> retriever = Retriever(document_store=None)
            >>> retriever.search_documents("deployment", k=2)
            []
        """
        if self.document_store is None:
            return []

        try:
            docs = self.document_store.list(limit=1000)
        except Exception as exc:
            logger.debug("Document store list failed: %s", exc)
            try:
                docs = self.document_store.search(query, top_k=k)
            except Exception as inner_exc:
                logger.debug("Document store search failed: %s", inner_exc)
                docs = []

        try:
            query_embedding = self.embeddings.embed(query)
        except EmbeddingError as exc:
            logger.exception("Failed to embed query for document store retrieval")
            return []

        chunks: list[RetrievedChunk] = []
        for doc in docs:
            try:
                doc_embedding = self.embeddings.embed(doc.content)
                score = self._cosine_similarity(query_embedding, doc_embedding)
                chunks.append(
                    RetrievedChunk(
                        content=doc.content,
                        source=doc.metadata.get("source", "Document"),
                        score=score,
                        metadata=dict(doc.metadata),
                    )
                )
            except Exception as e:
                logger.debug(f"Skipping document during retrieval: {e}")

        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks[:k]

    def search_files(
        self: "Retriever",
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

        try:
            query_embedding = self.embeddings.embed(query)
        except EmbeddingError as exc:
            logger.exception("Failed to embed query for file search")
            return []

        chunks: list[RetrievedChunk] = []
        dir_path = Path(directory)

        if not dir_path.exists():
            logger.warning("Search directory not found: %s", dir_path)
            return []

        for ext in extensions:
            try:
                candidates = list(dir_path.rglob(f"*{ext}"))
            except (OSError, PermissionError) as exc:
                logger.debug("Directory traversal failed for %s: %s", dir_path, exc)
                continue

            for file_path in candidates:
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
                except (
                    OSError,
                    FileNotFoundError,
                    PermissionError,
                    UnicodeError,
                    ValueError,
                    EmbeddingError,
                ) as e:
                    # IOError: file read error
                    # FileNotFoundError: file disappeared
                    # PermissionError: no read permission
                    # ValueError: embedding provider error
                    logger.debug(f"Skipping file {file_path}: {e}")
                    continue

        chunks.sort(key=lambda x: x.score, reverse=True)
        return chunks[:k]

    def search(
        self: "Retriever", query: str, k: int = 5, sources: Optional[list[str]] = None, **kwargs: Any
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
        if self.document_store is not None:
            return self.search_documents(query, k=k)

        if self.document_store is not None:
            return self.search_documents(query, k=k)

        all_chunks: list[RetrievedChunk] = []

        # Neo4j search
        try:
            neo4j_chunks = self.search_neo4j(query, k=k, labels=sources)
            all_chunks.extend(neo4j_chunks)
        except RetrievalError as e:
            # Connection issues / timeouts / embedding failures
            logger.warning("Neo4j retrieval error: %s", e)
        except Exception as e:
            # Neo4j unavailable or authentication failure, skip
            logger.debug(f"Neo4j search unavailable: {e}")

        # Sort all by score
        all_chunks.sort(key=lambda x: x.score, reverse=True)
        if not all_chunks:
            logger.info("No retrieval results for query=%r", query)
        return all_chunks[:k]

    def retrieve(self: "Retriever", query: str, top_k: int = 5, **kwargs: Any) -> list[RetrievedChunk]:
        """Compatibility alias that forwards to :meth:`search`.

        Args:
            query: Query text to retrieve against.
            top_k: Maximum number of results to return.
            **kwargs: Additional keyword arguments passed through to ``search``.

        Returns:
            list[RetrievedChunk]: Ranked retrieval results.

        Raises:
            RuntimeError: Propagates retrieval errors from ``search``.

        Example:
            >>> retriever = Retriever(document_store=None)
            >>> retriever.retrieve("hello", top_k=1)
            []
        """
        return self.search(query, k=top_k, **kwargs)

    def close(self: "Retriever") -> None:
        """Close any owned Neo4j driver and reset connection state.

        Returns:
            None: Driver state is cleared on the instance.

        Raises:
            RuntimeError: If closing the owned driver fails.

        Example:
            >>> retriever = Retriever(document_store=None)
            >>> retriever.close()
        """
        if self._driver and not self._using_shared_driver:
            self._driver.close()
        self._driver = None
        self._using_shared_driver = False
