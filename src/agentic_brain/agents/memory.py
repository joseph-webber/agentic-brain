# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Agent Memory and Context Management.

Handles agent context windows, conversation history, and memory persistence.
Supports both in-memory and persistent storage backends.

Example:
    >>> from agentic_brain.agents.memory import AgentMemory, MemoryConfig
    >>> memory = AgentMemory(MemoryConfig(max_items=1000))
    >>> memory.add_message("user", "Hello, agent!")
    >>> messages = memory.recall(limit=10)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of agent memory."""

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"


@dataclass
class MemoryItem:
    """Single memory item."""

    id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    memory_type: MemoryType = MemoryType.SHORT_TERM
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5
    embedding: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "type": self.memory_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "importance": self.importance,
        }


@dataclass
class ConversationTurn:
    """Single conversation turn (message pair)."""

    id: str = field(default_factory=lambda: str(uuid4()))
    role: str = ""
    content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class MemoryConfig:
    """Memory configuration."""

    max_items: int = 1000
    max_context_tokens: int = 4000
    enable_summarization: bool = True
    enable_compression: bool = True
    ttl_seconds: int | None = None
    persistence_path: str | None = None


class AgentMemory:
    """
    Agent memory management system.

    Manages conversation history, memories, and context windows for agents.
    """

    def __init__(self, config: MemoryConfig | None = None):
        """
        Initialize agent memory.

        Args:
            config: Memory configuration
        """
        self.config = config or MemoryConfig()
        self._conversation_history: list[ConversationTurn] = []
        self._memories: dict[str, MemoryItem] = {}
        self._current_context: dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)

    def add_message(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationTurn:
        """
        Add message to conversation history.

        Args:
            role: Message role (e.g., 'user', 'assistant')
            content: Message content
            metadata: Additional metadata

        Returns:
            ConversationTurn instance
        """
        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._conversation_history.append(turn)

        if len(self._conversation_history) > self.config.max_items:
            self._conversation_history.pop(0)

        return turn

    def recall(self, limit: int | None = None) -> list[ConversationTurn]:
        """
        Recall conversation history.

        Args:
            limit: Maximum number of turns to return

        Returns:
            List of conversation turns
        """
        if limit is None:
            return self._conversation_history.copy()
        return self._conversation_history[-limit:]

    def add_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.EPISODIC,
        metadata: dict[str, Any] | None = None,
        importance: float = 0.5,
    ) -> MemoryItem:
        """
        Add memory item.

        Args:
            content: Memory content
            memory_type: Type of memory
            metadata: Additional metadata
            importance: Importance score (0.0-1.0)

        Returns:
            MemoryItem instance
        """
        item = MemoryItem(
            content=content,
            memory_type=memory_type,
            metadata=metadata or {},
            importance=max(0.0, min(1.0, importance)),
        )
        self._memories[item.id] = item

        if len(self._memories) > self.config.max_items:
            self._remove_least_important()

        return item

    def recall_memories(
        self,
        memory_type: MemoryType | None = None,
        min_importance: float = 0.0,
        limit: int | None = None,
    ) -> list[MemoryItem]:
        """
        Recall memories.

        Args:
            memory_type: Filter by memory type
            min_importance: Minimum importance threshold
            limit: Maximum number to return

        Returns:
            List of memory items sorted by importance
        """
        memories = list(self._memories.values())

        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]

        memories = [m for m in memories if m.importance >= min_importance]
        memories.sort(key=lambda m: m.importance, reverse=True)

        if limit:
            memories = memories[:limit]

        return memories

    def set_context(self, key: str, value: Any) -> None:
        """
        Set context variable.

        Args:
            key: Context key
            value: Context value
        """
        self._current_context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """
        Get context variable.

        Args:
            key: Context key
            default: Default value if not found

        Returns:
            Context value or default
        """
        return self._current_context.get(key, default)

    def get_full_context(self) -> dict[str, Any]:
        """
        Get full current context.

        Returns:
            Dictionary with all context
        """
        return self._current_context.copy()

    def clear_context(self) -> None:
        """Clear all context."""
        self._current_context.clear()

    def _remove_least_important(self) -> None:
        """Remove least important memory item."""
        if not self._memories:
            return

        least_important_id = min(
            self._memories.keys(),
            key=lambda k: self._memories[k].importance,
        )
        del self._memories[least_important_id]

    def get_context_window(self) -> list[dict[str, Any]]:
        """
        Get context window for LLM.

        Returns:
            List of conversation turns as dictionaries
        """
        turns = []
        token_count = 0

        for turn in reversed(self._conversation_history):
            turn_tokens = len(turn.content.split())
            if token_count + turn_tokens > self.config.max_context_tokens:
                break
            turns.insert(0, turn.to_dict())
            token_count += turn_tokens

        return turns

    def summarize(self) -> str:
        """
        Summarize conversation history.

        Returns:
            Summary string
        """
        if not self._conversation_history:
            return "No conversation history."

        summaries = []
        for turn in self._conversation_history[-10:]:
            summaries.append(f"{turn.role}: {turn.content[:100]}")

        return "\n".join(summaries)

    def clear(self) -> None:
        """Clear all memory."""
        self._conversation_history.clear()
        self._memories.clear()
        self._current_context.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get memory statistics."""
        return {
            "conversation_turns": len(self._conversation_history),
            "memories": len(self._memories),
            "context_size": len(self._current_context),
            "avg_importance": (
                sum(m.importance for m in self._memories.values())
                / len(self._memories)
                if self._memories
                else 0.0
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """Export memory to dictionary."""
        return {
            "conversation": [t.to_dict() for t in self._conversation_history],
            "memories": {id: m.to_dict() for id, m in self._memories.items()},
            "context": self._current_context,
        }

    def from_dict(self, data: dict[str, Any]) -> None:
        """
        Import memory from dictionary.

        Args:
            data: Dictionary with memory data
        """
        self.clear()

        for turn_data in data.get("conversation", []):
            turn = ConversationTurn(
                id=turn_data.get("id", str(uuid4())),
                role=turn_data.get("role", ""),
                content=turn_data.get("content", ""),
                metadata=turn_data.get("metadata", {}),
            )
            self._conversation_history.append(turn)

        for memory_data in data.get("memories", {}).values():
            memory = MemoryItem(
                id=memory_data.get("id", str(uuid4())),
                content=memory_data.get("content", ""),
                memory_type=MemoryType(
                    memory_data.get("type", MemoryType.EPISODIC.value)
                ),
                metadata=memory_data.get("metadata", {}),
                importance=memory_data.get("importance", 0.5),
            )
            self._memories[memory.id] = memory

        self._current_context = data.get("context", {})

    def __repr__(self) -> str:
        return f"AgentMemory(turns={len(self._conversation_history)}, memories={len(self._memories)})"
