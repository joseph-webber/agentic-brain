# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Tool Executor for Agent Actions.

Handles safe execution of tools with error handling, timeouts, and result validation.

Example:
    >>> from agentic_brain.agents.executor import ToolExecutor, ExecutionContext
    >>> executor = ToolExecutor()
    >>> result = await executor.execute_tool("search", query="Python async")
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from uuid import uuid4

from .tools import Tool, ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ExecutionContext:
    """Execution context for tool execution."""

    execution_id: str = field(default_factory=lambda: str(uuid4()))
    tool_name: str = ""
    started_at: float = field(default_factory=time.perf_counter)
    max_retries: int = 3
    timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)


class ExecutionError(Exception):
    """Tool execution error."""

    pass


class ExecutionTimeout(ExecutionError):
    """Tool execution timeout."""

    pass


class ToolExecutor:
    """
    Executes tools with proper error handling and constraints.

    Handles timeouts, retries, and result validation.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        max_concurrent: int = 10,
    ):
        """
        Initialize executor.

        Args:
            tool_registry: Registry of available tools
            max_concurrent: Maximum concurrent executions
        """
        self.tool_registry = tool_registry
        self.max_concurrent = max_concurrent
        self._active_executions: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._logger = logging.getLogger(__name__)

    async def execute_tool(
        self,
        tool_name: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 1,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute a tool with error handling.

        Args:
            tool_name: Name of tool to execute
            timeout_seconds: Execution timeout
            max_retries: Number of retries on failure
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome
        """
        if not self.tool_registry:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error="No tool registry configured",
            )

        tool = self.tool_registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool {tool_name!r} not found",
            )

        context = ExecutionContext(
            tool_name=tool_name,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
        )

        for attempt in range(max_retries):
            try:
                result = await self._execute_with_timeout(tool, context, **kwargs)

                if result.success:
                    self._logger.debug(
                        f"Tool {tool_name} executed successfully in "
                        f"{result.execution_time_ms:.0f}ms"
                    )
                    return result

            except ExecutionTimeout:
                self._logger.warning(
                    f"Tool {tool_name} timed out (attempt {attempt + 1}/{max_retries})"
                )
                if attempt == max_retries - 1:
                    return ToolResult(
                        tool_name=tool_name,
                        success=False,
                        error=f"Execution timeout after {timeout_seconds}s",
                    )
            except Exception as e:
                self._logger.warning(
                    f"Tool {tool_name} failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                if attempt == max_retries - 1:
                    return ToolResult(
                        tool_name=tool_name,
                        success=False,
                        error=f"Execution failed: {str(e)}",
                    )

        return ToolResult(
            tool_name=tool_name,
            success=False,
            error="All retry attempts failed",
        )

    async def _execute_with_timeout(
        self,
        tool: Tool,
        context: ExecutionContext,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute tool with timeout constraint.

        Args:
            tool: Tool to execute
            context: Execution context
            **kwargs: Tool parameters

        Returns:
            ToolResult
        """
        async with self._semaphore:
            try:
                result = await asyncio.wait_for(
                    tool.execute(**kwargs),
                    timeout=context.timeout_seconds,
                )
                return result
            except TimeoutError as e:
                raise ExecutionTimeout(
                    f"Tool execution exceeded {context.timeout_seconds}s"
                ) from e

    async def execute_batch(
        self,
        operations: list[tuple[str, dict[str, Any]]],
        timeout_seconds: float = 30.0,
        stop_on_error: bool = False,
    ) -> list[ToolResult]:
        """
        Execute multiple tools in parallel.

        Args:
            operations: List of (tool_name, kwargs) tuples
            timeout_seconds: Timeout per tool
            stop_on_error: Stop execution on first error

        Returns:
            List of ToolResult objects
        """
        tasks = []
        for tool_name, kwargs in operations:
            task = asyncio.create_task(
                self.execute_tool(tool_name, timeout_seconds=timeout_seconds, **kwargs)
            )
            tasks.append(task)

        results = []
        for task in asyncio.as_completed(tasks):
            try:
                result = await task
                results.append(result)

                if stop_on_error and not result.success:
                    for t in tasks:
                        if not t.done():
                            t.cancel()
                    break

            except asyncio.CancelledError:
                results.append(
                    ToolResult(
                        tool_name="unknown",
                        success=False,
                        error="Execution cancelled",
                    )
                )

        return results

    async def execute_with_fallback(
        self,
        primary_tool: str,
        fallback_tool: str,
        timeout_seconds: float = 30.0,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute tool with fallback.

        Args:
            primary_tool: Primary tool name
            fallback_tool: Fallback tool name
            timeout_seconds: Timeout per execution
            **kwargs: Tool parameters

        Returns:
            ToolResult from primary or fallback
        """
        result = await self.execute_tool(
            primary_tool,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

        if not result.success:
            self._logger.info(f"Primary tool failed, trying fallback: {fallback_tool}")
            result = await self.execute_tool(
                fallback_tool,
                timeout_seconds=timeout_seconds,
                **kwargs,
            )

        return result

    async def execute_with_validation(
        self,
        tool_name: str,
        timeout_seconds: float = 30.0,
        validator: Callable[[ToolResult], bool] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """
        Execute tool with result validation.

        Args:
            tool_name: Tool name
            timeout_seconds: Timeout
            validator: Validation function
            **kwargs: Tool parameters

        Returns:
            ToolResult
        """
        result = await self.execute_tool(
            tool_name,
            timeout_seconds=timeout_seconds,
            **kwargs,
        )

        if result.success and validator:
            if not validator(result):
                result.success = False
                result.error = "Result validation failed"
                self._logger.warning(f"Tool result validation failed: {tool_name}")

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics."""
        return {
            "active_executions": len(self._active_executions),
            "max_concurrent": self.max_concurrent,
            "available_tools": (
                len(self.tool_registry._tools) if self.tool_registry else 0
            ),
        }

    async def cancel_all(self) -> None:
        """Cancel all active executions."""
        for task in self._active_executions.values():
            if not task.done():
                task.cancel()
        self._active_executions.clear()

    def __repr__(self) -> str:
        return f"ToolExecutor(max_concurrent={self.max_concurrent})"
