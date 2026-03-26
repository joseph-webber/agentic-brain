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
MCP Server Entry Point.

Run with: python -m agentic_brain.mcp

Usage:
    # Basic usage (uses environment variables)
    python -m agentic_brain.mcp

    # With arguments
    python -m agentic_brain.mcp --neo4j-uri bolt://localhost:7687 --neo4j-password your-password-here

    # Different LLM model
    python -m agentic_brain.mcp --llm-model llama3.2:3b

    # Verbose logging
    python -m agentic_brain.mcp --log-level DEBUG

    # Show available tools
    python -m agentic_brain.mcp --list-tools
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="python -m agentic_brain.mcp",
        description="Agentic Brain MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run with default settings
    python -m agentic_brain.mcp

    # Connect to Neo4j
    python -m agentic_brain.mcp --neo4j-uri bolt://localhost:7687 --neo4j-password your-password-here

    # Use different LLM
    python -m agentic_brain.mcp --llm-model llama3.2:3b --ollama-host http://localhost:11434

Environment Variables:
    NEO4J_URI          Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_USER         Neo4j username (default: neo4j)
    NEO4J_PASSWORD     Neo4j password
    NEO4J_DATABASE     Neo4j database name (default: neo4j)
    LLM_PROVIDER       LLM provider (default: ollama)
    LLM_MODEL          LLM model name (default: llama3.1:8b)
    OLLAMA_HOST        Ollama host URL (default: http://localhost:11434)
    SESSION_DIR        Directory for session storage
    LOG_LEVEL          Logging level (default: INFO)
""",
    )

    # Server info
    parser.add_argument(
        "--name",
        default=os.getenv("AGENTIC_MCP_NAME", "agentic-brain"),
        help="Server name (default: agentic-brain)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    # Neo4j configuration
    neo4j_group = parser.add_argument_group("Neo4j Configuration")
    neo4j_group.add_argument(
        "--neo4j-uri",
        default=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j connection URI",
    )
    neo4j_group.add_argument(
        "--neo4j-user",
        default=os.getenv("NEO4J_USER", "neo4j"),
        help="Neo4j username",
    )
    neo4j_group.add_argument(
        "--neo4j-password",
        default=os.getenv("NEO4J_PASSWORD", ""),
        help="Neo4j password",
    )
    neo4j_group.add_argument(
        "--neo4j-database",
        default=os.getenv("NEO4J_DATABASE", "neo4j"),
        help="Neo4j database name",
    )

    # LLM configuration
    llm_group = parser.add_argument_group("LLM Configuration")
    llm_group.add_argument(
        "--llm-provider",
        default=os.getenv("LLM_PROVIDER", "ollama"),
        choices=["ollama", "openai", "anthropic", "openrouter"],
        help="LLM provider",
    )
    llm_group.add_argument(
        "--llm-model",
        default=os.getenv("LLM_MODEL", "llama3.1:8b"),
        help="LLM model name",
    )
    llm_group.add_argument(
        "--ollama-host",
        default=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        help="Ollama host URL",
    )

    # Session configuration
    session_group = parser.add_argument_group("Session Configuration")
    session_group.add_argument(
        "--session-dir",
        default=os.getenv("SESSION_DIR"),
        help="Directory for session storage",
    )
    session_group.add_argument(
        "--session-timeout",
        type=int,
        default=int(os.getenv("SESSION_TIMEOUT", "3600")),
        help="Session timeout in seconds",
    )
    session_group.add_argument(
        "--no-persist-sessions",
        action="store_true",
        help="Disable session persistence",
    )

    # Logging
    log_group = parser.add_argument_group("Logging")
    log_group.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level",
    )
    log_group.add_argument(
        "--log-file",
        default=os.getenv("LOG_FILE"),
        help="Log file path",
    )

    # Mode options
    mode_group = parser.add_argument_group("Mode Options")
    mode_group.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Run server in async mode",
    )
    mode_group.add_argument(
        "--list-tools",
        action="store_true",
        help="List available tools and exit",
    )
    mode_group.add_argument(
        "--health-check",
        action="store_true",
        help="Run health check and exit",
    )

    return parser.parse_args()


def list_tools(server: AgenticMCPServer) -> None:
    """Print available tools."""
    server.initialize()
    tools = server.tools

    print(f"\nAvailable Tools ({len(tools)}):\n")
    print("-" * 60)

    for tool in tools:
        name = tool["name"]
        desc = tool["description"]
        params = tool.get("inputSchema", {}).get("properties", {})
        required = tool.get("inputSchema", {}).get("required", [])

        print(f"\n{name}")
        print(f"  {desc}")

        if params:
            print("  Parameters:")
            for param_name, param_info in params.items():
                req = "*" if param_name in required else " "
                ptype = param_info.get("type", "any")
                pdesc = param_info.get("description", "")
                print(f"    {req} {param_name}: {ptype} - {pdesc}")

    print("\n" + "-" * 60)
    print("* = required parameter")


def run_health_check(server: AgenticMCPServer) -> None:
    """Run health check and print results."""
    from .tools import health_check

    server.initialize()

    # Health check is already registered, just call it
    result = health_check()
    data = json.loads(result)

    print("\nHealth Check Results:\n")
    print("-" * 40)
    print(f"Status: {data['status'].upper()}")
    print(f"Timestamp: {data['timestamp']}")
    print("\nComponents:")

    for component, status in data["components"].items():
        status_str = status.get("status", "unknown")
        icon = "✓" if status_str == "ok" else "✗" if status_str == "error" else "○"
        print(f"  {icon} {component}: {status_str}")

        if status_str == "error" and "error" in status:
            print(f"      Error: {status['error']}")

    if "issues" in data:
        print(f"\nIssues: {', '.join(data['issues'])}")

    print("-" * 40)

    # Exit with appropriate code
    sys.exit(0 if data["status"] == "healthy" else 1)


def main() -> None:
    """Main entry point."""
    from .server import AgenticMCPServer, ServerConfig

    args = parse_args()

    # Build config from args
    config = ServerConfig(
        name=args.name,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        neo4j_database=args.neo4j_database,
        llm_provider=args.llm_provider,
        llm_model=args.llm_model,
        ollama_host=args.ollama_host,
        session_dir=args.session_dir,
        session_timeout=args.session_timeout,
        persist_sessions=not args.no_persist_sessions,
        log_level=args.log_level,
        log_file=args.log_file,
    )

    # Create server
    server = AgenticMCPServer(config)

    # Handle special modes
    if args.list_tools:
        list_tools(server)
        return

    if args.health_check:
        run_health_check(server)
        return

    # Run server
    try:
        if args.use_async:
            asyncio.run(server.run_async())
        else:
            server.run()
    except KeyboardInterrupt:
        print("\nShutdown requested...", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
