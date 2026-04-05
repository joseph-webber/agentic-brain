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
- LCEL Runnables (RunnablePassthrough, RunnableLambda, RunnableParallel)
- Memory classes (ConversationBufferMemory, ConversationSummaryMemory, etc.)
- Document loaders (TextLoader, DirectoryLoader, UnstructuredFileLoader)
- Text splitters (RecursiveCharacterTextSplitter, TokenTextSplitter)
- Output parsers (StrOutputParser, JsonOutputParser, PydanticOutputParser)
- Chains (RetrievalQA, ConversationalRetrievalChain)
- Callbacks (BaseCallbackHandler, AsyncCallbackHandler, tracing)

Usage:
    from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

    # Basic usage
    retriever = AgenticBrainRetriever()
    docs = retriever.invoke("What is GraphRAG?")

    # In LCEL chain with pipe operator
    from agentic_brain.rag.langchain_compat import (
        RunnablePassthrough, RunnableLambda, RunnableParallel, StrOutputParser
    )

    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # With memory
    from agentic_brain.rag.langchain_compat import ConversationBufferMemory
    memory = ConversationBufferMemory()
    memory.add_user_message("What is RAG?")
    memory.add_ai_message("RAG stands for Retrieval-Augmented Generation...")

    # With text splitting
    from agentic_brain.rag.langchain_compat import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(long_document)

    # With callbacks
    from agentic_brain.rag.langchain_compat import TracingCallbackHandler
    docs = retriever.invoke("query", config={"callbacks": [TracingCallbackHandler()]})
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    Type,
    TypeVar,
    Union,
)

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


# =============================================================================
# LCEL RUNNABLES - Full LangChain Expression Language Support
# =============================================================================

# Type variables for generics
Input = TypeVar("Input")
Output = TypeVar("Output")
Other = TypeVar("Other")


class Runnable(ABC, Generic[Input, Output]):
    """Abstract base class for LCEL Runnables.

    Provides the core interface for composable chain components that support:
    - Pipe operator (|) for chaining
    - invoke() for sync execution
    - ainvoke() for async execution
    - batch() for parallel processing
    - stream() for streaming output

    Example:
        >>> class MyRunnable(Runnable[str, str]):
        ...     def invoke(self, input: str, config=None) -> str:
        ...         return input.upper()
        >>> r = MyRunnable()
        >>> r.invoke("hello")
        'HELLO'
    """

    @abstractmethod
    def invoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Synchronously invoke the runnable.

        Args:
            input: The input to process.
            config: Optional configuration dict with callbacks, tags, etc.

        Returns:
            The output of processing.
        """
        pass

    async def ainvoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Asynchronously invoke the runnable.

        Default implementation runs invoke() in a thread pool.

        Args:
            input: The input to process.
            config: Optional configuration dict.

        Returns:
            The output of processing.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.invoke(input, config))

    def batch(
        self,
        inputs: List[Input],
        config: Optional[Dict[str, Any]] = None,
        *,
        max_concurrency: Optional[int] = None,
    ) -> List[Output]:
        """Process multiple inputs in parallel.

        Args:
            inputs: List of inputs to process.
            config: Optional configuration dict.
            max_concurrency: Maximum number of concurrent executions.

        Returns:
            List of outputs, one per input.

        Example:
            >>> runnable.batch(["a", "b", "c"])
            ['A', 'B', 'C']
        """
        max_workers = max_concurrency or min(len(inputs), 10)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(lambda x: self.invoke(x, config), inputs))

    async def abatch(
        self,
        inputs: List[Input],
        config: Optional[Dict[str, Any]] = None,
        *,
        max_concurrency: Optional[int] = None,
    ) -> List[Output]:
        """Asynchronously process multiple inputs.

        Args:
            inputs: List of inputs to process.
            config: Optional configuration dict.
            max_concurrency: Maximum concurrent tasks.

        Returns:
            List of outputs.
        """
        semaphore = asyncio.Semaphore(max_concurrency or 10)

        async def bounded_invoke(x: Input) -> Output:
            async with semaphore:
                return await self.ainvoke(x, config)

        return await asyncio.gather(*[bounded_invoke(x) for x in inputs])

    def stream(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Iterator[Output]:
        """Stream output chunks.

        Default implementation yields single complete output.

        Args:
            input: The input to process.
            config: Optional configuration.

        Yields:
            Output chunks.
        """
        yield self.invoke(input, config)

    def __or__(self, other: "Runnable[Output, Other]") -> "RunnableSequence[Input, Other]":
        """Compose with another runnable using pipe operator.

        Args:
            other: The runnable to pipe output to.

        Returns:
            A new RunnableSequence that chains self -> other.

        Example:
            >>> chain = runnable1 | runnable2 | runnable3
        """
        return RunnableSequence(first=self, last=other)

    def __ror__(self, other: Any) -> "RunnableSequence":
        """Support piping from non-Runnable objects."""
        if isinstance(other, dict):
            return RunnableParallel(other) | self
        return NotImplemented

    def bind(self, **kwargs: Any) -> "RunnableBinding[Input, Output]":
        """Bind arguments to this runnable.

        Args:
            **kwargs: Arguments to bind.

        Returns:
            A RunnableBinding with bound arguments.
        """
        return RunnableBinding(bound=self, kwargs=kwargs)

    def with_config(
        self,
        config: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "RunnableBinding[Input, Output]":
        """Return runnable with updated configuration.

        Args:
            config: Configuration dict to merge.
            **kwargs: Additional config key-value pairs.

        Returns:
            A RunnableBinding with the config.
        """
        merged = {**(config or {}), **kwargs}
        return RunnableBinding(bound=self, config=merged)


class RunnableSequence(Runnable[Input, Output]):
    """A sequence of runnables executed in order.

    The output of each step is passed as input to the next.

    Example:
        >>> seq = RunnableSequence(
        ...     first=RunnableLambda(lambda x: x + "!"),
        ...     last=RunnableLambda(lambda x: x.upper())
        ... )
        >>> seq.invoke("hello")
        'HELLO!'
    """

    def __init__(
        self,
        first: Runnable,
        last: Runnable,
        middle: Optional[List[Runnable]] = None,
    ):
        """Initialize the sequence.

        Args:
            first: First runnable in the sequence.
            last: Last runnable in the sequence.
            middle: Optional list of middle runnables.
        """
        self.first = first
        self.middle = middle or []
        self.last = last

    @property
    def steps(self) -> List[Runnable]:
        """Get all steps in order."""
        return [self.first] + self.middle + [self.last]

    def invoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Execute all steps in sequence."""
        result = input
        for step in self.steps:
            result = step.invoke(result, config)
        return result

    async def ainvoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Async execute all steps in sequence."""
        result = input
        for step in self.steps:
            result = await step.ainvoke(result, config)
        return result

    def __or__(self, other: Runnable) -> "RunnableSequence":
        """Extend the sequence with another runnable."""
        return RunnableSequence(
            first=self.first,
            middle=self.middle + [self.last],
            last=other,
        )


class RunnableLambda(Runnable[Input, Output]):
    """Wrap a callable as a Runnable.

    Allows using plain functions in LCEL chains.

    Example:
        >>> upper = RunnableLambda(lambda x: x.upper())
        >>> upper.invoke("hello")
        'HELLO'

        >>> chain = retriever | RunnableLambda(lambda docs: docs[0].page_content)
    """

    def __init__(
        self,
        func: Callable[[Input], Output],
        afunc: Optional[Callable[[Input], Output]] = None,
        name: Optional[str] = None,
    ):
        """Initialize with a callable.

        Args:
            func: Sync callable to wrap.
            afunc: Optional async callable for ainvoke().
            name: Optional name for debugging.
        """
        self.func = func
        self.afunc = afunc
        self.name = name or getattr(func, "__name__", "lambda")

    def invoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Execute the wrapped function."""
        return self.func(input)

    async def ainvoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Execute async function or run sync in thread pool."""
        if self.afunc:
            return await self.afunc(input)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.func(input))


class RunnablePassthrough(Runnable[Input, Input]):
    """Pass input through unchanged.

    Useful in dict compositions to include the original input.

    Example:
        >>> chain = {"context": retriever, "question": RunnablePassthrough()}
        >>> result = chain["question"].invoke("What is RAG?")
        >>> result
        'What is RAG?'
    """

    def __init__(self, func: Optional[Callable[[Input], Any]] = None):
        """Initialize passthrough.

        Args:
            func: Optional function to call with input (input still passed through).
        """
        self.func = func

    def invoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Input:
        """Return input unchanged, optionally calling func as side effect."""
        if self.func:
            self.func(input)
        return input

    @classmethod
    def assign(cls, **kwargs: Runnable) -> "RunnableAssign":
        """Create a RunnableAssign that adds keys to input dict.

        Args:
            **kwargs: Runnables whose outputs become new dict keys.

        Returns:
            A RunnableAssign instance.

        Example:
            >>> assign = RunnablePassthrough.assign(context=retriever)
            >>> result = assign.invoke({"question": "What is RAG?"})
            >>> "context" in result
            True
        """
        return RunnableAssign(mapper=kwargs)


class RunnableAssign(Runnable[Dict[str, Any], Dict[str, Any]]):
    """Add new keys to input dict by running runnables.

    Example:
        >>> assign = RunnableAssign(mapper={"upper": RunnableLambda(lambda x: x["text"].upper())})
        >>> result = assign.invoke({"text": "hello"})
        >>> result["upper"]
        'HELLO'
    """

    def __init__(self, mapper: Dict[str, Runnable]):
        """Initialize with key-runnable mapping.

        Args:
            mapper: Dict mapping output keys to runnables.
        """
        self.mapper = mapper

    def invoke(
        self, input: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute all mapped runnables and merge with input."""
        result = dict(input)
        for key, runnable in self.mapper.items():
            result[key] = runnable.invoke(input, config)
        return result

    async def ainvoke(
        self, input: Dict[str, Any], config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Async execute all mapped runnables."""
        result = dict(input)
        tasks = {
            key: runnable.ainvoke(input, config)
            for key, runnable in self.mapper.items()
        }
        for key, task in tasks.items():
            result[key] = await task
        return result


class RunnableParallel(Runnable[Input, Dict[str, Any]]):
    """Run multiple runnables in parallel and combine results.

    Each runnable receives the same input, and outputs are combined into a dict.

    Example:
        >>> parallel = RunnableParallel({
        ...     "upper": RunnableLambda(lambda x: x.upper()),
        ...     "lower": RunnableLambda(lambda x: x.lower()),
        ...     "original": RunnablePassthrough(),
        ... })
        >>> result = parallel.invoke("Hello")
        >>> result
        {'upper': 'HELLO', 'lower': 'hello', 'original': 'Hello'}
    """

    def __init__(
        self,
        steps: Optional[Dict[str, Runnable]] = None,
        **kwargs: Runnable,
    ):
        """Initialize with dict of runnables.

        Args:
            steps: Dict mapping output keys to runnables.
            **kwargs: Additional key-runnable pairs.
        """
        self.steps = {**(steps or {}), **kwargs}

    def invoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute all runnables in parallel and combine results."""
        with ThreadPoolExecutor(max_workers=len(self.steps)) as executor:
            futures = {
                key: executor.submit(runnable.invoke, input, config)
                for key, runnable in self.steps.items()
            }
            return {key: future.result() for key, future in futures.items()}

    async def ainvoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Async execute all runnables in parallel."""
        tasks = {
            key: runnable.ainvoke(input, config)
            for key, runnable in self.steps.items()
        }
        return {key: await task for key, task in tasks.items()}


class RunnableBinding(Runnable[Input, Output]):
    """Runnable with bound arguments or configuration.

    Example:
        >>> runnable = SomeRunnable()
        >>> bound = runnable.bind(temperature=0.5)
        >>> bound.invoke(input)  # uses temperature=0.5
    """

    def __init__(
        self,
        bound: Runnable[Input, Output],
        kwargs: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        """Initialize binding.

        Args:
            bound: The wrapped runnable.
            kwargs: Arguments to pass to invoke.
            config: Configuration to merge.
        """
        self.bound = bound
        self.kwargs = kwargs or {}
        self.config = config or {}

    def invoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Execute with bound arguments."""
        merged_config = {**self.config, **(config or {})}
        return self.bound.invoke(input, merged_config)

    async def ainvoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Async execute with bound arguments."""
        merged_config = {**self.config, **(config or {})}
        return await self.bound.ainvoke(input, merged_config)


class RunnableBranch(Runnable[Input, Output]):
    """Conditionally route to different runnables based on input.

    Example:
        >>> branch = RunnableBranch(
        ...     (lambda x: x.startswith("hi"), RunnableLambda(lambda x: "greeting")),
        ...     (lambda x: x.startswith("bye"), RunnableLambda(lambda x: "farewell")),
        ...     RunnableLambda(lambda x: "unknown"),  # default
        ... )
        >>> branch.invoke("hi there")
        'greeting'
    """

    def __init__(
        self,
        *branches: Union[
            tuple[Callable[[Input], bool], Runnable[Input, Output]],
            Runnable[Input, Output],
        ],
    ):
        """Initialize with condition-runnable pairs and optional default.

        Args:
            *branches: Tuples of (condition, runnable) followed by optional default.
        """
        self.branches: List[tuple[Callable, Runnable]] = []
        self.default: Optional[Runnable] = None

        for branch in branches:
            if isinstance(branch, tuple):
                condition, runnable = branch
                self.branches.append((condition, runnable))
            else:
                self.default = branch

    def invoke(
        self, input: Input, config: Optional[Dict[str, Any]] = None
    ) -> Output:
        """Execute matching branch or default."""
        for condition, runnable in self.branches:
            if condition(input):
                return runnable.invoke(input, config)

        if self.default:
            return self.default.invoke(input, config)

        raise ValueError(f"No matching branch for input: {input}")


# =============================================================================
# MEMORY CLASSES - Conversation Memory for Chat Applications
# =============================================================================


@dataclass
class ChatMessage:
    """A single message in a conversation.

    Attributes:
        role: The role (human, ai, system).
        content: The message content.
        timestamp: When the message was created.
        metadata: Additional message metadata.
    """

    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseMemory(ABC):
    """Abstract base class for conversation memory.

    Memory classes store and retrieve conversation history for context.

    Example:
        >>> memory = ConversationBufferMemory()
        >>> memory.add_user_message("Hello!")
        >>> memory.add_ai_message("Hi there!")
        >>> memory.load_memory_variables({})
        {'history': 'Human: Hello!\\nAI: Hi there!'}
    """

    memory_key: str = "history"
    human_prefix: str = "Human"
    ai_prefix: str = "AI"
    return_messages: bool = False

    @abstractmethod
    def load_memory_variables(
        self, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Load memory variables for prompt formatting.

        Args:
            inputs: Current inputs to the chain.

        Returns:
            Dict with memory_key containing history.
        """
        pass

    @abstractmethod
    def save_context(
        self, inputs: Dict[str, Any], outputs: Dict[str, str]
    ) -> None:
        """Save context from this conversation turn.

        Args:
            inputs: The inputs to this turn.
            outputs: The outputs from this turn.
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all memory."""
        pass


class ConversationBufferMemory(BaseMemory):
    """Simple buffer memory that stores all messages.

    Keeps the full conversation history. Best for short conversations.

    Example:
        >>> memory = ConversationBufferMemory()
        >>> memory.add_user_message("What is RAG?")
        >>> memory.add_ai_message("RAG is Retrieval-Augmented Generation.")
        >>> vars = memory.load_memory_variables({})
        >>> print(vars["history"])
        Human: What is RAG?
        AI: RAG is Retrieval-Augmented Generation.
    """

    def __init__(
        self,
        memory_key: str = "history",
        human_prefix: str = "Human",
        ai_prefix: str = "AI",
        return_messages: bool = False,
        input_key: Optional[str] = None,
        output_key: Optional[str] = None,
    ):
        """Initialize buffer memory.

        Args:
            memory_key: Key to use in memory variables.
            human_prefix: Prefix for human messages.
            ai_prefix: Prefix for AI messages.
            return_messages: If True, return list of messages instead of string.
            input_key: Key for input in context dict.
            output_key: Key for output in context dict.
        """
        self.memory_key = memory_key
        self.human_prefix = human_prefix
        self.ai_prefix = ai_prefix
        self.return_messages = return_messages
        self.input_key = input_key
        self.output_key = output_key
        self.messages: List[ChatMessage] = []

    def add_user_message(self, content: str) -> None:
        """Add a human message to memory.

        Args:
            content: The message content.
        """
        self.messages.append(ChatMessage(role="human", content=content))

    def add_ai_message(self, content: str) -> None:
        """Add an AI message to memory.

        Args:
            content: The message content.
        """
        self.messages.append(ChatMessage(role="ai", content=content))

    def load_memory_variables(
        self, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Load conversation history as memory variables."""
        if self.return_messages:
            return {self.memory_key: self.messages.copy()}

        history_lines = []
        for msg in self.messages:
            prefix = self.human_prefix if msg.role == "human" else self.ai_prefix
            history_lines.append(f"{prefix}: {msg.content}")

        return {self.memory_key: "\n".join(history_lines)}

    def save_context(
        self, inputs: Dict[str, Any], outputs: Dict[str, str]
    ) -> None:
        """Save input/output pair to memory.

        Args:
            inputs: Dict containing user input.
            outputs: Dict containing AI output.
        """
        input_key = self.input_key or list(inputs.keys())[0]
        output_key = self.output_key or list(outputs.keys())[0]

        if input_key in inputs:
            self.add_user_message(str(inputs[input_key]))
        if output_key in outputs:
            self.add_ai_message(str(outputs[output_key]))

    def clear(self) -> None:
        """Clear all messages from memory."""
        self.messages.clear()

    @property
    def buffer(self) -> str:
        """Get buffer as formatted string."""
        return self.load_memory_variables({}).get(self.memory_key, "")


class ConversationBufferWindowMemory(ConversationBufferMemory):
    """Buffer memory with a sliding window of recent messages.

    Keeps only the last k conversation turns to manage context length.

    Example:
        >>> memory = ConversationBufferWindowMemory(k=2)
        >>> memory.add_user_message("Message 1")
        >>> memory.add_ai_message("Response 1")
        >>> memory.add_user_message("Message 2")
        >>> memory.add_ai_message("Response 2")
        >>> memory.add_user_message("Message 3")
        >>> memory.add_ai_message("Response 3")
        >>> # Only last 2 turns (4 messages) are kept
        >>> len(memory.messages)
        4
    """

    def __init__(self, k: int = 5, **kwargs: Any):
        """Initialize window memory.

        Args:
            k: Number of conversation turns to keep.
            **kwargs: Additional arguments for base class.
        """
        super().__init__(**kwargs)
        self.k = k

    def add_user_message(self, content: str) -> None:
        """Add user message and trim if needed."""
        super().add_user_message(content)
        self._trim_messages()

    def add_ai_message(self, content: str) -> None:
        """Add AI message and trim if needed."""
        super().add_ai_message(content)
        self._trim_messages()

    def _trim_messages(self) -> None:
        """Keep only the last k turns (2k messages)."""
        max_messages = self.k * 2
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]


class ConversationSummaryMemory(BaseMemory):
    """Memory that maintains a running summary of the conversation.

    Uses an LLM to summarize conversation history, keeping context compact.

    Example:
        >>> memory = ConversationSummaryMemory(llm=my_llm)
        >>> memory.add_user_message("Tell me about GraphRAG")
        >>> memory.add_ai_message("GraphRAG combines graphs with RAG...")
        >>> vars = memory.load_memory_variables({})
        >>> # Returns summarized history
    """

    def __init__(
        self,
        llm: Optional[Any] = None,
        memory_key: str = "history",
        human_prefix: str = "Human",
        ai_prefix: str = "AI",
        buffer: str = "",
        summarize_prompt: Optional[str] = None,
    ):
        """Initialize summary memory.

        Args:
            llm: LLM to use for summarization (optional, uses default if None).
            memory_key: Key for memory variables.
            human_prefix: Prefix for human messages.
            ai_prefix: Prefix for AI messages.
            buffer: Initial summary buffer.
            summarize_prompt: Custom prompt for summarization.
        """
        self.llm = llm
        self.memory_key = memory_key
        self.human_prefix = human_prefix
        self.ai_prefix = ai_prefix
        self.buffer = buffer
        self.messages: List[ChatMessage] = []
        self.summarize_prompt = summarize_prompt or (
            "Progressively summarize the conversation, adding to the summary:\n\n"
            "Current summary:\n{summary}\n\n"
            "New lines:\n{new_lines}\n\n"
            "New summary:"
        )

    def _get_summary(self, current_summary: str, new_lines: str) -> str:
        """Generate a summary using the LLM or fallback."""
        if self.llm is None:
            # Simple fallback: append truncated new lines
            if current_summary:
                return f"{current_summary}\n{new_lines[:500]}"
            return new_lines[:1000]

        # Use LLM for proper summarization
        prompt = self.summarize_prompt.format(
            summary=current_summary or "None yet.",
            new_lines=new_lines,
        )

        if hasattr(self.llm, "invoke"):
            return str(self.llm.invoke(prompt))
        elif hasattr(self.llm, "predict"):
            return str(self.llm.predict(prompt))
        else:
            return new_lines[:1000]

    def add_user_message(self, content: str) -> None:
        """Add user message and update summary."""
        self.messages.append(ChatMessage(role="human", content=content))
        self._update_summary()

    def add_ai_message(self, content: str) -> None:
        """Add AI message and update summary."""
        self.messages.append(ChatMessage(role="ai", content=content))
        self._update_summary()

    def _update_summary(self) -> None:
        """Update the running summary with new messages."""
        if len(self.messages) >= 2:
            # Summarize every 2 messages (one turn)
            new_lines = []
            for msg in self.messages[-2:]:
                prefix = self.human_prefix if msg.role == "human" else self.ai_prefix
                new_lines.append(f"{prefix}: {msg.content}")

            self.buffer = self._get_summary(self.buffer, "\n".join(new_lines))

    def load_memory_variables(
        self, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Load summary as memory variables."""
        return {self.memory_key: self.buffer}

    def save_context(
        self, inputs: Dict[str, Any], outputs: Dict[str, str]
    ) -> None:
        """Save context and update summary."""
        input_key = list(inputs.keys())[0] if inputs else None
        output_key = list(outputs.keys())[0] if outputs else None

        if input_key and input_key in inputs:
            self.add_user_message(str(inputs[input_key]))
        if output_key and output_key in outputs:
            self.add_ai_message(str(outputs[output_key]))

    def clear(self) -> None:
        """Clear all memory and summary."""
        self.messages.clear()
        self.buffer = ""


class VectorStoreRetrieverMemory(BaseMemory):
    """Memory that stores messages in a vector store for semantic retrieval.

    Uses embeddings to find relevant past conversation context.

    Example:
        >>> from agentic_brain.rag.store import InMemoryDocumentStore
        >>> store = InMemoryDocumentStore()
        >>> memory = VectorStoreRetrieverMemory(vectorstore=store)
        >>> memory.add_user_message("GraphRAG uses knowledge graphs")
        >>> memory.add_ai_message("Yes, it combines graphs with retrieval")
        >>> vars = memory.load_memory_variables({"input": "Tell me about graphs"})
        >>> # Returns relevant past messages
    """

    def __init__(
        self,
        vectorstore: Optional[Any] = None,
        memory_key: str = "history",
        input_key: str = "input",
        k: int = 5,
    ):
        """Initialize vector store memory.

        Args:
            vectorstore: Vector store for message storage.
            memory_key: Key for memory variables.
            input_key: Key for input in variables.
            k: Number of relevant messages to retrieve.
        """
        self.memory_key = memory_key
        self.input_key = input_key
        self.k = k
        self.messages: List[ChatMessage] = []

        if vectorstore is not None:
            self._store = vectorstore
        else:
            from .store import InMemoryDocumentStore
            self._store = InMemoryDocumentStore()

    def add_user_message(self, content: str) -> None:
        """Add and store user message."""
        msg = ChatMessage(role="human", content=content)
        self.messages.append(msg)
        self._store.add(f"Human: {content}")

    def add_ai_message(self, content: str) -> None:
        """Add and store AI message."""
        msg = ChatMessage(role="ai", content=content)
        self.messages.append(msg)
        self._store.add(f"AI: {content}")

    def load_memory_variables(
        self, inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Retrieve relevant past messages based on current input."""
        query = inputs.get(self.input_key, "")
        if not query:
            return {self.memory_key: ""}

        results = self._store.search(query, top_k=self.k)
        history = "\n".join(doc.content for doc in results)
        return {self.memory_key: history}

    def save_context(
        self, inputs: Dict[str, Any], outputs: Dict[str, str]
    ) -> None:
        """Save input/output to vector store."""
        input_key = self.input_key
        output_key = list(outputs.keys())[0] if outputs else None

        if input_key in inputs:
            self.add_user_message(str(inputs[input_key]))
        if output_key and output_key in outputs:
            self.add_ai_message(str(outputs[output_key]))

    def clear(self) -> None:
        """Clear all memory."""
        self.messages.clear()
        if hasattr(self._store, "clear"):
            self._store.clear()


# =============================================================================
# DOCUMENT LOADERS - Load Documents from Various Sources
# =============================================================================


class BaseLoader(ABC):
    """Abstract base class for document loaders.

    Loaders convert source data into LangChain Document objects.
    """

    @abstractmethod
    def load(self) -> List["LangChainDocument"]:
        """Load and return documents.

        Returns:
            List of LangChain Document objects.
        """
        pass

    def lazy_load(self) -> Iterator["LangChainDocument"]:
        """Lazily load documents one at a time.

        Yields:
            Individual Document objects.
        """
        for doc in self.load():
            yield doc


class TextLoader(BaseLoader):
    """Load a single text file as a document.

    Example:
        >>> loader = TextLoader("path/to/file.txt")
        >>> docs = loader.load()
        >>> docs[0].page_content[:50]
        'This is the content of the file...'
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        encoding: str = "utf-8",
        autodetect_encoding: bool = False,
    ):
        """Initialize text loader.

        Args:
            file_path: Path to the text file.
            encoding: Text encoding to use.
            autodetect_encoding: Try to detect encoding if default fails.
        """
        self.file_path = Path(file_path)
        self.encoding = encoding
        self.autodetect_encoding = autodetect_encoding

    def load(self) -> List["LangChainDocument"]:
        """Load the text file."""
        _check_langchain()
        from langchain_core.documents import Document as LCDocument

        text = self._read_file()
        metadata = {
            "source": str(self.file_path),
            "filename": self.file_path.name,
        }
        return [LCDocument(page_content=text, metadata=metadata)]

    def _read_file(self) -> str:
        """Read file content with optional encoding detection."""
        try:
            return self.file_path.read_text(encoding=self.encoding)
        except UnicodeDecodeError:
            if self.autodetect_encoding:
                # Try common encodings
                for enc in ["utf-8", "latin-1", "cp1252", "ascii"]:
                    try:
                        return self.file_path.read_text(encoding=enc)
                    except UnicodeDecodeError:
                        continue
            raise


class DirectoryLoader(BaseLoader):
    """Load all matching files from a directory.

    Example:
        >>> loader = DirectoryLoader("docs/", glob="**/*.md")
        >>> docs = loader.load()
        >>> len(docs)
        15
    """

    def __init__(
        self,
        path: Union[str, Path],
        glob: str = "**/*.*",
        loader_cls: Optional[Type[BaseLoader]] = None,
        loader_kwargs: Optional[Dict[str, Any]] = None,
        recursive: bool = True,
        show_progress: bool = False,
        use_multithreading: bool = False,
        max_concurrency: int = 4,
        silent_errors: bool = False,
    ):
        """Initialize directory loader.

        Args:
            path: Directory path to load from.
            glob: Glob pattern for file matching.
            loader_cls: Loader class to use for files (default: TextLoader).
            loader_kwargs: Arguments to pass to loader.
            recursive: Whether to search recursively.
            show_progress: Show loading progress.
            use_multithreading: Use multiple threads.
            max_concurrency: Max concurrent threads.
            silent_errors: Suppress file loading errors.
        """
        self.path = Path(path)
        self.glob = glob
        self.loader_cls = loader_cls or TextLoader
        self.loader_kwargs = loader_kwargs or {}
        self.recursive = recursive
        self.show_progress = show_progress
        self.use_multithreading = use_multithreading
        self.max_concurrency = max_concurrency
        self.silent_errors = silent_errors

    def load(self) -> List["LangChainDocument"]:
        """Load all matching files."""
        files = list(self.path.glob(self.glob))

        if self.use_multithreading:
            return self._load_multithreaded(files)

        docs = []
        for file_path in files:
            if file_path.is_file():
                try:
                    loader = self.loader_cls(file_path, **self.loader_kwargs)
                    docs.extend(loader.load())
                except Exception as e:
                    if not self.silent_errors:
                        logger.warning(f"Error loading {file_path}: {e}")
        return docs

    def _load_multithreaded(
        self, files: List[Path]
    ) -> List["LangChainDocument"]:
        """Load files using multiple threads."""
        docs: List["LangChainDocument"] = []

        def load_file(file_path: Path) -> List["LangChainDocument"]:
            if not file_path.is_file():
                return []
            try:
                loader = self.loader_cls(file_path, **self.loader_kwargs)
                return loader.load()
            except Exception as e:
                if not self.silent_errors:
                    logger.warning(f"Error loading {file_path}: {e}")
                return []

        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            results = executor.map(load_file, files)
            for result in results:
                docs.extend(result)

        return docs


class UnstructuredFileLoader(BaseLoader):
    """Load files using unstructured content detection.

    Handles various file types by detecting content structure.

    Example:
        >>> loader = UnstructuredFileLoader("document.pdf")
        >>> docs = loader.load()
    """

    # Supported file extensions and their handlers
    HANDLERS: Dict[str, Callable[[Path], str]] = {}

    def __init__(
        self,
        file_path: Union[str, Path],
        mode: str = "single",  # "single" | "elements" | "paged"
        strategy: str = "auto",
        encoding: str = "utf-8",
    ):
        """Initialize unstructured loader.

        Args:
            file_path: Path to file.
            mode: Loading mode (single document or elements).
            strategy: Parsing strategy (auto, fast, accurate).
            encoding: Text encoding.
        """
        self.file_path = Path(file_path)
        self.mode = mode
        self.strategy = strategy
        self.encoding = encoding

    def load(self) -> List["LangChainDocument"]:
        """Load file based on extension."""
        _check_langchain()
        from langchain_core.documents import Document as LCDocument

        ext = self.file_path.suffix.lower()

        # Handle common text formats
        if ext in {".txt", ".md", ".rst", ".py", ".js", ".ts", ".json", ".yaml", ".yml"}:
            text = self.file_path.read_text(encoding=self.encoding)
        elif ext in {".html", ".htm"}:
            text = self._parse_html()
        elif ext == ".csv":
            text = self._parse_csv()
        else:
            # Fallback: try reading as text
            try:
                text = self.file_path.read_text(encoding=self.encoding)
            except UnicodeDecodeError:
                text = self.file_path.read_bytes().decode("utf-8", errors="replace")

        metadata = {
            "source": str(self.file_path),
            "filename": self.file_path.name,
            "file_type": ext,
        }

        return [LCDocument(page_content=text, metadata=metadata)]

    def _parse_html(self) -> str:
        """Extract text from HTML."""
        html = self.file_path.read_text(encoding=self.encoding)
        # Simple HTML tag stripping
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _parse_csv(self) -> str:
        """Convert CSV to text representation."""
        import csv

        lines = []
        with open(self.file_path, encoding=self.encoding) as f:
            reader = csv.reader(f)
            for row in reader:
                lines.append(" | ".join(row))
        return "\n".join(lines)


# =============================================================================
# TEXT SPLITTERS - Split Documents into Chunks
# =============================================================================


class TextSplitter(ABC):
    """Abstract base class for text splitters.

    Splitters divide text into smaller chunks for embedding and retrieval.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
        keep_separator: bool = False,
        add_start_index: bool = False,
    ):
        """Initialize splitter.

        Args:
            chunk_size: Maximum size of chunks.
            chunk_overlap: Overlap between consecutive chunks.
            length_function: Function to measure text length.
            keep_separator: Keep separator in chunks.
            add_start_index: Add start index to metadata.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function
        self.keep_separator = keep_separator
        self.add_start_index = add_start_index

    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        """Split text into chunks.

        Args:
            text: Text to split.

        Returns:
            List of text chunks.
        """
        pass

    def split_documents(
        self, documents: List["LangChainDocument"]
    ) -> List["LangChainDocument"]:
        """Split documents into chunks.

        Args:
            documents: List of documents to split.

        Returns:
            List of chunked documents.
        """
        _check_langchain()
        from langchain_core.documents import Document as LCDocument

        chunks = []
        for doc in documents:
            texts = self.split_text(doc.page_content)
            for i, text in enumerate(texts):
                metadata = dict(doc.metadata)
                if self.add_start_index:
                    metadata["start_index"] = doc.page_content.find(text)
                metadata["chunk_index"] = i
                chunks.append(LCDocument(page_content=text, metadata=metadata))
        return chunks

    def _merge_splits(
        self, splits: List[str], separator: str
    ) -> List[str]:
        """Merge splits into chunks respecting size limits."""
        chunks = []
        current_chunk: List[str] = []
        current_length = 0

        for split in splits:
            split_length = self.length_function(split)

            if current_length + split_length > self.chunk_size:
                if current_chunk:
                    chunks.append(separator.join(current_chunk))

                # Handle overlap
                while current_length > self.chunk_overlap:
                    removed = current_chunk.pop(0)
                    current_length -= self.length_function(removed) + len(separator)

            current_chunk.append(split)
            current_length += split_length + len(separator)

        if current_chunk:
            chunks.append(separator.join(current_chunk))

        return chunks


class CharacterTextSplitter(TextSplitter):
    """Split text by character separator.

    Example:
        >>> splitter = CharacterTextSplitter(separator="\\n", chunk_size=500)
        >>> chunks = splitter.split_text(long_text)
    """

    def __init__(
        self,
        separator: str = "\n\n",
        **kwargs: Any,
    ):
        """Initialize character splitter.

        Args:
            separator: String to split on.
            **kwargs: Additional arguments for base class.
        """
        super().__init__(**kwargs)
        self.separator = separator

    def split_text(self, text: str) -> List[str]:
        """Split text by separator."""
        if self.separator:
            splits = text.split(self.separator)
        else:
            splits = list(text)

        separator = self.separator if self.keep_separator else ""
        return self._merge_splits(splits, separator)


class RecursiveCharacterTextSplitter(TextSplitter):
    """Recursively split text by multiple separators.

    Tries to keep semantic units together by using a hierarchy of separators.

    Example:
        >>> splitter = RecursiveCharacterTextSplitter(
        ...     chunk_size=1000,
        ...     chunk_overlap=200,
        ...     separators=["\\n\\n", "\\n", " ", ""]
        ... )
        >>> chunks = splitter.split_text(document)
    """

    def __init__(
        self,
        separators: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        """Initialize recursive splitter.

        Args:
            separators: List of separators in order of preference.
            **kwargs: Additional arguments for base class.
        """
        super().__init__(**kwargs)
        self.separators = separators or ["\n\n", "\n", " ", ""]

    def split_text(self, text: str) -> List[str]:
        """Recursively split text using separator hierarchy."""
        return self._split_text(text, self.separators)

    def _split_text(
        self, text: str, separators: List[str]
    ) -> List[str]:
        """Internal recursive split implementation."""
        final_chunks: List[str] = []

        # Find the best separator
        separator = separators[-1]
        for sep in separators:
            if sep == "":
                separator = sep
                break
            if sep in text:
                separator = sep
                break

        # Split by the chosen separator
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # Process splits
        good_splits: List[str] = []
        remaining_separators = separators[separators.index(separator) + 1:] if separator in separators else []

        for split in splits:
            if self.length_function(split) < self.chunk_size:
                good_splits.append(split)
            else:
                if good_splits:
                    merged = self._merge_splits(good_splits, separator)
                    final_chunks.extend(merged)
                    good_splits = []

                if remaining_separators:
                    # Recurse with finer separators
                    sub_chunks = self._split_text(split, remaining_separators)
                    final_chunks.extend(sub_chunks)
                else:
                    # Can't split further
                    final_chunks.append(split)

        if good_splits:
            merged = self._merge_splits(good_splits, separator)
            final_chunks.extend(merged)

        return final_chunks

    @classmethod
    def from_language(
        cls,
        language: str,
        **kwargs: Any,
    ) -> "RecursiveCharacterTextSplitter":
        """Create splitter with language-specific separators.

        Args:
            language: Programming language (python, js, markdown, etc).
            **kwargs: Additional arguments.

        Returns:
            Configured splitter for the language.
        """
        separators_by_language = {
            "python": ["\nclass ", "\ndef ", "\n\tdef ", "\n\n", "\n", " ", ""],
            "javascript": ["\nfunction ", "\nconst ", "\nlet ", "\n\n", "\n", " ", ""],
            "typescript": ["\nfunction ", "\nconst ", "\nlet ", "\ninterface ", "\ntype ", "\n\n", "\n", " ", ""],
            "markdown": ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " ", ""],
            "html": ["<div", "<p", "<h1", "<h2", "<h3", "\n\n", "\n", " ", ""],
            "go": ["\nfunc ", "\ntype ", "\n\n", "\n", " ", ""],
            "rust": ["\nfn ", "\nimpl ", "\nstruct ", "\nenum ", "\n\n", "\n", " ", ""],
            "java": ["\npublic ", "\nprivate ", "\nclass ", "\n\n", "\n", " ", ""],
        }

        separators = separators_by_language.get(
            language.lower(),
            ["\n\n", "\n", " ", ""],
        )
        return cls(separators=separators, **kwargs)


class TokenTextSplitter(TextSplitter):
    """Split text by token count.

    Uses tokenizer to ensure chunks fit within token limits.

    Example:
        >>> splitter = TokenTextSplitter(chunk_size=500, chunk_overlap=50)
        >>> chunks = splitter.split_text(document)
    """

    def __init__(
        self,
        encoding_name: str = "cl100k_base",
        model_name: Optional[str] = None,
        **kwargs: Any,
    ):
        """Initialize token splitter.

        Args:
            encoding_name: Tiktoken encoding name.
            model_name: Model name for encoding lookup.
            **kwargs: Additional arguments for base class.
        """
        super().__init__(**kwargs)
        self.encoding_name = encoding_name
        self.model_name = model_name
        self._tokenizer = None

    def _get_tokenizer(self) -> Any:
        """Get or create tokenizer."""
        if self._tokenizer is None:
            try:
                import tiktoken

                if self.model_name:
                    self._tokenizer = tiktoken.encoding_for_model(self.model_name)
                else:
                    self._tokenizer = tiktoken.get_encoding(self.encoding_name)
            except ImportError:
                # Fallback to simple word-based tokenization
                self._tokenizer = None
        return self._tokenizer

    def _token_length(self, text: str) -> int:
        """Count tokens in text."""
        tokenizer = self._get_tokenizer()
        if tokenizer:
            return len(tokenizer.encode(text))
        # Fallback: estimate ~4 chars per token
        return len(text) // 4

    def split_text(self, text: str) -> List[str]:
        """Split text by token count."""
        tokenizer = self._get_tokenizer()

        if tokenizer is None:
            # Fallback to character-based splitting
            splitter = CharacterTextSplitter(
                separator=" ",
                chunk_size=self.chunk_size * 4,  # Estimate chars
                chunk_overlap=self.chunk_overlap * 4,
            )
            return splitter.split_text(text)

        # Token-based splitting
        tokens = tokenizer.encode(text)
        chunks = []

        start = 0
        while start < len(tokens):
            end = start + self.chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
            start = end - self.chunk_overlap

        return chunks


# =============================================================================
# OUTPUT PARSERS - Parse LLM Outputs
# =============================================================================


class BaseOutputParser(ABC, Generic[Output]):
    """Abstract base class for output parsers.

    Parsers convert raw LLM output strings into structured data.
    """

    @abstractmethod
    def parse(self, text: str) -> Output:
        """Parse the output.

        Args:
            text: Raw LLM output string.

        Returns:
            Parsed output.
        """
        pass

    def parse_with_prompt(
        self, completion: str, prompt: str
    ) -> Output:
        """Parse with access to the original prompt.

        Args:
            completion: LLM completion.
            prompt: Original prompt.

        Returns:
            Parsed output.
        """
        return self.parse(completion)

    def get_format_instructions(self) -> str:
        """Get instructions for formatting output.

        Returns:
            Instructions string to include in prompts.
        """
        return ""


class StrOutputParser(BaseOutputParser[str]):
    """Parse output as string (identity parser).

    Example:
        >>> parser = StrOutputParser()
        >>> parser.parse("Hello world")
        'Hello world'
    """

    def parse(self, text: str) -> str:
        """Return text unchanged."""
        return text.strip()


class JsonOutputParser(BaseOutputParser[Dict[str, Any]]):
    """Parse JSON from LLM output.

    Handles markdown code blocks and common JSON formatting issues.

    Example:
        >>> parser = JsonOutputParser()
        >>> parser.parse('{"name": "Alice", "age": 30}')
        {'name': 'Alice', 'age': 30}
    """

    def __init__(self, strict: bool = False):
        """Initialize JSON parser.

        Args:
            strict: If True, raise on invalid JSON. If False, try to fix.
        """
        self.strict = strict

    def parse(self, text: str) -> Dict[str, Any]:
        """Parse JSON from text."""
        # Remove markdown code blocks
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            if self.strict:
                raise

            # Try to extract JSON from text
            match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass

            raise ValueError(f"Could not parse JSON: {e}")

    def get_format_instructions(self) -> str:
        """Get JSON formatting instructions."""
        return (
            "Return your response as a valid JSON object. "
            "Do not include any text before or after the JSON."
        )


class PydanticOutputParser(BaseOutputParser[Any]):
    """Parse output into a Pydantic model.

    Example:
        >>> from pydantic import BaseModel
        >>> class Person(BaseModel):
        ...     name: str
        ...     age: int
        >>> parser = PydanticOutputParser(pydantic_object=Person)
        >>> person = parser.parse('{"name": "Alice", "age": 30}')
        >>> person.name
        'Alice'
    """

    def __init__(self, pydantic_object: Type[Any]):
        """Initialize Pydantic parser.

        Args:
            pydantic_object: The Pydantic model class to parse into.
        """
        self.pydantic_object = pydantic_object

    def parse(self, text: str) -> Any:
        """Parse text into Pydantic model."""
        # First parse as JSON
        json_parser = JsonOutputParser()
        data = json_parser.parse(text)

        # Then validate with Pydantic
        return self.pydantic_object(**data)

    def get_format_instructions(self) -> str:
        """Get Pydantic-specific formatting instructions."""
        schema = self.pydantic_object.model_json_schema()
        return (
            f"Return your response as a JSON object matching this schema:\n"
            f"{json.dumps(schema, indent=2)}"
        )


class ListOutputParser(BaseOutputParser[List[str]]):
    """Parse output as a list of items.

    Example:
        >>> parser = ListOutputParser()
        >>> parser.parse("1. Apple\\n2. Banana\\n3. Cherry")
        ['Apple', 'Banana', 'Cherry']
    """

    def __init__(self, separator: Optional[str] = None):
        """Initialize list parser.

        Args:
            separator: Optional custom separator.
        """
        self.separator = separator

    def parse(self, text: str) -> List[str]:
        """Parse text as list."""
        text = text.strip()

        if self.separator:
            return [item.strip() for item in text.split(self.separator) if item.strip()]

        # Try numbered list
        numbered = re.findall(r"^\d+[\.\)]\s*(.+)$", text, re.MULTILINE)
        if numbered:
            return numbered

        # Try bullet list
        bulleted = re.findall(r"^[-*•]\s*(.+)$", text, re.MULTILINE)
        if bulleted:
            return bulleted

        # Fallback to newline separation
        return [line.strip() for line in text.split("\n") if line.strip()]


class CommaSeparatedListOutputParser(BaseOutputParser[List[str]]):
    """Parse comma-separated list from output.

    Example:
        >>> parser = CommaSeparatedListOutputParser()
        >>> parser.parse("apple, banana, cherry")
        ['apple', 'banana', 'cherry']
    """

    def parse(self, text: str) -> List[str]:
        """Parse comma-separated values."""
        return [item.strip() for item in text.split(",") if item.strip()]

    def get_format_instructions(self) -> str:
        """Get comma-separated formatting instructions."""
        return "Return a comma-separated list of items."


# =============================================================================
# CHAINS - Pre-built Chain Patterns
# =============================================================================


class BaseChain(ABC, Runnable[Dict[str, Any], Dict[str, Any]]):
    """Abstract base class for chains.

    Chains combine multiple components into a processing pipeline.
    """

    memory: Optional[BaseMemory] = None
    verbose: bool = False
    callbacks: Optional[List[Any]] = None

    @abstractmethod
    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute the chain.

        Args:
            inputs: Input variables.
            run_manager: Optional callback manager.

        Returns:
            Output variables.
        """
        pass

    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Invoke the chain."""
        # Load memory if available
        if self.memory:
            memory_vars = self.memory.load_memory_variables(input)
            input = {**input, **memory_vars}

        # Execute chain
        output = self._call(input)

        # Save to memory
        if self.memory:
            self.memory.save_context(input, output)

        return output


class RetrievalQA(BaseChain):
    """Question-answering chain with retrieval.

    Retrieves relevant documents and uses them to answer questions.

    Example:
        >>> qa = RetrievalQA(
        ...     retriever=my_retriever,
        ...     llm=my_llm,
        ... )
        >>> result = qa.invoke({"query": "What is GraphRAG?"})
        >>> print(result["result"])
    """

    def __init__(
        self,
        retriever: Any,
        llm: Optional[Any] = None,
        prompt_template: Optional[str] = None,
        return_source_documents: bool = False,
        input_key: str = "query",
        output_key: str = "result",
        document_variable_name: str = "context",
    ):
        """Initialize RetrievalQA chain.

        Args:
            retriever: Document retriever (LangChain BaseRetriever).
            llm: Language model for answering.
            prompt_template: Custom prompt template.
            return_source_documents: Include source docs in output.
            input_key: Key for input question.
            output_key: Key for output answer.
            document_variable_name: Key for context in prompt.
        """
        self.retriever = retriever
        self.llm = llm
        self.return_source_documents = return_source_documents
        self.input_key = input_key
        self.output_key = output_key
        self.document_variable_name = document_variable_name
        self.prompt_template = prompt_template or (
            "Use the following context to answer the question.\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Answer:"
        )

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute retrieval and answering."""
        question = inputs[self.input_key]

        # Retrieve documents
        if hasattr(self.retriever, "invoke"):
            docs = self.retriever.invoke(question)
        elif hasattr(self.retriever, "get_relevant_documents"):
            docs = self.retriever.get_relevant_documents(question)
        else:
            docs = self.retriever(question)

        # Format context
        context = "\n\n".join(
            doc.page_content if hasattr(doc, "page_content") else str(doc)
            for doc in docs
        )

        # Generate answer
        prompt = self.prompt_template.format(
            context=context,
            question=question,
        )

        if self.llm:
            if hasattr(self.llm, "invoke"):
                answer = str(self.llm.invoke(prompt))
            elif hasattr(self.llm, "predict"):
                answer = str(self.llm.predict(prompt))
            else:
                answer = str(self.llm(prompt))
        else:
            # No LLM - return context
            answer = context

        result = {self.output_key: answer}
        if self.return_source_documents:
            result["source_documents"] = docs

        return result


class ConversationalRetrievalChain(BaseChain):
    """Conversational retrieval chain with memory.

    Combines conversation history with document retrieval.

    Example:
        >>> chain = ConversationalRetrievalChain(
        ...     retriever=my_retriever,
        ...     llm=my_llm,
        ...     memory=ConversationBufferMemory(),
        ... )
        >>> result = chain.invoke({"question": "What is RAG?"})
        >>> result = chain.invoke({"question": "Tell me more about it"})
    """

    def __init__(
        self,
        retriever: Any,
        llm: Optional[Any] = None,
        memory: Optional[BaseMemory] = None,
        condense_question_prompt: Optional[str] = None,
        combine_docs_prompt: Optional[str] = None,
        return_source_documents: bool = False,
        verbose: bool = False,
    ):
        """Initialize conversational chain.

        Args:
            retriever: Document retriever.
            llm: Language model.
            memory: Conversation memory.
            condense_question_prompt: Prompt for question condensing.
            combine_docs_prompt: Prompt for combining docs and answering.
            return_source_documents: Include source docs in output.
            verbose: Enable verbose logging.
        """
        self.retriever = retriever
        self.llm = llm
        self.memory = memory or ConversationBufferMemory()
        self.return_source_documents = return_source_documents
        self.verbose = verbose

        self.condense_question_prompt = condense_question_prompt or (
            "Given the following conversation and a follow up question, "
            "rephrase the follow up question to be a standalone question.\n\n"
            "Chat History:\n{chat_history}\n\n"
            "Follow Up Input: {question}\n"
            "Standalone question:"
        )

        self.combine_docs_prompt = combine_docs_prompt or (
            "Use the following context to answer the question.\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Answer:"
        )

    def _call(
        self,
        inputs: Dict[str, Any],
        run_manager: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute conversational retrieval."""
        question = inputs.get("question", "")
        chat_history = inputs.get("chat_history", "")

        # Condense question with history
        if chat_history and self.llm:
            condense_prompt = self.condense_question_prompt.format(
                chat_history=chat_history,
                question=question,
            )
            if hasattr(self.llm, "invoke"):
                standalone_question = str(self.llm.invoke(condense_prompt))
            else:
                standalone_question = str(self.llm.predict(condense_prompt))
        else:
            standalone_question = question

        # Retrieve documents
        if hasattr(self.retriever, "invoke"):
            docs = self.retriever.invoke(standalone_question)
        else:
            docs = self.retriever.get_relevant_documents(standalone_question)

        # Format context
        context = "\n\n".join(
            doc.page_content if hasattr(doc, "page_content") else str(doc)
            for doc in docs
        )

        # Generate answer
        combine_prompt = self.combine_docs_prompt.format(
            context=context,
            question=standalone_question,
        )

        if self.llm:
            if hasattr(self.llm, "invoke"):
                answer = str(self.llm.invoke(combine_prompt))
            else:
                answer = str(self.llm.predict(combine_prompt))
        else:
            answer = context

        result = {"answer": answer}
        if self.return_source_documents:
            result["source_documents"] = docs

        return result


# =============================================================================
# CALLBACKS - Event Handlers for Tracing and Monitoring
# =============================================================================


class BaseCallbackHandler:
    """Base class for callback handlers.

    Implement methods to handle various LangChain events.

    Example:
        >>> class MyHandler(BaseCallbackHandler):
        ...     def on_llm_start(self, serialized, prompts, **kwargs):
        ...         print(f"LLM started with {len(prompts)} prompts")
        ...
        ...     def on_retriever_end(self, documents, **kwargs):
        ...         print(f"Retrieved {len(documents)} documents")
    """

    # Run lifecycle
    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain starts running."""
        pass

    def on_chain_end(
        self,
        outputs: Dict[str, Any],
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain finishes."""
        pass

    def on_chain_error(
        self,
        error: Exception,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain errors."""
        pass

    # LLM events
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM starts."""
        pass

    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM finishes."""
        pass

    def on_llm_error(
        self,
        error: Exception,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM errors."""
        pass

    def on_llm_new_token(
        self,
        token: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when streaming a new token."""
        pass

    # Retriever events
    def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever starts."""
        pass

    def on_retriever_end(
        self,
        documents: List[Any],
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever finishes."""
        pass

    def on_retriever_error(
        self,
        error: Exception,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when retriever errors."""
        pass

    # Tool events
    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool starts."""
        pass

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool finishes."""
        pass

    def on_tool_error(
        self,
        error: Exception,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called when a tool errors."""
        pass

    # Text events
    def on_text(
        self,
        text: str,
        *,
        run_id: Optional[str] = None,
        parent_run_id: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Called with any text output."""
        pass


class AsyncCallbackHandler(BaseCallbackHandler):
    """Async version of callback handler.

    All methods are async and can perform I/O without blocking.

    Example:
        >>> class MyAsyncHandler(AsyncCallbackHandler):
        ...     async def on_llm_end(self, response, **kwargs):
        ...         await self.log_to_database(response)
    """

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Async chain start handler."""
        pass

    async def on_chain_end(
        self,
        outputs: Dict[str, Any],
        **kwargs: Any,
    ) -> None:
        """Async chain end handler."""
        pass

    async def on_chain_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        """Async chain error handler."""
        pass

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        **kwargs: Any,
    ) -> None:
        """Async LLM start handler."""
        pass

    async def on_llm_end(
        self,
        response: Any,
        **kwargs: Any,
    ) -> None:
        """Async LLM end handler."""
        pass

    async def on_llm_error(
        self,
        error: Exception,
        **kwargs: Any,
    ) -> None:
        """Async LLM error handler."""
        pass

    async def on_retriever_start(
        self,
        serialized: Dict[str, Any],
        query: str,
        **kwargs: Any,
    ) -> None:
        """Async retriever start handler."""
        pass

    async def on_retriever_end(
        self,
        documents: List[Any],
        **kwargs: Any,
    ) -> None:
        """Async retriever end handler."""
        pass


class StdOutCallbackHandler(BaseCallbackHandler):
    """Callback handler that prints events to stdout.

    Useful for debugging and development.

    Example:
        >>> handler = StdOutCallbackHandler(color=True)
        >>> retriever.invoke("query", config={"callbacks": [handler]})
    """

    def __init__(self, color: bool = True):
        """Initialize stdout handler.

        Args:
            color: Use colored output.
        """
        self.color = color

    def _print(self, text: str, color: Optional[str] = None) -> None:
        """Print with optional color."""
        if self.color and color:
            colors = {
                "green": "\033[92m",
                "blue": "\033[94m",
                "red": "\033[91m",
                "yellow": "\033[93m",
                "reset": "\033[0m",
            }
            print(f"{colors.get(color, '')}{text}{colors['reset']}")
        else:
            print(text)

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Print chain start."""
        name = serialized.get("name", "Chain")
        self._print(f"\n> Entering {name}...", "green")

    def on_chain_end(
        self, outputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Print chain end."""
        self._print("> Finished chain.", "green")

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Print LLM start."""
        self._print(f"\n[LLM] Processing {len(prompts)} prompt(s)...", "blue")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Print LLM end."""
        self._print("[LLM] Complete.", "blue")

    def on_retriever_start(
        self, serialized: Dict[str, Any], query: str, **kwargs: Any
    ) -> None:
        """Print retriever start."""
        self._print(f"\n[Retriever] Searching: {query[:50]}...", "yellow")

    def on_retriever_end(
        self, documents: List[Any], **kwargs: Any
    ) -> None:
        """Print retriever end."""
        self._print(f"[Retriever] Found {len(documents)} documents.", "yellow")

    def on_chain_error(self, error: Exception, **kwargs: Any) -> None:
        """Print error."""
        self._print(f"[ERROR] {error}", "red")


class TracingCallbackHandler(BaseCallbackHandler):
    """Callback handler that records traces for debugging.

    Captures a complete trace of all events for analysis.

    Example:
        >>> tracer = TracingCallbackHandler()
        >>> chain.invoke(input, config={"callbacks": [tracer]})
        >>> for event in tracer.get_trace():
        ...     print(event)
    """

    def __init__(self, project_name: Optional[str] = None):
        """Initialize tracer.

        Args:
            project_name: Optional project name for grouping traces.
        """
        self.project_name = project_name
        self.traces: List[Dict[str, Any]] = []
        self.start_time: Optional[float] = None

    def _record(
        self,
        event_type: str,
        data: Dict[str, Any],
        run_id: Optional[str] = None,
    ) -> None:
        """Record an event."""
        self.traces.append({
            "type": event_type,
            "run_id": run_id or str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": (time.time() - self.start_time) * 1000 if self.start_time else 0,
            "data": data,
        })

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Record chain start."""
        self.start_time = time.time()
        self._record(
            "chain_start",
            {"name": serialized.get("name"), "inputs": inputs},
            kwargs.get("run_id"),
        )

    def on_chain_end(
        self, outputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Record chain end."""
        self._record("chain_end", {"outputs": outputs}, kwargs.get("run_id"))

    def on_chain_error(
        self, error: Exception, **kwargs: Any
    ) -> None:
        """Record chain error."""
        self._record(
            "chain_error",
            {"error": str(error), "type": type(error).__name__},
            kwargs.get("run_id"),
        )

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Record LLM start."""
        self._record(
            "llm_start",
            {"model": serialized.get("name"), "prompt_count": len(prompts)},
            kwargs.get("run_id"),
        )

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Record LLM end."""
        self._record("llm_end", {"response": str(response)[:500]}, kwargs.get("run_id"))

    def on_retriever_start(
        self, serialized: Dict[str, Any], query: str, **kwargs: Any
    ) -> None:
        """Record retriever start."""
        self._record("retriever_start", {"query": query}, kwargs.get("run_id"))

    def on_retriever_end(
        self, documents: List[Any], **kwargs: Any
    ) -> None:
        """Record retriever end."""
        self._record(
            "retriever_end",
            {"document_count": len(documents)},
            kwargs.get("run_id"),
        )

    def get_trace(self) -> List[Dict[str, Any]]:
        """Get the recorded trace.

        Returns:
            List of trace events.
        """
        return self.traces.copy()

    def clear(self) -> None:
        """Clear recorded traces."""
        self.traces.clear()
        self.start_time = None

    def to_json(self) -> str:
        """Export traces as JSON.

        Returns:
            JSON string of traces.
        """
        return json.dumps(
            {
                "project": self.project_name,
                "traces": self.traces,
            },
            indent=2,
            default=str,
        )


class FileCallbackHandler(BaseCallbackHandler):
    """Callback handler that logs events to a file.

    Example:
        >>> handler = FileCallbackHandler("langchain.log")
        >>> chain.invoke(input, config={"callbacks": [handler]})
    """

    def __init__(self, filename: Union[str, Path]):
        """Initialize file handler.

        Args:
            filename: Path to log file.
        """
        self.filename = Path(filename)
        self.filename.parent.mkdir(parents=True, exist_ok=True)

    def _log(self, message: str) -> None:
        """Write message to file."""
        timestamp = datetime.now().isoformat()
        with open(self.filename, "a") as f:
            f.write(f"[{timestamp}] {message}\n")

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Log chain start."""
        self._log(f"CHAIN_START: {serialized.get('name', 'unknown')}")

    def on_chain_end(
        self, outputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Log chain end."""
        self._log(f"CHAIN_END: {list(outputs.keys())}")

    def on_chain_error(
        self, error: Exception, **kwargs: Any
    ) -> None:
        """Log chain error."""
        self._log(f"CHAIN_ERROR: {error}")

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        """Log LLM start."""
        self._log(f"LLM_START: {len(prompts)} prompts")

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Log LLM end."""
        self._log("LLM_END")

    def on_retriever_start(
        self, serialized: Dict[str, Any], query: str, **kwargs: Any
    ) -> None:
        """Log retriever start."""
        self._log(f"RETRIEVER_START: {query[:100]}")

    def on_retriever_end(
        self, documents: List[Any], **kwargs: Any
    ) -> None:
        """Log retriever end."""
        self._log(f"RETRIEVER_END: {len(documents)} docs")


# =============================================================================
# MODULE EXPORTS
# =============================================================================

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
    # LCEL Runnables
    "Runnable",
    "RunnableSequence",
    "RunnableLambda",
    "RunnablePassthrough",
    "RunnableAssign",
    "RunnableParallel",
    "RunnableBinding",
    "RunnableBranch",
    # Memory classes
    "BaseMemory",
    "ChatMessage",
    "ConversationBufferMemory",
    "ConversationBufferWindowMemory",
    "ConversationSummaryMemory",
    "VectorStoreRetrieverMemory",
    # Document loaders
    "BaseLoader",
    "TextLoader",
    "DirectoryLoader",
    "UnstructuredFileLoader",
    # Text splitters
    "TextSplitter",
    "CharacterTextSplitter",
    "RecursiveCharacterTextSplitter",
    "TokenTextSplitter",
    # Output parsers
    "BaseOutputParser",
    "StrOutputParser",
    "JsonOutputParser",
    "PydanticOutputParser",
    "ListOutputParser",
    "CommaSeparatedListOutputParser",
    # Chains
    "BaseChain",
    "RetrievalQA",
    "ConversationalRetrievalChain",
    # Callbacks
    "BaseCallbackHandler",
    "AsyncCallbackHandler",
    "StdOutCallbackHandler",
    "TracingCallbackHandler",
    "FileCallbackHandler",
]
