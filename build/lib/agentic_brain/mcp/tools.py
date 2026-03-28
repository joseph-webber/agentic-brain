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
MCP Tools for agentic-brain.

Provides tool functions that can be registered with the MCP server.
Each tool returns a string that Claude can understand.

Tools are organized into categories:
- Chat: Send messages and get responses
- Session: Manage chat sessions
- Knowledge/RAG: Search and add documents
- System: Health checks and analytics
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentic_brain.chat.chatbot import Chatbot
    from agentic_brain.chat.session import SessionManager

logger = logging.getLogger(__name__)


class ToolContext:
    """
    Context for tool execution.

    Holds references to shared resources like chatbot, memory, and session manager.
    """

    def __init__(
        self,
        chatbot: Chatbot | None = None,
        memory: Any | None = None,  # Neo4jMemory or InMemoryStore
        session_manager: SessionManager | None = None,
        rag_pipeline: Any | None = None,
        neo4j_driver: Any | None = None,
    ) -> None:
        self.chatbot = chatbot
        self.memory = memory
        self.session_manager = session_manager
        self.rag_pipeline = rag_pipeline
        self.neo4j_driver = neo4j_driver
        self._initialized = False

    @property
    def is_ready(self) -> bool:
        """Check if context is ready for use."""
        return self.chatbot is not None or self.memory is not None


# Global context - initialized by server
_context: ToolContext | None = None


def set_context(ctx: ToolContext) -> None:
    """Set the global tool context."""
    global _context
    _context = ctx


def get_context() -> ToolContext:
    """Get the global tool context."""
    if _context is None:
        raise RuntimeError("Tool context not initialized. Call set_context() first.")
    return _context


# =============================================================================
# Chat Tools
# =============================================================================


def chat(
    message: str,
    session_id: str = "default",
    system_prompt: str | None = None,
) -> str:
    """
    Send a message to the agent and get a response.

    Args:
        message: The user's message
        session_id: Session identifier for conversation continuity
        system_prompt: Optional system prompt override

    Returns:
        The agent's response text
    """
    ctx = get_context()

    if not ctx.chatbot:
        return "Error: Chatbot not initialized. Check server configuration."

    try:
        # Override system prompt if provided
        original_prompt = None
        if system_prompt:
            original_prompt = ctx.chatbot.system_prompt
            ctx.chatbot.set_system_prompt(system_prompt)

        # Get response (sync version)
        response = ctx.chatbot.chat(
            message=message,
            session_id=session_id,
        )

        # Restore original prompt
        if original_prompt:
            ctx.chatbot.set_system_prompt(original_prompt)

        return response
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        return f"Error during chat: {str(e)}"


async def chat_async(
    message: str,
    session_id: str = "default",
    system_prompt: str | None = None,
) -> str:
    """
    Send a message to the agent and get a response (async version).

    Args:
        message: The user's message
        session_id: Session identifier for conversation continuity
        system_prompt: Optional system prompt override

    Returns:
        The agent's response text
    """
    ctx = get_context()

    if not ctx.chatbot:
        return "Error: Chatbot not initialized. Check server configuration."

    try:
        # Override system prompt if provided
        original_prompt = None
        if system_prompt:
            original_prompt = ctx.chatbot.system_prompt
            ctx.chatbot.set_system_prompt(system_prompt)

        # Get response (async version)
        response = await ctx.chatbot.chat_async(
            message=message,
            session_id=session_id,
        )

        # Restore original prompt
        if original_prompt:
            ctx.chatbot.set_system_prompt(original_prompt)

        return response
    except Exception as e:
        logger.error(f"Async chat error: {e}", exc_info=True)
        return f"Error during chat: {str(e)}"


def chat_stream(message: str, session_id: str = "default") -> str:
    """
    Stream a response from the agent.

    Note: MCP tools return complete strings, so this returns info about
    how to use the streaming endpoint directly.

    Args:
        message: The user's message
        session_id: Session identifier

    Returns:
        Information about streaming usage
    """
    return (
        "Streaming is not directly supported via MCP tools.\n\n"
        "To stream responses, use the HTTP API:\n"
        "POST /api/v1/chat/stream\n"
        'Body: {"message": "...", "session_id": "..."}\n\n'
        "Or use the Chatbot class directly with async generators."
    )


# =============================================================================
# Session Tools
# =============================================================================


def create_session(
    session_id: str | None = None,
    user_id: str | None = None,
) -> str:
    """
    Create a new chat session.

    Args:
        session_id: Optional custom session ID (auto-generated if not provided)
        user_id: Optional user identifier

    Returns:
        JSON string with session details
    """
    ctx = get_context()

    # Generate session ID if not provided
    if not session_id:
        session_id = f"session_{uuid.uuid4().hex[:12]}"

    try:
        if ctx.session_manager:
            session = ctx.session_manager.get_session(
                session_id=session_id,
                user_id=user_id,
                bot_name=ctx.chatbot.name if ctx.chatbot else "assistant",
            )
            ctx.session_manager.save_session(session)

            return json.dumps(
                {
                    "success": True,
                    "session_id": session.session_id,
                    "user_id": session.user_id,
                    "created_at": session.created_at,
                    "message": f"Session '{session_id}' created successfully",
                },
                indent=2,
            )
        else:
            # No persistent session manager, create in-memory
            return json.dumps(
                {
                    "success": True,
                    "session_id": session_id,
                    "user_id": user_id,
                    "created_at": datetime.now(UTC).isoformat(),
                    "message": f"In-memory session '{session_id}' created (not persistent)",
                },
                indent=2,
            )
    except Exception as e:
        logger.error(f"Create session error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def list_sessions(limit: int = 10) -> str:
    """
    List active chat sessions.

    Args:
        limit: Maximum number of sessions to return

    Returns:
        JSON string with session list
    """
    ctx = get_context()

    try:
        if ctx.session_manager:
            session_ids = ctx.session_manager.list_sessions()[:limit]
            sessions = []

            for sid in session_ids:
                session = ctx.session_manager.load_session(sid)
                if session:
                    sessions.append(
                        {
                            "session_id": session.session_id,
                            "user_id": session.user_id,
                            "message_count": len(session.messages),
                            "created_at": session.created_at,
                            "updated_at": session.updated_at,
                        }
                    )

            return json.dumps(
                {"success": True, "count": len(sessions), "sessions": sessions},
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "success": True,
                    "count": 0,
                    "sessions": [],
                    "message": "No session manager configured (sessions are in-memory only)",
                },
                indent=2,
            )
    except Exception as e:
        logger.error(f"List sessions error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def get_session_history(session_id: str, limit: int = 20) -> str:
    """
    Get conversation history for a session.

    Args:
        session_id: Session identifier
        limit: Maximum number of messages to return

    Returns:
        JSON string with conversation history
    """
    ctx = get_context()

    try:
        if ctx.session_manager:
            session = ctx.session_manager.load_session(session_id)
            if session:
                history = session.get_history(limit)
                return json.dumps(
                    {
                        "success": True,
                        "session_id": session_id,
                        "message_count": len(history),
                        "messages": history,
                    },
                    indent=2,
                )
            else:
                return json.dumps(
                    {"success": False, "error": f"Session '{session_id}' not found"},
                    indent=2,
                )
        elif ctx.chatbot:
            # Try chatbot's internal sessions
            chat_session = ctx.chatbot.get_session(session_id=session_id)
            history = [m.to_dict() for m in chat_session.history[-limit:]]
            return json.dumps(
                {
                    "success": True,
                    "session_id": session_id,
                    "message_count": len(history),
                    "messages": history,
                },
                indent=2,
            )
        else:
            return json.dumps(
                {"success": False, "error": "No session manager or chatbot configured"},
                indent=2,
            )
    except Exception as e:
        logger.error(f"Get history error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def delete_session(session_id: str) -> str:
    """
    Delete a session and its history.

    Args:
        session_id: Session identifier to delete

    Returns:
        JSON string with deletion result
    """
    ctx = get_context()

    try:
        if ctx.session_manager:
            success = ctx.session_manager.delete_session(session_id)
            return json.dumps(
                {
                    "success": success,
                    "message": (
                        f"Session '{session_id}' deleted"
                        if success
                        else f"Failed to delete session '{session_id}'"
                    ),
                },
                indent=2,
            )
        else:
            return json.dumps(
                {"success": False, "error": "No session manager configured"}, indent=2
            )
    except Exception as e:
        logger.error(f"Delete session error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# =============================================================================
# Knowledge/RAG Tools
# =============================================================================


def search_knowledge(query: str, limit: int = 5) -> str:
    """
    Search the knowledge base using RAG.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        JSON string with search results
    """
    ctx = get_context()

    try:
        # Try RAG pipeline first
        if ctx.rag_pipeline:
            result = ctx.rag_pipeline.query(query, limit=limit)
            return json.dumps(
                {
                    "success": True,
                    "query": query,
                    "answer": result.answer,
                    "confidence": result.confidence,
                    "confidence_level": result.confidence_level,
                    "sources": [
                        {
                            "content": s.content[:300],
                            "source": s.source,
                            "score": s.score,
                        }
                        for s in result.sources[:limit]
                    ],
                },
                indent=2,
            )

        # Fall back to memory search
        if ctx.memory:
            from agentic_brain.memory import DataScope

            results = ctx.memory.search(
                query=query, scope=DataScope.PUBLIC, limit=limit
            )

            if results:
                return json.dumps(
                    {
                        "success": True,
                        "query": query,
                        "count": len(results),
                        "results": [
                            {
                                "id": r.id,
                                "content": r.content[:300],
                                "timestamp": (
                                    r.timestamp.isoformat() if r.timestamp else None
                                ),
                            }
                            for r in results
                        ],
                    },
                    indent=2,
                )
            else:
                return json.dumps(
                    {
                        "success": True,
                        "query": query,
                        "count": 0,
                        "results": [],
                        "message": "No results found",
                    },
                    indent=2,
                )

        return json.dumps(
            {"success": False, "error": "No RAG pipeline or memory configured"},
            indent=2,
        )
    except Exception as e:
        logger.error(f"Search knowledge error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


def add_document(content: str, metadata: dict[str, Any] | None = None) -> str:
    """
    Add a document to the knowledge base.

    Args:
        content: Document content
        metadata: Optional metadata dict

    Returns:
        JSON string with result
    """
    ctx = get_context()

    try:
        if ctx.memory:
            from agentic_brain.memory import DataScope

            memory = ctx.memory.store(
                content=content, scope=DataScope.PUBLIC, metadata=metadata or {}
            )

            return json.dumps(
                {
                    "success": True,
                    "id": memory.id,
                    "message": f"Document stored with ID: {memory.id}",
                },
                indent=2,
            )

        return json.dumps(
            {"success": False, "error": "No memory store configured"}, indent=2
        )
    except Exception as e:
        logger.error(f"Add document error: {e}", exc_info=True)
        return json.dumps({"success": False, "error": str(e)}, indent=2)


# =============================================================================
# Memory Tools (from original implementation)
# =============================================================================


def store_memory(content: str, scope: str = "private") -> str:
    """
    Store content in agent memory.

    Args:
        content: Content to store
        scope: Data scope (public, private, customer)

    Returns:
        Confirmation message
    """
    ctx = get_context()

    if not ctx.memory:
        return "Error: Memory not configured"

    try:
        from agentic_brain.memory import DataScope

        scope_enum = DataScope(scope)
        memory = ctx.memory.store(content, scope=scope_enum)
        return f"Stored memory with ID: {memory.id}"
    except Exception as e:
        logger.error(f"Store memory error: {e}", exc_info=True)
        return f"Error storing memory: {str(e)}"


def search_memory(query: str, scope: str = "private", limit: int = 5) -> str:
    """
    Search agent memory.

    Args:
        query: Search query
        scope: Data scope to search
        limit: Maximum results

    Returns:
        Formatted search results
    """
    ctx = get_context()

    if not ctx.memory:
        return "Error: Memory not configured"

    try:
        from agentic_brain.memory import DataScope

        scope_enum = DataScope(scope)
        results = ctx.memory.search(query, scope=scope_enum, limit=limit)

        if not results:
            return "No memories found."

        output = []
        for mem in results:
            output.append(f"- {mem.content}")
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Search memory error: {e}", exc_info=True)
        return f"Error searching memory: {str(e)}"


def get_recent_memories(scope: str = "private", limit: int = 10) -> str:
    """
    Get recent memories.

    Args:
        scope: Data scope
        limit: Maximum results

    Returns:
        Formatted list of recent memories
    """
    ctx = get_context()

    if not ctx.memory:
        return "Error: Memory not configured"

    try:
        from agentic_brain.memory import DataScope

        scope_enum = DataScope(scope)
        results = ctx.memory.get_recent(scope=scope_enum, limit=limit)

        if not results:
            return "No recent memories."

        output = []
        for mem in results:
            ts = mem.timestamp.isoformat() if mem.timestamp else "unknown"
            output.append(f"[{ts}] {mem.content}")
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Get recent memories error: {e}", exc_info=True)
        return f"Error getting memories: {str(e)}"


# =============================================================================
# System Tools
# =============================================================================


def health_check() -> str:
    """
    Check system health (Neo4j, LLM, memory).

    Returns:
        JSON string with health status
    """
    ctx = get_context()

    health = {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "components": {},
    }

    # Check chatbot
    if ctx.chatbot:
        health["components"]["chatbot"] = {
            "status": "ok",
            "name": ctx.chatbot.name,
            "model": (
                ctx.chatbot.config.model
                if hasattr(ctx.chatbot, "config")
                else "unknown"
            ),
        }
    else:
        health["components"]["chatbot"] = {"status": "not_configured"}

    # Check memory
    if ctx.memory:
        try:
            # Test connection
            if hasattr(ctx.memory, "_connected"):
                connected = ctx.memory._connected
            else:
                connected = True  # InMemoryStore is always connected

            health["components"]["memory"] = {
                "status": "ok" if connected else "disconnected",
                "type": type(ctx.memory).__name__,
            }
        except Exception as e:
            health["components"]["memory"] = {"status": "error", "error": str(e)}
    else:
        health["components"]["memory"] = {"status": "not_configured"}

    # Check session manager
    if ctx.session_manager:
        try:
            count = ctx.session_manager.get_session_count()
            health["components"]["sessions"] = {
                "status": "ok",
                "active_sessions": count,
            }
        except Exception as e:
            health["components"]["sessions"] = {"status": "error", "error": str(e)}
    else:
        health["components"]["sessions"] = {"status": "not_configured"}

    # Check RAG pipeline
    if ctx.rag_pipeline:
        health["components"]["rag"] = {"status": "ok"}
    else:
        health["components"]["rag"] = {"status": "not_configured"}

    # Check Neo4j driver
    if ctx.neo4j_driver:
        try:
            with ctx.neo4j_driver.session() as session:
                result = session.run("RETURN 1 as n")
                result.single()
            health["components"]["neo4j"] = {"status": "ok"}
        except Exception as e:
            health["components"]["neo4j"] = {"status": "error", "error": str(e)}
            health["status"] = "degraded"
    else:
        health["components"]["neo4j"] = {"status": "not_configured"}

    # Overall status
    error_components = [
        k for k, v in health["components"].items() if v.get("status") == "error"
    ]
    if error_components:
        health["status"] = "degraded"
        health["issues"] = error_components

    return json.dumps(health, indent=2)


def get_analytics(days: int = 7) -> str:
    """
    Get usage analytics for the past N days.

    Args:
        days: Number of days to look back

    Returns:
        JSON string with analytics data
    """
    ctx = get_context()

    # Try to get stats from chatbot
    if ctx.chatbot:
        stats = ctx.chatbot.get_stats()

        # Add session info if available
        if ctx.session_manager:
            stats["active_sessions"] = ctx.session_manager.get_session_count()

        return json.dumps(
            {
                "success": True,
                "period_days": days,
                "stats": stats,
                "note": "Detailed analytics require Neo4j and the analytics module",
            },
            indent=2,
        )

    # Try analytics module if Neo4j is available
    if ctx.neo4j_driver:
        try:
            from agentic_brain.analytics import UsageTracker

            tracker = UsageTracker(ctx.neo4j_driver)

            from datetime import timedelta

            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=days)

            # Get daily stats for period
            daily_stats = []
            current = start_date
            while current <= end_date:
                date_str = current.strftime("%Y-%m-%d")
                try:
                    stats = tracker.get_daily_stats(date_str)
                    daily_stats.append(
                        {
                            "date": date_str,
                            "responses": stats.responses,
                            "errors": stats.errors,
                            "tokens_in": stats.tokens_in,
                            "tokens_out": stats.tokens_out,
                        }
                    )
                except Exception:
                    pass  # Skip days with no data
                current += timedelta(days=1)

            return json.dumps(
                {"success": True, "period_days": days, "daily_stats": daily_stats},
                indent=2,
            )
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Analytics error: {e}")

    return json.dumps(
        {
            "success": True,
            "period_days": days,
            "stats": {
                "message": "Basic stats only - configure Neo4j for detailed analytics"
            },
        },
        indent=2,
    )


# =============================================================================
# Tool Registry
# =============================================================================

# All available tools with their metadata
TOOLS = {
    # Chat tools
    "chat": {
        "function": chat,
        "description": "Send a message to the agent and get a response",
        "async_function": chat_async,
    },
    "chat_stream": {
        "function": chat_stream,
        "description": "Stream a response (returns info about streaming endpoint)",
    },
    # Session tools
    "create_session": {
        "function": create_session,
        "description": "Create a new chat session, returns session_id",
    },
    "list_sessions": {
        "function": list_sessions,
        "description": "List active sessions with their metadata",
    },
    "get_session_history": {
        "function": get_session_history,
        "description": "Get conversation history for a session",
    },
    "delete_session": {
        "function": delete_session,
        "description": "Delete a session and its history",
    },
    # Knowledge/RAG tools
    "search_knowledge": {
        "function": search_knowledge,
        "description": "Search the knowledge base using RAG",
    },
    "add_document": {
        "function": add_document,
        "description": "Add a document to the knowledge base",
    },
    # Memory tools
    "store_memory": {
        "function": store_memory,
        "description": "Store content in agent memory",
    },
    "search_memory": {
        "function": search_memory,
        "description": "Search agent memory",
    },
    "get_recent_memories": {
        "function": get_recent_memories,
        "description": "Get recent memories",
    },
    # System tools
    "health_check": {
        "function": health_check,
        "description": "Check system health (Neo4j, LLM, memory)",
    },
    "get_analytics": {
        "function": get_analytics,
        "description": "Get usage analytics for the past N days",
    },
}


def get_all_tools() -> dict[str, Any]:
    """Get all registered tools."""
    return TOOLS.copy()
