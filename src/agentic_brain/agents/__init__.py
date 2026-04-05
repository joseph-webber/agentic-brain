# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Agentic RAG Framework.

Complete agent framework with RAG support, planning, tool use, and memory.

Available components:
- Agent: Base agent class
- RAGAgent: RAG-enabled agent implementation
- Tool: Base tool class with built-in search, calculator, code execution, web lookup
- ToolRegistry: Tool management and execution
- AgentMemory: Conversation history and memory persistence
- Planner: ReAct-style planning and decomposition
- ToolExecutor: Safe tool execution with timeouts and retries

Example:
    >>> from agentic_brain.agents import RAGAgent, RAGAgentConfig
    >>> config = RAGAgentConfig(name="my_agent", max_iterations=10)
    >>> agent = RAGAgent(config)
    >>> result = await agent.execute("Answer my question")
"""

from __future__ import annotations

from .base import (
    Agent,
    AgentConfig,
    AgentContext,
    AgentResult,
    AgentRole,
    AgentState,
    MultiAgentOrchestrator,
)
from .executor import (
    ExecutionContext,
    ExecutionError,
    ExecutionTimeout,
    ToolExecutor,
)
from .memory import (
    AgentMemory,
    ConversationTurn,
    MemoryConfig,
    MemoryItem,
    MemoryType,
)
from .planner import (
    Action,
    ActionType,
    Plan,
    Planner,
    PlanningStrategy,
    ReActAgent,
)
from .rag_agent import (
    RAGAgent,
    RAGAgentConfig,
)
from .tools import (
    CalculatorTool,
    CodeExecutionTool,
    SearchTool,
    Tool,
    ToolCategory,
    ToolParameter,
    ToolRegistry,
    ToolResult,
    WebLookupTool,
    create_default_registry,
)

__all__ = [
    # Base agent framework
    "Agent",
    "AgentConfig",
    "AgentContext",
    "AgentResult",
    "AgentRole",
    "AgentState",
    "MultiAgentOrchestrator",
    # Tools
    "Tool",
    "ToolCategory",
    "ToolParameter",
    "ToolRegistry",
    "ToolResult",
    "SearchTool",
    "CalculatorTool",
    "CodeExecutionTool",
    "WebLookupTool",
    "create_default_registry",
    # Memory
    "AgentMemory",
    "ConversationTurn",
    "MemoryConfig",
    "MemoryItem",
    "MemoryType",
    # Planning
    "Action",
    "ActionType",
    "Plan",
    "Planner",
    "PlanningStrategy",
    "ReActAgent",
    # Execution
    "ExecutionContext",
    "ExecutionError",
    "ExecutionTimeout",
    "ToolExecutor",
    # RAG agent
    "RAGAgent",
    "RAGAgentConfig",
]
