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
Inter-bot messaging module for agentic-brain.

Provides pub/sub messaging between autonomous agents with Neo4j persistence.
Supports direct messages, message history, and handoff protocol for task transfers.

Example:
    >>> from agentic_brain.bots import BotMessaging, BotMessage
    >>> from agentic_brain.memory import Neo4jMemory
    >>>
    >>> # Create messaging with existing Neo4j connection
    >>> memory = Neo4jMemory(uri, user, password)
    >>> memory.connect()
    >>> messaging = BotMessaging("agent_1", memory=memory)
    >>>
    >>> # Send message to another agent
    >>> msg_id = messaging.send("agent_2", "Process this data", {"items": [1, 2, 3]})
    >>>
    >>> # Receive messages (as agent_2)
    >>> messages = messaging.receive()
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BotMessage:
    """
    Message between two bots.

    Attributes:
        id: Unique message identifier
        from_bot: Sender bot ID
        to_bot: Recipient bot ID
        message: Message text content
        data: Additional data payload
        timestamp: When the message was created
        read: Whether the message has been read
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_bot: str = ""
    to_bot: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, serializing complex types."""
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        d["data"] = json.dumps(self.data) if self.data else "{}"
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BotMessage:
        """Create from dictionary, deserializing complex types."""
        d = data.copy()
        if isinstance(d.get("timestamp"), str):
            d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        if isinstance(d.get("data"), str):
            d["data"] = json.loads(d["data"]) if d["data"] else {}
        return cls(**d)


@dataclass
class BotHandoff:
    """
    Handoff of work/data between bots.

    Attributes:
        id: Unique handoff identifier
        from_bot: Sender bot ID
        to_bot: Recipient bot ID
        data: Data being handed off
        message: Context message for the handoff
        created: When the handoff was created
        claimed: Whether the handoff has been claimed
        claimed_by: Bot ID that claimed the handoff
        claimed_at: When the handoff was claimed
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    from_bot: str = ""
    to_bot: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    created: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    claimed: bool = False
    claimed_by: str | None = None
    claimed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary, serializing complex types."""
        d = asdict(self)
        d["created"] = self.created.isoformat()
        if d.get("claimed_at") and self.claimed_at:
            d["claimed_at"] = self.claimed_at.isoformat()
        d["data"] = json.dumps(self.data) if self.data else "{}"
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BotHandoff:
        """Create from dictionary, deserializing complex types."""
        d = data.copy()
        if isinstance(d.get("created"), str):
            d["created"] = datetime.fromisoformat(d["created"])
        if isinstance(d.get("claimed_at"), str):
            d["claimed_at"] = datetime.fromisoformat(d["claimed_at"])
        if isinstance(d.get("data"), str):
            d["data"] = json.loads(d["data"]) if d["data"] else {}
        return cls(**d)


class BotMessaging:
    """
    Inter-bot messaging system with Neo4j persistence.

    Provides reliable message passing between autonomous agents, with
    support for direct messages, message acknowledgment, and work handoffs.

    Example:
        >>> from agentic_brain.memory import Neo4jMemory
        >>>
        >>> # Using with Neo4jMemory
        >>> memory = Neo4jMemory(uri, user, password)
        >>> memory.connect()
        >>> messaging = BotMessaging("my_agent", memory=memory)
        >>>
        >>> # Send a message
        >>> messaging.send("other_agent", "Hello!", {"key": "value"})
        >>>
        >>> # Receive messages
        >>> messages = messaging.receive()
        >>> for msg in messages:
        ...     print(f"{msg.from_bot}: {msg.message}")
    """

    def __init__(
        self,
        bot_id: str,
        memory: Any | None = None,
    ) -> None:
        """
        Initialize messaging system for a bot.

        Args:
            bot_id: ID of this bot
            memory: Neo4jMemory instance (creates own connection if not provided)
        """
        self.bot_id = bot_id
        self.memory = memory
        self._driver: Any | None = None
        self._pending_handoff: dict[str, Any] | None = None

        if self.memory and hasattr(self.memory, "_driver"):
            self._driver = self.memory._driver
        else:
            self._setup_neo4j()

        self._ensure_schema()

    def _setup_neo4j(self) -> None:
        """Set up Neo4j connection if no memory instance provided."""
        try:
            from neo4j import GraphDatabase

            uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            user = os.getenv("NEO4J_USER", "neo4j")
            password = os.getenv("NEO4J_PASSWORD", "")
            auth = (user, password)
            self._driver = GraphDatabase.driver(uri, auth=auth)
            logger.debug(f"BotMessaging connected to Neo4j at {uri}")
        except ImportError:
            logger.warning(
                "neo4j package not installed - messaging will work in memory only"
            )
        except Exception as e:
            logger.warning(
                f"Could not connect to Neo4j: {e} - messaging will work in memory only"
            )

    def _ensure_schema(self) -> None:
        """Create Neo4j schema/constraints if driver available."""
        if not self._driver:
            return

        try:
            with self._driver.session() as session:
                session.run(
                    """
                    CREATE CONSTRAINT bot_message_id IF NOT EXISTS
                    FOR (m:BotMessage) REQUIRE m.id IS UNIQUE
                """
                )

                session.run(
                    """
                    CREATE CONSTRAINT handoff_id IF NOT EXISTS
                    FOR (h:Handoff) REQUIRE h.id IS UNIQUE
                """
                )

                session.run(
                    """
                    CREATE INDEX bot_message_to_bot_read IF NOT EXISTS
                    FOR (m:BotMessage) ON (m.to_bot, m.read)
                """
                )

                session.run(
                    """
                    CREATE INDEX handoff_to_bot_claimed IF NOT EXISTS
                    FOR (h:Handoff) ON (h.to_bot, h.claimed)
                """
                )
        except Exception:
            pass

    def send(
        self, to_bot: str, message: str, data: dict[str, Any] | None = None
    ) -> str:
        """
        Send a message to another bot.

        Args:
            to_bot: ID of recipient bot
            message: Message text
            data: Optional data payload

        Returns:
            Message ID
        """
        msg = BotMessage(
            from_bot=self.bot_id, to_bot=to_bot, message=message, data=data or {}
        )

        if self._driver:
            self._store_message(msg)

        logger.debug(f"Message sent from {self.bot_id} to {to_bot}: {message[:50]}...")
        return msg.id

    async def send_async(
        self,
        to_bot: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> str:
        """
        Send a message to another bot asynchronously.

        Args:
            to_bot: ID of recipient bot
            message: Message text
            data: Optional data payload

        Returns:
            Message ID
        """
        return self.send(to_bot, message, data)

    def _store_message(self, msg: BotMessage) -> None:
        """Store message in Neo4j."""
        if not self._driver:
            return

        try:
            with self._driver.session() as session:
                session.run(
                    """
                    CREATE (m:BotMessage {
                        id: $id,
                        from_bot: $from_bot,
                        to_bot: $to_bot,
                        message: $message,
                        data_json: $data_json,
                        timestamp: $timestamp,
                        read: $read
                    })
                """,
                    {
                        "id": msg.id,
                        "from_bot": msg.from_bot,
                        "to_bot": msg.to_bot,
                        "message": msg.message,
                        "data_json": json.dumps(msg.data) if msg.data else "{}",
                        "timestamp": msg.timestamp.isoformat(),
                        "read": msg.read,
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to store message in Neo4j: {e}")

    def receive(self, mark_read: bool = True) -> list[BotMessage]:
        """
        Get unread messages for this bot.

        Args:
            mark_read: If True, mark retrieved messages as read

        Returns:
            List of unread BotMessage objects
        """
        messages = self._query_messages(to_bot=self.bot_id, read=False)

        if mark_read and messages:
            for msg in messages:
                self.acknowledge(msg.id)

        return messages

    async def receive_async(self, mark_read: bool = True) -> list[BotMessage]:
        """
        Get unread messages for this bot asynchronously.

        Args:
            mark_read: If True, mark retrieved messages as read

        Returns:
            List of unread BotMessage objects
        """
        return self.receive(mark_read)

    def peek(self) -> list[BotMessage]:
        """
        Get unread messages without marking as read.

        Returns:
            List of unread BotMessage objects
        """
        return self._query_messages(to_bot=self.bot_id, read=False)

    def _query_messages(
        self,
        from_bot: str | None = None,
        to_bot: str | None = None,
        read: bool | None = None,
        limit: int = 50,
    ) -> list[BotMessage]:
        """Query messages from Neo4j."""
        if not self._driver:
            return []

        try:
            with self._driver.session() as session:
                conditions = []
                params: dict[str, Any] = {"limit": limit}

                if from_bot:
                    conditions.append("m.from_bot = $from_bot")
                    params["from_bot"] = from_bot

                if to_bot:
                    conditions.append("m.to_bot = $to_bot")
                    params["to_bot"] = to_bot

                if read is not None:
                    conditions.append("m.read = $read")
                    params["read"] = read

                where_clause = " AND ".join(conditions)
                query = f"""
                    MATCH (m:BotMessage)
                    {f'WHERE {where_clause}' if where_clause else ''}
                    RETURN m
                    ORDER BY m.timestamp DESC
                    LIMIT $limit
                """

                result = session.run(query, params)
                messages = []

                for record in result:
                    node = record["m"]
                    msg = BotMessage(
                        id=node["id"],
                        from_bot=node["from_bot"],
                        to_bot=node["to_bot"],
                        message=node["message"],
                        data=json.loads(node.get("data_json", "{}")),
                        timestamp=datetime.fromisoformat(node["timestamp"]),
                        read=node["read"],
                    )
                    messages.append(msg)

                return messages
        except Exception as e:
            logger.warning(f"Failed to query messages from Neo4j: {e}")
            return []

    def get_history(
        self,
        with_bot: str | None = None,
        limit: int = 50,
    ) -> list[BotMessage]:
        """
        Get message history between this bot and another.

        Args:
            with_bot: Filter to messages with specific bot (both directions)
            limit: Maximum messages to return

        Returns:
            List of BotMessage objects
        """
        if not self._driver:
            return []

        try:
            with self._driver.session() as session:
                if with_bot:
                    result = session.run(
                        """
                        MATCH (m:BotMessage)
                        WHERE (m.from_bot = $bot_id AND m.to_bot = $with_bot)
                           OR (m.from_bot = $with_bot AND m.to_bot = $bot_id)
                        RETURN m
                        ORDER BY m.timestamp DESC
                        LIMIT $limit
                    """,
                        {"bot_id": self.bot_id, "with_bot": with_bot, "limit": limit},
                    )
                else:
                    result = session.run(
                        """
                        MATCH (m:BotMessage)
                        WHERE m.from_bot = $bot_id OR m.to_bot = $bot_id
                        RETURN m
                        ORDER BY m.timestamp DESC
                        LIMIT $limit
                    """,
                        {"bot_id": self.bot_id, "limit": limit},
                    )

                messages = []
                for record in result:
                    node = record["m"]
                    msg = BotMessage(
                        id=node["id"],
                        from_bot=node["from_bot"],
                        to_bot=node["to_bot"],
                        message=node["message"],
                        data=json.loads(node.get("data_json", "{}")),
                        timestamp=datetime.fromisoformat(node["timestamp"]),
                        read=node["read"],
                    )
                    messages.append(msg)

                return messages
        except Exception as e:
            logger.warning(f"Failed to query history from Neo4j: {e}")
            return []

    def acknowledge(self, message_id: str) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: ID of message to mark read

        Returns:
            True if successful
        """
        if not self._driver:
            return False

        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (m:BotMessage {id: $id})
                    SET m.read = true
                    RETURN COUNT(m) as updated
                """,
                    {"id": message_id},
                )

                record = result.single()
                return record["updated"] > 0 if record else False
        except Exception as e:
            logger.warning(f"Failed to acknowledge message: {e}")
            return False

    def handoff(
        self,
        to_bot: str,
        data: dict[str, Any],
        message: str | None = None,
    ) -> str:
        """
        Hand off work/data to another bot.

        Args:
            to_bot: ID of recipient bot
            data: Data to hand off
            message: Optional message with context

        Returns:
            Handoff ID
        """
        handoff = BotHandoff(
            from_bot=self.bot_id, to_bot=to_bot, data=data, message=message or ""
        )

        if self._driver:
            self._store_handoff(handoff)

        logger.debug(f"Handoff created from {self.bot_id} to {to_bot}")
        return handoff.id

    def _store_handoff(self, handoff: BotHandoff) -> None:
        """Store handoff in Neo4j."""
        if not self._driver:
            return

        try:
            with self._driver.session() as session:
                session.run(
                    """
                    CREATE (h:Handoff {
                        id: $id,
                        from_bot: $from_bot,
                        to_bot: $to_bot,
                        data_json: $data_json,
                        message: $message,
                        created: $created,
                        claimed: $claimed,
                        claimed_by: $claimed_by,
                        claimed_at: $claimed_at
                    })
                """,
                    {
                        "id": handoff.id,
                        "from_bot": handoff.from_bot,
                        "to_bot": handoff.to_bot,
                        "data_json": json.dumps(handoff.data) if handoff.data else "{}",
                        "message": handoff.message,
                        "created": handoff.created.isoformat(),
                        "claimed": handoff.claimed,
                        "claimed_by": handoff.claimed_by,
                        "claimed_at": (
                            handoff.claimed_at.isoformat()
                            if handoff.claimed_at
                            else None
                        ),
                    },
                )
        except Exception as e:
            logger.warning(f"Failed to store handoff in Neo4j: {e}")

    def set_handoff(self, data: Any) -> None:
        """
        Set pending handoff data (for pipeline in-memory handoff).

        This is used by Pipeline to pass data between stages without
        requiring Neo4j. The data is stored locally and retrieved by
        get_handoff().

        Args:
            data: Data to hand off to this bot
        """
        self._pending_handoff = data

    def get_handoff(self) -> dict[str, Any] | None:
        """
        Check for pending handoff to this bot.

        First checks local in-memory handoff (set by pipeline),
        then checks Neo4j for persisted handoffs.

        Returns:
            Handoff dict or None if no pending handoff
        """
        if self._pending_handoff is not None:
            data = self._pending_handoff
            self._pending_handoff = None
            return data

        if not self._driver:
            return None

        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (h:Handoff)
                    WHERE h.to_bot = $bot_id AND h.claimed = false
                    RETURN h
                    ORDER BY h.created ASC
                    LIMIT 1
                """,
                    {"bot_id": self.bot_id},
                )

                record = result.single()
                if not record:
                    return None

                node = record["h"]
                return {
                    "id": node["id"],
                    "from_bot": node["from_bot"],
                    "to_bot": node["to_bot"],
                    "data": json.loads(node.get("data_json", "{}")),
                    "message": node["message"],
                    "created": node["created"],
                }
        except Exception as e:
            logger.warning(f"Failed to get handoff from Neo4j: {e}")
            return None

    def claim_handoff(self, handoff_id: str) -> dict[str, Any] | None:
        """
        Claim and mark handoff as processed.

        Args:
            handoff_id: ID of handoff to claim

        Returns:
            Handoff data dict or None if not found
        """
        if not self._driver:
            return None

        try:
            with self._driver.session() as session:
                result = session.run(
                    """
                    MATCH (h:Handoff {id: $id})
                    WHERE h.to_bot = $bot_id AND h.claimed = false
                    SET h.claimed = true,
                        h.claimed_by = $bot_id,
                        h.claimed_at = $claimed_at
                    RETURN h
                """,
                    {
                        "id": handoff_id,
                        "bot_id": self.bot_id,
                        "claimed_at": datetime.now(timezone.utc).isoformat(),
                    },
                )

                record = result.single()
                if not record:
                    return None

                node = record["h"]
                return {
                    "id": node["id"],
                    "from_bot": node["from_bot"],
                    "to_bot": node["to_bot"],
                    "data": json.loads(node.get("data_json", "{}")),
                    "message": node["message"],
                    "created": node["created"],
                }
        except Exception as e:
            logger.warning(f"Failed to claim handoff: {e}")
            return None

    def close(self) -> None:
        """Clean up Neo4j resources."""
        if self._driver and not self.memory:
            with contextlib.suppress(Exception):
                self._driver.close()

    def __del__(self) -> None:
        """Clean up on deletion."""
        self.close()


__all__ = [
    "BotMessage",
    "BotHandoff",
    "BotMessaging",
]
