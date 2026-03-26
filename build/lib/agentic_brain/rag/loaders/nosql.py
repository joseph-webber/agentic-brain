# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""NoSQL database loaders for RAG pipelines.

Supports:
- MongoDB
- Redis
- Elasticsearch
- Firebase Firestore
"""

import json
import logging
import os
import queue
import threading
from collections.abc import Generator
from datetime import datetime, timezone
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for pymongo
try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, OperationFailure

    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False

# Check for redis
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Check for elasticsearch
try:
    from elasticsearch import Elasticsearch

    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False

# Check for Firebase
try:
    import firebase_admin
    from firebase_admin import credentials as firebase_credentials
    from firebase_admin import firestore

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False


class MongoDBLoader(BaseLoader):
    """Load documents from MongoDB.

    MongoDB is a document database storing JSON-like documents.
    Perfect for RAG as documents are already structured.

    Authentication options:
        1. Connection URI (mongodb://user:pass@host:port/db)
        2. Separate host/port/credentials

    Example:
        # With connection URI
        loader = MongoDBLoader(
            uri="mongodb://localhost:27017",
            database="knowledge_base",
            collection="documents"
        )
        docs = loader.load_collection()

        # With authentication
        loader = MongoDBLoader(
            host="mongodb.company.com",
            port=27017,
            database="docs",
            collection="articles",
            username="reader",
            password="secret",
            auth_source="admin"
        )
        docs = loader.load_collection(filter={"status": "published"})
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        host: str = "localhost",
        port: int = 27017,
        database: str = "test",
        collection: str = "documents",
        username: Optional[str] = None,
        password: Optional[str] = None,
        auth_source: str = "admin",
        content_field: str = "content",
        title_field: str = "title",
        metadata_fields: Optional[list[str]] = None,
    ):
        if not PYMONGO_AVAILABLE:
            raise ImportError(
                "pymongo not available. Install with: pip install pymongo"
            )

        self._uri = uri
        self._host = host
        self._port = port
        self._database_name = database
        self._collection_name = collection
        self._username = username
        self._password = password
        self._auth_source = auth_source
        self._content_field = content_field
        self._title_field = title_field
        self._metadata_fields = metadata_fields or []

        self._client: Optional[Any] = None
        self._db: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "mongodb"

    def authenticate(self) -> bool:
        """Connect to MongoDB."""
        if self._authenticated and self._client is not None:
            return True

        try:
            if self._uri:
                self._client = MongoClient(self._uri)
            else:
                conn_kwargs = {
                    "host": self._host,
                    "port": self._port,
                }

                if self._username and self._password:
                    conn_kwargs["username"] = self._username
                    conn_kwargs["password"] = self._password
                    conn_kwargs["authSource"] = self._auth_source

                self._client = MongoClient(**conn_kwargs)

            self._client.admin.command("ping")
            self._db = self._client[self._database_name]
            self._authenticated = True

            logger.info(f"MongoDB connected: {self._database_name}")
            return True

        except ConnectionFailure as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False
        except Exception as e:
            logger.error(f"MongoDB authentication failed: {e}")
            return False

    def _ensure_authenticated(self) -> None:
        if not self._authenticated and not self.authenticate():
            raise RuntimeError("MongoDB connection required")

    def _doc_to_loaded_document(
        self, doc: dict[str, Any], collection_name: str
    ) -> Optional[LoadedDocument]:
        """Convert MongoDB document to LoadedDocument."""
        try:
            content = doc.get(self._content_field, "")
            if not content:
                for fallback in ["text", "body", "description", "data"]:
                    if fallback in doc:
                        content = str(doc[fallback])
                        break

            if not content:
                doc_copy = {k: v for k, v in doc.items() if k != "_id"}
                content = json.dumps(doc_copy, indent=2, default=str)

            title = doc.get(self._title_field, "")
            if not title:
                for fallback in ["name", "filename", "subject", "heading"]:
                    if fallback in doc:
                        title = str(doc[fallback])
                        break
            if not title:
                title = str(doc.get("_id", "Untitled"))

            doc_id = doc.get("_id")
            metadata = {
                "database": self._database_name,
                "collection": collection_name,
                "document_id": str(doc_id) if doc_id else None,
            }

            for field in self._metadata_fields:
                if field in doc and field not in [self._content_field, "_id"]:
                    try:
                        json.dumps(doc[field], default=str)
                        metadata[field] = doc[field]
                    except (TypeError, ValueError):
                        metadata[field] = str(doc[field])

            for key, value in doc.items():
                if key not in [self._content_field, self._title_field, "_id"]:
                    if key not in metadata:
                        try:
                            json.dumps(value, default=str)
                            metadata[key] = value
                        except (TypeError, ValueError):
                            metadata[key] = str(value)

            created_at = None
            modified_at = None

            for ts_field in ["created_at", "createdAt", "timestamp", "created"]:
                if ts_field in doc:
                    ts = doc[ts_field]
                    if isinstance(ts, datetime):
                        created_at = ts
                    break

            for ts_field in ["updated_at", "updatedAt", "modified", "modified_at"]:
                if ts_field in doc:
                    ts = doc[ts_field]
                    if isinstance(ts, datetime):
                        modified_at = ts
                    break

            return LoadedDocument(
                content=str(content),
                metadata=metadata,
                source="mongodb",
                source_id=f"{self._database_name}/{collection_name}/{doc_id}",
                filename=title,
                mime_type="application/json",
                created_at=created_at,
                modified_at=modified_at,
                size_bytes=len(str(content).encode("utf-8")),
            )

        except Exception as e:
            logger.error(f"Failed to convert MongoDB document: {e}")
            return None

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID."""
        self._ensure_authenticated()

        try:
            from bson import ObjectId

            collection = self._db[self._collection_name]

            try:
                doc = collection.find_one({"_id": ObjectId(doc_id)})
            except Exception:
                doc = collection.find_one({"_id": doc_id})

            if not doc:
                logger.warning(f"Document not found: {doc_id}")
                return None

            return self._doc_to_loaded_document(doc, self._collection_name)

        except Exception as e:
            logger.error(f"Failed to load MongoDB document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a collection."""
        return self.load_collection(collection_name=folder_path)

    def load_collection(
        self,
        collection_name: Optional[str] = None,
        filter: Optional[dict[str, Any]] = None,
        projection: Optional[dict[str, int]] = None,
        sort: Optional[list[tuple]] = None,
        limit: int = 0,
        skip: int = 0,
    ) -> list[LoadedDocument]:
        """Load documents from a MongoDB collection."""
        self._ensure_authenticated()

        collection_name = collection_name or self._collection_name
        documents = []

        try:
            collection = self._db[collection_name]

            cursor = collection.find(filter=filter or {}, projection=projection)

            if sort:
                cursor = cursor.sort(sort)
            if skip:
                cursor = cursor.skip(skip)
            if limit:
                cursor = cursor.limit(limit)

            for doc in cursor:
                loaded_doc = self._doc_to_loaded_document(doc, collection_name)
                if loaded_doc:
                    documents.append(loaded_doc)

            logger.info(f"Loaded {len(documents)} documents from {collection_name}")
            return documents

        except Exception as e:
            logger.error(f"Failed to load collection {collection_name}: {e}")
            return []

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for documents using MongoDB text search."""
        self._ensure_authenticated()

        documents = []
        collection = self._db[self._collection_name]

        try:
            try:
                cursor = (
                    collection.find(
                        {"$text": {"$search": query}}, {"score": {"$meta": "textScore"}}
                    )
                    .sort([("score", {"$meta": "textScore"})])
                    .limit(max_results)
                )

                for doc in cursor:
                    loaded_doc = self._doc_to_loaded_document(
                        doc, self._collection_name
                    )
                    if loaded_doc:
                        documents.append(loaded_doc)

                if documents:
                    logger.info(f"Found {len(documents)} documents via text search")
                    return documents

            except OperationFailure:
                pass

            regex_filter = {
                "$or": [
                    {self._content_field: {"$regex": query, "$options": "i"}},
                    {self._title_field: {"$regex": query, "$options": "i"}},
                ]
            }

            cursor = collection.find(regex_filter).limit(max_results)

            for doc in cursor:
                loaded_doc = self._doc_to_loaded_document(doc, self._collection_name)
                if loaded_doc:
                    documents.append(loaded_doc)

            logger.info(f"Found {len(documents)} documents via regex search")
            return documents

        except Exception as e:
            logger.error(f"MongoDB search failed: {e}")
            return []

    def save_document(
        self,
        content: str,
        title: str = "",
        metadata: Optional[dict[str, Any]] = None,
        collection_name: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> Optional[str]:
        """Save a document to MongoDB."""
        self._ensure_authenticated()

        collection_name = collection_name or self._collection_name

        try:
            doc = {
                self._content_field: content,
                self._title_field: title or "Untitled",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }

            if metadata:
                doc.update(metadata)

            collection = self._db[collection_name]

            if document_id:
                from bson import ObjectId

                try:
                    doc["_id"] = ObjectId(document_id)
                except Exception:
                    doc["_id"] = document_id
                collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
                return str(doc["_id"])
            else:
                result = collection.insert_one(doc)
                return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Failed to save MongoDB document: {e}")
            return None

    def delete_document(
        self, doc_id: str, collection_name: Optional[str] = None
    ) -> bool:
        """Delete a document from MongoDB."""
        self._ensure_authenticated()

        collection_name = collection_name or self._collection_name

        try:
            from bson import ObjectId

            collection = self._db[collection_name]

            try:
                result = collection.delete_one({"_id": ObjectId(doc_id)})
            except Exception:
                result = collection.delete_one({"_id": doc_id})

            if result.deleted_count > 0:
                logger.info(f"Deleted MongoDB document: {doc_id}")
                return True
            else:
                logger.warning(f"Document not found: {doc_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to delete MongoDB document: {e}")
            return False

    def list_collections(self) -> list[str]:
        """List all collections in the database."""
        self._ensure_authenticated()

        try:
            return self._db.list_collection_names()
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def create_text_index(
        self, fields: Optional[list[str]] = None, collection_name: Optional[str] = None
    ) -> bool:
        """Create a text index for full-text search."""
        self._ensure_authenticated()

        collection_name = collection_name or self._collection_name
        fields = fields or [self._content_field, self._title_field]

        try:
            collection = self._db[collection_name]
            index_spec = [(field, "text") for field in fields]
            collection.create_index(index_spec, name="text_search_index")
            logger.info(f"Created text index on {collection_name}: {fields}")
            return True

        except Exception as e:
            logger.error(f"Failed to create text index: {e}")
            return False

    def aggregate(
        self, pipeline: list[dict[str, Any]], collection_name: Optional[str] = None
    ) -> list[LoadedDocument]:
        """Run aggregation pipeline and return as documents."""
        self._ensure_authenticated()

        collection_name = collection_name or self._collection_name
        documents = []

        try:
            collection = self._db[collection_name]

            for doc in collection.aggregate(pipeline):
                loaded_doc = self._doc_to_loaded_document(doc, collection_name)
                if loaded_doc:
                    documents.append(loaded_doc)

            return documents

        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            return []


class RedisLoader(BaseLoader):
    """Load documents from Redis.

    Supports loading from Redis strings, hashes, and JSON (RedisJSON).

    Example:
        loader = RedisLoader(host="localhost", port=6379)
        docs = loader.load_folder("articles:*")  # key pattern
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        url: Optional[str] = None,
        content_field: str = "content",
    ):
        if not REDIS_AVAILABLE:
            raise ImportError("redis not installed. Run: pip install redis")

        self.host = host
        self.port = port
        self.db = db
        self.password = password or os.environ.get("REDIS_PASSWORD")
        self.url = url or os.environ.get("REDIS_URL")
        self.content_field = content_field
        self._client = None

    @property
    def source_name(self) -> str:
        return "redis"

    def authenticate(self) -> bool:
        """Connect to Redis."""
        try:
            if self.url:
                self._client = redis.from_url(self.url)
            else:
                self._client = redis.Redis(
                    host=self.host, port=self.port, db=self.db, password=self.password
                )
            self._client.ping()
            logger.info("Redis connection successful")
            return True
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._client and not self.authenticate():
            raise RuntimeError("Failed to connect to Redis")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single key."""
        self._ensure_authenticated()
        try:
            key_type = self._client.type(doc_id).decode()

            if key_type == "string":
                content = self._client.get(doc_id)
                content = content.decode() if content else ""
            elif key_type == "hash":
                data = self._client.hgetall(doc_id)
                data = {k.decode(): v.decode() for k, v in data.items()}
                content = data.get(self.content_field, json.dumps(data))
            elif key_type == "ReJSON-RL":
                content = self._client.execute_command("JSON.GET", doc_id)
                content = content if isinstance(content, str) else content.decode()
            else:
                logger.debug(f"Unsupported Redis type: {key_type}")
                return None

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=doc_id,
                metadata={"key": doc_id, "type": key_type},
            )
        except Exception as e:
            logger.error(f"Failed to load key {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all keys matching a pattern."""
        self._ensure_authenticated()
        docs = []
        pattern = folder_path if "*" in folder_path else f"{folder_path}*"

        try:
            for key in self._client.scan_iter(match=pattern):
                key_str = key.decode() if isinstance(key, bytes) else key
                doc = self.load_document(key_str)
                if doc:
                    docs.append(doc)
        except Exception as e:
            logger.error(f"Failed to scan pattern {pattern}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search using RediSearch (if available)."""
        self._ensure_authenticated()
        docs = []

        try:
            result = self._client.execute_command(
                "FT.SEARCH", "idx:docs", query, "LIMIT", 0, max_results
            )
            if isinstance(result, list) and len(result) > 1:
                for i in range(1, len(result), 2):
                    doc_id = (
                        result[i].decode()
                        if isinstance(result[i], bytes)
                        else result[i]
                    )
                    doc = self.load_document(doc_id)
                    if doc:
                        docs.append(doc)
        except Exception as e:
            logger.debug(f"RediSearch not available or failed: {e}")
            docs = self.load_folder(f"*{query}*")[:max_results]

        return docs


class ElasticsearchLoader(BaseLoader):
    """Load documents from Elasticsearch.

    Perfect for existing search indices that need RAG integration.

    Example:
        loader = ElasticsearchLoader(
            hosts=["http://localhost:9200"],
            index="articles",
            content_field="body"
        )
        docs = loader.search("machine learning")
    """

    def __init__(
        self,
        hosts: list[str] = None,
        index: str = "documents",
        content_field: str = "content",
        cloud_id: Optional[str] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        if not ELASTICSEARCH_AVAILABLE:
            raise ImportError(
                "elasticsearch not installed. Run: pip install elasticsearch"
            )

        self.hosts = hosts or ["http://localhost:9200"]
        self.index = index
        self.content_field = content_field
        self.cloud_id = cloud_id
        self.api_key = api_key or os.environ.get("ELASTICSEARCH_API_KEY")
        self.username = username
        self.password = password
        self._client = None

    @property
    def source_name(self) -> str:
        return "elasticsearch"

    def authenticate(self) -> bool:
        """Connect to Elasticsearch."""
        try:
            if self.cloud_id:
                self._client = Elasticsearch(
                    cloud_id=self.cloud_id, api_key=self.api_key
                )
            elif self.api_key:
                self._client = Elasticsearch(hosts=self.hosts, api_key=self.api_key)
            elif self.username and self.password:
                self._client = Elasticsearch(
                    hosts=self.hosts, basic_auth=(self.username, self.password)
                )
            else:
                self._client = Elasticsearch(hosts=self.hosts)

            self._client.info()
            logger.info("Elasticsearch connection successful")
            return True
        except Exception as e:
            logger.error(f"Elasticsearch connection failed: {e}")
            return False

    def _ensure_authenticated(self):
        if not self._client and not self.authenticate():
            raise RuntimeError("Failed to connect to Elasticsearch")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID."""
        self._ensure_authenticated()
        try:
            result = self._client.get(index=self.index, id=doc_id)
            source = result["_source"]
            content = source.get(self.content_field, "")

            return LoadedDocument(
                content=str(content),
                source=self.source_name,
                source_id=doc_id,
                filename=f"{self.index}_{doc_id}",
                metadata={"index": self.index, **source},
            )
        except Exception as e:
            logger.error(f"Failed to load document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from an index."""
        self._ensure_authenticated()
        docs = []

        try:
            result = self._client.search(
                index=self.index,
                query={"match_all": {}},
                size=1000,
                scroll="2m",
            )

            scroll_id = result["_scroll_id"]
            hits = result["hits"]["hits"]

            while hits:
                for hit in hits:
                    content = hit["_source"].get(self.content_field, "")
                    docs.append(
                        LoadedDocument(
                            content=str(content),
                            source=self.source_name,
                            source_id=hit["_id"],
                            filename=f"{self.index}_{hit['_id']}",
                            metadata={"index": self.index, **hit["_source"]},
                        )
                    )

                result = self._client.scroll(scroll_id=scroll_id, scroll="2m")
                hits = result["hits"]["hits"]

            self._client.clear_scroll(scroll_id=scroll_id)
        except Exception as e:
            logger.error(f"Failed to load index {self.index}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search using Elasticsearch query."""
        self._ensure_authenticated()
        docs = []

        try:
            result = self._client.search(
                index=self.index,
                query={"match": {self.content_field: query}},
                size=max_results,
            )

            for hit in result["hits"]["hits"]:
                content = hit["_source"].get(self.content_field, "")
                docs.append(
                    LoadedDocument(
                        content=str(content),
                        source=self.source_name,
                        source_id=hit["_id"],
                        filename=f"{self.index}_{hit['_id']}",
                        metadata={
                            "index": self.index,
                            "score": hit["_score"],
                            **hit["_source"],
                        },
                    )
                )
        except Exception as e:
            logger.error(f"Elasticsearch search failed: {e}")

        return docs


class FirestoreLoader(BaseLoader):
    """Load documents from Firebase Firestore.

    Firestore is a document database that stores JSON-like documents
    in collections.

    Authentication options:
        1. Service account JSON file (for server deployments)
        2. Default credentials (for GCP environments)

    Example:
        loader = FirestoreLoader(
            service_account_path="firebase-adminsdk.json",
            project_id="my-project"
        )
        docs = loader.load_collection("documents")
    """

    def __init__(
        self,
        service_account_path: Optional[str] = None,
        project_id: Optional[str] = None,
        app_name: str = "[DEFAULT]",
        content_field: str = "content",
        title_field: str = "title",
        metadata_fields: Optional[list[str]] = None,
    ):
        if not FIREBASE_AVAILABLE:
            raise ImportError(
                "Firebase Admin SDK not available. Install with: "
                "pip install firebase-admin"
            )

        self._service_account_path = service_account_path
        self._project_id = project_id
        self._app_name = app_name
        self._content_field = content_field
        self._title_field = title_field
        self._metadata_fields = metadata_fields or []
        self._db: Optional[Any] = None
        self._app: Optional[Any] = None
        self._authenticated = False

    @property
    def source_name(self) -> str:
        return "firestore"

    def authenticate(self) -> bool:
        """Initialize Firebase Admin and get Firestore client."""
        if self._authenticated and self._db is not None:
            return True

        try:
            try:
                self._app = firebase_admin.get_app(self._app_name)
                logger.info(f"Using existing Firebase app: {self._app_name}")
            except ValueError:
                if self._service_account_path:
                    cred = firebase_credentials.Certificate(self._service_account_path)
                    options = (
                        {"projectId": self._project_id} if self._project_id else {}
                    )
                    self._app = firebase_admin.initialize_app(
                        cred,
                        options,
                        name=self._app_name if self._app_name != "[DEFAULT]" else None,
                    )
                    logger.info("Firebase authenticated with service account")
                else:
                    self._app = firebase_admin.initialize_app(
                        options=(
                            {"projectId": self._project_id}
                            if self._project_id
                            else None
                        ),
                        name=self._app_name if self._app_name != "[DEFAULT]" else None,
                    )
                    logger.info("Firebase authenticated with default credentials")

            self._db = firestore.client(self._app)
            self._authenticated = True
            return True

        except Exception as e:
            logger.error(f"Firebase authentication failed: {e}")
            return False

    def _ensure_authenticated(self) -> None:
        if not self._authenticated and not self.authenticate():
            raise RuntimeError("Firestore authentication required")

    def _doc_to_loaded_document(
        self, doc_snapshot: Any, collection: str
    ) -> Optional[LoadedDocument]:
        """Convert Firestore document snapshot to LoadedDocument."""
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

            title = data.get(self._title_field, "")
            if not title:
                for fallback in ["name", "filename", "subject", "heading"]:
                    if fallback in data:
                        title = str(data[fallback])
                        break
            if not title:
                title = doc_snapshot.id

            metadata = {
                "collection": collection,
                "document_id": doc_snapshot.id,
            }

            for field in self._metadata_fields:
                if field in data:
                    metadata[field] = data[field]

            for key, value in data.items():
                if key not in [self._content_field, self._title_field]:
                    if key not in metadata:
                        try:
                            json.dumps(value, default=str)
                            metadata[key] = value
                        except (TypeError, ValueError):
                            metadata[key] = str(value)

            created_at = None
            modified_at = None

            if hasattr(doc_snapshot, "create_time") and doc_snapshot.create_time:
                created_at = doc_snapshot.create_time
            if hasattr(doc_snapshot, "update_time") and doc_snapshot.update_time:
                modified_at = doc_snapshot.update_time

            for ts_field in ["created_at", "createdAt", "timestamp", "created"]:
                if ts_field in data and created_at is None:
                    ts = data[ts_field]
                    if hasattr(ts, "isoformat"):
                        created_at = ts
                    break

            for ts_field in ["updated_at", "updatedAt", "modified", "modified_at"]:
                if ts_field in data and modified_at is None:
                    ts = data[ts_field]
                    if hasattr(ts, "isoformat"):
                        modified_at = ts
                    break

            return LoadedDocument(
                content=str(content),
                metadata=metadata,
                source="firestore",
                source_id=f"{collection}/{doc_snapshot.id}",
                filename=title,
                mime_type="application/json",
                created_at=created_at,
                modified_at=modified_at,
                size_bytes=len(str(content).encode("utf-8")),
            )

        except Exception as e:
            logger.error(f"Failed to convert Firestore document: {e}")
            return None

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID."""
        self._ensure_authenticated()

        try:
            if "/" not in doc_id:
                raise ValueError(
                    f"Invalid doc_id format: {doc_id}. Use 'collection/document_id'"
                )

            parts = doc_id.split("/")
            collection = "/".join(parts[:-1])
            document_id = parts[-1]

            doc_ref = self._db.collection(collection).document(document_id)
            doc_snapshot = doc_ref.get()

            if not doc_snapshot.exists:
                logger.warning(f"Document not found: {doc_id}")
                return None

            return self._doc_to_loaded_document(doc_snapshot, collection)

        except Exception as e:
            logger.error(f"Failed to load Firestore document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a collection."""
        return self.load_collection(folder_path, recursive=recursive)

    def load_collection(
        self,
        collection: str,
        where: Optional[list[tuple]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        recursive: bool = False,
    ) -> list[LoadedDocument]:
        """Load documents from a Firestore collection."""
        self._ensure_authenticated()

        documents = []

        try:
            query = self._db.collection(collection)

            if where:
                for field, op, value in where:
                    query = query.where(field, op, value)

            if order_by:
                if order_by.startswith("-"):
                    query = query.order_by(
                        order_by[1:], direction=firestore.Query.DESCENDING
                    )
                else:
                    query = query.order_by(order_by)

            if limit:
                query = query.limit(limit)

            for doc_snapshot in query.stream():
                loaded_doc = self._doc_to_loaded_document(doc_snapshot, collection)
                if loaded_doc:
                    documents.append(loaded_doc)

                if recursive:
                    subcollections = doc_snapshot.reference.collections()
                    for subcoll in subcollections:
                        subcoll_path = f"{collection}/{doc_snapshot.id}/{subcoll.id}"
                        subdocs = self.load_collection(subcoll_path, recursive=True)
                        documents.extend(subdocs)

            logger.info(f"Loaded {len(documents)} documents from {collection}")
            return documents

        except Exception as e:
            logger.error(f"Failed to load collection {collection}: {e}")
            return []

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for documents containing text."""
        self._ensure_authenticated()

        documents = []
        query_lower = query.lower()

        try:
            collections = self._db.collections()

            for collection in collections:
                for doc_snapshot in collection.stream():
                    data = doc_snapshot.to_dict()
                    if not data:
                        continue

                    searchable = []
                    searchable.append(str(data.get(self._content_field, "")))
                    searchable.append(str(data.get(self._title_field, "")))
                    searchable.append(str(data.get("description", "")))
                    searchable.append(doc_snapshot.id)

                    combined = " ".join(searchable).lower()

                    if query_lower in combined:
                        loaded_doc = self._doc_to_loaded_document(
                            doc_snapshot, collection.id
                        )
                        if loaded_doc:
                            documents.append(loaded_doc)
                            if len(documents) >= max_results:
                                break

                if len(documents) >= max_results:
                    break

            logger.info(f"Found {len(documents)} documents matching '{query}'")
            return documents

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def watch_collection(
        self, collection: str, where: Optional[list[tuple]] = None
    ) -> Generator[LoadedDocument, None, None]:
        """Watch a collection for real-time updates."""
        self._ensure_authenticated()

        doc_queue: queue.Queue = queue.Queue()
        stop_event = threading.Event()

        def on_snapshot(doc_snapshot, changes, read_time):
            for change in changes:
                if change.type.name in ("ADDED", "MODIFIED"):
                    doc_queue.put(change.document)

        query = self._db.collection(collection)
        if where:
            for field, op, value in where:
                query = query.where(field, op, value)

        unsubscribe = query.on_snapshot(on_snapshot)

        try:
            while not stop_event.is_set():
                try:
                    doc_snapshot = doc_queue.get(timeout=1.0)
                    loaded_doc = self._doc_to_loaded_document(doc_snapshot, collection)
                    if loaded_doc:
                        yield loaded_doc
                except queue.Empty:
                    continue
        finally:
            unsubscribe()

    def save_document(
        self,
        collection: str,
        content: str,
        title: str = "",
        metadata: Optional[dict[str, Any]] = None,
        document_id: Optional[str] = None,
    ) -> Optional[str]:
        """Save a document to Firestore."""
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
                self._db.collection(collection).document(document_id).set(data)
                return document_id
            else:
                doc_ref = self._db.collection(collection).add(data)
                return doc_ref[1].id

        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return None

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from Firestore."""
        self._ensure_authenticated()

        try:
            if "/" not in doc_id:
                raise ValueError(f"Invalid doc_id format: {doc_id}")

            parts = doc_id.split("/")
            collection = "/".join(parts[:-1])
            document_id = parts[-1]

            self._db.collection(collection).document(document_id).delete()
            logger.info(f"Deleted document: {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return False

    def list_collections(self) -> list[str]:
        """List all root collections in Firestore."""
        self._ensure_authenticated()

        try:
            return [coll.id for coll in self._db.collections()]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []


__all__ = [
    "MongoDBLoader",
    "RedisLoader",
    "ElasticsearchLoader",
    "FirestoreLoader",
]
