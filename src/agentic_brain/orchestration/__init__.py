"""
Multi-agent orchestration system for agentic-brain.

Simple, powerful orchestration of multiple agents with different execution strategies.
"""

from __future__ import annotations

from .crew import Crew, CrewConfig, ExecutionStrategy, AgentRole
from .workflow import Workflow, WorkflowStep, WorkflowState, WorkflowResult

__all__ = [
    "Crew",
    "CrewConfig",
    "ExecutionStrategy",
    "AgentRole",
    "Workflow",
    "WorkflowStep",
    "WorkflowState",
    "WorkflowResult",
]
