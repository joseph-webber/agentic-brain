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
MCP Server - Full production implementation.

A complete MCP server that:
- Imports and registers all tools from tools.py
- Has proper error handling
- Supports async operations
- Integrates with the Chatbot class

Usage:
    from agentic_brain.mcp.server import AgenticMCPServer

    server = AgenticMCPServer()
    server.initialize()
    server.run()
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# LAZY IMPORT: Neo4j pool imported inside _connect_neo4j() to avoid blocking at startup
# See: MCP_STARTUP_AUDIT.md for why lazy loading is critical

from . import MCPServer
from .tools import (
    ToolContext,
    get_all_tools,
    set_context,
)

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for the MCP server."""

    name: str = "agentic-brain"
    version: str = "1.0.0"
    description: str = "Agentic Brain MCP Server"

    # Neo4j configuration
    neo4j_uri: str = field(
        default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687")
    )
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))
    neo4j_database: str = "neo4j"

    # LLM configuration
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1:8b"
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )

    # Session configuration
    session_dir: str | None = None
    session_timeout: int = 3600
    persist_sessions: bool = True

    # Logging
    log_level: str = "INFO"
    log_file: str | None = None

    @classmethod
    def from_env(cls) -> ServerConfig:
        """Create config from environment variables."""
        return cls(
            name=os.getenv("AGENTIC_MCP_NAME", "agentic-brain"),
            version=os.getenv("AGENTIC_MCP_VERSION", "1.0.0"),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
            llm_provider=os.getenv("LLM_PROVIDER", "ollama"),
            llm_model=os.getenv("LLM_MODEL", "llama3.1:8b"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            session_dir=os.getenv("SESSION_DIR"),
            session_timeout=int(os.getenv("SESSION_TIMEOUT", "3600")),
            persist_sessions=os.getenv("PERSIST_SESSIONS", "true").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE"),
        )


class AgenticMCPServer:
    """
    Production-ready MCP server for agentic-brain.

    Features:
    - Auto-registers all tools from tools.py
    - Connects to Neo4j for persistent memory
    - Integrates with Chatbot for conversation
    - Falls back to in-memory storage when Neo4j unavailable
    - Proper error handling and logging

    Usage:
        # Simple usage
        server = AgenticMCPServer()
        server.run()

        # With custom config
        config = ServerConfig(
            neo4j_uri="bolt://myneo4j:7687",
            llm_model="llama3.2:3b"
        )
        server = AgenticMCPServer(config)
        server.run()

        # With existing resources
        server = AgenticMCPServer()
        server.initialize(
            chatbot=my_chatbot,
            memory=my_memory
        )
        server.run()
    """

    def __init__(self, config: ServerConfig | None = None) -> None:
        """
        Initialize the MCP server.

        Args:
            config: Server configuration (uses env vars if not provided)
        """
        self.config = config or ServerConfig.from_env()
        self._setup_logging()

        # Core components
        self._mcp_server: MCPServer | None = None
        self._chatbot = None
        self._memory = None
        self._session_manager = None
        self._rag_pipeline = None
        self._neo4j_driver = None

        self._initialized = False

        logger.info(
            f"AgenticMCPServer created: {self.config.name} v{self.config.version}"
        )

    def _setup_logging(self) -> None:
        """Configure logging."""
        level = getattr(logging, self.config.log_level.upper(), logging.INFO)

        handlers = [logging.StreamHandler(sys.stderr)]
        if self.config.log_file:
            handlers.append(logging.FileHandler(self.config.log_file))

        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
        )

    def _connect_neo4j(self) -> bool:
        """
        Connect to Neo4j database.

        LAZY IMPORT: Neo4j pool is imported here, not at module level,
        to avoid blocking MCP server startup. This can save 2+ seconds.

        Returns:
            True if connection successful
        """
        if not self.config.neo4j_password:
            logger.warning("No Neo4j password configured, skipping Neo4j connection")
            return False

        try:
            # LAZY IMPORT: Import here to avoid blocking MCP server startup!
            from agentic_brain.core.neo4j_pool import (
                configure_pool as configure_neo4j_pool,
                get_driver as get_shared_neo4j_driver,
            )

            configure_neo4j_pool(
                uri=self.config.neo4j_uri,
                user=self.config.neo4j_user,
                password=self.config.neo4j_password,
                database=self.config.neo4j_database,
            )
            self._neo4j_driver = get_shared_neo4j_driver()

            # Test connection
            with self._neo4j_driver.session(
                database=self.config.neo4j_database
            ) as session:
                session.run("RETURN 1")

            logger.info(f"Connected to Neo4j at {self.config.neo4j_uri}")
            return True
        except ImportError:
            logger.warning("neo4j package not installed, using in-memory storage")
            return False
        except Exception as e:
            logger.warning(f"Failed to connect to Neo4j: {e}, using in-memory storage")
            return False

    def _create_memory(self) -> Any:
        """
        Create memory store (Neo4j or in-memory fallback).

        Returns:
            Memory instance
        """
        from agentic_brain.memory import InMemoryStore, Neo4jMemory

        if self._neo4j_driver:
            try:
                memory = Neo4jMemory(
                    uri=self.config.neo4j_uri,
                    user=self.config.neo4j_user,
                    password=self.config.neo4j_password,
                    database=self.config.neo4j_database,
                )
                memory.connect()
                logger.info("Using Neo4j memory")
                return memory
            except Exception as e:
                logger.warning(f"Failed to create Neo4j memory: {e}")

        logger.info("Using in-memory storage (data will not persist)")
        return InMemoryStore()

    def _create_chatbot(self) -> Any:
        """
        Create chatbot instance.

        Returns:
            Chatbot instance
        """
        from agentic_brain.chat.chatbot import Chatbot
        from agentic_brain.chat.config import ChatConfig

        # Create config
        config = ChatConfig(
            model=self.config.llm_model,
            persist_sessions=self.config.persist_sessions,
        )

        if self.config.session_dir:
            config.session_dir = Path(self.config.session_dir)

        # Create chatbot
        chatbot = Chatbot(
            name=self.config.name,
            memory=self._memory,
            config=config,
        )

        logger.info(f"Created chatbot: {chatbot.name}")
        return chatbot

    def _create_rag_pipeline(self) -> Any | None:
        """
        Create RAG pipeline if Neo4j is available.

        Returns:
            RAGPipeline or None
        """
        if not self._neo4j_driver:
            return None

        try:
            from agentic_brain.rag import RAGPipeline

            pipeline = RAGPipeline(
                neo4j_uri=self.config.neo4j_uri,
                neo4j_user=self.config.neo4j_user,
                neo4j_password=self.config.neo4j_password,
                llm_provider=self.config.llm_provider,
                llm_model=self.config.llm_model,
            )
            logger.info("Created RAG pipeline")
            return pipeline
        except Exception as e:
            logger.warning(f"Failed to create RAG pipeline: {e}")
            return None

    def initialize(
        self,
        chatbot: Any | None = None,
        memory: Any | None = None,
        session_manager: Any | None = None,
        rag_pipeline: Any | None = None,
    ) -> None:
        """
        Initialize the server with all components.

        Args:
            chatbot: Optional existing Chatbot instance
            memory: Optional existing memory instance
            session_manager: Optional existing SessionManager
            rag_pipeline: Optional existing RAGPipeline
        """
        if self._initialized:
            logger.warning("Server already initialized")
            return

        # Connect to Neo4j
        self._connect_neo4j()

        # Use provided components or create new ones
        self._memory = memory or self._create_memory()
        self._chatbot = chatbot or self._create_chatbot()

        # Get session manager from chatbot if available
        if session_manager:
            self._session_manager = session_manager
        elif self._chatbot and hasattr(self._chatbot, "session_manager"):
            self._session_manager = self._chatbot.session_manager

        # Create RAG pipeline
        self._rag_pipeline = rag_pipeline or self._create_rag_pipeline()

        # Set up tool context
        context = ToolContext(
            chatbot=self._chatbot,
            memory=self._memory,
            session_manager=self._session_manager,
            rag_pipeline=self._rag_pipeline,
            neo4j_driver=self._neo4j_driver,
        )
        set_context(context)

        # Create MCP server and register tools
        self._mcp_server = MCPServer(
            name=self.config.name,
            version=self.config.version,
            description=self.config.description,
        )
        self._register_tools()

        self._initialized = True
        logger.info("Server initialized successfully")

    def _register_tools(self) -> None:
        """Register all tools with the MCP server."""
        tools = get_all_tools()

        for name, tool_info in tools.items():
            func = tool_info["function"]
            description = tool_info.get("description", func.__doc__ or f"Tool: {name}")

            # Register using the decorator approach (handles parameter extraction)
            self._mcp_server.tool(func)

            # Update description if provided
            if name in self._mcp_server._tools:
                self._mcp_server._tools[name].description = description

        logger.info(f"Registered {len(tools)} tools")

    def handle_request(self, request: dict) -> dict:
        """
        Handle an MCP request.

        Args:
            request: MCP request object

        Returns:
            MCP response object
        """
        if not self._initialized:
            self.initialize()

        return self._mcp_server.handle_request(request)

    async def handle_request_async(self, request: dict) -> dict:
        """
        Handle an MCP request asynchronously.

        Args:
            request: MCP request object

        Returns:
            MCP response object
        """
        if not self._initialized:
            self.initialize()

        method = request.get("method", "")

        # Handle async tool calls specially
        if method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name")

            # Check if tool has async version
            tools = get_all_tools()
            if tool_name in tools and "async_function" in tools[tool_name]:
                try:
                    async_func = tools[tool_name]["async_function"]
                    arguments = params.get("arguments", {})
                    result = await async_func(**arguments)

                    # Format response
                    if isinstance(result, str):
                        content = [{"type": "text", "text": result}]
                    elif isinstance(result, dict):
                        content = [
                            {"type": "text", "text": json.dumps(result, indent=2)}
                        ]
                    else:
                        content = [{"type": "text", "text": str(result)}]

                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {"content": content},
                    }
                except Exception as e:
                    logger.error(f"Async tool error: {e}", exc_info=True)
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {"code": -32603, "message": str(e)},
                    }

        # Fall back to sync handling
        return self._mcp_server.handle_request(request)

    def run(self) -> None:
        """
        Run the MCP server on stdio.

        Reads JSON-RPC requests from stdin, writes responses to stdout.
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"Starting MCP server: {self.config.name}")

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
            except Exception as e:
                logger.error(f"Server error: {e}", exc_info=True)

        self.shutdown()

    async def run_async(self) -> None:
        """
        Run the MCP server asynchronously.

        Uses asyncio for non-blocking I/O.
        """
        if not self._initialized:
            self.initialize()

        logger.info(f"Starting async MCP server: {self.config.name}")

        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        while True:
            try:
                line = await reader.readline()
                if not line:
                    break

                request = json.loads(line.decode().strip())
                response = await self.handle_request_async(request)

                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Server error: {e}", exc_info=True)

        self.shutdown()

    def shutdown(self) -> None:
        """Shutdown the server and cleanup resources."""
        logger.info("Shutting down MCP server")

        # Close memory connection
        if self._memory and hasattr(self._memory, "close"):
            try:
                self._memory.close()
            except Exception as e:
                logger.warning(f"Error closing memory: {e}")

        # Close Neo4j driver
        if self._neo4j_driver:
            try:
                self._neo4j_driver.close()
            except Exception as e:
                logger.warning(f"Error closing Neo4j driver: {e}")

        self._initialized = False
        logger.info("Server shutdown complete")

    @property
    def tools(self) -> list[dict]:
        """Get list of registered tools."""
        if self._mcp_server:
            return self._mcp_server.list_tools()
        return []

    def __enter__(self) -> AgenticMCPServer:
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.shutdown()


def create_server(
    neo4j_uri: str | None = None,
    neo4j_password: str | None = None,
    llm_model: str | None = None,
    **kwargs,
) -> AgenticMCPServer:
    """
    Factory function to create an MCP server.

    Args:
        neo4j_uri: Neo4j connection URI
        neo4j_password: Neo4j password
        llm_model: LLM model name
        **kwargs: Additional ServerConfig options

    Returns:
        Configured AgenticMCPServer instance

    Example:
        server = create_server(
            neo4j_uri="bolt://localhost:7687",
            neo4j_password="your-password-here",
            llm_model="llama3.2:3b"
        )
        server.run()
    """
    config = ServerConfig.from_env()

    if neo4j_uri:
        config.neo4j_uri = neo4j_uri
    if neo4j_password:
        config.neo4j_password = neo4j_password
    if llm_model:
        config.llm_model = llm_model

    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)

    return AgenticMCPServer(config)
