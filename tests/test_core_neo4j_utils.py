import asyncio
import time
import types

import pytest
from neo4j.exceptions import ClientError, ServiceUnavailable, TransientError

from agentic_brain.core import neo4j_utils as nu


class DummyResult:
    def __init__(self, data):
        self._data = data

    def data(self):
        return self._data


class AsyncDummyResult:
    def __init__(self, data):
        self._data = data

    async def data(self):
        return self._data


class FakeAsyncSession:
    def __init__(self, responses):
        self._responses = list(responses)

    async def run(self, query, **params):
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return AsyncDummyResult(resp)


class FakeSyncSession:
    def __init__(self, responses):
        self._responses = list(responses)

    def run(self, query, **params):
        resp = self._responses.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return DummyResult(resp)


@pytest.mark.asyncio
async def test_materialize_async_result_none():
    out = await nu._materialize_async_result(None)
    assert out == []


def test_materialize_sync_result_none():
    assert nu._materialize_sync_result(None) == []


def test_materialize_sync_result_data_method():
    r = DummyResult([{"a": 1}])
    assert nu._materialize_sync_result(r) == [{"a": 1}]


@pytest.mark.asyncio
async def test_resilient_query_retries_on_transient_then_success(monkeypatch):
    # Make asyncio.sleep a no-op to speed up test
    async def fast_sleep(n):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    session = FakeAsyncSession([TransientError("t1"), [{"x": 1}]])
    res = await nu.resilient_query(session, "MATCH (n) RETURN n", max_retries=3)
    assert res == [{"x": 1}]


@pytest.mark.asyncio
async def test_resilient_query_raises_on_client_error(monkeypatch):
    session = FakeAsyncSession([ClientError("bad")])
    with pytest.raises(ClientError):
        await nu.resilient_query(session, "x", max_retries=1)


def test_resilient_query_sync_retries_and_success(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda n: None)
    session = FakeSyncSession([TransientError("t1"), [{"y": 2}]])
    out = nu.resilient_query_sync(session, "q", max_retries=3)
    assert out == [{"y": 2}]


def test_resilient_query_sync_raises_after_retries(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda n: None)
    session = FakeSyncSession([ServiceUnavailable("nope"), ServiceUnavailable("nope")])
    with pytest.raises(ServiceUnavailable):
        nu.resilient_query_sync(session, "q", max_retries=2)
