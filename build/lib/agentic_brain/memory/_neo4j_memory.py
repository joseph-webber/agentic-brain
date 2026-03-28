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

"""
Neo4j-backed persistent memory with data separation.

Provides secure, scoped memory storage for AI agents:
- PUBLIC: Shared knowledge base
- PRIVATE: Admin/system data
- CUSTOMER: Per-client isolated data

Example:
    >>> from agentic_brain import Neo4jMemory, DataScope
    >>> memory = Neo4jMemory()  # Uses env vars for connection
    >>> memory.store("User prefers morning meetings", scope=DataScope.PRIVATE)
    >>> results = memory.search("meetings", scope=DataScope.PRIVATE)
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False

from agentic_brain.core.neo4j_pool import (
    configure_pool as configure_neo4j_pool,
)
from agentic_brain.core.neo4j_pool import (
    get_driver as get_shared_neo4j_driver,
)


class DataScope(Enum):
    """
    Data separation scopes for multi-tenant security.

    Attributes:
        PUBLIC: Shared knowledge accessible to all
        PRIVATE: Admin/system data (internal use only)
        CUSTOMER: Per-client isolated data (B2B)

    Example:
        >>> memory.store("API docs", scope=DataScope.PUBLIC)
        >>> memory.store("Admin notes", scope=DataScope.PRIVATE)
        >>> memory.store("Client config", scope=DataScope.CUSTOMER, customer_id="acme")
    """

    PUBLIC = "public"
    PRIVATE = "private"
    CUSTOMER = "customer"


@dataclass
class Memory:
    """A single memory entry."""

    id: str
    content: str
    scope: DataScope
    timestamp: datetime
    customer_id: str | None = None
    metadata: dict = field(default_factory=dict)
    embedding: list[float] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "id": self.id,
            "content": self.content,
            "scope": self.scope.value,
            "timestamp": self.timestamp.isoformat(),
            "customer_id": self.customer_id,
            "metadata": self.metadata,
        }


@dataclass
class MemoryConfig:
    """Memory system configuration."""

    uri: str = field(
        default_factory=lambda: os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    )
    user: str = field(default_factory=lambda: os.environ.get("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.environ.get("NEO4J_PASSWORD", ""))
    database: str = "neo4j"
    embedding_dim: int = 384
    max_results: int = 10


class Neo4jMemory:
    """
    Persistent memory backed by Neo4j graph database.

    Features:
    - Scoped data separation (public/private/customer)
    - Vector similarity search (when embeddings available)
    - Relationship tracking between memories
    - Automatic timestamping

    Example:
        >>> memory = Neo4jMemory(
        ...     uri="bolt://localhost:7687",
        ...     user="neo4j",
        ...     password="your-password"
        ... )
        >>>
        >>> # Store memories with different scopes
        >>> memory.store("Python best practices", scope=DataScope.PUBLIC)
        >>> memory.store("Internal API keys", scope=DataScope.PRIVATE)
        >>> memory.store("Acme Corp preferences",
        ...              scope=DataScope.CUSTOMER,
        ...              customer_id="acme")
        >>>
        >>> # Search within scope
        >>> results = memory.search("python", scope=DataScope.PUBLIC)
        >>>
        >>> # Customer data is isolated
        >>> acme_data = memory.search("preferences",
        ...                           scope=DataScope.CUSTOMER,
        ...                           customer_id="acme")
    """

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
        database: str = "neo4j",
        use_pool: bool = True,
    ) -> None:
        """
        Initialize Neo4j memory connection.

        Args:
            uri: Neo4j bolt URI. Defaults to env NEO4J_URI or bolt://localhost:7687
            user: Database username. Defaults to env NEO4J_USER or neo4j
            password: Database password. Defaults to env NEO4J_PASSWORD
            database: Database name
            use_pool: Use connection pooling (shared driver)
        """
        self.config = MemoryConfig(
            uri=uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            user=user or os.environ.get("NEO4J_USER", "neo4j"),
            password=password or os.environ.get("NEO4J_PASSWORD", ""),
            database=database,
        )
        self._driver = None
        self._connected = False
        self._use_pool = use_pool
        self._using_shared_driver = False

    def connect(self) -> bool:
        """
        Establish connection to Neo4j.

        Returns:
            True if connection successful

        Raises:
            ImportError: If neo4j package not installed
        """
        # Try to use pool if configured
        if self._use_pool:
            try:
                configure_neo4j_pool(
                    uri=self.config.uri,
                    user=self.config.user,
                    password=self.config.password,
                    database=self.config.database,
                )
                self._driver = get_shared_neo4j_driver()
                with self._driver.session(database=self.config.database) as session:
                    session.run("RETURN 1")
                self._connected = True
                self._using_shared_driver = True
                logger.info("Using shared Neo4j connection pool")
                return True
            except Exception as e:
                logger.warning(f"Shared pool not available, falling back: {e}")

        # Fall back to direct connection
        try:
            if not NEO4J_AVAILABLE or GraphDatabase is None:
                raise ImportError

            self._driver = GraphDatabase.driver(
                self.config.uri,
                auth=(self.config.user, self.config.password),
            )

            # Verify connection
            with self._driver.session(database=self.config.database) as session:
                session.run("RETURN 1")

            self._connected = True
            logger.info(f"Connected to Neo4j at {self.config.uri}")
            return True

        except ImportError:
            logger.error("neo4j package not installed. Run: pip install neo4j")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self._connected = False
            return False

    def close(self) -> None:
        """Close Neo4j connection."""
        # Pool connections are managed by PoolManager
        if self._using_shared_driver:
            self._driver = None
            self._using_shared_driver = False
            self._connected = False
            return

        if self._driver:
            self._driver.close()
            self._driver = None
            self._connected = False

    def _ensure_connected(self) -> None:
        """Ensure connection is established."""
        if not self._connected:
            self.connect()

    def _generate_id(self, content: str, scope: DataScope) -> str:
        """Generate unique ID for memory."""
        data = f"{content}:{scope.value}:{datetime.now(UTC).isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def store(
        self,
        content: str,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: str | None = None,
        metadata: dict | None = None,
        embedding: list[float] | None = None,
    ) -> Memory:
        """
        Store a memory with data scope.

        Args:
            content: Memory content to store
            scope: Data scope (PUBLIC, PRIVATE, CUSTOMER)
            customer_id: Required for CUSTOMER scope
            metadata: Additional metadata
            embedding: Vector embedding for similarity search

        Returns:
            Created Memory object

        Raises:
            ValueError: If CUSTOMER scope without customer_id

        Example:
            >>> memory.store("Meeting notes", scope=DataScope.PRIVATE)
            >>> memory.store("Product FAQ", scope=DataScope.PUBLIC)
            >>> memory.store("Client config",
            ...              scope=DataScope.CUSTOMER,
            ...              customer_id="client123")
        """
        if scope == DataScope.CUSTOMER and not customer_id:
            raise ValueError("customer_id required for CUSTOMER scope")

        logger.debug(f"Storing memory: key={content[:50]}..., scope={scope.value}")

        self._ensure_connected()

        memory = Memory(
            id=self._generate_id(content, scope),
            content=content,
            scope=scope,
            timestamp=datetime.now(UTC),
            customer_id=customer_id,
            metadata=metadata or {},
            embedding=embedding,
        )

        # Build Cypher query
        query = """
        CREATE (m:Memory {
            id: $id,
            content: $content,
            scope: $scope,
            timestamp: datetime($timestamp),
            customer_id: $customer_id,
            metadata: $metadata
        })
        RETURN m.id as id
        """

        # Add embedding if provided
        if embedding:
            query = """
            CREATE (m:Memory {
                id: $id,
                content: $content,
                scope: $scope,
                timestamp: datetime($timestamp),
                customer_id: $customer_id,
                metadata: $metadata,
                embedding: $embedding
            })
            RETURN m.id as id
            """

        params = {
            "id": memory.id,
            "content": memory.content,
            "scope": memory.scope.value,
            "timestamp": memory.timestamp.isoformat(),
            "customer_id": memory.customer_id,
            "metadata": str(memory.metadata),
            "embedding": embedding,
        }

        try:
            with self._driver.session(database=self.config.database) as session:
                result = session.run(query, params)
                record = result.single()
                if record:
                    logger.debug(f"Memory stored successfully: key={memory.id}")
        except Exception:
            logger.error(
                f"Memory operation failed: operation=store, key={memory.id}",
                exc_info=True,
            )
            raise

        return memory

    def search(
        self,
        query: str,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """
        Search memories within scope.

        Args:
            query: Search query (substring match)
            scope: Data scope to search within
            customer_id: Required for CUSTOMER scope
            limit: Maximum results to return

        Returns:
            List of matching Memory objects

        Example:
            >>> results = memory.search("meeting", scope=DataScope.PRIVATE)
            >>> for r in results:
            ...     print(r.content)
        """
        if scope == DataScope.CUSTOMER and not customer_id:
            raise ValueError("customer_id required for CUSTOMER scope search")

        logger.debug(f"Retrieving memory: key={query}, scope={scope.value}")

        self._ensure_connected()

        # Scope-filtered search
        cypher = """
        MATCH (m:Memory)
        WHERE m.scope = $scope
        AND toLower(m.content) CONTAINS toLower($query)
        """

        params = {"scope": scope.value, "query": query, "limit": limit}

        # Add customer filter for CUSTOMER scope
        if scope == DataScope.CUSTOMER:
            cypher += " AND m.customer_id = $customer_id"
            params["customer_id"] = customer_id

        cypher += """
        RETURN m.id as id, m.content as content, m.scope as scope,
               m.timestamp as timestamp, m.customer_id as customer_id
        ORDER BY m.timestamp DESC
        LIMIT $limit
        """

        memories = []
        try:
            with self._driver.session(database=self.config.database) as session:
                result = session.run(cypher, params)
                for record in result:
                    memories.append(
                        Memory(
                            id=record["id"],
                            content=record["content"],
                            scope=DataScope(record["scope"]),
                            timestamp=(
                                record["timestamp"].to_native()
                                if record["timestamp"]
                                else datetime.now(UTC)
                            ),
                            customer_id=record["customer_id"],
                        )
                    )

            logger.debug(
                f"Memory retrieved: key={query}, found={len(memories) > 0}, count={len(memories)}"
            )
        except Exception:
            logger.error(
                f"Memory operation failed: operation=search, key={query}", exc_info=True
            )
            raise

        return memories

    def get_recent(
        self,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """
        Get recent memories within scope.

        Args:
            scope: Data scope
            customer_id: Required for CUSTOMER scope
            limit: Maximum results

        Returns:
            List of recent Memory objects
        """
        self._ensure_connected()

        cypher = """
        MATCH (m:Memory)
        WHERE m.scope = $scope
        """

        params = {"scope": scope.value, "limit": limit}

        if scope == DataScope.CUSTOMER:
            if not customer_id:
                raise ValueError("customer_id required for CUSTOMER scope")
            cypher += " AND m.customer_id = $customer_id"
            params["customer_id"] = customer_id

        cypher += """
        RETURN m.id as id, m.content as content, m.scope as scope,
               m.timestamp as timestamp, m.customer_id as customer_id
        ORDER BY m.timestamp DESC
        LIMIT $limit
        """

        memories = []
        with self._driver.session(database=self.config.database) as session:
            result = session.run(cypher, params)
            for record in result:
                memories.append(
                    Memory(
                        id=record["id"],
                        content=record["content"],
                        scope=DataScope(record["scope"]),
                        timestamp=(
                            record["timestamp"].to_native()
                            if record["timestamp"]
                            else datetime.now(UTC)
                        ),
                        customer_id=record["customer_id"],
                    )
                )

        return memories

    def delete(
        self,
        memory_id: str,
        scope: DataScope,
        customer_id: str | None = None,
    ) -> bool:
        """
        Delete a memory by ID (scope-protected).

        Args:
            memory_id: Memory ID to delete
            scope: Must match memory's scope
            customer_id: Required for CUSTOMER scope

        Returns:
            True if deleted
        """
        self._ensure_connected()

        cypher = """
        MATCH (m:Memory {id: $id, scope: $scope})
        """

        params = {"id": memory_id, "scope": scope.value}

        if scope == DataScope.CUSTOMER:
            if not customer_id:
                raise ValueError("customer_id required")
            cypher += " WHERE m.customer_id = $customer_id"
            params["customer_id"] = customer_id

        cypher += " DELETE m RETURN count(m) as deleted"

        with self._driver.session(database=self.config.database) as session:
            result = session.run(cypher, params)
            record = result.single()
            return record and record["deleted"] > 0

    def count(
        self,
        scope: DataScope | None = None,
        customer_id: str | None = None,
    ) -> int:
        """
        Count memories in scope.

        Args:
            scope: Specific scope to count (None for all)
            customer_id: Filter by customer

        Returns:
            Number of memories
        """
        self._ensure_connected()

        cypher = "MATCH (m:Memory)"
        params = {}

        conditions = []
        if scope:
            conditions.append("m.scope = $scope")
            params["scope"] = scope.value
        if customer_id:
            conditions.append("m.customer_id = $customer_id")
            params["customer_id"] = customer_id

        if conditions:
            cypher += " WHERE " + " AND ".join(conditions)

        cypher += " RETURN count(m) as count"

        with self._driver.session(database=self.config.database) as session:
            result = session.run(cypher, params)
            record = result.single()
            return record["count"] if record else 0

    def init_schema(self) -> None:
        """
        Initialize Neo4j schema with indexes.

        Creates indexes for:
        - Memory.id (unique)
        - Memory.scope
        - Memory.customer_id
        - Memory.timestamp
        """
        self._ensure_connected()

        indexes = [
            "CREATE INDEX memory_id IF NOT EXISTS FOR (m:Memory) ON (m.id)",
            "CREATE INDEX memory_scope IF NOT EXISTS FOR (m:Memory) ON (m.scope)",
            "CREATE INDEX memory_customer IF NOT EXISTS FOR (m:Memory) ON (m.customer_id)",
            "CREATE INDEX memory_timestamp IF NOT EXISTS FOR (m:Memory) ON (m.timestamp)",
        ]

        with self._driver.session(database=self.config.database) as session:
            for index in indexes:
                try:
                    session.run(index)
                    logger.debug(f"Created index: {index}")
                except Exception as e:
                    logger.debug(f"Index may already exist: {e}")

        logger.info("Memory schema initialized")


# In-memory fallback when Neo4j unavailable
class InMemoryStore:
    """
    Simple in-memory storage fallback.

    Use when Neo4j is not available. Data is not persistent.

    Example:
        >>> store = InMemoryStore()
        >>> store.store("test", scope=DataScope.PUBLIC)
    """

    def __init__(self) -> None:
        self._memories: dict[str, Memory] = {}

    def store(
        self,
        content: str,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: str | None = None,
        **kwargs,
    ) -> Memory:
        """Store in memory."""
        memory = Memory(
            id=hashlib.sha256(f"{content}:{datetime.now(UTC)}".encode()).hexdigest()[
                :16
            ],
            content=content,
            scope=scope,
            timestamp=datetime.now(UTC),
            customer_id=customer_id,
        )
        self._memories[memory.id] = memory
        return memory

    def search(
        self,
        query: str,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Search in memory."""
        if scope == DataScope.CUSTOMER and not customer_id:
            raise ValueError("customer_id required for CUSTOMER scope search")

        results = []
        query_lower = query.lower()

        for memory in self._memories.values():
            if memory.scope != scope:
                continue
            if scope == DataScope.CUSTOMER and memory.customer_id != customer_id:
                continue
            if query_lower in memory.content.lower():
                results.append(memory)

        return sorted(results, key=lambda m: m.timestamp, reverse=True)[:limit]

    def get_recent(
        self,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: str | None = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Get recent memories."""
        results = [
            m
            for m in self._memories.values()
            if m.scope == scope
            and (scope != DataScope.CUSTOMER or m.customer_id == customer_id)
        ]
        return sorted(results, key=lambda m: m.timestamp, reverse=True)[:limit]

    def connect(self) -> bool:
        """No-op for compatibility."""
        return True

    def close(self) -> None:
        """No-op for compatibility."""
        pass


# Global memory instance (lazy-initialized)
_memory_instance: Neo4jMemory | InMemoryStore | None = None


def get_memory_backend(
    uri: str | None = None,
    user: str | None = None,
    password: str | None = None,
) -> Neo4jMemory | InMemoryStore:
    """
    Get the configured memory backend with automatic fallback.

    This factory function implements the same pattern as Redis sessions:
    - Tries Neo4j first if configured
    - Automatically falls back to InMemoryStore if Neo4j unavailable
    - Logs warnings but doesn't crash on connection failure

    Args:
        uri: Neo4j URI (default: from NEO4J_URI env var)
        user: Neo4j user (default: from NEO4J_USER env var)
        password: Neo4j password (default: from NEO4J_PASSWORD env var)

    Returns:
        Neo4jMemory if Neo4j available, InMemoryStore otherwise

    Environment Variables:
        NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
        NEO4J_USER: Database username (default: neo4j)
        NEO4J_PASSWORD: Database password
        MEMORY_BACKEND: Force backend type ("neo4j" or "memory")

    Example:
        >>> memory = get_memory_backend()
        >>> memory.store("test", scope=DataScope.PUBLIC)
    """
    import os

    global _memory_instance

    if _memory_instance is not None:
        return _memory_instance

    # Check if explicitly set to memory-only
    backend_type = os.getenv("MEMORY_BACKEND", "auto").lower()
    if backend_type == "memory":
        logger.info("Using in-memory backend (MEMORY_BACKEND=memory)")
        _memory_instance = InMemoryStore()
        return _memory_instance

    # Try Neo4j with automatic fallback
    neo4j_uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = user or os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = password or os.getenv("NEO4J_PASSWORD", "")

    try:
        memory = Neo4jMemory(
            uri=neo4j_uri,
            user=neo4j_user,
            password=neo4j_password,
        )
        if memory.connect():
            logger.info(f"Connected to Neo4j memory backend at {neo4j_uri}")
            _memory_instance = memory
            return _memory_instance
        else:
            logger.warning("Neo4j connection failed, falling back to in-memory")
            _memory_instance = InMemoryStore()
            return _memory_instance

    except ImportError:
        logger.warning(
            "neo4j package not installed, using in-memory backend. "
            "Install with: pip install agentic-brain[memory]"
        )
        _memory_instance = InMemoryStore()
        return _memory_instance

    except Exception as e:
        logger.warning(f"Neo4j unavailable ({e}), falling back to in-memory")
        _memory_instance = InMemoryStore()
        return _memory_instance


def reset_memory_backend() -> None:
    """
    Reset the global memory backend instance.

    Useful for testing to ensure a fresh backend.
    """
    global _memory_instance
    if _memory_instance is not None:
        _memory_instance.close()
    _memory_instance = None
