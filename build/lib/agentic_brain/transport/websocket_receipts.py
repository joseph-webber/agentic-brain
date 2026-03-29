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
WebSocket Read Receipts - Message delivery/read tracking via WebSocket.

Mirrors the Firebase receipts API but syncs over WebSocket instead of Firebase.
Both can be used interchangeably through the same interface.
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import WebSocket

from .firebase_receipts import (
    MessageReadInfo,
    MessageStatus,
    ReadReceiptManager,
    _utc_now,
)

logger = logging.getLogger(__name__)


class WebSocketReadReceipts(ReadReceiptManager):
    """Read receipt manager that syncs over WebSocket.

    Inherits all local functionality from ReadReceiptManager,
    adds WebSocket broadcast for multi-client sync.

    Usage:
        receipts = WebSocketReadReceipts()

        # Add connected WebSockets
        receipts.add_connection("user1", websocket1)

        # Track message (broadcasts to recipients)
        await receipts.track_message(
            message_id="msg1",
            session_id="chat",
            sender_id="user1",
            recipient_ids=["user2", "user3"],
        )

        # Mark as read (broadcasts to sender)
        await receipts.mark_read("msg1", "user2")
    """

    def __init__(self, broadcast_changes: bool = True):
        """Initialize WebSocket receipts manager.

        Args:
            broadcast_changes: Broadcast changes to connected clients
        """
        super().__init__()

        self._broadcast_changes = broadcast_changes
        # Map user_id -> set of WebSocket connections
        self._connections: dict[str, set[WebSocket]] = {}
        # Map WebSocket -> user_id
        self._ws_to_user: dict[WebSocket, str] = {}
        # Lock for connection management
        self._conn_lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    async def add_connection(self, user_id: str, websocket: WebSocket) -> None:
        """Add a WebSocket connection for a user."""
        async with self._conn_lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
            self._ws_to_user[websocket] = user_id

        logger.debug(f"Added receipts connection for {user_id}")

    async def remove_connection(self, websocket: WebSocket) -> Optional[str]:
        """Remove a WebSocket connection."""
        async with self._conn_lock:
            user_id = self._ws_to_user.pop(websocket, None)
            if user_id and user_id in self._connections:
                self._connections[user_id].discard(websocket)
                if not self._connections[user_id]:
                    del self._connections[user_id]
        return user_id

    # -------------------------------------------------------------------------
    # Broadcast Helpers
    # -------------------------------------------------------------------------

    async def _send_to_user(
        self,
        user_id: str,
        message: dict[str, Any],
    ) -> int:
        """Send message to specific user's connections.

        Returns:
            Number of successful sends
        """
        if not self._broadcast_changes:
            return 0

        websockets = self._connections.get(user_id, set())
        if not websockets:
            return 0

        sent = 0
        failed: list[WebSocket] = []

        for ws in websockets:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception as e:
                logger.warning(f"Send to {user_id} failed: {e}")
                failed.append(ws)

        for ws in failed:
            await self.remove_connection(ws)

        return sent

    async def _send_to_users(
        self,
        user_ids: list[str],
        message: dict[str, Any],
    ) -> int:
        """Send message to multiple users."""
        total = 0
        for user_id in user_ids:
            total += await self._send_to_user(user_id, message)
        return total

    async def _broadcast_all(self, message: dict[str, Any]) -> int:
        """Broadcast to all connected users."""
        if not self._broadcast_changes:
            return 0

        sent = 0
        for user_id in list(self._connections.keys()):
            sent += await self._send_to_user(user_id, message)
        return sent

    # -------------------------------------------------------------------------
    # Override Receipt Methods to Add Broadcasting
    # -------------------------------------------------------------------------

    def track_message(
        self,
        message_id: str,
        sender_id: str,
        session_id: str,
    ) -> MessageReadInfo:
        """Track message - base class signature.

        Note: Use track_message_with_recipients() for WebSocket broadcasting.
        """
        return super().track_message(message_id, sender_id, session_id)

    async def track_message_with_recipients(
        self,
        message_id: str,
        sender_id: str,
        session_id: str,
        recipient_ids: list[str],
    ) -> MessageReadInfo:
        """Track message and notify recipients via WebSocket."""
        info = super().track_message(message_id, sender_id, session_id)

        if self._broadcast_changes:
            # Notify recipients about new message
            await self._send_to_users(
                recipient_ids,
                {
                    "type": "receipt",
                    "action": "new_message",
                    "message_id": message_id,
                    "session_id": session_id,
                    "sender_id": sender_id,
                    "status": info.status.value,
                },
            )

        return info

    async def mark_sent(self, message_id: str) -> Optional[MessageReadInfo]:
        """Mark message as sent and notify sender."""
        info = await super().mark_sent(message_id)

        if info and self._broadcast_changes:
            await self._send_to_user(
                info.sender_id,
                {
                    "type": "receipt",
                    "action": "status_change",
                    "message_id": message_id,
                    "status": MessageStatus.SENT.value,
                    "timestamp": _utc_now().isoformat(),
                },
            )

        return info

    async def mark_delivered(self, message_id: str) -> Optional[MessageReadInfo]:
        """Mark message as delivered and notify sender."""
        info = await super().mark_delivered(message_id)

        if info and self._broadcast_changes:
            await self._send_to_user(
                info.sender_id,
                {
                    "type": "receipt",
                    "action": "status_change",
                    "message_id": message_id,
                    "status": MessageStatus.DELIVERED.value,
                    "timestamp": _utc_now().isoformat(),
                },
            )

        return info

    async def mark_read(
        self,
        message_id: str,
        reader_id: str,
    ) -> Optional[MessageReadInfo]:
        """Mark message as read by user and notify sender."""
        info = await super().mark_read(message_id, reader_id)

        if info and self._broadcast_changes:
            # Notify sender that someone read their message
            await self._send_to_user(
                info.sender_id,
                {
                    "type": "receipt",
                    "action": "read",
                    "message_id": message_id,
                    "reader_id": reader_id,
                    "status": info.status.value,
                    "read_by": {k: v.isoformat() for k, v in info.read_by.items()},
                    "timestamp": _utc_now().isoformat(),
                },
            )

        return info

    async def mark_failed(
        self,
        message_id: str,
        error: Optional[str] = None,
    ) -> Optional[MessageReadInfo]:
        """Mark message as failed and notify sender."""
        info = await super().mark_failed(message_id, error)

        if info and self._broadcast_changes:
            await self._send_to_user(
                info.sender_id,
                {
                    "type": "receipt",
                    "action": "status_change",
                    "message_id": message_id,
                    "status": MessageStatus.FAILED.value,
                    "error": error,
                    "timestamp": _utc_now().isoformat(),
                },
            )

        return info

    async def mark_all_read(
        self,
        user_id: str,
        session_id: str,
    ) -> list[str]:
        """Mark all messages in session as read."""
        marked_ids = await super().mark_all_read(user_id, session_id)

        if marked_ids and self._broadcast_changes:
            # Notify senders of all marked messages
            for msg_id in marked_ids:
                info = self.get_message_info(msg_id)
                if info:
                    await self._send_to_user(
                        info.sender_id,
                        {
                            "type": "receipt",
                            "action": "read",
                            "message_id": msg_id,
                            "reader_id": user_id,
                            "status": info.status.value,
                        },
                    )

        return marked_ids

    # -------------------------------------------------------------------------
    # Handle Incoming Messages
    # -------------------------------------------------------------------------

    async def handle_message(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        """Handle incoming receipt message from client.

        Message format:
        {
            "type": "receipt",
            "action": "delivered" | "read" | "read_all",
            "message_id": "...",
            "session_id": "...",  # for read_all
        }
        """
        user_id = self._ws_to_user.get(websocket)
        if not user_id:
            logger.warning("Received receipt from unknown WebSocket")
            return

        action = message.get("action")
        message_id = message.get("message_id")

        if action == "delivered" and message_id:
            await self.mark_delivered(message_id)

        elif action == "read" and message_id:
            await self.mark_read(message_id, user_id)

        elif action == "read_all":
            session_id = message.get("session_id", "default")
            await self.mark_all_read(user_id, session_id)

    # -------------------------------------------------------------------------
    # Sync State
    # -------------------------------------------------------------------------

    async def send_unread_count(self, websocket: WebSocket, session_id: str) -> None:
        """Send unread count for a session to a client."""
        user_id = self._ws_to_user.get(websocket)
        if not user_id:
            return

        try:
            count = self.get_unread_count(user_id, session_id)
            await websocket.send_json(
                {
                    "type": "receipt_sync",
                    "action": "unread_count",
                    "session_id": session_id,
                    "count": count,
                }
            )
        except Exception as e:
            logger.error(f"Failed to send unread count: {e}")

    async def send_session_state(
        self,
        websocket: WebSocket,
        session_id: str,
    ) -> None:
        """Send receipt state for a session to client."""
        user_id = self._ws_to_user.get(websocket)
        if not user_id:
            return

        try:
            messages = self.get_session_messages(session_id)
            await websocket.send_json(
                {
                    "type": "receipt_sync",
                    "action": "session_state",
                    "session_id": session_id,
                    "messages": [
                        {
                            "message_id": m.message_id,
                            "status": m.status.value,
                            "sender_id": m.sender_id,
                            "read_by": {k: v.isoformat() for k, v in m.read_by.items()},
                        }
                        for m in messages
                    ],
                }
            )
        except Exception as e:
            logger.error(f"Failed to send session state: {e}")

    # -------------------------------------------------------------------------
    # Stats Override
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        """Get receipt stats including connection counts."""
        stats = super().get_stats()
        stats["connections"] = sum(len(conns) for conns in self._connections.values())
        stats["connected_users"] = len(self._connections)
        return stats
