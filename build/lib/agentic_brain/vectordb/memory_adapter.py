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
In-Memory Vector Database Adapter
==================================

Simple in-memory implementation for testing and small datasets.
Uses numpy for efficient cosine similarity calculations.

This adapter always works as it only requires numpy (or falls back
to pure Python if numpy is not available).

Copyright (C) 2026 Joseph Webber
License: Apache-2.0
"""

import logging
import math
from collections import defaultdict
from typing import Any, Optional, Union

from agentic_brain.vectordb import (
    VectorDBAdapter,
    VectorRecord,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)

# Try to import numpy for faster operations
try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning("numpy not available, using pure Python for vector operations")


class MemoryVectorAdapter(VectorDBAdapter):
    """
    In-memory vector database adapter.

    Stores vectors in memory using dictionaries. Supports multiple
    collections and namespaces. Good for testing and small datasets.

    Example:
        >>> adapter = MemoryVectorAdapter(dimension=384)
        >>> adapter.connect()
        >>> adapter.create_collection("embeddings")
        >>> adapter.upsert("embeddings", [
        ...     {"id": "1", "vector": [0.1] * 384, "metadata": {"text": "hello"}}
        ... ])
        >>> results = adapter.search("embeddings", [0.1] * 384, top_k=5)
    """

    def __init__(self, dimension: int = 384, metric: str = "cosine", **kwargs):
        """
        Initialize the in-memory adapter.

        Args:
            dimension: Vector dimensionality
            metric: Distance metric ("cosine", "euclidean", "dotproduct")
        """
        super().__init__(dimension=dimension, metric=metric, **kwargs)

        # Storage: {collection: {namespace: {id: VectorRecord}}}
        self._collections: dict[str, dict[str, dict[str, VectorRecord]]] = {}
        self._collection_configs: dict[str, dict[str, Any]] = {}

    def connect(self) -> bool:
        """Connect (always succeeds for in-memory)."""
        self.connected = True
        logger.info("MemoryVectorAdapter connected")
        return True

    def disconnect(self) -> None:
        """Disconnect and clear all data."""
        self.connected = False
        self._collections.clear()
        self._collection_configs.clear()
        logger.info("MemoryVectorAdapter disconnected")

    def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metric: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Create a new collection.

        Args:
            name: Collection name
            dimension: Vector dimension
            metric: Distance metric

        Returns:
            True if created
        """
        if name in self._collections:
            logger.warning(f"Collection '{name}' already exists")
            return False

        self._collections[name] = defaultdict(dict)
        self._collection_configs[name] = {
            "dimension": dimension or self.dimension,
            "metric": metric or self.metric,
            **kwargs,
        }
        logger.info(f"Created collection '{name}'")
        return True

    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.

        Args:
            name: Collection name

        Returns:
            True if deleted
        """
        if name not in self._collections:
            return False

        del self._collections[name]
        del self._collection_configs[name]
        logger.info(f"Deleted collection '{name}'")
        return True

    def collection_exists(self, name: str) -> bool:
        """Check if collection exists."""
        return name in self._collections

    def list_collections(self) -> list[str]:
        """List all collections."""
        return list(self._collections.keys())

    def upsert(
        self,
        collection: str,
        vectors: list[dict[str, Any] | VectorRecord],
        namespace: Optional[str] = None,
    ) -> int:
        """
        Insert or update vectors.

        Args:
            collection: Collection name
            vectors: List of vector records
            namespace: Optional namespace

        Returns:
            Number of vectors upserted
        """
        ns = namespace or "default"

        # Auto-create collection if needed
        if collection not in self._collections:
            self.create_collection(collection)

        count = 0
        for item in vectors:
            record = self._to_vector_record(item)
            self._validate_vector(record.vector)
            self._collections[collection][ns][record.id] = record
            count += 1

        logger.debug(f"Upserted {count} vectors to '{collection}/{ns}'")
        return count

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
            collection: Collection name
            query_vector: Query embedding
            top_k: Number of results
            namespace: Optional namespace
            filter: Metadata filter
            include_vectors: Include vectors in results
            include_metadata: Include metadata in results

        Returns:
            List of search results
        """
        if collection not in self._collections:
            return []

        self._validate_vector(query_vector)

        # Get vectors from namespace(s)
        if namespace:
            namespaces = [namespace]
        else:
            namespaces = list(self._collections[collection].keys())

        candidates = []
        for ns in namespaces:
            if ns in self._collections[collection]:
                candidates.extend(self._collections[collection][ns].values())

        # Apply metadata filter
        if filter:
            candidates = [
                c for c in candidates if self._matches_filter(c.metadata, filter)
            ]

        # Calculate similarities
        scores = []
        for record in candidates:
            score = self._calculate_similarity(query_vector, record.vector)
            scores.append((record, score))

        # Sort by score (descending for similarity)
        scores.sort(key=lambda x: x[1], reverse=True)

        # Build results
        results = []
        for record, score in scores[:top_k]:
            result = VectorSearchResult(
                id=record.id,
                score=score,
                vector=record.vector if include_vectors else None,
                metadata=record.metadata if include_metadata else {},
            )
            results.append(result)

        return results

    def delete(
        self,
        collection: str,
        ids: Optional[list[str]] = None,
        namespace: Optional[str] = None,
        filter: Optional[dict[str, Any]] = None,
        delete_all: bool = False,
    ) -> int:
        """
        Delete vectors.

        Args:
            collection: Collection name
            ids: Specific IDs to delete
            namespace: Optional namespace
            filter: Delete by filter
            delete_all: Delete all

        Returns:
            Number deleted
        """
        if collection not in self._collections:
            return 0

        ns = namespace or "default"
        count = 0

        if delete_all:
            # Delete entire collection
            for ns_data in self._collections[collection].values():
                count += len(ns_data)
            self._collections[collection] = defaultdict(dict)
            return count

        if ids:
            # Delete specific IDs
            if ns in self._collections[collection]:
                for id_ in ids:
                    if id_ in self._collections[collection][ns]:
                        del self._collections[collection][ns][id_]
                        count += 1

        if filter:
            # Delete by filter
            if ns in self._collections[collection]:
                to_delete = []
                for id_, record in self._collections[collection][ns].items():
                    if self._matches_filter(record.metadata, filter):
                        to_delete.append(id_)
                for id_ in to_delete:
                    del self._collections[collection][ns][id_]
                    count += 1

        return count

    def count(self, collection: str, namespace: Optional[str] = None) -> int:
        """
        Count vectors in collection.

        Args:
            collection: Collection name
            namespace: Optional namespace

        Returns:
            Vector count
        """
        if collection not in self._collections:
            return 0

        if namespace:
            return len(self._collections[collection].get(namespace, {}))

        return sum(len(ns_data) for ns_data in self._collections[collection].values())

    def get_vector(
        self, collection: str, id: str, namespace: Optional[str] = None
    ) -> Optional[VectorRecord]:
        """
        Get a specific vector by ID.

        Args:
            collection: Collection name
            id: Vector ID
            namespace: Optional namespace

        Returns:
            VectorRecord or None
        """
        if collection not in self._collections:
            return None

        ns = namespace or "default"
        return self._collections[collection].get(ns, {}).get(id)

    def _calculate_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate similarity between two vectors.

        Uses numpy if available, otherwise pure Python.
        """
        if HAS_NUMPY:
            return self._numpy_similarity(vec1, vec2)
        return self._python_similarity(vec1, vec2)

    def _numpy_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate similarity using numpy."""
        a = np.array(vec1)
        b = np.array(vec2)

        if self.metric == "cosine":
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))

        elif self.metric == "dotproduct":
            return float(np.dot(a, b))

        elif self.metric == "euclidean":
            # Return negative distance (so higher = more similar)
            return -float(np.linalg.norm(a - b))

        else:
            raise ValueError(f"Unknown metric: {self.metric}")

    def _python_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate similarity using pure Python."""
        if self.metric == "cosine":
            dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
            norm1 = math.sqrt(sum(a * a for a in vec1))
            norm2 = math.sqrt(sum(b * b for b in vec2))
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)

        elif self.metric == "dotproduct":
            return sum(a * b for a, b in zip(vec1, vec2, strict=False))

        elif self.metric == "euclidean":
            dist = math.sqrt(
                sum((a - b) ** 2 for a, b in zip(vec1, vec2, strict=False))
            )
            return -dist

        else:
            raise ValueError(f"Unknown metric: {self.metric}")

    def _matches_filter(self, metadata: dict[str, Any], filter: dict[str, Any]) -> bool:
        """
        Check if metadata matches filter criteria.

        Supports:
        - Exact match: {"field": "value"}
        - $eq: {"field": {"$eq": "value"}}
        - $ne: {"field": {"$ne": "value"}}
        - $gt, $gte, $lt, $lte for numbers
        - $in: {"field": {"$in": ["a", "b"]}}
        - $nin: {"field": {"$nin": ["a", "b"]}}
        """
        for key, condition in filter.items():
            if key not in metadata:
                return False

            value = metadata[key]

            if isinstance(condition, dict):
                # Operator-based filter
                for op, op_value in condition.items():
                    if (
                        op == "$eq"
                        and value != op_value
                        or op == "$ne"
                        and value == op_value
                        or op == "$gt"
                        and not (value > op_value)
                        or op == "$gte"
                        and not (value >= op_value)
                        or op == "$lt"
                        and not (value < op_value)
                        or op == "$lte"
                        and not (value <= op_value)
                        or op == "$in"
                        and value not in op_value
                        or op == "$nin"
                        and value in op_value
                    ):
                        return False
            else:
                # Exact match
                if value != condition:
                    return False

        return True

    def get_info(self) -> dict[str, Any]:
        """Get adapter information."""
        info = super().get_info()
        info.update(
            {
                "collections": self.list_collections(),
                "total_vectors": sum(self.count(c) for c in self.list_collections()),
                "has_numpy": HAS_NUMPY,
            }
        )
        return info
