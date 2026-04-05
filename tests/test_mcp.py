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

"""Tests for MCP (Model Context Protocol) module."""

import importlib
import json
import sys

import pytest

from agentic_brain.mcp import (
    MCPCapabilities,
    # Client
    MCPClient,
    MCPClientConfig,
    MCPPrompt,
    MCPPromptArgument,
    MCPProtocolError,
    MCPRequest,
    MCPResource,
    MCPResponse,
    MCPServer,
    # New Pydantic types
    MCPTool,
    MockTransport,
    ToolDefinition,
    # Legacy types
    ToolParameter,
)


def _clear_modules(prefixes: tuple[str, ...]) -> None:
    """Remove modules from sys.modules so import side effects can be inspected."""
    for name in list(sys.modules):
        if any(name == prefix or name.startswith(f"{prefix}.") for prefix in prefixes):
            sys.modules.pop(name, None)


class TestToolParameter:
    """Tests for ToolParameter dataclass."""

    def test_tool_parameter_creation(self):
        """Test creating a ToolParameter."""
        param = ToolParameter(
            name="query", type="string", description="Search query", required=True
        )
        assert param.name == "query"
        assert param.type == "string"
        assert param.description == "Search query"
        assert param.required is True

    def test_tool_parameter_with_default(self):
        """Test ToolParameter with default value."""
        param = ToolParameter(
            name="limit",
            type="integer",
            description="Result limit",
            required=False,
            default=10,
        )
        assert param.default == 10
        assert param.required is False


class TestLazyLoading:
    """Tests for lazy-loading package exports."""

    def test_mcp_package_import_is_lazy(self):
        """Importing the MCP package should not eagerly import heavy submodules."""
        _clear_modules(("agentic_brain",))

        mcp = importlib.import_module("agentic_brain.mcp")

        assert mcp is not None
        assert "agentic_brain.mcp.server" not in sys.modules
        assert "agentic_brain.mcp.client" not in sys.modules
        assert "agentic_brain.mcp.types" not in sys.modules
        assert "agentic_brain.mcp.tools" not in sys.modules

    def test_mcp_lazy_exports_load_on_demand(self):
        """Accessing exported MCP symbols should import only their target module."""
        _clear_modules(("agentic_brain",))

        mcp = importlib.import_module("agentic_brain.mcp")
        _ = mcp.AgenticMCPServer
        _ = mcp.MCPClient

        assert "agentic_brain.mcp.server" in sys.modules
        assert "agentic_brain.mcp.client" in sys.modules


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""

    def test_tool_definition_creation(self):
        """Test creating a ToolDefinition."""
        params = [
            ToolParameter("query", "string", "Search query"),
            ToolParameter("limit", "integer", "Result limit", required=False),
        ]
        tool = ToolDefinition(
            name="search", description="Search memory", parameters=params
        )
        assert tool.name == "search"
        assert tool.description == "Search memory"
        assert len(tool.parameters) == 2

    def test_tool_definition_to_mcp_schema(self):
        """Test converting ToolDefinition to MCP schema."""
        params = [
            ToolParameter("query", "string", "Search query", required=True),
            ToolParameter(
                "limit", "integer", "Result limit", required=False, default=10
            ),
        ]
        tool = ToolDefinition(
            name="search", description="Search memory", parameters=params
        )

        schema = tool.to_mcp_schema()

        assert schema["name"] == "search"
        assert schema["description"] == "Search memory"
        assert "query" in schema["inputSchema"]["properties"]
        assert "limit" in schema["inputSchema"]["properties"]
        assert schema["inputSchema"]["required"] == ["query"]
        assert schema["inputSchema"]["properties"]["query"]["type"] == "string"
        assert schema["inputSchema"]["properties"]["limit"]["type"] == "integer"

    def test_tool_definition_empty_parameters(self):
        """Test ToolDefinition with no parameters."""
        tool = ToolDefinition(
            name="get_status",
            description="Get server status",
        )
        schema = tool.to_mcp_schema()
        assert schema["inputSchema"]["properties"] == {}
        assert schema["inputSchema"]["required"] == []


class TestMCPServer:
    """Tests for MCPServer class."""

    def test_mcp_server_creation(self):
        """Test creating an MCPServer."""
        server = MCPServer("test-server", version="1.0.0", description="Test server")
        assert server.name == "test-server"
        assert server.version == "1.0.0"
        assert server.description == "Test server"

    def test_mcp_server_defaults(self):
        """Test MCPServer with default values."""
        server = MCPServer("test-server")
        assert server.version == "1.0.0"
        assert server.description == ""

    def test_tool_decorator_registration(self):
        """Test tool decorator registers function as tool."""
        server = MCPServer("test-server")

        @server.tool
        def my_tool(query: str) -> str:
            """Search for something."""
            return f"Results for {query}"

        assert "my_tool" in server._tools
        tool = server._tools["my_tool"]
        assert tool.name == "my_tool"
        assert tool.description == "Search for something."
        assert tool.handler == my_tool

    def test_tool_decorator_with_parameters(self):
        """Test tool decorator extracts parameter types."""
        server = MCPServer("test-server")

        @server.tool
        def search(query: str, limit: int = 5, active: bool = True) -> str:
            """Search with filters."""
            return "results"

        tool = server._tools["search"]
        assert len(tool.parameters) == 3

        params = {p.name: p for p in tool.parameters}
        assert params["query"].type == "string"
        assert params["query"].required is True
        assert params["limit"].type == "integer"
        assert params["limit"].required is False
        assert params["limit"].default == 5
        assert params["active"].type == "boolean"
        assert params["active"].required is False

    def test_tool_decorator_with_complex_types(self):
        """Test tool decorator with list and dict types."""
        server = MCPServer("test-server")

        @server.tool
        def process(items: list, metadata: dict) -> str:
            """Process items."""
            return "done"

        tool = server._tools["process"]
        params = {p.name: p for p in tool.parameters}
        assert params["items"].type == "array"
        assert params["metadata"].type == "object"

    def test_register_tool_manually(self):
        """Test registering a tool manually."""
        server = MCPServer("test-server")

        def handler(query: str) -> str:
            return f"Result: {query}"

        params = [ToolParameter("query", "string", "Search query")]
        server.register_tool("search", "Search memory", handler, params)

        assert "search" in server._tools
        tool = server._tools["search"]
        assert tool.name == "search"
        assert tool.description == "Search memory"
        assert tool.handler == handler

    def test_list_tools(self):
        """Test listing tools in MCP schema format."""
        server = MCPServer("test-server")

        @server.tool
        def tool1(arg: str) -> str:
            """Tool 1."""
            return "result"

        @server.tool
        def tool2(arg: int) -> str:
            """Tool 2."""
            return "result"

        tools = server.list_tools()
        assert len(tools) == 2
        names = [t["name"] for t in tools]
        assert "tool1" in names
        assert "tool2" in names

    def test_call_tool_success(self):
        """Test calling a registered tool."""
        server = MCPServer("test-server")

        @server.tool
        def greet(name: str) -> str:
            """Greet someone."""
            return f"Hello, {name}!"

        result = server.call_tool("greet", {"name": "World"})
        assert result == "Hello, World!"

    def test_call_tool_with_multiple_args(self):
        """Test calling tool with multiple arguments."""
        server = MCPServer("test-server")

        @server.tool
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = server.call_tool("add", {"a": 5, "b": 3})
        assert result == 8

    def test_call_tool_unknown_tool(self):
        """Test calling unknown tool raises error."""
        server = MCPServer("test-server")

        with pytest.raises(ValueError, match="Unknown tool"):
            server.call_tool("nonexistent", {})

    def test_call_tool_no_handler(self):
        """Test calling tool with no handler raises error."""
        server = MCPServer("test-server")

        # Register tool without handler
        tool = ToolDefinition("no_handler", "Tool without handler")
        server._tools["no_handler"] = tool

        with pytest.raises(ValueError, match="no handler"):
            server.call_tool("no_handler", {})

    def test_handle_initialize_request(self):
        """Test handling initialize request."""
        server = MCPServer("test-server", version="2.0.0")

        request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}

        response = server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["serverInfo"]["name"] == "test-server"
        assert response["result"]["serverInfo"]["version"] == "2.0.0"
        assert "capabilities" in response["result"]

    def test_handle_list_tools_request(self):
        """Test handling tools/list request."""
        server = MCPServer("test-server")

        @server.tool
        def search(query: str) -> str:
            """Search."""
            return "result"

        request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        response = server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 2
        assert "result" in response
        assert len(response["result"]["tools"]) == 1
        assert response["result"]["tools"][0]["name"] == "search"

    def test_handle_call_tool_request_string_result(self):
        """Test handling tools/call request with string result."""
        server = MCPServer("test-server")

        @server.tool
        def greet(name: str) -> str:
            """Greet."""
            return f"Hello, {name}!"

        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "greet", "arguments": {"name": "Alice"}},
        }

        response = server.handle_request(request)

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 3
        assert "result" in response
        assert response["result"]["content"][0]["type"] == "text"
        assert response["result"]["content"][0]["text"] == "Hello, Alice!"

    def test_handle_call_tool_request_dict_result(self):
        """Test handling tools/call request with dict result."""
        server = MCPServer("test-server")

        @server.tool
        def get_info() -> dict:
            """Get info."""
            return {"status": "ok", "count": 42}

        request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "get_info", "arguments": {}},
        }

        response = server.handle_request(request)

        assert response["result"]["content"][0]["type"] == "text"
        text = response["result"]["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"
        assert data["count"] == 42

    def test_handle_unknown_method(self):
        """Test handling unknown method returns error."""
        server = MCPServer("test-server")

        request = {"jsonrpc": "2.0", "id": 5, "method": "unknown/method", "params": {}}

        response = server.handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Unknown method" in response["error"]["message"]

    def test_handle_tool_call_error(self):
        """Test handling tool call that raises exception."""
        server = MCPServer("test-server")

        @server.tool
        def failing_tool() -> str:
            """Failing tool."""
            raise RuntimeError("Tool failed")

        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "failing_tool", "arguments": {}},
        }

        response = server.handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32603
        assert "Tool failed" in response["error"]["message"]

    def test_handle_request_defaults(self):
        """Test handle_request with missing fields."""
        server = MCPServer("test-server")

        request = {"method": "initialize"}

        response = server.handle_request(request)

        assert response["id"] is None
        assert "result" in response


class TestMCPServerIntegration:
    """Integration tests for MCPServer."""

    def test_complete_workflow(self):
        """Test complete workflow: initialize, list tools, call tool."""
        server = MCPServer("integration-test")

        @server.tool
        def add(a: int, b: int) -> int:
            """Add numbers."""
            return a + b

        @server.tool
        def multiply(a: int, b: int) -> int:
            """Multiply numbers."""
            return a * b

        # Initialize
        init_response = server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        assert init_response["result"]["serverInfo"]["name"] == "integration-test"

        # List tools
        list_response = server.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        assert len(list_response["result"]["tools"]) == 2

        # Call add
        add_response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "add", "arguments": {"a": 10, "b": 5}},
            }
        )
        assert "15" in add_response["result"]["content"][0]["text"]

        # Call multiply
        mul_response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "multiply", "arguments": {"a": 10, "b": 5}},
            }
        )
        assert "50" in mul_response["result"]["content"][0]["text"]

    def test_tool_with_default_parameters(self):
        """Test calling tool with default parameters."""
        server = MCPServer("test-server")

        @server.tool
        def search(query: str, limit: int = 5) -> str:
            """Search with optional limit."""
            return f"Searching for '{query}' (limit={limit})"

        # Call with all args
        result1 = server.call_tool("search", {"query": "test", "limit": 10})
        assert "limit=10" in result1

        # Call with default
        result2 = server.call_tool("search", {"query": "test"})
        assert "limit=5" in result2


# =============================================================================
# Tests for MCP Types (Pydantic models)
# =============================================================================


class TestMCPTool:
    """Tests for MCPTool Pydantic model."""

    def test_mcp_tool_creation(self):
        """Test creating an MCPTool."""
        tool = MCPTool(
            name="search",
            description="Search memory",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        )
        assert tool.name == "search"
        assert tool.description == "Search memory"
        assert "query" in tool.parameters["properties"]

    def test_mcp_tool_to_schema(self):
        """Test converting MCPTool to MCP schema."""
        tool = MCPTool(
            name="greet",
            description="Greet someone",
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        )

        schema = tool.to_mcp_schema()

        assert schema["name"] == "greet"
        assert schema["description"] == "Greet someone"
        assert schema["inputSchema"]["properties"]["name"]["type"] == "string"

    def test_mcp_tool_from_function(self):
        """Test creating MCPTool from a Python function."""

        def calculator(a: int, b: int, operation: str = "add") -> int:
            """Perform calculation."""
            if operation == "add":
                return a + b
            return a - b

        tool = MCPTool.from_function(calculator)

        assert tool.name == "calculator"
        assert "calculation" in tool.description.lower()
        assert tool.handler == calculator
        assert "a" in tool.parameters["properties"]
        assert "b" in tool.parameters["properties"]
        assert "operation" in tool.parameters["properties"]
        assert "a" in tool.parameters["required"]
        assert "b" in tool.parameters["required"]
        assert "operation" not in tool.parameters["required"]

    def test_mcp_tool_invoke(self):
        """Test invoking an MCPTool."""

        def add(a: int, b: int) -> int:
            return a + b

        tool = MCPTool.from_function(add)
        result = tool.invoke({"a": 5, "b": 3})

        assert result == 8

    def test_mcp_tool_invoke_no_handler(self):
        """Test invoking tool without handler raises error."""
        tool = MCPTool(name="no_handler", description="No handler")

        with pytest.raises(ValueError, match="has no handler"):
            tool.invoke({})


class TestMCPResource:
    """Tests for MCPResource Pydantic model."""

    def test_mcp_resource_creation(self):
        """Test creating an MCPResource."""
        resource = MCPResource(
            uri="file:///data/config.json",
            name="Config File",
            description="Application configuration",
            mime_type="application/json",
        )

        assert resource.uri == "file:///data/config.json"
        assert resource.name == "Config File"
        assert resource.description == "Application configuration"
        assert resource.mime_type == "application/json"

    def test_mcp_resource_to_schema(self):
        """Test converting MCPResource to MCP schema."""
        resource = MCPResource(
            uri="file:///readme.md", name="README", mime_type="text/markdown"
        )

        schema = resource.to_mcp_schema()

        assert schema["uri"] == "file:///readme.md"
        assert schema["name"] == "README"
        assert schema["mimeType"] == "text/markdown"

    def test_mcp_resource_defaults(self):
        """Test MCPResource default values."""
        resource = MCPResource(uri="file:///test.txt", name="Test")

        assert resource.mime_type == "text/plain"
        assert resource.description is None
        assert resource.metadata == {}


class TestMCPPrompt:
    """Tests for MCPPrompt Pydantic model."""

    def test_mcp_prompt_creation(self):
        """Test creating an MCPPrompt."""
        prompt = MCPPrompt(
            name="code_review",
            description="Review code changes",
            arguments=[
                MCPPromptArgument(name="code", description="Code to review"),
                MCPPromptArgument(
                    name="language", description="Programming language", required=False
                ),
            ],
            template="Please review the following {language} code:\n\n{code}",
        )

        assert prompt.name == "code_review"
        assert len(prompt.arguments) == 2
        assert prompt.arguments[0].name == "code"
        assert prompt.arguments[1].required is False

    def test_mcp_prompt_to_schema(self):
        """Test converting MCPPrompt to MCP schema."""
        prompt = MCPPrompt(
            name="summarize",
            description="Summarize text",
            arguments=[MCPPromptArgument(name="text", description="Text to summarize")],
        )

        schema = prompt.to_mcp_schema()

        assert schema["name"] == "summarize"
        assert schema["description"] == "Summarize text"
        assert len(schema["arguments"]) == 1
        assert schema["arguments"][0]["name"] == "text"

    def test_mcp_prompt_render(self):
        """Test rendering a prompt with arguments."""
        prompt = MCPPrompt(name="greet", template="Hello, {name}! Welcome to {place}.")

        rendered = prompt.render({"name": "User", "place": "Adelaide"})

        assert rendered == "Hello, User! Welcome to Adelaide."


class TestMCPCapabilities:
    """Tests for MCPCapabilities container."""

    def test_capabilities_creation(self):
        """Test creating MCPCapabilities."""
        tool = MCPTool(name="search", description="Search")
        resource = MCPResource(uri="file:///data", name="Data")
        prompt = MCPPrompt(name="assist", description="Assist")

        caps = MCPCapabilities(tools=[tool], resources=[resource], prompts=[prompt])

        assert len(caps.tools) == 1
        assert len(caps.resources) == 1
        assert len(caps.prompts) == 1

    def test_capabilities_get_tool(self):
        """Test getting tool by name."""
        tool1 = MCPTool(name="search", description="Search")
        tool2 = MCPTool(name="store", description="Store")

        caps = MCPCapabilities(tools=[tool1, tool2])

        found = caps.get_tool("search")
        assert found is not None
        assert found.name == "search"

        not_found = caps.get_tool("unknown")
        assert not_found is None

    def test_capabilities_get_resource(self):
        """Test getting resource by URI."""
        res = MCPResource(uri="file:///config", name="Config")
        caps = MCPCapabilities(resources=[res])

        found = caps.get_resource("file:///config")
        assert found is not None
        assert found.name == "Config"

    def test_capabilities_get_prompt(self):
        """Test getting prompt by name."""
        prompt = MCPPrompt(name="help", description="Help")
        caps = MCPCapabilities(prompts=[prompt])

        found = caps.get_prompt("help")
        assert found is not None
        assert found.name == "help"

    def test_capabilities_to_server_capabilities(self):
        """Test converting to server capabilities format."""
        caps = MCPCapabilities(
            tools=[MCPTool(name="t", description="t")],
            resources=[MCPResource(uri="r", name="r")],
            prompts=[MCPPrompt(name="p", description="p")],
        )

        server_caps = caps.to_server_capabilities()

        assert "tools" in server_caps
        assert "resources" in server_caps
        assert "prompts" in server_caps


class TestMCPProtocol:
    """Tests for MCP protocol messages."""

    def test_mcp_request(self):
        """Test MCPRequest model."""
        request = MCPRequest(id=1, method="tools/list", params={})

        assert request.jsonrpc == "2.0"
        assert request.id == 1
        assert request.method == "tools/list"

    def test_mcp_response_success(self):
        """Test MCPResponse success factory."""
        response = MCPResponse.success(1, {"tools": []})

        assert response.id == 1
        assert response.result == {"tools": []}
        assert response.error is None

    def test_mcp_response_error(self):
        """Test MCPResponse error factory."""
        response = MCPResponse.error_response(1, -32601, "Method not found")

        assert response.id == 1
        assert response.result is None
        assert response.error["code"] == -32601
        assert response.error["message"] == "Method not found"


# =============================================================================
# Tests for MCPServer Resources and Prompts
# =============================================================================


class TestMCPServerResources:
    """Tests for MCPServer resource handling."""

    def test_register_resource(self):
        """Test registering a resource."""
        server = MCPServer("test-server")

        server.register_resource(
            uri="file:///config.json",
            name="Config",
            description="App config",
            mime_type="application/json",
        )

        resources = server.list_resources()
        assert len(resources) == 1
        assert resources[0]["uri"] == "file:///config.json"
        assert resources[0]["name"] == "Config"

    def test_register_resource_with_handler(self):
        """Test registering a resource with handler."""
        server = MCPServer("test-server")

        def get_config():
            return '{"version": "1.0"}'

        server.register_resource(
            uri="file:///config.json",
            name="Config",
            mime_type="application/json",
            handler=get_config,
        )

        content = server.read_resource("file:///config.json")
        assert content["text"] == '{"version": "1.0"}'

    def test_handle_resources_list_request(self):
        """Test handling resources/list request."""
        server = MCPServer("test-server")
        server.register_resource("file:///data", "Data", "Test data")

        response = server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {}}
        )

        assert response["id"] == 1
        assert len(response["result"]["resources"]) == 1

    def test_handle_resources_read_request(self):
        """Test handling resources/read request."""
        server = MCPServer("test-server")
        server.register_resource("file:///test", "Test", handler=lambda: "Hello")

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "resources/read",
                "params": {"uri": "file:///test"},
            }
        )

        assert response["result"]["contents"][0]["text"] == "Hello"


class TestMCPServerPrompts:
    """Tests for MCPServer prompt handling."""

    def test_register_prompt(self):
        """Test registering a prompt."""
        server = MCPServer("test-server")

        server.register_prompt(
            name="code_review",
            description="Review code",
            arguments=[{"name": "code", "required": True}],
        )

        prompts = server.list_prompts()
        assert len(prompts) == 1
        assert prompts[0]["name"] == "code_review"

    def test_register_prompt_with_handler(self):
        """Test registering a prompt with handler."""
        server = MCPServer("test-server")

        def generate_review_prompt(code: str):
            return [
                {"role": "user", "content": {"type": "text", "text": f"Review: {code}"}}
            ]

        server.register_prompt(
            name="review", description="Code review", handler=generate_review_prompt
        )

        messages = server.get_prompt("review", {"code": "print('hello')"})
        assert len(messages) == 1
        assert "Review:" in messages[0]["content"]["text"]

    def test_handle_prompts_list_request(self):
        """Test handling prompts/list request."""
        server = MCPServer("test-server")
        server.register_prompt("help", "Get help")

        response = server.handle_request(
            {"jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {}}
        )

        assert len(response["result"]["prompts"]) == 1

    def test_handle_prompts_get_request(self):
        """Test handling prompts/get request."""
        server = MCPServer("test-server")
        server.register_prompt(
            "greet",
            "Greet user",
            handler=lambda name: [
                {"role": "user", "content": {"type": "text", "text": f"Hello {name}"}}
            ],
        )

        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {"name": "greet", "arguments": {"name": "User"}},
            }
        )

        assert "Hello User" in response["result"]["messages"][0]["content"]["text"]


# =============================================================================
# Tests for MCP Client
# =============================================================================


class TestMCPClient:
    """Tests for MCPClient."""

    @pytest.mark.asyncio
    async def test_client_creation(self):
        """Test creating an MCPClient."""
        client = MCPClient.mock()

        assert client.config.name == "agentic-brain-client"
        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_client_connect_and_initialize(self):
        """Test client connection and initialization."""
        responses = [
            # Initialize response
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test-server", "version": "1.0.0"},
                    "capabilities": {"tools": {}},
                },
            }
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        assert client.is_connected
        assert client.server_info is not None
        assert client.server_info.name == "test-server"

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_list_tools(self):
        """Test listing tools from server."""
        responses = [
            # Initialize response
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # tools/list response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "tools": [
                        {
                            "name": "search",
                            "description": "Search memory",
                            "inputSchema": {},
                        }
                    ]
                },
            },
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        tools = await client.list_tools()

        assert len(tools) == 1
        assert tools[0].name == "search"

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_call_tool(self):
        """Test calling a tool."""
        responses = [
            # Initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # tools/call response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {"content": [{"type": "text", "text": "Found 5 results"}]},
            },
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        result = await client.call_tool("search", {"query": "test"})

        assert len(result) == 1
        assert result[0]["text"] == "Found 5 results"

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_list_resources(self):
        """Test listing resources."""
        responses = [
            # Initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # resources/list response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "resources": [
                        {
                            "uri": "file:///config",
                            "name": "Config",
                            "mimeType": "application/json",
                        }
                    ]
                },
            },
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        resources = await client.list_resources()

        assert len(resources) == 1
        assert resources[0].uri == "file:///config"

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_read_resource(self):
        """Test reading a resource."""
        responses = [
            # Initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # resources/read response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "contents": [
                        {
                            "uri": "file:///data",
                            "mimeType": "text/plain",
                            "text": "Hello World",
                        }
                    ]
                },
            },
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        content = await client.read_resource("file:///data")

        assert content.text == "Hello World"
        assert content.mime_type == "text/plain"

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_list_prompts(self):
        """Test listing prompts."""
        responses = [
            # Initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # prompts/list response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "prompts": [
                        {
                            "name": "code_review",
                            "description": "Review code",
                            "arguments": [],
                        }
                    ]
                },
            },
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        prompts = await client.list_prompts()

        assert len(prompts) == 1
        assert prompts[0].name == "code_review"

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_get_prompt(self):
        """Test getting a prompt."""
        responses = [
            # Initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # prompts/get response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "messages": [
                        {
                            "role": "user",
                            "content": {"type": "text", "text": "Review this code"},
                        }
                    ]
                },
            },
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        messages = await client.get_prompt("code_review", {"code": "print()"})

        assert len(messages) == 1
        assert messages[0].role == "user"

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_error_handling(self):
        """Test client error handling."""
        responses = [
            # Initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # Error response
            {
                "jsonrpc": "2.0",
                "id": 2,
                "error": {"code": -32002, "message": "Tool not found"},
            },
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        with pytest.raises(MCPProtocolError) as exc_info:
            await client.call_tool("nonexistent", {})

        assert exc_info.value.code == -32002
        assert "Tool not found" in str(exc_info.value)

        await client.disconnect()

    @pytest.mark.asyncio
    async def test_client_context_manager(self):
        """Test client as async context manager."""
        responses = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            }
        ]

        transport = MockTransport(responses)
        config = MCPClientConfig(name="test-client")

        async with MCPClient(transport, config) as client:
            assert client.is_connected

        assert not client.is_connected

    @pytest.mark.asyncio
    async def test_client_get_capabilities(self):
        """Test getting all capabilities."""
        responses = [
            # Initialize
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": "test", "version": "1.0"},
                    "capabilities": {},
                },
            },
            # tools/list
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "tools": [{"name": "t1", "description": "d1", "inputSchema": {}}]
                },
            },
            # resources/list
            {"jsonrpc": "2.0", "id": 3, "result": {"resources": []}},
            # prompts/list
            {"jsonrpc": "2.0", "id": 4, "result": {"prompts": []}},
        ]

        client = MCPClient.mock(responses)
        await client.connect()

        caps = await client.get_capabilities()

        assert len(caps.tools) == 1
        assert caps.tools[0].name == "t1"

        await client.disconnect()


class TestMockTransport:
    """Tests for MockTransport."""

    @pytest.mark.asyncio
    async def test_mock_transport_connect_disconnect(self):
        """Test mock transport connection."""
        transport = MockTransport()

        assert not transport.is_connected

        await transport.connect()
        assert transport.is_connected

        await transport.disconnect()
        assert not transport.is_connected

    @pytest.mark.asyncio
    async def test_mock_transport_send_receive(self):
        """Test mock transport send and receive."""
        responses = [{"result": "ok"}]
        transport = MockTransport(responses)

        await transport.connect()

        # Send
        await transport.send({"method": "test"})
        assert len(transport.sent_messages) == 1
        assert transport.sent_messages[0]["method"] == "test"

        # Receive
        response = await transport.receive()
        assert response["result"] == "ok"

    @pytest.mark.asyncio
    async def test_mock_transport_add_response(self):
        """Test adding responses to mock transport."""
        transport = MockTransport()
        transport.add_response({"id": 1, "result": "first"})
        transport.add_response({"id": 2, "result": "second"})

        await transport.connect()

        r1 = await transport.receive()
        r2 = await transport.receive()

        assert r1["result"] == "first"
        assert r2["result"] == "second"
