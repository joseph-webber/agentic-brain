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

"""Tests for WebSocket read receipts system."""

import pytest

from agentic_brain.transport import (
    MessageStatus,
    WebSocketReadReceipts,
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


class TestWebSocketReceiptsInit:
    """Test WebSocketReadReceipts initialization."""

    def test_init_defaults(self):
        """Test default initialization."""
        receipts = WebSocketReadReceipts()
        assert receipts._broadcast_changes is True
        assert len(receipts._connections) == 0

    def test_init_no_broadcast(self):
        """Test initialization without broadcasting."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        assert receipts._broadcast_changes is False


class TestConnectionManagement:
    """Test connection management."""

    @pytest.mark.asyncio
    async def test_add_connection(self):
        """Test adding a connection."""
        receipts = WebSocketReadReceipts()
        ws = MockWebSocket()

        await receipts.add_connection("user1", ws)

        assert "user1" in receipts._connections
        assert ws in receipts._connections["user1"]

    @pytest.mark.asyncio
    async def test_remove_connection(self):
        """Test removing a connection."""
        receipts = WebSocketReadReceipts()
        ws = MockWebSocket()

        await receipts.add_connection("user1", ws)
        user_id = await receipts.remove_connection(ws)

        assert user_id == "user1"
        assert "user1" not in receipts._connections


class TestReceiptBroadcasting:
    """Test receipt status broadcasting."""

    @pytest.mark.asyncio
    async def test_track_message_notifies_recipients(self):
        """Test tracking message notifies recipients."""
        receipts = WebSocketReadReceipts()
        ws_sender = MockWebSocket()
        ws_recipient = MockWebSocket()

        await receipts.add_connection("sender", ws_sender)
        await receipts.add_connection("recipient", ws_recipient)

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )

        # Recipient should get notification
        assert len(ws_recipient.sent_messages) == 1
        assert ws_recipient.sent_messages[0]["type"] == "receipt"
        assert ws_recipient.sent_messages[0]["action"] == "new_message"

    @pytest.mark.asyncio
    async def test_mark_sent_notifies_sender(self):
        """Test mark_sent notifies sender."""
        receipts = WebSocketReadReceipts()
        ws = MockWebSocket()

        await receipts.add_connection("sender", ws)

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )
        ws.sent_messages.clear()  # Clear tracking notification

        await receipts.mark_sent("msg1")

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["action"] == "status_change"
        assert ws.sent_messages[0]["status"] == "sent"

    @pytest.mark.asyncio
    async def test_mark_delivered_notifies_sender(self):
        """Test mark_delivered notifies sender."""
        receipts = WebSocketReadReceipts()
        ws = MockWebSocket()

        await receipts.add_connection("sender", ws)

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )
        await receipts.mark_sent("msg1")
        ws.sent_messages.clear()

        await receipts.mark_delivered("msg1")

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["status"] == "delivered"

    @pytest.mark.asyncio
    async def test_mark_read_notifies_sender(self):
        """Test mark_read notifies sender."""
        receipts = WebSocketReadReceipts()
        ws_sender = MockWebSocket()

        await receipts.add_connection("sender", ws_sender)

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )
        ws_sender.sent_messages.clear()

        await receipts.mark_read("msg1", "recipient")

        assert len(ws_sender.sent_messages) == 1
        assert ws_sender.sent_messages[0]["action"] == "read"
        assert ws_sender.sent_messages[0]["reader_id"] == "recipient"

    @pytest.mark.asyncio
    async def test_mark_failed_notifies_sender(self):
        """Test mark_failed notifies sender."""
        receipts = WebSocketReadReceipts()
        ws = MockWebSocket()

        await receipts.add_connection("sender", ws)

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )
        ws.sent_messages.clear()

        await receipts.mark_failed("msg1", "Network error")

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["status"] == "failed"
        assert ws.sent_messages[0]["error"] == "Network error"

    @pytest.mark.asyncio
    async def test_no_broadcast_when_disabled(self):
        """Test no broadcast when disabled."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        ws = MockWebSocket()

        await receipts.add_connection("sender", ws)
        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )

        assert len(ws.sent_messages) == 0


class TestHandleMessage:
    """Test handling incoming WebSocket messages."""

    @pytest.mark.asyncio
    async def test_handle_delivered(self):
        """Test handling delivered message."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        ws_sender = MockWebSocket()
        ws_recipient = MockWebSocket()

        await receipts.add_connection("sender", ws_sender)
        await receipts.add_connection("recipient", ws_recipient)

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )
        await receipts.mark_sent("msg1")

        await receipts.handle_message(
            ws_recipient,
            {
                "type": "receipt",
                "action": "delivered",
                "message_id": "msg1",
            },
        )

        info = receipts.get_message_info("msg1")
        assert info.status == MessageStatus.DELIVERED

    @pytest.mark.asyncio
    async def test_handle_read(self):
        """Test handling read message."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        ws = MockWebSocket()

        await receipts.add_connection("recipient", ws)
        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )

        await receipts.handle_message(
            ws,
            {
                "type": "receipt",
                "action": "read",
                "message_id": "msg1",
            },
        )

        info = receipts.get_message_info("msg1")
        assert "recipient" in info.read_by

    @pytest.mark.asyncio
    async def test_handle_read_all(self):
        """Test handling read_all message."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        ws = MockWebSocket()

        await receipts.add_connection("recipient", ws)
        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )
        await receipts.track_message_with_recipients(
            "msg2", "sender", "session1", ["recipient"]
        )

        await receipts.handle_message(
            ws,
            {
                "type": "receipt",
                "action": "read_all",
                "session_id": "session1",
            },
        )

        assert receipts.get_unread_count("recipient", "session1") == 0


class TestSyncState:
    """Test state synchronization."""

    @pytest.mark.asyncio
    async def test_send_unread_count(self):
        """Test sending unread count."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        ws = MockWebSocket()

        await receipts.add_connection("user1", ws)
        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["user1"]
        )
        await receipts.track_message_with_recipients(
            "msg2", "sender", "session1", ["user1"]
        )

        await receipts.send_unread_count(ws, "session1")

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["count"] == 2
        assert ws.sent_messages[0]["session_id"] == "session1"

    @pytest.mark.asyncio
    async def test_send_session_state(self):
        """Test sending session state."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        ws = MockWebSocket()

        await receipts.add_connection("user1", ws)
        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["user1"]
        )
        await receipts.mark_sent("msg1")

        await receipts.send_session_state(ws, "session1")

        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "receipt_sync"
        assert len(ws.sent_messages[0]["messages"]) == 1


class TestStats:
    """Test statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_includes_connections(self):
        """Test stats include connection info."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()

        await receipts.add_connection("user1", ws1)
        await receipts.add_connection("user2", ws2)

        stats = receipts.get_stats()

        assert stats["connections"] == 2
        assert stats["connected_users"] == 2


class TestInheritance:
    """Test inheritance from ReadReceiptManager."""

    @pytest.mark.asyncio
    async def test_inherits_local_behavior(self):
        """Test local-only behavior still works."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["r1", "r2"]
        )
        await receipts.mark_sent("msg1")
        await receipts.mark_read("msg1", "r1")

        info = receipts.get_message_info("msg1")
        assert info.status == MessageStatus.READ
        assert "r1" in info.read_by

    @pytest.mark.asyncio
    async def test_callbacks_work(self):
        """Test callbacks still fire."""
        receipts = WebSocketReadReceipts(broadcast_changes=False)

        statuses = []
        receipts.on_status_change(lambda info: statuses.append(info.status))

        await receipts.track_message_with_recipients(
            "msg1", "sender", "session1", ["recipient"]
        )
        await receipts.mark_sent("msg1")

        assert MessageStatus.SENT in statuses
