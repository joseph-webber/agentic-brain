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
Crew class for managing multiple agents with different execution strategies.

Features:
- Sequential execution
- Parallel execution
- Hierarchical execution (with manager agent)
- Shared memory between agents
- Role-based agent delegation
- Result aggregation and filtering
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Any, Callable, Protocol

logger = logging.getLogger(__name__)


class ExecutionStrategy(str, Enum):
    """Agent execution strategies."""

    SEQUENTIAL = "sequential"  # Execute agents one by one
    PARALLEL = "parallel"  # Execute agents concurrently
    HIERARCHICAL = "hierarchical"  # Manager agent coordinates


class AgentRole(str, Enum):
    """Pre-defined agent roles."""

    MANAGER = "manager"  # Coordinates and delegates
    RESEARCHER = "researcher"  # Gathers and analyzes information
    ANALYST = "analyst"  # Deep analysis and insights
    EXECUTOR = "executor"  # Implements decisions
    REVIEWER = "reviewer"  # Validates and reviews work
    WORKER = "worker"  # General purpose worker


class Agent(Protocol):
    """Protocol for agent interface."""

    name: str
    role: str

    def run(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Execute task and return result."""
        ...


@dataclass
class AgentTask:
    """Task assigned to an agent."""

    agent_name: str
    task: str
    priority: int = 0  # Higher = more important
    depends_on: list[str] = field(
        default_factory=list
    )  # Agent names that must complete first
    context: dict[str, Any] = field(default_factory=dict)  # Shared context
    timeout: float | None = None
    retry_count: int = 0


@dataclass
class AgentResult:
    """Result from running an agent task."""

    agent_name: str
    task: str
    result: Any
    success: bool = True
    error: str | None = None
    duration_ms: float = 0.0


class SharedMemory:
    """Thread-safe shared memory for agent communication."""

    def __init__(self) -> None:
        """Initialize shared memory."""
        self._data: dict[str, Any] = {}
        self._lock = RLock()

    def set(self, key: str, value: Any) -> None:
        """Set a value in shared memory."""
        with self._lock:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from shared memory."""
        with self._lock:
            return self._data.get(key, default)

    def update(self, updates: dict[str, Any]) -> None:
        """Update multiple values."""
        with self._lock:
            self._data.update(updates)

    def clear(self) -> None:
        """Clear all shared memory."""
        with self._lock:
            self._data.clear()

    def to_dict(self) -> dict[str, Any]:
        """Get a copy of all data."""
        with self._lock:
            return dict(self._data)


@dataclass
class CrewConfig:
    """Configuration for a Crew."""

    strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL
    max_workers: int = 4  # For parallel execution
    timeout: float | None = None  # Total crew timeout
    verbose: bool = False
    on_task_complete: Callable[[AgentResult], None] | None = None


class Crew:
    """
    Multi-agent crew for orchestrating agent execution.

    Example:
        >>> agents = [researcher, analyst, executor]
        >>> crew = Crew(agents, strategy=ExecutionStrategy.PARALLEL)
        >>> results = crew.run("Analyze market trends")
    """

    def __init__(
        self,
        agents: list[Agent],
        strategy: ExecutionStrategy = ExecutionStrategy.SEQUENTIAL,
        config: CrewConfig | None = None,
    ) -> None:
        """
        Initialize crew.

        Args:
            agents: List of agents to manage
            strategy: Execution strategy
            config: Optional crew configuration
        """
        self.agents = {agent.name: agent for agent in agents}
        self.strategy = strategy
        self.config = config or CrewConfig(strategy=strategy)
        self.shared_memory = SharedMemory()
        self._results: dict[str, AgentResult] = {}
        self._execution_order: list[str] = []

    def add_agent(self, agent: Agent) -> None:
        """Add an agent to the crew."""
        self.agents[agent.name] = agent

    def remove_agent(self, agent_name: str) -> None:
        """Remove an agent from the crew."""
        if agent_name in self.agents:
            del self.agents[agent_name]

    def get_agent(self, agent_name: str) -> Agent | None:
        """Get agent by name."""
        return self.agents.get(agent_name)

    def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        filter_results: bool = True,
    ) -> list[AgentResult]:
        """
        Run the crew on a task.

        Args:
            task: Main task description
            context: Optional context to pass to agents
            filter_results: Whether to filter results (remove None/empty)

        Returns:
            List of AgentResult from all agents
        """
        context = context or {}

        if self.config.verbose:
            logger.info(
                f"Crew starting with {len(self.agents)} agents: {self.strategy.value}"
            )

        # Prepare tasks for each agent
        tasks = [
            AgentTask(agent_name=name, task=task, context=context)
            for name in self.agents
        ]

        # Execute based on strategy
        if self.strategy == ExecutionStrategy.SEQUENTIAL:
            self._execute_sequential(tasks)
        elif self.strategy == ExecutionStrategy.PARALLEL:
            self._execute_parallel(tasks)
        elif self.strategy == ExecutionStrategy.HIERARCHICAL:
            self._execute_hierarchical(tasks)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")

        # Build results list
        results = list(self._results.values())

        if filter_results:
            results = [r for r in results if r.result is not None]

        if self.config.verbose:
            logger.info(f"Crew completed: {len(results)} results")

        return results

    def _execute_sequential(self, tasks: list[AgentTask]) -> None:
        """Execute tasks sequentially."""
        for task in tasks:
            self._execute_task(task)
            if self.config.on_task_complete and task.agent_name in self._results:
                self.config.on_task_complete(self._results[task.agent_name])

    def _execute_parallel(self, tasks: list[AgentTask]) -> None:
        """Execute tasks in parallel."""
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._execute_task, task): task for task in tasks
            }

            for future in as_completed(futures):
                task = futures[future]
                try:
                    future.result(timeout=self.config.timeout)
                    if (
                        self.config.on_task_complete
                        and task.agent_name in self._results
                    ):
                        self.config.on_task_complete(self._results[task.agent_name])
                except Exception as e:
                    # Store failed agent result instead of silently logging
                    logger.error(
                        f"Error in parallel execution for {task.agent_name}: {e}"
                    )
                    self._results[task.agent_name] = AgentResult(
                        agent_name=task.agent_name,
                        task=task.task,
                        result=None,
                        success=False,
                        error=str(e),
                        duration_ms=0.0,
                    )

    def _execute_hierarchical(self, tasks: list[AgentTask]) -> None:
        """Execute with manager delegation pattern."""
        # Find manager agent
        manager = None
        worker_tasks = []

        for task in tasks:
            agent = self.agents.get(task.agent_name)
            if agent and getattr(agent, "role", None) == AgentRole.MANAGER.value:
                manager = agent
            else:
                worker_tasks.append(task)

        if manager:
            # Manager coordinates work
            self._execute_task(
                AgentTask(
                    agent_name=manager.name,
                    task=f"Coordinate: {', '.join([t.task for t in worker_tasks])}",
                    context={"worker_count": len(worker_tasks)},
                )
            )

        # Workers execute in parallel
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._execute_task, task): task for task in worker_tasks
            }

            for future in as_completed(futures):
                task = futures[future]
                try:
                    future.result(timeout=self.config.timeout)
                    if (
                        self.config.on_task_complete
                        and task.agent_name in self._results
                    ):
                        self.config.on_task_complete(self._results[task.agent_name])
                except Exception as e:
                    # Store failed agent result instead of silently logging
                    logger.error(
                        f"Error in hierarchical execution for {task.agent_name}: {e}"
                    )
                    self._results[task.agent_name] = AgentResult(
                        agent_name=task.agent_name,
                        task=task.task,
                        result=None,
                        success=False,
                        error=str(e),
                        duration_ms=0.0,
                    )

    def _execute_task(self, task: AgentTask) -> None:
        """Execute a single task."""
        import time

        agent = self.agents.get(task.agent_name)
        if not agent:
            logger.error(f"Agent not found: {task.agent_name}")
            return

        start_time = time.time()

        try:
            # Prepare context with shared memory
            context = {**task.context, **self.shared_memory.to_dict()}

            # Run agent
            result = agent.run(task.task, context=context)

            # Store result
            duration_ms = (time.time() - start_time) * 1000
            agent_result = AgentResult(
                agent_name=task.agent_name,
                task=task.task,
                result=result,
                success=True,
                duration_ms=duration_ms,
            )
            self._results[task.agent_name] = agent_result

            # Update shared memory with result
            self.shared_memory.set(f"{task.agent_name}_result", result)

            if self.config.verbose:
                logger.info(f"✓ {task.agent_name}: {str(result)[:100]}")

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            agent_result = AgentResult(
                agent_name=task.agent_name,
                task=task.task,
                result=None,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
            self._results[task.agent_name] = agent_result

            if self.config.verbose:
                logger.error(f"✗ {task.agent_name}: {e}")

    def get_results(
        self, agent_name: str | None = None
    ) -> AgentResult | list[AgentResult]:
        """
        Get results from crew execution.

        Args:
            agent_name: Optional specific agent name

        Returns:
            Single result if agent_name provided, otherwise list of all results
        """
        if agent_name:
            return self._results.get(agent_name)
        return list(self._results.values())

    def reset(self) -> None:
        """Reset crew state."""
        self._results.clear()
        self._execution_order.clear()
        self.shared_memory.clear()


# Mock agent for testing/examples
@dataclass
class MockAgent:
    """Simple mock agent for testing."""

    name: str
    role: str = "worker"
    process_fn: Callable[[str, dict], str] | None = None

    def run(self, task: str, context: dict[str, Any] | None = None) -> str:
        """Run the mock agent."""
        if self.process_fn:
            return self.process_fn(task, context or {})
        return f"[{self.name}] Processed: {task}"
