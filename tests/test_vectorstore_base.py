from __future__ import annotations

import math
from typing import Any

import pytest

from agentic_brain.vectorstore.base import (
    VectorRecord,
    VectorStore,
    VectorStoreBackend,
)


class DummyVectorStore(VectorStore):
    backend_name = "dummy"

    def connect(self) -> bool:
        self._connected = True
        return True

    def close(self) -> None:
        self._connected = False

    def create_collection(
        self, collection_name=None, *, dimension=None, metric=None, **kwargs
    ):
        return self._memory_create_collection(
            collection_name, dimension=dimension, metric=metric
        )

    def delete_collection(self, collection_name=None):
        return self._memory_delete_collection(collection_name)

    def list_collections(self):
        return self._memory_list_collections()

    def upsert(self, records, *, collection_name=None, namespace=None):
        return self._memory_upsert(
            records, collection_name=collection_name, namespace=namespace
        )

    def search(
        self,
        query_vector,
        *,
        collection_name=None,
        top_k=5,
        namespace=None,
        filter=None,
        include_vectors=False,
        include_metadata=True,
    ):
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
        collection_name=None,
        ids=None,
        namespace=None,
        filter=None,
        delete_all=False,
    ):
        return self._memory_delete(
            collection_name=collection_name,
            ids=ids,
            namespace=namespace,
            filter=filter,
            delete_all=delete_all,
        )

    def count(self, *, collection_name=None, namespace=None):
        return self._memory_count(collection_name=collection_name, namespace=namespace)

    def stats(self) -> dict[str, Any]:
        return self._memory_stats()


def test_backend_aliases_normalize():
    assert VectorStoreBackend.normalize("chroma") is VectorStoreBackend.CHROMADB
    assert VectorStoreBackend.normalize("chromadb") is VectorStoreBackend.CHROMADB
    assert VectorStoreBackend.normalize("qdrant") is VectorStoreBackend.QDRANT
    assert VectorStoreBackend.normalize("weaviate") is VectorStoreBackend.WEAVIATE
    assert VectorStoreBackend.normalize("pinecone") is VectorStoreBackend.PINECONE


def test_vector_record_round_trip():
    record = VectorRecord.from_mapping(
        {"id": "a", "vector": [1, 2, 3], "metadata": {"text": "hello"}}
    )
    assert record.id == "a"
    assert record.text == "hello"
    assert record.as_dict()["vector"] == [1.0, 2.0, 3.0]


@pytest.mark.parametrize(
    ("metric", "expected_best"),
    [
        ("cosine", "high"),
        ("dotproduct", "high"),
        ("euclidean", "high"),
    ],
)
def test_memory_scoring_orders_results(metric: str, expected_best: str):
    store = DummyVectorStore(collection_name="docs", dimension=3, metric=metric)
    store.connect()
    store.create_collection()
    store.upsert(
        [
            {"id": "high", "vector": [1, 0, 0], "metadata": {"kind": "high"}},
            {"id": "medium", "vector": [0.5, 0, 0], "metadata": {"kind": "medium"}},
            {"id": "low", "vector": [0, 1, 0], "metadata": {"kind": "low"}},
        ]
    )
    result = store.search([1, 0, 0], top_k=3)
    assert result[0].id == expected_best
    assert len(result) == 3


def test_filter_matching_supports_comparators():
    store = DummyVectorStore(collection_name="docs", dimension=3)
    store.connect()
    store.create_collection()
    store.upsert(
        [
            {
                "id": "a",
                "vector": [1, 0, 0],
                "metadata": {"priority": 1, "active": True, "kind": "note"},
            },
            {
                "id": "b",
                "vector": [0, 1, 0],
                "metadata": {"priority": 3, "active": False, "kind": "note"},
            },
        ],
        namespace="team-a",
    )
    matches = store.search(
        [1, 0, 0],
        namespace="team-a",
        filter={"priority": {"$gte": 2}, "active": False},
    )
    assert [item.id for item in matches] == ["b"]


def test_dummy_store_memory_round_trip():
    store = DummyVectorStore(collection_name="docs", dimension=3)
    assert store.connect() is True
    assert store.create_collection("docs") is True
    assert (
        store.upsert([{"id": "x", "vector": [1, 0, 0], "metadata": {"tag": "one"}}])
        == 1
    )
    assert store.count() == 1
    assert store.search([1, 0, 0])[0].id == "x"
    assert store.delete(ids=["x"]) == 1
    assert store.count() == 0
    assert store.delete_collection("docs") is True
    assert store.list_collections() == []


def test_dummy_store_stats_and_health():
    store = DummyVectorStore(collection_name="docs", dimension=3)
    store.connect()
    store.create_collection()
    store.upsert([{"id": "x", "vector": [1, 0, 0]}])
    stats = store.stats()
    health = store.health()
    assert stats["total_records"] == 1
    assert stats["backend"] == "dummy"
    assert health["status"] == "ok"
    assert health["backend"] == "dummy"
