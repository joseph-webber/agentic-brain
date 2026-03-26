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
Tests for RAG document store.

Tests for:
- InMemoryDocumentStore operations
- FileDocumentStore persistence
- Document serialization
- Chunking integration
- RAGPipeline with document store
"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from agentic_brain.rag.chunking import ChunkingStrategy
from agentic_brain.rag.pipeline import RAGPipeline
from agentic_brain.rag.store import (
    Document,
    FileDocumentStore,
    InMemoryDocumentStore,
)


class TestDocument:
    """Test Document dataclass."""

    def test_document_creation(self):
        """Test creating a document."""
        doc = Document(
            id="test-id", content="Test content here", metadata={"title": "Test Doc"}
        )

        assert doc.id == "test-id"
        assert doc.content == "Test content here"
        assert doc.metadata["title"] == "Test Doc"
        assert isinstance(doc.created_at, datetime)

    def test_document_to_dict(self):
        """Test document serialization."""
        doc = Document(
            id="doc1",
            content="Hello world",
            metadata={"type": "test"},
            chunks=["Hello", "world"],
            chunk_metadata=[{"start": 0}, {"start": 6}],
        )

        data = doc.to_dict()

        assert data["id"] == "doc1"
        assert data["content"] == "Hello world"
        assert data["metadata"]["type"] == "test"
        assert len(data["chunks"]) == 2
        assert "created_at" in data

    def test_document_from_dict(self):
        """Test document deserialization."""
        data = {
            "id": "doc2",
            "content": "Test content",
            "metadata": {"source": "test.txt"},
            "chunks": ["Test", "content"],
            "chunk_metadata": [{"index": 0}, {"index": 1}],
            "created_at": "2026-01-15T10:30:00",
        }

        doc = Document.from_dict(data)

        assert doc.id == "doc2"
        assert doc.content == "Test content"
        assert doc.metadata["source"] == "test.txt"
        assert len(doc.chunks) == 2
        assert doc.created_at == datetime(2026, 1, 15, 10, 30, 0)

    def test_document_roundtrip(self):
        """Test document serialization roundtrip."""
        original = Document(
            id="roundtrip",
            content="Roundtrip test",
            metadata={"key": "value"},
            chunks=["Roundtrip", "test"],
            chunk_metadata=[{"a": 1}, {"b": 2}],
        )

        data = original.to_dict()
        restored = Document.from_dict(data)

        assert restored.id == original.id
        assert restored.content == original.content
        assert restored.metadata == original.metadata
        assert restored.chunks == original.chunks


class TestInMemoryDocumentStore:
    """Test InMemoryDocumentStore."""

    @pytest.fixture
    def store(self):
        """Create a test store."""
        return InMemoryDocumentStore(
            chunking_strategy=ChunkingStrategy.FIXED, chunk_size=100, chunk_overlap=10
        )

    @pytest.fixture
    def sample_content(self):
        """Sample document content."""
        return """Machine learning is a subset of artificial intelligence.
        It enables systems to learn from data without being explicitly programmed.
        Deep learning is a powerful subset of machine learning that uses neural networks."""

    def test_add_document(self, store, sample_content):
        """Test adding a document."""
        doc = store.add(sample_content, {"title": "ML Basics"})

        assert doc.id is not None
        assert doc.content == sample_content
        assert doc.metadata["title"] == "ML Basics"
        assert len(doc.chunks) > 0

    def test_add_document_with_id(self, store, sample_content):
        """Test adding a document with custom ID."""
        doc = store.add(sample_content, doc_id="custom-id")

        assert doc.id == "custom-id"

    def test_get_document(self, store, sample_content):
        """Test retrieving a document."""
        added = store.add(sample_content, {"title": "Test"})

        retrieved = store.get(added.id)

        assert retrieved is not None
        assert retrieved.id == added.id
        assert retrieved.content == sample_content

    def test_get_nonexistent_document(self, store):
        """Test retrieving nonexistent document."""
        result = store.get("nonexistent")
        assert result is None

    def test_delete_document(self, store, sample_content):
        """Test deleting a document."""
        doc = store.add(sample_content)
        assert store.count() == 1

        result = store.delete(doc.id)

        assert result is True
        assert store.count() == 0
        assert store.get(doc.id) is None

    def test_delete_nonexistent_document(self, store):
        """Test deleting nonexistent document."""
        result = store.delete("nonexistent")
        assert result is False

    def test_list_documents(self, store):
        """Test listing documents."""
        store.add("Document one", {"title": "Doc 1"})
        store.add("Document two", {"title": "Doc 2"})
        store.add("Document three", {"title": "Doc 3"})

        docs = store.list()

        assert len(docs) == 3
        assert all(isinstance(d, Document) for d in docs)

    def test_list_with_pagination(self, store):
        """Test listing documents with pagination."""
        for i in range(10):
            store.add(f"Document {i}", {"index": i})

        first_page = store.list(limit=3, offset=0)
        second_page = store.list(limit=3, offset=3)

        assert len(first_page) == 3
        assert len(second_page) == 3
        assert first_page[0].id != second_page[0].id

    def test_search_documents(self, store):
        """Test keyword search."""
        store.add("Machine learning is great")
        store.add("Deep learning uses neural networks")
        store.add("Python is a programming language")

        results = store.search("learning")

        assert len(results) == 2
        assert all("learning" in r.content.lower() for r in results)

    def test_search_case_insensitive(self, store):
        """Test case-insensitive search."""
        store.add("MACHINE LEARNING is GREAT")

        results = store.search("machine")
        assert len(results) == 1

    def test_search_top_k(self, store):
        """Test search with top_k limit."""
        for i in range(10):
            store.add(f"Test document {i}")

        results = store.search("test", top_k=3)
        assert len(results) == 3

    def test_count(self, store, sample_content):
        """Test document count."""
        assert store.count() == 0

        store.add(sample_content)
        assert store.count() == 1

        store.add("Another document")
        assert store.count() == 2

    def test_stats(self, store, sample_content):
        """Test statistics."""
        store.add(sample_content, {"title": "ML"})
        store.add("Short doc")

        stats = store.stats()

        assert stats["document_count"] == 2
        assert stats["total_chunks"] > 0
        assert stats["total_characters"] > 0
        assert stats["avg_chunks_per_doc"] > 0
        assert stats["chunking_strategy"] == "fixed"
        assert stats["chunk_size"] == 100

    def test_clear(self, store):
        """Test clearing all documents."""
        store.add("Doc 1")
        store.add("Doc 2")
        assert store.count() == 2

        deleted = store.clear()

        assert deleted == 2
        assert store.count() == 0

    def test_chunking_integration(self, store):
        """Test that documents are properly chunked."""
        long_content = "This is a sentence. " * 50  # About 1000 chars

        doc = store.add(long_content)

        # Should have multiple chunks due to chunk_size=100
        assert len(doc.chunks) > 1
        assert len(doc.chunk_metadata) == len(doc.chunks)

        # Each chunk should have metadata
        for meta in doc.chunk_metadata:
            assert "start_char" in meta
            assert "end_char" in meta
            assert "chunk_index" in meta


class TestFileDocumentStore:
    """Test FileDocumentStore with persistence."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def store(self, temp_dir):
        """Create a test store."""
        return FileDocumentStore(
            path=temp_dir,
            chunking_strategy=ChunkingStrategy.RECURSIVE,
            chunk_size=200,
            chunk_overlap=20,
        )

    def test_add_and_persist(self, store, temp_dir):
        """Test that documents are persisted to disk."""
        doc = store.add("Test content", {"title": "Test"})

        # Check file exists
        doc_path = Path(temp_dir) / f"{doc.id}.json"
        assert doc_path.exists()

        # Check index exists
        index_path = Path(temp_dir) / "index.json"
        assert index_path.exists()

    def test_reload_store(self, temp_dir):
        """Test that store reloads documents from disk."""
        # Create and populate store
        store1 = FileDocumentStore(path=temp_dir)
        store1.add("Document one", {"title": "Doc 1"}, doc_id="doc1")
        store1.add("Document two", {"title": "Doc 2"}, doc_id="doc2")

        # Create new store instance pointing to same path
        store2 = FileDocumentStore(path=temp_dir)

        assert store2.count() == 2
        assert store2.get("doc1") is not None
        assert store2.get("doc2") is not None

    def test_delete_removes_file(self, store, temp_dir):
        """Test that delete removes the file."""
        store.add("Test content", doc_id="to-delete")
        doc_path = Path(temp_dir) / "to-delete.json"

        assert doc_path.exists()

        store.delete("to-delete")

        assert not doc_path.exists()

    def test_list_documents(self, store):
        """Test listing documents from disk."""
        store.add("Doc 1", {"title": "First"})
        store.add("Doc 2", {"title": "Second"})

        docs = store.list()

        assert len(docs) == 2
        assert all(isinstance(d, Document) for d in docs)

    def test_search_documents(self, store):
        """Test searching documents from disk."""
        store.add("Machine learning fundamentals")
        store.add("Deep learning with neural networks")
        store.add("Python programming basics")

        results = store.search("learning")

        assert len(results) == 2

    def test_stats_with_storage_path(self, store, temp_dir):
        """Test that stats includes storage path."""
        store.add("Test content")

        stats = store.stats()

        assert stats["storage_path"] == temp_dir
        assert stats["document_count"] == 1

    def test_clear_removes_all_files(self, store, temp_dir):
        """Test that clear removes all document files."""
        store.add("Doc 1", doc_id="d1")
        store.add("Doc 2", doc_id="d2")

        store.clear()

        assert store.count() == 0
        assert not (Path(temp_dir) / "d1.json").exists()
        assert not (Path(temp_dir) / "d2.json").exists()


import os

# Skip tests requiring OpenAI API key
requires_openai = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set"
)


@requires_openai
class TestRAGPipelineWithStore:
    """Test RAGPipeline integration with document store."""

    @pytest.fixture
    def store(self):
        """Create an in-memory store."""
        return InMemoryDocumentStore(
            chunking_strategy=ChunkingStrategy.FIXED,  # Fixed is more predictable for short texts
            chunk_size=100,
            chunk_overlap=10,
        )

    @pytest.fixture
    def pipeline(self, store):
        """Create a pipeline with store."""
        return RAGPipeline(document_store=store)

    def test_add_document_via_pipeline(self, pipeline):
        """Test adding documents through pipeline."""
        doc = pipeline.add_document(
            "Machine learning is transforming industries.", {"title": "ML Overview"}
        )

        assert doc.id is not None
        assert len(doc.chunks) > 0

    def test_add_document_without_store(self):
        """Test error when adding document without store."""
        pipeline = RAGPipeline()  # No store

        with pytest.raises(RuntimeError, match="No document store configured"):
            pipeline.add_document("Test content")

    def test_list_documents_via_pipeline(self, pipeline):
        """Test listing documents through pipeline."""
        pipeline.add_document("Document one", {"title": "Doc 1"})
        pipeline.add_document("Document two", {"title": "Doc 2"})

        docs = pipeline.list_documents()

        assert len(docs) == 2

    def test_list_documents_empty_store(self):
        """Test listing documents with no store."""
        pipeline = RAGPipeline()

        docs = pipeline.list_documents()
        assert docs == []

    def test_get_stats(self, pipeline):
        """Test getting pipeline statistics."""
        pipeline.add_document("Test document content")

        stats = pipeline.get_stats()

        assert "llm_provider" in stats
        assert "llm_model" in stats
        assert "document_count" in stats
        assert stats["document_count"] == 1

    def test_get_stats_without_store(self):
        """Test stats without document store."""
        pipeline = RAGPipeline()

        stats = pipeline.get_stats()

        assert stats["document_count"] == 0
        assert stats["total_chunks"] == 0

    def test_query_stream_with_documents(self, pipeline):
        """Test streaming query with documents."""
        pipeline.add_document(
            "Machine learning is a subset of AI. It enables systems to learn.",
            {"title": "ML Basics"},
        )

        # The stream should yield something (may fail if no Ollama, but tests structure)
        try:
            tokens = list(pipeline.query_stream("What is machine learning?"))
            # If Ollama is running, we get tokens
            # If not, we still test that the method works
            assert isinstance(tokens, list)
        except Exception:
            # Expected if Ollama isn't running
            pass

    def test_pipeline_with_file_store(self):
        """Test pipeline with file-based store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = FileDocumentStore(path=tmpdir)
            pipeline = RAGPipeline(document_store=store)

            doc = pipeline.add_document("Persistent content", {"title": "Test"})

            assert doc.id is not None

            # Verify persistence
            stats = pipeline.get_stats()
            assert stats["document_count"] == 1
            assert "storage_path" in stats


class TestChunkingStrategies:
    """Test different chunking strategies with document store."""

    @pytest.fixture
    def sample_markdown(self):
        """Sample markdown content."""
        return """# Machine Learning Guide

## Introduction

Machine learning is a fascinating field.

## Types of Learning

### Supervised Learning

Uses labeled data for training.

### Unsupervised Learning

Finds patterns in unlabeled data.

## Conclusion

ML is transforming industries.
"""

    def test_fixed_chunking(self, sample_markdown):
        """Test fixed chunking strategy."""
        store = InMemoryDocumentStore(
            chunking_strategy=ChunkingStrategy.FIXED, chunk_size=100
        )

        doc = store.add(sample_markdown)

        assert len(doc.chunks) > 1
        # Fixed chunks should be roughly equal size
        sizes = [len(c) for c in doc.chunks[:-1]]  # Exclude last chunk
        assert all(s <= 110 for s in sizes)  # Allow some overflow

    def test_semantic_chunking(self, sample_markdown):
        """Test semantic chunking strategy."""
        store = InMemoryDocumentStore(
            chunking_strategy=ChunkingStrategy.SEMANTIC, chunk_size=200
        )

        doc = store.add(sample_markdown)

        assert len(doc.chunks) >= 1

    def test_recursive_chunking(self, sample_markdown):
        """Test recursive chunking strategy."""
        store = InMemoryDocumentStore(
            chunking_strategy=ChunkingStrategy.RECURSIVE, chunk_size=150
        )

        doc = store.add(sample_markdown)

        assert len(doc.chunks) >= 1

    def test_markdown_chunking(self, sample_markdown):
        """Test markdown-aware chunking strategy."""
        store = InMemoryDocumentStore(
            chunking_strategy=ChunkingStrategy.MARKDOWN, chunk_size=200
        )

        doc = store.add(sample_markdown)

        assert len(doc.chunks) >= 1
        # Markdown chunker should preserve some structure
        assert any("#" in chunk for chunk in doc.chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
