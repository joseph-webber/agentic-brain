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
Pinecone Vector Database Adapter
=================================

Adapter for Pinecone cloud vector database.
Requires: pip install pinecone-client

The pinecone-client is an OPTIONAL dependency. This module
gracefully handles ImportError if not installed.

Copyright (C) 2026 Joseph Webber
License: GPL-3.0-or-later
"""

import logging
import os
from typing import Any, Optional, Union

from agentic_brain.vectordb import (
    VectorDBAdapter,
    VectorRecord,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)

# Try to import pinecone
try:
    from pinecone import Pinecone, ServerlessSpec

    HAS_PINECONE = True
except ImportError:
    HAS_PINECONE = False
    Pinecone = None  # type: ignore
    ServerlessSpec = None  # type: ignore
    logger.debug("pinecone-client not installed, PineconeAdapter unavailable")


class PineconeNotInstalledError(ImportError):
    """Raised when pinecone-client is not installed."""

    def __init__(self):
        super().__init__(
            "pinecone-client is not installed. "
            "Install with: pip install pinecone-client"
        )


class PineconeAdapter(VectorDBAdapter):
    """
    Pinecone vector database adapter.

    Requires the pinecone-client package to be installed.
    Supports serverless and pod-based indexes.

    Example:
        >>> adapter = PineconeAdapter(
        ...     api_key="your-api-key",
        ...     dimension=384
        ... )
        >>> adapter.connect()
        >>> adapter.create_collection("my-index")
        >>> adapter.upsert("my-index", vectors)
        >>> results = adapter.search("my-index", query_vector, top_k=10)

    Environment Variables:
        PINECONE_API_KEY: API key for Pinecone
        PINECONE_ENVIRONMENT: Pinecone environment (e.g., "us-east-1-aws")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        dimension: int = 384,
        metric: str = "cosine",
        cloud: str = "aws",
        region: str = "us-east-1",
        **kwargs,
    ):
        """
        Initialize Pinecone adapter.

        Args:
            api_key: Pinecone API key (or PINECONE_API_KEY env var)
            environment: Pinecone environment (for pod-based, deprecated)
            dimension: Vector dimensionality
            metric: Distance metric ("cosine", "euclidean", "dotproduct")
            cloud: Cloud provider for serverless ("aws", "gcp", "azure")
            region: Cloud region for serverless
        """
        if not HAS_PINECONE:
            raise PineconeNotInstalledError()

        super().__init__(dimension=dimension, metric=metric, **kwargs)

        self.api_key = api_key or os.getenv("PINECONE_API_KEY")
        self.environment = environment or os.getenv("PINECONE_ENVIRONMENT")
        self.cloud = cloud
        self.region = region

        self._client: Optional[Pinecone] = None
        self._indexes: dict[str, Any] = {}

    def connect(self) -> bool:
        """
        Connect to Pinecone.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If API key is missing or connection fails
        """
        if not self.api_key:
            raise ConnectionError(
                "Pinecone API key required. Set PINECONE_API_KEY or pass api_key"
            )

        try:
            self._client = Pinecone(api_key=self.api_key)
            # Test connection by listing indexes
            self._client.list_indexes()
            self.connected = True
            logger.info("Connected to Pinecone")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Pinecone: {e}")
            raise ConnectionError(f"Pinecone connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from Pinecone."""
        self._client = None
        self._indexes.clear()
        self.connected = False
        logger.info("Disconnected from Pinecone")

    def _get_index(self, name: str) -> Any:
        """Get or cache an index connection."""
        if name not in self._indexes:
            if not self._client:
                raise ConnectionError("Not connected to Pinecone")
            self._indexes[name] = self._client.Index(name)
        return self._indexes[name]

    def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metric: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Create a Pinecone index.

        Args:
            name: Index name
            dimension: Vector dimension
            metric: Distance metric
            **kwargs: Additional options (e.g., pod_type, replicas)

        Returns:
            True if created successfully
        """
        if not self._client:
            raise ConnectionError("Not connected to Pinecone")

        dim = dimension or self.dimension
        met = metric or self.metric

        try:
            # Check if already exists
            if self.collection_exists(name):
                logger.warning(f"Index '{name}' already exists")
                return False

            # Create serverless index
            self._client.create_index(
                name=name,
                dimension=dim,
                metric=met,
                spec=ServerlessSpec(
                    cloud=kwargs.get("cloud", self.cloud),
                    region=kwargs.get("region", self.region),
                ),
            )

            logger.info(f"Created Pinecone index '{name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to create index '{name}': {e}")
            return False

    def delete_collection(self, name: str) -> bool:
        """
        Delete a Pinecone index.

        Args:
            name: Index name

        Returns:
            True if deleted
        """
        if not self._client:
            raise ConnectionError("Not connected to Pinecone")

        try:
            self._client.delete_index(name)
            self._indexes.pop(name, None)
            logger.info(f"Deleted Pinecone index '{name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete index '{name}': {e}")
            return False

    def collection_exists(self, name: str) -> bool:
        """Check if index exists."""
        if not self._client:
            return False

        try:
            indexes = self._client.list_indexes()
            return any(idx.name == name for idx in indexes)
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """List all indexes."""
        if not self._client:
            return []

        try:
            indexes = self._client.list_indexes()
            return [idx.name for idx in indexes]
        except Exception as e:
            logger.error(f"Failed to list indexes: {e}")
            return []

    def upsert(
        self,
        collection: str,
        vectors: list[Union[dict[str, Any], VectorRecord]],
        namespace: Optional[str] = None,
    ) -> int:
        """
        Upsert vectors to Pinecone.

        Args:
            collection: Index name
            vectors: Vector records
            namespace: Optional namespace

        Returns:
            Number of vectors upserted
        """
        index = self._get_index(collection)

        # Convert to Pinecone format
        pinecone_vectors = []
        for item in vectors:
            record = self._to_vector_record(item)
            self._validate_vector(record.vector)
            pinecone_vectors.append(
                {"id": record.id, "values": record.vector, "metadata": record.metadata}
            )

        # Batch upsert (Pinecone recommends batches of ~100)
        batch_size = 100
        total_upserted = 0

        for i in range(0, len(pinecone_vectors), batch_size):
            batch = pinecone_vectors[i : i + batch_size]
            try:
                if namespace:
                    index.upsert(vectors=batch, namespace=namespace)
                else:
                    index.upsert(vectors=batch)
                total_upserted += len(batch)
            except Exception as e:
                logger.error(f"Upsert batch failed: {e}")

        logger.debug(f"Upserted {total_upserted} vectors to '{collection}'")
        return total_upserted

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
        Search for similar vectors in Pinecone.

        Args:
            collection: Index name
            query_vector: Query embedding
            top_k: Number of results
            namespace: Optional namespace
            filter: Metadata filter (Pinecone format)
            include_vectors: Include vectors in results
            include_metadata: Include metadata in results

        Returns:
            List of search results
        """
        index = self._get_index(collection)
        self._validate_vector(query_vector)

        try:
            kwargs = {
                "vector": query_vector,
                "top_k": top_k,
                "include_values": include_vectors,
                "include_metadata": include_metadata,
            }

            if namespace:
                kwargs["namespace"] = namespace
            if filter:
                kwargs["filter"] = filter

            response = index.query(**kwargs)

            results = []
            for match in response.get("matches", []):
                result = VectorSearchResult(
                    id=match["id"],
                    score=match.get("score", 0.0),
                    vector=match.get("values") if include_vectors else None,
                    metadata=match.get("metadata", {}) if include_metadata else {},
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
        Delete vectors from Pinecone.

        Args:
            collection: Index name
            ids: Specific IDs to delete
            namespace: Optional namespace
            filter: Delete by filter
            delete_all: Delete all vectors

        Returns:
            Number deleted (estimated for Pinecone)
        """
        index = self._get_index(collection)

        try:
            kwargs = {}
            if namespace:
                kwargs["namespace"] = namespace

            if delete_all:
                index.delete(delete_all=True, **kwargs)
                return -1  # Pinecone doesn't return count for delete_all

            if ids:
                index.delete(ids=ids, **kwargs)
                return len(ids)

            if filter:
                index.delete(filter=filter, **kwargs)
                return -1  # Unknown count for filter delete

            return 0

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return 0

    def count(self, collection: str, namespace: Optional[str] = None) -> int:
        """
        Get vector count in index.

        Note: Pinecone stats may have some delay.

        Args:
            collection: Index name
            namespace: Optional namespace

        Returns:
            Vector count
        """
        index = self._get_index(collection)

        try:
            stats = index.describe_index_stats()

            if namespace:
                ns_stats = stats.get("namespaces", {}).get(namespace, {})
                return ns_stats.get("vector_count", 0)

            return stats.get("total_vector_count", 0)

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return 0

    def get_info(self) -> dict[str, Any]:
        """Get adapter information."""
        info = super().get_info()
        info.update(
            {
                "cloud": self.cloud,
                "region": self.region,
                "indexes": self.list_collections(),
            }
        )
        return info
