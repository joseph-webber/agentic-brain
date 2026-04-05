# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tests for RAG agent implementation.
"""

import pytest

from agentic_brain.agents import (
    RAGAgent,
    RAGAgentConfig,
    AgentRole,
    ToolCategory,
)


class TestRAGAgentConfig:
    """Test RAGAgentConfig."""

    def test_config_defaults(self):
        """Test default configuration."""
        config = RAGAgentConfig(name="test_rag")
        assert config.name == "test_rag"
        assert config.role == AgentRole.RAG_AGENT
        assert config.max_context_docs == 5
        assert config.enable_planning is True

    def test_config_custom(self):
        """Test custom configuration."""
        config = RAGAgentConfig(
            name="custom_rag",
            max_context_docs=10,
            enable_planning=False,
        )
        assert config.max_context_docs == 10
        assert config.enable_planning is False


class TestRAGAgent:
    """Test RAGAgent."""

    def test_agent_creation(self):
        """Test agent creation."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        assert agent.config.name == "test_rag"
        assert agent.memory is not None
        assert agent.tool_registry is not None

    def test_agent_with_custom_registry(self):
        """Test agent with custom tool registry."""
        from agentic_brain.agents import create_default_registry
        
        config = RAGAgentConfig(name="test_rag")
        registry = create_default_registry()
        agent = RAGAgent(config, tool_registry=registry)
        
        assert agent.tool_registry is registry

    @pytest.mark.asyncio
    async def test_agent_execute_task(self):
        """Test executing task."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        result = await agent.execute("What is Python?")
        
        assert result.success is True
        assert result.output is not None

    @pytest.mark.asyncio
    async def test_agent_think(self):
        """Test agent thinking."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        thinking = await agent.think("Sample question")
        assert "Considering" in thinking

    @pytest.mark.asyncio
    async def test_agent_observe(self):
        """Test agent observation."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        observation = await agent.observe()
        assert "memory_size" in observation
        assert "available_tools" in observation

    @pytest.mark.asyncio
    async def test_agent_add_document(self):
        """Test adding document to knowledge base."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        await agent.add_document("Python is a programming language")
        assert len(agent._documents) == 1

    @pytest.mark.asyncio
    async def test_agent_add_multiple_documents(self):
        """Test adding multiple documents."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        docs = [
            {"content": "Document 1"},
            {"content": "Document 2"},
        ]
        await agent.add_documents(docs)
        assert len(agent._documents) == 2

    def test_get_tools(self):
        """Test getting tools schema."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        tools = agent.get_tools()
        assert len(tools) > 0
        assert any(t["name"] == "search" for t in tools)

    @pytest.mark.asyncio
    async def test_call_tool(self):
        """Test calling tool through agent."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        result = await agent.call_tool("calculate", expression="2 + 2")
        assert result.success is True

    def test_get_conversation_history(self):
        """Test getting conversation history."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        history = agent.get_conversation_history()
        assert isinstance(history, list)

    @pytest.mark.asyncio
    async def test_agent_with_context(self):
        """Test agent execution with context."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        result = await agent.execute(
            "Answer a question",
            context_data="relevant info",
        )
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_agent_memory_persistence(self):
        """Test memory across calls."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        await agent.execute("First task")
        history1 = agent.get_conversation_history()
        
        await agent.execute("Second task")
        history2 = agent.get_conversation_history()
        
        assert len(history2) > len(history1)

    @pytest.mark.asyncio
    async def test_agent_with_planning_disabled(self):
        """Test agent with planning disabled."""
        config = RAGAgentConfig(
            name="test_rag",
            enable_planning=False,
        )
        agent = RAGAgent(config)
        
        result = await agent.execute("Quick task")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_agent_with_reflection_disabled(self):
        """Test agent with reflection disabled."""
        config = RAGAgentConfig(
            name="test_rag",
            enable_reflection=False,
        )
        agent = RAGAgent(config)
        
        result = await agent.execute("Task")
        assert result.success is True
        assert "reflection" not in result.context.metadata

    @pytest.mark.asyncio
    async def test_agent_cleanup(self):
        """Test agent cleanup."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        await agent.reset()
        history = agent.get_conversation_history()
        assert len(history) == 0

    def test_agent_metadata(self):
        """Test agent metadata."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        metadata = agent.get_metadata()
        assert metadata["role"] == "rag_agent"
        assert metadata["name"] == "test_rag"

    @pytest.mark.asyncio
    async def test_agent_multiple_sequential_tasks(self):
        """Test multiple sequential task executions."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        results = []
        for i in range(3):
            result = await agent.execute(f"Task {i}")
            results.append(result)
        
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_agent_document_retrieval(self):
        """Test document retrieval for context."""
        config = RAGAgentConfig(name="test_rag", max_context_docs=3)
        agent = RAGAgent(config)
        
        for i in range(5):
            await agent.add_document(f"Document {i}")
        
        docs = await agent._retrieve_context("test query")
        assert len(docs) <= 3

    @pytest.mark.asyncio
    async def test_agent_execution_time(self):
        """Test that execution time is measured."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        result = await agent.execute("Test task")
        assert result.execution_time_ms > 0

    def test_agent_tool_list(self):
        """Test tool listing."""
        config = RAGAgentConfig(name="test_rag")
        agent = RAGAgent(config)
        
        tools = agent.get_tools()
        tool_names = [t["name"] for t in tools]
        
        assert "search" in tool_names
        assert "calculate" in tool_names
        assert "execute_code" in tool_names


class TestRAGAgentIntegration:
    """Integration tests for RAG agent."""

    @pytest.mark.asyncio
    async def test_full_rag_workflow(self):
        """Test complete RAG workflow."""
        config = RAGAgentConfig(
            name="integration_test",
            enable_planning=True,
            enable_reflection=True,
        )
        agent = RAGAgent(config)
        
        await agent.add_document("Python is a programming language")
        await agent.add_document("It was created by Guido van Rossum")
        
        result = await agent.execute("Tell me about Python")
        
        assert result.success is True
        assert len(agent.get_conversation_history()) > 0

    @pytest.mark.asyncio
    async def test_rag_with_tool_usage(self):
        """Test RAG agent using tools."""
        config = RAGAgentConfig(name="tool_test")
        agent = RAGAgent(config)
        
        await agent.add_document("2 plus 2 equals 4")
        result = await agent.execute("Calculate: what is 2 + 2?")
        
        assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
