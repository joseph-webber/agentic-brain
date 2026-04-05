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

from __future__ import annotations

import contextlib
import logging
import os
from typing import Any, Mapping, Sequence

from .base import VectorRecord, VectorSearchResult, VectorStore

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency
    from agentic_brain.vectordb.qdrant_adapter import HAS_QDRANT
    from agentic_brain.vectordb.qdrant_adapter import (
        QdrantAdapter as LegacyQdrantAdapter,
    )
except Exception:  # pragma: no cover - optional dependency
    HAS_QDRANT = False
    LegacyQdrantAdapter = None  # type: ignore[assignment]


class QdrantVectorStore(VectorStore):
    """Unified Qdrant-backed vector store."""

    backend_name = "qdrant"

    def __init__(
        self,
        *,
        collection_name: str = "default",
        dimension: int = 1536,
        metric: str = "cosine",
        namespace: str | None = None,
        url: str | None = None,
        api_key: str | None = None,
        prefer_grpc: bool = False,
        timeout: float = 30.0,
        **settings: Any,
    ) -> None:
        super().__init__(
            collection_name=collection_name,
            dimension=dimension,
            metric=metric,
            namespace=namespace,
            url=url,
            api_key=api_key,
            prefer_grpc=prefer_grpc,
            timeout=timeout,
            **settings,
        )
        self.url = url or os.getenv("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.prefer_grpc = prefer_grpc
        self.timeout = timeout
        self._legacy: Any | None = None

    @classmethod
    def available(cls) -> bool:
        return HAS_QDRANT

    def connect(self) -> bool:
        if HAS_QDRANT and LegacyQdrantAdapter is not None:
            try:
                self._legacy = LegacyQdrantAdapter(
                    url=self.url,
                    api_key=self.api_key,
                    dimension=self.config.dimension,
                    metric=self.config.metric,
                    prefer_grpc=self.prefer_grpc,
                    timeout=self.timeout,
                )
                self._legacy.connect()
                self._mode = "remote"
            except Exception as exc:
                logger.warning("Qdrant connection failed, using memory fallback: %s", exc)
                self._legacy = None
                self._mode = "memory"
        self._connected = True
        return True

    def close(self) -> None:
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                self._legacy.disconnect()
        self._legacy = None
        self._connected = False

    def create_collection(
        self,
        collection_name: str | None = None,
        *,
        dimension: int | None = None,
        metric: str | None = None,
        **kwargs: Any,
    ) -> bool:
        created = self._memory_create_collection(
            collection_name, dimension=dimension, metric=metric
        )
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                self._legacy.create_collection(
                    self._collection_name(collection_name),
                    dimension=dimension,
                    metric=metric,
                    **kwargs,
                )
        return created

    def delete_collection(self, collection_name: str | None = None) -> bool:
        collection_name = self._collection_name(collection_name)
        deleted = self._memory_delete_collection(collection_name)
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                self._legacy.delete_collection(collection_name)
        return deleted

    def list_collections(self) -> list[str]:
        collections = set(self._memory_list_collections())
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                collections.update(self._legacy.list_collections())
        return sorted(collections)

    def upsert(
        self,
        records: Sequence[Mapping[str, Any] | VectorRecord],
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        collection_name = self._collection_name(collection_name)
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                self._legacy.upsert(
                    collection_name,
                    [record.as_dict() if isinstance(record, VectorRecord) else record for record in records],
                    namespace=namespace,
                )
        return self._memory_upsert(records, collection_name=collection_name, namespace=namespace)

    def search(
        self,
        query_vector: Sequence[float],
        *,
        collection_name: str | None = None,
        top_k: int = 5,
        namespace: str | None = None,
        filter: Mapping[str, Any] | None = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> list[VectorSearchResult]:
        collection_name = self._collection_name(collection_name)
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                results = self._legacy.search(
                    collection_name,
                    list(query_vector),
                    top_k=top_k,
                    namespace=namespace,
                    filter=dict(filter or {}),
                    include_vectors=include_vectors,
                    include_metadata=include_metadata,
                )
                return [self._result_from_mapping(result.__dict__) for result in results]
        return self._memory_search(
            query_vector,
            collection_name=collection_name,
            top_k=top_k,
            namespace=namespace,
            filter=filter,
            include_vectors=include_vectors,
            include_metadata=include_metadata,
        )

    def delete(
        self,
        *,
        collection_name: str | None = None,
        ids: Sequence[str] | None = None,
        namespace: str | None = None,
        filter: Mapping[str, Any] | None = None,
        delete_all: bool = False,
    ) -> int:
        collection_name = self._collection_name(collection_name)
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                self._legacy.delete(
                    collection_name,
                    ids=list(ids) if ids else None,
                    namespace=namespace,
                    filter=dict(filter or {}) if filter else None,
                    delete_all=delete_all,
                )
        return self._memory_delete(
            collection_name=collection_name,
            ids=ids,
            namespace=namespace,
            filter=filter,
            delete_all=delete_all,
        )

    def count(
        self,
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        collection_name = self._collection_name(collection_name)
        if self._legacy is not None:
            with contextlib.suppress(Exception):
                return int(self._legacy.count(collection_name, namespace=namespace))
        return self._memory_count(collection_name=collection_name, namespace=namespace)

    def stats(self) -> dict[str, Any]:
        stats = self._memory_stats()
        stats.update(
            {
                "available": self.available(),
                "url": self.url,
                "prefer_grpc": self.prefer_grpc,
                "timeout": self.timeout,
            }
        )
        return stats
