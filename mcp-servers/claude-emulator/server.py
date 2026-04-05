#!/usr/bin/env python3
"""
Claude Emulator MCP Server
==========================
Allows Claude to delegate tasks to the local autonomous emulator.

WHY THIS EXISTS:
Claude (the real one) has limitations:
- Can't run continuous AI loops
- Can't do real-time processing
- Creates static scripts, can't monitor/react
- Context resets between sessions

The local emulator CAN:
- Run 24/7 continuous tasks
- Monitor and react in real-time
- Maintain persistent state
- Process audio/events continuously
- Handle load when Claude is busy

TOOLS PROVIDED:
- emulator_delegate: Send a task to run autonomously
- emulator_status: Check emulator load and running tasks
- emulator_query: Quick one-shot query
- emulator_continuous: Start a continuous monitoring job
- emulator_stop: Stop a running job
- emulator_results: Get results from completed tasks
- emulator_load: Check current load, get overload warnings

Usage:
    Claude can now say: "I'll delegate this real-time monitoring to the emulator"
    And the emulator handles it autonomously!
"""

import os
import sys
import json
import time
import uuid
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque

sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("claude-emulator")


# ============================================================================
# TASK MANAGEMENT
# ============================================================================


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(Enum):
    ONE_SHOT = "one_shot"  # Single query
    CONTINUOUS = "continuous"  # Runs until stopped
    SCHEDULED = "scheduled"  # Runs periodically
    REACTIVE = "reactive"  # Triggered by events


@dataclass
class EmulatorTask:
    id: str
    task_type: TaskType
    prompt: str
    status: TaskStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    iterations: int = 0
    interval_seconds: int = 60
    max_iterations: int = 0  # 0 = unlimited for continuous
    context: Dict[str, Any] = field(default_factory=dict)


# Global task registry
_tasks: Dict[str, EmulatorTask] = {}
_task_threads: Dict[str, threading.Thread] = {}
_running = True

# Load tracking
_load_stats = {
    "active_tasks": 0,
    "completed_today": 0,
    "failed_today": 0,
    "avg_response_time": 0.0,
    "response_times": deque(maxlen=100),
    "overloaded": False,
    "max_concurrent": 5,
}


# ============================================================================
# EMULATOR INTERFACE
# ============================================================================


def query_emulator(
    prompt: str, system: str = None, max_tokens: int = 500
) -> tuple[Optional[str], float]:
    """Query the local emulator, returns (response, response_time)."""
    start_time = time.time()

    try:
        full_prompt = prompt
        if system:
            full_prompt = f"System: {system}\n\n{prompt}"

        payload = {
            "model": "claude-emulator:latest",
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.7,
            },
        }

        result = subprocess.run(
            [
                "curl",
                "-s",
                "-X",
                "POST",
                "http://localhost:11434/api/generate",
                "-d",
                json.dumps(payload),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        response_time = time.time() - start_time

        if result.returncode == 0:
            data = json.loads(result.stdout)
            return data.get("response"), response_time

        return None, response_time

    except Exception as e:
        return None, time.time() - start_time


def update_load_stats(response_time: float, success: bool):
    """Update load statistics."""
    _load_stats["response_times"].append(response_time)
    _load_stats["avg_response_time"] = sum(_load_stats["response_times"]) / len(
        _load_stats["response_times"]
    )

    if success:
        _load_stats["completed_today"] += 1
    else:
        _load_stats["failed_today"] += 1

    # Check if overloaded
    _load_stats["active_tasks"] = len(
        [t for t in _tasks.values() if t.status == TaskStatus.RUNNING]
    )
    _load_stats["overloaded"] = (
        _load_stats["active_tasks"] >= _load_stats["max_concurrent"]
        or _load_stats["avg_response_time"] > 30.0  # > 30s avg = overloaded
    )


# ============================================================================
# MCP TOOLS
# ============================================================================


@mcp.tool()
def emulator_delegate(
    task_description: str,
    task_type: str = "one_shot",
    interval_seconds: int = 60,
    max_iterations: int = 0,
    context: dict = None,
) -> dict:
    """
    Delegate a task to the autonomous emulator.

    Use this when Claude can't fulfill a task that requires:
    - Continuous monitoring
    - Real-time processing
    - Persistent loops
    - Background work

    Args:
        task_description: What the emulator should do (natural language)
        task_type: "one_shot" (single query), "continuous" (runs until stopped),
                  "scheduled" (periodic), "reactive" (event-triggered)
        interval_seconds: For scheduled tasks, how often to run
        max_iterations: Max runs (0 = unlimited for continuous)
        context: Additional context data

    Returns:
        Task ID and status for tracking
    """
    task_id = f"task_{uuid.uuid4().hex[:8]}"

    task = EmulatorTask(
        id=task_id,
        task_type=TaskType(task_type),
        prompt=task_description,
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
        interval_seconds=interval_seconds,
        max_iterations=max_iterations,
        context=context or {},
    )

    _tasks[task_id] = task

    # Start task execution
    if task_type == "one_shot":
        thread = threading.Thread(target=_run_one_shot, args=(task_id,), daemon=True)
    elif task_type in ["continuous", "scheduled"]:
        thread = threading.Thread(target=_run_continuous, args=(task_id,), daemon=True)
    else:
        thread = threading.Thread(target=_run_one_shot, args=(task_id,), daemon=True)

    _task_threads[task_id] = thread
    thread.start()

    return {
        "task_id": task_id,
        "status": "delegated",
        "type": task_type,
        "message": f"Task delegated to emulator. Track with: emulator_status('{task_id}')",
    }


@mcp.tool()
def emulator_status(task_id: str = None) -> dict:
    """
    Check status of emulator tasks.

    Args:
        task_id: Specific task to check, or None for all tasks

    Returns:
        Task status and results if completed
    """
    if task_id:
        task = _tasks.get(task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}

        return {
            "task_id": task.id,
            "status": task.status.value,
            "type": task.task_type.value,
            "iterations": task.iterations,
            "created": task.created_at.isoformat(),
            "started": task.started_at.isoformat() if task.started_at else None,
            "completed": task.completed_at.isoformat() if task.completed_at else None,
            "result": task.result[:500] if task.result else None,
            "error": task.error,
        }

    # All tasks summary
    return {
        "total_tasks": len(_tasks),
        "running": len([t for t in _tasks.values() if t.status == TaskStatus.RUNNING]),
        "completed": len(
            [t for t in _tasks.values() if t.status == TaskStatus.COMPLETED]
        ),
        "failed": len([t for t in _tasks.values() if t.status == TaskStatus.FAILED]),
        "tasks": [
            {"id": t.id, "status": t.status.value, "type": t.task_type.value}
            for t in list(_tasks.values())[-10:]  # Last 10 tasks
        ],
    }


@mcp.tool()
def emulator_query(prompt: str, system: str = None, max_tokens: int = 500) -> dict:
    """
    Quick one-shot query to the emulator.

    Use for simple questions that don't need task tracking.

    Args:
        prompt: Question or task
        system: Optional system prompt
        max_tokens: Max response length

    Returns:
        Emulator response
    """
    response, response_time = query_emulator(prompt, system, max_tokens)
    update_load_stats(response_time, response is not None)

    if response:
        return {
            "response": response,
            "response_time": f"{response_time:.2f}s",
            "model": "claude-emulator:latest",
        }
    else:
        return {
            "error": "Emulator failed to respond",
            "response_time": f"{response_time:.2f}s",
        }


@mcp.tool()
def emulator_continuous(
    description: str,
    monitor_type: str,
    interval_seconds: int = 30,
    alert_condition: str = None,
) -> dict:
    """
    Start a continuous monitoring job.

    The emulator will run this task continuously in the background,
    optionally alerting when conditions are met.

    Args:
        description: What to monitor/do
        monitor_type: "audio", "events", "files", "api", "custom"
        interval_seconds: How often to check
        alert_condition: Condition that triggers an alert (natural language)

    Returns:
        Job ID for tracking

    Example:
        emulator_continuous(
            "Monitor Neo4j for anomalies in email patterns",
            "events",
            interval_seconds=300,
            alert_condition="More than 100 emails from same sender in an hour"
        )
    """
    task_id = f"continuous_{uuid.uuid4().hex[:8]}"

    system_prompt = f"""You are a continuous monitoring agent.

TASK: {description}
TYPE: {monitor_type} monitoring
INTERVAL: Every {interval_seconds} seconds

{"ALERT WHEN: " + alert_condition if alert_condition else "Report findings periodically."}

For each iteration:
1. Check the current state
2. Compare to previous state (if any)
3. Report changes or findings
4. If alert condition met, prefix with "🚨 ALERT:"

Keep responses concise. Focus on changes and anomalies."""

    task = EmulatorTask(
        id=task_id,
        task_type=TaskType.CONTINUOUS,
        prompt=system_prompt,
        status=TaskStatus.PENDING,
        created_at=datetime.now(),
        interval_seconds=interval_seconds,
        context={
            "monitor_type": monitor_type,
            "alert_condition": alert_condition,
            "description": description,
        },
    )

    _tasks[task_id] = task

    thread = threading.Thread(target=_run_continuous, args=(task_id,), daemon=True)
    _task_threads[task_id] = thread
    thread.start()

    return {
        "job_id": task_id,
        "status": "started",
        "monitor_type": monitor_type,
        "interval": f"{interval_seconds}s",
        "message": f"Continuous job started. Stop with: emulator_stop('{task_id}')",
    }


@mcp.tool()
def emulator_stop(task_id: str) -> dict:
    """
    Stop a running emulator task.

    Args:
        task_id: Task to stop

    Returns:
        Confirmation and final results
    """
    task = _tasks.get(task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

    if task.status != TaskStatus.RUNNING:
        return {"error": f"Task {task_id} is not running (status: {task.status.value})"}

    task.status = TaskStatus.CANCELLED
    task.completed_at = datetime.now()

    return {
        "task_id": task_id,
        "status": "stopped",
        "iterations_completed": task.iterations,
        "last_result": task.result[:500] if task.result else None,
    }


@mcp.tool()
def emulator_results(task_id: str, last_n: int = 5) -> dict:
    """
    Get results from a task (especially useful for continuous tasks).

    Args:
        task_id: Task to get results from
        last_n: Number of recent results to return

    Returns:
        Task results and history
    """
    task = _tasks.get(task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

    return {
        "task_id": task_id,
        "status": task.status.value,
        "iterations": task.iterations,
        "current_result": task.result,
        "context": task.context,
    }


@mcp.tool()
def emulator_load() -> dict:
    """
    Check emulator load and get warnings if overloaded.

    Use this to decide whether to delegate more tasks or wait.

    Returns:
        Load statistics and recommendations
    """
    return {
        "active_tasks": _load_stats["active_tasks"],
        "max_concurrent": _load_stats["max_concurrent"],
        "completed_today": _load_stats["completed_today"],
        "failed_today": _load_stats["failed_today"],
        "avg_response_time": f"{_load_stats['avg_response_time']:.2f}s",
        "overloaded": _load_stats["overloaded"],
        "recommendation": (
            "⚠️ Emulator is overloaded. Wait for tasks to complete or increase capacity."
            if _load_stats["overloaded"]
            else "✅ Emulator has capacity for more tasks."
        ),
        "capacity_remaining": max(
            0, _load_stats["max_concurrent"] - _load_stats["active_tasks"]
        ),
    }


@mcp.tool()
def emulator_capabilities() -> dict:
    """
    List what the emulator can do that Claude cannot.

    Use this to understand when to delegate.

    Returns:
        Capability comparison
    """
    return {
        "emulator_strengths": [
            "🔄 Continuous monitoring loops (run 24/7)",
            "🎵 Real-time audio processing (analyze, generate)",
            "📊 Persistent event watching (Redpanda consumer)",
            "⏰ Scheduled periodic tasks",
            "🔍 Background anomaly detection",
            "📝 Continuous logging and reporting",
            "🚨 Alert generation when conditions met",
            "💾 Maintain state across iterations",
        ],
        "claude_strengths": [
            "🧠 Complex reasoning and planning",
            "💻 Code generation and debugging",
            "📚 Large context understanding",
            "🔧 Tool orchestration (MCP)",
            "💬 Nuanced conversation",
            "📋 Task decomposition",
        ],
        "when_to_delegate": [
            "Real-time audio monitoring/analysis",
            "Continuous event stream processing",
            "Periodic health checks",
            "Background data collection",
            "Long-running monitoring jobs",
            "Tasks that need to persist after session ends",
        ],
        "delegation_example": """
Claude: "I'll create a real-time audio monitor..."
        "But I can't run continuously, so I'll delegate:"
        
emulator_continuous(
    "Monitor audio input for specific patterns",
    "audio",
    interval_seconds=5,
    alert_condition="Detect speech or unusual sounds"
)
""",
    }


# ============================================================================
# TASK EXECUTION
# ============================================================================


def _run_one_shot(task_id: str):
    """Execute a one-shot task."""
    task = _tasks.get(task_id)
    if not task:
        return

    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now()

    response, response_time = query_emulator(task.prompt)
    update_load_stats(response_time, response is not None)

    task.iterations = 1

    if response:
        task.status = TaskStatus.COMPLETED
        task.result = response
    else:
        task.status = TaskStatus.FAILED
        task.error = "Emulator failed to respond"

    task.completed_at = datetime.now()


def _run_continuous(task_id: str):
    """Execute a continuous/scheduled task."""
    task = _tasks.get(task_id)
    if not task:
        return

    task.status = TaskStatus.RUNNING
    task.started_at = datetime.now()

    while task.status == TaskStatus.RUNNING:
        # Check max iterations
        if task.max_iterations > 0 and task.iterations >= task.max_iterations:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            break

        # Run iteration
        iteration_prompt = f"""Iteration {task.iterations + 1}
Previous result: {task.result[:200] if task.result else 'None'}

{task.prompt}

Current time: {datetime.now().isoformat()}
Provide update:"""

        response, response_time = query_emulator(iteration_prompt)
        update_load_stats(response_time, response is not None)

        task.iterations += 1

        if response:
            task.result = response

            # Check for alerts
            if "🚨 ALERT:" in response:
                _emit_alert(task, response)
        else:
            task.error = f"Iteration {task.iterations} failed"

        # Wait for next interval
        time.sleep(task.interval_seconds)

    if task.status == TaskStatus.RUNNING:
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()


def _emit_alert(task: EmulatorTask, alert_message: str):
    """Emit alert to event bus."""
    try:
        from core.kafka_bus import BrainEventBus, BrainTopics

        bus = BrainEventBus(group_id="emulator-alerts")
        bus.connect()
        bus.emit(
            BrainTopics.ALERTS,
            {
                "_event_type": "emulator_alert",
                "task_id": task.id,
                "message": alert_message,
                "context": task.context,
                "timestamp": datetime.now().isoformat(),
            },
        )
        bus.disconnect()
    except Exception:
        pass


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("🤖 Claude Emulator MCP Server starting...")
    print("   Model: claude-emulator:latest")
    print(
        "   Tools: delegate, status, query, continuous, stop, results, load, capabilities"
    )
    print("   Max concurrent tasks:", _load_stats["max_concurrent"])

    mcp.run()
