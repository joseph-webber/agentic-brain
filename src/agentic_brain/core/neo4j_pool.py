"""Shared Neo4j connection pool with lazy initialization.

Provides both synchronous and asynchronous access to Neo4j.
Sync functions use ``neo4j.GraphDatabase``; async functions use
``neo4j.AsyncGraphDatabase``.  Both share the same
:class:`Neo4jPoolConfig`.
"""

# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

import atexit
import os
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    from neo4j.exceptions import ServiceUnavailable

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    ServiceUnavailable = Exception  # type: ignore
    NEO4J_AVAILABLE = False

try:
    from neo4j import AsyncGraphDatabase

    ASYNC_NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncGraphDatabase = None  # type: ignore
    ASYNC_NEO4J_AVAILABLE = False

if TYPE_CHECKING:  # pragma: no cover - import only for typing
    try:
        from neo4j import Driver  # pylint: disable=ungrouped-imports
    except ImportError:  # pragma: no cover
        Driver = Any  # type: ignore
else:  # pragma: no cover - fallback type hint
    Driver = Any  # type: ignore


@dataclass(frozen=True)
class Neo4jPoolConfig:
    """Configuration for the shared Neo4j driver."""

    uri: str = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user: str = os.environ.get("NEO4J_USER", "neo4j")
    password: str = os.environ.get("NEO4J_PASSWORD", "")
    database: str = os.environ.get("NEO4J_DATABASE", "neo4j")
    max_connection_pool_size: int = int(os.environ.get("NEO4J_POOL_SIZE", "50"))
    connection_acquisition_timeout: float = float(
        os.environ.get("NEO4J_POOL_TIMEOUT", "30")
    )


_config = Neo4jPoolConfig()
_driver: Optional[Driver] = None
_async_driver: Optional[Any] = None


def configure_pool(
    *,
    uri: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
    max_connection_pool_size: Optional[int] = None,
    connection_acquisition_timeout: Optional[float] = None,
) -> None:
    """Update pool configuration and rebuild the driver if needed."""

    global _config, _driver, _async_driver

    new_config = replace(
        _config,
        uri=uri or _config.uri,
        user=user or _config.user,
        password=password if password is not None else _config.password,
        database=database or _config.database,
        max_connection_pool_size=max_connection_pool_size
        or _config.max_connection_pool_size,
        connection_acquisition_timeout=connection_acquisition_timeout
        or _config.connection_acquisition_timeout,
    )

    if new_config != _config:
        if _driver is not None:
            _driver.close()
            _driver = None
        # Mark async driver for re-creation; cannot await close() here.
        _async_driver = None

    _config = new_config


def _create_driver() -> Driver:
    """Create the global driver using the current config."""

    if not NEO4J_AVAILABLE:
        raise ImportError("neo4j package is required. Install with: pip install neo4j")

    from neo4j import GraphDatabase  # local import for lazy loading

    driver = GraphDatabase.driver(
        _config.uri,
        auth=(_config.user, _config.password),
        max_connection_pool_size=_config.max_connection_pool_size,
        connection_acquisition_timeout=_config.connection_acquisition_timeout,
    )
    atexit.register(driver.close)
    return driver


def get_driver(
    *,
    uri: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> Driver:
    """
    Return the shared Neo4j driver, creating it on first use.

    Optional overrides will reconfigure the pool if different from the current
    settings before returning the driver.
    """

    global _driver

    if any(value is not None for value in (uri, user, password, database)):
        configure_pool(
            uri=uri,
            user=user,
            password=password,
            database=database,
        )

    if _driver is None:
        _driver = _create_driver()

    return _driver


@contextmanager
def get_session(database: Optional[str] = None):
    """Context manager that yields a Neo4j session."""

    driver = get_driver(database=database)
    session = (
        driver.session(database=database or _config.database)
        if database or _config.database
        else driver.session()
    )
    try:
        yield session
    finally:
        session.close()


def close_pool() -> None:
    """Close the global driver."""

    global _driver
    if _driver:
        _driver.close()
        _driver = None


def query(cypher: str, **params) -> List[Dict[str, Any]]:
    """Execute a Cypher query and return rows as dictionaries."""

    with get_session() as session:
        result = session.run(cypher, **params)
        return [dict(record) for record in result]


def query_single(cypher: str, **params) -> Optional[Dict[str, Any]]:
    """Execute a Cypher query and return the first record."""

    with get_session() as session:
        result = session.run(cypher, **params)
        record = result.single()
        return dict(record) if record else None


def query_value(cypher: str, **params) -> Any:
    """Execute a query and return the first scalar value."""

    record = query_single(cypher, **params)
    if record:
        return next(iter(record.values()))
    return None


def write(cypher: str, **params) -> int:
    """Execute a write query and return the number of affected entities."""

    with get_session() as session:
        result = session.run(cypher, **params)
        summary = result.consume()
        counters = summary.counters
        return (
            counters.nodes_created
            + counters.nodes_deleted
            + counters.relationships_created
            + counters.relationships_deleted
            + counters.properties_set
        )


def health_check() -> Dict[str, Any]:
    """Return a health payload for the pool."""

    try:
        driver = get_driver()
        driver.verify_connectivity()
        with get_session() as session:
            total_nodes = session.run("MATCH (n) RETURN count(n) AS total").single()[
                "total"
            ]
        return {
            "status": "healthy",
            "uri": _config.uri,
            "database": _config.database,
            "total_nodes": total_nodes,
            "pool_size": _config.max_connection_pool_size,
        }
    except ServiceUnavailable as exc:
        return {
            "status": "unavailable",
            "uri": _config.uri,
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "error",
            "uri": _config.uri,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Async API – mirrors the sync functions above using AsyncGraphDatabase
# ---------------------------------------------------------------------------


def _create_async_driver() -> Any:
    """Create the global async driver using the current config."""

    if not ASYNC_NEO4J_AVAILABLE or AsyncGraphDatabase is None:
        raise ImportError(
            "neo4j async driver is required. Install with: pip install neo4j"
        )

    return AsyncGraphDatabase.driver(
        _config.uri,
        auth=(_config.user, _config.password),
        max_connection_pool_size=_config.max_connection_pool_size,
        connection_acquisition_timeout=_config.connection_acquisition_timeout,
    )


async def async_get_driver(
    *,
    uri: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> Any:
    """Return the shared async Neo4j driver, creating it on first use.

    Optional overrides will reconfigure the pool if different from the current
    settings before returning the driver.
    """

    global _async_driver

    if any(value is not None for value in (uri, user, password, database)):
        configure_pool(uri=uri, user=user, password=password, database=database)

    if _async_driver is None:
        _async_driver = _create_async_driver()

    return _async_driver


@asynccontextmanager
async def async_get_session(database: Optional[str] = None):
    """Async context manager that yields a Neo4j async session."""

    driver = await async_get_driver()
    db = database or _config.database
    session = driver.session(database=db) if db else driver.session()
    try:
        yield session
    finally:
        await session.close()


async def async_close_pool() -> None:
    """Close the global async driver."""

    global _async_driver
    if _async_driver:
        await _async_driver.close()
        _async_driver = None


async def async_query(cypher: str, **params) -> List[Dict[str, Any]]:
    """Execute a Cypher query asynchronously and return rows as dicts."""

    async with async_get_session() as session:
        result = await session.run(cypher, **params)
        return [dict(record) async for record in result]


async def async_query_single(cypher: str, **params) -> Optional[Dict[str, Any]]:
    """Execute a Cypher query asynchronously and return the first record."""

    async with async_get_session() as session:
        result = await session.run(cypher, **params)
        record = await result.single()
        return dict(record) if record else None


async def async_query_value(cypher: str, **params) -> Any:
    """Execute a query asynchronously and return the first scalar value."""

    record = await async_query_single(cypher, **params)
    if record:
        return next(iter(record.values()))
    return None


async def async_write(cypher: str, **params) -> int:
    """Execute a write query asynchronously and return affected entity count."""

    async with async_get_session() as session:
        result = await session.run(cypher, **params)
        summary = await result.consume()
        counters = summary.counters
        return (
            counters.nodes_created
            + counters.nodes_deleted
            + counters.relationships_created
            + counters.relationships_deleted
            + counters.properties_set
        )


async def async_health_check() -> Dict[str, Any]:
    """Return an async health payload for the pool."""

    try:
        driver = await async_get_driver()
        await driver.verify_connectivity()
        async with async_get_session() as session:
            result = await session.run("MATCH (n) RETURN count(n) AS total")
            record = await result.single()
            total_nodes = record["total"]
        return {
            "status": "healthy",
            "uri": _config.uri,
            "database": _config.database,
            "total_nodes": total_nodes,
            "pool_size": _config.max_connection_pool_size,
        }
    except ServiceUnavailable as exc:
        return {
            "status": "unavailable",
            "uri": _config.uri,
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "error",
            "uri": _config.uri,
            "error": str(exc),
        }
