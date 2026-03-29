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
Tests for Vector Database Adapters
====================================

Comprehensive tests for all vector database adapters:
- MemoryVectorAdapter (full testing, no mocks needed)
- PineconeAdapter (mocked)
- WeaviateAdapter (mocked)
- QdrantAdapter (mocked)

Copyright (C) 2026 Joseph Webber
License: Apache-2.0
"""

from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Base Classes and Utility Tests
# ============================================================================


class TestVectorDBBaseClasses:
    """Tests for base classes and utilities."""

    def test_vector_search_result_creation(self):
        """Test VectorSearchResult dataclass."""
        from agentic_brain.vectordb import VectorSearchResult

        result = VectorSearchResult(
            id="test-1", score=0.95, vector=[0.1, 0.2, 0.3], metadata={"text": "hello"}
        )

        assert result.id == "test-1"
        assert result.score == 0.95
        assert result.vector == [0.1, 0.2, 0.3]
        assert result.metadata == {"text": "hello"}

    def test_vector_search_result_defaults(self):
        """Test VectorSearchResult default values."""
        from agentic_brain.vectordb import VectorSearchResult

        result = VectorSearchResult(id="test", score=0.5)

        assert result.vector is None
        assert result.metadata == {}
        assert result.distance is None

    def test_vector_record_creation(self):
        """Test VectorRecord dataclass."""
        from agentic_brain.vectordb import VectorRecord

        record = VectorRecord(id="rec-1", vector=[0.1, 0.2], metadata={"key": "value"})

        assert record.id == "rec-1"
        assert record.vector == [0.1, 0.2]
        assert record.metadata == {"key": "value"}

    def test_vector_record_to_dict(self):
        """Test VectorRecord to_dict method."""
        from agentic_brain.vectordb import VectorRecord

        record = VectorRecord(id="rec-1", vector=[0.1, 0.2], metadata={"key": "value"})

        d = record.to_dict()
        assert d == {"id": "rec-1", "vector": [0.1, 0.2], "metadata": {"key": "value"}}

    def test_vector_db_type_enum(self):
        """Test VectorDBType enum values."""
        from agentic_brain.vectordb import VectorDBType

        assert VectorDBType.PINECONE.value == "pinecone"
        assert VectorDBType.WEAVIATE.value == "weaviate"
        assert VectorDBType.QDRANT.value == "qdrant"
        assert VectorDBType.MEMORY.value == "memory"

    def test_get_adapter_memory(self):
        """Test get_adapter factory for memory adapter."""
        from agentic_brain.vectordb import VectorDBType, get_adapter

        adapter = get_adapter(VectorDBType.MEMORY, dimension=128)
        assert adapter is not None
        assert adapter.dimension == 128

    def test_get_adapter_string_type(self):
        """Test get_adapter with string type."""
        from agentic_brain.vectordb import get_adapter

        adapter = get_adapter("memory", dimension=256)
        assert adapter is not None
        assert adapter.dimension == 256

    def test_get_adapter_invalid_type(self):
        """Test get_adapter with invalid type."""
        from agentic_brain.vectordb import get_adapter

        with pytest.raises(ValueError):
            get_adapter("invalid_db")


# ============================================================================
# MemoryVectorAdapter Tests (Full Implementation Testing)
# ============================================================================


class TestMemoryVectorAdapter:
    """Comprehensive tests for the in-memory adapter."""

    @pytest.fixture
    def adapter(self):
        """Create a fresh adapter for each test."""
        from agentic_brain.vectordb import MemoryVectorAdapter

        adapter = MemoryVectorAdapter(dimension=4, metric="cosine")
        adapter.connect()
        return adapter

    @pytest.fixture
    def sample_vectors(self):
        """Sample vectors for testing."""
        return [
            {"id": "v1", "vector": [1.0, 0.0, 0.0, 0.0], "metadata": {"text": "first"}},
            {
                "id": "v2",
                "vector": [0.0, 1.0, 0.0, 0.0],
                "metadata": {"text": "second"},
            },
            {"id": "v3", "vector": [0.0, 0.0, 1.0, 0.0], "metadata": {"text": "third"}},
            {
                "id": "v4",
                "vector": [0.5, 0.5, 0.0, 0.0],
                "metadata": {"text": "fourth"},
            },
        ]

    def test_connect(self, adapter):
        """Test connection."""
        assert adapter.connected is True
        assert adapter.is_connected() is True

    def test_disconnect(self, adapter):
        """Test disconnection."""
        adapter.disconnect()
        assert adapter.connected is False
        assert adapter.is_connected() is False

    def test_create_collection(self, adapter):
        """Test collection creation."""
        result = adapter.create_collection("test-collection")
        assert result is True
        assert adapter.collection_exists("test-collection")

    def test_create_duplicate_collection(self, adapter):
        """Test creating duplicate collection returns False."""
        adapter.create_collection("test")
        result = adapter.create_collection("test")
        assert result is False

    def test_delete_collection(self, adapter):
        """Test collection deletion."""
        adapter.create_collection("to-delete")
        assert adapter.collection_exists("to-delete")

        result = adapter.delete_collection("to-delete")
        assert result is True
        assert not adapter.collection_exists("to-delete")

    def test_delete_nonexistent_collection(self, adapter):
        """Test deleting non-existent collection."""
        result = adapter.delete_collection("nonexistent")
        assert result is False

    def test_list_collections(self, adapter):
        """Test listing collections."""
        adapter.create_collection("col1")
        adapter.create_collection("col2")

        collections = adapter.list_collections()
        assert "col1" in collections
        assert "col2" in collections

    def test_upsert_vectors(self, adapter, sample_vectors):
        """Test upserting vectors."""
        count = adapter.upsert("embeddings", sample_vectors)
        assert count == 4
        assert adapter.count("embeddings") == 4

    def test_upsert_auto_creates_collection(self, adapter, sample_vectors):
        """Test that upsert auto-creates collection."""
        count = adapter.upsert("new-collection", sample_vectors[:1])
        assert count == 1
        assert adapter.collection_exists("new-collection")

    def test_upsert_with_namespace(self, adapter, sample_vectors):
        """Test upserting with namespace."""
        adapter.upsert("coll", sample_vectors[:2], namespace="ns1")
        adapter.upsert("coll", sample_vectors[2:], namespace="ns2")

        assert adapter.count("coll", namespace="ns1") == 2
        assert adapter.count("coll", namespace="ns2") == 2
        assert adapter.count("coll") == 4

    def test_search_cosine_similarity(self, adapter, sample_vectors):
        """Test cosine similarity search."""
        adapter.upsert("test", sample_vectors)

        # Search with exact match to v1
        results = adapter.search("test", query_vector=[1.0, 0.0, 0.0, 0.0], top_k=2)

        assert len(results) == 2
        assert results[0].id == "v1"
        assert results[0].score == pytest.approx(1.0, abs=0.001)

    def test_search_returns_sorted_results(self, adapter, sample_vectors):
        """Test that search results are sorted by score."""
        adapter.upsert("test", sample_vectors)

        # v4 is [0.5, 0.5, 0, 0] - closer to [0.6, 0.4, 0, 0]
        results = adapter.search("test", query_vector=[0.6, 0.4, 0.0, 0.0], top_k=4)

        # Scores should be in descending order
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_search_with_metadata_filter(self, adapter, sample_vectors):
        """Test search with metadata filter."""
        adapter.upsert("test", sample_vectors)

        results = adapter.search(
            "test",
            query_vector=[1.0, 0.0, 0.0, 0.0],
            filter={"text": "first"},
            top_k=10,
        )

        assert len(results) == 1
        assert results[0].id == "v1"

    def test_search_with_operator_filters(self, adapter):
        """Test search with various filter operators."""
        vectors = [
            {"id": "1", "vector": [1, 0, 0, 0], "metadata": {"score": 10}},
            {"id": "2", "vector": [1, 0, 0, 0], "metadata": {"score": 20}},
            {"id": "3", "vector": [1, 0, 0, 0], "metadata": {"score": 30}},
        ]
        adapter.upsert("test", vectors)

        # Test $gt
        results = adapter.search(
            "test", [1, 0, 0, 0], filter={"score": {"$gt": 15}}, top_k=10
        )
        assert len(results) == 2

        # Test $lte
        results = adapter.search(
            "test", [1, 0, 0, 0], filter={"score": {"$lte": 20}}, top_k=10
        )
        assert len(results) == 2

        # Test $in
        results = adapter.search(
            "test", [1, 0, 0, 0], filter={"score": {"$in": [10, 30]}}, top_k=10
        )
        assert len(results) == 2

    def test_search_include_vectors(self, adapter, sample_vectors):
        """Test search with include_vectors=True."""
        adapter.upsert("test", sample_vectors)

        results = adapter.search(
            "test", query_vector=[1.0, 0.0, 0.0, 0.0], include_vectors=True, top_k=1
        )

        assert results[0].vector == [1.0, 0.0, 0.0, 0.0]

    def test_search_exclude_metadata(self, adapter, sample_vectors):
        """Test search with include_metadata=False."""
        adapter.upsert("test", sample_vectors)

        results = adapter.search(
            "test", query_vector=[1.0, 0.0, 0.0, 0.0], include_metadata=False, top_k=1
        )

        assert results[0].metadata == {}

    def test_search_nonexistent_collection(self, adapter):
        """Test searching non-existent collection returns empty."""
        results = adapter.search("nonexistent", [1, 0, 0, 0])
        assert results == []

    def test_delete_by_ids(self, adapter, sample_vectors):
        """Test deleting specific IDs."""
        adapter.upsert("test", sample_vectors)

        count = adapter.delete("test", ids=["v1", "v2"])
        assert count == 2
        assert adapter.count("test") == 2

    def test_delete_all(self, adapter, sample_vectors):
        """Test delete_all flag."""
        adapter.upsert("test", sample_vectors)

        count = adapter.delete("test", delete_all=True)
        assert count == 4
        assert adapter.count("test") == 0

    def test_delete_by_filter(self, adapter, sample_vectors):
        """Test deleting by filter."""
        adapter.upsert("test", sample_vectors)

        count = adapter.delete("test", filter={"text": "first"})
        assert count == 1
        assert adapter.count("test") == 3

    def test_count_empty_collection(self, adapter):
        """Test count on empty/nonexistent collection."""
        assert adapter.count("nonexistent") == 0

    def test_get_vector(self, adapter, sample_vectors):
        """Test getting specific vector by ID."""
        adapter.upsert("test", sample_vectors)

        record = adapter.get_vector("test", "v1")
        assert record is not None
        assert record.id == "v1"
        assert record.vector == [1.0, 0.0, 0.0, 0.0]

    def test_get_vector_nonexistent(self, adapter):
        """Test getting non-existent vector."""
        adapter.create_collection("test")
        record = adapter.get_vector("test", "nonexistent")
        assert record is None

    def test_get_info(self, adapter, sample_vectors):
        """Test get_info method."""
        adapter.upsert("test", sample_vectors)

        info = adapter.get_info()
        assert info["type"] == "MemoryVectorAdapter"
        assert info["dimension"] == 4
        assert info["metric"] == "cosine"
        assert info["connected"] is True
        assert "test" in info["collections"]
        assert info["total_vectors"] == 4

    def test_euclidean_distance(self):
        """Test Euclidean distance metric."""
        from agentic_brain.vectordb import MemoryVectorAdapter

        adapter = MemoryVectorAdapter(dimension=2, metric="euclidean")
        adapter.connect()

        vectors = [
            {"id": "1", "vector": [0, 0], "metadata": {}},
            {"id": "2", "vector": [3, 4], "metadata": {}},  # distance = 5
            {"id": "3", "vector": [1, 1], "metadata": {}},  # distance = sqrt(2)
        ]
        adapter.upsert("test", vectors)

        results = adapter.search("test", [0, 0], top_k=3)

        # Closest should be [0,0] itself
        assert results[0].id == "1"
        # Next should be [1,1]
        assert results[1].id == "3"

    def test_dotproduct_metric(self):
        """Test dot product metric."""
        from agentic_brain.vectordb import MemoryVectorAdapter

        adapter = MemoryVectorAdapter(dimension=2, metric="dotproduct")
        adapter.connect()

        vectors = [
            {"id": "1", "vector": [1, 0], "metadata": {}},
            {"id": "2", "vector": [2, 0], "metadata": {}},
        ]
        adapter.upsert("test", vectors)

        results = adapter.search("test", [1, 0], top_k=2)

        # Higher dot product = better match
        assert results[0].id == "2"  # dot product = 2
        assert results[1].id == "1"  # dot product = 1

    def test_vector_dimension_validation(self, adapter):
        """Test that dimension mismatch raises error."""
        with pytest.raises(ValueError, match="dimension mismatch"):
            adapter.upsert(
                "test",
                [
                    {
                        "id": "bad",
                        "vector": [1, 2, 3],
                        "metadata": {},
                    }  # 3D instead of 4D
                ],
            )

    def test_upsert_with_vector_record_objects(self, adapter):
        """Test upserting with VectorRecord objects."""
        from agentic_brain.vectordb import VectorRecord

        records = [
            VectorRecord(id="r1", vector=[1, 0, 0, 0], metadata={"a": 1}),
            VectorRecord(id="r2", vector=[0, 1, 0, 0], metadata={"b": 2}),
        ]

        count = adapter.upsert("test", records)
        assert count == 2


# ============================================================================
# PineconeAdapter Tests (Mocked)
# ============================================================================


class TestPineconeAdapter:
    """Tests for Pinecone adapter with mocking."""

    @pytest.fixture
    def mock_pinecone(self):
        """Mock Pinecone client."""
        with patch.dict("sys.modules", {"pinecone": MagicMock()}):
            with patch("agentic_brain.vectordb.pinecone_adapter.HAS_PINECONE", True):
                with patch(
                    "agentic_brain.vectordb.pinecone_adapter.Pinecone"
                ) as mock_pc:
                    with patch(
                        "agentic_brain.vectordb.pinecone_adapter.ServerlessSpec"
                    ):
                        yield mock_pc

    def test_pinecone_not_installed_error(self):
        """Test error when Pinecone not installed."""
        with patch("agentic_brain.vectordb.pinecone_adapter.HAS_PINECONE", False):
            from agentic_brain.vectordb.pinecone_adapter import (
                PineconeAdapter,
                PineconeNotInstalledError,
            )

            with pytest.raises(PineconeNotInstalledError):
                PineconeAdapter(api_key="test")

    def test_pinecone_connect_success(self, mock_pinecone):
        """Test successful Pinecone connection."""
        # Reload module to pick up mocks
        import importlib

        from agentic_brain.vectordb import pinecone_adapter

        importlib.reload(pinecone_adapter)

        mock_client = MagicMock()
        mock_client.list_indexes.return_value = []
        mock_pinecone.return_value = mock_client

        adapter = pinecone_adapter.PineconeAdapter(api_key="test-key")
        result = adapter.connect()

        assert result is True
        assert adapter.connected is True

    def test_pinecone_connect_no_api_key(self, mock_pinecone):
        """Test connection without API key raises error."""
        import importlib

        from agentic_brain.vectordb import pinecone_adapter

        importlib.reload(pinecone_adapter)

        adapter = pinecone_adapter.PineconeAdapter()

        with pytest.raises(ConnectionError, match="API key required"):
            adapter.connect()


# ============================================================================
# WeaviateAdapter Tests (Mocked)
# ============================================================================


class TestWeaviateAdapter:
    """Tests for Weaviate adapter with mocking."""

    def test_weaviate_not_installed_error(self):
        """Test error when Weaviate not installed."""
        with patch("agentic_brain.vectordb.weaviate_adapter.HAS_WEAVIATE", False):
            from agentic_brain.vectordb.weaviate_adapter import (
                WeaviateAdapter,
                WeaviateNotInstalledError,
            )

            with pytest.raises(WeaviateNotInstalledError):
                WeaviateAdapter(url="http://localhost:8080")

    @pytest.fixture
    def mock_weaviate(self):
        """Mock Weaviate client."""
        mock_weaviate_module = MagicMock()
        mock_weaviate_module.WeaviateClient = MagicMock()
        mock_weaviate_module.connect_to_local = MagicMock()
        mock_weaviate_module.connect_to_wcs = MagicMock()
        mock_weaviate_module.auth = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "weaviate": mock_weaviate_module,
                    "weaviate.classes.config": MagicMock(),
                    "weaviate.classes.query": MagicMock(),
                },
            ),
            patch("agentic_brain.vectordb.weaviate_adapter.HAS_WEAVIATE", True),
            patch(
                "agentic_brain.vectordb.weaviate_adapter.weaviate",
                mock_weaviate_module,
            ),
        ):
            yield mock_weaviate_module

    def test_weaviate_connect_local(self, mock_weaviate):
        """Test connecting to local Weaviate."""
        import importlib

        from agentic_brain.vectordb import weaviate_adapter

        importlib.reload(weaviate_adapter)

        mock_client = MagicMock()
        mock_client.is_ready.return_value = True
        mock_weaviate.connect_to_local.return_value = mock_client

        adapter = weaviate_adapter.WeaviateAdapter(url="http://localhost:8080")
        result = adapter.connect()

        assert result is True
        assert adapter.connected is True


# ============================================================================
# QdrantAdapter Tests (Mocked)
# ============================================================================


class TestQdrantAdapter:
    """Tests for Qdrant adapter with mocking."""

    def test_qdrant_not_installed_error(self):
        """Test error when Qdrant not installed."""
        with patch("agentic_brain.vectordb.qdrant_adapter.HAS_QDRANT", False):
            from agentic_brain.vectordb.qdrant_adapter import (
                QdrantAdapter,
                QdrantNotInstalledError,
            )

            with pytest.raises(QdrantNotInstalledError):
                QdrantAdapter(url="http://localhost:6333")

    @pytest.fixture
    def mock_qdrant(self):
        """Mock Qdrant client."""
        mock_qdrant_client = MagicMock()
        mock_models = MagicMock()

        with (
            patch.dict(
                "sys.modules",
                {
                    "qdrant_client": mock_qdrant_client,
                    "qdrant_client.http": MagicMock(),
                    "qdrant_client.http.models": mock_models,
                },
            ),
            patch("agentic_brain.vectordb.qdrant_adapter.HAS_QDRANT", True),
            patch("agentic_brain.vectordb.qdrant_adapter.QdrantClient") as mock_qc,
        ):
            yield mock_qc

    def test_qdrant_connect_success(self, mock_qdrant):
        """Test successful Qdrant connection."""
        import importlib

        from agentic_brain.vectordb import qdrant_adapter

        importlib.reload(qdrant_adapter)

        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        mock_qdrant.return_value = mock_client

        adapter = qdrant_adapter.QdrantAdapter(url="http://localhost:6333")
        result = adapter.connect()

        assert result is True
        assert adapter.connected is True

    def test_qdrant_in_memory_mode(self, mock_qdrant):
        """Test Qdrant in-memory mode uses correct location."""
        from agentic_brain.vectordb import qdrant_adapter

        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(collections=[])
        mock_qdrant.return_value = mock_client

        adapter = qdrant_adapter.QdrantAdapter(url=":memory:")

        # Verify the URL was set correctly for in-memory mode
        assert adapter.url == ":memory:"

        # Mock the QdrantClient at module level for connect
        with patch.object(qdrant_adapter, "QdrantClient", mock_qdrant):
            result = adapter.connect()
            assert result is True
            mock_qdrant.assert_called_with(location=":memory:")


# ============================================================================
# Graceful Degradation Tests
# ============================================================================


class TestGracefulDegradation:
    """Tests for graceful handling of missing dependencies."""

    def test_memory_adapter_always_works(self):
        """Memory adapter should always be available."""
        from agentic_brain.vectordb import MemoryVectorAdapter

        assert MemoryVectorAdapter is not None

        adapter = MemoryVectorAdapter(dimension=128)
        assert adapter.connect() is True

    def test_vectordb_module_imports(self):
        """Module should import even if adapters are unavailable."""
        # This should not raise even if optional deps missing
        from agentic_brain.vectordb import (
            VectorDBAdapter,
            VectorDBType,
            VectorRecord,
            VectorSearchResult,
            get_adapter,
        )

        assert VectorDBAdapter is not None
        assert VectorSearchResult is not None
        assert VectorRecord is not None
        assert VectorDBType is not None
        assert get_adapter is not None


# ============================================================================
# Integration-Style Tests (Using Memory Adapter)
# ============================================================================


class TestVectorDBWorkflow:
    """End-to-end workflow tests using memory adapter."""

    def test_full_rag_workflow(self):
        """Test a complete RAG-style workflow."""
        from agentic_brain.vectordb import MemoryVectorAdapter

        adapter = MemoryVectorAdapter(dimension=4)
        adapter.connect()

        # Create collection
        adapter.create_collection("documents")

        # Add document embeddings
        docs = [
            {
                "id": "doc1",
                "vector": [0.9, 0.1, 0.0, 0.0],
                "metadata": {"title": "Python Guide", "category": "programming"},
            },
            {
                "id": "doc2",
                "vector": [0.1, 0.9, 0.0, 0.0],
                "metadata": {"title": "Cooking Recipes", "category": "food"},
            },
            {
                "id": "doc3",
                "vector": [0.8, 0.2, 0.0, 0.0],
                "metadata": {"title": "Java Tutorial", "category": "programming"},
            },
        ]
        adapter.upsert("documents", docs)

        # Search for programming content
        results = adapter.search(
            "documents",
            query_vector=[0.85, 0.15, 0.0, 0.0],
            top_k=2,
            filter={"category": "programming"},
        )

        assert len(results) == 2
        assert all(r.metadata["category"] == "programming" for r in results)

        # Clean up
        adapter.disconnect()

    def test_namespace_isolation(self):
        """Test that namespaces properly isolate data."""
        from agentic_brain.vectordb import MemoryVectorAdapter

        adapter = MemoryVectorAdapter(dimension=2)
        adapter.connect()

        # Add vectors to different namespaces
        adapter.upsert(
            "coll",
            [{"id": "a", "vector": [1, 0], "metadata": {"ns": "user1"}}],
            namespace="user1",
        )
        adapter.upsert(
            "coll",
            [{"id": "b", "vector": [0, 1], "metadata": {"ns": "user2"}}],
            namespace="user2",
        )

        # Search in specific namespace
        results = adapter.search("coll", [1, 0], namespace="user1", top_k=10)

        assert len(results) == 1
        assert results[0].id == "a"

        # Delete from namespace
        adapter.delete("coll", ids=["a"], namespace="user1")
        assert adapter.count("coll", namespace="user1") == 0
        assert adapter.count("coll", namespace="user2") == 1
