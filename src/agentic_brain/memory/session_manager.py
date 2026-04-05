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

import copy
import hashlib
import json
import logging
import math
import re
import statistics
import threading
import uuid
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

logger = logging.getLogger(__name__)


# =============================================================================
# EXPORT FORMAT ENUM
# =============================================================================


class ExportFormat(Enum):
    """Supported export formats."""

    JSON = "json"
    MARKDOWN = "markdown"
    TRAINING_DATA = "training_data"  # OpenAI fine-tuning format
    JSONL = "jsonl"


# =============================================================================
# SESSION TAG
# =============================================================================


@dataclass
class SessionTag:
    """
    Metadata tag for session organization.

    Attributes:
        name: Tag name (e.g., "project", "priority")
        value: Tag value (e.g., "brain-ui", "high")
        created_at: When the tag was added
    """

    name: str
    value: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionTag:
        """Create from dictionary."""
        return cls(
            name=data["name"],
            value=data["value"],
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if isinstance(data.get("created_at"), str)
                else datetime.now(UTC)
            ),
        )


# =============================================================================
# SESSION ANALYTICS
# =============================================================================


@dataclass
class SessionAnalytics:
    """
    Analytics data for a session.

    Attributes:
        session_id: Session identifier
        total_messages: Total message count
        user_messages: User message count
        assistant_messages: Assistant message count
        total_tokens: Total token count
        avg_response_time_ms: Average response time in milliseconds
        topics: Topic clusters with frequency
        entities: Entity frequency map
        sentiment_distribution: Sentiment analysis
        time_distribution: Messages by hour
        response_times: List of response times for percentile calc
    """

    session_id: str
    total_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    total_tokens: int = 0
    avg_response_time_ms: float = 0.0
    topics: dict[str, int] = field(default_factory=dict)
    entities: dict[str, int] = field(default_factory=dict)
    sentiment_distribution: dict[str, float] = field(default_factory=dict)
    time_distribution: dict[int, int] = field(default_factory=dict)
    response_times: list[float] = field(default_factory=list)

    @property
    def p50_response_time(self) -> float:
        """50th percentile response time."""
        if not self.response_times:
            return 0.0
        return statistics.median(self.response_times)

    @property
    def p95_response_time(self) -> float:
        """95th percentile response time."""
        if not self.response_times:
            return 0.0
        if len(self.response_times) < 2:
            return self.response_times[0]
        sorted_times = sorted(self.response_times)
        idx = int(len(sorted_times) * 0.95)
        return sorted_times[min(idx, len(sorted_times) - 1)]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "total_messages": self.total_messages,
            "user_messages": self.user_messages,
            "assistant_messages": self.assistant_messages,
            "total_tokens": self.total_tokens,
            "avg_response_time_ms": self.avg_response_time_ms,
            "p50_response_time_ms": self.p50_response_time,
            "p95_response_time_ms": self.p95_response_time,
            "topics": self.topics,
            "entities": self.entities,
            "sentiment_distribution": self.sentiment_distribution,
            "time_distribution": self.time_distribution,
        }


# =============================================================================
# SEMANTIC SEARCH RESULT
# =============================================================================


@dataclass
class SemanticSearchResult:
    """
    Result from semantic search across sessions.

    Attributes:
        message: The matching message
        score: Relevance score (0.0-1.0)
        highlights: Matching text highlights
        session_context: Context from the session
    """

    message: Any  # SessionMessage, resolved later
    score: float
    highlights: list[str] = field(default_factory=list)
    session_context: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message": self.message.to_dict() if hasattr(self.message, "to_dict") else self.message,
            "score": self.score,
            "highlights": self.highlights,
            "session_context": self.session_context,
        }


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

    def copy(self) -> SessionMessage:
        """Create a deep copy of this message."""
        return SessionMessage(
            id=self.id,
            role=self.role,
            content=self.content,
            timestamp=self.timestamp,
            session_id=self.session_id,
            metadata=copy.deepcopy(self.metadata),
            entities=copy.deepcopy(self.entities),
            importance=self.importance,
            access_count=self.access_count,
            token_count=self.token_count,
        )

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
        parent_session_id: For branched sessions, the parent ID
        branch_point_index: Message index where branch occurred
        merged_from: List of session IDs that were merged into this
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
    parent_session_id: str | None = None
    branch_point_index: int | None = None
    merged_from: list[str] = field(default_factory=list)

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
            "parent_session_id": self.parent_session_id,
            "branch_point_index": self.branch_point_index,
            "merged_from": self.merged_from,
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
            "parent_session_id": self.parent_session_id,
            "branch_point_index": self.branch_point_index,
            "merged_from_json": json.dumps(self.merged_from),
        }


@dataclass
class ReplayConfig:
    """
    Configuration for session replay.

    Attributes:
        modify_system_prompt: New system prompt to use
        modify_temperature: Different temperature setting
        filter_roles: Only replay messages with these roles
        transform_fn: Optional function to transform messages
        skip_indices: Message indices to skip
        inject_messages: Messages to inject at specific indices
    """

    modify_system_prompt: str | None = None
    modify_temperature: float | None = None
    filter_roles: list[str] | None = None
    transform_fn: Callable[[SessionMessage], SessionMessage] | None = None
    skip_indices: list[int] = field(default_factory=list)
    inject_messages: dict[int, list[dict[str, str]]] = field(default_factory=dict)


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
        """Store a single message in Neo4j."""
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

    def store_messages_bulk(self, messages: list[SessionMessage]) -> int:
        """Store multiple messages in a single batch UNWIND operation.

        Returns the number of messages attempted to store.
        """
        if not messages:
            return 0
        self.initialize()
        payload = [
            {
                "id": m.id,
                "role": m.role.value,
                "content": m.content,
                "timestamp": m.timestamp.isoformat(),
                "session_id": m.session_id,
                "importance": m.importance,
                "access_count": m.access_count,
                "metadata": json.dumps(m.metadata),
                "entities_json": json.dumps(m.entities),
            }
            for m in messages
        ]
        try:
            with self._get_session() as session:
                session.run(
                    """
                    UNWIND $rows AS r
                    MERGE (m:SessionMessage {id: r.id})
                    SET m.role = r.role,
                        m.content = r.content,
                        m.timestamp = datetime(r.timestamp),
                        m.session_id = r.session_id,
                        m.importance = r.importance,
                        m.access_count = r.access_count,
                        m.metadata = r.metadata,
                        m.entities_json = r.entities_json
                    """,
                    rows=payload,
                )
            return len(payload)
        except Exception as e:
            logger.error(f"Failed to store messages bulk in Neo4j: {e}")
            return 0

    def get_messages(
        self,
        session_id: str,
        page: int = 0,
        page_size: int | None = None,
        include_content: bool = True,
    ) -> list[SessionMessage]:
        """Get messages for a session with pagination and optional lazy content loading.

        Args:
            session_id: Session identifier
            page: Zero-based page index
            page_size: Number of messages per page (None => use limit param or return all)
            include_content: If False only load metadata (id, role, timestamp)
        """
        self.initialize()
        messages: list[SessionMessage] = []
        try:
            with self._get_session() as session:
                fields = "m.id AS id, m.role AS role, m.timestamp AS timestamp, m.session_id AS session_id, m.importance AS importance, m.access_count AS access_count"
                if include_content:
                    fields += ", m.content AS content, m.metadata AS metadata, m.entities_json AS entities_json"

                query = f"""
                    MATCH (m:SessionMessage {{session_id: $session_id}})
                    RETURN {fields}
                    ORDER BY m.timestamp DESC
                """

                params: dict = {"session_id": session_id}
                if page_size:
                    params["skip"] = page * page_size
                    params["limit"] = page_size
                    query += " SKIP $skip LIMIT $limit"

                result = session.run(query, **params)
                for record in result:
                    ts = record["timestamp"].to_native() if hasattr(record["timestamp"], "to_native") else record["timestamp"]
                    msg = SessionMessage(
                        id=record["id"],
                        role=MessageRole(record["role"]),
                        content=record.get("content", "") if include_content else "",
                        timestamp=ts,
                        session_id=record["session_id"],
                        importance=record.get("importance", 0.5),
                        access_count=record.get("access_count", 0),
                        metadata=json.loads(record.get("metadata") or "{}") if include_content else {},
                        entities=json.loads(record.get("entities_json") or "[]") if include_content else [],
                    )
                    messages.append(msg)
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
        parent_session_id: str | None = None,
        branch_point_index: int | None = None,
    ):
        """Initialize session."""
        self.session_id = session_id
        self.backend = backend
        self.config = config
        self.cache = cache
        self._messages: list[SessionMessage] = []
        self._started_at = datetime.now(UTC)
        self._entity_patterns = [re.compile(p) for p in config.entity_patterns]
        self._session_metadata: dict[str, Any] = {
            "tags": [],
            "parent_session_id": parent_session_id,
            "branch_point_index": branch_point_index,
            "merged_from": [],
        }

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

    # =========================================================================
    # ADVANCED FEATURES: Tagging
    # =========================================================================

    def add_tag(self, name: str, value: str) -> SessionTag:
        """
        Add a metadata tag to the session.

        Args:
            name: Tag name (e.g., "project", "priority")
            value: Tag value (e.g., "brain-ui", "high")

        Returns:
            The created SessionTag
        """
        tag = SessionTag(name=name, value=value)
        if "tags" not in self._session_metadata:
            self._session_metadata["tags"] = []
        self._session_metadata["tags"].append(tag.to_dict())
        return tag

    def get_tags(self) -> list[SessionTag]:
        """Get all tags for this session."""
        tags_data = self._session_metadata.get("tags", [])
        return [SessionTag.from_dict(t) for t in tags_data]

    def remove_tag(self, name: str, value: str | None = None) -> int:
        """
        Remove tag(s) from the session.

        Args:
            name: Tag name to remove
            value: Optional specific value (removes all with name if None)

        Returns:
            Number of tags removed
        """
        if "tags" not in self._session_metadata:
            return 0

        initial_count = len(self._session_metadata["tags"])
        if value is None:
            self._session_metadata["tags"] = [
                t for t in self._session_metadata["tags"] if t["name"] != name
            ]
        else:
            self._session_metadata["tags"] = [
                t for t in self._session_metadata["tags"]
                if not (t["name"] == name and t["value"] == value)
            ]
        return initial_count - len(self._session_metadata["tags"])

    def has_tag(self, name: str, value: str | None = None) -> bool:
        """Check if session has a specific tag."""
        for tag in self._session_metadata.get("tags", []):
            if tag["name"] == name:
                if value is None or tag["value"] == value:
                    return True
        return False

    # =========================================================================
    # ADVANCED FEATURES: Analytics
    # =========================================================================

    def get_analytics(self) -> SessionAnalytics:
        """
        Generate analytics for this session.

        Returns:
            SessionAnalytics with token usage, response times, topic clustering
        """
        analytics = SessionAnalytics(session_id=self.session_id)
        analytics.total_messages = len(self._messages)

        response_times = []
        prev_user_time = None
        entity_counts: Counter = Counter()
        topic_words: Counter = Counter()
        hour_distribution: Counter = Counter()

        for i, msg in enumerate(self._messages):
            # Count by role
            if msg.role == MessageRole.USER:
                analytics.user_messages += 1
                prev_user_time = msg.timestamp
            elif msg.role == MessageRole.ASSISTANT:
                analytics.assistant_messages += 1
                # Calculate response time
                if prev_user_time:
                    delta = (msg.timestamp - prev_user_time).total_seconds() * 1000
                    response_times.append(delta)
                    prev_user_time = None

            # Token count
            analytics.total_tokens += msg.token_count

            # Entity frequency
            for entity in msg.entities:
                entity_counts[entity["text"]] += 1

            # Topic extraction (simple word frequency)
            words = re.findall(r"\b[a-zA-Z]{4,}\b", msg.content.lower())
            topic_words.update(words)

            # Time distribution
            hour_distribution[msg.timestamp.hour] += 1

        # Calculate averages and distributions
        analytics.response_times = response_times
        if response_times:
            analytics.avg_response_time_ms = sum(response_times) / len(response_times)

        # Top entities
        analytics.entities = dict(entity_counts.most_common(20))

        # Top topics (filter common words)
        common_words = {"this", "that", "with", "have", "from", "what", "your", "they", "will", "been", "when", "were"}
        analytics.topics = {
            word: count for word, count in topic_words.most_common(30)
            if word not in common_words
        }

        # Time distribution
        analytics.time_distribution = dict(hour_distribution)

        return analytics

    # =========================================================================
    # ADVANCED FEATURES: Export
    # =========================================================================

    def export(self, format: ExportFormat = ExportFormat.JSON) -> str:
        """
        Export session to various formats.

        Args:
            format: Export format (JSON, MARKDOWN, TRAINING_DATA, JSONL)

        Returns:
            Exported content as string
        """
        if format == ExportFormat.JSON:
            return self._export_json()
        elif format == ExportFormat.MARKDOWN:
            return self._export_markdown()
        elif format == ExportFormat.TRAINING_DATA:
            return self._export_training_data()
        elif format == ExportFormat.JSONL:
            return self._export_jsonl()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def _export_json(self) -> str:
        """Export to JSON format."""
        data = {
            "session_id": self.session_id,
            "started_at": self._started_at.isoformat(),
            "message_count": len(self._messages),
            "metadata": self._session_metadata,
            "messages": [msg.to_dict() for msg in self._messages],
        }
        return json.dumps(data, indent=2)

    def _export_markdown(self) -> str:
        """Export to Markdown format for documentation."""
        lines = [
            f"# Session: {self.session_id}",
            f"",
            f"**Started**: {self._started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Messages**: {len(self._messages)}",
            f"",
            "---",
            "",
        ]

        # Add tags if present
        tags = self.get_tags()
        if tags:
            lines.append("## Tags")
            for tag in tags:
                lines.append(f"- **{tag.name}**: {tag.value}")
            lines.extend(["", "---", ""])

        # Add conversation
        lines.append("## Conversation")
        lines.append("")

        for msg in self._messages:
            role_emoji = {
                MessageRole.USER: "👤",
                MessageRole.ASSISTANT: "🤖",
                MessageRole.SYSTEM: "⚙️",
                MessageRole.TOOL: "🔧",
            }.get(msg.role, "❓")

            timestamp = msg.timestamp.strftime("%H:%M:%S")
            lines.append(f"### {role_emoji} {msg.role.value.title()} ({timestamp})")
            lines.append("")
            lines.append(msg.content)
            lines.append("")

        return "\n".join(lines)

    def _export_training_data(self) -> str:
        """Export to OpenAI fine-tuning format."""
        conversations = []
        current_conversation = {"messages": []}

        for msg in self._messages:
            current_conversation["messages"].append({
                "role": msg.role.value,
                "content": msg.content,
            })

        if current_conversation["messages"]:
            conversations.append(current_conversation)

        return "\n".join(json.dumps(conv) for conv in conversations)

    def _export_jsonl(self) -> str:
        """Export to JSON Lines format."""
        lines = []
        for msg in self._messages:
            lines.append(json.dumps(msg.to_dict()))
        return "\n".join(lines)

    # =========================================================================
    # ADVANCED FEATURES: Compression
    # =========================================================================

    async def compress(
        self,
        target_tokens: int | None = None,
        keep_important: bool = True,
        summarize_fn: Callable[[list[SessionMessage]], str] | None = None,
    ) -> tuple[int, int]:
        """
        Intelligently compress session to reduce token count.

        Args:
            target_tokens: Target token count (defaults to 50% reduction)
            keep_important: Keep high-importance messages intact
            summarize_fn: Custom summarization function (uses default if None)

        Returns:
            Tuple of (original_tokens, new_tokens)
        """
        original_tokens = sum(msg.token_count for msg in self._messages)
        target_tokens = target_tokens or (original_tokens // 2)

        if original_tokens <= target_tokens:
            return (original_tokens, original_tokens)

        # Sort messages by importance (keep important ones)
        if keep_important:
            important_threshold = 0.7
            important_msgs = [m for m in self._messages if m.effective_importance >= important_threshold]
            compressible_msgs = [m for m in self._messages if m.effective_importance < important_threshold]
        else:
            important_msgs = []
            compressible_msgs = list(self._messages)

        important_tokens = sum(m.token_count for m in important_msgs)

        # If important messages alone exceed target, just keep them
        if important_tokens >= target_tokens:
            self._messages = sorted(important_msgs, key=lambda m: m.timestamp)
            new_tokens = sum(m.token_count for m in self._messages)
            return (original_tokens, new_tokens)

        # Compress the compressible messages
        remaining_budget = target_tokens - important_tokens

        if summarize_fn and compressible_msgs:
            summary_text = summarize_fn(compressible_msgs)
        else:
            # Default summarization: extract key points
            summary_text = self._default_summarize(compressible_msgs)

        # Create summary message
        summary_msg = SessionMessage(
            id=f"summary_{uuid.uuid4().hex[:8]}",
            role=MessageRole.SYSTEM,
            content=f"[COMPRESSED CONTEXT]\n{summary_text}",
            timestamp=compressible_msgs[0].timestamp if compressible_msgs else datetime.now(UTC),
            session_id=self.session_id,
            metadata={"compressed": True, "original_count": len(compressible_msgs)},
            importance=0.6,
        )

        # Rebuild messages: summary + important messages
        self._messages = [summary_msg] + sorted(important_msgs, key=lambda m: m.timestamp)
        new_tokens = sum(m.token_count for m in self._messages)

        logger.info(f"Compressed session {self.session_id}: {original_tokens} -> {new_tokens} tokens")
        return (original_tokens, new_tokens)

    def _default_summarize(self, messages: list[SessionMessage]) -> str:
        """Default summarization for compression."""
        if not messages:
            return "No messages to summarize."

        # Extract key information
        entities = set()
        key_points = []

        for msg in messages:
            for entity in msg.entities:
                entities.add(entity["text"])

            # Extract potential key points (sentences with keywords)
            if msg.importance >= 0.6:
                sentences = re.split(r'[.!?]+', msg.content)
                for sentence in sentences[:2]:  # First 2 sentences of important messages
                    if len(sentence.strip()) > 20:
                        key_points.append(sentence.strip())

        summary_parts = [
            f"Context from {len(messages)} messages.",
        ]

        if entities:
            summary_parts.append(f"Entities: {', '.join(list(entities)[:10])}.")

        if key_points:
            summary_parts.append("Key points:")
            for point in key_points[:5]:
                summary_parts.append(f"- {point}")

        return "\n".join(summary_parts)

    # =========================================================================
    # ADVANCED FEATURES: Get Messages (for branching/replay)
    # =========================================================================

    def get_messages(self, start_index: int = 0, end_index: int | None = None) -> list[SessionMessage]:
        """
        Get messages from the session.

        Args:
            start_index: Start index (inclusive)
            end_index: End index (exclusive), None for all

        Returns:
            List of SessionMessage
        """
        if end_index is None:
            return self._messages[start_index:]
        return self._messages[start_index:end_index]

    @property
    def message_count(self) -> int:
        """Get total message count."""
        return len(self._messages)

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
            parent_session_id=self._session_metadata.get("parent_session_id"),
            branch_point_index=self._session_metadata.get("branch_point_index"),
            merged_from=self._session_metadata.get("merged_from", []),
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

    # =========================================================================
    # ADVANCED FEATURES: Session Branching
    # =========================================================================

    async def branch_session(
        self,
        source_session_id: str,
        branch_at_index: int | None = None,
        new_session_id: str | None = None,
    ) -> Session:
        """
        Create a branch (fork) of an existing session for A/B testing.

        Args:
            source_session_id: Session to branch from
            branch_at_index: Message index to branch at (None = branch at current point)
            new_session_id: Optional ID for new session

        Returns:
            New branched Session

        Raises:
            ValueError: If source session not found
        """
        source_session = self._sessions.get(source_session_id)
        if source_session is None:
            raise ValueError(f"Source session not found: {source_session_id}")

        # Generate new session ID
        if new_session_id is None:
            new_session_id = hashlib.sha256(
                f"branch_{source_session_id}_{datetime.now(UTC)}_{uuid.uuid4()}".encode()
            ).hexdigest()[:16]

        # Determine branch point
        if branch_at_index is None:
            branch_at_index = len(source_session._messages)

        # Create new session with branch metadata
        branched_session = Session(
            session_id=new_session_id,
            backend=self._get_backend(),
            config=self.config,
            cache=self._get_cache(),
            parent_session_id=source_session_id,
            branch_point_index=branch_at_index,
        )

        # Copy messages up to branch point
        for msg in source_session.get_messages(0, branch_at_index):
            # Create a copy with new session ID
            copied_msg = msg.copy()
            copied_msg.session_id = new_session_id
            copied_msg.id = f"branch_{msg.id}"
            branched_session._messages.append(copied_msg)

        # Copy tags from source session
        branched_session._session_metadata["tags"] = copy.deepcopy(
            source_session._session_metadata.get("tags", [])
        )

        self._sessions[new_session_id] = branched_session
        logger.info(f"Branched session {source_session_id} at index {branch_at_index} -> {new_session_id}")

        return branched_session

    # =========================================================================
    # ADVANCED FEATURES: Session Merging
    # =========================================================================

    async def merge_sessions(
        self,
        session_ids: list[str],
        strategy: str = "interleave",
        new_session_id: str | None = None,
    ) -> Session:
        """
        Merge multiple sessions into one.

        Args:
            session_ids: List of session IDs to merge
            strategy: Merge strategy:
                - "interleave": Interleave by timestamp
                - "concatenate": Append sessions in order
                - "deduplicate": Remove duplicate messages
            new_session_id: Optional ID for merged session

        Returns:
            New merged Session

        Raises:
            ValueError: If any session not found or less than 2 sessions
        """
        if len(session_ids) < 2:
            raise ValueError("Need at least 2 sessions to merge")

        sessions = []
        for sid in session_ids:
            session = self._sessions.get(sid)
            if session is None:
                raise ValueError(f"Session not found: {sid}")
            sessions.append(session)

        # Generate new session ID
        if new_session_id is None:
            new_session_id = hashlib.sha256(
                f"merge_{'_'.join(session_ids)}_{datetime.now(UTC)}".encode()
            ).hexdigest()[:16]

        # Create merged session
        merged_session = Session(
            session_id=new_session_id,
            backend=self._get_backend(),
            config=self.config,
            cache=self._get_cache(),
        )
        merged_session._session_metadata["merged_from"] = session_ids

        # Collect all messages
        all_messages = []
        for session in sessions:
            for msg in session._messages:
                copied_msg = msg.copy()
                copied_msg.session_id = new_session_id
                all_messages.append(copied_msg)

        # Apply merge strategy
        if strategy == "interleave":
            all_messages.sort(key=lambda m: m.timestamp)
        elif strategy == "concatenate":
            pass  # Already in order from collecting
        elif strategy == "deduplicate":
            all_messages.sort(key=lambda m: m.timestamp)
            seen_content = set()
            deduplicated = []
            for msg in all_messages:
                content_hash = hashlib.sha256(msg.content.encode()).hexdigest()
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    deduplicated.append(msg)
            all_messages = deduplicated
        else:
            raise ValueError(f"Unknown merge strategy: {strategy}")

        merged_session._messages = all_messages

        # Merge tags from all sessions
        all_tags = []
        seen_tags = set()
        for session in sessions:
            for tag in session._session_metadata.get("tags", []):
                tag_key = (tag["name"], tag["value"])
                if tag_key not in seen_tags:
                    seen_tags.add(tag_key)
                    all_tags.append(tag)
        merged_session._session_metadata["tags"] = all_tags

        self._sessions[new_session_id] = merged_session
        logger.info(f"Merged sessions {session_ids} -> {new_session_id} using strategy '{strategy}'")

        return merged_session

    # =========================================================================
    # ADVANCED FEATURES: Session Replay
    # =========================================================================

    async def replay_session(
        self,
        source_session_id: str,
        replay_config: ReplayConfig | None = None,
        new_session_id: str | None = None,
    ) -> Session:
        """
        Replay a session with different parameters.

        Args:
            source_session_id: Session to replay
            replay_config: Configuration for replay modifications
            new_session_id: Optional ID for replay session

        Returns:
            New Session with replayed messages

        Raises:
            ValueError: If source session not found
        """
        source_session = self._sessions.get(source_session_id)
        if source_session is None:
            raise ValueError(f"Source session not found: {source_session_id}")

        replay_config = replay_config or ReplayConfig()

        # Generate new session ID
        if new_session_id is None:
            new_session_id = hashlib.sha256(
                f"replay_{source_session_id}_{datetime.now(UTC)}_{uuid.uuid4()}".encode()
            ).hexdigest()[:16]

        # Create replay session
        replay_session = Session(
            session_id=new_session_id,
            backend=self._get_backend(),
            config=self.config,
            cache=self._get_cache(),
        )
        replay_session._session_metadata["replayed_from"] = source_session_id
        replay_session._session_metadata["replay_config"] = {
            "modify_system_prompt": replay_config.modify_system_prompt,
            "modify_temperature": replay_config.modify_temperature,
            "filter_roles": replay_config.filter_roles,
            "skip_indices": replay_config.skip_indices,
        }

        # Process messages
        for idx, msg in enumerate(source_session._messages):
            # Skip if in skip list
            if idx in replay_config.skip_indices:
                continue

            # Filter by role
            if replay_config.filter_roles and msg.role.value not in replay_config.filter_roles:
                continue

            # Inject messages before this index
            if idx in replay_config.inject_messages:
                for inject_msg in replay_config.inject_messages[idx]:
                    injected = SessionMessage(
                        id=f"inject_{uuid.uuid4().hex[:8]}",
                        role=MessageRole(inject_msg.get("role", "system")),
                        content=inject_msg["content"],
                        timestamp=msg.timestamp - timedelta(milliseconds=1),
                        session_id=new_session_id,
                        metadata={"injected": True},
                        importance=0.5,
                    )
                    replay_session._messages.append(injected)

            # Copy and potentially transform message
            copied_msg = msg.copy()
            copied_msg.session_id = new_session_id
            copied_msg.id = f"replay_{msg.id}"

            # Apply transform function if provided
            if replay_config.transform_fn:
                copied_msg = replay_config.transform_fn(copied_msg)

            # Modify system prompt if requested
            if (
                replay_config.modify_system_prompt
                and copied_msg.role == MessageRole.SYSTEM
                and idx == 0
            ):
                copied_msg.content = replay_config.modify_system_prompt

            replay_session._messages.append(copied_msg)

        self._sessions[new_session_id] = replay_session
        logger.info(f"Replayed session {source_session_id} -> {new_session_id}")

        return replay_session

    # =========================================================================
    # ADVANCED FEATURES: Cross-Session Semantic Search
    # =========================================================================

    async def semantic_search(
        self,
        query: str,
        limit: int = 10,
        session_ids: list[str] | None = None,
        min_score: float = 0.0,
        include_context: bool = True,
    ) -> list[SemanticSearchResult]:
        """
        Perform semantic search across sessions.

        Args:
            query: Search query
            limit: Maximum results
            session_ids: Optional list of sessions to search (None = all)
            min_score: Minimum relevance score (0.0-1.0)
            include_context: Include surrounding context in results

        Returns:
            List of SemanticSearchResult
        """
        # Get messages to search
        if session_ids:
            all_messages = []
            for sid in session_ids:
                session = self._sessions.get(sid)
                if session:
                    all_messages.extend(session._messages)
        else:
            all_messages = []
            for session in self._sessions.values():
                all_messages.extend(session._messages)

        # Also search backend for historical messages
        backend_results = self._get_backend().search(query, limit * 2)
        all_messages.extend(backend_results)

        # Deduplicate by ID
        seen_ids = set()
        unique_messages = []
        for msg in all_messages:
            if msg.id not in seen_ids:
                seen_ids.add(msg.id)
                unique_messages.append(msg)

        # Score messages (simple keyword matching - would use embeddings in production)
        results = []
        query_lower = query.lower()
        query_words = set(re.findall(r"\b\w+\b", query_lower))

        for msg in unique_messages:
            content_lower = msg.content.lower()
            content_words = set(re.findall(r"\b\w+\b", content_lower))

            # Calculate score based on word overlap and position
            overlap = len(query_words & content_words)
            if overlap == 0:
                continue

            # Basic TF-IDF-like scoring
            score = overlap / max(len(query_words), 1)

            # Boost for exact phrase match
            if query_lower in content_lower:
                score += 0.3

            # Boost for importance
            score += msg.effective_importance * 0.1

            score = min(1.0, score)

            if score >= min_score:
                # Extract highlights
                highlights = []
                for word in query_words:
                    pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
                    matches = pattern.findall(msg.content)
                    highlights.extend(matches)

                # Get context if requested
                context = ""
                if include_context:
                    session = self._sessions.get(msg.session_id)
                    if session:
                        idx = next(
                            (i for i, m in enumerate(session._messages) if m.id == msg.id),
                            -1
                        )
                        if idx > 0:
                            context = session._messages[idx - 1].content[:100] + "..."

                results.append(SemanticSearchResult(
                    message=msg,
                    score=score,
                    highlights=highlights[:5],
                    session_context=context,
                ))

        # Sort by score and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    # =========================================================================
    # ADVANCED FEATURES: Session Analytics (Aggregate)
    # =========================================================================

    async def get_aggregate_analytics(
        self,
        session_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Get aggregate analytics across multiple sessions.

        Args:
            session_ids: Sessions to analyze (None = all active sessions)

        Returns:
            Aggregate analytics dictionary
        """
        if session_ids is None:
            session_ids = list(self._sessions.keys())

        total_messages = 0
        total_tokens = 0
        all_topics: Counter = Counter()
        all_entities: Counter = Counter()
        all_response_times: list[float] = []

        for sid in session_ids:
            session = self._sessions.get(sid)
            if session:
                analytics = session.get_analytics()
                total_messages += analytics.total_messages
                total_tokens += analytics.total_tokens
                all_topics.update(analytics.topics)
                all_entities.update(analytics.entities)
                all_response_times.extend(analytics.response_times)

        return {
            "session_count": len(session_ids),
            "total_messages": total_messages,
            "total_tokens": total_tokens,
            "avg_messages_per_session": total_messages / max(len(session_ids), 1),
            "top_topics": dict(all_topics.most_common(20)),
            "top_entities": dict(all_entities.most_common(20)),
            "avg_response_time_ms": (
                sum(all_response_times) / len(all_response_times)
                if all_response_times else 0.0
            ),
            "p50_response_time_ms": (
                statistics.median(all_response_times)
                if all_response_times else 0.0
            ),
            "p95_response_time_ms": (
                sorted(all_response_times)[int(len(all_response_times) * 0.95)]
                if len(all_response_times) >= 2 else 0.0
            ),
        }

    # =========================================================================
    # ADVANCED FEATURES: List Sessions with Filtering
    # =========================================================================

    def list_sessions(
        self,
        tag_filter: dict[str, str] | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """
        List session IDs with optional filtering.

        Args:
            tag_filter: Filter by tags (e.g., {"project": "brain-ui"})
            limit: Maximum sessions to return

        Returns:
            List of session IDs
        """
        results = []

        for session_id, session in self._sessions.items():
            if tag_filter:
                match = True
                for name, value in tag_filter.items():
                    if not session.has_tag(name, value):
                        match = False
                        break
                if not match:
                    continue

            results.append(session_id)

            if limit and len(results) >= limit:
                break

        return results


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
    # Core classes
    "SessionManager",
    "Session",
    "SessionMessage",
    "SessionSummary",
    "SessionConfig",
    "MessageRole",
    # Backends
    "Neo4jSessionBackend",
    "SQLiteSessionBackend",
    # Advanced features
    "SessionTag",
    "SessionAnalytics",
    "SemanticSearchResult",
    "ExportFormat",
    "ReplayConfig",
    # Factory functions
    "get_session_manager",
    "reset_session_manager",
]
