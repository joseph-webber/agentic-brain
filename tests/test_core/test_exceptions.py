# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import asyncio

import pytest

from agentic_brain.core import (
    AgenticBrainError,
    EmbeddingError,
    GraphConnectionError,
    LLMError,
    RateLimitError,
    ValidationError,
    circuit_breaker,
    retry_with_backoff,
    timeout,
)
from agentic_brain.core import retry as retry_module


@pytest.mark.parametrize(
    "error,expected",
    [
        (
            AgenticBrainError(
                "boom",
                cause="root",
                fix="try again",
                context={"a": 1},
            ),
            ["❌ boom", "Cause: root", "Fix: try again", "Context: {'a': 1}"],
        ),
        (
            GraphConnectionError("Neo4j", "bolt://localhost:7687"),
            ["Neo4j graph connection failed", "bolt://localhost:7687"],
        ),
        (
            EmbeddingError(provider="ollama", model="nomic-embed-text"),
            ["Embedding operation failed", "ollama", "nomic-embed-text"],
        ),
        (
            LLMError(provider="openai", model="gpt-4o"),
            ["LLM operation failed", "openai", "gpt-4o"],
        ),
    ],
)
def test_error_formatting(error, expected):
    msg = str(error)
    for part in expected:
        assert part in msg


@pytest.mark.parametrize(
    "error,fields",
    [
        (RateLimitError(100, "minute"), {"limit": 100, "window": "minute"}),
        (
            RateLimitError(10, "hour", retry_after=120, provider="openai"),
            {"retry_after": 120, "provider": "openai"},
        ),
        (
            ValidationError("email", "valid email", "bad", reason="format"),
            {"field": "email", "expected": "valid email", "got": "bad", "reason": "format"},
        ),
        (
            GraphConnectionError("Neo4j", "bolt://x", operation="query"),
            {"backend": "Neo4j", "uri": "bolt://x", "operation": "query"},
        ),
        (
            EmbeddingError(provider="mlx", model="mxbai", operation="embed"),
            {"provider": "mlx", "model": "mxbai", "operation": "embed"},
        ),
    ],
)
def test_error_context(error, fields):
    for key, value in fields.items():
        assert error.context[key] == value


@pytest.mark.parametrize(
    "error_cls,args",
    [
        (AgenticBrainError, ("x",)),
        (GraphConnectionError, ("Neo4j", "bolt://localhost:7687")),
        (EmbeddingError, ()),
        (LLMError, ()),
        (RateLimitError, (1, "minute")),
        (ValidationError, ("field", "expected", "got")),
    ],
)
def test_errors_inherit_from_base(error_cls, args):
    assert issubclass(error_cls, Exception)
    assert isinstance(error_cls(*args), AgenticBrainError)


@pytest.mark.parametrize(
    "error, retryable",
    [
        (GraphConnectionError("Neo4j", "bolt://localhost"), True),
        (EmbeddingError(), True),
        (LLMError(), True),
        (RateLimitError(1, "minute"), True),
        (ValidationError("field", "expected", "got"), False),
    ],
)
def test_retryable_flags(error, retryable):
    assert error.retryable is retryable


def test_to_dict_contains_serializable_fields():
    error = AgenticBrainError("boom", cause="cause", fix="fix", context={"x": 1})
    data = error.to_dict()
    assert data["type"] == "AgenticBrainError"
    assert data["message"] == "boom"
    assert data["cause"] == "cause"
    assert data["fix"] == "fix"
    assert data["context"] == {"x": 1}


def test_retry_with_backoff_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr(retry_module.time, "sleep", lambda *_: None)

    @retry_with_backoff(attempts=3, initial_delay=0.0, backoff_factor=1.0)
    def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RateLimitError(10, "minute")
        return "ok"

    assert flaky() == "ok"
    assert calls["count"] == 3


def test_retry_with_backoff_stops_on_validation_error(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr(retry_module.time, "sleep", lambda *_: None)

    @retry_with_backoff(attempts=5, initial_delay=0.0)
    def bad_input():
        calls["count"] += 1
        raise ValidationError("field", "expected", "got")

    with pytest.raises(ValidationError):
        bad_input()
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_retry_with_backoff_async(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr(retry_module.asyncio, "sleep", lambda *_: asyncio.sleep(0))

    @retry_with_backoff(attempts=3, initial_delay=0.0, backoff_factor=1.0)
    async def flaky_async():
        calls["count"] += 1
        if calls["count"] < 3:
            raise RateLimitError(5, "minute")
        return "ok"

    assert await flaky_async() == "ok"
    assert calls["count"] == 3


def test_circuit_breaker_opens_after_threshold(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(retry_module.time, "monotonic", lambda: clock["now"])

    calls = {"count": 0}

    @circuit_breaker(failure_threshold=2, recovery_timeout=5.0)
    def unstable():
        calls["count"] += 1
        raise RateLimitError(1, "minute")

    with pytest.raises(RateLimitError):
        unstable()
    with pytest.raises(RuntimeError):
        unstable()
    with pytest.raises(RuntimeError):
        unstable()
    assert calls["count"] == 2


def test_circuit_breaker_recovers_after_timeout(monkeypatch):
    clock = {"now": 0.0}
    monkeypatch.setattr(retry_module.time, "monotonic", lambda: clock["now"])

    calls = {"count": 0}

    @circuit_breaker(failure_threshold=2, recovery_timeout=5.0)
    def unstable_then_ok():
        calls["count"] += 1
        if calls["count"] <= 2:
            raise RateLimitError(1, "minute")
        return "ok"

    with pytest.raises(RateLimitError):
        unstable_then_ok()
    with pytest.raises(RuntimeError):
        unstable_then_ok()

    clock["now"] = 6.0
    assert unstable_then_ok() == "ok"


def test_timeout_sync():
    @timeout(0.01)
    def slow():
        import time

        time.sleep(0.05)
        return "late"

    with pytest.raises(TimeoutError):
        slow()


@pytest.mark.asyncio
async def test_timeout_async():
    @timeout(0.01)
    async def slow():
        await asyncio.sleep(0.05)
        return "late"

    with pytest.raises(TimeoutError):
        await slow()


def test_core_exports_are_available():
    assert AgenticBrainError is not None
    assert circuit_breaker is not None
    assert retry_with_backoff is not None
    assert timeout is not None


@pytest.mark.parametrize(
    "field,expected,got",
    [
        ("user_id", "UUID", "123"),
        ("email", "email", "missing"),
        ("age", "integer", "-1"),
        ("status", "enum", "unknown"),
    ],
)
def test_validation_error_messages(field, expected, got):
    error = ValidationError(field, expected, got)
    msg = str(error)
    assert field in msg
    assert expected in msg
    assert str(got) in msg


@pytest.mark.parametrize(
    "backend,uri",
    [
        ("Neo4j", "bolt://localhost:7687"),
        ("Arango", "http://localhost:8529"),
        ("Memgraph", "bolt://memgraph:7687"),
    ],
)
def test_graph_connection_error_messages(backend, uri):
    error = GraphConnectionError(backend, uri)
    assert backend in str(error)
    assert uri in str(error)

