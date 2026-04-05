# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Base Agent Abstract Base Class.

Defines the core interface for all agents in the agentic-brain framework.
All agents inherit from this base class and must implement the required methods.

Example:
    >>> from agentic_brain.agents import Agent, AgentConfig
    >>> config = AgentConfig(name="my_agent", max_iterations=10)
    >>> agent = ConcreteAgent(config)
    >>> result = agent.run("Solve this problem: 2 + 2")
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional, TypeVar, Generic
from uuid import uuid4

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AgentState(str, Enum):
    """Agent execution states."""

    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    THINKING = "thinking"
    OBSERVING = "observing"
    ERROR = "error"
    COMPLETE = "complete"


class AgentRole(str, Enum):
    """Agent roles in the system."""

    ORCHESTRATOR = "orchestrator"
    EXECUTOR = "executor"
    PLANNER = "planner"
    REASONER = "reasoner"
    VALIDATOR = "validator"
    TOOL_USER = "tool_user"
    RAG_AGENT = "rag_agent"
    GENERALIST = "generalist"


@dataclass
class AgentConfig:
    """Base configuration for all agents."""

    name: str
    role: AgentRole = AgentRole.GENERALIST
    description: str = ""
    max_iterations: int = 10
    timeout_seconds: float = 300.0
    system_prompt: str | None = None
    memory_enabled: bool = True
    logging_enabled: bool = True
    telemetry_enabled: bool = False
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentContext:
    """Execution context for agent operations."""

    agent_id: str = field(default_factory=lambda: str(uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    state: AgentState = AgentState.IDLE
    iteration_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult(Generic[T]):
    """Result of agent execution."""

    success: bool
    output: T | None = None
    error: str | None = None
    reasoning: str = ""
    context: AgentContext | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"AgentResult({status}, time={self.execution_time_ms:.0f}ms)"


class Agent(ABC):
    """
    Abstract base class for all agents.

    All agents in the agentic-brain system must inherit from this class and implement
    the required abstract methods. This ensures a consistent interface and enables
    proper orchestration across agents.

    Attributes:
        config: Agent configuration
        context: Current execution context
    """

    def __init__(self, config: AgentConfig):
        """
        Initialize agent with configuration.

        Args:
            config: Agent configuration object
        """
        self.config = config
        self.context = AgentContext()
        self._logger = logging.getLogger(f"{__name__}.{config.name}")

    @property
    def agent_id(self) -> str:
        """Get unique agent ID."""
        return self.context.agent_id

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self.context.session_id

    @property
    def state(self) -> AgentState:
        """Get current execution state."""
        return self.context.state

    def set_state(self, state: AgentState) -> None:
        """
        Update agent state.

        Args:
            state: New agent state
        """
        self.context.state = state
        if self.config.logging_enabled:
            self._logger.info(f"State transition: {state.value}")

    @abstractmethod
    async def execute(self, task: str, **kwargs: Any) -> AgentResult:
        """
        Execute a task asynchronously.

        This is the main entry point for agent execution. Subclasses must implement
        this method to define their specific behavior.

        Args:
            task: Task description or query
            **kwargs: Additional task-specific arguments

        Returns:
            AgentResult with execution outcome and metadata
        """
        pass

    @abstractmethod
    async def think(self, task: str, **kwargs: Any) -> str:
        """
        Perform reasoning/planning.

        Args:
            task: Task description
            **kwargs: Additional arguments

        Returns:
            Reasoning string or plan
        """
        pass

    @abstractmethod
    async def observe(self, **kwargs: Any) -> dict[str, Any]:
        """
        Observe the environment or context.

        Used to gather information needed for decision making.

        Args:
            **kwargs: Observation parameters

        Returns:
            Dictionary with observation results
        """
        pass

    async def run(self, task: str, **kwargs: Any) -> AgentResult:
        """
        Synchronous wrapper for async execute.

        Handles setup, error handling, and timing.

        Args:
            task: Task to execute
            **kwargs: Additional arguments

        Returns:
            AgentResult with execution outcome
        """
        import time

        start_time = time.perf_counter()
        self.context.iteration_count = 0

        try:
            self.set_state(AgentState.PLANNING)
            result = await self.execute(task, **kwargs)
            self.set_state(AgentState.COMPLETE)

            result.context = self.context
            result.execution_time_ms = (time.perf_counter() - start_time) * 1000

            return result

        except asyncio.TimeoutError:
            self.set_state(AgentState.ERROR)
            return AgentResult(
                success=False,
                error=f"Task timeout after {self.config.timeout_seconds}s",
                context=self.context,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            self.set_state(AgentState.ERROR)
            self._logger.exception(f"Error executing task: {task}")
            return AgentResult(
                success=False,
                error=f"Execution error: {str(e)}",
                context=self.context,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

    async def reset(self) -> None:
        """
        Reset agent state.

        Called between task executions or to clear state.
        """
        self.context = AgentContext()
        self.set_state(AgentState.IDLE)
        await self._cleanup()

    async def _cleanup(self) -> None:
        """
        Cleanup resources.

        Override in subclasses if needed.
        """
        pass

    def get_metadata(self) -> dict[str, Any]:
        """Get agent metadata."""
        return {
            "agent_id": self.agent_id,
            "name": self.config.name,
            "role": self.config.role.value,
            "state": self.context.state.value,
            "iterations": self.context.iteration_count,
        }

    def __repr__(self) -> str:
        return f"Agent(name={self.config.name!r}, role={self.config.role.value}, state={self.state.value})"


class MultiAgentOrchestrator(ABC):
    """
    Abstract base class for orchestrating multiple agents.

    Subclasses implement specific coordination patterns (sequential, parallel, hierarchical).
    """

    def __init__(self, agents: list[Agent]):
        """
        Initialize orchestrator with agents.

        Args:
            agents: List of agents to orchestrate
        """
        self.agents = agents
        self._logger = logging.getLogger(__name__)

    @abstractmethod
    async def orchestrate(self, task: str, **kwargs: Any) -> list[AgentResult]:
        """
        Orchestrate agents to complete task.

        Args:
            task: Task description
            **kwargs: Additional arguments

        Returns:
            List of agent execution results
        """
        pass

    async def parallel_execute(
        self, task: str, **kwargs: Any
    ) -> list[AgentResult]:
        """
        Execute all agents in parallel.

        Args:
            task: Task description
            **kwargs: Additional arguments

        Returns:
            List of results from all agents
        """
        results = await asyncio.gather(
            *[agent.execute(task, **kwargs) for agent in self.agents],
            return_exceptions=True,
        )

        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(
                    AgentResult(success=False, error=str(result))
                )
            else:
                processed_results.append(result)

        return processed_results
