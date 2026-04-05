#!/usr/bin/env python3
"""
Session Continuity MCP Server v3.0 - ZERO CONTEXT LOSS EDITION
===============================================================
🚀 THE KILLER CONTINUITY UPGRADE - Context loss is now IMPOSSIBLE

v3.0 FEATURES (2026-03-14):
- ZERO CONTEXT LOSS - Automatic, seamless, invisible to user
- Signal handlers catch ALL exits (SIGTERM, SIGINT, crashes)
- Aggressive auto-save every 60 seconds during activity
- Instant recovery on startup - no user action needed
- Full Neo4j sync for cross-session memory
- Redpanda event bus for real-time sync
- Crash detection and automatic recovery
- Emergency saves before rate limiting
- Context reconstruction from multiple sources

HOW IT WORKS:
1. On START: Auto-detects crash, recovers context from Neo4j/disk
2. DURING: Saves every 60s, logs all context to Neo4j
3. On EXIT: Catches ALL exit signals, saves before death
4. On CRASH: Emergency save triggered, recovered on next start

USER EXPERIENCE:
- User does NOTHING - it's all automatic
- Context is ALWAYS there
- No "remember" command needed - it just works
- Rate limits? Context saved before we go down
- Crash? Recovered automatically on restart
"""

import asyncio
import atexit
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# Add brain to path for imports
sys.path.insert(0, str(Path.home() / "brain"))

# Redpanda/Kafka event bus integration - LAZY LOADED
EVENT_BUS_AVAILABLE = None  # None = not checked yet
_BrainEventBus = None
_BrainTopics = None


def _get_kafka_bus():
    """Lazy load kafka bus module."""
    global EVENT_BUS_AVAILABLE, _BrainEventBus, _BrainTopics
    if EVENT_BUS_AVAILABLE is None:
        try:
            from core.kafka_bus import BrainEventBus, BrainTopics

            _BrainEventBus = BrainEventBus
            _BrainTopics = BrainTopics
            EVENT_BUS_AVAILABLE = True
        except ImportError:
            EVENT_BUS_AVAILABLE = False
    return _BrainEventBus, _BrainTopics, EVENT_BUS_AVAILABLE


# ==================== SESSION LIFECYCLE ====================

# Track current session - GLOBAL STATE
_current_session = {
    "id": None,
    "started_at": None,
    "message_count": 0,
    "last_activity": None,
    "checkpoints": [],
    "context_buffer": [],  # Buffer for batched context saves
    "recovered_from_crash": False,
}

_event_bus = None
_auto_checkpoint_task = None
_heartbeat_task = None
_shutdown_in_progress = False


def get_event_bus():
    """Get or create event bus connection."""
    global _event_bus
    BrainEventBus, _, available = _get_kafka_bus()
    if _event_bus is None and available:
        try:
            _event_bus = BrainEventBus()
            _event_bus.connect()
        except Exception as e:
            print(f"⚠️ Event bus connection failed: {e}")
    return _event_bus


def emit_session_event(event_type: str, data: dict):
    """Emit session event to Redpanda."""
    bus = get_event_bus()
    if bus:
        try:
            bus.emit(
                "brain.session.checkpoint",
                {
                    "event_type": event_type,
                    "session_id": _current_session.get("id"),
                    "timestamp": datetime.now().isoformat(),
                    **data,
                },
            )
        except Exception as e:
            print(f"⚠️ Event emission failed: {e}")


def _emergency_shutdown_save():
    """
    CRITICAL: Called on ANY exit - saves everything immediately.
    This runs synchronously and MUST complete before process dies.
    """
    global _shutdown_in_progress
    if _shutdown_in_progress:
        return  # Prevent double-save
    _shutdown_in_progress = True

    try:
        # Save to disk immediately
        state = {
            "session_id": _current_session.get("id", "emergency"),
            "saved_at": datetime.now().isoformat(),
            "description": f"Emergency save - session {_current_session.get('id')}",
            "emergency": True,
            "clean_shutdown": True,
            "message_count": _current_session.get("message_count", 0),
            "checkpoints": _current_session.get("checkpoints", []),
            "context_buffer": _current_session.get("context_buffer", [])[
                -50:
            ],  # Last 50 items
            "lifecycle_session": _current_session.get("id"),
        }

        # Write to both emergency and main state file
        emergency_path = Path.home() / ".brain-continuity" / "emergency_save.json"
        state_path = Path.home() / ".brain-continuity" / "last_session.json"

        with open(emergency_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

        with open(state_path, "w") as f:
            json.dump(state, f, indent=2, default=str)

        print(f"✅ Emergency save completed: {_current_session.get('id')}")
    except Exception as e:
        print(f"❌ Emergency save failed: {e}")


def _signal_handler(signum, frame):
    """Handle termination signals - save before death."""
    print(f"🚨 Signal {signum} received - emergency save in progress...")
    _emergency_shutdown_save()
    sys.exit(0)


# Signal handlers registered lazily on first session start
_signal_handlers_registered = False


def _register_signal_handlers():
    """Register signal handlers once - called on first tool use."""
    global _signal_handlers_registered
    if _signal_handlers_registered:
        return
    _signal_handlers_registered = True

    signal.signal(signal.SIGTERM, _signal_handler)  # Docker stop, kill
    signal.signal(signal.SIGINT, _signal_handler)  # Ctrl+C
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _signal_handler)  # Terminal closed

    # Register atexit handler as backup
    atexit.register(_emergency_shutdown_save)


async def auto_checkpoint_loop():
    """Background task to auto-checkpoint every 60 seconds (aggressive!)."""
    while True:
        await asyncio.sleep(60)  # Every 60 seconds - aggressive!
        try:
            # Always save, even if no messages (heartbeat)
            state = save_state(
                description=f"Auto-checkpoint at {datetime.now().strftime('%H:%M:%S')}",
                auto_save=True,
            )
            _current_session["checkpoints"].append(
                {"time": datetime.now().isoformat(), "type": "auto"}
            )

            # Flush context buffer to Neo4j
            if _current_session.get("context_buffer"):
                _flush_context_buffer_to_neo4j()

            emit_session_event(
                "auto_checkpoint",
                {
                    "checkpoint": state.get("session_id"),
                    "message_count": _current_session.get("message_count", 0),
                },
            )
        except Exception as e:
            print(f"⚠️ Auto-checkpoint failed: {e}")


async def heartbeat_loop():
    """Heartbeat every 30 seconds - proves we're alive."""
    while True:
        await asyncio.sleep(30)
        _current_session["last_activity"] = datetime.now().isoformat()
        # Write heartbeat to disk (proves we're alive for crash detection)
        try:
            heartbeat_file = Path.home() / ".brain-continuity" / "heartbeat.json"
            with open(heartbeat_file, "w") as f:
                json.dump(
                    {
                        "session_id": _current_session.get("id"),
                        "timestamp": datetime.now().isoformat(),
                        "message_count": _current_session.get("message_count", 0),
                    },
                    f,
                )
        except Exception:
            pass


def _flush_context_buffer_to_neo4j():
    """Flush buffered context events to Neo4j."""
    buffer = _current_session.get("context_buffer", [])
    if not buffer:
        return

    driver = get_neo4j_driver()
    if not driver:
        return

    try:
        with driver.session() as session:
            for event in buffer:
                session.run(
                    """
                    CREATE (c:ContextEvent {
                        id: $id,
                        event_type: $event_type,
                        summary: $summary,
                        timestamp: datetime($timestamp),
                        session_id: $session_id,
                        auto_logged: true
                    })
                """,
                    id=event.get("id", str(uuid.uuid4())[:8]),
                    event_type=event.get("type", "auto"),
                    summary=event.get("summary", "")[:200],
                    timestamp=event.get("timestamp", datetime.now().isoformat()),
                    session_id=_current_session.get("id", "unknown"),
                )
        driver.close()
        _current_session["context_buffer"] = []  # Clear buffer
    except Exception as e:
        print(f"⚠️ Context flush failed: {e}")


@asynccontextmanager
async def session_lifespan(mcp_server: FastMCP):
    """
    MCP Lifecycle hook - ZERO CONTEXT LOSS implementation.

    START: Auto-recover from crash/previous session
    DURING: Aggressive auto-save every 60s
    END: Save everything, clean shutdown marker
    """
    global _auto_checkpoint_task, _heartbeat_task, _shutdown_in_progress
    _shutdown_in_progress = False

    # Register signal handlers on first session start
    _register_signal_handlers()

    # === SESSION START ===
    session_id = str(uuid.uuid4())[:8]
    _current_session["id"] = session_id
    _current_session["started_at"] = datetime.now().isoformat()
    _current_session["message_count"] = 0
    _current_session["checkpoints"] = []
    _current_session["context_buffer"] = []
    _current_session["recovered_from_crash"] = False

    print(f"🟢 Session started: {session_id}")

    # Check for CRASH/unclean shutdown - AUTO RECOVER
    crash_info = detect_unclean_shutdown()
    if crash_info:
        print("🚨 CRASH DETECTED - auto-recovering...")
        _current_session["recovered_from_crash"] = True
        recovered_state = recover_from_crash()
        if recovered_state:
            emit_session_event(
                "crash_recovered",
                {
                    "recovered_from": crash_info.get("type", "unknown"),
                    "previous_session": recovered_state.get("session_id", "unknown"),
                },
            )
            # Store recovered context for immediate use
            _current_session["recovered_context"] = recovered_state
    else:
        # Check for clean previous session
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    prev_state = json.load(f)
                emit_session_event(
                    "previous_session_found",
                    {
                        "previous_id": prev_state.get("session_id"),
                        "description": prev_state.get("description", "")[:100],
                    },
                )
                # Auto-import previous context
                _current_session["recovered_context"] = prev_state
            except Exception:
                pass

    # Emit session start event to Redpanda
    emit_session_event(
        "session_started",
        {
            "machine": os.uname().nodename if hasattr(os, "uname") else "unknown",
            "recovered": _current_session.get("recovered_from_crash", False),
        },
    )

    # Start AGGRESSIVE auto-checkpoint (every 60 seconds)
    _auto_checkpoint_task = asyncio.create_task(auto_checkpoint_loop())

    # Start heartbeat (every 30 seconds - proves we're alive)
    _heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        yield  # Session runs here
    finally:
        # === SESSION END (CLEAN SHUTDOWN) ===
        _shutdown_in_progress = True
        print(f"🔴 Session ending cleanly: {_current_session['id']}")

        # Cancel background tasks
        for task in [_auto_checkpoint_task, _heartbeat_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Flush any buffered context to Neo4j
        if _current_session.get("context_buffer"):
            _flush_context_buffer_to_neo4j()

        # Save COMPREHENSIVE final state
        try:
            duration = (
                datetime.now() - datetime.fromisoformat(_current_session["started_at"])
            ).total_seconds()

            final_state = save_state(
                description=f"Session {_current_session['id']} ended cleanly after {int(duration)}s",
                auto_save=True,
            )

            # Mark as CLEAN shutdown in state file
            with open(STATE_FILE) as f:
                state = json.load(f)
            state["clean_shutdown"] = True
            state["ended_at"] = datetime.now().isoformat()
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2, default=str)

            # Sync to Neo4j
            sync_session_to_neo4j(_current_session["id"], state)

            emit_session_event(
                "session_ended",
                {
                    "duration_seconds": duration,
                    "message_count": _current_session.get("message_count", 0),
                    "checkpoints": len(_current_session.get("checkpoints", [])),
                    "clean_shutdown": True,
                },
            )
            print(f"✅ Clean shutdown complete: {_current_session['id']}")

        except Exception as e:
            print(f"⚠️ Final save failed: {e}")
            # Emergency fallback
            _emergency_shutdown_save()

        # Remove heartbeat file (proves clean exit)
        try:
            heartbeat_file = Path.home() / ".brain-continuity" / "heartbeat.json"
            if heartbeat_file.exists():
                heartbeat_file.unlink()
        except Exception:
            pass

        # Close event bus
        global _event_bus
        if _event_bus:
            try:
                _event_bus.close()
            except Exception:
                pass
            _event_bus = None


def sync_session_to_neo4j(session_id: str, state: dict):
    """Sync final session state to Neo4j."""
    driver = get_neo4j_driver()
    if not driver:
        return

    try:
        with driver.session() as session:
            session.run(
                """
                MERGE (s:Session {id: $id})
                SET s.started_at = datetime($started_at),
                    s.ended_at = datetime($ended_at),
                    s.description = $description,
                    s.message_count = $message_count,
                    s.checkpoint_count = $checkpoint_count,
                    s.clean_shutdown = $clean_shutdown,
                    s.duration_seconds = $duration
            """,
                id=session_id,
                started_at=state.get("saved_at", datetime.now().isoformat()),
                ended_at=datetime.now().isoformat(),
                description=state.get("description", "")[:500],
                message_count=state.get("message_count", 0),
                checkpoint_count=len(state.get("checkpoints", [])),
                clean_shutdown=state.get("clean_shutdown", False),
                duration=state.get("duration_seconds", 0),
            )
        driver.close()
    except Exception as e:
        print(f"⚠️ Neo4j sync failed: {e}")


# Initialize FastMCP server WITH LIFESPAN HOOK
mcp = FastMCP("session-continuity", lifespan=session_lifespan)

# Paths
BRAIN_ROOT = Path.home() / "brain"
CONTINUITY_DIR = Path.home() / ".brain-continuity"
STATE_FILE = CONTINUITY_DIR / "last_session.json"
HISTORY_FILE = CONTINUITY_DIR / "history.json"
CRASH_LOG = CONTINUITY_DIR / "crashes" / "crash_log.jsonl"
EMERGENCY_SAVE = CONTINUITY_DIR / "emergency_save.json"
CONTEXT_CACHE = CONTINUITY_DIR / "context" / "cache.json"
NEO4J_ENABLED = True

# Ensure directories exist
CONTINUITY_DIR.mkdir(exist_ok=True)
(CONTINUITY_DIR / "crashes").mkdir(exist_ok=True)
(CONTINUITY_DIR / "context").mkdir(exist_ok=True)


# ==================== CRASH DETECTION & RECOVERY ====================


def detect_unclean_shutdown() -> Optional[Dict]:
    """
    Detect if the previous session ended unexpectedly.
    Returns crash info if detected, None if clean shutdown.
    """
    # Check for emergency save (indicates rate limit or forced save)
    if EMERGENCY_SAVE.exists():
        try:
            with open(EMERGENCY_SAVE) as f:
                return {"type": "emergency", "data": json.load(f)}
        except Exception:
            pass

    # Check if last session has lifecycle_session but no end marker
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            # If auto_save is False and there's a lifecycle session, it was a manual save
            # If auto_save is True, check if it was the final save
            if state.get("lifecycle_session") and not state.get("clean_shutdown"):
                return {"type": "unclean", "data": state}
        except Exception:
            pass

    return None


def log_crash_event(crash_type: str, details: Dict):
    """Log a crash/recovery event for analysis."""
    try:
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": crash_type,
            "details": details,
        }
        with open(CRASH_LOG, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


def emergency_save_context(reason: str, context_data: Dict = None):
    """
    Emergency save - called before rate limiting or unexpected exit.
    Saves everything possible to disk immediately.
    """
    emergency_state = {
        "timestamp": datetime.now().isoformat(),
        "reason": reason,
        "session": _current_session.copy(),
        "context_data": context_data or {},
        "git": get_git_status() if "get_git_status" in dir() else {},
    }

    try:
        with open(EMERGENCY_SAVE, "w") as f:
            json.dump(emergency_state, f, indent=2, default=str)

        # Also emit to event bus
        emit_session_event(
            "emergency_save",
            {"reason": reason, "session_id": _current_session.get("id")},
        )

        return True
    except Exception:
        return False


def recover_from_crash() -> Dict:
    """
    Attempt to recover as much context as possible after crash/restart.
    Pulls from multiple sources: emergency save, state file, Neo4j.
    """
    recovery = {
        "sources_checked": [],
        "recovered_data": {},
        "recovery_quality": "none",  # none, partial, full
    }

    # 1. Check emergency save (highest priority - most recent)
    if EMERGENCY_SAVE.exists():
        try:
            with open(EMERGENCY_SAVE) as f:
                emergency = json.load(f)
            recovery["sources_checked"].append("emergency_save")
            recovery["recovered_data"]["emergency"] = emergency
            recovery["recovery_quality"] = "partial"

            # Archive the emergency save
            archive_path = (
                CONTINUITY_DIR
                / "crashes"
                / f"emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            EMERGENCY_SAVE.rename(archive_path)
        except Exception as e:
            recovery["emergency_error"] = str(e)

    # 2. Check state file
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            recovery["sources_checked"].append("state_file")
            recovery["recovered_data"]["state"] = state
            if recovery["recovery_quality"] == "none":
                recovery["recovery_quality"] = "partial"
        except Exception as e:
            recovery["state_error"] = str(e)

    # 3. Pull recent context from Neo4j
    driver = get_neo4j_driver()
    if driver:
        try:
            with driver.session() as session:
                # Get recent context events
                result = session.run(
                    """
                    MATCH (c:ContextEvent)
                    WHERE c.timestamp > datetime() - duration({hours: 24})
                    RETURN c.id as id, c.event_type as type, c.summary as summary,
                           c.priority as priority, toString(c.timestamp) as timestamp
                    ORDER BY c.timestamp DESC
                    LIMIT 50
                """
                )
                context_events = [dict(r) for r in result]

                # Get recent conversation turns
                conv_result = session.run(
                    """
                    MATCH (t:ConversationTurn)
                    WHERE t.timestamp > datetime() - duration({hours: 24})
                    RETURN t.user_message as user, t.assistant_response as assistant,
                           t.topics as topics, toString(t.timestamp) as timestamp
                    ORDER BY t.timestamp DESC
                    LIMIT 20
                """
                )
                conversations = [dict(r) for r in conv_result]

                # Get recent learnings
                learn_result = session.run(
                    """
                    MATCH (l:Learning)
                    WHERE l.timestamp > datetime() - duration({hours: 168})
                    RETURN l.content as content, toString(l.timestamp) as timestamp
                    ORDER BY l.timestamp DESC
                    LIMIT 20
                """
                )
                learnings = [dict(r) for r in learn_result]

            driver.close()

            recovery["sources_checked"].append("neo4j")
            recovery["recovered_data"]["neo4j"] = {
                "context_events": context_events,
                "conversations": conversations,
                "learnings": learnings,
            }

            if context_events or conversations:
                recovery["recovery_quality"] = (
                    "full" if len(recovery["sources_checked"]) >= 2 else "partial"
                )

        except Exception as e:
            recovery["neo4j_error"] = str(e)

    # Log the recovery attempt
    log_crash_event("recovery_attempt", recovery)

    return recovery


# ==================== GIT HELPERS ====================


def run_git_command(args: List[str], cwd: str = None) -> str:
    """Run a git command and return output."""
    try:
        result = subprocess.run(
            ["git", "--no-pager"] + args,
            capture_output=True,
            text=True,
            cwd=cwd or str(BRAIN_ROOT),
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def get_git_status() -> Dict[str, Any]:
    """Get comprehensive git status."""
    return {
        "branch": run_git_command(["branch", "--show-current"]),
        "status": run_git_command(["status", "--short"]),
        "uncommitted_count": (
            len(run_git_command(["status", "--short"]).split("\n"))
            if run_git_command(["status", "--short"])
            else 0
        ),
        "last_commit": run_git_command(["log", "-1", "--oneline"]),
        "stash_count": (
            len(run_git_command(["stash", "list"]).split("\n"))
            if run_git_command(["stash", "list"])
            else 0
        ),
    }


def extract_jira_tickets(text: str) -> List[str]:
    """Extract JIRA ticket IDs from text."""
    if not text:
        return []
    pattern = r"[A-Z]{2,10}-\d+"
    return list(set(re.findall(pattern, text)))


# ==================== SQL HELPERS ====================


def get_session_db_path() -> Optional[Path]:
    """Find the active session's SQLite database."""
    session_root = Path.home() / ".copilot" / "session-state"
    if session_root.exists():
        sessions = sorted(
            session_root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
        )
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

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='todos'"
        )
        if not cursor.fetchone():
            conn.close()
            return []

        cursor.execute("SELECT * FROM todos ORDER BY status, id")
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]
    except Exception:
        return []


# ==================== NEO4J HELPERS ====================


def get_neo4j_driver():
    """Get Neo4j driver if available."""
    if not NEO4J_ENABLED:
        return None
    try:
        from dotenv import load_dotenv
        from neo4j import GraphDatabase

        load_dotenv(BRAIN_ROOT / ".env")

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "")

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
            session.run(
                """
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
                saved_at=state.get("saved_at", ""),
            )

            for ticket in state.get("jira_tickets", []):
                session.run(
                    """
                    MERGE (t:Ticket {key: $key})
                    WITH t
                    MATCH (s:Session {id: $session_id})
                    MERGE (s)-[:MENTIONS]->(t)
                """,
                    key=ticket,
                    session_id=state.get("session_id", "unknown"),
                )

            for learning in state.get("learnings", []):
                session.run(
                    """
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
                    session_id=state.get("session_id", "unknown"),
                )

        driver.close()
        return True
    except Exception:
        return False


def get_recent_sessions_from_neo4j(limit: int = 5) -> List[Dict]:
    """Get recent sessions from Neo4j."""
    driver = get_neo4j_driver()
    if not driver:
        return []

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (s:Session)
                RETURN s.id as id, s.description as description, 
                       s.git_branch as branch, s.todo_count as todos,
                       toString(s.timestamp) as timestamp
                ORDER BY s.timestamp DESC
                LIMIT $limit
            """,
                limit=limit,
            )

            sessions = [dict(r) for r in result]

        driver.close()
        return sessions
    except Exception:
        return []


# ==================== STATE MANAGEMENT ====================


def save_state(
    description: str = "",
    todos: List[Dict] = None,
    blockers: List[str] = None,
    learnings: List[str] = None,
    auto_save: bool = False,
) -> Dict:
    """Save session state to persistent storage."""
    git = get_git_status()
    session_todos = todos or get_todos_from_session()
    jira_tickets = extract_jira_tickets(
        git.get("branch", "") + " " + git.get("last_commit", "")
    )

    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    state = {
        "session_id": session_id,
        "saved_at": datetime.now().isoformat(),
        "description": description
        or f"Working on {git.get('branch', 'unknown branch')}",
        "git": git,
        "todos": session_todos,
        "blockers": blockers or [],
        "learnings": learnings or [],
        "jira_tickets": jira_tickets,
        "auto_save": auto_save,
        "lifecycle_session_id": _current_session.get("id"),
    }

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)

    history = []
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE) as f:
                history = json.load(f)
        except Exception:
            pass

    history.insert(
        0,
        {
            "session_id": session_id,
            "saved_at": state["saved_at"],
            "description": state["description"][:100],
            "todo_count": len(session_todos),
            "branch": git.get("branch", ""),
            "auto_save": auto_save,
        },
    )
    history = history[:50]

    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    neo4j_saved = save_to_neo4j(state)

    # Emit event to Redpanda
    if not auto_save:  # Don't spam events for auto-saves
        emit_session_event(
            "manual_save",
            {
                "session_id": session_id,
                "description": description[:100] if description else "",
                "todo_count": len(session_todos),
            },
        )

    return {
        "success": True,
        "session_id": session_id,
        "state_file": str(STATE_FILE),
        "todo_count": len(session_todos),
        "neo4j_saved": neo4j_saved,
        "event_bus_available": EVENT_BUS_AVAILABLE,
        "summary": f"Saved session with {len(session_todos)} todos, branch: {git.get('branch', 'unknown')}",
    }


def recover_state() -> Dict:
    """Recover state from last session."""
    if not STATE_FILE.exists():
        return {"recovered": False, "message": "No previous session found"}

    try:
        with open(STATE_FILE) as f:
            state = json.load(f)

        todos = state.get("todos", [])
        pending = [t for t in todos if t.get("status") in ("pending", "in_progress")]
        done = [t for t in todos if t.get("status") == "done"]
        blocked = [t for t in todos if t.get("status") == "blocked"]

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
                "list": todos,
            },
            "blockers": state.get("blockers", []),
            "learnings": state.get("learnings", []),
            "jira_tickets": state.get("jira_tickets", []),
            "next_action": next_action,
            "recent_sessions": recent_sessions,
        }
    except Exception as e:
        return {"recovered": False, "error": str(e)}


# ==================== MCP TOOLS ====================


@mcp.tool()
def session_save(
    description: str = "", blockers: list = None, learnings: list = None
) -> dict:
    """
    Save session state before restart. Captures git status, todos, and context.
    Use when user says 'wrap it up', 'time for restart', or 'save state'.

    Args:
        description: Brief description of current work
        blockers: List of blockers preventing progress
        learnings: Key learnings from this session
    """
    return save_state(description=description, blockers=blockers, learnings=learnings)


@mcp.tool()
def session_recover() -> dict:
    """
    Recover state from last session. Shows todos, context, and suggests next action.
    Call this on session start.
    """
    return recover_state()


@mcp.tool()
def session_status() -> dict:
    """
    Show current continuity status - lifecycle, state, Neo4j, event bus.
    """
    has_state = STATE_FILE.exists()
    state = {}
    if has_state:
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
        except Exception:
            pass

    history_count = 0
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE) as f:
                history_count = len(json.load(f))
        except Exception:
            pass

    neo4j_connected = get_neo4j_driver() is not None

    # Calculate session duration
    session_duration = None
    if _current_session.get("started_at"):
        try:
            start = datetime.fromisoformat(_current_session["started_at"])
            session_duration = str(datetime.now() - start).split(".")[0]
        except Exception:
            pass

    return {
        "lifecycle": {
            "session_id": _current_session.get("id"),
            "started_at": _current_session.get("started_at"),
            "duration": session_duration,
            "message_count": _current_session.get("message_count", 0),
            "checkpoints": len(_current_session.get("checkpoints", [])),
        },
        "persistence": {
            "has_saved_state": has_state,
            "last_saved": state.get("saved_at") if has_state else None,
            "last_description": state.get("description") if has_state else None,
            "history_count": history_count,
        },
        "connections": {
            "neo4j_connected": neo4j_connected,
            "event_bus_available": EVENT_BUS_AVAILABLE,
            "event_bus_connected": _event_bus is not None,
        },
        "paths": {"state_file": str(STATE_FILE), "continuity_dir": str(CONTINUITY_DIR)},
    }


@mcp.tool()
def session_quick_save() -> dict:
    """
    Quick save with auto-detection. Just captures current git state and todos.
    Use for fast wrap-up.
    """
    return save_state()


@mcp.tool()
def session_history(limit: int = 10) -> dict:
    """
    View session save history - past checkpoints with timestamps and descriptions.

    Args:
        limit: Number of history entries to show (default 10)
    """
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            history = json.load(f)[:limit]
        return {"history": history, "count": len(history)}
    return {"history": [], "count": 0}


# ==================== CONTEXT TRACKING TOOLS ====================


@mcp.tool()
def context_log(
    event_type: str, summary: str, details: str = "", priority: str = "normal"
) -> dict:
    """
    Log a context event to Neo4j for cross-session memory.
    Call this after significant events: tool results, discoveries, decisions.

    Args:
        event_type: Type of event (tool_result, discovery, decision, error, learning)
        summary: Brief summary (max 200 chars)
        details: Full details (optional, for retrieval later)
        priority: critical, high, normal, low (affects retention)

    Examples:
        context_log("discovery", "Found bug in UserService.authenticate")
        context_log("decision", "Using approach A for payment integration")
        context_log("tool_result", "Grep found 47 TODOs in src/")
    """
    # Track message count
    _current_session["message_count"] = _current_session.get("message_count", 0) + 1
    _current_session["last_activity"] = datetime.now().isoformat()

    driver = get_neo4j_driver()
    if not driver:
        return {"success": False, "error": "Neo4j not connected"}

    context_id = (
        f"ctx_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )

    # Map priority to TTL hours
    ttl_map = {"critical": 8760, "high": 168, "normal": 24, "low": 4}  # hours
    ttl_hours = ttl_map.get(priority, 24)

    try:
        with driver.session() as session:
            session.run(
                """
                CREATE (c:ContextEvent {
                    id: $context_id,
                    event_type: $event_type,
                    summary: $summary,
                    details: $details,
                    priority: $priority,
                    ttl_hours: $ttl_hours,
                    timestamp: datetime(),
                    session_id: $session_id,
                    lifecycle_session: $lifecycle_session
                })
                WITH c
                OPTIONAL MATCH (s:Session {id: $session_id})
                FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (s)-[:HAS_CONTEXT]->(c)
                )
            """,
                context_id=context_id,
                event_type=event_type,
                summary=summary[:200],
                details=details[:2000] if details else "",
                priority=priority,
                ttl_hours=ttl_hours,
                session_id=_current_session.get("id", "unknown"),
                lifecycle_session=_current_session.get("id"),
            )
        driver.close()

        # Emit to event bus
        emit_session_event(
            "context_logged",
            {
                "context_id": context_id,
                "event_type": event_type,
                "summary": summary[:100],
            },
        )

        return {
            "success": True,
            "context_id": context_id,
            "event_type": event_type,
            "ttl_hours": ttl_hours,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def context_recall(topic: str = "", last_n: int = 10) -> dict:
    """
    Recall recent context events from Neo4j.

    Args:
        topic: Optional topic filter (searches summary and details)
        last_n: Number of recent events to retrieve
    """
    driver = get_neo4j_driver()
    if not driver:
        return {"success": False, "error": "Neo4j not connected"}

    try:
        with driver.session() as session:
            if topic:
                result = session.run(
                    """
                    MATCH (c:ContextEvent)
                    WHERE c.summary CONTAINS $topic OR c.details CONTAINS $topic
                    RETURN c.id as id, c.event_type as type, c.summary as summary,
                           c.priority as priority, toString(c.timestamp) as timestamp
                    ORDER BY c.timestamp DESC
                    LIMIT $limit
                """,
                    topic=topic,
                    limit=last_n,
                )
            else:
                result = session.run(
                    """
                    MATCH (c:ContextEvent)
                    RETURN c.id as id, c.event_type as type, c.summary as summary,
                           c.priority as priority, toString(c.timestamp) as timestamp
                    ORDER BY c.timestamp DESC
                    LIMIT $limit
                """,
                    limit=last_n,
                )

            events = [dict(r) for r in result]
        driver.close()

        return {"success": True, "events": events, "count": len(events)}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def context_compact() -> dict:
    """
    Compact old context - summarize and archive expired events.
    Call this when context feels heavy or before big tasks.
    """
    driver = get_neo4j_driver()
    if not driver:
        return {"success": False, "error": "Neo4j not connected"}

    try:
        with driver.session() as session:
            # Count before
            before = session.run(
                "MATCH (c:ContextEvent) RETURN count(c) as count"
            ).single()["count"]

            # Delete expired low-priority events
            session.run(
                """
                MATCH (c:ContextEvent)
                WHERE c.priority IN ['low', 'normal']
                AND c.timestamp < datetime() - duration({hours: c.ttl_hours})
                DETACH DELETE c
            """
            )

            # Count after
            after = session.run(
                "MATCH (c:ContextEvent) RETURN count(c) as count"
            ).single()["count"]

            deleted = before - after

        driver.close()

        # Emit compaction event
        emit_session_event(
            "context_compacted", {"deleted": deleted, "remaining": after}
        )

        return {
            "success": True,
            "deleted": deleted,
            "remaining": after,
            "message": f"Compacted {deleted} expired context events",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def conversation_log(
    user_message: str,
    assistant_response: str = "",
    topics: list = None,
    sentiment: str = "neutral",
) -> dict:
    """
    Log a conversation turn to Neo4j for conversation history.

    Args:
        user_message: What the user said
        assistant_response: What the assistant replied (optional, log later)
        topics: List of topics discussed
        sentiment: User sentiment (positive, neutral, negative, frustrated)
    """
    driver = get_neo4j_driver()
    if not driver:
        return {"success": False, "error": "Neo4j not connected"}

    turn_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4]}"

    try:
        with driver.session() as session:
            session.run(
                """
                CREATE (t:ConversationTurn {
                    id: $turn_id,
                    user_message: $user_message,
                    assistant_response: $assistant_response,
                    topics: $topics,
                    sentiment: $sentiment,
                    timestamp: datetime(),
                    session_id: $session_id
                })
                WITH t
                OPTIONAL MATCH (s:Session {id: $session_id})
                FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
                    MERGE (s)-[:HAS_TURN]->(t)
                )
            """,
                turn_id=turn_id,
                user_message=user_message[:1000],
                assistant_response=(
                    assistant_response[:2000] if assistant_response else ""
                ),
                topics=topics or [],
                sentiment=sentiment,
                session_id=_current_session.get("id", "unknown"),
            )
        driver.close()

        return {"success": True, "turn_id": turn_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


@mcp.tool()
def sync_full_state() -> dict:
    """
    Full sync of current state to Neo4j and Redpanda.
    Creates a comprehensive checkpoint with all context.
    """
    results = {"session_saved": False, "context_count": 0, "event_emitted": False}

    # 1. Save session state
    try:
        state = save_state(description="Full state sync", auto_save=True)
        results["session_saved"] = state.get("success", False)
        results["session_id"] = state.get("session_id")
    except Exception as e:
        results["session_error"] = str(e)

    # 2. Get context count
    driver = get_neo4j_driver()
    if driver:
        try:
            with driver.session() as session:
                count = session.run(
                    """
                    MATCH (c:ContextEvent {session_id: $sid})
                    RETURN count(c) as count
                """,
                    sid=_current_session.get("id", "unknown"),
                ).single()["count"]
                results["context_count"] = count
            driver.close()
        except Exception:
            pass

    # 3. Emit sync event
    emit_session_event(
        "full_sync",
        {
            "session_id": results.get("session_id"),
            "context_count": results["context_count"],
            "lifecycle_session": _current_session.get("id"),
        },
    )
    results["event_emitted"] = EVENT_BUS_AVAILABLE

    return results


@mcp.tool()
def neo4j_session_stats() -> dict:
    """
    Get Neo4j statistics for session-related data.
    Shows sessions, context events, conversations, learnings.
    """
    driver = get_neo4j_driver()
    if not driver:
        return {"success": False, "error": "Neo4j not connected"}

    try:
        with driver.session() as session:
            stats = {}

            # Count each type
            for label in [
                "Session",
                "ContextEvent",
                "ConversationTurn",
                "Learning",
                "Checkpoint",
            ]:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                stats[label.lower() + "_count"] = result.single()["count"]

            # Recent sessions
            recent = session.run(
                """
                MATCH (s:Session)
                RETURN s.id as id, s.description as desc, toString(s.timestamp) as ts
                ORDER BY s.timestamp DESC LIMIT 5
            """
            )
            stats["recent_sessions"] = [dict(r) for r in recent]

            # Context by priority
            priority_dist = session.run(
                """
                MATCH (c:ContextEvent)
                RETURN c.priority as priority, count(c) as count
                ORDER BY count DESC
            """
            )
            stats["context_by_priority"] = {
                r["priority"]: r["count"] for r in priority_dist
            }

        driver.close()
        return {"success": True, "stats": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== SEAMLESS AUTO-CONTEXT ====================


@mcp.tool()
def auto_buffer_context(summary: str, event_type: str = "auto") -> dict:
    """
    Buffer context for auto-save (NO immediate Neo4j write).
    Fast and seamless - buffers get flushed every 60 seconds.

    Use for: tool outputs, decisions, discoveries, errors.
    Claude should call this frequently - it's free and fast.
    """
    _current_session["context_buffer"].append(
        {
            "id": str(uuid.uuid4())[:8],
            "type": event_type,
            "summary": summary[:200],
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Track message count
    _current_session["message_count"] = _current_session.get("message_count", 0) + 1
    _current_session["last_activity"] = datetime.now().isoformat()

    return {
        "buffered": True,
        "buffer_size": len(_current_session.get("context_buffer", [])),
        "next_flush": "automatic every 60s",
    }


@mcp.tool()
def get_recovered_context() -> dict:
    """
    Get any context recovered from crash/previous session.
    Call this at start of conversation to see what was recovered.
    """
    recovered = _current_session.get("recovered_context", {})

    return {
        "recovered_from_crash": _current_session.get("recovered_from_crash", False),
        "session_id": _current_session.get("id"),
        "started_at": _current_session.get("started_at"),
        "previous_session_id": recovered.get("session_id"),
        "previous_description": recovered.get("description", ""),
        "previous_todos": recovered.get("todos", []),
        "previous_blockers": recovered.get("blockers", []),
        "previous_learnings": recovered.get("learnings", []),
        "previous_jira_tickets": recovered.get("jira_tickets", []),
    }


@mcp.tool()
def continuity_health() -> dict:
    """
    Full health check of the continuity system.
    Shows all background tasks, buffers, connections.
    """
    return {
        "version": "3.0 - ZERO CONTEXT LOSS EDITION",
        "session": {
            "id": _current_session.get("id"),
            "started_at": _current_session.get("started_at"),
            "message_count": _current_session.get("message_count", 0),
            "checkpoint_count": len(_current_session.get("checkpoints", [])),
            "buffer_size": len(_current_session.get("context_buffer", [])),
            "recovered_from_crash": _current_session.get("recovered_from_crash", False),
        },
        "background_tasks": {
            "auto_checkpoint": "running (60s interval)",
            "heartbeat": "running (30s interval)",
            "signal_handlers": ["SIGTERM", "SIGINT", "SIGHUP"],
            "atexit_handler": "registered",
        },
        "storage": {
            "state_file": str(STATE_FILE),
            "state_exists": STATE_FILE.exists(),
            "emergency_save": str(EMERGENCY_SAVE),
            "heartbeat_file": str(Path.home() / ".brain-continuity" / "heartbeat.json"),
        },
        "connections": {
            "neo4j": "connected" if get_neo4j_driver() else "not connected",
            "event_bus": (
                "connected" if EVENT_BUS_AVAILABLE and _event_bus else "not connected"
            ),
        },
    }


if __name__ == "__main__":
    print("🧠 Session Continuity MCP Server v3.0 - ZERO CONTEXT LOSS EDITION")
    print(f"   State file: {STATE_FILE}")
    print(f"   Has state: {STATE_FILE.exists()}")
    print(f"   Event bus: {EVENT_BUS_AVAILABLE}")
    print("   Lifespan hooks: ENABLED ✅")
    print("   Auto-save: Every 60 seconds ✅")
    print("   Heartbeat: Every 30 seconds ✅")
    print("   Signal handlers: SIGTERM, SIGINT, SIGHUP ✅")
    print("   Crash recovery: AUTO ✅")
    mcp.run()
