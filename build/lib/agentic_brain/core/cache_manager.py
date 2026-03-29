# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Neo4j-backed cache helpers for the "query Neo4j first" pattern."""

from __future__ import annotations

import json
import logging
import re
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from .neo4j_pool import get_session

logger = logging.getLogger(__name__)

_LABEL_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _json_default(value: Any) -> str:
    """Serialize common non-JSON-native values safely."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC).isoformat()
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


class CacheManager:
    """Persist API responses in Neo4j with optional TTL support.

    Cached values are stored as JSON on nodes keyed by ``cache_key``. The cache
    is intentionally generic so it can be shared across integrations such as
    JIRA, GitHub, ServiceNow, or any other external API.
    """

    def __init__(
        self,
        *,
        label: str = "ExternalApiCache",
        database: str | None = None,
    ) -> None:
        if not _LABEL_PATTERN.match(label):
            raise ValueError(
                "label must be a valid Neo4j label containing only letters, "
                "numbers, and underscores"
            )

        self.label = label
        self.database = database

    def get_cached(self, cache_key: str) -> Any | None:
        """Return cached data when present and not expired."""

        record = self._run_single(
            f"""
            MATCH (entry:{self.label} {{cache_key: $cache_key}})
            WHERE entry.expires_at IS NULL OR entry.expires_at > datetime()
            RETURN entry.payload_json AS payload_json
            """,
            cache_key=cache_key,
        )
        if record is None:
            return None

        payload_json = record.get("payload_json")
        if payload_json is None:
            return None

        try:
            return json.loads(payload_json)
        except json.JSONDecodeError:
            logger.warning("Ignoring corrupt cache payload for key '%s'", cache_key)
            return None

    def set_cached(
        self,
        cache_key: str,
        value: Any,
        *,
        ttl_hours: float | None = None,
    ) -> None:
        """Store data in Neo4j, replacing any existing cache entry."""

        cached_at = datetime.now(UTC)
        expires_at = (
            cached_at + timedelta(hours=ttl_hours) if ttl_hours is not None else None
        )
        payload_json = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=_json_default,
        )

        self._execute(
            f"""
            MERGE (entry:{self.label} {{cache_key: $cache_key}})
            SET entry.payload_json = $payload_json,
                entry.cached_at = datetime($cached_at),
                entry.updated_at = datetime($cached_at),
                entry.expires_at = CASE
                    WHEN $expires_at IS NULL THEN NULL
                    ELSE datetime($expires_at)
                END,
                entry.ttl_hours = $ttl_hours
            """,
            cache_key=cache_key,
            payload_json=payload_json,
            cached_at=cached_at.isoformat(),
            expires_at=expires_at.isoformat() if expires_at else None,
            ttl_hours=ttl_hours,
        )

    def invalidate(self, cache_key: str) -> None:
        """Remove a cache entry so the next lookup falls through to the API."""

        self._execute(
            f"""
            MATCH (entry:{self.label} {{cache_key: $cache_key}})
            DELETE entry
            """,
            cache_key=cache_key,
        )

    def _get_session(self) -> AbstractContextManager[Any]:
        return get_session(database=self.database)

    def _run_single(self, cypher: str, **params: Any) -> dict[str, Any] | None:
        with self._get_session() as session:
            record = session.run(cypher, **params).single()
            return dict(record) if record else None

    def _execute(self, cypher: str, **params: Any) -> None:
        with self._get_session() as session:
            session.run(cypher, **params).consume()
