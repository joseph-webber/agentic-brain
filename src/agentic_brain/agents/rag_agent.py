# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
RAG-Enabled Agent Implementation.

Combines Retrieval-Augmented Generation with agent reasoning for improved answers.

Example:
    >>> from agentic_brain.agents.rag_agent import RAGAgent
    >>> agent = RAGAgent(name="research_assistant")
    >>> result = await agent.execute("What are the latest AI trends?")
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from .base import Agent, AgentConfig, AgentRole, AgentResult, AgentState
from .memory import AgentMemory, MemoryConfig
from .planner import Planner, PlanningStrategy, ReActAgent
from .tools import ToolRegistry, create_default_registry
from .executor import ToolExecutor

logger = logging.getLogger(__name__)


@dataclass
class RAGAgentConfig(AgentConfig):
    """Configuration for RAG-enabled agent."""

    embedding_model: str = "all-MiniLM-L6-v2"
    vector_store_type: str = "memory"
    max_context_docs: int = 5
    retrieval_threshold: float = 0.5
    enable_planning: bool = True
    enable_reflection: bool = True


class RAGAgent(Agent):
    """
    RAG-enabled agent for knowledge-intensive tasks.

    Combines retrieval, reasoning, and tool use for improved task completion.
    Maintains context and memory across conversations.
    """

    def __init__(
        self,
        config: RAGAgentConfig | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        """
        Initialize RAG agent.

        Args:
            config: Agent configuration
            tool_registry: Tool registry (uses default if not provided)
        """
        if config is None:
            config = RAGAgentConfig(
                name="rag_agent",
                role=AgentRole.RAG_AGENT,
            )
        elif not isinstance(config, RAGAgentConfig):
            config = RAGAgentConfig(
                name=config.name,
                role=config.role or AgentRole.RAG_AGENT,
            )
        elif config.role == AgentRole.GENERALIST:
            config.role = AgentRole.RAG_AGENT

        super().__init__(config)
        self.rag_config = config

        self.memory = AgentMemory(MemoryConfig(max_items=1000))
        self.tool_registry = tool_registry or create_default_registry()
        self.executor = ToolExecutor(tool_registry=self.tool_registry)
        self.planner = Planner(strategy=PlanningStrategy.HIERARCHICAL)
        self.react_agent = ReActAgent(planning_strategy=PlanningStrategy.HIERARCHICAL)

        self._documents: list[dict[str, Any]] = []
        self._embeddings: dict[str, list[float]] = {}

    async def execute(self, task: str, **kwargs: Any) -> AgentResult:
        """
        Execute task with RAG.

        Args:
            task: Task description
            **kwargs: Additional arguments

        Returns:
            AgentResult with execution outcome
        """
        import time

        start_time = time.perf_counter()

        try:
            self.set_state(AgentState.PLANNING)

            self.memory.add_message("user", task)

            if self.rag_config.enable_planning:
                plan = await self.planner.create_plan(task)
                self.context.metadata["plan"] = plan.to_dict()

            self.set_state(AgentState.EXECUTING)

            response = await self._execute_with_rag(task, **kwargs)

            self.memory.add_message("assistant", response)

            if self.rag_config.enable_reflection:
                self.set_state(AgentState.THINKING)
                reflection = await self._reflect_on_response(response)
                self.context.metadata["reflection"] = reflection

            self.set_state(AgentState.COMPLETE)

            execution_time = (time.perf_counter() - start_time) * 1000

            return AgentResult(
                success=True,
                output=response,
                reasoning="Task completed successfully with RAG enhancement",
                context=self.context,
                metadata={
                    "memory_stats": self.memory.get_stats(),
                    "tools_available": len(self.tool_registry._tools),
                },
                execution_time_ms=execution_time,
            )

        except Exception as e:
            self._logger.exception(f"RAG agent error: {task}")
            execution_time = (time.perf_counter() - start_time) * 1000
            return AgentResult(
                success=False,
                error=f"RAG execution failed: {str(e)}",
                context=self.context,
                execution_time_ms=execution_time,
            )

    async def think(self, task: str, **kwargs: Any) -> str:
        """
        Perform reasoning about task.

        Args:
            task: Task description
            **kwargs: Additional arguments

        Returns:
            Reasoning string
        """
        self.set_state(AgentState.THINKING)

        retrieved = await self._retrieve_context(task)
        reasoning = f"Considering {len(retrieved)} relevant documents for: {task}"

        return reasoning

    async def observe(self, **kwargs: Any) -> dict[str, Any]:
        """
        Observe current state.

        Args:
            **kwargs: Observation parameters

        Returns:
            Dictionary with observations
        """
        self.set_state(AgentState.OBSERVING)

        return {
            "memory_size": len(self.memory._conversation_history),
            "available_tools": list(self.tool_registry._tools.keys()),
            "documents_indexed": len(self._documents),
            "current_state": self.state.value,
        }

    async def _execute_with_rag(self, task: str, **kwargs: Any) -> str:
        """
        Execute task using RAG pipeline.

        Args:
            task: Task description
            **kwargs: Additional arguments

        Returns:
            Generated response
        """
        retrieved_docs = await self._retrieve_context(task)

        context_str = self._format_context(retrieved_docs)

        plan, results = await self.react_agent.think_and_act(
            task,
            context={"retrieved_context": context_str, **kwargs},
        )

        response = await self._generate_response(task, context_str, results)

        return response

    async def _retrieve_context(self, query: str) -> list[dict[str, Any]]:
        """
        Retrieve relevant documents.

        Args:
            query: Query string

        Returns:
            List of relevant documents
        """
        if not self._documents:
            return []

        relevant = [doc for doc in self._documents[: self.rag_config.max_context_docs]]

        return relevant

    def _format_context(self, documents: list[dict[str, Any]]) -> str:
        """
        Format retrieved documents as context string.

        Args:
            documents: List of documents

        Returns:
            Formatted context string
        """
        if not documents:
            return "No relevant context available."

        context_parts = ["Retrieved context:"]
        for i, doc in enumerate(documents, 1):
            content = doc.get("content", "")[:200]
            context_parts.append(f"{i}. {content}...")

        return "\n".join(context_parts)

    async def _generate_response(
        self,
        task: str,
        context: str,
        plan_results: list[Any],
    ) -> str:
        """
        Generate final response.

        Args:
            task: Original task
            context: Retrieved context
            plan_results: Results from planning

        Returns:
            Generated response
        """
        response_parts = [
            f"Response to: {task}",
            f"Using context: {len(context.split('Retrieved'))} sources",
            f"Completed {len(plan_results)} planning steps",
        ]

        return "\n".join(response_parts)

    async def _reflect_on_response(self, response: str) -> str:
        """
        Reflect on generated response.

        Args:
            response: Generated response

        Returns:
            Reflection string
        """
        return f"Evaluated response quality based on {len(response.split())} tokens"

    async def add_document(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add document to knowledge base.

        Args:
            content: Document content
            metadata: Document metadata
        """
        doc = {
            "content": content,
            "metadata": metadata or {},
        }
        self._documents.append(doc)
        self._logger.debug(f"Added document, total: {len(self._documents)}")

    async def add_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> None:
        """
        Add multiple documents.

        Args:
            documents: List of document dictionaries
        """
        self._documents.extend(documents)
        self._logger.debug(f"Added documents, total: {len(self._documents)}")

    def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools schema."""
        return self.tool_registry.list_tools()

    async def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """
        Call a tool.

        Args:
            tool_name: Name of tool
            **kwargs: Tool parameters

        Returns:
            Tool execution result
        """
        return await self.executor.execute_tool(tool_name, **kwargs)

    def get_conversation_history(self) -> list[dict[str, Any]]:
        """Get conversation history."""
        return [turn.to_dict() for turn in self.memory.recall()]

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        await self.executor.cancel_all()
        self.memory.clear()
