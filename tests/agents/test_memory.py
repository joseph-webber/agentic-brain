# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tests for agent memory framework.
"""

import pytest

from agentic_brain.agents import (
    AgentMemory,
    ConversationTurn,
    MemoryConfig,
    MemoryItem,
    MemoryType,
)


class TestMemoryConfig:
    """Test MemoryConfig."""

    def test_config_defaults(self):
        """Test default configuration."""
        config = MemoryConfig()
        assert config.max_items == 1000
        assert config.max_context_tokens == 4000
        assert config.enable_summarization is True

    def test_config_custom(self):
        """Test custom configuration."""
        config = MemoryConfig(
            max_items=500,
            max_context_tokens=2000,
            enable_summarization=False,
        )
        assert config.max_items == 500
        assert config.max_context_tokens == 2000
        assert config.enable_summarization is False


class TestConversationTurn:
    """Test ConversationTurn."""

    def test_turn_creation(self):
        """Test turn creation."""
        turn = ConversationTurn(
            role="user",
            content="Hello",
        )
        assert turn.role == "user"
        assert turn.content == "Hello"
        assert turn.id is not None

    def test_turn_to_dict(self):
        """Test converting to dictionary."""
        turn = ConversationTurn(
            role="assistant",
            content="Hi there!",
        )
        turn_dict = turn.to_dict()
        assert turn_dict["role"] == "assistant"
        assert turn_dict["content"] == "Hi there!"


class TestMemoryItem:
    """Test MemoryItem."""

    def test_memory_item_creation(self):
        """Test memory item creation."""
        item = MemoryItem(
            content="Important fact",
            memory_type=MemoryType.SEMANTIC,
        )
        assert item.content == "Important fact"
        assert item.memory_type == MemoryType.SEMANTIC
        assert item.importance == 0.5

    def test_memory_item_importance(self):
        """Test importance scoring."""
        item = MemoryItem(
            content="Critical info",
            importance=0.95,
        )
        assert item.importance == 0.95

    def test_memory_item_to_dict(self):
        """Test converting to dictionary."""
        item = MemoryItem(
            content="Test",
            memory_type=MemoryType.EPISODIC,
        )
        item_dict = item.to_dict()
        assert item_dict["content"] == "Test"
        assert item_dict["type"] == "episodic"


class TestAgentMemory:
    """Test AgentMemory."""

    def test_memory_creation(self):
        """Test memory creation."""
        memory = AgentMemory()
        assert memory is not None
        assert len(memory._conversation_history) == 0

    def test_add_message(self):
        """Test adding message."""
        memory = AgentMemory()
        turn = memory.add_message("user", "Hello")
        
        assert turn.role == "user"
        assert turn.content == "Hello"
        assert len(memory._conversation_history) == 1

    def test_add_multiple_messages(self):
        """Test adding multiple messages."""
        memory = AgentMemory()
        memory.add_message("user", "Hello")
        memory.add_message("assistant", "Hi there")
        memory.add_message("user", "How are you?")
        
        assert len(memory._conversation_history) == 3

    def test_recall_all(self):
        """Test recalling all messages."""
        memory = AgentMemory()
        memory.add_message("user", "First")
        memory.add_message("assistant", "Response")
        
        messages = memory.recall()
        assert len(messages) == 2

    def test_recall_limit(self):
        """Test recalling with limit."""
        memory = AgentMemory()
        memory.add_message("user", "First")
        memory.add_message("assistant", "Second")
        memory.add_message("user", "Third")
        
        recent = memory.recall(limit=2)
        assert len(recent) == 2
        assert recent[-1].content == "Third"

    def test_max_items_limit(self):
        """Test maximum items limit."""
        config = MemoryConfig(max_items=5)
        memory = AgentMemory(config)
        
        for i in range(10):
            memory.add_message("user", f"Message {i}")
        
        assert len(memory._conversation_history) <= 5

    def test_add_memory_item(self):
        """Test adding memory item."""
        memory = AgentMemory()
        item = memory.add_memory(
            "Important fact",
            memory_type=MemoryType.SEMANTIC,
        )
        
        assert item.content == "Important fact"
        assert item.id in memory._memories

    def test_recall_memories(self):
        """Test recalling memories."""
        memory = AgentMemory()
        memory.add_memory("Fact 1", importance=0.9)
        memory.add_memory("Fact 2", importance=0.5)
        memory.add_memory("Fact 3", importance=0.7)
        
        memories = memory.recall_memories()
        assert len(memories) == 3
        assert memories[0].importance >= memories[1].importance

    def test_recall_memories_by_type(self):
        """Test filtering memories by type."""
        memory = AgentMemory()
        memory.add_memory("Semantic fact", MemoryType.SEMANTIC)
        memory.add_memory("Episodic event", MemoryType.EPISODIC)
        
        semantic = memory.recall_memories(MemoryType.SEMANTIC)
        assert len(semantic) == 1
        assert semantic[0].memory_type == MemoryType.SEMANTIC

    def test_recall_memories_by_importance(self):
        """Test filtering by importance."""
        memory = AgentMemory()
        memory.add_memory("Important", importance=0.9)
        memory.add_memory("Less important", importance=0.3)
        
        important = memory.recall_memories(min_importance=0.7)
        assert len(important) == 1

    def test_recall_memories_limit(self):
        """Test limiting recalled memories."""
        memory = AgentMemory()
        for i in range(5):
            memory.add_memory(f"Fact {i}")
        
        limited = memory.recall_memories(limit=2)
        assert len(limited) == 2

    def test_context_management(self):
        """Test context management."""
        memory = AgentMemory()
        memory.set_context("user_id", "user123")
        
        assert memory.get_context("user_id") == "user123"
        assert memory.get_context("nonexistent", "default") == "default"

    def test_full_context(self):
        """Test getting full context."""
        memory = AgentMemory()
        memory.set_context("key1", "value1")
        memory.set_context("key2", "value2")
        
        full_ctx = memory.get_full_context()
        assert full_ctx["key1"] == "value1"
        assert full_ctx["key2"] == "value2"

    def test_clear_context(self):
        """Test clearing context."""
        memory = AgentMemory()
        memory.set_context("key", "value")
        memory.clear_context()
        
        assert memory.get_context("key") is None

    def test_context_window(self):
        """Test context window generation."""
        memory = AgentMemory()
        memory.add_message("user", "Hello" * 100)
        memory.add_message("assistant", "Hi" * 100)
        
        window = memory.get_context_window()
        assert len(window) > 0

    def test_summarize(self):
        """Test conversation summarization."""
        memory = AgentMemory()
        memory.add_message("user", "What is Python?")
        memory.add_message("assistant", "Python is a programming language")
        
        summary = memory.summarize()
        assert "Python" in summary

    def test_clear_all(self):
        """Test clearing all memory."""
        memory = AgentMemory()
        memory.add_message("user", "Hello")
        memory.add_memory("Fact")
        memory.set_context("key", "value")
        
        memory.clear()
        assert len(memory._conversation_history) == 0
        assert len(memory._memories) == 0
        assert len(memory._current_context) == 0

    def test_get_stats(self):
        """Test getting statistics."""
        memory = AgentMemory()
        memory.add_message("user", "Hello")
        memory.add_memory("Fact", importance=0.8)
        
        stats = memory.get_stats()
        assert stats["conversation_turns"] == 1
        assert stats["memories"] == 1

    def test_to_dict(self):
        """Test exporting to dictionary."""
        memory = AgentMemory()
        memory.add_message("user", "Hello")
        memory.add_memory("Fact")
        memory.set_context("key", "value")
        
        data = memory.to_dict()
        assert "conversation" in data
        assert "memories" in data
        assert "context" in data

    def test_from_dict(self):
        """Test importing from dictionary."""
        memory = AgentMemory()
        memory.add_message("user", "Hello")
        original_data = memory.to_dict()
        
        memory2 = AgentMemory()
        memory2.from_dict(original_data)
        
        assert len(memory2._conversation_history) == 1
        assert memory2._conversation_history[0].content == "Hello"

    def test_repr(self):
        """Test memory representation."""
        memory = AgentMemory()
        memory.add_message("user", "Hello")
        
        repr_str = repr(memory)
        assert "AgentMemory" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
