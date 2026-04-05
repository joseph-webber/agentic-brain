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
Unified Session Management Module
=================================

Canonical session management for agentic-brain. Consolidates best patterns from:
- neo4j_memory.py: ConversationMemory with entity linking
- unified.py: UnifiedMemory with SQLite fallback and importance scoring
- summarization.py: Real-time and session summarization
- core/hooks/ultimate_memory_hooks.py: Perfect memory hooks

Key Features:
- Neo4j-preferred persistence with SQLite fallback
- Context window management with token awareness
- Memory summarization and compression (Mem0-inspired)
- Cross-session continuity
- Optional Redis caching layer
- Entity extraction and linking
- Importance-based retention with time decay

Example:
    >>> from agentic_brain.memory import SessionManager
    >>> manager = SessionManager()
    >>> session = await manager.create_session()
    >>> await session.add_message("user", "Hello, I'm Alice")
    >>> await session.add_message("assistant", "Nice to meet you, Alice!")
    >>> context = await session.get_context(max_tokens=4000)
    >>> await session.end()  # Generates summary, persists to Neo4j

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                      SESSION MANAGER                            │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
    │  │   Session   │    │   Memory    │    │    Cache    │        │
    │  │   Context   │───▶│   Backend   │◀───│   (Redis)   │        │
    │  │  (in-mem)   │    │ (Neo4j/SQL) │    │  (optional) │        │
    │  └─────────────┘    └─────────────┘    └─────────────┘        │
    │         │                  │                  │                │
    │         ▼                  ▼                  ▼                │
    │  ┌─────────────────────────────────────────────────────────┐  │
    │  │                   UNIFIED API                           │  │
    │  │  create_session() | get_context() | recall() | end()    │  │
    │  └─────────────────────────────────────────────────────────┘  │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


class MessageRole(Enum):
    """Message roles in a conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class SessionMessage:
    """
    A single message in a session.

    Attributes:
        id: Unique message identifier
        role: Message role (user, assistant, system, tool)
        content: Message content
        timestamp: When the message was created
        session_id: Parent session identifier
        metadata: Optional metadata dict
        entities: Extracted entities (people, places, things)
        importance: Importance score 0.0-1.0 (affects retention)
        access_count: Times this message has been recalled (reinforcement)
        token_count: Estimated token count for context management
    """

    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    session_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    entities: list[dict[str, str]] = field(default_factory=list)
    importance: float = 0.5
    access_count: int = 0
    token_count: int = 0

    def __post_init__(self):
        """Estimate token count if not provided."""
        if self.token_count == 0:
            # Rough estimate: ~4 chars per token
            self.token_count = len(self.content) // 4 + 1

    @property
    def effective_importance(self) -> float:
        """
        Get importance with time-decay applied (Mem0-inspired).

        Memories fade over time unless reinforced by access.
        """
        days = max(0.0, (datetime.now(UTC) - self.timestamp).total_seconds() / 86400)
        decay = math.exp(-0.01 * days)  # Exponential decay
        reinforcement = min(self.access_count * 0.02, 0.2)  # Access boosts importance
        return max(0.1, min(1.0, self.importance * decay + reinforcement))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "metadata": self.metadata,
            "entities": self.entities,
            "importance": self.importance,
            "access_count": self.access_count,
            "token_count": self.token_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMessage:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if isinstance(data.get("timestamp"), str)
                else data.get("timestamp", datetime.now(UTC))
            ),
            session_id=data["session_id"],
            metadata=data.get("metadata", {}),
            entities=data.get("entities", []),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            token_count=data.get("token_count", 0),
        )


@dataclass
class SessionSummary:
    """
    Summary of a session for long-term storage.

    Attributes:
        id: Summary identifier
        session_id: Session this summarizes
        content: Summary text
        message_count: Number of messages summarized
        start_time: Session start timestamp
        end_time: Session end timestamp
        topics: Main topics discussed
        entities: Named entities mentioned
        key_facts: Key decisions and facts
    """

    id: str
    session_id: str
    content: str
    message_count: int
    start_time: datetime
    end_time: datetime
    topics: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content": self.content,
            "message_count": self.message_count,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "topics": self.topics,
            "entities": self.entities,
            "key_facts": self.key_facts,
        }

    def to_neo4j(self) -> dict[str, Any]:
        """Convert to Neo4j-compatible format."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content": self.content,
            "message_count": self.message_count,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "topics_json": json.dumps(self.topics),
            "entities_json": json.dumps(self.entities),
            "key_facts_json": json.dumps(self.key_facts),
        }


@dataclass
class SessionConfig:
    """
    Configuration for session management.

    Attributes:
        max_context_tokens: Maximum tokens in context window
        summarize_threshold: Messages before auto-summarization
        importance_keywords: Keywords that boost importance
        entity_patterns: Regex patterns for entity extraction
        decay_rate: Daily importance decay rate
        use_redis_cache: Enable Redis caching layer
        redis_url: Redis connection URL
    """

    max_context_tokens: int = 8000
    summarize_threshold: int = 50
    importance_keywords: list[str] = field(
        default_factory=lambda: [
            "important",
            "critical",
            "remember",
            "always",
            "never",
            "password",
            "deadline",
            "decision",
            "agreed",
            "preference",
            "error",
            "bug",
            "fix",
        ]
    )
    entity_patterns: list[str] = field(
        default_factory=lambda: [
            r"(?:SD|CITB|PR)-\d+",  # JIRA tickets
            r"@\w+",  # Mentions
            r"[A-Z][a-z]+ [A-Z][a-z]+",  # Names
        ]
    )
    decay_rate: float = 0.01
    use_redis_cache: bool = False
    redis_url: str = "redis://localhost:6379"


# =============================================================================
# STORAGE BACKENDS
# =============================================================================


class SessionBackend(Protocol):
    """Protocol for session storage backends."""

    def store_message(self, message: SessionMessage) -> None:
        """Store a message."""
        ...

    def get_messages(
        self, session_id: str, limit: int | None = None
    ) -> list[SessionMessage]:
        """Get messages for a session."""
        ...

    def store_summary(self, summary: SessionSummary) -> None:
        """Store a session summary."""
        ...

    def get_recent_context(self, hours: int = 24) -> list[SessionMessage]:
        """Get recent messages across all sessions."""
        ...

    def search(self, query: str, limit: int = 10) -> list[SessionMessage]:
        """Search messages by content."""
        ...


class Neo4jSessionBackend:
    """
    Neo4j-backed session storage.

    Graph structure:
        (Session)-[:CONTAINS]->(Message)-[:NEXT]->(Message)
        (Message)-[:MENTIONS]->(Entity)
        (Session)-[:SUMMARIZED_BY]->(Summary)
    """

    def __init__(self, use_pool: bool = True):
        """Initialize Neo4j backend."""
        self.use_pool = use_pool
        self._initialized = False

    def _get_session(self):
        """Get Neo4j session."""
        if self.use_pool:
            try:
                from agentic_brain.core.neo4j_pool import get_session

                return get_session()
            except ImportError:
                pass

        try:
            from neo4j import GraphDatabase

            driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", ""))
            return driver.session()
        except Exception as e:
            logger.warning(f"Neo4j not available: {e}")
            raise

    def initialize(self) -> None:
        """Initialize schema and indexes."""
        if self._initialized:
            return

        try:
            with self._get_session() as session:
                # Create constraints
                session.run(
                    """
                    CREATE CONSTRAINT session_msg_id IF NOT EXISTS
                    FOR (m:SessionMessage) REQUIRE m.id IS UNIQUE
                    """
                )
                session.run(
                    """
                    CREATE INDEX session_msg_time IF NOT EXISTS
                    FOR (m:SessionMessage) ON (m.timestamp)
                    """
                )
                session.run(
                    """
                    CREATE INDEX session_msg_session IF NOT EXISTS
                    FOR (m:SessionMessage) ON (m.session_id)
                    """
                )
            self._initialized = True
        except Exception as e:
            logger.warning(f"Failed to initialize Neo4j schema: {e}")

    def store_message(self, message: SessionMessage) -> None:
        """Store a message in Neo4j."""
        self.initialize()
        try:
            with self._get_session() as session:
                session.run(
                    """
                    MERGE (m:SessionMessage {id: $id})
                    SET m.role = $role,
                        m.content = $content,
                        m.timestamp = datetime($timestamp),
                        m.session_id = $session_id,
                        m.importance = $importance,
                        m.access_count = $access_count,
                        m.metadata = $metadata,
                        m.entities_json = $entities_json
                    """,
                    id=message.id,
                    role=message.role.value,
                    content=message.content,
                    timestamp=message.timestamp.isoformat(),
                    session_id=message.session_id,
                    importance=message.importance,
                    access_count=message.access_count,
                    metadata=json.dumps(message.metadata),
                    entities_json=json.dumps(message.entities),
                )
        except Exception as e:
            logger.error(f"Failed to store message in Neo4j: {e}")

    def get_messages(
        self, session_id: str, limit: int | None = None
    ) -> list[SessionMessage]:
        """Get messages for a session."""
        self.initialize()
        messages = []
        try:
            with self._get_session() as session:
                query = """
                    MATCH (m:SessionMessage {session_id: $session_id})
                    RETURN m
                    ORDER BY m.timestamp DESC
                """
                if limit:
                    query += f" LIMIT {limit}"

                result = session.run(query, session_id=session_id)
                for record in result:
                    node = record["m"]
                    messages.append(
                        SessionMessage(
                            id=node["id"],
                            role=MessageRole(node["role"]),
                            content=node["content"],
                            timestamp=node["timestamp"].to_native(),
                            session_id=node["session_id"],
                            importance=node.get("importance", 0.5),
                            access_count=node.get("access_count", 0),
                            metadata=json.loads(node.get("metadata", "{}")),
                            entities=json.loads(node.get("entities_json", "[]")),
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to get messages from Neo4j: {e}")
        return messages

    def store_summary(self, summary: SessionSummary) -> None:
        """Store a session summary in Neo4j."""
        self.initialize()
        try:
            with self._get_session() as session:
                session.run(
                    """
                    MERGE (s:SessionSummary {id: $id})
                    SET s.session_id = $session_id,
                        s.content = $content,
                        s.message_count = $message_count,
                        s.start_time = datetime($start_time),
                        s.end_time = datetime($end_time),
                        s.topics_json = $topics_json,
                        s.entities_json = $entities_json,
                        s.key_facts_json = $key_facts_json
                    """,
                    **summary.to_neo4j(),
                )
        except Exception as e:
            logger.error(f"Failed to store summary in Neo4j: {e}")

    def get_recent_context(self, hours: int = 24) -> list[SessionMessage]:
        """Get recent messages across all sessions."""
        self.initialize()
        messages = []
        try:
            with self._get_session() as session:
                result = session.run(
                    f"""
                    MATCH (m:SessionMessage)
                    WHERE m.timestamp > datetime() - duration('PT{hours}H')
                    RETURN m
                    ORDER BY m.timestamp DESC
                    LIMIT 50
                    """
                )
                for record in result:
                    node = record["m"]
                    messages.append(
                        SessionMessage(
                            id=node["id"],
                            role=MessageRole(node["role"]),
                            content=node["content"],
                            timestamp=node["timestamp"].to_native(),
                            session_id=node["session_id"],
                            importance=node.get("importance", 0.5),
                            access_count=node.get("access_count", 0),
                            metadata=json.loads(node.get("metadata", "{}")),
                            entities=json.loads(node.get("entities_json", "[]")),
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to get recent context: {e}")
        return messages

    def search(self, query: str, limit: int = 10) -> list[SessionMessage]:
        """Search messages by content."""
        self.initialize()
        messages = []
        try:
            with self._get_session() as session:
                result = session.run(
                    """
                    MATCH (m:SessionMessage)
                    WHERE toLower(m.content) CONTAINS toLower($search_term)
                    RETURN m
                    ORDER BY m.timestamp DESC
                    LIMIT $max_results
                    """,
                    search_term=query,
                    max_results=limit,
                )
                for record in result:
                    node = record["m"]
                    messages.append(
                        SessionMessage(
                            id=node["id"],
                            role=MessageRole(node["role"]),
                            content=node["content"],
                            timestamp=node["timestamp"].to_native(),
                            session_id=node["session_id"],
                            importance=node.get("importance", 0.5),
                            access_count=node.get("access_count", 0),
                            metadata=json.loads(node.get("metadata", "{}")),
                            entities=json.loads(node.get("entities_json", "[]")),
                        )
                    )
        except Exception as e:
            logger.error(f"Failed to search messages: {e}")
        return messages


class SQLiteSessionBackend:
    """
    SQLite-backed session storage (fallback when Neo4j unavailable).

    Works offline with zero external dependencies.
    """

    def __init__(self, db_path: str = "~/.agentic_brain/sessions.db"):
        """Initialize SQLite backend."""
        import sqlite3

        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self):
        """Get thread-local connection."""
        import sqlite3

        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                metadata TEXT,
                entities TEXT,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                token_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_msg_time ON messages(timestamp);

            CREATE TABLE IF NOT EXISTS summaries (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                message_count INTEGER,
                start_time TEXT,
                end_time TEXT,
                topics TEXT,
                entities TEXT,
                key_facts TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content='messages',
                content_rowid='rowid'
            );
        """
        )
        conn.commit()

    def store_message(self, message: SessionMessage) -> None:
        """Store a message."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO messages
            (id, role, content, timestamp, session_id, metadata, entities,
             importance, access_count, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.role.value,
                message.content,
                message.timestamp.isoformat(),
                message.session_id,
                json.dumps(message.metadata),
                json.dumps(message.entities),
                message.importance,
                message.access_count,
                message.token_count,
            ),
        )
        conn.commit()

    def get_messages(
        self, session_id: str, limit: int | None = None
    ) -> list[SessionMessage]:
        """Get messages for a session."""
        conn = self._get_conn()
        query = """
            SELECT * FROM messages
            WHERE session_id = ?
            ORDER BY timestamp DESC
        """
        if limit:
            query += f" LIMIT {limit}"

        cursor = conn.execute(query, (session_id,))
        messages = []
        for row in cursor:
            messages.append(
                SessionMessage(
                    id=row["id"],
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    session_id=row["session_id"],
                    metadata=json.loads(row["metadata"] or "{}"),
                    entities=json.loads(row["entities"] or "[]"),
                    importance=row["importance"],
                    access_count=row["access_count"],
                    token_count=row["token_count"],
                )
            )
        return messages

    def store_summary(self, summary: SessionSummary) -> None:
        """Store a session summary."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO summaries
            (id, session_id, content, message_count, start_time, end_time,
             topics, entities, key_facts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                summary.id,
                summary.session_id,
                summary.content,
                summary.message_count,
                summary.start_time.isoformat(),
                summary.end_time.isoformat(),
                json.dumps(summary.topics),
                json.dumps(summary.entities),
                json.dumps(summary.key_facts),
            ),
        )
        conn.commit()

    def get_recent_context(self, hours: int = 24) -> list[SessionMessage]:
        """Get recent messages across all sessions."""
        conn = self._get_conn()
        cutoff = (datetime.now(UTC) - timedelta(hours=hours)).isoformat()
        cursor = conn.execute(
            """
            SELECT * FROM messages
            WHERE timestamp > ?
            ORDER BY timestamp DESC
            LIMIT 50
            """,
            (cutoff,),
        )
        messages = []
        for row in cursor:
            messages.append(
                SessionMessage(
                    id=row["id"],
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    session_id=row["session_id"],
                    metadata=json.loads(row["metadata"] or "{}"),
                    entities=json.loads(row["entities"] or "[]"),
                    importance=row["importance"],
                    access_count=row["access_count"],
                    token_count=row["token_count"],
                )
            )
        return messages

    def search(self, query: str, limit: int = 10) -> list[SessionMessage]:
        """Search messages by content."""
        conn = self._get_conn()
        cursor = conn.execute(
            """
            SELECT * FROM messages
            WHERE content LIKE ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        messages = []
        for row in cursor:
            messages.append(
                SessionMessage(
                    id=row["id"],
                    role=MessageRole(row["role"]),
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    session_id=row["session_id"],
                    metadata=json.loads(row["metadata"] or "{}"),
                    entities=json.loads(row["entities"] or "[]"),
                    importance=row["importance"],
                    access_count=row["access_count"],
                    token_count=row["token_count"],
                )
            )
        return messages


# =============================================================================
# SESSION CLASS
# =============================================================================


class Session:
    """
    Active conversation session with context management.

    Handles:
    - In-memory message buffer
    - Token-aware context window
    - Automatic importance scoring
    - Entity extraction
    - Session summarization on end
    """

    def __init__(
        self,
        session_id: str,
        backend: SessionBackend,
        config: SessionConfig,
        cache: Any | None = None,
    ):
        """Initialize session."""
        self.session_id = session_id
        self.backend = backend
        self.config = config
        self.cache = cache
        self._messages: list[SessionMessage] = []
        self._started_at = datetime.now(UTC)
        self._entity_patterns = [re.compile(p) for p in config.entity_patterns]

    async def add_message(
        self,
        role: str | MessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> SessionMessage:
        """
        Add a message to the session.

        Args:
            role: Message role (user, assistant, system, tool)
            content: Message content
            metadata: Optional metadata

        Returns:
            The created SessionMessage
        """
        if isinstance(role, str):
            role = MessageRole(role)

        # Generate message ID
        msg_id = hashlib.sha256(
            f"{self.session_id}_{content}_{datetime.now(UTC)}".encode()
        ).hexdigest()[:16]

        # Calculate importance
        importance = self._calculate_importance(content)

        # Extract entities
        entities = self._extract_entities(content)

        message = SessionMessage(
            id=msg_id,
            role=role,
            content=content,
            timestamp=datetime.now(UTC),
            session_id=self.session_id,
            metadata=metadata or {},
            entities=entities,
            importance=importance,
        )

        # Add to in-memory buffer
        self._messages.append(message)

        # Persist to backend
        self.backend.store_message(message)

        # Cache if enabled
        if self.cache:
            self.cache.set(f"msg:{msg_id}", message.to_dict())

        # Check if summarization needed
        if len(self._messages) >= self.config.summarize_threshold:
            await self._compress_old_messages()

        return message

    def _calculate_importance(self, content: str) -> float:
        """Calculate importance score for content."""
        importance = 0.5
        content_lower = content.lower()

        # Boost for importance keywords
        for keyword in self.config.importance_keywords:
            if keyword in content_lower:
                importance += 0.1

        # Boost for questions (often need follow-up)
        if "?" in content:
            importance += 0.05

        # Boost for code blocks
        if "```" in content:
            importance += 0.1

        return min(1.0, importance)

    def _extract_entities(self, content: str) -> list[dict[str, str]]:
        """Extract named entities from content."""
        entities = []
        for pattern in self._entity_patterns:
            for match in pattern.finditer(content):
                entity_text = match.group()
                entity_type = self._classify_entity(entity_text)
                entities.append({"text": entity_text, "type": entity_type})
        return entities

    def _classify_entity(self, entity: str) -> str:
        """Classify entity type."""
        if re.match(r"(?:SD|CITB|PR)-\d+", entity):
            return "ticket"
        elif entity.startswith("@"):
            return "mention"
        else:
            return "person"

    async def get_context(
        self,
        max_tokens: int | None = None,
        include_summaries: bool = True,
    ) -> list[dict[str, str]]:
        """
        Get conversation context within token limit.

        Args:
            max_tokens: Maximum tokens (defaults to config)
            include_summaries: Include compressed summaries

        Returns:
            List of message dicts for LLM context
        """
        max_tokens = max_tokens or self.config.max_context_tokens
        context = []
        total_tokens = 0

        # Add messages newest-first until we hit token limit
        for msg in reversed(self._messages):
            if total_tokens + msg.token_count > max_tokens:
                break
            context.insert(0, {"role": msg.role.value, "content": msg.content})
            total_tokens += msg.token_count

            # Increment access count (reinforcement)
            msg.access_count += 1

        return context

    async def recall(self, query: str, limit: int = 5) -> list[SessionMessage]:
        """
        Recall relevant past messages.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Relevant messages
        """
        # Search backend
        results = self.backend.search(query, limit)

        # Increment access count for recalled messages
        for msg in results:
            msg.access_count += 1

        return results

    async def _compress_old_messages(self) -> None:
        """Compress older messages into summary."""
        # Keep last 20 messages, summarize the rest
        if len(self._messages) <= 20:
            return

        to_compress = self._messages[:-20]
        self._messages = self._messages[-20:]

        # Generate summary (simplified - would use LLM in production)
        topics = set()
        entities = set()
        for msg in to_compress:
            for entity in msg.entities:
                entities.add(entity["text"])

        content = f"Compressed {len(to_compress)} messages. "
        content += f"Entities mentioned: {', '.join(entities) if entities else 'none'}."

        summary = SessionSummary(
            id=str(uuid.uuid4())[:16],
            session_id=self.session_id,
            content=content,
            message_count=len(to_compress),
            start_time=to_compress[0].timestamp,
            end_time=to_compress[-1].timestamp,
            topics=list(topics),
            entities=list(entities),
            key_facts=[],
        )

        self.backend.store_summary(summary)
        logger.info(f"Compressed {len(to_compress)} messages for session {self.session_id}")

    async def end(self) -> SessionSummary:
        """
        End the session and generate final summary.

        Returns:
            Session summary
        """
        # Generate final summary
        topics = set()
        entities = set()
        for msg in self._messages:
            for entity in msg.entities:
                entities.add(entity["text"])

        content = f"Session with {len(self._messages)} messages. "
        content += f"Discussed: {', '.join(entities) if entities else 'general topics'}."

        summary = SessionSummary(
            id=str(uuid.uuid4())[:16],
            session_id=self.session_id,
            content=content,
            message_count=len(self._messages),
            start_time=self._started_at,
            end_time=datetime.now(UTC),
            topics=list(topics),
            entities=list(entities),
            key_facts=[],
        )

        self.backend.store_summary(summary)
        logger.info(f"Session {self.session_id} ended with {len(self._messages)} messages")

        return summary


# =============================================================================
# SESSION MANAGER
# =============================================================================


class SessionManager:
    """
    Unified session manager with auto-fallback.

    Creates and manages sessions with:
    - Neo4j-preferred storage (falls back to SQLite)
    - Optional Redis caching
    - Cross-session context recall
    """

    def __init__(
        self,
        config: SessionConfig | None = None,
        prefer_neo4j: bool = True,
    ):
        """
        Initialize session manager.

        Args:
            config: Session configuration
            prefer_neo4j: Prefer Neo4j backend (falls back to SQLite)
        """
        self.config = config or SessionConfig()
        self._backend: SessionBackend | None = None
        self._cache = None
        self._prefer_neo4j = prefer_neo4j
        self._sessions: dict[str, Session] = {}

    def _get_backend(self) -> SessionBackend:
        """Get or create storage backend."""
        if self._backend is not None:
            return self._backend

        if self._prefer_neo4j:
            try:
                backend = Neo4jSessionBackend()
                backend.initialize()
                self._backend = backend
                logger.info("Using Neo4j session backend")
                return backend
            except Exception as e:
                logger.warning(f"Neo4j unavailable, falling back to SQLite: {e}")

        self._backend = SQLiteSessionBackend()
        logger.info("Using SQLite session backend")
        return self._backend

    def _get_cache(self):
        """Get Redis cache if enabled."""
        if not self.config.use_redis_cache:
            return None

        if self._cache is not None:
            return self._cache

        try:
            import redis

            self._cache = redis.from_url(self.config.redis_url)
            self._cache.ping()
            logger.info("Redis cache enabled")
            return self._cache
        except Exception as e:
            logger.warning(f"Redis unavailable: {e}")
            return None

    async def create_session(self, session_id: str | None = None) -> Session:
        """
        Create a new session.

        Args:
            session_id: Optional session ID (generated if not provided)

        Returns:
            New Session instance
        """
        if session_id is None:
            session_id = hashlib.sha256(
                f"{datetime.now(UTC).isoformat()}_{uuid.uuid4()}".encode()
            ).hexdigest()[:16]

        session = Session(
            session_id=session_id,
            backend=self._get_backend(),
            config=self.config,
            cache=self._get_cache(),
        )

        self._sessions[session_id] = session
        logger.info(f"Created session {session_id}")

        return session

    async def get_session(self, session_id: str) -> Session | None:
        """Get an existing session."""
        return self._sessions.get(session_id)

    async def get_recent_context(self, hours: int = 24) -> list[SessionMessage]:
        """
        Get recent context across all sessions.

        Useful for session continuity - recall what was discussed recently.

        Args:
            hours: Look back period in hours

        Returns:
            Recent messages
        """
        return self._get_backend().get_recent_context(hours)

    async def search(self, query: str, limit: int = 10) -> list[SessionMessage]:
        """
        Search across all sessions.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            Matching messages
        """
        return self._get_backend().search(query, limit)


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

_manager: SessionManager | None = None


def get_session_manager(config: SessionConfig | None = None) -> SessionManager:
    """
    Get the global session manager instance.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        SessionManager singleton
    """
    global _manager
    if _manager is None:
        _manager = SessionManager(config)
    return _manager


def reset_session_manager() -> None:
    """Reset the global session manager (for testing)."""
    global _manager
    _manager = None


__all__ = [
    "SessionManager",
    "Session",
    "SessionMessage",
    "SessionSummary",
    "SessionConfig",
    "MessageRole",
    "Neo4jSessionBackend",
    "SQLiteSessionBackend",
    "get_session_manager",
    "reset_session_manager",
]
