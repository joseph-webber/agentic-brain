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
LlamaIndex Compatibility Layer for Agentic Brain GraphRAG.

This module provides LlamaIndex-compatible interfaces for users migrating
from or integrating with LlamaIndex. It wraps Agentic Brain's native RAG
components with LlamaIndex-style APIs.

Supported LlamaIndex patterns:
- QueryEngine: query() returns Response with source_nodes
- BaseRetriever: retrieve() returns list of NodeWithScore
- BaseIndex: from_documents() / as_query_engine() / as_retriever()
- ResponseSynthesizer: synthesize() combines context + query

Usage (Migration from LlamaIndex):
    # Before (LlamaIndex)
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents)
    query_engine = index.as_query_engine()
    response = query_engine.query("What is the main topic?")

    # After (Agentic Brain with LlamaIndex compat)
    from agentic_brain.rag.llamaindex_compat import (
        AgenticIndex,
        SimpleDirectoryReader,
    )
    documents = SimpleDirectoryReader("data").load_data()
    index = AgenticIndex.from_documents(documents)
    query_engine = index.as_query_engine()
    response = query_engine.query("What is the main topic?")

The key differences:
- Uses Agentic Brain's GraphRAG for enhanced retrieval
- Supports Neo4j knowledge graphs out of the box
- Hardware-accelerated embeddings (MLX/CUDA/ROCm)
- Community-aware retrieval strategies
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from .embeddings import EmbeddingProvider, get_embeddings
from .graph_rag import GraphRAG, GraphRAGConfig, SearchStrategy
from .pipeline import RAGPipeline, RAGResult
from .retriever import RetrievedChunk, Retriever
from .store import Document, DocumentStore, InMemoryDocumentStore

logger = logging.getLogger(__name__)


# ============================================================================
# Core Data Structures (LlamaIndex-compatible)
# ============================================================================


@dataclass
class TextNode:
    """
    LlamaIndex-compatible TextNode representation.

    Maps to LlamaIndex TextNode/Document for seamless migration.

    Attributes:
        text: The node content
        node_id: Unique identifier (auto-generated if not provided)
        metadata: Arbitrary metadata dictionary
        embedding: Optional pre-computed embedding vector
        relationships: Node relationships (parent/child/etc)
    """

    text: str
    node_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    relationships: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.node_id is None:
            import hashlib

            self.node_id = hashlib.sha256(self.text.encode()).hexdigest()[:16]

    @property
    def id_(self) -> str:
        """LlamaIndex compatibility - id_ property."""
        return self.node_id or ""

    @property
    def content(self) -> str:
        """Alias for text content."""
        return self.text

    def get_content(self, metadata_mode: str = "none") -> str:
        """Get content with optional metadata inclusion."""
        if metadata_mode == "none":
            return self.text
        elif metadata_mode == "embed":
            meta_str = "\n".join(f"{k}: {v}" for k, v in self.metadata.items())
            return f"{meta_str}\n\n{self.text}" if meta_str else self.text
        return self.text

    def to_agentic_document(self) -> Document:
        """Convert to Agentic Brain Document."""
        return Document(
            id=self.node_id or "",
            content=self.text,
            metadata=self.metadata,
        )

    @classmethod
    def from_agentic_document(cls, doc: Document) -> "TextNode":
        """Create TextNode from Agentic Brain Document."""
        return cls(
            text=doc.content,
            node_id=doc.id,
            metadata=doc.metadata,
        )

    @classmethod
    def from_retrieved_chunk(cls, chunk: RetrievedChunk) -> "TextNode":
        """Create TextNode from RetrievedChunk."""
        return cls(
            text=chunk.content,
            node_id=chunk.metadata.get("id", chunk.source),
            metadata={**chunk.metadata, "source": chunk.source, "score": chunk.score},
        )


# LlamaIndex compatibility aliases
LIDocument = TextNode


@dataclass
class NodeWithScore:
    """
    LlamaIndex-compatible NodeWithScore.

    Wraps a node with its retrieval score for ranking.
    """

    node: TextNode
    score: float = 0.0

    @classmethod
    def from_retrieved_chunk(cls, chunk: RetrievedChunk) -> "NodeWithScore":
        """Create from Agentic Brain RetrievedChunk."""
        return cls(
            node=TextNode.from_retrieved_chunk(chunk),
            score=chunk.score,
        )

    @property
    def text(self) -> str:
        """Quick access to node text."""
        return self.node.text

    def get_content(self) -> str:
        """Get node content."""
        return self.node.get_content()


@dataclass
class Response:
    """
    LlamaIndex-compatible Response object.

    Returned by QueryEngine.query() with full source attribution.
    """

    response: str
    source_nodes: List[NodeWithScore] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.response

    @classmethod
    def from_rag_result(cls, result: RAGResult) -> "Response":
        """Create from Agentic Brain RAGResult."""
        source_nodes = [
            NodeWithScore.from_retrieved_chunk(chunk) for chunk in result.sources
        ]
        return cls(
            response=result.answer,
            source_nodes=source_nodes,
            metadata={
                "query": result.query,
                "confidence": result.confidence,
                "model": result.model,
                "cached": result.cached,
                "generation_time_ms": result.generation_time_ms,
            },
        )

    def get_formatted_sources(self, length: int = 100) -> str:
        """Get formatted source information."""
        sources = []
        for i, node in enumerate(self.source_nodes, 1):
            text = node.text[:length] + "..." if len(node.text) > length else node.text
            sources.append(f"Source {i} (score: {node.score:.3f}):\n{text}")
        return "\n\n".join(sources)


# ============================================================================
# Retriever Interfaces (LlamaIndex-compatible)
# ============================================================================


class BaseRetriever(ABC):
    """
    Abstract base retriever matching LlamaIndex BaseRetriever.

    Subclasses must implement _retrieve() method.
    """

    @abstractmethod
    def _retrieve(self, query: str, **kwargs: Any) -> List[NodeWithScore]:
        """Internal retrieve implementation."""
        pass

    def retrieve(self, query: str, **kwargs: Any) -> List[NodeWithScore]:
        """
        Retrieve relevant nodes for a query.

        Args:
            query: The query string
            **kwargs: Additional retrieval parameters

        Returns:
            List of NodeWithScore objects ranked by relevance
        """
        return self._retrieve(query, **kwargs)

    async def aretrieve(self, query: str, **kwargs: Any) -> List[NodeWithScore]:
        """Async retrieve (default: runs sync version)."""
        return self._retrieve(query, **kwargs)


class AgenticRetriever(BaseRetriever):
    """
    LlamaIndex-compatible retriever wrapping Agentic Brain Retriever.

    Provides drop-in replacement for LlamaIndex retrievers while using
    Agentic Brain's advanced retrieval capabilities.

    Example:
        retriever = AgenticRetriever(
            neo4j_uri="bolt://localhost:7687",
            similarity_top_k=5,
        )
        nodes = retriever.retrieve("What is GraphRAG?")
    """

    def __init__(
        self,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
        similarity_top_k: int = 5,
        sources: Optional[List[str]] = None,
        document_store: Optional[DocumentStore] = None,
    ):
        """
        Initialize the retriever.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            embedding_provider: Custom embedding provider
            similarity_top_k: Number of results to return
            sources: Neo4j node labels to search
            document_store: Optional document store for non-graph retrieval
        """
        self._retriever = Retriever(
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            embedding_provider=embedding_provider,
            sources=sources,
            document_store=document_store,
        )
        self.similarity_top_k = similarity_top_k

    def _retrieve(self, query: str, **kwargs: Any) -> List[NodeWithScore]:
        """Retrieve nodes using Agentic Brain Retriever."""
        top_k = kwargs.get("top_k", self.similarity_top_k)
        chunks = self._retriever.search(query, k=top_k)
        return [NodeWithScore.from_retrieved_chunk(chunk) for chunk in chunks]


class LlamaIndexGraphRAGRetriever(BaseRetriever):
    """
    LlamaIndex-compatible retriever using Agentic Brain GraphRAG.

    Provides knowledge graph-enhanced retrieval with community detection,
    multi-hop reasoning, and hybrid search strategies.

    Example:
        retriever = LlamaIndexGraphRAGRetriever(
            config=GraphRAGConfig(enable_communities=True),
            strategy=SearchStrategy.HYBRID,
        )
        nodes = retriever.retrieve("Explain the architecture")
    """

    def __init__(
        self,
        config: Optional[GraphRAGConfig] = None,
        strategy: SearchStrategy = SearchStrategy.HYBRID,
        similarity_top_k: int = 10,
    ):
        self._graph_rag = GraphRAG(config)
        self.strategy = strategy
        self.similarity_top_k = similarity_top_k

    def _retrieve(self, query: str, **kwargs: Any) -> List[NodeWithScore]:
        """Retrieve using GraphRAG (sync wrapper)."""
        import asyncio

        top_k = kwargs.get("top_k", self.similarity_top_k)
        strategy = kwargs.get("strategy", self.strategy)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self._graph_rag.search(query, strategy=strategy, top_k=top_k),
                )
                results = future.result()
        else:
            results = loop.run_until_complete(
                self._graph_rag.search(query, strategy=strategy, top_k=top_k)
            )

        nodes = []
        for result in results:
            text = result.get("content", result.get("description", ""))
            node = TextNode(
                text=text,
                node_id=result.get("entity_id"),
                metadata={
                    k: v
                    for k, v in result.items()
                    if k not in ("content", "description", "entity_id", "score")
                },
            )
            nodes.append(NodeWithScore(node=node, score=result.get("score", 0.0)))

        return nodes

    async def aretrieve(self, query: str, **kwargs: Any) -> List[NodeWithScore]:
        """Async retrieve using GraphRAG."""
        top_k = kwargs.get("top_k", self.similarity_top_k)
        strategy = kwargs.get("strategy", self.strategy)
        results = await self._graph_rag.search(query, strategy=strategy, top_k=top_k)

        nodes = []
        for result in results:
            text = result.get("content", result.get("description", ""))
            node = TextNode(
                text=text,
                node_id=result.get("entity_id"),
                metadata={
                    k: v
                    for k, v in result.items()
                    if k not in ("content", "description", "entity_id", "score")
                },
            )
            nodes.append(NodeWithScore(node=node, score=result.get("score", 0.0)))

        return nodes


# ============================================================================
# Response Synthesizer (LlamaIndex-compatible)
# ============================================================================


class ResponseMode(Enum):
    """Response synthesis modes matching LlamaIndex."""

    COMPACT = "compact"
    REFINE = "refine"
    SIMPLE_SUMMARIZE = "simple_summarize"
    TREE_SUMMARIZE = "tree_summarize"
    ACCUMULATE = "accumulate"
    NO_TEXT = "no_text"


class BaseSynthesizer(ABC):
    """Abstract base synthesizer matching LlamaIndex interface."""

    @abstractmethod
    def synthesize(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> Response:
        """Synthesize a response from query and retrieved nodes."""
        pass


class AgenticSynthesizer(BaseSynthesizer):
    """
    LlamaIndex-compatible response synthesizer using Agentic Brain.

    Combines retrieved context with LLM generation to produce answers.

    Example:
        synthesizer = AgenticSynthesizer(response_mode=ResponseMode.COMPACT)
        response = synthesizer.synthesize(
            query="What is GraphRAG?",
            nodes=retrieved_nodes,
        )
    """

    def __init__(
        self,
        response_mode: ResponseMode = ResponseMode.COMPACT,
        llm_model: str = "gpt-4o-mini",
        streaming: bool = False,
    ):
        self.response_mode = response_mode
        self.llm_model = llm_model
        self.streaming = streaming
        self._pipeline = RAGPipeline()

    def synthesize(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> Response:
        """
        Synthesize response from query and nodes.

        Args:
            query: The original query
            nodes: Retrieved nodes with scores
            **kwargs: Additional synthesis parameters

        Returns:
            Response object with answer and source attribution
        """
        import time

        start = time.time()

        # Build context from nodes
        context_chunks = []
        for node in nodes:
            chunk = RetrievedChunk(
                content=node.node.text,
                source=node.node.metadata.get("source", "unknown"),
                score=node.score,
                metadata=node.node.metadata,
            )
            context_chunks.append(chunk)

        # Build context string and generate response
        if not context_chunks:
            answer = "I don't have enough information to answer that question."
            confidence = 0.0
        else:
            context_parts = []
            for i, chunk in enumerate(context_chunks, 1):
                context_parts.append(
                    f"[Source {i}: {chunk.source}]\n{chunk.content}"
                )
            context = "\n\n".join(context_parts)

            # Try to generate response, fall back to context summary if LLM unavailable
            try:
                answer = self._pipeline._generate(query, context)
            except Exception as e:
                logger.debug(f"LLM generation failed, using context summary: {e}")
                # Fallback: summarize context as the answer
                answer = f"Based on the provided context:\n\n{context[:500]}"
                if len(context) > 500:
                    answer += "..."

            confidence = (
                sum(c.score for c in context_chunks) / len(context_chunks)
                if context_chunks
                else 0.0
            )

        generation_time = (time.time() - start) * 1000

        # Build RAGResult
        result = RAGResult(
            query=query,
            answer=answer,
            sources=context_chunks,
            confidence=confidence,
            model=self.llm_model,
            cached=False,
            generation_time_ms=generation_time,
        )

        return Response.from_rag_result(result)


# ============================================================================
# Query Engine (LlamaIndex-compatible)
# ============================================================================


class BaseQueryEngine(ABC):
    """Abstract query engine matching LlamaIndex interface."""

    @abstractmethod
    def query(self, query: str, **kwargs: Any) -> Response:
        """Execute a query and return response."""
        pass

    async def aquery(self, query: str, **kwargs: Any) -> Response:
        """Async query (default: runs sync version)."""
        return self.query(query, **kwargs)


class AgenticQueryEngine(BaseQueryEngine):
    """
    LlamaIndex-compatible query engine using Agentic Brain RAG.

    Combines retrieval and synthesis in a single query() call.

    Example:
        # Basic usage
        engine = AgenticQueryEngine()
        response = engine.query("What is the main topic?")
        print(response)
        print(response.source_nodes)

        # With custom retriever
        engine = AgenticQueryEngine(
            retriever=LlamaIndexGraphRAGRetriever(strategy=SearchStrategy.COMMUNITY),
            synthesizer=AgenticSynthesizer(response_mode=ResponseMode.REFINE),
        )
    """

    def __init__(
        self,
        retriever: Optional[BaseRetriever] = None,
        synthesizer: Optional[BaseSynthesizer] = None,
        similarity_top_k: int = 5,
    ):
        self.retriever = retriever or AgenticRetriever(similarity_top_k=similarity_top_k)
        self.synthesizer = synthesizer or AgenticSynthesizer()
        self.similarity_top_k = similarity_top_k

    def query(self, query: str, **kwargs: Any) -> Response:
        """
        Execute query with retrieval and synthesis.

        Args:
            query: The query string
            **kwargs: Additional parameters for retrieval/synthesis

        Returns:
            Response with answer and source nodes
        """
        nodes = self.retriever.retrieve(query, **kwargs)
        return self.synthesizer.synthesize(query, nodes, **kwargs)

    async def aquery(self, query: str, **kwargs: Any) -> Response:
        """Async query execution."""
        nodes = await self.retriever.aretrieve(query, **kwargs)
        return self.synthesizer.synthesize(query, nodes, **kwargs)


class GraphRAGQueryEngine(BaseQueryEngine):
    """
    Query engine optimized for GraphRAG knowledge graphs.

    Provides additional graph-specific query capabilities.
    """

    def __init__(
        self,
        config: Optional[GraphRAGConfig] = None,
        strategy: SearchStrategy = SearchStrategy.HYBRID,
        similarity_top_k: int = 10,
    ):
        self._retriever = LlamaIndexGraphRAGRetriever(
            config=config,
            strategy=strategy,
            similarity_top_k=similarity_top_k,
        )
        self._synthesizer = AgenticSynthesizer()
        self.strategy = strategy

    def query(self, query: str, **kwargs: Any) -> Response:
        """Execute graph-enhanced query."""
        strategy = kwargs.pop("strategy", self.strategy)
        nodes = self._retriever._retrieve(query, strategy=strategy, **kwargs)
        return self._synthesizer.synthesize(query, nodes, **kwargs)


# ============================================================================
# Index Abstraction (LlamaIndex-compatible)
# ============================================================================


class BaseIndex(ABC):
    """Abstract index matching LlamaIndex interface."""

    @classmethod
    @abstractmethod
    def from_documents(
        cls,
        documents: Sequence[Union[TextNode, Document, Dict[str, Any]]],
        **kwargs: Any,
    ) -> "BaseIndex":
        """Create index from documents."""
        pass

    @abstractmethod
    def as_query_engine(self, **kwargs: Any) -> BaseQueryEngine:
        """Get a query engine for this index."""
        pass

    @abstractmethod
    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        """Get a retriever for this index."""
        pass


class AgenticIndex(BaseIndex):
    """
    LlamaIndex-compatible index using Agentic Brain DocumentStore.

    Drop-in replacement for LlamaIndex VectorStoreIndex.

    Example:
        # Create from documents
        documents = [TextNode(text="Document 1"), TextNode(text="Document 2")]
        index = AgenticIndex.from_documents(documents)

        # Query
        query_engine = index.as_query_engine()
        response = query_engine.query("What is in document 1?")

        # Or use retriever directly
        retriever = index.as_retriever(similarity_top_k=10)
        nodes = retriever.retrieve("search query")
    """

    def __init__(
        self,
        document_store: Optional[DocumentStore] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self._store = document_store or InMemoryDocumentStore()
        self._embeddings = embedding_provider or get_embeddings()

    @classmethod
    def from_documents(
        cls,
        documents: Sequence[Union[TextNode, Document, Dict[str, Any]]],
        show_progress: bool = True,
        **kwargs: Any,
    ) -> "AgenticIndex":
        """
        Create index from documents.

        Args:
            documents: List of documents (TextNode, Document, or dict)
            show_progress: Show indexing progress
            **kwargs: Additional index configuration

        Returns:
            Configured AgenticIndex instance
        """
        store = kwargs.pop("document_store", None) or InMemoryDocumentStore()
        embedding_provider = kwargs.pop("embedding_provider", None)
        index = cls(document_store=store, embedding_provider=embedding_provider)

        for i, doc in enumerate(documents):
            if show_progress and (i + 1) % 100 == 0:
                logger.info(f"Indexed {i + 1}/{len(documents)} documents")

            if isinstance(doc, TextNode):
                index._store.add(doc.text, metadata=doc.metadata, doc_id=doc.node_id)
            elif isinstance(doc, Document):
                index._store.add(doc)
            elif isinstance(doc, dict):
                text = doc.get("text", doc.get("content", doc.get("page_content", "")))
                metadata = {k: v for k, v in doc.items() if k not in ("text", "content", "page_content")}
                index._store.add(text, metadata=metadata)
            else:
                raise TypeError(f"Unsupported document type: {type(doc)}")

        logger.info(f"Indexed {len(documents)} documents into AgenticIndex")
        return index

    def as_query_engine(self, **kwargs: Any) -> BaseQueryEngine:
        """Get query engine for this index."""
        retriever = self.as_retriever(**kwargs)
        return AgenticQueryEngine(
            retriever=retriever,
            similarity_top_k=kwargs.get("similarity_top_k", 5),
        )

    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        """Get retriever for this index."""
        return AgenticRetriever(
            document_store=self._store,
            embedding_provider=self._embeddings,
            similarity_top_k=kwargs.get("similarity_top_k", 5),
        )

    def insert(self, document: Union[TextNode, Document, Dict[str, Any]]) -> None:
        """Insert a single document into the index."""
        if isinstance(document, TextNode):
            self._store.add(document.text, metadata=document.metadata, doc_id=document.node_id)
        elif isinstance(document, Document):
            self._store.add(document)
        elif isinstance(document, dict):
            text = document.get("text", document.get("content", ""))
            metadata = {k: v for k, v in document.items() if k not in ("text", "content")}
            self._store.add(text, metadata=metadata)

    def delete(self, doc_id: str) -> None:
        """Delete a document from the index."""
        self._store.delete(doc_id)

    def refresh(
        self,
        documents: Sequence[Union[TextNode, Document]],
    ) -> List[bool]:
        """
        Refresh documents in index (update existing, add new).

        Returns list of bools indicating if each document was refreshed.
        """
        results = []
        for doc in documents:
            if isinstance(doc, TextNode):
                doc_id = doc.node_id or ""
                existing = self._store.get(doc_id)
                if existing and existing.content == doc.text:
                    results.append(False)
                else:
                    self._store.add(doc.text, metadata=doc.metadata, doc_id=doc_id)
                    results.append(True)
            elif isinstance(doc, Document):
                existing = self._store.get(doc.id)
                if existing and existing.content == doc.content:
                    results.append(False)
                else:
                    self._store.add(doc)
                    results.append(True)
            else:
                results.append(False)
        return results


class GraphRAGIndex(BaseIndex):
    """
    Knowledge graph index using Agentic Brain GraphRAG.

    Provides entity extraction, relationship mapping, and community detection.

    Example:
        index = GraphRAGIndex.from_documents(
            documents,
            neo4j_uri="bolt://localhost:7687",
            enable_communities=True,
        )
        query_engine = index.as_query_engine(strategy=SearchStrategy.COMMUNITY)
    """

    def __init__(
        self,
        config: Optional[GraphRAGConfig] = None,
    ):
        self._graph_rag = GraphRAG(config)
        self._config = config or GraphRAGConfig()

    @classmethod
    def from_documents(
        cls,
        documents: Sequence[Union[TextNode, Document, Dict[str, Any]]],
        show_progress: bool = True,
        **kwargs: Any,
    ) -> "GraphRAGIndex":
        """
        Create GraphRAG index from documents.

        Extracts entities and relationships, builds knowledge graph.
        """
        config = GraphRAGConfig(
            neo4j_uri=kwargs.pop("neo4j_uri", "bolt://localhost:7687"),
            neo4j_user=kwargs.pop("neo4j_user", "neo4j"),
            neo4j_password=kwargs.pop("neo4j_password", None),
            enable_communities=kwargs.pop("enable_communities", True),
            **{k: v for k, v in kwargs.items() if hasattr(GraphRAGConfig, k)},
        )
        index = cls(config=config)

        docs_to_ingest = []
        for doc in documents:
            if isinstance(doc, TextNode):
                docs_to_ingest.append({"content": doc.text, "metadata": doc.metadata})
            elif isinstance(doc, Document):
                docs_to_ingest.append({"content": doc.content, "metadata": doc.metadata})
            elif isinstance(doc, dict):
                text = doc.get("text", doc.get("content", doc.get("page_content", "")))
                docs_to_ingest.append({"content": text, "metadata": doc})

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run, index._graph_rag.ingest(docs_to_ingest)
                )
                stats = future.result()
        else:
            stats = loop.run_until_complete(index._graph_rag.ingest(docs_to_ingest))

        logger.info(f"GraphRAG ingest complete: {stats}")
        return index

    def as_query_engine(self, **kwargs: Any) -> BaseQueryEngine:
        """Get GraphRAG query engine."""
        strategy = kwargs.pop("strategy", SearchStrategy.HYBRID)
        return GraphRAGQueryEngine(
            config=self._config,
            strategy=strategy,
            similarity_top_k=kwargs.get("similarity_top_k", 10),
        )

    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        """Get GraphRAG retriever."""
        strategy = kwargs.pop("strategy", SearchStrategy.HYBRID)
        return LlamaIndexGraphRAGRetriever(
            config=self._config,
            strategy=strategy,
            similarity_top_k=kwargs.get("similarity_top_k", 10),
        )


# ============================================================================
# Document Loaders (LlamaIndex-compatible)
# ============================================================================


class SimpleDirectoryReader:
    """
    LlamaIndex-compatible directory reader.

    Loads documents from a directory with various file types.

    Example:
        reader = SimpleDirectoryReader("./data", recursive=True)
        documents = reader.load_data()
    """

    def __init__(
        self,
        input_dir: Optional[str] = None,
        input_files: Optional[List[str]] = None,
        recursive: bool = False,
        required_exts: Optional[List[str]] = None,
        exclude: Optional[List[str]] = None,
        file_metadata: Optional[Callable[[str], Dict[str, Any]]] = None,
    ):
        self.input_dir = Path(input_dir) if input_dir else None
        self.input_files = [Path(f) for f in (input_files or [])]
        self.recursive = recursive
        self.required_exts = required_exts or [".txt", ".md", ".pdf", ".json"]
        self.exclude = exclude or []
        self.file_metadata = file_metadata

    def load_data(self, show_progress: bool = True) -> List[TextNode]:
        """
        Load documents from directory/files.

        Returns list of TextNode objects.
        """
        files_to_load = []

        if self.input_dir and self.input_dir.exists():
            if self.recursive:
                for ext in self.required_exts:
                    files_to_load.extend(self.input_dir.rglob(f"*{ext}"))
            else:
                for ext in self.required_exts:
                    files_to_load.extend(self.input_dir.glob(f"*{ext}"))

        files_to_load.extend(self.input_files)
        files_to_load = [
            f for f in files_to_load if not any(ex in str(f) for ex in self.exclude)
        ]

        documents = []
        for i, file_path in enumerate(files_to_load):
            if show_progress and (i + 1) % 10 == 0:
                logger.info(f"Loading {i + 1}/{len(files_to_load)} files")

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                metadata = {"source": str(file_path), "file_name": file_path.name}
                if self.file_metadata:
                    metadata.update(self.file_metadata(str(file_path)))

                documents.append(TextNode(text=content, metadata=metadata))
            except Exception as e:
                logger.warning(f"Failed to load {file_path}: {e}")

        logger.info(f"Loaded {len(documents)} documents")
        return documents


# ============================================================================
# Settings / ServiceContext (LlamaIndex-compatible)
# ============================================================================


class Settings:
    """
    Global settings matching LlamaIndex Settings pattern.

    Example:
        from agentic_brain.rag.llamaindex_compat import Settings

        Settings.llm = "gpt-4o"
        Settings.embed_model = "text-embedding-3-small"
        Settings.chunk_size = 512
    """

    _llm: str = "gpt-4o-mini"
    _embed_model: str = "all-MiniLM-L6-v2"
    _chunk_size: int = 512
    _chunk_overlap: int = 50

    @classmethod
    @property
    def llm(cls) -> str:
        return cls._llm

    @classmethod
    def set_llm(cls, value: str) -> None:
        cls._llm = value

    @classmethod
    @property
    def embed_model(cls) -> str:
        return cls._embed_model

    @classmethod
    def set_embed_model(cls, value: str) -> None:
        cls._embed_model = value

    @classmethod
    @property
    def chunk_size(cls) -> int:
        return cls._chunk_size

    @classmethod
    def set_chunk_size(cls, value: int) -> None:
        cls._chunk_size = value

    @classmethod
    @property
    def chunk_overlap(cls) -> int:
        return cls._chunk_overlap

    @classmethod
    def set_chunk_overlap(cls, value: int) -> None:
        cls._chunk_overlap = value


# ============================================================================
# Public API
# ============================================================================

__all__ = [
    # Core data structures
    "TextNode",
    "LIDocument",
    "NodeWithScore",
    "Response",
    # Retrievers
    "BaseRetriever",
    "AgenticRetriever",
    "LlamaIndexGraphRAGRetriever",
    # Synthesizers
    "ResponseMode",
    "BaseSynthesizer",
    "AgenticSynthesizer",
    # Query engines
    "BaseQueryEngine",
    "AgenticQueryEngine",
    "GraphRAGQueryEngine",
    # Indexes
    "BaseIndex",
    "AgenticIndex",
    "GraphRAGIndex",
    # Loaders
    "SimpleDirectoryReader",
    # Settings
    "Settings",
    # Re-exports for convenience
    "GraphRAGConfig",
    "SearchStrategy",
]
