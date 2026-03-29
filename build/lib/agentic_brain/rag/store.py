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

"""Document store for RAG - manages document ingestion and retrieval."""

import builtins
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .chunking import Chunk, ChunkingStrategy, create_chunker

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """A document in the store."""

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[str] = field(default_factory=list)
    chunk_metadata: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "chunks": self.chunks,
            "chunk_metadata": self.chunk_metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Document":
        data = data.copy()
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class DocumentStore(ABC):
    """Abstract base class for document stores."""

    @abstractmethod
    def add(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> Document:
        """Add a document to the store."""
        pass

    @abstractmethod
    def get(self, doc_id: str) -> Optional[Document]:
        """Get a document by ID."""
        pass

    @abstractmethod
    def delete(self, doc_id: str) -> bool:
        """Delete a document."""
        pass

    @abstractmethod
    def list(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """List documents."""
        pass

    @abstractmethod
    def search(self, query: str, top_k: int = 5) -> builtins.list[Document]:
        """Search documents."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Count total documents."""
        pass

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        """Get store statistics."""
        pass


class InMemoryDocumentStore(DocumentStore):
    """In-memory document store for development and testing."""

    def __init__(
        self,
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        self._documents: dict[str, Document] = {}
        self._chunker = create_chunker(
            chunking_strategy, chunk_size=chunk_size, overlap=chunk_overlap
        )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._strategy = chunking_strategy

    def _generate_id(self, content: str) -> str:
        """Generate a document ID from content hash."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _chunk_to_metadata(self, chunk: Chunk) -> dict[str, Any]:
        """Convert Chunk object to metadata dict."""
        return {
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "chunk_index": chunk.chunk_index,
            "token_count": chunk.token_count,
            "metadata": chunk.metadata,
        }

    def add(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> Document:
        """Add a document, automatically chunking it."""
        if doc_id is None:
            doc_id = self._generate_id(content)

        # Chunk the document
        chunk_objects = self._chunker.chunk(content, metadata)
        chunks = [c.content for c in chunk_objects]
        chunk_metadata = [self._chunk_to_metadata(c) for c in chunk_objects]

        doc = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {},
            chunks=chunks,
            chunk_metadata=chunk_metadata,
        )
        self._documents[doc_id] = doc
        logger.info(f"Added document {doc_id} with {len(chunks)} chunks")
        return doc

    def get(self, doc_id: str) -> Optional[Document]:
        return self._documents.get(doc_id)

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._documents:
            del self._documents[doc_id]
            logger.info(f"Deleted document {doc_id}")
            return True
        return False

    def list(self, limit: int = 100, offset: int = 0) -> list[Document]:
        docs = list(self._documents.values())
        return docs[offset : offset + limit]

    def search(self, query: str, top_k: int = 5) -> builtins.list[Document]:
        """Simple keyword search."""
        query_lower = query.lower()
        results = []
        for doc in self._documents.values():
            if query_lower in doc.content.lower():
                results.append(doc)
        return results[:top_k]

    def count(self) -> int:
        return len(self._documents)

    def stats(self) -> dict[str, Any]:
        total_chunks = sum(len(d.chunks) for d in self._documents.values())
        total_chars = sum(len(d.content) for d in self._documents.values())
        return {
            "document_count": len(self._documents),
            "total_chunks": total_chunks,
            "total_characters": total_chars,
            "avg_chunks_per_doc": total_chunks / max(1, len(self._documents)),
            "chunking_strategy": self._strategy.value,
            "chunk_size": self._chunk_size,
            "chunk_overlap": self._chunk_overlap,
        }

    def clear(self) -> int:
        """Clear all documents. Returns count deleted."""
        count = len(self._documents)
        self._documents.clear()
        return count


class FileDocumentStore(DocumentStore):
    """File-based persistent document store."""

    def __init__(
        self,
        path: str = ".rag_store",
        chunking_strategy: ChunkingStrategy = ChunkingStrategy.RECURSIVE,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        self._path = Path(path)
        self._path.mkdir(parents=True, exist_ok=True)
        self._index_file = self._path / "index.json"
        self._chunker = create_chunker(
            chunking_strategy, chunk_size=chunk_size, overlap=chunk_overlap
        )
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._strategy = chunking_strategy
        self._index: dict[str, str] = self._load_index()

    def _load_index(self) -> dict[str, str]:
        if self._index_file.exists():
            return json.loads(self._index_file.read_text())
        return {}

    def _save_index(self):
        self._index_file.write_text(json.dumps(self._index, indent=2))

    def _doc_path(self, doc_id: str) -> Path:
        return self._path / f"{doc_id}.json"

    def _generate_id(self, content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _chunk_to_metadata(self, chunk: Chunk) -> dict[str, Any]:
        """Convert Chunk object to metadata dict."""
        return {
            "start_char": chunk.start_char,
            "end_char": chunk.end_char,
            "chunk_index": chunk.chunk_index,
            "token_count": chunk.token_count,
            "metadata": chunk.metadata,
        }

    def add(
        self,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> Document:
        if doc_id is None:
            doc_id = self._generate_id(content)

        chunk_objects = self._chunker.chunk(content, metadata)
        chunks = [c.content for c in chunk_objects]
        chunk_metadata = [self._chunk_to_metadata(c) for c in chunk_objects]

        doc = Document(
            id=doc_id,
            content=content,
            metadata=metadata or {},
            chunks=chunks,
            chunk_metadata=chunk_metadata,
        )

        # Save to file
        self._doc_path(doc_id).write_text(
            json.dumps(doc.to_dict(), indent=2, default=str)
        )
        self._index[doc_id] = metadata.get("title", doc_id) if metadata else doc_id
        self._save_index()

        logger.info(f"Added document {doc_id} with {len(chunks)} chunks")
        return doc

    def get(self, doc_id: str) -> Optional[Document]:
        path = self._doc_path(doc_id)
        if path.exists():
            return Document.from_dict(json.loads(path.read_text()))
        return None

    def delete(self, doc_id: str) -> bool:
        path = self._doc_path(doc_id)
        if path.exists():
            path.unlink()
            self._index.pop(doc_id, None)
            self._save_index()
            return True
        return False

    def list(self, limit: int = 100, offset: int = 0) -> list[Document]:
        doc_ids = list(self._index.keys())[offset : offset + limit]
        return [self.get(did) for did in doc_ids if self.get(did)]

    def search(self, query: str, top_k: int = 5) -> builtins.list[Document]:
        query_lower = query.lower()
        results = []
        for doc_id in self._index:
            doc = self.get(doc_id)
            if doc and query_lower in doc.content.lower():
                results.append(doc)
        return results[:top_k]

    def count(self) -> int:
        return len(self._index)

    def stats(self) -> dict[str, Any]:
        docs = self.list(limit=10000)
        total_chunks = sum(len(d.chunks) for d in docs)
        total_chars = sum(len(d.content) for d in docs)
        return {
            "document_count": len(docs),
            "total_chunks": total_chunks,
            "total_characters": total_chars,
            "avg_chunks_per_doc": total_chunks / max(1, len(docs)),
            "storage_path": str(self._path),
            "chunking_strategy": self._strategy.value,
            "chunk_size": self._chunk_size,
        }

    def clear(self) -> int:
        """Clear all documents. Returns count deleted."""
        count = len(self._index)
        for doc_id in list(self._index.keys()):
            self.delete(doc_id)
        return count
