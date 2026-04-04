#!/usr/bin/env python3
"""
Session Continuity MCP Server
=============================
Dedicated MCP server for session state persistence across restarts.

Key features:
- Auto-recovers state on session start
- Saves to persistent location (~/.brain-continuity/)
- Neo4j backup for cross-session context
- Git status capture
- Quick "wrap up" with auto-detection

Tools:
- session_save: Save current session state (use before restart)
- session_recover: Recover from last session (use on start)
- session_status: Show current continuity status
- session_quick_save: One-command save with auto-detection
"""

import asyncio
import json
import os
import re
import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Paths
BRAIN_ROOT = Path.home() / "brain"
CONTINUITY_DIR = Path.home() / ".brain-continuity"
STATE_FILE = CONTINUITY_DIR / "last_session.json"
HISTORY_FILE = CONTINUITY_DIR / "history.json"
NEO4J_ENABLED = True

# Ensure directory exists
CONTINUITY_DIR.mkdir(exist_ok=True)


# ==================== GIT HELPERS ====================

def run_git_command(args: List[str], cwd: str = None) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git", "--no-pager"] + args,
            capture_output=True,
            text=True,
            cwd=cwd or str(BRAIN_ROOT),
            timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_git_status() -> Dict[str, Any]:
    """Get comprehensive git status."""
    return {
        "branch": run_git_command(["branch", "--show-current"]),
        "status": run_git_command(["status", "--short"]),
        "uncommitted_count": len(run_git_command(["status", "--short"]).split("\n")) if run_git_command(["status", "--short"]) else 0,
        "last_commit": run_git_command(["log", "-1", "--oneline"]),
        "stash_count": len(run_git_command(["stash", "list"]).split("\n")) if run_git_command(["stash", "list"]) else 0
    }


def extract_jira_tickets(text: str) -> List[str]:
    """Extract JIRA ticket IDs from text."""
    if not text:
        return []
    pattern = r'[A-Z]{2,10}-\d+'
    return list(set(re.findall(pattern, text)))


# ==================== SQL HELPERS ====================

def get_session_db_path() -> Optional[Path]:
    """Find the active session's SQLite database."""
    # Check for copilot session state
    session_root = Path.home() / ".copilot" / "session-state"
    if session_root.exists():
        # Find most recent session folder
        sessions = sorted(session_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        for session in sessions:
            db_path = session / "session.db"
            if db_path.exists():
                return db_path
    return None


def get_todos_from_session() -> List[Dict]:
    """Get todos from the current session's SQL database."""
    db_path = get_session_db_path()
    if not db_path:
        return []
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if todos table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='todos'")
        if not cursor.fetchone():
            conn.close()
            return []
        
        cursor.execute("SELECT * FROM todos ORDER BY status, id")
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error reading todos: {e}")
        return []


# ==================== NEO4J HELPERS ====================

def get_neo4j_driver():
    """Get Neo4j driver if available."""
    if not NEO4J_ENABLED:
        return None
    try:
        from neo4j import GraphDatabase
        from dotenv import load_dotenv
        
        load_dotenv(BRAIN_ROOT / '.env')
        
        uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        user = os.getenv('NEO4J_USER', 'neo4j')
        password = os.getenv('NEO4J_PASSWORD', '')
        
        if not password:
            return None
        
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            session.run("RETURN 1")
        return driver
    except Exception:
        return None


def save_to_neo4j(state: Dict) -> bool:
    """Save session state to Neo4j."""
    driver = get_neo4j_driver()
    if not driver:
        return False
    
    try:
        with driver.session() as session:
            # Create or update Session node
            session.run("""
                MERGE (s:Session {id: $session_id})
                SET s.description = $description,
                    s.timestamp = datetime(),
                    s.git_branch = $git_branch,
                    s.todo_count = $todo_count,
                    s.saved_at = $saved_at
            """,
                session_id=state.get("session_id", "unknown"),
                description=state.get("description", "")[:500],
                git_branch=state.get("git", {}).get("branch", ""),
                todo_count=len(state.get("todos", [])),
                saved_at=state.get("saved_at", "")
            )
            
            # Link to JIRA tickets mentioned
            for ticket in state.get("jira_tickets", []):
                session.run("""
                    MERGE (t:Ticket {key: $key})
                    WITH t
                    MATCH (s:Session {id: $session_id})
                    MERGE (s)-[:MENTIONS]->(t)
                """,
                    key=ticket,
                    session_id=state.get("session_id", "unknown")
                )
            
            # Store learnings
            for learning in state.get("learnings", []):
                session.run("""
                    CREATE (l:Learning {
                        content: $content,
                        timestamp: datetime(),
                        session_id: $session_id
                    })
                    WITH l
                    MATCH (s:Session {id: $session_id})
                    MERGE (s)-[:LEARNED]->(l)
                """,
                    content=learning[:500],
                    session_id=state.get("session_id", "unknown")
                )
        
        driver.close()
        return True
    except Exception as e:
        print(f"Neo4j save error: {e}")
        return False


def get_recent_sessions_from_neo4j(limit: int = 5) -> List[Dict]:
    """Get recent sessions from Neo4j."""
    driver = get_neo4j_driver()
    if not driver:
        return []
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (s:Session)
                RETURN s.id as id, s.description as description, 
                       s.git_branch as branch, s.todo_count as todos,
                       toString(s.timestamp) as timestamp
                ORDER BY s.timestamp DESC
                LIMIT $limit
            """, limit=limit)
            
            sessions = [dict(r) for r in result]
        
        driver.close()
        return sessions
    except Exception:
        return []


# ==================== COMMUNICATIONS INTEGRATION ====================

def get_comms_state() -> Dict:
    """Get communications state from the communications MCP server."""
    try:
        # Import from communications server
        sys.path.insert(0, str(BRAIN_ROOT / "mcp-servers/communications"))
        from server import save_comms_state_for_continuity, get_urgent_items
        
        comms_state = save_comms_state_for_continuity()
        urgent = get_urgent_items()
        
        return {
            "pending_from_steve": comms_state.get("pending_from_steve", [])[:3],
            "unanswered_questions": comms_state.get("unanswered_questions", [])[:3],
            "active_tickets": comms_state.get("active_tickets", [])[:5],
            "urgent_count": len(urgent.get("needs_attention", [])),
            "important_people_messages": len(urgent.get("from_important_people", []))
        }
    except Exception as e:
        return {"error": str(e)}


# ==================== STATE MANAGEMENT ====================

def save_state(
    description: str = "",
    todos: List[Dict] = None,
    blockers: List[str] = None,
    learnings: List[str] = None
) -> Dict:
    """Save session state to persistent storage."""
    # Auto-detect context
    git = get_git_status()
    session_todos = todos or get_todos_from_session()
    jira_tickets = extract_jira_tickets(git.get("branch", "") + " " + git.get("last_commit", ""))
    
    # Generate session ID
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Build state object
    state = {
        "session_id": session_id,
        "saved_at": datetime.now().isoformat(),
        "description": description or f"Working on {git.get('branch', 'unknown branch')}",
        "git": git,
        "todos": session_todos,
        "blockers": blockers or [],
        "learnings": learnings or [],
        "jira_tickets": jira_tickets,
        "communications": get_comms_state()
    }
    
    # Save to file
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, default=str)
    
    # Update history
    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except Exception:
            history = []
    
    history.insert(0, {
        "session_id": session_id,
        "saved_at": state["saved_at"],
        "description": state["description"][:100],
        "todo_count": len(session_todos),
        "branch": git.get("branch", "")
    })
    history = history[:50]  # Keep last 50
    
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)
    
    # Save to Neo4j
    neo4j_saved = save_to_neo4j(state)
    
    return {
        "success": True,
        "session_id": session_id,
        "state_file": str(STATE_FILE),
        "todo_count": len(session_todos),
        "neo4j_saved": neo4j_saved,
        "summary": f"Saved session with {len(session_todos)} todos, branch: {git.get('branch', 'unknown')}"
    }


def recover_state() -> Dict:
    """Recover state from last session."""
    if not STATE_FILE.exists():
        return {
            "recovered": False,
            "message": "No previous session found"
        }
    
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        
        # Build recovery summary
        todos = state.get("todos", [])
        pending = [t for t in todos if t.get("status") in ("pending", "in_progress")]
        done = [t for t in todos if t.get("status") == "done"]
        blocked = [t for t in todos if t.get("status") == "blocked"]
        
        # Determine what to work on
        next_action = ""
        if blocked:
            next_action = f"⚠️ Blocked: {blocked[0].get('title', 'Unknown')}"
        elif pending:
            in_progress = [t for t in todos if t.get("status") == "in_progress"]
            if in_progress:
                next_action = f"▶️ Continue: {in_progress[0].get('title', 'Unknown')}"
            else:
                next_action = f"🎯 Start: {pending[0].get('title', 'Unknown')}"
        else:
            next_action = "✅ All clear - no pending todos!"
        
        # Get recent Neo4j context
        recent_sessions = get_recent_sessions_from_neo4j(3)
        
        return {
            "recovered": True,
            "session_id": state.get("session_id"),
            "saved_at": state.get("saved_at"),
            "description": state.get("description"),
            "git_branch": state.get("git", {}).get("branch"),
            "todos": {
                "pending": len(pending),
                "done": len(done),
                "blocked": len(blocked),
                "list": todos
            },
            "blockers": state.get("blockers", []),
            "learnings": state.get("learnings", []),
            "jira_tickets": state.get("jira_tickets", []),
            "communications": state.get("communications", {}),
            "next_action": next_action,
            "recent_sessions": recent_sessions
        }
    except Exception as e:
        return {
            "recovered": False,
            "error": str(e)
        }


def get_status() -> Dict:
    """Get current continuity status."""
    has_state = STATE_FILE.exists()
    state = {}
    if has_state:
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
        except Exception:
            pass
    
    history_count = 0
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, 'r') as f:
                history_count = len(json.load(f))
        except Exception:
            pass
    
    neo4j_connected = get_neo4j_driver() is not None
    
    return {
        "has_saved_state": has_state,
        "last_saved": state.get("saved_at") if has_state else None,
        "last_description": state.get("description") if has_state else None,
        "history_count": history_count,
        "neo4j_connected": neo4j_connected,
        "state_file": str(STATE_FILE),
        "continuity_dir": str(CONTINUITY_DIR)
    }


# ==================== MCP SERVER ====================

server = Server("session-continuity")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available continuity tools."""
    return [
        Tool(
            name="session_save",
            description="Save session state before restart. Captures git status, todos, and context. Use when user says 'wrap it up', 'time for restart', or 'save state'.",
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Brief description of current work"
                    },
                    "blockers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of blockers preventing progress"
                    },
                    "learnings": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Key learnings from this session"
                    }
                }
            }
        ),
        Tool(
            name="session_recover",
            description="Recover state from last session. Shows todos, context, and suggests next action. Call this on session start.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="session_status",
            description="Show current continuity status - whether state exists, when last saved, Neo4j connection.",
            inputSchema={
                "type": "object", 
                "properties": {}
            }
        ),
        Tool(
            name="session_quick_save",
            description="Quick save with auto-detection. Just captures current git state and todos without needing details. Use for fast wrap-up.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="session_history",
            description="View session save history - past checkpoints with timestamps and descriptions.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of history entries to show (default 10)"
                    }
                }
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "session_save":
            result = save_state(
                description=arguments.get("description", ""),
                blockers=arguments.get("blockers"),
                learnings=arguments.get("learnings")
            )
        
        elif name == "session_recover":
            result = recover_state()
        
        elif name == "session_status":
            result = get_status()
        
        elif name == "session_quick_save":
            result = save_state()
        
        elif name == "session_history":
            limit = arguments.get("limit", 10)
            if HISTORY_FILE.exists():
                with open(HISTORY_FILE, 'r') as f:
                    history = json.load(f)[:limit]
                result = {"history": history, "count": len(history)}
            else:
                result = {"history": [], "count": 0}
        
        else:
            result = {"error": f"Unknown tool: {name}"}
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str)
        )]
    
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)}, indent=2)
        )]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
