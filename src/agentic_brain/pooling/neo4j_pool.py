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
Neo4j connection pool implementation.

Provides connection pooling for Neo4j with:
- Configurable pool size
- Connection health checks
- Graceful shutdown
- Connection metrics

Example:
    >>> from agentic_brain.pooling import Neo4jPool, Neo4jPoolConfig
    >>>
    >>> config = Neo4jPoolConfig(
    ...     uri="bolt://localhost:7687",
    ...     user="neo4j",
    ...     password="password",
    ...     max_connections=50
    ... )
    >>> pool = Neo4jPool(config)
    >>> await pool.startup()
    >>>
    >>> async with pool.acquire() as conn:
    ...     result = await conn.run("MATCH (n) RETURN count(n)")
    >>>
    >>> await pool.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False


@dataclass
class Neo4jPoolConfig:
    """
    Configuration for Neo4j connection pool.

    Attributes:
        uri: Neo4j bolt URI
        user: Database username
        password: Database password
        database: Database name
        max_connections: Maximum number of connections in pool
        min_connections: Minimum idle connections to maintain
        connection_timeout: Timeout for acquiring a connection (seconds)
        max_lifetime: Maximum lifetime of a connection (seconds)
        acquisition_timeout: Timeout for connection acquisition (seconds)

    Environment Variables:
        NEO4J_URI: Override uri
        NEO4J_USER: Override user
        NEO4J_PASSWORD: Override password
        NEO4J_POOL_SIZE: Override max_connections
        CONNECTION_TIMEOUT: Override connection_timeout
    """

    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    max_connections: int = 50
    min_connections: int = 5
    connection_timeout: float = 30.0
    max_lifetime: float = 3600.0
    acquisition_timeout: float = 30.0

    def __post_init__(self) -> None:
        """Load from environment variables if set."""
        self.uri = os.environ.get("NEO4J_URI", self.uri)
        self.user = os.environ.get("NEO4J_USER", self.user)
        self.password = os.environ.get("NEO4J_PASSWORD", self.password)

        if pool_size := os.environ.get("NEO4J_POOL_SIZE"):
            self.max_connections = int(pool_size)

        if timeout := os.environ.get("CONNECTION_TIMEOUT"):
            self.connection_timeout = float(timeout)


@dataclass
class PoolMetrics:
    """
    Connection pool metrics.

    Attributes:
        active_connections: Number of currently active connections
        idle_connections: Number of idle connections in pool
        waiting_requests: Number of requests waiting for a connection
        total_acquisitions: Total number of connection acquisitions
        total_releases: Total number of connection releases
        failed_acquisitions: Number of failed acquisition attempts
        average_acquisition_time: Average time to acquire a connection (ms)
    """

    active_connections: int = 0
    idle_connections: int = 0
    waiting_requests: int = 0
    total_acquisitions: int = 0
    total_releases: int = 0
    failed_acquisitions: int = 0
    average_acquisition_time: float = 0.0
    _acquisition_times: list[float] = field(default_factory=list)

    def record_acquisition(self, duration_ms: float) -> None:
        """Record a connection acquisition."""
        self._acquisition_times.append(duration_ms)
        self.total_acquisitions += 1
        # Keep only last 1000 measurements
        if len(self._acquisition_times) > 1000:
            self._acquisition_times = self._acquisition_times[-1000:]
        self.average_acquisition_time = sum(self._acquisition_times) / len(
            self._acquisition_times
        )


class Neo4jConnection:
    """
    Wrapper for a Neo4j connection from the pool.

    Provides async-compatible methods for running queries.
    """

    def __init__(self, driver: Any, database: str, pool: Neo4jPool) -> None:
        """Initialize connection wrapper."""
        self._driver = driver
        self._database = database
        self._pool = pool
        self._session = None
        self._created_at = time.time()

    @property
    def age(self) -> float:
        """Return connection age in seconds."""
        return time.time() - self._created_at

    async def run(self, query: str, parameters: dict | None = None) -> list[dict]:
        """
        Run a Cypher query.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        loop = asyncio.get_event_loop()

        def _run_sync():
            with self._driver.session(database=self._database) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]

        return await loop.run_in_executor(None, _run_sync)

    async def execute_write(self, query: str, parameters: dict | None = None) -> Any:
        """
        Execute a write transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            Transaction result
        """
        loop = asyncio.get_event_loop()

        def _write_sync():
            with self._driver.session(database=self._database) as session:

                def _tx(tx):
                    result = tx.run(query, parameters or {})
                    return result.consume()

                return session.execute_write(_tx)

        return await loop.run_in_executor(None, _write_sync)

    async def execute_read(
        self, query: str, parameters: dict | None = None
    ) -> list[dict]:
        """
        Execute a read transaction.

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        loop = asyncio.get_event_loop()

        def _read_sync():
            with self._driver.session(database=self._database) as session:

                def _tx(tx):
                    result = tx.run(query, parameters or {})
                    return [dict(record) for record in result]

                return session.execute_read(_tx)

        return await loop.run_in_executor(None, _read_sync)

    def is_valid(self, max_lifetime: float) -> bool:
        """Check if connection is still valid."""
        return self.age < max_lifetime


class Neo4jPool:
    """
    Connection pool for Neo4j.

    Manages a pool of Neo4j connections with configurable size,
    health checks, and graceful shutdown.

    Features:
    - Configurable pool size (min/max connections)
    - Connection health checking
    - Automatic connection recycling
    - Metrics tracking
    - Graceful shutdown

    Example:
        >>> pool = Neo4jPool(Neo4jPoolConfig(
        ...     uri="bolt://localhost:7687",
        ...     user="neo4j",
        ...     password="password"
        ... ))
        >>> await pool.startup()
        >>>
        >>> async with pool.acquire() as conn:
        ...     result = await conn.run("MATCH (n) RETURN n LIMIT 10")
        >>>
        >>> print(pool.metrics)
        >>> await pool.shutdown()
    """

    def __init__(self, config: Neo4jPoolConfig | None = None) -> None:
        """
        Initialize the connection pool.

        Args:
            config: Pool configuration (uses defaults if not provided)
        """
        self.config = config or Neo4jPoolConfig()
        self._driver = None
        self._pool: asyncio.Queue[Neo4jConnection] = asyncio.Queue(
            maxsize=self.config.max_connections
        )
        self._active_connections: set[Neo4jConnection] = set()
        self._metrics = PoolMetrics()
        self._started = False
        self._shutdown = False
        self._lock = asyncio.Lock()
        self._waiting_count = 0
        self._semaphore: asyncio.BoundedSemaphore | None = None

    def _create_connection(self) -> Neo4jConnection:
        """Create a new connection wrapper."""
        if not self._driver:
            raise RuntimeError("Neo4j driver not initialized")
        return Neo4jConnection(self._driver, self.config.database, self)

    @property
    def metrics(self) -> PoolMetrics:
        """Get current pool metrics."""
        self._metrics.active_connections = len(self._active_connections)
        self._metrics.idle_connections = self._pool.qsize()
        self._metrics.waiting_requests = self._waiting_count
        return self._metrics

    @property
    def is_started(self) -> bool:
        """Check if pool is started."""
        return self._started and not self._shutdown

    async def startup(self) -> None:
        """
        Start the connection pool.

        Creates the Neo4j driver and pre-warms the pool with
        minimum connections.

        Raises:
            RuntimeError: If pool already started
            ImportError: If neo4j package not installed
        """
        if self._started:
            logger.warning("Neo4j pool already started")
            return

        if not NEO4J_AVAILABLE or GraphDatabase is None:
            logger.error("neo4j package not installed. Run: pip install neo4j")
            raise ImportError("neo4j package not installed")

        logger.info(
            f"Starting Neo4j pool: uri={self.config.uri}, max_connections={self.config.max_connections}"
        )

        # Create driver with pool configuration
        self._driver = GraphDatabase.driver(
            self.config.uri,
            auth=(self.config.user, self.config.password),
            max_connection_pool_size=self.config.max_connections,
            connection_timeout=self.config.connection_timeout,
            max_connection_lifetime=int(self.config.max_lifetime),
        )

        # Verify connectivity
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._driver.verify_connectivity)

        # Reset pool/semaphore for a clean start
        self._pool = asyncio.Queue(maxsize=self.config.max_connections)
        self._active_connections.clear()
        self._semaphore = asyncio.BoundedSemaphore(self.config.max_connections)

        # Pre-warm pool with minimum connections
        min_connections = min(self.config.min_connections, self.config.max_connections)
        for _ in range(min_connections):
            try:
                self._pool.put_nowait(self._create_connection())
            except asyncio.QueueFull:
                break

        self._started = True
        logger.info("Neo4j pool started successfully")

    async def shutdown(self) -> None:
        """
        Shutdown the connection pool gracefully.

        Closes all connections and releases resources.
        """
        if not self._started or self._shutdown:
            return

        logger.info("Shutting down Neo4j pool...")
        self._shutdown = True

        # Clear pool
        while not self._pool.empty():
            try:
                self._pool.get_nowait()
            except asyncio.QueueEmpty:
                break

        # Clear active connections
        self._active_connections.clear()

        # Close driver
        if self._driver:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._driver.close)
            self._driver = None

        self._started = False
        self._semaphore = None
        logger.info("Neo4j pool shutdown complete")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[Neo4jConnection, None]:
        """
        Acquire a connection from the pool.

        Yields:
            Neo4jConnection: A connection wrapper for running queries

        Raises:
            RuntimeError: If pool not started or shutting down
            TimeoutError: If acquisition timeout exceeded

        Example:
            >>> async with pool.acquire() as conn:
            ...     result = await conn.run("MATCH (n) RETURN n")
        """
        if not self._started or self._shutdown:
            raise RuntimeError("Pool not started or shutting down")

        start_time = time.time()
        conn: Neo4jConnection | None = None
        acquired = False
        self._waiting_count += 1

        try:
            if self._semaphore is None:
                raise RuntimeError("Pool not started")

            try:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=self.config.acquisition_timeout,
                )
                acquired = True
            except TimeoutError as e:
                raise TimeoutError("Timed out waiting for Neo4j connection") from e

            # Reuse existing connection if available, else create a new one
            while True:
                try:
                    candidate = self._pool.get_nowait()
                except asyncio.QueueEmpty:
                    candidate = None

                if candidate and not candidate.is_valid(self.config.max_lifetime):
                    candidate = None
                    continue

                conn = candidate or self._create_connection()
                break

            self._active_connections.add(conn)
            duration_ms = (time.time() - start_time) * 1000
            self._metrics.record_acquisition(duration_ms)

            logger.debug(f"Connection acquired: active={len(self._active_connections)}")

        except Exception as e:
            self._metrics.failed_acquisitions += 1
            logger.error(f"Connection acquisition failed: {e}")
            if acquired and self._semaphore:
                self._semaphore.release()
            self._waiting_count -= 1
            raise

        try:
            yield conn
        finally:
            self._waiting_count -= 1
            if conn:
                self._active_connections.discard(conn)
                self._metrics.total_releases += 1
                if not self._shutdown and conn.is_valid(self.config.max_lifetime):
                    try:
                        self._pool.put_nowait(conn)
                    except asyncio.QueueFull:
                        pass
                logger.debug(
                    f"Connection released: active={len(self._active_connections)}"
                )
            if acquired and self._semaphore:
                self._semaphore.release()

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the pool.

        Returns:
            Health status dictionary with:
            - healthy: Overall health status
            - connected: Whether connected to Neo4j
            - pool_size: Current pool size
            - active: Active connections
            - metrics: Pool metrics
        """
        if not self._started or self._shutdown:
            return {
                "healthy": False,
                "connected": False,
                "pool_size": 0,
                "active": 0,
                "error": "Pool not started",
            }

        try:
            async with self.acquire() as conn:
                await conn.run("RETURN 1 as health")

            return {
                "healthy": True,
                "connected": True,
                "pool_size": self.config.max_connections,
                "active": len(self._active_connections),
                "idle": self._pool.qsize(),
                "metrics": {
                    "total_acquisitions": self._metrics.total_acquisitions,
                    "total_releases": self._metrics.total_releases,
                    "failed_acquisitions": self._metrics.failed_acquisitions,
                    "avg_acquisition_ms": round(
                        self._metrics.average_acquisition_time, 2
                    ),
                },
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "healthy": False,
                "connected": False,
                "error": str(e),
            }


# Fallback for when pool is not configured
class DirectNeo4jConnection:
    """
    Direct Neo4j connection without pooling.

    Use this as a fallback when pooling is not needed or configured.

    Example:
        >>> conn = DirectNeo4jConnection(
        ...     uri="bolt://localhost:7687",
        ...     user="neo4j",
        ...     password="password"
        ... )
        >>> await conn.run("MATCH (n) RETURN n")
        >>> conn.close()
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        user: str = "neo4j",
        password: str = "",
        database: str = "neo4j",
    ) -> None:
        """Initialize direct connection."""
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver = None

    def connect(self) -> None:
        """Establish connection."""
        if not NEO4J_AVAILABLE or GraphDatabase is None:
            raise ImportError("neo4j package is required. Install with: pip install neo4j")

        self._driver = GraphDatabase.driver(
            self._uri,
            auth=(self._user, self._password),
        )

    async def run(self, query: str, parameters: dict | None = None) -> list[dict]:
        """Run a query."""
        if not self._driver:
            self.connect()

        loop = asyncio.get_event_loop()

        def _run_sync():
            with self._driver.session(database=self._database) as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]

        return await loop.run_in_executor(None, _run_sync)

    def close(self) -> None:
        """Close connection."""
        if self._driver:
            self._driver.close()
            self._driver = None
