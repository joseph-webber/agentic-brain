# Temporal.io to Agentic Brain Migration Guide

**Version**: 1.0  
**Status**: Complete  
**Date**: 2026

## Overview

This guide helps you migrate from Temporal.io to Agentic Brain's native durable execution engine. The migration is designed to be **seamless** - change your imports, and everything works.

### Why Migrate?

| Feature | Temporal.io | Agentic Brain |
|---------|-------------|---------------|
| Server Required | ✅ Yes (Go binary) | ❌ No server needed |
| Database | Cassandra/PostgreSQL/MySQL | SQLite (built-in) |
| Installation | Multi-step setup | `pip install agentic-brain` |
| Docker | Often required | Not required |
| Offline Mode | ❌ No | ✅ Yes |
| AI/LLM Native | ❌ No | ✅ Built-in |
| Time to Start | Minutes/hours | Seconds |

---

## Quick Migration (3 Steps)

### Step 1: Install Agentic Brain

```bash
pip install agentic-brain
```

### Step 2: Change Your Imports

Find and replace these imports in your codebase:

```python
# BEFORE (Temporal)
from temporalio import workflow, activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.testing import WorkflowEnvironment

# AFTER (Agentic Brain)
from agentic_brain.temporal import workflow, activity
from agentic_brain.temporal.client import Client
from agentic_brain.temporal.worker import Worker
from agentic_brain.temporal.testing import WorkflowEnvironment
```

### Step 3: Remove Temporal Server

Your workflows now run locally! Remove:
- Temporal server process
- Cassandra/PostgreSQL
- Docker containers
- `temporal.yaml` config files

**That's it!** Your existing workflow and activity code works unchanged.

---

## Detailed Migration

### Workflows

Workflow code requires **no changes**:

```python
from agentic_brain.temporal import workflow

@workflow.defn
class OrderWorkflow:
    @workflow.run
    async def run(self, order_id: str) -> str:
        # All Temporal patterns work:
        
        # Execute activities
        result = await workflow.execute_activity(
            process_order,
            order_id,
            start_to_close_timeout=timedelta(minutes=5),
        )
        
        # Durable sleep
        await workflow.sleep(timedelta(hours=24))
        
        # Get workflow info
        info = workflow.info()
        print(f"Workflow ID: {info.workflow_id}")
        
        return result
    
    @workflow.signal
    async def update_status(self, status: str) -> None:
        self.status = status
    
    @workflow.query
    def get_status(self) -> str:
        return self.status
```

### Activities

Activity code requires **no changes**:

```python
from agentic_brain.temporal import activity

@activity.defn
async def process_order(order_id: str) -> dict:
    # Get activity info
    info = activity.info()
    print(f"Processing on attempt {info.attempt}")
    
    # Heartbeat for long operations
    activity.heartbeat("Processing step 1")
    
    # Check for cancellation
    if activity.is_cancelled():
        raise activity.CancelledError()
    
    return {"order_id": order_id, "status": "processed"}
```

### Client

Client changes are minimal:

```python
from agentic_brain.temporal.client import Client

async def main():
    # Connect is instant - no server needed!
    # The address parameter is accepted for compatibility but ignored
    client = await Client.connect("localhost:7233")
    
    # Execute workflow (same API)
    result = await client.execute_workflow(
        OrderWorkflow.run,
        "order-123",
        id="order-workflow-1",
        task_queue="orders",
    )
    
    # Start workflow (same API)
    handle = await client.start_workflow(
        OrderWorkflow.run,
        "order-456",
        id="order-workflow-2",
        task_queue="orders",
    )
    
    # All handle operations work
    await handle.signal(OrderWorkflow.update_status, "shipped")
    status = await handle.query(OrderWorkflow.get_status)
    result = await handle.result()
```

### Worker

Worker code requires **no changes**:

```python
from agentic_brain.temporal.client import Client
from agentic_brain.temporal.worker import Worker

async def main():
    client = await Client.connect("localhost:7233")
    
    worker = Worker(
        client,
        task_queue="orders",
        workflows=[OrderWorkflow],
        activities=[process_order, send_email],
    )
    
    await worker.run()
```

### Testing

Test code requires **no changes**:

```python
import pytest
from agentic_brain.temporal.testing import (
    WorkflowEnvironment,
    ActivityEnvironment,
)

@pytest.mark.asyncio
async def test_order_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Time-skipping means workflow.sleep() is instant
        result = await env.client.execute_workflow(
            OrderWorkflow.run,
            "order-123",
            id="test-order",
            task_queue="test",
        )
        assert result["status"] == "completed"

@pytest.mark.asyncio
async def test_process_order_activity():
    env = ActivityEnvironment()
    result = await env.run(process_order, "order-123")
    assert result["order_id"] == "order-123"
```

---

## API Compatibility Reference

### workflow module

| Temporal API | Agentic Brain | Status |
|--------------|---------------|--------|
| `@workflow.defn` | `@workflow.defn` | ✅ Full |
| `@workflow.run` | `@workflow.run` | ✅ Full |
| `@workflow.signal` | `@workflow.signal` | ✅ Full |
| `@workflow.query` | `@workflow.query` | ✅ Full |
| `@workflow.update` | `@workflow.update` | ✅ Full |
| `workflow.execute_activity()` | `workflow.execute_activity()` | ✅ Full |
| `workflow.execute_local_activity()` | `workflow.execute_local_activity()` | ✅ Full |
| `workflow.sleep()` | `workflow.sleep()` | ✅ Full |
| `workflow.now()` | `workflow.now()` | ✅ Full |
| `workflow.info()` | `workflow.info()` | ✅ Full |
| `workflow.uuid4()` | `workflow.uuid4()` | ✅ Full |
| `workflow.random()` | `workflow.random()` | ✅ Full |
| `workflow.continue_as_new()` | `workflow.continue_as_new()` | ✅ Full |
| `workflow.wait_condition()` | `workflow.wait_condition()` | ✅ Full |
| `ContinueAsNewError` | `ContinueAsNewError` | ✅ Full |
| `ApplicationError` | `ApplicationError` | ✅ Full |

### activity module

| Temporal API | Agentic Brain | Status |
|--------------|---------------|--------|
| `@activity.defn` | `@activity.defn` | ✅ Full |
| `activity.heartbeat()` | `activity.heartbeat()` | ✅ Full |
| `activity.info()` | `activity.info()` | ✅ Full |
| `activity.is_cancelled()` | `activity.is_cancelled()` | ✅ Full |
| `activity.wait_for_cancelled()` | `activity.wait_for_cancelled()` | ✅ Full |
| `CancelledError` | `CancelledError` | ✅ Full |

### Client

| Temporal API | Agentic Brain | Status |
|--------------|---------------|--------|
| `Client.connect()` | `Client.connect()` | ✅ Full* |
| `client.execute_workflow()` | `client.execute_workflow()` | ✅ Full |
| `client.start_workflow()` | `client.start_workflow()` | ✅ Full |
| `client.get_workflow_handle()` | `client.get_workflow_handle()` | ✅ Full |
| `handle.result()` | `handle.result()` | ✅ Full |
| `handle.signal()` | `handle.signal()` | ✅ Full |
| `handle.query()` | `handle.query()` | ✅ Full |
| `handle.update()` | `handle.update()` | ✅ Full |
| `handle.cancel()` | `handle.cancel()` | ✅ Full |
| `handle.terminate()` | `handle.terminate()` | ✅ Full |
| `handle.describe()` | `handle.describe()` | ✅ Full |

*Note: `Client.connect()` is instant - no actual network connection needed.

### Worker

| Temporal API | Agentic Brain | Status |
|--------------|---------------|--------|
| `Worker()` | `Worker()` | ✅ Full |
| `worker.run()` | `worker.run()` | ✅ Full |
| `worker.shutdown()` | `worker.shutdown()` | ✅ Full |

### Testing

| Temporal API | Agentic Brain | Status |
|--------------|---------------|--------|
| `WorkflowEnvironment.start_time_skipping()` | Same | ✅ Full |
| `WorkflowEnvironment.start_local()` | Same | ✅ Full |
| `env.client` | `env.client` | ✅ Full |
| `env.sleep()` | `env.sleep()` | ✅ Full |
| `ActivityEnvironment` | `ActivityEnvironment` | ✅ Full |

---

## Advanced Features

### Async Completion

Complete activities from external systems:

```python
from agentic_brain.temporal import activity
from agentic_brain.temporal.activity import TaskToken

@activity.defn
async def wait_for_approval(order_id: str) -> dict:
    # Return task token for async completion
    info = activity.info()
    return {"task_token": str(info.task_token), "order_id": order_id}

# Later, from another process:
from agentic_brain.durability import AsyncCompletion

completion = AsyncCompletion()
await completion.complete(
    task_token="...",
    result={"approved": True}
)
```

### Sagas (Distributed Transactions)

Built-in saga pattern support:

```python
from agentic_brain.durability import Saga, SagaStep

async def book_trip(user_id: str, trip: dict):
    saga = Saga(
        name="book-trip",
        steps=[
            SagaStep(
                name="book-flight",
                action=book_flight,
                compensation=cancel_flight,
            ),
            SagaStep(
                name="book-hotel",
                action=book_hotel,
                compensation=cancel_hotel,
            ),
            SagaStep(
                name="book-car",
                action=book_car,
                compensation=cancel_car,
            ),
        ]
    )
    
    result = await saga.execute(user_id, trip)
    # If any step fails, previous steps are automatically compensated
```

### Workflow Versioning

Safe workflow upgrades:

```python
from agentic_brain.durability import WorkflowVersioning

@workflow.run
async def run(self, data: str):
    version = WorkflowVersioning.get_version("my-change", 1, 2)
    
    if version == 1:
        # Old logic
        result = await workflow.execute_activity(old_process, data)
    else:
        # New logic
        result = await workflow.execute_activity(new_process, data)
```

### AI-Native Features

Agentic Brain adds AI capabilities not in Temporal:

```python
from agentic_brain.durability import DurableLLM

@activity.defn
async def analyze_with_ai(text: str) -> dict:
    llm = DurableLLM()
    
    # Durable LLM calls - survives crashes!
    result = await llm.generate(
        model="gpt-4",
        prompt=f"Analyze: {text}",
        fallback=["claude-3", "llama-3"],  # Automatic fallback chain
    )
    
    return {"analysis": result}
```

---

## Troubleshooting

### ImportError: No module named 'agentic_brain.temporal'

Make sure you have the latest version:
```bash
pip install --upgrade agentic-brain
```

### Workflow doesn't persist after restart

Ensure SQLite database path is persistent:
```python
from agentic_brain.durability import DurableEngine

engine = DurableEngine(
    db_path="/var/lib/agentic-brain/workflows.db"  # Persistent path
)
```

### Activities not found

Make sure activities are registered with the worker:
```python
worker = Worker(
    client,
    task_queue="my-queue",
    workflows=[MyWorkflow],
    activities=[my_activity_1, my_activity_2],  # Register all activities
)
```

---

## Getting Help

- **Documentation**: https://github.com/joseph-webber/agentic-brain
- **Issues**: https://github.com/joseph-webber/agentic-brain/issues
- **Discussions**: https://github.com/joseph-webber/agentic-brain/discussions

---

## Migration Checklist

- [ ] Install agentic-brain: `pip install agentic-brain`
- [ ] Update imports from `temporalio` to `agentic_brain.temporal`
- [ ] Remove Temporal server and dependencies
- [ ] Run tests to verify everything works
- [ ] Deploy and enjoy zero-infrastructure durable workflows!

**Welcome to Agentic Brain!** 🧠✨
