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
                raise ImportError("neo4j package is required. Install with: pip install neo4j")

            driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", ""))
            return driver.session()

    async def initialize(self) -> None:
        """
        Initialize memory schema.

        Creates:
        - Node labels: Session, Message, Entity, Summary
        - Relationships: CONTAINS, NEXT, MENTIONS, DISCUSSED_IN, SUMMARIZED_BY
        - Indexes for performance
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

        with self._get_session() as session:
            # Create message node
            session.run(
                """
                CREATE (m:Message {
                    id: $msg_id,
                    role: $role,
                    content: $content,
                    timestamp: $timestamp,
                    session_id: $session_id,
                    metadata: $metadata
                })
                """,
                msg_id=msg_id,
                role=role,
                content=content,
                timestamp=timestamp,
                session_id=self.session_id,
                metadata=metadata,
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
            result = session.run(
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

            # Extract and link entities if enabled
            if self.config.extract_entities:
                entities = self._extract_entities(content)
                for entity_name, entity_type in entities:
                    session.run(
                        """
                        MERGE (e:Entity {name: $name})
                        ON CREATE SET e.type = $type,
                                      e.first_seen = datetime(),
                                      e.mention_count = 0
                        SET e.last_seen = datetime(),
                            e.mention_count = e.mention_count + 1
                        """,
                        name=entity_name,
                        type=entity_type,
                    )

                    # Link message to entity
                    session.run(
                        """
                        MATCH (m:Message {id: $msg_id})
                        MATCH (e:Entity {name: $name})
                        MERGE (m)-[:MENTIONS]->(e)
                        """,
                        msg_id=msg_id,
                        name=entity_name,
                    )

                    # Link entity to session
                    session.run(
                        """
                        MATCH (s:Session {id: $session_id})
                        MATCH (e:Entity {name: $name})
                        MERGE (e)-[r:DISCUSSED_IN]->(s)
                        ON CREATE SET r.first_mentioned = datetime(),
                                      r.mention_count = 0
                        SET r.last_mentioned = datetime(),
                            r.mention_count = r.mention_count + 1
                        """,
                        session_id=self.session_id,
                        name=entity_name,
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

    def _extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract entities from text.

        Simple implementation - in production use NER model.

        Args:
            text: Input text

        Returns:
            List of (entity_name, entity_type) tuples
        """
        entities = []
        words = text.split()

        for word in words:
            cleaned = word.strip(".,!?;:")
            if len(cleaned) >= self.config.min_entity_length and cleaned[0].isupper():
                # Simple heuristic - in production use spaCy/transformers
                entity_type = "CONCEPT"
                if "@" in cleaned:
                    entity_type = "EMAIL"
                elif cleaned.endswith("Corp") or cleaned.endswith("Inc"):
                    entity_type = "ORGANIZATION"

                entities.append((cleaned, entity_type))

        # Deduplicate
        return list(set(entities))

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
