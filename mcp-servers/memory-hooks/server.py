#!/usr/bin/env python3
"""
Memory Hooks MCP Server - Real-time Perfect Memory
===================================================

MCP server exposing Ultimate Memory Hooks for Claude/Copilot.

Tools:
- capture_message: Store user/assistant message
- recall_memories: Semantic search past conversations
- get_session_context: Get recent conversation context
- memory_status: Check system status
- search_all_sessions: Search across ALL sessions

Author: Iris Lumina 💜
"""

import json
import os
import sys
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional

sys.path.insert(0, os.path.expanduser("~/brain"))

from mcp.server.fastmcp import FastMCP

# LAZY IMPORT - Don't import Neo4j-dependent modules at startup
if TYPE_CHECKING:
    from core.hooks.ultimate_memory_hooks import UltimateMemoryHooks

mcp = FastMCP("memory-hooks")
_hooks: Optional["UltimateMemoryHooks"] = None


def get_memory_hooks() -> "UltimateMemoryHooks":
    """Lazy load memory hooks - Neo4j connects on first use, not at startup."""
    global _hooks
    if _hooks is None:
        from core.hooks.ultimate_memory_hooks import get_hooks

        _hooks = get_hooks()
    return _hooks


@mcp.tool()
def capture_message(content: str, role: str = "user", source: str = "mcp") -> dict:
    """Capture a message and store in perfect memory. Role: 'user' or 'assistant'."""
    hooks = get_memory_hooks()
    event_type = "userPromptSubmitted" if role == "user" else "assistantResponse"
    event = hooks.capture_event(
        event_type=event_type, source=source, content=content, role=role
    )
    return {
        "success": True,
        "event_id": event.event_id,
        "topics": event.topics,
        "importance": event.importance,
    }


@mcp.tool()
def recall_memories(query: str, top_k: int = 10) -> dict:
    """Recall relevant past conversations using semantic search across ALL sessions."""
    hooks = get_memory_hooks()
    memories = hooks.recall_relevant(query, top_k=top_k)
    return {"query": query, "count": len(memories), "memories": memories}


@mcp.tool()
def get_session_context() -> dict:
    """Get context from recent conversations in this session."""
    hooks = get_memory_hooks()
    events = hooks.get_session_events()
    context = [
        {"role": e.get("role"), "content": e.get("content", "")[:200]}
        for e in events[-15:]
    ]
    return {
        "session_id": hooks.session_id,
        "turn_count": hooks.turn_count,
        "context": context,
    }


@mcp.tool()
def memory_status() -> str:
    """Get status of the memory system - Neo4j, Redpanda, statistics."""
    hooks = get_memory_hooks()
    neo4j = "✅" if hooks.neo4j_driver else "❌"
    kafka = "✅" if hooks.kafka_bus else "❌"
    return f"""🧠 **Perfect Memory Status**
Session: {hooks.session_id} | Turns: {hooks.turn_count} | Events: {len(hooks.events)}
Neo4j: {neo4j} | Redpanda: {kafka}
All messages → Neo4j (vectors) + Redpanda (events) + JSONL (backup)"""


@mcp.tool()
def search_all_sessions(query: str, limit: int = 20) -> dict:
    """Search across ALL past sessions in Neo4j."""
    hooks = get_memory_hooks()
    if not hooks.neo4j_driver:
        return {"error": "Neo4j not connected"}
    try:
        with hooks.neo4j_driver.session() as session:
            result = session.run(
                """
                MATCH (e:HookEvent)
                WHERE toLower(e.content) CONTAINS toLower($query)
                RETURN e.session_id as session, e.role as role, 
                       e.content as content, e.primary_topic as topic
                ORDER BY e.timestamp DESC LIMIT $limit
            """,
                {"query": query, "limit": limit},
            )
            matches = [
                {
                    "session": r["session"],
                    "role": r["role"],
                    "content": r["content"][:200] if r["content"] else "",
                    "topic": r["topic"],
                }
                for r in result
            ]
            return {"query": query, "count": len(matches), "matches": matches}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def start_session() -> dict:
    """Start session tracking for memory. Returns recent context from last 24 hours!"""
    hooks = get_memory_hooks()
    return hooks.on_session_start()


@mcp.tool()
def get_recent_memories(hours: int = 24, limit: int = 30) -> dict:
    """
    Get recent memories from Neo4j. Call this on EVERY session start!

    Returns messages from the last N hours, ordered by recency.
    This is how we remember what we were working on.
    """
    hooks = get_memory_hooks()
    if not hooks.neo4j_driver:
        return {"error": "Neo4j not connected", "memories": []}

    try:
        with hooks.neo4j_driver.session() as session:
            result = session.run(
                f"""
                MATCH (m:Memory) 
                WHERE m.timestamp > datetime() - duration('PT{hours}H')
                RETURN m.text as text, m.importance as importance, 
                       m.session_id as session_id, m.timestamp as timestamp
                ORDER BY m.timestamp DESC 
                LIMIT $limit
            """,
                {"limit": limit},
            )

            memories = []
            for record in result:
                memories.append(
                    {
                        "text": record["text"][:400] if record["text"] else "",
                        "importance": record["importance"],
                        "session_id": record["session_id"],
                        "timestamp": str(record["timestamp"]),
                    }
                )

            return {
                "success": True,
                "count": len(memories),
                "hours": hours,
                "memories": memories,
            }
    except Exception as e:
        return {"error": str(e), "memories": []}


@mcp.tool()
def end_session() -> dict:
    """End session and save summary to Neo4j."""
    hooks = get_memory_hooks()
    return hooks.on_session_end()


if __name__ == "__main__":
    print("🧠 Memory Hooks MCP Server starting...")
    mcp.run()
