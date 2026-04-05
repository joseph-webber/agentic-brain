# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""
Shared fixtures for RAG test suite.

Provides mock documents, embeddings, indices, and stores used
across test_chunking, test_embeddings, test_retrievers and test_loaders.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.chunking.base import Chunk
from agentic_brain.rag.embeddings import EmbeddingProvider
from agentic_brain.rag.loaders.base import LoadedDocument
from agentic_brain.rag.retriever import RetrievedChunk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIM = 8  # Small dimension for test speed

SAMPLE_TEXT_SHORT = "The quick brown fox jumps over the lazy dog."

SAMPLE_TEXT_PARAGRAPHS = (
    "Introduction to machine learning.\n\n"
    "Machine learning is a subset of artificial intelligence. "
    "It enables computers to learn from data without being explicitly programmed.\n\n"
    "Types of machine learning include supervised, unsupervised, and reinforcement learning.\n\n"
    "Applications span computer vision, natural language processing, and robotics."
)

SAMPLE_MARKDOWN = (
    "# Getting Started\n\n"
    "Welcome to the project. Follow the steps below.\n\n"
    "## Installation\n\n"
    "Run `pip install agentic-brain` to install the package.\n\n"
    "## Configuration\n\n"
    "Set `NEO4J_URI` in your environment before starting.\n\n"
    "```python\n"
    "import os\n"
    "os.environ['NEO4J_URI'] = 'bolt://localhost:7687'\n"
    "```\n\n"
    "## Usage\n\n"
    "Import the brain and run your first query."
)


# ---------------------------------------------------------------------------
# Embedding fixtures
# ---------------------------------------------------------------------------


def _unit_vector(seed: int, dim: int = EMBEDDING_DIM) -> list[float]:
    """Return a deterministic unit vector for testing."""
    raw = [float((seed * (i + 1)) % 7 + 1) for i in range(dim)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm for v in raw]


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic mock embedding provider - no external calls."""

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dimensions = dim
        self.embed_call_count = 0

    def embed(self, text: str) -> list[float]:
        self.embed_call_count += 1
        # Deterministic hash-based embedding
        seed = sum(ord(c) for c in text) % 100
        return _unit_vector(seed, self._dimensions)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    @property
    def dimensions(self) -> int:
        return self._dimensions


@pytest.fixture
def mock_embeddings() -> MockEmbeddingProvider:
    """Return a deterministic mock embedding provider."""
    return MockEmbeddingProvider()


@pytest.fixture
def mock_embeddings_large() -> MockEmbeddingProvider:
    """Return a mock embedding provider with larger dimensions."""
    return MockEmbeddingProvider(dim=384)


# ---------------------------------------------------------------------------
# Document fixtures
# ---------------------------------------------------------------------------


def _make_document(
    doc_id: str = "doc-001",
    content: str = SAMPLE_TEXT_SHORT,
    source: str = "test",
    **meta: Any,
) -> LoadedDocument:
    return LoadedDocument(
        id=doc_id,
        content=content,
        source=source,
        metadata={"title": doc_id, **meta},
    )


@pytest.fixture
def sample_document() -> LoadedDocument:
    """Single document for basic loader tests."""
    return _make_document()


@pytest.fixture
def sample_documents() -> list[LoadedDocument]:
    """Collection of documents for batch tests."""
    return [
        _make_document("doc-001", SAMPLE_TEXT_SHORT, "text", category="animal"),
        _make_document("doc-002", SAMPLE_TEXT_PARAGRAPHS, "markdown", category="ml"),
        _make_document(
            "doc-003",
            "Python is a programming language.",
            "code",
            category="programming",
        ),
        _make_document(
            "doc-004",
            "Neo4j is a graph database.",
            "database",
            category="database",
        ),
        _make_document(
            "doc-005",
            "FastAPI is a modern web framework for building APIs with Python.",
            "web",
            category="web",
        ),
    ]


# ---------------------------------------------------------------------------
# Chunk fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_chunk() -> Chunk:
    return Chunk(
        content=SAMPLE_TEXT_SHORT,
        start_char=0,
        end_char=len(SAMPLE_TEXT_SHORT),
        chunk_index=0,
        metadata={"source": "test"},
    )


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    texts = [
        SAMPLE_TEXT_SHORT,
        "Machine learning is transforming technology.",
        "Graph databases store data as nodes and relationships.",
    ]
    return [
        Chunk(
            content=t,
            start_char=i * 60,
            end_char=i * 60 + len(t),
            chunk_index=i,
            metadata={"source": "test", "index": i},
        )
        for i, t in enumerate(texts)
    ]


# ---------------------------------------------------------------------------
# Retrieved chunk fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def retrieved_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            content="Machine learning enables computers to learn.",
            source="Document",
            score=0.92,
            metadata={"doc_id": "ml-001"},
        ),
        RetrievedChunk(
            content="Deep learning is a subfield of machine learning.",
            source="Memory",
            score=0.75,
            metadata={"doc_id": "dl-002"},
        ),
        RetrievedChunk(
            content="Neural networks are inspired by the brain.",
            source="Knowledge",
            score=0.61,
            metadata={"doc_id": "nn-003"},
        ),
        RetrievedChunk(
            content="Python is widely used for data science.",
            source="Document",
            score=0.48,
            metadata={"doc_id": "py-004"},
        ),
    ]


# ---------------------------------------------------------------------------
# File fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_text_dir(tmp_path: Path) -> Path:
    """Temporary directory with sample text files."""
    (tmp_path / "readme.txt").write_text("This is a readme file.\nIt has two lines.")
    (tmp_path / "notes.txt").write_text("Meeting notes from Monday.\nAction items follow.")
    (tmp_path / "log.log").write_text("2026-01-01 INFO: Service started\n2026-01-01 ERROR: timeout")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.txt").write_text("Nested document content here.")
    return tmp_path


@pytest.fixture
def temp_json_dir(tmp_path: Path) -> Path:
    """Temporary directory with sample JSON files."""
    import json

    (tmp_path / "article.json").write_text(
        json.dumps({"title": "ML Article", "body": "Machine learning overview.", "tags": ["ml", "ai"]})
    )
    (tmp_path / "config.json").write_text(
        json.dumps({"name": "brain", "version": "1.0", "debug": False})
    )
    (tmp_path / "data.jsonl").write_text(
        json.dumps({"id": 1, "text": "First record"}) + "\n"
        + json.dumps({"id": 2, "text": "Second record"})
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Mock document store
# ---------------------------------------------------------------------------


class InMemoryDocumentStore:
    """Simple in-memory document store for retriever tests."""

    def __init__(self, documents: list[LoadedDocument] | None = None) -> None:
        self._docs: list[LoadedDocument] = list(documents or [])

    def add(self, doc: LoadedDocument) -> None:
        self._docs.append(doc)

    def list(self, limit: int = 100) -> list[LoadedDocument]:
        return self._docs[:limit]

    def search(self, query: str, top_k: int = 5) -> list[LoadedDocument]:
        return self._docs[:top_k]


@pytest.fixture
def in_memory_store(sample_documents: list[LoadedDocument]) -> InMemoryDocumentStore:
    return InMemoryDocumentStore(sample_documents)
