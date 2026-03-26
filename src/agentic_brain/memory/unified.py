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
Unified Memory System
=====================

4-type memory architecture with graceful fallbacks:
1. Session memory (conversation context)
2. Long-term memory (Neo4j knowledge graph / SQLite fallback)
3. Semantic memory (vector embeddings for similarity search)
4. Episodic memory (event sourcing / timeline)

Works without external dependencies (Neo4j, vector DBs) by using SQLite.

Example:
    >>> from agentic_brain.memory import UnifiedMemory
    >>> mem = UnifiedMemory()  # Works with defaults (SQLite)
    >>> mem.store("user likes Python")
    >>> results = mem.search("programming preferences")
    >>> print(results[0].content)
    'user likes Python'
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Protocol, Union

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Type of memory entry."""

    SESSION = "session"  # Conversation context
    LONG_TERM = "long_term"  # Persistent knowledge
    SEMANTIC = "semantic"  # Vector-indexed for similarity
    EPISODIC = "episodic"  # Event timeline


@dataclass
class MemoryEntry:
    """
    A single memory entry.

    Attributes:
        id: Unique identifier
        content: Text content
        memory_type: Type of memory
        timestamp: When created
        metadata: Additional data
        embedding: Vector embedding (for semantic search)
        session_id: Session this belongs to (for session memory)
        score: Relevance score (set during search)
    """

    id: str
    content: str
    memory_type: MemoryType
    timestamp: datetime
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    session_id: Optional[str] = None
    score: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "session_id": self.session_id,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data.get("memory_type", "long_term")),
            timestamp=(
                datetime.fromisoformat(data["timestamp"])
                if isinstance(data.get("timestamp"), str)
                else data.get("timestamp", datetime.now(UTC))
            ),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
            session_id=data.get("session_id"),
            score=data.get("score", 0.0),
        )


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for batch of texts."""
        ...

    @property
    def dimension(self) -> int:
        """Embedding dimension."""
        ...


class SimpleHashEmbedding:
    """
    Simple hash-based embeddings (no ML dependencies).

    Uses character n-grams hashed to fixed positions.
    Not as good as transformer embeddings, but works offline.
    """

    def __init__(self, dimension: int = 384):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> list[float]:
        """Generate embedding using hash-based approach."""
        text = text.lower().strip()
        vector = [0.0] * self._dimension

        # Use character n-grams (2-4 chars)
        for n in range(2, 5):
            for i in range(len(text) - n + 1):
                ngram = text[i : i + n]
                # Hash to position
                h = hash(ngram) % self._dimension
                # Use second hash for value
                val = (hash(ngram + "val") % 1000) / 1000.0
                vector[h] += val

        # Normalize
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]

        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for batch."""
        return [self.embed(t) for t in texts]


class SQLiteMemoryStore:
    """
    SQLite-based memory storage (works without external deps).

    Stores all 4 memory types with full-text search and
    basic vector similarity (using hash embeddings).
    """

    def __init__(
        self,
        db_path: str = "~/.agentic_brain/memory.db",
        embedder: Optional[EmbeddingProvider] = None,
    ):
        """
        Initialize SQLite store.

        Args:
            db_path: Path to SQLite database
            embedder: Embedding provider (defaults to SimpleHashEmbedding)
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedder = embedder or SimpleHashEmbedding()
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                embedding TEXT,
                session_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_memory_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_session_id ON memories(session_id);
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp);

            -- Full-text search
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content,
                content='memories',
                content_rowid='rowid'
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content)
                SELECT rowid, content FROM memories WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid = OLD.rowid;
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid = OLD.rowid;
                INSERT INTO memories_fts(rowid, content)
                SELECT rowid, content FROM memories WHERE id = NEW.id;
            END;

            -- Session context table
            CREATE TABLE IF NOT EXISTS session_context (
                session_id TEXT PRIMARY KEY,
                messages TEXT,
                summary TEXT,
                created_at TEXT,
                updated_at TEXT
            );

            -- Event timeline for episodic memory
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                data TEXT,
                timestamp TEXT NOT NULL,
                session_id TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_event_type ON events(event_type);
            CREATE INDEX IF NOT EXISTS idx_event_time ON events(timestamp);
        """
        )
        conn.commit()

    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
        memory_id: Optional[str] = None,
    ) -> MemoryEntry:
        """
        Store a memory.

        Args:
            content: Text content to store
            memory_type: Type of memory
            metadata: Additional metadata
            session_id: Session ID for session memory
            memory_id: Optional custom ID

        Returns:
            Created MemoryEntry
        """
        conn = self._get_conn()

        # Generate ID if not provided
        if not memory_id:
            memory_id = hashlib.sha256(
                f"{content}:{datetime.now(UTC).isoformat()}".encode()
            ).hexdigest()[:16]

        timestamp = datetime.now(UTC)

        # Generate embedding for semantic memory
        embedding = None
        if memory_type in (MemoryType.SEMANTIC, MemoryType.LONG_TERM):
            embedding = self.embedder.embed(content)

        entry = MemoryEntry(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            timestamp=timestamp,
            metadata=metadata or {},
            embedding=embedding,
            session_id=session_id,
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO memories
            (id, content, memory_type, timestamp, metadata, embedding, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry.id,
                entry.content,
                entry.memory_type.value,
                entry.timestamp.isoformat(),
                json.dumps(entry.metadata),
                json.dumps(embedding) if embedding else None,
                entry.session_id,
            ),
        )
        conn.commit()

        logger.debug(f"Stored memory {entry.id}: {content[:50]}...")
        return entry

    def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        use_semantic: bool = True,
    ) -> list[MemoryEntry]:
        """
        Search memories using hybrid text + semantic search.

        Args:
            query: Search query
            memory_type: Filter by type
            session_id: Filter by session
            limit: Max results
            use_semantic: Use semantic similarity

        Returns:
            List of matching MemoryEntry objects
        """
        conn = self._get_conn()
        results = []

        # Full-text search
        fts_query = """
            SELECT m.*, rank
            FROM memories_fts fts
            JOIN memories m ON fts.rowid = m.rowid
            WHERE memories_fts MATCH ?
        """
        params: list = [query]

        if memory_type:
            fts_query += " AND m.memory_type = ?"
            params.append(memory_type.value)

        if session_id:
            fts_query += " AND m.session_id = ?"
            params.append(session_id)

        fts_query += " ORDER BY rank LIMIT ?"
        params.append(limit * 2)  # Get more for re-ranking

        try:
            cursor = conn.execute(fts_query, params)
            for row in cursor:
                entry = self._row_to_entry(row)
                # FTS rank is negative (lower = better)
                entry.score = -row["rank"] if row["rank"] else 0.5
                results.append(entry)
        except sqlite3.OperationalError:
            # FTS query syntax error - fall back to LIKE
            logger.debug("FTS query failed, using LIKE search")
            results = self._like_search(query, memory_type, session_id, limit)

        # Semantic re-ranking if enabled and we have results
        if use_semantic and results:
            query_embedding = self.embedder.embed(query)
            results = self._semantic_rerank(results, query_embedding)

        # If no results from FTS, try semantic search directly
        if not results and use_semantic:
            results = self._semantic_search(query, memory_type, session_id, limit)

        return results[:limit]

    def _like_search(
        self,
        query: str,
        memory_type: Optional[MemoryType],
        session_id: Optional[str],
        limit: int,
    ) -> list[MemoryEntry]:
        """Fallback LIKE search."""
        conn = self._get_conn()
        sql = "SELECT * FROM memories WHERE content LIKE ?"
        params: list = [f"%{query}%"]

        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)

        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        results = []
        for row in conn.execute(sql, params):
            entry = self._row_to_entry(row)
            entry.score = 0.5  # Default score for LIKE matches
            results.append(entry)

        return results

    def _semantic_search(
        self,
        query: str,
        memory_type: Optional[MemoryType],
        session_id: Optional[str],
        limit: int,
    ) -> list[MemoryEntry]:
        """Pure semantic search using embeddings."""
        conn = self._get_conn()
        query_embedding = self.embedder.embed(query)

        sql = "SELECT * FROM memories WHERE embedding IS NOT NULL"
        params: list = []

        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)

        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)

        results = []
        for row in conn.execute(sql, params):
            entry = self._row_to_entry(row)
            if entry.embedding:
                entry.score = self._cosine_similarity(query_embedding, entry.embedding)
                results.append(entry)

        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _semantic_rerank(
        self, results: list[MemoryEntry], query_embedding: list[float]
    ) -> list[MemoryEntry]:
        """Re-rank results using semantic similarity."""
        for entry in results:
            if entry.embedding:
                semantic_score = self._cosine_similarity(
                    query_embedding, entry.embedding
                )
                # Combine FTS score with semantic score
                entry.score = 0.5 * entry.score + 0.5 * semantic_score

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between vectors."""
        dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert SQLite row to MemoryEntry."""
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            session_id=row["session_id"],
        )

    def get_recent(
        self,
        memory_type: Optional[MemoryType] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        hours: Optional[int] = None,
    ) -> list[MemoryEntry]:
        """Get recent memories."""
        conn = self._get_conn()

        sql = "SELECT * FROM memories WHERE 1=1"
        params: list = []

        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type.value)

        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)

        if hours:
            cutoff = datetime.now(UTC) - timedelta(hours=hours)
            sql += " AND timestamp >= ?"
            params.append(cutoff.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        results = []
        for row in conn.execute(sql, params):
            results.append(self._row_to_entry(row))

        return results

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID."""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        return cursor.rowcount > 0

    def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count memories."""
        conn = self._get_conn()

        if memory_type:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE memory_type = ?",
                (memory_type.value,),
            )
        else:
            cursor = conn.execute("SELECT COUNT(*) FROM memories")

        return cursor.fetchone()[0]

    # Session context methods

    def save_session_context(
        self, session_id: str, messages: list[dict], summary: Optional[str] = None
    ) -> None:
        """Save session context (conversation history)."""
        conn = self._get_conn()
        now = datetime.now(UTC).isoformat()

        conn.execute(
            """
            INSERT OR REPLACE INTO session_context
            (session_id, messages, summary, created_at, updated_at)
            VALUES (?, ?, ?, COALESCE(
                (SELECT created_at FROM session_context WHERE session_id = ?),
                ?
            ), ?)
        """,
            (
                session_id,
                json.dumps(messages),
                summary,
                session_id,
                now,
                now,
            ),
        )
        conn.commit()

    def get_session_context(self, session_id: str) -> Optional[dict]:
        """Get session context."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM session_context WHERE session_id = ?", (session_id,)
        )
        row = cursor.fetchone()
        if row:
            return {
                "session_id": row["session_id"],
                "messages": json.loads(row["messages"]) if row["messages"] else [],
                "summary": row["summary"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        return None

    # Event/episodic memory methods

    def record_event(
        self,
        event_type: str,
        data: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Record an event for episodic memory."""
        conn = self._get_conn()
        event_id = hashlib.sha256(
            f"{event_type}:{datetime.now(UTC).isoformat()}".encode()
        ).hexdigest()[:16]

        conn.execute(
            """
            INSERT INTO events (id, event_type, data, timestamp, session_id)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                event_id,
                event_type,
                json.dumps(data) if data else None,
                datetime.now(UTC).isoformat(),
                session_id,
            ),
        )
        conn.commit()
        return event_id

    def get_events(
        self,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get events from episodic memory."""
        conn = self._get_conn()

        sql = "SELECT * FROM events WHERE 1=1"
        params: list = []

        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)

        if session_id:
            sql += " AND session_id = ?"
            params.append(session_id)

        if since:
            sql += " AND timestamp >= ?"
            params.append(since.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        events = []
        for row in conn.execute(sql, params):
            events.append(
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "data": json.loads(row["data"]) if row["data"] else None,
                    "timestamp": row["timestamp"],
                    "session_id": row["session_id"],
                }
            )

        return events

    def close(self) -> None:
        """Close connection."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn


class UnifiedMemory:
    """
    Unified memory system with 4-type architecture.

    Works WITHOUT external dependencies (uses SQLite by default).
    Can optionally use Neo4j and vector DBs if available.

    Memory Types:
        - SESSION: Conversation context within a session
        - LONG_TERM: Persistent knowledge across sessions
        - SEMANTIC: Vector-indexed for similarity search
        - EPISODIC: Event timeline for recall

    Example:
        >>> from agentic_brain.memory import UnifiedMemory
        >>>
        >>> # Simple usage (SQLite, no external deps)
        >>> mem = UnifiedMemory()
        >>> mem.store("user likes Python")
        >>> results = mem.search("programming preferences")
        >>> print(results[0].content)
        'user likes Python'
        >>>
        >>> # With session context
        >>> mem.add_message("session-1", "user", "Hello")
        >>> mem.add_message("session-1", "assistant", "Hi there!")
        >>> context = mem.get_session_context("session-1")
        >>>
        >>> # Record events for episodic memory
        >>> mem.record_event("user_action", {"action": "login"})
        >>> events = mem.get_events(event_type="user_action")
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        neo4j_uri: Optional[str] = None,
        neo4j_user: Optional[str] = None,
        neo4j_password: Optional[str] = None,
        embedder: Optional[EmbeddingProvider] = None,
        use_neo4j: bool = False,
    ):
        """
        Initialize unified memory.

        Args:
            db_path: SQLite database path
            neo4j_uri: Neo4j URI (optional)
            neo4j_user: Neo4j user (optional)
            neo4j_password: Neo4j password (optional)
            embedder: Custom embedding provider
            use_neo4j: Try to use Neo4j if available
        """
        self._db_path = db_path or os.environ.get(
            "MEMORY_DB_PATH", "~/.agentic_brain/memory.db"
        )
        self._embedder = embedder
        self._neo4j = None
        self._sqlite: Optional[SQLiteMemoryStore] = None
        self._current_session: Optional[str] = None

        # Try Neo4j if requested
        if use_neo4j:
            self._init_neo4j(neo4j_uri, neo4j_user, neo4j_password)

        # Always have SQLite as fallback
        self._init_sqlite()

    def _init_neo4j(
        self,
        uri: Optional[str],
        user: Optional[str],
        password: Optional[str],
    ) -> None:
        """Initialize Neo4j connection."""
        try:
            from agentic_brain.memory import Neo4jMemory

            self._neo4j = Neo4jMemory(
                uri=uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                user=user or os.environ.get("NEO4J_USER", "neo4j"),
                password=password or os.environ.get("NEO4J_PASSWORD", ""),
            )
            if not self._neo4j.connect():
                logger.warning("Neo4j unavailable, using SQLite")
                self._neo4j = None
            else:
                logger.info("Connected to Neo4j for long-term memory")
        except ImportError:
            logger.debug("Neo4j not installed, using SQLite")
        except Exception as e:
            logger.warning(f"Neo4j connection failed: {e}, using SQLite")
            self._neo4j = None

    def _init_sqlite(self) -> None:
        """Initialize SQLite store."""
        self._sqlite = SQLiteMemoryStore(
            db_path=self._db_path,
            embedder=self._embedder,
        )
        logger.info(f"Initialized SQLite memory at {self._db_path}")

    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> MemoryEntry:
        """
        Store a memory.

        Args:
            content: Text content to store
            memory_type: Type of memory
            metadata: Additional metadata
            session_id: Session ID

        Returns:
            Created MemoryEntry
        """
        session = session_id or self._current_session
        return self._sqlite.store(
            content=content,
            memory_type=memory_type,
            metadata=metadata,
            session_id=session,
        )

    def search(
        self,
        query: str,
        memory_type: Optional[MemoryType] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        use_semantic: bool = True,
    ) -> list[MemoryEntry]:
        """
        Search memories.

        Uses hybrid full-text + semantic search.

        Args:
            query: Search query
            memory_type: Filter by type
            session_id: Filter by session
            limit: Max results
            use_semantic: Use semantic similarity

        Returns:
            List of matching MemoryEntry objects
        """
        return self._sqlite.search(
            query=query,
            memory_type=memory_type,
            session_id=session_id,
            limit=limit,
            use_semantic=use_semantic,
        )

    def get_recent(
        self,
        memory_type: Optional[MemoryType] = None,
        session_id: Optional[str] = None,
        limit: int = 10,
        hours: Optional[int] = None,
    ) -> list[MemoryEntry]:
        """Get recent memories."""
        return self._sqlite.get_recent(
            memory_type=memory_type,
            session_id=session_id,
            limit=limit,
            hours=hours,
        )

    def delete(self, memory_id: str) -> bool:
        """Delete a memory."""
        return self._sqlite.delete(memory_id)

    def count(self, memory_type: Optional[MemoryType] = None) -> int:
        """Count memories."""
        return self._sqlite.count(memory_type)

    # Session memory methods

    def set_session(self, session_id: str) -> None:
        """Set current session ID."""
        self._current_session = session_id

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> None:
        """Add message to session context."""
        context = self._sqlite.get_session_context(session_id)
        messages = context["messages"] if context else []

        messages.append(
            {
                "role": role,
                "content": content,
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": metadata or {},
            }
        )

        self._sqlite.save_session_context(session_id, messages)

    def get_session_context(self, session_id: str) -> Optional[dict]:
        """Get session context."""
        return self._sqlite.get_session_context(session_id)

    def get_session_messages(
        self, session_id: str, limit: Optional[int] = None
    ) -> list[dict]:
        """Get session messages."""
        context = self._sqlite.get_session_context(session_id)
        if not context:
            return []

        messages = context.get("messages", [])
        if limit:
            return messages[-limit:]
        return messages

    # Episodic memory methods

    def record_event(
        self,
        event_type: str,
        data: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Record an event for episodic memory."""
        session = session_id or self._current_session
        return self._sqlite.record_event(event_type, data, session)

    def get_events(
        self,
        event_type: Optional[str] = None,
        session_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get events from episodic memory."""
        return self._sqlite.get_events(event_type, session_id, since, limit)

    # Utility methods

    def remember(self, content: str, **kwargs) -> MemoryEntry:
        """Alias for store() - more natural language."""
        return self.store(content, **kwargs)

    def recall(self, query: str, **kwargs) -> list[MemoryEntry]:
        """Alias for search() - more natural language."""
        return self.search(query, **kwargs)

    def stats(self) -> dict:
        """Get memory statistics."""
        return {
            "total": self.count(),
            "session": self.count(MemoryType.SESSION),
            "long_term": self.count(MemoryType.LONG_TERM),
            "semantic": self.count(MemoryType.SEMANTIC),
            "episodic": self.count(MemoryType.EPISODIC),
            "db_path": str(self._sqlite.db_path),
            "neo4j_connected": self._neo4j is not None,
        }

    def close(self) -> None:
        """Close connections."""
        if self._sqlite:
            self._sqlite.close()
        if self._neo4j:
            self._neo4j.close()

    def __enter__(self) -> UnifiedMemory:
        return self

    def __exit__(self, *args) -> None:
        self.close()


# Convenience alias - allows `from agentic_brain.memory import Memory`
# to get the new unified system
Memory = UnifiedMemory


# Factory function with same interface as original
def get_unified_memory(**kwargs) -> UnifiedMemory:
    """
    Get a unified memory instance.

    This is the recommended way to get memory in agentic-brain.
    Works without external dependencies.

    Returns:
        UnifiedMemory instance
    """
    return UnifiedMemory(**kwargs)
