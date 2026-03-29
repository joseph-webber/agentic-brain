# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Tests for session backend implementations.

Tests cover:
- InMemorySessionBackend (full coverage)
- RedisSessionBackend (mocked)
- Factory function
- Session lifecycle
"""

import os
from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.api.sessions import (
    InMemorySessionBackend,
    RedisSessionBackend,
    Session,
    generate_message_id,
    generate_session_id,
    get_session_backend,
    reset_session_backend,
)


class TestSession:
    """Tests for the Session dataclass."""

    def test_session_creation(self):
        """Test creating a session with required fields."""
        now = datetime.now(UTC)
        session = Session(
            id="sess_abc123",
            user_id="user_1",
            created_at=now,
            updated_at=now,
        )

        assert session.id == "sess_abc123"
        assert session.user_id == "user_1"
        assert session.created_at == now
        assert session.updated_at == now
        assert session.message_count == 0
        assert session.metadata == {}

    def test_session_with_metadata(self):
        """Test creating a session with metadata."""
        now = datetime.now(UTC)
        session = Session(
            id="sess_abc123",
            user_id=None,
            created_at=now,
            updated_at=now,
            message_count=5,
            metadata={"key": "value"},
        )

        assert session.message_count == 5
        assert session.metadata == {"key": "value"}

    def test_session_to_dict(self):
        """Test serializing session to dictionary."""
        now = datetime.now(UTC)
        session = Session(
            id="sess_abc123",
            user_id="user_1",
            created_at=now,
            updated_at=now,
            message_count=3,
            metadata={"foo": "bar"},
        )

        data = session.to_dict()

        assert data["id"] == "sess_abc123"
        assert data["user_id"] == "user_1"
        assert data["created_at"] == now.isoformat()
        assert data["updated_at"] == now.isoformat()
        assert data["message_count"] == 3
        assert data["metadata"] == {"foo": "bar"}

    def test_session_from_dict(self):
        """Test deserializing session from dictionary."""
        now = datetime.now(UTC)
        data = {
            "id": "sess_abc123",
            "user_id": "user_1",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "message_count": 3,
            "metadata": {"foo": "bar"},
        }

        session = Session.from_dict(data)

        assert session.id == "sess_abc123"
        assert session.user_id == "user_1"
        assert session.message_count == 3
        assert session.metadata == {"foo": "bar"}

    def test_session_from_dict_with_datetime_objects(self):
        """Test deserializing when datetime fields are already datetime objects."""
        now = datetime.now(UTC)
        data = {
            "id": "sess_abc123",
            "user_id": None,
            "created_at": now,
            "updated_at": now,
        }

        session = Session.from_dict(data)

        assert session.created_at == now
        assert session.updated_at == now


class TestInMemorySessionBackend:
    """Tests for the in-memory session backend."""

    @pytest.fixture
    def backend(self):
        """Create a fresh in-memory backend for each test."""
        return InMemorySessionBackend()

    @pytest.mark.asyncio
    async def test_create_session(self, backend):
        """Test creating a new session."""
        session = await backend.create("sess_123", user_id="user_1")

        assert session.id == "sess_123"
        assert session.user_id == "user_1"
        assert session.message_count == 0
        assert isinstance(session.created_at, datetime)
        assert isinstance(session.updated_at, datetime)

    @pytest.mark.asyncio
    async def test_create_session_without_user(self, backend):
        """Test creating a session without user_id."""
        session = await backend.create("sess_123")

        assert session.id == "sess_123"
        assert session.user_id is None

    @pytest.mark.asyncio
    async def test_get_session(self, backend):
        """Test retrieving an existing session."""
        await backend.create("sess_123", user_id="user_1")

        session = await backend.get("sess_123")

        assert session is not None
        assert session.id == "sess_123"
        assert session.user_id == "user_1"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, backend):
        """Test retrieving a session that doesn't exist."""
        session = await backend.get("nonexistent")

        assert session is None

    @pytest.mark.asyncio
    async def test_update_session(self, backend):
        """Test updating session attributes."""
        await backend.create("sess_123")

        updated = await backend.update("sess_123", message_count=5)

        assert updated.message_count == 5

    @pytest.mark.asyncio
    async def test_update_session_increment(self, backend):
        """Test incrementing message count."""
        await backend.create("sess_123")

        await backend.update("sess_123", increment_messages=True)
        await backend.update("sess_123", increment_messages=True)

        session = await backend.get("sess_123")
        assert session.message_count == 2

    @pytest.mark.asyncio
    async def test_update_session_metadata(self, backend):
        """Test updating session metadata."""
        await backend.create("sess_123")

        await backend.update("sess_123", metadata={"key": "value"})

        session = await backend.get("sess_123")
        assert session.metadata == {"key": "value"}

    @pytest.mark.asyncio
    async def test_update_nonexistent_session(self, backend):
        """Test updating a session that doesn't exist."""
        with pytest.raises(KeyError):
            await backend.update("nonexistent")

    @pytest.mark.asyncio
    async def test_delete_session(self, backend):
        """Test deleting a session."""
        await backend.create("sess_123")
        await backend.add_message("sess_123", {"content": "test"})

        result = await backend.delete("sess_123")

        assert result is True
        assert await backend.get("sess_123") is None
        assert await backend.get_messages("sess_123") == []

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, backend):
        """Test deleting a session that doesn't exist."""
        result = await backend.delete("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_all_sessions(self, backend):
        """Test listing all sessions."""
        await backend.create("sess_1")
        await backend.create("sess_2")
        await backend.create("sess_3")

        sessions = await backend.list_all()

        assert len(sessions) == 3
        session_ids = {s.id for s in sessions}
        assert session_ids == {"sess_1", "sess_2", "sess_3"}

    @pytest.mark.asyncio
    async def test_list_all_empty(self, backend):
        """Test listing when no sessions exist."""
        sessions = await backend.list_all()

        assert sessions == []

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, backend):
        """Test cleaning up expired sessions."""
        # Create old session
        await backend.create("sess_old")
        # Manually set created_at to be old
        backend._sessions["sess_old"].created_at = datetime.now(UTC) - timedelta(
            hours=2
        )

        # Create new session
        await backend.create("sess_new")

        # Cleanup with 1 hour max age
        expired = await backend.cleanup_expired(3600)

        assert expired == 1
        assert await backend.get("sess_old") is None
        assert await backend.get("sess_new") is not None

    @pytest.mark.asyncio
    async def test_add_message(self, backend):
        """Test adding messages to a session."""
        await backend.create("sess_123")

        await backend.add_message("sess_123", {"role": "user", "content": "Hello"})
        await backend.add_message("sess_123", {"role": "assistant", "content": "Hi"})

        messages = await backend.get_messages("sess_123")

        assert len(messages) == 2
        assert messages[0]["content"] == "Hello"
        assert messages[1]["content"] == "Hi"

    @pytest.mark.asyncio
    async def test_get_messages_empty(self, backend):
        """Test getting messages from empty/nonexistent session."""
        messages = await backend.get_messages("nonexistent")

        assert messages == []

    @pytest.mark.asyncio
    async def test_clear_all(self, backend):
        """Test clearing all sessions."""
        await backend.create("sess_1")
        await backend.create("sess_2")
        await backend.add_message("sess_1", {"content": "test"})

        count = await backend.clear_all()

        assert count == 2
        assert await backend.list_all() == []
        assert await backend.get_messages("sess_1") == []

    @pytest.mark.asyncio
    async def test_ensure_exists_creates(self, backend):
        """Test ensure_exists creates new session."""
        session = await backend.ensure_exists("sess_new", user_id="user_1")

        assert session.id == "sess_new"
        assert session.user_id == "user_1"

    @pytest.mark.asyncio
    async def test_ensure_exists_updates(self, backend):
        """Test ensure_exists updates existing session."""
        from datetime import datetime
        from unittest.mock import patch

        await backend.create("sess_123")
        original = await backend.get("sess_123")

        # Mock datetime to return a future time for update
        future_time = datetime.now(UTC).replace(year=2030)
        with patch("agentic_brain.api.sessions.datetime") as mock_dt:
            mock_dt.now.return_value = future_time
            mock_dt.fromisoformat = datetime.fromisoformat
            session = await backend.ensure_exists("sess_123")

        assert session.id == "sess_123"
        assert session.updated_at >= original.updated_at


class TestRedisSessionBackend:
    """Tests for the Redis session backend with mocked Redis."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        mock = MagicMock()
        mock.ping = AsyncMock(return_value=True)
        mock.get = AsyncMock(return_value=None)
        mock.set = AsyncMock(return_value=True)
        mock.delete = AsyncMock(return_value=1)
        mock.exists = AsyncMock(return_value=1)
        mock.sadd = AsyncMock(return_value=1)
        mock.srem = AsyncMock(return_value=1)
        mock.smembers = AsyncMock(return_value=set())
        mock.lrange = AsyncMock(return_value=[])
        mock.rpush = AsyncMock(return_value=1)
        mock.expire = AsyncMock(return_value=True)
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def backend(self, mock_redis):
        """Create a Redis backend with mocked client."""
        backend = RedisSessionBackend(redis_url="redis://localhost:6379")
        backend._client = mock_redis
        return backend

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting to Redis."""
        pytest.importorskip("redis")  # Skip if redis not installed

        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_client = MagicMock()
            mock_client.ping = AsyncMock(return_value=True)
            mock_from_url.return_value = mock_client

            backend = RedisSessionBackend()
            await backend.connect()

            mock_from_url.assert_called_once()
            mock_client.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_missing_redis(self):
        """Test error when redis package not installed."""
        backend = RedisSessionBackend()

        with patch.dict("sys.modules", {"redis.asyncio": None}):
            with patch("builtins.__import__", side_effect=ImportError):
                with pytest.raises(ImportError) as exc_info:
                    await backend.connect()

                assert "redis package not installed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_disconnect(self, backend, mock_redis):
        """Test disconnecting from Redis."""
        await backend.disconnect()

        mock_redis.close.assert_called_once()
        assert backend._client is None

    @pytest.mark.asyncio
    async def test_create_session(self, backend, mock_redis):
        """Test creating a session in Redis."""
        session = await backend.create("sess_123", user_id="user_1")

        assert session.id == "sess_123"
        assert session.user_id == "user_1"
        mock_redis.set.assert_called_once()
        mock_redis.sadd.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session(self, backend, mock_redis):
        """Test retrieving a session from Redis."""
        now = datetime.now(UTC)
        {
            "id": "sess_123",
            "user_id": "user_1",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "message_count": 5,
            "metadata": {},
        }
        mock_redis.get = AsyncMock(
            return_value='{"id": "sess_123", "user_id": "user_1", "created_at": "'
            + now.isoformat()
            + '", "updated_at": "'
            + now.isoformat()
            + '", "message_count": 5, "metadata": {}}'
        )

        session = await backend.get("sess_123")

        assert session is not None
        assert session.id == "sess_123"
        assert session.message_count == 5

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, backend, mock_redis):
        """Test retrieving a nonexistent session."""
        mock_redis.get = AsyncMock(return_value=None)

        session = await backend.get("nonexistent")

        assert session is None

    @pytest.mark.asyncio
    async def test_update_session(self, backend, mock_redis):
        """Test updating a session in Redis."""
        now = datetime.now(UTC)
        mock_redis.get = AsyncMock(
            return_value='{"id": "sess_123", "user_id": null, "created_at": "'
            + now.isoformat()
            + '", "updated_at": "'
            + now.isoformat()
            + '", "message_count": 0, "metadata": {}}'
        )

        session = await backend.update("sess_123", message_count=5)

        assert session.message_count == 5
        mock_redis.set.assert_called()

    @pytest.mark.asyncio
    async def test_delete_session(self, backend, mock_redis):
        """Test deleting a session from Redis."""
        mock_redis.exists = AsyncMock(return_value=1)

        result = await backend.delete("sess_123")

        assert result is True
        mock_redis.delete.assert_called()
        mock_redis.srem.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, backend, mock_redis):
        """Test deleting a nonexistent session."""
        mock_redis.exists = AsyncMock(return_value=0)

        result = await backend.delete("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_all_sessions(self, backend, mock_redis):
        """Test listing all sessions from Redis."""
        now = datetime.now(UTC)
        mock_redis.smembers = AsyncMock(return_value={"sess_1", "sess_2"})
        mock_redis.get = AsyncMock(
            return_value='{"id": "sess_1", "user_id": null, "created_at": "'
            + now.isoformat()
            + '", "updated_at": "'
            + now.isoformat()
            + '", "message_count": 0, "metadata": {}}'
        )

        sessions = await backend.list_all()

        # Both sessions should be returned (mocked to return same data)
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_add_message(self, backend, mock_redis):
        """Test adding a message to Redis."""
        await backend.add_message("sess_123", {"role": "user", "content": "Hello"})

        mock_redis.rpush.assert_called_once()
        mock_redis.expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_messages(self, backend, mock_redis):
        """Test getting messages from Redis."""
        mock_redis.lrange = AsyncMock(
            return_value=[
                '{"role": "user", "content": "Hello"}',
                '{"role": "assistant", "content": "Hi"}',
            ]
        )

        messages = await backend.get_messages("sess_123")

        assert len(messages) == 2
        assert messages[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_clear_all(self, backend, mock_redis):
        """Test clearing all sessions from Redis."""
        mock_redis.smembers = AsyncMock(return_value={"sess_1", "sess_2"})

        count = await backend.clear_all()

        assert count == 2
        assert mock_redis.delete.call_count >= 1


class TestFactoryFunction:
    """Tests for the get_session_backend factory function."""

    def setup_method(self):
        """Reset backend before each test."""
        reset_session_backend()

    def teardown_method(self):
        """Clean up after each test."""
        reset_session_backend()
        # Restore env vars
        if "SESSION_BACKEND" in os.environ:
            del os.environ["SESSION_BACKEND"]

    def test_default_memory_backend(self):
        """Test that memory backend is default."""
        backend = get_session_backend()

        assert isinstance(backend, InMemorySessionBackend)

    def test_memory_backend_explicit(self):
        """Test explicit memory backend selection."""
        os.environ["SESSION_BACKEND"] = "memory"

        backend = get_session_backend()

        assert isinstance(backend, InMemorySessionBackend)

    def test_redis_backend_selection(self):
        """Test Redis backend selection."""
        os.environ["SESSION_BACKEND"] = "redis"

        backend = get_session_backend()

        assert isinstance(backend, RedisSessionBackend)

    def test_singleton_behavior(self):
        """Test that same instance is returned."""
        backend1 = get_session_backend()
        backend2 = get_session_backend()

        assert backend1 is backend2

    def test_reset_backend(self):
        """Test resetting the backend."""
        backend1 = get_session_backend()
        reset_session_backend()
        backend2 = get_session_backend()

        assert backend1 is not backend2


class TestHelperFunctions:
    """Tests for session helper functions."""

    def test_generate_session_id(self):
        """Test session ID generation."""
        session_id = generate_session_id()

        assert session_id.startswith("sess_")
        assert len(session_id) == 17  # "sess_" + 12 hex chars

    def test_generate_session_id_uniqueness(self):
        """Test that generated IDs are unique."""
        ids = {generate_session_id() for _ in range(100)}

        assert len(ids) == 100

    def test_generate_message_id(self):
        """Test message ID generation."""
        message_id = generate_message_id()

        assert message_id.startswith("msg_")
        assert len(message_id) == 16  # "msg_" + 12 hex chars

    def test_generate_message_id_uniqueness(self):
        """Test that generated message IDs are unique."""
        ids = {generate_message_id() for _ in range(100)}

        assert len(ids) == 100


class TestSessionLifecycle:
    """Integration tests for complete session lifecycle."""

    @pytest.fixture
    def backend(self):
        """Create a fresh backend for lifecycle tests."""
        return InMemorySessionBackend()

    @pytest.mark.asyncio
    async def test_complete_lifecycle(self, backend):
        """Test a complete session lifecycle."""
        # Create session
        session = await backend.create("sess_lifecycle", user_id="user_1")
        assert session.id == "sess_lifecycle"

        # Add messages
        await backend.add_message(
            "sess_lifecycle",
            {
                "id": "msg_1",
                "role": "user",
                "content": "Hello",
            },
        )
        await backend.update("sess_lifecycle", increment_messages=True)

        await backend.add_message(
            "sess_lifecycle",
            {
                "id": "msg_2",
                "role": "assistant",
                "content": "Hi there!",
            },
        )
        await backend.update("sess_lifecycle", increment_messages=True)

        # Check state
        session = await backend.get("sess_lifecycle")
        assert session.message_count == 2

        messages = await backend.get_messages("sess_lifecycle")
        assert len(messages) == 2

        # List all
        all_sessions = await backend.list_all()
        assert len(all_sessions) == 1

        # Delete
        deleted = await backend.delete("sess_lifecycle")
        assert deleted is True

        # Verify deletion
        assert await backend.get("sess_lifecycle") is None
        assert await backend.get_messages("sess_lifecycle") == []

    @pytest.mark.asyncio
    async def test_multiple_sessions(self, backend):
        """Test managing multiple sessions."""
        # Create multiple sessions
        for i in range(5):
            await backend.create(f"sess_{i}", user_id=f"user_{i % 2}")
            await backend.add_message(f"sess_{i}", {"content": f"Message {i}"})

        # Verify all created
        sessions = await backend.list_all()
        assert len(sessions) == 5

        # Delete some
        await backend.delete("sess_0")
        await backend.delete("sess_2")

        # Verify remaining
        sessions = await backend.list_all()
        assert len(sessions) == 3
        remaining_ids = {s.id for s in sessions}
        assert remaining_ids == {"sess_1", "sess_3", "sess_4"}

        # Clear all
        count = await backend.clear_all()
        assert count == 3
        assert await backend.list_all() == []
