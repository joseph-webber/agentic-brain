# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tool Framework for Agent Actions.

Provides a flexible system for agents to use external tools (calculators, web searches,
code execution, etc.) with proper validation, error handling, and result formatting.

Example:
    >>> from agentic_brain.agents.tools import Tool, ToolRegistry, SearchTool
    >>> registry = ToolRegistry()
    >>> result = await registry.call_tool("search", query="Python async")
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
from uuid import uuid4

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ToolCategory(str, Enum):
    """Tool categories for organization."""

    SEARCH = "search"
    CALCULATION = "calculation"
    CODE = "code"
    WEB = "web"
    FILE = "file"
    DATA = "data"
    MEMORY = "memory"
    CUSTOM = "custom"


@dataclass
class ToolParameter:
    """Parameter definition for a tool."""

    name: str
    type: str = "string"
    description: str = ""
    required: bool = True
    default: Any = None
    choices: list[Any] = field(default_factory=list)

    def validate(self, value: Any) -> tuple[bool, str]:
        """
        Validate a value against this parameter.

        Args:
            value: Value to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if value is None:
            if self.required:
                return False, f"Parameter {self.name} is required"
            return True, ""

        if self.choices and value not in self.choices:
            return False, f"Value must be one of: {self.choices}"

        type_map = {"string": str, "int": int, "float": float, "bool": bool}
        expected_type = type_map.get(self.type)
        if expected_type and not isinstance(value, expected_type):
            try:
                expected_type(value)
            except (ValueError, TypeError):
                return (
                    False,
                    f"Parameter {self.name} must be of type {self.type}",
                )

        return True, ""


@dataclass
class ToolResult:
    """Result of tool execution."""

    tool_name: str
    success: bool
    output: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"ToolResult({status}, {self.tool_name}, {self.execution_time_ms:.0f}ms)"


class Tool(ABC):
    """
    Abstract base class for all tools.

    Tools are actions that agents can execute. Each tool defines its parameters,
    execution logic, and output format.
    """

    def __init__(
        self,
        name: str,
        category: ToolCategory = ToolCategory.CUSTOM,
        description: str = "",
        parameters: list[ToolParameter] | None = None,
    ):
        """
        Initialize tool.

        Args:
            name: Tool name (unique)
            category: Tool category
            description: Tool description
            parameters: List of parameter definitions
        """
        self.name = name
        self.category = category
        self.description = description
        self.parameters = parameters or []
        self._logger = logging.getLogger(f"{__name__}.{name}")

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        Execute the tool.

        Args:
            **kwargs: Tool-specific parameters

        Returns:
            ToolResult with execution outcome
        """
        pass

    def validate_parameters(self, **kwargs: Any) -> tuple[bool, str]:
        """
        Validate input parameters.

        Args:
            **kwargs: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        for param in self.parameters:
            if param.name not in kwargs and param.required:
                return False, f"Missing required parameter: {param.name}"

            if param.name in kwargs:
                is_valid, error = param.validate(kwargs[param.name])
                if not is_valid:
                    return False, error

        return True, ""

    def get_schema(self) -> dict[str, Any]:
        """Get OpenAPI-like schema for this tool."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "description": p.description,
                    "required": p.required,
                    "default": p.default,
                    "choices": p.choices if p.choices else None,
                }
                for p in self.parameters
            ],
        }

    def __repr__(self) -> str:
        return f"Tool({self.name}, category={self.category.value})"


class SearchTool(Tool):
    """Search engine tool."""

    def __init__(self):
        super().__init__(
            name="search",
            category=ToolCategory.SEARCH,
            description="Search the web for information",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Search query",
                    required=True,
                ),
                ToolParameter(
                    name="max_results",
                    type="int",
                    description="Maximum results to return",
                    required=False,
                    default=5,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute search (simulated)."""
        import time

        start_time = time.perf_counter()
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)

        is_valid, error = self.validate_parameters(**kwargs)
        if not is_valid:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=error,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        try:
            results = [
                {
                    "title": f"Result {i+1} for {query}",
                    "url": f"https://example.com/result{i+1}",
                    "snippet": f"Snippet about {query} - result {i+1}",
                }
                for i in range(min(max_results, 5))
            ]

            return ToolResult(
                tool_name=self.name,
                success=True,
                output=results,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            self._logger.exception(f"Search failed: {query}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )


class CalculatorTool(Tool):
    """Calculator tool for math operations."""

    def __init__(self):
        super().__init__(
            name="calculate",
            category=ToolCategory.CALCULATION,
            description="Perform mathematical calculations",
            parameters=[
                ToolParameter(
                    name="expression",
                    type="string",
                    description="Math expression (e.g., '2 + 2 * 3')",
                    required=True,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute calculation."""
        import time

        start_time = time.perf_counter()
        expression = kwargs.get("expression", "")

        is_valid, error = self.validate_parameters(**kwargs)
        if not is_valid:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=error,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return ToolResult(
                tool_name=self.name,
                success=True,
                output={"expression": expression, "result": result},
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            self._logger.exception(f"Calculation failed: {expression}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Calculation error: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )


class CodeExecutionTool(Tool):
    """Execute Python code safely."""

    def __init__(self, max_timeout: float = 5.0):
        super().__init__(
            name="execute_code",
            category=ToolCategory.CODE,
            description="Execute Python code (with safety restrictions)",
            parameters=[
                ToolParameter(
                    name="code",
                    type="string",
                    description="Python code to execute",
                    required=True,
                ),
                ToolParameter(
                    name="timeout_seconds",
                    type="float",
                    description="Execution timeout",
                    required=False,
                    default=5.0,
                ),
            ],
        )
        self.max_timeout = max_timeout

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute code safely."""
        import time

        start_time = time.perf_counter()
        code = kwargs.get("code", "")
        timeout = min(kwargs.get("timeout_seconds", 5.0), self.max_timeout)

        is_valid, error = self.validate_parameters(**kwargs)
        if not is_valid:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=error,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        try:
            namespace = {"__builtins__": {}}
            exec(code, namespace)
            output = namespace.get("result", "Code executed successfully")

            return ToolResult(
                tool_name=self.name,
                success=True,
                output=output,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            self._logger.exception(f"Code execution failed")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=f"Execution error: {str(e)}",
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )


class WebLookupTool(Tool):
    """Web lookup tool for fetching URLs."""

    def __init__(self):
        super().__init__(
            name="web_lookup",
            category=ToolCategory.WEB,
            description="Fetch and summarize web page content",
            parameters=[
                ToolParameter(
                    name="url",
                    type="string",
                    description="URL to fetch",
                    required=True,
                ),
                ToolParameter(
                    name="max_length",
                    type="int",
                    description="Maximum content length",
                    required=False,
                    default=5000,
                ),
            ],
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Fetch web content (simulated)."""
        import time

        start_time = time.perf_counter()
        url = kwargs.get("url", "")
        max_length = kwargs.get("max_length", 5000)

        is_valid, error = self.validate_parameters(**kwargs)
        if not is_valid:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=error,
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )

        try:
            content = f"Simulated content from {url} (truncated to {max_length} chars)"
            return ToolResult(
                tool_name=self.name,
                success=True,
                output={"url": url, "content": content[:max_length]},
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as e:
            self._logger.exception(f"Web lookup failed: {url}")
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(e),
                execution_time_ms=(time.perf_counter() - start_time) * 1000,
            )


class ToolRegistry:
    """
    Registry for managing tools.

    Provides centralized tool management, lookup, and execution.
    """

    def __init__(self):
        """Initialize tool registry."""
        self._tools: dict[str, Tool] = {}
        self._categories: dict[ToolCategory, list[str]] = {}
        self._logger = logging.getLogger(__name__)

    def register(self, tool: Tool) -> None:
        """
        Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool name already registered
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} already registered")

        self._tools[tool.name] = tool

        if tool.category not in self._categories:
            self._categories[tool.category] = []
        self._categories[tool.category].append(tool.name)

        self._logger.debug(f"Registered tool: {tool.name}")

    def unregister(self, tool_name: str) -> None:
        """
        Unregister a tool.

        Args:
            tool_name: Name of tool to unregister
        """
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name!r} not found")

        tool = self._tools.pop(tool_name)
        self._categories[tool.category].remove(tool_name)

    def get_tool(self, tool_name: str) -> Tool | None:
        """
        Get a tool by name.

        Args:
            tool_name: Name of tool

        Returns:
            Tool instance or None
        """
        return self._tools.get(tool_name)

    def list_tools(self, category: ToolCategory | None = None) -> list[dict[str, Any]]:
        """
        List available tools.

        Args:
            category: Filter by category (optional)

        Returns:
            List of tool schemas
        """
        if category:
            tool_names = self._categories.get(category, [])
        else:
            tool_names = self._tools.keys()

        return [self._tools[name].get_schema() for name in tool_names]

    async def call_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """
        Call a tool.

        Args:
            tool_name: Name of tool to call
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool {tool_name!r} not found",
            )

        return await tool.execute(**kwargs)

    def __repr__(self) -> str:
        return f"ToolRegistry({len(self._tools)} tools)"


def create_default_registry() -> ToolRegistry:
    """
    Create default tool registry with built-in tools.

    Returns:
        ToolRegistry with default tools registered
    """
    registry = ToolRegistry()
    registry.register(SearchTool())
    registry.register(CalculatorTool())
    registry.register(CodeExecutionTool())
    registry.register(WebLookupTool())
    return registry
