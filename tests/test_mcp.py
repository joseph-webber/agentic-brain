"""Tests for MCP (Model Context Protocol) module."""
import pytest
import json
from unittest.mock import MagicMock, patch, mock_open
from agentic_brain.mcp import (
    ToolParameter,
    ToolDefinition,
    MCPServer,
)


class TestToolParameter:
    """Tests for ToolParameter dataclass."""
    
    def test_tool_parameter_creation(self):
        """Test creating a ToolParameter."""
        param = ToolParameter(
            name="query",
            type="string",
            description="Search query",
            required=True
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
            default=10
        )
        assert param.default == 10
        assert param.required is False


class TestToolDefinition:
    """Tests for ToolDefinition dataclass."""
    
    def test_tool_definition_creation(self):
        """Test creating a ToolDefinition."""
        params = [
            ToolParameter("query", "string", "Search query"),
            ToolParameter("limit", "integer", "Result limit", required=False),
        ]
        tool = ToolDefinition(
            name="search",
            description="Search memory",
            parameters=params
        )
        assert tool.name == "search"
        assert tool.description == "Search memory"
        assert len(tool.parameters) == 2
    
    def test_tool_definition_to_mcp_schema(self):
        """Test converting ToolDefinition to MCP schema."""
        params = [
            ToolParameter("query", "string", "Search query", required=True),
            ToolParameter("limit", "integer", "Result limit", required=False, default=10),
        ]
        tool = ToolDefinition(
            name="search",
            description="Search memory",
            parameters=params
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
        
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        
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
        
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
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
            "params": {
                "name": "greet",
                "arguments": {"name": "Alice"}
            }
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
            "params": {
                "name": "get_info",
                "arguments": {}
            }
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
        
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "unknown/method",
            "params": {}
        }
        
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
            "params": {
                "name": "failing_tool",
                "arguments": {}
            }
        }
        
        response = server.handle_request(request)
        
        assert "error" in response
        assert response["error"]["code"] == -32603
        assert "Tool failed" in response["error"]["message"]
    
    def test_handle_request_defaults(self):
        """Test handle_request with missing fields."""
        server = MCPServer("test-server")
        
        request = {
            "method": "initialize"
        }
        
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
        init_response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        })
        assert init_response["result"]["serverInfo"]["name"] == "integration-test"
        
        # List tools
        list_response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        })
        assert len(list_response["result"]["tools"]) == 2
        
        # Call add
        add_response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "add",
                "arguments": {"a": 10, "b": 5}
            }
        })
        assert "15" in add_response["result"]["content"][0]["text"]
        
        # Call multiply
        mul_response = server.handle_request({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "multiply",
                "arguments": {"a": 10, "b": 5}
            }
        })
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
