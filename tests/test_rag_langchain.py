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
Tests for LangChain compatibility layer.

Tests for:
- Document format conversion
- BaseRetriever interface compliance
- LCEL chain integration
- Callback support
- Factory functions
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime

from agentic_brain.rag.retriever import RetrievedChunk, Retriever
from agentic_brain.rag.store import Document as AgenticDocument, InMemoryDocumentStore
from agentic_brain.rag.langchain_compat import (
    LANGCHAIN_AVAILABLE,
    retrieved_chunk_to_langchain_document,
    agentic_document_to_langchain_document,
    langchain_document_to_agentic_document,
    AgenticBrainCallbackAdapter,
    create_langchain_retriever,
)


# Skip all tests if LangChain is not installed
pytestmark = pytest.mark.skipif(
    not LANGCHAIN_AVAILABLE,
    reason="LangChain not installed (pip install langchain-core)"
)


class TestDocumentConversion:
    """Test document format conversion between Agentic Brain and LangChain."""

    def test_retrieved_chunk_to_langchain(self):
        """Test converting RetrievedChunk to LangChain Document."""
        chunk = RetrievedChunk(
            content="This is test content about RAG.",
            source="test.md",
            score=0.85,
            metadata={"page": 1, "section": "intro"}
        )

        doc = retrieved_chunk_to_langchain_document(chunk)

        assert doc.page_content == "This is test content about RAG."
        assert doc.metadata["source"] == "test.md"
        assert doc.metadata["score"] == 0.85
        assert doc.metadata["confidence"] == "high"
        assert doc.metadata["page"] == 1
        assert doc.metadata["section"] == "intro"

    def test_agentic_document_to_langchain(self):
        """Test converting Agentic Brain Document to LangChain Document."""
        agentic_doc = AgenticDocument(
            id="doc-123",
            content="Hello world content here.",
            metadata={"title": "Test Doc", "author": "Joe"},
        )

        lc_doc = agentic_document_to_langchain_document(agentic_doc)

        assert lc_doc.page_content == "Hello world content here."
        assert lc_doc.metadata["id"] == "doc-123"
        assert lc_doc.metadata["title"] == "Test Doc"
        assert lc_doc.metadata["author"] == "Joe"
        assert "created_at" in lc_doc.metadata

    def test_langchain_to_agentic_document(self):
        """Test converting LangChain Document to Agentic Brain Document."""
        from langchain_core.documents import Document as LCDocument

        lc_doc = LCDocument(
            page_content="LangChain document content.",
            metadata={"id": "lc-456", "source": "langchain.py"}
        )

        agentic_doc = langchain_document_to_agentic_document(lc_doc)

        assert agentic_doc.id == "lc-456"
        assert agentic_doc.content == "LangChain document content."
        assert agentic_doc.metadata["source"] == "langchain.py"
        assert "id" not in agentic_doc.metadata  # ID moved to doc.id

    def test_langchain_to_agentic_generates_id(self):
        """Test that ID is generated when not provided."""
        from langchain_core.documents import Document as LCDocument

        lc_doc = LCDocument(
            page_content="No ID provided here.",
            metadata={"source": "test.txt"}
        )

        agentic_doc = langchain_document_to_agentic_document(lc_doc)

        assert agentic_doc.id is not None
        assert len(agentic_doc.id) == 16  # SHA256 hash prefix

    def test_roundtrip_conversion(self):
        """Test that document conversion is lossless for content."""
        original = AgenticDocument(
            id="roundtrip-test",
            content="Content survives round trip.",
            metadata={"key": "value"}
        )

        # Convert to LangChain
        lc_doc = agentic_document_to_langchain_document(original)

        # Convert back
        restored = langchain_document_to_agentic_document(lc_doc)

        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.metadata["key"] == original.metadata["key"]


class TestAgenticBrainRetriever:
    """Test the LangChain-compatible AgenticBrainRetriever."""

    def test_retriever_initialization(self):
        """Test basic retriever initialization."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        retriever = AgenticBrainRetriever(k=10, min_score=0.5)

        assert retriever.k == 10
        assert retriever.min_score == 0.5
        assert retriever._retriever_instance is not None

    def test_retriever_with_custom_instance(self):
        """Test retriever with pre-configured Retriever instance."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        mock_retriever = MagicMock(spec=Retriever)
        retriever = AgenticBrainRetriever(retriever=mock_retriever, k=5)

        assert retriever._retriever_instance is mock_retriever
        assert retriever.k == 5

    @patch.object(Retriever, 'search')
    def test_invoke_returns_langchain_docs(self, mock_search):
        """Test that invoke() returns LangChain Documents."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        mock_search.return_value = [
            RetrievedChunk(content="Result 1", source="a.md", score=0.9),
            RetrievedChunk(content="Result 2", source="b.md", score=0.7),
        ]

        retriever = AgenticBrainRetriever(k=5)
        docs = retriever.invoke("test query")

        assert len(docs) == 2
        assert docs[0].page_content == "Result 1"
        assert docs[0].metadata["source"] == "a.md"
        assert docs[1].page_content == "Result 2"

    @patch.object(Retriever, 'search')
    def test_min_score_filtering(self, mock_search):
        """Test that results below min_score are filtered."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        mock_search.return_value = [
            RetrievedChunk(content="High score", source="a.md", score=0.9),
            RetrievedChunk(content="Low score", source="b.md", score=0.2),
        ]

        retriever = AgenticBrainRetriever(k=5, min_score=0.5)
        docs = retriever.invoke("test query")

        assert len(docs) == 1
        assert docs[0].page_content == "High score"

    @patch.object(Retriever, 'search')
    def test_with_config_creates_new_instance(self, mock_search):
        """Test with_config creates a new retriever with updated settings."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        original = AgenticBrainRetriever(k=5, min_score=0.3)
        updated = original.with_config(k=10, min_score=0.6)

        assert original.k == 5
        assert original.min_score == 0.3
        assert updated.k == 10
        assert updated.min_score == 0.6


class TestDocumentStoreRetriever:
    """Test the DocumentStore-backed retriever."""

    def test_document_store_retriever_init(self):
        """Test DocumentStoreRetriever initialization."""
        from agentic_brain.rag.langchain_compat import DocumentStoreRetriever

        store = InMemoryDocumentStore()
        retriever = DocumentStoreRetriever(store=store, k=3)

        assert retriever.k == 3
        assert retriever._store_instance is store

    def test_document_store_retriever_search(self):
        """Test search through DocumentStoreRetriever."""
        from agentic_brain.rag.langchain_compat import DocumentStoreRetriever

        store = InMemoryDocumentStore()
        store.add("GraphRAG is a knowledge graph retrieval system.")
        store.add("LangChain is an orchestration framework.")

        retriever = DocumentStoreRetriever(store=store, k=5)
        docs = retriever.invoke("GraphRAG")

        assert len(docs) >= 1
        assert "GraphRAG" in docs[0].page_content

    def test_add_documents(self):
        """Test adding LangChain documents to the store."""
        from langchain_core.documents import Document as LCDocument
        from agentic_brain.rag.langchain_compat import DocumentStoreRetriever

        store = InMemoryDocumentStore()
        retriever = DocumentStoreRetriever(store=store)

        lc_docs = [
            LCDocument(page_content="First document", metadata={"id": "doc1"}),
            LCDocument(page_content="Second document", metadata={"id": "doc2"}),
        ]

        ids = retriever.add_documents(lc_docs)

        assert len(ids) == 2
        assert "doc1" in ids
        assert "doc2" in ids
        assert store.count() == 2


class TestCallbackAdapter:
    """Test the callback adapter for LangChain integration."""

    def test_callback_on_retrieval_start(self):
        """Test that retrieval start events are forwarded."""
        mock_handler = MagicMock()
        mock_handler.on_retriever_start = MagicMock()

        adapter = AgenticBrainCallbackAdapter([mock_handler])
        adapter.on_retrieval_start("test query", {"k": 5})

        mock_handler.on_retriever_start.assert_called_once()
        call_args = mock_handler.on_retriever_start.call_args
        assert call_args.kwargs["query"] == "test query"

    def test_callback_on_retrieval_end(self):
        """Test that retrieval end events are forwarded."""
        from langchain_core.documents import Document as LCDocument

        mock_handler = MagicMock()
        mock_handler.on_retriever_end = MagicMock()

        adapter = AgenticBrainCallbackAdapter([mock_handler])
        docs = [LCDocument(page_content="result")]
        adapter.on_retrieval_end(docs)

        mock_handler.on_retriever_end.assert_called_once_with(docs)

    def test_callback_on_retrieval_error(self):
        """Test that error events are forwarded."""
        mock_handler = MagicMock()
        mock_handler.on_retriever_error = MagicMock()

        adapter = AgenticBrainCallbackAdapter([mock_handler])
        error = ValueError("Test error")
        adapter.on_retrieval_error(error)

        mock_handler.on_retriever_error.assert_called_once_with(error)

    def test_multiple_callbacks(self):
        """Test that events are forwarded to all callbacks."""
        handlers = [MagicMock() for _ in range(3)]
        for h in handlers:
            h.on_retriever_start = MagicMock()

        adapter = AgenticBrainCallbackAdapter(handlers)
        adapter.on_retrieval_start("query")

        for h in handlers:
            h.on_retriever_start.assert_called_once()


class TestFactoryFunction:
    """Test the factory function for creating retrievers."""

    def test_create_basic_retriever(self):
        """Test creating basic retriever."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        retriever = create_langchain_retriever("basic", k=10)

        assert isinstance(retriever, AgenticBrainRetriever)
        assert retriever.k == 10

    def test_create_store_retriever(self):
        """Test creating store-backed retriever."""
        from agentic_brain.rag.langchain_compat import DocumentStoreRetriever

        store = InMemoryDocumentStore()
        retriever = create_langchain_retriever("store", store=store, k=5)

        assert isinstance(retriever, DocumentStoreRetriever)
        assert retriever.k == 5

    def test_create_unknown_type_raises(self):
        """Test that unknown type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown retriever type"):
            create_langchain_retriever("unknown")


class TestLCELChainIntegration:
    """Test integration with LangChain Expression Language chains."""

    @patch.object(Retriever, 'search')
    def test_retriever_in_dict_chain(self, mock_search):
        """Test retriever as part of a dict chain component."""
        from langchain_core.runnables import RunnablePassthrough
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        mock_search.return_value = [
            RetrievedChunk(content="Context here", source="test.md", score=0.9)
        ]

        retriever = AgenticBrainRetriever(k=5)

        # Create a simple chain that just returns context
        chain = {"context": retriever, "question": RunnablePassthrough()}

        result = chain["context"].invoke("test question")

        assert len(result) == 1
        assert result[0].page_content == "Context here"

    @patch.object(Retriever, 'search')
    def test_retriever_pipe_operator(self, mock_search):
        """Test retriever works with pipe operator."""
        from langchain_core.runnables import RunnableLambda
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        mock_search.return_value = [
            RetrievedChunk(content="RAG result", source="doc.md", score=0.8)
        ]

        retriever = AgenticBrainRetriever(k=5)

        # Chain: retriever -> extract content
        extract_content = RunnableLambda(
            lambda docs: [d.page_content for d in docs]
        )
        chain = retriever | extract_content

        result = chain.invoke("query")

        assert result == ["RAG result"]


class TestAsyncRetrieval:
    """Test async retrieval capabilities."""

    @pytest.mark.asyncio
    @patch.object(Retriever, 'search')
    async def test_async_invoke(self, mock_search):
        """Test async retrieval."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        mock_search.return_value = [
            RetrievedChunk(content="Async result", source="async.md", score=0.9)
        ]

        retriever = AgenticBrainRetriever(k=5)
        docs = await retriever.ainvoke("async query")

        assert len(docs) == 1
        assert docs[0].page_content == "Async result"

    @pytest.mark.asyncio
    async def test_async_document_store_retrieval(self):
        """Test async retrieval from document store."""
        from agentic_brain.rag.langchain_compat import DocumentStoreRetriever

        store = InMemoryDocumentStore()
        store.add("Async document content for testing.")

        retriever = DocumentStoreRetriever(store=store)
        docs = await retriever.ainvoke("async document")

        assert len(docs) >= 1


class TestErrorHandling:
    """Test error handling in LangChain compatibility layer."""

    def test_langchain_not_available_raises(self):
        """Test that ImportError is raised when LangChain is not available."""
        from agentic_brain.rag import langchain_compat

        # Mock LANGCHAIN_AVAILABLE as False
        original = langchain_compat.LANGCHAIN_AVAILABLE
        langchain_compat.LANGCHAIN_AVAILABLE = False

        try:
            with pytest.raises(ImportError, match="LangChain is required"):
                langchain_compat._check_langchain()
        finally:
            langchain_compat.LANGCHAIN_AVAILABLE = original

    @patch.object(Retriever, 'search')
    def test_retrieval_error_propagates(self, mock_search):
        """Test that retrieval errors are properly propagated."""
        from agentic_brain.rag.langchain_compat import AgenticBrainRetriever

        mock_search.side_effect = RuntimeError("Neo4j connection failed")

        retriever = AgenticBrainRetriever(k=5)

        with pytest.raises(RuntimeError, match="Neo4j connection failed"):
            retriever.invoke("test query")


class TestGraphRAGRetriever:
    """Test GraphRAG-specific retriever functionality."""

    def test_graphrag_retriever_init(self):
        """Test GraphRAGRetriever initialization."""
        from agentic_brain.rag.langchain_compat import GraphRAGRetriever

        # Create with minimal config (no actual Neo4j connection)
        with patch('agentic_brain.rag.langchain_compat.GraphRAGRetriever._graph_rag_instance'):
            retriever = GraphRAGRetriever(
                search_strategy="hybrid",
                k=10,
                include_communities=True
            )

            assert retriever.search_strategy == "hybrid"
            assert retriever.k == 10
            assert retriever.include_communities is True
