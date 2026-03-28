from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from neo4j.exceptions import ClientError, ServiceUnavailable, TransientError

logger = logging.getLogger(__name__)


def _materialize_sync_result(result: Any) -> list[dict[str, Any]]:
    if hasattr(result, "data"):
        return result.data()
    if result is None:
        return []
    return list(result)


async def _materialize_async_result(result: Any) -> list[dict[str, Any]]:
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
    """Execute query with exponential backoff retry."""
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
    """Sync version for legacy code."""
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
