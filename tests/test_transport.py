# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Tests for the transport layer."""

import asyncio
import contextlib
from datetime import UTC, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from agentic_brain.transport import (
    TransportConfig,
    TransportManager,
    TransportMessage,
    TransportMode,
    TransportStatus,
    TransportType,
    WebSocketAuthConfig,
    WebSocketTransport,
)

# ============================================================================
# TransportConfig Tests
# ============================================================================


class TestTransportConfig:
    """Test TransportConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TransportConfig()
        assert config.transport_type == TransportType.WEBSOCKET
        assert config.timeout == 30.0
        assert config.reconnect_attempts == 3
        assert config.heartbeat_interval == 30.0
        assert config.websocket_url is None
        assert config.firebase_url is None
        assert config.firebase_credentials is None

    def test_custom_transport_type_config(self):
        """Test configuration with custom transport type."""
        config = TransportConfig(transport_type=TransportType.FIREBASE)
        assert config.transport_type == TransportType.FIREBASE

    def test_custom_timeout_config(self):
        """Test configuration with custom timeout."""
        config = TransportConfig(timeout=60.0)
        assert config.timeout == 60.0

    def test_custom_reconnect_attempts_config(self):
        """Test configuration with custom reconnect attempts."""
        config = TransportConfig(reconnect_attempts=5)
        assert config.reconnect_attempts == 5

    def test_custom_heartbeat_interval_config(self):
        """Test configuration with custom heartbeat interval."""
        config = TransportConfig(heartbeat_interval=15.0)
        assert config.heartbeat_interval == 15.0

    def test_firebase_url_config(self):
        """Test configuration with Firebase URL."""
        config = TransportConfig(firebase_url="https://test.firebaseio.com")
        assert config.firebase_url == "https://test.firebaseio.com"

    def test_firebase_credentials_config(self):
        """Test configuration with Firebase credentials path."""
        config = TransportConfig(firebase_credentials="/path/to/creds.json")
        assert config.firebase_credentials == "/path/to/creds.json"

    def test_websocket_url_config(self):
        """Test configuration with WebSocket URL."""
        config = TransportConfig(websocket_url="wss://example.com")
        assert config.websocket_url == "wss://example.com"

    def test_full_custom_config(self):
        """Test configuration with all custom values."""
        config = TransportConfig(
            transport_type=TransportType.FIREBASE,
            timeout=45.0,
            reconnect_attempts=4,
            heartbeat_interval=20.0,
            websocket_url="wss://ws.example.com",
            firebase_url="https://test.firebaseio.com",
            firebase_credentials="/creds.json",
        )
        assert config.transport_type == TransportType.FIREBASE
        assert config.timeout == 45.0
        assert config.reconnect_attempts == 4
        assert config.heartbeat_interval == 20.0
        assert config.websocket_url == "wss://ws.example.com"
        assert config.firebase_url == "https://test.firebaseio.com"
        assert config.firebase_credentials == "/creds.json"


# ============================================================================
# TransportMessage Tests
# ============================================================================


class TestTransportMessage:
    """Test TransportMessage dataclass."""

    def test_message_creation_minimal(self):
        """Test minimal message creation."""
        msg = TransportMessage(
            content="Hello",
            session_id="sess-123",
            message_id="msg-456",
        )
        assert msg.content == "Hello"
        assert msg.session_id == "sess-123"
        assert msg.message_id == "msg-456"
        assert isinstance(msg.timestamp, datetime)
        assert msg.metadata == {}

    def test_message_with_metadata(self):
        """Test message with metadata."""
        msg = TransportMessage(
            content="Test",
            session_id="s1",
            message_id="m1",
            metadata={"role": "user", "tokens": 10},
        )
        assert msg.metadata["role"] == "user"
        assert msg.metadata["tokens"] == 10

    def test_message_timestamp_utc(self):
        """Test that message timestamp is in UTC."""
        before = datetime.now(UTC)
        msg = TransportMessage(
            content="Test",
            session_id="s1",
            message_id="m1",
        )
        after = datetime.now(UTC)
        assert before <= msg.timestamp <= after
        assert msg.timestamp.tzinfo == UTC

    def test_message_custom_timestamp(self):
        """Test message with custom timestamp."""
        custom_ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        msg = TransportMessage(
            content="Test",
            session_id="s1",
            message_id="m1",
            timestamp=custom_ts,
        )
        assert msg.timestamp == custom_ts

    def test_message_empty_content(self):
        """Test message with empty content."""
        msg = TransportMessage(
            content="",
            session_id="s1",
            message_id="m1",
        )
        assert msg.content == ""

    def test_message_complex_metadata(self):
        """Test message with complex nested metadata."""
        metadata = {
            "role": "assistant",
            "tokens": 100,
            "context": {
                "model": "gpt-4",
                "temperature": 0.7,
                "nested": {"deep": "value"},
            },
            "tags": ["important", "streaming"],
        }
        msg = TransportMessage(
            content="Complex",
            session_id="s1",
            message_id="m1",
            metadata=metadata,
        )
        assert msg.metadata["context"]["nested"]["deep"] == "value"
        assert len(msg.metadata["tags"]) == 2


# ============================================================================
# TransportType Enum Tests
# ============================================================================


class TestTransportType:
    """Test TransportType enum."""

    def test_websocket_type_value(self):
        """Test WebSocket transport type value."""
        assert TransportType.WEBSOCKET.value == "websocket"

    def test_firebase_type_value(self):
        """Test Firebase transport type value."""
        assert TransportType.FIREBASE.value == "firebase"

    def test_transport_type_enum_members(self):
        """Test that expected transport types exist."""
        types = list(TransportType)
        assert len(types) == 3
        assert TransportType.WEBSOCKET in types
        assert TransportType.FIREBASE in types
        assert TransportType.FIRESTORE in types


# ============================================================================
# TransportMode Enum Tests
# ============================================================================


class TestTransportMode:
    """Test TransportMode enum."""

    def test_all_modes_exist(self):
        """Test that all expected modes exist."""
        modes = list(TransportMode)
        assert len(modes) == 5

    def test_websocket_only_mode(self):
        """Test WebSocket only mode."""
        assert TransportMode.WEBSOCKET_ONLY.value == "websocket_only"

    def test_firebase_only_mode(self):
        """Test Firebase only mode."""
        assert TransportMode.FIREBASE_ONLY.value == "firebase_only"

    def test_websocket_primary_mode(self):
        """Test WebSocket primary mode."""
        assert TransportMode.WEBSOCKET_PRIMARY.value == "websocket_primary"

    def test_firebase_primary_mode(self):
        """Test Firebase primary mode."""
        assert TransportMode.FIREBASE_PRIMARY.value == "firebase_primary"

    def test_dual_write_mode(self):
        """Test dual write mode."""
        assert TransportMode.DUAL_WRITE.value == "dual_write"


# ============================================================================
# WebSocketTransport Tests
# ============================================================================


class TestWebSocketTransport:
    """Test WebSocketTransport class."""

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.close = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_json = AsyncMock(return_value={"content": "test"})
        return ws

    @pytest.fixture
    def config(self):
        """Create a transport config."""
        return TransportConfig()

    @pytest.fixture
    def auth_config(self):
        """Create an auth config with auth disabled for tests."""
        return WebSocketAuthConfig(require_auth=False)

    @pytest.fixture
    def transport(self, config, mock_websocket, auth_config):
        """Create a WebSocket transport with auth disabled for tests."""
        return WebSocketTransport(config, mock_websocket, auth_config=auth_config)

    def test_transport_type(self, transport):
        """Test transport type is WebSocket."""
        assert transport.transport_type == TransportType.WEBSOCKET

    def test_initial_state(self, transport):
        """Test initial transport state."""
        assert transport.connected is False
        assert transport._closed is False

    @pytest.mark.asyncio
    async def test_connect_success(self, transport, mock_websocket):
        """Test successful WebSocket connection."""
        result = await transport.connect()
        assert result is True
        assert transport.connected is True
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_no_websocket(self, config, auth_config):
        """Test connection without WebSocket instance."""
        transport = WebSocketTransport(config, None, auth_config=auth_config)
        result = await transport.connect()
        assert result is False
        assert transport.connected is False

    @pytest.mark.asyncio
    async def test_connect_exception(self, config, mock_websocket, auth_config):
        """Test connection with exception."""
        mock_websocket.accept.side_effect = Exception("Connection failed")
        transport = WebSocketTransport(config, mock_websocket, auth_config=auth_config)
        result = await transport.connect()
        assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_success(self, transport, mock_websocket):
        """Test successful disconnection."""
        await transport.connect()
        await transport.disconnect()
        assert transport.connected is False
        assert transport._closed is True
        mock_websocket.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_exception(self, transport, mock_websocket):
        """Test disconnection with exception."""
        await transport.connect()
        mock_websocket.close.side_effect = Exception("Close failed")
        # Should not raise, just log warning
        await transport.disconnect()
        assert transport.connected is False

    @pytest.mark.asyncio
    async def test_send_message_success(self, transport, mock_websocket):
        """Test successful message sending."""
        await transport.connect()
        msg = TransportMessage(
            content="Hello",
            session_id="sess-1",
            message_id="msg-1",
        )
        result = await transport.send(msg)
        assert result is True
        # send_json called twice: once for auth_result, once for message
        assert mock_websocket.send_json.call_count == 2

        # Verify message structure (last call is the actual message)
        call_args = mock_websocket.send_json.call_args
        sent_data = call_args[0][0]
        assert sent_data["content"] == "Hello"
        assert sent_data["session_id"] == "sess-1"
        assert sent_data["message_id"] == "msg-1"
        assert "timestamp" in sent_data
        assert sent_data["metadata"] == {}

    @pytest.mark.asyncio
    async def test_send_without_connection(self, transport, config, mock_websocket):
        """Test send without connection."""
        msg = TransportMessage(content="Test", session_id="s", message_id="m")
        result = await transport.send(msg)
        assert result is False
        mock_websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_without_websocket(self, config, auth_config):
        """Test send without WebSocket instance."""
        transport = WebSocketTransport(config, None, auth_config=auth_config)
        msg = TransportMessage(content="Test", session_id="s", message_id="m")
        result = await transport.send(msg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_with_metadata(self, transport, mock_websocket):
        """Test sending message with metadata."""
        await transport.connect()
        msg = TransportMessage(
            content="Test",
            session_id="s1",
            message_id="m1",
            metadata={"role": "user", "tokens": 50},
        )
        result = await transport.send(msg)
        assert result is True

        call_args = mock_websocket.send_json.call_args
        sent_data = call_args[0][0]
        assert sent_data["metadata"]["role"] == "user"
        assert sent_data["metadata"]["tokens"] == 50

    @pytest.mark.asyncio
    async def test_send_token(self, transport, mock_websocket):
        """Test sending streaming token."""
        await transport.connect()
        result = await transport.send_token("Hello", is_end=False)
        assert result is True
        mock_websocket.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_send_token_end(self, transport, mock_websocket):
        """Test sending end token."""
        await transport.connect()
        result = await transport.send_token("", is_end=True)
        assert result is True

        call_args = mock_websocket.send_json.call_args
        sent_data = call_args[0][0]
        assert sent_data["is_end"] is True

    @pytest.mark.asyncio
    async def test_is_healthy_connected(self, transport, mock_websocket):
        """Test health check when connected."""
        await transport.connect()
        result = await transport.is_healthy()
        assert result is True

    @pytest.mark.asyncio
    async def test_is_healthy_not_connected(self, transport):
        """Test health check when not connected."""
        result = await transport.is_healthy()
        assert result is False

    @pytest.mark.asyncio
    async def test_is_healthy_exception(self, transport, mock_websocket):
        """Test health check with exception."""
        await transport.connect()
        mock_websocket.send_json.side_effect = Exception("Health check failed")
        result = await transport.is_healthy()
        assert result is False


# ============================================================================
# TransportStatus Tests
# ============================================================================


class TestTransportStatus:
    """Test TransportStatus dataclass."""

    def test_default_status(self):
        """Test default status values."""
        status = TransportStatus()
        assert status.websocket_connected is False
        assert status.firebase_connected is False
        assert status.active_transport is None
        assert status.mode == TransportMode.WEBSOCKET_ONLY
        assert status.last_message_at is None

    def test_custom_websocket_status(self):
        """Test status with custom WebSocket connection."""
        status = TransportStatus(websocket_connected=True)
        assert status.websocket_connected is True
        assert status.firebase_connected is False

    def test_custom_firebase_status(self):
        """Test status with custom Firebase connection."""
        status = TransportStatus(firebase_connected=True)
        assert status.firebase_connected is True
        assert status.websocket_connected is False

    def test_custom_active_transport(self):
        """Test status with custom active transport."""
        status = TransportStatus(active_transport=TransportType.WEBSOCKET)
        assert status.active_transport == TransportType.WEBSOCKET

    def test_custom_mode(self):
        """Test status with custom mode."""
        status = TransportStatus(mode=TransportMode.DUAL_WRITE)
        assert status.mode == TransportMode.DUAL_WRITE

    def test_custom_last_message(self):
        """Test status with custom last message time."""
        now = datetime.now(UTC)
        status = TransportStatus(last_message_at=now)
        assert status.last_message_at == now


# ============================================================================
# TransportManager Tests
# ============================================================================


class TestTransportManager:
    """Test TransportManager class."""

    def test_default_initialization(self):
        """Test default manager initialization."""
        manager = TransportManager()
        assert manager.mode == TransportMode.WEBSOCKET_ONLY
        assert manager.config is not None
        assert isinstance(manager.config, TransportConfig)

    def test_custom_mode_initialization(self):
        """Test initialization with custom mode."""
        manager = TransportManager(mode=TransportMode.DUAL_WRITE)
        assert manager.mode == TransportMode.DUAL_WRITE

    def test_custom_config_initialization(self):
        """Test initialization with custom config."""
        config = TransportConfig(timeout=60.0)
        manager = TransportManager(config=config)
        assert manager.config.timeout == 60.0

    def test_status_initial_state(self):
        """Test initial manager status."""
        manager = TransportManager()
        status = manager.status
        assert status.websocket_connected is False
        assert status.firebase_connected is False
        assert status.active_transport is None
        assert status.mode == TransportMode.WEBSOCKET_ONLY
        assert status.last_message_at is None

    @pytest.mark.asyncio
    async def test_connect_websocket_only(self):
        """Test connecting in WebSocket only mode."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        result = await manager.connect(websocket=mock_ws)

        assert result is True
        assert manager.status.websocket_connected is True
        assert manager.status.active_transport == TransportType.WEBSOCKET

    @pytest.mark.asyncio
    async def test_connect_no_websocket(self):
        """Test connecting without WebSocket."""
        manager = TransportManager(mode=TransportMode.WEBSOCKET_ONLY)
        result = await manager.connect(websocket=None)

        assert result is False
        assert manager.status.websocket_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_success(self):
        """Test successful disconnection."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.close = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        await manager.connect(websocket=mock_ws)
        assert manager.status.websocket_connected is True

        await manager.disconnect()
        assert manager.status.websocket_connected is False
        assert manager.status.active_transport is None

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """Test successful message sending."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        await manager.connect(websocket=mock_ws)

        msg = TransportMessage(content="Test", session_id="s1", message_id="m1")
        result = await manager.send(msg)

        assert result is True
        assert manager.status.last_message_at is not None

    @pytest.mark.asyncio
    async def test_send_without_connection(self):
        """Test send without connection."""
        manager = TransportManager()
        msg = TransportMessage(content="Test", session_id="s1", message_id="m1")
        result = await manager.send(msg)

        assert result is False

    @pytest.mark.asyncio
    async def test_send_token_success(self):
        """Test successful token sending."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        await manager.connect(websocket=mock_ws)

        result = await manager.send_token("Hello", is_end=False)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_token_without_connection(self):
        """Test token send without connection."""
        manager = TransportManager()
        result = await manager.send_token("Hello", is_end=False)
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_connected(self):
        """Test health check when connected."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        manager = TransportManager()
        await manager.connect(websocket=mock_ws)

        health = await manager.health_check()
        assert "websocket" in health
        assert "firebase" in health
        assert "mode" in health
        assert "active_transport" in health
        assert health["mode"] == "websocket_only"

    @pytest.mark.asyncio
    async def test_health_check_not_connected(self):
        """Test health check when not connected."""
        manager = TransportManager()
        health = await manager.health_check()

        assert health["websocket"] is False
        assert health["firebase"] is False
        assert health["active_transport"] is None

    @pytest.mark.asyncio
    async def test_multiple_modes(self):
        """Test manager with different modes."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        for mode in TransportMode:
            manager = TransportManager(mode=mode)
            assert manager.mode == mode

    @pytest.mark.asyncio
    async def test_dual_write_mode(self):
        """Test dual write mode sends to both transports."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.DUAL_WRITE,
            websocket_auth_config=auth_config,
        )
        await manager.connect(websocket=mock_ws)

        msg = TransportMessage(content="Test", session_id="s1", message_id="m1")
        result = await manager.send(msg)

        assert result is True


# ============================================================================
# Firebase Graceful Fallback Tests
# ============================================================================


class TestFirebaseGracefulFallback:
    """Test that Firebase import failure is handled gracefully."""

    def test_firebase_import_handling(self):
        """Test that FirebaseTransport handles import gracefully."""
        from agentic_brain.transport import FirebaseTransport

        # FirebaseTransport should be None or importable without error
        # Both are valid - if firebase-admin is not installed, it's None
        # If installed, it's a class
        assert FirebaseTransport is None or hasattr(FirebaseTransport, "__init__")

    def test_firebase_not_required(self):
        """Test that transport module works without Firebase."""
        # This should work even if Firebase is not installed
        manager = TransportManager(mode=TransportMode.WEBSOCKET_ONLY)
        assert manager is not None

    @pytest.mark.asyncio
    async def test_connect_without_firebase(self):
        """Test connection works without Firebase."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        result = await manager.connect(websocket=mock_ws)

        # Should succeed even without Firebase available
        assert result is True


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================


class TestTransportEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_send_large_message(self):
        """Test sending large message."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        await manager.connect(websocket=mock_ws)

        large_content = "x" * 1000000  # 1MB message
        msg = TransportMessage(content=large_content, session_id="s1", message_id="m1")
        result = await manager.send(msg)
        assert result is True

    @pytest.mark.asyncio
    async def test_rapid_connect_disconnect(self):
        """Test rapid connect/disconnect cycles."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.close = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )

        for _ in range(5):
            result = await manager.connect(websocket=mock_ws)
            assert result is True
            await manager.disconnect()
            assert manager.status.websocket_connected is False

    @pytest.mark.asyncio
    async def test_send_empty_message(self):
        """Test sending empty message."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        await manager.connect(websocket=mock_ws)

        msg = TransportMessage(content="", session_id="s1", message_id="m1")
        result = await manager.send(msg)
        assert result is True

    def test_transport_config_immutability(self):
        """Test that config has expected field types."""
        config = TransportConfig()
        assert isinstance(config.timeout, float)
        assert isinstance(config.reconnect_attempts, int)
        assert isinstance(config.heartbeat_interval, float)

    @pytest.mark.asyncio
    async def test_multiple_sends_tracking(self):
        """Test that send count is tracked correctly."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Disable auth for testing
        auth_config = WebSocketAuthConfig(require_auth=False)
        manager = TransportManager(
            mode=TransportMode.WEBSOCKET_ONLY,
            websocket_auth_config=auth_config,
        )
        await manager.connect(websocket=mock_ws)

        for i in range(5):
            msg = TransportMessage(
                content=f"Message {i}", session_id="s1", message_id=f"m{i}"
            )
            await manager.send(msg)

        assert mock_ws.send_json.call_count == 6
        assert manager.status.last_message_at is not None


# ============================================================================
# Transport Mode Specific Tests
# ============================================================================


class TestTransportModes:
    """Test specific transport mode behaviors."""

    @pytest.mark.asyncio
    async def test_websocket_primary_mode(self):
        """Test WebSocket primary mode initialization."""
        manager = TransportManager(mode=TransportMode.WEBSOCKET_PRIMARY)
        assert manager.mode == TransportMode.WEBSOCKET_PRIMARY

    @pytest.mark.asyncio
    async def test_firebase_primary_mode(self):
        """Test Firebase primary mode initialization."""
        manager = TransportManager(mode=TransportMode.FIREBASE_PRIMARY)
        assert manager.mode == TransportMode.FIREBASE_PRIMARY

    @pytest.mark.asyncio
    async def test_firebase_only_mode(self):
        """Test Firebase only mode initialization."""
        manager = TransportManager(mode=TransportMode.FIREBASE_ONLY)
        assert manager.mode == TransportMode.FIREBASE_ONLY

    @pytest.mark.asyncio
    async def test_dual_write_initialization(self):
        """Test dual write mode initialization."""
        manager = TransportManager(mode=TransportMode.DUAL_WRITE)
        assert manager.mode == TransportMode.DUAL_WRITE


# ============================================================================
# WebSocket Transport Receive Tests
# ============================================================================


class TestWebSocketReceive:
    """Test WebSocket message receiving."""

    @pytest.mark.asyncio
    async def test_receive_basic_message(self):
        """Test receiving a basic message."""
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.receive_json = AsyncMock(
            return_value={
                "content": "Hello",
                "session_id": "s1",
                "message_id": "m1",
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        )

        config = TransportConfig()
        auth_config = WebSocketAuthConfig(require_auth=False)
        transport = WebSocketTransport(config, mock_ws, auth_config=auth_config)
        await transport.connect()

        received_messages = []

        async def collect_messages():
            async for msg in transport.receive():
                received_messages.append(msg)
                if len(received_messages) >= 1:
                    await transport.disconnect()
                    break

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(collect_messages(), timeout=1)

        assert len(received_messages) > 0
        assert received_messages[0].content == "Hello"


# ============================================================================
# Transport Message Timestamp Tests
# ============================================================================


class TestTransportMessageTimestamps:
    """Test message timestamp handling."""

    def test_timestamp_timezone_aware(self):
        """Test that timestamps are timezone aware."""
        msg = TransportMessage(content="Test", session_id="s1", message_id="m1")
        assert msg.timestamp.tzinfo is not None
        assert msg.timestamp.tzinfo == UTC

    def test_timestamp_uniqueness(self):
        """Test that different messages have proper timestamps."""
        msg1 = TransportMessage(content="Test1", session_id="s1", message_id="m1")
        msg2 = TransportMessage(content="Test2", session_id="s1", message_id="m2")
        # Timestamps should be close but could be equal due to precision
        assert abs((msg2.timestamp - msg1.timestamp).total_seconds()) < 1

    def test_message_serialization_timestamp(self):
        """Test that timestamp can be serialized."""
        msg = TransportMessage(content="Test", session_id="s1", message_id="m1")
        timestamp_str = msg.timestamp.isoformat()
        # Reconstruct from ISO format
        reconstructed = datetime.fromisoformat(timestamp_str)
        assert reconstructed.tzinfo == UTC


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
