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

"""Tests for Firebase read receipts and message delivery tracking.

Tests the ReadReceiptManager, MessageStatus, and delivery status system.
"""

from datetime import UTC, datetime, timezone

import pytest

from agentic_brain.transport import (
    FirebaseReadReceipts,
    MessageReadInfo,
    MessageStatus,
    ReadReceipt,
    ReadReceiptManager,
)


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class TestMessageStatus:
    """Test MessageStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        assert MessageStatus.SENDING is not None
        assert MessageStatus.SENT is not None
        assert MessageStatus.DELIVERED is not None
        assert MessageStatus.READ is not None
        assert MessageStatus.FAILED is not None

    def test_status_values(self):
        """Test status string values."""
        assert MessageStatus.SENDING.value == "sending"
        assert MessageStatus.SENT.value == "sent"
        assert MessageStatus.DELIVERED.value == "delivered"
        assert MessageStatus.READ.value == "read"
        assert MessageStatus.FAILED.value == "failed"


class TestReadReceipt:
    """Test ReadReceipt dataclass."""

    def test_create_receipt(self):
        """Test creating a read receipt."""
        now = _utc_now()
        receipt = ReadReceipt(
            message_id="msg123",
            user_id="user456",
            status=MessageStatus.READ,
            timestamp=now,
        )
        assert receipt.message_id == "msg123"
        assert receipt.user_id == "user456"
        assert receipt.status == MessageStatus.READ
        assert receipt.timestamp == now

    def test_receipt_to_dict(self):
        """Test serializing receipt to dict."""
        now = _utc_now()
        receipt = ReadReceipt(
            message_id="msg123",
            user_id="user456",
            status=MessageStatus.READ,
            timestamp=now,
        )
        data = receipt.to_dict()

        assert data["message_id"] == "msg123"
        assert data["user_id"] == "user456"
        assert data["status"] == "read"
        assert data["timestamp"] == now.isoformat()

    def test_receipt_from_dict(self):
        """Test deserializing receipt from dict."""
        now = _utc_now()
        data = {
            "message_id": "msg123",
            "user_id": "user456",
            "status": "delivered",
            "timestamp": now.isoformat(),
        }
        receipt = ReadReceipt.from_dict(data)

        assert receipt.message_id == "msg123"
        assert receipt.user_id == "user456"
        assert receipt.status == MessageStatus.DELIVERED


class TestMessageReadInfo:
    """Test MessageReadInfo dataclass."""

    def test_create_info(self):
        """Test creating message read info."""
        now = _utc_now()
        info = MessageReadInfo(
            message_id="msg123",
            sender_id="user1",
            session_id="sess456",
            status=MessageStatus.SENT,
            sent_at=now,
        )
        assert info.message_id == "msg123"
        assert info.sender_id == "user1"
        assert info.session_id == "sess456"
        assert info.status == MessageStatus.SENT
        assert info.sent_at == now

    def test_info_with_reads(self):
        """Test message info with read receipts."""
        now = _utc_now()
        info = MessageReadInfo(
            message_id="msg123",
            sender_id="user1",
            session_id="sess456",
            status=MessageStatus.READ,
            sent_at=now,
            read_by={"user2": now, "user3": now},
        )
        assert info.read_count == 2
        assert info.is_read is True
        assert info.is_read_by("user2") is True
        assert info.is_read_by("user4") is False

    def test_info_to_dict(self):
        """Test serializing message info."""
        now = _utc_now()
        info = MessageReadInfo(
            message_id="msg123",
            sender_id="user1",
            session_id="sess456",
            status=MessageStatus.DELIVERED,
            sent_at=now,
        )
        data = info.to_dict()

        assert data["message_id"] == "msg123"
        assert data["status"] == "delivered"

    def test_info_from_dict(self):
        """Test deserializing message info."""
        now = _utc_now()
        data = {
            "message_id": "msg123",
            "sender_id": "user1",
            "session_id": "sess456",
            "status": "read",
            "sent_at": now.isoformat(),
            "read_by": {"user2": now.isoformat()},
        }
        info = MessageReadInfo.from_dict(data)

        assert info.message_id == "msg123"
        assert info.status == MessageStatus.READ
        assert "user2" in info.read_by


class TestReadReceiptManager:
    """Test local ReadReceiptManager."""

    def test_init(self):
        """Test manager initialization."""
        manager = ReadReceiptManager()
        assert manager is not None

    def test_track_message(self):
        """Test tracking a new message."""
        manager = ReadReceiptManager()

        info = manager.track_message("msg123", "user1", "sess456")

        assert info.message_id == "msg123"
        assert info.sender_id == "user1"
        assert info.session_id == "sess456"
        assert info.status == MessageStatus.SENDING

    @pytest.mark.asyncio
    async def test_mark_sent(self):
        """Test marking message as sent."""
        manager = ReadReceiptManager()
        manager.track_message("msg123", "user1", "sess456")

        info = await manager.mark_sent("msg123")

        assert info is not None
        assert info.status == MessageStatus.SENT
        assert info.sent_at is not None

    @pytest.mark.asyncio
    async def test_mark_delivered(self):
        """Test marking message as delivered."""
        manager = ReadReceiptManager()
        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")

        info = await manager.mark_delivered("msg123")

        assert info.status == MessageStatus.DELIVERED
        assert info.delivered_at is not None

    @pytest.mark.asyncio
    async def test_mark_read(self):
        """Test marking message as read by user."""
        manager = ReadReceiptManager()
        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")

        info = await manager.mark_read("msg123", "user2")

        assert info.status == MessageStatus.READ
        assert "user2" in info.read_by

    @pytest.mark.asyncio
    async def test_multiple_readers(self):
        """Test multiple users reading same message."""
        manager = ReadReceiptManager()
        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")

        await manager.mark_read("msg123", "user2")
        await manager.mark_read("msg123", "user3")
        await manager.mark_read("msg123", "user4")

        info = manager.get_message_info("msg123")
        assert info.read_count == 3
        assert "user2" in info.read_by
        assert "user3" in info.read_by
        assert "user4" in info.read_by

    @pytest.mark.asyncio
    async def test_sender_reading_own_message(self):
        """Test that sender reading own message doesn't count."""
        manager = ReadReceiptManager()
        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")

        info = await manager.mark_read("msg123", "user1")  # Sender

        # Sender's read shouldn't be tracked
        assert "user1" not in info.read_by

    @pytest.mark.asyncio
    async def test_mark_failed(self):
        """Test marking message as failed."""
        manager = ReadReceiptManager()
        manager.track_message("msg123", "user1", "sess456")

        info = await manager.mark_failed("msg123", error="Network error")

        assert info.status == MessageStatus.FAILED

    def test_get_message_info(self):
        """Test getting message info."""
        manager = ReadReceiptManager()
        manager.track_message("msg123", "user1", "sess456")

        info = manager.get_message_info("msg123")

        assert info is not None
        assert info.message_id == "msg123"

    def test_get_nonexistent(self):
        """Test getting info for unknown message."""
        manager = ReadReceiptManager()
        info = manager.get_message_info("unknown")
        assert info is None

    @pytest.mark.asyncio
    async def test_get_unread_messages(self):
        """Test getting unread messages for user."""
        manager = ReadReceiptManager()

        # Create 5 messages from different sender
        for i in range(5):
            manager.track_message(f"msg{i}", "sender", "sess456")
            await manager.mark_sent(f"msg{i}")

        # User2 reads 2 of them
        await manager.mark_read("msg0", "user2")
        await manager.mark_read("msg1", "user2")

        unread = manager.get_unread_messages("user2", "sess456")
        assert len(unread) == 3

    @pytest.mark.asyncio
    async def test_get_unread_count(self):
        """Test getting unread count for user."""
        manager = ReadReceiptManager()

        for i in range(5):
            manager.track_message(f"msg{i}", "sender", "sess456")
            await manager.mark_sent(f"msg{i}")

        await manager.mark_read("msg0", "user2")
        await manager.mark_read("msg1", "user2")

        count = manager.get_unread_count("user2", "sess456")
        assert count == 3

    @pytest.mark.asyncio
    async def test_mark_all_read(self):
        """Test marking all messages as read."""
        manager = ReadReceiptManager()

        for i in range(5):
            manager.track_message(f"msg{i}", "sender", "sess456")
            await manager.mark_sent(f"msg{i}")

        await manager.mark_all_read("user2", "sess456")

        count = manager.get_unread_count("user2", "sess456")
        assert count == 0

    @pytest.mark.asyncio
    async def test_get_session_messages(self):
        """Test getting all messages for a session."""
        manager = ReadReceiptManager()

        manager.track_message("msg1", "user1", "sess123")
        manager.track_message("msg2", "user1", "sess123")
        manager.track_message("msg3", "user1", "sess456")  # Different session

        messages = manager.get_session_messages("sess123")
        assert len(messages) == 2


class TestFirebaseReadReceipts:
    """Test Firebase-synced read receipts."""

    def test_inherits_local_behavior(self):
        """Test that Firebase receipts has all local methods."""
        receipts = FirebaseReadReceipts()

        assert hasattr(receipts, "track_message")
        assert hasattr(receipts, "mark_sent")
        assert hasattr(receipts, "mark_delivered")
        assert hasattr(receipts, "mark_read")
        assert hasattr(receipts, "mark_failed")
        assert hasattr(receipts, "get_message_info")
        assert hasattr(receipts, "get_unread_count")

    @pytest.mark.asyncio
    async def test_local_mode_works(self):
        """Test receipts work in local-only mode."""
        receipts = FirebaseReadReceipts()  # No Firebase URL = local only

        receipts.track_message("msg123", "user1", "sess456")
        await receipts.mark_sent("msg123")
        await receipts.mark_read("msg123", "user2")

        info = receipts.get_message_info("msg123")
        assert info.status == MessageStatus.READ


class TestReceiptCallbacks:
    """Test receipt change callbacks."""

    @pytest.mark.asyncio
    async def test_on_status_change(self):
        """Test callback fires on status change."""
        manager = ReadReceiptManager()
        changes = []

        def callback(info):
            changes.append(info)

        manager.on_status_change(callback)

        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")
        await manager.mark_delivered("msg123")
        await manager.mark_read("msg123", "user2")

        assert len(changes) >= 3

    @pytest.mark.asyncio
    async def test_on_read(self):
        """Test callback fires when message is read."""
        manager = ReadReceiptManager()
        reads = []

        def callback(message_id: str, user_id: str):
            reads.append((message_id, user_id))

        manager.on_read(callback)

        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")
        await manager.mark_read("msg123", "user2")
        await manager.mark_read("msg123", "user3")

        assert len(reads) == 2


class TestReceiptStats:
    """Test receipt statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting receipt statistics."""
        manager = ReadReceiptManager()

        manager.track_message("msg1", "user1", "sess1")
        await manager.mark_sent("msg1")

        manager.track_message("msg2", "user1", "sess1")
        await manager.mark_sent("msg2")
        await manager.mark_delivered("msg2")

        manager.track_message("msg3", "user1", "sess1")
        await manager.mark_sent("msg3")
        await manager.mark_read("msg3", "user2")

        manager.track_message("msg4", "user1", "sess1")
        await manager.mark_failed("msg4", error="timeout")

        stats = manager.get_stats()

        assert stats["sent"] >= 1
        assert stats["delivered"] >= 1
        assert stats["read"] >= 1
        assert stats["failed"] >= 1
        assert stats["total"] == 4


class TestReadReceiptTiming:
    """Test receipt timing information."""

    @pytest.mark.asyncio
    async def test_sent_time_recorded(self):
        """Test that sent time is recorded."""
        manager = ReadReceiptManager()

        manager.track_message("msg123", "user1", "sess456")
        before_send = _utc_now()
        await manager.mark_sent("msg123")

        info = manager.get_message_info("msg123")
        assert info.sent_at is not None
        assert info.sent_at >= before_send

    @pytest.mark.asyncio
    async def test_delivery_time_recorded(self):
        """Test that delivery time is recorded."""
        manager = ReadReceiptManager()

        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")
        before_delivery = _utc_now()
        await manager.mark_delivered("msg123")

        info = manager.get_message_info("msg123")
        assert info.delivered_at is not None
        assert info.delivered_at >= before_delivery

    @pytest.mark.asyncio
    async def test_read_time_recorded(self):
        """Test that read time is recorded per user."""
        manager = ReadReceiptManager()

        manager.track_message("msg123", "user1", "sess456")
        await manager.mark_sent("msg123")
        before_read = _utc_now()
        await manager.mark_read("msg123", "user2")

        info = manager.get_message_info("msg123")
        assert "user2" in info.read_by
        assert info.read_by["user2"] >= before_read
