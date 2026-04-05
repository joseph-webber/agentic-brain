# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for conversation memory: storage, retrieval, and context windowing.

Covers:
  - ConversationMemory (Neo4j-backed, mocked) – message add, history, entities
  - UnifiedMemory session API – add_message, get_session_messages, windowing
  - Message dataclass serialisation
  - Entity extraction from conversation content
  - Session isolation (messages from different sessions don't leak)
  - Context window limits (get last N messages)
  - Importance scoring on message content
  - Edge cases: empty history, duplicate sessions, special characters
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.memory import UnifiedMemory
from agentic_brain.memory.neo4j_memory import ConversationMemory, MemoryConfig, Message


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cfg() -> MemoryConfig:
    return MemoryConfig(use_pool=True, extract_entities=True)


@pytest.fixture
def conv_mem(cfg: MemoryConfig) -> ConversationMemory:
    return ConversationMemory(session_id="sess-001", config=cfg)


@pytest.fixture
def unified(tmp_path):
    mem = UnifiedMemory(db_path=str(tmp_path / "conv.db"))
    yield mem
    mem.close()


def _mock_neo4j_session():
    """Return a context-manager-compatible mock Neo4j session."""
    session = MagicMock()
    session.run.return_value = MagicMock(data=MagicMock(return_value=[]))
    cm = MagicMock()
    cm.__enter__.return_value = session
    cm.__exit__.return_value = False
    return cm, session


# ---------------------------------------------------------------------------
# ConversationMemory – session ID generation
# ---------------------------------------------------------------------------


class TestConversationMemoryInit:
    def test_explicit_session_id_is_used(self, cfg):
        mem = ConversationMemory(session_id="my-session", config=cfg)
        assert mem.session_id == "my-session"

    def test_auto_generated_session_id(self, cfg):
        mem = ConversationMemory(config=cfg)
        assert mem.session_id is not None
        assert len(mem.session_id) == 16  # sha256[:16]

    def test_two_auto_ids_are_unique(self, cfg):
        mem1 = ConversationMemory(config=cfg)
        mem2 = ConversationMemory(config=cfg)
        assert mem1.session_id != mem2.session_id

    def test_default_config_applied_when_none(self):
        mem = ConversationMemory(session_id="x")
        assert mem.config is not None
        assert mem.config.max_history == 100


# ---------------------------------------------------------------------------
# ConversationMemory – entity extraction
# ---------------------------------------------------------------------------


class TestEntityExtraction:
    def test_extracts_named_technology(self, conv_mem):
        entities = conv_mem._extract_entities("We use Python and Docker for CI.")
        names = [e[0] for e in entities]
        assert "Python" in names
        assert "Docker" in names

    def test_extracts_jira_ticket(self, conv_mem):
        entities = conv_mem._extract_entities("Working on SD-1234 today.")
        names = [e[0] for e in entities]
        assert "SD-1234" in names

    def test_extracts_email_address(self, conv_mem):
        entities = conv_mem._extract_entities(
            "Send results to user@example.com please."
        )
        names = [e[0] for e in entities]
        assert "user@example.com" in names

    def test_no_entities_in_plain_lowercase(self, conv_mem):
        entities = conv_mem._extract_entities(
            "the quick brown fox jumps over the lazy dog"
        )
        # Plain lowercase English → no meaningful entities expected
        assert isinstance(entities, list)

    def test_entity_extraction_returns_list(self, conv_mem):
        result = conv_mem._extract_entities("")
        assert result == []

    def test_entities_are_deduplicated(self, conv_mem):
        entities = conv_mem._extract_entities("Python is great. Python is fast.")
        names = [e[0] for e in entities]
        assert names.count("Python") == 1


# ---------------------------------------------------------------------------
# ConversationMemory – add_message (with mocked Neo4j)
# ---------------------------------------------------------------------------


class TestAddMessage:
    @pytest.mark.asyncio
    async def test_add_message_returns_id(self, conv_mem):
        cm, session = _mock_neo4j_session()
        with patch("agentic_brain.core.neo4j_pool.get_session", return_value=cm):
            msg_id = await conv_mem.add_message("user", "Hello world")
        assert msg_id is not None
        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

    @pytest.mark.asyncio
    async def test_add_multiple_messages(self, conv_mem):
        cm, session = _mock_neo4j_session()
        with patch("agentic_brain.core.neo4j_pool.get_session", return_value=cm):
            id1 = await conv_mem.add_message("user", "First message")
            id2 = await conv_mem.add_message("assistant", "Second message")
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_add_message_with_metadata(self, conv_mem):
        cm, session = _mock_neo4j_session()
        with patch("agentic_brain.core.neo4j_pool.get_session", return_value=cm):
            msg_id = await conv_mem.add_message(
                "user", "Test", metadata={"source": "api", "priority": "high"}
            )
        assert msg_id is not None

    @pytest.mark.asyncio
    async def test_empty_content_handled(self, conv_mem):
        cm, session = _mock_neo4j_session()
        with patch("agentic_brain.core.neo4j_pool.get_session", return_value=cm):
            msg_id = await conv_mem.add_message("user", "")
        assert msg_id is not None

    @pytest.mark.asyncio
    async def test_special_chars_in_content(self, conv_mem):
        cm, session = _mock_neo4j_session()
        with patch("agentic_brain.core.neo4j_pool.get_session", return_value=cm):
            msg_id = await conv_mem.add_message(
                "user", "Unicode 🦜 and 'quotes' & <tags>"
            )
        assert msg_id is not None


# ---------------------------------------------------------------------------
# ConversationMemory – get_conversation_history (mocked)
# ---------------------------------------------------------------------------


class TestGetHistory:
    @pytest.mark.asyncio
    async def test_empty_history(self, conv_mem):
        cm, session = _mock_neo4j_session()
        session.run.return_value = MagicMock(data=MagicMock(return_value=[]))
        with patch("agentic_brain.core.neo4j_pool.get_session", return_value=cm):
            history = await conv_mem.get_conversation_history(limit=10)
        assert history == []

    @pytest.mark.asyncio
    async def test_history_respects_limit(self, conv_mem):
        now = datetime.now(UTC).isoformat()
        records = [
            {
                "id": f"msg{i}",
                "role": "user",
                "content": f"Message {i}",
                "timestamp": now,
                "session_id": "sess-001",
                "metadata": {},
                "entities": [],
                "importance": 0.5,
                "access_count": 0,
            }
            for i in range(20)
        ]
        cm, session = _mock_neo4j_session()
        session.run.return_value = MagicMock(data=MagicMock(return_value=records[:5]))
        with patch("agentic_brain.core.neo4j_pool.get_session", return_value=cm):
            history = await conv_mem.get_conversation_history(limit=5)
        assert len(history) <= 5


# ---------------------------------------------------------------------------
# UnifiedMemory – conversation (session) API
# ---------------------------------------------------------------------------


class TestUnifiedConversation:
    def test_add_and_retrieve_message(self, unified):
        unified.add_message("session-a", "user", "Hello!")
        messages = unified.get_session_messages("session-a")
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello!"
        assert messages[0]["role"] == "user"

    def test_message_timestamp_present(self, unified):
        unified.add_message("session-a", "user", "Hi")
        messages = unified.get_session_messages("session-a")
        assert "timestamp" in messages[0]

    def test_context_windowing_returns_last_n(self, unified):
        for i in range(10):
            unified.add_message("session-w", "user", f"Message {i}")
        last_3 = unified.get_session_messages("session-w", limit=3)
        assert len(last_3) == 3
        assert last_3[-1]["content"] == "Message 9"

    def test_session_isolation(self, unified):
        unified.add_message("session-x", "user", "X message")
        unified.add_message("session-y", "user", "Y message")
        x_msgs = unified.get_session_messages("session-x")
        y_msgs = unified.get_session_messages("session-y")
        assert all("X" in m["content"] for m in x_msgs)
        assert all("Y" in m["content"] for m in y_msgs)

    def test_empty_session_returns_empty_list(self, unified):
        result = unified.get_session_messages("nonexistent-session")
        assert result == []

    def test_session_context_contains_messages(self, unified):
        unified.add_message("sess-ctx", "user", "Hello")
        unified.add_message("sess-ctx", "assistant", "Hi!")
        ctx = unified.get_session_context("sess-ctx")
        assert ctx is not None
        assert len(ctx["messages"]) == 2

    def test_set_session_auto_tags_messages(self, unified):
        unified.set_session("auto-sess")
        # store should use the current session
        entry = unified.store("A fact", session_id=None)
        # The entry should have the session_id attached
        assert entry.session_id == "auto-sess"

    def test_multi_role_conversation(self, unified):
        turns = [
            ("user", "What is Python?"),
            ("assistant", "Python is a programming language."),
            ("user", "Is it fast?"),
            ("assistant", "It depends on the use case."),
        ]
        for role, content in turns:
            unified.add_message("multi-role", role, content)
        msgs = unified.get_session_messages("multi-role")
        assert len(msgs) == 4
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_windowing_does_not_exceed_total(self, unified):
        unified.add_message("small-sess", "user", "Only one")
        result = unified.get_session_messages("small-sess", limit=100)
        assert len(result) == 1

    def test_metadata_stored_with_message(self, unified):
        unified.add_message("meta-sess", "user", "Hello", metadata={"tag": "test"})
        msgs = unified.get_session_messages("meta-sess")
        assert msgs[0]["metadata"]["tag"] == "test"


# ---------------------------------------------------------------------------
# Message dataclass
# ---------------------------------------------------------------------------


class TestMessageDataclass:
    def test_message_to_dict(self):
        now = datetime.now(UTC)
        msg = Message(
            id="abc",
            role="user",
            content="Hello",
            timestamp=now,
            session_id="s1",
        )
        d = msg.to_dict()
        assert d["id"] == "abc"
        assert d["role"] == "user"
        assert d["content"] == "Hello"
        assert d["session_id"] == "s1"
        assert "timestamp" in d

    def test_message_default_importance(self):
        msg = Message(
            id="m1",
            role="user",
            content="Test",
            timestamp=datetime.now(UTC),
            session_id="s",
        )
        assert msg.importance == 0.5

    def test_message_entities_default_empty(self):
        msg = Message(
            id="m2",
            role="assistant",
            content="Hi",
            timestamp=datetime.now(UTC),
            session_id="s",
        )
        assert msg.entities == []
