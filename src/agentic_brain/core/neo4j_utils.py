# SPDX-License-Identifier: Apache-2.0
"""Neo4j query resilience utilities with automatic retry logic.

This module provides sync and async query execution with exponential backoff
retry for transient failures (ServiceUnavailable, TransientError).
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from neo4j.exceptions import ClientError, ServiceUnavailable, TransientError

logger = logging.getLogger(__name__)


def _materialize_sync_result(result: Any) -> list[dict[str, Any]]:
    """Materialize sync Neo4j result into list of dictionaries."""
    if hasattr(result, "data"):
        return result.data()
    if result is None:
        return []
    return list(result)


async def _materialize_async_result(result: Any) -> list[dict[str, Any]]:
    """Materialize async Neo4j result into list of dictionaries."""
    if hasattr(result, "data"):
        return await result.data()
    if result is None:
        return []
    return list(result)


async def resilient_query(
    session: Any,
    query: str,
    params: dict[str, Any] | None = None,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """Execute query with exponential backoff retry on transient errors.

    Retries automatically on ServiceUnavailable and TransientError with
    backoff delays: 1s, 2s, 4s, etc. Fails immediately on ClientError.

    Args:
        session: Async Neo4j session.
        query: Cypher query string.
        params: Optional query parameters.
        max_retries: Maximum retry attempts (default: 3).

    Returns:
        List of result rows as dictionaries.

    Raises:
        ClientError: Query syntax or semantic errors (not retried).
        ServiceUnavailable: Raised after max retries exhausted.
    """
    query_params = params or {}

    for attempt in range(max_retries):
        try:
            result = await session.run(query, **query_params)
            return await _materialize_async_result(result)
        except ClientError:
            raise
        except (TransientError, ServiceUnavailable) as exc:
            if attempt == max_retries - 1:
                raise

            wait = 2**attempt
            logger.warning(
                "Retrying Neo4j query attempt %s/%s after %s: %s",
                attempt + 1,
                max_retries,
                type(exc).__name__,
                exc,
            )
            await asyncio.sleep(wait)

    raise RuntimeError("Max retries exceeded")


def resilient_query_sync(
    session: Any,
    query: str,
    params: dict[str, Any] | None = None,
    max_retries: int = 3,
) -> list[dict[str, Any]]:
    """Execute query synchronously with exponential backoff retry.

    Synchronous version of resilient_query for blocking contexts.
    Retries automatically on ServiceUnavailable and TransientError with
    backoff delays: 1s, 2s, 4s, etc. Fails immediately on ClientError.

    Args:
        session: Sync Neo4j session.
        query: Cypher query string.
        params: Optional query parameters.
        max_retries: Maximum retry attempts (default: 3).

    Returns:
        List of result rows as dictionaries.

    Raises:
        ClientError: Query syntax or semantic errors (not retried).
        ServiceUnavailable: Raised after max retries exhausted.
    """
    query_params = params or {}

    for attempt in range(max_retries):
        try:
            result = session.run(query, **query_params)
            return _materialize_sync_result(result)
        except ClientError:
            raise
        except (TransientError, ServiceUnavailable) as exc:
            if attempt == max_retries - 1:
                raise

            wait = 2**attempt
            logger.warning(
                "Retrying Neo4j query attempt %s/%s after %s: %s",
                attempt + 1,
                max_retries,
                type(exc).__name__,
                exc,
            )
            time.sleep(wait)

    raise RuntimeError("Max retries exceeded")
