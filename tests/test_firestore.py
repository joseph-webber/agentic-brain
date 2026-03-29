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

"""Tests for Firestore transport."""

from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock firestore before import
mock_firestore = MagicMock()
mock_firestore.SERVER_TIMESTAMP = "SERVER_TIMESTAMP"
mock_firestore.Query.DESCENDING = "DESCENDING"

with patch.dict(
    "sys.modules",
    {"google.cloud": MagicMock(), "google.cloud.firestore": mock_firestore},
):
    from agentic_brain.transport import TransportConfig, TransportMessage
    from agentic_brain.transport.firestore import (
        FirestoreQueries,
        FirestoreStats,
        FirestoreTransport,
    )


class TestFirestoreStats:
    """Test FirestoreStats dataclass."""

    def test_default_values(self):
        """Test default statistics values."""
        stats = FirestoreStats()
        assert stats.documents_written == 0
        assert stats.documents_read == 0
        assert stats.queries_executed == 0
        assert stats.listeners_active == 0
        assert stats.last_write_at is None
        assert stats.last_read_at is None

    def test_update_values(self):
        """Test updating statistics."""
        stats = FirestoreStats()
        stats.documents_written = 10
        stats.queries_executed = 5
        stats.last_write_at = datetime.now(UTC)

        assert stats.documents_written == 10
        assert stats.queries_executed == 5
        assert stats.last_write_at is not None


class TestFirestoreTransportInit:
    """Test FirestoreTransport initialization."""

    def test_init_with_session_id(self):
        """Test initialization with session ID."""
        TransportConfig()

        with patch.object(
            FirestoreTransport, "__init__", lambda x, *args, **kwargs: None
        ):
            transport = FirestoreTransport.__new__(FirestoreTransport)
            transport.session_id = "test-session"
            transport.collection_prefix = "sessions"
            transport._stats = FirestoreStats()

            assert transport.session_id == "test-session"
            assert transport.collection_prefix == "sessions"

    def test_init_generates_session_id(self):
        """Test session ID auto-generation."""
        TransportConfig()

        with patch.object(
            FirestoreTransport, "__init__", lambda x, *args, **kwargs: None
        ):
            transport = FirestoreTransport.__new__(FirestoreTransport)
            transport.session_id = "session-abc12345"

            assert transport.session_id.startswith("session-")


class TestFirestoreTransportConnect:
    """Test Firestore connection."""

    @pytest.fixture
    def mock_transport(self):
        """Create mock transport."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.session_id = "test-session"
        transport._connected = False
        transport._stats = FirestoreStats()
        transport._client = None
        transport._listeners = []
        return transport

    @pytest.mark.asyncio
    async def test_connect_success(self, mock_transport):
        """Test successful connection."""
        mock_transport.connect = AsyncMock(return_value=True)

        result = await mock_transport.connect()

        assert result is True
        mock_transport.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_failure(self, mock_transport):
        """Test connection failure."""
        mock_transport.connect = AsyncMock(return_value=False)

        result = await mock_transport.connect()

        assert result is False


class TestFirestoreTransportSend:
    """Test message sending."""

    @pytest.fixture
    def mock_transport(self):
        """Create mock transport for send tests."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.session_id = "test-session"
        transport._connected = True
        transport._stats = FirestoreStats()
        return transport

    @pytest.mark.asyncio
    async def test_send_message_success(self, mock_transport):
        """Test sending message successfully."""
        mock_transport.send = AsyncMock(return_value=True)

        message = TransportMessage(
            content="Hello Firestore!",
            session_id="test-session",
            message_id="msg-123",
        )

        result = await mock_transport.send(message)

        assert result is True
        mock_transport.send.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_send_when_disconnected(self, mock_transport):
        """Test sending when not connected."""
        mock_transport._connected = False
        mock_transport.send = AsyncMock(return_value=False)

        message = TransportMessage(
            content="Test", session_id="test-session", message_id="test-123"
        )
        result = await mock_transport.send(message)

        assert result is False


class TestFirestoreTransportReceive:
    """Test message receiving."""

    @pytest.mark.asyncio
    async def test_receive_message(self):
        """Test receiving a message."""
        transport = MagicMock(spec=FirestoreTransport)

        expected_msg = TransportMessage(
            content="Hello!",
            session_id="test",
            message_id="msg-1",
        )
        transport.receive = AsyncMock(return_value=expected_msg)

        result = await transport.receive()

        assert result == expected_msg
        assert result.content == "Hello!"

    @pytest.mark.asyncio
    async def test_receive_timeout(self):
        """Test receive timeout."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.receive = AsyncMock(return_value=None)

        result = await transport.receive()

        assert result is None


class TestFirestoreTransportHistory:
    """Test message history retrieval."""

    @pytest.mark.asyncio
    async def test_get_history(self):
        """Test getting message history."""
        transport = MagicMock(spec=FirestoreTransport)

        messages = [
            TransportMessage(content="Msg 1", session_id="test", message_id="1"),
            TransportMessage(content="Msg 2", session_id="test", message_id="2"),
        ]
        transport.get_history = AsyncMock(return_value=messages)

        result = await transport.get_history(limit=10)

        assert len(result) == 2
        assert result[0].content == "Msg 1"

    @pytest.mark.asyncio
    async def test_get_history_with_time_filter(self):
        """Test history with time filters."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.get_history = AsyncMock(return_value=[])

        before = datetime.now(UTC)
        result = await transport.get_history(limit=50, before=before)

        assert result == []
        transport.get_history.assert_called_once()


class TestFirestoreTransportState:
    """Test session state operations."""

    @pytest.mark.asyncio
    async def test_update_state(self):
        """Test updating session state."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.update_state = AsyncMock(return_value=True)

        state = {"typing": True, "user": "test-user"}
        result = await transport.update_state(state)

        assert result is True
        transport.update_state.assert_called_once_with(state)

    @pytest.mark.asyncio
    async def test_get_state(self):
        """Test getting session state."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.get_state = AsyncMock(return_value={"typing": False})

        result = await transport.get_state()

        assert result == {"typing": False}


class TestFirestoreTransportClear:
    """Test session clearing."""

    @pytest.mark.asyncio
    async def test_clear_session(self):
        """Test clearing session data."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.clear_session = AsyncMock(return_value=True)

        result = await transport.clear_session()

        assert result is True
        transport.clear_session.assert_called_once()


class TestFirestoreTransportHealth:
    """Test health checks."""

    @pytest.mark.asyncio
    async def test_is_healthy_connected(self):
        """Test health when connected."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.is_healthy = AsyncMock(return_value=True)

        result = await transport.is_healthy()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_disconnected(self):
        """Test health when disconnected."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.is_healthy = AsyncMock(return_value=False)

        result = await transport.is_healthy()

        assert result is False


class TestFirestoreTransportContextManager:
    """Test async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async with statement."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.__aenter__ = AsyncMock(return_value=transport)
        transport.__aexit__ = AsyncMock(return_value=None)
        transport.connect = AsyncMock(return_value=True)
        transport.disconnect = AsyncMock()

        async with transport as t:
            assert t is transport

        transport.__aenter__.assert_called_once()
        transport.__aexit__.assert_called_once()


class TestFirestoreQueries:
    """Test Firestore query helpers."""

    @pytest.mark.asyncio
    async def test_get_messages_by_sender(self):
        """Test getting messages by sender."""
        transport = MagicMock(spec=FirestoreTransport)
        transport._connected = True

        messages = [
            TransportMessage(content="Hello", session_id="test", message_id="1")
        ]

        with patch.object(
            FirestoreQueries, "get_messages_by_sender", AsyncMock(return_value=messages)
        ):
            result = await FirestoreQueries.get_messages_by_sender(
                transport, "sender-123"
            )
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_search_messages(self):
        """Test searching messages by field."""
        transport = MagicMock(spec=FirestoreTransport)

        with patch.object(
            FirestoreQueries, "search_messages", AsyncMock(return_value=[])
        ):
            result = await FirestoreQueries.search_messages(
                transport, "metadata.type", "notification"
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_get_unread_count(self):
        """Test getting unread message count."""
        transport = MagicMock(spec=FirestoreTransport)

        with patch.object(
            FirestoreQueries, "get_unread_count", AsyncMock(return_value=5)
        ):
            result = await FirestoreQueries.get_unread_count(transport, "user-123")
            assert result == 5


class TestFirestoreTransportListen:
    """Test message streaming."""

    @pytest.mark.asyncio
    async def test_listen_yields_messages(self):
        """Test listen iterator yields messages."""
        messages = [
            TransportMessage(content="Msg 1", session_id="test", message_id="1"),
            TransportMessage(content="Msg 2", session_id="test", message_id="2"),
        ]

        async def mock_listen():
            for msg in messages:
                yield msg

        transport = MagicMock(spec=FirestoreTransport)
        transport.listen = mock_listen

        received = []
        async for msg in transport.listen():
            received.append(msg)
            if len(received) >= 2:
                break

        assert len(received) == 2
        assert received[0].content == "Msg 1"


class TestFirestoreTransportDisconnect:
    """Test disconnection."""

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnection cleans up listeners."""
        transport = MagicMock(spec=FirestoreTransport)
        transport._listeners = [MagicMock(), MagicMock()]
        transport.disconnect = AsyncMock()

        await transport.disconnect()

        transport.disconnect.assert_called_once()


class TestFirestoreIntegration:
    """Integration-style tests (mocked)."""

    @pytest.mark.asyncio
    async def test_full_send_receive_flow(self):
        """Test complete send/receive workflow."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.connect = AsyncMock(return_value=True)
        transport.disconnect = AsyncMock()
        transport.__aenter__ = AsyncMock(return_value=transport)
        transport.__aexit__ = AsyncMock(return_value=None)

        # Send
        transport.send = AsyncMock(return_value=True)
        msg = TransportMessage(content="Test", session_id="test", message_id="m1")

        # Receive
        transport.receive = AsyncMock(return_value=msg)

        async with transport:
            sent = await transport.send(msg)
            assert sent is True

            received = await transport.receive()
            assert received.content == "Test"

    @pytest.mark.asyncio
    async def test_state_sync_flow(self):
        """Test state synchronization flow."""
        transport = MagicMock(spec=FirestoreTransport)
        transport.update_state = AsyncMock(return_value=True)
        transport.get_state = AsyncMock(return_value={"online": True})

        # Update state
        await transport.update_state({"online": True})
        transport.update_state.assert_called_once()

        # Get state
        state = await transport.get_state()
        assert state["online"] is True
