#!/usr/bin/env python3
"""
🔐 Continuity MCP Server - Clock Chain Session Persistence
==========================================================

MCP server providing session continuity tools using the blockchain-secured
clock chain system.

TOOLS:
- continuity_save: Save checkpoint (the 'sav' command)
- continuity_recover: Recover session (the 'rem' command)
- continuity_verify: Verify chain integrity
- continuity_proof: Get cryptographic proof
- continuity_status: Get system status
- continuity_history: View recent checkpoints
- continuity_repair: Repair corrupted chain
- continuity_backup: Create backup

USAGE:
    # Start server
    python server.py

    # Or run directly with stdio
    mcp run server.py

CONFIG (add to mcp-config.json):
    {
        "mcpServers": {
            "continuity": {
                "command": "python",
                "args": ["server.py"]
            }
        }
    }
"""

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add brain paths for imports
BRAIN_ROOT = Path.home() / "brain"
sys.path.insert(0, str(BRAIN_ROOT))
sys.path.insert(0, str(BRAIN_ROOT / "core"))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("ERROR: FastMCP not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# Import continuity API
try:
    from core.continuity import (
        BlockSummary,
        ContinuityAPI,
        CryptoProof,
        RepairResult,
        SaveResult,
        SessionState,
        SystemStatus,
        VerifyResult,
        get_api,
    )
except ImportError as e:
    print(f"ERROR: Could not import continuity API: {e}", file=sys.stderr)

    # Fallback - define minimal stubs for testing
    class ContinuityAPI:
        pass


# ============ Initialize MCP Server ============

mcp = FastMCP("continuity")

# Global API instance
_api: Optional[ContinuityAPI] = None


def get_continuity_api() -> ContinuityAPI:
    """Get or create the ContinuityAPI instance"""
    global _api
    if _api is None:
        _api = get_api()
    return _api


# ============ Helper Functions ============


def safe_asdict(obj: Any) -> Dict:
    """Safely convert dataclass to dict, handling nested objects"""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    elif isinstance(obj, dict):
        return obj
    elif isinstance(obj, list):
        return [safe_asdict(item) for item in obj]
    else:
        return str(obj)


def format_todos_for_display(todos: List[Dict]) -> str:
    """Format todos for readable display"""
    if not todos:
        return "No todos"

    lines = []
    status_icons = {"pending": "⏳", "in_progress": "▶️", "done": "✅", "blocked": "🚫"}

    for todo in todos:
        icon = status_icons.get(todo.get("status", "pending"), "•")
        title = todo.get("title", todo.get("id", "Untitled"))
        lines.append(f"  {icon} {title}")

    return "\n".join(lines)


def parse_todos_from_string(todos_str: str) -> List[Dict]:
    """Parse todos from various string formats"""
    if not todos_str:
        return []

    # Try JSON first
    try:
        parsed = json.loads(todos_str)
        if isinstance(parsed, list):
            return parsed
        elif isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    # Parse line by line
    todos = []
    for line in todos_str.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        # Remove common prefixes
        for prefix in ["- ", "* ", "• ", "[ ] ", "[x] ", "✅ ", "⏳ ", "▶️ ", "🚫 "]:
            if line.startswith(prefix):
                line = line[len(prefix) :]
                break

        # Create todo object
        todos.append({"id": f"todo-{len(todos)}", "title": line, "status": "pending"})

    return todos


def parse_learnings_from_string(learnings_str: str) -> List[str]:
    """Parse learnings from string"""
    if not learnings_str:
        return []

    # Try JSON first
    try:
        parsed = json.loads(learnings_str)
        if isinstance(parsed, list):
            return [str(l) for l in parsed]
    except json.JSONDecodeError:
        pass

    # Parse line by line
    learnings = []
    for line in learnings_str.strip().split("\n"):
        line = line.strip()
        if line:
            # Remove common prefixes
            for prefix in ["- ", "* ", "• "]:
                if line.startswith(prefix):
                    line = line[len(prefix) :]
                    break
            learnings.append(line)

    return learnings


# ============ MCP Tools ============


@mcp.tool()
def continuity_save(
    summary: str, todos: str = None, learnings: str = None, context: str = None
) -> dict:
    """
    📍 Save checkpoint to continuity chain (the 'sav' command)

    Creates a blockchain-secured checkpoint of your current session state.
    Use this before restarting, at natural breaks, or when told to 'wrap up'.

    Args:
        summary: Brief description of current work (required)
        todos: Todo items - JSON array or newline-separated list
        learnings: Key insights - JSON array or newline-separated list
        context: Additional context data as JSON

    Returns:
        Save result with block hash and chain info

    Examples:
        continuity_save("Working on DNB bass synthesis")
        continuity_save("PR review complete", todos="- Fix tests\\n- Update docs")
        continuity_save("Session end", learnings='["Noisia uses 5 saws", "Filter key is resonance"]')
    """
    api = get_continuity_api()

    # Parse inputs
    todos_list = parse_todos_from_string(todos) if todos else []
    learnings_list = parse_learnings_from_string(learnings) if learnings else []

    # Parse context
    context_dict = {}
    if context:
        try:
            context_dict = json.loads(context)
        except json.JSONDecodeError:
            context_dict = {"raw": context}

    # Save
    result = api.save(
        summary=summary,
        todos=todos_list,
        learnings=learnings_list,
        context=context_dict,
        force=True,
    )

    return {
        "success": result.success,
        "block_hash": result.block_hash[:16] + "..." if result.block_hash else "",
        "block_index": result.block_index,
        "chain_height": result.chain_height,
        "message": result.message,
        "timestamp": result.timestamp,
        "todos_saved": len(todos_list),
        "learnings_saved": len(learnings_list),
    }


@mcp.tool()
def continuity_recover() -> dict:
    """
    🔄 Recover from continuity chain (the 'rem' command)

    Loads your previous session state with full verification.
    Use this on session start or after a restart.

    Returns:
        Recovered session state including todos, learnings, and next actions

    Example:
        state = continuity_recover()
        if state['recovered']:
            print(f"Resuming: {state['summary']}")
    """
    api = get_continuity_api()

    state = api.recover()

    if not state:
        return {
            "recovered": False,
            "message": "No previous session found",
            "chain_height": api.chain.height,
        }

    # Determine next action
    pending_todos = [
        t for t in state.todos if t.get("status") in ("pending", "in_progress")
    ]
    blocked_todos = [t for t in state.todos if t.get("status") == "blocked"]

    if blocked_todos:
        next_action = f"⚠️ Resolve blocker: {blocked_todos[0].get('title', 'Unknown')}"
    elif pending_todos:
        in_progress = [t for t in state.todos if t.get("status") == "in_progress"]
        if in_progress:
            next_action = f"▶️ Continue: {in_progress[0].get('title', 'Unknown')}"
        else:
            next_action = f"🎯 Start: {pending_todos[0].get('title', 'Unknown')}"
    else:
        next_action = "✅ All clear - no pending todos!"

    return {
        "recovered": True,
        "session_id": state.session_id,
        "summary": state.summary,
        "timestamp": state.timestamp,
        "chain_verified": state.chain_verified,
        "chain_height": state.chain_height,
        "block_hash": state.block_hash[:16] + "...",
        "todos": {
            "total": len(state.todos),
            "pending": len([t for t in state.todos if t.get("status") == "pending"]),
            "in_progress": len(
                [t for t in state.todos if t.get("status") == "in_progress"]
            ),
            "done": len([t for t in state.todos if t.get("status") == "done"]),
            "blocked": len(blocked_todos),
            "list": state.todos,
        },
        "learnings": state.learnings,
        "blockers": state.blockers,
        "context": state.context,
        "next_action": next_action,
        "previous_session": state.previous_session,
    }


@mcp.tool()
def continuity_verify() -> dict:
    """
    ✅ Verify chain integrity

    Checks all blocks for valid hashes and chain links.
    Detects any tampering or corruption.

    Returns:
        Verification result with integrity score
    """
    api = get_continuity_api()

    result = api.verify()

    return {
        "valid": result.valid,
        "chain_height": result.chain_height,
        "blocks_verified": result.blocks_verified,
        "integrity_score": f"{result.integrity_score * 100:.1f}%",
        "first_invalid_block": result.first_invalid_block,
        "error_message": result.error_message,
        "repair_possible": result.repair_possible,
        "status": (
            "✅ Chain verified"
            if result.valid
            else f"❌ Chain broken at block {result.first_invalid_block}"
        ),
    }


@mcp.tool()
def continuity_proof(block_index: int = None) -> dict:
    """
    🔐 Get cryptographic proof for a block

    Returns proof that can verify session authenticity.
    Useful for auditing or blockchain anchoring.

    Args:
        block_index: Block to get proof for (default: latest)

    Returns:
        Cryptographic proof with hashes and signatures
    """
    api = get_continuity_api()

    try:
        proof = api.get_proof(block_index)

        return {
            "success": True,
            "block_hash": proof.block_hash,
            "block_index": proof.block_index,
            "previous_hash": proof.previous_hash,
            "merkle_root": proof.merkle_root,
            "timestamp": proof.timestamp,
            "chain_height": proof.chain_height,
            "genesis_hash": proof.genesis_hash[:16] + "...",
            "proof_signature": proof.proof_signature,
            "zk_commitment": proof.zk_commitment,
        }
    except ValueError as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def continuity_status() -> dict:
    """
    📊 Get continuity system status

    Returns comprehensive system health including chain stats,
    storage size, and health score.

    Returns:
        System status with all metrics
    """
    api = get_continuity_api()

    status = api.status()

    # Format storage size
    size_bytes = status.storage_size_bytes
    if size_bytes < 1024:
        size_str = f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        size_str = f"{size_bytes / 1024:.1f} KB"
    else:
        size_str = f"{size_bytes / (1024 * 1024):.1f} MB"

    return {
        "chain_height": status.chain_height,
        "chain_verified": status.chain_verified,
        "current_session": status.current_session[:30] + "...",
        "last_save": status.last_save,
        "storage_size": size_str,
        "storage_bytes": size_bytes,
        "total_todos": status.total_todos,
        "total_learnings": status.total_learnings,
        "forks_count": status.forks_count,
        "consensus_status": status.consensus_status,
        "health_score": f"{status.health_score * 100:.0f}%",
        "health_emoji": (
            "🟢"
            if status.health_score >= 0.9
            else "🟡" if status.health_score >= 0.7 else "🔴"
        ),
    }


@mcp.tool()
def continuity_history(limit: int = 10) -> dict:
    """
    📜 Get recent checkpoints

    Returns summarized view of recent session saves.

    Args:
        limit: Number of entries to return (default: 10)

    Returns:
        List of recent checkpoints with timestamps and summaries
    """
    api = get_continuity_api()

    history = api.get_history(limit)

    entries = []
    for h in history:
        entries.append(
            {
                "index": h.index,
                "block_hash": h.block_hash,
                "timestamp": h.timestamp,
                "summary": h.summary,
                "todos": h.todo_count,
                "learnings": h.learning_count,
                "session": h.session_id[:20] + "...",
            }
        )

    return {
        "count": len(entries),
        "limit": limit,
        "chain_height": api.chain.height,
        "history": entries,
    }


@mcp.tool()
def continuity_repair() -> dict:
    """
    🔧 Attempt to repair corrupted chain

    Creates a backup and attempts to fix chain integrity issues.
    Use this if verify reports problems.

    Returns:
        Repair result with actions taken
    """
    api = get_continuity_api()

    result = api.repair()

    return {
        "success": result.success,
        "blocks_repaired": result.blocks_repaired,
        "blocks_removed": result.blocks_removed,
        "new_chain_height": result.new_chain_height,
        "backup_created": result.backup_created,
        "message": result.message,
        "action": "✅ Repair complete" if result.success else "❌ Repair failed",
    }


@mcp.tool()
def continuity_backup() -> dict:
    """
    💾 Create backup of chain

    Creates a timestamped backup of the entire chain.
    Keeps last 20 backups automatically.

    Returns:
        Backup path and chain stats
    """
    api = get_continuity_api()

    backup_path = api.backup()
    backups = api.list_backups()

    return {
        "success": True,
        "backup_path": backup_path,
        "chain_height": api.chain.height,
        "total_backups": len(backups),
        "recent_backups": backups[:5],
        "message": f"💾 Backup created with {api.chain.height} blocks",
    }


@mcp.tool()
def continuity_restore(backup_path: str) -> dict:
    """
    📥 Restore chain from backup

    Restores the chain from a previous backup file.
    WARNING: This replaces the current chain!

    Args:
        backup_path: Path to backup file

    Returns:
        Restore result
    """
    api = get_continuity_api()

    # Create backup of current state first
    current_backup = api.backup()

    # Attempt restore
    success = api.restore(backup_path)

    if success:
        return {
            "success": True,
            "restored_from": backup_path,
            "new_chain_height": api.chain.height,
            "safety_backup": current_backup,
            "message": "✅ Chain restored successfully",
        }
    else:
        return {
            "success": False,
            "error": "Failed to restore from backup",
            "backup_path": backup_path,
            "message": "❌ Restore failed - backup may be corrupted",
        }


@mcp.tool()
def continuity_list_backups() -> dict:
    """
    📋 List available backups

    Shows all backup files with timestamps and sizes.

    Returns:
        List of available backups
    """
    api = get_continuity_api()

    backups = api.list_backups()

    return {
        "count": len(backups),
        "backups": backups,
        "message": f"Found {len(backups)} backups",
    }


@mcp.tool()
def continuity_export_blockchain() -> dict:
    """
    ⛓️ Export for blockchain anchoring

    Exports minimal data (hashes only) for anchoring to
    a public blockchain like Ethereum or Bitcoin.
    Privacy-preserving - no content exposed.

    Returns:
        Blockchain anchor data
    """
    api = get_continuity_api()

    anchor = api.export_for_blockchain()

    return {
        "chain_id": anchor.chain_id,
        "version": anchor.version,
        "genesis_hash": (
            anchor.genesis_hash[:16] + "..." if anchor.genesis_hash else None
        ),
        "tip_hash": anchor.tip_hash[:16] + "..." if anchor.tip_hash else None,
        "chain_height": anchor.chain_height,
        "merkle_roots_count": len(anchor.merkle_roots),
        "timestamp": anchor.timestamp,
        "signature": anchor.signature,
        "message": "Ready for blockchain anchoring (hashes only, no content)",
    }


@mcp.tool()
def continuity_get_block(index: int) -> dict:
    """
    🔍 Get specific block by index

    Retrieves full details of a specific block.

    Args:
        index: Block index (0 = genesis)

    Returns:
        Block details or error
    """
    api = get_continuity_api()

    block = api.get_block(index)

    if not block:
        return {
            "success": False,
            "error": f"Block {index} not found",
            "chain_height": api.chain.height,
        }

    return {
        "success": True,
        "index": block.index,
        "block_hash": block.block_hash,
        "previous_hash": block.previous_hash[:16] + "...",
        "merkle_root": block.merkle_root[:16] + "...",
        "timestamp": block.iso_time,
        "session_id": block.session_id,
        "summary": block.summary,
        "todos": block.todos,
        "learnings": block.learnings,
        "context": block.context,
    }


@mcp.tool()
def continuity_compact() -> dict:
    """
    🗜️ Compact storage

    Removes old backups and optimizes storage.
    Keeps last 5 backups.

    Returns:
        Compaction result
    """
    api = get_continuity_api()

    # Get size before
    size_before = api.storage.get_storage_size()
    backups_before = len(api.list_backups())

    # Compact
    api.compact()

    # Get size after
    size_after = api.storage.get_storage_size()
    backups_after = len(api.list_backups())

    saved = size_before - size_after

    return {
        "success": True,
        "size_before": size_before,
        "size_after": size_after,
        "bytes_saved": saved,
        "backups_removed": backups_before - backups_after,
        "backups_remaining": backups_after,
        "message": f"🗜️ Compacted - saved {saved} bytes, removed {backups_before - backups_after} old backups",
    }


# ============ Main Entry Point ============

if __name__ == "__main__":
    print("🔐 Continuity MCP Server starting...", file=sys.stderr)
    print("   Chain file: ~/.brain-continuity/chain.json", file=sys.stderr)

    # Initialize API to check chain
    try:
        api = get_continuity_api()
        print(f"   Chain height: {api.chain.height} blocks", file=sys.stderr)

        verify = api.verify()
        if verify.valid:
            print("   ✅ Chain verified", file=sys.stderr)
        else:
            print("   ⚠️ Chain has issues - run continuity_repair", file=sys.stderr)
    except Exception as e:
        print(f"   ⚠️ API init error: {e}", file=sys.stderr)

    # Run the MCP server
    mcp.run()
