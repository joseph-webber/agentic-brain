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
MCP Client - Connect to external MCP servers.

Provides a client implementation for connecting to MCP-compatible servers,
listing their capabilities, and invoking tools/resources.

Usage:
    from agentic_brain.mcp.client import MCPClient

    # Connect to stdio-based server
    async with MCPClient.stdio("python", "-m", "my_mcp_server") as client:
        tools = await client.list_tools()
        result = await client.call_tool("search", {"query": "test"})

    # Connect via HTTP (WebSocket)
    async with MCPClient.websocket("ws://localhost:8080/mcp") as client:
        resources = await client.list_resources()
        content = await client.read_resource("file:///data.txt")
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .types import (
    MCPCapabilities,
    MCPErrorCode,
    MCPPrompt,
    MCPPromptMessage,
    MCPResource,
    MCPResourceContent,
    MCPServerInfo,
    MCPTool,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class MCPClientError(Exception):
    """Base exception for MCP client errors."""

    pass


class MCPConnectionError(MCPClientError):
    """Error connecting to MCP server."""

    pass


class MCPTimeoutError(MCPClientError):
    """Timeout waiting for server response."""

    pass


class MCPProtocolError(MCPClientError):
    """Protocol-level error from server."""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(f"MCP Error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data


# =============================================================================
# Transport Layer
# =============================================================================


class MCPTransport(ABC):
    """Abstract transport for MCP communication."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """Send a JSON message."""
        pass

    @abstractmethod
    async def receive(self) -> dict[str, Any]:
        """Receive a JSON message."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass


class StdioTransport(MCPTransport):
    """Transport using subprocess stdio."""

    def __init__(self, command: list[str], cwd: str | None = None):
        self.command = command
        self.cwd = cwd
        self._process: subprocess.Popen | None = None
        self._connected = False

    async def connect(self) -> None:
        """Start the subprocess."""
        try:
            self._process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.cwd,
                text=True,
                bufsize=1,
            )
            self._connected = True
            logger.info(f"Started MCP server: {' '.join(self.command)}")
        except Exception as e:
            raise MCPConnectionError(f"Failed to start server: {e}") from e

    async def disconnect(self) -> None:
        """Stop the subprocess."""
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        self._connected = False
        logger.info("MCP server stopped")

    async def send(self, message: dict[str, Any]) -> None:
        """Send message to subprocess stdin."""
        if not self._process or not self._process.stdin:
            raise MCPConnectionError("Not connected")

        try:
            line = json.dumps(message) + "\n"
            self._process.stdin.write(line)
            self._process.stdin.flush()
        except Exception as e:
            raise MCPConnectionError(f"Failed to send: {e}") from e

    async def receive(self) -> dict[str, Any]:
        """Receive message from subprocess stdout."""
        if not self._process or not self._process.stdout:
            raise MCPConnectionError("Not connected")

        try:
            # Use asyncio to avoid blocking
            loop = asyncio.get_event_loop()
            line = await loop.run_in_executor(None, self._process.stdout.readline)

            if not line:
                raise MCPConnectionError("Server closed connection")

            return json.loads(line.strip())
        except json.JSONDecodeError as e:
            raise MCPProtocolError(
                MCPErrorCode.PARSE_ERROR, f"Invalid JSON: {e}"
            ) from e

    @property
    def is_connected(self) -> bool:
        return self._connected and self._process is not None


class WebSocketTransport(MCPTransport):
    """Transport using WebSocket."""

    def __init__(self, url: str):
        self.url = url
        self._ws = None
        self._connected = False

    async def connect(self) -> None:
        """Connect to WebSocket server."""
        try:
            import websockets

            self._ws = await websockets.connect(self.url)
            self._connected = True
            logger.info(f"Connected to MCP server: {self.url}")
        except ImportError:
            raise MCPConnectionError(
                "websockets package required for WebSocket transport"
            )
        except Exception as e:
            raise MCPConnectionError(f"Failed to connect: {e}") from e

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        if self._ws:
            await self._ws.close()
            self._ws = None
        self._connected = False

    async def send(self, message: dict[str, Any]) -> None:
        """Send message via WebSocket."""
        if not self._ws:
            raise MCPConnectionError("Not connected")
        await self._ws.send(json.dumps(message))

    async def receive(self) -> dict[str, Any]:
        """Receive message via WebSocket."""
        if not self._ws:
            raise MCPConnectionError("Not connected")

        try:
            data = await self._ws.recv()
            return json.loads(data)
        except json.JSONDecodeError as e:
            raise MCPProtocolError(
                MCPErrorCode.PARSE_ERROR, f"Invalid JSON: {e}"
            ) from e

    @property
    def is_connected(self) -> bool:
        return self._connected and self._ws is not None


class MockTransport(MCPTransport):
    """Mock transport for testing."""

    def __init__(self, responses: list[dict[str, Any]] | None = None):
        self.responses = list(responses) if responses else []
        self.sent_messages: list[dict[str, Any]] = []
        self._connected = False
        self._response_index = 0

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def send(self, message: dict[str, Any]) -> None:
        self.sent_messages.append(message)

    async def receive(self) -> dict[str, Any]:
        if self._response_index < len(self.responses):
            response = self.responses[self._response_index]
            self._response_index += 1
            return response
        raise MCPConnectionError("No more mock responses")

    def add_response(self, response: dict[str, Any]) -> None:
        """Add a mock response."""
        self.responses.append(response)

    @property
    def is_connected(self) -> bool:
        return self._connected


# =============================================================================
# MCP Client
# =============================================================================


@dataclass
class MCPClientConfig:
    """MCP client configuration."""

    name: str = "agentic-brain-client"
    version: str = "1.0.0"
    timeout: float = 30.0
    reconnect_attempts: int = 3


class MCPClient:
    """
    MCP Client for connecting to external MCP servers.

    Supports stdio and WebSocket transports for communicating with
    MCP-compatible servers.

    Usage:
        # Stdio transport
        async with MCPClient.stdio("python", "-m", "my_server") as client:
            tools = await client.list_tools()
            result = await client.call_tool("search", query="test")

        # WebSocket transport
        async with MCPClient.websocket("ws://localhost:8080") as client:
            resources = await client.list_resources()
    """

    def __init__(
        self,
        transport: MCPTransport,
        config: MCPClientConfig | None = None,
    ):
        """
        Initialize MCP client.

        Args:
            transport: Transport layer for communication
            config: Client configuration
        """
        self.transport = transport
        self.config = config or MCPClientConfig()
        self._request_id = 0
        self._server_info: MCPServerInfo | None = None
        self._capabilities: MCPCapabilities = MCPCapabilities()
        self._initialized = False
        self._pending_requests: dict[str | int, asyncio.Future] = {}

    @classmethod
    def stdio(
        cls,
        *command: str,
        cwd: str | None = None,
        config: MCPClientConfig | None = None,
    ) -> MCPClient:
        """
        Create client with stdio transport.

        Args:
            *command: Command and arguments to run
            cwd: Working directory
            config: Client configuration

        Returns:
            MCPClient instance
        """
        transport = StdioTransport(list(command), cwd=cwd)
        return cls(transport, config)

    @classmethod
    def websocket(
        cls,
        url: str,
        config: MCPClientConfig | None = None,
    ) -> MCPClient:
        """
        Create client with WebSocket transport.

        Args:
            url: WebSocket URL
            config: Client configuration

        Returns:
            MCPClient instance
        """
        transport = WebSocketTransport(url)
        return cls(transport, config)

    @classmethod
    def mock(
        cls,
        responses: list[dict[str, Any]] | None = None,
        config: MCPClientConfig | None = None,
    ) -> MCPClient:
        """
        Create client with mock transport for testing.

        Args:
            responses: List of mock responses
            config: Client configuration

        Returns:
            MCPClient instance
        """
        transport = MockTransport(responses)
        return cls(transport, config)

    def _next_id(self) -> int:
        """Generate next request ID."""
        self._request_id += 1
        return self._request_id

    async def _send_request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Send a request and wait for response.

        Args:
            method: Method name
            params: Method parameters

        Returns:
            Response result

        Raises:
            MCPProtocolError: On error response
            MCPTimeoutError: On timeout
        """
        request_id = self._next_id()
        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params:
            request["params"] = params

        await self.transport.send(request)

        try:
            response = await asyncio.wait_for(
                self.transport.receive(),
                timeout=self.config.timeout,
            )
        except TimeoutError:
            raise MCPTimeoutError(f"Timeout waiting for response to {method}")

        if "error" in response:
            error = response["error"]
            raise MCPProtocolError(
                error.get("code", -1),
                error.get("message", "Unknown error"),
                error.get("data"),
            )

        return response.get("result")

    async def _send_notification(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Send a notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params:
            notification["params"] = params
        await self.transport.send(notification)

    async def connect(self) -> None:
        """Connect to the MCP server and initialize."""
        await self.transport.connect()

        # Send initialize request
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "clientInfo": {
                    "name": self.config.name,
                    "version": self.config.version,
                },
                "capabilities": {},
            },
        )

        # Store server info
        if result and "serverInfo" in result:
            info = result["serverInfo"]
            self._server_info = MCPServerInfo(
                name=info.get("name", "unknown"),
                version=info.get("version", "1.0.0"),
                protocol_version=result.get("protocolVersion", "2024-11-05"),
            )

        # Send initialized notification
        await self._send_notification("notifications/initialized")

        self._initialized = True
        logger.info(f"Connected to MCP server: {self._server_info}")

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        await self.transport.disconnect()
        self._initialized = False

    async def __aenter__(self) -> MCPClient:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.disconnect()

    @property
    def server_info(self) -> MCPServerInfo | None:
        """Get server information."""
        return self._server_info

    @property
    def is_connected(self) -> bool:
        """Check if connected and initialized."""
        return self._initialized and self.transport.is_connected

    # =========================================================================
    # Tool Methods
    # =========================================================================

    async def list_tools(self) -> list[MCPTool]:
        """
        List available tools from the server.

        Returns:
            List of MCPTool objects
        """
        result = await self._send_request("tools/list")

        tools = []
        for tool_data in result.get("tools", []):
            tool = MCPTool(
                name=tool_data.get("name", ""),
                description=tool_data.get("description", ""),
                parameters=tool_data.get("inputSchema", {}),
            )
            tools.append(tool)

        self._capabilities.tools = tools
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> Any:
        """
        Call a tool on the server.

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            Tool result (usually a list of content items)
        """
        result = await self._send_request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )

        return result.get("content", [])

    # =========================================================================
    # Resource Methods
    # =========================================================================

    async def list_resources(self) -> list[MCPResource]:
        """
        List available resources from the server.

        Returns:
            List of MCPResource objects
        """
        result = await self._send_request("resources/list")

        resources = []
        for res_data in result.get("resources", []):
            resource = MCPResource(
                uri=res_data.get("uri", ""),
                name=res_data.get("name", ""),
                description=res_data.get("description"),
                mime_type=res_data.get("mimeType", "text/plain"),
            )
            resources.append(resource)

        self._capabilities.resources = resources
        return resources

    async def read_resource(self, uri: str) -> MCPResourceContent:
        """
        Read a resource from the server.

        Args:
            uri: Resource URI

        Returns:
            Resource content
        """
        result = await self._send_request(
            "resources/read",
            {"uri": uri},
        )

        contents = result.get("contents", [])
        if not contents:
            return MCPResourceContent(uri=uri)

        content = contents[0]
        return MCPResourceContent(
            uri=content.get("uri", uri),
            mime_type=content.get("mimeType", "text/plain"),
            text=content.get("text"),
            blob=content.get("blob"),
        )

    async def subscribe_resource(self, uri: str) -> None:
        """Subscribe to resource updates."""
        await self._send_request("resources/subscribe", {"uri": uri})

    async def unsubscribe_resource(self, uri: str) -> None:
        """Unsubscribe from resource updates."""
        await self._send_request("resources/unsubscribe", {"uri": uri})

    # =========================================================================
    # Prompt Methods
    # =========================================================================

    async def list_prompts(self) -> list[MCPPrompt]:
        """
        List available prompts from the server.

        Returns:
            List of MCPPrompt objects
        """
        result = await self._send_request("prompts/list")

        prompts = []
        for prompt_data in result.get("prompts", []):
            arguments = []
            for arg_data in prompt_data.get("arguments", []):
                from .types import MCPPromptArgument

                arguments.append(
                    MCPPromptArgument(
                        name=arg_data.get("name", ""),
                        description=arg_data.get("description"),
                        required=arg_data.get("required", True),
                    )
                )

            prompt = MCPPrompt(
                name=prompt_data.get("name", ""),
                description=prompt_data.get("description"),
                arguments=arguments,
            )
            prompts.append(prompt)

        self._capabilities.prompts = prompts
        return prompts

    async def get_prompt(
        self,
        name: str,
        arguments: dict[str, str] | None = None,
    ) -> list[MCPPromptMessage]:
        """
        Get a prompt with filled arguments.

        Args:
            name: Prompt name
            arguments: Prompt arguments

        Returns:
            List of prompt messages
        """
        result = await self._send_request(
            "prompts/get",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )

        messages = []
        for msg_data in result.get("messages", []):
            content = msg_data.get("content", {})
            text = (
                content.get("text", "") if isinstance(content, dict) else str(content)
            )
            messages.append(
                MCPPromptMessage(
                    role=msg_data.get("role", "user"),
                    content=text,
                )
            )

        return messages

    # =========================================================================
    # Utility Methods
    # =========================================================================

    async def ping(self) -> bool:
        """
        Ping the server to check connectivity.

        Returns:
            True if server responds
        """
        try:
            await self._send_request("ping")
            return True
        except Exception:
            return False

    async def get_capabilities(self) -> MCPCapabilities:
        """
        Get all server capabilities.

        Returns:
            MCPCapabilities object with tools, resources, and prompts
        """
        # Fetch all capability lists
        with contextlib.suppress(MCPProtocolError):
            await self.list_tools()

        with contextlib.suppress(MCPProtocolError):
            await self.list_resources()

        with contextlib.suppress(MCPProtocolError):
            await self.list_prompts()

        return self._capabilities


__all__ = [
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
