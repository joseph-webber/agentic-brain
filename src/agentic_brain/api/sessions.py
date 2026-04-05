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
Session backend abstraction for the Agentic Brain API.

Provides pluggable session storage with in-memory (default) and Redis backends.
The backend is selected via the SESSION_BACKEND environment variable.
"""

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Session:
    """Represents a chat session.

    Attributes:
        id: Unique session identifier
        user_id: Optional user identifier for multi-user support
        created_at: When the session was created
        updated_at: When the session was last accessed/modified
        message_count: Number of messages in the session
        metadata: Additional session metadata
    """

    id: str
    user_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    metadata: Optional[dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert session to dictionary for serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "message_count": self.message_count,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Session":
        """Create session from dictionary."""
        return cls(
            id=data["id"],
            user_id=data.get("user_id"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data["created_at"], str)
                else data["created_at"]
            ),
            updated_at=(
                datetime.fromisoformat(data["updated_at"])
                if isinstance(data["updated_at"], str)
                else data["updated_at"]
            ),
            message_count=data.get("message_count", 0),
            metadata=data.get("metadata", {}),
        )


class SessionBackend(ABC):
    """Abstract base class for session storage backends.

    Implementations must provide async methods for CRUD operations
    on sessions and their associated messages.
    """

    @abstractmethod
    async def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID.

        Args:
            session_id: The session identifier

        Returns:
            Session if found, None otherwise
        """
        ...

    @abstractmethod
    async def create(self, session_id: str, user_id: Optional[str] = None) -> Session:
        """Create a new session.

        Args:
            session_id: The session identifier
            user_id: Optional user identifier

        Returns:
            The created Session
        """
        ...

    @abstractmethod
    async def update(self, session_id: str, **kwargs) -> Session:
        """Update a session's attributes.

        Args:
            session_id: The session identifier
            **kwargs: Attributes to update (message_count, metadata, etc.)

        Returns:
            The updated Session

        Raises:
            KeyError: If session not found
        """
        ...

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """Delete a session and its messages.

        Args:
            session_id: The session identifier

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def list_all(self) -> list[Session]:
        """List all active sessions.

        Returns:
            List of all sessions
        """
        ...

    @abstractmethod
    async def cleanup_expired(self, max_age_seconds: int) -> int:
        """Remove sessions older than max_age_seconds.

        Args:
            max_age_seconds: Maximum session age in seconds

        Returns:
            Number of sessions removed
        """
        ...

    @abstractmethod
    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of messages
        """
        ...

    @abstractmethod
    async def add_message(self, session_id: str, message: dict[str, Any]) -> None:
        """Add a message to a session.

        Args:
            session_id: The session identifier
            message: The message to add
        """
        ...

    @abstractmethod
    async def clear_all(self) -> int:
        """Clear all sessions and messages.

        Returns:
            Number of sessions cleared
        """
        ...

    async def ensure_exists(
        self, session_id: str, user_id: Optional[str] = None
    ) -> Session:
        """Ensure a session exists, creating it if necessary.

        Args:
            session_id: The session identifier
            user_id: Optional user identifier

        Returns:
            The existing or newly created Session
        """
        session = await self.get(session_id)
        if session is None:
            session = await self.create(session_id, user_id)
            logger.info(f"Created new session: {session_id}")
        else:
            # Update last accessed time
            session = await self.update(session_id)
        return session


class InMemorySessionBackend(SessionBackend):
    """In-memory session storage for development and testing.

    This backend stores all data in Python dictionaries. Data is lost
    when the process exits. Suitable for development, testing, and
    single-instance deployments that don't require persistence.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {}

    async def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    async def create(self, session_id: str, user_id: Optional[str] = None) -> Session:
        now = datetime.now(UTC)
        session = Session(
            id=session_id,
            user_id=user_id,
            created_at=now,
            updated_at=now,
            message_count=0,
            metadata={},
        )
        self._sessions[session_id] = session
        self._messages[session_id] = []
        return session

    async def update(self, session_id: str, **kwargs) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")

        session.updated_at = datetime.now(UTC)

        if "message_count" in kwargs:
            session.message_count = kwargs["message_count"]
        if "metadata" in kwargs:
            session.metadata = kwargs["metadata"]
        if "increment_messages" in kwargs and kwargs["increment_messages"]:
            session.message_count += 1

        return session

    async def delete(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        self._messages.pop(session_id, None)
        return True

    async def list_all(self) -> list[Session]:
        return list(self._sessions.values())

    async def cleanup_expired(self, max_age_seconds: int) -> int:
        now = datetime.now(UTC)
        expired = []

        for session_id, session in self._sessions.items():
            age = (now - session.created_at).total_seconds()
            if age > max_age_seconds:
                expired.append(session_id)

        for session_id in expired:
            await self.delete(session_id)

        return len(expired)

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        return self._messages.get(session_id, [])

    async def add_message(self, session_id: str, message: dict[str, Any]) -> None:
        if session_id not in self._messages:
            self._messages[session_id] = []
        self._messages[session_id].append(message)

    async def clear_all(self) -> int:
        count = len(self._sessions)
        self._sessions.clear()
        self._messages.clear()
        return count


class RedisSessionBackend(SessionBackend):
    """Redis-backed session storage for production deployments.

    This backend stores sessions in Redis, providing persistence,
    horizontal scalability, and automatic expiration. Requires
    redis-py[asyncio] to be installed.

    Environment Variables:
        REDIS_URL: Redis connection URL (default: redis://localhost:6379)
        SESSION_MAX_AGE: Session TTL in seconds (default: 3600)
    """

    SESSION_PREFIX = "session:"
    MESSAGES_PREFIX = "session_messages:"
    ALL_SESSIONS_KEY = "sessions:all"

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._client = None
        self._ttl = int(os.getenv("SESSION_MAX_AGE", "3600"))

    async def connect(self) -> None:
        """Establish connection to Redis.

        Must be called before using the backend.
        """
        if self._client is not None:
            return

        try:
            import redis.asyncio as redis
        except ImportError:
            raise ImportError(
                "redis package not installed. Install with: pip install redis"
            )

        self._client = redis.from_url(
            self.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        # Test connection
        await self._client.ping()
        logger.info(f"Connected to Redis at {self.redis_url}")

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _session_key(self, session_id: str) -> str:
        return f"{self.SESSION_PREFIX}{session_id}"

    def _messages_key(self, session_id: str) -> str:
        return f"{self.MESSAGES_PREFIX}{session_id}"

    async def _ensure_connected(self) -> None:
        if self._client is None:
            await self.connect()

    async def get(self, session_id: str) -> Optional[Session]:
        await self._ensure_connected()

        data = await self._client.get(self._session_key(session_id))
        if data is None:
            return None

        return Session.from_dict(json.loads(data))

    async def create(self, session_id: str, user_id: Optional[str] = None) -> Session:
        await self._ensure_connected()

        now = datetime.now(UTC)
        session = Session(
            id=session_id,
            user_id=user_id,
            created_at=now,
            updated_at=now,
            message_count=0,
            metadata={},
        )

        # Store session with TTL
        await self._client.set(
            self._session_key(session_id),
            json.dumps(session.to_dict()),
            ex=self._ttl,
        )

        # Track session ID in set
        await self._client.sadd(self.ALL_SESSIONS_KEY, session_id)

        # Initialize empty message list
        await self._client.delete(self._messages_key(session_id))

        return session

    async def update(self, session_id: str, **kwargs) -> Session:
        await self._ensure_connected()

        session = await self.get(session_id)
        if session is None:
            raise KeyError(f"Session {session_id} not found")

        session.updated_at = datetime.now(UTC)

        if "message_count" in kwargs:
            session.message_count = kwargs["message_count"]
        if "metadata" in kwargs:
            session.metadata = kwargs["metadata"]
        if "increment_messages" in kwargs and kwargs["increment_messages"]:
            session.message_count += 1

        # Update with refreshed TTL
        await self._client.set(
            self._session_key(session_id),
            json.dumps(session.to_dict()),
            ex=self._ttl,
        )

        return session

    async def delete(self, session_id: str) -> bool:
        await self._ensure_connected()

        session_key = self._session_key(session_id)
        messages_key = self._messages_key(session_id)

        # Check if exists
        exists = await self._client.exists(session_key)
        if not exists:
            return False

        # Delete session and messages
        await self._client.delete(session_key, messages_key)
        await self._client.srem(self.ALL_SESSIONS_KEY, session_id)

        return True

    async def list_all(self) -> list[Session]:
        await self._ensure_connected()

        session_ids = await self._client.smembers(self.ALL_SESSIONS_KEY)
        sessions = []

        for session_id in session_ids:
            session = await self.get(session_id)
            if session is not None:
                sessions.append(session)
            else:
                # Clean up stale reference
                await self._client.srem(self.ALL_SESSIONS_KEY, session_id)

        return sessions

    async def cleanup_expired(self, max_age_seconds: int) -> int:
        """Clean up expired sessions.

        Note: Redis TTL handles expiration automatically, but this method
        is useful for cleaning up the session ID tracking set and for
        explicit cleanup with different age thresholds.
        """
        await self._ensure_connected()

        now = datetime.now(UTC)
        session_ids = await self._client.smembers(self.ALL_SESSIONS_KEY)
        expired_count = 0

        for session_id in session_ids:
            session = await self.get(session_id)
            if session is None:
                # Already expired by TTL
                await self._client.srem(self.ALL_SESSIONS_KEY, session_id)
                expired_count += 1
            elif (now - session.created_at).total_seconds() > max_age_seconds:
                await self.delete(session_id)
                expired_count += 1

        return expired_count

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        await self._ensure_connected()

        messages = await self._client.lrange(self._messages_key(session_id), 0, -1)
        return [json.loads(msg) for msg in messages]

    async def add_message(self, session_id: str, message: dict[str, Any]) -> None:
        await self._ensure_connected()

        messages_key = self._messages_key(session_id)
        await self._client.rpush(messages_key, json.dumps(message))

        # Set TTL on messages list to match session
        await self._client.expire(messages_key, self._ttl)

    async def clear_all(self) -> int:
        await self._ensure_connected()

        session_ids = await self._client.smembers(self.ALL_SESSIONS_KEY)
        count = len(session_ids)

        # Delete all session keys
        for session_id in session_ids:
            await self._client.delete(
                self._session_key(session_id),
                self._messages_key(session_id),
            )

        # Clear the tracking set
        await self._client.delete(self.ALL_SESSIONS_KEY)

        return count


# Global backend instance (lazy-initialized)
_backend_instance: Optional[SessionBackend] = None


def get_session_backend() -> SessionBackend:
    """Get the configured session backend.

    The backend type is determined by the SESSION_BACKEND environment variable:
    - "memory" (default): In-memory storage
    - "redis": Redis-backed storage

    Returns:
        SessionBackend instance

    Environment Variables:
        SESSION_BACKEND: Backend type ("memory" or "redis")
        REDIS_URL: Redis connection URL (for redis backend)
    """
    global _backend_instance

    if _backend_instance is not None:
        return _backend_instance

    backend_type = os.getenv("SESSION_BACKEND", "memory").lower()

    if backend_type == "redis":
        logger.info("Using Redis session backend")
        _backend_instance = RedisSessionBackend()
    else:
        logger.info("Using in-memory session backend")
        _backend_instance = InMemorySessionBackend()

    return _backend_instance


def reset_session_backend() -> None:
    """Reset the global backend instance.

    Useful for testing to ensure a fresh backend.
    """
    global _backend_instance
    _backend_instance = None


def generate_session_id() -> str:
    """Generate a unique session ID."""
    return f"sess_{uuid.uuid4().hex[:12]}"


def generate_message_id() -> str:
    """Generate a unique message ID."""
    return f"msg_{uuid.uuid4().hex[:12]}"
