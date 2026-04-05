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
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional, Protocol

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
        importance: Importance level 0.0-1.0 (affects search ranking and retention)
        access_count: Times this memory has been retrieved (reinforcement)
        last_accessed: When this memory was last accessed
        entities: Extracted entities from content
    """

    id: str
    content: str
    memory_type: MemoryType
    timestamp: datetime
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    session_id: Optional[str] = None
    score: float = 0.0
    importance: float = 0.5
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    entities: list[dict[str, str]] = field(default_factory=list)

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
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": (
                self.last_accessed.isoformat() if self.last_accessed else None
            ),
            "entities": self.entities,
        }

    @property
    def effective_importance(self) -> float:
        """
        Get importance with time-decay applied (Mem0-inspired).

        Memories fade over time unless reinforced by access.
        """
        ref_time = self.last_accessed or self.timestamp
        if isinstance(ref_time, str):
            ref_time = datetime.fromisoformat(ref_time)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=UTC)
        days = max(0.0, (datetime.now(UTC) - ref_time).total_seconds() / 86400)
        decay = math.exp(-0.01 * days)
        reinforcement = min(self.access_count * 0.02, 0.2) if self.access_count else 0.0
        return max(0.1, min(1.0, self.importance * decay + reinforcement))

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
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=(
                datetime.fromisoformat(data["last_accessed"])
                if data.get("last_accessed")
                else None
            ),
            entities=data.get("entities", []),
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
                session_id TEXT,
                importance REAL DEFAULT 0.5,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT,
                entities TEXT
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

            -- Entity tracking table (Mem0-inspired)
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                mention_count INTEGER DEFAULT 1
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_entity_unique
                ON entities(name, entity_type);
            CREATE INDEX IF NOT EXISTS idx_entity_name ON entities(name);

            -- Memory-entity associations
            CREATE TABLE IF NOT EXISTS memory_entities (
                memory_id TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                PRIMARY KEY (memory_id, entity_id)
            );

            -- Cross-session links (Mem0-inspired)
            CREATE TABLE IF NOT EXISTS session_links (
                session1 TEXT NOT NULL,
                session2 TEXT NOT NULL,
                relationship TEXT DEFAULT 'RELATED_TO',
                shared_entities TEXT,
                linked_at TEXT NOT NULL,
                PRIMARY KEY (session1, session2)
            );
        """
        )
        conn.commit()
        # Migrate existing DBs that don't have new columns
        self._migrate_schema(conn)

    def _migrate_schema(self, conn: sqlite3.Connection) -> None:
        """Add new columns to existing databases (safe migration)."""
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()
        }
        migrations = [
            (
                "access_count",
                "ALTER TABLE memories ADD COLUMN access_count INTEGER DEFAULT 0",
            ),
            ("last_accessed", "ALTER TABLE memories ADD COLUMN last_accessed TEXT"),
            ("entities", "ALTER TABLE memories ADD COLUMN entities TEXT"),
            (
                "importance",
                "ALTER TABLE memories ADD COLUMN importance REAL DEFAULT 0.5",
            ),
        ]
        for col, sql in migrations:
            if col not in columns:
                try:
                    conn.execute(sql)
                except sqlite3.OperationalError:
                    pass  # column already exists or table issue
        # Create indexes on new columns (safe if they already exist)
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_importance ON memories(importance)"
            )
        except sqlite3.OperationalError:
            pass
        conn.commit()

    def store(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.LONG_TERM,
        metadata: Optional[dict] = None,
        session_id: Optional[str] = None,
        memory_id: Optional[str] = None,
        importance: float = 0.5,
    ) -> MemoryEntry:
        """
        Store a memory.

        Args:
            content: Text content to store
            memory_type: Type of memory
            metadata: Additional metadata
            session_id: Session ID for session memory
            memory_id: Optional custom ID
            importance: Importance level 0.0-1.0 (higher = more important,
                        affects search ranking and retention during cleanup)

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

        # Auto-score importance based on content signals (Mem0-inspired)
        if importance == 0.5:
            importance = self._score_importance(content, memory_type, metadata)

        # Extract entities
        extracted_entities = self._extract_entities(content)

        entry = MemoryEntry(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            timestamp=timestamp,
            metadata=metadata or {},
            embedding=embedding,
            session_id=session_id,
            importance=max(0.0, min(1.0, importance)),
            access_count=0,
            last_accessed=timestamp,
            entities=extracted_entities,
        )

        conn.execute(
            """
            INSERT OR REPLACE INTO memories
            (id, content, memory_type, timestamp, metadata, embedding, session_id,
             importance, access_count, last_accessed, entities)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                entry.id,
                entry.content,
                entry.memory_type.value,
                entry.timestamp.isoformat(),
                json.dumps(entry.metadata),
                json.dumps(embedding) if embedding else None,
                entry.session_id,
                entry.importance,
                entry.access_count,
                entry.last_accessed.isoformat() if entry.last_accessed else None,
                json.dumps(extracted_entities),
            ),
        )
        conn.commit()

        # Store entities in entity tracking table
        self._store_entities(conn, entry.id, extracted_entities)

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
        """Re-rank results using semantic similarity + importance."""
        for entry in results:
            if entry.embedding:
                semantic_score = self._cosine_similarity(
                    query_embedding, entry.embedding
                )
                # Combine FTS score + semantic score + importance boost
                entry.score = (
                    0.4 * entry.score + 0.4 * semantic_score + 0.2 * entry.importance
                )

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

        # Safely read columns that may not exist in older databases
        def _safe(col: str, default=None):
            try:
                val = row[col]
                return val if val is not None else default
            except (IndexError, KeyError):
                return default

        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            session_id=row["session_id"],
            importance=_safe("importance", 0.5),
            access_count=_safe("access_count", 0),
            last_accessed=(
                datetime.fromisoformat(_safe("last_accessed"))
                if _safe("last_accessed")
                else None
            ),
            entities=json.loads(_safe("entities", "[]")),
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

    # Importance scoring and entity extraction

    # High-signal keywords that indicate important content
    _IMPORTANCE_KEYWORDS = {
        "error",
        "bug",
        "fix",
        "critical",
        "urgent",
        "important",
        "decision",
        "agreed",
        "remember",
        "always",
        "never",
        "rule",
        "password",
        "secret",
        "key",
        "credential",
        "preference",
    }

    def _score_importance(
        self,
        content: str,
        memory_type: MemoryType,
        metadata: Optional[dict],
    ) -> float:
        """
        Auto-score memory importance based on content signals.

        Analyses keyword presence, memory type, and metadata hints
        to assign 0.0-1.0 importance without requiring an LLM call.
        """
        score = 0.5
        lower = content.lower()

        # Keyword boost
        hits = sum(1 for kw in self._IMPORTANCE_KEYWORDS if kw in lower)
        score += min(hits * 0.05, 0.2)

        # Memory type boost
        if memory_type == MemoryType.LONG_TERM:
            score += 0.1
        elif memory_type == MemoryType.EPISODIC:
            score += 0.05

        # Metadata hints
        if metadata:
            if metadata.get("important") or metadata.get("pinned"):
                score += 0.2
            if metadata.get("source") == "user":
                score += 0.05

        # Length heuristic: very short or very long = less likely important
        word_count = len(content.split())
        if 10 <= word_count <= 200:
            score += 0.05

        return max(0.1, min(1.0, score))

    def _extract_entities(self, content: str) -> list[dict[str, str]]:
        """
        Extract named entities from content using simple heuristics.

        Returns list of {name, type} dicts.
        """
        entities: list[dict[str, str]] = []
        seen: set[str] = set()

        for word in content.split():
            # Simple heuristic: capitalised words that aren't sentence starters
            clean = word.strip(".,!?;:'\"()")
            if (
                clean
                and clean[0].isupper()
                and len(clean) > 1
                and clean.lower()
                not in {
                    "the",
                    "this",
                    "that",
                    "it",
                    "he",
                    "she",
                    "we",
                    "they",
                    "is",
                    "are",
                    "was",
                    "were",
                    "i",
                    "a",
                    "an",
                }
                and clean.lower() not in seen
            ):
                seen.add(clean.lower())
                entities.append({"name": clean, "type": "UNKNOWN"})

        return entities[:20]  # Cap at 20 entities

    def _store_entities(
        self, conn: sqlite3.Connection, memory_id: str, entities: list[dict[str, str]]
    ) -> None:
        """Persist extracted entities to the entity tracking tables."""
        now = datetime.now(UTC).isoformat()
        for ent in entities:
            eid = hashlib.sha256(f"{ent['name']}:{ent['type']}".encode()).hexdigest()[
                :16
            ]

            conn.execute(
                """
                INSERT INTO entities (id, name, entity_type, first_seen, last_seen, mention_count)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(name, entity_type) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    mention_count = mention_count + 1
                """,
                (eid, ent["name"], ent["type"], now, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO memory_entities (memory_id, entity_id) VALUES (?, ?)",
                (memory_id, eid),
            )
        if entities:
            conn.commit()

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

    # =========================================================================
    # IMPORTANCE SCORING (Mem0-inspired)
    # =========================================================================

    # High-signal keywords that boost importance
    IMPORTANCE_KEYWORDS = frozenset(
        {
            "important",
            "critical",
            "urgent",
            "remember",
            "always",
            "never",
            "must",
            "password",
            "key",
            "secret",
            "deadline",
            "decision",
            "agreed",
            "confirmed",
            "preference",
            "birthday",
            "error",
            "bug",
            "fix",
            "deploy",
            "production",
            "breaking",
            "security",
        }
    )

    def _score_importance(
        self,
        content: str,
        memory_type: MemoryType,
        metadata: Optional[dict],
    ) -> float:
        """
        Score memory importance based on content signals (Mem0-inspired).

        Args:
            content: Text content
            memory_type: Type of memory
            metadata: Additional metadata

        Returns:
            Importance score 0.0-1.0
        """
        score = 0.5
        text_lower = content.lower()

        # Memory type boost
        if memory_type == MemoryType.LONG_TERM:
            score += 0.15
        elif memory_type == MemoryType.EPISODIC:
            score += 0.1

        # Keyword boost
        hits = sum(1 for kw in self.IMPORTANCE_KEYWORDS if kw in text_lower)
        score += min(hits * 0.08, 0.3)

        # Length signal
        word_count = len(content.split())
        if word_count < 5:
            score -= 0.1
        elif word_count > 50:
            score += 0.1

        # Question signal
        if "?" in content:
            score += 0.05

        # Code signal
        if "```" in content or "def " in content or "class " in content:
            score += 0.1

        # Metadata overrides
        if metadata:
            if metadata.get("importance"):
                try:
                    score = float(metadata["importance"])
                except (ValueError, TypeError):
                    pass
            if metadata.get("pinned"):
                score = max(score, 0.9)

        return max(0.0, min(1.0, score))

    # =========================================================================
    # ENTITY EXTRACTION (Mem0-inspired)
    # =========================================================================

    def _extract_entities(self, text: str) -> list[dict[str, str]]:
        """
        Extract entities from text using pattern matching (Mem0-inspired).

        Returns:
            List of {"name": ..., "type": ...} dicts
        """
        entities: list[dict[str, str]] = []
        seen: set[str] = set()

        def _add(name: str, etype: str) -> None:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                entities.append({"name": name, "type": etype})

        # Emails
        for m in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
            _add(m.group(), "EMAIL")

        # URLs
        for m in re.finditer(r"https?://[^\s<>\"']+", text):
            _add(m.group(), "URL")

        # JIRA tickets
        for m in re.finditer(r"\b[A-Z]{2,6}-\d{1,6}\b", text):
            _add(m.group(), "TICKET")

        # File paths
        for m in re.finditer(r"(?:~/|/[\w]+/|\./)[\w/.-]+\.\w+", text):
            _add(m.group(), "FILE")

        # Technology names
        tech_re = re.compile(
            r"\b(Python|JavaScript|TypeScript|Java|Neo4j|Docker|Redis|React|"
            r"Angular|Vue|Node\.js|FastAPI|Django|Flask|PostgreSQL|MySQL|"
            r"MongoDB|Kubernetes|AWS|Azure|GCP|Git|GitHub|Bitbucket|JIRA|"
            r"Safari|Chrome|macOS|Linux|Windows|VoiceOver)\b",
            re.IGNORECASE,
        )
        for m in tech_re.finditer(text):
            _add(m.group(), "TECHNOLOGY")

        # Multi-word proper nouns (e.g., "Steve Taylor")
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
            name = m.group()
            if name.lower() not in {"the end", "the other"}:
                _add(name, "PERSON")

        # Single capitalized words
        skip_words = {
            "the",
            "this",
            "that",
            "these",
            "those",
            "when",
            "where",
            "what",
            "which",
            "how",
            "who",
            "why",
            "but",
            "and",
            "for",
            "not",
            "with",
            "from",
        }
        for word in text.split():
            cleaned = word.strip(".,!?;:()[]{}\"'")
            if (
                len(cleaned) >= 3
                and cleaned[0].isupper()
                and not cleaned.isupper()
                and cleaned.lower() not in skip_words
            ):
                etype = "CONCEPT"
                if cleaned.endswith(("Corp", "Inc", "Ltd", "LLC", "Pty")):
                    etype = "ORGANIZATION"
                _add(cleaned, etype)

        return entities

    def _store_entities(
        self,
        conn: sqlite3.Connection,
        memory_id: str,
        entities: list[dict[str, str]],
    ) -> None:
        """Store extracted entities and link to memory."""
        now = datetime.now(UTC).isoformat()
        for ent in entities:
            eid = hashlib.sha256(f"{ent['name']}:{ent['type']}".encode()).hexdigest()[
                :16
            ]

            conn.execute(
                """
                INSERT INTO entities (id, name, entity_type, first_seen, last_seen, mention_count)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(name, entity_type) DO UPDATE SET
                    last_seen = ?,
                    mention_count = mention_count + 1
                """,
                (eid, ent["name"], ent["type"], now, now, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO memory_entities (memory_id, entity_id) VALUES (?, ?)",
                (memory_id, eid),
            )
        conn.commit()

    # =========================================================================
    # MEMORY DECAY & REINFORCEMENT (Mem0-inspired)
    # =========================================================================

    def reinforce_memory(
        self, memory_id: str, boost: float = 0.15
    ) -> Optional[MemoryEntry]:
        """
        Reinforce a memory (boost importance on access).

        Args:
            memory_id: Memory to reinforce
            boost: Importance boost amount

        Returns:
            Updated MemoryEntry or None
        """
        conn = self._get_conn()
        now = datetime.now(UTC).isoformat()

        conn.execute(
            """
            UPDATE memories
            SET access_count = COALESCE(access_count, 0) + 1,
                last_accessed = ?,
                importance = MIN(1.0, COALESCE(importance, 0.5) + ?)
            WHERE id = ?
            """,
            (now, boost, memory_id),
        )
        conn.commit()

        cursor = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        return self._row_to_entry(row) if row else None

    def apply_decay(self, decay_rate: float = 0.01, min_importance: float = 0.1) -> int:
        """
        Apply time-based decay to all memories.

        Args:
            decay_rate: Importance lost per day since last access
            min_importance: Floor - memories never fully disappear

        Returns:
            Number of memories updated
        """
        conn = self._get_conn()
        now = datetime.now(UTC)
        updated = 0

        rows = conn.execute(
            "SELECT id, importance, timestamp, access_count, last_accessed "
            "FROM memories WHERE importance > ?",
            (min_importance,),
        ).fetchall()

        for row in rows:
            ref_time_str = row["last_accessed"] or row["timestamp"]
            ref_time = datetime.fromisoformat(ref_time_str)
            if ref_time.tzinfo is None:
                ref_time = ref_time.replace(tzinfo=UTC)

            days = max(0.0, (now - ref_time).total_seconds() / 86400)
            decay = math.exp(-decay_rate * days)
            access_bonus = min((row["access_count"] or 0) * 0.02, 0.2)
            new_importance = max(
                min_importance, min(1.0, row["importance"] * decay + access_bonus)
            )

            if abs(new_importance - row["importance"]) > 0.001:
                conn.execute(
                    "UPDATE memories SET importance = ? WHERE id = ?",
                    (new_importance, row["id"]),
                )
                updated += 1

        conn.commit()
        logger.info(f"Applied decay to {updated} memories")
        return updated

    def condense_old_memories(
        self,
        older_than_days: int = 7,
        importance_threshold: float = 0.3,
    ) -> dict:
        """
        Condense old, low-importance memories into summaries (Mem0-inspired).

        Args:
            older_than_days: Only condense memories older than this
            importance_threshold: Only condense memories below this

        Returns:
            Stats dict with condensed count
        """
        conn = self._get_conn()
        cutoff = (datetime.now(UTC) - timedelta(hours=older_than_days * 24)).isoformat()

        rows = conn.execute(
            """
            SELECT id, content, memory_type, session_id, importance
            FROM memories
            WHERE timestamp < ? AND importance < ?
            ORDER BY timestamp
            """,
            (cutoff, importance_threshold),
        ).fetchall()

        if not rows:
            return {"condensed": 0, "summary_created": False}

        # Group by session
        by_session: dict[str, list] = {}
        for r in rows:
            sid = r["session_id"] or "no_session"
            by_session.setdefault(sid, []).append(dict(r))

        condensed_count = 0
        for sid, msgs in by_session.items():
            # Create summary
            parts = [f"{m['content'][:200]}" for m in msgs[:10]]
            summary = f"Condensed {len(msgs)} memories: " + " | ".join(parts[:5])
            if len(msgs) > 5:
                summary += f" [... and {len(msgs) - 5} more]"

            # Store as a new high-importance summary memory
            self.store(
                content=summary[:2000],
                memory_type=MemoryType.LONG_TERM,
                metadata={"condensation": True, "original_count": len(msgs)},
                session_id=sid if sid != "no_session" else None,
                importance=0.7,
            )

            # Delete originals
            ids = [m["id"] for m in msgs]
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM memories WHERE id IN ({placeholders})", ids)
            condensed_count += len(msgs)

        conn.commit()
        logger.info(f"Condensed {condensed_count} old memories")
        return {
            "condensed": condensed_count,
            "sessions": len(by_session),
            "summary_created": True,
        }

    # =========================================================================
    # CROSS-SESSION LINKING (Mem0-inspired)
    # =========================================================================

    def link_sessions(
        self,
        session1: str,
        session2: str,
        relationship: str = "RELATED_TO",
        shared_entities: Optional[list[str]] = None,
    ) -> None:
        """Link two sessions that share context."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT OR REPLACE INTO session_links
            (session1, session2, relationship, shared_entities, linked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session1,
                session2,
                relationship,
                json.dumps(shared_entities or []),
                datetime.now(UTC).isoformat(),
            ),
        )
        conn.commit()

    def find_related_sessions(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Find sessions related to the given one via shared entities."""
        conn = self._get_conn()

        # Find sessions that share entities with this one
        rows = conn.execute(
            """
            SELECT DISTINCT m2.session_id, COUNT(DISTINCT me2.entity_id) as shared_count
            FROM memory_entities me1
            JOIN memories m1 ON me1.memory_id = m1.id
            JOIN memory_entities me2 ON me1.entity_id = me2.entity_id
            JOIN memories m2 ON me2.memory_id = m2.id
            WHERE m1.session_id = ? AND m2.session_id != ? AND m2.session_id IS NOT NULL
            GROUP BY m2.session_id
            ORDER BY shared_count DESC
            LIMIT ?
            """,
            (session_id, session_id, limit),
        ).fetchall()

        results = []
        for r in rows:
            # Get shared entity names
            entity_rows = conn.execute(
                """
                SELECT DISTINCT e.name
                FROM memory_entities me1
                JOIN memories m1 ON me1.memory_id = m1.id
                JOIN memory_entities me2 ON me1.entity_id = me2.entity_id
                JOIN memories m2 ON me2.memory_id = m2.id
                JOIN entities e ON me1.entity_id = e.id
                WHERE m1.session_id = ? AND m2.session_id = ?
                """,
                (session_id, r["session_id"]),
            ).fetchall()

            results.append(
                {
                    "session_id": r["session_id"],
                    "shared_entity_count": r["shared_count"],
                    "shared_entities": [er["name"] for er in entity_rows],
                }
            )
        return results

    def get_entity_timeline(self, entity_name: str, limit: int = 20) -> list[dict]:
        """Get timeline of an entity across all memories."""
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT m.id, m.content, m.timestamp, m.session_id, m.importance
            FROM memories m
            JOIN memory_entities me ON m.id = me.memory_id
            JOIN entities e ON me.entity_id = e.id
            WHERE LOWER(e.name) = LOWER(?)
            ORDER BY m.timestamp DESC
            LIMIT ?
            """,
            (entity_name, limit),
        ).fetchall()

        return [
            {
                "memory_id": r["id"],
                "content": r["content"],
                "timestamp": r["timestamp"],
                "session_id": r["session_id"],
                "importance": r["importance"],
            }
            for r in rows
        ]

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
        importance: float = 0.5,
    ) -> MemoryEntry:
        """
        Store a memory.

        Args:
            content: Text content to store
            memory_type: Type of memory
            metadata: Additional metadata
            session_id: Session ID
            importance: Importance level 0.0-1.0

        Returns:
            Created MemoryEntry
        """
        session = session_id or self._current_session
        return self._sqlite.store(
            content=content,
            memory_type=memory_type,
            metadata=metadata,
            session_id=session,
            importance=importance,
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

    # Mem0-inspired methods delegated to SQLite store

    def reinforce_memory(
        self, memory_id: str, boost: float = 0.15
    ) -> Optional[MemoryEntry]:
        """Reinforce a memory (boost importance on access)."""
        return self._sqlite.reinforce_memory(memory_id, boost)

    def apply_decay(self, decay_rate: float = 0.01, min_importance: float = 0.1) -> int:
        """Apply time-based decay to all memories."""
        return self._sqlite.apply_decay(decay_rate, min_importance)

    def condense_old_memories(
        self, older_than_days: int = 7, importance_threshold: float = 0.3
    ) -> dict:
        """Condense old, low-importance memories into summaries."""
        return self._sqlite.condense_old_memories(older_than_days, importance_threshold)

    def link_sessions(
        self,
        session1: str,
        session2: str,
        relationship: str = "RELATED_TO",
        shared_entities: Optional[list[str]] = None,
    ) -> None:
        """Link two related sessions."""
        self._sqlite.link_sessions(session1, session2, relationship, shared_entities)

    def find_related_sessions(self, session_id: str, limit: int = 10) -> list[dict]:
        """Find sessions related via shared entities."""
        return self._sqlite.find_related_sessions(session_id, limit)

    def get_entity_timeline(self, entity_name: str, limit: int = 20) -> list[dict]:
        """Get timeline of an entity across all memories."""
        return self._sqlite.get_entity_timeline(entity_name, limit)

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


@dataclass
class HookEvent:
    """Event captured from hooks (merged from ultimate_memory_hooks)."""

    event_type: str  # userPromptSubmitted, toolUse, sessionStart, etc.
    source: str  # copilot-cli, claude-code, mcp, voice
    timestamp: str
    session_id: str
    content: str = ""
    role: str = "user"  # user, assistant, tool, system
    metadata: dict = field(default_factory=dict)
    event_id: str = field(
        default_factory=lambda: str(
            hashlib.sha256(f"{datetime.now(UTC).isoformat()}".encode()).hexdigest()
        )[:16]
    )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "content": self.content,
            "role": self.role,
            "metadata": self.metadata,
        }


@dataclass
class SessionLink:
    """Link between two sessions (merged from session_stitcher)."""

    from_session: str
    to_session: str
    link_type: str  # 'entity', 'topic', 'continuation'
    shared_items: list[str]
    strength: float  # 0-1
    timestamp: str

    def to_dict(self) -> dict:
        return {
            "from_session": self.from_session,
            "to_session": self.to_session,
            "link_type": self.link_type,
            "shared_items": self.shared_items,
            "strength": self.strength,
            "timestamp": self.timestamp,
        }


class SessionHooks:
    """
    Multi-source hook capture system (consolidated from ultimate_memory_hooks).

    Captures events from:
    - GitHub Copilot CLI
    - Claude Code extensions
    - MCP tool calls
    - Voice interactions

    All events are stored in unified memory and optionally published to event bus.
    """

    def __init__(
        self,
        memory: UnifiedMemory,
        enable_kafka: bool = False,
        enable_neo4j: bool = False,
        session_id: Optional[str] = None,
    ):
        """
        Initialize session hooks.

        Args:
            memory: UnifiedMemory instance for storage
            enable_kafka: Whether to publish to event bus
            enable_neo4j: Whether to use Neo4j for session storage
            session_id: Optional session ID (auto-generated if not provided)
        """
        self.memory = memory
        timestamp_hash = hashlib.sha256(
            datetime.now(UTC).isoformat().encode()
        ).hexdigest()[:16]
        self.session_id = session_id or f"session-{timestamp_hash}"
        self.session_start = datetime.now(UTC)
        self.turn_count = 0
        self.events: list[HookEvent] = []
        self.enable_kafka = enable_kafka
        self.enable_neo4j = enable_neo4j
        self._event_bus = None

        if enable_kafka:
            try:
                # Try to import event bus - optional dependency
                from event_bus import EventBus

                self._event_bus = EventBus()
            except ImportError:
                logger.debug("Event bus not available")

    def on_session_start(self, data: Optional[dict] = None) -> dict:
        """Called when a new session starts."""
        event = self._capture_event(
            event_type="sessionStart",
            source="copilot-cli",
            content=f"Session started: {self.session_id}",
            role="system",
            metadata=data or {},
        )

        # Recall recent memories so we don't forget
        recent_context = self._recall_recent_context()

        return {
            "success": True,
            "event_id": event.event_id,
            "session_id": self.session_id,
            "recent_context": recent_context,
        }

    def on_session_end(self, data: Optional[dict] = None) -> dict:
        """Called when session ends."""
        summary = self._generate_session_summary()

        event = self._capture_event(
            event_type="sessionEnd",
            source="copilot-cli",
            content=f"Session ended. {summary}",
            role="system",
            metadata=data or {},
        )

        return {
            "success": True,
            "event_id": event.event_id,
            "summary": summary,
        }

    def on_user_prompt(self, prompt: str, data: Optional[dict] = None) -> dict:
        """Called when user submits a prompt."""
        event = self._capture_event(
            event_type="userPromptSubmitted",
            source="copilot-cli",
            content=prompt,
            role="user",
            metadata=data or {},
        )
        return {"success": True, "event_id": event.event_id}

    def on_assistant_response(self, response: str, data: Optional[dict] = None) -> dict:
        """Called when assistant responds."""
        event = self._capture_event(
            event_type="assistantResponse",
            source="copilot-cli",
            content=response,
            role="assistant",
            metadata=data or {},
        )
        return {"success": True, "event_id": event.event_id}

    def on_tool_use(
        self,
        tool_name: str,
        tool_args: Optional[dict] = None,
        phase: str = "pre",
        result: Optional[str] = None,
        data: Optional[dict] = None,
    ) -> dict:
        """Called before/after tool use."""
        event_type = f"{'pre' if phase == 'pre' else 'post'}ToolUse"

        content = f"Tool: {tool_name}"
        if tool_args:
            content += f", Args: {json.dumps(tool_args)[:200]}"
        if result:
            content += f", Result: {result[:500]}"

        event = self._capture_event(
            event_type=event_type,
            source="copilot-cli",
            content=content,
            role="tool",
            metadata={"tool_name": tool_name, "phase": phase, **(data or {})},
        )
        return {"success": True, "event_id": event.event_id}

    def on_voice_input(
        self, text: str, lady: Optional[str] = None, data: Optional[dict] = None
    ) -> dict:
        """Called when voice input is received."""
        event = self._capture_event(
            event_type="voiceInput",
            source="voice",
            content=text,
            role="user",
            metadata={"lady": lady, **(data or {})},
        )
        return {"success": True, "event_id": event.event_id}

    def _capture_event(
        self,
        event_type: str,
        source: str,
        content: str,
        role: str = "user",
        metadata: Optional[dict] = None,
    ) -> HookEvent:
        """Capture an event and store it."""
        event = HookEvent(
            event_type=event_type,
            source=source,
            timestamp=datetime.now(UTC).isoformat(),
            session_id=self.session_id,
            content=content,
            role=role,
            metadata=metadata or {},
        )

        self.events.append(event)
        self.turn_count += 1

        # Store in unified memory
        self.memory.store(
            content=content,
            memory_type=MemoryType.SESSION,
            metadata={
                "event_type": event_type,
                "source": source,
                "role": role,
                **event.metadata,
            },
            session_id=self.session_id,
            importance=0.7 if role != "tool" else 0.4,
        )

        # Publish to event bus if enabled
        if self._event_bus:
            try:
                self._event_bus.publish(
                    topic=f"memory.{event_type}",
                    message=event.to_dict(),
                )
            except Exception as e:
                logger.debug(f"Could not publish to event bus: {e}")

        return event

    def _recall_recent_context(self) -> dict:
        """Recall what we were working on recently."""
        # Search for recent memories from this session
        recent = self.memory.search(
            "recent work context",
            memory_type=MemoryType.SESSION,
            session_id=self.session_id,
            limit=10,
        )

        # Find memories from past sessions
        related_memories = self.memory.search(
            "recent work context",
            memory_type=MemoryType.LONG_TERM,
            limit=5,
        )

        return {
            "recent_memories": [
                {"text": m.content[:300], "importance": m.importance} for m in recent
            ],
            "related_context": [
                {"text": m.content[:300], "session": m.session_id}
                for m in related_memories
            ],
            "memory_count": len(recent),
        }

    def _generate_session_summary(self) -> str:
        """Generate a summary of the session."""
        if not self.events:
            return "Empty session"

        # Summarize key events
        key_events = [e for e in self.events if e.role != "tool"][-5:]
        summary_parts = [f"{len(self.events)} events across {self.turn_count} turns"]

        if key_events:
            topics = [e.event_type for e in key_events]
            summary_parts.append(f"Topics: {', '.join(set(topics))}")

        return "; ".join(summary_parts)


class SessionStitcher:
    """
    Links related conversations across sessions (consolidated from session_stitcher).

    Uses entity and topic extraction to automatically find related sessions
    and provide cross-session context.
    """

    def __init__(self, memory: UnifiedMemory):
        """
        Initialize session stitcher.

        Args:
            memory: UnifiedMemory instance for querying
        """
        self.memory = memory
        self._current_session: Optional[str] = None
        self._session_entities: dict[str, set[str]] = {}
        self._session_topics: set[str] = set()
        self._message_count = 0

    def start_session(self, session_id: str) -> str:
        """Start tracking a new session."""
        self._current_session = session_id
        self._session_entities = {
            "jira_tickets": set(),
            "pr_numbers": set(),
            "people": set(),
            "file_paths": set(),
        }
        self._session_topics = set()
        self._message_count = 0
        return session_id

    def process_message(self, message: str, session_id: Optional[str] = None) -> dict:
        """
        Process a message - extract entities/topics and link to past sessions.

        Args:
            message: The message text
            session_id: Optional session ID (uses current if not provided)

        Returns:
            Dict with extracted entities, topics, and related sessions
        """
        session_id = session_id or self._current_session
        if not session_id:
            session_id = self.start_session(
                f"auto-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
            )

        # Simple entity extraction from message
        entities = self._extract_entities(message)
        topics = self._extract_topics(message)

        # Track locally
        self._session_entities["jira_tickets"].update(entities.get("jira_tickets", []))
        self._session_entities["pr_numbers"].update(entities.get("pr_numbers", []))
        self._session_entities["people"].update(entities.get("people", []))
        self._session_entities["file_paths"].update(entities.get("file_paths", []))
        self._session_topics.update(topics)
        self._message_count += 1

        # Find related sessions
        related_sessions = self._find_related_sessions(entities, topics)

        # Store in memory
        self.memory.store(
            content=message,
            memory_type=MemoryType.SESSION,
            metadata={
                "entities": entities,
                "topics": list(topics),  # Convert set to list for JSON serialization
                "related_sessions": len(related_sessions),
            },
            session_id=session_id,
            importance=0.6,
        )

        return {
            "session_id": session_id,
            "entities": entities,
            "topics": list(topics),  # Also return as list
            "related_sessions": related_sessions,
            "message_count": self._message_count,
        }

    def find_related_sessions(
        self,
        entities: Optional[list[str]] = None,
        topics: Optional[list[str]] = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Find sessions related to given entities or topics.

        Args:
            entities: List of entity values to search
            topics: List of topics to search
            limit: Max results to return

        Returns:
            List of related session dicts
        """
        related = []

        # Search for memories containing entities
        if entities:
            for entity in entities[:5]:  # Limit search entities
                results = self.memory.search(entity, limit=limit // 2)
                for mem in results:
                    if mem.session_id and mem.session_id != self._current_session:
                        related.append(
                            {
                                "session_id": mem.session_id,
                                "reason": f"Mentioned {entity}",
                                "relevance": mem.score,
                            }
                        )

        # Search for memories with topics
        if topics:
            for topic in topics[:5]:
                results = self.memory.search(topic, limit=limit // 2)
                for mem in results:
                    if mem.session_id and mem.session_id != self._current_session:
                        related.append(
                            {
                                "session_id": mem.session_id,
                                "reason": f"Discussed {topic}",
                                "relevance": mem.score,
                            }
                        )

        # Deduplicate and sort by relevance
        seen = set()
        unique = []
        for r in sorted(related, key=lambda x: x["relevance"], reverse=True):
            key = r["session_id"]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:limit]

    def get_session_context(self, session_id: Optional[str] = None) -> dict:
        """
        Get context for a session.

        Args:
            session_id: Session to get context for

        Returns:
            Session context dict
        """
        session_id = session_id or self._current_session

        if not session_id:
            return {
                "session_id": None,
                "entities": {},
                "topics": [],
                "related_sessions": [],
                "message_count": 0,
            }

        # Get memories from this session
        results = self.memory.search(
            "*", memory_type=MemoryType.SESSION, session_id=session_id, limit=50
        )

        entities = {}
        topics = set()
        related_sessions = []

        for mem in results:
            if mem.metadata.get("entities"):
                for k, v in mem.metadata["entities"].items():
                    entities.setdefault(k, []).extend(v)
            if mem.metadata.get("topics"):
                topics.update(mem.metadata["topics"])
            if mem.metadata.get("related_sessions"):
                related_sessions.append(mem)

        return {
            "session_id": session_id,
            "entities": {k: list(set(v)) for k, v in entities.items()},
            "topics": list(topics),
            "related_sessions": [
                {
                    "id": m.session_id,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                }
                for m in related_sessions[:5]
            ],
            "message_count": self._message_count,
        }

    def end_session(self, summary: Optional[str] = None) -> dict:
        """End the current session."""
        if not self._current_session:
            return {"success": False, "message": "No active session"}

        summary = summary or self._generate_session_summary()

        # Store session summary as episodic memory
        self.memory.record_event(
            event_type="session_end",
            data={
                "session_id": self._current_session,
                "summary": summary,
                "message_count": self._message_count,
                "entities": {k: list(v) for k, v in self._session_entities.items()},
                "topics": list(self._session_topics),
            },
        )

        self._current_session = None
        return {
            "success": True,
            "summary": summary,
            "message_count": self._message_count,
        }

    def _extract_entities(self, message: str) -> dict:
        """Extract entities from message using simple patterns."""
        entities = {
            "jira_tickets": [],
            "pr_numbers": [],
            "people": [],
            "file_paths": [],
        }

        # JIRA tickets: SD-1330, ACME-999, etc.
        jira_pattern = r"\b[A-Z]+-\d+\b"
        entities["jira_tickets"] = re.findall(jira_pattern, message)

        # PR numbers: #209, PR-123, etc.
        pr_pattern = r"(?:#|PR[-\s]?)(\d+)"
        entities["pr_numbers"] = re.findall(pr_pattern, message)

        # Simple people detection (capitalized words that could be names)
        words = message.split()
        entities["people"] = [
            w.rstrip(".:,;") for w in words if w and w[0].isupper() and len(w) > 1
        ]

        # File paths - match /path, ./path, ~/path patterns
        path_pattern = r"(?:~/|\./?|(?<![/\w]))[\w\-./]{2,}(?:\.\w+)?"
        paths = re.findall(path_pattern, message)
        entities["file_paths"] = [
            p for p in paths if "/" in p
        ]  # Only keep paths with /

        return entities

    def _extract_topics(self, message: str) -> set[str]:
        """Extract potential topics from message."""
        # Simple keyword-based topic detection
        topic_keywords = {
            "work": ["work", "working", "job", "task"],
            "coding": ["code", "coding", "debug", "bug", "fix"],
            "deployment": ["deploy", "release", "production"],
            "review": ["review", "pr", "merge", "pull request"],
            "meeting": ["meet", "meeting", "discuss", "sync"],
        }

        topics = set()
        message_lower = message.lower()

        for topic, keywords in topic_keywords.items():
            if any(kw in message_lower for kw in keywords):
                topics.add(topic)

        return topics

    def _find_related_sessions(self, entities: dict, topics: set[str]) -> list[dict]:
        """Find sessions related to entities and topics."""
        related = []

        # Search for JIRA tickets
        for ticket in entities.get("jira_tickets", [])[:3]:
            results = self.memory.search(ticket, limit=5)
            for mem in results:
                if mem.session_id != self._current_session:
                    related.append(
                        {
                            "session_id": mem.session_id,
                            "link_reason": f"Both mention {ticket}",
                            "link_type": "jira_ticket",
                        }
                    )

        # Search for topics
        for topic in topics:
            results = self.memory.search(topic, limit=3)
            for mem in results:
                if mem.session_id != self._current_session:
                    related.append(
                        {
                            "session_id": mem.session_id,
                            "link_reason": f"Both discuss {topic}",
                            "link_type": "topic",
                        }
                    )

        # Deduplicate
        seen = set()
        unique = []
        for r in related:
            key = r["session_id"]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:10]

    def _generate_session_summary(self) -> str:
        """Generate a summary of the session."""
        parts = [f"{self._message_count} messages"]

        if self._session_entities["jira_tickets"]:
            parts.append(
                f"JIRA: {', '.join(list(self._session_entities['jira_tickets'])[:3])}"
            )

        if self._session_topics:
            parts.append(f"Topics: {', '.join(list(self._session_topics)[:3])}")

        return " | ".join(parts) if parts else "Session summary"


# Convenience alias - allows `from agentic_brain.memory import Memory`
# to get the new unified system
Memory = UnifiedMemory


# ============================================================================
# FACTORY FUNCTIONS & CONVENIENCE ACCESSORS
# ============================================================================

# Global instances (singletons for convenience)
_unified_memory: Optional[UnifiedMemory] = None
_session_hooks: Optional[SessionHooks] = None
_session_stitcher: Optional[SessionStitcher] = None


def get_unified_memory(**kwargs) -> UnifiedMemory:
    """
    Get a unified memory instance.

    This is the recommended way to get memory in agentic-brain.
    Works without external dependencies.

    Returns:
        UnifiedMemory instance
    """
    global _unified_memory
    if _unified_memory is None:
        _unified_memory = UnifiedMemory(**kwargs)
    return _unified_memory


def get_session_hooks(
    enable_kafka: bool = False, enable_neo4j: bool = False
) -> SessionHooks:
    """
    Get or create the global session hooks instance.

    Args:
        enable_kafka: Enable event bus publishing
        enable_neo4j: Enable Neo4j storage

    Returns:
        SessionHooks instance
    """
    global _session_hooks
    if _session_hooks is None:
        mem = get_unified_memory()
        _session_hooks = SessionHooks(
            memory=mem, enable_kafka=enable_kafka, enable_neo4j=enable_neo4j
        )
    return _session_hooks


def get_session_stitcher() -> SessionStitcher:
    """
    Get or create the global session stitcher instance.

    Returns:
        SessionStitcher instance
    """
    global _session_stitcher
    if _session_stitcher is None:
        mem = get_unified_memory()
        _session_stitcher = SessionStitcher(memory=mem)
    return _session_stitcher


# Shell-callable hook functions (for CLI integration)
def on_session_start(data_json: str = "{}") -> str:
    """Shell-callable session start hook."""
    hooks = get_session_hooks()
    data = json.loads(data_json) if data_json else {}
    result = hooks.on_session_start(data)
    return json.dumps(result)


def on_session_end(data_json: str = "{}") -> str:
    """Shell-callable session end hook."""
    hooks = get_session_hooks()
    data = json.loads(data_json) if data_json else {}
    result = hooks.on_session_end(data)
    return json.dumps(result)


def on_user_prompt(prompt: str, data_json: str = "{}") -> str:
    """Shell-callable user prompt hook."""
    hooks = get_session_hooks()
    data = json.loads(data_json) if data_json else {}
    result = hooks.on_user_prompt(prompt, data)
    return json.dumps(result)


def on_assistant_response(response: str, data_json: str = "{}") -> str:
    """Shell-callable assistant response hook."""
    hooks = get_session_hooks()
    data = json.loads(data_json) if data_json else {}
    result = hooks.on_assistant_response(response, data)
    return json.dumps(result)


def on_tool_use(
    tool_name: str, phase: str = "pre", args_json: str = "{}", result: str = ""
) -> str:
    """Shell-callable tool use hook."""
    hooks = get_session_hooks()
    args = json.loads(args_json) if args_json else {}
    result_obj = hooks.on_tool_use(tool_name, args, phase, result)
    return json.dumps(result_obj)


def on_voice_input(text: str, lady: Optional[str] = None) -> str:
    """Shell-callable voice input hook."""
    hooks = get_session_hooks()
    result = hooks.on_voice_input(text, lady)
    return json.dumps(result)


# Session stitching convenience functions
def stitch_message(message: str, session_id: Optional[str] = None) -> dict:
    """Process a message and return related sessions."""
    stitcher = get_session_stitcher()
    return stitcher.process_message(message, session_id)


def find_related_sessions(
    entities: Optional[list[str]] = None, topics: Optional[list[str]] = None
) -> list[dict]:
    """Find sessions related to entities or topics."""
    stitcher = get_session_stitcher()
    return stitcher.find_related_sessions(entities=entities, topics=topics)


def get_session_context(session_id: Optional[str] = None) -> dict:
    """Get context for current or specified session."""
    stitcher = get_session_stitcher()
    return stitcher.get_session_context(session_id)
