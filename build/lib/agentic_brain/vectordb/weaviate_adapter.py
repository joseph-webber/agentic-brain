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
Weaviate Vector Database Adapter
=================================

Adapter for Weaviate vector search engine.
Requires: pip install weaviate-client

The weaviate-client is an OPTIONAL dependency. This module
gracefully handles ImportError if not installed.

Copyright (C) 2026 Joseph Webber
License: Apache-2.0
"""

import contextlib
import logging
import os
import uuid as uuid_lib
from typing import Any, Optional, Union

from agentic_brain.vectordb import (
    VectorDBAdapter,
    VectorRecord,
    VectorSearchResult,
)

logger = logging.getLogger(__name__)

# Try to import weaviate
try:
    import weaviate
    from weaviate.classes.config import Configure, DataType, Property
    from weaviate.classes.query import MetadataQuery

    HAS_WEAVIATE = True
except ImportError:
    HAS_WEAVIATE = False
    weaviate = None  # type: ignore
    logger.debug("weaviate-client not installed, WeaviateAdapter unavailable")


class WeaviateNotInstalledError(ImportError):
    """Raised when weaviate-client is not installed."""

    def __init__(self):
        super().__init__(
            "weaviate-client is not installed. "
            "Install with: pip install weaviate-client"
        )


class WeaviateAdapter(VectorDBAdapter):
    """
    Weaviate vector database adapter.

    Requires the weaviate-client package to be installed.
    Supports both local Weaviate and Weaviate Cloud.

    Example:
        >>> adapter = WeaviateAdapter(
        ...     url="http://localhost:8080",
        ...     dimension=384
        ... )
        >>> adapter.connect()
        >>> adapter.create_collection("Document")
        >>> adapter.upsert("Document", vectors)
        >>> results = adapter.search("Document", query_vector, top_k=10)

    Environment Variables:
        WEAVIATE_URL: Weaviate server URL
        WEAVIATE_API_KEY: API key for Weaviate Cloud
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        dimension: int = 384,
        metric: str = "cosine",
        grpc_port: int = 50051,
        **kwargs,
    ):
        """
        Initialize Weaviate adapter.

        Args:
            url: Weaviate server URL (or WEAVIATE_URL env var)
            api_key: API key for Weaviate Cloud (or WEAVIATE_API_KEY env var)
            dimension: Vector dimensionality
            metric: Distance metric ("cosine", "l2", "dot")
            grpc_port: gRPC port for batch operations
        """
        if not HAS_WEAVIATE:
            raise WeaviateNotInstalledError()

        super().__init__(dimension=dimension, metric=metric, **kwargs)

        self.url = url or os.getenv("WEAVIATE_URL", "http://localhost:8080")
        self.api_key = api_key or os.getenv("WEAVIATE_API_KEY")
        self.grpc_port = grpc_port

        self._client: Optional[weaviate.WeaviateClient] = None

    def _get_distance_metric(self) -> str:
        """Convert metric to Weaviate format."""
        metric_map = {
            "cosine": "cosine",
            "euclidean": "l2-squared",
            "l2": "l2-squared",
            "dotproduct": "dot",
            "dot": "dot",
        }
        return metric_map.get(self.metric, "cosine")

    def connect(self) -> bool:
        """
        Connect to Weaviate.

        Returns:
            True if connection successful

        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Parse URL to determine connection type
            if "weaviate.cloud" in self.url or "wcs." in self.url:
                # Weaviate Cloud Service
                if not self.api_key:
                    raise ConnectionError("API key required for Weaviate Cloud")

                self._client = weaviate.connect_to_wcs(
                    cluster_url=self.url,
                    auth_credentials=weaviate.auth.AuthApiKey(self.api_key),
                )
            else:
                # Local Weaviate
                # Parse host and port from URL
                host = self.url.replace("http://", "").replace("https://", "")
                if ":" in host:
                    host, port_str = host.split(":")
                    port = int(port_str)
                else:
                    port = 8080

                self._client = weaviate.connect_to_local(
                    host=host, port=port, grpc_port=self.grpc_port
                )

            # Test connection
            self._client.is_ready()
            self.connected = True
            logger.info(f"Connected to Weaviate at {self.url}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            raise ConnectionError(f"Weaviate connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from Weaviate."""
        if self._client:
            with contextlib.suppress(Exception):
                self._client.close()
        self._client = None
        self.connected = False
        logger.info("Disconnected from Weaviate")

    def create_collection(
        self,
        name: str,
        dimension: Optional[int] = None,
        metric: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Create a Weaviate collection (class).

        Args:
            name: Collection name (will be capitalized)
            dimension: Vector dimension
            metric: Distance metric
            **kwargs: Additional properties

        Returns:
            True if created successfully
        """
        if not self._client:
            raise ConnectionError("Not connected to Weaviate")

        # Weaviate class names must be capitalized
        class_name = name[0].upper() + name[1:] if name else name

        try:
            if self.collection_exists(class_name):
                logger.warning(f"Collection '{class_name}' already exists")
                return False

            # Create collection with vector index
            self._client.collections.create(
                name=class_name,
                vectorizer_config=Configure.Vectorizer.none(),
                vector_index_config=Configure.VectorIndex.hnsw(
                    distance_metric=(
                        Configure.VectorDistances.COSINE
                        if (metric or self.metric) == "cosine"
                        else Configure.VectorDistances.L2_SQUARED
                    )
                ),
                properties=[
                    Property(name="content", data_type=DataType.TEXT),
                    Property(name="metadata_json", data_type=DataType.TEXT),
                ],
            )

            logger.info(f"Created Weaviate collection '{class_name}'")
            return True

        except Exception as e:
            logger.error(f"Failed to create collection '{name}': {e}")
            return False

    def delete_collection(self, name: str) -> bool:
        """
        Delete a Weaviate collection.

        Args:
            name: Collection name

        Returns:
            True if deleted
        """
        if not self._client:
            raise ConnectionError("Not connected to Weaviate")

        class_name = name[0].upper() + name[1:] if name else name

        try:
            self._client.collections.delete(class_name)
            logger.info(f"Deleted Weaviate collection '{class_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{name}': {e}")
            return False

    def collection_exists(self, name: str) -> bool:
        """Check if collection exists."""
        if not self._client:
            return False

        class_name = name[0].upper() + name[1:] if name else name

        try:
            return self._client.collections.exists(class_name)
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        """List all collections."""
        if not self._client:
            return []

        try:
            collections = self._client.collections.list_all()
            return list(collections.keys())
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
        Upsert vectors to Weaviate.

        Args:
            collection: Collection name
            vectors: Vector records
            namespace: Optional namespace (stored in metadata)

        Returns:
            Number of vectors upserted
        """
        if not self._client:
            raise ConnectionError("Not connected to Weaviate")

        class_name = (
            collection[0].upper() + collection[1:] if collection else collection
        )

        # Auto-create collection if needed
        if not self.collection_exists(class_name):
            self.create_collection(class_name)

        coll = self._client.collections.get(class_name)
        count = 0

        try:
            import json

            with coll.batch.dynamic() as batch:
                for item in vectors:
                    record = self._to_vector_record(item)
                    self._validate_vector(record.vector)

                    # Add namespace to metadata if provided
                    metadata = record.metadata.copy()
                    if namespace:
                        metadata["_namespace"] = namespace

                    # Use record ID as UUID if valid, else generate
                    try:
                        obj_uuid = uuid_lib.UUID(record.id)
                    except ValueError:
                        # Create deterministic UUID from ID string
                        obj_uuid = uuid_lib.uuid5(uuid_lib.NAMESPACE_DNS, record.id)

                    batch.add_object(
                        properties={
                            "content": metadata.get("content", ""),
                            "metadata_json": json.dumps(metadata),
                        },
                        vector=record.vector,
                        uuid=obj_uuid,
                    )
                    count += 1

            logger.debug(f"Upserted {count} vectors to '{class_name}'")
            return count

        except Exception as e:
            logger.error(f"Upsert failed: {e}")
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
        Search for similar vectors in Weaviate.

        Args:
            collection: Collection name
            query_vector: Query embedding
            top_k: Number of results
            namespace: Optional namespace filter
            filter: Metadata filter
            include_vectors: Include vectors in results
            include_metadata: Include metadata in results

        Returns:
            List of search results
        """
        if not self._client:
            return []

        class_name = (
            collection[0].upper() + collection[1:] if collection else collection
        )

        if not self.collection_exists(class_name):
            return []

        self._validate_vector(query_vector)

        try:
            import json

            coll = self._client.collections.get(class_name)

            response = coll.query.near_vector(
                near_vector=query_vector,
                limit=top_k,
                return_metadata=MetadataQuery(distance=True),
                include_vector=include_vectors,
            )

            results = []
            for obj in response.objects:
                # Parse metadata from JSON
                metadata = {}
                if include_metadata:
                    with contextlib.suppress(json.JSONDecodeError):
                        metadata = json.loads(obj.properties.get("metadata_json", "{}"))

                # Apply namespace filter
                if namespace and metadata.get("_namespace") != namespace:
                    continue

                # Convert distance to score (1 - distance for cosine)
                distance = obj.metadata.distance if obj.metadata else 0
                score = 1.0 - distance if self.metric == "cosine" else -distance

                result = VectorSearchResult(
                    id=str(obj.uuid),
                    score=score,
                    distance=distance,
                    vector=(
                        obj.vector.get("default")
                        if include_vectors and obj.vector
                        else None
                    ),
                    metadata=metadata if include_metadata else {},
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
        Delete vectors from Weaviate.

        Args:
            collection: Collection name
            ids: Specific IDs (UUIDs) to delete
            namespace: Optional namespace
            filter: Delete by filter
            delete_all: Delete all vectors

        Returns:
            Number deleted
        """
        if not self._client:
            raise ConnectionError("Not connected to Weaviate")

        class_name = (
            collection[0].upper() + collection[1:] if collection else collection
        )

        if not self.collection_exists(class_name):
            return 0

        coll = self._client.collections.get(class_name)
        count = 0

        try:
            if delete_all:
                # Delete and recreate collection
                old_count = self.count(collection)
                self.delete_collection(collection)
                self.create_collection(collection)
                return old_count

            if ids:
                for id_str in ids:
                    try:
                        obj_uuid = uuid_lib.UUID(id_str)
                    except ValueError:
                        obj_uuid = uuid_lib.uuid5(uuid_lib.NAMESPACE_DNS, id_str)

                    try:
                        coll.data.delete_by_id(obj_uuid)
                        count += 1
                    except Exception:
                        pass

            return count

        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return count

    def count(self, collection: str, namespace: Optional[str] = None) -> int:
        """
        Get vector count in collection.

        Args:
            collection: Collection name
            namespace: Optional namespace (not supported, returns total)

        Returns:
            Vector count
        """
        if not self._client:
            return 0

        class_name = (
            collection[0].upper() + collection[1:] if collection else collection
        )

        if not self.collection_exists(class_name):
            return 0

        try:
            coll = self._client.collections.get(class_name)
            result = coll.aggregate.over_all(total_count=True)
            return result.total_count or 0
        except Exception as e:
            logger.error(f"Failed to get count: {e}")
            return 0

    def get_info(self) -> dict[str, Any]:
        """Get adapter information."""
        info = super().get_info()
        info.update({"url": self.url, "collections": self.list_collections()})
        return info
