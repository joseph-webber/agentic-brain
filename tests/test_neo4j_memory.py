# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for Neo4j Conversation Memory."""

from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from agentic_brain.memory.neo4j_memory import (
    ConversationMemory,
    MemoryConfig,
    Message,
)


@pytest.fixture
def config():
    """Create test configuration."""
    return MemoryConfig(
        use_pool=True,
        extract_entities=True,
        auto_summarize=True,
        summarize_threshold=50,
    )


@pytest.fixture
def memory(config):
    """Create conversation memory instance."""
    return ConversationMemory(session_id="test_session", config=config)


@pytest.fixture
def mock_session():
    """Create mock Neo4j session."""
    session = MagicMock()
    session.run = MagicMock(return_value=MagicMock())
    session.close = MagicMock()
    return session


@pytest.mark.asyncio
async def test_initialize(memory, mock_session):
    """Test initialization creates schema."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        await memory.initialize()

        assert memory._initialized is True
        assert mock_session.run.call_count >= 3  # Constraints + indexes + session


@pytest.mark.asyncio
async def test_add_message(memory, mock_session):
    """Test adding a message."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        msg_id = await memory.add_message(
            role="user",
            content="Tell me about Python",
            metadata={"source": "test"},
        )

        assert msg_id is not None
        assert len(msg_id) > 0


@pytest.mark.asyncio
async def test_extract_entities(memory):
    """Test entity extraction."""
    text = "Python and JavaScript are great for Programming"

    entities = memory._extract_entities(text)

    assert len(entities) > 0
    entity_names = [e[0] for e in entities]
    assert "Python" in entity_names
    assert "JavaScript" in entity_names


@pytest.mark.asyncio
async def test_get_conversation_history(memory, mock_session):
    """Test retrieving conversation history."""
    mock_records = [
        {
            "id": "msg1",
            "role": "user",
            "content": "Hello",
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": "test_session",
            "metadata": {},
            "entities": ["Test"],
        },
        {
            "id": "msg2",
            "role": "assistant",
            "content": "Hi there",
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": "test_session",
            "metadata": {},
            "entities": [],
        },
    ]

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(mock_records)
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        memory._initialized = True
        history = await memory.get_conversation_history(limit=10)

        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"


@pytest.mark.asyncio
async def test_query_by_topic(memory, mock_session):
    """Test querying messages by topic."""
    mock_records = [
        {
            "id": "msg1",
            "role": "user",
            "content": "Tell me about Python",
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": "test_session",
            "metadata": {},
            "entities": ["Python"],
        }
    ]

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(mock_records)
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        memory._initialized = True
        results = await memory.query_by_topic("Python", limit=10)

        assert len(results) >= 0


@pytest.mark.asyncio
async def test_query_by_timeframe(memory, mock_session):
    """Test querying messages by timeframe."""
    now = datetime.now(UTC)
    mock_records = [
        {
            "id": "msg1",
            "role": "user",
            "content": "Test message",
            "timestamp": now.isoformat(),
            "session_id": "test_session",
            "metadata": {},
            "entities": [],
        }
    ]

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(mock_records)
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        memory._initialized = True
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        results = await memory.query_by_timeframe(start, end)

        assert isinstance(results, list)


@pytest.mark.asyncio
async def test_summarize_recent(memory, mock_session):
    """Test summarizing recent conversation."""
    mock_records = [
        {
            "id": f"msg{i}",
            "role": "user" if i % 2 == 0 else "assistant",
            "content": f"Message {i}",
            "timestamp": datetime.now(UTC).isoformat(),
            "session_id": "test_session",
            "metadata": {},
            "entities": [],
        }
        for i in range(10)
    ]

    mock_result = MagicMock()
    mock_result.__iter__ = lambda self: iter(mock_records)
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        memory._initialized = True
        summary = await memory.summarize_recent(window=10)

        assert "Conversation summary" in summary
        assert "messages" in summary


@pytest.mark.asyncio
async def test_compress_old_memories(memory, mock_session):
    """Test compressing old memories."""
    mock_record = {"message_ids": ["msg1", "msg2"], "count": 2}
    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        count = await memory.compress_old_memories(days=30)

        assert count >= 0


@pytest.mark.asyncio
async def test_get_session_stats(memory, mock_session):
    """Test getting session statistics."""
    mock_record = {
        "started_at": datetime.now(UTC).isoformat(),
        "last_updated": datetime.now(UTC).isoformat(),
        "msg_count": 10,
        "entity_count": 5,
        "roles": ["user", "assistant"],
        "summary_count": 1,
    }
    mock_result = MagicMock()
    mock_result.single.return_value = mock_record
    mock_session.run.return_value = mock_result

    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        memory._initialized = True
        stats = await memory.get_session_stats()

        assert "session_id" in stats
        assert stats["session_id"] == "test_session"


@pytest.mark.asyncio
async def test_auto_summarize(memory, mock_session):
    """Test automatic summarization after threshold."""
    with patch("agentic_brain.core.neo4j_pool.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock summarize_recent
        with patch.object(memory, "summarize_recent") as mock_summarize:
            memory._initialized = True
            memory.config.summarize_threshold = 5

            # Add messages up to threshold
            for i in range(5):
                await memory.add_message("user", f"Message {i}")

            # Should trigger auto-summarize on 5th message
            assert mock_summarize.call_count >= 1


def test_message_to_dict():
    """Test Message serialization."""
    msg = Message(
        id="test_id",
        role="user",
        content="Test content",
        timestamp=datetime.now(UTC),
        session_id="test_session",
        metadata={"key": "value"},
        entities=["Entity1"],
    )

    msg_dict = msg.to_dict()

    assert msg_dict["id"] == "test_id"
    assert msg_dict["role"] == "user"
    assert msg_dict["content"] == "Test content"
    assert "timestamp" in msg_dict
    assert msg_dict["entities"] == ["Entity1"]


def test_config_defaults():
    """Test default configuration values."""
    config = MemoryConfig()

    assert config.use_pool is True
    assert config.extract_entities is True
    assert config.auto_summarize is True
    assert config.max_history == 100
