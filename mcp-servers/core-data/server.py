#!/usr/bin/env python3
"""
Core Data MCP Server
====================

Auto-exposes ALL core_data modules as MCP tools.
No manual wiring needed - add to core_data, it becomes an MCP tool!

Usage:
    python server.py

Tools are named: {module}_{method}
Example: teams_send_message, jira_get_ticket, bitbucket_get_pull_requests
"""

import os
import sys
import json
import asyncio
import inspect
import importlib
from typing import Any, Dict, List, Optional

# Add brain to path
sys.path.insert(0, os.path.expanduser("~/brain"))

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# Modules to expose (add more as needed)
EXPOSED_MODULES = {
    "teams": {
        "class": "TeamsAPI",
        "factory": "get_teams",
        "description": "Microsoft Teams messaging",
    },
    "jira": {
        "class": "JiraProvider",
        "factory": "get_jira",
        "description": "JIRA ticket management",
    },
    "bitbucket": {
        "class": "BitBucketProvider",
        "factory": "get_bitbucket",
        "description": "Bitbucket PRs and repos",
    },
    "github": {
        "class": "GitHubProvider",
        "factory": "get_github",
        "description": "GitHub repos and commits",
    },
    "outlook": {
        "class": "Outlook",
        "factory": None,  # Direct instantiation
        "description": "Outlook email",
    },
    "freqtrade": {
        "class": "FreqTradeProvider",
        "factory": "get_freqtrade",
        "description": "Trading bots",
    },
    "sage_tracker": {
        "class": "SageTracker",
        "factory": None,
        "description": "Sage/Intacct failure tracking",
    },
    "neo4j_context": {
        "class": "ContextManager",
        "factory": "get_context_manager",
        "description": "Context offloading to prevent context overflow",
    },
}

# Methods to skip (internal/private)
SKIP_METHODS = {"close", "driver", "neo4j", "observer", "events", "session"}


def get_type_hint(param) -> str:
    """Convert Python type hint to JSON schema type"""
    hint = param.annotation
    if hint == inspect.Parameter.empty:
        return "string"

    hint_str = str(hint)
    if "int" in hint_str:
        return "integer"
    elif "bool" in hint_str:
        return "boolean"
    elif "float" in hint_str:
        return "number"
    elif "list" in hint_str.lower() or "List" in hint_str:
        return "array"
    elif "dict" in hint_str.lower() or "Dict" in hint_str:
        return "object"
    return "string"


def build_tool_schema(method) -> Dict:
    """Build JSON schema from method signature"""
    sig = inspect.signature(method)
    properties = {}
    required = []

    for name, param in sig.parameters.items():
        if name == "self":
            continue

        prop = {"type": get_type_hint(param)}

        # Add description from docstring if available
        if method.__doc__:
            # Try to extract param description
            prop["description"] = f"Parameter: {name}"

        properties[name] = prop

        # Required if no default
        if param.default == inspect.Parameter.empty:
            required.append(name)

    schema = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required

    return schema


class CoreDataMCP:
    def __init__(self, discover_now: bool = False):
        self.instances = {}  # Lazy-loaded module instances
        self.tools = []
        self.tool_map = {}  # tool_name -> (module, method_name)
        self._discovered = False

        # Only discover on init if explicitly requested (for testing)
        if discover_now:
            self._discover_tools()

    def ensure_discovered(self):
        """Lazy discovery - called when tools are first needed."""
        if not self._discovered:
            self._discover_tools()
            self._discovered = True

    def _discover_tools(self):
        """Discover all tools from core_data modules"""
        for mod_name, config in EXPOSED_MODULES.items():
            try:
                # Import the module
                module = importlib.import_module(f"core_data.{mod_name}")

                # Get the class
                cls = getattr(module, config["class"])

                # Get all public methods
                for method_name in dir(cls):
                    if method_name.startswith("_"):
                        continue
                    if method_name in SKIP_METHODS:
                        continue

                    method = getattr(cls, method_name)
                    if not callable(method):
                        continue

                    # Build tool
                    tool_name = f"{mod_name}_{method_name}"
                    description = (
                        f"{config['description']}: {method_name.replace('_', ' ')}"
                    )

                    if method.__doc__:
                        # Use first line of docstring
                        description = method.__doc__.strip().split("\n")[0]

                    schema = build_tool_schema(method)

                    tool = Tool(
                        name=tool_name, description=description, inputSchema=schema
                    )

                    self.tools.append(tool)
                    self.tool_map[tool_name] = (mod_name, method_name)

            except Exception as e:
                print(f"Warning: Could not load {mod_name}: {e}", file=sys.stderr)

    def _get_instance(self, mod_name: str):
        """Get or create module instance"""
        if mod_name not in self.instances:
            config = EXPOSED_MODULES[mod_name]
            module = importlib.import_module(f"core_data.{mod_name}")

            if config["factory"]:
                factory = getattr(module, config["factory"])
                self.instances[mod_name] = factory()
            else:
                cls = getattr(module, config["class"])
                self.instances[mod_name] = cls()

        return self.instances[mod_name]

    def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Execute a tool"""
        if tool_name not in self.tool_map:
            return {"error": f"Unknown tool: {tool_name}"}

        mod_name, method_name = self.tool_map[tool_name]

        try:
            instance = self._get_instance(mod_name)
            method = getattr(instance, method_name)
            result = method(**arguments)
            return result
        except Exception as e:
            return {"error": str(e), "tool": tool_name}


# Create server
app = Server("core-data")
core_data = CoreDataMCP()


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools"""
    core_data.ensure_discovered()  # Lazy discovery on first list_tools call
    tools = core_data.tools.copy()
    # Add the reality_check tool
    tools.append(
        Tool(
            name="reality_check",
            description="Check data freshness across all sources. Returns reality score and staleness report.",
            inputSchema={"type": "object", "properties": {}},
        )
    )
    # Add context offloading tools (direct access for convenience)
    tools.append(
        Tool(
            name="context_store",
            description="Store context to Neo4j to prevent context overflow. Call after tool results or significant events.",
            inputSchema={
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "description": "Type: tool_result, user_message, file_read, error, learning, checkpoint",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Brief summary of the context",
                    },
                    "full_content": {
                        "type": "string",
                        "description": "Optional full content (stored separately)",
                    },
                    "priority": {
                        "type": "string",
                        "description": "critical, high, normal, low, ephemeral (default: normal)",
                    },
                    "ttl_hours": {
                        "type": "number",
                        "description": "Custom TTL in hours (overrides priority default)",
                    },
                },
                "required": ["event_type", "summary"],
            },
        )
    )
    tools.append(
        Tool(
            name="context_recall",
            description="Recall recent context from Neo4j. Use when switching topics or needing past information.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Optional topic filter"},
                    "last_n": {
                        "type": "integer",
                        "description": "Number of items to recall (default: 10)",
                    },
                },
            },
        )
    )
    tools.append(
        Tool(
            name="context_search",
            description="Search past context in Neo4j.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default: 20)",
                    },
                },
                "required": ["query"],
            },
        )
    )
    tools.append(
        Tool(
            name="context_compact",
            description="Proactively compact context - expire old chunks and free up space. Call when feeling context pressure.",
            inputSchema={"type": "object", "properties": {}},
        )
    )
    tools.append(
        Tool(
            name="context_health",
            description="Check context system health - counts, expiring items, stats.",
            inputSchema={"type": "object", "properties": {}},
        )
    )
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Dict) -> List[TextContent]:
    """Execute a tool"""
    core_data.ensure_discovered()  # Lazy discovery on first tool call
    # Handle special tools
    if name == "reality_check":
        result = await reality_check()
    elif name == "context_store":
        from core_data.neo4j_context import context_store

        result = context_store(
            event_type=arguments.get("event_type", "unknown"),
            summary=arguments.get("summary", ""),
            full_content=arguments.get("full_content"),
            priority=arguments.get("priority", "normal"),
            ttl_hours=arguments.get("ttl_hours"),
        )
    elif name == "context_recall":
        from core_data.neo4j_context import context_recall

        result = context_recall(
            topic=arguments.get("topic"), last_n=arguments.get("last_n", 10)
        )
    elif name == "context_search":
        from core_data.neo4j_context import context_search

        result = context_search(
            query=arguments.get("query", ""), limit=arguments.get("limit", 20)
        )
    elif name == "context_compact":
        from core_data.neo4j_context import context_compact

        result = context_compact()
    elif name == "context_health":
        from core_data.neo4j_context import context_health

        result = context_health()
    else:
        result = core_data.call_tool(name, arguments or {})

    # Format result
    if isinstance(result, (dict, list)):
        text = json.dumps(result, indent=2, default=str)
    else:
        text = str(result)

    return [TextContent(type="text", text=text)]


async def reality_check() -> str:
    """Check data freshness across all sources. Returns reality score and staleness report."""
    import subprocess
    import shutil

    # Try to find reality-check in PATH or relative to brain root
    reality_check_path = shutil.which("reality-check")
    if not reality_check_path:
        brain_root = Path(__file__).resolve().parent.parent.parent
        reality_check_path = brain_root / "bin" / "reality-check"

    try:
        result = subprocess.run(
            [str(reality_check_path), "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout or result.stderr or "Reality check failed"
    except Exception as e:
        return f"Reality check error: {e}"


async def main():
    """Run the MCP server"""
    print(
        f"Core Data MCP Server starting with {len(core_data.tools)} tools...",
        file=sys.stderr,
    )
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
