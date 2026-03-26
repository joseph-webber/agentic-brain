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

"""RAG Test Fixtures - Mock data for RAG testing.

Provides:
- Mock embeddings (deterministic, no GPU needed)
- Sample documents (various formats and sizes)
- Mock Neo4j responses
- Test data generators
"""

from typing import Any, Dict, List
from unittest.mock import MagicMock, Mock

import pytest

from agentic_brain.rag import (
    Document,
    EmbeddingProvider,
    LoadedDocument,
    RetrievedChunk,
)

# ============ MOCK EMBEDDINGS ============


class MockEmbeddingProvider(EmbeddingProvider):
    """Mock embedding provider for testing.

    Uses deterministic hash-based embeddings that don't require GPU/ML libraries.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        """Generate deterministic embedding from text hash."""
        # Use hash for deterministic results
        base_hash = hash(text)

        # Generate embedding vector
        embedding = []
        for i in range(self.dimension):
            # Create deterministic float from hash
            val = ((base_hash + i * 7919) % 10000) / 10000.0
            embedding.append(val)

        return embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts."""
        return [self.embed_text(t) for t in texts]


class FastMockEmbeddings(EmbeddingProvider):
    """Even faster mock for CI - constant embeddings."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        """Return constant embedding (super fast)."""
        # Use first char of text to add tiny variation
        base = ord(text[0]) / 1000.0 if text else 0.0
        return [base + (i / 10000.0) for i in range(self.dimension)]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_text(t) for t in texts]


# ============ SAMPLE DOCUMENTS ============


SAMPLE_TEXTS = {
    "short": "This is a short document.",
    "medium": "This is a medium-length document. " * 20,
    "long": "This is a long document with multiple paragraphs.\n\n" * 50,
    "code": """
def hello_world():
    print("Hello, World!")
    return True

class Example:
    def __init__(self):
        self.data = []
""",
    "markdown": """
# Main Title

This is an introduction paragraph.

## Section 1

Content for section 1 with **bold** and *italic* text.

## Section 2

More content here.

- List item 1
- List item 2
- List item 3
""",
    "technical": """
The RAG (Retrieval-Augmented Generation) system combines vector search
with large language models. It uses embeddings to find relevant context,
then passes that context to an LLM for generation. This improves factual
accuracy and reduces hallucinations.
""",
}


@pytest.fixture
def sample_documents():
    """Provide sample documents for testing."""
    docs = []
    for doc_type, content in SAMPLE_TEXTS.items():
        doc = Document(
            id=f"doc_{doc_type}",
            content=content,
            metadata={
                "type": doc_type,
                "source": f"{doc_type}.txt",
            },
        )
        docs.append(doc)
    return docs


@pytest.fixture
def sample_loaded_documents():
    """Provide sample LoadedDocument instances."""
    docs = []
    for doc_type, content in SAMPLE_TEXTS.items():
        doc = LoadedDocument(
            content=content,
            metadata={
                "type": doc_type,
                "source": f"{doc_type}.txt",
            },
        )
        docs.append(doc)
    return docs


@pytest.fixture
def mock_embeddings():
    """Provide mock embedding provider."""
    return MockEmbeddingProvider()


@pytest.fixture
def fast_mock_embeddings():
    """Provide fast mock embedding provider for CI."""
    return FastMockEmbeddings()


# ============ MOCK NEO4J RESPONSES ============


def create_mock_neo4j_driver():
    """Create a mock Neo4j driver for testing."""
    mock_driver = MagicMock()
    mock_session = MagicMock()

    # Mock query results
    mock_result = MagicMock()
    mock_result.data.return_value = [
        {"node": {"id": "1", "content": "Node 1"}},
        {"node": {"id": "2", "content": "Node 2"}},
    ]

    mock_session.run.return_value = mock_result
    mock_driver.session.return_value.__enter__.return_value = mock_session

    return mock_driver


@pytest.fixture
def mock_neo4j_driver():
    """Provide mock Neo4j driver."""
    return create_mock_neo4j_driver()


def create_mock_neo4j_graph_response():
    """Create mock graph traversal response."""
    return {
        "nodes": [
            {
                "id": "1",
                "labels": ["Document"],
                "properties": {"content": "Test document 1"},
            },
            {
                "id": "2",
                "labels": ["Document"],
                "properties": {"content": "Test document 2"},
            },
        ],
        "relationships": [
            {
                "id": "r1",
                "type": "RELATES_TO",
                "start": "1",
                "end": "2",
            },
        ],
    }


@pytest.fixture
def mock_graph_response():
    """Provide mock graph response."""
    return create_mock_neo4j_graph_response()


# ============ RETRIEVED CHUNKS ============


def create_mock_retrieved_chunks(count: int = 5) -> List[RetrievedChunk]:
    """Create mock retrieved chunks for testing."""
    chunks = []
    for i in range(count):
        chunk = RetrievedChunk(
            content=f"This is chunk {i} with relevant content.",
            score=1.0 - (i * 0.1),  # Descending scores
            metadata={
                "source": f"doc_{i}.txt",
                "chunk_id": i,
            },
        )
        chunks.append(chunk)
    return chunks


@pytest.fixture
def mock_retrieved_chunks():
    """Provide mock retrieved chunks."""
    return create_mock_retrieved_chunks()


# ============ RAG PIPELINE MOCKS ============


@pytest.fixture
def mock_rag_pipeline():
    """Provide fully mocked RAG pipeline."""
    from unittest.mock import patch

    from agentic_brain.rag import RAGPipeline

    with patch("agentic_brain.rag.pipeline.get_embeddings") as mock_emb:
        mock_emb.return_value = FastMockEmbeddings()
        pipeline = RAGPipeline()

        # Mock retrieval
        pipeline.retriever.retrieve = MagicMock(
            return_value=create_mock_retrieved_chunks()
        )

        return pipeline


# ============ TEST DATA GENERATORS ============


def generate_test_corpus(size: int = 100) -> List[str]:
    """Generate a test corpus of documents."""
    topics = [
        "Python programming",
        "Machine learning",
        "Data science",
        "Web development",
        "Cloud computing",
    ]

    corpus = []
    for i in range(size):
        topic = topics[i % len(topics)]
        doc = f"Document {i} about {topic}. This contains relevant information."
        corpus.append(doc)

    return corpus


def generate_query_answer_pairs() -> List[Dict[str, str]]:
    """Generate test query-answer pairs for evaluation."""
    return [
        {
            "query": "What is Python?",
            "answer": "Python is a high-level programming language.",
            "context": "Python is a high-level, interpreted programming language.",
        },
        {
            "query": "What is machine learning?",
            "answer": "Machine learning is a subset of AI.",
            "context": "Machine learning is a subset of artificial intelligence.",
        },
        {
            "query": "What is a database?",
            "answer": "A database stores structured data.",
            "context": "A database is a system for storing structured data.",
        },
    ]


@pytest.fixture
def test_corpus():
    """Provide test corpus."""
    return generate_test_corpus()


@pytest.fixture
def qa_pairs():
    """Provide query-answer pairs."""
    return generate_query_answer_pairs()


# ============ FILE FIXTURES ============


@pytest.fixture
def temp_test_files(tmp_path):
    """Create temporary test files."""
    files = {}

    # Create text file
    text_file = tmp_path / "test.txt"
    text_file.write_text("This is a test file.\nWith multiple lines.")
    files["text"] = text_file

    # Create markdown file
    md_file = tmp_path / "test.md"
    md_file.write_text("# Header\n\nContent here.")
    files["markdown"] = md_file

    # Create JSON file
    json_file = tmp_path / "test.json"
    json_file.write_text('{"key": "value"}')
    files["json"] = json_file

    # Create code file
    py_file = tmp_path / "test.py"
    py_file.write_text("def test():\n    pass")
    files["python"] = py_file

    return files


# ============ HELPER FUNCTIONS ============


def assert_valid_embedding(embedding: List[float], expected_dim: int = 384):
    """Assert embedding is valid."""
    assert isinstance(embedding, list)
    assert len(embedding) == expected_dim
    assert all(isinstance(x, float) for x in embedding)
    assert all(-1.0 <= x <= 1.0 for x in embedding)


def assert_valid_chunk(chunk):
    """Assert chunk is valid."""
    assert hasattr(chunk, "content")
    assert hasattr(chunk, "metadata")
    assert isinstance(chunk.content, str)
    assert len(chunk.content) > 0


def assert_valid_document(doc):
    """Assert document is valid."""
    assert hasattr(doc, "content")
    assert isinstance(doc.content, str)
    assert hasattr(doc, "metadata")
    assert isinstance(doc.metadata, dict)


# Make fixtures available at module level
__all__ = [
    "MockEmbeddingProvider",
    "FastMockEmbeddings",
    "sample_documents",
    "sample_loaded_documents",
    "mock_embeddings",
    "fast_mock_embeddings",
    "mock_neo4j_driver",
    "mock_graph_response",
    "mock_retrieved_chunks",
    "mock_rag_pipeline",
    "test_corpus",
    "qa_pairs",
    "temp_test_files",
    "assert_valid_embedding",
    "assert_valid_chunk",
    "assert_valid_document",
    "create_mock_neo4j_driver",
    "create_mock_retrieved_chunks",
    "generate_test_corpus",
    "generate_query_answer_pairs",
]
