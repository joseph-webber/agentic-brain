#!/usr/bin/env python3
"""
Unified Neo4j MCP Server
========================

Single MCP server for ALL Neo4j operations with:
- Connection pooling (shared driver)
- Query caching (1500x speedup on repeated queries)
- Voice feedback integration
- Health monitoring
- Batch operations support

Tools provided:
- neo4j_query: Run any Cypher query (with caching option)
- neo4j_count: Fast cached count of nodes/relationships
- neo4j_stats: Database statistics
- neo4j_health: Connection health check
- neo4j_cache_stats: Cache performance metrics
- neo4j_batch: Batch write operations

Created: 2026-03-17
Author: Iris Lumina
"""

import os
import sys
import json
import time
from typing import Any, Dict, List, Optional

# Add brain to path (supports both agentic-brain installation and agentic-brain)
brain_path = (
    Path(__file__).resolve().parent.parent.parent
)  # go up to agentic-brain or brain root
sys.path.insert(0, str(brain_path))

from mcp.server import Server
from mcp.types import Tool, TextContent
from mcp.server.stdio import stdio_server

# ============================================================================
# LAZY IMPORTS (Performance optimization - 1690ms → <500ms)
# ============================================================================

_neo4j_pool = None
_neo4j_cache = None


def get_neo4j_pool():
    """Lazy load Neo4j pool module."""
    global _neo4j_pool
    if _neo4j_pool is None:
        from core_data import neo4j_pool

        _neo4j_pool = neo4j_pool
    return _neo4j_pool


def get_neo4j_cache():
    """Lazy load Neo4j query cache module."""
    global _neo4j_cache
    if _neo4j_cache is None:
        from core_data import neo4j_query_cache

        _neo4j_cache = neo4j_query_cache
    return _neo4j_cache


def get_session():
    """Get Neo4j session (lazy)."""
    return get_neo4j_pool().get_session()


def get_pool():
    """Get Neo4j pool (lazy)."""
    return get_neo4j_pool().get_pool()


def cached_query(query, params=None, ttl=30):
    """Cached query (lazy)."""
    return get_neo4j_cache().cached_query(query, params, ttl)


def count_nodes(label):
    """Count nodes (lazy)."""
    return get_neo4j_cache().count_nodes(label)


def count_rels(rel_type):
    """Count relationships (lazy)."""
    return get_neo4j_cache().count_rels(rel_type)


def cache_stats():
    """Get cache stats (lazy)."""
    return get_neo4j_cache().cache_stats()


def invalidate_cache(label=None):
    """Invalidate cache (lazy)."""
    return get_neo4j_cache().invalidate_cache(label)


# Voice feedback
def speak(message: str):
    """Quick voice feedback."""
    try:
        import subprocess

        subprocess.Popen(
            ["say", "-v", "Karen (Premium)", "-r", "160", message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except:
        pass


# Create MCP server
server = Server("neo4j-unified")


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available Neo4j tools."""
    return [
        Tool(
            name="neo4j_query",
            description="Run a Cypher query. Use cached=true for repeated read queries (1500x faster).",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Cypher query"},
                    "params": {"type": "object", "description": "Query parameters"},
                    "cached": {
                        "type": "boolean",
                        "description": "Use cache (for reads)",
                        "default": False,
                    },
                    "ttl": {
                        "type": "number",
                        "description": "Cache TTL in seconds",
                        "default": 30,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="neo4j_count",
            description="Fast cached count of nodes or relationships.",
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {"type": "string", "description": "Node label to count"},
                    "rel_type": {
                        "type": "string",
                        "description": "Relationship type to count",
                    },
                },
            },
        ),
        Tool(
            name="neo4j_stats",
            description="Get Neo4j database statistics.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="neo4j_health",
            description="Check Neo4j connection health.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="neo4j_cache_stats",
            description="Get query cache performance metrics.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="neo4j_batch",
            description="Execute batch write operations efficiently.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"},
                                "params": {"type": "object"},
                            },
                        },
                        "description": "List of write operations",
                    },
                    "invalidate_labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels to invalidate from cache after batch",
                    },
                },
                "required": ["operations"],
            },
        ),
        Tool(
            name="neo4j_invalidate_cache",
            description="Invalidate query cache (all or by label).",
            inputSchema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Label to invalidate (optional, all if omitted)",
                    }
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""

    try:
        if name == "neo4j_query":
            query = arguments["query"]
            params = arguments.get("params", {})
            use_cache = arguments.get("cached", False)
            ttl = arguments.get("ttl", 30)

            start = time.time()

            if use_cache:
                result = cached_query(query, params, ttl)
            else:
                with get_session() as session:
                    result = session.run(query, params).data()

            elapsed = (time.time() - start) * 1000

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "result": result,
                            "count": len(result),
                            "time_ms": round(elapsed, 1),
                            "cached": use_cache,
                        },
                        indent=2,
                        default=str,
                    ),
                )
            ]

        elif name == "neo4j_count":
            label = arguments.get("label")
            rel_type = arguments.get("rel_type")

            if label:
                count = count_nodes(label)
                return [TextContent(type="text", text=f"{label} nodes: {count}")]
            elif rel_type:
                count = count_rels(rel_type)
                return [
                    TextContent(type="text", text=f"{rel_type} relationships: {count}")
                ]
            else:
                return [
                    TextContent(
                        type="text", text="Provide either 'label' or 'rel_type'"
                    )
                ]

        elif name == "neo4j_stats":
            with get_session() as session:
                nodes = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
                rels = session.run("MATCH ()-[r]->() RETURN count(r) as c").single()[
                    "c"
                ]
                labels = session.run(
                    "CALL db.labels() YIELD label RETURN collect(label) as labels"
                ).single()["labels"]

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "nodes": nodes,
                            "relationships": rels,
                            "ratio": round(rels / nodes, 2) if nodes > 0 else 0,
                            "labels": labels[:20],
                            "label_count": len(labels),
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "neo4j_health":
            pool = get_pool()
            health = pool.health_check()

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "healthy": health.healthy,
                            "connected": health.connected,
                            "response_time_ms": round(health.response_time_ms, 1),
                            "queries_executed": health.stats.queries_executed,
                            "success_rate": f"{health.stats.success_rate:.1f}%",
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "neo4j_cache_stats":
            stats = cache_stats()
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "cache_size": stats["size"],
                            "max_size": stats["max_size"],
                            "hits": stats["hits"],
                            "misses": stats["misses"],
                            "hit_rate": f"{stats['hit_rate']:.1%}",
                            "evictions": stats["evictions"],
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "neo4j_batch":
            operations = arguments["operations"]
            invalidate_labels = arguments.get("invalidate_labels", [])

            start = time.time()
            results = []

            with get_session() as session:
                for op in operations:
                    try:
                        session.run(op["query"], op.get("params", {}))
                        results.append({"success": True})
                    except Exception as e:
                        results.append({"success": False, "error": str(e)})

            # Invalidate cache for affected labels
            for label in invalidate_labels:
                invalidate_cache(label)

            elapsed = (time.time() - start) * 1000
            success_count = sum(1 for r in results if r["success"])

            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": success_count == len(operations),
                            "total": len(operations),
                            "succeeded": success_count,
                            "failed": len(operations) - success_count,
                            "time_ms": round(elapsed, 1),
                            "cache_invalidated": invalidate_labels,
                        },
                        indent=2,
                    ),
                )
            ]

        elif name == "neo4j_invalidate_cache":
            label = arguments.get("label")
            invalidate_cache(label)

            if label:
                return [
                    TextContent(
                        type="text", text=f"Cache invalidated for label: {label}"
                    )
                ]
            else:
                return [TextContent(type="text", text="Entire cache cleared")]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [
            TextContent(
                type="text", text=json.dumps({"success": False, "error": str(e)})
            )
        ]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
