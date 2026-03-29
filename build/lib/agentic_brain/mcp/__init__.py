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
MCP (Model Context Protocol) server for agentic-brain.

Provides tools that Claude and other MCP-compatible clients can use.
Based on Anthropic's MCP specification.

Quick Start:
    # Run as module
    python -m agentic_brain.mcp

    # Or in code
    from agentic_brain.mcp import AgenticMCPServer
    server = AgenticMCPServer()
    server.run()

Custom Server:
    >>> from agentic_brain.mcp import MCPServer
    >>>
    >>> server = MCPServer("my-agent")
    >>>
    >>> @server.tool
    ... def search_memory(query: str) -> str:
    ...     '''Search agent memory.'''
    ...     return "Found: ..."
    >>>
    >>> server.run()

With Neo4j Memory:
    >>> from agentic_brain.mcp import create_memory_server
    >>> from agentic_brain import Neo4jMemory
    >>>
    >>> memory = Neo4jMemory(uri="bolt://localhost:7687", password="secret")
    >>> server = create_memory_server(memory)
    >>> server.run()

Production Server:
    >>> from agentic_brain.mcp import AgenticMCPServer, ServerConfig
    >>>
    >>> config = ServerConfig(
    ...     neo4j_uri="bolt://myhost:7687",
    ...     neo4j_password="secret",
    ...     llm_model="llama3.2:3b"
    ... )
    >>> server = AgenticMCPServer(config)
    >>> server.run()
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolParameter:
    """Tool parameter definition."""

    name: str
    type: str  # string, integer, boolean, array, object
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolDefinition:
    """
    MCP tool definition.

    Compatible with Claude's tool use format.
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    handler: Callable | None = None

    def to_mcp_schema(self) -> dict:
        """Convert to MCP tool schema."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


class MCPServer:
    """
    MCP server for exposing agent capabilities to Claude.

    Implements the Model Context Protocol for tool integration.

    Example:
        >>> server = MCPServer("memory-agent")
        >>>
        >>> @server.tool
        ... def store(content: str, scope: str = "private") -> str:
        ...     '''Store content in memory.'''
        ...     return f"Stored in {scope}"
        >>>
        >>> @server.tool
        ... def search(query: str) -> str:
        ...     '''Search memory.'''
        ...     return f"Found results for: {query}"
        >>>
        >>> # Run as stdio server
        >>> server.run()
    """

    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = "",
    ):
        """
        Initialize MCP server.

        Args:
            name: Server name
            version: Server version
            description: Server description
        """
        self.name = name
        self.version = version
        self.description = description
        self._tools: dict[str, ToolDefinition] = {}
        self._resources: dict[str, Any] = {}  # uri -> resource info
        self._prompts: dict[str, Any] = {}  # name -> prompt info
        self._resource_handlers: dict[str, Callable] = {}  # uri -> handler
        self._prompt_handlers: dict[str, Callable] = {}  # name -> handler

    def tool(self, func: Callable) -> Callable:
        """
        Decorator to register a function as MCP tool.

        Args:
            func: Function to register

        Returns:
            Wrapped function

        Example:
            >>> @server.tool
            ... def my_tool(arg: str) -> str:
            ...     '''Tool description.'''
            ...     return "result"
        """
        # Extract parameter info from type hints
        import inspect

        sig = inspect.signature(func)
        hints = func.__annotations__

        parameters = []
        for param_name, param in sig.parameters.items():
            if param_name == "return":
                continue

            param_type = hints.get(param_name, str)
            type_map = {
                str: "string",
                int: "integer",
                float: "number",
                bool: "boolean",
                list: "array",
                dict: "object",
            }

            parameters.append(
                ToolParameter(
                    name=param_name,
                    type=type_map.get(param_type, "string"),
                    description=f"Parameter: {param_name}",
                    required=param.default == inspect.Parameter.empty,
                    default=(
                        None
                        if param.default == inspect.Parameter.empty
                        else param.default
                    ),
                )
            )

        tool_def = ToolDefinition(
            name=func.__name__,
            description=func.__doc__ or f"Tool: {func.__name__}",
            parameters=parameters,
            handler=func,
        )

        self._tools[func.__name__] = tool_def
        logger.info(f"Registered MCP tool: {func.__name__}")

        return func

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: list[ToolParameter] | None = None,
    ) -> None:
        """
        Register a tool manually.

        Args:
            name: Tool name
            description: Tool description
            handler: Function to call
            parameters: Parameter definitions
        """
        self._tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or [],
            handler=handler,
        )

    def list_tools(self) -> list[dict]:
        """List all tools in MCP schema format."""
        return [tool.to_mcp_schema() for tool in self._tools.values()]

    def register_resource(
        self,
        uri: str,
        name: str,
        description: str = "",
        mime_type: str = "text/plain",
        handler: Callable | None = None,
    ) -> None:
        """
        Register a resource.

        Args:
            uri: Resource URI
            name: Resource name
            description: Resource description
            mime_type: Content MIME type
            handler: Function to read resource content
        """
        self._resources[uri] = {
            "uri": uri,
            "name": name,
            "description": description,
            "mimeType": mime_type,
        }
        if handler:
            self._resource_handlers[uri] = handler

    def list_resources(self) -> list[dict]:
        """List all resources in MCP schema format."""
        return list(self._resources.values())

    def read_resource(self, uri: str) -> dict:
        """
        Read a resource.

        Args:
            uri: Resource URI

        Returns:
            Resource content
        """
        if uri not in self._resources:
            raise ValueError(f"Unknown resource: {uri}")

        handler = self._resource_handlers.get(uri)
        content = handler() if handler else ""

        return {
            "uri": uri,
            "mimeType": self._resources[uri].get("mimeType", "text/plain"),
            "text": content if isinstance(content, str) else json.dumps(content),
        }

    def register_prompt(
        self,
        name: str,
        description: str = "",
        arguments: list[dict] | None = None,
        handler: Callable | None = None,
    ) -> None:
        """
        Register a prompt.

        Args:
            name: Prompt name
            description: Prompt description
            arguments: List of argument definitions
            handler: Function to generate prompt messages
        """
        self._prompts[name] = {
            "name": name,
            "description": description,
            "arguments": arguments or [],
        }
        if handler:
            self._prompt_handlers[name] = handler

    def list_prompts(self) -> list[dict]:
        """List all prompts in MCP schema format."""
        return list(self._prompts.values())

    def get_prompt(self, name: str, arguments: dict) -> list[dict]:
        """
        Get prompt messages.

        Args:
            name: Prompt name
            arguments: Prompt arguments

        Returns:
            List of prompt messages
        """
        if name not in self._prompts:
            raise ValueError(f"Unknown prompt: {name}")

        handler = self._prompt_handlers.get(name)
        if handler:
            messages = handler(**arguments)
        else:
            messages = [{"role": "user", "content": {"type": "text", "text": ""}}]

        return messages

    def call_tool(self, name: str, arguments: dict) -> Any:
        """
        Call a registered tool.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result
        """
        if name not in self._tools:
            raise ValueError(f"Unknown tool: {name}")

        tool = self._tools[name]
        if not tool.handler:
            raise ValueError(f"Tool {name} has no handler")

        return tool.handler(**arguments)

    def handle_request(self, request: dict) -> dict:
        """
        Handle MCP request.

        Args:
            request: MCP request object

        Returns:
            MCP response object
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        try:
            if method == "initialize":
                return self._handle_initialize(req_id, params)
            elif method == "tools/list":
                return self._handle_list_tools(req_id)
            elif method == "tools/call":
                return self._handle_call_tool(req_id, params)
            elif method == "resources/list":
                return self._handle_list_resources(req_id)
            elif method == "resources/read":
                return self._handle_read_resource(req_id, params)
            elif method == "prompts/list":
                return self._handle_list_prompts(req_id)
            elif method == "prompts/get":
                return self._handle_get_prompt(req_id, params)
            else:
                return self._error_response(req_id, -32601, f"Unknown method: {method}")
        except Exception as e:
            logger.error(f"MCP error: {e}")
            return self._error_response(req_id, -32603, str(e))

    def _handle_initialize(self, req_id: Any, params: dict) -> dict:
        """Handle initialize request."""
        capabilities: dict[str, Any] = {}

        if self._tools:
            capabilities["tools"] = {}
        if self._resources:
            capabilities["resources"] = {}
        if self._prompts:
            capabilities["prompts"] = {}

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
                "capabilities": capabilities,
            },
        }

    def _handle_list_tools(self, req_id: Any) -> dict:
        """Handle tools/list request."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": self.list_tools(),
            },
        }

    def _handle_call_tool(self, req_id: Any, params: dict) -> dict:
        """Handle tools/call request."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        result = self.call_tool(name, arguments)

        # Format result as content
        if isinstance(result, str):
            content = [{"type": "text", "text": result}]
        elif isinstance(result, dict):
            content = [{"type": "text", "text": json.dumps(result, indent=2)}]
        else:
            content = [{"type": "text", "text": str(result)}]

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": content,
            },
        }

    def _handle_list_resources(self, req_id: Any) -> dict:
        """Handle resources/list request."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "resources": self.list_resources(),
            },
        }

    def _handle_read_resource(self, req_id: Any, params: dict) -> dict:
        """Handle resources/read request."""
        uri = params.get("uri")

        content = self.read_resource(uri)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "contents": [content],
            },
        }

    def _handle_list_prompts(self, req_id: Any) -> dict:
        """Handle prompts/list request."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "prompts": self.list_prompts(),
            },
        }

    def _handle_get_prompt(self, req_id: Any, params: dict) -> dict:
        """Handle prompts/get request."""
        name = params.get("name")
        arguments = params.get("arguments", {})

        messages = self.get_prompt(name, arguments)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "messages": messages,
            },
        }

    def _error_response(self, req_id: Any, code: int, message: str) -> dict:
        """Create error response."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    def run(self) -> None:
        """
        Run MCP server on stdio.

        Reads JSON-RPC requests from stdin, writes responses to stdout.
        """
        logger.info(f"Starting MCP server: {self.name}")

        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line.strip())
                response = self.handle_request(request)

                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
            except KeyboardInterrupt:
                break

        logger.info("MCP server stopped")


def create_memory_server(memory) -> MCPServer:
    """
    Create MCP server with memory tools.

    Args:
        memory: Memory instance (Neo4jMemory or InMemoryStore)

    Returns:
        Configured MCP server

    Example:
        >>> from agentic_brain import Neo4jMemory
        >>> from agentic_brain.mcp import create_memory_server
        >>>
        >>> memory = Neo4jMemory(...)
        >>> server = create_memory_server(memory)
        >>> server.run()
    """
    server = MCPServer(
        name="agentic-memory",
        version="1.0.0",
        description="Memory management tools for agentic-brain",
    )

    @server.tool
    def store_memory(content: str, scope: str = "private") -> str:
        """Store content in agent memory."""
        from .memory import DataScope

        scope_enum = DataScope(scope)
        mem = memory.store(content, scope=scope_enum)
        return f"Stored memory: {mem.id}"

    @server.tool
    def search_memory(query: str, scope: str = "private", limit: int = 5) -> str:
        """Search agent memory."""
        from .memory import DataScope

        scope_enum = DataScope(scope)
        results = memory.search(query, scope=scope_enum, limit=limit)

        if not results:
            return "No memories found."

        output = []
        for mem in results:
            output.append(f"- {mem.content}")
        return "\n".join(output)

    @server.tool
    def get_recent_memories(scope: str = "private", limit: int = 10) -> str:
        """Get recent memories."""
        from .memory import DataScope

        scope_enum = DataScope(scope)
        results = memory.get_recent(scope=scope_enum, limit=limit)

        if not results:
            return "No recent memories."

        output = []
        for mem in results:
            output.append(f"[{mem.timestamp}] {mem.content}")
        return "\n".join(output)

    return server


# Import server components for easy access
# Import MCP client
from .client import (
    MCPClient,
    MCPClientConfig,
    MCPClientError,
    MCPConnectionError,
    MCPProtocolError,
    MCPTimeoutError,
    MCPTransport,
    MockTransport,
    StdioTransport,
    WebSocketTransport,
)
from .server import AgenticMCPServer, ServerConfig, create_server
from .tools import (
    ToolContext,
    add_document,
    # Chat tools
    chat,
    chat_async,
    chat_stream,
    # Session tools
    create_session,
    delete_session,
    get_all_tools,
    get_analytics,
    get_context,
    get_session_history,
    # System tools
    health_check,
    list_sessions,
    # Knowledge tools
    search_knowledge,
    set_context,
)
from .tools import (
    get_recent_memories as get_recent_memories_tool,
)
from .tools import (
    search_memory as search_memory_tool,
)
from .tools import (
    # Memory tools
    store_memory as store_memory_tool,
)

# Import MCP types (Pydantic models)
from .types import (
    # JSON Schema
    JSONSchema,
    JSONSchemaProperty,
    JSONSchemaType,
    # Capabilities
    MCPCapabilities,
    MCPClientInfo,
    MCPErrorCode,
    MCPNotification,
    # Prompts
    MCPPrompt,
    MCPPromptArgument,
    MCPPromptMessage,
    # Protocol
    MCPRequest,
    # Resources
    MCPResource,
    MCPResourceContent,
    MCPResourceTemplate,
    MCPResponse,
    # Server/Client Info
    MCPServerInfo,
    # Tools
    MCPTool,
)

__all__ = [
    # Core classes (legacy)
    "MCPServer",
    "ToolParameter",
    "ToolDefinition",
    # Production server
    "AgenticMCPServer",
    "ServerConfig",
    "create_server",
    "create_memory_server",
    # Tool context
    "ToolContext",
    "set_context",
    "get_context",
    "get_all_tools",
    # Chat tools
    "chat",
    "chat_async",
    "chat_stream",
    # Session tools
    "create_session",
    "list_sessions",
    "get_session_history",
    "delete_session",
    # Knowledge tools
    "search_knowledge",
    "add_document",
    # Memory tools
    "store_memory_tool",
    "search_memory_tool",
    "get_recent_memories_tool",
    # System tools
    "health_check",
    "get_analytics",
    # MCP Types (Pydantic)
    "JSONSchema",
    "JSONSchemaProperty",
    "JSONSchemaType",
    "MCPTool",
    "MCPResource",
    "MCPResourceContent",
    "MCPResourceTemplate",
    "MCPPrompt",
    "MCPPromptArgument",
    "MCPPromptMessage",
    "MCPCapabilities",
    "MCPRequest",
    "MCPResponse",
    "MCPNotification",
    "MCPErrorCode",
    "MCPServerInfo",
    "MCPClientInfo",
    # MCP Client
    "MCPClient",
    "MCPClientConfig",
    "MCPClientError",
    "MCPConnectionError",
    "MCPTimeoutError",
    "MCPProtocolError",
    "MCPTransport",
    "StdioTransport",
    "WebSocketTransport",
    "MockTransport",
]
