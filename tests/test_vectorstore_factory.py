# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import pytest

from agentic_brain.vectorstore import (
    ChromaDBVectorStore,
    PineconeVectorStore,
    QdrantVectorStore,
    VectorStoreBackend,
    WeaviateVectorStore,
    available_backends,
    create_vector_store,
)


def test_available_backends_reports_all_keys():
    backends = available_backends()
    assert set(backends) == {"chromadb", "qdrant", "weaviate", "pinecone"}


@pytest.mark.parametrize(
    ("backend", "expected_type"),
    [
        ("chroma", ChromaDBVectorStore),
        ("chromadb", ChromaDBVectorStore),
        ("qdrant", QdrantVectorStore),
        ("weaviate", WeaviateVectorStore),
        ("pinecone", PineconeVectorStore),
    ],
)
def test_factory_returns_expected_backend(backend, expected_type):
    store = create_vector_store(backend, collection_name="docs", dimension=3)
    assert isinstance(store, expected_type)
    assert store.config.collection_name == "docs"
    assert store.config.dimension == 3


def test_factory_accepts_enum_values():
    store = create_vector_store(VectorStoreBackend.QDRANT, collection_name="docs")
    assert isinstance(store, QdrantVectorStore)


def test_factory_rejects_unknown_backend():
    with pytest.raises(ValueError):
        create_vector_store("unknown")


def test_factory_preserves_backend_specific_kwargs():
    store = create_vector_store(
        "pinecone",
        collection_name="docs",
        dimension=8,
        api_key="token",
        environment="dev",
        cloud="gcp",
        region="us-central1",
    )
    assert store.api_key == "token"
    assert store.environment == "dev"
    assert store.cloud == "gcp"
    assert store.region == "us-central1"
