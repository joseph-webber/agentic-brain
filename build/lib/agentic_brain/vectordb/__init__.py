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
Vector Database Adapters for Agentic Brain
==========================================

Provides unified interface for various vector databases:
- Pinecone (cloud-native vector DB)
- Weaviate (open-source vector search)
- Qdrant (high-performance vector similarity)
- In-Memory (testing and small datasets)

All external dependencies are OPTIONAL. The adapters gracefully
handle missing packages and fall back appropriately.

Example:
    >>> from agentic_brain.vectordb import MemoryVectorAdapter
    >>> adapter = MemoryVectorAdapter(dimension=384)
    >>> adapter.connect()
    >>> adapter.upsert("collection", [{"id": "1", "vector": [...], "metadata": {...}}])
    >>> results = adapter.search("collection", query_vector=[...], top_k=5)

Copyright (C) 2026 Joseph Webber
License: GPL-3.0-or-later
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class VectorDBType(Enum):
    """Supported vector database types."""

    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"
    MEMORY = "memory"


@dataclass
class VectorSearchResult:
    """
    Result from a vector similarity search.

    Attributes:
        id: Unique identifier of the vector
        score: Similarity score (higher = more similar for cosine)
        vector: The actual vector (optional, may not be returned)
        metadata: Associated metadata dictionary
        distance: Distance metric value (for distance-based searches)
    """

    id: str
    score: float
    vector: Optional[list[float]] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    distance: Optional[float] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class VectorRecord:
    """
    A vector record for upsert operations.

    Attributes:
        id: Unique identifier
        vector: The embedding vector
        metadata: Associated metadata
    """

    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format."""
        return {"id": self.id, "vector": self.vector, "metadata": self.metadata or {}}


class VectorDBAdapter(ABC):
    """
    Abstract base class for vector database adapters.

    All vector database implementations must inherit from this class
    and implement the required abstract methods.

    Attributes:
        dimension: The dimensionality of vectors (e.g., 384, 768, 1536)
        metric: Distance metric ("cosine", "euclidean", "dotproduct")
        connected: Whether the adapter is currently connected
    """

    def __init__(self, dimension: int = 384, metric: str = "cosine", **kwargs):
        """
        Initialize the vector database adapter.

        Args:
            dimension: Vector dimensionality
            metric: Distance metric to use
            **kwargs: Additional adapter-specific configuration
        """
        self.dimension = dimension
        self.metric = metric
        self.connected = False
        self._config = kwargs

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the vector database.

        Returns:
            True if connection successful, False otherwise

        Raises:
            ConnectionError: If connection fails critically
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection to the vector database."""
        pass

    @abstractmethod
    def upsert(
        self,
        collection: str,
        vectors: list[Union[dict[str, Any], VectorRecord]],
        namespace: Optional[str] = None,
    ) -> int:
        """
        Insert or update vectors in a collection.

        Args:
            collection: Name of the collection/index
            vectors: List of vector records (dict or VectorRecord)
            namespace: Optional namespace for partitioning

        Returns:
            Number of vectors upserted

        Raises:
            ValueError: If vectors are malformed
        """
        pass

    @abstractmethod
    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int = 10,
        namespace: Optional[str] = None,
        filter: Optional[dict[str, Any]] = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> list[VectorSearchResult]:
        """
        Search for similar vectors.

        Args:
            collection: Name of the collection/index
            query_vector: The query embedding vector
            top_k: Number of results to return
            namespace: Optional namespace to search within
            filter: Optional metadata filter
            include_vectors: Whether to return the actual vectors
            include_metadata: Whether to return metadata

        Returns:
            List of VectorSearchResult objects
        """
        pass

    @abstractmethod
    def delete(
        self,
        collection: str,
        ids: Optional[list[str]] = None,
        namespace: Optional[str] = None,
        filter: Optional[dict[str, Any]] = None,
        delete_all: bool = False,
    ) -> int:
        """
        Delete vectors from a collection.

        Args:
            collection: Name of the collection/index
            ids: Specific vector IDs to delete
            namespace: Optional namespace
            filter: Delete by metadata filter
            delete_all: Delete all vectors in collection

        Returns:
            Number of vectors deleted
        """
        pass

    @abstractmethod
    def list_collections(self) -> list[str]:
        """
        List all available collections/indexes.

        Returns:
            List of collection names
        """
        pass

    @abstractmethod
    def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metric: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Create a new collection/index.

        Args:
            name: Collection name
            dimension: Vector dimension (uses default if not specified)
            metric: Distance metric (uses default if not specified)
            **kwargs: Additional collection-specific options

        Returns:
            True if created successfully
        """
        pass

    @abstractmethod
    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection/index.

        Args:
            name: Collection name to delete

        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    def collection_exists(self, name: str) -> bool:
        """
        Check if a collection exists.

        Args:
            name: Collection name

        Returns:
            True if collection exists
        """
        pass

    @abstractmethod
    def count(self, collection: str, namespace: Optional[str] = None) -> int:
        """
        Count vectors in a collection.

        Args:
            collection: Collection name
            namespace: Optional namespace

        Returns:
            Number of vectors
        """
        pass

    def is_connected(self) -> bool:
        """Check if adapter is connected."""
        return self.connected

    def get_info(self) -> dict[str, Any]:
        """
        Get adapter information.

        Returns:
            Dictionary with adapter details
        """
        return {
            "type": self.__class__.__name__,
            "dimension": self.dimension,
            "metric": self.metric,
            "connected": self.connected,
        }

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        """
        Normalize a vector to unit length (for cosine similarity).

        Args:
            vector: Input vector

        Returns:
            Normalized vector
        """
        import math

        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude == 0:
            return vector
        return [x / magnitude for x in vector]

    def _validate_vector(self, vector: list[float]) -> bool:
        """
        Validate vector dimensionality.

        Args:
            vector: Vector to validate

        Returns:
            True if valid

        Raises:
            ValueError: If dimension mismatch
        """
        if len(vector) != self.dimension:
            raise ValueError(
                f"Vector dimension mismatch: expected {self.dimension}, "
                f"got {len(vector)}"
            )
        return True

    def _to_vector_record(
        self, item: Union[dict[str, Any], VectorRecord]
    ) -> VectorRecord:
        """Convert dict to VectorRecord if needed."""
        if isinstance(item, VectorRecord):
            return item
        return VectorRecord(
            id=item["id"], vector=item["vector"], metadata=item.get("metadata", {})
        )


# Lazy imports for adapters (they handle their own optional dependencies)
def get_adapter(db_type: Union[str, VectorDBType], **kwargs) -> VectorDBAdapter:
    """
    Factory function to get the appropriate adapter.

    Args:
        db_type: Type of vector database
        **kwargs: Adapter-specific configuration

    Returns:
        Configured VectorDBAdapter instance

    Raises:
        ValueError: If unknown database type
        ImportError: If required package not installed
    """
    if isinstance(db_type, str):
        db_type = VectorDBType(db_type.lower())

    if db_type == VectorDBType.PINECONE:
        from agentic_brain.vectordb.pinecone_adapter import PineconeAdapter

        return PineconeAdapter(**kwargs)
    elif db_type == VectorDBType.WEAVIATE:
        from agentic_brain.vectordb.weaviate_adapter import WeaviateAdapter

        return WeaviateAdapter(**kwargs)
    elif db_type == VectorDBType.QDRANT:
        from agentic_brain.vectordb.qdrant_adapter import QdrantAdapter

        return QdrantAdapter(**kwargs)
    elif db_type == VectorDBType.MEMORY:
        from agentic_brain.vectordb.memory_adapter import MemoryVectorAdapter

        return MemoryVectorAdapter(**kwargs)
    else:
        raise ValueError(f"Unknown vector database type: {db_type}")


# Import adapters for convenience (they handle missing deps gracefully)
try:
    from agentic_brain.vectordb.memory_adapter import MemoryVectorAdapter
except ImportError:
    MemoryVectorAdapter = None  # type: ignore

try:
    from agentic_brain.vectordb.pinecone_adapter import PineconeAdapter
except ImportError:
    PineconeAdapter = None  # type: ignore

try:
    from agentic_brain.vectordb.weaviate_adapter import WeaviateAdapter
except ImportError:
    WeaviateAdapter = None  # type: ignore

try:
    from agentic_brain.vectordb.qdrant_adapter import QdrantAdapter
except ImportError:
    QdrantAdapter = None  # type: ignore


__all__ = [
    # Base classes
    "VectorDBAdapter",
    "VectorSearchResult",
    "VectorRecord",
    "VectorDBType",
    # Factory
    "get_adapter",
    # Adapters (may be None if deps missing)
    "MemoryVectorAdapter",
    "PineconeAdapter",
    "WeaviateAdapter",
    "QdrantAdapter",
]
