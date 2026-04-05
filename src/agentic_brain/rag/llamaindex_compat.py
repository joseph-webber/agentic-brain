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
- ServiceContext: Global service configuration (llm, embed_model, chunk_size)
- NodeParser: SentenceSplitter, TokenTextSplitter with overlap
- Streaming: StreamingResponse with async generators
- Callbacks: CBEventType, CallbackManager for tracing
- Metadata Extractors: TitleExtractor, QuestionsAnsweredExtractor, SummaryExtractor
- ComposableGraph: Multi-index queries

Usage (Migration from LlamaIndex):
    # Before (LlamaIndex)
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
    from llama_index.core import ServiceContext
    documents = SimpleDirectoryReader("data").load_data()
    index = VectorStoreIndex.from_documents(documents)
    query_engine = index.as_query_engine()
    response = query_engine.query("What is the main topic?")

    # After (Agentic Brain with LlamaIndex compat)
    from agentic_brain.rag.llamaindex_compat import (
        AgenticIndex,
        SimpleDirectoryReader,
        ServiceContext,
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

import asyncio
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generator,
    Generic,
    List,
    Optional,
    Protocol,
    Sequence,
    TypeVar,
    Union,
)

from .embeddings import EmbeddingProvider, get_embeddings
from .graph_rag import GraphRAG, GraphRAGConfig, SearchStrategy
from .pipeline import RAGPipeline, RAGResult
from .retriever import RetrievedChunk, Retriever
from .store import Document, DocumentStore, InMemoryDocumentStore

logger = logging.getLogger(__name__)

T = TypeVar("T")


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
# ServiceContext (LlamaIndex-compatible)
# ============================================================================


@dataclass
class ServiceContext:
    """
    LlamaIndex-compatible ServiceContext for global configuration.

    Provides a centralized configuration for LLM, embeddings, and chunking
    that can be passed to indexes and query engines.

    Example:
        from agentic_brain.rag.llamaindex_compat import ServiceContext

        # Create custom context
        service_context = ServiceContext.from_defaults(
            llm="gpt-4o",
            embed_model="text-embedding-3-small",
            chunk_size=1024,
            chunk_overlap=100,
        )

        # Use with index
        index = AgenticIndex.from_documents(
            documents,
            service_context=service_context,
        )
    """

    llm: Optional[str] = None
    embed_model: Optional[str] = None
    chunk_size: int = 512
    chunk_overlap: int = 50
    callback_manager: Optional["CallbackManager"] = None
    node_parser: Optional["BaseNodeParser"] = None

    @classmethod
    def from_defaults(
        cls,
        llm: Optional[str] = None,
        embed_model: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        callback_manager: Optional["CallbackManager"] = None,
        node_parser: Optional["BaseNodeParser"] = None,
        **kwargs: Any,
    ) -> "ServiceContext":
        """
        Create ServiceContext with defaults from Settings.

        Args:
            llm: LLM model name (default: Settings.llm)
            embed_model: Embedding model name (default: Settings.embed_model)
            chunk_size: Chunk size (default: Settings.chunk_size)
            chunk_overlap: Chunk overlap (default: Settings.chunk_overlap)
            callback_manager: Optional callback manager for tracing
            node_parser: Optional custom node parser

        Returns:
            Configured ServiceContext instance
        """
        return cls(
            llm=llm or Settings._llm,
            embed_model=embed_model or Settings._embed_model,
            chunk_size=chunk_size or Settings._chunk_size,
            chunk_overlap=chunk_overlap or Settings._chunk_overlap,
            callback_manager=callback_manager,
            node_parser=node_parser,
        )

    def to_settings(self) -> None:
        """Apply this context's configuration to global Settings."""
        if self.llm:
            Settings.set_llm(self.llm)
        if self.embed_model:
            Settings.set_embed_model(self.embed_model)
        Settings.set_chunk_size(self.chunk_size)
        Settings.set_chunk_overlap(self.chunk_overlap)


# ============================================================================
# Node Parsers (LlamaIndex-compatible)
# ============================================================================


class BaseNodeParser(ABC):
    """
    Abstract base node parser matching LlamaIndex interface.

    Node parsers split documents into smaller chunks (nodes) for indexing.
    """

    @abstractmethod
    def get_nodes_from_documents(
        self,
        documents: Sequence[Union[TextNode, Document]],
        show_progress: bool = False,
    ) -> List[TextNode]:
        """Parse documents into nodes."""
        pass

    def __call__(
        self,
        documents: Sequence[Union[TextNode, Document]],
        **kwargs: Any,
    ) -> List[TextNode]:
        """Callable interface for parsing."""
        return self.get_nodes_from_documents(documents, **kwargs)


class SentenceSplitter(BaseNodeParser):
    """
    LlamaIndex-compatible sentence splitter.

    Splits text into chunks based on sentences with configurable overlap.

    Example:
        splitter = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=50,
            paragraph_separator="\n\n",
        )
        nodes = splitter.get_nodes_from_documents(documents)
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separator: str = " ",
        paragraph_separator: str = "\n\n",
        secondary_chunking_regex: Optional[str] = None,
        include_metadata: bool = True,
        include_prev_next_rel: bool = True,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separator = separator
        self.paragraph_separator = paragraph_separator
        self.secondary_chunking_regex = secondary_chunking_regex
        self.include_metadata = include_metadata
        self.include_prev_next_rel = include_prev_next_rel

        # Sentence ending patterns
        self._sentence_endings = re.compile(r'(?<=[.!?])\s+')

    def _split_text(self, text: str) -> List[str]:
        """Split text into sentences then combine into chunks."""
        # Split into paragraphs first
        paragraphs = text.split(self.paragraph_separator)

        # Split paragraphs into sentences
        sentences = []
        for para in paragraphs:
            para_sentences = self._sentence_endings.split(para)
            sentences.extend([s.strip() for s in para_sentences if s.strip()])

        # Combine sentences into chunks
        chunks = []
        current_chunk: List[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence)

            if current_length + sentence_length > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(self.separator.join(current_chunk))

                # Start new chunk with overlap
                overlap_text = self.separator.join(current_chunk)
                if len(overlap_text) > self.chunk_overlap:
                    # Keep last portion for overlap
                    overlap_sentences = []
                    overlap_length = 0
                    for s in reversed(current_chunk):
                        if overlap_length + len(s) <= self.chunk_overlap:
                            overlap_sentences.insert(0, s)
                            overlap_length += len(s)
                        else:
                            break
                    current_chunk = overlap_sentences
                    current_length = overlap_length
                else:
                    current_chunk = []
                    current_length = 0

            current_chunk.append(sentence)
            current_length += sentence_length + len(self.separator)

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(self.separator.join(current_chunk))

        return chunks

    def get_nodes_from_documents(
        self,
        documents: Sequence[Union[TextNode, Document]],
        show_progress: bool = False,
    ) -> List[TextNode]:
        """Split documents into nodes."""
        all_nodes: List[TextNode] = []

        for doc_idx, doc in enumerate(documents):
            if show_progress and (doc_idx + 1) % 100 == 0:
                logger.info(f"Parsed {doc_idx + 1}/{len(documents)} documents")

            # Get text content
            if isinstance(doc, TextNode):
                text = doc.text
                metadata = doc.metadata.copy() if self.include_metadata else {}
            elif isinstance(doc, Document):
                text = doc.content
                metadata = doc.metadata.copy() if self.include_metadata else {}
            else:
                continue

            # Split into chunks
            chunks = self._split_text(text)

            # Create nodes
            prev_node: Optional[TextNode] = None
            for chunk_idx, chunk in enumerate(chunks):
                node = TextNode(
                    text=chunk,
                    metadata={
                        **metadata,
                        "chunk_index": chunk_idx,
                        "total_chunks": len(chunks),
                    },
                )

                # Add prev/next relationships
                if self.include_prev_next_rel:
                    if prev_node:
                        node.relationships["prev"] = prev_node.node_id
                        prev_node.relationships["next"] = node.node_id

                all_nodes.append(node)
                prev_node = node

        return all_nodes


class TokenTextSplitter(BaseNodeParser):
    """
    LlamaIndex-compatible token-based text splitter.

    Splits text into chunks based on approximate token count.

    Example:
        splitter = TokenTextSplitter(
            chunk_size=256,  # tokens
            chunk_overlap=20,
        )
        nodes = splitter.get_nodes_from_documents(documents)
    """

    # Approximate chars per token (conservative estimate)
    CHARS_PER_TOKEN = 4

    def __init__(
        self,
        chunk_size: int = 256,
        chunk_overlap: int = 20,
        separator: str = "\n",
        backup_separators: Optional[List[str]] = None,
    ):
        self.chunk_size = chunk_size  # in tokens
        self.chunk_overlap = chunk_overlap  # in tokens
        self.separator = separator
        self.backup_separators = backup_separators or ["\n\n", ". ", " "]

        # Convert to character estimates
        self._char_chunk_size = chunk_size * self.CHARS_PER_TOKEN
        self._char_overlap = chunk_overlap * self.CHARS_PER_TOKEN

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def _split_text(self, text: str) -> List[str]:
        """Split text into token-bounded chunks."""
        if self._estimate_tokens(text) <= self.chunk_size:
            return [text] if text.strip() else []

        # Try splitting by separator
        splits = text.split(self.separator)
        chunks = []
        current_chunk: List[str] = []
        current_tokens = 0

        for split in splits:
            split_tokens = self._estimate_tokens(split)

            if current_tokens + split_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append(self.separator.join(current_chunk))

                # Calculate overlap
                overlap_tokens = 0
                overlap_splits: List[str] = []
                for s in reversed(current_chunk):
                    s_tokens = self._estimate_tokens(s)
                    if overlap_tokens + s_tokens <= self.chunk_overlap:
                        overlap_splits.insert(0, s)
                        overlap_tokens += s_tokens
                    else:
                        break

                current_chunk = overlap_splits
                current_tokens = overlap_tokens

            current_chunk.append(split)
            current_tokens += split_tokens

        if current_chunk:
            chunks.append(self.separator.join(current_chunk))

        return chunks

    def get_nodes_from_documents(
        self,
        documents: Sequence[Union[TextNode, Document]],
        show_progress: bool = False,
    ) -> List[TextNode]:
        """Split documents into token-bounded nodes."""
        all_nodes: List[TextNode] = []

        for doc in documents:
            if isinstance(doc, TextNode):
                text = doc.text
                metadata = doc.metadata.copy()
            elif isinstance(doc, Document):
                text = doc.content
                metadata = doc.metadata.copy()
            else:
                continue

            chunks = self._split_text(text)
            for idx, chunk in enumerate(chunks):
                node = TextNode(
                    text=chunk,
                    metadata={
                        **metadata,
                        "chunk_index": idx,
                        "estimated_tokens": self._estimate_tokens(chunk),
                    },
                )
                all_nodes.append(node)

        return all_nodes


# ============================================================================
# Response Synthesizer Modes (Extended)
# ============================================================================


class CompactSynthesizer(BaseSynthesizer):
    """
    Compact response synthesizer - stuffs all context into one prompt.

    This is the simplest and most token-efficient mode.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model
        self._pipeline = RAGPipeline()

    def synthesize(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> Response:
        """Synthesize by combining all context into one prompt."""
        if not nodes:
            return Response(
                response="I don't have enough information to answer that question.",
                source_nodes=[],
                metadata={"mode": "compact", "nodes_used": 0},
            )

        # Build compact context
        context_parts = []
        for i, node in enumerate(nodes, 1):
            context_parts.append(f"[{i}] {node.node.text}")

        context = "\n\n".join(context_parts)

        try:
            answer = self._pipeline._generate(query, context)
        except Exception as e:
            logger.debug(f"LLM failed, using context summary: {e}")
            answer = f"Based on the context:\n{context[:500]}..."

        return Response(
            response=answer,
            source_nodes=nodes,
            metadata={"mode": "compact", "nodes_used": len(nodes)},
        )


class RefineSynthesizer(BaseSynthesizer):
    """
    Refine response synthesizer - iteratively refines answer with each context.

    Produces higher quality answers but uses more tokens.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model
        self._pipeline = RAGPipeline()

    def synthesize(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> Response:
        """Synthesize by iteratively refining the answer."""
        if not nodes:
            return Response(
                response="I don't have enough information to answer that question.",
                source_nodes=[],
                metadata={"mode": "refine", "refinement_steps": 0},
            )

        # Start with first node
        current_answer = ""

        for i, node in enumerate(nodes):
            if i == 0:
                # Initial answer
                context = node.node.text
                prompt = f"Query: {query}\n\nContext:\n{context}\n\nProvide an answer."
            else:
                # Refine existing answer
                context = node.node.text
                prompt = (
                    f"Query: {query}\n\n"
                    f"Existing Answer:\n{current_answer}\n\n"
                    f"New Context:\n{context}\n\n"
                    f"Refine the answer with this new information."
                )

            try:
                current_answer = self._pipeline._generate(query, prompt)
            except Exception as e:
                logger.debug(f"Refinement step {i} failed: {e}")
                if not current_answer:
                    current_answer = node.node.text[:500]

        return Response(
            response=current_answer,
            source_nodes=nodes,
            metadata={"mode": "refine", "refinement_steps": len(nodes)},
        )


class TreeSummarizeSynthesizer(BaseSynthesizer):
    """
    Tree summarize synthesizer - builds answer through hierarchical summarization.

    Good for large numbers of nodes as it processes in a tree structure.
    """

    def __init__(
        self,
        llm_model: str = "gpt-4o-mini",
        num_children: int = 4,
    ):
        self.llm_model = llm_model
        self.num_children = num_children
        self._pipeline = RAGPipeline()

    def _summarize_group(self, query: str, texts: List[str]) -> str:
        """Summarize a group of texts."""
        combined = "\n\n---\n\n".join(texts)
        prompt = f"Query: {query}\n\nTexts to summarize:\n{combined}"

        try:
            return self._pipeline._generate(query, prompt)
        except Exception:
            return combined[:500]

    def synthesize(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> Response:
        """Synthesize through tree summarization."""
        if not nodes:
            return Response(
                response="I don't have enough information to answer that question.",
                source_nodes=[],
                metadata={"mode": "tree_summarize", "levels": 0},
            )

        # Get all texts
        texts = [node.node.text for node in nodes]
        levels = 0

        # Build tree bottom-up
        while len(texts) > 1:
            new_texts = []
            for i in range(0, len(texts), self.num_children):
                group = texts[i : i + self.num_children]
                summary = self._summarize_group(query, group)
                new_texts.append(summary)
            texts = new_texts
            levels += 1

        return Response(
            response=texts[0] if texts else "",
            source_nodes=nodes,
            metadata={"mode": "tree_summarize", "levels": levels},
        )


class SimpleSummarizeSynthesizer(BaseSynthesizer):
    """
    Simple summarize synthesizer - concatenates and summarizes.

    Quick and simple, best for small numbers of nodes.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model
        self._pipeline = RAGPipeline()

    def synthesize(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> Response:
        """Simple concatenation and summarization."""
        if not nodes:
            return Response(
                response="I don't have enough information to answer that question.",
                source_nodes=[],
                metadata={"mode": "simple_summarize"},
            )

        combined = "\n\n".join(node.node.text for node in nodes)
        prompt = f"Summarize the following to answer: {query}\n\n{combined}"

        try:
            answer = self._pipeline._generate(query, combined)
        except Exception:
            answer = combined[:500]

        return Response(
            response=answer,
            source_nodes=nodes,
            metadata={"mode": "simple_summarize"},
        )


def get_response_synthesizer(
    response_mode: Union[ResponseMode, str] = ResponseMode.COMPACT,
    llm_model: str = "gpt-4o-mini",
    **kwargs: Any,
) -> BaseSynthesizer:
    """
    Factory function to get a response synthesizer by mode.

    LlamaIndex-compatible factory for creating synthesizers.

    Args:
        response_mode: The synthesis mode to use
        llm_model: LLM model name
        **kwargs: Additional synthesizer parameters

    Returns:
        Configured synthesizer instance

    Example:
        synthesizer = get_response_synthesizer(ResponseMode.REFINE)
        response = synthesizer.synthesize(query, nodes)
    """
    if isinstance(response_mode, str):
        response_mode = ResponseMode(response_mode)

    synthesizers = {
        ResponseMode.COMPACT: CompactSynthesizer,
        ResponseMode.REFINE: RefineSynthesizer,
        ResponseMode.TREE_SUMMARIZE: TreeSummarizeSynthesizer,
        ResponseMode.SIMPLE_SUMMARIZE: SimpleSummarizeSynthesizer,
        ResponseMode.ACCUMULATE: CompactSynthesizer,  # Alias
        ResponseMode.NO_TEXT: CompactSynthesizer,  # Alias
    }

    synthesizer_class = synthesizers.get(response_mode, CompactSynthesizer)
    return synthesizer_class(llm_model=llm_model, **kwargs)


# ============================================================================
# Streaming Support (LlamaIndex-compatible)
# ============================================================================


@dataclass
class StreamingResponse:
    """
    LlamaIndex-compatible streaming response.

    Provides both sync and async iteration over response tokens.

    Example:
        response = query_engine.query("What is GraphRAG?", streaming=True)
        for token in response.response_gen:
            print(token, end="", flush=True)

        # Async
        async for token in response.async_response_gen():
            print(token, end="", flush=True)
    """

    response_gen: Generator[str, None, None]
    source_nodes: List[NodeWithScore] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    _response_txt: Optional[str] = field(default=None, repr=False)

    def __str__(self) -> str:
        """Get full response text (consumes generator if not already done)."""
        if self._response_txt is None:
            self._response_txt = self.get_response()
        return self._response_txt

    def get_response(self) -> str:
        """Consume generator and return full response."""
        if self._response_txt is not None:
            return self._response_txt

        tokens = []
        for token in self.response_gen:
            tokens.append(token)
        self._response_txt = "".join(tokens)
        return self._response_txt

    async def async_response_gen(self) -> AsyncGenerator[str, None]:
        """Async generator wrapper."""
        for token in self.response_gen:
            yield token
            await asyncio.sleep(0)  # Yield control

    def print_response_stream(self) -> str:
        """Print tokens as they stream and return full response."""
        tokens = []
        for token in self.response_gen:
            print(token, end="", flush=True)
            tokens.append(token)
        print()  # Newline at end
        self._response_txt = "".join(tokens)
        return self._response_txt


class StreamingSynthesizer(BaseSynthesizer):
    """
    Streaming response synthesizer.

    Yields tokens as they are generated for real-time display.
    """

    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model

    def _stream_generate(
        self,
        query: str,
        context: str,
    ) -> Generator[str, None, None]:
        """Generate response tokens (simulated streaming)."""
        # Build response
        response = f"Based on the context provided:\n\n"

        # Simulate token-by-token streaming
        words = context.split()[:50]  # Take first 50 words
        summary = " ".join(words)
        if len(context.split()) > 50:
            summary += "..."

        full_response = response + summary

        # Yield word by word (simulates streaming)
        for word in full_response.split():
            yield word + " "
            time.sleep(0.02)  # Small delay for streaming effect

    def synthesize(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> Response:
        """Non-streaming synthesis (for compatibility)."""
        context = "\n\n".join(node.node.text for node in nodes)
        tokens = list(self._stream_generate(query, context))
        response_text = "".join(tokens)

        return Response(
            response=response_text,
            source_nodes=nodes,
            metadata={"mode": "streaming", "streaming": False},
        )

    def synthesize_stream(
        self,
        query: str,
        nodes: List[NodeWithScore],
        **kwargs: Any,
    ) -> StreamingResponse:
        """Streaming synthesis."""
        context = "\n\n".join(node.node.text for node in nodes)

        return StreamingResponse(
            response_gen=self._stream_generate(query, context),
            source_nodes=nodes,
            metadata={"mode": "streaming", "streaming": True},
        )


# ============================================================================
# Callback System (LlamaIndex-compatible)
# ============================================================================


class CBEventType(Enum):
    """
    LlamaIndex-compatible callback event types.

    Used for tracing and monitoring RAG operations.
    """

    CHUNKING = auto()
    NODE_PARSING = auto()
    EMBEDDING = auto()
    LLM = auto()
    QUERY = auto()
    RETRIEVE = auto()
    SYNTHESIZE = auto()
    TREE = auto()
    SUB_QUESTION = auto()
    TEMPLATING = auto()
    FUNCTION_CALL = auto()
    RERANKING = auto()
    EXCEPTION = auto()


@dataclass
class CBEvent:
    """A callback event with timing and payload data."""

    event_type: CBEventType
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    parent_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    time: float = field(default_factory=time.time)


class BaseCallbackHandler(ABC):
    """
    Abstract base callback handler matching LlamaIndex interface.

    Implement this to create custom callback handlers for logging,
    tracing, or monitoring.
    """

    @abstractmethod
    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Called when an event starts. Returns event_id."""
        pass

    @abstractmethod
    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Called when an event ends."""
        pass

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        """Start a trace (optional)."""
        pass

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """End a trace (optional)."""
        pass


class TokenCountingHandler(BaseCallbackHandler):
    """
    Callback handler that counts tokens.

    Useful for monitoring token usage and costs.

    Example:
        handler = TokenCountingHandler()
        callback_manager = CallbackManager([handler])

        # After queries...
        print(f"Total tokens: {handler.total_tokens}")
    """

    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.embedding_tokens = 0
        self._events: List[CBEvent] = []

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        event_id = event_id or str(uuid.uuid4())[:8]
        event = CBEvent(
            event_type=event_type,
            event_id=event_id,
            parent_id=parent_id,
            payload=payload or {},
        )
        self._events.append(event)

        # Count input tokens
        if payload and event_type == CBEventType.LLM:
            prompt = payload.get("prompt", "")
            self.prompt_tokens += len(prompt) // 4  # Rough estimate

        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        # Count output tokens
        if payload:
            if event_type == CBEventType.LLM:
                response = payload.get("response", "")
                tokens = len(response) // 4
                self.completion_tokens += tokens
                self.total_tokens += tokens
            elif event_type == CBEventType.EMBEDDING:
                self.embedding_tokens += payload.get("token_count", 0)

    def reset(self) -> None:
        """Reset all counters."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.embedding_tokens = 0
        self._events.clear()


class LlamaDebugHandler(BaseCallbackHandler):
    """
    Debug callback handler for development.

    Logs all events for debugging and inspection.

    Example:
        handler = LlamaDebugHandler(print_trace_on_end=True)
        callback_manager = CallbackManager([handler])
    """

    def __init__(
        self,
        print_trace_on_end: bool = False,
        event_starts_to_ignore: Optional[List[CBEventType]] = None,
        event_ends_to_ignore: Optional[List[CBEventType]] = None,
    ):
        self.print_trace_on_end = print_trace_on_end
        self.event_starts_to_ignore = event_starts_to_ignore or []
        self.event_ends_to_ignore = event_ends_to_ignore or []
        self._events: List[CBEvent] = []
        self._trace_map: Dict[str, List[str]] = {}

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        if event_type in self.event_starts_to_ignore:
            return event_id or str(uuid.uuid4())[:8]

        event_id = event_id or str(uuid.uuid4())[:8]
        event = CBEvent(
            event_type=event_type,
            event_id=event_id,
            parent_id=parent_id,
            payload=payload or {},
        )
        self._events.append(event)

        logger.debug(f"[TRACE] START {event_type.name} (id={event_id})")

        # Track parent-child relationships
        if parent_id:
            if parent_id not in self._trace_map:
                self._trace_map[parent_id] = []
            self._trace_map[parent_id].append(event_id)

        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        if event_type in self.event_ends_to_ignore:
            return

        logger.debug(f"[TRACE] END {event_type.name} (id={event_id})")

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        if self.print_trace_on_end:
            self._print_trace()

    def _print_trace(self) -> None:
        """Print formatted trace."""
        print("\n=== Trace ===")
        for event in self._events:
            indent = "  " if event.parent_id else ""
            print(f"{indent}{event.event_type.name}: {event.event_id}")
        print("=============\n")

    def get_events(self) -> List[CBEvent]:
        """Get all recorded events."""
        return self._events.copy()

    def flush_events(self) -> List[CBEvent]:
        """Get and clear all events."""
        events = self._events.copy()
        self._events.clear()
        return events


class CallbackManager:
    """
    LlamaIndex-compatible callback manager.

    Manages multiple callback handlers and dispatches events.

    Example:
        token_counter = TokenCountingHandler()
        debug_handler = LlamaDebugHandler()

        callback_manager = CallbackManager(
            handlers=[token_counter, debug_handler]
        )

        # Use with service context
        service_context = ServiceContext.from_defaults(
            callback_manager=callback_manager
        )
    """

    def __init__(
        self,
        handlers: Optional[List[BaseCallbackHandler]] = None,
    ):
        self.handlers = handlers or []
        self._trace_stack: List[str] = []

    def add_handler(self, handler: BaseCallbackHandler) -> None:
        """Add a callback handler."""
        self.handlers.append(handler)

    def remove_handler(self, handler: BaseCallbackHandler) -> None:
        """Remove a callback handler."""
        if handler in self.handlers:
            self.handlers.remove(handler)

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        """Dispatch event start to all handlers."""
        event_id = event_id or str(uuid.uuid4())[:8]
        parent_id = parent_id or (self._trace_stack[-1] if self._trace_stack else "")

        for handler in self.handlers:
            handler.on_event_start(
                event_type=event_type,
                payload=payload,
                event_id=event_id,
                parent_id=parent_id,
                **kwargs,
            )

        self._trace_stack.append(event_id)
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[Dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        """Dispatch event end to all handlers."""
        if self._trace_stack:
            self._trace_stack.pop()

        for handler in self.handlers:
            handler.on_event_end(
                event_type=event_type,
                payload=payload,
                event_id=event_id,
                **kwargs,
            )

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        """Start a new trace."""
        for handler in self.handlers:
            handler.start_trace(trace_id)

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[Dict[str, List[str]]] = None,
    ) -> None:
        """End the current trace."""
        for handler in self.handlers:
            handler.end_trace(trace_id, trace_map)


# ============================================================================
# Metadata Extractors (LlamaIndex-compatible)
# ============================================================================


class BaseExtractor(ABC):
    """
    Abstract base metadata extractor matching LlamaIndex interface.

    Extractors enhance nodes with additional metadata.
    """

    @abstractmethod
    def extract(self, nodes: List[TextNode]) -> List[Dict[str, Any]]:
        """Extract metadata from nodes."""
        pass

    async def aextract(self, nodes: List[TextNode]) -> List[Dict[str, Any]]:
        """Async extraction (default: runs sync)."""
        return self.extract(nodes)


class TitleExtractor(BaseExtractor):
    """
    Extracts document titles from content.

    Useful for auto-generating titles for chunks.

    Example:
        extractor = TitleExtractor(nodes=5)
        metadata_list = extractor.extract(nodes)
    """

    def __init__(
        self,
        nodes: int = 5,
        node_template: Optional[str] = None,
        combine_template: Optional[str] = None,
    ):
        self.nodes = nodes
        self.node_template = node_template or "Generate a title for: {context}"
        self.combine_template = combine_template

    def _extract_title(self, text: str) -> str:
        """Extract/generate title from text."""
        # Try to find existing title (first line or header)
        lines = text.strip().split("\n")
        first_line = lines[0].strip() if lines else ""

        # Check for markdown header
        if first_line.startswith("#"):
            return first_line.lstrip("#").strip()

        # Check if first line looks like a title (short, no period)
        if len(first_line) < 100 and not first_line.endswith("."):
            return first_line

        # Generate title from first few words
        words = text.split()[:10]
        return " ".join(words) + "..."

    def extract(self, nodes: List[TextNode]) -> List[Dict[str, Any]]:
        """Extract titles for nodes."""
        metadata_list = []

        for i, node in enumerate(nodes[: self.nodes]):
            title = self._extract_title(node.text)
            metadata_list.append({"document_title": title, "node_index": i})

        # Pad remaining nodes with empty metadata
        for _ in range(len(nodes) - len(metadata_list)):
            metadata_list.append({})

        return metadata_list


class QuestionsAnsweredExtractor(BaseExtractor):
    """
    Extracts questions that a node can answer.

    Useful for question-answering retrieval optimization.

    Example:
        extractor = QuestionsAnsweredExtractor(questions=3)
        metadata_list = extractor.extract(nodes)
    """

    def __init__(
        self,
        questions: int = 3,
        prompt_template: Optional[str] = None,
    ):
        self.questions = questions
        self.prompt_template = prompt_template

    def _generate_questions(self, text: str) -> List[str]:
        """Generate questions that this text could answer."""
        # Simple heuristic-based question generation
        questions = []

        # Extract key phrases/topics
        sentences = text.split(".")
        for sent in sentences[:3]:
            sent = sent.strip()
            if len(sent) > 20:
                # Convert statement to question
                if sent.lower().startswith(("the ", "a ", "an ")):
                    questions.append(f"What is {sent.lower()[4:]}?")
                else:
                    questions.append(f"What about {sent.lower()}?")

                if len(questions) >= self.questions:
                    break

        return questions

    def extract(self, nodes: List[TextNode]) -> List[Dict[str, Any]]:
        """Extract answerable questions for nodes."""
        metadata_list = []

        for node in nodes:
            questions = self._generate_questions(node.text)
            metadata_list.append({"questions_this_excerpt_can_answer": questions})

        return metadata_list


class SummaryExtractor(BaseExtractor):
    """
    Extracts summaries of document sections.

    Example:
        extractor = SummaryExtractor(summaries=["self", "prev", "next"])
        metadata_list = extractor.extract(nodes)
    """

    def __init__(
        self,
        summaries: List[str] = None,
        prompt_template: Optional[str] = None,
    ):
        self.summaries = summaries or ["self"]
        self.prompt_template = prompt_template

    def _summarize(self, text: str, max_length: int = 100) -> str:
        """Create a brief summary of text."""
        words = text.split()
        if len(words) <= max_length // 4:
            return text

        # Take first portion
        summary_words = words[: max_length // 4]
        return " ".join(summary_words) + "..."

    def extract(self, nodes: List[TextNode]) -> List[Dict[str, Any]]:
        """Extract summaries for nodes."""
        metadata_list = []

        for i, node in enumerate(nodes):
            meta = {}

            if "self" in self.summaries:
                meta["section_summary"] = self._summarize(node.text)

            if "prev" in self.summaries and i > 0:
                meta["prev_section_summary"] = self._summarize(nodes[i - 1].text)

            if "next" in self.summaries and i < len(nodes) - 1:
                meta["next_section_summary"] = self._summarize(nodes[i + 1].text)

            metadata_list.append(meta)

        return metadata_list


class KeywordExtractor(BaseExtractor):
    """
    Extracts keywords from document content.

    Example:
        extractor = KeywordExtractor(keywords=5)
        metadata_list = extractor.extract(nodes)
    """

    def __init__(
        self,
        keywords: int = 5,
        prompt_template: Optional[str] = None,
    ):
        self.keywords = keywords
        self.prompt_template = prompt_template
        self._stopwords = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "must", "shall",
            "can", "need", "dare", "ought", "used", "to", "of", "in",
            "for", "on", "with", "at", "by", "from", "as", "into",
            "through", "during", "before", "after", "above", "below",
            "between", "under", "again", "further", "then", "once",
            "and", "but", "or", "nor", "so", "yet", "both", "either",
            "neither", "not", "only", "same", "than", "too", "very",
            "just", "also", "now", "here", "there", "when", "where",
            "why", "how", "all", "each", "every", "both", "few", "more",
            "most", "other", "some", "such", "no", "any", "this", "that",
        }

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text using simple frequency analysis."""
        # Tokenize and clean
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

        # Filter stopwords and count
        word_counts: Dict[str, int] = {}
        for word in words:
            if word not in self._stopwords:
                word_counts[word] = word_counts.get(word, 0) + 1

        # Get top keywords
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[: self.keywords]]

    def extract(self, nodes: List[TextNode]) -> List[Dict[str, Any]]:
        """Extract keywords for nodes."""
        metadata_list = []

        for node in nodes:
            keywords = self._extract_keywords(node.text)
            metadata_list.append({"excerpt_keywords": keywords})

        return metadata_list


class IngestionPipeline:
    """
    LlamaIndex-compatible ingestion pipeline.

    Chains transformations: parsing, extraction, embedding.

    Example:
        pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(chunk_size=512),
                TitleExtractor(),
                KeywordExtractor(),
            ]
        )
        nodes = pipeline.run(documents=documents)
    """

    def __init__(
        self,
        transformations: Optional[List[Union[BaseNodeParser, BaseExtractor]]] = None,
        documents: Optional[List[TextNode]] = None,
    ):
        self.transformations = transformations or []
        self.documents = documents or []

    def run(
        self,
        documents: Optional[List[TextNode]] = None,
        show_progress: bool = True,
        **kwargs: Any,
    ) -> List[TextNode]:
        """Run the ingestion pipeline."""
        docs = documents or self.documents
        nodes = list(docs)  # Copy

        for transform in self.transformations:
            if isinstance(transform, BaseNodeParser):
                nodes = transform.get_nodes_from_documents(nodes, show_progress)
            elif isinstance(transform, BaseExtractor):
                metadata_list = transform.extract(nodes)
                for node, meta in zip(nodes, metadata_list):
                    node.metadata.update(meta)

        return nodes


# ============================================================================
# Composable Indices (LlamaIndex-compatible)
# ============================================================================


@dataclass
class IndexNode(TextNode):
    """
    A node that references an index for composability.

    Used in ComposableGraph to create hierarchical index structures.
    """

    index_id: Optional[str] = None
    obj: Optional[Any] = None  # Reference to actual index


class ComposableGraph:
    """
    LlamaIndex-compatible composable graph for multi-index queries.

    Allows building hierarchical index structures where queries can
    be routed to appropriate sub-indices.

    Example:
        # Create sub-indices
        finance_index = AgenticIndex.from_documents(finance_docs)
        tech_index = AgenticIndex.from_documents(tech_docs)

        # Create composable graph
        graph = ComposableGraph.from_indices(
            root_index=AgenticIndex,
            children_indices=[finance_index, tech_index],
            index_summaries=["Financial documents", "Technical documents"],
        )

        # Query across all indices
        query_engine = graph.as_query_engine()
        response = query_engine.query("What are the Q4 revenues?")
    """

    def __init__(
        self,
        root_index: BaseIndex,
        children_indices: Optional[Dict[str, BaseIndex]] = None,
        index_summaries: Optional[Dict[str, str]] = None,
    ):
        self.root_index = root_index
        self.children_indices = children_indices or {}
        self.index_summaries = index_summaries or {}

    @classmethod
    def from_indices(
        cls,
        root_index: type,
        children_indices: List[BaseIndex],
        index_summaries: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> "ComposableGraph":
        """
        Create composable graph from multiple indices.

        Args:
            root_index: Root index class to use
            children_indices: List of child indices
            index_summaries: Optional summaries for each child index
            **kwargs: Additional index configuration

        Returns:
            Configured ComposableGraph
        """
        # Create index nodes for children
        index_nodes = []
        children_dict: Dict[str, BaseIndex] = {}
        summaries_dict: Dict[str, str] = {}

        for i, child_index in enumerate(children_indices):
            index_id = f"index_{i}"
            summary = (index_summaries[i] if index_summaries else f"Index {i}")

            # Create an IndexNode representing this child
            index_node = IndexNode(
                text=summary,
                node_id=index_id,
                index_id=index_id,
                obj=child_index,
            )
            index_nodes.append(index_node)
            children_dict[index_id] = child_index
            summaries_dict[index_id] = summary

        # Create root index from the index nodes
        root = root_index.from_documents(index_nodes, show_progress=False, **kwargs)

        return cls(
            root_index=root,
            children_indices=children_dict,
            index_summaries=summaries_dict,
        )

    def as_query_engine(
        self,
        child_query_engine_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "ComposableQueryEngine":
        """Get a query engine for the composable graph."""
        return ComposableQueryEngine(
            graph=self,
            child_kwargs=child_query_engine_kwargs or {},
            **kwargs,
        )

    def as_retriever(
        self,
        **kwargs: Any,
    ) -> "ComposableRetriever":
        """Get a retriever for the composable graph."""
        return ComposableRetriever(graph=self, **kwargs)


class ComposableQueryEngine(BaseQueryEngine):
    """
    Query engine for ComposableGraph.

    Routes queries to appropriate sub-indices based on content.
    """

    def __init__(
        self,
        graph: ComposableGraph,
        child_kwargs: Optional[Dict[str, Any]] = None,
        similarity_top_k: int = 3,
    ):
        self.graph = graph
        self.child_kwargs = child_kwargs or {}
        self.similarity_top_k = similarity_top_k

    def query(self, query: str, **kwargs: Any) -> Response:
        """Query across composable graph."""
        # First, query root to find relevant indices
        root_retriever = self.graph.root_index.as_retriever(
            similarity_top_k=self.similarity_top_k
        )
        root_nodes = root_retriever.retrieve(query)

        # Collect responses from relevant children
        all_source_nodes: List[NodeWithScore] = []
        all_responses: List[str] = []

        for node in root_nodes:
            # Check if this is an IndexNode
            if isinstance(node.node, IndexNode) and node.node.index_id:
                index_id = node.node.index_id
                if index_id in self.graph.children_indices:
                    child_index = self.graph.children_indices[index_id]
                    child_engine = child_index.as_query_engine(**self.child_kwargs)
                    child_response = child_engine.query(query)

                    all_source_nodes.extend(child_response.source_nodes)
                    all_responses.append(str(child_response))
            else:
                # Regular node - include in sources
                all_source_nodes.append(node)

        # Combine responses
        if all_responses:
            combined_response = "\n\n---\n\n".join(all_responses)
        else:
            combined_response = "No relevant information found across indices."

        return Response(
            response=combined_response,
            source_nodes=all_source_nodes,
            metadata={
                "indices_queried": len(all_responses),
                "total_sources": len(all_source_nodes),
            },
        )

    async def aquery(self, query: str, **kwargs: Any) -> Response:
        """Async query (runs sync version)."""
        return self.query(query, **kwargs)


class ComposableRetriever(BaseRetriever):
    """
    Retriever for ComposableGraph.

    Retrieves from multiple indices based on content relevance.
    """

    def __init__(
        self,
        graph: ComposableGraph,
        similarity_top_k: int = 5,
    ):
        self.graph = graph
        self.similarity_top_k = similarity_top_k

    def _retrieve(self, query: str, **kwargs: Any) -> List[NodeWithScore]:
        """Retrieve from composable graph."""
        # First, query root to find relevant indices
        root_retriever = self.graph.root_index.as_retriever(
            similarity_top_k=min(3, len(self.graph.children_indices))
        )
        root_nodes = root_retriever.retrieve(query)

        # Retrieve from relevant children
        all_nodes: List[NodeWithScore] = []

        for node in root_nodes:
            if isinstance(node.node, IndexNode) and node.node.index_id:
                index_id = node.node.index_id
                if index_id in self.graph.children_indices:
                    child_index = self.graph.children_indices[index_id]
                    child_retriever = child_index.as_retriever(
                        similarity_top_k=self.similarity_top_k
                    )
                    child_nodes = child_retriever.retrieve(query)
                    all_nodes.extend(child_nodes)
            else:
                all_nodes.append(node)

        # Sort by score and limit
        all_nodes.sort(key=lambda x: x.score, reverse=True)
        return all_nodes[: self.similarity_top_k * len(self.graph.children_indices)]


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
