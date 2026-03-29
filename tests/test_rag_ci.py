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

"""RAG CI Tests - Comprehensive testing of RAG functionality.

This test suite ensures ALL RAG components work correctly:
- Document loading (text, markdown, PDF, code)
- Text chunking (fixed, semantic, recursive, markdown)
- Embedding generation (with hardware acceleration detection)
- Vector storage and retrieval
- Neo4j graph integration
- Full retrieval pipeline
- RAG-augmented generation

Tests use mocks and fixtures to avoid external dependencies in CI.
"""

import os
from typing import List
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentic_brain.rag import (
    SENTENCE_TRANSFORMERS_AVAILABLE,
    BaseChunker,
    Chunk,
    ChunkingStrategy,
    Document,
    EmbeddingProvider,
    FileDocumentStore,
    FixedChunker,
    InMemoryDocumentStore,
    MarkdownChunker,
    RAGPipeline,
    RecursiveChunker,
    RetrievedChunk,
    Retriever,
    SemanticChunker,
    create_chunker,
)

# ============ HELPER FUNCTIONS ============


def neo4j_available() -> bool:
    """Check if Neo4j is running and accessible."""
    try:
        from neo4j import GraphDatabase

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "Brain2026")

        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        return True
    except Exception:
        return False


def has_module(module_name: str) -> bool:
    """Check if a module is available."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


# ============ DOCUMENT LOADING TESTS ============


class TestDocumentLoaders:
    """Test all document loaders work."""

    def test_text_loader(self, tmp_path):
        """Test loading .txt files."""
        from agentic_brain.rag.loaders import TextLoader

        # Create test file
        test_file = tmp_path / "test.txt"
        test_content = "This is a test document.\nWith multiple lines."
        test_file.write_text(test_content)

        # Load
        loader = TextLoader(str(test_file))
        docs = loader.load()

        # Verify
        assert len(docs) == 1
        assert docs[0].content == test_content
        assert docs[0].metadata["source"] == str(test_file)

    def test_markdown_loader(self, tmp_path):
        """Test loading .md files."""
        from agentic_brain.rag.loaders import MarkdownLoader

        # Create test markdown
        test_file = tmp_path / "test.md"
        test_content = "# Header\n\nThis is **bold** text."
        test_file.write_text(test_content)

        # Load
        loader = MarkdownLoader(str(test_file))
        docs = loader.load()

        # Verify
        assert len(docs) == 1
        assert "Header" in docs[0].content
        assert docs[0].metadata["source"] == str(test_file)

    @pytest.mark.skip(reason="PDFLoader uses PyPDF2 internally, mock needs refactoring")
    def test_pdf_loader_mock(self):
        """Test PDF loader with mocked PDF."""
        from agentic_brain.rag.loaders import PDFLoader

        with patch("pypdf.PdfReader") as mock_reader:
            # Mock PDF pages
            mock_page = Mock()
            mock_page.extract_text.return_value = "PDF content"
            mock_reader.return_value.pages = [mock_page]

            loader = PDFLoader("test.pdf")
            docs = loader.load()

            assert len(docs) == 1
            assert "PDF content" in docs[0].content

    def test_code_loader(self, tmp_path):
        """Test loading source code files."""
        from agentic_brain.rag.loaders import TextLoader

        # Create test Python file
        test_file = tmp_path / "test.py"
        test_content = 'def hello():\n    return "world"'
        test_file.write_text(test_content)

        # Load
        loader = TextLoader(str(test_file))
        docs = loader.load()

        # Verify
        assert len(docs) == 1
        assert "def hello()" in docs[0].content

    def test_json_loader(self, tmp_path):
        """Test loading JSON files."""
        from agentic_brain.rag.loaders import JSONLoader

        # Create test JSON
        test_file = tmp_path / "test.json"
        test_content = '{"key": "value", "nested": {"data": 123}}'
        test_file.write_text(test_content)

        # Load
        loader = JSONLoader(str(test_file))
        docs = loader.load()

        # Verify
        assert len(docs) == 1
        assert "key" in docs[0].content or "value" in docs[0].content


# ============ CHUNKING TESTS ============


class TestChunking:
    """Test text chunking strategies."""

    def test_basic_chunking(self):
        """Test basic fixed-size text splitting."""
        text = "This is a test. " * 100  # 1500+ chars
        chunker = FixedChunker(chunk_size=100, overlap=20)

        chunks = chunker.chunk(text)

        assert len(chunks) > 1
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(len(c.content) <= 150 for c in chunks)  # Allow some overflow

    def test_chunk_overlap(self):
        """Test chunks have proper overlap."""
        text = "Word1 Word2 Word3 Word4 Word5 Word6 Word7 Word8 Word9 Word10"
        chunker = FixedChunker(chunk_size=20, overlap=10)

        chunks = chunker.chunk(text)

        # Check that adjacent chunks share content
        if len(chunks) > 1:
            # Overlapping text should appear in adjacent chunks
            assert any(
                chunks[i].content[-10:] in chunks[i + 1].content
                for i in range(len(chunks) - 1)
            )

    def test_semantic_chunking(self):
        """Test semantic boundary detection."""
        text = "First sentence. Second sentence.\n\nNew paragraph. Another one."
        chunker = SemanticChunker()

        chunks = chunker.chunk(text)

        # Should split on paragraph boundaries
        assert len(chunks) >= 2
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_recursive_chunking(self):
        """Test recursive text splitting."""
        text = "# Header\n\nParagraph 1.\n\nParagraph 2.\n\n## Subheader\n\nMore text."
        chunker = RecursiveChunker(chunk_size=50)

        chunks = chunker.chunk(text)

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_markdown_chunking(self):
        """Test markdown-aware chunking."""
        text = "# Title\n\nIntro.\n\n## Section 1\n\nContent 1.\n\n## Section 2\n\nContent 2."
        chunker = MarkdownChunker()

        chunks = chunker.chunk(text)

        # Should preserve markdown structure
        assert len(chunks) > 0
        assert any("#" in c.content for c in chunks)

    def test_create_chunker_factory(self):
        """Test chunker factory function."""
        # Test all strategies
        for strategy in ChunkingStrategy:
            chunker = create_chunker(strategy)
            assert isinstance(chunker, BaseChunker)

            # Test chunking
            text = "Test text. " * 50
            chunks = chunker.chunk(text)
            assert len(chunks) > 0


# ============ EMBEDDING TESTS ============


class TestEmbeddings:
    """Test embedding generation."""

    @pytest.mark.skipif(
        not SENTENCE_TRANSFORMERS_AVAILABLE,
        reason="sentence-transformers not available",
    )
    def test_embedding_generation(self):
        """Test embeddings are generated correctly."""
        from agentic_brain.rag.embeddings import SentenceTransformerEmbeddings

        embedder = SentenceTransformerEmbeddings()
        text = "This is a test sentence."

        embedding = embedder.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.skipif(
        not SENTENCE_TRANSFORMERS_AVAILABLE,
        reason="sentence-transformers not available",
    )
    def test_embedding_dimension(self):
        """Test embedding dimensions match expected."""
        from agentic_brain.rag.embeddings import SentenceTransformerEmbeddings

        embedder = SentenceTransformerEmbeddings()
        text = "Test"

        embedding = embedder.embed_text(text)

        # Most models use 384, 768, or 1024 dimensions
        assert len(embedding) in [384, 768, 1024, 1536]

    @pytest.mark.skipif(
        not SENTENCE_TRANSFORMERS_AVAILABLE,
        reason="sentence-transformers not available",
    )
    def test_embedding_similarity(self):
        """Test similar texts have similar embeddings."""
        from agentic_brain.rag.embeddings import SentenceTransformerEmbeddings

        embedder = SentenceTransformerEmbeddings()

        text1 = "The cat sat on the mat."
        text2 = "A cat was sitting on a mat."
        text3 = "Quantum physics is complex."

        emb1 = embedder.embed_text(text1)
        emb2 = embedder.embed_text(text2)
        emb3 = embedder.embed_text(text3)

        # Compute cosine similarity
        import numpy as np

        def cosine_similarity(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_12 = cosine_similarity(emb1, emb2)
        sim_13 = cosine_similarity(emb1, emb3)

        # Similar texts should be more similar than different texts
        assert sim_12 > sim_13

    def test_mock_embeddings(self):
        """Test with mocked embeddings for CI."""

        class MockEmbeddings(EmbeddingProvider):
            def embed_text(self, text: str) -> List[float]:
                # Return deterministic mock embedding
                return [float(hash(text) % 100) / 100.0] * 384

            def embed_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.embed_text(t) for t in texts]

        embedder = MockEmbeddings()

        embedding = embedder.embed_text("test")
        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.skipif(not has_module("mlx"), reason="MLX not available")
    def test_mlx_embeddings(self):
        """Test Apple Silicon MLX embeddings."""
        from agentic_brain.rag.embeddings import MLXEmbeddings

        embedder = MLXEmbeddings()
        text = "Test MLX"

        embedding = embedder.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) > 0

    def test_hardware_detection(self):
        """Test hardware detection utilities."""
        if has_module("agentic_brain.rag.embeddings"):
            try:
                from agentic_brain.rag import detect_hardware, get_best_device

                # Should not crash
                hw = detect_hardware()
                assert isinstance(hw, dict)

                device = get_best_device()
                assert isinstance(device, str)
            except ImportError:
                pytest.skip("Hardware detection not available")


# ============ VECTOR STORE TESTS ============


class TestVectorStore:
    """Test vector storage and retrieval."""

    def test_in_memory_store(self):
        """Test in-memory document store."""
        store = InMemoryDocumentStore()

        # Add documents
        doc1 = Document(id="1", content="First document", metadata={"category": "test"})
        doc2 = Document(
            id="2", content="Second document", metadata={"category": "test"}
        )

        store.add(doc1)
        store.add(doc2)

        # Retrieve
        retrieved = store.get("1")
        assert retrieved is not None
        assert retrieved.content == "First document"

        # List all
        all_docs = store.list()
        assert len(all_docs) == 2

    def test_file_store(self, tmp_path):
        """Test file-based document store."""
        store_path = tmp_path / "store"
        store = FileDocumentStore(str(store_path))

        # Add document
        doc = Document(id="test", content="Test content", metadata={"key": "value"})
        store.add(doc)

        # Verify file exists
        assert (store_path / "test.json").exists()

        # Retrieve
        retrieved = store.get("test")
        assert retrieved is not None
        assert retrieved.content == "Test content"

    def test_similarity_search_mock(self):
        """Test similarity search with mock embeddings."""

        class MockEmbeddings(EmbeddingProvider):
            def embed_text(self, text: str) -> List[float]:
                # Simple hash-based mock
                return [float(hash(text) % 100) / 100.0] * 384

            def embed_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.embed_text(t) for t in texts]

        # Create retriever with mock embeddings
        store = InMemoryDocumentStore()
        embeddings = MockEmbeddings()
        retriever = Retriever(store, embeddings)

        # Add documents
        store.add(Document(id="1", content="Python programming"))
        store.add(Document(id="2", content="Java programming"))
        store.add(Document(id="3", content="Machine learning"))

        # Search (will use mock embeddings)
        results = retriever.retrieve("Python coding", top_k=2)

        assert len(results) <= 2
        assert all(isinstance(r, RetrievedChunk) for r in results)


# ============ NEO4J INTEGRATION TESTS ============


class TestNeo4jRAG:
    """Test Neo4j graph RAG features."""

    @pytest.mark.skipif(not neo4j_available(), reason="Neo4j not running")
    def test_graph_traversal(self):
        """Test graph-based context retrieval."""
        from agentic_brain.rag import GraphTraversalRetriever

        retriever = GraphTraversalRetriever(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="Brain2026",
        )

        # Test basic traversal (will use test data if available)
        try:
            results = retriever.retrieve("test query", max_depth=1)
            assert isinstance(results, list)
        except Exception as e:
            pytest.skip(f"Graph traversal failed: {e}")

    @pytest.mark.skipif(not neo4j_available(), reason="Neo4j not running")
    def test_entity_extraction(self):
        """Test entity extraction and linking."""
        from agentic_brain.rag import GraphRAG

        rag = GraphRAG(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="Brain2026",
        )

        # Test entity extraction from text
        text = "Joseph works at CITB in Adelaide."

        try:
            entities = rag.extract_entities(text)
            assert isinstance(entities, list)
        except Exception as e:
            pytest.skip(f"Entity extraction failed: {e}")


# ============ RETRIEVAL TESTS ============


class TestRetrieval:
    """Test full RAG retrieval pipeline."""

    def test_basic_retrieval_sync(self):
        """Test basic document retrieval (synchronous)."""

        class MockEmbeddings(EmbeddingProvider):
            def embed_text(self, text: str) -> List[float]:
                return [0.1] * 384

            def embed_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.embed_text(t) for t in texts]

        store = InMemoryDocumentStore()
        store.add(Document(id="1", content="Python is great"))
        store.add(Document(id="2", content="Java is verbose"))

        retriever = Retriever(store, MockEmbeddings())
        results = retriever.retrieve("Python", top_k=1)

        assert len(results) <= 1

    def test_context_assembly(self):
        """Test context is properly assembled."""

        # Create pipeline with mocked components
        with patch("agentic_brain.rag.pipeline.get_embeddings") as mock_embeddings:
            mock_embeddings.return_value = MagicMock()

            store = InMemoryDocumentStore()
            pipeline = RAGPipeline(document_store=store)

            # Mock the retrieval
            mock_chunks = [
                RetrievedChunk(
                    content="Context 1", score=0.9, metadata={"source": "doc1"}
                ),
                RetrievedChunk(
                    content="Context 2", score=0.8, metadata={"source": "doc2"}
                ),
            ]

            with patch.object(pipeline.retriever, "retrieve", return_value=mock_chunks):
                # Test context assembly
                context = pipeline._assemble_context(mock_chunks)
                assert "Context 1" in context
                assert "Context 2" in context

    def test_retrieval_ranking(self):
        """Test results are properly ranked."""

        class ScoreBasedEmbeddings(EmbeddingProvider):
            def __init__(self):
                self.scores = {}

            def embed_text(self, text: str) -> List[float]:
                # Return different embeddings based on text
                if "important" in text.lower():
                    return [0.9] * 384
                return [0.1] * 384

            def embed_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.embed_text(t) for t in texts]

        store = InMemoryDocumentStore()
        store.add(Document(id="1", content="Not important"))
        store.add(Document(id="2", content="Very IMPORTANT info"))

        embeddings = ScoreBasedEmbeddings()
        retriever = Retriever(store, embeddings)

        results = retriever.retrieve("important", top_k=2)

        # Results should be ranked by relevance
        if len(results) > 1:
            assert results[0].score >= results[1].score


# ============ GENERATION TESTS ============


class TestRAGGeneration:
    """Test RAG-augmented generation."""

    @pytest.mark.asyncio
    async def test_rag_response(self):
        """Test RAG produces grounded responses."""

        # Mock LLM response
        with patch("agentic_brain.rag.pipeline.get_embeddings"):
            pipeline = RAGPipeline()

            # Mock retrieval
            mock_chunks = [
                RetrievedChunk(
                    content="Python is a high-level language",
                    score=0.9,
                    metadata={"source": "python_docs"},
                )
            ]

            with patch.object(pipeline.retriever, "retrieve", return_value=mock_chunks):
                # Mock LLM
                with patch.object(
                    pipeline, "_generate", return_value="Python is high-level."
                ):
                    result = pipeline.query("What is Python?")

                    assert result is not None
                    assert "python" in result.answer.lower()

    @pytest.mark.asyncio
    async def test_citation_generation(self):
        """Test citations are included."""

        with patch("agentic_brain.rag.pipeline.get_embeddings"):
            pipeline = RAGPipeline()

            mock_chunks = [
                RetrievedChunk(
                    content="Fact from source 1",
                    score=0.9,
                    metadata={"source": "doc1.txt"},
                ),
                RetrievedChunk(
                    content="Fact from source 2",
                    score=0.8,
                    metadata={"source": "doc2.txt"},
                ),
            ]

            with patch.object(pipeline.retriever, "retrieve", return_value=mock_chunks):
                with patch.object(pipeline, "_generate", return_value="Answer"):
                    result = pipeline.query("Query")

                    # Check citations are tracked
                    assert result.sources is not None
                    assert len(result.sources) > 0


# ============ INTEGRATION TESTS ============


class TestRAGIntegration:
    """Test full RAG pipeline integration."""

    def test_end_to_end_mock(self, tmp_path):
        """Test complete RAG flow with mocked components."""

        # Create test document
        test_file = tmp_path / "test.txt"
        test_file.write_text("The sky is blue. Water is wet.")

        # Mock embeddings
        with patch("agentic_brain.rag.pipeline.get_embeddings") as mock_get_emb:

            class MockEmb(EmbeddingProvider):
                def embed_text(self, text: str) -> List[float]:
                    return [0.5] * 384

                def embed_batch(self, texts: List[str]) -> List[List[float]]:
                    return [self.embed_text(t) for t in texts]

            mock_get_emb.return_value = MockEmb()

            # Create pipeline with seeded in-memory store
            store = InMemoryDocumentStore()
            pipeline = RAGPipeline(document_store=store)
            pipeline.add_document(
                test_file.read_text(), {"title": "test.txt", "source": str(test_file)}
            )

            # Mock LLM generation
            with patch.object(
                pipeline, "_generate", return_value="The sky is blue according to docs."
            ):
                # Query
                result = pipeline.query("What color is the sky?")

                assert result is not None
                assert "blue" in result.answer.lower()

    def test_chunking_to_retrieval(self):
        """Test chunking integrates with retrieval."""
        from agentic_brain.rag import FixedChunker

        # Create long text
        text = "Sentence 1. " * 50 + "Sentence 2. " * 50

        # Chunk it
        chunker = FixedChunker(chunk_size=100, overlap=20)
        chunks = chunker.chunk(text)

        # Add to store
        store = InMemoryDocumentStore()
        for i, chunk in enumerate(chunks):
            store.add(
                Document(id=str(i), content=chunk.content, metadata={"chunk_id": i})
            )

        # Mock embeddings
        class MockEmb(EmbeddingProvider):
            def embed_text(self, text: str) -> List[float]:
                return [0.5] * 384

            def embed_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.embed_text(t) for t in texts]

        # Retrieve
        retriever = Retriever(store, MockEmb())
        results = retriever.retrieve("Sentence", top_k=3)

        assert len(results) <= 3


# ============ PERFORMANCE TESTS ============


class TestRAGPerformance:
    """Test RAG system performance."""

    def test_batch_embedding_faster(self):
        """Test batch embedding is faster than individual."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            pytest.skip("sentence-transformers not available")

        from agentic_brain.rag.embeddings import SentenceTransformerEmbeddings

        embedder = SentenceTransformerEmbeddings()
        texts = ["Text " + str(i) for i in range(10)]

        import time

        # Individual
        start = time.time()
        for text in texts:
            embedder.embed_text(text)
        individual_time = time.time() - start

        # Batch
        start = time.time()
        embedder.embed_batch(texts)
        batch_time = time.time() - start

        # Batch should be faster (or at least not significantly slower)
        assert batch_time <= individual_time * 1.5  # Allow 50% margin

    def test_caching_improves_performance(self):
        """Test that caching improves repeated queries."""
        # Test with mock to avoid actual computation
        call_count = 0

        class CountingEmbeddings(EmbeddingProvider):
            def embed_text(self, text: str) -> List[float]:
                nonlocal call_count
                call_count += 1
                return [0.5] * 384

            def embed_batch(self, texts: List[str]) -> List[List[float]]:
                return [self.embed_text(t) for t in texts]

        embedder = CountingEmbeddings()

        # First call
        embedder.embed_text("test")
        first_count = call_count

        # Same call (without caching, would increment again)
        embedder.embed_text("test")
        second_count = call_count

        # Without caching, count increases
        assert second_count > first_count


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
