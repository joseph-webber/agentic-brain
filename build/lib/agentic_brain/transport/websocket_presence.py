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
WebSocket Presence System - Real-time online/offline/typing via WebSocket.

Mirrors the Firebase presence API but syncs over WebSocket instead of Firebase.
Both can be used interchangeably through the same interface.
"""

import asyncio
import logging
from typing import Any, Optional

from fastapi import WebSocket

from .firebase_presence import (
    PresenceManager,
    TypingIndicator,
    UserPresence,
)

logger = logging.getLogger(__name__)


class WebSocketPresence(PresenceManager):
    """Presence manager that syncs over WebSocket.

    Inherits all local functionality from PresenceManager,
    adds WebSocket broadcast for multi-client sync.

    Usage:
        presence = WebSocketPresence()

        # Add connected WebSockets
        presence.add_connection("user1", websocket1)
        presence.add_connection("user2", websocket2)

        # Set presence (broadcasts to all connected clients)
        await presence.set_online("user1")

        # Typing indicators
        await presence.start_typing("user1", "chat-room")
    """

    def __init__(
        self,
        away_timeout: float = 300.0,
        offline_timeout: float = 600.0,
        typing_timeout: float = 5.0,
        broadcast_changes: bool = True,
    ):
        """Initialize WebSocket presence manager.

        Args:
            away_timeout: Seconds before auto-away
            offline_timeout: Seconds before auto-offline
            typing_timeout: Seconds before typing indicator expires
            broadcast_changes: Broadcast changes to all connected clients
        """
        super().__init__(
            away_timeout=away_timeout,
            offline_timeout=offline_timeout,
            typing_timeout=typing_timeout,
        )

        self._broadcast_changes = broadcast_changes
        # Map user_id -> set of WebSocket connections (multi-device)
        self._connections: dict[str, set[WebSocket]] = {}
        # Map WebSocket -> user_id for reverse lookup
        self._ws_to_user: dict[WebSocket, str] = {}
        # Lock for connection management
        self._conn_lock = asyncio.Lock()

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------

    async def add_connection(
        self,
        user_id: str,
        websocket: WebSocket,
        auto_online: bool = True,
    ) -> None:
        """Add a WebSocket connection for a user.

        Args:
            user_id: User identifier
            websocket: FastAPI WebSocket connection
            auto_online: Automatically set user online
        """
        async with self._conn_lock:
            if user_id not in self._connections:
                self._connections[user_id] = set()
            self._connections[user_id].add(websocket)
            self._ws_to_user[websocket] = user_id

        if auto_online:
            await self.set_online(user_id)

        logger.debug(f"Added WebSocket connection for {user_id}")

    async def remove_connection(
        self,
        websocket: WebSocket,
        auto_offline: bool = True,
    ) -> Optional[str]:
        """Remove a WebSocket connection.

        Args:
            websocket: WebSocket to remove
            auto_offline: Set user offline if no more connections

        Returns:
            User ID that was disconnected, or None
        """
        async with self._conn_lock:
            user_id = self._ws_to_user.pop(websocket, None)
            if user_id and user_id in self._connections:
                self._connections[user_id].discard(websocket)

                # If no more connections, optionally set offline
                if auto_offline and not self._connections[user_id]:
                    del self._connections[user_id]
                    await self.set_offline(user_id)
                    logger.debug(f"User {user_id} went offline (no connections)")

        return user_id

    def get_connected_users(self) -> list[str]:
        """Get list of users with active WebSocket connections."""
        return [uid for uid, conns in self._connections.items() if conns]

    def connection_count(self, user_id: str) -> int:
        """Get number of active connections for a user."""
        return len(self._connections.get(user_id, set()))

    # -------------------------------------------------------------------------
    # Broadcast Helpers
    # -------------------------------------------------------------------------

    async def _broadcast_all(self, message: dict[str, Any]) -> int:
        """Broadcast message to ALL connected clients.

        Returns:
            Number of successful sends
        """
        if not self._broadcast_changes:
            return 0

        sent = 0
        failed_ws: list[WebSocket] = []

        for user_id, websockets in self._connections.items():
            for ws in websockets:
                try:
                    await ws.send_json(message)
                    sent += 1
                except Exception as e:
                    logger.warning(f"Broadcast to {user_id} failed: {e}")
                    failed_ws.append(ws)

        # Clean up failed connections
        for ws in failed_ws:
            await self.remove_connection(ws, auto_offline=True)

        return sent

    async def _broadcast_to_session(
        self,
        session_id: str,
        message: dict[str, Any],
        exclude_user: Optional[str] = None,
    ) -> int:
        """Broadcast message to users in a session.

        For now, broadcasts to all (session membership would need separate tracking).
        """
        return await self._broadcast_all(message)

    # -------------------------------------------------------------------------
    # Override Presence Methods to Add Broadcasting
    # -------------------------------------------------------------------------

    async def set_online(
        self,
        user_id: str,
        device_id: Optional[str] = None,
        custom_status: Optional[str] = None,
    ) -> UserPresence:
        """Set user online and broadcast to all clients."""
        presence = await super().set_online(user_id, device_id, custom_status)

        if presence and self._broadcast_changes:
            await self._broadcast_all(
                {
                    "type": "presence",
                    "action": "online",
                    "user_id": user_id,
                    "presence": presence.to_dict(),
                }
            )

        return presence

    async def set_away(self, user_id: str) -> Optional[UserPresence]:
        """Set user away and broadcast."""
        presence = await super().set_away(user_id)

        if presence and self._broadcast_changes:
            await self._broadcast_all(
                {
                    "type": "presence",
                    "action": "away",
                    "user_id": user_id,
                    "presence": presence.to_dict(),
                }
            )

        return presence

    async def set_busy(
        self,
        user_id: str,
        custom_status: Optional[str] = None,
    ) -> Optional[UserPresence]:
        """Set user busy and broadcast."""
        presence = await super().set_busy(user_id, custom_status)

        if presence and self._broadcast_changes:
            await self._broadcast_all(
                {
                    "type": "presence",
                    "action": "busy",
                    "user_id": user_id,
                    "presence": presence.to_dict(),
                }
            )

        return presence

    async def set_offline(self, user_id: str) -> Optional[UserPresence]:
        """Set user offline and broadcast."""
        presence = await super().set_offline(user_id)

        if presence and self._broadcast_changes:
            await self._broadcast_all(
                {
                    "type": "presence",
                    "action": "offline",
                    "user_id": user_id,
                    "presence": presence.to_dict(),
                }
            )

        return presence

    # -------------------------------------------------------------------------
    # Override Typing Methods to Add Broadcasting
    # -------------------------------------------------------------------------

    async def start_typing(
        self,
        user_id: str,
        session_id: str,
    ) -> TypingIndicator:
        """Start typing and broadcast to session."""
        indicator = await super().start_typing(user_id, session_id)

        if self._broadcast_changes:
            await self._broadcast_all(
                {
                    "type": "typing",
                    "action": "start",
                    "user_id": user_id,
                    "session_id": session_id,
                    "indicator": indicator.to_dict(),
                }
            )

        return indicator

    async def stop_typing(
        self,
        user_id: str,
        session_id: str,
    ) -> Optional[TypingIndicator]:
        """Stop typing and broadcast to session."""
        indicator = await super().stop_typing(user_id, session_id)

        if self._broadcast_changes:
            await self._broadcast_all(
                {
                    "type": "typing",
                    "action": "stop",
                    "user_id": user_id,
                    "session_id": session_id,
                }
            )

        return indicator

    # -------------------------------------------------------------------------
    # Handle Incoming Messages
    # -------------------------------------------------------------------------

    async def handle_message(
        self,
        websocket: WebSocket,
        message: dict[str, Any],
    ) -> None:
        """Handle incoming presence/typing message from client.

        Message format:
        {
            "type": "presence" | "typing",
            "action": "online" | "away" | "busy" | "offline" | "start" | "stop",
            "session_id": "...",  # for typing
            "custom_status": "...",  # optional
        }
        """
        user_id = self._ws_to_user.get(websocket)
        if not user_id:
            logger.warning("Received message from unknown WebSocket")
            return

        msg_type = message.get("type")
        action = message.get("action")

        if msg_type == "presence":
            if action == "online":
                await self.set_online(
                    user_id,
                    custom_status=message.get("custom_status"),
                )
            elif action == "away":
                await self.set_away(user_id)
            elif action == "busy":
                await self.set_busy(
                    user_id,
                    custom_status=message.get("custom_status"),
                )
            elif action == "offline":
                await self.set_offline(user_id)
            elif action == "heartbeat":
                await self.heartbeat(user_id)

        elif msg_type == "typing":
            session_id = message.get("session_id", "default")
            if action == "start":
                await self.start_typing(user_id, session_id)
            elif action == "stop":
                await self.stop_typing(user_id, session_id)

    # -------------------------------------------------------------------------
    # Sync State
    # -------------------------------------------------------------------------

    async def send_full_state(self, websocket: WebSocket) -> None:
        """Send full presence state to a newly connected client."""
        try:
            # Send all online users
            all_presence = self.get_all_presence()  # Returns List[UserPresence]
            await websocket.send_json(
                {
                    "type": "presence_sync",
                    "users": {p.user_id: p.to_dict() for p in all_presence},
                }
            )

            # Send active typing indicators
            typing_by_session: dict[str, list[dict]] = {}
            for indicator in self._typing.values():
                sid = indicator.session_id
                if sid not in typing_by_session:
                    typing_by_session[sid] = []
                typing_by_session[sid].append(indicator.to_dict())

            if typing_by_session:
                await websocket.send_json(
                    {
                        "type": "typing_sync",
                        "sessions": typing_by_session,
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send state sync: {e}")

    # -------------------------------------------------------------------------
    # Stats Override
    # -------------------------------------------------------------------------

    def get_stats(self) -> dict[str, int]:
        """Get presence stats including connection counts."""
        stats = super().get_stats()
        stats["connections"] = sum(len(conns) for conns in self._connections.values())
        stats["connected_users"] = len(self.get_connected_users())
        return stats
