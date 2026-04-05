from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentic_brain.vectorstore.chromadb import ChromaDBVectorStore
from agentic_brain.vectorstore.pinecone import PineconeVectorStore
from agentic_brain.vectorstore.qdrant import QdrantVectorStore
from agentic_brain.vectorstore.weaviate import WeaviateVectorStore

BACKENDS = [
    ("chromadb", ChromaDBVectorStore),
    ("qdrant", QdrantVectorStore),
    ("weaviate", WeaviateVectorStore),
    ("pinecone", PineconeVectorStore),
]


class FakeLegacyAdapter:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.connected = False
        self.collections: dict[str, dict[str, list[dict[str, object]]]] = {}
        self.calls: list[tuple[str, tuple, dict]] = []

    def connect(self):
        self.connected = True
        self.calls.append(("connect", (), {}))
        return True

    def disconnect(self):
        self.connected = False
        self.calls.append(("disconnect", (), {}))

    def create_collection(self, name, **kwargs):
        self.collections.setdefault(name, {})
        self.calls.append(("create_collection", (name,), kwargs))
        return True

    def delete_collection(self, name):
        self.collections.pop(name, None)
        self.calls.append(("delete_collection", (name,), {}))
        return True

    def list_collections(self):
        self.calls.append(("list_collections", (), {}))
        return sorted(self.collections)

    def upsert(self, collection_name, vectors, namespace=None):
        bucket = self.collections.setdefault(collection_name, {}).setdefault(namespace or "__default__", [])
        bucket.extend(vectors)
        self.calls.append(("upsert", (collection_name, vectors), {"namespace": namespace}))
        return len(vectors)

    def search(
        self,
        collection_name,
        query_vector,
        top_k=5,
        namespace=None,
        filter=None,
        include_vectors=False,
        include_metadata=True,
    ):
        self.calls.append(
            (
                "search",
                (collection_name, list(query_vector)),
                {
                    "top_k": top_k,
                    "namespace": namespace,
                    "filter": filter,
                    "include_vectors": include_vectors,
                    "include_metadata": include_metadata,
                },
            )
        )
        return [
            SimpleNamespace(
                id="remote-1",
                score=0.99,
                vector=list(query_vector) if include_vectors else None,
                metadata={"source": "remote"} if include_metadata else {},
                distance=0.01,
                text="remote",
                namespace=namespace,
            )
        ][:top_k]

    def delete(self, collection_name, ids=None, namespace=None, filter=None, delete_all=False):
        self.calls.append(
            (
                "delete",
                (collection_name,),
                {
                    "ids": ids,
                    "namespace": namespace,
                    "filter": filter,
                    "delete_all": delete_all,
                },
            )
        )
        return len(ids or []) or 1

    def count(self, collection_name, namespace=None):
        self.calls.append(("count", (collection_name,), {"namespace": namespace}))
        return sum(len(bucket) for bucket in self.collections.get(collection_name, {}).values())

    def collection_exists(self, name):
        return name in self.collections


class FakeChromaCollection:
    def __init__(self, name: str):
        self.name = name
        self.records: dict[str, dict[str, object]] = {}

    def upsert(self, ids, embeddings, metadatas, documents):
        for index, record_id in enumerate(ids):
            self.records[str(record_id)] = {
                "embedding": embeddings[index],
                "metadata": metadatas[index],
                "document": documents[index],
            }

    def query(self, query_embeddings, n_results, where, include):
        items = list(self.records.items())[:n_results]
        return {
            "ids": [[record_id for record_id, _ in items]],
            "metadatas": [[payload["metadata"] for _, payload in items]],
            "embeddings": [[payload["embedding"] for _, payload in items]],
            "documents": [[payload["document"] for _, payload in items]],
            "distances": [[0.1 + index * 0.1 for index, _ in enumerate(items)]],
        }

    def delete(self, ids=None, where=None):
        if ids:
            for record_id in ids:
                self.records.pop(str(record_id), None)
        else:
            self.records.clear()

    def count(self):
        return len(self.records)


class FakeChromaClient:
    def __init__(self):
        self.collections: dict[str, FakeChromaCollection] = {}

    def get_collection(self, name):
        return self.collections[name]

    def get_or_create_collection(self, name):
        self.collections.setdefault(name, FakeChromaCollection(name))
        return self.collections[name]

    def delete_collection(self, name):
        self.collections.pop(name, None)

    def list_collections(self):
        return list(self.collections)


class FakeChromadbModule:
    def __init__(self):
        self.clients = []

    def PersistentClient(self, path=None):
        client = FakeChromaClient()
        self.clients.append(("persistent", path, client))
        return client

    def HttpClient(self, host=None, port=None):
        client = FakeChromaClient()
        self.clients.append(("http", host, port, client))
        return client


@pytest.mark.parametrize("backend_name,backend_cls", BACKENDS)
def test_connect_uses_fallback_when_dependency_missing(backend_name, backend_cls):
    store = backend_cls(collection_name="docs", dimension=3)
    assert store.connect() is True
    assert store.connected is True
    assert store.mode == "memory"
    assert store.stats()["backend"] == backend_name


@pytest.mark.parametrize("backend_name,backend_cls", BACKENDS)
def test_memory_upsert_search_delete_round_trip(backend_name, backend_cls):
    store = backend_cls(collection_name="docs", dimension=3)
    store.connect()
    store.create_collection("docs")
    inserted = store.upsert(
        [{"id": "a", "vector": [1, 0, 0], "metadata": {"kind": backend_name}}]
    )
    assert inserted == 1
    assert store.count(collection_name="docs") == 1
    assert store.search([1, 0, 0], collection_name="docs")[0].id == "a"
    assert store.delete(collection_name="docs", ids=["a"]) == 1
    assert store.count(collection_name="docs") == 0


@pytest.mark.parametrize("backend_name,backend_cls", BACKENDS)
def test_memory_namespace_support(backend_name, backend_cls):
    store = backend_cls(collection_name="docs", dimension=3)
    store.connect()
    store.create_collection("docs")
    store.upsert([{"id": "a", "vector": [1, 0, 0]}], namespace="team-a")
    store.upsert([{"id": "b", "vector": [1, 0, 0]}], namespace="team-b")
    assert store.count(collection_name="docs", namespace="team-a") == 1
    assert store.count(collection_name="docs", namespace="team-b") == 1
    assert store.search([1, 0, 0], collection_name="docs", namespace="team-b")[0].id == "b"


@pytest.mark.parametrize("backend_name,backend_cls", BACKENDS)
def test_collection_management_and_stats(backend_name, backend_cls):
    store = backend_cls(collection_name="docs", dimension=3)
    store.connect()
    assert store.create_collection("docs") is True
    assert "docs" in store.list_collections()
    store.upsert([{"id": "a", "vector": [1, 0, 0]}])
    stats = store.stats()
    assert stats["collection_name"] == "docs"
    assert stats["total_records"] == 1
    assert store.delete_collection("docs") is True
    assert store.list_collections() == []


@pytest.mark.parametrize("backend_name,backend_cls", BACKENDS)
def test_filtering_support(backend_name, backend_cls):
    store = backend_cls(collection_name="docs", dimension=3)
    store.connect()
    store.create_collection("docs")
    store.upsert(
        [
            {"id": "a", "vector": [1, 0, 0], "metadata": {"rank": 1, "active": True}},
            {"id": "b", "vector": [1, 0, 0], "metadata": {"rank": 2, "active": False}},
        ]
    )
    result = store.search([1, 0, 0], filter={"rank": {"$gte": 2}, "active": False})
    assert [item.id for item in result] == ["b"]


@pytest.mark.parametrize("backend_name,backend_cls", BACKENDS)
def test_close_resets_connection(backend_name, backend_cls):
    store = backend_cls(collection_name="docs", dimension=3)
    store.connect()
    store.close()
    assert store.connected is False


@pytest.mark.parametrize("backend_name,backend_cls", BACKENDS)
def test_remote_adapter_delegation(monkeypatch, backend_name, backend_cls):
    store = backend_cls(collection_name="docs", dimension=3)
    module = __import__(store.__module__, fromlist=["dummy"])
    if backend_name == "chromadb":
        fake_module = FakeChromadbModule()
        monkeypatch.setattr(module, "HAS_CHROMADB", True)
        monkeypatch.setattr(module, "chromadb", fake_module)
    else:
        monkeypatch.setattr(module, f"HAS_{backend_name.upper()}", True)
        monkeypatch.setattr(module, f"Legacy{backend_name.title()}Adapter", FakeLegacyAdapter)

    assert store.connect() is True
    assert store.mode == "remote"
    store.create_collection("docs")
    store.upsert([{"id": "a", "vector": [1, 0, 0], "metadata": {"source": "remote"}}])
    search = store.search([1, 0, 0])
    assert search[0].id == ("a" if backend_name == "chromadb" else "remote-1")
    assert store.count() >= 0
    assert store.delete(ids=["a"]) >= 1
    store.close()
