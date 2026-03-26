# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Claude Desktop Integration Example.

This example demonstrates how to use agentic-brain with Claude Desktop
through the Model Context Protocol (MCP):

- MCP tool registration
- Memory persistence across Claude sessions
- RAG for Claude context augmentation
- Session continuity patterns

Setup:
    1. Install agentic-brain: pip install agentic-brain
    2. Add to Claude Desktop config (see below)
    3. Start chatting with Claude and use brain tools!

Claude Desktop Config (~/.config/claude/config.json):
    {
      "mcpServers": {
        "agentic-brain": {
          "command": "python",
          "args": ["-m", "agentic_brain.mcp"],
          "env": {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_PASSWORD": "your-password"
          }
        }
      }
    }

Usage (standalone):
    python examples/core/claude_desktop_agent.py
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class SessionState:
    """
    Persistent session state for Claude Desktop.

    Stores conversation context, memories, and user preferences
    that persist across Claude sessions.
    """

    session_id: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = field(default_factory=lambda: datetime.now().isoformat())
    memories: list[dict[str, Any]] = field(default_factory=list)
    context_keys: list[str] = field(default_factory=list)
    user_preferences: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_active": self.last_active,
            "memories": self.memories,
            "context_keys": self.context_keys,
            "user_preferences": self.user_preferences,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionState:
        """Create from dictionary."""
        return cls(**data)

    def add_memory(
        self,
        content: str,
        category: str = "general",
        importance: float = 0.5,
    ) -> None:
        """Add a memory to the session."""
        self.memories.append(
            {
                "content": content,
                "category": category,
                "importance": importance,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self.last_active = datetime.now().isoformat()

    def get_recent_memories(self, limit: int = 10) -> list[dict]:
        """Get most recent memories."""
        sorted_memories = sorted(
            self.memories,
            key=lambda m: m.get("timestamp", ""),
            reverse=True,
        )
        return sorted_memories[:limit]


class ClaudeSessionManager:
    """
    Manages persistent sessions for Claude Desktop integration.

    Features:
    - Session persistence across Claude restarts
    - Memory storage and retrieval
    - Context injection for Claude conversations
    - User preference tracking
    """

    def __init__(self, storage_dir: Path | None = None) -> None:
        """Initialize session manager."""
        self.storage_dir = storage_dir or Path.home() / ".agentic-brain" / "claude"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: dict[str, SessionState] = {}
        self._load_sessions()

    def _load_sessions(self) -> None:
        """Load existing sessions from disk."""
        for session_file in self.storage_dir.glob("*.json"):
            try:
                with open(session_file) as f:
                    data = json.load(f)
                    session = SessionState.from_dict(data)
                    self._sessions[session.session_id] = session
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load session {session_file}: {e}")

    def _save_session(self, session: SessionState) -> None:
        """Persist session to disk."""
        session_file = self.storage_dir / f"{session.session_id}.json"
        with open(session_file, "w") as f:
            json.dump(session.to_dict(), f, indent=2)

    def get_or_create_session(self, session_id: str) -> SessionState:
        """Get existing session or create new one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionState(session_id=session_id)
            self._save_session(self._sessions[session_id])
        return self._sessions[session_id]

    def save_memory(
        self,
        session_id: str,
        content: str,
        category: str = "general",
        importance: float = 0.5,
    ) -> None:
        """Save a memory to a session."""
        session = self.get_or_create_session(session_id)
        session.add_memory(content, category, importance)
        self._save_session(session)

    def get_context_for_claude(
        self,
        session_id: str,
        max_memories: int = 10,
    ) -> str:
        """
        Generate context string for Claude from session memories.

        This context can be injected into Claude conversations
        to provide relevant background information.
        """
        session = self.get_or_create_session(session_id)
        memories = session.get_recent_memories(max_memories)

        if not memories:
            return ""

        context_parts = ["## Relevant Memories", ""]
        for mem in memories:
            timestamp = mem.get("timestamp", "")[:10]  # Just date
            category = mem.get("category", "general")
            content = mem.get("content", "")
            context_parts.append(f"- [{category}] ({timestamp}): {content}")

        return "\n".join(context_parts)


class ClaudeRAGHelper:
    """
    RAG (Retrieval-Augmented Generation) helper for Claude Desktop.

    Provides context augmentation for Claude conversations by:
    - Searching knowledge bases
    - Retrieving relevant documents
    - Building context windows
    """

    def __init__(self, session_manager: ClaudeSessionManager) -> None:
        """Initialize RAG helper."""
        self.session_manager = session_manager
        self._knowledge_base: list[dict[str, Any]] = []

    def add_document(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 500,
    ) -> int:
        """
        Add document to knowledge base with chunking.

        Returns number of chunks created.
        """
        chunks = []
        words = content.split()

        for i in range(0, len(words), chunk_size):
            chunk_words = words[i : i + chunk_size]
            chunk_text = " ".join(chunk_words)
            chunks.append(
                {
                    "content": chunk_text,
                    "metadata": metadata or {},
                    "chunk_index": len(chunks),
                    "added_at": datetime.now().isoformat(),
                }
            )

        self._knowledge_base.extend(chunks)
        return len(chunks)

    def search(
        self,
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Simple keyword search in knowledge base.

        For production, use vector embeddings via Neo4j or similar.
        """
        query_words = set(query.lower().split())
        scored_results = []

        for doc in self._knowledge_base:
            content_words = set(doc["content"].lower().split())
            overlap = len(query_words & content_words)
            if overlap > 0:
                scored_results.append(
                    {
                        "content": doc["content"],
                        "metadata": doc["metadata"],
                        "score": overlap / len(query_words),
                    }
                )

        # Sort by score descending
        scored_results.sort(key=lambda x: x["score"], reverse=True)
        return scored_results[:top_k]

    def build_context(
        self,
        query: str,
        session_id: str,
        include_memories: bool = True,
        include_search: bool = True,
        max_context_chars: int = 4000,
    ) -> str:
        """
        Build context for Claude from memories and search results.

        Combines:
        - Session memories
        - RAG search results
        - Query-specific context
        """
        context_parts = []

        # Add session memories
        if include_memories:
            memories_ctx = self.session_manager.get_context_for_claude(
                session_id,
                max_memories=5,
            )
            if memories_ctx:
                context_parts.append(memories_ctx)

        # Add search results
        if include_search and self._knowledge_base:
            results = self.search(query, top_k=3)
            if results:
                context_parts.append("\n## Relevant Information\n")
                for i, result in enumerate(results, 1):
                    content = result["content"][:500]  # Truncate
                    context_parts.append(f"{i}. {content}...")

        # Combine and truncate
        full_context = "\n\n".join(context_parts)
        if len(full_context) > max_context_chars:
            full_context = full_context[:max_context_chars] + "\n...(truncated)"

        return full_context


def create_mcp_tools(
    session_manager: ClaudeSessionManager,
    rag_helper: ClaudeRAGHelper,
) -> list[dict[str, Any]]:
    """
    Create MCP tool definitions for Claude Desktop.

    These tools allow Claude to:
    - Save and retrieve memories
    - Search knowledge bases
    - Manage session state
    """
    return [
        {
            "name": "save_memory",
            "description": "Save important information to remember later",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "The information to remember",
                    },
                    "category": {
                        "type": "string",
                        "description": "Category: personal, work, project, etc.",
                        "default": "general",
                    },
                },
                "required": ["content"],
            },
        },
        {
            "name": "recall_memories",
            "description": "Recall previously saved memories",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category (optional)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max memories to return",
                        "default": 10,
                    },
                },
            },
        },
        {
            "name": "search_knowledge",
            "description": "Search the knowledge base for relevant information",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_context",
            "description": "Get full context including memories and relevant knowledge",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Current query or topic",
                    },
                },
                "required": ["query"],
            },
        },
    ]


async def demo_claude_integration() -> None:
    """Demonstrate Claude Desktop integration patterns."""
    print("🎭 Claude Desktop Integration Demo")
    print("=" * 50)

    # Initialize components
    session_manager = ClaudeSessionManager()
    rag_helper = ClaudeRAGHelper(session_manager)

    # Create a demo session
    session_id = "claude-demo-session"
    print(f"\n📁 Session: {session_id}")

    # Add some memories
    print("\n💾 Saving memories...")
    session_manager.save_memory(
        session_id,
        "User prefers Australian English spelling",
        category="preference",
        importance=0.8,
    )
    session_manager.save_memory(
        session_id,
        "Working on the agentic-brain project",
        category="project",
        importance=0.9,
    )
    session_manager.save_memory(
        session_id,
        "Deadline for v2.0 release is end of month",
        category="project",
        importance=0.95,
    )
    print("   ✅ 3 memories saved")

    # Add knowledge to RAG
    print("\n📚 Adding knowledge base documents...")
    sample_doc = """
    Agentic Brain is an AI agent framework built in Australia.
    It supports multiple LLM providers including Anthropic Claude,
    OpenAI, Ollama, and OpenRouter. The framework is designed
    for enterprise use with features like multi-tenant isolation,
    on-premise deployment, and comprehensive security controls.
    
    Key features include:
    - MCP server for Claude Desktop integration
    - Neo4j knowledge graphs for persistent memory
    - RAG pipeline with hybrid search
    - Real-time streaming via WebSocket and SSE
    """
    chunks = rag_helper.add_document(
        sample_doc,
        metadata={"source": "documentation", "type": "overview"},
    )
    print(f"   ✅ Added {chunks} document chunks")

    # Build context for a query
    print("\n🔍 Building context for Claude...")
    context = rag_helper.build_context(
        query="What LLM providers does agentic-brain support?",
        session_id=session_id,
    )
    print("\nGenerated Context:")
    print("-" * 40)
    print(context)
    print("-" * 40)

    # Show MCP tools
    print("\n🔧 Available MCP Tools:")
    tools = create_mcp_tools(session_manager, rag_helper)
    for tool in tools:
        print(f"   • {tool['name']}: {tool['description']}")

    # Show Claude config
    print("\n📝 Claude Desktop Configuration:")
    config = {
        "mcpServers": {
            "agentic-brain": {
                "command": "python",
                "args": ["-m", "agentic_brain.mcp"],
                "env": {
                    "NEO4J_URI": "bolt://localhost:7687",
                    "NEO4J_PASSWORD": "your-password",
                },
            }
        }
    }
    print(json.dumps(config, indent=2))

    print("\n✅ Demo complete!")
    print(f"\nSession data stored at: {session_manager.storage_dir}")


async def main() -> None:
    """Main entry point."""
    await demo_claude_integration()


if __name__ == "__main__":
    asyncio.run(main())
