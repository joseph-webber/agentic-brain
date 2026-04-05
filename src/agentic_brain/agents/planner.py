# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
ReAct-style Planning and Action Selection.

Implements Reasoning + Acting pattern for agent decision-making.
Agents use this to plan tasks, break them down, and select actions.

Example:
    >>> from agentic_brain.agents.planner import PlannerAgent, PlanningStrategy
    >>> planner = PlannerAgent(strategy=PlanningStrategy.HIERARCHICAL)
    >>> plan = await planner.create_plan("Write a blog post about AI")
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


class PlanningStrategy(str, Enum):
    """Planning strategies."""

    LINEAR = "linear"
    HIERARCHICAL = "hierarchical"
    REACTIVE = "reactive"
    TREE_SEARCH = "tree_search"


class ActionType(str, Enum):
    """Types of actions."""

    THINK = "think"
    OBSERVE = "observe"
    ACT = "act"
    CALL_TOOL = "call_tool"
    REFLECT = "reflect"
    REPORT = "report"


@dataclass
class Action:
    """Single action to execute."""

    id: str = field(default_factory=lambda: str(uuid4()))
    type: ActionType = ActionType.ACT
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    prerequisites: list[str] = field(default_factory=list)
    estimated_duration_seconds: float = 0.0
    priority: int = 5
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "type": self.type.value,
            "description": self.description,
            "parameters": self.parameters,
            "prerequisites": self.prerequisites,
            "estimated_duration_seconds": self.estimated_duration_seconds,
            "priority": self.priority,
            "status": self.status,
        }


@dataclass
class Plan:
    """Execution plan."""

    id: str = field(default_factory=lambda: str(uuid4()))
    goal: str = ""
    strategy: PlanningStrategy = PlanningStrategy.LINEAR
    actions: list[Action] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    estimated_total_duration: float = 0.0
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_action(self, action: Action) -> None:
        """Add action to plan."""
        self.actions.append(action)
        self.estimated_total_duration += action.estimated_duration_seconds

    def get_next_action(self) -> Action | None:
        """Get next executable action."""
        for action in self.actions:
            if action.status == "pending":
                prereqs_met = all(
                    next(
                        (a for a in self.actions if a.id == prereq_id),
                        None,
                    ).status
                    == "complete"
                    for prereq_id in action.prerequisites
                )
                if prereqs_met:
                    return action
        return None

    def mark_action_complete(self, action_id: str) -> None:
        """Mark action as complete."""
        for action in self.actions:
            if action.id == action_id:
                action.status = "complete"
                break

    def is_complete(self) -> bool:
        """Check if plan is complete."""
        return all(a.status == "complete" for a in self.actions)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "goal": self.goal,
            "strategy": self.strategy.value,
            "actions": [a.to_dict() for a in self.actions],
            "created_at": self.created_at.isoformat(),
            "estimated_total_duration": self.estimated_total_duration,
            "reasoning": self.reasoning,
            "metadata": self.metadata,
        }


class Planner:
    """
    Task planning engine.

    Converts high-level goals into executable action sequences.
    """

    def __init__(self, strategy: PlanningStrategy = PlanningStrategy.LINEAR):
        """
        Initialize planner.

        Args:
            strategy: Planning strategy to use
        """
        self.strategy = strategy
        self._logger = logging.getLogger(__name__)

    async def create_plan(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
        reasoning_prompt: str = "",
    ) -> Plan:
        """
        Create execution plan for goal.

        Args:
            goal: High-level goal
            context: Contextual information
            reasoning_prompt: Optional reasoning prompt

        Returns:
            Plan instance with actions
        """
        plan = Plan(
            goal=goal,
            strategy=self.strategy,
            reasoning=reasoning_prompt,
        )

        if self.strategy == PlanningStrategy.LINEAR:
            plan = await self._plan_linear(plan, context or {})
        elif self.strategy == PlanningStrategy.HIERARCHICAL:
            plan = await self._plan_hierarchical(plan, context or {})
        elif self.strategy == PlanningStrategy.REACTIVE:
            plan = await self._plan_reactive(plan, context or {})
        else:
            plan = await self._plan_linear(plan, context or {})

        return plan

    async def _plan_linear(
        self, plan: Plan, context: dict[str, Any]
    ) -> Plan:
        """Linear planning (sequential steps)."""
        action = Action(
            type=ActionType.THINK,
            description=f"Analyze goal: {plan.goal}",
            estimated_duration_seconds=1.0,
            priority=10,
        )
        plan.add_action(action)

        action = Action(
            type=ActionType.ACT,
            description=f"Execute primary task for: {plan.goal}",
            estimated_duration_seconds=5.0,
            prerequisites=[plan.actions[-1].id],
            priority=5,
        )
        plan.add_action(action)

        action = Action(
            type=ActionType.REFLECT,
            description="Evaluate results and success",
            estimated_duration_seconds=1.0,
            prerequisites=[plan.actions[-1].id],
            priority=5,
        )
        plan.add_action(action)

        return plan

    async def _plan_hierarchical(
        self, plan: Plan, context: dict[str, Any]
    ) -> Plan:
        """Hierarchical planning (with sub-goals)."""
        action = Action(
            type=ActionType.THINK,
            description="Decompose goal into sub-tasks",
            estimated_duration_seconds=2.0,
            priority=10,
        )
        plan.add_action(action)

        action = Action(
            type=ActionType.ACT,
            description="Complete primary sub-goal",
            estimated_duration_seconds=5.0,
            prerequisites=[plan.actions[-1].id],
            priority=7,
        )
        plan.add_action(action)

        action = Action(
            type=ActionType.ACT,
            description="Complete secondary sub-goal",
            estimated_duration_seconds=5.0,
            prerequisites=[plan.actions[-1].id],
            priority=7,
        )
        plan.add_action(action)

        action = Action(
            type=ActionType.REFLECT,
            description="Validate all objectives met",
            estimated_duration_seconds=1.0,
            prerequisites=[plan.actions[-2].id, plan.actions[-1].id],
            priority=5,
        )
        plan.add_action(action)

        return plan

    async def _plan_reactive(
        self, plan: Plan, context: dict[str, Any]
    ) -> Plan:
        """Reactive planning (adapt based on observations)."""
        action = Action(
            type=ActionType.OBSERVE,
            description="Assess current state",
            estimated_duration_seconds=1.0,
            priority=10,
        )
        plan.add_action(action)

        action = Action(
            type=ActionType.THINK,
            description="Decide on immediate action",
            estimated_duration_seconds=1.0,
            prerequisites=[plan.actions[-1].id],
            priority=8,
        )
        plan.add_action(action)

        action = Action(
            type=ActionType.ACT,
            description="Execute immediate action",
            estimated_duration_seconds=3.0,
            prerequisites=[plan.actions[-1].id],
            priority=5,
        )
        plan.add_action(action)

        return plan

    async def refine_plan(
        self, plan: Plan, feedback: str
    ) -> Plan:
        """
        Refine plan based on feedback.

        Args:
            plan: Original plan
            feedback: Feedback or failure reason

        Returns:
            Refined plan
        """
        self._logger.info(f"Refining plan based on: {feedback}")

        new_plan = Plan(
            goal=plan.goal,
            strategy=self.strategy,
            reasoning=f"Refined due to: {feedback}",
            metadata=plan.metadata,
        )

        new_plan.actions = plan.actions.copy()

        alt_action = Action(
            type=ActionType.THINK,
            description=f"Alternative approach: {feedback}",
            estimated_duration_seconds=2.0,
            priority=10,
        )
        new_plan.add_action(alt_action)

        return new_plan


class ReActAgent:
    """
    ReAct (Reasoning + Acting) agent.

    Interleaves reasoning and tool use for improved task completion.
    """

    def __init__(self, planning_strategy: PlanningStrategy = PlanningStrategy.LINEAR):
        """
        Initialize ReAct agent.

        Args:
            planning_strategy: Strategy for plan creation
        """
        self.planner = Planner(strategy=planning_strategy)
        self.current_plan: Plan | None = None
        self._logger = logging.getLogger(__name__)

    async def think_and_act(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> tuple[Plan, list[Any]]:
        """
        Execute ReAct loop (think -> act -> reflect).

        Args:
            task: Task description
            context: Contextual information

        Returns:
            Tuple of (plan, results)
        """
        self.current_plan = await self.planner.create_plan(
            task, context=context or {}
        )
        results = []

        while not self.current_plan.is_complete():
            next_action = self.current_plan.get_next_action()
            if not next_action:
                break

            result = await self._execute_action(next_action)
            results.append(result)
            self.current_plan.mark_action_complete(next_action.id)

        return self.current_plan, results

    async def _execute_action(self, action: Action) -> Any:
        """
        Execute single action.

        Args:
            action: Action to execute

        Returns:
            Action result
        """
        self._logger.debug(f"Executing action: {action.description}")

        if action.type == ActionType.THINK:
            return await self._think_action(action)
        elif action.type == ActionType.ACT:
            return await self._act_action(action)
        elif action.type == ActionType.OBSERVE:
            return await self._observe_action(action)
        elif action.type == ActionType.REFLECT:
            return await self._reflect_action(action)
        else:
            return {"status": "unknown"}

    async def _think_action(self, action: Action) -> dict[str, Any]:
        """Thinking action."""
        return {
            "type": "think",
            "description": action.description,
            "result": "Reasoning completed",
        }

    async def _act_action(self, action: Action) -> dict[str, Any]:
        """Acting action."""
        return {
            "type": "act",
            "description": action.description,
            "result": "Action completed successfully",
        }

    async def _observe_action(self, action: Action) -> dict[str, Any]:
        """Observation action."""
        return {
            "type": "observe",
            "description": action.description,
            "result": "Observation recorded",
        }

    async def _reflect_action(self, action: Action) -> dict[str, Any]:
        """Reflection action."""
        return {
            "type": "reflect",
            "description": action.description,
            "result": "Reflection completed",
        }
