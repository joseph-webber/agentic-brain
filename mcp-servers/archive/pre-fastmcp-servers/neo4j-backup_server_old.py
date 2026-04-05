#!/usr/bin/env python3
"""
Neo4j iCloud Backup MCP Server
==============================

MCP server for Neo4j backup operations via Claude.

TOOLS (12 total):
1. backup_neo4j - Run full backup to iCloud
2. backup_status - Get backup system status
3. backup_list - List all backups
4. backup_browse - Browse backup contents
5. backup_compare - Compare two backups
6. backup_verify - Verify backup integrity
7. backup_restore - Restore from backup
8. backup_health - Health report
9. backup_metrics - Performance metrics
10. backup_estimate - Estimate backup size
11. backup_simulate_gfs - Simulate retention
12. backup_self_test - Run self-test

Start with: python server.py
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

# Add brain to path
sys.path.insert(0, os.path.expanduser("~/brain"))
sys.path.insert(0, os.path.expanduser("~/brain/tools/neo4j-backup"))

# Load environment
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/brain/.env"))

# MCP protocol
# Import backup functions
from importlib import import_module

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# Lazy import backup module
_backup_module = None


def get_backup_module():
    """Lazy load backup module to avoid import issues."""
    global _backup_module
    if _backup_module is None:
        spec = import_module("neo4j-icloud-backup".replace("-", "_"))
        _backup_module = spec
    return _backup_module


# Create MCP server
server = Server("neo4j-backup")

# Backup script path
BACKUP_SCRIPT = os.path.expanduser("~/brain/tools/neo4j-backup/neo4j-icloud-backup.py")


def run_backup_command(command: str, *args) -> Dict[str, Any]:
    """Run a backup command and return result."""
    cmd = ["python3", BACKUP_SCRIPT, command] + list(args)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300  # 5 min timeout
        )
        output = result.stdout + result.stderr

        # Try to parse JSON output
        try:
            # Find JSON in output
            lines = output.strip().split("\n")
            json_lines = []
            in_json = False
            for line in lines:
                if line.strip().startswith("{") or line.strip().startswith("["):
                    in_json = True
                if in_json:
                    json_lines.append(line)
                if in_json and (
                    line.strip().endswith("}") or line.strip().endswith("]")
                ):
                    break

            if json_lines:
                return {
                    "success": result.returncode == 0,
                    "data": json.loads("\n".join(json_lines)),
                    "output": output,
                }
        except json.JSONDecodeError:
            pass

        return {"success": result.returncode == 0, "output": output}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out (5 min limit)"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@server.list_tools()
async def list_tools() -> List[Tool]:
    """List available Neo4j backup tools - 12 total."""
    return [
        Tool(
            name="backup_neo4j",
            description="Run a full Neo4j backup to iCloud. Uses v4.0 ultimate backup with encryption, GFS retention, and verification.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="backup_status",
            description="Get full Neo4j backup system status including last backup time, total backups, disk space, and health status.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="backup_list",
            description="List all Neo4j backups on iCloud with dates and sizes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max number of backups to return (default: 10)",
                    }
                },
                "required": [],
            },
        ),
        Tool(
            name="backup_browse",
            description="Browse a backup's contents without restoring. Shows node labels, relationship types, and sample data.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Backup filename (e.g., neo4j-backup-20260223_230246.json.gz)",
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional: Filter by label (e.g., 'Email', 'Ticket')",
                    },
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="backup_compare",
            description="Compare two backups to see what changed (nodes/relationships added, removed, modified).",
            inputSchema={
                "type": "object",
                "properties": {
                    "backup1": {
                        "type": "string",
                        "description": "First backup filename",
                    },
                    "backup2": {
                        "type": "string",
                        "description": "Second backup filename",
                    },
                },
                "required": ["backup1", "backup2"],
            },
        ),
        Tool(
            name="backup_verify",
            description="Verify a backup's integrity and test if it can be restored.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Backup filename to verify",
                    }
                },
                "required": ["filename"],
            },
        ),
        Tool(
            name="backup_restore",
            description="Restore Neo4j from a backup. CAUTION: This will replace current data!",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "Backup filename to restore",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be true to confirm restore",
                    },
                },
                "required": ["filename", "confirm"],
            },
        ),
        Tool(
            name="backup_health",
            description="Get backup system health report including status, metrics, and any issues.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="backup_metrics",
            description="Get detailed backup performance metrics (size trends, throughput, backup types).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="backup_estimate",
            description="Estimate the size of the next backup based on current Neo4j data.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="backup_simulate_gfs",
            description="Simulate GFS (Grandfather-Father-Son) retention policy to preview which backups would be kept/deleted.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="backup_self_test",
            description="Run comprehensive self-test of the backup system (config, connections, encryption, scheduler).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Execute a backup tool."""

    try:
        # Get backup directory
        backup_dir = os.path.expanduser(
            "~/Library/Mobile Documents/com~apple~CloudDocs/brain-backups/neo4j"
        )

        if name == "backup_neo4j":
            result = run_backup_command("backup")
            return [
                TextContent(
                    type="text",
                    text=f"Backup Result:\n{json.dumps(result, indent=2, default=str)}",
                )
            ]

        elif name == "backup_status":
            result = run_backup_command("status")
            return [
                TextContent(
                    type="text",
                    text=f"Backup Status:\n{result.get('output', str(result))}",
                )
            ]

        elif name == "backup_list":
            result = run_backup_command("list")
            output = result.get("output", "")
            limit = arguments.get("limit", 10)
            lines = output.strip().split("\n")
            limited = "\n".join(lines[:limit]) if lines else "No backups found"
            return [
                TextContent(
                    type="text",
                    text=f"Backups ({len(lines)} total, showing {min(limit, len(lines))}):\n{limited}",
                )
            ]

        elif name == "backup_browse":
            filename = arguments.get("filename", "")
            query = arguments.get("query", "")

            # Find full path if just filename given
            if not filename.startswith("/"):
                filename = os.path.join(backup_dir, filename)

            args = [filename]
            if query:
                args.append(query)

            result = run_backup_command("browse", *args)
            return [
                TextContent(
                    type="text",
                    text=f"Backup Contents:\n{json.dumps(result.get('data', result), indent=2, default=str)}",
                )
            ]

        elif name == "backup_compare":
            backup1 = arguments.get("backup1", "")
            backup2 = arguments.get("backup2", "")

            # Find full paths
            if not backup1.startswith("/"):
                backup1 = os.path.join(backup_dir, backup1)
            if not backup2.startswith("/"):
                backup2 = os.path.join(backup_dir, backup2)

            result = run_backup_command("compare", backup1, backup2)
            return [
                TextContent(
                    type="text",
                    text=f"Backup Comparison:\n{json.dumps(result.get('data', result), indent=2, default=str)}",
                )
            ]

        elif name == "backup_verify":
            filename = arguments.get("filename", "")
            if not filename.startswith("/"):
                filename = os.path.join(backup_dir, filename)

            result = run_backup_command("verify", filename)
            return [
                TextContent(
                    type="text",
                    text=f"Verification Result:\n{result.get('output', str(result))}",
                )
            ]

        elif name == "backup_restore":
            filename = arguments.get("filename", "")
            confirm = arguments.get("confirm", False)

            if not confirm:
                return [
                    TextContent(
                        type="text",
                        text="⚠️ RESTORE BLOCKED: You must set confirm=true to restore. This will REPLACE all current Neo4j data!",
                    )
                ]

            if not filename.startswith("/"):
                filename = os.path.join(backup_dir, filename)

            result = run_backup_command("full-restore", filename, "--confirm")
            return [
                TextContent(
                    type="text",
                    text=f"Restore Result:\n{json.dumps(result.get('data', result), indent=2, default=str)}",
                )
            ]

        elif name == "backup_health":
            result = run_backup_command("health")
            return [
                TextContent(
                    type="text",
                    text=f"Health Report:\n{result.get('output', str(result))}",
                )
            ]

        elif name == "backup_metrics":
            result = run_backup_command("perf")
            return [
                TextContent(
                    type="text",
                    text=f"Performance Metrics:\n{json.dumps(result.get('data', result), indent=2, default=str)}",
                )
            ]

        elif name == "backup_estimate":
            result = run_backup_command("estimate")
            return [
                TextContent(
                    type="text",
                    text=f"Backup Estimate:\n{json.dumps(result.get('data', result), indent=2, default=str)}",
                )
            ]

        elif name == "backup_simulate_gfs":
            result = run_backup_command("simulate-gfs")
            return [
                TextContent(
                    type="text",
                    text=f"GFS Simulation:\n{json.dumps(result.get('data', result), indent=2, default=str)}",
                )
            ]

        elif name == "backup_self_test":
            result = run_backup_command("self-test")
            return [
                TextContent(
                    type="text",
                    text=f"Self-Test Result:\n{result.get('output', str(result))}",
                )
            ]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
