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

"""Vector database loaders for RAG pipelines.

Supports:
- Pinecone (cloud vector DB)
- Weaviate (open-source vector DB)
- Qdrant (open-source vector DB)
- ChromaDB (embedded vector DB)
- Milvus (open-source vector DB)
"""

import logging
import os
from typing import Optional

from .base import BaseLoader, LoadedDocument, with_rate_limit

logger = logging.getLogger(__name__)

# Check for Pinecone
try:
    from pinecone import Pinecone

    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False

# Check for Weaviate
try:
    import weaviate

    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False

# Check for Qdrant
try:
    from qdrant_client import QdrantClient

    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

# Check for ChromaDB
try:
    import chromadb

    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

# Check for Milvus
try:
    from pymilvus import Collection, connections

    MILVUS_AVAILABLE = True
except ImportError:
    MILVUS_AVAILABLE = False


class PineconeLoader(BaseLoader):
    """Load documents from Pinecone vector database.

    Retrieves documents stored with their embeddings.

    Example:
        loader = PineconeLoader(
            api_key="your-api-key",
            environment="us-west1-gcp",
            index_name="my-index"
        )
        docs = loader.load_folder("namespace")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        index_name: Optional[str] = None,
    ):
        """Initialize Pinecone loader.

        Args:
            api_key: Pinecone API key
            environment: Pinecone environment
            index_name: Index name
        """
        if not PINECONE_AVAILABLE:
            raise ImportError(
                "pinecone-client package is required. Install with: pip install pinecone-client"
            )

        self.api_key = api_key or os.environ.get("PINECONE_API_KEY", "")
        self.environment = environment or os.environ.get("PINECONE_ENVIRONMENT", "")
        self.index_name = index_name or os.environ.get("PINECONE_INDEX_NAME", "")
        self._client = None
        self._index = None

    def source_name(self) -> str:
        return "pinecone"

    def authenticate(self) -> bool:
        """Connect to Pinecone."""
        try:
            self._client = Pinecone(api_key=self.api_key)
            self._index = self._client.Index(self.index_name)
            logger.info(f"Connected to Pinecone index: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Pinecone: {e}")
            return False

    def close(self) -> None:
        """Close Pinecone connection."""
        if self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.error(f"Error closing Pinecone: {e}")

    @with_rate_limit(requests_per_minute=60)
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a document by ID (uses fetch).

        Args:
            doc_id: Document ID

        Returns:
            Loaded document
        """
        if not self._index:
            return None

        try:
            # Fetch by ID
            result = self._index.fetch(ids=[doc_id])

            if not result.get("vectors"):
                return None

            vector_data = result["vectors"][0]
            metadata = vector_data.get("metadata", {})
            content = metadata.get("content", "")

            return LoadedDocument(
                content=content,
                metadata=metadata,
                source="pinecone",
                source_id=doc_id,
                filename=metadata.get("filename", doc_id),
                mime_type=metadata.get("mime_type", "text/plain"),
            )
        except Exception as e:
            logger.error(f"Error loading document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a namespace.

        Args:
            folder_path: Namespace name
            recursive: Unused

        Returns:
            List of documents
        """
        if not self._index:
            return []

        documents = []
        try:
            # Query all vectors in namespace
            namespace = folder_path or None

            # List vectors (requires v2 API)
            results = self._index.list(namespace=namespace, limit=100)

            for vector_id in results.get("vectors", []):
                # Fetch each vector
                fetch_result = self._index.fetch(ids=[vector_id], namespace=namespace)
                if fetch_result.get("vectors"):
                    vector_data = fetch_result["vectors"][0]
                    metadata = vector_data.get("metadata", {})
                    content = metadata.get("content", "")

                    doc = LoadedDocument(
                        content=content,
                        metadata=metadata,
                        source="pinecone",
                        source_id=vector_id,
                        filename=metadata.get("filename", vector_id),
                        mime_type=metadata.get("mime_type", "text/plain"),
                    )
                    documents.append(doc)

            logger.info(f"Loaded {len(documents)} documents from Pinecone")
        except Exception as e:
            logger.error(f"Error loading Pinecone documents: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search documents by ID prefix or metadata.

        Args:
            query: Search term (ID prefix)
            max_results: Maximum results

        Returns:
            Matching documents
        """
        if not self._index:
            return []

        documents = []
        try:
            # List with filter prefix
            results = self._index.list(prefix=query, limit=max_results)

            for vector_id in results.get("vectors", []):
                fetch_result = self._index.fetch(ids=[vector_id])
                if fetch_result.get("vectors"):
                    vector_data = fetch_result["vectors"][0]
                    metadata = vector_data.get("metadata", {})
                    content = metadata.get("content", "")

                    doc = LoadedDocument(
                        content=content,
                        metadata=metadata,
                        source="pinecone",
                        source_id=vector_id,
                        filename=metadata.get("filename", vector_id),
                        mime_type=metadata.get("mime_type", "text/plain"),
                    )
                    documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching Pinecone: {e}")

        return documents


class WeaviateLoader(BaseLoader):
    """Load documents from Weaviate vector database.

    Example:
        loader = WeaviateLoader(
            url="http://localhost:8080",
            api_key="your-api-key",
            class_name="Document"
        )
        docs = loader.load_folder("documents")
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        class_name: str = "Document",
    ):
        """Initialize Weaviate loader.

        Args:
            url: Weaviate URL
            api_key: API key (optional)
            class_name: Weaviate class name
        """
        if not WEAVIATE_AVAILABLE:
            raise ImportError(
                "weaviate-client package is required. Install with: pip install weaviate-client"
            )

        self.url = url or os.environ.get("WEAVIATE_URL", "http://localhost:8080")
        self.api_key = api_key or os.environ.get("WEAVIATE_API_KEY")
        self.class_name = class_name
        self._client = None

    def source_name(self) -> str:
        return "weaviate"

    def authenticate(self) -> bool:
        """Connect to Weaviate."""
        try:
            auth = None
            if self.api_key:
                auth = weaviate.auth.ApiKey(api_key=self.api_key)

            self._client = weaviate.Client(url=self.url, auth_client_secret=auth)
            self._client.schema.get()  # Test connection
            logger.info(f"Connected to Weaviate at {self.url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Weaviate: {e}")
            return False

    def close(self) -> None:
        """Close Weaviate connection."""
        if self._client:
            self._client.close()

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single Weaviate object.

        Args:
            doc_id: Object ID

        Returns:
            Loaded document
        """
        if not self._client:
            return None

        try:
            obj = self._client.data_object.get_by_id(
                uuid=doc_id, class_name=self.class_name
            )

            if not obj:
                return None

            properties = obj.get("properties", {})
            content = properties.get("content", "")

            return LoadedDocument(
                content=content,
                metadata=properties,
                source="weaviate",
                source_id=doc_id,
                filename=properties.get("filename", doc_id),
                mime_type=properties.get("mime_type", "text/plain"),
            )
        except Exception as e:
            logger.error(f"Error loading Weaviate object: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all objects from Weaviate class.

        Args:
            folder_path: Unused
            recursive: Unused

        Returns:
            List of documents
        """
        if not self._client:
            return []

        documents = []
        try:
            query = (
                self._client.query.get(self.class_name, ["content", "filename"])
                .with_limit(1000)
                .do()
            )

            objects = query.get("data", {}).get("Get", {}).get(self.class_name, [])

            for obj in objects:
                content = obj.get("content", "")

                doc = LoadedDocument(
                    content=content,
                    metadata=obj,
                    source="weaviate",
                    source_id=obj.get("_additional", {}).get("id"),
                    filename=obj.get("filename", "document"),
                    mime_type=obj.get("mime_type", "text/plain"),
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Weaviate objects")
        except Exception as e:
            logger.error(f"Error loading Weaviate objects: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Weaviate objects by text.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching documents
        """
        if not self._client:
            return []

        documents = []
        try:
            result = (
                self._client.query.get(self.class_name, ["content", "filename"])
                .with_text_by_fuzzy(query)
                .with_limit(max_results)
                .do()
            )

            objects = result.get("data", {}).get("Get", {}).get(self.class_name, [])

            for obj in objects:
                content = obj.get("content", "")

                doc = LoadedDocument(
                    content=content,
                    metadata=obj,
                    source="weaviate",
                    source_id=obj.get("_additional", {}).get("id"),
                    filename=obj.get("filename", "document"),
                    mime_type=obj.get("mime_type", "text/plain"),
                )
                documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching Weaviate: {e}")

        return documents


class QdrantLoader(BaseLoader):
    """Load documents from Qdrant vector database.

    Example:
        loader = QdrantLoader(
            url="http://localhost:6333",
            api_key="your-api-key",
            collection_name="documents"
        )
        docs = loader.load_folder("collection")
    """

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: str = "documents",
    ):
        """Initialize Qdrant loader.

        Args:
            url: Qdrant URL
            api_key: API key
            collection_name: Collection name
        """
        if not QDRANT_AVAILABLE:
            raise ImportError(
                "qdrant-client package is required. Install with: pip install qdrant-client"
            )

        self.url = url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.api_key = api_key or os.environ.get("QDRANT_API_KEY")
        self.collection_name = collection_name
        self._client = None

    def source_name(self) -> str:
        return "qdrant"

    def authenticate(self) -> bool:
        """Connect to Qdrant."""
        try:
            self._client = QdrantClient(url=self.url, api_key=self.api_key)
            self._client.get_collections()  # Test connection
            logger.info(f"Connected to Qdrant at {self.url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            return False

    def close(self) -> None:
        """Close Qdrant connection."""
        if self._client:
            self._client.close()

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a point by ID.

        Args:
            doc_id: Point ID

        Returns:
            Loaded document
        """
        if not self._client:
            return None

        try:
            point = self._client.retrieve(
                collection_name=self.collection_name, ids=[int(doc_id)]
            )

            if not point:
                return None

            payload = point[0].payload
            content = payload.get("content", "")

            return LoadedDocument(
                content=content,
                metadata=payload,
                source="qdrant",
                source_id=doc_id,
                filename=payload.get("filename", doc_id),
                mime_type=payload.get("mime_type", "text/plain"),
            )
        except Exception as e:
            logger.error(f"Error loading Qdrant point: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all points from collection.

        Args:
            folder_path: Unused
            recursive: Unused

        Returns:
            List of documents
        """
        if not self._client:
            return []

        documents = []
        try:
            # Scroll through collection
            points, _ = self._client.scroll(
                collection_name=self.collection_name, limit=100
            )

            for point in points:
                payload = point.payload
                content = payload.get("content", "")

                doc = LoadedDocument(
                    content=content,
                    metadata=payload,
                    source="qdrant",
                    source_id=str(point.id),
                    filename=payload.get("filename", str(point.id)),
                    mime_type=payload.get("mime_type", "text/plain"),
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Qdrant points")
        except Exception as e:
            logger.error(f"Error loading Qdrant collection: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search points by payload filter.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching documents
        """
        if not self._client:
            return []

        documents = []
        try:
            # Search for text in content field
            logger.warning("Qdrant search requires vector embedding")
        except Exception as e:
            logger.error(f"Error searching Qdrant: {e}")

        return documents


class ChromaLoader(BaseLoader):
    """Load documents from ChromaDB (embedded vector DB).

    Example:
        loader = ChromaLoader(
            persist_directory="./chroma_data",
            collection_name="documents"
        )
        docs = loader.load_folder("collection")
    """

    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = "documents",
    ):
        """Initialize ChromaDB loader.

        Args:
            persist_directory: Directory for persistent storage
            collection_name: Collection name
        """
        if not CHROMA_AVAILABLE:
            raise ImportError(
                "chromadb package is required. Install with: pip install chromadb"
            )

        self.persist_directory = persist_directory or "./chroma_data"
        self.collection_name = collection_name
        self._client = None
        self._collection = None

    def source_name(self) -> str:
        return "chroma"

    def authenticate(self) -> bool:
        """Initialize ChromaDB client."""
        try:
            self._client = chromadb.PersistentClient(path=self.persist_directory)
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name
            )
            logger.info(f"Connected to ChromaDB at {self.persist_directory}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            return False

    def close(self) -> None:
        """Close ChromaDB connection."""
        if self._client:
            try:
                self._client = None
            except Exception as e:
                logger.error(f"Error closing ChromaDB: {e}")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Loaded document
        """
        if not self._collection:
            return None

        try:
            result = self._collection.get(ids=[doc_id])

            if not result["ids"]:
                return None

            metadata = result["metadatas"][0] if result["metadatas"] else {}
            documents = result["documents"]
            content = documents[0] if documents else ""

            return LoadedDocument(
                content=content,
                metadata=metadata,
                source="chroma",
                source_id=doc_id,
                filename=metadata.get("filename", doc_id),
                mime_type=metadata.get("mime_type", "text/plain"),
            )
        except Exception as e:
            logger.error(f"Error loading ChromaDB document: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from collection.

        Args:
            folder_path: Unused
            recursive: Unused

        Returns:
            List of documents
        """
        if not self._collection:
            return []

        documents = []
        try:
            result = self._collection.get()

            for i, doc_id in enumerate(result["ids"]):
                content = result["documents"][i] if i < len(result["documents"]) else ""
                metadata = (
                    result["metadatas"][i] if i < len(result["metadatas"]) else {}
                )

                doc = LoadedDocument(
                    content=content,
                    metadata=metadata,
                    source="chroma",
                    source_id=doc_id,
                    filename=metadata.get("filename", doc_id),
                    mime_type=metadata.get("mime_type", "text/plain"),
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} ChromaDB documents")
        except Exception as e:
            logger.error(f"Error loading ChromaDB collection: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search documents by content.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching documents
        """
        if not self._collection:
            return []

        documents = []
        try:
            result = self._collection.query(query_texts=[query], n_results=max_results)

            for i, doc_id in enumerate(result["ids"][0]):
                content = (
                    result["documents"][0][i] if i < len(result["documents"][0]) else ""
                )
                metadata = (
                    result["metadatas"][0][i] if i < len(result["metadatas"][0]) else {}
                )

                doc = LoadedDocument(
                    content=content,
                    metadata=metadata,
                    source="chroma",
                    source_id=doc_id,
                    filename=metadata.get("filename", doc_id),
                    mime_type=metadata.get("mime_type", "text/plain"),
                )
                documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching ChromaDB: {e}")

        return documents


class MilvusLoader(BaseLoader):
    """Load documents from Milvus vector database.

    Example:
        loader = MilvusLoader(
            host="localhost",
            port=19530,
            collection_name="documents"
        )
        docs = loader.load_folder("collection")
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 19530,
        collection_name: str = "documents",
        db_name: str = "default",
    ):
        """Initialize Milvus loader.

        Args:
            host: Milvus host
            port: Milvus port
            collection_name: Collection name
            db_name: Database name
        """
        if not MILVUS_AVAILABLE:
            raise ImportError(
                "pymilvus package is required. Install with: pip install pymilvus"
            )

        self.host = host or os.environ.get("MILVUS_HOST", "localhost")
        self.port = port
        self.collection_name = collection_name
        self.db_name = db_name
        self._collection = None

    def source_name(self) -> str:
        return "milvus"

    def authenticate(self) -> bool:
        """Connect to Milvus."""
        try:
            connections.connect("default", host=self.host, port=self.port)

            self._collection = Collection(self.collection_name)
            logger.info(f"Connected to Milvus at {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            return False

    def close(self) -> None:
        """Close Milvus connection."""
        try:
            connections.disconnect()
        except Exception as e:
            logger.error(f"Error closing Milvus: {e}")

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a document by ID.

        Args:
            doc_id: Document ID

        Returns:
            Loaded document
        """
        if not self._collection:
            return None

        try:
            # Load from Milvus (simplified)
            logger.warning("Individual document loading requires query implementation")
            return None
        except Exception as e:
            logger.error(f"Error loading Milvus document: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from collection.

        Args:
            folder_path: Unused
            recursive: Unused

        Returns:
            List of documents
        """
        if not self._collection:
            return []

        documents = []
        try:
            # Load all entities
            self._collection.load()
            entities = self._collection.query(expr="", output_fields=["*"])

            for entity in entities:
                doc = LoadedDocument(
                    content=str(entity),
                    metadata=entity,
                    source="milvus",
                    source_id=str(entity.get("id", "")),
                    filename=f"document_{entity.get('id')}",
                    mime_type="text/plain",
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} Milvus documents")
        except Exception as e:
            logger.error(f"Error loading Milvus collection: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search Milvus collection.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            Matching documents
        """
        if not self._collection:
            return []

        documents = []
        try:
            logger.warning("Search requires vector embedding")
        except Exception as e:
            logger.error(f"Error searching Milvus: {e}")

        return documents


__all__ = [
    "PineconeLoader",
    "WeaviateLoader",
    "QdrantLoader",
    "ChromaLoader",
    "MilvusLoader",
    "PINECONE_AVAILABLE",
    "WEAVIATE_AVAILABLE",
    "QDRANT_AVAILABLE",
    "CHROMA_AVAILABLE",
    "MILVUS_AVAILABLE",
]
