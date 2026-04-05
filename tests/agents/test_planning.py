# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tests for planning and execution framework.
"""

import pytest

from agentic_brain.agents import (
    Action,
    ActionType,
    Plan,
    Planner,
    PlanningStrategy,
    ReActAgent,
    ToolExecutor,
    ExecutionContext,
    ExecutionError,
    create_default_registry,
)


class TestActionAndPlan:
    """Test Action and Plan classes."""

    def test_action_creation(self):
        """Test action creation."""
        action = Action(
            type=ActionType.THINK,
            description="Analyze task",
        )
        assert action.type == ActionType.THINK
        assert action.description == "Analyze task"
        assert action.status == "pending"

    def test_action_to_dict(self):
        """Test action to dictionary."""
        action = Action(
            type=ActionType.ACT,
            description="Execute",
            priority=7,
        )
        action_dict = action.to_dict()
        assert action_dict["type"] == "act"
        assert action_dict["priority"] == 7

    def test_plan_creation(self):
        """Test plan creation."""
        plan = Plan(goal="Test goal")
        assert plan.goal == "Test goal"
        assert len(plan.actions) == 0

    def test_plan_add_action(self):
        """Test adding action to plan."""
        plan = Plan(goal="Test goal")
        action = Action(
            type=ActionType.THINK,
            estimated_duration_seconds=1.0,
        )
        plan.add_action(action)
        
        assert len(plan.actions) == 1
        assert plan.estimated_total_duration == 1.0

    def test_plan_get_next_action(self):
        """Test getting next action."""
        plan = Plan(goal="Test")
        action1 = Action(type=ActionType.THINK, status="pending")
        action2 = Action(type=ActionType.ACT, status="pending")
        
        plan.actions.append(action1)
        plan.actions.append(action2)
        
        next_action = plan.get_next_action()
        assert next_action is not None
        assert next_action.type == ActionType.THINK

    def test_plan_mark_complete(self):
        """Test marking action complete."""
        plan = Plan(goal="Test")
        action = Action(type=ActionType.THINK, status="pending")
        plan.actions.append(action)
        
        plan.mark_action_complete(action.id)
        assert action.status == "complete"

    def test_plan_is_complete(self):
        """Test checking plan completion."""
        plan = Plan(goal="Test")
        action1 = Action(type=ActionType.THINK, status="complete")
        action2 = Action(type=ActionType.ACT, status="complete")
        
        plan.actions.append(action1)
        plan.actions.append(action2)
        
        assert plan.is_complete() is True

    def test_plan_to_dict(self):
        """Test plan to dictionary."""
        plan = Plan(goal="Test goal")
        plan_dict = plan.to_dict()
        
        assert plan_dict["goal"] == "Test goal"
        assert "actions" in plan_dict


class TestPlanner:
    """Test Planner."""

    @pytest.mark.asyncio
    async def test_planner_creation(self):
        """Test planner creation."""
        planner = Planner()
        assert planner.strategy == PlanningStrategy.LINEAR

    @pytest.mark.asyncio
    async def test_create_linear_plan(self):
        """Test creating linear plan."""
        planner = Planner(PlanningStrategy.LINEAR)
        plan = await planner.create_plan("Complete task")
        
        assert plan.goal == "Complete task"
        assert len(plan.actions) > 0
        assert plan.strategy == PlanningStrategy.LINEAR

    @pytest.mark.asyncio
    async def test_create_hierarchical_plan(self):
        """Test creating hierarchical plan."""
        planner = Planner(PlanningStrategy.HIERARCHICAL)
        plan = await planner.create_plan("Complete complex task")
        
        assert plan.strategy == PlanningStrategy.HIERARCHICAL
        assert len(plan.actions) > 0

    @pytest.mark.asyncio
    async def test_create_reactive_plan(self):
        """Test creating reactive plan."""
        planner = Planner(PlanningStrategy.REACTIVE)
        plan = await planner.create_plan("Adapt to changes")
        
        assert plan.strategy == PlanningStrategy.REACTIVE
        assert any(a.type == ActionType.OBSERVE for a in plan.actions)

    @pytest.mark.asyncio
    async def test_refine_plan(self):
        """Test plan refinement."""
        planner = Planner()
        plan = await planner.create_plan("Initial task")
        original_count = len(plan.actions)
        
        refined = await planner.refine_plan(plan, "Plan failed")
        assert len(refined.actions) >= original_count


class TestReActAgent:
    """Test ReActAgent."""

    @pytest.mark.asyncio
    async def test_react_agent_creation(self):
        """Test ReAct agent creation."""
        agent = ReActAgent()
        assert agent.current_plan is None

    @pytest.mark.asyncio
    async def test_react_think_and_act(self):
        """Test ReAct think and act loop."""
        agent = ReActAgent()
        plan, results = await agent.think_and_act("Test task")
        
        assert plan is not None
        assert isinstance(results, list)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_react_plan_execution(self):
        """Test ReAct executes all actions."""
        agent = ReActAgent()
        plan, results = await agent.think_and_act("Complete workflow")
        
        assert plan.is_complete() is True


class TestToolExecutor:
    """Test ToolExecutor."""

    @pytest.mark.asyncio
    async def test_executor_creation(self):
        """Test executor creation."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        assert executor.tool_registry is not None
        assert executor.max_concurrent == 10

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        """Test successful tool execution."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        result = await executor.execute_tool(
            "calculate",
            expression="2 + 2",
        )
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        """Test executing nonexistent tool."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        result = await executor.execute_tool("nonexistent")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_batch(self):
        """Test batch execution."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        operations = [
            ("calculate", {"expression": "2 + 2"}),
            ("calculate", {"expression": "5 * 5"}),
        ]
        
        results = await executor.execute_batch(operations)
        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_batch_stop_on_error(self):
        """Test batch execution with stop on error."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        operations = [
            ("calculate", {"expression": "invalid"}),
            ("calculate", {"expression": "2 + 2"}),
        ]
        
        results = await executor.execute_batch(
            operations,
            stop_on_error=True,
        )
        assert any(not r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_with_fallback(self):
        """Test execution with fallback."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        result = await executor.execute_with_fallback(
            "calculate",
            "search",
            expression="2 + 2",
            query="test",
        )
        
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_with_validation(self):
        """Test execution with validation."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        def validator(result):
            return result.output.get("result", 0) > 0
        
        result = await executor.execute_with_validation(
            "calculate",
            validator=validator,
            expression="2 + 2",
        )
        
        assert result.success is True

    def test_executor_stats(self):
        """Test executor statistics."""
        registry = create_default_registry()
        executor = ToolExecutor(tool_registry=registry)
        
        stats = executor.get_stats()
        assert "active_executions" in stats
        assert stats["available_tools"] > 0

    def test_executor_repr(self):
        """Test executor representation."""
        executor = ToolExecutor()
        repr_str = repr(executor)
        assert "ToolExecutor" in repr_str


class TestExecutionContext:
    """Test ExecutionContext."""

    def test_context_creation(self):
        """Test context creation."""
        ctx = ExecutionContext(tool_name="test_tool")
        assert ctx.tool_name == "test_tool"
        assert ctx.max_retries == 3
        assert ctx.execution_id is not None

    def test_context_timeout(self):
        """Test context with custom timeout."""
        ctx = ExecutionContext(timeout_seconds=60.0)
        assert ctx.timeout_seconds == 60.0


class TestExecutionErrors:
    """Test execution errors."""

    def test_execution_error(self):
        """Test ExecutionError."""
        error = ExecutionError("Test error")
        assert "Test error" in str(error)

    def test_execution_timeout(self):
        """Test ExecutionTimeout."""
        timeout = ExecutionTimeout("Timed out")
        assert isinstance(timeout, ExecutionError)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
