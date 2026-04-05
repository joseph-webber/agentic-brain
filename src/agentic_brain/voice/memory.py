# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""GraphRAG Voice Memory — persistent voice utterance storage in Neo4j.

This module implements semantic voice memory using Neo4j as the backing store,
with sentence-transformer embeddings for similarity search.

Architecture
============

Nodes:
    - VoiceUtterance: Individual spoken utterance with embedding
    - VoiceConversation: Container for a conversation session

Relationships:
    - SPOKEN_BY: VoiceUtterance → speaker (Person or Voice Persona)
    - PART_OF: VoiceUtterance → VoiceConversation
    - DISCUSSES: VoiceConversation → Topic
    - FOLLOWS: VoiceUtterance → VoiceUtterance (temporal ordering)

Embeddings:
    - Uses sentence-transformers (all-MiniLM-L6-v2) → 384 dimensions
    - Stored as list[float] property on VoiceUtterance nodes
    - Vector similarity search via Neo4j native index

Usage::

    from agentic_brain.voice.memory import get_voice_memory, VoiceUtterance

    memory = get_voice_memory()

    # Store an utterance
    utt = VoiceUtterance(
        text="Good morning Joseph!",
        timestamp=datetime.now(UTC),
        speaker="Karen",
    )
    memory.store_utterance(utt, conversation_id="session-123")

    # Find similar past utterances
    similar = memory.recall_similar("morning greeting", limit=5)

    # Get conversation context
    context = memory.get_conversation_context("session-123", limit=10)
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 384

# Node labels
LABEL_UTTERANCE = "VoiceUtterance"
LABEL_CONVERSATION = "VoiceConversation"
LABEL_TOPIC = "Topic"

# Relationship types
REL_SPOKEN_BY = "SPOKEN_BY"
REL_PART_OF = "PART_OF"
REL_DISCUSSES = "DISCUSSES"
REL_FOLLOWS = "FOLLOWS"

# Vector index name
VECTOR_INDEX_NAME = "voice_utterance_embedding_index"


@dataclass
class VoiceUtterance:
    """A single voice utterance with optional embedding.

    Attributes:
        text: The transcribed or generated text.
        timestamp: When the utterance occurred (UTC).
        speaker: Speaker identifier ("user", "assistant", or voice persona name).
        embedding: Optional 384-dim vector from sentence-transformers.
        emotion: Optional detected emotion label.
        id: Unique identifier (auto-generated if not provided).
    """

    text: str
    timestamp: datetime
    speaker: str
    embedding: Optional[List[float]] = None
    emotion: Optional[str] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for Neo4j storage."""
        return {
            "id": self.id,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "speaker": self.speaker,
            "emotion": self.emotion,
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> VoiceUtterance:
        """Deserialize from Neo4j record."""
        ts = record.get("timestamp")
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts)
        elif ts is None:
            ts = datetime.now(UTC)

        embedding = record.get("embedding")
        if embedding is not None and not isinstance(embedding, list):
            embedding = list(embedding)

        return cls(
            id=record.get("id", str(uuid.uuid4())),
            text=record.get("text", ""),
            timestamp=ts,
            speaker=record.get("speaker", "unknown"),
            embedding=embedding,
            emotion=record.get("emotion"),
        )


@dataclass
class VoiceConversation:
    """A container for a voice conversation session.

    Attributes:
        session_id: Unique session identifier.
        started_at: When the conversation started (UTC).
        utterances: List of utterances in this conversation.
        topic: Optional topic label for the conversation.
    """

    session_id: str
    started_at: datetime
    utterances: List[VoiceUtterance] = field(default_factory=list)
    topic: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for Neo4j storage."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "topic": self.topic,
            "utterance_count": len(self.utterances),
        }


class VoiceMemory:
    """GraphRAG voice memory with Neo4j backend and embedding search.

    Thread-safe singleton that provides:
    - Persistent storage of voice utterances with embeddings
    - Semantic similarity search for recall
    - Conversation context retrieval
    - Automatic schema management

    Example::

        memory = VoiceMemory()

        # Store utterance
        utt = VoiceUtterance(
            text="Hello!",
            timestamp=datetime.now(UTC),
            speaker="user",
        )
        memory.store_utterance(utt, "session-1")

        # Find similar
        similar = memory.recall_similar("greeting", limit=3)
    """

    def __init__(self, *, use_neo4j: bool = True) -> None:
        """Initialize VoiceMemory.

        Args:
            use_neo4j: Whether to use Neo4j backend (fallback to in-memory).
        """
        self._lock = threading.Lock()
        self._embedder: Any = None
        self._neo4j_available = False
        self._use_neo4j = use_neo4j

        # In-memory fallback storage
        self._utterances: List[VoiceUtterance] = []
        self._conversations: Dict[str, VoiceConversation] = {}

        if use_neo4j:
            self._init_neo4j()

    def _init_neo4j(self) -> None:
        """Initialize Neo4j connection and schema."""
        try:
            from agentic_brain.core import neo4j_pool_health

            health = neo4j_pool_health()
            if health.get("status") == "healthy":
                self._neo4j_available = True
                self._ensure_schema()
                logger.debug("VoiceMemory: Neo4j connected")
            else:
                logger.warning(
                    "VoiceMemory: Neo4j unhealthy (%s), using in-memory fallback",
                    health.get("error", "unknown"),
                )
        except Exception as exc:
            logger.warning(
                "VoiceMemory: Neo4j unavailable (%s), using in-memory fallback",
                exc,
            )

    def _ensure_schema(self) -> None:
        """Create Neo4j indexes and constraints for voice memory."""
        if not self._neo4j_available:
            return

        try:
            from agentic_brain.core import neo4j_write

            # Uniqueness constraint on utterance id
            neo4j_write(
                f"""
                CREATE CONSTRAINT voice_utterance_id IF NOT EXISTS
                FOR (u:{LABEL_UTTERANCE}) REQUIRE u.id IS UNIQUE
                """
            )

            # Uniqueness constraint on conversation session_id
            neo4j_write(
                f"""
                CREATE CONSTRAINT voice_conversation_id IF NOT EXISTS
                FOR (c:{LABEL_CONVERSATION}) REQUIRE c.session_id IS UNIQUE
                """
            )

            # Index on timestamp for temporal queries
            neo4j_write(
                f"""
                CREATE INDEX voice_utterance_timestamp IF NOT EXISTS
                FOR (u:{LABEL_UTTERANCE}) ON (u.timestamp)
                """
            )

            # Index on speaker for filtering
            neo4j_write(
                f"""
                CREATE INDEX voice_utterance_speaker IF NOT EXISTS
                FOR (u:{LABEL_UTTERANCE}) ON (u.speaker)
                """
            )

            # Vector index for similarity search (Neo4j 5.x)
            try:
                neo4j_write(
                    f"""
                    CREATE VECTOR INDEX {VECTOR_INDEX_NAME} IF NOT EXISTS
                    FOR (u:{LABEL_UTTERANCE})
                    ON (u.embedding)
                    OPTIONS {{
                        indexConfig: {{
                            `vector.dimensions`: {EMBEDDING_DIM},
                            `vector.similarity_function`: 'cosine'
                        }}
                    }}
                    """
                )
                logger.debug("VoiceMemory: Vector index created/verified")
            except Exception as vec_exc:
                # Vector indexes require Neo4j 5.x with vector plugin
                logger.debug(
                    "VoiceMemory: Vector index not created (may need Neo4j 5.x): %s",
                    vec_exc,
                )

            logger.debug("VoiceMemory: Schema initialized")

        except Exception as exc:
            logger.warning("VoiceMemory: Schema setup failed: %s", exc)

    def _get_embedder(self) -> Any:
        """Lazy-load the sentence-transformer model."""
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
                logger.debug("VoiceMemory: Loaded sentence-transformers model")
            except ImportError:
                logger.warning(
                    "VoiceMemory: sentence-transformers not installed, "
                    "embedding disabled"
                )
                self._embedder = False  # Sentinel to avoid retry
        return self._embedder if self._embedder is not False else None

    def _compute_embedding(self, text: str) -> Optional[List[float]]:
        """Compute embedding vector for text."""
        embedder = self._get_embedder()
        if embedder is None:
            return None
        try:
            vec = embedder.encode(text, convert_to_numpy=True)
            return vec.tolist()
        except Exception as exc:
            logger.debug("VoiceMemory: Embedding failed: %s", exc)
            return None

    # ── Core API ─────────────────────────────────────────────────────

    def store_utterance(
        self,
        utterance: VoiceUtterance,
        conversation_id: str,
        *,
        compute_embedding: bool = True,
        previous_utterance_id: Optional[str] = None,
    ) -> str:
        """Store an utterance in Neo4j with optional embedding.

        Args:
            utterance: The utterance to store.
            conversation_id: Conversation session ID.
            compute_embedding: Whether to compute embedding (default True).
            previous_utterance_id: ID of the preceding utterance for FOLLOWS.

        Returns:
            The utterance ID.
        """
        # Compute embedding if requested and not already present
        if compute_embedding and utterance.embedding is None:
            utterance.embedding = self._compute_embedding(utterance.text)

        if self._neo4j_available:
            return self._store_neo4j(utterance, conversation_id, previous_utterance_id)
        else:
            return self._store_memory(utterance, conversation_id)

    def _store_neo4j(
        self,
        utterance: VoiceUtterance,
        conversation_id: str,
        previous_id: Optional[str],
    ) -> str:
        """Store utterance in Neo4j."""
        try:
            from agentic_brain.core import neo4j_write

            # Create/merge conversation node
            neo4j_write(
                f"""
                MERGE (c:{LABEL_CONVERSATION} {{session_id: $session_id}})
                ON CREATE SET c.started_at = $started_at
                """,
                session_id=conversation_id,
                started_at=datetime.now(UTC).isoformat(),
            )

            # Create utterance node with embedding
            props = utterance.to_dict()
            embedding = utterance.embedding

            neo4j_write(
                f"""
                CREATE (u:{LABEL_UTTERANCE} {{
                    id: $id,
                    text: $text,
                    timestamp: $timestamp,
                    speaker: $speaker,
                    emotion: $emotion,
                    embedding: $embedding
                }})
                WITH u
                MATCH (c:{LABEL_CONVERSATION} {{session_id: $conversation_id}})
                CREATE (u)-[:{REL_PART_OF}]->(c)
                """,
                id=props["id"],
                text=props["text"],
                timestamp=props["timestamp"],
                speaker=props["speaker"],
                emotion=props["emotion"],
                embedding=embedding,
                conversation_id=conversation_id,
            )

            # Create FOLLOWS relationship if previous utterance exists
            if previous_id:
                neo4j_write(
                    f"""
                    MATCH (prev:{LABEL_UTTERANCE} {{id: $prev_id}})
                    MATCH (curr:{LABEL_UTTERANCE} {{id: $curr_id}})
                    CREATE (curr)-[:{REL_FOLLOWS}]->(prev)
                    """,
                    prev_id=previous_id,
                    curr_id=utterance.id,
                )

            logger.debug(
                "VoiceMemory: Stored utterance %s in conversation %s",
                utterance.id,
                conversation_id,
            )
            return utterance.id

        except Exception as exc:
            logger.error("VoiceMemory: Neo4j store failed: %s", exc)
            # Fallback to memory
            return self._store_memory(utterance, conversation_id)

    def _store_memory(
        self,
        utterance: VoiceUtterance,
        conversation_id: str,
    ) -> str:
        """Store utterance in memory (fallback)."""
        with self._lock:
            self._utterances.append(utterance)

            if conversation_id not in self._conversations:
                self._conversations[conversation_id] = VoiceConversation(
                    session_id=conversation_id,
                    started_at=datetime.now(UTC),
                )
            self._conversations[conversation_id].utterances.append(utterance)

            # Limit memory growth
            if len(self._utterances) > 1000:
                self._utterances = self._utterances[-500:]

        return utterance.id

    def recall_similar(
        self,
        query: str,
        limit: int = 5,
        *,
        speaker_filter: Optional[str] = None,
        min_score: float = 0.5,
    ) -> List[VoiceUtterance]:
        """Find similar past utterances using vector search.

        Args:
            query: Text to find similar utterances for.
            limit: Maximum number of results.
            speaker_filter: Optional speaker to filter by.
            min_score: Minimum cosine similarity (0-1).

        Returns:
            List of similar utterances, ordered by similarity.
        """
        query_embedding = self._compute_embedding(query)
        if query_embedding is None:
            logger.debug("VoiceMemory: No embedding, returning empty results")
            return []

        if self._neo4j_available:
            return self._recall_neo4j(query_embedding, limit, speaker_filter, min_score)
        else:
            return self._recall_memory(
                query_embedding, limit, speaker_filter, min_score
            )

    def _recall_neo4j(
        self,
        query_embedding: List[float],
        limit: int,
        speaker_filter: Optional[str],
        min_score: float,
    ) -> List[VoiceUtterance]:
        """Vector similarity search in Neo4j."""
        try:
            from agentic_brain.core import neo4j_query

            # Try vector index search (Neo4j 5.x)
            try:
                if speaker_filter:
                    cypher = f"""
                    CALL db.index.vector.queryNodes(
                        '{VECTOR_INDEX_NAME}',
                        $limit,
                        $embedding
                    ) YIELD node, score
                    WHERE score >= $min_score AND node.speaker = $speaker
                    RETURN node, score
                    ORDER BY score DESC
                    """
                    results = neo4j_query(
                        cypher,
                        limit=limit * 2,  # Over-fetch for filter
                        embedding=query_embedding,
                        min_score=min_score,
                        speaker=speaker_filter,
                    )
                else:
                    cypher = f"""
                    CALL db.index.vector.queryNodes(
                        '{VECTOR_INDEX_NAME}',
                        $limit,
                        $embedding
                    ) YIELD node, score
                    WHERE score >= $min_score
                    RETURN node, score
                    ORDER BY score DESC
                    """
                    results = neo4j_query(
                        cypher,
                        limit=limit,
                        embedding=query_embedding,
                        min_score=min_score,
                    )

                utterances = []
                for record in results[:limit]:
                    node = record.get("node", {})
                    utt = VoiceUtterance.from_record(dict(node))
                    utterances.append(utt)
                return utterances

            except Exception as vec_exc:
                # Fallback to brute-force cosine similarity if vector index unavailable
                logger.debug(
                    "VoiceMemory: Vector index query failed (%s), "
                    "falling back to manual cosine",
                    vec_exc,
                )
                return self._recall_neo4j_manual(
                    query_embedding, limit, speaker_filter, min_score
                )

        except Exception as exc:
            logger.error("VoiceMemory: Neo4j recall failed: %s", exc)
            return []

    def _recall_neo4j_manual(
        self,
        query_embedding: List[float],
        limit: int,
        speaker_filter: Optional[str],
        min_score: float,
    ) -> List[VoiceUtterance]:
        """Manual cosine similarity search (fallback for older Neo4j)."""
        try:
            from agentic_brain.core import neo4j_query

            # Fetch all utterances with embeddings
            if speaker_filter:
                cypher = f"""
                MATCH (u:{LABEL_UTTERANCE})
                WHERE u.embedding IS NOT NULL AND u.speaker = $speaker
                RETURN u
                ORDER BY u.timestamp DESC
                LIMIT 500
                """
                results = neo4j_query(cypher, speaker=speaker_filter)
            else:
                cypher = f"""
                MATCH (u:{LABEL_UTTERANCE})
                WHERE u.embedding IS NOT NULL
                RETURN u
                ORDER BY u.timestamp DESC
                LIMIT 500
                """
                results = neo4j_query(cypher)

            # Compute cosine similarity in Python
            scored = []
            for record in results:
                node = record.get("u", {})
                stored_emb = node.get("embedding")
                if stored_emb:
                    score = self._cosine_similarity(query_embedding, list(stored_emb))
                    if score >= min_score:
                        utt = VoiceUtterance.from_record(dict(node))
                        scored.append((utt, score))

            # Sort by score descending
            scored.sort(key=lambda x: x[1], reverse=True)
            return [utt for utt, _ in scored[:limit]]

        except Exception as exc:
            logger.error("VoiceMemory: Manual recall failed: %s", exc)
            return []

    def _recall_memory(
        self,
        query_embedding: List[float],
        limit: int,
        speaker_filter: Optional[str],
        min_score: float,
    ) -> List[VoiceUtterance]:
        """In-memory similarity search (fallback)."""
        with self._lock:
            scored = []
            for utt in self._utterances:
                if speaker_filter and utt.speaker != speaker_filter:
                    continue
                if utt.embedding is None:
                    continue
                score = self._cosine_similarity(query_embedding, utt.embedding)
                if score >= min_score:
                    scored.append((utt, score))

            scored.sort(key=lambda x: x[1], reverse=True)
            return [utt for utt, _ in scored[:limit]]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_conversation_context(
        self,
        conversation_id: str,
        limit: int = 10,
    ) -> List[VoiceUtterance]:
        """Get recent utterances from a conversation.

        Args:
            conversation_id: The conversation session ID.
            limit: Maximum number of utterances to return.

        Returns:
            List of utterances ordered oldest to newest.
        """
        if self._neo4j_available:
            return self._get_context_neo4j(conversation_id, limit)
        else:
            return self._get_context_memory(conversation_id, limit)

    def _get_context_neo4j(
        self, conversation_id: str, limit: int
    ) -> List[VoiceUtterance]:
        """Get conversation context from Neo4j."""
        try:
            from agentic_brain.core import neo4j_query

            cypher = f"""
            MATCH (u:{LABEL_UTTERANCE})-[:{REL_PART_OF}]->(c:{LABEL_CONVERSATION})
            WHERE c.session_id = $session_id
            RETURN u
            ORDER BY u.timestamp DESC
            LIMIT $limit
            """
            results = neo4j_query(cypher, session_id=conversation_id, limit=limit)

            utterances = [
                VoiceUtterance.from_record(dict(r.get("u", {}))) for r in results
            ]
            # Reverse to get oldest-first order
            utterances.reverse()
            return utterances

        except Exception as exc:
            logger.error("VoiceMemory: Context query failed: %s", exc)
            return []

    def _get_context_memory(
        self, conversation_id: str, limit: int
    ) -> List[VoiceUtterance]:
        """Get conversation context from memory."""
        with self._lock:
            conv = self._conversations.get(conversation_id)
            if conv is None:
                return []
            return list(conv.utterances[-limit:])

    def create_conversation(
        self,
        session_id: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> VoiceConversation:
        """Create a new conversation session.

        Args:
            session_id: Optional ID (auto-generated if not provided).
            topic: Optional topic label.

        Returns:
            The created VoiceConversation.
        """
        conv = VoiceConversation(
            session_id=session_id or str(uuid.uuid4()),
            started_at=datetime.now(UTC),
            topic=topic,
        )

        if self._neo4j_available:
            try:
                from agentic_brain.core import neo4j_write

                neo4j_write(
                    f"""
                    CREATE (c:{LABEL_CONVERSATION} {{
                        session_id: $session_id,
                        started_at: $started_at,
                        topic: $topic
                    }})
                    """,
                    session_id=conv.session_id,
                    started_at=conv.started_at.isoformat(),
                    topic=conv.topic,
                )
            except Exception as exc:
                logger.warning("VoiceMemory: Conversation create failed: %s", exc)

        with self._lock:
            self._conversations[conv.session_id] = conv

        return conv

    def set_conversation_topic(
        self,
        conversation_id: str,
        topic: str,
    ) -> None:
        """Set or update the topic for a conversation.

        Also creates a DISCUSSES relationship to a Topic node.
        """
        if self._neo4j_available:
            try:
                from agentic_brain.core import neo4j_write

                neo4j_write(
                    f"""
                    MATCH (c:{LABEL_CONVERSATION} {{session_id: $session_id}})
                    SET c.topic = $topic
                    WITH c
                    MERGE (t:{LABEL_TOPIC} {{name: $topic}})
                    MERGE (c)-[:{REL_DISCUSSES}]->(t)
                    """,
                    session_id=conversation_id,
                    topic=topic,
                )
            except Exception as exc:
                logger.warning("VoiceMemory: Topic update failed: %s", exc)

        with self._lock:
            if conversation_id in self._conversations:
                # dataclass is frozen, so recreate
                old = self._conversations[conversation_id]
                self._conversations[conversation_id] = VoiceConversation(
                    session_id=old.session_id,
                    started_at=old.started_at,
                    utterances=old.utterances,
                    topic=topic,
                )

    def get_conversations_by_topic(
        self,
        topic: str,
        limit: int = 10,
    ) -> List[VoiceConversation]:
        """Find conversations discussing a topic."""
        if not self._neo4j_available:
            with self._lock:
                return [
                    c
                    for c in self._conversations.values()
                    if c.topic and topic.lower() in c.topic.lower()
                ][:limit]

        try:
            from agentic_brain.core import neo4j_query

            cypher = f"""
            MATCH (c:{LABEL_CONVERSATION})-[:{REL_DISCUSSES}]->(t:{LABEL_TOPIC})
            WHERE toLower(t.name) CONTAINS toLower($topic)
            RETURN c
            ORDER BY c.started_at DESC
            LIMIT $limit
            """
            results = neo4j_query(cypher, topic=topic, limit=limit)

            conversations = []
            for record in results:
                node = record.get("c", {})
                ts = node.get("started_at")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                else:
                    ts = datetime.now(UTC)

                conv = VoiceConversation(
                    session_id=node.get("session_id", ""),
                    started_at=ts,
                    topic=node.get("topic"),
                )
                conversations.append(conv)
            return conversations

        except Exception as exc:
            logger.error("VoiceMemory: Topic search failed: %s", exc)
            return []

    def health(self) -> Dict[str, Any]:
        """Return health status of voice memory."""
        with self._lock:
            in_mem_count = len(self._utterances)
            conv_count = len(self._conversations)

        status: Dict[str, Any] = {
            "neo4j_available": self._neo4j_available,
            "embedder_available": self._embedder is not None
            and self._embedder is not False,
            "in_memory_utterances": in_mem_count,
            "in_memory_conversations": conv_count,
        }

        if self._neo4j_available:
            try:
                from agentic_brain.core import neo4j_query_value

                status["neo4j_utterances"] = neo4j_query_value(
                    f"MATCH (u:{LABEL_UTTERANCE}) RETURN count(u) AS n"
                )
                status["neo4j_conversations"] = neo4j_query_value(
                    f"MATCH (c:{LABEL_CONVERSATION}) RETURN count(c) AS n"
                )
            except Exception:
                pass

        return status


# ── Singleton ────────────────────────────────────────────────────────

_instance: Optional[VoiceMemory] = None
_instance_lock = threading.Lock()


def get_voice_memory(**kwargs: Any) -> VoiceMemory:
    """Return (or create) the global VoiceMemory singleton."""
    global _instance
    if _instance is None:
        with _instance_lock:
            if _instance is None:
                _instance = VoiceMemory(**kwargs)
    return _instance


def reset_voice_memory() -> None:
    """Tear down the singleton (useful in tests)."""
    global _instance
    with _instance_lock:
        _instance = None
