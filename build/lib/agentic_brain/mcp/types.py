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
MCP (Model Context Protocol) types.

Pydantic models for MCP protocol elements including tools, resources, and prompts.
Based on the Model Context Protocol specification.

Reference: https://modelcontextprotocol.io/
"""

from __future__ import annotations

import builtins
from enum import Enum
from typing import Any, Callable

try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError:
    # Fallback for environments without pydantic

    ConfigDict = None  # type: ignore

    class BaseModel:
        """Fallback BaseModel when pydantic is not available."""

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def model_dump(self) -> builtins.dict[str, Any]:
            """Convert to dictionary."""
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}

        def dict(self) -> builtins.dict[str, Any]:
            """Alias for model_dump."""
            return self.model_dump()

    def Field(default=None, **kwargs):
        """Fallback Field function."""
        return default


# =============================================================================
# JSON Schema Types
# =============================================================================


class JSONSchemaType(str, Enum):
    """JSON Schema type values."""

    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    NULL = "null"


class JSONSchemaProperty(BaseModel):
    """JSON Schema property definition."""

    type: str | list[str] = Field(default="string")
    description: str | None = Field(default=None)
    enum: list[Any] | None = Field(default=None)
    default: Any | None = Field(default=None)
    items: dict[str, Any] | None = Field(default=None)
    properties: dict[str, Any] | None = Field(default=None)
    required: list[str] | None = Field(default=None)


class JSONSchema(BaseModel):
    """JSON Schema definition for tool parameters."""

    type: str = Field(default="object")
    properties: dict[str, JSONSchemaProperty] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)
    additionalProperties: bool | None = Field(default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert to MCP-compatible dictionary."""
        result: dict[str, Any] = {"type": self.type}

        if self.properties:
            result["properties"] = {}
            for name, prop in self.properties.items():
                if isinstance(prop, BaseModel):
                    result["properties"][name] = prop.model_dump()
                else:
                    result["properties"][name] = prop

        if self.required:
            result["required"] = self.required

        if self.additionalProperties is not None:
            result["additionalProperties"] = self.additionalProperties

        return result


# =============================================================================
# MCP Tool Types
# =============================================================================


class MCPTool(BaseModel):
    """
    MCP Tool definition.

    Represents a tool that can be invoked by an MCP client.

    Attributes:
        name: Unique identifier for the tool
        description: Human-readable description
        parameters: JSON Schema for input parameters
        handler: Optional callable to execute the tool
    """

    name: str = Field(description="Unique identifier for the tool")
    description: str = Field(description="Human-readable description of the tool")
    parameters: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object", "properties": {}, "required": []},
        description="JSON Schema for input parameters",
    )
    handler: Callable[..., Any] | None = Field(
        default=None,
        exclude=True,
        description="Callable to execute the tool",
    )

    model_config = ConfigDict(arbitrary_types_allowed=True) if ConfigDict else None

    def to_mcp_schema(self) -> dict[str, Any]:
        """Convert to MCP tool schema format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.parameters,
        }

    @classmethod
    def from_function(
        cls,
        func: Callable[..., Any],
        name: str | None = None,
        description: str | None = None,
    ) -> MCPTool:
        """
        Create an MCPTool from a Python function.

        Extracts parameter information from type hints and docstring.

        Args:
            func: Python function to wrap
            name: Override name (defaults to function name)
            description: Override description (defaults to docstring)

        Returns:
            MCPTool instance
        """
        import inspect

        func_name = name or func.__name__
        func_desc = description or func.__doc__ or f"Tool: {func_name}"

        # Extract parameters from type hints
        sig = inspect.signature(func)
        hints = func.__annotations__

        properties: dict[str, Any] = {}
        required: list[str] = []

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            type(None): "null",
        }

        for param_name, param in sig.parameters.items():
            if param_name == "return":
                continue

            param_type = hints.get(param_name, str)
            json_type = type_map.get(param_type, "string")

            properties[param_name] = {
                "type": json_type,
                "description": f"Parameter: {param_name}",
            }

            if param.default == inspect.Parameter.empty:
                required.append(param_name)
            else:
                properties[param_name]["default"] = param.default

        parameters = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

        return cls(
            name=func_name,
            description=func_desc,
            parameters=parameters,
            handler=func,
        )

    def invoke(self, arguments: dict[str, Any]) -> Any:
        """
        Invoke the tool with given arguments.

        Args:
            arguments: Tool arguments

        Returns:
            Tool result

        Raises:
            ValueError: If no handler is set
        """
        if self.handler is None:
            raise ValueError(f"Tool '{self.name}' has no handler")
        return self.handler(**arguments)

    async def invoke_async(self, arguments: dict[str, Any]) -> Any:
        """
        Invoke the tool asynchronously.

        Args:
            arguments: Tool arguments

        Returns:
            Tool result
        """
        import asyncio

        if self.handler is None:
            raise ValueError(f"Tool '{self.name}' has no handler")

        if inspect.iscoroutinefunction(self.handler):
            return await self.handler(**arguments)
        else:
            return self.handler(**arguments)


# =============================================================================
# MCP Resource Types
# =============================================================================


class MCPResource(BaseModel):
    """
    MCP Resource definition.

    Represents a resource that can be read by an MCP client.

    Attributes:
        uri: Unique URI identifying the resource
        name: Human-readable name
        description: Optional description
        mime_type: MIME type of the resource content
    """

    uri: str = Field(description="Unique URI identifying the resource")
    name: str = Field(description="Human-readable name for the resource")
    description: str | None = Field(
        default=None, description="Optional description of the resource"
    )
    mime_type: str = Field(
        default="text/plain", description="MIME type of the resource content"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def to_mcp_schema(self) -> dict[str, Any]:
        """Convert to MCP resource schema format."""
        result = {
            "uri": self.uri,
            "name": self.name,
            "mimeType": self.mime_type,
        }
        if self.description:
            result["description"] = self.description
        return result


class MCPResourceContent(BaseModel):
    """Content of an MCP resource."""

    uri: str = Field(description="Resource URI")
    mime_type: str = Field(default="text/plain", description="Content MIME type")
    text: str | None = Field(default=None, description="Text content")
    blob: str | None = Field(default=None, description="Base64-encoded binary content")


class MCPResourceTemplate(BaseModel):
    """
    MCP Resource Template.

    Defines a template for dynamic resources.
    """

    uri_template: str = Field(description="URI template with placeholders")
    name: str = Field(description="Human-readable name")
    description: str | None = Field(default=None)
    mime_type: str = Field(default="text/plain")


# =============================================================================
# MCP Prompt Types
# =============================================================================


class MCPPromptArgument(BaseModel):
    """Argument definition for an MCP prompt."""

    name: str = Field(description="Argument name")
    description: str | None = Field(default=None)
    required: bool = Field(default=True)


class MCPPrompt(BaseModel):
    """
    MCP Prompt definition.

    Represents a prompt template that can be filled with arguments.

    Attributes:
        name: Unique identifier for the prompt
        description: Human-readable description
        arguments: List of argument definitions
        template: The prompt template string
    """

    name: str = Field(description="Unique identifier for the prompt")
    description: str | None = Field(default=None, description="Prompt description")
    arguments: list[MCPPromptArgument] = Field(
        default_factory=list, description="List of argument definitions"
    )
    template: str = Field(default="", description="Prompt template string")

    def to_mcp_schema(self) -> dict[str, Any]:
        """Convert to MCP prompt schema format."""
        result = {"name": self.name}
        if self.description:
            result["description"] = self.description
        if self.arguments:
            result["arguments"] = [
                {
                    "name": arg.name,
                    "description": arg.description,
                    "required": arg.required,
                }
                for arg in self.arguments
            ]
        return result

    def render(self, arguments: dict[str, str]) -> str:
        """
        Render the prompt with given arguments.

        Args:
            arguments: Dictionary of argument values

        Returns:
            Rendered prompt string
        """
        result = self.template
        for key, value in arguments.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result


class MCPPromptMessage(BaseModel):
    """Message in a prompt response."""

    role: str = Field(description="Message role (user, assistant, system)")
    content: str = Field(description="Message content")


# =============================================================================
# MCP Capabilities
# =============================================================================


class MCPCapabilities(BaseModel):
    """
    MCP Capabilities container.

    Holds all the capabilities (tools, resources, prompts) of an MCP server.
    """

    tools: list[MCPTool] = Field(default_factory=list, description="Available tools")
    resources: list[MCPResource] = Field(
        default_factory=list, description="Available resources"
    )
    prompts: list[MCPPrompt] = Field(
        default_factory=list, description="Available prompts"
    )
    resource_templates: list[MCPResourceTemplate] = Field(
        default_factory=list, description="Available resource templates"
    )

    def get_tool(self, name: str) -> MCPTool | None:
        """Get a tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def get_resource(self, uri: str) -> MCPResource | None:
        """Get a resource by URI."""
        for resource in self.resources:
            if resource.uri == uri:
                return resource
        return None

    def get_prompt(self, name: str) -> MCPPrompt | None:
        """Get a prompt by name."""
        for prompt in self.prompts:
            if prompt.name == name:
                return prompt
        return None

    def to_server_capabilities(self) -> dict[str, Any]:
        """Convert to MCP server capabilities format."""
        caps: dict[str, Any] = {}

        if self.tools:
            caps["tools"] = {}

        if self.resources or self.resource_templates:
            caps["resources"] = {}
            if self.resource_templates:
                caps["resources"]["listChanged"] = True

        if self.prompts:
            caps["prompts"] = {}
            caps["prompts"]["listChanged"] = True

        return caps


# =============================================================================
# MCP Protocol Messages
# =============================================================================


class MCPRequest(BaseModel):
    """MCP JSON-RPC request."""

    jsonrpc: str = Field(default="2.0")
    id: str | int | None = Field(default=None)
    method: str = Field(description="Method name")
    params: dict[str, Any] | None = Field(default=None)


class MCPResponse(BaseModel):
    """MCP JSON-RPC response."""

    jsonrpc: str = Field(default="2.0")
    id: str | int | None = Field(default=None)
    result: Any | None = Field(default=None)
    error: dict[str, Any] | None = Field(default=None)

    @classmethod
    def success(cls, id: str | int | None, result: Any) -> MCPResponse:
        """Create a success response."""
        return cls(id=id, result=result)

    @classmethod
    def error_response(
        cls,
        id: str | int | None,
        code: int,
        message: str,
        data: Any | None = None,
    ) -> MCPResponse:
        """Create an error response."""
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data
        return cls(id=id, error=error)


class MCPNotification(BaseModel):
    """MCP JSON-RPC notification (no response expected)."""

    jsonrpc: str = Field(default="2.0")
    method: str = Field(description="Notification method")
    params: dict[str, Any] | None = Field(default=None)


# =============================================================================
# Error Codes (JSON-RPC standard + MCP extensions)
# =============================================================================


class MCPErrorCode:
    """Standard MCP/JSON-RPC error codes."""

    # JSON-RPC standard errors
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific errors
    RESOURCE_NOT_FOUND = -32001
    TOOL_NOT_FOUND = -32002
    PROMPT_NOT_FOUND = -32003
    TOOL_EXECUTION_ERROR = -32004


# =============================================================================
# Server Info
# =============================================================================


class MCPServerInfo(BaseModel):
    """MCP server information."""

    name: str = Field(description="Server name")
    version: str = Field(default="1.0.0", description="Server version")
    protocol_version: str = Field(
        default="2024-11-05", description="MCP protocol version"
    )


class MCPClientInfo(BaseModel):
    """MCP client information."""

    name: str = Field(description="Client name")
    version: str = Field(default="1.0.0", description="Client version")


__all__ = [
    # JSON Schema
    "JSONSchemaType",
    "JSONSchemaProperty",
    "JSONSchema",
    # Tools
    "MCPTool",
    # Resources
    "MCPResource",
    "MCPResourceContent",
    "MCPResourceTemplate",
    # Prompts
    "MCPPromptArgument",
    "MCPPrompt",
    "MCPPromptMessage",
    # Capabilities
    "MCPCapabilities",
    # Protocol
    "MCPRequest",
    "MCPResponse",
    "MCPNotification",
    "MCPErrorCode",
    # Server/Client Info
    "MCPServerInfo",
    "MCPClientInfo",
]
