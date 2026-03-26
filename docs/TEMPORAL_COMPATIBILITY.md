# Temporal.io Compatibility Audit

Agentic Brain ships a Temporal.io-compatible API layer in
`agentic_brain.temporal` built on the durable workflow engine in
`agentic_brain.durability`. This provides drop-in support for common
Temporal workflow patterns without requiring a Temporal cluster.

## Feature Compatibility Matrix

| Feature | Temporal.io | Agentic Brain | Status |
|--------|-------------|---------------|--------|
| Workflow definitions (durable functions) | `@workflow.defn` classes with `@workflow.run` methods executed by Temporal workers against a Temporal cluster. | `agentic_brain.temporal.workflow.defn` and `workflow.run` wrap `durability.DurableWorkflow`, recording events in `EventStore` for replay and crash recovery. | ✅ Fully supported |
| Activity definitions | `@activity.defn` decorated callables scheduled via `workflow.execute_activity`. | `agentic_brain.temporal.activity.defn` tags callables and dispatches to `DurableWorkflow.execute_activity` with durable event logging and retries. | ✅ Fully supported |
| Workflow signals | `@workflow.signal` methods invoked via `WorkflowHandle.signal`, delivered through Temporal’s signal subsystem. | `workflow.signal` delegates to `durability.signal_handler`; `WorkflowHandle.signal` uses `SignalDispatcher` and `SignalHandler` to deliver typed signals with buffering and history. | ✅ Fully supported |
| Workflow queries | `@workflow.query` methods invoked via `WorkflowHandle.query`. | `workflow.query` uses `durability.query_handler`; `WorkflowHandle.query` routes through `QueryDispatcher` to strongly-typed query handlers. | ✅ Fully supported |
| Retry policies with backoff | Activity/workflow retry policies with exponential backoff and jitter. | `durability.RetryPolicy`, `with_retry` decorator and `DurableWorkflow.execute_activity` implement exponential backoff, jitter and non-retryable error filters; Temporal-style activities use these under the hood. | ✅ Fully supported |
| Timeouts and heartbeats | Activity timeouts (schedule/start-to-close, heartbeat) and heartbeats for long-running work. | `durability.activity_timeouts` and `heartbeat` support schedule/start-to-close and heartbeat timeouts; `temporal.activity.info` and `activity.heartbeat` mirror Temporal semantics, feeding into the same timeout logic. | ✅ Fully supported |
| Child workflows | Parent workflows starting and awaiting child workflows. | `durability.child_workflows` plus Temporal-style `client.start_workflow`/`execute_workflow` allow workflows to orchestrate other workflows using the same event-sourced engine. | ✅ Fully supported |
| Saga pattern | Orchestrated distributed transactions with compensating actions. | `durability.saga` (`Saga`, `SagaExecutor`, `saga_step`) provides a first-class Saga implementation; Temporal workflows can call into this module to model compensating transactions. | ✅ Fully supported |

## Implementation Notes

- **Durability core** lives in `src/agentic_brain/durability/`.
- **Temporal compatibility** lives in `src/agentic_brain/temporal/`.
- `docs/integrations/TEMPORAL.md` and `docs/TEMPORAL_MIGRATION_GUIDE.md` document the full API surface, matching `temporalio` modules (`workflow`, `activity`, `client`, `worker`, `testing`).

Key modules:

- `durability.state_machine.DurableWorkflow` – event-sourced workflow engine
- `durability.retry.RetryPolicy` – exponential backoff with jitter
- `durability.activity_timeouts.ActivityTimeouts` – preset timeout profiles
- `durability.signals` / `durability.queries` – signal and query dispatchers
- `durability.saga` – Saga pattern implementation
- `temporal.workflow` / `temporal.activity` – decorator and helper shims
- `temporal.client.Client` / `temporal.worker.Worker` – Temporal-style client/worker
- `temporal.testing.WorkflowEnvironment` / `ActivityEnvironment` – test utilities

## Tests

Temporal compatibility is covered by:

- `tests/test_temporal_compatibility.py` – API-level compatibility tests
- `tests/e2e/test_temporal_e2e.py` – end-to-end Temporal-style workflows (opt-in via `RUN_TEMPORAL_E2E=true`)
- `tests/test_durability.py` / `tests/test_durability_complete.py` – durability engine behaviour
- `tests/test_temporal_compat.py` – lightweight CI smoke tests for:
  - `test_workflow_execution()` – workflow through Temporal API + durability
  - `test_activity_retry()` – retry semantics on durable activities
  - `test_workflow_signals()` – durable signal delivery via `SignalHandler`
  - `test_state_persistence()` – `EventStore` records workflow events

## Redis Working-Bee Channel

To announce Temporal audits or background work to other agents, you can
publish a message on Redis:

```python
import json

import redis

r = redis.Redis()
r.publish(
    "agentic-brain:working-bee",
    json.dumps(
        {
            "agent": "gpt-temporal",
            "features_checked": 8,
            "status": "auditing",
        }
    ),
)
```

This requires the optional Redis dependency (for example,
`pip install "agentic-brain[redis]"` or `pip install redis`).

## Summary

The audit confirms that Agentic Brain’s `temporal` layer and
`durability` engine together provide full support for the listed
Temporal.io workflow patterns, with CI coverage in
`tests/test_temporal_compat.py` and deeper integration tests available
when enabled.
