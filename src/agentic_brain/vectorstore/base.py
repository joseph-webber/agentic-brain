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

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, ClassVar, Mapping, Sequence


class VectorStoreBackend(str, Enum):
    """Supported vector store backends."""

    CHROMADB = "chromadb"
    QDRANT = "qdrant"
    WEAVIATE = "weaviate"
    PINECONE = "pinecone"

    @classmethod
    def normalize(cls, value: str | VectorStoreBackend) -> VectorStoreBackend:
        """Normalize backend aliases to enum members."""
        if isinstance(value, cls):
            return value

        alias = value.strip().lower().replace("_", "").replace("-", "")
        if alias in {"chroma", "chromadb"}:
            return cls.CHROMADB
        if alias == "qdrant":
            return cls.QDRANT
        if alias == "weaviate":
            return cls.WEAVIATE
        if alias == "pinecone":
            return cls.PINECONE
        raise ValueError(f"Unknown vector store backend: {value}")


@dataclass(slots=True)
class VectorRecord:
    """A record stored in a vector store."""

    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    text: str | None = None
    namespace: str | None = None

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any] | VectorRecord,
        namespace: str | None = None,
    ) -> VectorRecord:
        """Create a record from a mapping or another record."""
        if isinstance(value, cls):
            if namespace is not None and value.namespace != namespace:
                return cls(
                    id=value.id,
                    vector=list(value.vector),
                    metadata=dict(value.metadata),
                    text=value.text,
                    namespace=namespace,
                )
            return value

        if "id" not in value:
            raise ValueError("Vector records require an 'id'")

        vector = value.get("vector")
        if vector is None:
            vector = value.get("values")
        if vector is None:
            raise ValueError("Vector records require a 'vector'")

        metadata = dict(value.get("metadata") or {})
        text = value.get("text")
        if text is None:
            text = metadata.get("text")

        return cls(
            id=str(value["id"]),
            vector=[float(component) for component in vector],
            metadata=metadata,
            text=text if text is None or isinstance(text, str) else str(text),
            namespace=namespace or value.get("namespace"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize the record to a backend-friendly mapping."""
        payload: dict[str, Any] = {
            "id": self.id,
            "vector": list(self.vector),
            "metadata": dict(self.metadata),
        }
        if self.text is not None:
            payload["text"] = self.text
        if self.namespace is not None:
            payload["namespace"] = self.namespace
        return payload


@dataclass(slots=True)
class VectorSearchResult:
    """A ranked vector search result."""

    id: str
    score: float
    vector: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    distance: float | None = None
    text: str | None = None
    namespace: str | None = None


@dataclass(slots=True)
class VectorStoreConfig:
    """Common configuration shared by all vector stores."""

    backend: str
    collection_name: str = "default"
    dimension: int = 1536
    metric: str = "cosine"
    namespace: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)


class VectorStore(ABC):
    """Unified vector store interface."""

    backend_name: ClassVar[str] = "base"

    def __init__(
        self,
        *,
        collection_name: str = "default",
        dimension: int = 1536,
        metric: str = "cosine",
        namespace: str | None = None,
        **settings: Any,
    ) -> None:
        self.config = VectorStoreConfig(
            backend=self.backend_name,
            collection_name=collection_name,
            dimension=dimension,
            metric=metric,
            namespace=namespace,
            settings=dict(settings),
        )
        self._connected = False
        self._mode = "memory"
        self._collections: dict[str, dict[str, dict[str, VectorRecord]]] = {}

    @classmethod
    def available(cls) -> bool:
        """Return whether the backend dependency is available."""
        return True

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return self._mode

    def _collection_name(self, collection_name: str | None = None) -> str:
        return collection_name or self.config.collection_name

    def _namespace_name(self, namespace: str | None = None) -> str:
        return namespace or self.config.namespace or "__default__"

    def _validate_vector(self, vector: Sequence[float]) -> None:
        if len(vector) != self.config.dimension:
            raise ValueError(
                f"Expected vector dimension {self.config.dimension}, got {len(vector)}"
            )

    def _coerce_records(
        self,
        records: Sequence[Mapping[str, Any] | VectorRecord],
        namespace: str | None = None,
    ) -> list[VectorRecord]:
        return [
            VectorRecord.from_mapping(record, namespace=namespace) for record in records
        ]

    def _ensure_collection(
        self,
        collection_name: str,
        dimension: int | None = None,
        metric: str | None = None,
    ) -> dict[str, dict[str, VectorRecord]]:
        if collection_name not in self._collections:
            self._collections[collection_name] = {}
        self.config.collection_name = collection_name
        if dimension is not None:
            self.config.dimension = dimension
        if metric is not None:
            self.config.metric = metric
        return self._collections[collection_name]

    def _matches_filter(
        self,
        record: VectorRecord,
        filter_criteria: Mapping[str, Any] | None,
    ) -> bool:
        if not filter_criteria:
            return True

        for key, expected in filter_criteria.items():
            actual = (
                record.namespace
                if key in {"namespace", "_namespace"}
                else record.metadata.get(key)
            )
            if isinstance(expected, Mapping):
                for operator, value in expected.items():
                    if not self._compare(actual, operator, value):
                        return False
            elif actual != expected:
                return False
        return True

    def _compare(self, actual: Any, operator: str, expected: Any) -> bool:
        if operator == "$eq":
            return actual == expected
        if actual is None:
            return False
        if operator == "$gt":
            return actual > expected
        if operator == "$gte":
            return actual >= expected
        if operator == "$lt":
            return actual < expected
        if operator == "$lte":
            return actual <= expected
        return False

    def _score(
        self, query_vector: Sequence[float], vector: Sequence[float]
    ) -> tuple[float, float | None]:
        metric = self.config.metric.lower()
        if metric in {"cosine", "cos"}:
            dot = sum(
                left * right for left, right in zip(query_vector, vector, strict=False)
            )
            left_norm = math.sqrt(
                sum(component * component for component in query_vector)
            )
            right_norm = math.sqrt(sum(component * component for component in vector))
            if not left_norm or not right_norm:
                return 0.0, None
            score = dot / (left_norm * right_norm)
            return score, 1.0 - score

        if metric in {"dot", "dotproduct"}:
            return (
                sum(
                    left * right
                    for left, right in zip(query_vector, vector, strict=False)
                ),
                None,
            )

        distance = math.sqrt(
            sum(
                (left - right) ** 2
                for left, right in zip(query_vector, vector, strict=False)
            )
        )
        return 1.0 / (1.0 + distance), distance

    def _memory_create_collection(
        self,
        collection_name: str | None = None,
        dimension: int | None = None,
        metric: str | None = None,
    ) -> bool:
        collection_name = self._collection_name(collection_name)
        existed = collection_name in self._collections
        self._ensure_collection(collection_name, dimension=dimension, metric=metric)
        return not existed

    def _memory_delete_collection(self, collection_name: str | None = None) -> bool:
        collection_name = self._collection_name(collection_name)
        if collection_name not in self._collections:
            return False
        del self._collections[collection_name]
        return True

    def _memory_list_collections(self) -> list[str]:
        return sorted(self._collections)

    def _memory_upsert(
        self,
        records: Sequence[Mapping[str, Any] | VectorRecord],
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        collection_name = self._collection_name(collection_name)
        bucket = self._ensure_collection(collection_name)

        count = 0
        for record in self._coerce_records(records, namespace=namespace):
            namespace_name = record.namespace or self._namespace_name(namespace)
            namespace_bucket = bucket.setdefault(namespace_name, {})
            record.namespace = namespace_name
            self._validate_vector(record.vector)
            namespace_bucket[record.id] = record
            count += 1
        return count

    def _memory_search(
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
        if collection_name not in self._collections:
            return []

        self._validate_vector(query_vector)

        namespaces = (
            [self._namespace_name(namespace)]
            if namespace
            else list(self._collections[collection_name])
        )
        candidates: list[VectorRecord] = []
        for namespace_name in namespaces:
            candidates.extend(
                self._collections[collection_name].get(namespace_name, {}).values()
            )

        results: list[VectorSearchResult] = []
        for record in candidates:
            if not self._matches_filter(record, filter):
                continue
            score, distance = self._score(query_vector, record.vector)
            results.append(
                VectorSearchResult(
                    id=record.id,
                    score=score,
                    vector=list(record.vector) if include_vectors else None,
                    metadata=dict(record.metadata) if include_metadata else {},
                    distance=distance,
                    text=record.text,
                    namespace=record.namespace,
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def _memory_delete(
        self,
        *,
        collection_name: str | None = None,
        ids: Sequence[str] | None = None,
        namespace: str | None = None,
        filter: Mapping[str, Any] | None = None,
        delete_all: bool = False,
    ) -> int:
        collection_name = self._collection_name(collection_name)
        if collection_name not in self._collections:
            return 0

        if delete_all:
            deleted = self._memory_count(
                collection_name=collection_name, namespace=namespace
            )
            self._collections[collection_name] = {}
            return deleted

        deleted = 0
        namespaces = (
            [self._namespace_name(namespace)]
            if namespace
            else list(self._collections[collection_name])
        )
        for namespace_name in namespaces:
            namespace_bucket = self._collections[collection_name].get(
                namespace_name, {}
            )
            for record_id, record in list(namespace_bucket.items()):
                if ids and record_id not in ids:
                    continue
                if filter and not self._matches_filter(record, filter):
                    continue
                del namespace_bucket[record_id]
                deleted += 1
        return deleted

    def _memory_count(
        self,
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        collection_name = self._collection_name(collection_name)
        if collection_name not in self._collections:
            return 0
        if namespace:
            return len(
                self._collections[collection_name].get(
                    self._namespace_name(namespace), {}
                )
            )
        return sum(
            len(bucket) for bucket in self._collections[collection_name].values()
        )

    def _memory_stats(self) -> dict[str, Any]:
        return {
            "backend": self.backend_name,
            "mode": self.mode,
            "connected": self.connected,
            "collection_name": self.config.collection_name,
            "collections": self._memory_list_collections(),
            "dimension": self.config.dimension,
            "metric": self.config.metric,
            "namespace": self.config.namespace,
            "total_records": self._memory_count(),
            "settings": dict(self.config.settings),
        }

    def _memory_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "backend": self.backend_name,
            "connected": self.connected,
            "mode": self.mode,
        }

    def _result_from_mapping(
        self, value: Mapping[str, Any] | VectorSearchResult
    ) -> VectorSearchResult:
        if isinstance(value, VectorSearchResult):
            return value
        return VectorSearchResult(
            id=str(value["id"]),
            score=float(value["score"]),
            vector=(
                [float(component) for component in value.get("vector", [])]
                if value.get("vector") is not None
                else None
            ),
            metadata=dict(value.get("metadata") or {}),
            distance=value.get("distance"),
            text=value.get("text"),
            namespace=value.get("namespace"),
        )

    @abstractmethod
    def connect(self) -> bool:
        """Connect to the backend."""

    @abstractmethod
    def close(self) -> None:
        """Close the backend connection."""

    @abstractmethod
    def create_collection(
        self,
        collection_name: str | None = None,
        *,
        dimension: int | None = None,
        metric: str | None = None,
        **kwargs: Any,
    ) -> bool:
        """Create a collection."""

    @abstractmethod
    def delete_collection(self, collection_name: str | None = None) -> bool:
        """Delete a collection."""

    @abstractmethod
    def list_collections(self) -> list[str]:
        """List available collections."""

    @abstractmethod
    def upsert(
        self,
        records: Sequence[Mapping[str, Any] | VectorRecord],
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        """Store records."""

    @abstractmethod
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
        """Search records."""

    @abstractmethod
    def delete(
        self,
        *,
        collection_name: str | None = None,
        ids: Sequence[str] | None = None,
        namespace: str | None = None,
        filter: Mapping[str, Any] | None = None,
        delete_all: bool = False,
    ) -> int:
        """Delete records."""

    @abstractmethod
    def count(
        self,
        *,
        collection_name: str | None = None,
        namespace: str | None = None,
    ) -> int:
        """Count records."""

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        """Return store statistics."""

    def health(self) -> dict[str, Any]:
        """Return a concise health summary."""
        return self._memory_health()
