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
Pool manager for unified connection management.

Provides a singleton manager for all connection pools:
- Neo4j connection pool
- HTTP connection pool
- Unified startup/shutdown
- Health aggregation

Example:
    >>> from agentic_brain.pooling import PoolManager
    >>>
    >>> # Initialize on startup
    >>> pool_manager = PoolManager()
    >>> await pool_manager.startup()
    >>>
    >>> # Use Neo4j
    >>> async with pool_manager.neo4j.acquire() as conn:
    ...     result = await conn.run("MATCH (n) RETURN n")
    >>>
    >>> # Use HTTP
    >>> response = await pool_manager.http.get("https://api.example.com")
    >>>
    >>> # Shutdown
    >>> await pool_manager.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Any

from agentic_brain.pooling.http_pool import (
    DirectHttpClient,
    HttpPool,
    HttpPoolConfig,
)
from agentic_brain.pooling.neo4j_pool import (
    DirectNeo4jConnection,
    Neo4jPool,
    Neo4jPoolConfig,
)

logger = logging.getLogger(__name__)

# Global singleton instance
_pool_manager: PoolManager | None = None


@dataclass
class PoolManagerConfig:
    """
    Configuration for pool manager.

    Attributes:
        enable_neo4j: Enable Neo4j pooling
        enable_http: Enable HTTP pooling
        neo4j_config: Neo4j pool configuration
        http_config: HTTP pool configuration

    Environment Variables:
        POOL_ENABLE_NEO4J: Enable/disable Neo4j pooling
        POOL_ENABLE_HTTP: Enable/disable HTTP pooling
    """

    enable_neo4j: bool = True
    enable_http: bool = True
    neo4j_config: Neo4jPoolConfig | None = None
    http_config: HttpPoolConfig | None = None

    def __post_init__(self) -> None:
        """Load from environment."""
        if os.environ.get("POOL_ENABLE_NEO4J", "").lower() == "false":
            self.enable_neo4j = False
        if os.environ.get("POOL_ENABLE_HTTP", "").lower() == "false":
            self.enable_http = False


class PoolManager:
    """
    Unified manager for all connection pools.

    Provides centralized management of Neo4j and HTTP connection pools
    with unified startup, shutdown, and health monitoring.

    Features:
    - Singleton pattern (get_instance)
    - Lazy initialization
    - Graceful degradation (fallback to direct connections)
    - Unified health checks

    Example:
        >>> # Option 1: Use global instance
        >>> from agentic_brain.pooling import PoolManager
        >>> manager = PoolManager.get_instance()
        >>> await manager.startup()
        >>>
        >>> # Option 2: Create custom instance
        >>> config = PoolManagerConfig(
        ...     neo4j_config=Neo4jPoolConfig(max_connections=100)
        ... )
        >>> manager = PoolManager(config)
        >>> await manager.startup()
        >>>
        >>> # Use pools
        >>> async with manager.neo4j.acquire() as conn:
        ...     await conn.run("MATCH (n) RETURN n")
        >>>
        >>> response = await manager.http.get("https://api.example.com")
        >>>
        >>> # Shutdown
        >>> await manager.shutdown()
    """

    def __init__(self, config: PoolManagerConfig | None = None) -> None:
        """
        Initialize pool manager.

        Args:
            config: Manager configuration
        """
        self.config = config or PoolManagerConfig()

        # Pools (initialized on startup)
        self._neo4j_pool: Neo4jPool | None = None
        self._http_pool: HttpPool | None = None

        # Fallbacks
        self._neo4j_direct: DirectNeo4jConnection | None = None
        self._http_direct: DirectHttpClient | None = None

        # State
        self._started = False
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> PoolManager:
        """
        Get the global pool manager instance.

        Creates a new instance if one doesn't exist.

        Returns:
            Global PoolManager instance
        """
        global _pool_manager
        if _pool_manager is None:
            _pool_manager = cls()
        return _pool_manager

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the global instance (useful for testing)."""
        global _pool_manager
        _pool_manager = None

    @property
    def neo4j(self) -> Neo4jPool:
        """
        Get Neo4j connection pool.

        Returns:
            Neo4j pool (or raises if not enabled/started)

        Raises:
            RuntimeError: If Neo4j pooling not enabled or not started
        """
        if not self.config.enable_neo4j:
            raise RuntimeError("Neo4j pooling not enabled")
        if not self._started or self._neo4j_pool is None:
            raise RuntimeError("Pool manager not started")
        return self._neo4j_pool

    @property
    def http(self) -> HttpPool:
        """
        Get HTTP connection pool.

        Returns:
            HTTP pool (or raises if not enabled/started)

        Raises:
            RuntimeError: If HTTP pooling not enabled or not started
        """
        if not self.config.enable_http:
            raise RuntimeError("HTTP pooling not enabled")
        if not self._started or self._http_pool is None:
            raise RuntimeError("Pool manager not started")
        return self._http_pool

    @property
    def is_started(self) -> bool:
        """Check if manager is started."""
        return self._started

    async def startup(self) -> None:
        """
        Start all configured connection pools.

        Starts Neo4j and HTTP pools based on configuration.
        Pools that fail to start will use fallback direct connections.
        """
        async with self._lock:
            if self._started:
                logger.warning("Pool manager already started")
                return

            logger.info("Starting pool manager...")

            # Start Neo4j pool
            if self.config.enable_neo4j:
                try:
                    neo4j_config = self.config.neo4j_config or Neo4jPoolConfig()
                    self._neo4j_pool = Neo4jPool(neo4j_config)
                    await self._neo4j_pool.startup()
                    logger.info("Neo4j pool started")
                except Exception as e:
                    logger.warning(
                        f"Neo4j pool failed to start, using direct connection: {e}"
                    )
                    # Create fallback
                    neo4j_config = self.config.neo4j_config or Neo4jPoolConfig()
                    self._neo4j_direct = DirectNeo4jConnection(
                        uri=neo4j_config.uri,
                        user=neo4j_config.user,
                        password=neo4j_config.password,
                        database=neo4j_config.database,
                    )

            # Start HTTP pool
            if self.config.enable_http:
                try:
                    http_config = self.config.http_config or HttpPoolConfig()
                    self._http_pool = HttpPool(http_config)
                    await self._http_pool.startup()
                    logger.info("HTTP pool started")
                except Exception as e:
                    logger.warning(
                        f"HTTP pool failed to start, using direct client: {e}"
                    )
                    # Create fallback
                    self._http_direct = DirectHttpClient()

            self._started = True
            logger.info("Pool manager started")

    async def shutdown(self) -> None:
        """
        Shutdown all connection pools gracefully.

        Closes all connections and releases resources.
        """
        async with self._lock:
            if not self._started:
                return

            logger.info("Shutting down pool manager...")

            # Shutdown Neo4j
            if self._neo4j_pool:
                try:
                    await self._neo4j_pool.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down Neo4j pool: {e}")
                self._neo4j_pool = None

            if self._neo4j_direct:
                try:
                    self._neo4j_direct.close()
                except Exception as e:
                    logger.error(f"Error closing Neo4j direct connection: {e}")
                self._neo4j_direct = None

            # Shutdown HTTP
            if self._http_pool:
                try:
                    await self._http_pool.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down HTTP pool: {e}")
                self._http_pool = None

            self._http_direct = None

            self._started = False
            logger.info("Pool manager shutdown complete")

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all pools.

        Returns:
            Aggregated health status for all pools
        """
        health = {
            "healthy": True,
            "started": self._started,
            "pools": {},
        }

        if not self._started:
            health["healthy"] = False
            health["error"] = "Pool manager not started"
            return health

        # Check Neo4j
        if self.config.enable_neo4j:
            if self._neo4j_pool:
                neo4j_health = await self._neo4j_pool.health_check()
                health["pools"]["neo4j"] = neo4j_health
                if not neo4j_health.get("healthy"):
                    health["healthy"] = False
            elif self._neo4j_direct:
                health["pools"]["neo4j"] = {
                    "healthy": True,
                    "mode": "direct",
                }

        # Check HTTP
        if self.config.enable_http:
            if self._http_pool:
                http_health = await self._http_pool.health_check()
                health["pools"]["http"] = http_health
                if not http_health.get("healthy"):
                    health["healthy"] = False
            elif self._http_direct:
                health["pools"]["http"] = {
                    "healthy": True,
                    "mode": "direct",
                }

        return health

    def get_metrics(self) -> dict[str, Any]:
        """
        Get metrics from all pools.

        Returns:
            Dictionary with metrics from each pool
        """
        metrics = {}

        if self._neo4j_pool:
            pool_metrics = self._neo4j_pool.metrics
            metrics["neo4j"] = {
                "active_connections": pool_metrics.active_connections,
                "idle_connections": pool_metrics.idle_connections,
                "waiting_requests": pool_metrics.waiting_requests,
                "total_acquisitions": pool_metrics.total_acquisitions,
                "total_releases": pool_metrics.total_releases,
                "failed_acquisitions": pool_metrics.failed_acquisitions,
                "avg_acquisition_ms": round(pool_metrics.average_acquisition_time, 2),
            }

        if self._http_pool:
            pool_metrics = self._http_pool.metrics
            metrics["http"] = {
                "total_requests": pool_metrics.total_requests,
                "successful_requests": pool_metrics.successful_requests,
                "failed_requests": pool_metrics.failed_requests,
                "retried_requests": pool_metrics.retried_requests,
                "circuit_rejections": pool_metrics.circuit_rejections,
                "avg_response_ms": round(pool_metrics.average_response_time, 2),
            }

        return metrics


# Convenience functions for direct access
async def get_pool_manager() -> PoolManager:
    """
    Get started pool manager instance.

    Starts the manager if not already started.

    Returns:
        Started PoolManager instance
    """
    manager = PoolManager.get_instance()
    if not manager.is_started:
        await manager.startup()
    return manager


async def shutdown_pools() -> None:
    """Shutdown the global pool manager."""
    manager = PoolManager.get_instance()
    await manager.shutdown()
    PoolManager.reset_instance()
