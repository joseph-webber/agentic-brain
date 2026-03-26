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
Unified Chat Features - Transport-agnostic presence and receipts.

Provides a single interface for presence and read receipts that works
with any transport backend (WebSocket, Firebase, or local-only).

Usage:
    from agentic_brain.transport import ChatFeatures, TransportType

    # WebSocket-backed
    features = ChatFeatures(transport_type=TransportType.WEBSOCKET)

    # Firebase-backed
    features = ChatFeatures(
        transport_type=TransportType.FIREBASE,
        firebase_ref=db.reference("chat"),
    )

    # Local-only (no sync, for testing)
    features = ChatFeatures(transport_type=None)

    # Use the same API regardless of backend
    await features.set_online("user1")
    await features.start_typing("user1", "chat-room")
    await features.track_message("msg1", "chat-room", "user1", ["user2"])
"""

import logging
from typing import Any, Optional

from fastapi import WebSocket

from .base import TransportType
from .firebase_presence import (
    PresenceManager,
    TypingIndicator,
    UserPresence,
)
from .firebase_receipts import (
    MessageReadInfo,
    ReadReceiptManager,
)

logger = logging.getLogger(__name__)


class ChatFeatures:
    """Unified interface for chat features (presence + receipts).

    Works with any backend:
    - WebSocket: Real-time sync over WebSocket connections
    - Firebase: Cloud sync via Firebase Realtime Database
    - Local: In-memory only, no sync (great for testing)

    The API is identical regardless of backend, making it easy to
    switch transports without changing application code.
    """

    def __init__(
        self,
        transport_type: Optional[TransportType] = None,
        # Firebase options
        firebase_ref: Optional[Any] = None,
        # Common options
        away_timeout: float = 300.0,
        offline_timeout: float = 600.0,
        typing_timeout: float = 5.0,
    ):
        """Initialize chat features.

        Args:
            transport_type: WEBSOCKET, FIREBASE, or None for local-only
            firebase_ref: Firebase database reference (for Firebase mode)
            away_timeout: Auto-away timeout
            offline_timeout: Auto-offline timeout
            typing_timeout: Typing indicator expiry
        """
        self._transport_type = transport_type
        self._firebase_ref = firebase_ref

        # Initialize appropriate backends
        if transport_type == TransportType.WEBSOCKET:
            from .websocket_presence import WebSocketPresence
            from .websocket_receipts import WebSocketReadReceipts

            self._presence = WebSocketPresence(
                away_timeout=away_timeout,
                offline_timeout=offline_timeout,
                typing_timeout=typing_timeout,
            )
            self._receipts = WebSocketReadReceipts()

        elif transport_type == TransportType.FIREBASE:
            from .firebase_presence import FirebasePresence
            from .firebase_receipts import FirebaseReadReceipts

            presence_ref = firebase_ref.child("presence") if firebase_ref else None
            receipts_ref = firebase_ref.child("receipts") if firebase_ref else None

            self._presence = FirebasePresence(
                presence_ref,
                away_timeout=away_timeout,
                offline_timeout=offline_timeout,
                typing_timeout=typing_timeout,
                local_only=(firebase_ref is None),
            )
            self._receipts = FirebaseReadReceipts(
                receipts_ref,
                local_only=(firebase_ref is None),
            )

        else:
            # Local-only mode
            self._presence = PresenceManager(
                away_timeout=away_timeout,
                offline_timeout=offline_timeout,
                typing_timeout=typing_timeout,
            )
            self._receipts = ReadReceiptManager()

        logger.info(
            f"ChatFeatures initialized with {transport_type or 'local'} backend"
        )

    @property
    def presence(self) -> PresenceManager:
        """Get the presence manager instance."""
        return self._presence

    @property
    def receipts(self) -> ReadReceiptManager:
        """Get the receipts manager instance."""
        return self._receipts

    @property
    def transport_type(self) -> Optional[TransportType]:
        """Get the transport type."""
        return self._transport_type

    # -------------------------------------------------------------------------
    # Connection Management (WebSocket mode only)
    # -------------------------------------------------------------------------

    async def add_connection(
        self,
        user_id: str,
        websocket: WebSocket,
        auto_online: bool = True,
    ) -> None:
        """Add a WebSocket connection for a user.

        Only works in WebSocket mode. In Firebase mode, connections
        are managed by Firebase SDK.
        """
        if self._transport_type != TransportType.WEBSOCKET:
            logger.warning("add_connection only works in WebSocket mode")
            return

        await self._presence.add_connection(user_id, websocket, auto_online)
        await self._receipts.add_connection(user_id, websocket)

    async def remove_connection(
        self,
        websocket: WebSocket,
        auto_offline: bool = True,
    ) -> Optional[str]:
        """Remove a WebSocket connection.

        Returns the user_id that was disconnected.
        """
        if self._transport_type != TransportType.WEBSOCKET:
            return None

        await self._receipts.remove_connection(websocket)
        return await self._presence.remove_connection(websocket, auto_offline)

    # -------------------------------------------------------------------------
    # Presence API (delegated)
    # -------------------------------------------------------------------------

    async def set_online(
        self,
        user_id: str,
        device_id: Optional[str] = None,
        custom_status: Optional[str] = None,
    ) -> UserPresence:
        """Set user online."""
        return await self._presence.set_online(user_id, device_id, custom_status)

    async def set_away(self, user_id: str) -> Optional[UserPresence]:
        """Set user away."""
        return await self._presence.set_away(user_id)

    async def set_busy(
        self,
        user_id: str,
        custom_status: Optional[str] = None,
    ) -> Optional[UserPresence]:
        """Set user busy."""
        return await self._presence.set_busy(user_id, custom_status)

    async def set_offline(self, user_id: str) -> Optional[UserPresence]:
        """Set user offline."""
        return await self._presence.set_offline(user_id)

    async def heartbeat(self, user_id: str) -> Optional[UserPresence]:
        """Update user's last active time."""
        return await self._presence.heartbeat(user_id)

    def get_presence(self, user_id: str) -> Optional[UserPresence]:
        """Get user's presence info."""
        return self._presence.get_presence(user_id)

    def get_online_users(self) -> list[UserPresence]:
        """Get all online users."""
        return self._presence.get_online_users()

    def is_online(self, user_id: str) -> bool:
        """Check if user is online."""
        return self._presence.is_online(user_id)

    # -------------------------------------------------------------------------
    # Typing API (delegated)
    # -------------------------------------------------------------------------

    async def start_typing(
        self,
        user_id: str,
        session_id: str,
    ) -> TypingIndicator:
        """Start typing indicator."""
        return await self._presence.start_typing(user_id, session_id)

    async def stop_typing(
        self,
        user_id: str,
        session_id: str,
    ) -> Optional[TypingIndicator]:
        """Stop typing indicator."""
        return await self._presence.stop_typing(user_id, session_id)

    def get_typing_users(self, session_id: str) -> list[TypingIndicator]:
        """Get who's typing in a session."""
        return self._presence.get_typing_users(session_id)

    def is_typing(self, user_id: str, session_id: str) -> bool:
        """Check if user is typing."""
        return self._presence.is_typing(user_id, session_id)

    # -------------------------------------------------------------------------
    # Receipts API (delegated)
    # -------------------------------------------------------------------------

    async def track_message(
        self,
        message_id: str,
        sender_id: str,
        session_id: str,
        recipient_ids: Optional[list[str]] = None,
    ) -> MessageReadInfo:
        """Start tracking a message.

        For WebSocket mode with recipients, broadcasts to recipients.
        For local/Firebase mode, recipients are ignored.
        """
        # Check if we're using WebSocket with recipients
        if self._transport_type == TransportType.WEBSOCKET and recipient_ids:
            from .websocket_receipts import WebSocketReadReceipts

            if isinstance(self._receipts, WebSocketReadReceipts):
                return await self._receipts.track_message_with_recipients(
                    message_id, sender_id, session_id, recipient_ids
                )

        # Base case - just call track_message
        return self._receipts.track_message(message_id, sender_id, session_id)

    async def mark_sent(self, message_id: str) -> Optional[MessageReadInfo]:
        """Mark message as sent."""
        return await self._receipts.mark_sent(message_id)

    async def mark_delivered(self, message_id: str) -> Optional[MessageReadInfo]:
        """Mark message as delivered."""
        return await self._receipts.mark_delivered(message_id)

    async def mark_read(
        self,
        message_id: str,
        reader_id: str,
    ) -> Optional[MessageReadInfo]:
        """Mark message as read by user."""
        return await self._receipts.mark_read(message_id, reader_id)

    async def mark_failed(
        self,
        message_id: str,
        error: Optional[str] = None,
    ) -> Optional[MessageReadInfo]:
        """Mark message as failed."""
        return await self._receipts.mark_failed(message_id, error)

    def get_message_info(self, message_id: str) -> Optional[MessageReadInfo]:
        """Get message info."""
        return self._receipts.get_message_info(message_id)

    def get_unread_count(self, user_id: str, session_id: str) -> int:
        """Get unread message count for user in session."""
        return self._receipts.get_unread_count(user_id, session_id)

    def get_unread_messages(
        self, user_id: str, session_id: str
    ) -> list[MessageReadInfo]:
        """Get unread messages for user in session."""
        return self._receipts.get_unread_messages(user_id, session_id)

    async def mark_all_read(
        self,
        user_id: str,
        session_id: str,
    ) -> list[str]:
        """Mark all messages in session as read."""
        return await self._receipts.mark_all_read(user_id, session_id)

    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------

    def on_presence_change(self, callback) -> None:
        """Register callback for presence changes."""
        self._presence.on_presence_change(callback)

    def on_typing_change(self, callback) -> None:
        """Register callback for typing changes."""
        self._presence.on_typing_change(callback)

    def on_status_change(self, callback) -> None:
        """Register callback for message status changes."""
        self._receipts.on_status_change(callback)

    def on_read(self, callback) -> None:
        """Register callback for message reads."""
        self._receipts.on_read(callback)

    # -------------------------------------------------------------------------
    # Stats
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get combined stats."""
        return {
            "transport": (
                self._transport_type.value if self._transport_type else "local"
            ),
            "presence": self._presence.get_stats(),
            "receipts": self._receipts.get_stats(),
        }

    # -------------------------------------------------------------------------
    # Handle Incoming Messages (WebSocket mode)
    # -------------------------------------------------------------------------

    async def handle_message(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        """Handle incoming WebSocket message for presence/receipts.

        Routes to appropriate handler based on message type.
        """
        if self._transport_type != TransportType.WEBSOCKET:
            return

        msg_type = message.get("type")

        if msg_type == "presence" or msg_type == "typing":
            await self._presence.handle_message(websocket, message)
        elif msg_type == "receipt":
            await self._receipts.handle_message(websocket, message)

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        """Start background tasks."""
        await self._presence.start()

    async def stop(self) -> None:
        """Stop background tasks."""
        await self._presence.stop()

    async def __aenter__(self) -> "ChatFeatures":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.stop()
