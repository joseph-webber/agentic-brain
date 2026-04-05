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
Qdrant Vector Database Adapter
===============================

Adapter for Qdrant vector similarity search engine.
Requires: pip install qdrant-client

The qdrant-client is an OPTIONAL dependency. This module
gracefully handles ImportError if not installed.

Copyright (C) 2026 Joseph Webber
License: Apache-2.0
"""

import contextlib
import logging
import os
from typing import Any, Optional

from agentic_brain.vectordb import (
    VectorDBAdapter,
    VectorRecord,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)

# Try to import qdrant
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qdrant_models
    from qdrant_client.http.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        Range,
        VectorParams,
    )

    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False
    QdrantClient = None  # type: ignore
    qdrant_models = None  # type: ignore
    logger.debug("qdrant-client not installed, QdrantAdapter unavailable")


class QdrantNotInstalledError(ImportError):
    """Raised when qdrant-client is not installed."""

    def __init__(self):
        super().__init__(
            "qdrant-client is not installed. " "Install with: pip install qdrant-client"
        )


class QdrantAdapter(VectorDBAdapter):
    """
    Qdrant vector database adapter.

    Requires the qdrant-client package to be installed.
    Supports local, in-memory, and cloud Qdrant instances.

    Example:
        >>> adapter = QdrantAdapter(
        ...     url="http://localhost:6333",
        ...     dimension=384
        ... )
        >>> adapter.connect()
        >>> adapter.create_collection("embeddings")
        >>> adapter.upsert("embeddings", vectors)
        >>> results = adapter.search("embeddings", query_vector, top_k=10)

    Environment Variables:
        QDRANT_URL: Qdrant server URL
        QDRANT_API_KEY: API key for Qdrant Cloud
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        dimension: int = 384,
        metric: str = "cosine",
        prefer_grpc: bool = False,
        timeout: float = 30.0,
        **kwargs,
    ):
        """
        Initialize Qdrant adapter.

        Args:
            url: Qdrant server URL (or QDRANT_URL env var)
                 Use ":memory:" for in-memory mode
            api_key: API key for Qdrant Cloud (or QDRANT_API_KEY env var)
            dimension: Vector dimensionality
            metric: Distance metric ("cosine", "euclidean", "dot")
            prefer_grpc: Use gRPC instead of HTTP
            timeout: Request timeout in seconds
        """
        if not HAS_QDRANT:
            raise QdrantNotInstalledError()

        super().__init__(dimension=dimension, metric=metric, **kwargs)

        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.prefer_grpc = prefer_grpc
        self.timeout = timeout

        self._client: Optional[QdrantClient] = None

    def _get_distance(self) -> "Distance":
        """Convert metric to Qdrant Distance enum."""
        metric_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "l2": Distance.EUCLID,
            "dotproduct": Distance.DOT,
            "dot": Distance.DOT,
        }
        return metric_map.get(self.metric, Distance.COSINE)

    def connect(self) -> bool:
        """
        Connect to Qdrant.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
        """
        try:
            if self.url == ":memory:":
                # In-memory mode
                self._client = QdrantClient(location=":memory:")
            elif "cloud.qdrant.io" in self.url or self.api_key:
                # Qdrant Cloud
                self._client = QdrantClient(
                    url=self.url,
                    api_key=self.api_key,
                    prefer_grpc=self.prefer_grpc,
                    timeout=self.timeout,
                )
            else:
                # Local Qdrant
                self._client = QdrantClient(
                    url=self.url, prefer_grpc=self.prefer_grpc, timeout=self.timeout
                )

            # Test connection
            self._client.get_collections()
            self.connected = True
            logger.info(f"Connected to Qdrant at {self.url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise ConnectionError(f"Qdrant connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from Qdrant."""
        if self._client:
            with contextlib.suppress(Exception):
                self._client.close()
        self._client = None
        self.connected = False
        logger.info("Disconnected from Qdrant")

    def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metric: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Create a Qdrant collection.

        Args:
            name: Collection name
            dimension: Vector dimension
            metric: Distance metric
            **kwargs: Additional options (e.g., on_disk, hnsw_config)

        Returns:
            True if created successfully
        """
        if not self._client:
            raise ConnectionError("Not connected to Qdrant")

        dim = dimension or self.dimension

        try:
            if self.collection_exists(name):
                logger.warning(f"Collection '{name}' already exists")
                return False

            # Determine distance metric
            if metric:
                distance = {
                    "cosine": Distance.COSINE,
                    "euclidean": Distance.EUCLID,
                    "dot": Distance.DOT,
                }.get(metric, Distance.COSINE)
            else:
                distance = self._get_distance()

            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=dim, distance=distance, on_disk=kwargs.get("on_disk", False)
                ),
            )

            logger.info(f"Created Qdrant collection '{name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection '{name}': {e}")
            return False

    def delete_collection(self, name: str) -> bool:
        """
        Delete a Qdrant collection.

        Args:
            name: Collection name

        Returns:
            True if deleted
        """
        if not self._client:
            raise ConnectionError("Not connected to Qdrant")

        try:
            self._client.delete_collection(collection_name=name)
            logger.info(f"Deleted Qdrant collection '{name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{name}': {e}")
            return False

    def collection_exists(self, name: str) -> bool:
        """Check if collection exists."""
        if not self._client:
            return False

        try:
            self._client.get_collection(collection_name=name)
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """List all collections."""
        if not self._client:
            return []

        try:
            collections = self._client.get_collections()
            return [c.name for c in collections.collections]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def upsert(
        self,
        collection: str,
        vectors: list[dict[str, Any] | VectorRecord],
        namespace: Optional[str] = None,
    ) -> int:
        """
        Upsert vectors to Qdrant.

        Args:
            collection: Collection name
            vectors: Vector records
            namespace: Optional namespace (stored in payload)

        Returns:
            Number of vectors upserted
        """
        if not self._client:
            raise ConnectionError("Not connected to Qdrant")

        # Auto-create collection if needed
        if not self.collection_exists(collection):
            self.create_collection(collection)

        points = []
        for _i, item in enumerate(vectors):
            record = self._to_vector_record(item)
            self._validate_vector(record.vector)

            # Add namespace to payload if provided
            payload = record.metadata.copy()
            if namespace:
                payload["_namespace"] = namespace

            # Generate numeric ID if string
            try:
                point_id = int(record.id)
            except ValueError:
                # Use hash for non-numeric IDs
                point_id = abs(hash(record.id)) % (2**63)

            points.append(
                PointStruct(
                    id=point_id,
                    vector=record.vector,
                    payload={**payload, "_original_id": record.id},
                )
            )

        try:
            self._client.upsert(collection_name=collection, points=points, wait=True)
            logger.debug(f"Upserted {len(points)} vectors to '{collection}'")
            return len(points)

        except Exception as e:
            logger.error(f"Upsert failed: {e}")
            return 0

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
        Search for similar vectors in Qdrant.

        Args:
            collection: Collection name
            query_vector: Query embedding
            top_k: Number of results
            namespace: Optional namespace filter
            filter: Metadata filter
            include_vectors: Include vectors in results
            include_metadata: Include metadata (payload)

        Returns:
            List of search results
        """
        if not self._client:
            return []

        if not self.collection_exists(collection):
            return []

        self._validate_vector(query_vector)

        try:
            # Build filter
            qdrant_filter = None
            conditions = []

            if namespace:
                conditions.append(
                    FieldCondition(key="_namespace", match=MatchValue(value=namespace))
                )

            if filter:
                for key, value in filter.items():
                    if isinstance(value, dict):
                        # Handle operators
                        for op, op_value in value.items():
                            if op == "$eq":
                                conditions.append(
                                    FieldCondition(
                                        key=key, match=MatchValue(value=op_value)
                                    )
                                )
                            elif op in ("$gt", "$gte", "$lt", "$lte"):
                                range_params = {}
                                if op == "$gt":
                                    range_params["gt"] = op_value
                                elif op == "$gte":
                                    range_params["gte"] = op_value
                                elif op == "$lt":
                                    range_params["lt"] = op_value
                                elif op == "$lte":
                                    range_params["lte"] = op_value

                                conditions.append(
                                    FieldCondition(key=key, range=Range(**range_params))
                                )
                    else:
                        # Exact match
                        conditions.append(
                            FieldCondition(key=key, match=MatchValue(value=value))
                        )

            if conditions:
                qdrant_filter = Filter(must=conditions)

            response = self._client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_vectors=include_vectors,
                with_payload=include_metadata,
            )

            results = []
            for hit in response:
                payload = hit.payload or {}
                original_id = payload.pop("_original_id", str(hit.id))

                result = VectorSearchResult(
                    id=original_id,
                    score=hit.score,
                    vector=hit.vector if include_vectors else None,
                    metadata=payload if include_metadata else {},
                )
                results.append(result)

            return results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def delete(
        self,
        collection: str,
        ids: Optional[list[str]] = None,
        namespace: Optional[str] = None,
        filter: Optional[dict[str, Any]] = None,
        delete_all: bool = False,
    ) -> int:
        """
        Delete vectors from Qdrant.

        Args:
            collection: Collection name
            ids: Specific IDs to delete
            namespace: Optional namespace
            filter: Delete by filter
            delete_all: Delete all vectors

        Returns:
            Number deleted (estimated)
        """
        if not self._client:
            raise ConnectionError("Not connected to Qdrant")

        if not self.collection_exists(collection):
            return 0

        try:
            if delete_all:
                # Delete and recreate collection
                old_count = self.count(collection)
                self.delete_collection(collection)
                self.create_collection(collection)
                return old_count

            if ids:
                # Convert string IDs to point IDs
                point_ids = []
                for id_str in ids:
                    try:
                        point_ids.append(int(id_str))
                    except ValueError:
                        point_ids.append(abs(hash(id_str)) % (2**63))

                self._client.delete(
                    collection_name=collection,
                    points_selector=qdrant_models.PointIdsList(points=point_ids),
                )
                return len(ids)

            if namespace or filter:
                conditions = []

                if namespace:
                    conditions.append(
                        FieldCondition(
                            key="_namespace", match=MatchValue(value=namespace)
                        )
                    )

                if filter:
                    for key, value in filter.items():
                        if not isinstance(value, dict):
                            conditions.append(
                                FieldCondition(key=key, match=MatchValue(value=value))
                            )

                self._client.delete(
                    collection_name=collection,
                    points_selector=qdrant_models.FilterSelector(
                        filter=Filter(must=conditions)
                    ),
                )
                return -1  # Unknown count

            return 0

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0

    def count(self, collection: str, namespace: Optional[str] = None) -> int:
        """
        Get vector count in collection.

        Args:
            collection: Collection name
            namespace: Optional namespace filter

        Returns:
            Vector count
        """
        if not self._client:
            return 0

        if not self.collection_exists(collection):
            return 0

        try:
            if namespace:
                # Count with filter
                result = self._client.count(
                    collection_name=collection,
                    count_filter=Filter(
                        must=[
                            FieldCondition(
                                key="_namespace", match=MatchValue(value=namespace)
                            )
                        ]
                    ),
                )
            else:
                result = self._client.count(collection_name=collection)

            return result.count

        except Exception as e:
            logger.error(f"Failed to get count: {e}")
            return 0

    def get_info(self) -> dict[str, Any]:
        """Get adapter information."""
        info = super().get_info()
        info.update(
            {
                "url": self.url,
                "prefer_grpc": self.prefer_grpc,
                "collections": self.list_collections(),
            }
        )
        return info
