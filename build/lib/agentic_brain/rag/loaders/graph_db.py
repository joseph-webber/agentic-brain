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

"""Graph database loaders for RAG pipelines.

Supports:
- Neo4j (property graph database)
- Memgraph (Neo4j-compatible graph database)
"""

import json
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from agentic_brain.core.neo4j_pool import (
    configure_pool as configure_neo4j_pool,
)
from agentic_brain.core.neo4j_pool import (
    get_driver as get_shared_neo4j_driver,
)

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

try:
    import neo4j  # noqa: F401

    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

if TYPE_CHECKING:  # pragma: no cover
    from neo4j import Session  # pylint: disable=ungrouped-imports
else:  # pragma: no cover
    Session = Any


class Neo4jLoader(BaseLoader):
    """Load documents from Neo4j knowledge graph.

    Extracts nodes and relationships as documents, useful for
    knowledge graph augmented generation.

    Example:
        loader = Neo4jLoader(
            uri="neo4j://localhost:7687",
            username="neo4j",
            password="password"
        )
        docs = loader.load_folder("nodes")  # All nodes as documents
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "neo4j",
    ):
        """Initialize Neo4j loader.

        Args:
            uri: Neo4j connection URI (e.g., neo4j://localhost:7687)
            username: Neo4j username
            password: Neo4j password
            database: Database name (default: "neo4j")
        """
        if not NEO4J_AVAILABLE:
            raise ImportError(
                "neo4j package is required. Install with: pip install neo4j"
            )

        self.uri = uri or os.environ.get("NEO4J_URI", "neo4j://localhost:7687")
        self.username = username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "")
        self.database = database
        self._driver = None
        self._session: Optional[Session] = None
        self._using_shared_driver = False

    def source_name(self) -> str:
        return "neo4j"

    def authenticate(self) -> bool:
        """Connect to Neo4j database."""
        try:
            configure_neo4j_pool(
                uri=self.uri,
                user=self.username,
                password=self.password,
                database=self.database,
            )
            self._driver = get_shared_neo4j_driver()
            self._session = self._driver.session(database=self.database)
            self._session.run("RETURN 1")
            self._using_shared_driver = True
            logger.info(f"Connected to Neo4j at {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            return False

    def close(self) -> None:
        """Close Neo4j connection."""
        if self._session:
            self._session.close()
        if self._driver and not self._using_shared_driver:
            self._driver.close()
        self._driver = None
        self._using_shared_driver = False

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single node by ID."""
        if not self._session:
            return None

        try:
            query = """
            MATCH (n)
            WHERE id(n) = $node_id
            RETURN n as node
            """
            result = self._session.run(query, node_id=int(doc_id))
            record = result.single()

            if not record:
                return None

            node = record["node"]
            content = self._node_to_text(node)

            return LoadedDocument(
                content=content,
                metadata=dict(node),
                source="neo4j",
                source_id=str(id(node)),
                filename=f"node_{doc_id}",
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading node {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all nodes as documents.

        Args:
            folder_path: Unused, loads all nodes in database
            recursive: Unused

        Returns:
            List of documents, one per node
        """
        if not self._session:
            return []

        documents = []
        try:
            query = "MATCH (n) RETURN n as node LIMIT 1000"
            result = self._session.run(query)

            for record in result:
                node = record["node"]
                content = self._node_to_text(node)

                doc = LoadedDocument(
                    content=content,
                    metadata=dict(node),
                    source="neo4j",
                    source_id=str(id(node)),
                    filename=f"node_{id(node)}",
                    mime_type="text/plain",
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} nodes from Neo4j")
        except Exception as e:
            logger.error(f"Error loading nodes: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search nodes using Cypher-like query.

        Args:
            query: Free text search (searches all string properties)
            max_results: Maximum results to return

        Returns:
            List of matching documents
        """
        if not self._session:
            return []

        documents = []
        try:
            cypher_query = """
            MATCH (n)
            WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS $query)
            RETURN n as node
            LIMIT $limit
            """
            result = self._session.run(cypher_query, query=query, limit=max_results)

            for record in result:
                node = record["node"]
                content = self._node_to_text(node)

                doc = LoadedDocument(
                    content=content,
                    metadata=dict(node),
                    source="neo4j",
                    source_id=str(id(node)),
                    filename=f"node_{id(node)}",
                    mime_type="text/plain",
                )
                documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching nodes: {e}")

        return documents

    @staticmethod
    def _node_to_text(node) -> str:
        """Convert Neo4j node to text representation."""
        labels = ":".join(node.labels) if hasattr(node, "labels") else "Node"
        properties = dict(node) if hasattr(node, "items") else {}

        lines = [f"Node [{labels}]"]
        for key, value in properties.items():
            lines.append(f"  {key}: {value}")

        return "\n".join(lines)


class MemgraphLoader(BaseLoader):
    """Load documents from Memgraph (Neo4j-compatible graph database).

    Memgraph is an in-memory graph database with Neo4j protocol support.

    Example:
        loader = MemgraphLoader(
            host="localhost",
            port=7687,
            database="memgraph"
        )
        docs = loader.load_folder("nodes")
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: int = 7687,
        username: Optional[str] = None,
        password: Optional[str] = None,
        database: str = "memgraph",
    ):
        """Initialize Memgraph loader.

        Args:
            host: Memgraph host
            port: Memgraph port (default: 7687)
            username: Username (optional)
            password: Password (optional)
            database: Database name (default: "memgraph")
        """
        if not NEO4J_AVAILABLE:
            raise ImportError(
                "neo4j package is required. Install with: pip install neo4j"
            )

        self.host = host or os.environ.get("MEMGRAPH_HOST", "localhost")
        self.port = port
        self.username = username or os.environ.get("MEMGRAPH_USERNAME")
        self.password = password or os.environ.get("MEMGRAPH_PASSWORD")
        self.database = database

        # Construct URI
        self.uri = f"neo4j://{self.host}:{self.port}"

        self._driver = None
        self._session: Optional[Session] = None

    def source_name(self) -> str:
        return "memgraph"

    def authenticate(self) -> bool:
        """Connect to Memgraph database."""
        try:
            from neo4j import GraphDatabase

            auth = None
            if self.username and self.password:
                auth = (self.username, self.password)

            self._driver = GraphDatabase.driver(self.uri, auth=auth)
            self._driver.verify_connectivity()
            self._session = self._driver.session()
            logger.info(f"Connected to Memgraph at {self.uri}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Memgraph: {e}")
            return False

    def close(self) -> None:
        """Close Memgraph connection."""
        if self._session:
            self._session.close()
        if self._driver:
            self._driver.close()

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single node by ID."""
        if not self._session:
            return None

        try:
            query = """
            MATCH (n)
            WHERE id(n) = $node_id
            RETURN n as node
            """
            result = self._session.run(query, node_id=int(doc_id))
            record = result.single()

            if not record:
                return None

            node = record["node"]
            content = self._node_to_text(node)

            return LoadedDocument(
                content=content,
                metadata=dict(node) if hasattr(node, "items") else {},
                source="memgraph",
                source_id=str(id(node)),
                filename=f"node_{doc_id}",
                mime_type="text/plain",
            )
        except Exception as e:
            logger.error(f"Error loading node {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all nodes as documents.

        Args:
            folder_path: Unused, loads all nodes
            recursive: Unused

        Returns:
            List of documents, one per node
        """
        if not self._session:
            return []

        documents = []
        try:
            query = "MATCH (n) RETURN n as node LIMIT 1000"
            result = self._session.run(query)

            for record in result:
                node = record["node"]
                content = self._node_to_text(node)

                doc = LoadedDocument(
                    content=content,
                    metadata=dict(node) if hasattr(node, "items") else {},
                    source="memgraph",
                    source_id=str(id(node)),
                    filename=f"node_{id(node)}",
                    mime_type="text/plain",
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} nodes from Memgraph")
        except Exception as e:
            logger.error(f"Error loading nodes: {e}")

        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search nodes by property value.

        Args:
            query: Search term
            max_results: Maximum results

        Returns:
            List of matching documents
        """
        if not self._session:
            return []

        documents = []
        try:
            cypher_query = """
            MATCH (n)
            WHERE any(prop IN keys(n) WHERE toString(n[prop]) CONTAINS $query)
            RETURN n as node
            LIMIT $limit
            """
            result = self._session.run(cypher_query, query=query, limit=max_results)

            for record in result:
                node = record["node"]
                content = self._node_to_text(node)

                doc = LoadedDocument(
                    content=content,
                    metadata=dict(node) if hasattr(node, "items") else {},
                    source="memgraph",
                    source_id=str(id(node)),
                    filename=f"node_{id(node)}",
                    mime_type="text/plain",
                )
                documents.append(doc)

        except Exception as e:
            logger.error(f"Error searching nodes: {e}")

        return documents

    @staticmethod
    def _node_to_text(node) -> str:
        """Convert Memgraph node to text representation."""
        labels = ":".join(node.labels) if hasattr(node, "labels") else "Node"
        properties = dict(node) if hasattr(node, "items") else {}

        lines = [f"Node [{labels}]"]
        for key, value in properties.items():
            lines.append(f"  {key}: {value}")

        return "\n".join(lines)


__all__ = [
    "Neo4jLoader",
    "MemgraphLoader",
    "NEO4J_AVAILABLE",
]
