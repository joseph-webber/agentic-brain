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

"""Firebase Realtime Database transport - scalable, persistent, cross-device sync.

Production-ready Firebase transport with:
- Real-time message streaming via listeners
- Session state sync across devices
- Offline support with local persistence queue
- Automatic reconnection handling
- Connection state monitoring
"""

import asyncio
import contextlib
import json
import logging
import os
import sqlite3
import threading
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from .base import BaseTransport, TransportConfig, TransportMessage, TransportType

logger = logging.getLogger(__name__)

# Firebase is optional - graceful fallback if not installed
try:
    import firebase_admin
    from firebase_admin import credentials, db

    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False
    firebase_admin = None  # type: ignore
    credentials = None  # type: ignore
    db = None  # type: ignore


class ConnectionState(Enum):
    """Firebase connection states."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class FirebaseStats:
    """Statistics for Firebase transport."""

    messages_sent: int = 0
    messages_received: int = 0
    reconnection_count: int = 0
    last_connected_at: Optional[datetime] = None
    last_disconnected_at: Optional[datetime] = None
    offline_queue_size: int = 0
    total_bytes_sent: int = 0


@dataclass
class OfflineMessage:
    """Message queued for offline send."""

    id: str
    message: TransportMessage
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    retry_count: int = 0


class OfflineQueue:
    """SQLite-backed offline message queue for persistence.

    Survives app restarts and syncs when connection is restored.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / ".agentic_brain" / "firebase_offline.db"
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS offline_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    retry_count INTEGER DEFAULT 0
                )
            """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_id
                ON offline_messages(session_id)
            """
            )
            conn.commit()
            conn.close()

    def enqueue(self, message: TransportMessage) -> str:
        """Add message to offline queue. Returns queue entry ID."""
        entry_id = str(uuid.uuid4())
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                """
                INSERT INTO offline_messages
                (id, session_id, message_id, content, timestamp, metadata, created_at, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
                (
                    entry_id,
                    message.session_id,
                    message.message_id,
                    message.content,
                    message.timestamp.isoformat(),
                    json.dumps(message.metadata),
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        logger.debug(f"Queued offline message: {entry_id}")
        return entry_id

    def dequeue(self, entry_id: str) -> None:
        """Remove message from queue after successful send."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("DELETE FROM offline_messages WHERE id = ?", (entry_id,))
            conn.commit()
            conn.close()
        logger.debug(f"Dequeued offline message: {entry_id}")

    def increment_retry(self, entry_id: str) -> None:
        """Increment retry count for a message."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute(
                "UPDATE offline_messages SET retry_count = retry_count + 1 WHERE id = ?",
                (entry_id,),
            )
            conn.commit()
            conn.close()

    def get_pending(
        self, session_id: Optional[str] = None, limit: int = 100
    ) -> list[OfflineMessage]:
        """Get pending messages, optionally filtered by session."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            if session_id:
                cursor = conn.execute(
                    """
                    SELECT id, session_id, message_id, content, timestamp, metadata, created_at, retry_count
                    FROM offline_messages WHERE session_id = ?
                    ORDER BY created_at ASC LIMIT ?
                """,
                    (session_id, limit),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, session_id, message_id, content, timestamp, metadata, created_at, retry_count
                    FROM offline_messages ORDER BY created_at ASC LIMIT ?
                """,
                    (limit,),
                )

            messages = []
            for row in cursor.fetchall():
                msg = TransportMessage(
                    content=row[3],
                    session_id=row[1],
                    message_id=row[2],
                    timestamp=datetime.fromisoformat(row[4]),
                    metadata=json.loads(row[5]),
                )
                messages.append(
                    OfflineMessage(
                        id=row[0],
                        message=msg,
                        created_at=datetime.fromisoformat(row[6]),
                        retry_count=row[7],
                    )
                )
            conn.close()
            return messages

    def size(self, session_id: Optional[str] = None) -> int:
        """Get count of pending messages."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            if session_id:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM offline_messages WHERE session_id = ?",
                    (session_id,),
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM offline_messages")
            count = cursor.fetchone()[0]
            conn.close()
            return count

    def clear(self, session_id: Optional[str] = None) -> int:
        """Clear all pending messages. Returns count cleared."""
        with self._lock:
            conn = sqlite3.connect(str(self.db_path))
            if session_id:
                cursor = conn.execute(
                    "DELETE FROM offline_messages WHERE session_id = ?", (session_id,)
                )
            else:
                cursor = conn.execute("DELETE FROM offline_messages")
            count = cursor.rowcount
            conn.commit()
            conn.close()
            return count


class FirebaseTransport(BaseTransport):
    """Firebase Realtime Database transport.

    Production-ready transport with:
    - Persistent message storage
    - Cross-device synchronization
    - Offline support with SQLite persistence
    - Automatic reconnection with backoff
    - Connection state monitoring
    - Message history retrieval
    - Session state sync

    Usage:
    ```python
    from agentic_brain.transport import FirebaseTransport, TransportConfig

    config = TransportConfig(
        firebase_url="https://my-project.firebaseio.com",
        firebase_credentials="/path/to/service-account.json",
    )

    transport = FirebaseTransport(config, session_id="my-session")
    await transport.connect()

    # Send message (syncs to all connected clients)
    await transport.send(message)

    # Listen for responses
    async for response in transport.listen():
        print(response)
    ```

    Requires:
    - pip install firebase-admin
    - Firebase project with Realtime Database enabled
    - Service account credentials JSON file
    """

    # Maximum retries for offline messages before discarding
    MAX_OFFLINE_RETRIES = 5
    # Reconnection backoff settings
    MIN_RECONNECT_DELAY = 1.0
    MAX_RECONNECT_DELAY = 60.0
    RECONNECT_BACKOFF_FACTOR = 2.0

    def __init__(
        self,
        config: TransportConfig,
        session_id: Optional[str] = None,
        *,
        offline_db_path: Optional[Path] = None,
        enable_offline: bool = True,
        auto_reconnect: bool = True,
        sync_state: bool = True,
    ) -> None:
        """Initialize Firebase transport.

        Args:
            config: Transport configuration with Firebase settings
            session_id: Unique session identifier (auto-generated if None)
            offline_db_path: Custom path for offline queue database
            enable_offline: Enable offline message queueing
            auto_reconnect: Automatically reconnect on disconnection
            sync_state: Sync session state to Firebase
        """
        super().__init__(config)
        self.session_id = session_id or str(uuid.uuid4())
        self._app: Optional[Any] = None
        self._ref: Optional[Any] = None
        self._state_ref: Optional[Any] = None
        self._listener: Optional[Any] = None
        self._state_listener: Optional[Any] = None
        self._message_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._state_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._closed = False
        self._connection_state = ConnectionState.DISCONNECTED
        self._stats = FirebaseStats()

        # Offline support
        self._enable_offline = enable_offline
        self._offline_queue: Optional[OfflineQueue] = None
        if enable_offline:
            self._offline_queue = OfflineQueue(offline_db_path)

        # Reconnection
        self._auto_reconnect = auto_reconnect
        self._reconnect_task: Optional[asyncio.Task] = None
        self._current_reconnect_delay = self.MIN_RECONNECT_DELAY

        # Session state sync
        self._sync_state = sync_state
        self._session_state: dict[str, Any] = {}

        # Connection callbacks
        self._on_connect_callbacks: list[Callable[[], None]] = []
        self._on_disconnect_callbacks: list[Callable[[], None]] = []
        self._on_state_change_callbacks: list[Callable[[dict[str, Any]], None]] = []

    @property
    def transport_type(self) -> TransportType:
        return TransportType.FIREBASE

    @property
    def connection_state(self) -> ConnectionState:
        """Get current connection state."""
        return self._connection_state

    @property
    def stats(self) -> FirebaseStats:
        """Get transport statistics."""
        if self._offline_queue:
            self._stats.offline_queue_size = self._offline_queue.size(self.session_id)
        return self._stats

    @property
    def session_state(self) -> dict[str, Any]:
        """Get current session state."""
        return self._session_state.copy()

    @classmethod
    def is_available(cls) -> bool:
        """Check if Firebase SDK is installed."""
        return FIREBASE_AVAILABLE

    def on_connect(self, callback: Callable[[], None]) -> None:
        """Register callback for connection events."""
        self._on_connect_callbacks.append(callback)

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        """Register callback for disconnection events."""
        self._on_disconnect_callbacks.append(callback)

    def on_state_change(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register callback for session state changes."""
        self._on_state_change_callbacks.append(callback)

    async def connect(self) -> bool:
        """Initialize Firebase connection.

        Returns:
            True if connection successful, False otherwise.
        """
        if not FIREBASE_AVAILABLE:
            logger.error("Firebase SDK not installed. Run: pip install firebase-admin")
            self._connection_state = ConnectionState.ERROR
            return False

        self._connection_state = ConnectionState.CONNECTING

        try:
            # Get credentials from config or environment
            cred_path = (
                self.config.firebase_credentials
                or os.getenv("FIREBASE_CREDENTIALS_FILE")
                or os.getenv("FIREBASE_CREDENTIALS")
            )
            if not cred_path:
                logger.error("Firebase credentials not configured")
                self._connection_state = ConnectionState.ERROR
                return False

            # Get database URL
            database_url = self.config.firebase_url or os.getenv(
                "FIREBASE_DATABASE_URL"
            )
            if not database_url:
                logger.error("Firebase database URL not configured")
                self._connection_state = ConnectionState.ERROR
                return False

            # Initialize Firebase app (only once globally)
            if not firebase_admin._apps:
                cred = credentials.Certificate(cred_path)
                self._app = firebase_admin.initialize_app(
                    cred, {"databaseURL": database_url}
                )
                logger.info(f"Firebase app initialized: {database_url}")
            else:
                self._app = firebase_admin.get_app()

            # Get reference to session messages
            self._ref = db.reference(f"sessions/{self.session_id}/messages")

            # Get reference to session state
            if self._sync_state:
                self._state_ref = db.reference(f"sessions/{self.session_id}/state")

            # Set up message listener
            self._setup_message_listener()

            # Set up state listener
            if self._sync_state:
                self._setup_state_listener()

            self._connection_state = ConnectionState.CONNECTED
            self.connected = True
            self._stats.last_connected_at = datetime.now(UTC)
            self._current_reconnect_delay = self.MIN_RECONNECT_DELAY

            logger.info(f"Firebase connected: session={self.session_id}")

            # Fire connect callbacks
            for callback in self._on_connect_callbacks:
                try:
                    callback()
                except Exception as e:
                    logger.warning(f"Connect callback error: {e}")

            # Sync offline queue
            if self._enable_offline and self._offline_queue:
                await self._sync_offline_queue()

            return True

        except Exception as e:
            logger.error(f"Firebase connect failed: {e}")
            self._connection_state = ConnectionState.ERROR

            if self._auto_reconnect:
                self._schedule_reconnect()

            return False

    def _setup_message_listener(self) -> None:
        """Set up Firebase listener for incoming messages."""

        def on_message(event: Any) -> None:
            if event.data and not self._closed:
                try:
                    # Handle both single messages and batches
                    if isinstance(event.data, dict):
                        # Check if it's a nested dict (batch) or single message
                        if "content" in event.data:
                            # Single message
                            asyncio.get_event_loop().call_soon_threadsafe(
                                self._message_queue.put_nowait, event.data
                            )
                        else:
                            # Batch - extract individual messages
                            for _key, msg_data in event.data.items():
                                if isinstance(msg_data, dict) and "content" in msg_data:
                                    asyncio.get_event_loop().call_soon_threadsafe(
                                        self._message_queue.put_nowait, msg_data
                                    )
                except RuntimeError:
                    # Event loop not running - happens during shutdown
                    pass
                except Exception as e:
                    logger.error(f"Firebase listener error: {e}")

        self._listener = self._ref.listen(on_message)

    def _setup_state_listener(self) -> None:
        """Set up Firebase listener for session state changes."""

        def on_state_change(event: Any) -> None:
            if event.data and not self._closed:
                try:
                    self._session_state = (
                        event.data if isinstance(event.data, dict) else {}
                    )
                    asyncio.get_event_loop().call_soon_threadsafe(
                        self._state_queue.put_nowait, self._session_state
                    )
                    # Fire state change callbacks
                    for callback in self._on_state_change_callbacks:
                        try:
                            callback(self._session_state)
                        except Exception as e:
                            logger.warning(f"State change callback error: {e}")
                except RuntimeError:
                    pass
                except Exception as e:
                    logger.error(f"Firebase state listener error: {e}")

        if self._state_ref:
            self._state_listener = self._state_ref.listen(on_state_change)

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt."""
        if self._reconnect_task and not self._reconnect_task.done():
            return  # Already scheduled

        async def reconnect() -> None:
            self._connection_state = ConnectionState.RECONNECTING
            logger.info(f"Reconnecting in {self._current_reconnect_delay}s...")
            await asyncio.sleep(self._current_reconnect_delay)

            # Exponential backoff
            self._current_reconnect_delay = min(
                self._current_reconnect_delay * self.RECONNECT_BACKOFF_FACTOR,
                self.MAX_RECONNECT_DELAY,
            )

            self._stats.reconnection_count += 1
            success = await self.connect()
            if not success and self._auto_reconnect and not self._closed:
                self._schedule_reconnect()

        try:
            loop = asyncio.get_event_loop()
            self._reconnect_task = loop.create_task(reconnect())
        except RuntimeError:
            pass  # No event loop

    async def _sync_offline_queue(self) -> None:
        """Send all queued offline messages."""
        if not self._offline_queue:
            return

        pending = self._offline_queue.get_pending(self.session_id)
        if not pending:
            return

        logger.info(f"Syncing {len(pending)} offline messages...")

        for offline_msg in pending:
            if offline_msg.retry_count >= self.MAX_OFFLINE_RETRIES:
                logger.warning(
                    f"Discarding message after {self.MAX_OFFLINE_RETRIES} retries: {offline_msg.id}"
                )
                self._offline_queue.dequeue(offline_msg.id)
                continue

            try:
                success = await self._send_to_firebase(offline_msg.message)
                if success:
                    self._offline_queue.dequeue(offline_msg.id)
                else:
                    self._offline_queue.increment_retry(offline_msg.id)
            except Exception as e:
                logger.error(f"Offline sync error: {e}")
                self._offline_queue.increment_retry(offline_msg.id)

    async def disconnect(self) -> None:
        """Close Firebase connection gracefully."""
        self._closed = True

        # Cancel reconnection task
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reconnect_task

        # Close listeners
        if self._listener:
            try:
                self._listener.close()
            except Exception as e:
                logger.warning(f"Firebase listener close error: {e}")

        if self._state_listener:
            try:
                self._state_listener.close()
            except Exception as e:
                logger.warning(f"Firebase state listener close error: {e}")

        self._connection_state = ConnectionState.DISCONNECTED
        self.connected = False
        self._stats.last_disconnected_at = datetime.now(UTC)

        logger.info("Firebase disconnected")

        # Fire disconnect callbacks
        for callback in self._on_disconnect_callbacks:
            try:
                callback()
            except Exception as e:
                logger.warning(f"Disconnect callback error: {e}")

    async def send(self, message: TransportMessage) -> bool:
        """Send message to Firebase.

        If offline, queues message for later sync.

        Args:
            message: Message to send

        Returns:
            True if sent (or queued), False on failure.
        """
        if self._closed:
            return False

        # If not connected, queue for offline
        if not self.connected or not self._ref:
            if self._enable_offline and self._offline_queue:
                self._offline_queue.enqueue(message)
                logger.debug(f"Message queued offline: {message.message_id}")
                return True
            return False

        return await self._send_to_firebase(message)

    async def _send_to_firebase(self, message: TransportMessage) -> bool:
        """Send message directly to Firebase."""
        try:
            data = {
                "content": message.content,
                "session_id": message.session_id,
                "message_id": message.message_id,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
            }

            # Push creates unique key
            self._ref.push(data)

            self._stats.messages_sent += 1
            self._stats.total_bytes_sent += len(json.dumps(data))

            logger.debug(f"Message sent to Firebase: {message.message_id}")
            return True

        except Exception as e:
            logger.error(f"Firebase send error: {e}")

            # Queue for retry if offline enabled
            if self._enable_offline and self._offline_queue:
                self._offline_queue.enqueue(message)

            # Trigger reconnection if needed
            if self._auto_reconnect:
                self.connected = False
                self._schedule_reconnect()

            return False

    async def receive(self) -> AsyncIterator[TransportMessage]:
        """Receive messages from Firebase listener.

        Yields messages as they arrive from Firebase.
        Uses the configured timeout for blocking.

        Yields:
            TransportMessage objects from Firebase.
        """
        while self.connected and not self._closed:
            try:
                data = await asyncio.wait_for(
                    self._message_queue.get(), timeout=self.config.timeout
                )
                if isinstance(data, dict):
                    self._stats.messages_received += 1
                    yield TransportMessage(
                        content=data.get("content", ""),
                        session_id=data.get("session_id", self.session_id),
                        message_id=data.get("message_id", ""),
                        timestamp=(
                            datetime.fromisoformat(data["timestamp"])
                            if "timestamp" in data
                            else datetime.now(UTC)
                        ),
                        metadata=data.get("metadata", {}),
                    )
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Firebase receive error: {e}")
                break

    async def listen(self) -> AsyncIterator[TransportMessage]:
        """Alias for receive() - more intuitive name."""
        async for message in self.receive():
            yield message

    async def receive_state_changes(self) -> AsyncIterator[dict[str, Any]]:
        """Receive session state changes.

        Yields:
            Session state dictionaries when changes occur.
        """
        while self.connected and not self._closed and self._sync_state:
            try:
                state = await asyncio.wait_for(
                    self._state_queue.get(), timeout=self.config.timeout
                )
                yield state
            except TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Firebase state receive error: {e}")
                break

    async def update_state(self, updates: dict[str, Any]) -> bool:
        """Update session state in Firebase.

        Args:
            updates: Dictionary of state updates (merged with existing)

        Returns:
            True if update successful.
        """
        if not self._sync_state or not self._state_ref:
            return False

        try:
            self._state_ref.update(updates)
            self._session_state.update(updates)
            logger.debug(f"Session state updated: {list(updates.keys())}")
            return True
        except Exception as e:
            logger.error(f"Session state update error: {e}")
            return False

    async def set_state(self, state: dict[str, Any]) -> bool:
        """Replace entire session state.

        Args:
            state: Complete state dictionary

        Returns:
            True if set successful.
        """
        if not self._sync_state or not self._state_ref:
            return False

        try:
            self._state_ref.set(state)
            self._session_state = state.copy()
            logger.debug("Session state replaced")
            return True
        except Exception as e:
            logger.error(f"Session state set error: {e}")
            return False

    async def is_healthy(self) -> bool:
        """Check Firebase connection health.

        Performs a simple write to verify connection.
        """
        if not self.connected or not self._ref:
            return False
        try:
            # Write to health node
            health_ref = self._ref.parent.child("_health")
            health_ref.set(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "session_id": self.session_id,
                }
            )
            return True
        except Exception:
            return False

    async def get_history(self, limit: int = 50) -> list[TransportMessage]:
        """Get message history from Firebase.

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages, ordered by timestamp (oldest first).
        """
        if not self._ref:
            return []
        try:
            snapshot = self._ref.order_by_child("timestamp").limit_to_last(limit).get()
            messages = []
            if snapshot:
                for key, data in snapshot.items():
                    if isinstance(data, dict):
                        messages.append(
                            TransportMessage(
                                content=data.get("content", ""),
                                session_id=data.get("session_id", self.session_id),
                                message_id=data.get("message_id", key),
                                timestamp=(
                                    datetime.fromisoformat(data["timestamp"])
                                    if "timestamp" in data
                                    else datetime.now(UTC)
                                ),
                                metadata=data.get("metadata", {}),
                            )
                        )
            return messages
        except Exception as e:
            logger.error(f"Firebase history error: {e}")
            return []

    async def delete_message(self, message_id: str) -> bool:
        """Delete a specific message by ID.

        Args:
            message_id: The message_id to delete

        Returns:
            True if deleted, False otherwise.
        """
        if not self._ref:
            return False
        try:
            # Find and delete by message_id
            snapshot = self._ref.order_by_child("message_id").equal_to(message_id).get()
            if snapshot:
                for key in snapshot:
                    self._ref.child(key).delete()
                    logger.debug(f"Deleted message: {message_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Firebase delete error: {e}")
            return False

    async def clear_session(self) -> bool:
        """Clear all messages in the current session.

        Returns:
            True if cleared successfully.
        """
        if not self._ref:
            return False
        try:
            self._ref.delete()
            logger.info(f"Cleared session: {self.session_id}")
            return True
        except Exception as e:
            logger.error(f"Firebase clear error: {e}")
            return False

    def clear_offline_queue(self) -> int:
        """Clear the offline message queue.

        Returns:
            Number of messages cleared.
        """
        if not self._offline_queue:
            return 0
        return self._offline_queue.clear(self.session_id)

    async def __aenter__(self) -> "FirebaseTransport":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.disconnect()
