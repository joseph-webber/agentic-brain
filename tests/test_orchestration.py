# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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
Comprehensive tests for the orchestration system.

Tests cover:
- Crew execution strategies (sequential, parallel, hierarchical)
- Workflow with branching and state management
- Error handling and retries
- Shared memory between agents
- Complex multi-step workflows
"""

import pytest

from agentic_brain.orchestration import (
    AgentRole,
    Crew,
    CrewConfig,
    ExecutionStrategy,
    Workflow,
    WorkflowState,
    WorkflowStep,
)
from agentic_brain.orchestration.crew import (
    AgentResult,
    MockAgent,
    SharedMemory,
)
from agentic_brain.orchestration.workflow import (
    Transition,
    branch_if,
    on_failure,
    on_success,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_agents():
    """Create mock agents for testing."""
    return [
        MockAgent(name="agent1", role="worker"),
        MockAgent(name="agent2", role="worker"),
        MockAgent(name="agent3", role="worker"),
    ]


@pytest.fixture
def counting_agents():
    """Create agents that count their executions."""
    counter = {"count": 0}

    def count_fn(task: str, context: dict) -> str:
        counter["count"] += 1
        return f"Execution {counter['count']}"

    return [
        MockAgent(name="counter1", process_fn=count_fn),
        MockAgent(name="counter2", process_fn=count_fn),
    ]


@pytest.fixture
def context_agents():
    """Create agents that use context."""

    def context_fn(task: str, context: dict) -> str:
        value = context.get("multiplier", 1)
        return f"Result: {len(task) * value}"

    return [
        MockAgent(name="processor", process_fn=context_fn),
    ]


# ============================================================================
# Crew Tests
# ============================================================================


class TestCrew:
    """Tests for Crew class."""

    def test_crew_init(self, mock_agents):
        """Test crew initialization."""
        crew = Crew(mock_agents, strategy=ExecutionStrategy.SEQUENTIAL)
        assert len(crew.agents) == 3
        assert crew.strategy == ExecutionStrategy.SEQUENTIAL

    def test_crew_add_agent(self, mock_agents):
        """Test adding agents to crew."""
        crew = Crew(mock_agents[:1])
        assert len(crew.agents) == 1

        crew.add_agent(mock_agents[1])
        assert len(crew.agents) == 2

    def test_crew_remove_agent(self, mock_agents):
        """Test removing agents from crew."""
        crew = Crew(mock_agents)
        assert len(crew.agents) == 3

        crew.remove_agent("agent1")
        assert len(crew.agents) == 2
        assert "agent1" not in crew.agents

    def test_crew_get_agent(self, mock_agents):
        """Test getting agent by name."""
        crew = Crew(mock_agents)
        agent = crew.get_agent("agent1")
        assert agent is not None
        assert agent.name == "agent1"

    def test_crew_sequential_execution(self, mock_agents):
        """Test sequential execution strategy."""
        crew = Crew(mock_agents, strategy=ExecutionStrategy.SEQUENTIAL)
        results = crew.run("Test task")

        assert len(results) == 3
        assert all(r.success for r in results)
        assert all("Processed" in str(r.result) for r in results)

    def test_crew_parallel_execution(self, mock_agents):
        """Test parallel execution strategy."""
        crew = Crew(mock_agents, strategy=ExecutionStrategy.PARALLEL)
        results = crew.run("Test task")

        assert len(results) == 3
        assert all(r.success for r in results)

    def test_crew_hierarchical_execution(self):
        """Test hierarchical execution with manager."""
        manager = MockAgent(name="manager", role=AgentRole.MANAGER.value)
        worker1 = MockAgent(name="worker1", role="worker")
        worker2 = MockAgent(name="worker2", role="worker")

        crew = Crew(
            [manager, worker1, worker2],
            strategy=ExecutionStrategy.HIERARCHICAL,
        )
        results = crew.run("Coordinate work")

        # Manager + 2 workers
        assert len(results) >= 2

    def test_crew_reset(self, mock_agents):
        """Test crew reset."""
        crew = Crew(mock_agents)
        crew.run("Test")

        assert len(crew._results) > 0

        crew.reset()

        assert len(crew._results) == 0

    def test_crew_shared_memory(self):
        """Test shared memory between agents."""

        def agent1_fn(task: str, context: dict) -> str:
            context.get("shared_memory", {})["key1"] = "value1"
            return "agent1_result"

        def agent2_fn(task: str, context: dict) -> str:
            value = context.get("key1", "not_found")
            return f"agent2_result: {value}"

        agent1 = MockAgent(name="agent1", process_fn=agent1_fn)
        agent2 = MockAgent(name="agent2", process_fn=agent2_fn)

        crew = Crew([agent1, agent2])
        crew.run("Test")

        # Check that shared memory was used
        shared = crew.shared_memory.to_dict()
        # The memory includes the results from execution
        assert "agent1_result" in str(shared)

    def test_crew_config_with_callback(self, mock_agents):
        """Test crew with task completion callback."""
        completed = []

        def on_complete(result: AgentResult):
            completed.append(result.agent_name)

        config = CrewConfig(on_task_complete=on_complete)
        crew = Crew(mock_agents, config=config)
        crew.run("Test")

        assert len(completed) == 3

    def test_crew_with_context(self, context_agents):
        """Test passing context to agents."""
        crew = Crew(context_agents)
        results = crew.run("12345", context={"multiplier": 2})

        assert results[0].success
        assert "10" in str(results[0].result)  # 5 * 2

    def test_crew_filter_results(self, mock_agents):
        """Test filtering results."""

        def none_fn(task: str, context: dict) -> None:
            return None

        mock_agents[0].process_fn = none_fn

        crew = Crew(mock_agents)
        results = crew.run("Test", filter_results=True)

        # Should only have 2 results (agent2 and agent3)
        assert len(results) == 2

    def test_crew_get_results_by_agent(self, mock_agents):
        """Test getting results by agent name."""
        crew = Crew(mock_agents)
        crew.run("Test")

        result = crew.get_results(agent_name="agent1")
        assert result is not None
        assert result.agent_name == "agent1"

        all_results = crew.get_results()
        assert len(all_results) == 3


# ============================================================================
# Workflow Tests
# ============================================================================


class TestWorkflow:
    """Tests for Workflow class."""

    def test_workflow_init(self):
        """Test workflow initialization."""
        workflow = Workflow(start_step="step1")
        assert workflow.start_step == "step1"
        assert workflow.state == WorkflowState.PENDING

    def test_workflow_add_step(self):
        """Test adding steps."""

        def execute_fn(ctx):
            return "result"

        workflow = Workflow("step1")
        step = WorkflowStep(name="step1", execute=execute_fn)

        workflow.add_step(step)
        assert "step1" in workflow.steps

    def test_workflow_add_steps_fluent(self):
        """Test fluent API for adding steps."""

        def execute_fn(ctx):
            return "result"

        workflow = Workflow("step1")
        result = (
            workflow.add_step(WorkflowStep(name="step1", execute=execute_fn))
            .add_step(WorkflowStep(name="step2", execute=execute_fn))
            .add_steps(
                [
                    WorkflowStep(name="step3", execute=execute_fn),
                    WorkflowStep(name="step4", execute=execute_fn),
                ]
            )
        )

        assert result is workflow
        assert len(workflow.steps) == 4

    def test_workflow_simple_execution(self):
        """Test simple linear workflow."""
        results = []

        def step1_fn(ctx):
            results.append("step1")
            return "step1_result"

        def step2_fn(ctx):
            results.append("step2")
            return "step2_result"

        workflow = Workflow("step1")
        workflow.add_step(
            WorkflowStep(
                name="step1",
                execute=step1_fn,
                transitions=[Transition(to_step="step2")],
            )
        )
        workflow.add_step(WorkflowStep(name="step2", execute=step2_fn))

        result = workflow.run()

        assert result.state == WorkflowState.COMPLETED
        assert result.steps_executed == ["step1", "step2"]
        assert results == ["step1", "step2"]

    def test_workflow_branching(self):
        """Test conditional branching."""
        executed = []

        def check_fn(ctx):
            return "use_path_a" in ctx

        def init_fn(ctx):
            ctx["use_path_a"] = True
            return "init"

        def path_a_fn(ctx):
            executed.append("a")
            return "path_a"

        def path_b_fn(ctx):
            executed.append("b")
            return "path_b"

        workflow = Workflow("init")
        workflow.add_step(
            WorkflowStep(
                name="init",
                execute=init_fn,
                transitions=branch_if(check_fn, "path_a", "path_b"),
            )
        )
        workflow.add_step(WorkflowStep(name="path_a", execute=path_a_fn))
        workflow.add_step(WorkflowStep(name="path_b", execute=path_b_fn))

        result = workflow.run()

        assert result.success()
        assert "a" in executed
        assert "b" not in executed

    def test_workflow_on_success_transition(self):
        """Test on_success transition."""
        executed = []

        def success_fn(ctx):
            executed.append("success")
            return "success_result"

        def recover_fn(ctx):
            executed.append("recover")
            return "recover_result"

        def final_fn(ctx):
            executed.append("final")
            return "final_result"

        workflow = Workflow("success")
        workflow.add_step(
            WorkflowStep(
                name="success", execute=success_fn, transitions=on_success("final")
            )
        )
        workflow.add_step(WorkflowStep(name="recover", execute=recover_fn))
        workflow.add_step(WorkflowStep(name="final", execute=final_fn))

        result = workflow.run()

        assert result.success()
        assert executed == ["success", "final"]

    def test_workflow_on_failure_transition(self):
        """Test on_failure transition."""
        executed = []

        def failing_fn(ctx):
            executed.append("fail")
            raise ValueError("Intentional failure")

        def recover_fn(ctx):
            executed.append("recover")
            return "recovered"

        workflow = Workflow("fail")
        workflow.add_step(
            WorkflowStep(
                name="fail",
                execute=failing_fn,
                transitions=on_failure("recover"),
                retry_count=0,
            )
        )
        workflow.add_step(WorkflowStep(name="recover", execute=recover_fn))

        workflow.run()

        assert executed == ["fail", "recover"]

    def test_workflow_retry(self):
        """Test step retry mechanism."""
        attempts = []

        def retrying_fn(ctx):
            attempts.append(1)
            if len(attempts) < 3:
                raise ValueError("Try again")
            return "success"

        workflow = Workflow("retry_step")
        workflow.add_step(
            WorkflowStep(
                name="retry_step",
                execute=retrying_fn,
                retry_count=2,
            )
        )

        result = workflow.run()

        assert result.success()
        assert len(attempts) == 3

    def test_workflow_skip_condition(self):
        """Test skipping steps with conditions."""
        executed = []

        def normal_fn(ctx):
            executed.append("normal")
            return "normal_result"

        def skipped_fn(ctx):
            executed.append("skipped")
            return "skipped_result"

        def final_fn(ctx):
            executed.append("final")
            return "final_result"

        workflow = Workflow("normal")
        workflow.add_step(
            WorkflowStep(
                name="normal",
                execute=normal_fn,
                transitions=[Transition(to_step="maybe_skip")],
            )
        )
        workflow.add_step(
            WorkflowStep(
                name="maybe_skip",
                execute=skipped_fn,
                skip_condition=lambda ctx: True,
                transitions=[Transition(to_step="final")],
            )
        )
        workflow.add_step(WorkflowStep(name="final", execute=final_fn))

        result = workflow.run()

        assert result.success()
        assert "skipped" not in executed
        assert executed == ["normal", "final"]

    def test_workflow_context_passing(self):
        """Test context passing between steps."""

        def step1_fn(ctx):
            ctx["value"] = 42
            return "step1"

        def step2_fn(ctx):
            return ctx.get("value") * 2

        workflow = Workflow("step1")
        workflow.add_step(
            WorkflowStep(
                name="step1",
                execute=step1_fn,
                transitions=[Transition(to_step="step2")],
            )
        )
        workflow.add_step(WorkflowStep(name="step2", execute=step2_fn))

        result = workflow.run(context={"initial": "value"})

        assert result.success()
        assert result.get_step_result("step2") == 84
        assert result.final_context["value"] == 42

    def test_workflow_error_handling(self):
        """Test error handling in workflow."""
        errors = []

        def error_handler(error, ctx):
            errors.append(str(error))

        def failing_fn(ctx):
            raise ValueError("Expected error")

        workflow = Workflow("fail")
        workflow.add_step(
            WorkflowStep(
                name="fail",
                execute=failing_fn,
                on_error=error_handler,
                retry_count=0,
            )
        )

        result = workflow.run()

        assert not result.success()
        assert len(errors) == 1
        assert "Expected error" in errors[0]

    def test_workflow_state_management(self):
        """Test workflow state transitions."""

        def simple_fn(ctx):
            return "result"

        workflow = Workflow("step1")
        workflow.add_step(WorkflowStep(name="step1", execute=simple_fn))

        assert workflow.get_state() == WorkflowState.PENDING

        workflow.run()
        assert workflow.get_state() == WorkflowState.COMPLETED

        workflow.reset()
        assert workflow.get_state() == WorkflowState.PENDING

    def test_workflow_pause_cancel(self):
        """Test pausing and cancelling workflows."""
        workflow = Workflow("step1")

        workflow.pause()
        assert workflow.state == WorkflowState.PAUSED

        workflow.cancel()
        assert workflow.state == WorkflowState.CANCELLED

    def test_workflow_missing_start_step(self):
        """Test error when start step doesn't exist."""
        workflow = Workflow("nonexistent")
        result = workflow.run()

        assert not result.success()
        assert "not found" in result.error.lower()

    def test_workflow_infinite_loop_detection(self):
        """Test detection of infinite loops."""

        def dummy_fn(ctx):
            return "result"

        workflow = Workflow("step1")
        workflow.add_step(
            WorkflowStep(
                name="step1",
                execute=dummy_fn,
                transitions=[Transition(to_step="step1")],  # Loop to itself
            )
        )

        result = workflow.run()

        assert not result.success()
        assert "infinite loop" in result.error.lower()

    def test_workflow_complex_branching(self):
        """Test complex multi-path workflow."""
        executed = []

        def init_fn(ctx):
            ctx["score"] = 75
            executed.append("init")
            return "init"

        def high_score_fn(ctx):
            executed.append("high_score")
            return "high_score_result"

        def low_score_fn(ctx):
            executed.append("low_score")
            return "low_score_result"

        def finish_fn(ctx):
            executed.append("finish")
            return "finish_result"

        workflow = Workflow("init")
        workflow.add_step(
            WorkflowStep(
                name="init",
                execute=init_fn,
                transitions=branch_if(
                    lambda ctx: ctx.get("score", 0) >= 70, "high_score", "low_score"
                ),
            )
        )
        workflow.add_step(
            WorkflowStep(
                name="high_score",
                execute=high_score_fn,
                transitions=[Transition(to_step="finish")],
            )
        )
        workflow.add_step(
            WorkflowStep(
                name="low_score",
                execute=low_score_fn,
                transitions=[Transition(to_step="finish")],
            )
        )
        workflow.add_step(WorkflowStep(name="finish", execute=finish_fn))

        result = workflow.run()

        assert result.success()
        assert executed == ["init", "high_score", "finish"]


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining Crew and Workflow."""

    def test_crew_with_workflow(self):
        """Test crew agents within workflow."""
        agents_ran = []

        def workflow_fn(ctx):
            crew = Crew(
                [
                    MockAgent(
                        name="a",
                        process_fn=lambda t, c: (agents_ran.append("a"), "a_result")[1],
                    ),
                    MockAgent(
                        name="b",
                        process_fn=lambda t, c: (agents_ran.append("b"), "b_result")[1],
                    ),
                ]
            )
            results = crew.run("Task")
            return len(results)

        workflow = Workflow("run_crew")
        workflow.add_step(WorkflowStep(name="run_crew", execute=workflow_fn))

        result = workflow.run()

        assert result.success()
        assert len(agents_ran) == 2

    def test_workflow_with_conditional_crew(self):
        """Test conditional crew execution in workflow."""
        executed = []

        def run_crew_sequential(ctx):
            executed.append("seq_crew")
            crew = Crew(
                [MockAgent(name="s1"), MockAgent(name="s2")],
                strategy=ExecutionStrategy.SEQUENTIAL,
            )
            return len(crew.run("Task"))

        def run_crew_parallel(ctx):
            executed.append("par_crew")
            crew = Crew(
                [MockAgent(name="p1"), MockAgent(name="p2")],
                strategy=ExecutionStrategy.PARALLEL,
            )
            return len(crew.run("Task"))

        workflow = Workflow("decide")
        workflow.add_step(
            WorkflowStep(
                name="decide",
                execute=lambda ctx: ctx.update({"use_parallel": True}) or "decided",
                transitions=[
                    Transition(to_step="run_seq"),
                    Transition(to_step="run_par"),
                ],
            )
        )
        workflow.add_step(WorkflowStep(name="run_seq", execute=run_crew_sequential))
        workflow.add_step(WorkflowStep(name="run_par", execute=run_crew_parallel))


# ============================================================================
# Shared Memory Tests
# ============================================================================


class TestSharedMemory:
    """Tests for SharedMemory class."""

    def test_shared_memory_basic(self):
        """Test basic shared memory operations."""
        memory = SharedMemory()

        memory.set("key1", "value1")
        assert memory.get("key1") == "value1"

    def test_shared_memory_update(self):
        """Test updating multiple values."""
        memory = SharedMemory()

        memory.update({"k1": "v1", "k2": "v2"})
        assert memory.get("k1") == "v1"
        assert memory.get("k2") == "v2"

    def test_shared_memory_to_dict(self):
        """Test getting all data."""
        memory = SharedMemory()

        memory.set("k1", "v1")
        memory.set("k2", "v2")

        data = memory.to_dict()
        assert data == {"k1": "v1", "k2": "v2"}

    def test_shared_memory_clear(self):
        """Test clearing shared memory."""
        memory = SharedMemory()

        memory.set("k1", "v1")
        memory.clear()

        assert memory.to_dict() == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
