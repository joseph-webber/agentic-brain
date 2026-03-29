# Temporal.io Integration

Durable workflow execution for the agentic-brain platform.

## Overview

Temporal.io provides fault-tolerant, durable execution for long-running workflows. Workflows can:
- **Survive crashes** - Resume from last checkpoint
- **Handle failures** - Automatic retries with exponential backoff
- **Scale horizontally** - Multiple workers processing tasks
- **Track history** - Full audit trail of all executions
- **Support patterns** - Saga, human-in-the-loop, scheduled, child workflows

## Installation

Temporal.io is included as a core dependency:

```bash
pip install agentic-brain
```

## Quick Start

### 1. Start Temporal Server

Using Docker Compose (recommended):

```bash
# In agentic-brain directory
cd docker
docker-compose up -d temporal

# Or start all services
docker-compose up -d
```

Temporal will be available at:
- Frontend: http://localhost:8088
- Server: localhost:7233

### 2. Start a Worker

Workers poll for tasks and execute workflows/activities:

```bash
agentic temporal-worker

# Custom configuration
agentic temporal-worker \
  --host localhost:7233 \
  --namespace production \
  --task-queue my-queue
```

### 3. Execute a Workflow

```bash
# RAG workflow
agentic temporal-run rag query-123 \
  --args '{"query": "What is Temporal?", "collection": "docs", "top_k": 5}'

# Agent workflow with tools
agentic temporal-run agent task-456 \
  --args '{"task": "Research competitors", "tools": ["search", "scrape"]}'

# Commerce workflow (e-commerce order)
agentic temporal-run commerce order-789 \
  --args '{"items": [{"id": "prod1", "price": 29.99}], "method": "credit_card"}'

# Long-running analysis
agentic temporal-run analysis data-001 \
  --args '{"dataset": "/data/customers.csv", "type": "sentiment"}'
```

### 4. Check Status

```bash
# List all workflows
agentic temporal-list

# Filter by type
agentic temporal-list --query 'WorkflowType="RAGWorkflow"'

# Get specific workflow status
agentic temporal-status query-123
```

## Available Workflows

### RAGWorkflow

Retrieval-Augmented Generation with vector search:

```python
from agentic_brain.workflows.temporal import RAGWorkflow, TemporalClient

client = TemporalClient()
await client.connect()

result = await client.start_workflow(
    RAGWorkflow,
    workflow_id="query-123",
    task_queue="agentic-brain",
    args=["What is RAG?", "docs", 5, "gpt-4"],
)
```

**Steps:**
1. Vector search for relevant documents
2. LLM query with retrieved context
3. Return response with sources

### AgentWorkflow

Multi-step reasoning agent with tool usage:

```python
from agentic_brain.workflows.temporal import AgentWorkflow

result = await client.start_workflow(
    AgentWorkflow,
    workflow_id="task-456",
    task_queue="agentic-brain",
    args=["Research AI trends", 10, ["search", "scrape"]],
)
```

**Features:**
- Iterative reasoning loop
- Tool selection and execution
- Context accumulation
- Automatic stopping condition

### CommerceWorkflow

E-commerce order processing with saga pattern:

```python
from agentic_brain.workflows.temporal import CommerceWorkflow

result = await client.start_workflow(
    CommerceWorkflow,
    workflow_id="order-789",
    task_queue="agentic-brain",
    args=[
        "order-789",
        [{"id": "prod1", "price": 29.99}],
        "credit_card",
        {"street": "123 Main St", "city": "Adelaide"},
    ],
)
```

**Steps with compensation:**
1. Reserve inventory (compensation: release)
2. Process payment (compensation: refund)
3. Create shipment
4. Send confirmation

If any step fails, compensations run in reverse order.

### LongRunningAnalysisWorkflow

Data analysis with checkpoints:

```python
from agentic_brain.workflows.temporal import LongRunningAnalysisWorkflow

result = await client.start_workflow(
    LongRunningAnalysisWorkflow,
    workflow_id="analysis-001",
    task_queue="agentic-brain",
    args=["/data/dataset.csv", "sentiment", 1000],
)
```

**Features:**
- Processes data in batches
- Checkpoints every N records
- Can pause/resume safely
- Aggregates results at end

## Durable Execution Patterns

### Saga Pattern

Distributed transactions with compensations:

```python
from agentic_brain.workflows.temporal.patterns import SagaPattern
from temporalio import workflow

@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self):
        saga = SagaPattern()
        
        # Add steps with compensations
        saga.add_step(
            "reserve_inventory",
            reserve_activity,
            release_activity,
            {"items": [...]},
        )
        
        saga.add_step(
            "charge_payment",
            charge_activity,
            refund_activity,
            {"amount": 100},
        )
        
        # Execute with auto-rollback on failure
        return await saga.execute()
```

### Human-in-the-Loop

Workflows that wait for human approval:

```python
from agentic_brain.workflows.temporal.patterns import HumanInTheLoopWorkflow

# Start workflow
handle = await client.start_workflow(
    HumanInTheLoopWorkflow,
    workflow_id="approval-123",
    task_queue="agentic-brain",
    args=["Deploy to production", None],  # None = wait forever
)

# Later: approve or reject
await handle.signal(HumanInTheLoopWorkflow.approval, "Looks good!")
# or
await handle.signal(HumanInTheLoopWorkflow.rejection, "Not ready")

# Get result
result = await handle.result()
```

### Scheduled Workflows

Execute tasks on a schedule:

```python
from agentic_brain.workflows.temporal.patterns import ScheduledWorkflow

# Run every hour for 24 hours
result = await client.start_workflow(
    ScheduledWorkflow,
    workflow_id="health-check",
    task_queue="agentic-brain",
    args=["Check system health", 3600, 24],
)
```

### Child Workflows

Parallel or sequential child workflow execution:

```python
from agentic_brain.workflows.temporal.patterns import ChildWorkflowManager
from temporalio import workflow

@workflow.defn
class ParentWorkflow:
    @workflow.run
    async def run(self):
        # Execute children in parallel
        results = await ChildWorkflowManager.execute_parallel_children(
            RAGWorkflow,
            [
                {"id": "q1", "args": ["What is AI?"]},
                {"id": "q2", "args": ["What is ML?"]},
                {"id": "q3", "args": ["What is DL?"]},
            ],
        )
        return results
```

## Activities

Reusable tasks that workflows call:

### llm_query

```python
from agentic_brain.workflows.temporal import activities

result = await workflow.execute_activity(
    activities.llm_query,
    args=["What is Temporal?", {}, "gpt-4"],
    start_to_close_timeout=timedelta(seconds=60),
)
```

### vector_search

```python
documents = await workflow.execute_activity(
    activities.vector_search,
    args=["AI trends", "docs", 10],
    start_to_close_timeout=timedelta(seconds=30),
)
```

### database_operation

```python
result = await workflow.execute_activity(
    activities.database_operation,
    args=["create_user", {"name": "Alice", "email": "alice@example.com"}],
    start_to_close_timeout=timedelta(seconds=30),
)
```

### external_api_call

```python
response = await workflow.execute_activity(
    activities.external_api_call,
    args=["payment_gateway", {"amount": 100, "method": "card"}],
    start_to_close_timeout=timedelta(seconds=60),
)
```

### process_file

```python
result = await workflow.execute_activity(
    activities.process_file,
    args=["sentiment_analysis", "/data/reviews.csv", 0, 1000],
    start_to_close_timeout=timedelta(minutes=10),
    heartbeat_timeout=timedelta(seconds=30),
)
```

### send_notification

```python
await workflow.execute_activity(
    activities.send_notification,
    args=["email", {"to": "user@example.com", "subject": "Order complete"}],
    start_to_close_timeout=timedelta(seconds=10),
)
```

## Configuration

### Connection

```python
from agentic_brain.workflows.temporal import TemporalConfig, TemporalClient

config = TemporalConfig(
    host="temporal.example.com:7233",
    namespace="production",
    tls_enabled=True,
    tls_cert_path="/path/to/cert.pem",
    tls_key_path="/path/to/key.pem",
    tls_ca_path="/path/to/ca.pem",
)

client = TemporalClient(config)
await client.connect()
```

### Worker

```python
from agentic_brain.workflows.temporal import TemporalWorker

worker = TemporalWorker(
    task_queue="my-queue",
    config=config,
    max_concurrent_activities=100,
    max_concurrent_workflows=100,
)

await worker.start()
```

## Best Practices

### 1. Workflow Determinism

Workflows must be deterministic - same inputs = same execution path:

✅ **DO:**
```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self):
        # Use workflow.now() for time
        now = workflow.now()
        
        # Use workflow.random() for randomness
        random_val = workflow.random().random()
        
        # Execute activities for side effects
        result = await workflow.execute_activity(...)
```

❌ **DON'T:**
```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self):
        # DON'T use datetime.now()
        now = datetime.now()
        
        # DON'T use random.random()
        random_val = random.random()
        
        # DON'T make API calls directly
        response = requests.get("...")
```

### 2. Activity Retries

Configure retries for transient failures:

```python
from temporalio.common import RetryPolicy

result = await workflow.execute_activity(
    my_activity,
    retry_policy=RetryPolicy(
        initial_interval=timedelta(seconds=1),
        maximum_interval=timedelta(minutes=5),
        maximum_attempts=10,
        backoff_coefficient=2.0,
    ),
)
```

### 3. Activity Heartbeats

For long-running activities, send heartbeats:

```python
@activity.defn
async def process_large_file(path: str):
    for i, chunk in enumerate(read_chunks(path)):
        # Send heartbeat with progress
        activity.heartbeat({"progress": i})
        
        # Process chunk
        process(chunk)
```

### 4. Workflow Timeouts

Set appropriate timeouts:

```python
handle = await client.start_workflow(
    MyWorkflow,
    workflow_id="task-123",
    task_queue="queue",
    execution_timeout=timedelta(hours=24),  # Max workflow duration
    run_timeout=timedelta(hours=12),        # Max single run
    task_timeout=timedelta(minutes=5),      # Max decision task
)
```

### 5. Error Handling

Use try/except for business logic errors:

```python
@workflow.defn
class MyWorkflow:
    @workflow.run
    async def run(self):
        try:
            result = await workflow.execute_activity(...)
            return WorkflowResult(success=True, data=result)
        except Exception as e:
            workflow.logger.error(f"Failed: {e}")
            return WorkflowResult(success=False, error=str(e))
```

## Monitoring

### Temporal Web UI

Access at http://localhost:8088 to:
- View workflow executions
- See workflow history
- Debug failed workflows
- Monitor worker health

### CLI Status

```bash
# List recent workflows
agentic temporal-list --limit 50

# Filter by status
agentic temporal-list --query 'ExecutionStatus="Running"'

# Check specific workflow
agentic temporal-status my-workflow-123
```

## Testing

Unit tests with Temporal test environment:

```python
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

@pytest.mark.asyncio
async def test_my_workflow():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test",
            workflows=[MyWorkflow],
            activities=[my_activity],
        ):
            result = await env.client.execute_workflow(
                MyWorkflow.run,
                "input",
                id="test-123",
                task_queue="test",
            )
            
            assert result.success is True
```

## Production Deployment

### Docker Compose

```yaml
services:
  temporal:
    image: temporalio/auto-setup:latest
    ports:
      - "7233:7233"
      - "8088:8088"
    environment:
      - DB=postgresql
      - POSTGRES_HOST=postgres
      - POSTGRES_USER=temporal
      - POSTGRES_PWD=temporal
    depends_on:
      - postgres
  
  worker:
    build: .
    command: agentic temporal-worker --host temporal:7233
    depends_on:
      - temporal
    environment:
      - TEMPORAL_HOST=temporal:7233
```

### Kubernetes

Use [Temporal Helm Chart](https://github.com/temporalio/helm-charts):

```bash
helm install temporal temporalio/temporal \
  --set server.replicaCount=3 \
  --set worker.replicaCount=5
```

## License

MIT © 2026 Agentic Brain Contributors
