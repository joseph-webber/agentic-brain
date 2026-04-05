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
    import chromadb

    HAS_CHROMADB = True
except ImportError:  # pragma: no cover - optional dependency
    chromadb = None  # type: ignore[assignment]
    HAS_CHROMADB = False


class ChromaDBVectorStore(VectorStore):
    """Unified ChromaDB-backed vector store."""

    backend_name = "chromadb"

    def __init__(
        self,
        *,
        collection_name: str = "default",
        dimension: int = 1536,
        metric: str = "cosine",
        namespace: str | None = None,
        persist_directory: str | None = None,
        host: str | None = None,
        port: int | None = None,
        **settings: Any,
    ) -> None:
        super().__init__(
            collection_name=collection_name,
            dimension=dimension,
            metric=metric,
            namespace=namespace,
            persist_directory=persist_directory,
            host=host,
            port=port,
            **settings,
        )
        self.persist_directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIRECTORY"
        )
        self.host = host or os.getenv("CHROMA_HOST")
        self.port = port or int(os.getenv("CHROMA_PORT", "8000"))
        self._client: Any | None = None
        self._collections_cache: dict[str, Any] = {}

    @classmethod
    def available(cls) -> bool:
        return HAS_CHROMADB

    def connect(self) -> bool:
        if HAS_CHROMADB:
            try:
                if self.host:
                    self._client = chromadb.HttpClient(host=self.host, port=self.port)
                else:
                    self._client = chromadb.PersistentClient(
                        path=self.persist_directory or "./chroma"
                    )
                self._mode = "remote"
            except Exception as exc:
                logger.warning(
                    "ChromaDB connection failed, using memory fallback: %s", exc
                )
                self._client = None
                self._mode = "memory"
        self._connected = True
        return True

    def close(self) -> None:
        self._client = None
        self._collections_cache.clear()
        self._connected = False

    def _get_collection(self, collection_name: str, create: bool = True) -> Any | None:
        collection_name = self._collection_name(collection_name)
        if not self._client:
            return None
        if collection_name in self._collections_cache:
            return self._collections_cache[collection_name]
        try:
            collection = (
                self._client.get_collection(collection_name)
                if not create
                else self._client.get_or_create_collection(collection_name)
            )
            self._collections_cache[collection_name] = collection
            return collection
        except Exception:
            if create:
                collection = self._client.get_or_create_collection(collection_name)
                self._collections_cache[collection_name] = collection
                return collection
            return None

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
        if self._client:
            self._get_collection(self._collection_name(collection_name), create=True)
        return created

    def delete_collection(self, collection_name: str | None = None) -> bool:
        collection_name = self._collection_name(collection_name)
        deleted = self._memory_delete_collection(collection_name)
        if self._client:
            with contextlib.suppress(Exception):
                self._client.delete_collection(collection_name)
            self._collections_cache.pop(collection_name, None)
        return deleted

    def list_collections(self) -> list[str]:
        collections = set(self._memory_list_collections())
        if self._client:
            try:
                for collection in self._client.list_collections():
                    collections.add(getattr(collection, "name", collection))
            except Exception:
                pass
        return sorted(collections)

    def upsert(
        self,
        records: Sequence[Mapping[str, Any] | VectorRecord],
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        collection_name = self._collection_name(collection_name)
        if self._client:
            collection = self._get_collection(collection_name, create=True)
            if collection is not None:
                coerced = self._coerce_records(records, namespace=namespace)
                ids = [record.id for record in coerced]
                vectors = [record.vector for record in coerced]
                metadatas = [record.metadata for record in coerced]
                documents = [record.text or "" for record in coerced]
                try:
                    collection.upsert(
                        ids=ids,
                        embeddings=vectors,
                        metadatas=metadatas,
                        documents=documents,
                    )
                    return self._memory_upsert(
                        records, collection_name=collection_name, namespace=namespace
                    )
                except Exception as exc:
                    logger.warning("ChromaDB upsert failed, using memory only: %s", exc)
        return self._memory_upsert(
            records, collection_name=collection_name, namespace=namespace
        )

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
        if self._client:
            collection = self._get_collection(collection_name, create=False)
            if collection is not None:
                try:
                    response = collection.query(
                        query_embeddings=[list(query_vector)],
                        n_results=top_k,
                        where=dict(filter or {}),
                        include=["embeddings", "metadatas", "documents", "distances"],
                    )
                    results: list[VectorSearchResult] = []
                    ids = response.get("ids", [[]])[0]
                    metadatas = response.get("metadatas", [[]])[0]
                    embeddings = response.get("embeddings", [[]])[0]
                    documents = response.get("documents", [[]])[0]
                    distances = response.get("distances", [[]])[0]
                    for index, record_id in enumerate(ids):
                        metadata = (
                            dict(metadatas[index] or {}) if include_metadata else {}
                        )
                        distance = distances[index] if index < len(distances) else None
                        score = 1.0 / (1.0 + distance) if distance is not None else 0.0
                        if namespace and metadata.get("_namespace") != namespace:
                            continue
                        results.append(
                            VectorSearchResult(
                                id=str(record_id),
                                score=score,
                                vector=embeddings[index] if include_vectors else None,
                                metadata=metadata,
                                distance=distance,
                                text=(
                                    documents[index] if index < len(documents) else None
                                ),
                                namespace=metadata.get("_namespace"),
                            )
                        )
                    if results:
                        return results
                except Exception as exc:
                    logger.warning("ChromaDB search failed, using memory only: %s", exc)
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
        deleted = self._memory_delete(
            collection_name=collection_name,
            ids=ids,
            namespace=namespace,
            filter=filter,
            delete_all=delete_all,
        )
        if self._client:
            collection = self._get_collection(collection_name, create=False)
            if collection is not None:
                with contextlib.suppress(Exception):
                    if delete_all:
                        collection.delete(where={})
                    elif ids:
                        collection.delete(ids=list(ids))
                    elif filter:
                        collection.delete(where=dict(filter))
        return deleted

    def count(
        self,
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        if self._client:
            collection = self._get_collection(
                self._collection_name(collection_name), create=False
            )
            if collection is not None:
                try:
                    return int(collection.count())
                except Exception:
                    pass
        return self._memory_count(collection_name=collection_name, namespace=namespace)

    def stats(self) -> dict[str, Any]:
        stats = self._memory_stats()
        stats.update(
            {"available": self.available(), "persist_directory": self.persist_directory}
        )
        return stats
