#!/usr/bin/env python3
"""Voice memory — Neo4j + Redis for perfect conversation recall.

Redis:  Hot session state (last 10 exchanges, current context)
Neo4j:  Long-term memory (all conversations, searchable, RAG-ready)

This gives Karen perfect memory across sessions.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any


REDIS_URL = os.getenv("VOICE_REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "Brain2026")

HISTORY_KEY = "voice:history"
SESSION_KEY = "voice:session_context"
HISTORY_MAX = 20  # messages in Redis hot cache


# ---------------------------------------------------------------------------
# Redis session memory (fast, volatile)
# ---------------------------------------------------------------------------

_redis = None


def _get_redis():
    global _redis
    if _redis is None:
        import redis as _r

        _redis = _r.from_url(REDIS_URL, decode_responses=True)
    return _redis


def push_message(role: str, content: str, *, metadata: dict | None = None) -> None:
    """Push a message to Redis conversation history."""
    r = _get_redis()
    entry = {
        "role": role,
        "content": content,
        "timestamp": time.time(),
        **(metadata or {}),
    }
    r.lpush(HISTORY_KEY, json.dumps(entry))
    r.ltrim(HISTORY_KEY, 0, HISTORY_MAX - 1)


def get_recent_messages(n: int = 10) -> list[dict[str, str]]:
    """Get the last N messages in chronological order."""
    r = _get_redis()
    raw = r.lrange(HISTORY_KEY, 0, n - 1)
    messages = []
    for item in reversed(raw):
        try:
            entry = json.loads(item)
            messages.append({"role": entry["role"], "content": entry["content"]})
        except (json.JSONDecodeError, KeyError):
            continue
    return messages


def set_session_context(key: str, value: Any) -> None:
    """Store arbitrary session context in Redis."""
    r = _get_redis()
    ctx = json.loads(r.get(SESSION_KEY) or "{}")
    ctx[key] = value
    ctx["_updated"] = time.time()
    r.set(SESSION_KEY, json.dumps(ctx))


def get_session_context() -> dict[str, Any]:
    """Get all session context."""
    r = _get_redis()
    raw = r.get(SESSION_KEY)
    return json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# Neo4j long-term memory
# ---------------------------------------------------------------------------

_neo4j_driver = None


def _get_neo4j():
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            from neo4j import GraphDatabase

            _neo4j_driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
            )
        except Exception:
            _neo4j_driver = None
    return _neo4j_driver


def _ensure_neo4j_indexes(tx) -> None:
    """Create indexes for voice memory nodes (idempotent)."""
    tx.run(
        "CREATE INDEX voice_conversation_id IF NOT EXISTS "
        "FOR (c:VoiceConversation) ON (c.id)"
    )
    tx.run(
        "CREATE INDEX voice_message_timestamp IF NOT EXISTS "
        "FOR (m:VoiceMessage) ON (m.timestamp)"
    )
    tx.run(
        "CREATE INDEX voice_message_session IF NOT EXISTS "
        "FOR (m:VoiceMessage) ON (m.session_id)"
    )


_indexes_created = False


def store_conversation(
    session_id: str,
    role: str,
    content: str,
    *,
    provider: str | None = None,
    complexity: str | None = None,
    latency_ms: float | None = None,
    strategy: str | None = None,
) -> bool:
    """Store a message in Neo4j for long-term recall."""
    driver = _get_neo4j()
    if not driver:
        return False

    global _indexes_created
    try:
        with driver.session() as session:
            if not _indexes_created:
                session.execute_write(_ensure_neo4j_indexes)
                _indexes_created = True

            ts = time.time()
            session.run(
                """
                MERGE (c:VoiceConversation {id: $session_id})
                ON CREATE SET c.created = datetime(),
                              c.timestamp = $ts_str
                WITH c
                CREATE (m:VoiceMessage {
                    session_id: $session_id,
                    role: $role,
                    content: $content,
                    timestamp: $ts,
                    provider: $provider,
                    complexity: $complexity,
                    latency_ms: $latency_ms,
                    strategy: $strategy
                })
                MERGE (c)-[:HAS_MESSAGE]->(m)
                """,
                session_id=session_id,
                role=role,
                content=content,
                ts=ts,
                ts_str=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
                provider=provider or "",
                complexity=complexity or "",
                latency_ms=latency_ms,
                strategy=strategy or "",
            )
        return True
    except Exception:
        return False


def recall_relevant(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search Neo4j for past conversations relevant to the query.

    Uses CONTAINS text matching (upgrade to vector search when embeddings
    are added in Phase 1 of the roadmap).
    """
    driver = _get_neo4j()
    if not driver:
        return []

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:VoiceMessage)
                WHERE m.content CONTAINS $query
                  AND m.role = 'assistant'
                RETURN m.content AS content,
                       m.timestamp AS timestamp,
                       m.provider AS provider,
                       m.session_id AS session_id
                ORDER BY m.timestamp DESC
                LIMIT $limit
                """,
                query=query,
                limit=limit,
            )
            return [dict(record) for record in result]
    except Exception:
        return []


def get_conversation_stats() -> dict[str, Any]:
    """Get memory statistics from Neo4j."""
    driver = _get_neo4j()
    if not driver:
        return {"neo4j": "unavailable"}

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:VoiceMessage)
                RETURN count(m) AS total_messages,
                       count(DISTINCT m.session_id) AS total_sessions,
                       max(m.timestamp) AS latest_message
                """
            )
            record = result.single()
            if record:
                return {
                    "total_messages": record["total_messages"],
                    "total_sessions": record["total_sessions"],
                    "latest_message": record["latest_message"],
                    "neo4j": "connected",
                }
    except Exception:
        pass
    return {"neo4j": "error"}


# ---------------------------------------------------------------------------
# RAG: build context from memory
# ---------------------------------------------------------------------------


def build_rag_context(
    user_text: str,
    *,
    session_messages: int = 6,
    memory_results: int = 3,
) -> list[dict[str, str]]:
    """Build enriched context by combining session history + long-term memory.

    Returns a list of messages suitable for prepending to the LLM prompt.
    """
    context: list[dict[str, str]] = []

    # 1. Recent session messages from Redis
    recent = get_recent_messages(session_messages)
    context.extend(recent)

    # 2. Relevant past conversations from Neo4j
    memories = recall_relevant(user_text, limit=memory_results)
    if memories:
        memory_text = "Here's what I recall from past conversations:\n"
        for mem in memories:
            memory_text += f"- {mem.get('content', '')[:200]}\n"
        context.insert(0, {"role": "system", "content": memory_text})

    return context
