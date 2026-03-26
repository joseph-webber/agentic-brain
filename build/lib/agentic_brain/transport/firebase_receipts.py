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

"""
Firebase Read Receipts - Track message delivery and read status.

Features:
- Delivery confirmation (message reached server)
- Read receipts (message was seen)
- Per-user read tracking
- Unread count queries
- Bulk read operations
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from .utils import utc_now as _utc_now

logger = logging.getLogger(__name__)


class MessageStatus(Enum):
    """Message delivery/read status."""

    SENDING = "sending"  # Being sent
    SENT = "sent"  # Sent to server
    DELIVERED = "delivered"  # Delivered to recipient device
    READ = "read"  # Read by recipient
    FAILED = "failed"  # Send failed


@dataclass
class ReadReceipt:
    """Read receipt for a message."""

    message_id: str
    user_id: str
    status: MessageStatus
    timestamp: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReadReceipt":
        """Create from dictionary."""
        return cls(
            message_id=data["message_id"],
            user_id=data["user_id"],
            status=MessageStatus(data.get("status", "sent")),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if "timestamp" in data
                else _utc_now()
            ),
        )


@dataclass
class MessageReadInfo:
    """Read information for a single message."""

    message_id: str
    sender_id: str
    session_id: str
    status: MessageStatus = MessageStatus.SENT
    sent_at: datetime = field(default_factory=_utc_now)
    delivered_at: Optional[datetime] = None
    read_by: dict[str, datetime] = field(default_factory=dict)  # user_id -> read_time

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "sent_at": self.sent_at.isoformat(),
            "delivered_at": (
                self.delivered_at.isoformat() if self.delivered_at else None
            ),
            "read_by": {uid: ts.isoformat() for uid, ts in self.read_by.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MessageReadInfo":
        """Create from dictionary."""
        read_by = {}
        if "read_by" in data:
            read_by = {
                uid: datetime.fromisoformat(ts) for uid, ts in data["read_by"].items()
            }

        return cls(
            message_id=data["message_id"],
            sender_id=data["sender_id"],
            session_id=data["session_id"],
            status=MessageStatus(data.get("status", "sent")),
            sent_at=(
                datetime.fromisoformat(data["sent_at"])
                if "sent_at" in data
                else _utc_now()
            ),
            delivered_at=(
                datetime.fromisoformat(data["delivered_at"])
                if data.get("delivered_at")
                else None
            ),
            read_by=read_by,
        )

    @property
    def is_read(self) -> bool:
        """Check if message has been read by anyone."""
        return len(self.read_by) > 0

    @property
    def read_count(self) -> int:
        """Number of users who have read this message."""
        return len(self.read_by)

    def is_read_by(self, user_id: str) -> bool:
        """Check if specific user has read this message."""
        return user_id in self.read_by


class ReadReceiptManager:
    """
    Manages read receipts for messages.

    Usage:
        receipts = ReadReceiptManager()

        # Track a sent message
        receipts.track_message("msg-123", "user-1", "session-456")

        # Mark as delivered
        await receipts.mark_delivered("msg-123")

        # Mark as read by user
        await receipts.mark_read("msg-123", "user-2")

        # Get unread count for user
        count = receipts.get_unread_count("user-2", "session-456")

        # Mark all as read
        await receipts.mark_all_read("user-2", "session-456")
    """

    def __init__(self):
        """Initialize receipt manager."""
        self._messages: dict[str, MessageReadInfo] = {}
        self._callbacks: dict[str, list[Callable]] = {
            "status_change": [],
            "read": [],
        }

    def on_status_change(self, callback: Callable[[MessageReadInfo], None]) -> None:
        """Register callback for status changes."""
        self._callbacks["status_change"].append(callback)

    def on_read(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for read events (message_id, user_id)."""
        self._callbacks["read"].append(callback)

    async def _notify_status(self, info: MessageReadInfo) -> None:
        """Notify status change callbacks."""
        for callback in self._callbacks["status_change"]:
            try:
                if hasattr(callback, "__await__"):
                    await callback(info)
                else:
                    callback(info)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    async def _notify_read(self, message_id: str, user_id: str) -> None:
        """Notify read callbacks."""
        for callback in self._callbacks["read"]:
            try:
                if hasattr(callback, "__await__"):
                    await callback(message_id, user_id)
                else:
                    callback(message_id, user_id)
            except Exception as e:
                logger.error(f"Read callback error: {e}")

    def track_message(
        self,
        message_id: str,
        sender_id: str,
        session_id: str,
    ) -> MessageReadInfo:
        """
        Start tracking a message.

        Args:
            message_id: Unique message identifier
            sender_id: ID of message sender
            session_id: Session/conversation ID

        Returns:
            MessageReadInfo for tracking
        """
        info = MessageReadInfo(
            message_id=message_id,
            sender_id=sender_id,
            session_id=session_id,
            status=MessageStatus.SENDING,
        )

        self._messages[message_id] = info
        logger.debug(f"Tracking message {message_id}")
        return info

    async def mark_sent(self, message_id: str) -> Optional[MessageReadInfo]:
        """Mark message as sent to server."""
        if message_id not in self._messages:
            return None

        info = self._messages[message_id]
        info.status = MessageStatus.SENT
        info.sent_at = _utc_now()

        await self._notify_status(info)
        return info

    async def mark_delivered(self, message_id: str) -> Optional[MessageReadInfo]:
        """Mark message as delivered to recipient device."""
        if message_id not in self._messages:
            return None

        info = self._messages[message_id]
        info.status = MessageStatus.DELIVERED
        info.delivered_at = _utc_now()

        await self._notify_status(info)
        logger.debug(f"Message {message_id} delivered")
        return info

    async def mark_read(
        self, message_id: str, user_id: str
    ) -> Optional[MessageReadInfo]:
        """
        Mark message as read by user.

        Args:
            message_id: Message identifier
            user_id: User who read the message

        Returns:
            Updated MessageReadInfo
        """
        if message_id not in self._messages:
            return None

        info = self._messages[message_id]

        # Don't track sender reading their own message
        if user_id == info.sender_id:
            return info

        # Already read by this user
        if user_id in info.read_by:
            return info

        info.read_by[user_id] = _utc_now()
        info.status = MessageStatus.READ

        await self._notify_status(info)
        await self._notify_read(message_id, user_id)

        logger.debug(f"Message {message_id} read by {user_id}")
        return info

    async def mark_failed(
        self, message_id: str, error: Optional[str] = None
    ) -> Optional[MessageReadInfo]:
        """Mark message as failed to send."""
        if message_id not in self._messages:
            return None

        info = self._messages[message_id]
        info.status = MessageStatus.FAILED

        await self._notify_status(info)
        logger.warning(f"Message {message_id} failed: {error}")
        return info

    def get_message_info(self, message_id: str) -> Optional[MessageReadInfo]:
        """Get read info for a message."""
        return self._messages.get(message_id)

    def get_unread_messages(
        self, user_id: str, session_id: str
    ) -> list[MessageReadInfo]:
        """
        Get all unread messages for a user in a session.

        Args:
            user_id: User to check
            session_id: Session/conversation

        Returns:
            List of unread messages
        """
        return [
            info
            for info in self._messages.values()
            if info.session_id == session_id
            and info.sender_id != user_id
            and user_id not in info.read_by
        ]

    def get_unread_count(self, user_id: str, session_id: str) -> int:
        """Get count of unread messages for user in session."""
        return len(self.get_unread_messages(user_id, session_id))

    async def mark_all_read(self, user_id: str, session_id: str) -> int:
        """
        Mark all messages as read by user in session.

        Args:
            user_id: User who is reading
            session_id: Session/conversation

        Returns:
            Number of messages marked as read
        """
        unread = self.get_unread_messages(user_id, session_id)

        for info in unread:
            await self.mark_read(info.message_id, user_id)

        logger.debug(f"Marked {len(unread)} messages read for {user_id}")
        return len(unread)

    def get_read_by(self, message_id: str) -> list[str]:
        """Get list of users who have read a message."""
        info = self._messages.get(message_id)
        return list(info.read_by.keys()) if info else []

    def get_session_messages(self, session_id: str) -> list[MessageReadInfo]:
        """Get all messages for a session."""
        return [
            info for info in self._messages.values() if info.session_id == session_id
        ]

    def cleanup_old_messages(self, max_age_hours: int = 24) -> int:
        """
        Remove old message tracking data.

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of messages removed
        """
        now = _utc_now()
        old_messages = []

        for msg_id, info in self._messages.items():
            age = (now - info.sent_at).total_seconds() / 3600
            if age > max_age_hours:
                old_messages.append(msg_id)

        for msg_id in old_messages:
            del self._messages[msg_id]

        logger.info(f"Cleaned up {len(old_messages)} old messages")
        return len(old_messages)

    def get_stats(self) -> dict[str, Any]:
        """Get receipt statistics."""
        messages = list(self._messages.values())

        return {
            "total_tracked": len(messages),
            "total": len(messages),  # Alias for compatibility
            "sending": sum(1 for m in messages if m.status == MessageStatus.SENDING),
            "sent": sum(1 for m in messages if m.status == MessageStatus.SENT),
            "delivered": sum(
                1 for m in messages if m.status == MessageStatus.DELIVERED
            ),
            "read": sum(1 for m in messages if m.status == MessageStatus.READ),
            "failed": sum(1 for m in messages if m.status == MessageStatus.FAILED),
        }


class FirebaseReadReceipts(ReadReceiptManager):
    """
    Read receipt manager backed by Firebase.

    Syncs read status across all connected clients.

    Usage:
        receipts = FirebaseReadReceipts(
            database_url="https://project.firebaseio.com",
            credentials_path="service-account.json"
        )

        # Track and sync read status
        receipts.track_message("msg-1", "user-1", "session-1")
        await receipts.mark_read("msg-1", "user-2")
    """

    def __init__(
        self,
        database_url: Optional[str] = None,
        credentials_path: Optional[str] = None,
        receipts_path: str = "receipts",
    ):
        """
        Initialize Firebase-backed receipts.

        Args:
            database_url: Firebase Realtime Database URL
            credentials_path: Path to service account JSON
            receipts_path: Database path for receipts
        """
        super().__init__()

        self._database_url = database_url
        self._credentials_path = credentials_path
        self._receipts_path = receipts_path
        self._db = None
        self._initialized = False

        # Try to initialize Firebase
        try:
            import firebase_admin
            from firebase_admin import credentials, db

            if credentials_path:
                cred = credentials.Certificate(credentials_path)
                try:
                    firebase_admin.get_app("receipts")
                except ValueError:
                    firebase_admin.initialize_app(
                        cred, {"databaseURL": database_url}, name="receipts"
                    )

                self._db = db
                self._initialized = True
                logger.info("Firebase read receipts initialized")
        except ImportError:
            logger.warning("Firebase SDK not installed, using local receipts only")
        except Exception as e:
            logger.warning(f"Firebase initialization failed: {e}")

    @property
    def is_firebase_enabled(self) -> bool:
        """Check if Firebase backend is available."""
        return self._initialized and self._db is not None

    def track_message(
        self,
        message_id: str,
        sender_id: str,
        session_id: str,
    ) -> MessageReadInfo:
        """Track message (syncs to Firebase)."""
        info = super().track_message(message_id, sender_id, session_id)

        if self.is_firebase_enabled:
            try:
                ref = self._db.reference(
                    f"{self._receipts_path}/{session_id}/{message_id}"
                )
                ref.set(info.to_dict())
            except Exception as e:
                logger.error(f"Firebase receipt sync failed: {e}")

        return info

    async def mark_read(
        self, message_id: str, user_id: str
    ) -> Optional[MessageReadInfo]:
        """Mark as read (syncs to Firebase)."""
        info = await super().mark_read(message_id, user_id)

        if info and self.is_firebase_enabled:
            try:
                # Update read_by in Firebase
                ref = self._db.reference(
                    f"{self._receipts_path}/{info.session_id}/{message_id}/read_by/{user_id}"
                )
                ref.set(_utc_now().isoformat())

                # Update status
                status_ref = self._db.reference(
                    f"{self._receipts_path}/{info.session_id}/{message_id}/status"
                )
                status_ref.set("read")
            except Exception as e:
                logger.error(f"Firebase read sync failed: {e}")

        return info

    async def mark_delivered(self, message_id: str) -> Optional[MessageReadInfo]:
        """Mark as delivered (syncs to Firebase)."""
        info = await super().mark_delivered(message_id)

        if info and self.is_firebase_enabled:
            try:
                ref = self._db.reference(
                    f"{self._receipts_path}/{info.session_id}/{message_id}"
                )
                ref.update(
                    {
                        "status": "delivered",
                        "delivered_at": info.delivered_at.isoformat(),
                    }
                )
            except Exception as e:
                logger.error(f"Firebase delivery sync failed: {e}")

        return info
