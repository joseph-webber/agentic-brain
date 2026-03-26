"""Shared Neo4j connection pool with lazy initialization."""

# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

import atexit
import os
from contextlib import contextmanager
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Dict, List, Optional

try:
    from neo4j.exceptions import ServiceUnavailable

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    ServiceUnavailable = Exception  # type: ignore
    NEO4J_AVAILABLE = False

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

    global _config, _driver

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

    if new_config != _config and _driver is not None:
        # Close existing driver so the next call will use the new config.
        _driver.close()
        _driver = None

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
