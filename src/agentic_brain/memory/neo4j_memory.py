# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Neo4j-backed conversational memory with entity linking.

Provides persistent conversation storage with:
- Conversation history in graph structure
- Entity extraction and linking
- Topic-based memory retrieval
- Temporal memory queries (what did we discuss when?)
- Memory summarization and compression
- Cross-session memory continuity

Example:
    >>> from agentic_brain.memory.neo4j_memory import ConversationMemory
    >>> memory = ConversationMemory()
    >>> await memory.add_message("user", "Tell me about Python")
    >>> await memory.add_message("assistant", "Python is a programming language")
    >>> history = await memory.get_conversation_history(limit=10)
    >>> related = await memory.query_by_topic("Python")
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from neo4j import GraphDatabase

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    GraphDatabase = None  # type: ignore
    NEO4J_AVAILABLE = False


@dataclass
class Message:
    """A single conversation message."""

    id: str
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime
    session_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    entities: List[str] = field(default_factory=list)
    importance: float = 0.5
    access_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "metadata": self.metadata,
            "entities": self.entities,
            "importance": self.importance,
            "access_count": self.access_count,
        }


@dataclass
class MemoryConfig:
    """Configuration for conversation memory."""

    # Use shared neo4j pool
    use_pool: bool = True

    # Entity extraction
    extract_entities: bool = True
    min_entity_length: int = 3

    # Summarization
    auto_summarize: bool = True
    summarize_threshold: int = 50  # messages before auto-summarize
    summary_window: int = 20  # messages per summary

    # Compression
    compress_old_memories: bool = True
    compress_after_days: int = 30

    # Retrieval
    max_history: int = 100
    include_metadata: bool = True

    # Importance scoring (Mem0-inspired)
    importance_keywords: List[str] = field(
        default_factory=lambda: [
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
        ]
    )
    base_importance: float = 0.5

    # Memory decay (Mem0-inspired)
    decay_enabled: bool = True
    decay_rate: float = 0.01  # importance lost per day
    min_importance: float = 0.1  # floor - memories never fully disappear
    reinforce_boost: float = 0.15  # boost when memory is accessed


class ConversationMemory:
    """
    Neo4j-backed conversation memory with entity linking.

    Graph structure:
        (Session)-[:CONTAINS]->(Message)-[:NEXT]->(Message)
        (Message)-[:MENTIONS]->(Entity)
        (Entity)-[:DISCUSSED_IN]->(Session)
        (Session)-[:SUMMARIZED_BY]->(Summary)

    Features:
    - Persistent conversation storage
    - Entity extraction and linking across conversations
    - Topic-based memory queries
    - Temporal queries (what did we discuss about X last week?)
    - Automatic summarization of long conversations
    - Memory compression for old conversations
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        config: Optional[MemoryConfig] = None,
    ):
        """
        Initialize conversation memory.

        Args:
            session_id: Unique session identifier (generated if not provided)
            config: Memory configuration
        """
        self.session_id = session_id or self._generate_session_id()
        self.config = config or MemoryConfig()
        self._initialized = False
        self._message_count = 0

    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now(UTC).isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:16]

    def _get_session(self):
        """Get Neo4j session using lazy pool."""
        if self.config.use_pool:
            from agentic_brain.core.neo4j_pool import get_session

            return get_session()
        else:
            if not NEO4J_AVAILABLE or GraphDatabase is None:
                raise ImportError(
                    "neo4j package is required. Install with: pip install neo4j"
                )

            driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", ""))
            return driver.session()

    async def initialize(self) -> None:
        """
        Initialize memory schema.

        Creates:
        - Node labels: Session, Message, Entity, Summary
        - Relationships: CONTAINS, NEXT, MENTIONS, DISCUSSED_IN, SUMMARIZED_BY,
                         LINKS_TO (cross-session)
        - Indexes for performance (including importance for decay queries)
        """
        if self._initialized:
            return

        with self._get_session() as session:
            # Create constraints
            session.run(
                """
                CREATE CONSTRAINT session_id IF NOT EXISTS
                FOR (s:Session) REQUIRE s.id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT message_id IF NOT EXISTS
                FOR (m:Message) REQUIRE m.id IS UNIQUE
                """
            )
            session.run(
                """
                CREATE CONSTRAINT entity_name IF NOT EXISTS
                FOR (e:Entity) REQUIRE e.name IS UNIQUE
                """
            )

            # Create indexes
            session.run(
                "CREATE INDEX message_timestamp IF NOT EXISTS FOR (m:Message) ON (m.timestamp)"
            )
            session.run(
                "CREATE INDEX message_importance IF NOT EXISTS FOR (m:Message) ON (m.importance)"
            )
            session.run(
                "CREATE INDEX session_timestamp IF NOT EXISTS FOR (s:Session) ON (s.started_at)"
            )
            session.run(
                "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)"
            )

            # Create session node if doesn't exist
            session.run(
                """
                MERGE (s:Session {id: $session_id})
                ON CREATE SET s.started_at = datetime(),
                              s.message_count = 0
                """,
                session_id=self.session_id,
            )

        self._initialized = True
        logger.info(f"Conversation memory initialized for session {self.session_id}")

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Add a message to conversation history.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata dict

        Returns:
            Message ID
        """
        if not self._initialized:
            await self.initialize()

        # Generate message ID
        msg_id = hashlib.sha256(
            f"{self.session_id}_{content}_{datetime.now(UTC)}".encode()
        ).hexdigest()[:16]
        timestamp = datetime.now(UTC).isoformat()
        metadata = metadata or {}

        # Score importance (Mem0-inspired)
        importance = self._score_importance(content, role, metadata)

        with self._get_session() as session:
            # Create message node with importance
            session.run(
                """
                CREATE (m:Message {
                    id: $msg_id,
                    role: $role,
                    content: $content,
                    timestamp: $timestamp,
                    session_id: $session_id,
                    metadata: $metadata,
                    importance: $importance,
                    access_count: 0,
                    last_accessed: $timestamp
                })
                """,
                msg_id=msg_id,
                role=role,
                content=content,
                timestamp=timestamp,
                session_id=self.session_id,
                metadata=metadata,
                importance=importance,
            )

            # Link to session
            session.run(
                """
                MATCH (s:Session {id: $session_id})
                MATCH (m:Message {id: $msg_id})
                MERGE (s)-[:CONTAINS]->(m)
                SET s.message_count = s.message_count + 1,
                    s.last_updated = datetime()
                """,
                session_id=self.session_id,
                msg_id=msg_id,
            )

            # Link to previous message (maintain conversation order)
            session.run(
                """
                MATCH (s:Session {id: $session_id})-[:CONTAINS]->(prev:Message)
                WHERE NOT exists((prev)-[:NEXT]->())
                  AND prev.id <> $msg_id
                WITH prev
                ORDER BY prev.timestamp DESC
                LIMIT 1
                MATCH (m:Message {id: $msg_id})
                MERGE (prev)-[:NEXT]->(m)
                RETURN prev.id AS prev_id
                """,
                session_id=self.session_id,
                msg_id=msg_id,
            )

            # Extract and link entities if enabled (batched UNWIND)
            if self.config.extract_entities:
                entities = self._extract_entities(content)
                if entities:
                    entity_params = [
                        {"name": name, "type": etype}
                        for name, etype in entities
                    ]
                    session.run(
                        """
                        UNWIND $entities AS ent
                        MERGE (e:Entity {name: ent.name})
                        ON CREATE SET e.type = ent.type,
                                      e.first_seen = datetime(),
                                      e.mention_count = 0
                        SET e.last_seen = datetime(),
                            e.mention_count = e.mention_count + 1
                        WITH e
                        MATCH (m:Message {id: $msg_id})
                        MERGE (m)-[:MENTIONS]->(e)
                        WITH e
                        MATCH (s:Session {id: $session_id})
                        MERGE (e)-[r:DISCUSSED_IN]->(s)
                        ON CREATE SET r.first_mentioned = datetime(),
                                      r.mention_count = 0
                        SET r.last_mentioned = datetime(),
                            r.mention_count = r.mention_count + 1
                        """,
                        entities=entity_params,
                        msg_id=msg_id,
                        session_id=self.session_id,
                    )

        self._message_count += 1

        # Auto-summarize if threshold reached
        if (
            self.config.auto_summarize
            and self._message_count % self.config.summarize_threshold == 0
        ):
            await self.summarize_recent()

        logger.debug(f"Added message {msg_id} to session {self.session_id}")
        return msg_id

    # =========================================================================
    # IMPORTANCE SCORING (Mem0-inspired)
    # =========================================================================

    def _score_importance(
        self,
        content: str,
        role: str,
        metadata: Dict[str, Any],
    ) -> float:
        """
        Score memory importance based on content signals.

        Inspired by Mem0's relevance scoring: analyses keyword presence,
        content length, role, and metadata hints to assign a 0.0-1.0 score.

        Args:
            content: Message text
            role: Message role
            metadata: Additional metadata

        Returns:
            Importance score between 0.0 and 1.0
        """
        score = self.config.base_importance
        text_lower = content.lower()

        # Keyword boost - high-signal words increase importance
        keyword_hits = sum(
            1 for kw in self.config.importance_keywords if kw in text_lower
        )
        score += min(keyword_hits * 0.08, 0.3)

        # Length signal - very short messages are less important
        word_count = len(content.split())
        if word_count < 5:
            score -= 0.1
        elif word_count > 50:
            score += 0.1

        # Questions are important (user asking = needs answer)
        if "?" in content:
            score += 0.05

        # Code blocks are important (technical content)
        if "```" in content or "def " in content or "class " in content:
            score += 0.1

        # Entity density - more entities = more important
        entities = self._extract_entities(content)
        if len(entities) >= 3:
            score += 0.1

        # Metadata overrides
        if metadata.get("importance"):
            try:
                score = float(metadata["importance"])
            except (ValueError, TypeError):
                pass
        if metadata.get("pinned"):
            score = max(score, 0.9)

        return max(0.0, min(1.0, score))

    # =========================================================================
    # MEMORY DECAY (Mem0-inspired)
    # =========================================================================

    def _calculate_decayed_importance(
        self,
        base_importance: float,
        created_at: datetime,
        access_count: int = 0,
        last_accessed: Optional[datetime] = None,
    ) -> float:
        """
        Apply time-based decay to importance score.

        Memories fade over time unless reinforced by access. This mirrors
        Mem0's approach where older memories naturally become less relevant
        but can be boosted by retrieval (spaced repetition effect).

        Args:
            base_importance: Original importance score
            created_at: When the memory was created
            access_count: How many times this memory has been accessed
            last_accessed: When the memory was last accessed

        Returns:
            Decayed importance score
        """
        if not self.config.decay_enabled:
            return base_importance

        now = datetime.now(UTC)

        # Calculate days since last relevant interaction
        reference_time = last_accessed or created_at
        if isinstance(reference_time, str):
            reference_time = datetime.fromisoformat(reference_time)
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=UTC)

        days_elapsed = max(0.0, (now - reference_time).total_seconds() / 86400)

        # Exponential decay from last access
        decay = math.exp(-self.config.decay_rate * days_elapsed)
        decayed = base_importance * decay

        # Reinforcement bonus: more accesses = slower decay
        if access_count > 0:
            reinforcement = min(access_count * 0.02, 0.2)
            decayed += reinforcement

        return max(self.config.min_importance, min(1.0, decayed))

    async def apply_decay(self) -> int:
        """
        Apply memory decay to all messages in the current session.

        Returns:
            Number of messages updated
        """
        if not self._initialized:
            await self.initialize()

        with self._get_session() as session:
            result = session.run(
                """
                MATCH (s:Session {id: $session_id})-[:CONTAINS]->(m:Message)
                WHERE m.importance > $min_importance
                RETURN m.id AS id, m.importance AS importance,
                       m.timestamp AS timestamp, m.access_count AS access_count,
                       m.last_accessed AS last_accessed
                """,
                session_id=self.session_id,
                min_importance=self.config.min_importance,
            )

            updates = []
            for record in result:
                created = datetime.fromisoformat(record["timestamp"])
                new_importance = self._calculate_decayed_importance(
                    base_importance=record["importance"],
                    created_at=created,
                    access_count=record["access_count"] or 0,
                    last_accessed=(
                        datetime.fromisoformat(record["last_accessed"])
                        if record["last_accessed"]
                        else None
                    ),
                )
                if abs(new_importance - record["importance"]) > 0.001:
                    updates.append({"id": record["id"], "importance": new_importance})

            updated = len(updates)
            if updates:
                session.run(
                    """
                    UNWIND $updates AS u
                    MATCH (m:Message {id: u.id})
                    SET m.importance = u.importance
                    """,
                    updates=updates,
                )

            logger.info(f"Applied decay to {updated} messages")
            return updated

    async def reinforce_memory(self, message_id: str) -> float:
        """
        Reinforce a memory (boost importance on access).

        Call this when a memory is retrieved/used to prevent decay.

        Args:
            message_id: ID of the message to reinforce

        Returns:
            New importance score
        """
        if not self._initialized:
            await self.initialize()

        with self._get_session() as session:
            result = session.run(
                """
                MATCH (m:Message {id: $msg_id})
                SET m.access_count = coalesce(m.access_count, 0) + 1,
                    m.last_accessed = $now,
                    m.importance = CASE
                        WHEN m.importance + $boost > 1.0 THEN 1.0
                        ELSE m.importance + $boost
                    END
                RETURN m.importance AS importance
                """,
                msg_id=message_id,
                now=datetime.now(UTC).isoformat(),
                boost=self.config.reinforce_boost,
            )

            record = result.single()
            new_importance = record["importance"] if record else 0.5
            logger.debug(f"Reinforced memory {message_id}: importance={new_importance}")
            return new_importance

    # =========================================================================
    # ENTITY EXTRACTION (Enhanced, Mem0-inspired)
    # =========================================================================

    def _extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract entities from text using pattern matching.

        Enhanced extraction inspired by Mem0's entity identification:
        - Capitalized words → PERSON/CONCEPT
        - Email patterns → EMAIL
        - URL patterns → URL
        - Ticket patterns (SD-1234) → TICKET
        - Multi-word proper nouns → PERSON/ORGANIZATION
        - File paths → FILE
        - Technology names → TECHNOLOGY

        Args:
            text: Input text

        Returns:
            List of (entity_name, entity_type) tuples
        """
        entities: List[Tuple[str, str]] = []

        # Email addresses
        for match in re.finditer(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
            entities.append((match.group(), "EMAIL"))

        # URLs
        for match in re.finditer(r"https?://[^\s<>\"']+", text):
            entities.append((match.group(), "URL"))

        # JIRA-style tickets (SD-1234, PROJ-456)
        for match in re.finditer(r"\b[A-Z]{2,6}-\d{1,6}\b", text):
            entities.append((match.group(), "TICKET"))

        # File paths
        for match in re.finditer(
            r"(?:~/|/[\w]+/|\./)[\w/.-]+\.\w+", text
        ):
            entities.append((match.group(), "FILE"))

        # Technology names (common patterns)
        tech_patterns = re.compile(
            r"\b(Python|JavaScript|TypeScript|Java|Neo4j|Docker|Redis|React|"
            r"Angular|Vue|Node\.js|FastAPI|Django|Flask|PostgreSQL|MySQL|"
            r"MongoDB|Kubernetes|AWS|Azure|GCP|Git|GitHub|Bitbucket|JIRA|"
            r"Safari|Chrome|macOS|Linux|Windows|VoiceOver)\b",
            re.IGNORECASE,
        )
        for match in tech_patterns.finditer(text):
            entities.append((match.group(), "TECHNOLOGY"))

        # Multi-word proper nouns (e.g., "Steve Taylor", "Joseph Webber")
        for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text):
            name = match.group()
            # Skip common phrases
            if name.lower() not in {"the end", "the other"}:
                entities.append((name, "PERSON"))

        # Single capitalized words (concepts, organizations)
        for word in text.split():
            cleaned = word.strip(".,!?;:()[]{}\"'")
            if (
                len(cleaned) >= self.config.min_entity_length
                and cleaned[0].isupper()
                and not cleaned.isupper()  # skip ALL CAPS (likely acronyms already caught)
                and cleaned not in {"The", "This", "That", "These", "Those", "When",
                                    "Where", "What", "Which", "How", "Who", "Why",
                                    "But", "And", "For", "Not", "With", "From"}
            ):
                # Classify based on suffix
                entity_type = "CONCEPT"
                if cleaned.endswith(("Corp", "Inc", "Ltd", "LLC", "Pty")):
                    entity_type = "ORGANIZATION"
                entities.append((cleaned, entity_type))

        # Deduplicate (keep first occurrence's type)
        seen: set[str] = set()
        unique: List[Tuple[str, str]] = []
        for name, etype in entities:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                unique.append((name, etype))
        return unique

    # =========================================================================
    # CROSS-SESSION MEMORY LINKING (Mem0-inspired)
    # =========================================================================

    async def link_related_sessions(
        self,
        other_session_id: str,
        relationship: str = "RELATED_TO",
        shared_entities: Optional[List[str]] = None,
    ) -> bool:
        """
        Link two sessions that share context or entities.

        Inspired by Mem0's cross-memory linking: sessions that discuss
        the same entities or topics are connected for better retrieval.

        Args:
            other_session_id: Session to link to
            relationship: Relationship type
            shared_entities: Entities both sessions discuss

        Returns:
            True if link was created
        """
        if not self._initialized:
            await self.initialize()

        with self._get_session() as session:
            session.run(
                """
                MATCH (s1:Session {id: $session1})
                MATCH (s2:Session {id: $session2})
                MERGE (s1)-[r:LINKS_TO]->(s2)
                SET r.relationship = $rel,
                    r.shared_entities = $entities,
                    r.linked_at = datetime()
                """,
                session1=self.session_id,
                session2=other_session_id,
                rel=relationship,
                entities=shared_entities or [],
            )
            logger.info(
                f"Linked session {self.session_id} -> {other_session_id} ({relationship})"
            )
            return True

    async def find_related_sessions(
        self,
        min_shared_entities: int = 1,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find sessions related to the current one via shared entities.

        Args:
            min_shared_entities: Minimum shared entities to count as related
            limit: Maximum sessions to return

        Returns:
            List of related session dicts with shared entity info
        """
        if not self._initialized:
            await self.initialize()

        with self._get_session() as session:
            result = session.run(
                """
                MATCH (s1:Session {id: $session_id})-[:CONTAINS]->(m1:Message)
                      -[:MENTIONS]->(e:Entity)<-[:MENTIONS]-(m2:Message)
                      <-[:CONTAINS]-(s2:Session)
                WHERE s2.id <> $session_id
                WITH s2, collect(DISTINCT e.name) AS shared_entities
                WHERE size(shared_entities) >= $min_shared
                RETURN s2.id AS session_id,
                       s2.started_at AS started_at,
                       s2.message_count AS message_count,
                       shared_entities
                ORDER BY size(shared_entities) DESC
                LIMIT $limit
                """,
                session_id=self.session_id,
                min_shared=min_shared_entities,
                limit=limit,
            )

            return [
                {
                    "session_id": r["session_id"],
                    "started_at": r["started_at"],
                    "message_count": r["message_count"],
                    "shared_entities": r["shared_entities"],
                }
                for r in result
            ]

    async def get_entity_timeline(
        self,
        entity_name: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get the timeline of an entity across all sessions.

        Args:
            entity_name: Entity to trace
            limit: Max results

        Returns:
            Timeline of mentions across sessions
        """
        if not self._initialized:
            await self.initialize()

        with self._get_session() as session:
            result = session.run(
                """
                MATCH (e:Entity)
                WHERE toLower(e.name) = toLower($name)
                WITH e
                MATCH (m:Message)-[:MENTIONS]->(e)
                RETURN m.id AS message_id,
                       m.content AS content,
                       m.timestamp AS timestamp,
                       m.session_id AS session_id,
                       m.importance AS importance
                ORDER BY m.timestamp DESC
                LIMIT $limit
                """,
                name=entity_name,
                limit=limit,
            )

            return [
                {
                    "message_id": r["message_id"],
                    "content": r["content"],
                    "timestamp": r["timestamp"],
                    "session_id": r["session_id"],
                    "importance": r["importance"],
                }
                for r in result
            ]

    # =========================================================================
    # MEMORY SUMMARIZATION (Enhanced, Mem0-inspired)
    # =========================================================================

    async def summarize_and_condense(
        self,
        older_than_days: int = 7,
        importance_threshold: float = 0.3,
    ) -> Dict[str, Any]:
        """
        Condense old, low-importance memories into summaries.

        Mem0-inspired: instead of just compressing, this creates proper
        summaries that preserve key information while removing noise.
        High-importance memories are preserved regardless of age.

        Args:
            older_than_days: Only condense memories older than this
            importance_threshold: Only condense memories below this importance

        Returns:
            Dict with condensation stats
        """
        if not self._initialized:
            await self.initialize()

        cutoff = (datetime.now(UTC) - timedelta(days=older_than_days)).isoformat()

        with self._get_session() as session:
            # Find old, low-importance messages
            result = session.run(
                """
                MATCH (m:Message)
                WHERE m.timestamp < $cutoff
                  AND m.importance < $threshold
                  AND NOT coalesce(m.compressed, false)
                WITH m
                ORDER BY m.timestamp
                RETURN m.id AS id, m.content AS content,
                       m.role AS role, m.session_id AS session_id,
                       m.importance AS importance
                """,
                cutoff=cutoff,
                threshold=importance_threshold,
            )

            messages = [dict(r) for r in result]
            if not messages:
                return {"condensed": 0, "preserved": 0, "summary_created": False}

            # Group by session for summarization
            by_session: Dict[str, list] = {}
            for msg in messages:
                sid = msg["session_id"]
                by_session.setdefault(sid, []).append(msg)

            condensed_count = 0
            for sid, msgs in by_session.items():
                # Create condensed summary
                content_parts = [
                    f"{m['role']}: {m['content'][:200]}" for m in msgs[:20]
                ]
                summary_text = (
                    f"Condensed {len(msgs)} messages: "
                    + " | ".join(content_parts[:5])
                )
                if len(msgs) > 5:
                    summary_text += f" [... and {len(msgs) - 5} more]"

                summary_id = hashlib.sha256(
                    f"condense_{sid}_{datetime.now(UTC)}".encode()
                ).hexdigest()[:16]

                session.run(
                    """
                    CREATE (s:Summary {
                        id: $summary_id,
                        content: $summary,
                        message_count: $count,
                        timestamp: datetime(),
                        summary_type: 'condensation'
                    })
                    """,
                    summary_id=summary_id,
                    summary=summary_text[:2000],
                    count=len(msgs),
                )

                # Mark original messages as compressed
                msg_ids = [m["id"] for m in msgs]
                session.run(
                    """
                    MATCH (m:Message)
                    WHERE m.id IN $ids
                    SET m.compressed = true,
                        m.compressed_at = datetime(),
                        m.condensed_into = $summary_id
                    """,
                    ids=msg_ids,
                    summary_id=summary_id,
                )
                condensed_count += len(msgs)

            logger.info(f"Condensed {condensed_count} old memories across {len(by_session)} sessions")
            return {
                "condensed": condensed_count,
                "sessions": len(by_session),
                "summary_created": True,
            }

    async def get_conversation_history(
        self,
        limit: Optional[int] = None,
        since: Optional[datetime] = None,
        include_entities: bool = False,
    ) -> List[Message]:
        """
        Get conversation history.

        Args:
            limit: Maximum number of messages (None for all)
            since: Only messages after this timestamp
            include_entities: Whether to include extracted entities

        Returns:
            List of Message objects in chronological order
        """
        if not self._initialized:
            await self.initialize()

        limit = limit or self.config.max_history
        messages = []

        with self._get_session() as session:
            query = """
                MATCH (s:Session {id: $session_id})-[:CONTAINS]->(m:Message)
            """

            if since:
                query += " WHERE m.timestamp >= $since"

            query += """
                OPTIONAL MATCH (m)-[:MENTIONS]->(e:Entity)
                WITH m, collect(e.name) AS entities
                RETURN m.id AS id,
                       m.role AS role,
                       m.content AS content,
                       m.timestamp AS timestamp,
                       m.session_id AS session_id,
                       m.metadata AS metadata,
                       entities
                ORDER BY m.timestamp ASC
            """

            if limit:
                query += " LIMIT $limit"

            params = {"session_id": self.session_id}
            if since:
                params["since"] = since.isoformat()
            if limit:
                params["limit"] = limit

            result = session.run(query, **params)

            for record in result:
                msg = Message(
                    id=record["id"],
                    role=record["role"],
                    content=record["content"],
                    timestamp=datetime.fromisoformat(record["timestamp"]),
                    session_id=record["session_id"],
                    metadata=record["metadata"] or {},
                    entities=record["entities"] if include_entities else [],
                )
                messages.append(msg)

        return messages

    async def query_by_topic(
        self,
        topic: str,
        limit: int = 10,
        since: Optional[datetime] = None,
    ) -> List[Message]:
        """
        Query messages related to a specific topic.

        Args:
            topic: Topic/entity to search for
            limit: Maximum results
            since: Only messages after this timestamp

        Returns:
            List of relevant messages
        """
        if not self._initialized:
            await self.initialize()

        messages = []
        with self._get_session() as session:
            query = """
                MATCH (e:Entity)
                WHERE toLower(e.name) CONTAINS toLower($topic)
                WITH e
                MATCH (m:Message)-[:MENTIONS]->(e)
            """

            if since:
                query += " WHERE m.timestamp >= $since"

            query += """
                OPTIONAL MATCH (m)-[:MENTIONS]->(related:Entity)
                WITH DISTINCT m, collect(related.name) AS entities
                RETURN m.id AS id,
                       m.role AS role,
                       m.content AS content,
                       m.timestamp AS timestamp,
                       m.session_id AS session_id,
                       m.metadata AS metadata,
                       entities
                ORDER BY m.timestamp DESC
                LIMIT $limit
            """

            params = {"topic": topic, "limit": limit}
            if since:
                params["since"] = since.isoformat()

            result = session.run(query, **params)

            for record in result:
                msg = Message(
                    id=record["id"],
                    role=record["role"],
                    content=record["content"],
                    timestamp=datetime.fromisoformat(record["timestamp"]),
                    session_id=record["session_id"],
                    metadata=record["metadata"] or {},
                    entities=record["entities"],
                )
                messages.append(msg)

        return messages

    async def query_by_timeframe(
        self,
        start: datetime,
        end: datetime,
        entity: Optional[str] = None,
    ) -> List[Message]:
        """
        Query messages within a timeframe.

        Args:
            start: Start timestamp
            end: End timestamp
            entity: Optional entity filter

        Returns:
            List of messages in timeframe
        """
        if not self._initialized:
            await self.initialize()

        messages = []
        with self._get_session() as session:
            if entity:
                query = """
                    MATCH (m:Message)-[:MENTIONS]->(e:Entity {name: $entity})
                    WHERE m.timestamp >= $start AND m.timestamp <= $end
                    OPTIONAL MATCH (m)-[:MENTIONS]->(related:Entity)
                    WITH DISTINCT m, collect(related.name) AS entities
                    RETURN m.id AS id,
                           m.role AS role,
                           m.content AS content,
                           m.timestamp AS timestamp,
                           m.session_id AS session_id,
                           m.metadata AS metadata,
                           entities
                    ORDER BY m.timestamp ASC
                """
                params = {
                    "entity": entity,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }
            else:
                query = """
                    MATCH (m:Message)
                    WHERE m.timestamp >= $start AND m.timestamp <= $end
                    OPTIONAL MATCH (m)-[:MENTIONS]->(e:Entity)
                    WITH m, collect(e.name) AS entities
                    RETURN m.id AS id,
                           m.role AS role,
                           m.content AS content,
                           m.timestamp AS timestamp,
                           m.session_id AS session_id,
                           m.metadata AS metadata,
                           entities
                    ORDER BY m.timestamp ASC
                """
                params = {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                }

            result = session.run(query, **params)

            for record in result:
                msg = Message(
                    id=record["id"],
                    role=record["role"],
                    content=record["content"],
                    timestamp=datetime.fromisoformat(record["timestamp"]),
                    session_id=record["session_id"],
                    metadata=record["metadata"] or {},
                    entities=record["entities"],
                )
                messages.append(msg)

        return messages

    async def summarize_recent(self, window: Optional[int] = None) -> str:
        """
        Summarize recent conversation.

        Args:
            window: Number of messages to summarize (uses config default if not provided)

        Returns:
            Summary text
        """
        window = window or self.config.summary_window

        # Get recent messages
        messages = await self.get_conversation_history(limit=window)

        if not messages:
            return "No messages to summarize."

        # Create simple summary
        # In production: use LLM for better summarization
        user_msgs = [m for m in messages if m.role == "user"]
        assistant_msgs = [m for m in messages if m.role == "assistant"]

        summary_parts = [
            f"Conversation summary ({len(messages)} messages):",
            f"User messages: {len(user_msgs)}",
            f"Assistant messages: {len(assistant_msgs)}",
        ]

        # Extract discussed topics
        all_entities = set()
        for msg in messages:
            all_entities.update(msg.entities)

        if all_entities:
            summary_parts.append(
                f"Topics discussed: {', '.join(list(all_entities)[:10])}"
            )

        summary = "\n".join(summary_parts)

        # Store summary
        with self._get_session() as session:
            summary_id = hashlib.sha256(
                f"{self.session_id}_{datetime.now(UTC)}".encode()
            ).hexdigest()[:16]

            session.run(
                """
                CREATE (sum:Summary {
                    id: $summary_id,
                    content: $summary,
                    message_count: $msg_count,
                    timestamp: datetime()
                })
                """,
                summary_id=summary_id,
                summary=summary,
                msg_count=len(messages),
            )

            session.run(
                """
                MATCH (s:Session {id: $session_id})
                MATCH (sum:Summary {id: $summary_id})
                MERGE (s)-[:SUMMARIZED_BY]->(sum)
                """,
                session_id=self.session_id,
                summary_id=summary_id,
            )

        logger.info(f"Created summary {summary_id} for {len(messages)} messages")
        return summary

    async def compress_old_memories(self, days: Optional[int] = None) -> int:
        """
        Compress old conversation memories.

        Replaces old message chains with summaries to save space
        while preserving key information.

        Args:
            days: Messages older than this will be compressed

        Returns:
            Number of messages compressed
        """
        days = days or self.config.compress_after_days
        cutoff = datetime.now(UTC) - timedelta(days=days)

        with self._get_session() as session:
            # Find old messages without summaries
            result = session.run(
                """
                MATCH (m:Message)
                WHERE m.timestamp < $cutoff
                  AND NOT exists((m)-[:SUMMARIZED_AS]->(:Summary))
                WITH m
                ORDER BY m.timestamp
                RETURN collect(m.id) AS message_ids,
                       count(m) AS count
                """,
                cutoff=cutoff.isoformat(),
            )

            record = result.single()
            if not record or record["count"] == 0:
                return 0

            message_ids = record["message_ids"]

            # In production: create proper summary using LLM
            # For now: mark as compressed
            session.run(
                """
                MATCH (m:Message)
                WHERE m.id IN $message_ids
                SET m.compressed = true,
                    m.compressed_at = datetime()
                """,
                message_ids=message_ids,
            )

        logger.info(f"Compressed {len(message_ids)} old messages")
        return len(message_ids)

    async def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the current session.

        Returns:
            Dict with message counts, entities, and other stats
        """
        if not self._initialized:
            await self.initialize()

        with self._get_session() as session:
            result = session.run(
                """
                MATCH (s:Session {id: $session_id})
                OPTIONAL MATCH (s)-[:CONTAINS]->(m:Message)
                OPTIONAL MATCH (m)-[:MENTIONS]->(e:Entity)
                WITH s,
                     count(DISTINCT m) AS msg_count,
                     count(DISTINCT e) AS entity_count,
                     collect(DISTINCT m.role) AS roles
                OPTIONAL MATCH (s)-[:SUMMARIZED_BY]->(sum:Summary)
                RETURN s.started_at AS started_at,
                       s.last_updated AS last_updated,
                       msg_count,
                       entity_count,
                       roles,
                       count(sum) AS summary_count
                """,
                session_id=self.session_id,
            )

            record = result.single()
            if record:
                return {
                    "session_id": self.session_id,
                    "started_at": record["started_at"],
                    "last_updated": record["last_updated"],
                    "message_count": record["msg_count"],
                    "entity_count": record["entity_count"],
                    "roles": record["roles"],
                    "summary_count": record["summary_count"],
                }

        return {"session_id": self.session_id, "message_count": 0}

    async def close(self) -> None:
        """Close and cleanup."""
        logger.info(f"Closing conversation memory for session {self.session_id}")
