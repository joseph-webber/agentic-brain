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

"""Fluent builder API for Agentic Brain.

Chainable, readable configuration for complex workflows.

Examples:
    # Simple query
    result = (
        AgenticBrain()
        .with_llm("ollama", "llama3.1:8b")
        .query("What is the status of project X?")
    )

    # Complex RAG with graph
    result = (
        AgenticBrain()
        .with_llm("openai", "gpt-4")
        .with_graph(neo4j_uri="bolt://localhost:7687")
        .with_rag(cache_ttl_hours=24)
        .ingest_documents(["deployment.md", "docs/"])
        .query("How do I deploy?")
    )

    # Multi-step workflow
    brain = (
        AgenticBrain()
        .with_llm("groq")  # Fast routing
        .with_graph()
        .with_rag()
    )
    result1 = brain.query("Q1")
    result2 = brain.query("Q2")
    metrics = brain.evaluate_recent_queries()
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from agentic_brain.graph import TopicHub
from agentic_brain.rag import RAGPipeline, RAGResult

logger = logging.getLogger(__name__)

__all__ = ["AgenticBrain"]


class AgenticBrain:
    """Fluent builder for Agentic Brain workflows.

    Build complex AI pipelines with readable, chainable methods.
    Every method returns self for fluent chaining.
    """

    def __init__(self) -> None:
        """Initialize empty builder."""
        self._llm_provider: Optional[str] = None
        self._llm_model: Optional[str] = None
        self._llm_base_url: Optional[str] = None
        self._llm_api_key: Optional[str] = None

        self._graph: Optional[TopicHub] = None
        self._graph_uri: Optional[str] = None
        self._graph_user: str = "neo4j"
        self._graph_password: Optional[str] = None

        self._rag: Optional[RAGPipeline] = None
        self._rag_cache_ttl: int = 4
        self._rag_embedding_provider: Optional[str] = None

        self._query_history: list[tuple[str, RAGResult]] = []
        self._max_history: int = 100

    # LLM Configuration
    def with_llm(
        self,
        provider: str = "ollama",
        model: str = "llama3.1:8b",
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> AgenticBrain:
        """Configure LLM for generation.

        Args:
            provider: "ollama", "openai", "groq", "anthropic", "azure", etc
            model: Model name (e.g., "gpt-4", "claude-opus")
            base_url: Optional custom base URL
            api_key: Optional API key (uses env vars if not provided)

        Returns:
            self for chaining
        """
        self._llm_provider = provider
        self._llm_model = model
        self._llm_base_url = base_url
        self._llm_api_key = api_key
        return self

    def with_llm_openai(self, model: str = "gpt-4") -> AgenticBrain:
        """Quick setup for OpenAI."""
        return self.with_llm("openai", model)

    def with_llm_groq(self, model: str = "mixtral-8x7b-32768") -> AgenticBrain:
        """Quick setup for Groq (fast & free!)."""
        return self.with_llm("groq", model)

    def with_llm_ollama(self, model: str = "llama3.1:8b") -> AgenticBrain:
        """Quick setup for local Ollama."""
        return self.with_llm("ollama", model)

    def with_llm_anthropic(self, model: str = "claude-opus") -> AgenticBrain:
        """Quick setup for Anthropic."""
        return self.with_llm("anthropic", model)

    # Graph Configuration
    def with_graph(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
    ) -> AgenticBrain:
        """Configure knowledge graph.

        Args:
            neo4j_uri: Neo4j connection URI (default: bolt://localhost:7687)
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password

        Returns:
            self for chaining
        """
        self._graph_uri = neo4j_uri or "bolt://localhost:7687"
        self._graph_user = neo4j_user
        self._graph_password = neo4j_password

        try:
            self._graph = TopicHub()
        except Exception as e:
            logger.warning(f"Failed to initialize graph: {e}")

        return self

    def without_graph(self) -> AgenticBrain:
        """Disable graph."""
        self._graph = None
        return self

    # RAG Configuration
    def with_rag(
        self,
        cache_ttl_hours: int = 4,
        embedding_provider: Optional[str] = None,
    ) -> AgenticBrain:
        """Configure RAG pipeline.

        Args:
            cache_ttl_hours: Cache time-to-live in hours
            embedding_provider: "mlx", "openai", "local", etc

        Returns:
            self for chaining
        """
        self._rag_cache_ttl = cache_ttl_hours
        self._rag_embedding_provider = embedding_provider

        try:
            self._rag = RAGPipeline(
                neo4j_uri=self._graph_uri,
                neo4j_user=self._graph_user,
                neo4j_password=self._graph_password,
                llm_provider=self._llm_provider or "ollama",
                llm_model=self._llm_model or "llama3.1:8b",
                llm_base_url=self._llm_base_url,
                cache_ttl_hours=cache_ttl_hours,
            )
        except Exception as e:
            logger.warning(f"Failed to initialize RAG: {e}")

        return self

    def without_rag(self) -> AgenticBrain:
        """Disable RAG."""
        self._rag = None
        return self

    # Document Management
    def ingest_documents(
        self, documents: list[str], extensions: Optional[list[str]] = None
    ) -> AgenticBrain:
        """Ingest documents for RAG.

        Args:
            documents: List of file paths or URLs
            extensions: Specific file extensions to process (e.g., [".md", ".txt"])

        Returns:
            self for chaining
        """
        if not self._rag:
            self.with_rag()

        if self._rag:
            for doc in documents:
                try:
                    if extensions:
                        # Filter by extension
                        if any(doc.endswith(ext) for ext in extensions):
                            self._rag.ingest_document(doc)
                    else:
                        self._rag.ingest_document(doc)
                except Exception as e:
                    logger.warning(f"Failed to ingest {doc}: {e}")

        return self

    def ingest_folder(self, folder_path: str, recursive: bool = True) -> AgenticBrain:
        """Ingest all documents from a folder.

        Args:
            folder_path: Path to folder
            recursive: Search subfolders (default True)

        Returns:
            self for chaining
        """
        from pathlib import Path

        folder = Path(folder_path)
        pattern = "**/*" if recursive else "*"

        docs = list(folder.glob(pattern))
        return self.ingest_documents([str(d) for d in docs if d.is_file()])

    # Graph Operations
    def add_entities(self, entities: list[str]) -> AgenticBrain:
        """Add entities to knowledge graph.

        Args:
            entities: List of entity names

        Returns:
            self for chaining
        """
        if not self._graph:
            self.with_graph()

        if self._graph:
            for entity in entities:
                try:
                    self._graph.create_topic(entity)
                except Exception as e:
                    logger.warning(f"Failed to create entity {entity}: {e}")

        return self

    def add_relationships(
        self, relationships: list[tuple[str, str, str]]
    ) -> AgenticBrain:
        """Add relationships to knowledge graph.

        Args:
            relationships: List of (source, relation, target) tuples

        Returns:
            self for chaining
        """
        if not self._graph:
            self.with_graph()

        if self._graph:
            for source, relation, target in relationships:
                try:
                    self._graph.link_topic(source, relation, target)
                except Exception as e:
                    logger.warning(f"Failed to link {source} -> {target}: {e}")

        return self

    # Query Operations
    def query(self, question: str) -> RAGResult:
        """Execute a query.

        Args:
            question: Your question or query

        Returns:
            RAGResult with answer and sources
        """
        if not self._rag:
            self.with_rag()

        result = self._rag.query(question) if self._rag else None

        if result:
            # Track in history
            self._query_history.append((question, result))
            if len(self._query_history) > self._max_history:
                self._query_history.pop(0)

        return result

    def search(
        self,
        query: str,
        num_results: int = 5,
        search_type: str = "hybrid",
    ) -> list[dict[str, Any]]:
        """Execute a search.

        Args:
            query: Search query
            num_results: Number of results
            search_type: "hybrid", "vector", or "keyword"

        Returns:
            List of search results
        """
        if not self._rag:
            self.with_rag()

        if not self._rag:
            return []

        try:
            if search_type == "hybrid":
                results = self._rag.hybrid_search(query, limit=num_results)
            elif search_type == "vector":
                results = self._rag.vector_search(query, limit=num_results)
            elif search_type == "keyword":
                results = self._rag.keyword_search(query, limit=num_results)
            else:
                raise ValueError(f"Unknown search_type: {search_type}")

            return [
                {
                    "content": r.content[:500],
                    "source": r.source,
                    "score": r.score,
                }
                for r in results
            ]

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    # History & Analytics
    def get_query_history(self, limit: int = 10) -> list[tuple[str, str]]:
        """Get recent query history.

        Args:
            limit: Number of queries to return

        Returns:
            List of (question, answer) tuples
        """
        return [(q, r.answer) for q, r in self._query_history[-limit:]]

    def evaluate_recent_queries(self) -> dict[str, Any]:
        """Evaluate recent queries.

        Returns:
            Dictionary with evaluation metrics
        """
        if not self._query_history:
            return {"error": "No queries to evaluate"}

        results = [r for _, r in self._query_history]

        return {
            "total_queries": len(results),
            "avg_confidence": sum(r.confidence for r in results) / len(results),
            "with_sources": sum(1 for r in results if r.has_sources),
            "avg_answer_length": sum(len(r.answer) for r in results) / len(results),
        }

    def clear_history(self) -> AgenticBrain:
        """Clear query history.

        Returns:
            self for chaining
        """
        self._query_history.clear()
        return self

    # Configuration Summary
    def describe(self) -> str:
        """Get human-readable configuration summary.

        Returns:
            Description string
        """
        parts = ["AgenticBrain Configuration:"]

        if self._llm_provider:
            parts.append(f"  LLM: {self._llm_provider}/{self._llm_model}")

        if self._graph:
            parts.append(f"  Graph: Neo4j ({self._graph_uri})")

        if self._rag:
            parts.append(f"  RAG: Enabled (cache TTL: {self._rag_cache_ttl}h)")

        if self._query_history:
            parts.append(f"  History: {len(self._query_history)} queries")

        return "\n".join(parts)

    def __repr__(self) -> str:
        """Return configuration summary."""
        return self.describe()
