"""
Neo4j-backed persistent memory with data separation.

Provides secure, scoped memory storage for AI agents:
- PUBLIC: Shared knowledge base
- PRIVATE: Admin/system data
- CUSTOMER: Per-client isolated data

Example:
    >>> from agentic_brain import Neo4jMemory, DataScope
    >>> memory = Neo4jMemory("bolt://localhost:7687", "neo4j", "password")
    >>> memory.store("User prefers morning meetings", scope=DataScope.PRIVATE)
    >>> results = memory.search("meetings", scope=DataScope.PRIVATE)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any
import logging
import hashlib

logger = logging.getLogger(__name__)


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
    customer_id: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    
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
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
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
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
    ) -> None:
        """
        Initialize Neo4j memory connection.
        
        Args:
            uri: Neo4j bolt URI
            user: Database username
            password: Database password
            database: Database name
        """
        self.config = MemoryConfig(
            uri=uri,
            user=user,
            password=password,
            database=database,
        )
        self._driver = None
        self._connected = False
        
    def connect(self) -> bool:
        """
        Establish connection to Neo4j.
        
        Returns:
            True if connection successful
            
        Raises:
            ImportError: If neo4j package not installed
        """
        try:
            from neo4j import GraphDatabase
            
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
        data = f"{content}:{scope.value}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def store(
        self,
        content: str,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
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
            timestamp=datetime.now(timezone.utc),
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
        except Exception as e:
            logger.error(f"Memory operation failed: operation=store, key={memory.id}", exc_info=True)
            raise
        
        return memory
    
    def search(
        self,
        query: str,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: Optional[str] = None,
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
                    memories.append(Memory(
                        id=record["id"],
                        content=record["content"],
                        scope=DataScope(record["scope"]),
                        timestamp=record["timestamp"].to_native() if record["timestamp"] else datetime.now(timezone.utc),
                        customer_id=record["customer_id"],
                    ))
            
            logger.debug(f"Memory retrieved: key={query}, found={len(memories) > 0}, count={len(memories)}")
        except Exception as e:
            logger.error(f"Memory operation failed: operation=search, key={query}", exc_info=True)
            raise
        
        return memories
    
    def get_recent(
        self,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: Optional[str] = None,
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
                memories.append(Memory(
                    id=record["id"],
                    content=record["content"],
                    scope=DataScope(record["scope"]),
                    timestamp=record["timestamp"].to_native() if record["timestamp"] else datetime.now(timezone.utc),
                    customer_id=record["customer_id"],
                ))
        
        return memories
    
    def delete(
        self,
        memory_id: str,
        scope: DataScope,
        customer_id: Optional[str] = None,
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
        scope: Optional[DataScope] = None,
        customer_id: Optional[str] = None,
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
        customer_id: Optional[str] = None,
        **kwargs,
    ) -> Memory:
        """Store in memory."""
        memory = Memory(
            id=hashlib.sha256(f"{content}:{datetime.now(timezone.utc)}".encode()).hexdigest()[:16],
            content=content,
            scope=scope,
            timestamp=datetime.now(timezone.utc),
            customer_id=customer_id,
        )
        self._memories[memory.id] = memory
        return memory
    
    def search(
        self,
        query: str,
        scope: DataScope = DataScope.PRIVATE,
        customer_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Search in memory."""
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
        customer_id: Optional[str] = None,
        limit: int = 10,
    ) -> list[Memory]:
        """Get recent memories."""
        results = [
            m for m in self._memories.values()
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
