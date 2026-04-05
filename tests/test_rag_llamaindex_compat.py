# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tests for LlamaIndex Compatibility Layer.

Verifies that the LlamaIndex-compatible API works correctly and provides
a seamless migration path for LlamaIndex users.
"""

import pytest
from typing import List
from dataclasses import dataclass

# Import the compatibility layer
from agentic_brain.rag.llamaindex_compat import (
    # Core data structures
    TextNode,
    LIDocument,
    NodeWithScore,
    Response,
    # Retrievers
    BaseRetriever,
    AgenticRetriever,
    LlamaIndexGraphRAGRetriever,
    # Synthesizers
    ResponseMode,
    BaseSynthesizer,
    AgenticSynthesizer,
    # Query engines
    BaseQueryEngine,
    AgenticQueryEngine,
    GraphRAGQueryEngine,
    # Indexes
    BaseIndex,
    AgenticIndex,
    GraphRAGIndex,
    # Loaders
    SimpleDirectoryReader,
    # Settings
    Settings,
    # Re-exports
    GraphRAGConfig,
    SearchStrategy,
)

from agentic_brain.rag.retriever import RetrievedChunk
from agentic_brain.rag.pipeline import RAGResult
from agentic_brain.rag.store import Document, InMemoryDocumentStore


class TestTextNode:
    """Test TextNode LlamaIndex-compatible data structure."""

    def test_basic_creation(self):
        """Test basic TextNode creation."""
        node = TextNode(text="Hello, world!")
        assert node.text == "Hello, world!"
        assert node.content == "Hello, world!"
        assert node.node_id is not None
        assert len(node.node_id) == 16  # SHA256 hash prefix

    def test_with_metadata(self):
        """Test TextNode with metadata."""
        node = TextNode(
            text="Document content",
            node_id="custom-id",
            metadata={"source": "test.txt", "page": 1},
        )
        assert node.node_id == "custom-id"
        assert node.id_ == "custom-id"  # LlamaIndex compatibility
        assert node.metadata["source"] == "test.txt"

    def test_get_content_modes(self):
        """Test get_content with different metadata modes."""
        node = TextNode(
            text="Main content",
            metadata={"title": "Test", "author": "Alice"},
        )

        # No metadata
        assert node.get_content("none") == "Main content"

        # Embedded metadata
        content = node.get_content("embed")
        assert "Main content" in content
        assert "title: Test" in content

    def test_to_agentic_document(self):
        """Test conversion to Agentic Brain Document."""
        node = TextNode(
            text="Test content",
            node_id="doc-1",
            metadata={"key": "value"},
        )
        doc = node.to_agentic_document()

        assert isinstance(doc, Document)
        assert doc.id == "doc-1"
        assert doc.content == "Test content"
        assert doc.metadata["key"] == "value"

    def test_from_agentic_document(self):
        """Test creation from Agentic Brain Document."""
        doc = Document(
            id="doc-1",
            content="Test content",
            metadata={"source": "test"},
        )
        node = TextNode.from_agentic_document(doc)

        assert node.node_id == "doc-1"
        assert node.text == "Test content"
        assert node.metadata["source"] == "test"

    def test_from_retrieved_chunk(self):
        """Test creation from RetrievedChunk."""
        chunk = RetrievedChunk(
            content="Chunk content",
            source="knowledge_base",
            score=0.95,
            metadata={"doc_id": "doc-1"},
        )
        node = TextNode.from_retrieved_chunk(chunk)

        assert node.text == "Chunk content"
        assert node.metadata["source"] == "knowledge_base"
        assert node.metadata["score"] == 0.95


class TestNodeWithScore:
    """Test NodeWithScore wrapper."""

    def test_basic_creation(self):
        """Test basic NodeWithScore creation."""
        node = TextNode(text="Test content")
        nws = NodeWithScore(node=node, score=0.85)

        assert nws.node == node
        assert nws.score == 0.85
        assert nws.text == "Test content"

    def test_from_retrieved_chunk(self):
        """Test creation from RetrievedChunk."""
        chunk = RetrievedChunk(
            content="Chunk content",
            source="test",
            score=0.9,
        )
        nws = NodeWithScore.from_retrieved_chunk(chunk)

        assert nws.score == 0.9
        assert nws.node.text == "Chunk content"


class TestResponse:
    """Test Response object."""

    def test_basic_creation(self):
        """Test basic Response creation."""
        response = Response(
            response="This is the answer.",
            source_nodes=[],
            metadata={"model": "test"},
        )

        assert str(response) == "This is the answer."
        assert response.metadata["model"] == "test"

    def test_from_rag_result(self):
        """Test creation from RAGResult."""
        chunks = [
            RetrievedChunk(content="Source 1", source="doc1", score=0.9),
            RetrievedChunk(content="Source 2", source="doc2", score=0.8),
        ]
        result = RAGResult(
            query="What is RAG?",
            answer="RAG is retrieval-augmented generation.",
            sources=chunks,
            confidence=0.85,
            model="gpt-4",
            cached=False,
            generation_time_ms=150.0,
        )

        response = Response.from_rag_result(result)

        assert response.response == "RAG is retrieval-augmented generation."
        assert len(response.source_nodes) == 2
        assert response.source_nodes[0].score == 0.9
        assert response.metadata["confidence"] == 0.85

    def test_formatted_sources(self):
        """Test get_formatted_sources method."""
        node1 = TextNode(
            text="First source content that is quite long and might be truncated"
        )
        node2 = TextNode(text="Second source")
        response = Response(
            response="Answer",
            source_nodes=[
                NodeWithScore(node=node1, score=0.9),
                NodeWithScore(node=node2, score=0.8),
            ],
        )

        formatted = response.get_formatted_sources(length=20)
        assert "Source 1" in formatted
        assert "score: 0.900" in formatted


class TestAgenticRetriever:
    """Test AgenticRetriever LlamaIndex-compatible interface."""

    def test_initialization(self):
        """Test retriever initialization."""
        store = InMemoryDocumentStore()
        store.add("Test document about Python programming.")

        retriever = AgenticRetriever(
            document_store=store,
            similarity_top_k=3,
        )

        assert retriever.similarity_top_k == 3

    def test_retrieve_interface(self):
        """Test that retrieve() returns NodeWithScore list."""
        store = InMemoryDocumentStore()
        store.add("Python is a programming language.")
        store.add("Java is also a programming language.")

        retriever = AgenticRetriever(
            document_store=store,
            similarity_top_k=2,
        )

        results = retriever.retrieve("programming")

        assert isinstance(results, list)
        for result in results:
            assert isinstance(result, NodeWithScore)
            assert isinstance(result.node, TextNode)

    def test_base_retriever_interface(self):
        """Test that AgenticRetriever implements BaseRetriever."""
        retriever = AgenticRetriever(similarity_top_k=5)
        assert isinstance(retriever, BaseRetriever)


class TestAgenticSynthesizer:
    """Test AgenticSynthesizer response synthesis."""

    def test_initialization(self):
        """Test synthesizer initialization."""
        synthesizer = AgenticSynthesizer(
            response_mode=ResponseMode.COMPACT,
            llm_model="gpt-4o-mini",
        )

        assert synthesizer.response_mode == ResponseMode.COMPACT
        assert synthesizer.llm_model == "gpt-4o-mini"

    def test_synthesize_interface(self):
        """Test that synthesize() returns Response."""
        synthesizer = AgenticSynthesizer()

        nodes = [
            NodeWithScore(
                node=TextNode(text="Python is versatile."),
                score=0.9,
            ),
        ]

        response = synthesizer.synthesize("What is Python?", nodes)

        assert isinstance(response, Response)
        assert len(response.source_nodes) > 0


class TestAgenticQueryEngine:
    """Test AgenticQueryEngine query interface."""

    def test_initialization(self):
        """Test query engine initialization."""
        engine = AgenticQueryEngine(similarity_top_k=5)

        assert engine.similarity_top_k == 5
        assert engine.retriever is not None
        assert engine.synthesizer is not None

    def test_custom_components(self):
        """Test query engine with custom retriever and synthesizer."""
        store = InMemoryDocumentStore()
        retriever = AgenticRetriever(document_store=store)
        synthesizer = AgenticSynthesizer(response_mode=ResponseMode.REFINE)

        engine = AgenticQueryEngine(
            retriever=retriever,
            synthesizer=synthesizer,
        )

        assert engine.retriever == retriever
        assert engine.synthesizer == synthesizer

    def test_query_interface(self):
        """Test that query() returns Response."""
        store = InMemoryDocumentStore()
        store.add("GraphRAG combines graph databases with RAG for enhanced retrieval.")

        engine = AgenticQueryEngine(
            retriever=AgenticRetriever(document_store=store),
        )

        response = engine.query("What is GraphRAG?")

        assert isinstance(response, Response)


class TestAgenticIndex:
    """Test AgenticIndex document indexing."""

    def test_from_documents_textnodes(self):
        """Test index creation from TextNode list."""
        documents = [
            TextNode(text="Document 1 content"),
            TextNode(text="Document 2 content"),
        ]

        index = AgenticIndex.from_documents(documents, show_progress=False)

        assert index._store.count() == 2

    def test_from_documents_dicts(self):
        """Test index creation from dict list."""
        documents = [
            {"text": "First document"},
            {"content": "Second document"},
            {"page_content": "Third document"},  # LangChain style
        ]

        index = AgenticIndex.from_documents(documents, show_progress=False)

        assert index._store.count() == 3

    def test_from_documents_agentic(self):
        """Test index creation from Agentic Brain Documents."""
        documents = [
            Document(id="doc-1", content="First"),
            Document(id="doc-2", content="Second"),
        ]

        index = AgenticIndex.from_documents(documents, show_progress=False)

        assert index._store.count() == 2

    def test_as_query_engine(self):
        """Test getting query engine from index."""
        documents = [TextNode(text="Test content")]
        index = AgenticIndex.from_documents(documents, show_progress=False)

        engine = index.as_query_engine(similarity_top_k=3)

        assert isinstance(engine, BaseQueryEngine)

    def test_as_retriever(self):
        """Test getting retriever from index."""
        documents = [TextNode(text="Test content")]
        index = AgenticIndex.from_documents(documents, show_progress=False)

        retriever = index.as_retriever(similarity_top_k=3)

        assert isinstance(retriever, BaseRetriever)

    def test_insert_and_delete(self):
        """Test document insertion and deletion."""
        index = AgenticIndex()

        # Insert
        node = TextNode(text="New document", node_id="new-doc")
        index.insert(node)
        assert index._store.count() == 1

        # Delete
        index.delete("new-doc")
        assert index._store.count() == 0

    def test_refresh(self):
        """Test document refresh."""
        documents = [
            TextNode(text="Original content", node_id="doc-1"),
        ]
        index = AgenticIndex.from_documents(documents, show_progress=False)

        # Refresh with same content (should not update)
        results = index.refresh(
            [
                TextNode(text="Original content", node_id="doc-1"),
            ]
        )
        assert results == [False]

        # Refresh with new content (should update)
        results = index.refresh(
            [
                TextNode(text="Updated content", node_id="doc-1"),
            ]
        )
        assert results == [True]


class TestSimpleDirectoryReader:
    """Test SimpleDirectoryReader file loading."""

    def test_initialization(self):
        """Test reader initialization."""
        reader = SimpleDirectoryReader(
            input_dir="./data",
            recursive=True,
            required_exts=[".txt", ".md"],
        )

        assert reader.recursive is True
        assert ".txt" in reader.required_exts

    def test_load_nonexistent_dir(self):
        """Test loading from non-existent directory."""
        reader = SimpleDirectoryReader(
            input_dir="./nonexistent_directory_12345",
        )

        documents = reader.load_data(show_progress=False)
        assert documents == []


class TestSettings:
    """Test global Settings configuration."""

    def test_default_settings(self):
        """Test default settings values."""
        assert Settings._llm == "gpt-4o-mini"
        assert Settings._embed_model == "all-MiniLM-L6-v2"
        assert Settings._chunk_size == 512

    def test_set_settings(self):
        """Test setting configuration values."""
        original_llm = Settings._llm

        Settings.set_llm("gpt-4")
        assert Settings._llm == "gpt-4"

        # Reset
        Settings.set_llm(original_llm)


class TestGraphRAGIntegration:
    """Test GraphRAG-specific compatibility features."""

    def test_search_strategy_enum(self):
        """Test SearchStrategy enum values."""
        assert SearchStrategy.VECTOR.value == "vector"
        assert SearchStrategy.GRAPH.value == "graph"
        assert SearchStrategy.HYBRID.value == "hybrid"
        assert SearchStrategy.COMMUNITY.value == "community"

    def test_graphrag_config(self):
        """Test GraphRAGConfig initialization."""
        config = GraphRAGConfig(
            neo4j_uri="bolt://localhost:7687",
            enable_communities=True,
            embedding_dim=384,
        )

        assert config.enable_communities is True
        assert config.embedding_dim == 384

    def test_llamaindex_graphrag_retriever_init(self):
        """Test LlamaIndexGraphRAGRetriever initialization."""
        retriever = LlamaIndexGraphRAGRetriever(
            strategy=SearchStrategy.HYBRID,
            similarity_top_k=10,
        )

        assert retriever.strategy == SearchStrategy.HYBRID
        assert retriever.similarity_top_k == 10


class TestLlamaIndexMigration:
    """
    Test migration scenarios from LlamaIndex to Agentic Brain.

    These tests verify that common LlamaIndex patterns work with
    the compatibility layer.
    """

    def test_basic_rag_workflow(self):
        """Test basic RAG workflow similar to LlamaIndex."""
        # 1. Create documents (like LlamaIndex)
        documents = [
            TextNode(text="Python is a high-level programming language."),
            TextNode(text="Machine learning uses statistical methods."),
            TextNode(text="GraphRAG enhances retrieval with knowledge graphs."),
        ]

        # 2. Create index (like LlamaIndex VectorStoreIndex)
        index = AgenticIndex.from_documents(documents, show_progress=False)

        # 3. Get query engine (like LlamaIndex)
        query_engine = index.as_query_engine(similarity_top_k=2)

        # 4. Query (like LlamaIndex)
        response = query_engine.query("What is Python?")

        # 5. Access results (like LlamaIndex)
        assert isinstance(response, Response)
        assert response.response  # Has answer
        assert isinstance(response.source_nodes, list)

    def test_custom_retriever_workflow(self):
        """Test custom retriever workflow."""
        # Create store
        store = InMemoryDocumentStore()
        store.add("Document about AI and machine learning.")

        # Use custom retriever
        retriever = AgenticRetriever(
            document_store=store,
            similarity_top_k=3,
        )

        # Retrieve directly
        nodes = retriever.retrieve("machine learning")

        assert all(isinstance(n, NodeWithScore) for n in nodes)

    def test_response_synthesis_workflow(self):
        """Test response synthesis like LlamaIndex."""
        # Create synthesizer with specific mode
        synthesizer = AgenticSynthesizer(
            response_mode=ResponseMode.COMPACT,
        )

        # Create nodes
        nodes = [
            NodeWithScore(
                node=TextNode(text="AI is transforming industries."),
                score=0.9,
            ),
            NodeWithScore(
                node=TextNode(text="Machine learning is a subset of AI."),
                score=0.85,
            ),
        ]

        # Synthesize response
        response = synthesizer.synthesize("What is AI?", nodes)

        assert isinstance(response, Response)
        assert len(response.source_nodes) == 2


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_documents(self):
        """Test handling of empty document list."""
        index = AgenticIndex.from_documents([], show_progress=False)
        assert index._store.count() == 0

    def test_invalid_document_type(self):
        """Test handling of invalid document types."""
        with pytest.raises(TypeError):
            AgenticIndex.from_documents([123, 456], show_progress=False)

    def test_none_text_in_node(self):
        """Test TextNode requires text."""
        with pytest.raises(TypeError):
            TextNode()  # Missing required 'text' argument

    def test_empty_retrieval(self):
        """Test retrieval from empty store."""
        store = InMemoryDocumentStore()
        retriever = AgenticRetriever(document_store=store)

        results = retriever.retrieve("anything")
        assert results == []


# Run with: pytest tests/test_rag_llamaindex_compat.py -v
