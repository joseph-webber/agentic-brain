import json
from datetime import date, datetime
from decimal import Decimal

import pytest

from agentic_brain.core import cache_manager as cm


class DummySession:
    def __init__(self, single_return=None):
        self._single = single_return
        self.runs = []

    def run(self, cypher, **params):
        self.runs.append((cypher, params))

        class Rec:
            def __init__(self, data):
                self._data = data

            def single(self):
                return self._data

            def consume(self):
                return None

        return Rec(self._single)


class DummyCtx:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc, tb):
        return False


def test_json_default_serializes_datetime_naive_with_UTC():
    d = datetime(2020, 1, 1, 12, 0, 0)
    s = cm._json_default(d)
    assert "2020-01-01" in s


def test_json_default_serializes_date():
    d = date(2020, 1, 2)
    assert cm._json_default(d) == "2020-01-02"


def test_json_default_serializes_decimal():
    assert cm._json_default(Decimal("1.23")) == "1.23"


def test_cache_get_cached_returns_none_when_no_record(monkeypatch):
    monkeypatch.setattr(
        cm, "get_session", lambda database=None: DummyCtx(DummySession(None))
    )
    c = cm.CacheManager()
    assert c.get_cached("missing") is None


def test_cache_get_cached_returns_json_when_present(monkeypatch):
    payload = {"a": 1}
    rec = {"payload_json": json.dumps(payload)}
    monkeypatch.setattr(
        cm, "get_session", lambda database=None: DummyCtx(DummySession(rec))
    )
    c = cm.CacheManager()
    assert c.get_cached("k") == payload


def test_cache_get_cached_handles_corrupt_json(monkeypatch):
    rec = {"payload_json": "not json"}
    monkeypatch.setattr(
        cm, "get_session", lambda database=None: DummyCtx(DummySession(rec))
    )
    c = cm.CacheManager()
    assert c.get_cached("k") is None


def test_set_cached_calls_execute_with_payload(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(cm, "get_session", lambda database=None: DummyCtx(session))
    c = cm.CacheManager()
    c.set_cached("k", {"x": 2}, ttl_hours=1)
    assert len(session.runs) >= 1
    found = any("MERGE (entry" in cy for cy, _ in session.runs)
    assert found


def test_invalidate_calls_execute(monkeypatch):
    session = DummySession()
    monkeypatch.setattr(cm, "get_session", lambda database=None: DummyCtx(session))
    c = cm.CacheManager()
    c.invalidate("k")
    assert any("DELETE entry" in cy for cy, _ in session.runs)
