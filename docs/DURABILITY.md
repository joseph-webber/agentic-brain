# Durability Package - Fault-Tolerant Workflow Execution

The durability package provides fault-tolerant workflow execution for AI agents, enabling workflows to survive crashes, restarts, and network failures.

## Overview

This package implements durable execution specifically designed for AI workflows, with native LLM and RAG integration.

### Key Features

| Feature | Description |
|---------|-------------|
| **Event Sourcing** | All state changes recorded as immutable events |
| **Durable Execution** | Workflows survive process restarts |
| **Task Queues** | Distributed work across multiple workers |
| **Signals** | External input to running workflows |
| **Queries** | Read-only state inspection |
| **Retry Policies** | Sophisticated retry with backoff |
| **Heartbeats** | Detect hung activities |
| **Versioning** | Safe workflow updates |
| **Child Workflows** | Hierarchical workflow composition |
| **Schedules** | Cron and interval-based scheduling |
| **Timers** | Durable sleep with persistence |
| **Sagas** | Compensating transactions |
| **Search Attributes** | Custom searchable workflow fields |
| **Cancellation Scopes** | Structured cancellation |
| **Local Activities** | In-process fast execution |
| **Side Effects** | Deterministic replay |
| **Interceptors** | Middleware chain for cross-cutting concerns |

## Quick Start

### Basic Durable Workflow

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow,
    activity,
)

@activity(name="analyze_text")
async def analyze_text(text: str) -> dict:
    """Activity that can be retried on failure"""
    # Call LLM, RAG, or any external service
    return {"analysis": "result"}

@workflow(name="analysis-workflow")
class AnalysisWorkflow(DurableWorkflow):
    """Workflow that survives crashes"""
    
    async def run(self, query: str) -> dict:
        # This activity call is durable - if we crash,
        # we'll resume from here on restart
        result = await self.execute_activity(
            "analyze_text",
            args={"text": query}
        )
        return {"status": "complete", "result": result}

# Start workflow
wf = AnalysisWorkflow()
result = await wf.start(args={"query": "Analyze this data"})

# If crashed, resume from events
wf2 = AnalysisWorkflow(workflow_id=wf.workflow_id)
result = await wf2.resume()
```

### With Signals (External Input)

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow,
    signal_handler,
    get_signal_dispatcher,
)

@workflow(name="approval-workflow")
class ApprovalWorkflow(DurableWorkflow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approved = None
    
    @signal_handler("approval")
    async def handle_approval(self, payload: dict):
        """Handle external approval signal"""
        self.approved = payload.get("approved", False)
    
    async def run(self, request: dict) -> dict:
        # Wait for human approval
        await self.wait_for_signal("approval", timeout=3600)
        
        if self.approved:
            return {"status": "approved", "request": request}
        else:
            return {"status": "rejected", "request": request}

# Start workflow
wf = ApprovalWorkflow()
await wf.start(args={"request": {"amount": 1000}})

# Send approval signal from elsewhere
dispatcher = get_signal_dispatcher()
await dispatcher.send_signal(
    workflow_id=wf.workflow_id,
    signal_name="approval",
    payload={"approved": True}
)
```

### With Queries (State Inspection)

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow,
    query_handler,
    query_workflow,
)

@workflow(name="processing-workflow")
class ProcessingWorkflow(DurableWorkflow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.items_processed = 0
        self.total_items = 0
    
    @query_handler("get_progress")
    def get_progress(self) -> dict:
        """Query current progress (read-only)"""
        return {
            "processed": self.items_processed,
            "total": self.total_items,
            "percent": (self.items_processed / self.total_items * 100) 
                       if self.total_items > 0 else 0
        }
    
    async def run(self, items: list) -> dict:
        self.total_items = len(items)
        
        for item in items:
            await self.execute_activity("process_item", args={"item": item})
            self.items_processed += 1
        
        return {"processed": self.items_processed}

# Query progress from elsewhere
progress = await query_workflow(wf.workflow_id, "get_progress")
print(f"Progress: {progress['percent']}%")
```

### With Retry Policies

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow,
    LLM_RETRY_POLICY,
    with_retry,
)

# Use pre-built policy for LLM calls
@with_retry(LLM_RETRY_POLICY)
async def call_llm(prompt: str) -> str:
    """LLM call with automatic retry on rate limits"""
    # Will retry with exponential backoff on:
    # - Rate limit errors
    # - Timeout errors
    # - Transient failures
    return await llm.chat(prompt)

# Or configure custom retry
from agentic_brain.durability import RetryPolicy
from datetime import timedelta

custom_policy = RetryPolicy(
    max_attempts=5,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    max_interval=timedelta(minutes=5),
    jitter=0.2,
)

@with_retry(custom_policy)
async def my_activity():
    pass
```

### With Task Queues (Multi-Worker)

```python
from agentic_brain.durability import (
    create_task_queue_manager,
    create_worker_pool,
    TaskPriority,
)

# Create task queue manager
manager = await create_task_queue_manager()

# Get a queue
queue = await manager.get_queue("llm-tasks")

# Enqueue a task
task = await queue.enqueue(
    task_type="analyze",
    payload={"text": "analyze this"},
    priority=TaskPriority.HIGH,
)

# Create worker pool to process tasks
pool = await create_worker_pool(
    num_workers=4,
    task_queues=["llm-tasks"],
    activities={
        "analyze": analyze_activity,
    }
)

# Workers automatically poll and execute tasks
await pool.start()
```

### With Workflow Versioning

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow_version,
    migration_handler,
    get_version_manager,
)

@workflow_version("1.0")
class MyWorkflowV1(DurableWorkflow):
    async def run(self, data: dict) -> dict:
        return {"v1_result": data}

@workflow_version("2.0", migrates_from="1.0")
class MyWorkflowV2(DurableWorkflow):
    async def run(self, data: dict) -> dict:
        # New behavior
        return {"v2_result": data, "enhanced": True}

@migration_handler("1.0", "2.0")
def migrate_v1_to_v2(state: dict, from_version: str) -> dict:
    """Migrate state from v1 to v2"""
    return {
        **state,
        "migrated": True,
        "enhanced_field": "default_value",
    }

# Register versions
manager = get_version_manager()
manager.register_version("my-workflow", "1.0", MyWorkflowV1)
manager.register_version("my-workflow", "2.0", MyWorkflowV2)
manager.set_active_version("my-workflow", "2.0")
```

## API Reference

### Event Store

```python
from agentic_brain.durability import EventStore, get_event_store

store = get_event_store()

# Publish event
await store.publish(workflow_id, event)

# Load all events
events = await store.load_events(workflow_id)

# Stream events
async for event in store.stream_events(workflow_id):
    print(event)
```

### Checkpoints

```python
from agentic_brain.durability import get_checkpoint_manager

manager = get_checkpoint_manager()

# Create checkpoint
checkpoint = await manager.create(workflow_id, state)

# Load latest checkpoint
checkpoint = await manager.load_latest(workflow_id)

# Recover from checkpoint
state = checkpoint.state
```

### Recovery

```python
from agentic_brain.durability import recover_workflow, recover_all_workflows

# Recover single workflow
result = await recover_workflow(workflow_id)
if result.recovered:
    print(f"Resumed from step {result.resumed_from}")

# Recover all incomplete workflows on startup
results = await recover_all_workflows()
```

### Dashboard API

```python
from agentic_brain.durability import get_workflow_dashboard

dashboard = get_workflow_dashboard()

# List workflows
workflows = dashboard.list_workflows(
    filter=WorkflowFilter(status="running"),
    limit=100
)

# Get statistics
stats = dashboard.get_stats(period_hours=24)
print(f"Running: {stats.running}, Failed: {stats.failed}")

# Send signal via dashboard
await dashboard.send_signal(workflow_id, "cancel", {"reason": "timeout"})

# Cancel workflow
await dashboard.cancel_workflow(workflow_id, "No longer needed")
```

### FastAPI Integration

```python
from fastapi import FastAPI
from agentic_brain.durability import create_dashboard_routes

app = FastAPI()

# Add workflow dashboard routes
routes = create_dashboard_routes()
if routes:
    app.include_router(routes)

# Now available:
# GET  /api/workflows/          - List workflows
# GET  /api/workflows/stats     - Get statistics
# GET  /api/workflows/{id}      - Get workflow
# POST /api/workflows/{id}/signal  - Send signal
# POST /api/workflows/{id}/cancel  - Cancel workflow
```

## Pre-built Retry Policies

| Policy | Use Case |
|--------|----------|
| `DEFAULT_RETRY_POLICY` | General use (3 attempts, 1s backoff) |
| `AGGRESSIVE_RETRY_POLICY` | Critical tasks (5 attempts, fast retry) |
| `CONSERVATIVE_RETRY_POLICY` | Rate-limited APIs (3 attempts, slow backoff) |
| `LLM_RETRY_POLICY` | LLM calls (handles rate limits, timeouts) |
| `DB_RETRY_POLICY` | Database operations (handles connection errors) |
| `API_RETRY_POLICY` | External APIs (handles 5xx, timeouts) |

## Pre-built Signal Types

| Signal | Purpose |
|--------|---------|
| `CANCEL_SIGNAL` | Request workflow cancellation |
| `PAUSE_SIGNAL` | Pause workflow execution |
| `RESUME_SIGNAL` | Resume paused workflow |
| `APPROVAL_SIGNAL` | Human approval/rejection |
| `FEEDBACK_SIGNAL` | User feedback on LLM output |

## Pre-built Query Types

| Query | Returns |
|-------|---------|
| `STATUS_QUERY` | Current workflow status |
| `PROGRESS_QUERY` | Progress percentage |
| `STATE_QUERY` | Full workflow state |
| `HISTORY_QUERY` | Event history |
| `METRICS_QUERY` | LLM calls, tokens, timing |

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Workflow Client                        │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   Task Queue (Redpanda)                  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │workflows│ │activities│ │   llm   │ │   rag   │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                    Worker Pool                           │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐           │
│  │Worker 1│ │Worker 2│ │Worker 3│ │Worker 4│           │
│  └────────┘ └────────┘ └────────┘ └────────┘           │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   Event Store (Redpanda)                 │
│  workflow.{id} topics with event history                │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                  Checkpoint Store                        │
│  Periodic snapshots for faster recovery                 │
└─────────────────────────────────────────────────────────┘
```

## Dependencies

Required:
- `asyncio` - Async execution

Optional:
- `aiokafka` - Redpanda/Kafka client (falls back to in-memory)
- `fastapi` - Dashboard API routes

## License

Apache-2.0
