"""
MCP (Model Context Protocol) server for agentic-brain.

Provides tools that Claude and other MCP-compatible clients can use.
Based on Anthropic's MCP specification.

Example:
    >>> from agentic_brain.mcp import MCPServer, tool
    >>> 
    >>> server = MCPServer("my-agent")
    >>> 
    >>> @server.tool
    ... def search_memory(query: str) -> str:
    ...     return "Found: ..."
    >>> 
    >>> server.run()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Any, Dict, List
from functools import wraps
import json
import sys
import logging

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
    parameters: List[ToolParameter] = field(default_factory=list)
    handler: Optional[Callable] = None
    
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
        self._tools: Dict[str, ToolDefinition] = {}
    
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
            
            parameters.append(ToolParameter(
                name=param_name,
                type=type_map.get(param_type, "string"),
                description=f"Parameter: {param_name}",
                required=param.default == inspect.Parameter.empty,
                default=None if param.default == inspect.Parameter.empty else param.default,
            ))
        
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
        parameters: Optional[List[ToolParameter]] = None,
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
    
    def list_tools(self) -> List[dict]:
        """List all tools in MCP schema format."""
        return [tool.to_mcp_schema() for tool in self._tools.values()]
    
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
            else:
                return self._error_response(req_id, -32601, f"Unknown method: {method}")
        except Exception as e:
            logger.error(f"MCP error: {e}")
            return self._error_response(req_id, -32603, str(e))
    
    def _handle_initialize(self, req_id: Any, params: dict) -> dict:
        """Handle initialize request."""
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": self.name,
                    "version": self.version,
                },
                "capabilities": {
                    "tools": {},
                },
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
