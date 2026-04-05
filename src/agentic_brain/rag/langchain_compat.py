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
LangChain Compatibility Layer for Agentic Brain GraphRAG.

Provides seamless integration with LangChain pipelines:
- BaseRetriever interface for use in LCEL chains
- Document format compatible with LangChain Document class
- Callback support for LangChain callback handlers
- Runnable interface for chain composition

Usage:
    from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

    # Basic usage
    retriever = AgenticBrainRetriever()
    docs = retriever.invoke("What is GraphRAG?")

    # In LCEL chain
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # With callbacks
    from langchain_core.callbacks import StdOutCallbackHandler
    docs = retriever.invoke("query", config={"callbacks": [StdOutCallbackHandler()]})
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence

logger = logging.getLogger(__name__)

# Check for LangChain availability
try:
    from langchain_core.callbacks import (
        AsyncCallbackManagerForRetrieverRun,
        CallbackManagerForRetrieverRun,
    )
    from langchain_core.documents import Document as LangChainDocument
    from langchain_core.retrievers import BaseRetriever

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    LangChainDocument = None
    BaseRetriever = object  # Fallback for type hints
    CallbackManagerForRetrieverRun = None
    AsyncCallbackManagerForRetrieverRun = None

if TYPE_CHECKING:
    from langchain_core.callbacks import (
        AsyncCallbackManagerForRetrieverRun,
        CallbackManagerForRetrieverRun,
    )
    from langchain_core.documents import Document as LangChainDocument
    from langchain_core.retrievers import BaseRetriever


from .retriever import RetrievedChunk, Retriever
from .store import Document as AgenticDocument


def _check_langchain() -> None:
    """Raise ImportError if LangChain is not available."""
    if not LANGCHAIN_AVAILABLE:
        raise ImportError(
            "LangChain is required for this feature. "
            "Install with: pip install langchain-core"
        )


def retrieved_chunk_to_langchain_document(
    chunk: RetrievedChunk,
) -> "LangChainDocument":
    """Convert an Agentic Brain RetrievedChunk to a LangChain Document.

    Args:
        chunk: The RetrievedChunk from Agentic Brain retrieval.

    Returns:
        LangChainDocument: A LangChain-compatible Document object.

    Example:
        >>> chunk = RetrievedChunk(content="Hello", source="test.md", score=0.9)
        >>> doc = retrieved_chunk_to_langchain_document(chunk)
        >>> doc.page_content
        'Hello'
    """
    _check_langchain()
    from langchain_core.documents import Document as LCDocument

    metadata = {
        "source": chunk.source,
        "score": chunk.score,
        "confidence": chunk.confidence,
        **chunk.metadata,
    }
    return LCDocument(page_content=chunk.content, metadata=metadata)


def agentic_document_to_langchain_document(
    doc: AgenticDocument,
) -> "LangChainDocument":
    """Convert an Agentic Brain Document to a LangChain Document.

    Args:
        doc: The Agentic Brain Document object.

    Returns:
        LangChainDocument: A LangChain-compatible Document object.

    Example:
        >>> doc = AgenticDocument(id="1", content="Hello world")
        >>> lc_doc = agentic_document_to_langchain_document(doc)
        >>> lc_doc.page_content
        'Hello world'
    """
    _check_langchain()
    from langchain_core.documents import Document as LCDocument

    metadata = {
        "id": doc.id,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        **doc.metadata,
    }
    return LCDocument(page_content=doc.content, metadata=metadata)


def langchain_document_to_agentic_document(
    doc: "LangChainDocument",
    doc_id: Optional[str] = None,
) -> AgenticDocument:
    """Convert a LangChain Document to an Agentic Brain Document.

    Args:
        doc: The LangChain Document object.
        doc_id: Optional document ID. If not provided, uses metadata['id']
                or generates from content hash.

    Returns:
        AgenticDocument: An Agentic Brain Document object.

    Example:
        >>> from langchain_core.documents import Document
        >>> lc_doc = Document(page_content="Hello", metadata={"id": "doc1"})
        >>> doc = langchain_document_to_agentic_document(lc_doc)
        >>> doc.id
        'doc1'
    """
    import hashlib

    metadata = dict(doc.metadata) if doc.metadata else {}
    if doc_id is None:
        doc_id = metadata.pop("id", None)
    if doc_id is None:
        doc_id = hashlib.sha256(doc.page_content.encode()).hexdigest()[:16]

    return AgenticDocument(
        id=doc_id,
        content=doc.page_content,
        metadata=metadata,
    )


class AgenticBrainRetriever(BaseRetriever if LANGCHAIN_AVAILABLE else object):
    """LangChain-compatible retriever wrapping Agentic Brain GraphRAG.

    This retriever implements the LangChain BaseRetriever interface,
    allowing it to be used seamlessly in LCEL chains and other
    LangChain constructs.

    Attributes:
        retriever: The underlying Agentic Brain Retriever instance.
        k: Default number of documents to retrieve.
        min_score: Minimum relevance score threshold.
        sources: Neo4j labels to query during retrieval.

    Example:
        # Basic usage
        >>> retriever = AgenticBrainRetriever(k=5)
        >>> docs = retriever.invoke("What is RAG?")

        # In LCEL chain
        >>> from langchain_core.runnables import RunnablePassthrough
        >>> chain = {"context": retriever} | prompt | llm

        # With custom retriever
        >>> custom_retriever = Retriever(neo4j_uri="bolt://custom:7687")
        >>> lc_retriever = AgenticBrainRetriever(retriever=custom_retriever)
    """

    # Pydantic fields for LangChain compatibility
    retriever: Optional[Retriever] = None
    k: int = 5
    min_score: float = 0.3
    sources: Optional[list[str]] = None
    _retriever_instance: Optional[Retriever] = None

    class Config:
        """Pydantic config for arbitrary types."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        k: int = 5,
        min_score: float = 0.3,
        sources: Optional[list[str]] = None,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the LangChain-compatible retriever.

        Args:
            retriever: Pre-configured Agentic Brain Retriever. If not provided,
                      a new one will be created.
            k: Default number of documents to retrieve.
            min_score: Minimum relevance score threshold.
            sources: Neo4j labels to query during retrieval.
            neo4j_uri: Neo4j connection URI (if creating new retriever).
            neo4j_user: Neo4j username (if creating new retriever).
            neo4j_password: Neo4j password (if creating new retriever).
            **kwargs: Additional arguments passed to parent class.
        """
        _check_langchain()
        super().__init__(**kwargs)

        self.k = k
        self.min_score = min_score
        self.sources = sources

        if retriever is not None:
            self._retriever_instance = retriever
        else:
            self._retriever_instance = Retriever(
                neo4j_uri=neo4j_uri,
                neo4j_user=neo4j_user,
                neo4j_password=neo4j_password,
                sources=sources,
            )

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional["CallbackManagerForRetrieverRun"] = None,
    ) -> list["LangChainDocument"]:
        """Retrieve relevant documents for a query.

        This is the core method required by LangChain's BaseRetriever.

        Args:
            query: The search query string.
            run_manager: Optional callback manager for event tracking.

        Returns:
            list[LangChainDocument]: List of relevant documents.
        """
        try:
            chunks = self._retriever_instance.search(
                query=query,
                k=self.k,
                sources=self.sources,
            )

            # Filter by minimum score
            chunks = [c for c in chunks if c.score >= self.min_score]

            # Convert to LangChain documents
            docs = [retrieved_chunk_to_langchain_document(c) for c in chunks]

            return docs

        except Exception as e:
            if run_manager:
                run_manager.on_retriever_error(e)
            raise

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional["AsyncCallbackManagerForRetrieverRun"] = None,
    ) -> list["LangChainDocument"]:
        """Async version of document retrieval.

        Args:
            query: The search query string.
            run_manager: Optional async callback manager.

        Returns:
            list[LangChainDocument]: List of relevant documents.
        """
        # Run sync retrieval in thread pool for now
        # Future: implement true async when Retriever supports it
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._get_relevant_documents(query, run_manager=None),
        )

    def with_config(
        self,
        k: Optional[int] = None,
        min_score: Optional[float] = None,
        sources: Optional[list[str]] = None,
    ) -> "AgenticBrainRetriever":
        """Return a new retriever with updated configuration.

        Args:
            k: New number of documents to retrieve.
            min_score: New minimum score threshold.
            sources: New source labels.

        Returns:
            AgenticBrainRetriever: New retriever with updated config.

        Example:
            >>> retriever = AgenticBrainRetriever(k=5)
            >>> specific_retriever = retriever.with_config(k=10, min_score=0.5)
        """
        return AgenticBrainRetriever(
            retriever=self._retriever_instance,
            k=k if k is not None else self.k,
            min_score=min_score if min_score is not None else self.min_score,
            sources=sources if sources is not None else self.sources,
        )


class GraphRAGRetriever(BaseRetriever if LANGCHAIN_AVAILABLE else object):
    """LangChain-compatible retriever using GraphRAG with community detection.

    This retriever wraps the advanced GraphRAG system, providing access to
    community-aware retrieval, multi-hop reasoning, and hybrid search
    through the LangChain interface.

    Attributes:
        graph_rag: The underlying GraphRAG instance.
        search_strategy: Strategy for retrieval (vector, graph, hybrid, community).
        k: Default number of documents to retrieve.

    Example:
        >>> from agentic_brain.rag.graph_rag import GraphRAG, SearchStrategy
        >>> rag = GraphRAG()
        >>> retriever = GraphRAGRetriever(graph_rag=rag, search_strategy=SearchStrategy.HYBRID)
        >>> docs = retriever.invoke("How do communities relate?")
    """

    graph_rag: Optional[Any] = None  # GraphRAG type
    search_strategy: str = "hybrid"
    k: int = 5
    include_communities: bool = True
    _graph_rag_instance: Optional[Any] = None

    class Config:
        """Pydantic config for arbitrary types."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        graph_rag: Optional[Any] = None,
        search_strategy: str = "hybrid",
        k: int = 5,
        include_communities: bool = True,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the GraphRAG retriever.

        Args:
            graph_rag: Pre-configured GraphRAG instance.
            search_strategy: One of 'vector', 'graph', 'hybrid', 'community'.
            k: Number of documents to retrieve.
            include_communities: Whether to include community context.
            neo4j_uri: Neo4j connection URI (if creating new GraphRAG).
            neo4j_user: Neo4j username.
            neo4j_password: Neo4j password.
            **kwargs: Additional arguments for parent class.
        """
        _check_langchain()
        super().__init__(**kwargs)

        self.search_strategy = search_strategy
        self.k = k
        self.include_communities = include_communities

        if graph_rag is not None:
            self._graph_rag_instance = graph_rag
        else:
            # Lazy import to avoid circular dependencies
            from .graph_rag import GraphRAG, GraphRAGConfig

            config = GraphRAGConfig(
                neo4j_uri=neo4j_uri or "bolt://localhost:7687",
                neo4j_user=neo4j_user,
                neo4j_password=neo4j_password,
                enable_communities=include_communities,
            )
            self._graph_rag_instance = GraphRAG(config)

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional["CallbackManagerForRetrieverRun"] = None,
    ) -> list["LangChainDocument"]:
        """Retrieve documents using GraphRAG.

        Args:
            query: The search query.
            run_manager: Optional callback manager.

        Returns:
            list[LangChainDocument]: Retrieved documents with graph context.
        """
        from langchain_core.documents import Document as LCDocument

        try:
            # Import SearchStrategy for conversion
            from .graph_rag import SearchStrategy

            strategy = SearchStrategy(self.search_strategy)

            # Perform search (sync wrapper for now)
            loop = asyncio.new_event_loop()
            try:
                results = loop.run_until_complete(
                    self._graph_rag_instance.search(
                        query=query,
                        strategy=strategy,
                        limit=self.k,
                    )
                )
            finally:
                loop.close()

            # Convert results to LangChain documents
            docs = []
            for result in results:
                metadata = {
                    "score": getattr(result, "score", 0.0),
                    "source": getattr(result, "source", "graphrag"),
                    "node_id": getattr(result, "node_id", None),
                    "community_id": getattr(result, "community_id", None),
                    "relationships": getattr(result, "relationships", []),
                }
                content = getattr(result, "content", str(result))
                docs.append(LCDocument(page_content=content, metadata=metadata))

            return docs

        except Exception as e:
            if run_manager:
                run_manager.on_retriever_error(e)
            raise

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional["AsyncCallbackManagerForRetrieverRun"] = None,
    ) -> list["LangChainDocument"]:
        """Async document retrieval using GraphRAG.

        Args:
            query: The search query.
            run_manager: Optional async callback manager.

        Returns:
            list[LangChainDocument]: Retrieved documents.
        """
        from langchain_core.documents import Document as LCDocument
        from .graph_rag import SearchStrategy

        strategy = SearchStrategy(self.search_strategy)

        results = await self._graph_rag_instance.search(
            query=query,
            strategy=strategy,
            limit=self.k,
        )

        docs = []
        for result in results:
            metadata = {
                "score": getattr(result, "score", 0.0),
                "source": getattr(result, "source", "graphrag"),
                "node_id": getattr(result, "node_id", None),
                "community_id": getattr(result, "community_id", None),
            }
            content = getattr(result, "content", str(result))
            docs.append(LCDocument(page_content=content, metadata=metadata))

        return docs


class DocumentStoreRetriever(BaseRetriever if LANGCHAIN_AVAILABLE else object):
    """LangChain retriever backed by Agentic Brain DocumentStore.

    This retriever allows using InMemoryDocumentStore or FileDocumentStore
    as a LangChain retriever, enabling local document search in LCEL chains.

    Attributes:
        store: The underlying DocumentStore.
        k: Number of documents to retrieve.

    Example:
        >>> from agentic_brain.rag.store import InMemoryDocumentStore
        >>> store = InMemoryDocumentStore()
        >>> store.add("RAG stands for Retrieval-Augmented Generation")
        >>> retriever = DocumentStoreRetriever(store=store)
        >>> docs = retriever.invoke("What is RAG?")
    """

    store: Optional[Any] = None  # DocumentStore type
    k: int = 5
    _store_instance: Optional[Any] = None

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True

    def __init__(
        self,
        store: Optional[Any] = None,
        k: int = 5,
        **kwargs: Any,
    ) -> None:
        """Initialize the DocumentStore retriever.

        Args:
            store: The DocumentStore instance to use.
            k: Number of documents to retrieve.
            **kwargs: Additional arguments for parent class.
        """
        _check_langchain()
        super().__init__(**kwargs)

        self.k = k
        if store is not None:
            self._store_instance = store
        else:
            from .store import InMemoryDocumentStore

            self._store_instance = InMemoryDocumentStore()

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional["CallbackManagerForRetrieverRun"] = None,
    ) -> list["LangChainDocument"]:
        """Retrieve documents from the store.

        Args:
            query: The search query.
            run_manager: Optional callback manager.

        Returns:
            list[LangChainDocument]: Matching documents.
        """
        try:
            results = self._store_instance.search(query, top_k=self.k)
            docs = [agentic_document_to_langchain_document(doc) for doc in results]

            return docs

        except Exception as e:
            if run_manager:
                run_manager.on_retriever_error(e)
            raise

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: Optional["AsyncCallbackManagerForRetrieverRun"] = None,
    ) -> list["LangChainDocument"]:
        """Async retrieval (runs sync in executor)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._get_relevant_documents(query, run_manager=None),
        )

    def add_documents(self, documents: Sequence["LangChainDocument"]) -> list[str]:
        """Add LangChain documents to the store.

        Args:
            documents: Sequence of LangChain documents to add.

        Returns:
            list[str]: IDs of added documents.
        """
        ids = []
        for doc in documents:
            agentic_doc = langchain_document_to_agentic_document(doc)
            stored = self._store_instance.add(agentic_doc)
            ids.append(stored.id)
        return ids


# Callback adapter for custom monitoring
class AgenticBrainCallbackAdapter:
    """Adapter to bridge LangChain callbacks with Agentic Brain events.

    This adapter allows Agentic Brain retrieval operations to emit
    events through LangChain's callback system, enabling integration
    with LangSmith, custom loggers, and other monitoring tools.

    Example:
        >>> from langchain_core.callbacks import StdOutCallbackHandler
        >>> adapter = AgenticBrainCallbackAdapter([StdOutCallbackHandler()])
        >>> adapter.on_retrieval_start("What is RAG?")
        >>> adapter.on_retrieval_end([doc1, doc2])
    """

    def __init__(self, callbacks: Optional[list[Any]] = None) -> None:
        """Initialize the callback adapter.

        Args:
            callbacks: List of LangChain callback handlers.
        """
        self.callbacks = callbacks or []

    def on_retrieval_start(
        self,
        query: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit retrieval start event to all callbacks.

        Args:
            query: The retrieval query.
            metadata: Optional metadata about the retrieval.
        """
        for callback in self.callbacks:
            if hasattr(callback, "on_retriever_start"):
                callback.on_retriever_start(
                    serialized=metadata or {},
                    query=query,
                )

    def on_retrieval_end(
        self,
        documents: list["LangChainDocument"],
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit retrieval end event to all callbacks.

        Args:
            documents: Retrieved documents.
            metadata: Optional metadata about the retrieval.
        """
        for callback in self.callbacks:
            if hasattr(callback, "on_retriever_end"):
                callback.on_retriever_end(documents)

    def on_retrieval_error(
        self,
        error: Exception,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emit retrieval error event to all callbacks.

        Args:
            error: The exception that occurred.
            metadata: Optional metadata about the error.
        """
        for callback in self.callbacks:
            if hasattr(callback, "on_retriever_error"):
                callback.on_retriever_error(error)


# Factory function for easy creation
def create_langchain_retriever(
    retriever_type: str = "basic",
    **kwargs: Any,
) -> BaseRetriever:
    """Factory function to create LangChain-compatible retrievers.

    Args:
        retriever_type: Type of retriever ('basic', 'graphrag', 'store').
        **kwargs: Arguments passed to the retriever constructor.

    Returns:
        BaseRetriever: A LangChain-compatible retriever.

    Example:
        >>> retriever = create_langchain_retriever("basic", k=10)
        >>> graphrag_retriever = create_langchain_retriever(
        ...     "graphrag",
        ...     search_strategy="community"
        ... )
    """
    _check_langchain()

    if retriever_type == "basic":
        return AgenticBrainRetriever(**kwargs)
    elif retriever_type == "graphrag":
        return GraphRAGRetriever(**kwargs)
    elif retriever_type == "store":
        return DocumentStoreRetriever(**kwargs)
    else:
        raise ValueError(
            f"Unknown retriever type: {retriever_type}. "
            "Choose from: 'basic', 'graphrag', 'store'"
        )


__all__ = [
    # Availability flag
    "LANGCHAIN_AVAILABLE",
    # Retrievers
    "AgenticBrainRetriever",
    "GraphRAGRetriever",
    "DocumentStoreRetriever",
    # Conversion utilities
    "retrieved_chunk_to_langchain_document",
    "agentic_document_to_langchain_document",
    "langchain_document_to_agentic_document",
    # Callback adapter
    "AgenticBrainCallbackAdapter",
    # Factory
    "create_langchain_retriever",
]
