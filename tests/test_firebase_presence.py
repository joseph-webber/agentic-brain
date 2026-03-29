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

"""Tests for Firebase presence and typing indicators.

Tests the PresenceManager, PresenceStatus, and typing indicator system.
"""

import asyncio
from datetime import UTC, datetime, timezone

import pytest

from agentic_brain.transport import (
    FirebasePresence,
    PresenceManager,
    PresenceStatus,
    TypingIndicator,
    TypingStatus,
    UserPresence,
)


def _utc_now() -> datetime:
    """Get current UTC time as timezone-aware datetime."""
    return datetime.now(UTC)


class TestPresenceStatus:
    """Test PresenceStatus enum."""

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        assert PresenceStatus.ONLINE is not None
        assert PresenceStatus.AWAY is not None
        assert PresenceStatus.BUSY is not None
        assert PresenceStatus.OFFLINE is not None

    def test_status_values(self):
        """Test status string values."""
        assert PresenceStatus.ONLINE.value == "online"
        assert PresenceStatus.AWAY.value == "away"
        assert PresenceStatus.BUSY.value == "busy"
        assert PresenceStatus.OFFLINE.value == "offline"


class TestTypingStatus:
    """Test TypingStatus enum."""

    def test_all_statuses_exist(self):
        """Test typing statuses exist."""
        assert TypingStatus.TYPING is not None
        assert TypingStatus.STOPPED is not None

    def test_status_values(self):
        """Test typing status values."""
        assert TypingStatus.TYPING.value == "typing"
        assert TypingStatus.STOPPED.value == "stopped"


class TestUserPresence:
    """Test UserPresence dataclass."""

    def test_create_presence(self):
        """Test creating user presence."""
        now = _utc_now()
        presence = UserPresence(
            user_id="user123",
            status=PresenceStatus.ONLINE,
            last_seen=now,
            device_id="device-ios-123",
        )
        assert presence.user_id == "user123"
        assert presence.status == PresenceStatus.ONLINE
        assert presence.last_seen == now
        assert presence.device_id == "device-ios-123"

    def test_presence_to_dict(self):
        """Test serializing presence to dict."""
        now = _utc_now()
        presence = UserPresence(
            user_id="user123",
            status=PresenceStatus.ONLINE,
            last_seen=now,
        )
        data = presence.to_dict()
        assert data["user_id"] == "user123"
        assert data["status"] == "online"
        assert data["last_seen"] == now.isoformat()

    def test_presence_from_dict(self):
        """Test deserializing presence from dict."""
        now = _utc_now()
        data = {
            "user_id": "user123",
            "status": "away",
            "last_seen": now.isoformat(),
            "device_type": "mobile",
        }
        presence = UserPresence.from_dict(data)
        assert presence.user_id == "user123"
        assert presence.status == PresenceStatus.AWAY
        assert presence.device_type == "mobile"

    def test_is_online_property(self):
        """Test is_online property."""
        online = UserPresence(user_id="u1", status=PresenceStatus.ONLINE)
        away = UserPresence(user_id="u2", status=PresenceStatus.AWAY)
        busy = UserPresence(user_id="u3", status=PresenceStatus.BUSY)
        offline = UserPresence(user_id="u4", status=PresenceStatus.OFFLINE)

        assert online.is_online is True
        assert away.is_online is True
        assert busy.is_online is True
        assert offline.is_online is False


class TestTypingIndicator:
    """Test TypingIndicator dataclass."""

    def test_create_indicator(self):
        """Test creating typing indicator."""
        now = _utc_now()
        indicator = TypingIndicator(
            user_id="user123",
            session_id="sess456",
            status=TypingStatus.TYPING,
            started_at=now,
        )
        assert indicator.user_id == "user123"
        assert indicator.session_id == "sess456"
        assert indicator.status == TypingStatus.TYPING

    def test_indicator_to_dict(self):
        """Test serializing indicator."""
        now = _utc_now()
        indicator = TypingIndicator(
            user_id="user123",
            session_id="sess456",
            status=TypingStatus.TYPING,
            started_at=now,
        )
        data = indicator.to_dict()
        assert data["user_id"] == "user123"
        assert data["session_id"] == "sess456"
        assert data["status"] == "typing"

    def test_indicator_from_dict(self):
        """Test deserializing indicator."""
        now = _utc_now()
        data = {
            "user_id": "user123",
            "session_id": "sess456",
            "status": "stopped",
            "started_at": now.isoformat(),
        }
        indicator = TypingIndicator.from_dict(data)
        assert indicator.user_id == "user123"
        assert indicator.status == TypingStatus.STOPPED


class TestPresenceManager:
    """Test local PresenceManager."""

    def test_init(self):
        """Test manager initialization."""
        manager = PresenceManager()
        assert manager is not None

    def test_init_with_custom_timeouts(self):
        """Test initialization with custom timeouts."""
        manager = PresenceManager(
            away_timeout=60.0,
            offline_timeout=120.0,
            typing_timeout=3.0,
        )
        assert manager._away_timeout == 60.0
        assert manager._offline_timeout == 120.0
        assert manager._typing_timeout == 3.0

    @pytest.mark.asyncio
    async def test_set_online(self):
        """Test setting user online."""
        manager = PresenceManager()

        presence = await manager.set_online("user123", device_id="dev1")

        assert presence is not None
        assert presence.status == PresenceStatus.ONLINE
        assert presence.user_id == "user123"
        assert presence.device_id == "dev1"

    @pytest.mark.asyncio
    async def test_set_away(self):
        """Test setting user away."""
        manager = PresenceManager()
        await manager.set_online("user123")

        presence = await manager.set_away("user123")

        assert presence.status == PresenceStatus.AWAY

    @pytest.mark.asyncio
    async def test_set_busy(self):
        """Test setting user busy."""
        manager = PresenceManager()
        await manager.set_online("user123")

        presence = await manager.set_busy("user123", custom_status="In a meeting")

        assert presence.status == PresenceStatus.BUSY
        assert presence.custom_status == "In a meeting"

    @pytest.mark.asyncio
    async def test_set_offline(self):
        """Test setting user offline."""
        manager = PresenceManager()
        await manager.set_online("user123")

        presence = await manager.set_offline("user123")

        assert presence.status == PresenceStatus.OFFLINE

    @pytest.mark.asyncio
    async def test_get_presence(self):
        """Test getting user presence."""
        manager = PresenceManager()
        await manager.set_online("user123")

        presence = manager.get_presence("user123")

        assert presence is not None
        assert presence.user_id == "user123"

    def test_get_nonexistent_user(self):
        """Test getting presence for unknown user."""
        manager = PresenceManager()
        presence = manager.get_presence("nobody")
        assert presence is None

    @pytest.mark.asyncio
    async def test_get_online_users(self):
        """Test getting all online users."""
        manager = PresenceManager()
        await manager.set_online("user1")
        await manager.set_online("user2")
        await manager.set_online("user3")
        await manager.set_offline("user3")

        online = manager.get_online_users()

        assert len(online) == 2
        user_ids = [p.user_id for p in online]
        assert "user1" in user_ids
        assert "user2" in user_ids

    @pytest.mark.asyncio
    async def test_start_typing(self):
        """Test starting typing indicator."""
        manager = PresenceManager()

        indicator = await manager.start_typing("user123", "session456")

        assert indicator.user_id == "user123"
        assert indicator.session_id == "session456"
        assert indicator.status == TypingStatus.TYPING

    @pytest.mark.asyncio
    async def test_stop_typing(self):
        """Test stopping typing indicator."""
        manager = PresenceManager()
        await manager.start_typing("user123", "session456")

        indicator = await manager.stop_typing("user123", "session456")

        assert indicator.status == TypingStatus.STOPPED

    @pytest.mark.asyncio
    async def test_is_typing(self):
        """Test checking if user is typing."""
        manager = PresenceManager()

        assert not manager.is_typing("user123", "session456")

        await manager.start_typing("user123", "session456")
        assert manager.is_typing("user123", "session456")

        await manager.stop_typing("user123", "session456")
        assert not manager.is_typing("user123", "session456")

    @pytest.mark.asyncio
    async def test_get_typing_users(self):
        """Test getting all typing users in session."""
        manager = PresenceManager()
        await manager.start_typing("user1", "session456")
        await manager.start_typing("user2", "session456")
        await manager.start_typing("user3", "other_session")

        typing = manager.get_typing_users("session456")

        assert len(typing) == 2

    @pytest.mark.asyncio
    async def test_touch_updates_activity(self):
        """Test that touch updates last_activity."""
        manager = PresenceManager()
        await manager.set_online("user123")

        old_presence = manager.get_presence("user123")
        old_activity = old_presence.last_activity

        await asyncio.sleep(0.01)  # Small delay
        await manager.touch("user123")

        new_presence = manager.get_presence("user123")
        assert new_presence.last_activity > old_activity


class TestPresenceCallbacks:
    """Test presence change callbacks."""

    @pytest.mark.asyncio
    async def test_on_presence_change(self):
        """Test callback fires on presence change."""
        manager = PresenceManager()
        changes = []

        def callback(presence):
            changes.append(presence)

        manager.on_presence_change(callback)
        await manager.set_online("user123")
        await manager.set_away("user123")

        assert len(changes) >= 2

    @pytest.mark.asyncio
    async def test_on_typing_change(self):
        """Test callback fires on typing change."""
        manager = PresenceManager()
        typing_events = []

        def callback(indicator):
            typing_events.append(indicator)

        manager.on_typing_change(callback)
        await manager.start_typing("user123", "session456")

        assert len(typing_events) >= 1


class TestFirebasePresence:
    """Test Firebase-synced presence."""

    def test_inherits_local_behavior(self):
        """Test that Firebase presence has all local methods."""
        presence = FirebasePresence()

        # Should have all PresenceManager methods
        assert hasattr(presence, "set_online")
        assert hasattr(presence, "set_away")
        assert hasattr(presence, "set_busy")
        assert hasattr(presence, "set_offline")
        assert hasattr(presence, "get_presence")
        assert hasattr(presence, "start_typing")
        assert hasattr(presence, "stop_typing")

    @pytest.mark.asyncio
    async def test_local_mode_works(self):
        """Test presence works in local-only mode."""
        presence = FirebasePresence()  # No Firebase URL = local only

        result = await presence.set_online("user123")

        assert result is not None
        assert result.status == PresenceStatus.ONLINE


class TestPresenceLifecycle:
    """Test presence manager lifecycle."""

    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping manager."""
        manager = PresenceManager()

        await manager.start()
        assert manager._cleanup_task is not None

        await manager.stop()
        assert manager._cleanup_task is None

    @pytest.mark.asyncio
    async def test_get_all_presence(self):
        """Test getting all presence records."""
        manager = PresenceManager()

        await manager.set_online("user1")
        await manager.set_online("user2")
        await manager.set_away("user2")  # Must be online first
        await manager.set_online("user3")
        await manager.set_busy("user3")  # Must be online first

        all_presence = manager.get_all_presence()

        assert len(all_presence) == 3


class TestPresenceStats:
    """Test presence statistics."""

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting presence statistics."""
        manager = PresenceManager()

        await manager.set_online("user1")
        await manager.set_online("user2")
        await manager.set_online("user3")
        await manager.set_away("user3")  # Must be online first
        await manager.set_online("user4")
        await manager.set_busy("user4")  # Must be online first
        await manager.set_online("user5")
        await manager.set_offline("user5")  # Must be online first

        stats = manager.get_stats()

        assert stats["online"] == 2
        assert stats["away"] == 1
        assert stats["busy"] == 1
        assert stats["offline"] == 1
        assert stats["total"] == 5
