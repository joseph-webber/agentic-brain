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

"""Tests for WebSocket presence system."""

import pytest

from agentic_brain.transport import (
    PresenceStatus,
    WebSocketPresence,
)


class MockWebSocket:
    """Mock FastAPI WebSocket for testing."""

    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def send_json(self, data):
        if self.closed:
            raise Exception("WebSocket closed")
        self.sent_messages.append(data)

    async def close(self):
        self.closed = True


class TestWebSocketPresenceInit:
    """Test WebSocketPresence initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        presence = WebSocketPresence()
        assert presence._broadcast_changes is True
        assert len(presence._connections) == 0

    def test_init_no_broadcast(self):
        """Test initialization without broadcasting."""
        presence = WebSocketPresence(broadcast_changes=False)
        assert presence._broadcast_changes is False


class TestConnectionManagement:
    """Test WebSocket connection management."""

    @pytest.mark.asyncio
    async def test_add_connection(self):
        """Test adding a connection."""
        presence = WebSocketPresence()
        ws = MockWebSocket()

        await presence.add_connection("user1", ws)

        assert "user1" in presence._connections
        assert ws in presence._connections["user1"]
        assert presence._ws_to_user[ws] == "user1"

    @pytest.mark.asyncio
    async def test_add_connection_auto_online(self):
        """Test auto-online on connection."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws = MockWebSocket()

        await presence.add_connection("user1", ws, auto_online=True)

        user = presence.get_presence("user1")
        assert user is not None
        assert user.status == PresenceStatus.ONLINE

    @pytest.mark.asyncio
    async def test_add_multiple_connections_same_user(self):
        """Test multiple connections for same user (multi-device)."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await presence.add_connection("user1", ws1)
        await presence.add_connection("user1", ws2)

        assert len(presence._connections["user1"]) == 2
        assert presence.connection_count("user1") == 2

    @pytest.mark.asyncio
    async def test_remove_connection(self):
        """Test removing a connection."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws = MockWebSocket()

        await presence.add_connection("user1", ws)
        user_id = await presence.remove_connection(ws, auto_offline=False)

        assert user_id == "user1"
        assert ws not in presence._connections.get("user1", set())

    @pytest.mark.asyncio
    async def test_remove_connection_auto_offline(self):
        """Test auto-offline when last connection removed."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws = MockWebSocket()

        await presence.add_connection("user1", ws)
        await presence.remove_connection(ws, auto_offline=True)

        user = presence.get_presence("user1")
        assert user is None or user.status == PresenceStatus.OFFLINE

    def test_get_connected_users(self):
        """Test getting connected users."""
        presence = WebSocketPresence()
        presence._connections["user1"] = {MockWebSocket()}
        presence._connections["user2"] = {MockWebSocket(), MockWebSocket()}

        users = presence.get_connected_users()

        assert len(users) == 2
        assert "user1" in users
        assert "user2" in users


class TestBroadcasting:
    """Test presence broadcasting."""

    @pytest.mark.asyncio
    async def test_broadcast_on_online(self):
        """Test broadcast when user comes online."""
        presence = WebSocketPresence()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await presence.add_connection("user1", ws1, auto_online=False)
        await presence.add_connection("user2", ws2, auto_online=False)

        await presence.set_online("user1")

        # Both should receive the broadcast
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1
        assert ws1.sent_messages[0]["type"] == "presence"
        assert ws1.sent_messages[0]["action"] == "online"

    @pytest.mark.asyncio
    async def test_broadcast_on_typing(self):
        """Test broadcast when user starts typing."""
        presence = WebSocketPresence()
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await presence.add_connection("user1", ws1, auto_online=False)
        await presence.add_connection("user2", ws2, auto_online=False)
        await presence.set_online("user1")

        ws1.sent_messages.clear()
        ws2.sent_messages.clear()

        await presence.start_typing("user1", "chat-room")

        assert any(m["type"] == "typing" for m in ws1.sent_messages)
        assert any(m["type"] == "typing" for m in ws2.sent_messages)

    @pytest.mark.asyncio
    async def test_no_broadcast_when_disabled(self):
        """Test no broadcast when disabled."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws = MockWebSocket()

        await presence.add_connection("user1", ws, auto_online=False)
        await presence.set_online("user1")

        assert len(ws.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_cleanup_failed_connections(self):
        """Test cleanup of failed connections during broadcast."""
        presence = WebSocketPresence()
        ws_good = MockWebSocket()
        ws_bad = MockWebSocket()
        ws_bad.closed = True  # Simulate closed connection

        await presence.add_connection("user1", ws_good, auto_online=False)
        presence._connections["user2"] = {ws_bad}
        presence._ws_to_user[ws_bad] = "user2"

        await presence.set_online("user1")

        # Bad connection should be removed
        assert "user2" not in presence._connections


class TestHandleMessage:
    """Test handling incoming WebSocket messages."""

    @pytest.mark.asyncio
    async def test_handle_presence_online(self):
        """Test handling presence online message."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws = MockWebSocket()

        await presence.add_connection("user1", ws, auto_online=False)

        await presence.handle_message(
            ws,
            {
                "type": "presence",
                "action": "online",
            },
        )

        assert presence.is_online("user1")

    @pytest.mark.asyncio
    async def test_handle_typing_start(self):
        """Test handling typing start message."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws = MockWebSocket()

        await presence.add_connection("user1", ws)

        await presence.handle_message(
            ws,
            {
                "type": "typing",
                "action": "start",
                "session_id": "chat-room",
            },
        )

        assert presence.is_typing("user1", "chat-room")

    @pytest.mark.asyncio
    async def test_handle_unknown_websocket(self):
        """Test handling message from unknown WebSocket."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws = MockWebSocket()

        # Should not raise, just log warning
        await presence.handle_message(
            ws,
            {
                "type": "presence",
                "action": "online",
            },
        )


class TestSyncState:
    """Test state synchronization."""

    @pytest.mark.asyncio
    async def test_send_full_state(self):
        """Test sending full state to new client."""
        presence = WebSocketPresence(broadcast_changes=False)

        # Set up some users
        await presence.set_online("user1")
        await presence.set_online("user2")
        await presence.start_typing("user1", "chat-room")

        # New client connects
        ws = MockWebSocket()
        await presence.add_connection("user3", ws, auto_online=False)

        # Send state
        await presence.send_full_state(ws)

        # Should receive presence sync and typing sync
        assert len(ws.sent_messages) == 2
        assert ws.sent_messages[0]["type"] == "presence_sync"
        assert "user1" in ws.sent_messages[0]["users"]


class TestStats:
    """Test statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_includes_connections(self):
        """Test stats include connection info."""
        presence = WebSocketPresence(broadcast_changes=False)
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await presence.add_connection("user1", ws1)
        await presence.add_connection("user2", ws2)

        stats = presence.get_stats()

        assert stats["connections"] == 2
        assert stats["connected_users"] == 2
        assert stats["online"] == 2


class TestInheritance:
    """Test that WebSocketPresence inherits PresenceManager behavior."""

    @pytest.mark.asyncio
    async def test_inherits_local_behavior(self):
        """Test local-only behavior still works."""
        presence = WebSocketPresence(broadcast_changes=False)

        await presence.set_online("user1")
        await presence.set_away("user1")

        user = presence.get_presence("user1")
        assert user.status == PresenceStatus.AWAY

    @pytest.mark.asyncio
    async def test_callbacks_work(self):
        """Test callbacks still fire."""
        presence = WebSocketPresence(broadcast_changes=False)

        changes = []
        presence.on_presence_change(lambda u: changes.append(u))

        await presence.set_online("user1")

        assert len(changes) == 1
