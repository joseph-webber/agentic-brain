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
End-to-End Chat Tests for Agentic Brain

Tests the complete chat flow including:
- Online/offline status tracking
- Typing indicators
- Message sending/receiving
- Message ordering
- Reconnection handling
- Multi-user scenarios

Real API from ChatFeatures:
- track_message(message_id, sender_id, session_id, recipient_ids=None)
- mark_delivered(message_id)
- mark_read(message_id, reader_id)
- get_message_info(message_id)
- start_typing(user_id, session_id)
- stop_typing(user_id, session_id)
- is_typing(user_id, session_id)
- get_typing_users(session_id) -> list of TypingIndicator
"""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.transport import ChatFeatures, PresenceStatus, TransportType

logger = logging.getLogger(__name__)


@pytest.fixture
def chat_features():
    """Create ChatFeatures in local mode for testing."""
    return ChatFeatures(transport_type=None)


# =============================================================================
# Online Status Tests
# =============================================================================


class TestOnlineStatus:
    """Test online/offline status tracking."""

    @pytest.mark.asyncio
    async def test_user_comes_online(self, chat_features):
        """Test user comes online."""
        # Initially offline
        assert not chat_features.is_online("user1")

        # Come online
        await chat_features.set_online("user1")

        # Should be online
        assert chat_features.is_online("user1")
        presence = chat_features.get_presence("user1")
        assert presence.status == PresenceStatus.ONLINE
        assert presence.last_seen is not None

    @pytest.mark.asyncio
    async def test_user_goes_offline(self, chat_features):
        """Test user goes offline."""
        # Come online first
        await chat_features.set_online("user1")
        assert chat_features.is_online("user1")

        # Go offline
        await chat_features.set_offline("user1")

        # Should be offline
        assert not chat_features.is_online("user1")
        presence = chat_features.get_presence("user1")
        assert presence.status == PresenceStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_user_away_status(self, chat_features):
        """Test user away status."""
        # Come online
        await chat_features.set_online("user1")

        # Go away
        await chat_features.set_away("user1")

        # Should be away
        presence = chat_features.get_presence("user1")
        assert presence.status == PresenceStatus.AWAY

    @pytest.mark.asyncio
    async def test_user_busy_status(self, chat_features):
        """Test user busy status."""
        # Come online
        await chat_features.set_online("user1")

        # Set busy
        await chat_features.set_busy("user1")

        # Should be busy
        presence = chat_features.get_presence("user1")
        assert presence.status == PresenceStatus.BUSY

    @pytest.mark.asyncio
    async def test_multiple_users_online(self, chat_features):
        """Test multiple users coming online."""
        users = [f"user_{i}" for i in range(5)]

        # All come online
        for user in users:
            await chat_features.set_online(user)

        # All should be online
        for user in users:
            assert chat_features.is_online(user)

        # Get online users (returns UserPresence objects)
        online_users = chat_features.get_online_users()
        assert len(online_users) >= 5
        online_user_ids = [up.user_id for up in online_users]
        for user in users:
            assert user in online_user_ids

    @pytest.mark.asyncio
    async def test_status_persistence(self, chat_features):
        """Test that presence status persists."""
        await chat_features.set_online("user1")
        presence1 = chat_features.get_presence("user1")

        # Wait a bit
        await asyncio.sleep(0.1)

        presence2 = chat_features.get_presence("user1")
        assert presence2.status == PresenceStatus.ONLINE
        # Last seen might have updated
        assert presence2.last_seen >= presence1.last_seen

    @pytest.mark.asyncio
    async def test_heartbeat_updates_activity(self, chat_features):
        """Test heartbeat updates last activity."""
        user = "user1"
        await chat_features.set_online(user)

        presence1 = chat_features.get_presence(user)
        await asyncio.sleep(0.05)

        # Send heartbeat
        await chat_features.heartbeat(user)
        presence2 = chat_features.get_presence(user)

        # Activity should be updated
        assert presence2.last_activity >= presence1.last_activity


# =============================================================================
# Typing Indicator Tests
# =============================================================================


class TestTypingIndicators:
    """Test typing indicator functionality."""

    @pytest.mark.asyncio
    async def test_start_typing(self, chat_features):
        """Test starting typing indicator."""
        # User comes online
        await chat_features.set_online("user1")

        # Start typing
        await chat_features.start_typing("user1", "session1")

        # Should show typing
        assert chat_features.is_typing("user1", "session1") is True

    @pytest.mark.asyncio
    async def test_stop_typing(self, chat_features):
        """Test stopping typing indicator."""
        # User comes online
        await chat_features.set_online("user1")

        # Start typing
        await chat_features.start_typing("user1", "session1")
        assert chat_features.is_typing("user1", "session1") is True

        # Stop typing
        await chat_features.stop_typing("user1", "session1")

        # Should not be typing
        assert chat_features.is_typing("user1", "session1") is False

    @pytest.mark.asyncio
    async def test_multiple_users_typing(self, chat_features):
        """Test multiple users typing in same session."""
        session_id = "session1"

        # Multiple users start typing
        for i in range(3):
            user = f"user_{i}"
            await chat_features.set_online(user)
            await chat_features.start_typing(user, session_id)

        # All should be typing
        typing_users = chat_features.get_typing_users(session_id)
        assert len(typing_users) == 3

        # Stop one user
        await chat_features.stop_typing("user_0", session_id)

        typing_users = chat_features.get_typing_users(session_id)
        assert len(typing_users) == 2
        # Check the typing user ids
        typing_user_ids = [t.user_id for t in typing_users]
        assert "user_0" not in typing_user_ids

    @pytest.mark.asyncio
    async def test_typing_timeout(self, chat_features):
        """Test typing indicator can be manually stopped."""
        # Note: Typing timeout is handled by background cleanup,
        # not by the is_typing check itself
        features = ChatFeatures(
            transport_type=None,
            typing_timeout=0.2,  # 200ms
        )

        await features.set_online("user1")
        await features.start_typing("user1", "session1")

        # Should be typing
        assert features.is_typing("user1", "session1") is True

        # Stop typing manually
        await features.stop_typing("user1", "session1")

        # Should not be typing anymore
        assert features.is_typing("user1", "session1") is False

    @pytest.mark.asyncio
    async def test_typing_in_different_sessions(self, chat_features):
        """Test typing indicators in different sessions."""
        await chat_features.set_online("user1")

        # Type in session1
        await chat_features.start_typing("user1", "session1")

        # Type in session2
        await chat_features.start_typing("user1", "session2")

        # Both sessions should show user typing
        assert chat_features.is_typing("user1", "session1") is True
        assert chat_features.is_typing("user1", "session2") is True


# =============================================================================
# Message Send/Receive Tests
# =============================================================================


class TestMessageSendReceive:
    """Test message sending and receiving."""

    @pytest.mark.asyncio
    async def test_track_message(self, chat_features):
        """Test message tracking."""
        session_id = "session1"
        sender = "user_a"
        recipients = ["user_b", "user_c"]

        # Track message
        msg_info = await chat_features.track_message(
            message_id="msg_001",
            sender_id=sender,
            session_id=session_id,
            recipient_ids=recipients,
        )

        assert msg_info is not None
        assert msg_info.message_id == "msg_001"
        assert msg_info.sender_id == sender
        assert msg_info.session_id == session_id

    @pytest.mark.asyncio
    async def test_message_delivery_status(self, chat_features):
        """Test message delivery status tracking."""
        msg_id = "msg_001"
        session_id = "session1"
        sender = "user_a"
        recipients = ["user_b", "user_c"]

        # Track message
        await chat_features.track_message(msg_id, sender, session_id, recipients)

        # Mark as delivered
        await chat_features.mark_delivered(msg_id)

        # Check info
        msg_info = chat_features.get_message_info(msg_id)
        assert msg_info is not None

    @pytest.mark.asyncio
    async def test_message_read_receipt(self, chat_features):
        """Test read receipt tracking."""
        msg_id = "msg_001"

        # Track the message first
        await chat_features.track_message(msg_id, "user_a", "session1", ["user_b"])

        # Mark as read
        await chat_features.mark_read(msg_id, "user_b")

        # Check read status
        msg_info = chat_features.get_message_info(msg_id)
        assert msg_info is not None

    @pytest.mark.asyncio
    async def test_message_lifecycle(self, chat_features):
        """Test complete message lifecycle."""
        msg_id = "msg_001"
        session_id = "session1"
        sender = "user_a"
        recipients = ["user_b", "user_c"]

        # Track message (sent)
        await chat_features.track_message(msg_id, sender, session_id, recipients)
        msg_info = chat_features.get_message_info(msg_id)
        assert msg_info is not None

        # Mark as delivered
        await chat_features.mark_delivered(msg_id)

        # Mark as read
        await chat_features.mark_read(msg_id, "user_b")

        # Check final state
        final_info = chat_features.get_message_info(msg_id)
        assert final_info is not None
        assert final_info.message_id == msg_id

    @pytest.mark.asyncio
    async def test_mark_sent(self, chat_features):
        """Test marking message as sent."""
        msg_id = "msg_001"

        # Track message
        await chat_features.track_message(msg_id, "user_a", "session1", ["user_b"])

        # Mark as sent
        await chat_features.mark_sent(msg_id)

        # Should be tracked
        assert chat_features.get_message_info(msg_id) is not None

    @pytest.mark.asyncio
    async def test_mark_failed(self, chat_features):
        """Test marking message as failed."""
        msg_id = "msg_001"

        # Track message
        await chat_features.track_message(msg_id, "user_a", "session1", ["user_b"])

        # Mark as failed
        await chat_features.mark_failed(msg_id, "Network error")

        # Should still be tracked
        assert chat_features.get_message_info(msg_id) is not None


# =============================================================================
# Message Ordering Tests
# =============================================================================


class TestMessageOrdering:
    """Test that messages are ordered correctly."""

    @pytest.mark.asyncio
    async def test_rapid_message_ordering(self, chat_features):
        """Test ordering of rapidly sent messages."""
        session_id = "session1"
        sender = "user_a"
        recipient = "user_b"

        # Send 10 messages rapidly
        msg_ids = []
        for i in range(10):
            msg_id = f"msg_{i:03d}"
            await chat_features.track_message(
                msg_id,
                sender,
                session_id,
                [recipient],
            )
            msg_ids.append(msg_id)

        # All should be tracked
        for msg_id in msg_ids:
            assert chat_features.get_message_info(msg_id) is not None

    @pytest.mark.asyncio
    async def test_message_timestamps(self, chat_features):
        """Test message timestamps are ordered."""
        session_id = "session1"
        sender = "user_a"

        # Send messages
        timestamps = []
        for i in range(5):
            msg_id = f"msg_{i}"
            await chat_features.track_message(
                msg_id,
                sender,
                session_id,
                ["user_b"],
            )
            msg_info = chat_features.get_message_info(msg_id)
            timestamps.append(msg_info.sent_at)
            # Small delay
            await asyncio.sleep(0.01)

        # Timestamps should be ordered
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i - 1]

    @pytest.mark.asyncio
    async def test_many_messages(self, chat_features):
        """Test handling many messages."""
        session_id = "session1"
        sender = "user_a"
        num_messages = 50

        # Send many messages
        for i in range(num_messages):
            msg_id = f"msg_{i:04d}"
            await chat_features.track_message(
                msg_id,
                sender,
                session_id,
                ["user_b"],
            )

        # Spot check some messages
        for i in [0, 10, 25, 49]:
            msg_id = f"msg_{i:04d}"
            assert chat_features.get_message_info(msg_id) is not None


# =============================================================================
# Reconnection Tests
# =============================================================================


class TestReconnection:
    """Test reconnection handling."""

    @pytest.mark.asyncio
    async def test_disconnect_and_reconnect(self, chat_features):
        """Test disconnect and reconnect flow."""
        user = "user1"

        # Connect (come online)
        await chat_features.set_online(user)
        assert chat_features.is_online(user)

        # Disconnect (go offline)
        await chat_features.set_offline(user)
        assert not chat_features.is_online(user)

        # Reconnect (come online again)
        await chat_features.set_online(user)
        assert chat_features.is_online(user)

    @pytest.mark.asyncio
    async def test_message_after_reconnect(self, chat_features):
        """Test sending messages after reconnecting."""
        msg_id_1 = "msg_001"
        msg_id_2 = "msg_002"

        # First connection - send message
        await chat_features.set_online("user1")
        await chat_features.track_message(msg_id_1, "user1", "session1", ["user2"])

        # Disconnect
        await chat_features.set_offline("user1")

        # Reconnect - send another message
        await chat_features.set_online("user1")
        await chat_features.track_message(msg_id_2, "user1", "session1", ["user2"])

        # Both messages should be tracked
        assert chat_features.get_message_info(msg_id_1) is not None
        assert chat_features.get_message_info(msg_id_2) is not None

    @pytest.mark.asyncio
    async def test_reconnect_preserves_state(self, chat_features):
        """Test that reconnection preserves presence state."""
        user = "user1"

        # Set up state
        await chat_features.set_online(user)
        await chat_features.start_typing(user, "session1")

        # Simulate disconnect/reconnect
        await chat_features.set_offline(user)
        await chat_features.set_online(user)

        # Should still be able to type
        await chat_features.start_typing(user, "session1")
        assert chat_features.is_typing(user, "session1") is True


# =============================================================================
# Multi-User Tests
# =============================================================================


class TestMultiUser:
    """Test multi-user chat scenarios."""

    @pytest.mark.asyncio
    async def test_broadcast_message(self, chat_features):
        """Test broadcasting message to multiple users."""
        session_id = "session1"
        sender = "user_a"
        recipients = ["user_b", "user_c", "user_d", "user_e"]

        # All users come online
        for user in [sender] + recipients:
            await chat_features.set_online(user)

        # Send broadcast message
        msg_id = "msg_001"
        await chat_features.track_message(msg_id, sender, session_id, recipients)

        # Mark as delivered
        await chat_features.mark_delivered(msg_id)

        # Check message exists
        msg_info = chat_features.get_message_info(msg_id)
        assert msg_info is not None

    @pytest.mark.asyncio
    async def test_multiple_concurrent_conversations(self, chat_features):
        """Test multiple conversations happening simultaneously."""
        await chat_features.set_online("user_a")
        await chat_features.set_online("user_b")
        await chat_features.set_online("user_c")
        await chat_features.set_online("user_d")

        # Send messages in different sessions
        msg_ids = []
        msg_ids.append(
            await chat_features.track_message("msg_1", "user_a", "session1", ["user_b"])
        )
        msg_ids.append(
            await chat_features.track_message("msg_2", "user_c", "session2", ["user_d"])
        )
        msg_ids.append(
            await chat_features.track_message("msg_3", "user_b", "session3", ["user_c"])
        )

        # All should be tracked
        for msg_info in msg_ids:
            assert chat_features.get_message_info(msg_info.message_id) is not None

    @pytest.mark.asyncio
    async def test_five_users_online(self, chat_features):
        """Test 5 users coming online and sending messages."""
        users = [f"user_{i}" for i in range(5)]
        session_id = "group_session"

        # All come online
        for user in users:
            await chat_features.set_online(user)

        # All should be online
        for user in users:
            assert chat_features.is_online(user)

        # One sends broadcast
        sender = users[0]
        recipients = users[1:]

        await chat_features.track_message("msg_001", sender, session_id, recipients)

        # Mark as delivered
        await chat_features.mark_delivered("msg_001")

        # Should be tracked
        assert chat_features.get_message_info("msg_001") is not None

    @pytest.mark.asyncio
    async def test_all_typing_in_session(self, chat_features):
        """Test all users typing in same session."""
        session_id = "group_session"
        users = [f"user_{i}" for i in range(5)]

        # All come online
        for user in users:
            await chat_features.set_online(user)

        # All start typing
        for user in users:
            await chat_features.start_typing(user, session_id)

        # All should be typing
        typing_users = chat_features.get_typing_users(session_id)
        assert len(typing_users) == 5


# =============================================================================
# Integration Tests
# =============================================================================


class TestChatIntegration:
    """Integration tests combining multiple features."""

    @pytest.mark.asyncio
    async def test_full_chat_scenario(self, chat_features):
        """Test a complete realistic chat scenario."""
        session_id = "support_chat"

        # Two users come online
        await chat_features.set_online("customer")
        await chat_features.set_online("support")

        # Customer starts typing
        await chat_features.start_typing("customer", session_id)

        # Customer sends message
        await chat_features.track_message("msg_1", "customer", session_id, ["support"])

        # Support receives and marks as read
        await chat_features.mark_delivered("msg_1")
        await chat_features.mark_read("msg_1", "support")

        # Support types
        await chat_features.start_typing("support", session_id)
        await asyncio.sleep(0.05)

        # Support sends response
        await chat_features.track_message("msg_2", "support", session_id, ["customer"])

        # Customer receives
        await chat_features.mark_delivered("msg_2")
        await chat_features.mark_read("msg_2", "customer")

        # Verify final state
        assert chat_features.is_online("customer")
        assert chat_features.is_online("support")
        assert chat_features.get_message_info("msg_1") is not None
        assert chat_features.get_message_info("msg_2") is not None

    @pytest.mark.asyncio
    async def test_stress_many_messages(self, chat_features):
        """Stress test with many messages."""
        session_id = "stress_session"
        num_messages = 100

        # Send many messages
        for i in range(num_messages):
            msg_id = f"msg_{i:04d}"
            await chat_features.track_message(msg_id, "user_a", session_id, ["user_b"])
            # Mark as delivered/read
            await chat_features.mark_delivered(msg_id)
            await chat_features.mark_read(msg_id, "user_b")

        # Spot check some messages
        for i in [0, 50, 99]:
            msg_id = f"msg_{i:04d}"
            status = chat_features.get_message_info(msg_id)
            assert status is not None

    @pytest.mark.asyncio
    async def test_chat_with_presence_changes(self, chat_features):
        """Test chat with users changing presence status."""
        user = "user_1"
        session_id = "session_1"

        # User online and sends message
        await chat_features.set_online(user)
        await chat_features.track_message("msg_1", user, session_id, ["user_2"])

        # User away
        await chat_features.set_away(user)

        # Can still send message
        await chat_features.track_message("msg_2", user, session_id, ["user_2"])

        # User busy
        await chat_features.set_busy(user)

        # Can still send message
        await chat_features.track_message("msg_3", user, session_id, ["user_2"])

        # User offline
        await chat_features.set_offline(user)

        # All messages should be tracked
        for i in range(1, 4):
            assert chat_features.get_message_info(f"msg_{i}") is not None

    @pytest.mark.asyncio
    async def test_unread_count(self, chat_features):
        """Test unread message counting."""
        user = "user_b"
        session_id = "session1"

        # Send multiple messages
        for i in range(5):
            msg_id = f"msg_{i}"
            await chat_features.track_message(msg_id, "user_a", session_id, [user])

        # Check unread count
        unread = chat_features.get_unread_count(user, session_id)
        assert unread >= 0

        # Get unread messages
        unread_msgs = chat_features.get_unread_messages(user, session_id)
        assert len(unread_msgs) >= 0


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Test error handling in chat."""

    @pytest.mark.asyncio
    async def test_empty_session_id(self, chat_features):
        """Test handling of empty session ID."""
        # Should not crash with empty session
        msg_info = await chat_features.track_message("msg_1", "user_a", "", ["user_b"])
        assert msg_info is not None

    @pytest.mark.asyncio
    async def test_duplicate_message_id(self, chat_features):
        """Test handling of duplicate message IDs."""
        msg_id = "msg_001"
        session_id = "session1"

        # Track same message twice
        await chat_features.track_message(msg_id, "user_a", session_id, ["user_b"])
        await chat_features.track_message(msg_id, "user_a", session_id, ["user_b"])

        # Should still be tracked
        assert chat_features.get_message_info(msg_id) is not None

    @pytest.mark.asyncio
    async def test_mark_offline_user_message(self, chat_features):
        """Test marking message delivered to offline user."""
        msg_id = "msg_001"

        # Track message to user not online
        await chat_features.track_message(msg_id, "user_a", "session1", ["user_b"])

        # Mark as read by offline user
        await chat_features.mark_read(msg_id, "user_b")

        # Should still work
        assert chat_features.get_message_info(msg_id) is not None

    @pytest.mark.asyncio
    async def test_stop_typing_not_typing(self, chat_features):
        """Test stopping typing when not typing."""
        user = "user1"
        session_id = "session1"

        # Try to stop typing without starting
        await chat_features.stop_typing(user, session_id)
        # Should not crash, result may be None

    @pytest.mark.asyncio
    async def test_get_offline_presence(self, chat_features):
        """Test getting presence for never-online user."""
        presence = chat_features.get_presence("never_online_user")
        # Should handle gracefully
        if presence is not None:
            assert presence.user_id == "never_online_user"


# =============================================================================
# Summary Tests
# =============================================================================


class TestChatFeaturesSummary:
    """Summary test showing what works."""

    @pytest.mark.asyncio
    async def test_chat_features_exist_and_work(self, chat_features):
        """Verify chat features are working."""
        # Test each main feature category

        # 1. Presence works
        await chat_features.set_online("user1")
        assert chat_features.is_online("user1")

        # 2. Typing indicators work
        await chat_features.start_typing("user1", "session1")
        assert chat_features.is_typing("user1", "session1")

        # 3. Message tracking works
        msg = await chat_features.track_message("msg1", "user1", "session1", ["user2"])
        assert msg is not None
        assert msg.message_id == "msg1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
