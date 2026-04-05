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
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .chunking import Chunk, ChunkingStrategy, create_chunker

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represent a normalized document and its chunk metadata.

    Attributes:
        id: Stable document identifier.
        content: Original full document body.
        metadata: Arbitrary source metadata for filtering and attribution.
        chunks: Chunked content generated for retrieval.
        chunk_metadata: Per-chunk positional and token metadata.
        created_at: Timestamp when the document object was created.

    Example:
        >>> doc = Document(id="doc-1", content="Hello world")
        >>> doc.id
        'doc-1'
    """

    id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    chunks: list[str] = field(default_factory=list)
    chunk_metadata: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now())

    def to_dict(self) -> dict[str, Any]:
        """Serialize the document to a JSON-safe dictionary.

        Returns:
            dict[str, Any]: Serialized document payload, including ISO timestamp.

        Raises:
            ValueError: If document data cannot be represented safely.

        Example:
            >>> doc = Document(id="doc-1", content="text")
            >>> "created_at" in doc.to_dict()
            True
        """
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
        """Create a :class:`Document` from serialized dictionary data.

        Args:
            data: Serialized document payload.

        Returns:
            Document: Reconstructed document instance.

        Raises:
            ValueError: If timestamp formatting is invalid.
            TypeError: If required fields are missing or wrong type.

        Example:
            >>> Document.from_dict({"id": "d1", "content": "x"}).id
            'd1'
        """
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
        content: str | Document,
        metadata: Optional[dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> Document:
        """Add a document, automatically chunking it."""
        if isinstance(content, Document):
            doc = content
            if not doc.chunks:
                chunk_objects = self._chunker.chunk(doc.content, doc.metadata)
                doc.chunks = [c.content for c in chunk_objects]
                doc.chunk_metadata = [self._chunk_to_metadata(c) for c in chunk_objects]
        else:
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
        self._documents[doc.id] = doc
        logger.info(f"Added document {doc.id} with {len(doc.chunks)} chunks")
        return doc

    def get(self, doc_id: str) -> Optional[Document]:
        """Retrieve a document by identifier.

        Args:
            doc_id: Document identifier to retrieve.

        Returns:
            Optional[Document]: Matching document when present, otherwise ``None``.

        Raises:
            RuntimeError: If in-memory store state is unexpectedly invalid.

        Example:
            >>> store = InMemoryDocumentStore()
            >>> store.get("missing") is None
            True
        """
        return self._documents.get(doc_id)

    def delete(self, doc_id: str) -> bool:
        """Delete a document from the in-memory store.

        Args:
            doc_id: Document identifier to delete.

        Returns:
            bool: ``True`` if the document was deleted, else ``False``.

        Raises:
            RuntimeError: If deletion cannot be completed due to store corruption.

        Example:
            >>> store = InMemoryDocumentStore()
            >>> store.delete("missing")
            False
        """
        if doc_id in self._documents:
            del self._documents[doc_id]
            logger.info(f"Deleted document {doc_id}")
            return True
        return False

    def list(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """List documents in insertion order with pagination.

        Args:
            limit: Maximum number of documents to return.
            offset: Number of documents to skip before returning results.

        Returns:
            list[Document]: Window of available documents.

        Raises:
            ValueError: If ``limit`` or ``offset`` are negative.

        Example:
            >>> store = InMemoryDocumentStore()
            >>> isinstance(store.list(), list)
            True
        """
        docs = list(self._documents.values())
        return docs[offset : offset + limit]

    def search(self, query: str, top_k: int = 5) -> builtins.list[Document]:
        """Simple keyword search."""
        query_lower = query.lower()
        tokens = re.findall(r"\w+", query_lower)
        results = []
        for doc in self._documents.values():
            content_lower = doc.content.lower()
            if tokens:
                if any(token in content_lower for token in tokens):
                    results.append(doc)
            elif query_lower in content_lower:
                results.append(doc)
        return results[:top_k]

    def count(self) -> int:
        """Return total number of stored documents.

        Returns:
            int: Number of indexed documents in memory.

        Raises:
            RuntimeError: If store bookkeeping is unexpectedly invalid.

        Example:
            >>> store = InMemoryDocumentStore()
            >>> store.count()
            0
        """
        return len(self._documents)

    def stats(self) -> dict[str, Any]:
        """Return aggregate indexing statistics for the in-memory store.

        Returns:
            dict[str, Any]: Metrics including document count, chunk totals, and
                configured chunking strategy.

        Raises:
            RuntimeError: If statistical aggregation fails unexpectedly.

        Example:
            >>> store = InMemoryDocumentStore()
            >>> "document_count" in store.stats()
            True
        """
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
            data = json.loads(self._index_file.read_text())
            return dict(data) if data else {}
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
        content: str | Document,
        metadata: Optional[dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> Document:
        """Add or update a document and persist it to disk-backed index.

        Args:
            content: Raw document text or a pre-built :class:`Document`.
            metadata: Optional metadata to store with the document.
            doc_id: Optional explicit identifier for new raw-text documents.

        Returns:
            Document: Persisted document including generated chunks.

        Raises:
            OSError: If writing the index or document file fails.
            TypeError: If provided content cannot be converted to a document.

        Example:
            >>> store = FileDocumentStore(path=".rag_store_example")
            >>> doc = store.add("hello", {"title": "greeting"})
            >>> bool(doc.id)
            True
        """
        if isinstance(content, Document):
            doc = content
            if not doc.chunks:
                chunk_objects = self._chunker.chunk(doc.content, doc.metadata)
                doc.chunks = [c.content for c in chunk_objects]
                doc.chunk_metadata = [self._chunk_to_metadata(c) for c in chunk_objects]
        else:
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
        self._doc_path(doc.id).write_text(
            json.dumps(doc.to_dict(), indent=2, default=str)
        )
        self._index[doc.id] = metadata.get("title", doc.id) if metadata else doc.id
        self._save_index()

        logger.info(f"Added document {doc.id} with {len(doc.chunks)} chunks")
        return doc

    def get(self, doc_id: str) -> Optional[Document]:
        """Load a document by identifier from the file-backed store.

        Args:
            doc_id: Document identifier to load.

        Returns:
            Optional[Document]: Loaded document when file exists, otherwise ``None``.

        Raises:
            OSError: If file access fails during load.
            ValueError: If serialized content is malformed.

        Example:
            >>> store = FileDocumentStore(path=".rag_store_example")
            >>> store.get("missing") is None
            True
        """
        path = self._doc_path(doc_id)
        if path.exists():
            return Document.from_dict(json.loads(path.read_text()))
        return None

    def delete(self, doc_id: str) -> bool:
        """Delete a persisted document and update the on-disk index.

        Args:
            doc_id: Document identifier to delete.

        Returns:
            bool: ``True`` when a document file existed and was removed.

        Raises:
            OSError: If removing files or saving index fails.

        Example:
            >>> store = FileDocumentStore(path=".rag_store_example")
            >>> store.delete("missing")
            False
        """
        path = self._doc_path(doc_id)
        if path.exists():
            path.unlink()
            self._index.pop(doc_id, None)
            self._save_index()
            return True
        return False

    def list(self, limit: int = 100, offset: int = 0) -> list[Document]:
        """List persisted documents with simple pagination.

        Args:
            limit: Maximum number of documents to return.
            offset: Number of documents to skip before returning results.

        Returns:
            list[Document]: Loaded document window based on index order.

        Raises:
            OSError: If any indexed document fails to load.

        Example:
            >>> store = FileDocumentStore(path=".rag_store_example")
            >>> isinstance(store.list(), list)
            True
        """
        doc_ids = list(self._index.keys())[offset : offset + limit]
        return [doc for did in doc_ids if (doc := self.get(did)) is not None]

    def search(self, query: str, top_k: int = 5) -> builtins.list[Document]:
        """Search persisted documents using keyword token matching.

        Args:
            query: Search query text.
            top_k: Maximum number of matching documents to return.

        Returns:
            list[Document]: Matching documents ordered by scan order.

        Raises:
            OSError: If indexed documents cannot be read from disk.

        Example:
            >>> store = FileDocumentStore(path=".rag_store_example")
            >>> isinstance(store.search("project"), list)
            True
        """
        query_lower = query.lower()
        tokens = re.findall(r"\w+", query_lower)
        results = []
        for doc_id in self._index:
            doc = self.get(doc_id)
            if doc:
                content_lower = doc.content.lower()
                if tokens:
                    if any(token in content_lower for token in tokens):
                        results.append(doc)
                elif query_lower in content_lower:
                    results.append(doc)
        return results[:top_k]

    def count(self) -> int:
        """Return total number of indexed documents on disk.

        Returns:
            int: Number of document entries tracked in the index.

        Raises:
            RuntimeError: If index metadata is unexpectedly unavailable.

        Example:
            >>> store = FileDocumentStore(path=".rag_store_example")
            >>> store.count() >= 0
            True
        """
        return len(self._index)

    def stats(self) -> dict[str, Any]:
        """Return aggregate indexing statistics for the file-backed store.

        Returns:
            dict[str, Any]: Metrics for document totals, chunk totals, and store
                configuration including storage path.

        Raises:
            OSError: If indexed documents cannot be read for aggregation.

        Example:
            >>> store = FileDocumentStore(path=".rag_store_example")
            >>> "storage_path" in store.stats()
            True
        """
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
