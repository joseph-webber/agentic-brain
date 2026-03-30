# Swarm Coordination API Reference

The Redis swarm coordination system has two layers:

- `agentic_brain.smart_router.coordinator.RedisCoordinator` is the lightweight async coordinator used by the SmartRouter smash/fallback orchestration.
- `agentic_brain.swarm` provides the full Redis-backed swarm primitives used for multi-agent registration, queueing, event delivery, and findings aggregation. Its foundational class is `SwarmCoordinator`, which is consumed by `AgentRegistry`, `TaskQueue`, and `FindingsAggregator`.

The examples below use the local Redis instance configured for development.

## Redis Connection

```python
import redis

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
r = redis.from_url(REDIS_URL)
```

For the swarm package, the same URL is exposed as `REDIS_URL_DEFAULT` in `agentic_brain.swarm.redis_coordinator`.

## Imports

```python
from agentic_brain.smart_router.coordinator import RedisCoordinator
from agentic_brain.swarm import AgentRegistry, FindingsAggregator, SwarmCoordinator, TaskQueue
```

## Core Classes

### RedisCoordinator

Async helper from `agentic_brain.smart_router.coordinator` used by SmartRouter for distributed “first result wins” coordination.

#### Constructor

```python
RedisCoordinator(redis_url: str = "redis://localhost:6379")
```

#### Methods

##### `async connect() -> bool`
Attempts to connect to Redis using `redis.asyncio`.

- Returns `True` when Redis is reachable.
- Returns `False` and falls back to in-memory coordination when Redis is unavailable.
- Sets `self.client` to the Redis client on success, or `None` on failure.

##### `async publish_result(result: SmashResult) -> bool`
Publishes a `SmashResult` under `llm:response:{task_id}` using `SETNX` semantics.

- Returns `True` if this result is the first published result for that task.
- Returns `False` if another worker already won.
- When Redis is available, the winner key expires after 300 seconds.
- When Redis is unavailable, an in-memory dictionary provides the same “first write wins” behavior for the current process.

#### Notes

- `RedisCoordinator` is **not** the full swarm lifecycle API.
- For agent registration, task queues, and result aggregation, use `SwarmCoordinator` plus the higher-level swarm classes below.

### SwarmCoordinator

Primary Redis-backed coordinator from `agentic_brain.swarm.redis_coordinator`. It manages swarm lifecycle, agent registration, task distribution, result storage, and pub/sub events.

#### Factories

##### `from_url(url: str = REDIS_URL_DEFAULT) -> SwarmCoordinator`
Creates a coordinator from a Redis URL with `decode_responses=True` and a 5 second connect timeout.

##### `from_pool(pool_manager: Any) -> SwarmCoordinator`
Builds a coordinator from an existing Redis pool manager by reusing `pool_manager.client`.

#### Lifecycle methods

##### `start_swarm(swarm_id: str, *, total_tasks: int = 0, metadata: dict | None = None) -> None`
Initializes `swarm:{swarm_id}:status` and publishes a `swarm_started` event.

Stores:

- `status=running`
- `started_at`
- `total_tasks`
- `completed_tasks`
- `failed_tasks`
- any extra metadata

##### `finish_swarm(swarm_id: str, *, status: SwarmStatus = SwarmStatus.COMPLETED) -> None`
Marks the swarm as finished, writes `finished_at`, and publishes `swarm_finished`.

##### `swarm_status(swarm_id: str) -> dict[str, Any]`
Returns the swarm status hash plus computed counters:

- `swarm_id`
- `active_agents`
- `pending_tasks`
- `collected_results`

#### Agent methods

##### `register_agent(swarm_id: str, agent_id: str, *, capabilities: list[str] | None = None, metadata: dict | None = None, ttl: int = 60) -> None`
Registers an agent in the swarm hash and active set, creates a heartbeat TTL key, and publishes `agent_registered`.

##### `deregister_agent(swarm_id: str, agent_id: str) -> None`
Removes the agent hash entry, active set membership, and heartbeat key, then publishes `agent_deregistered`.

##### `heartbeat(swarm_id: str, agent_id: str, *, ttl: int = 60) -> None`
Renews the heartbeat TTL key for a registered agent.

##### `agent_status(swarm_id: str, agent_id: str) -> dict[str, Any] | None`
Returns the stored agent metadata only if the heartbeat key is still alive.

##### `active_agents(swarm_id: str) -> dict[str, dict[str, Any]]`
Returns all currently live agents keyed by `agent_id`.

#### Task methods

##### `push_task(swarm_id: str, task: dict[str, Any], *, task_id: str | None = None, priority: int = 0) -> str`
Pushes a task into the swarm task list, adds `task_id`, `priority`, and `enqueued_at`, then publishes `task_enqueued`.

##### `pull_task(swarm_id: str, *, timeout: int = 0) -> dict[str, Any] | None`
Pulls the next task.

- Uses `BRPOP` when `timeout > 0`.
- Uses `RPOP` for non-blocking reads.
- Returns `None` when no task is available.

##### `task_queue_depth(swarm_id: str) -> int`
Returns the number of pending tasks.

#### Result methods

##### `push_result(swarm_id: str, result: dict[str, Any]) -> None`
Stores a completed result, appends `stored_at`, increments `completed_tasks`, and publishes `result_stored`.

##### `get_results(swarm_id: str, *, limit: int = 0) -> list[dict[str, Any]]`
Reads stored results with `LRANGE`.

- `limit=0` means all results.
- Results are not removed from Redis.

##### `results_count(swarm_id: str) -> int`
Returns the total number of stored results.

#### Pub/sub methods

##### `publish(swarm_id: str, event: CoordinationEvent | dict[str, Any]) -> int`
Publishes an event to `swarm:channel:{swarm_id}` and returns the Redis publish count.

##### `subscribe(swarm_id: str) -> redis.client.PubSub`
Returns a Pub/Sub handle subscribed to the swarm channel.

##### `listen(swarm_id: str, callback: Callable[[CoordinationEvent], None], *, timeout: float = 0.1) -> None`
Continuously consumes swarm events and invokes `callback` until `shutdown()` is called.

##### `listen_in_thread(swarm_id: str, callback: Callable[[CoordinationEvent], None]) -> threading.Thread`
Starts `listen()` in a daemon thread and returns that thread.

#### Shutdown and health

##### `shutdown() -> None`
Signals listener threads to stop and joins the subscriber thread for up to 3 seconds.

##### `ping() -> bool`
Returns `True` when Redis is reachable.

### AgentRegistry

High-level registry from `agentic_brain.swarm.agent_registry` built on top of `SwarmCoordinator`.

```python
AgentRegistry(coordinator: SwarmCoordinator, swarm_id: str)
```

#### Methods

##### `register(agent_id: str | None = None, *, capabilities: list[str] | None = None, metadata: dict | None = None, ttl: int = 60) -> AgentProfile`
Registers an agent and returns its `AgentProfile`.

- Auto-generates an `agent_id` when omitted.
- Delegates storage and heartbeat setup to `SwarmCoordinator.register_agent()`.

##### `deregister(agent_id: str) -> None`
Removes an agent from the swarm.

##### `get(agent_id: str) -> AgentProfile | None`
Returns a live agent profile, including `active_tasks` from the workload key. Returns `None` if the heartbeat expired or the record is missing.

##### `all_active() -> list[AgentProfile]`
Returns all agents with live heartbeats.

##### `with_capability(capability: str) -> list[AgentProfile]`
Filters active agents to those advertising one capability.

##### `with_capabilities(required: list[str]) -> list[AgentProfile]`
Filters active agents to those that contain **all** required capabilities.

##### `pick(*, required_capabilities: list[str] | None = None, strategy: str = "least_loaded") -> AgentProfile | None`
Selects the best available agent.

Supported strategies:

- `least_loaded` — fewest `active_tasks`
- `random` — uniform random choice
- `round_robin` — oldest registration wins

Returns `None` if no matching agent is available.

##### `increment_workload(agent_id: str) -> int`
Increments the agent workload counter and returns the new count.

##### `decrement_workload(agent_id: str) -> int`
Decrements the workload counter, flooring at `0`.

##### `health_check(agent_id: str) -> dict[str, Any]`
Returns a health summary for one agent.

Healthy example fields:

- `agent_id`
- `healthy=True`
- `heartbeat_age_seconds`
- `active_tasks`
- `capabilities`

Expired example fields:

- `agent_id`
- `healthy=False`
- `reason="heartbeat_expired"`

##### `health_report() -> list[dict[str, Any]]`
Returns health records for every registered agent in the active set.

##### `prune_dead_agents() -> list[str]`
Removes agents whose heartbeat keys expired from the active set and returns the pruned agent IDs.

### TaskQueue

Reliable distributed queue from `agentic_brain.swarm.task_queue`.

```python
TaskQueue(
    coordinator: SwarmCoordinator,
    swarm_id: str,
    *,
    visibility_timeout: int = 120,
    max_retries: int = 3,
)
```

#### Delivery model

- Pending tasks live in a Redis list.
- Claimed tasks move into an inflight hash and timestamp sorted set.
- Failed tasks are retried until `max_retries` is exceeded.
- Permanently failed tasks move to a dead-letter list.
- `requeue_stalled()` re-enqueues inflight tasks whose visibility timeout elapsed.

#### Methods

##### `enqueue(task: dict[str, Any], *, task_id: str | None = None, priority: int = 0) -> str`
Enqueues a single task and returns its `task_id`.

##### `enqueue_many(tasks: list[dict[str, Any]], *, priority: int = 0) -> list[str]`
Pipelines multiple task inserts and returns the generated task IDs.

Each task is enriched with:

- `task_id`
- `priority`
- `enqueued_at`

##### `claim(*, agent_id: str | None = None, timeout: int = 0) -> dict[str, Any] | None`
Claims the next task from the pending queue.

The claimed task is updated with:

- `claimed_at`
- `agent_id`
- `state=inflight`

It is then stored in:

- `swarm:{swarm_id}:tasks:inflight` (hash)
- `swarm:{swarm_id}:tasks:inflight:ts` (sorted set for timeout scanning)

##### `complete(task_id: str, *, result: Any = None, agent_id: str | None = None) -> TaskResult`
Marks an inflight task as completed, stores it in the results list, removes inflight tracking, and returns a `TaskResult` with `state=completed`.

##### `fail(task_id: str, *, error: str = "unknown error", agent_id: str | None = None) -> TaskResult`
Marks an inflight task as failed.

Behavior:

- If retry budget remains, the task is re-enqueued and the returned `TaskResult.state` is `pending`.
- If retry budget is exhausted, the task is dead-lettered and `TaskResult.state` is `failed`.

##### `requeue_stalled() -> list[str]`
Re-enqueues stalled inflight tasks whose claim age exceeds `visibility_timeout`.

Returns the list of re-queued `task_id` values.

##### `stats() -> dict[str, int]`
Returns queue depth counters:

- `pending`
- `inflight`
- `completed`
- `failed`

##### `failed_tasks(*, limit: int = 0) -> list[dict[str, Any]]`
Returns permanently failed tasks from the dead-letter list.

- `limit=0` means all dead-lettered tasks.

### FindingsAggregator

Read-only result aggregation layer from `agentic_brain.swarm.findings_aggregator`.

```python
FindingsAggregator(
    coordinator: SwarmCoordinator,
    swarm_id: str,
    *,
    dedup_key: str = "task_id",
)
```

#### Methods

##### `aggregate(*, raw_results: list[dict[str, Any]] | None = None) -> AggregatedSummary`
Aggregates result records into `Finding` objects.

Behavior:

- Reads from `swarm:{swarm_id}:results` when `raw_results` is omitted.
- Deduplicates results using `dedup_key`.
- Groups findings by `category` and `severity`.
- Returns metadata with the deduplication count.

##### `merge(summaries: list[AggregatedSummary]) -> AggregatedSummary`
Merges multiple summaries, deduplicating by `task_id`.

Useful for combining sub-swarms into one report.

##### `store_to_neo4j(summary: AggregatedSummary, *, neo4j_session: Any = None) -> bool`
Persists an aggregated summary to Neo4j.

- Returns `True` on successful storage.
- Returns `False` when Neo4j is unavailable or persistence fails.
- Accepts an injected `neo4j_session` for tests or custom integrations.
- Lazily imports `agentic_brain.core.neo4j_pool.get_session()` when no session is supplied.

#### Related data models

##### `Finding`
Represents one normalized result entry.

Important fields:

- `task_id`
- `swarm_id`
- `category`
- `severity`
- `summary`
- `detail`
- `source_file`
- `agent_id`
- `stored_at`

Helper methods:

- `Finding.from_result(result: dict, swarm_id: str) -> Finding`
- `Finding.to_dict() -> dict`

##### `AggregatedSummary`
Represents the aggregate output for one swarm.

Important fields:

- `swarm_id`
- `total_results`
- `findings`
- `by_category`
- `by_severity`
- `aggregated_at`
- `metadata`

Helper properties and methods:

- `critical_count`
- `high_count`
- `human_summary() -> str`
- `top_findings(n: int = 5) -> list[Finding]`

## Redis Key Reference

### Legacy voice coordination keys

These are the keys used by the existing Redis-backed helper services in `router/gpt_backup.py` and `router/grok_helper.py`.

| Key Pattern | Type | Description |
|-------------|------|-------------|
| `voice:*_ready` | string | Agent ready status such as `voice:gpt_backup_ready` or `voice:grok_helper_ready` |
| `voice:*_status` | string | Human-readable current status for a helper agent |
| `voice:shared_state` | string (JSON) | Shared agent state used by voice-oriented coordination flows |
| `voice:coordination` | pubsub | Coordination channel used for helper events and announcements |
| `voice:coding_tasks` | list | GPT backup coding task queue |
| `voice:helper_tasks` | list | Grok helper task queue |
| `voice:*_results` | list | Historical result list for helpers such as `voice:gpt_backup_results` |
| `voice:*_last_result` | string (JSON) | Cached most recent helper result |
| `voice:gpt_backup_claim:{request_id}` | string | Claim lock that prevents duplicate handling of the same request |

### Swarm package keys

These are the keys used by `agentic_brain.swarm`.

| Key Pattern | Type | Description |
|-------------|------|-------------|
| `swarm:{swarm_id}:agents` | hash | Agent metadata JSON keyed by `agent_id` |
| `swarm:{swarm_id}:agents:set` | set | Active agent IDs |
| `swarm:{swarm_id}:status` | hash | Overall swarm status and counters |
| `swarm:{swarm_id}:hb:{agent_id}` | string | Heartbeat TTL key for liveness |
| `swarm:{swarm_id}:workload:{agent_id}` | string | Per-agent active task counter |
| `swarm:{swarm_id}:tasks` | list | Pending tasks |
| `swarm:{swarm_id}:tasks:inflight` | hash | Claimed tasks awaiting completion or failure |
| `swarm:{swarm_id}:tasks:inflight:ts` | sorted set | Claim timestamps used for visibility timeout recovery |
| `swarm:{swarm_id}:tasks:failed` | list | Dead-letter queue for exhausted tasks |
| `swarm:{swarm_id}:tasks:retry:{task_id}` | string | Retry counter for a task |
| `swarm:{swarm_id}:results` | list | Completed task results |
| `swarm:channel:{swarm_id}` | pubsub | Per-swarm coordination event channel |
| `llm:response:{task_id}` | string | SmartRouter winner record written by `RedisCoordinator.publish_result()` |

## Event Types

### Legacy helper events on `voice:coordination`

The helper services publish status and completion payloads rather than a strict event envelope. Common statuses and meanings are:

- `ready` — helper came online and is monitoring Redis
- `accepted` — GPT backup accepted a request and began work
- `completed` — helper finished successfully
- `error` — helper failed to complete a request

Useful payload fields include:

- `agent`
- `timestamp`
- `request_id`
- `in_reply_to`
- `prompt`
- `status`
- `answer` or `result`
- `provider`
- `model`
- `error`

### Swarm coordination events on `swarm:channel:{swarm_id}`

The swarm package uses a structured `CoordinationEvent` envelope:

```python
{
    "event_id": "7d2e4f1a",
    "event_type": "task_enqueued",
    "swarm_id": "pr-review-42",
    "agent_id": "worker-1",
    "payload": {"task_id": "..."},
    "timestamp": 1740000000.123,
}
```

Built-in event types emitted by the implementation:

- `swarm_started`
- `swarm_finished`
- `agent_registered`
- `agent_deregistered`
- `task_enqueued`
- `result_stored`

### Mapping to higher-level coordination concepts

If you are building UI or metrics around the swarm, these higher-level concepts map cleanly to the emitted statuses and events:

- `agent_ready` — use legacy helper `status=ready` or infer readiness after `agent_registered`
- `task_assigned` — emit your own coordination event when a worker claims a task, or infer from queue state changes
- `task_complete` — use legacy helper `status=completed` or swarm `result_stored`
- `swarm_complete` — use `swarm_finished`

## Code Examples

### Register an Agent

```python
from agentic_brain.swarm import AgentRegistry, SwarmCoordinator

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
swarm_id = "pr-review-42"

coord = SwarmCoordinator.from_url(REDIS_URL)
coord.start_swarm(swarm_id, total_tasks=3, metadata={"goal": "review PR 42"})

registry = AgentRegistry(coord, swarm_id)
agent = registry.register(
    "reviewer-1",
    capabilities=["python", "review", "security"],
    metadata={"provider": "copilot"},
    ttl=60,
)

print(agent.agent_id)
print(agent.capabilities)
print(registry.health_check(agent.agent_id))
```

### Submit a Task

```python
from agentic_brain.swarm import SwarmCoordinator, TaskQueue

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
swarm_id = "pr-review-42"

coord = SwarmCoordinator.from_url(REDIS_URL)
queue = TaskQueue(coord, swarm_id, visibility_timeout=120, max_retries=3)

# Producer
queue.enqueue_many(
    [
        {"action": "review", "file": "src/api.py", "category": "code_quality"},
        {"action": "review", "file": "src/auth.py", "category": "security"},
    ],
    priority=10,
)

# Worker
claimed = queue.claim(agent_id="reviewer-1", timeout=5)
if claimed:
    try:
        result_payload = {
            "task_id": claimed["task_id"],
            "file": claimed.get("file"),
            "severity": "info",
            "category": claimed.get("category", "general"),
            "summary": f"No issues in {claimed.get('file')}",
            "agent_id": claimed.get("agent_id"),
        }
        queue.complete(claimed["task_id"], result=result_payload, agent_id=claimed.get("agent_id"))
    except Exception as exc:
        queue.fail(claimed["task_id"], error=str(exc), agent_id=claimed.get("agent_id"))
```

### Collect Results

```python
from agentic_brain.swarm import FindingsAggregator, SwarmCoordinator

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
swarm_id = "pr-review-42"

coord = SwarmCoordinator.from_url(REDIS_URL)
agg = FindingsAggregator(coord, swarm_id)

summary = agg.aggregate()
print(summary.human_summary())

for finding in summary.top_findings(5):
    print(f"[{finding.severity}] {finding.summary}")

stored = agg.store_to_neo4j(summary)
print({"stored_to_neo4j": stored})

coord.finish_swarm(swarm_id)
```

### Listen for Coordination Events

```python
from agentic_brain.swarm import CoordinationEvent, SwarmCoordinator

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
swarm_id = "pr-review-42"

coord = SwarmCoordinator.from_url(REDIS_URL)


def on_event(event: CoordinationEvent) -> None:
    print(event.event_type, event.payload)

thread = coord.listen_in_thread(swarm_id, on_event)
coord.publish(
    swarm_id,
    CoordinationEvent(
        event_type="agent_ready",
        swarm_id=swarm_id,
        agent_id="reviewer-1",
        payload={"capabilities": ["python", "review"]},
    ),
)

# Later
coord.shutdown()
thread.join(timeout=3)
```
