# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""Tests for Neo4j-first caching helpers."""

from __future__ import annotations

from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

from agentic_brain.core.cache_manager import CacheManager
from agentic_brain.core.neo4j_first import neo4j_first


class FakeResult:
    """Simple Neo4j result stub for unit tests."""

    def __init__(self, record: dict[str, Any] | None = None) -> None:
        self.record = record
        self.consume_called = False

    def single(self) -> dict[str, Any] | None:
        return self.record

    def consume(self) -> None:
        self.consume_called = True


class FakeSession:
    """Simple session stub that records executed queries."""

    def __init__(self, results: list[FakeResult]) -> None:
        self._results = results
        self.calls: list[dict[str, Any]] = []

    def run(self, cypher: str, **params: Any) -> FakeResult:
        self.calls.append({"cypher": cypher, "params": params})
        if self._results:
            return self._results.pop(0)
        return FakeResult()


def test_cache_manager_get_cached_returns_deserialized_payload(monkeypatch):
    """CacheManager should deserialize stored JSON payloads."""

    session = FakeSession([FakeResult({"payload_json": '{"status":"ok","count":2}'})])
    monkeypatch.setattr(
        "agentic_brain.core.cache_manager.get_session",
        lambda database=None: nullcontext(session),
    )

    manager = CacheManager()

    assert manager.get_cached("jira:SD-123") == {"status": "ok", "count": 2}
    assert session.calls[0]["params"]["cache_key"] == "jira:SD-123"


def test_cache_manager_set_cached_stores_ttl_metadata(monkeypatch):
    """CacheManager should persist payloads with TTL metadata."""

    result = FakeResult()
    session = FakeSession([result])
    monkeypatch.setattr(
        "agentic_brain.core.cache_manager.get_session",
        lambda database=None: nullcontext(session),
    )

    manager = CacheManager()
    manager.set_cached(
        "jira:SD-123",
        {"updated_at": datetime(2026, 1, 2, 3, 4, tzinfo=UTC)},
        ttl_hours=1.5,
    )

    params = session.calls[0]["params"]
    assert params["cache_key"] == "jira:SD-123"
    assert params["ttl_hours"] == 1.5
    assert params["expires_at"] is not None
    assert "updated_at" in params["payload_json"]
    assert result.consume_called is True


def test_cache_manager_invalidate_deletes_cached_entry(monkeypatch):
    """Invalidation should delete the matching cache node."""

    result = FakeResult()
    session = FakeSession([result])
    monkeypatch.setattr(
        "agentic_brain.core.cache_manager.get_session",
        lambda database=None: nullcontext(session),
    )

    manager = CacheManager()
    manager.invalidate("jira:SD-123")

    assert "DELETE entry" in session.calls[0]["cypher"]
    assert session.calls[0]["params"]["cache_key"] == "jira:SD-123"
    assert result.consume_called is True


def test_neo4j_first_returns_cached_value_without_api_call():
    """Decorator should short-circuit external calls on cache hit."""

    manager = MagicMock()
    manager.get_cached.return_value = {"ticket": "SD-123", "source": "cache"}

    api_call = MagicMock()

    def fetch_ticket(ticket_id):
        api_call(ticket_id)
        return {"ticket": "SD-123", "source": "api"}

    wrapped = neo4j_first(
        cache_key="jira:{ticket_id}",
        ttl_hours=1,
        cache_manager=manager,
    )(fetch_ticket)

    assert wrapped("SD-123") == {"ticket": "SD-123", "source": "cache"}
    api_call.assert_not_called()
    manager.set_cached.assert_not_called()


def test_neo4j_first_populates_cache_on_miss():
    """Decorator should call the function and then populate the cache."""

    manager = MagicMock()
    manager.get_cached.return_value = None

    wrapped = neo4j_first(
        cache_key="jira:{ticket_id}",
        ttl_hours=2,
        cache_manager=manager,
    )(lambda ticket_id: {"ticket": ticket_id, "source": "api"})

    assert wrapped("SD-456") == {"ticket": "SD-456", "source": "api"}
    manager.get_cached.assert_called_once_with("jira:SD-456")
    manager.set_cached.assert_called_once_with(
        "jira:SD-456",
        {"ticket": "SD-456", "source": "api"},
        ttl_hours=2,
    )


@pytest.mark.asyncio
async def test_neo4j_first_supports_async_functions():
    """Decorator should work with async API functions as well."""

    manager = MagicMock()
    manager.get_cached.return_value = None

    @neo4j_first(
        cache_key="jira:{ticket_id}",
        ttl_hours=1,
        cache_manager=manager,
    )
    async def get_ticket(ticket_id: str) -> dict[str, str]:
        return {"ticket": ticket_id, "source": "api"}

    assert await get_ticket("SD-789") == {"ticket": "SD-789", "source": "api"}
    manager.set_cached.assert_called_once_with(
        "jira:SD-789",
        {"ticket": "SD-789", "source": "api"},
        ttl_hours=1,
    )
