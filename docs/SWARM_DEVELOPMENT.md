# Redis Swarm Development Guide

> **Multi-agent coordination via Redis primitives — parallel development at scale.**

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Quick Start (5 minutes)](#quick-start)
4. [Key Patterns](#key-patterns)
   - [SwarmCoordinator](#swarmcoordinator)
   - [Agent Registration & Heartbeating](#agent-registration--heartbeating)
   - [Task Distribution](#task-distribution)
   - [Result Collection](#result-collection)
   - [Pub/Sub Coordination](#pubsub-coordination)
   - [AgentRegistry (Capability Matching)](#agentregistry--capability-matching)
   - [TaskQueue (Advanced)](#taskqueue--advanced)
   - [FindingsAggregator](#findingsaggregator)
5. [Redis Key Reference](#redis-key-reference)
6. [Full Example: 5-Agent PR Review Swarm](#full-example-5-agent-pr-review-swarm)
7. [Voice / Legacy Pattern](#voice--legacy-pattern)
8. [Consensus Protocol](#consensus-protocol)
9. [Best Practices](#best-practices)
10. [Monitoring & Health Checks](#monitoring--health-checks)
11. [Troubleshooting](#troubleshooting)

---

## Overview

The agentic-brain swarm system lets multiple agents — regardless of which LLM backs them — collaborate on a shared task through Redis as a lightweight message bus. No central daemon required; Redis itself is the coordinator.

```
┌──────────────────────────────────────────────────────────────┐
│                     SWARM ARCHITECTURE                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Orchestrator (Copilot CLI / Python script)                  │
│       │  start_swarm()  push_task() × N                     │
│       ▼                                                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              R E D I S  6379                        │    │
│  │                                                     │    │
│  │  swarm:{id}:tasks    ◄── push   ──► brpop ──►      │    │
│  │  swarm:{id}:results  ◄── lpush  ◄── workers        │    │
│  │  swarm:{id}:agents   (HASH)  agent metadata        │    │
│  │  swarm:{id}:status   (HASH)  health counters       │    │
│  │  swarm:{id}:hb:{aid} (TTL)   heartbeat sentinel    │    │
│  │  swarm:channel:{id}  (pub/sub)  events             │    │
│  └─────────────────────────────────────────────────────┘    │
│       │                         ▲                            │
│       ▼  brpop (blocking pop)   │ lpush results             │
│   Agent-1   Agent-2   Agent-3  Agent-4   Agent-5            │
│   (GPT)    (Claude) (Gemini)  (Grok)  (Local LLM)           │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

**Why Redis?**
- Sub-millisecond task handoff
- Blocking pop (`BRPOP`) gives workers instant wake-up at zero CPU cost
- Pub/sub for event-driven coordination
- TTL heartbeats for automatic dead-agent detection
- Works across processes, containers, or machines
- No extra broker process — Docker Compose already runs Redis on port 6379

---

## Architecture

### Components

| Module | Location | Responsibility |
|--------|----------|----------------|
| `SwarmCoordinator` | `swarm/redis_coordinator.py` | Core Redis primitives: start/finish swarm, push/pull tasks, publish events, register agents |
| `AgentRegistry` | `swarm/agent_registry.py` | Capability-based agent matching, load balancing (least-loaded wins), workload tracking |
| `TaskQueue` | `swarm/task_queue.py` | Visibility timeout, inflight tracking, automatic retry on crash, dead-letter queue |
| `FindingsAggregator` | `swarm/findings_aggregator.py` | Pull results, deduplicate, categorise by severity, persist to Neo4j |

### Data Flow

```
Producer                Redis                   Workers
────────                ─────                   ───────
start_swarm()    →  status HASH created
push_task() × N  →  tasks LIST (LPUSH)
                                          ← claim() / BRPOP
                                          ← do_work()
                 ←  results LIST (LPUSH)  ← complete()
                 ←  channel pub/sub       ← publish()
aggregate()      ←  results LIST (LRANGE)
store_to_neo4j()
finish_swarm()   →  status HASH updated
```

---

## Quick Start

**Prerequisites:** Docker running, Redis available at `localhost:6379`.

```bash
cd ~/brain
docker-compose up -d redis        # or: docker-compose up -d
```

### 1. Install the package (editable)

```bash
cd agentic-brain
pip install -e ".[dev]"
```

### 2. Run a minimal swarm in 20 lines

```python
import json, time, threading
from agentic_brain.swarm.redis_coordinator import SwarmCoordinator

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
SWARM_ID  = "my-first-swarm"

coord = SwarmCoordinator.from_url(REDIS_URL)

# --- Producer: start and enqueue tasks ---
coord.start_swarm(SWARM_ID, total_tasks=3)
for i in range(3):
    coord.push_task(SWARM_ID, {"task_id": f"t{i}", "file": f"file_{i}.py"})

# --- Worker (runs in a thread / separate process) ---
def worker(name: str):
    coord.register_agent(SWARM_ID, name, capabilities=["python"])
    while True:
        task = coord.pull_task(SWARM_ID, timeout=5)
        if task is None:
            break
        result = {"task_id": task["task_id"], "status": "ok", "agent": name}
        coord.push_result(SWARM_ID, result)
        coord.publish(SWARM_ID, {"type": "task_complete", "agent": name, "task": task["task_id"]})

threads = [threading.Thread(target=worker, args=(f"worker-{i}",)) for i in range(3)]
for t in threads: t.start()
for t in threads: t.join()

# --- Collect and finish ---
results = coord.get_results(SWARM_ID)
print(f"Got {len(results)} results")
coord.finish_swarm(SWARM_ID)
```

### 3. Check swarm status

```python
status = coord.swarm_status(SWARM_ID)
print(json.dumps(status, indent=2))
# {
#   "swarm_id": "my-first-swarm",
#   "status": "completed",
#   "agent_count": 3,
#   "pending_tasks": 0,
#   "completed_results": 3,
#   ...
# }
```

---

## Key Patterns

### SwarmCoordinator

The entry point for all Redis swarm operations.

```python
from agentic_brain.swarm.redis_coordinator import SwarmCoordinator

# Connect via URL (password in URL is fine for local dev)
coord = SwarmCoordinator.from_url("redis://:BrainRedis2026@localhost:6379/0")

# Or inject a ConnectionPool from agentic_brain.core.redis_pool
from agentic_brain.core.redis_pool import RedisPoolManager
coord = SwarmCoordinator.from_pool(RedisPoolManager())
```

| Method | Description |
|--------|-------------|
| `start_swarm(swarm_id, total_tasks)` | Initialise status HASH, publish `swarm_started` event |
| `finish_swarm(swarm_id, status)` | Mark swarm done, publish `swarm_finished` event |
| `swarm_status(swarm_id)` | Returns dict: agent count, pending tasks, result count, status |
| `register_agent(swarm_id, agent_id, capabilities)` | Write agent to HASH + SET, set heartbeat TTL |
| `heartbeat(swarm_id, agent_id)` | Renew TTL — call every ~30 s from long-running workers |
| `push_task(swarm_id, task)` | `LPUSH` task JSON to the tasks list |
| `pull_task(swarm_id, timeout)` | `BRPOP` — blocks until a task arrives or timeout |
| `push_result(swarm_id, result)` | `LPUSH` result JSON to results list |
| `get_results(swarm_id)` | `LRANGE` all results |
| `publish(swarm_id, event)` | Pub/sub broadcast on `swarm:channel:{swarm_id}` |
| `subscribe(swarm_id, callback)` | Subscribe to coordination channel in a background thread |

---

### Agent Registration & Heartbeating

Agents self-register when they start and must keep their heartbeat alive.

```python
import time

SWARM_ID = "pr-review-42"

# Register with capabilities so the registry can match you to tasks
coord.register_agent(
    SWARM_ID,
    agent_id="claude-reviewer-1",
    capabilities=["python", "security", "review"],
    metadata={"model": "claude-opus", "version": "4.5"},
)

# Worker loop — renew heartbeat every 30 s
def worker_loop():
    while True:
        task = coord.pull_task(SWARM_ID, timeout=25)
        if task is None:
            break
        coord.heartbeat(SWARM_ID, "claude-reviewer-1")  # keep alive
        result = process(task)
        coord.push_result(SWARM_ID, result)
```

**Heartbeat TTL:** 60 seconds by default (`_AGENT_TTL` in `redis_coordinator.py`).
Agents that miss two heartbeat windows are considered dead and their in-flight
tasks are re-queued by `TaskQueue.requeue_stalled()`.

---

### Task Distribution

Tasks are JSON objects pushed to a Redis list. Workers compete via `BRPOP` —
the first worker to call it gets the task atomically. No duplicate processing.

```python
# Producer: enqueue tasks
tasks = [
    {"task_id": "r1", "action": "review", "file": "src/auth.py"},
    {"task_id": "r2", "action": "review", "file": "src/models.py"},
    {"task_id": "r3", "action": "security-scan", "file": "src/auth.py"},
]
for task in tasks:
    coord.push_task(SWARM_ID, task)

# Worker: claim and process
def worker():
    while True:
        task = coord.pull_task(SWARM_ID, timeout=30)  # blocks up to 30 s
        if task is None:
            break  # no more tasks
        try:
            result = do_work(task)
            coord.push_result(SWARM_ID, {**task, **result, "status": "ok"})
        except Exception as e:
            coord.push_result(SWARM_ID, {**task, "status": "error", "error": str(e)})
```

> **Tip:** Always include `task_id` in every task and result. The aggregator and
> TaskQueue use it for deduplication and inflight tracking.

---

### Result Collection

Results are pushed to `swarm:{swarm_id}:results` and read by the orchestrator
after all workers are done (or progressively as they arrive).

```python
# Pull all results at the end
results = coord.get_results(SWARM_ID)

# Or poll progressively (non-blocking)
import time
collected = []
while len(collected) < expected_count:
    results = coord.get_results(SWARM_ID)
    if len(results) > len(collected):
        new = results[len(collected):]
        collected = results
        for r in new:
            print(f"  [{r.get('status')}] {r.get('task_id')} — {r.get('summary','')}")
    time.sleep(1)
```

---

### Pub/Sub Coordination

Use the coordination channel for real-time event broadcasting — progress
updates, cancellation signals, or agent announcements.

```python
# Publisher (any agent or orchestrator)
coord.publish(SWARM_ID, {
    "type": "progress",
    "agent": "claude-reviewer-1",
    "task_id": "r1",
    "pct": 50,
})

# Subscriber (background thread)
def on_event(event):
    print(f"[{event['type']}] from {event.get('agent','?')}: {event}")

coord.subscribe(SWARM_ID, callback=on_event)
# Runs in a daemon thread — automatically cleaned up on process exit
```

**Built-in event types** (published automatically by `SwarmCoordinator`):

| Event type | When fired |
|------------|------------|
| `swarm_started` | `start_swarm()` called |
| `swarm_finished` | `finish_swarm()` called |
| `agent_registered` | `register_agent()` called |

All other event types are user-defined — use whatever makes sense for your swarm.

---

### AgentRegistry — Capability Matching

`AgentRegistry` wraps `SwarmCoordinator` and adds intelligent routing: pick
the **least-loaded** agent that has the required capabilities.

```python
from agentic_brain.swarm.agent_registry import AgentRegistry

reg = AgentRegistry(coord, swarm_id=SWARM_ID)

# Register agents with their capabilities
reg.register("gpt-coder",    capabilities=["python", "typescript", "fix"])
reg.register("claude-reviewer", capabilities=["python", "security", "review"])
reg.register("gemini-docs",  capabilities=["docs", "markdown"])

# Pick the least-loaded agent that can do "security"
agent = reg.pick(required_capabilities=["security"])
if agent:
    reg.increment_workload(agent.agent_id)   # track it
    try:
        result = agent_do_security_scan(agent.agent_id, task)
    finally:
        reg.decrement_workload(agent.agent_id)  # release

# List all healthy agents
agents = reg.list_agents()
for a in agents:
    print(f"  {a.agent_id:30s} tasks={a.active_tasks} caps={a.capabilities}")
```

**AgentProfile fields:**

| Field | Type | Description |
|-------|------|-------------|
| `agent_id` | str | Unique agent identifier |
| `capabilities` | list[str] | Skills this agent has |
| `status` | str | `"ready"` / `"busy"` / `"draining"` |
| `active_tasks` | int | Current workload (for load balancing) |
| `registered_at` | float | Unix timestamp |
| `metadata` | dict | Any extra info (model, version, etc.) |

---

### TaskQueue — Advanced

`TaskQueue` adds **visibility timeout** and **automatic retry** on top of the
basic list-based queue. Use it when workers can crash mid-task.

```python
from agentic_brain.swarm.task_queue import TaskQueue

queue = TaskQueue(
    coord,
    swarm_id=SWARM_ID,
    visibility_timeout=120,   # re-queue after 120 s if worker crashes
    max_retries=3,            # move to dead-letter after 3 failures
)

# Producer
task_ids = queue.enqueue_many([
    {"action": "review", "file": "main.py"},
    {"action": "review", "file": "utils.py"},
    {"action": "test",   "file": "tests/test_main.py"},
])

# Worker (crash-safe)
while True:
    task = queue.claim(timeout=5)     # atomically moves to inflight HASH
    if task is None:
        break
    try:
        result = do_work(task)
        queue.complete(task["task_id"], result=result)
    except Exception as exc:
        queue.fail(task["task_id"], error=str(exc))  # retried up to max_retries

# Recover stalled tasks from crashed workers
queue.requeue_stalled()   # call periodically (e.g. every 60 s from a monitor)
```

**Redis keys used by TaskQueue:**

| Key | Type | Purpose |
|-----|------|---------|
| `swarm:{id}:tasks` | LIST | Pending tasks |
| `swarm:{id}:tasks:inflight` | HASH | `task_id → task JSON` while being processed |
| `swarm:{id}:tasks:failed` | LIST | Exhausted all retries — dead-letter queue |

---

### FindingsAggregator

Collects results from the results list, deduplicates them, groups by severity
and category, and can persist everything to Neo4j for long-term storage.

```python
from agentic_brain.swarm.findings_aggregator import FindingsAggregator

agg = FindingsAggregator(coord, swarm_id=SWARM_ID)

# Aggregate all results currently on the results list
summary = agg.aggregate()

# Human-readable summary
print(summary.human_summary())
# SwarmRun my-first-swarm: 12 findings
# critical: 0, high: 2, medium: 5, low: 3, info: 2
# Categories: security(3), style(4), bug(5)

# Persist to Neo4j (gracefully skipped if Neo4j is unavailable)
agg.store_to_neo4j(summary)
```

**Result format expected** by the aggregator:

```python
{
    "task_id":     "r1",              # required — deduplication key
    "category":    "security",        # optional: bug, security, style, perf, general
    "severity":    "high",            # optional: critical, high, medium, low, info
    "summary":     "SQL injection in login endpoint",
    "detail":      "Line 42: user input concatenated into query string",
    "source_file": "src/auth.py",     # optional
    "agent_id":    "claude-reviewer", # optional — populated automatically if set
}
```

**Neo4j schema written:**

```
(:SwarmRun {swarm_id, started_at, total_findings, status})
    -[:HAS_FINDING]->
(:Finding {task_id, swarm_id, category, severity, summary, detail, stored_at})
```

---

## Redis Key Reference

All keys are namespaced under `swarm:{swarm_id}:` to avoid collisions.

| Key pattern | Redis type | Description |
|-------------|------------|-------------|
| `swarm:{id}:agents` | HASH | `agent_id → metadata JSON` |
| `swarm:{id}:agents:set` | SET | Active agent IDs (for fast existence checks) |
| `swarm:{id}:tasks` | LIST | Pending tasks — push left, pop right |
| `swarm:{id}:tasks:inflight` | HASH | `task_id → task JSON` while claimed |
| `swarm:{id}:tasks:failed` | LIST | Dead-letter: tasks that exhausted retries |
| `swarm:{id}:results` | LIST | Completed results |
| `swarm:{id}:status` | HASH | `started_at`, `status`, `total_tasks` |
| `swarm:{id}:hb:{agent_id}` | STRING | Heartbeat sentinel — TTL=60 s |
| `swarm:{id}:workload:{agent_id}` | STRING | Integer counter — active tasks per agent |
| `swarm:channel:{id}` | pub/sub | Coordination event channel |

### Inspecting live keys

```bash
# Connect to Redis
docker exec -it brain-redis-1 redis-cli -a BrainRedis2026

# List all keys for a swarm
KEYS swarm:pr-review-42:*

# Check task queue depth
LLEN swarm:pr-review-42:tasks

# Check result count
LLEN swarm:pr-review-42:results

# Read swarm status
HGETALL swarm:pr-review-42:status

# Read all agent registrations
HGETALL swarm:pr-review-42:agents

# Peek at first pending task (non-destructive)
LINDEX swarm:pr-review-42:tasks -1

# Subscribe to coordination events in real-time
SUBSCRIBE swarm:channel:pr-review-42
```

---

## Full Example: 5-Agent PR Review Swarm

This pattern runs a real PR review with specialist agents in parallel.

```python
"""
5-agent PR review swarm.

Agents:
  claude-reviewer  — deep code review, logic, architecture
  gpt-security     — security vulnerabilities, OWASP
  gemini-docs      — documentation and comments quality
  grok-style       — style, naming, formatting
  local-tests      — test coverage analysis (free, local LLM)
"""
import json
import threading
import time
from agentic_brain.swarm.redis_coordinator import SwarmCoordinator
from agentic_brain.swarm.agent_registry import AgentRegistry
from agentic_brain.swarm.task_queue import TaskQueue
from agentic_brain.swarm.findings_aggregator import FindingsAggregator

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
SWARM_ID  = f"pr-review-{int(time.time())}"

# ── Setup ──────────────────────────────────────────────────────────────────
coord   = SwarmCoordinator.from_url(REDIS_URL)
reg     = AgentRegistry(coord, swarm_id=SWARM_ID)
queue   = TaskQueue(coord, swarm_id=SWARM_ID, visibility_timeout=120, max_retries=2)
agg     = FindingsAggregator(coord, swarm_id=SWARM_ID)

# ── Define the files changed in the PR ────────────────────────────────────
changed_files = [
    "src/auth/login.py",
    "src/auth/tokens.py",
    "src/models/user.py",
    "tests/test_auth.py",
]

# ── Start swarm and enqueue tasks ─────────────────────────────────────────
tasks = []
for f in changed_files:
    tasks += [
        {"action": "review",   "file": f, "category": "logic",    "task_id": f"review-{f}"},
        {"action": "security", "file": f, "category": "security",  "task_id": f"sec-{f}"},
        {"action": "style",    "file": f, "category": "style",     "task_id": f"style-{f}"},
    ]

coord.start_swarm(SWARM_ID, total_tasks=len(tasks))
queue.enqueue_many(tasks)

# ── Subscribe to progress events ──────────────────────────────────────────
def on_event(event):
    t = event.get("type", "?")
    if t == "task_complete":
        print(f"  ✓ {event.get('agent')} completed {event.get('task_id')}")

coord.subscribe(SWARM_ID, callback=on_event)

# ── Agent workers ─────────────────────────────────────────────────────────
AGENTS = {
    "claude-reviewer": ["logic", "review"],
    "gpt-security":    ["security"],
    "gemini-docs":     ["docs", "review"],
    "grok-style":      ["style"],
    "local-tests":     ["test", "coverage"],
}

def make_worker(agent_id: str, capabilities: list):
    def _worker():
        reg.register(agent_id, capabilities=capabilities, metadata={"pid": __import__("os").getpid()})
        reg.increment_workload(agent_id)
        try:
            while True:
                task = queue.claim(timeout=10)
                if task is None:
                    break
                coord.heartbeat(SWARM_ID, agent_id)

                # === Replace this with real LLM call ===
                finding = {
                    "task_id":  task["task_id"],
                    "agent_id": agent_id,
                    "category": task.get("category", "general"),
                    "severity": "info",
                    "summary":  f"{agent_id} reviewed {task['file']}",
                    "detail":   f"Action: {task['action']}",
                }
                # =======================================

                queue.complete(task["task_id"], result=finding)
                coord.publish(SWARM_ID, {
                    "type":    "task_complete",
                    "agent":   agent_id,
                    "task_id": task["task_id"],
                })
        finally:
            reg.decrement_workload(agent_id)
    return _worker

threads = [
    threading.Thread(target=make_worker(aid, caps), name=aid, daemon=True)
    for aid, caps in AGENTS.items()
]
for t in threads: t.start()
for t in threads: t.join()

# ── Aggregate and finish ───────────────────────────────────────────────────
summary = agg.aggregate()
print("\n" + summary.human_summary())

agg.store_to_neo4j(summary)   # persists to Neo4j if available

coord.finish_swarm(SWARM_ID)
print(f"\nSwarm {SWARM_ID} complete. {summary.total_findings} findings stored.")
```

---

## Voice / Legacy Pattern

Older voice-system code predates `SwarmCoordinator` and uses simpler Redis
conventions directly. You will see these keys in the live Redis instance:

```python
# Ready signal (simple string flag)
r.set('voice:{name}_ready', 'true')

# Shared state (JSON blob)
r.set('voice:shared_state', json.dumps({
    "llms":   {"ollama": "installed", "claude": "ready"},
    "agents": {"helper": json.dumps({"status": "ready", "findings": 5})},
}))

# History (append-only list of JSON events)
r.lpush('voice:history', json.dumps({"event": "...", "ts": time.time()}))

# Coordination audit (summary after a run)
r.set('voice:coordination_audit', json.dumps({
    "coordinator": "copilot-cli",
    "agents_on_redis": ["gpt_coder", "grok", "helper", ...],
    "ready_count": 11,
    "tests_passing": True,
}))
```

> **Note:** New code should use `SwarmCoordinator` instead of these raw patterns.
> The voice keys are maintained for backward-compatibility only.

---

## Consensus Protocol

When multiple agents must agree before proceeding (e.g. "should we merge this
PR?"), use the consensus keys:

```python
import json, time

VOTE_KEY   = "consensus:votes"     # HASH: agent_id → vote JSON
STATUS_KEY = "consensus:status"    # STRING: "pending" / "reached" / "timeout"
RESULT_KEY = "consensus:result"    # STRING: winning option JSON
TIMELINE   = "consensus:timeline"  # STRING: metadata

# Agent casts a vote
r.hset(VOTE_KEY, agent_id, json.dumps({
    "vote":      "approve",
    "rationale": "All security checks pass",
    "confidence": 0.95,
    "ts":        time.time(),
}))

# Orchestrator checks votes
votes     = {k.decode(): json.loads(v) for k, v in r.hgetall(VOTE_KEY).items()}
approvals = sum(1 for v in votes.values() if v["vote"] == "approve")

if approvals >= 3:   # 3-of-N majority
    r.set(STATUS_KEY, "reached")
    r.set(RESULT_KEY, json.dumps({"decision": "approve", "votes": approvals}))
```

---

## Best Practices

### Do

- **Always set a `task_id`** in every task dict — aggregation and deduplication depend on it.
- **Use `TaskQueue.claim()` + `complete()`/`fail()`** for resilient workers; plain `pull_task()` is fine only for throwaway scripts.
- **Renew heartbeats** in long-running workers (`coord.heartbeat()` every 30 s).
- **Set `total_tasks` accurately** in `start_swarm()` — the status HASH uses it for progress calculation.
- **Namespace your swarm IDs** semantically: `pr-review-{pr_number}`, `sec-scan-{commit}`, `daily-audit-{date}`.
- **Include timestamps** in task and result payloads (`"ts": time.time()`).
- **Clean up** after completion — `finish_swarm()` marks the run complete; optionally delete keys with TTL or a cleanup script.
- **Handle `None` from `pull_task()`** — it means the queue is empty (timeout expired). Don't spin-loop.
- **Log agent_id in every result** — the aggregator can attribute findings to the agent that produced them.

### Don't

- Don't mix swarm IDs across unrelated runs — keys accumulate and keys from run A pollute run B.
- Don't skip `finish_swarm()` — it publishes the `swarm_finished` event that monitoring depends on.
- Don't use `KEYS swarm:*` in production — use `SCAN` instead. `KEYS` blocks Redis.
- Don't store large blobs (>1 MB) directly in Redis — store a reference path and keep the data in a file or Neo4j.
- Don't hard-code `BrainRedis2026` — read it from `.env` or the brain config YAML.

```python
# Good: read from environment
import os
REDIS_URL = os.getenv("REDIS_URL", "redis://:BrainRedis2026@localhost:6379/0")
```

---

## Monitoring & Health Checks

### Swarm status snapshot

```python
status = coord.swarm_status(SWARM_ID)
# Returns:
# {
#   "swarm_id":          "pr-review-42",
#   "status":            "running",        # started / running / completed / failed
#   "agent_count":       5,
#   "pending_tasks":     7,
#   "completed_results": 3,
#   "started_at":        "2026-04-01T09:00:00",
#   "total_tasks":       10,
# }
```

### Live Redis CLI monitoring

```bash
# Watch all swarm activity in real-time
docker exec -it brain-redis-1 redis-cli -a BrainRedis2026 monitor | grep swarm

# Queue depths across all swarms
docker exec -it brain-redis-1 redis-cli -a BrainRedis2026 \
  KEYS 'swarm:*:tasks' | xargs -I{} redis-cli -a BrainRedis2026 LLEN {}

# All active agents in a swarm
docker exec -it brain-redis-1 redis-cli -a BrainRedis2026 \
  SMEMBERS swarm:pr-review-42:agents:set

# Live pub/sub events
docker exec -it brain-redis-1 redis-cli -a BrainRedis2026 \
  SUBSCRIBE swarm:channel:pr-review-42
```

### Python health probe

```python
def swarm_health(coord, swarm_id):
    status   = coord.swarm_status(swarm_id)
    pending  = status["pending_tasks"]
    done     = status["completed_results"]
    total    = int(status.get("total_tasks", done + pending) or 1)
    pct      = round(done / total * 100) if total else 0
    agents   = status["agent_count"]

    print(f"Swarm {swarm_id}: {pct}% complete ({done}/{total}) — {agents} agents alive")
    if pending == 0 and done >= total:
        print("  → All tasks complete, ready to aggregate.")
    elif agents == 0:
        print("  ⚠ No live agents! Check heartbeat TTL or restart workers.")
    return status
```

---

## Troubleshooting

### Tasks stuck in queue — workers not consuming

```bash
# Check if any agents are registered
HKEYS swarm:my-swarm:agents

# Check heartbeat keys (these expire — absence = dead agent)
KEYS swarm:my-swarm:hb:*

# Manually inspect queue
LRANGE swarm:my-swarm:tasks 0 4
```

**Fix:** Restart workers; they will re-register and resume consuming.

---

### Tasks stuck in inflight — worker crashed

```bash
HGETALL swarm:my-swarm:tasks:inflight
```

**Fix:** Call `queue.requeue_stalled()` — it checks visibility timeouts and
re-enqueues tasks whose workers have vanished.

---

### Redis connection refused

```bash
docker ps | grep redis         # Is the container running?
docker-compose up -d redis     # Start it
docker logs brain-redis-1      # Check for errors
```

---

### `WRONGTYPE` error on Redis get

The key holds a different data type than expected (e.g. a LIST when GET expects
a STRING). This happens when the same key is reused across different swarm runs
or patterns.

```bash
TYPE swarm:my-key    # Check actual type
DEL  swarm:my-key    # Delete and let the code recreate it
```

Always use unique `swarm_id` values per run to avoid this.

---

### Results list shorter than expected

1. Check the failed queue: `LRANGE swarm:my-swarm:tasks:failed 0 -1`
2. Check worker logs for unhandled exceptions
3. Check inflight hash for stuck tasks: `HGETALL swarm:my-swarm:tasks:inflight`
4. Increase `visibility_timeout` if tasks take longer than 120 s

---

### Pub/sub callback not firing

The subscriber runs in a background thread. Make sure:
- The main thread is still alive (don't exit immediately after `subscribe()`)
- You are subscribed **before** the first events are published (pub/sub is not
  persistent — missed events are gone)
- Check for exceptions in the subscriber thread via logging

---

*Last updated: 2026-04-01 · Maintainer: the developer · agentic-brain v3.x*
