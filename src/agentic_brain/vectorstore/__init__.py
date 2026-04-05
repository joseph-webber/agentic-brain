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

"""Unified vector store interfaces and backend factory."""

from __future__ import annotations

from typing import Any

from .base import (
    VectorRecord,
    VectorSearchResult,
    VectorStore,
    VectorStoreBackend,
    VectorStoreConfig,
)
from .chromadb import HAS_CHROMADB, ChromaDBVectorStore
from .pinecone import HAS_PINECONE, PineconeVectorStore
from .qdrant import HAS_QDRANT, QdrantVectorStore
from .weaviate import HAS_WEAVIATE, WeaviateVectorStore

__all__ = [
    "VectorStore",
    "VectorStoreBackend",
    "VectorStoreConfig",
    "VectorRecord",
    "VectorSearchResult",
    "ChromaDBVectorStore",
    "QdrantVectorStore",
    "WeaviateVectorStore",
    "PineconeVectorStore",
    "create_vector_store",
    "available_backends",
]


_BACKENDS: dict[VectorStoreBackend, type[VectorStore]] = {
    VectorStoreBackend.CHROMADB: ChromaDBVectorStore,
    VectorStoreBackend.QDRANT: QdrantVectorStore,
    VectorStoreBackend.WEAVIATE: WeaviateVectorStore,
    VectorStoreBackend.PINECONE: PineconeVectorStore,
}


def available_backends() -> dict[str, bool]:
    """Return backend availability flags."""
    return {
        "chromadb": HAS_CHROMADB,
        "qdrant": HAS_QDRANT,
        "weaviate": HAS_WEAVIATE,
        "pinecone": HAS_PINECONE,
    }


def create_vector_store(
    backend: str | VectorStoreBackend,
    **kwargs: Any,
) -> VectorStore:
    """Create a vector store implementation by backend name."""
    backend_enum = VectorStoreBackend.normalize(backend)
    return _BACKENDS[backend_enum](**kwargs)
