#!/usr/bin/env python3
"""
Brain Core MCP Server - Lightweight Essential Tools
====================================================

Fast, focused server with just the essential brain tools.
Uses connection pooling and caching for maximum speed.

Tools (30):
- Neo4j queries (search, status, ask)
- JIRA basics (get, search, sprint)  
- Bitbucket (PRs, commits)
- Brain health & sync

Start: python server.py
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# Add brain to path
sys.path.insert(0, os.path.expanduser('~/brain'))

from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/brain/.env'))

# MCP protocol
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Core utilities (new!)
from core.neo4j_pool import query, query_single, query_value, health_check as neo4j_health
from core.mcp_cache import cache, cached
from core.fuzzy_search import fuzzy_ratio, fuzzy_filter

# Brain data
from core_data.neo4j_claude import brain_data
from core_data.core import CoreData

# Lazy-loaded core
_core: Optional[CoreData] = None

def get_core() -> CoreData:
    global _core
    if _core is None:
        _core = CoreData()
    return _core


# Create server
server = Server("brain-core")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """Essential brain tools - fast and focused."""
    return [
        # === NEO4J ESSENTIALS ===
        Tool(
            name="ask",
            description="Quick question about brain data. Uses fuzzy search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Natural language question"}
                },
                "required": ["question"]
            }
        ),
        Tool(
            name="search",
            description="Search all brain data (emails, teams, jira) with fuzzy matching.",
            inputSchema={
                "type": "object",
                "properties": {
                    "term": {"type": "string", "description": "Search term (typos OK)"}
                },
                "required": ["term"]
            }
        ),
        Tool(
            name="status",
            description="Get brain status - Neo4j health, node counts, cache stats.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="neo4j_query",
            description="Run raw Cypher query.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cypher": {"type": "string", "description": "Cypher query"}
                },
                "required": ["cypher"]
            }
        ),
        Tool(
            name="neo4j_emails",
            description="Get recent emails from Neo4j.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sender": {"type": "string"},
                    "subject": {"type": "string"},
                    "limit": {"type": "integer", "default": 20}
                }
            }
        ),
        Tool(
            name="neo4j_teams",
            description="Get Teams messages.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sender": {"type": "string"},
                    "contains": {"type": "string"}
                }
            }
        ),
        
        # === JIRA ESSENTIALS ===
        Tool(
            name="jira_get",
            description="Get JIRA ticket by key.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "e.g. SD-1330"}
                },
                "required": ["key"]
            }
        ),
        Tool(
            name="jira_search",
            description="Search JIRA with JQL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "jql": {"type": "string"},
                    "max": {"type": "integer", "default": 20}
                },
                "required": ["jql"]
            }
        ),
        Tool(
            name="jira_sprint",
            description="Get current sprint status.",
            inputSchema={"type": "object", "properties": {}}
        ),
        
        # === BITBUCKET ESSENTIALS ===
        Tool(
            name="bitbucket_prs",
            description="List open PRs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "default": "OPEN"}
                }
            }
        ),
        Tool(
            name="bitbucket_pr",
            description="Get PR details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "number": {"type": "integer"}
                },
                "required": ["number"]
            }
        ),
        
        # === CACHE CONTROL ===
        Tool(
            name="cache_stats",
            description="Get cache statistics.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="cache_clear",
            description="Clear cache (pattern optional).",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Prefix to clear, or all if empty"}
                }
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls with caching."""
    try:
        result = await _execute_tool(name, arguments)
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)}))]


async def _execute_tool(name: str, args: Dict[str, Any]) -> Any:
    """Execute tool with caching where appropriate."""
    
    # === NEO4J TOOLS ===
    if name == "ask":
        return brain_data.ask(args["question"])
    
    elif name == "search":
        # Check cache first
        cache_key = f"search:{args['term']}"
        cached_result = cache.get(cache_key)
        if cached_result:
            cached_result["_cached"] = True
            return cached_result
        
        result = brain_data.search(args["term"])
        cache.set(cache_key, result, ttl=120)  # 2 min cache
        return result
    
    elif name == "status":
        neo4j = neo4j_health()
        return {
            "neo4j": neo4j,
            "cache": cache.stats(),
            "timestamp": datetime.now().isoformat()
        }
    
    elif name == "neo4j_query":
        return query(args["cypher"])
    
    elif name == "neo4j_emails":
        return brain_data.emails(
            sender=args.get("sender"),
            subject=args.get("subject"),
            limit=args.get("limit", 20)
        )
    
    elif name == "neo4j_teams":
        return brain_data.teams(
            sender=args.get("sender"),
            contains=args.get("contains")
        )
    
    # === JIRA TOOLS ===
    elif name == "jira_get":
        key = args["key"].upper()
        cache_key = f"jira:{key}"
        cached = cache.get(cache_key)
        if cached:
            cached["_cached"] = True
            return cached
        
        core = get_core()
        result = core.jira.get_ticket(key)
        cache.set(cache_key, result, ttl=300)  # 5 min cache
        return result
    
    elif name == "jira_search":
        core = get_core()
        return core.jira.search_tickets(
            jql=args["jql"],
            max_results=args.get("max", 20)
        )
    
    elif name == "jira_sprint":
        cache_key = "jira:sprint"
        cached = cache.get(cache_key)
        if cached:
            cached["_cached"] = True
            return cached
        
        core = get_core()
        result = core.jira.get_sprint_status()
        cache.set(cache_key, result, ttl=600)  # 10 min cache
        return result
    
    # === BITBUCKET TOOLS ===
    elif name == "bitbucket_prs":
        core = get_core()
        return core.bitbucket.get_pull_requests(state=args.get("state", "OPEN"))
    
    elif name == "bitbucket_pr":
        core = get_core()
        return core.bitbucket.get_pr_details(args["number"])
    
    # === CACHE TOOLS ===
    elif name == "cache_stats":
        return cache.stats()
    
    elif name == "cache_clear":
        pattern = args.get("pattern")
        cleared = cache.invalidate(pattern)
        return {"cleared": cleared, "pattern": pattern or "all"}
    
    else:
        return {"error": f"Unknown tool: {name}"}


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
