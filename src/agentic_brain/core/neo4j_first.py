# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Decorator for enforcing the "query Neo4j first" integration pattern."""

from __future__ import annotations

import inspect
import logging
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar, cast

from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")
_CACHE_MISS = object()


def neo4j_first(
    *,
    cache_key: str,
    ttl_hours: float | None = None,
    cache_manager: CacheManager | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Check Neo4j before making an external API call.

    Args:
        cache_key: ``str.format`` template used to build the cache key from the
            wrapped function arguments.
        ttl_hours: Optional cache lifetime in hours. ``None`` disables expiry.
        cache_manager: Optional custom cache manager, primarily useful for tests
            or advanced dependency injection.

    Example:
        @neo4j_first(cache_key="jira:{ticket_id}", ttl_hours=1)
        def get_jira_ticket(ticket_id: str) -> dict[str, Any]:
            return jira_api.get(ticket_id)
    """

    manager = cache_manager or CacheManager()

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        signature = inspect.signature(func)

        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            resolved_key = _render_cache_key(
                template=cache_key,
                signature=signature,
                args=args,
                kwargs=kwargs,
            )
            cached = _safe_get_cached(manager, resolved_key)
            if cached is not _CACHE_MISS:
                return cast(R, cached)

            result = await cast(Callable[P, Any], func)(*args, **kwargs)
            _safe_set_cached(manager, resolved_key, result, ttl_hours=ttl_hours)
            return cast(R, result)

        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            resolved_key = _render_cache_key(
                template=cache_key,
                signature=signature,
                args=args,
                kwargs=kwargs,
            )
            cached = _safe_get_cached(manager, resolved_key)
            if cached is not _CACHE_MISS:
                return cast(R, cached)

            result = func(*args, **kwargs)
            _safe_set_cached(manager, resolved_key, result, ttl_hours=ttl_hours)
            return result

        if inspect.iscoroutinefunction(func):
            return cast(Callable[P, R], async_wrapper)
        return cast(Callable[P, R], sync_wrapper)

    return decorator


def _render_cache_key(
    *,
    template: str,
    signature: inspect.Signature,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> str:
    """Render the configured cache key template from function arguments."""

    try:
        bound = signature.bind(*args, **kwargs)
    except TypeError as exc:
        raise ValueError(f"Unable to resolve cache key template '{template}'") from exc

    bound.apply_defaults()

    try:
        return template.format(**bound.arguments)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(
            f"Cache key template '{template}' references unknown argument '{missing}'"
        ) from exc


def _safe_get_cached(manager: CacheManager, cache_key: str) -> Any:
    """Return cached data or a miss sentinel when cache access fails."""

    try:
        cached = manager.get_cached(cache_key)
    except Exception as exc:  # pragma: no cover - defensive fail-open behavior
        logger.warning(
            "Neo4j cache lookup failed for key '%s': %s", cache_key, exc, exc_info=True
        )
        return _CACHE_MISS

    if cached is None:
        return _CACHE_MISS
    return cached


def _safe_set_cached(
    manager: CacheManager,
    cache_key: str,
    value: Any,
    *,
    ttl_hours: float | None,
) -> None:
    """Persist data to cache without breaking the underlying API call."""

    try:
        manager.set_cached(cache_key, value, ttl_hours=ttl_hours)
    except Exception as exc:  # pragma: no cover - defensive fail-open behavior
        logger.warning(
            "Neo4j cache write failed for key '%s': %s", cache_key, exc, exc_info=True
        )
