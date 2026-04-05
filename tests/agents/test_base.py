# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tests for base agent framework.
"""

import asyncio
import pytest

from agentic_brain.agents import (
    Agent,
    AgentConfig,
    AgentContext,
    AgentResult,
    AgentRole,
    AgentState,
)


class ConcreteAgent(Agent):
    """Concrete agent for testing."""

    async def execute(self, task: str, **kwargs):
        """Execute task."""
        await asyncio.sleep(0.01)
        return AgentResult(
            success=True,
            output=f"Completed: {task}",
        )

    async def think(self, task: str, **kwargs):
        """Thinking step."""
        return f"Thinking about: {task}"

    async def observe(self, **kwargs):
        """Observation step."""
        return {"status": "observing"}


class TestAgentConfig:
    """Test AgentConfig."""

    def test_agent_config_defaults(self):
        """Test default configuration."""
        config = AgentConfig(name="test_agent")
        assert config.name == "test_agent"
        assert config.role == AgentRole.GENERALIST
        assert config.max_iterations == 10
        assert config.timeout_seconds == 300.0

    def test_agent_config_custom(self):
        """Test custom configuration."""
        config = AgentConfig(
            name="custom_agent",
            role=AgentRole.REASONER,
            max_iterations=20,
            timeout_seconds=60.0,
        )
        assert config.name == "custom_agent"
        assert config.role == AgentRole.REASONER
        assert config.max_iterations == 20
        assert config.timeout_seconds == 60.0


class TestAgentContext:
    """Test AgentContext."""

    def test_context_creation(self):
        """Test context creation."""
        ctx = AgentContext()
        assert ctx.agent_id is not None
        assert ctx.session_id is not None
        assert ctx.state == AgentState.IDLE
        assert ctx.iteration_count == 0

    def test_context_with_data(self):
        """Test context with metadata."""
        ctx = AgentContext(user_id="user123")
        assert ctx.user_id == "user123"
        ctx.metadata["test_key"] = "test_value"
        assert ctx.metadata["test_key"] == "test_value"


class TestAgentBase:
    """Test base Agent class."""

    def test_agent_initialization(self):
        """Test agent initialization."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        assert agent.config.name == "test_agent"
        assert agent.context.state == AgentState.IDLE
        assert agent.agent_id is not None

    def test_agent_state_management(self):
        """Test state management."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        
        agent.set_state(AgentState.PLANNING)
        assert agent.state == AgentState.PLANNING
        
        agent.set_state(AgentState.EXECUTING)
        assert agent.state == AgentState.EXECUTING

    def test_agent_metadata(self):
        """Test agent metadata."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        
        metadata = agent.get_metadata()
        assert metadata["name"] == "test_agent"
        assert metadata["role"] == "generalist"
        assert metadata["agent_id"] == agent.agent_id

    @pytest.mark.asyncio
    async def test_agent_execute(self):
        """Test agent execution."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        
        result = await agent.run("test task")
        assert result.success is True
        assert result.output == "Completed: test task"
        assert result.execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_agent_think(self):
        """Test agent thinking."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        
        thinking = await agent.think("test task")
        assert "Thinking about: test task" in thinking

    @pytest.mark.asyncio
    async def test_agent_observe(self):
        """Test agent observation."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        
        observation = await agent.observe()
        assert observation["status"] == "observing"

    @pytest.mark.asyncio
    async def test_agent_reset(self):
        """Test agent reset."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        
        agent.set_state(AgentState.EXECUTING)
        await agent.reset()
        assert agent.state == AgentState.IDLE
        assert agent.context.iteration_count == 0

    def test_agent_repr(self):
        """Test agent string representation."""
        config = AgentConfig(name="test_agent")
        agent = ConcreteAgent(config)
        
        repr_str = repr(agent)
        assert "test_agent" in repr_str
        assert "generalist" in repr_str

    @pytest.mark.asyncio
    async def test_agent_error_handling(self):
        """Test error handling in agent."""
        class ErrorAgent(Agent):
            async def execute(self, task: str, **kwargs):
                raise ValueError("Test error")
            
            async def think(self, task: str, **kwargs):
                return "thinking"
            
            async def observe(self, **kwargs):
                return {}

        config = AgentConfig(name="error_agent")
        agent = ErrorAgent(config)
        
        result = await agent.run("test")
        assert result.success is False
        assert "Execution error" in result.error

    @pytest.mark.asyncio
    async def test_agent_timeout(self):
        """Test agent timeout."""
        class SlowAgent(Agent):
            async def execute(self, task: str, **kwargs):
                await asyncio.sleep(10)
                return AgentResult(success=True)
            
            async def think(self, task: str, **kwargs):
                return "thinking"
            
            async def observe(self, **kwargs):
                return {}

        config = AgentConfig(name="slow_agent", timeout_seconds=0.1)
        agent = SlowAgent(config)
        
        result = await agent.run("test")
        assert result.success is False


class TestAgentResult:
    """Test AgentResult."""

    def test_result_creation(self):
        """Test result creation."""
        result = AgentResult(success=True, output="test output")
        assert result.success is True
        assert result.output == "test output"
        assert result.error is None

    def test_result_with_error(self):
        """Test result with error."""
        result = AgentResult(success=False, error="Test error")
        assert result.success is False
        assert result.error == "Test error"

    def test_result_repr(self):
        """Test result representation."""
        result = AgentResult(success=True)
        repr_str = repr(result)
        assert "✓" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
