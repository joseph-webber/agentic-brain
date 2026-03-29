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
Firebase Presence System - Real-time online/offline/typing status.

Features:
- User online/offline detection
- Typing indicators
- Last seen timestamps
- Multi-device presence
- Automatic cleanup on disconnect
"""

import asyncio
import contextlib
import inspect
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from .utils import utc_now as _utc_now

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials as firebase_credentials
    from firebase_admin import db as firebase_db

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None  # type: ignore[assignment]
    firebase_credentials = None  # type: ignore[assignment]
    firebase_db = None  # type: ignore[assignment]


class PresenceStatus(Enum):
    """User presence status."""

    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"


class TypingStatus(Enum):
    """Typing indicator status."""

    TYPING = "typing"
    STOPPED = "stopped"


@dataclass
class UserPresence:
    """User presence information."""

    user_id: str
    status: PresenceStatus = PresenceStatus.OFFLINE
    last_seen: datetime = field(default_factory=_utc_now)
    last_activity: datetime = field(default_factory=_utc_now)
    device_id: Optional[str] = None
    device_type: Optional[str] = None  # web, mobile, desktop
    custom_status: Optional[str] = None  # "In a meeting", etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Firebase."""
        return {
            "user_id": self.user_id,
            "status": self.status.value,
            "last_seen": self.last_seen.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "device_id": self.device_id,
            "device_type": self.device_type,
            "custom_status": self.custom_status,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserPresence":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            status=PresenceStatus(data.get("status", "offline")),
            last_seen=(
                datetime.fromisoformat(data["last_seen"])
                if "last_seen" in data
                else _utc_now()
            ),
            last_activity=(
                datetime.fromisoformat(data["last_activity"])
                if "last_activity" in data
                else _utc_now()
            ),
            device_id=data.get("device_id"),
            device_type=data.get("device_type"),
            custom_status=data.get("custom_status"),
        )

    @property
    def is_online(self) -> bool:
        """Check if user is online."""
        return self.status in (
            PresenceStatus.ONLINE,
            PresenceStatus.AWAY,
            PresenceStatus.BUSY,
        )

    @property
    def seconds_since_activity(self) -> float:
        """Seconds since last activity."""
        return (_utc_now() - self.last_activity).total_seconds()


@dataclass
class TypingIndicator:
    """Typing indicator for a session."""

    user_id: str
    session_id: str
    status: TypingStatus = TypingStatus.STOPPED
    started_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TypingIndicator":
        """Create from dictionary."""
        return cls(
            user_id=data["user_id"],
            session_id=data["session_id"],
            status=TypingStatus(data.get("status", "stopped")),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if "started_at" in data
                else _utc_now()
            ),
        )


class PresenceManager:
    """
    Manages user presence and typing indicators.

    Usage:
        presence = PresenceManager()

        # Set user online
        await presence.set_online("user-123", device_id="device-1")

        # Check who's online
        online_users = presence.get_online_users()

        # Typing indicators
        await presence.start_typing("user-123", "session-456")
        await presence.stop_typing("user-123", "session-456")

        # Get typing users in session
        typing = presence.get_typing_users("session-456")
    """

    def __init__(
        self,
        away_timeout: float = 300.0,  # 5 minutes
        offline_timeout: float = 600.0,  # 10 minutes
        typing_timeout: float = 5.0,  # 5 seconds
    ):
        """
        Initialize presence manager.

        Args:
            away_timeout: Seconds of inactivity before "away"
            offline_timeout: Seconds of inactivity before "offline"
            typing_timeout: Seconds before typing indicator expires
        """
        self._users: dict[str, UserPresence] = {}
        self._typing: dict[str, TypingIndicator] = {}  # key: user_id:session_id
        self._callbacks: dict[str, list[Callable]] = {
            "presence_change": [],
            "typing_change": [],
        }
        self._away_timeout = away_timeout
        self._offline_timeout = offline_timeout
        self._typing_timeout = typing_timeout
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Presence manager started")

    async def stop(self) -> None:
        """Stop background tasks."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
            self._cleanup_task = None
            logger.info("Presence manager stopped")

    async def _cleanup_loop(self) -> None:
        """Background task to update presence status."""
        while True:
            try:
                await asyncio.sleep(30)  # Check every 30 seconds
                await self._update_stale_presence()
                await self._cleanup_typing()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Presence cleanup error: {e}")

    async def _update_stale_presence(self) -> None:
        """Update users who have gone away/offline."""
        now = _utc_now()

        for user_id, presence in list(self._users.items()):
            if presence.status == PresenceStatus.OFFLINE:
                continue

            seconds_idle = (now - presence.last_activity).total_seconds()

            if seconds_idle > self._offline_timeout:
                await self.set_offline(user_id)
            elif (
                seconds_idle > self._away_timeout
                and presence.status == PresenceStatus.ONLINE
            ):
                await self.set_away(user_id)

    async def _cleanup_typing(self) -> None:
        """Remove stale typing indicators."""
        now = _utc_now()

        for _key, indicator in list(self._typing.items()):
            if indicator.status == TypingStatus.STOPPED:
                continue

            seconds = (now - indicator.started_at).total_seconds()
            if seconds > self._typing_timeout:
                await self.stop_typing(indicator.user_id, indicator.session_id)

    def on_presence_change(self, callback: Callable[[UserPresence], None]) -> None:
        """Register callback for presence changes."""
        self._callbacks["presence_change"].append(callback)

    def on_typing_change(self, callback: Callable[[TypingIndicator], None]) -> None:
        """Register callback for typing changes."""
        self._callbacks["typing_change"].append(callback)

    async def _notify_presence(self, presence: UserPresence) -> None:
        """Notify presence change callbacks."""
        for callback in self._callbacks["presence_change"]:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(presence)
                else:
                    callback(presence)
            except Exception as e:
                logger.error(f"Presence callback error: {e}")

    async def _notify_typing(self, indicator: TypingIndicator) -> None:
        """Notify typing change callbacks."""
        for callback in self._callbacks["typing_change"]:
            try:
                if inspect.iscoroutinefunction(callback):
                    await callback(indicator)
                else:
                    callback(indicator)
            except Exception as e:
                logger.error(f"Typing callback error: {e}")

    async def set_online(
        self,
        user_id: str,
        device_id: Optional[str] = None,
        device_type: Optional[str] = None,
        custom_status: Optional[str] = None,
    ) -> UserPresence:
        """
        Set user as online.

        Args:
            user_id: User identifier
            device_id: Device identifier
            device_type: Device type (web, mobile, desktop)
            custom_status: Custom status message

        Returns:
            Updated UserPresence
        """
        now = _utc_now()

        presence = UserPresence(
            user_id=user_id,
            status=PresenceStatus.ONLINE,
            last_seen=now,
            last_activity=now,
            device_id=device_id,
            device_type=device_type,
            custom_status=custom_status,
        )

        self._users[user_id] = presence
        await self._notify_presence(presence)

        logger.debug(f"User {user_id} is now online")
        return presence

    async def set_away(self, user_id: str) -> Optional[UserPresence]:
        """Set user as away."""
        if user_id not in self._users:
            return None

        presence = self._users[user_id]
        presence.status = PresenceStatus.AWAY
        presence.last_seen = _utc_now()

        await self._notify_presence(presence)
        logger.debug(f"User {user_id} is now away")
        return presence

    async def set_busy(
        self, user_id: str, custom_status: Optional[str] = None
    ) -> Optional[UserPresence]:
        """Set user as busy."""
        if user_id not in self._users:
            return None

        presence = self._users[user_id]
        presence.status = PresenceStatus.BUSY
        presence.last_seen = _utc_now()
        if custom_status:
            presence.custom_status = custom_status

        await self._notify_presence(presence)
        logger.debug(f"User {user_id} is now busy")
        return presence

    async def set_offline(self, user_id: str) -> Optional[UserPresence]:
        """Set user as offline."""
        if user_id not in self._users:
            return None

        presence = self._users[user_id]
        presence.status = PresenceStatus.OFFLINE
        presence.last_seen = _utc_now()

        await self._notify_presence(presence)
        logger.debug(f"User {user_id} is now offline")
        return presence

    async def heartbeat(self, user_id: str) -> Optional[UserPresence]:
        """
        Update user's last activity (call periodically to stay online).

        Args:
            user_id: User identifier

        Returns:
            Updated presence or None if user not found
        """
        if user_id not in self._users:
            return None

        presence = self._users[user_id]
        presence.last_activity = _utc_now()

        # If was away, come back online
        if presence.status == PresenceStatus.AWAY:
            presence.status = PresenceStatus.ONLINE
            await self._notify_presence(presence)

        return presence

    def get_presence(self, user_id: str) -> Optional[UserPresence]:
        """Get user's current presence."""
        return self._users.get(user_id)

    def get_online_users(self) -> list[UserPresence]:
        """Get all online users."""
        return [p for p in self._users.values() if p.is_online]

    def get_users_by_status(self, status: PresenceStatus) -> list[UserPresence]:
        """Get users with specific status."""
        return [p for p in self._users.values() if p.status == status]

    def is_online(self, user_id: str) -> bool:
        """Check if user is online."""
        presence = self._users.get(user_id)
        return presence.is_online if presence else False

    async def start_typing(self, user_id: str, session_id: str) -> TypingIndicator:
        """
        Set user as typing in a session.

        Args:
            user_id: User identifier
            session_id: Session/conversation identifier

        Returns:
            TypingIndicator
        """
        key = f"{user_id}:{session_id}"

        indicator = TypingIndicator(
            user_id=user_id,
            session_id=session_id,
            status=TypingStatus.TYPING,
            started_at=_utc_now(),
        )

        self._typing[key] = indicator
        await self._notify_typing(indicator)

        logger.debug(f"User {user_id} started typing in {session_id}")
        return indicator

    async def stop_typing(
        self, user_id: str, session_id: str
    ) -> Optional[TypingIndicator]:
        """
        Stop typing indicator.

        Args:
            user_id: User identifier
            session_id: Session identifier

        Returns:
            Updated indicator or None
        """
        key = f"{user_id}:{session_id}"

        if key not in self._typing:
            return None

        indicator = self._typing[key]
        indicator.status = TypingStatus.STOPPED

        await self._notify_typing(indicator)

        # Remove from tracking
        del self._typing[key]

        logger.debug(f"User {user_id} stopped typing in {session_id}")
        return indicator

    def get_typing_users(self, session_id: str) -> list[TypingIndicator]:
        """Get all users currently typing in a session."""
        return [
            ind
            for ind in self._typing.values()
            if ind.session_id == session_id and ind.status == TypingStatus.TYPING
        ]

    def is_typing(self, user_id: str, session_id: str) -> bool:
        """Check if user is typing in session."""
        key = f"{user_id}:{session_id}"
        indicator = self._typing.get(key)
        return indicator.status == TypingStatus.TYPING if indicator else False

    async def touch(self, user_id: str) -> Optional[UserPresence]:
        """Alias for heartbeat - update user's last activity."""
        return await self.heartbeat(user_id)

    def get_all_presence(self) -> list[UserPresence]:
        """Get all presence records."""
        return list(self._users.values())

    def get_stats(self) -> dict[str, Any]:
        """Get presence statistics."""
        users = list(self._users.values())

        return {
            "total_users": len(users),
            "total": len(users),  # Alias for compatibility
            "online": sum(1 for u in users if u.status == PresenceStatus.ONLINE),
            "away": sum(1 for u in users if u.status == PresenceStatus.AWAY),
            "busy": sum(1 for u in users if u.status == PresenceStatus.BUSY),
            "offline": sum(1 for u in users if u.status == PresenceStatus.OFFLINE),
            "typing_indicators": len(self._typing),
            "active_typing": sum(
                1 for t in self._typing.values() if t.status == TypingStatus.TYPING
            ),
        }


# Firebase-backed presence (requires Firebase)


class FirebasePresence(PresenceManager):
    """
    Presence manager backed by Firebase Realtime Database.

    Syncs presence across all connected clients in real-time.
    Uses Firebase's onDisconnect() for automatic offline detection.

    Usage:
        from agentic_brain.transport import FirebasePresence

        presence = FirebasePresence(
            database_url="https://project.firebaseio.com",
            credentials_path="service-account.json"
        )

        await presence.start()
        await presence.set_online("user-123")

        # Listen for presence changes
        presence.on_presence_change(lambda p: print(f"{p.user_id} is {p.status}"))
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        credentials_path: Optional[str] = None,
        presence_path: str = "presence",
        typing_path: str = "typing",
        **kwargs,
    ):
        """
        Initialize Firebase-backed presence.

        Args:
            database_url: Firebase Realtime Database URL
            credentials_path: Path to service account JSON
            presence_path: Database path for presence data
            typing_path: Database path for typing indicators
            **kwargs: Additional PresenceManager args
        """
        super().__init__(**kwargs)

        self._database_url = database_url
        self._credentials_path = credentials_path
        self._presence_path = presence_path
        self._typing_path = typing_path
        self._db = None
        self._initialized = False

        if not FIREBASE_AVAILABLE:
            logger.warning("Firebase SDK not installed, using local presence only")
            return

        # Try to initialize Firebase
        try:
            if credentials_path:
                cred = firebase_credentials.Certificate(credentials_path)
                try:
                    firebase_admin.get_app("presence")
                except ValueError:
                    firebase_admin.initialize_app(
                        cred, {"databaseURL": database_url}, name="presence"
                    )

                self._db = firebase_db
                self._initialized = True
                logger.info("Firebase presence initialized")
        except Exception as e:
            logger.warning(f"Firebase initialization failed: {e}")

    @property
    def is_firebase_enabled(self) -> bool:
        """Check if Firebase backend is available."""
        return self._initialized and self._db is not None

    async def set_online(
        self,
        user_id: str,
        device_id: Optional[str] = None,
        device_type: Optional[str] = None,
        custom_status: Optional[str] = None,
    ) -> UserPresence:
        """Set user online (syncs to Firebase)."""
        presence = await super().set_online(
            user_id, device_id, device_type, custom_status
        )

        if self.is_firebase_enabled:
            try:
                ref = self._db.reference(f"{self._presence_path}/{user_id}")
                ref.set(presence.to_dict())

                # Set up onDisconnect to mark offline
                ref.child("status").on_disconnect().set("offline")
                ref.child("last_seen").on_disconnect().set({".sv": "timestamp"})
            except Exception as e:
                logger.error(f"Firebase presence sync failed: {e}")

        return presence

    async def set_offline(self, user_id: str) -> Optional[UserPresence]:
        """Set user offline (syncs to Firebase)."""
        presence = await super().set_offline(user_id)

        if presence and self.is_firebase_enabled:
            try:
                ref = self._db.reference(f"{self._presence_path}/{user_id}")
                ref.update(
                    {
                        "status": "offline",
                        "last_seen": presence.last_seen.isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"Firebase presence sync failed: {e}")

        return presence

    async def start_typing(self, user_id: str, session_id: str) -> TypingIndicator:
        """Start typing (syncs to Firebase)."""
        indicator = await super().start_typing(user_id, session_id)

        if self.is_firebase_enabled:
            try:
                ref = self._db.reference(f"{self._typing_path}/{session_id}/{user_id}")
                ref.set(indicator.to_dict())

                # Auto-remove typing indicator on disconnect
                ref.on_disconnect().remove()
            except Exception as e:
                logger.error(f"Firebase typing sync failed: {e}")

        return indicator

    async def stop_typing(
        self, user_id: str, session_id: str
    ) -> Optional[TypingIndicator]:
        """Stop typing (syncs to Firebase)."""
        indicator = await super().stop_typing(user_id, session_id)

        if self.is_firebase_enabled:
            try:
                ref = self._db.reference(f"{self._typing_path}/{session_id}/{user_id}")
                ref.remove()
            except Exception as e:
                logger.error(f"Firebase typing sync failed: {e}")

        return indicator
