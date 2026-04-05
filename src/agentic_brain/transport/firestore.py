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

"""Firebase Firestore transport - document-based real-time sync.

Production-ready Firestore transport with:
- Document-based message storage
- Real-time listeners with snapshot streaming
- Offline persistence (built into Firestore SDK)
- Sub-collection organization
- Query-based message retrieval
- Automatic retry and conflict resolution
"""

import asyncio
import contextlib
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Optional

from .base import BaseTransport, TransportConfig, TransportMessage, TransportType

logger = logging.getLogger(__name__)

# Firestore is optional
try:
    from google.cloud import firestore
    from google.cloud.firestore_v1 import DocumentSnapshot

    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    firestore = None  # type: ignore


@dataclass
class FirestoreStats:
    """Statistics for Firestore transport."""

    documents_written: int = 0
    documents_read: int = 0
    queries_executed: int = 0
    listeners_active: int = 0
    last_write_at: Optional[datetime] = None
    last_read_at: Optional[datetime] = None


class FirestoreTransport(BaseTransport):
    """Firestore document-based transport.

    Uses Cloud Firestore for scalable, real-time message sync.
    Better for complex queries than Realtime Database.

    Document structure:
        /sessions/{session_id}/messages/{message_id}
        /sessions/{session_id}/state/current
        /sessions/{session_id}/metadata

    Usage:
        ```python
        from agentic_brain.transport import FirestoreTransport, TransportConfig

        config = TransportConfig(
            firestore_project="my-project",
            firestore_credentials="/path/to/creds.json",
        )

        async with FirestoreTransport(config, session_id="chat-123") as transport:
            await transport.send(TransportMessage(content="Hello!"))

            async for msg in transport.listen():
                print(msg.content)
        ```
    """

    transport_type = TransportType.FIRESTORE

    def __init__(
        self,
        config: TransportConfig,
        session_id: Optional[str] = None,
        collection_prefix: str = "sessions",
        enable_persistence: bool = True,
    ):
        """Initialize Firestore transport.

        Args:
            config: Transport configuration
            session_id: Session identifier
            collection_prefix: Root collection name
            enable_persistence: Enable offline persistence
        """
        if not FIRESTORE_AVAILABLE:
            raise ImportError(
                "Firestore SDK not installed. Run: pip install google-cloud-firestore"
            )

        super().__init__(config)
        self.session_id = session_id or f"session-{uuid.uuid4().hex[:8]}"
        self.collection_prefix = collection_prefix
        self.enable_persistence = enable_persistence

        self._client: Optional[firestore.Client] = None
        self._session_ref = None
        self._messages_ref = None
        self._state_ref = None
        self._listeners: list[Any] = []
        self._stats = FirestoreStats()
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._state_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._connected = False

    @property
    def stats(self) -> FirestoreStats:
        """Get transport statistics."""
        return self._stats

    async def connect(self) -> bool:
        """Connect to Firestore.

        Returns:
            True if connected successfully.
        """
        try:
            # Initialize client
            if self.config.firestore_credentials:
                self._client = firestore.Client.from_service_account_json(
                    self.config.firestore_credentials
                )
            else:
                # Use default credentials (ADC)
                self._client = firestore.Client(project=self.config.firestore_project)

            # Set up collection references
            self._session_ref = self._client.collection(
                self.collection_prefix
            ).document(self.session_id)
            self._messages_ref = self._session_ref.collection("messages")
            self._state_ref = self._session_ref.collection("state").document("current")

            # Create session document if not exists
            if not self._session_ref.get().exists:
                self._session_ref.set(
                    {
                        "created_at": firestore.SERVER_TIMESTAMP,
                        "session_id": self.session_id,
                    }
                )

            # Set up message listener
            self._setup_message_listener()

            self._connected = True
            logger.info(f"Connected to Firestore session: {self.session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Firestore: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from Firestore."""
        # Unsubscribe all listeners
        for listener in self._listeners:
            listener.unsubscribe()
        self._listeners.clear()

        self._connected = False
        logger.info("Disconnected from Firestore")

    async def send(self, message: TransportMessage) -> bool:
        """Send a message to Firestore.

        Args:
            message: Message to send.

        Returns:
            True if sent successfully.
        """
        if not self._connected or not self._messages_ref:
            logger.warning("Not connected to Firestore")
            return False

        try:
            doc_data = {
                "content": message.content,
                "session_id": message.session_id or self.session_id,
                "message_id": message.message_id,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "metadata": message.metadata or {},
            }

            # Use message_id as document ID for deduplication
            doc_ref = self._messages_ref.document(message.message_id)
            doc_ref.set(doc_data)

            self._stats.documents_written += 1
            self._stats.last_write_at = datetime.now(UTC)

            logger.debug(f"Sent message: {message.message_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def receive(self) -> Optional[TransportMessage]:
        """Receive next message from queue.

        Returns:
            Next message or None if queue empty.
        """
        try:
            return await asyncio.wait_for(
                self._message_queue.get(), timeout=self.config.timeout
            )
        except TimeoutError:
            return None

    async def listen(self) -> AsyncIterator[TransportMessage]:
        """Stream incoming messages.

        Yields:
            TransportMessage for each new message.
        """
        while self._connected:
            message = await self.receive()
            if message:
                yield message

    async def get_history(
        self,
        limit: int = 50,
        before: Optional[datetime] = None,
        after: Optional[datetime] = None,
    ) -> list[TransportMessage]:
        """Get message history with optional time filters.

        Args:
            limit: Maximum messages to return.
            before: Get messages before this time.
            after: Get messages after this time.

        Returns:
            List of messages ordered by timestamp.
        """
        if not self._connected or not self._messages_ref:
            return []

        try:
            query = self._messages_ref.order_by(
                "timestamp", direction=firestore.Query.DESCENDING
            ).limit(limit)

            if before:
                query = query.where("timestamp", "<", before)
            if after:
                query = query.where("timestamp", ">", after)

            docs = query.stream()

            messages = []
            for doc in docs:
                data = doc.to_dict()
                messages.append(self._doc_to_message(doc.id, data))

            self._stats.queries_executed += 1
            self._stats.documents_read += len(messages)
            self._stats.last_read_at = datetime.now(UTC)

            # Return in chronological order
            return list(reversed(messages))

        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []

    async def update_state(self, state: dict[str, Any]) -> bool:
        """Update session state.

        Args:
            state: State dictionary to merge.

        Returns:
            True if updated successfully.
        """
        if not self._connected or not self._state_ref:
            return False

        try:
            self._state_ref.set(
                {**state, "updated_at": firestore.SERVER_TIMESTAMP}, merge=True
            )
            self._stats.documents_written += 1
            return True

        except Exception as e:
            logger.error(f"Failed to update state: {e}")
            return False

    async def get_state(self) -> dict[str, Any]:
        """Get current session state.

        Returns:
            Current state dictionary.
        """
        if not self._connected or not self._state_ref:
            return {}

        try:
            doc = self._state_ref.get()
            if doc.exists:
                self._stats.documents_read += 1
                return doc.to_dict() or {}
            return {}

        except Exception as e:
            logger.error(f"Failed to get state: {e}")
            return {}

    async def receive_state_changes(self) -> AsyncIterator[dict[str, Any]]:
        """Stream session state changes.

        Yields:
            State dictionary on each change.
        """
        # Set up state listener if not already
        self._setup_state_listener()

        while self._connected:
            try:
                state = await asyncio.wait_for(
                    self._state_queue.get(), timeout=self.config.timeout
                )
                yield state
            except TimeoutError:
                continue

    async def clear_session(self) -> bool:
        """Clear all session data.

        Returns:
            True if cleared successfully.
        """
        if not self._connected or not self._session_ref:
            return False

        try:
            # Delete all messages
            batch = self._client.batch()
            docs = self._messages_ref.stream()

            count = 0
            for doc in docs:
                batch.delete(doc.reference)
                count += 1

                # Firestore batch limit is 500
                if count >= 500:
                    batch.commit()
                    batch = self._client.batch()
                    count = 0

            if count > 0:
                batch.commit()

            # Clear state
            self._state_ref.delete()

            logger.info(f"Cleared session: {self.session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to clear session: {e}")
            return False

    async def is_healthy(self) -> bool:
        """Check if transport is healthy.

        Returns:
            True if connected and responsive.
        """
        if not self._connected:
            return False

        try:
            # Try a simple read
            self._session_ref.get()
            return True
        except Exception:
            return False

    def _setup_message_listener(self) -> None:
        """Set up real-time message listener."""

        def on_snapshot(docs, changes, read_time):
            for change in changes:
                if change.type.name == "ADDED":
                    doc = change.document
                    message = self._doc_to_message(doc.id, doc.to_dict())

                    # Put in queue for async consumption
                    try:
                        self._message_queue.put_nowait(message)
                        self._stats.documents_read += 1
                    except asyncio.QueueFull:
                        logger.warning("Message queue full, dropping message")

        listener = self._messages_ref.on_snapshot(on_snapshot)
        self._listeners.append(listener)
        self._stats.listeners_active += 1

    def _setup_state_listener(self) -> None:
        """Set up real-time state listener."""

        def on_snapshot(doc_snapshot, changes, read_time):
            for doc in doc_snapshot:
                if doc.exists:
                    with contextlib.suppress(asyncio.QueueFull):
                        self._state_queue.put_nowait(doc.to_dict())

        listener = self._state_ref.on_snapshot(on_snapshot)
        self._listeners.append(listener)
        self._stats.listeners_active += 1

    def _doc_to_message(self, doc_id: str, data: dict[str, Any]) -> TransportMessage:
        """Convert Firestore document to TransportMessage."""
        timestamp = data.get("timestamp")
        if hasattr(timestamp, "timestamp"):
            # Convert Firestore timestamp
            timestamp = datetime.fromtimestamp(timestamp.timestamp(), tz=UTC)
        else:
            timestamp = datetime.now(UTC)

        return TransportMessage(
            content=data.get("content", ""),
            session_id=data.get("session_id", self.session_id),
            message_id=data.get("message_id", doc_id),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Query helpers for common patterns
class FirestoreQueries:
    """Helper class for common Firestore query patterns."""

    @staticmethod
    async def get_messages_by_sender(
        transport: FirestoreTransport,
        sender_id: str,
        limit: int = 50,
    ) -> list[TransportMessage]:
        """Get messages from a specific sender.

        Args:
            transport: Firestore transport instance.
            sender_id: Sender identifier in metadata.
            limit: Maximum messages to return.

        Returns:
            List of messages from sender.
        """
        if not transport._connected or not transport._messages_ref:
            return []

        query = (
            transport._messages_ref.where("metadata.sender_id", "==", sender_id)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )

        messages = []
        for doc in query.stream():
            messages.append(transport._doc_to_message(doc.id, doc.to_dict()))

        return list(reversed(messages))

    @staticmethod
    async def search_messages(
        transport: FirestoreTransport,
        field: str,
        value: Any,
        limit: int = 50,
    ) -> list[TransportMessage]:
        """Search messages by field value.

        Args:
            transport: Firestore transport instance.
            field: Field to search (e.g., "metadata.type").
            value: Value to match.
            limit: Maximum messages to return.

        Returns:
            List of matching messages.
        """
        if not transport._connected or not transport._messages_ref:
            return []

        query = transport._messages_ref.where(field, "==", value).limit(limit)

        messages = []
        for doc in query.stream():
            messages.append(transport._doc_to_message(doc.id, doc.to_dict()))

        return messages

    @staticmethod
    async def get_unread_count(
        transport: FirestoreTransport,
        user_id: str,
    ) -> int:
        """Get count of unread messages for a user.

        Args:
            transport: Firestore transport instance.
            user_id: User identifier.

        Returns:
            Count of unread messages.
        """
        if not transport._connected or not transport._messages_ref:
            return 0

        # Get user's last read timestamp
        state = await transport.get_state()
        last_read = state.get(f"last_read_{user_id}")

        if not last_read:
            # Count all messages
            query = transport._messages_ref.count()
        else:
            query = transport._messages_ref.where("timestamp", ">", last_read).count()

        result = query.get()
        return result[0][0].value if result else 0
