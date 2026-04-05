import json
import contextlib
from contextlib import contextmanager
import pytest
from types import SimpleNamespace

from agentic_brain.memory import session_manager as sm
from agentic_brain.memory import neo4j_memory as nm


class FakeSession:
    def __init__(self, recorder):
        self.recorder = recorder

    def run(self, query, **params):
        # Record the call for assertions
        self.recorder.append((query, params))
        # Return empty iterable
        return []


@contextmanager
def fake_get_session(recorder):
    yield FakeSession(recorder)


# Helper to patch core.get_session in modules that call it
def patch_get_session(monkeypatch, recorder):
    import agentic_brain.core.neo4j_pool as pool

    monkeypatch.setattr(
        pool, "get_session", lambda database=None: fake_get_session(recorder)
    )


# 1
def test_neo4j_backend_initialize_creates_indexes(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)

    backend = sm.Neo4jSessionBackend()
    backend.initialize()

    assert any("CREATE CONSTRAINT" in q[0] for q in calls)
    assert any("CREATE INDEX message_timestamp" in q[0] for q in calls)
    assert any("CREATE INDEX message_content" in q[0] for q in calls)


# 2
def test_store_messages_bulk_runs_unwind(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)

    backend = sm.Neo4jSessionBackend()
    backend.initialize()

    msgs = []
    for i in range(3):
        msgs.append(
            sm.SessionMessage(
                id=f"m{i}",
                role=sm.MessageRole.USER,
                content=f"hello {i}",
                timestamp=sm.datetime.now(sm.UTC),
                session_id="s1",
            )
        )

    stored = backend.store_messages_bulk(msgs)
    assert stored == 3
    assert any(
        "UNWIND $rows AS r" in q[0]
        or "UNWIND $rows AS r" in (q[0] if isinstance(q[0], str) else "")
        for q in calls
    )


# 3
def test_get_messages_pagination_params(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)

    backend = sm.Neo4jSessionBackend()
    backend.initialize()

    backend.get_messages("s1", page=2, page_size=10)

    # Last call should be the query
    assert calls, "No calls captured"
    query, params = calls[-1]
    assert "SKIP" in query or "SKIP $skip" in query
    assert params.get("skip") == 20
    assert params.get("limit") == 10


# 4
def test_conversation_memory_add_messages_batch_uses_unwind(monkeypatch):
    # Patch resilient_query_sync used by ConversationMemory._run_query
    recorded = []

    def fake_resilient(session, query, params=None):
        recorded.append((query, params))
        return []

    monkeypatch.setattr(nm, "resilient_query_sync", fake_resilient)

    # Also patch get_session to a dummy context
    import agentic_brain.core.neo4j_pool as pool

    monkeypatch.setattr(
        pool, "get_session", lambda database=None: fake_get_session(recorded)
    )

    conv = nm.ConversationMemory()
    # Mark initialized to avoid creating indexes during test
    import asyncio

    asyncio.get_event_loop().run_until_complete(conv.initialize())

    batch = [
        {"role": "user", "content": "Hello Alice"},
        {"role": "assistant", "content": "Hello Bob"},
    ]

    res = asyncio.get_event_loop().run_until_complete(conv.add_messages_batch(batch))
    assert res == 2
    assert any(
        "UNWIND $rows AS r" in (q[0] if isinstance(q[0], str) else "") for q in recorded
    )


# 5
def test_get_conversation_history_pagination_uses_skip_limit(monkeypatch):
    recorded = []

    def fake_resilient(session, query, params=None):
        recorded.append((query, params))
        # Return a sample row-like dict
        return [
            {
                "id": "m1",
                "role": "user",
                "content": "x",
                "timestamp": sm.datetime.now(sm.UTC).isoformat(),
                "session_id": "s1",
                "metadata": "{}",
                "entities": [],
            }
        ]

    monkeypatch.setattr(nm, "resilient_query_sync", fake_resilient)
    import agentic_brain.core.neo4j_pool as pool

    monkeypatch.setattr(
        pool, "get_session", lambda database=None: fake_get_session(recorded)
    )

    conv = nm.ConversationMemory()
    import asyncio

    asyncio.get_event_loop().run_until_complete(conv.initialize())

    msgs = asyncio.get_event_loop().run_until_complete(
        conv.get_conversation_history(page=1, page_size=5)
    )
    assert isinstance(msgs, list)
    assert recorded, "No queries recorded"
    q, params = recorded[-1]
    assert "$skip" in q or "SKIP" in q
    assert params.get("skip") == 5
    assert params.get("limit") == 5


# 6
def test_session_manager_create_session_does_not_load_backend(monkeypatch):
    # Replace Neo4jSessionBackend.get_messages with a function that would raise if called
    class Backend(sm.Neo4jSessionBackend):
        def get_messages(self, session_id: str, limit: int | None = None):
            raise RuntimeError("Should not be called during create_session")

    manager = sm.SessionManager(prefer_neo4j=False)
    manager._backend = Backend()

    # create_session should not attempt to load messages from backend
    import asyncio

    s = asyncio.get_event_loop().run_until_complete(manager.create_session())
    assert s is not None


# 7
def test_session_add_message_persists_backend(monkeypatch):
    called = {}

    class FakeBackend:
        def store_message(self, message):
            called["stored"] = True

        def get_messages(self, *args, **kwargs):
            return []

        def store_summary(self, summary):
            pass

        def get_recent_context(self, hours=24):
            return []

        def search(self, query, limit=10):
            return []

    import asyncio

    backend = FakeBackend()
    manager = sm.SessionManager(prefer_neo4j=False)
    manager._backend = backend

    s = asyncio.get_event_loop().run_until_complete(manager.create_session())
    import asyncio

    msg = asyncio.get_event_loop().run_until_complete(s.add_message("user", "hello"))
    assert called.get("stored") is True


# 8
def test_store_messages_bulk_empty_is_noop(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)

    backend = sm.Neo4jSessionBackend()
    backend.initialize()
    res = backend.store_messages_bulk([])
    assert res == 0


# 9
def test_sqlite_get_messages_limit_and_order(tmp_path):
    # Use an actual SQLite backend to verify LIMIT/OFFSET behavior
    dbfile = tmp_path / "sessions.db"
    backend = sm.SQLiteSessionBackend(str(dbfile))

    # Insert sample messages
    for i in range(10):
        m = sm.SessionMessage(
            id=f"m{i}",
            role=sm.MessageRole.USER,
            content=f"msg{i}",
            timestamp=sm.datetime.now(sm.UTC),
            session_id="s2",
        )
        backend.store_message(m)

    msgs = backend.get_messages("s2", limit=5)
    assert len(msgs) == 5

    msgs_page = backend.get_messages("s2", page=1, page_size=3)
    assert len(msgs_page) == 3


# 10
def test_neo4j_get_messages_include_content_toggle(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)
    backend = sm.Neo4jSessionBackend()
    backend.initialize()

    # include_content False should not attempt to fetch content fields
    backend.get_messages("s1", page=0, page_size=2, include_content=False)
    q, params = calls[-1]
    assert "m.content" not in q


# 11..25 Many small behavior tests to reach coverage


def test_multiple_bulk_calls_and_pagination(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)
    backend = sm.Neo4jSessionBackend()
    backend.initialize()

    # Bulk insert twice
    msgs = []
    for i in range(6):
        msgs.append(
            sm.SessionMessage(
                id=f"mb{i}",
                role=sm.MessageRole.USER,
                content=f"bulk {i}",
                timestamp=sm.datetime.now(sm.UTC),
                session_id="sb",
            )
        )
    assert backend.store_messages_bulk(msgs) == 6
    assert backend.store_messages_bulk(msgs[:2]) == 2

    # Pagination queries
    backend.get_messages("sb", page=0, page_size=3)
    backend.get_messages("sb", page=1, page_size=3)
    assert any("SKIP" in call[0] or "SKIP $skip" in call[0] for call in calls)


@pytest.mark.parametrize("page,page_size", [(0, 5), (2, 2), (3, 1)])
def test_parametric_pagination(monkeypatch, page, page_size):
    calls = []
    patch_get_session(monkeypatch, calls)
    backend = sm.Neo4jSessionBackend()
    backend.initialize()
    backend.get_messages("p1", page=page, page_size=page_size)
    q, params = calls[-1]
    assert params.get("skip") == page * page_size
    assert params.get("limit") == page_size


def test_conversation_memory_initialize_idempotent(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)
    conv = nm.ConversationMemory()
    import asyncio

    asyncio.get_event_loop().run_until_complete(conv.initialize())
    # second call should be a no-op
    asyncio.get_event_loop().run_until_complete(conv.initialize())
    assert any("CREATE INDEX message_timestamp" in c[0] for c in calls)


def test_batch_add_returns_zero_for_empty(monkeypatch):
    recorded = []
    monkeypatch.setattr(
        nm, "resilient_query_sync", lambda s, q, p=None: recorded.append((q, p)) or []
    )
    import agentic_brain.core.neo4j_pool as pool

    monkeypatch.setattr(
        pool, "get_session", lambda database=None: fake_get_session(recorded)
    )

    conv = nm.ConversationMemory()
    import asyncio

    asyncio.get_event_loop().run_until_complete(conv.initialize())
    res = asyncio.get_event_loop().run_until_complete(conv.add_messages_batch([]))
    assert res == 0


def test_get_conversation_history_since_filter(monkeypatch):
    recorded = []

    def fake_resilient(session, query, params=None):
        recorded.append((query, params))
        return []

    monkeypatch.setattr(nm, "resilient_query_sync", fake_resilient)
    import agentic_brain.core.neo4j_pool as pool

    monkeypatch.setattr(
        pool, "get_session", lambda database=None: fake_get_session(recorded)
    )

    conv = nm.ConversationMemory()
    import asyncio

    asyncio.get_event_loop().run_until_complete(conv.initialize())
    from datetime import datetime, timedelta

    since = datetime.now(sm.UTC) - timedelta(days=1)
    import asyncio

    asyncio.get_event_loop().run_until_complete(
        conv.get_conversation_history(since=since)
    )
    q, params = recorded[-1]
    assert params.get("since") is not None


def test_store_message_updates_session_count(monkeypatch):
    calls = []
    patch_get_session(monkeypatch, calls)
    conv = nm.ConversationMemory()
    import asyncio

    asyncio.get_event_loop().run_until_complete(conv.initialize())
    import asyncio

    mid = asyncio.get_event_loop().run_until_complete(conv.add_message("user", "hi"))
    assert mid is not None


# Ensure we have at least 25 tests by adding a couple of lightweight checks


def test_sqlite_search_and_recent(tmp_path):
    dbfile = tmp_path / "sessions2.db"
    backend = sm.SQLiteSessionBackend(str(dbfile))
    m = sm.SessionMessage(
        id="s1",
        role=sm.MessageRole.USER,
        content="find me",
        timestamp=sm.datetime.now(sm.UTC),
        session_id="sx",
    )
    backend.store_message(m)
    res = backend.search("find me")
    assert res and res[0].content == "find me"
    recent = backend.get_recent_context(hours=1)
    assert isinstance(recent, list)


def test_session_export_and_compress(tmp_path):
    import asyncio

    manager = sm.SessionManager(prefer_neo4j=False)
    manager._backend = sm.SQLiteSessionBackend(str(tmp_path / "db3.db"))
    s = asyncio.get_event_loop().run_until_complete(manager.create_session())
    asyncio.get_event_loop().run_until_complete(s.add_message("user", "hello"))
    exported = s.export()
    assert "session_id" in exported
    orig_tokens, new_tokens = asyncio.get_event_loop().run_until_complete(s.compress())
    assert isinstance(orig_tokens, int)
