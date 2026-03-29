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

"""Enhanced Firebase Firestore loader for RAG pipelines.

Features:
- Real-time collection and document sync hooks
- Collection group queries
- Recursive subcollection loading
- Batch save/delete operations
- Local offline cache for read fallback
"""

from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials as firebase_credentials
    from firebase_admin import firestore

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None  # type: ignore[assignment]
    firebase_credentials = None  # type: ignore[assignment]
    firestore = None  # type: ignore[assignment]


@dataclass(slots=True)
class FirestoreSyncEvent:
    """Represents a real-time change emitted by Firestore."""

    collection: str
    document_id: str
    event_type: str
    document: Optional[LoadedDocument]


class FirestoreOfflineCache:
    """Simple JSON-backed offline cache for Firestore reads."""

    def __init__(self, cache_path: Optional[str] = None):
        self.cache_path = Path(
            cache_path or (Path.home() / ".agentic_brain" / "firestore_rag_cache.json")
        )
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _read_cache(self) -> dict[str, Any]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning(
                "Ignoring corrupt Firestore offline cache at %s", self.cache_path
            )
            return {}

    def _write_cache(self, data: dict[str, Any]) -> None:
        self.cache_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def save_collection(self, collection: str, documents: list[LoadedDocument]) -> None:
        with self._lock:
            cache = self._read_cache()
            cache[collection] = [document.to_dict() for document in documents]
            self._write_cache(cache)

    def load_collection(self, collection: str) -> list[LoadedDocument]:
        with self._lock:
            cache = self._read_cache()
            return [
                LoadedDocument.from_dict(item) for item in cache.get(collection, [])
            ]


class FirestoreLoader(BaseLoader):
    """Load documents from Firebase Firestore for RAG indexing."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        service_account_path: Optional[str] = None,
        app_name: str = "[DEFAULT]",
        collection: str = "documents",
        content_field: str = "content",
        title_field: str = "title",
        metadata_fields: Optional[list[str]] = None,
        enable_offline_persistence: bool = False,
        cache_path: Optional[str] = None,
    ):
        if not FIREBASE_AVAILABLE:
            raise ImportError(
                "firebase-admin not available. Install with: pip install firebase-admin"
            )
        self._project_id = project_id
        self._service_account_path = service_account_path
        self._app_name = app_name
        self._collection = collection
        self._content_field = content_field
        self._title_field = title_field
        self._metadata_fields = metadata_fields or []
        self._db: Optional[Any] = None
        self._app: Optional[Any] = None
        self._authenticated = False
        self._offline_cache = (
            FirestoreOfflineCache(cache_path) if enable_offline_persistence else None
        )

    @property
    def source_name(self) -> str:
        return "firestore"

    def authenticate(self) -> bool:
        if self._authenticated and self._db is not None:
            return True
        try:
            try:
                self._app = firebase_admin.get_app(self._app_name)
            except ValueError:
                options = {"projectId": self._project_id} if self._project_id else None
                app_name = self._app_name if self._app_name != "[DEFAULT]" else None
                if self._service_account_path:
                    cred = firebase_credentials.Certificate(self._service_account_path)
                    self._app = firebase_admin.initialize_app(
                        cred, options=options, name=app_name
                    )
                else:
                    self._app = firebase_admin.initialize_app(
                        options=options, name=app_name
                    )
            self._db = firestore.client(self._app)
            self._authenticated = True
            return True
        except Exception as exc:
            logger.error("Firebase authentication failed: %s", exc)
            return False

    def _ensure_authenticated(self) -> None:
        if not self._authenticated and not self.authenticate():
            raise RuntimeError("Firestore authentication required")

    def _document_path_to_ref(self, document_path: str) -> Any:
        parts = [part for part in document_path.split("/") if part]
        if len(parts) < 2 or len(parts) % 2 != 0:
            raise ValueError(
                f"Invalid document path: {document_path}. Use collection/document pairs."
            )
        ref = self._db.collection(parts[0]).document(parts[1])
        for index in range(2, len(parts), 2):
            ref = ref.collection(parts[index]).document(parts[index + 1])
        return ref

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if hasattr(value, "isoformat") and callable(value.isoformat):
            try:
                return value.isoformat()
            except TypeError:
                return str(value)
        if isinstance(value, dict):
            return {key: self._serialize_value(val) for key, val in value.items()}
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]
        return value

    def _doc_to_loaded_document(
        self, doc_snapshot: Any, collection: str, *, include_path_metadata: bool = True
    ) -> Optional[LoadedDocument]:
        try:
            data = doc_snapshot.to_dict()
            if not data:
                return None
            content = data.get(self._content_field, "")
            if not content:
                for fallback in ["text", "body", "description", "data"]:
                    if fallback in data:
                        content = str(data[fallback])
                        break
            if not content:
                content = json.dumps(data, indent=2, default=str)
            title = data.get(self._title_field) or data.get("name") or doc_snapshot.id
            metadata = {"collection": collection, "document_id": doc_snapshot.id}
            if include_path_metadata and hasattr(doc_snapshot.reference, "path"):
                metadata["path"] = doc_snapshot.reference.path
            for field in self._metadata_fields:
                if field in data:
                    metadata[field] = self._serialize_value(data[field])
            for key, value in data.items():
                if (
                    key not in {self._content_field, self._title_field}
                    and key not in metadata
                ):
                    metadata[key] = self._serialize_value(value)
            created_at = getattr(doc_snapshot, "create_time", None)
            modified_at = getattr(doc_snapshot, "update_time", None)
            return LoadedDocument(
                content=str(content),
                metadata=metadata,
                source="firestore",
                source_id=f"{collection}/{doc_snapshot.id}",
                filename=str(title),
                mime_type="application/json",
                created_at=created_at,
                modified_at=modified_at,
                size_bytes=len(str(content).encode("utf-8")),
            )
        except Exception as exc:
            logger.error("Failed to convert Firestore document: %s", exc)
            return None

    def _apply_query_options(
        self,
        query: Any,
        where: Optional[list[tuple[str, str, Any]]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Any:
        if where:
            for field, operator, value in where:
                query = query.where(field, operator, value)
        if order_by:
            if order_by.startswith("-"):
                query = query.order_by(
                    order_by[1:], direction=firestore.Query.DESCENDING
                )
            else:
                query = query.order_by(order_by)
        if limit:
            query = query.limit(limit)
        return query

    def _persist_collection_cache(
        self, cache_key: str, documents: list[LoadedDocument]
    ) -> None:
        if self._offline_cache:
            self._offline_cache.save_collection(cache_key, documents)

    def _load_from_cache(self, cache_key: str) -> list[LoadedDocument]:
        return (
            self._offline_cache.load_collection(cache_key)
            if self._offline_cache
            else []
        )

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        self._ensure_authenticated()
        try:
            doc_ref = self._document_path_to_ref(doc_id)
            doc_snapshot = doc_ref.get()
            if not doc_snapshot.exists:
                return None
            collection = "/".join(doc_id.split("/")[:-1])
            document = self._doc_to_loaded_document(doc_snapshot, collection)
            if document:
                self._persist_collection_cache(collection, [document])
            return document
        except Exception as exc:
            logger.error("Failed to load Firestore document %s: %s", doc_id, exc)
            collection = "/".join(doc_id.split("/")[:-1])
            cached = self._load_from_cache(collection)
            return cached[0] if cached else None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        return self.load_collection(folder_path, recursive=recursive)

    def load_collection(
        self,
        collection: Optional[str] = None,
        where: Optional[list[tuple[str, str, Any]]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        recursive: bool = False,
    ) -> list[LoadedDocument]:
        self._ensure_authenticated()
        collection = collection or self._collection
        documents: list[LoadedDocument] = []
        try:
            query = self._apply_query_options(
                self._db.collection(collection),
                where=where,
                order_by=order_by,
                limit=limit,
            )
            for doc_snapshot in query.stream():
                loaded_doc = self._doc_to_loaded_document(doc_snapshot, collection)
                if loaded_doc:
                    documents.append(loaded_doc)
                if recursive:
                    documents.extend(
                        self.load_subcollections(
                            doc_snapshot.reference.path, recursive=True
                        )
                    )
            self._persist_collection_cache(collection, documents)
            return documents
        except Exception as exc:
            logger.error("Failed to load collection %s: %s", collection, exc)
            return self._load_from_cache(collection)

    def load_collection_group(
        self,
        collection_id: str,
        where: Optional[list[tuple[str, str, Any]]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[LoadedDocument]:
        self._ensure_authenticated()
        try:
            query = self._apply_query_options(
                self._db.collection_group(collection_id),
                where=where,
                order_by=order_by,
                limit=limit,
            )
            documents = []
            for doc_snapshot in query.stream():
                document = self._doc_to_loaded_document(doc_snapshot, collection_id)
                if document:
                    documents.append(document)
            self._persist_collection_cache(
                f"collection_group:{collection_id}", documents
            )
            return documents
        except Exception as exc:
            logger.error("Collection group query failed for %s: %s", collection_id, exc)
            return self._load_from_cache(f"collection_group:{collection_id}")

    def load_subcollections(
        self, document_path: str, recursive: bool = False
    ) -> list[LoadedDocument]:
        self._ensure_authenticated()
        documents: list[LoadedDocument] = []
        try:
            doc_ref = self._document_path_to_ref(document_path)
            for subcollection in doc_ref.collections():
                subcollection_path = f"{document_path}/{subcollection.id}"
                for doc_snapshot in subcollection.stream():
                    loaded_doc = self._doc_to_loaded_document(
                        doc_snapshot, subcollection_path
                    )
                    if loaded_doc:
                        documents.append(loaded_doc)
                    if recursive:
                        documents.extend(
                            self.load_subcollections(
                                f"{subcollection_path}/{doc_snapshot.id}",
                                recursive=True,
                            )
                        )
            self._persist_collection_cache(f"subcollections:{document_path}", documents)
            return documents
        except Exception as exc:
            logger.error("Failed to load subcollections for %s: %s", document_path, exc)
            return self._load_from_cache(f"subcollections:{document_path}")

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        self._ensure_authenticated()
        query_lower = query.lower()
        matches: list[LoadedDocument] = []
        try:
            for collection_ref in self._db.collections():
                for doc_snapshot in collection_ref.stream():
                    data = doc_snapshot.to_dict() or {}
                    combined = " ".join(
                        [
                            str(data.get(self._content_field, "")),
                            str(data.get(self._title_field, "")),
                            doc_snapshot.id,
                        ]
                    ).lower()
                    if query_lower in combined:
                        document = self._doc_to_loaded_document(
                            doc_snapshot, collection_ref.id
                        )
                        if document:
                            matches.append(document)
                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break
            return matches
        except Exception as exc:
            logger.error("Search failed: %s", exc)
            return []

    def watch_collection(
        self,
        collection: Optional[str] = None,
        where: Optional[list[tuple[str, str, Any]]] = None,
    ):
        self._ensure_authenticated()
        collection = collection or self._collection
        doc_queue: queue.Queue[Any] = queue.Queue()

        def on_snapshot(doc_snapshot, changes, read_time):
            for change in changes:
                if change.type.name in ("ADDED", "MODIFIED"):
                    doc_queue.put(change.document)

        query = self._apply_query_options(self._db.collection(collection), where=where)
        unsubscribe = query.on_snapshot(on_snapshot)
        try:
            while True:
                try:
                    snapshot = doc_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                document = self._doc_to_loaded_document(snapshot, collection)
                if document:
                    yield document
        finally:
            unsubscribe()

    def sync_collection(
        self,
        collection: Optional[str] = None,
        where: Optional[list[tuple[str, str, Any]]] = None,
        recursive: bool = False,
    ) -> list[LoadedDocument]:
        collection = collection or self._collection
        documents = self.load_collection(collection, where=where, recursive=recursive)
        self._persist_collection_cache(collection, documents)
        return documents

    def batch_save_documents(
        self,
        collection: Optional[str],
        documents: list[dict[str, Any] | LoadedDocument],
    ) -> list[str]:
        self._ensure_authenticated()
        collection = collection or self._collection
        batch = self._db.batch()
        saved_ids: list[str] = []
        for index, item in enumerate(documents):
            if isinstance(item, LoadedDocument):
                payload = {
                    self._content_field: item.content,
                    self._title_field: item.filename or f"Document {index + 1}",
                    **{
                        key: value
                        for key, value in item.metadata.items()
                        if key not in {"collection", "document_id", "path"}
                    },
                    "updated_at": firestore.SERVER_TIMESTAMP,
                }
                document_id = (
                    item.metadata.get("document_id")
                    or item.id
                    or item.source_id.split("/")[-1]
                )
            else:
                payload = dict(item)
                document_id = str(
                    payload.pop("document_id", payload.pop("id", f"doc-{index + 1}"))
                )
                payload.setdefault("updated_at", firestore.SERVER_TIMESTAMP)
                payload.setdefault(self._title_field, payload.get("name", document_id))
            ref = self._db.collection(collection).document(document_id)
            batch.set(ref, payload, merge=True)
            saved_ids.append(document_id)
        batch.commit()
        return saved_ids

    def save_document(
        self,
        collection: str,
        content: str,
        title: str = "",
        metadata: Optional[dict[str, Any]] = None,
        document_id: Optional[str] = None,
    ) -> Optional[str]:
        self._ensure_authenticated()
        try:
            data = {
                self._content_field: content,
                self._title_field: title or "Untitled",
                "created_at": firestore.SERVER_TIMESTAMP,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
            if metadata:
                data.update(metadata)
            if document_id:
                self._db.collection(collection).document(document_id).set(
                    data, merge=True
                )
                return document_id
            doc_ref = self._db.collection(collection).add(data)
            if isinstance(doc_ref, tuple) and len(doc_ref) > 1:
                return doc_ref[1].id
            return getattr(doc_ref, "id", None)
        except Exception as exc:
            logger.error("Failed to save document: %s", exc)
            return None

    def batch_delete_documents(self, document_paths: list[str]) -> int:
        self._ensure_authenticated()
        batch = self._db.batch()
        count = 0
        for document_path in document_paths:
            ref = self._document_path_to_ref(document_path)
            batch.delete(ref)
            count += 1
        if count:
            batch.commit()
        return count

    def delete_document(self, doc_id: str) -> bool:
        self._ensure_authenticated()
        try:
            self._document_path_to_ref(doc_id).delete()
            return True
        except Exception as exc:
            logger.error("Failed to delete document %s: %s", doc_id, exc)
            return False

    def list_collections(self) -> list[str]:
        self._ensure_authenticated()
        try:
            return [collection.id for collection in self._db.collections()]
        except Exception as exc:
            logger.error("Failed to list collections: %s", exc)
            return []
