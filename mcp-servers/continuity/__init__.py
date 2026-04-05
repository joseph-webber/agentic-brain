"""
🔐 Continuity MCP Server Package
================================

MCP server for clock chain session continuity.

Start the server:
    python -m mcp_servers.continuity.server
    
Or:
    cd ~/brain/mcp-servers/continuity && python server.py
"""

from .server import (
    continuity_backup,
    continuity_compact,
    continuity_export_blockchain,
    continuity_get_block,
    continuity_history,
    continuity_list_backups,
    continuity_proof,
    continuity_recover,
    continuity_repair,
    continuity_restore,
    continuity_save,
    continuity_status,
    continuity_verify,
    mcp,
)

__all__ = [
    "mcp",
    "continuity_save",
    "continuity_recover",
    "continuity_verify",
    "continuity_proof",
    "continuity_status",
    "continuity_history",
    "continuity_repair",
    "continuity_backup",
    "continuity_restore",
    "continuity_list_backups",
    "continuity_export_blockchain",
    "continuity_get_block",
    "continuity_compact",
]
