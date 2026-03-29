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

from __future__ import annotations

"""Native WebSocket transport - fast, bidirectional with auto-reconnect and authentication."""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Callable, Optional

from fastapi import WebSocket, WebSocketDisconnect

from ..auth.providers import get_auth_provider
from ..exceptions import AuthenticationError
from .base import BaseTransport, TransportConfig, TransportMessage, TransportType

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """WebSocket connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


@dataclass
class ReconnectConfig:
    """Configuration for auto-reconnection behavior."""

    enabled: bool = True
    max_retries: int = 5
    base_delay: float = 1.0  # seconds
    max_delay: float = 30.0  # seconds
    backoff_factor: float = 2.0  # exponential backoff
    buffer_size: int = 100  # max messages to queue during reconnect


@dataclass
class WebSocketAuthConfig:
    """WebSocket authentication configuration."""

    require_auth: bool = True  # Require auth in production (False for dev)
    auth_timeout: float = 5.0  # Seconds to provide token after connect
    allow_anonymous: bool = False  # Allow unauthenticated connections (read-only)


class WebSocketTransport(BaseTransport):
    """FastAPI native WebSocket transport with authentication.

    Features:
    - Token-based authentication (JWT)
    - Bidirectional communication
    - Low latency (~10ms)
    - Automatic ping/pong keepalive
    - Auto-reconnect with exponential backoff
    - Message buffering during reconnection

    Security:
    - Validates JWT tokens via AuthProvider
    - Rejects unauthenticated connections (when require_auth=True)
    - Logs all auth attempts for auditing
    - Supports auth timeout to prevent hanging connections
    """

    def __init__(
        self,
        config: TransportConfig,
        websocket: Optional[WebSocket] = None,
        reconnect_config: Optional[ReconnectConfig] = None,
        auth_config: Optional[WebSocketAuthConfig] = None,
        on_state_change: Optional[Callable[[ConnectionState], None]] = None,
    ) -> None:
        super().__init__(config)
        self.websocket = websocket
        self._receive_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._closed = False
        self._intentional_close = False

        # Reconnection support
        self._reconnect_config = reconnect_config or ReconnectConfig()
        self._state = ConnectionState.DISCONNECTED
        self._on_state_change = on_state_change
        self._reconnect_task: Optional[asyncio.Task] = None
        self._retries = 0

        # Message buffer for reconnection
        self._message_buffer: deque[TransportMessage] = deque(
            maxlen=self._reconnect_config.buffer_size
        )
        self._buffer_lock = asyncio.Lock()

        # Authentication state
        self._auth_config = auth_config or WebSocketAuthConfig()
        self._authenticated = False
        self._user_id: Optional[str] = None

    @property
    def transport_type(self) -> TransportType:
        return TransportType.WEBSOCKET

    @property
    def state(self) -> ConnectionState:
        """Current connection state."""
        return self._state

    @property
    def is_authenticated(self) -> bool:
        """Check if the connection is authenticated."""
        return self._authenticated

    @property
    def user_id(self) -> Optional[str]:
        """Get the authenticated user ID."""
        return self._user_id

    def _set_state(self, new_state: ConnectionState) -> None:
        """Update state and notify callback if registered."""
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            logger.debug(f"Connection state: {old_state.value} -> {new_state.value}")
            if self._on_state_change:
                try:
                    self._on_state_change(new_state)
                except Exception as e:
                    logger.warning(f"State change callback error: {e}")

    async def _authenticate_connection(self, token: str | None) -> bool:
        """Authenticate WebSocket connection using JWT token.

        Args:
            token: JWT token from client (from query param or first message)

        Returns:
            True if authenticated successfully, False otherwise.

        Security:
            - Never logs the actual token
            - Uses AuthProvider for validation
            - Records auth attempts for auditing
        """
        if not token:
            logger.warning("WebSocket connection attempt without token")
            return False

        try:
            auth_provider = get_auth_provider()
            if auth_provider:
                # Validate the token
                user = await auth_provider.validate_token(token)
                if user:
                    self._authenticated = True
                    self._user_id = user.login
                    logger.info(f"WebSocket authenticated for user: {user.login}")
                    return True
                else:
                    logger.warning("WebSocket auth failed: invalid token")
                    return False
            else:
                # No auth provider configured - development mode
                if not self._auth_config.require_auth:
                    logger.info("WebSocket auth skipped (no provider, dev mode)")
                    self._authenticated = True
                    self._user_id = "anonymous"
                    return True
                else:
                    logger.warning(
                        "WebSocket auth failed: no provider configured but auth required"
                    )
                    return False
        except AuthenticationError as e:
            logger.warning(f"WebSocket auth failed: {e.message}")
            return False
        except Exception as e:
            logger.error(f"WebSocket auth error: {e}", exc_info=True)
            return False

    async def _wait_for_auth_token(self) -> Optional[str]:
        """Wait for authentication token from client.

        Expects first message to be: {"type": "auth", "token": "..."}

        Returns:
            The token string if received, None if timeout or invalid.
        """
        if not self.websocket:
            return None

        try:
            data = await asyncio.wait_for(
                self.websocket.receive_json(),
                timeout=self._auth_config.auth_timeout,
            )

            if data.get("type") == "auth" and "token" in data:
                return data["token"]
            else:
                logger.warning(
                    f"WebSocket auth: expected auth message, got type={data.get('type')}"
                )
                return None

        except TimeoutError:
            logger.warning(
                f"WebSocket auth timeout after {self._auth_config.auth_timeout}s"
            )
            return None
        except Exception as e:
            logger.error(f"WebSocket auth receive error: {e}")
            return None

    async def _send_auth_result(self, success: bool, message: str) -> None:
        """Send authentication result to client."""
        if not self.websocket:
            return
        try:
            await self.websocket.send_json(
                {
                    "type": "auth_result",
                    "success": success,
                    "message": message,
                    "user_id": self._user_id if success else None,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        except Exception as e:
            logger.warning(f"Failed to send auth result: {e}")

    async def connect(self, token: Optional[str] = None) -> bool:
        """Accept WebSocket connection with optional authentication.

        Args:
            token: Optional JWT token (e.g., from query parameter).
                   If not provided and auth is required, waits for auth message.

        Returns:
            True if connected and authenticated (or auth not required).

        Flow:
            1. Accept WebSocket connection
            2. If auth required: validate token or wait for auth message
            3. Send auth result to client
            4. Set connected state
        """
        if self.websocket is None:
            logger.error("No WebSocket provided")
            return False
        try:
            self._set_state(ConnectionState.CONNECTING)
            await self.websocket.accept()
            logger.debug("WebSocket connection accepted, checking auth...")

            # Handle authentication
            if self._auth_config.require_auth:
                # Try token from parameter first
                if not token:
                    # Wait for auth message from client
                    token = await self._wait_for_auth_token()

                # Authenticate
                if await self._authenticate_connection(token):
                    await self._send_auth_result(True, "Authenticated successfully")
                    logger.info(
                        f"WebSocket connected and authenticated: {self._user_id}"
                    )
                else:
                    # Auth failed - close connection
                    await self._send_auth_result(False, "Authentication failed")
                    await self.websocket.close(
                        code=4001, reason="Authentication failed"
                    )
                    self._set_state(ConnectionState.DISCONNECTED)
                    logger.warning("WebSocket connection rejected: auth failed")
                    return False
            else:
                # Dev mode - skip auth
                self._authenticated = True
                self._user_id = "anonymous"
                await self._send_auth_result(True, "Auth not required (dev mode)")
                logger.info("WebSocket connected (auth disabled)")

            self.connected = True
            self._intentional_close = False
            self._set_state(ConnectionState.CONNECTED)

            # Replay any buffered messages
            await self._replay_buffer()
            return True
        except Exception as e:
            logger.error(f"WebSocket connect failed: {e}")
            self._set_state(ConnectionState.DISCONNECTED)
            return False

    async def disconnect(self) -> None:
        """Close WebSocket gracefully."""
        self._closed = True
        self._intentional_close = True

        # Reset authentication state
        self._authenticated = False
        self._user_id = None

        # Cancel any reconnect attempts
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass

        if self.websocket and self.connected:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.warning(f"WebSocket close error: {e}")
        self.connected = False
        self._set_state(ConnectionState.DISCONNECTED)
        logger.info("WebSocket disconnected (intentional)")

    async def send(self, message: TransportMessage) -> bool:
        """Send message over WebSocket.

        If disconnected and reconnecting, buffers the message for later delivery.
        Requires authentication if auth is enabled.
        """
        # Check authentication
        if self._auth_config.require_auth and not self._authenticated:
            logger.warning("Attempted to send on unauthenticated WebSocket")
            return False

        # Buffer message if reconnecting
        if self._state == ConnectionState.RECONNECTING:
            async with self._buffer_lock:
                if len(self._message_buffer) < self._reconnect_config.buffer_size:
                    self._message_buffer.append(message)
                    logger.debug(
                        f"Buffered message during reconnect "
                        f"({len(self._message_buffer)}/{self._reconnect_config.buffer_size})"
                    )
                    return True
                else:
                    logger.warning("Message buffer full, dropping message")
                    return False

        if not self.connected or not self.websocket:
            return False

        try:
            data = {
                "content": message.content,
                "session_id": message.session_id,
                "message_id": message.message_id,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            }
            await self.websocket.send_json(data)
            return True
        except WebSocketDisconnect:
            self.connected = False
            await self._handle_unexpected_disconnect()
            return False
        except Exception as e:
            logger.error(f"WebSocket send error: {e}")
            await self._handle_unexpected_disconnect()
            return False

    async def receive(self) -> AsyncIterator[TransportMessage]:
        """Receive messages from WebSocket.

        Requires authentication if auth is enabled.
        Skips auth messages after initial authentication.
        """
        if not self.websocket:
            return

        # Check authentication
        if self._auth_config.require_auth and not self._authenticated:
            logger.warning("Attempted to receive on unauthenticated WebSocket")
            return

        while self.connected and not self._closed:
            try:
                data = await asyncio.wait_for(
                    self.websocket.receive_json(), timeout=self.config.timeout
                )

                # Skip auth messages after initial auth
                if data.get("type") == "auth":
                    logger.debug("Ignoring duplicate auth message")
                    continue

                yield TransportMessage(
                    content=data.get("content", ""),
                    session_id=data.get("session_id", ""),
                    message_id=data.get("message_id", ""),
                    timestamp=(
                        datetime.fromisoformat(data["timestamp"])
                        if "timestamp" in data
                        else datetime.now(UTC)
                    ),
                    metadata=data.get("metadata", {}),
                )
            except TimeoutError:
                continue  # Keep listening
            except WebSocketDisconnect:
                self.connected = False
                await self._handle_unexpected_disconnect()
                break
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                await self._handle_unexpected_disconnect()
                break

    async def is_healthy(self) -> bool:
        """Check WebSocket health via ping."""
        if not self.websocket or not self.connected:
            return False
        try:
            await self.websocket.send_json({"type": "ping"})
            return True
        except Exception:
            return False

    async def send_token(self, token: str, is_end: bool = False) -> bool:
        """Send a streaming token (convenience method).

        Requires authentication if auth is enabled.
        """
        if not self.connected or not self.websocket:
            return False
        if self._auth_config.require_auth and not self._authenticated:
            logger.warning("Attempted to send token on unauthenticated WebSocket")
            return False
        try:
            await self.websocket.send_json(
                {
                    "token": token,
                    "is_end": is_end,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            return True
        except Exception as e:
            logger.error(f"Token send error: {e}")
            await self._handle_unexpected_disconnect()
            return False

    async def _handle_unexpected_disconnect(self) -> None:
        """Handle unexpected disconnection - trigger reconnect if enabled."""
        if self._intentional_close:
            return

        if not self._reconnect_config.enabled:
            self._set_state(ConnectionState.DISCONNECTED)
            logger.info("Reconnection disabled, staying disconnected")
            return

        if self._state == ConnectionState.RECONNECTING:
            return  # Already reconnecting

        self._set_state(ConnectionState.RECONNECTING)
        logger.info("Unexpected disconnect - starting reconnection")

        # Launch reconnect as background task (non-blocking)
        self._reconnect_task = asyncio.create_task(self._reconnect_loop())

    async def _reconnect_loop(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        retries = 0
        delay = self._reconnect_config.base_delay

        while retries < self._reconnect_config.max_retries:
            retries += 1
            logger.info(
                f"Reconnection attempt {retries}/{self._reconnect_config.max_retries}"
            )

            try:
                # For server-side WebSocket, we can't reconnect ourselves
                # The client must reconnect. We signal readiness.
                # For client-side WebSocket, implement connection logic here.

                # Check if a new WebSocket was provided (client reconnected)
                if self.websocket is not None and not self._closed:
                    success = await self.connect()
                    if success:
                        logger.info("WebSocket reconnected successfully")
                        self._retries = 0
                        return

                # Wait before retry
                if retries < self._reconnect_config.max_retries:
                    logger.info(f"Waiting {delay:.1f}s before next attempt")
                    await asyncio.sleep(delay)
                    delay = min(
                        delay * self._reconnect_config.backoff_factor,
                        self._reconnect_config.max_delay,
                    )

            except asyncio.CancelledError:
                logger.info("Reconnection cancelled")
                raise
            except Exception as e:
                logger.warning(f"Reconnection attempt failed: {e}")

                if retries < self._reconnect_config.max_retries:
                    logger.info(f"Waiting {delay:.1f}s before next attempt")
                    await asyncio.sleep(delay)
                    delay = min(
                        delay * self._reconnect_config.backoff_factor,
                        self._reconnect_config.max_delay,
                    )

        logger.error(f"Failed to reconnect after {retries} attempts")
        self._set_state(ConnectionState.DISCONNECTED)

    async def _replay_buffer(self) -> None:
        """Replay buffered messages after successful reconnection."""
        async with self._buffer_lock:
            if not self._message_buffer:
                return

            buffer_size = len(self._message_buffer)
            logger.info(f"Replaying {buffer_size} buffered messages")

            sent = 0
            while self._message_buffer:
                message = self._message_buffer.popleft()
                try:
                    if self.connected and self.websocket:
                        data = {
                            "content": message.content,
                            "session_id": message.session_id,
                            "message_id": message.message_id,
                            "timestamp": message.timestamp.isoformat(),
                            "metadata": message.metadata,
                        }
                        await self.websocket.send_json(data)
                        sent += 1
                except Exception as e:
                    logger.warning(f"Failed to replay message: {e}")
                    # Put it back for next attempt
                    self._message_buffer.appendleft(message)
                    break

            logger.info(f"Replayed {sent}/{buffer_size} buffered messages")

    def set_websocket(self, websocket: WebSocket) -> None:
        """Update the WebSocket instance (for reconnection scenarios)."""
        self.websocket = websocket
        self._closed = False

    def get_buffer_size(self) -> int:
        """Return current message buffer size."""
        return len(self._message_buffer)

    def clear_buffer(self) -> int:
        """Clear the message buffer, returns count of cleared messages."""
        count = len(self._message_buffer)
        self._message_buffer.clear()
        return count
