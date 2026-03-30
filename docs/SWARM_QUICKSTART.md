# Swarm Development Quick Start

Use this guide to get a small Redis-coordinated swarm running in about 5 minutes.

## Prerequisites

- Redis running on `localhost:6379`
- Python 3.11+
- `agentic-brain` installed
- `redis` Python package available (`pip install "agentic-brain[redis]"` is the easiest option)

> Default Redis URL used by the swarm helpers: `redis://:BrainRedis2026@localhost:6379/0`

## How swarm coordination works

Each swarm gets its own namespace in Redis:

- `swarm:{swarm_id}:agents` - registered agents
- `swarm:{swarm_id}:tasks` - pending work
- `swarm:{swarm_id}:results` - completed results
- `swarm:channel:{swarm_id}` - pub/sub events

For a real project, prefer the `agentic_brain.swarm` helpers instead of writing raw Redis commands by hand.

## 5-Minute Tutorial

### Step 1: Start Redis

```bash
docker-compose up -d redis
# Or: redis-server
```

Quick check:

```bash
redis-cli -a BrainRedis2026 ping
# PONG
```

### Step 2: Create Your First Agent

Create `worker.py`:

```python
#!/usr/bin/env python3
import os
import time

from agentic_brain.swarm import AgentRegistry, SwarmCoordinator, TaskQueue

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
swarm_id = "quickstart-demo"
agent_id = os.environ.get("AGENT_ID", "agent-1")

coord = SwarmCoordinator.from_url(REDIS_URL)
registry = AgentRegistry(coord, swarm_id)
queue = TaskQueue(coord, swarm_id)

registry.register(agent_id, capabilities=["worker", "demo"])
print(f"{agent_id} registered!")

while True:
    task = queue.claim(agent_id=agent_id, timeout=5)
    if task is None:
        print(f"{agent_id}: no more tasks, exiting")
        break

    print(f"{agent_id} received: {task}")
    time.sleep(1)  # simulate work

    queue.complete(
        task["task_id"],
        result={
            "summary": f"{agent_id} finished {task['task']}",
            "category": "demo",
            "severity": "info",
        },
        agent_id=agent_id,
    )
    coord.heartbeat(swarm_id, agent_id)
```

Make it executable if you want:

```bash
chmod +x worker.py
```

### Step 3: Deploy Multiple Agents

Run 5 workers in parallel:

```bash
for i in 1 2 3 4 5; do
  AGENT_ID="agent-$i" python worker.py &
done
wait
```

What this does:

- starts 5 independent worker processes
- registers each one in Redis
- lets each worker claim tasks from the shared queue
- exits cleanly once the queue is empty

### Step 4: Distribute Tasks

In a second terminal, enqueue some work:

```python
from agentic_brain.swarm import SwarmCoordinator, TaskQueue

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
swarm_id = "quickstart-demo"

coord = SwarmCoordinator.from_url(REDIS_URL)
coord.start_swarm(swarm_id, total_tasks=3)

queue = TaskQueue(coord, swarm_id)
tasks = [
    {"task": "search github"},
    {"task": "analyze code"},
    {"task": "write tests"},
]

for task in tasks:
    queue.enqueue(task)
```

If you want to see the raw Redis shape, the helper above is effectively pushing JSON into `swarm:quickstart-demo:tasks`.

### Step 5: Collect Results

Once the workers finish, collect and summarize the results:

```python
from agentic_brain.swarm import FindingsAggregator, SwarmCoordinator

REDIS_URL = "redis://:BrainRedis2026@localhost:6379/0"
swarm_id = "quickstart-demo"

coord = SwarmCoordinator.from_url(REDIS_URL)
results = coord.get_results(swarm_id)
print(f"Got {len(results)} results!")

summary = FindingsAggregator(coord, swarm_id).aggregate()
print(summary.human_summary())

for finding in summary.top_findings():
    print("-", finding.summary)
```

## Raw Redis Version (Minimal Example)

If you want to understand the underlying Redis pattern first, this is the smallest possible version:

```python
#!/usr/bin/env python3
import json
import redis

swarm_id = "quickstart-demo"
r = redis.from_url("redis://:BrainRedis2026@localhost:6379/0", decode_responses=True)

# Register a simple ready flag
r.set(f"swarm:{swarm_id}:my_agent:ready", "true")
print("Agent registered!")

# Listen for coordination events on the swarm channel
pubsub = r.pubsub(ignore_subscribe_messages=True)
pubsub.subscribe(f"swarm:channel:{swarm_id}")

for message in pubsub.listen():
    data = json.loads(message["data"])
    print(f"Received: {data}")
```

For production swarms, use `SwarmCoordinator`, `AgentRegistry`, and `TaskQueue` so your keys stay consistent with the built-in implementation.

## Real-World Example

A voice workflow is a great fit for a swarm because different agents can specialize:

- **agent-1**: writes the spoken script
- **agent-2**: chooses the best voice/persona
- **agent-3**: renders audio
- **agent-4**: runs accessibility QA
- **agent-5**: publishes the final result

Example controller:

```python
from agentic_brain.swarm import SwarmCoordinator, TaskQueue

coord = SwarmCoordinator.from_url("redis://:BrainRedis2026@localhost:6379/0")
swarm_id = "voice-demo"
coord.start_swarm(swarm_id, total_tasks=5, metadata={"pipeline": "voice"})

queue = TaskQueue(coord, swarm_id)
queue.enqueue_many([
    {"task": "draft narration", "capability": "script"},
    {"task": "select voice", "capability": "voice"},
    {"task": "render audio", "capability": "audio"},
    {"task": "run VoiceOver QA", "capability": "accessibility"},
    {"task": "publish output", "capability": "delivery"},
])
```

In a fuller setup, you would give each worker a capability list and let the coordinator or registry route work to the best agent.

## Next Steps

- Read `SWARM_DEVELOPMENT.md` for the full guide if your checkout includes it
- Read `SWARM_API_REFERENCE.md` for swarm-specific API details if available
- In older checkouts, use `API_REFERENCE.md` plus `src/agentic_brain/swarm/*.py`
- Run `pytest tests/test_swarm_coordination.py -q` to verify swarm behavior locally

## Troubleshooting

### Redis connection failed

Check that Redis is running and the password is correct:

```bash
redis-cli -a BrainRedis2026 ping
```

### Workers exit immediately

That usually means the queue is empty. Start the workers, then enqueue tasks in a second terminal.

### No results collected

Make sure workers call `queue.complete(...)`. Claimed tasks stay inflight until they are completed or failed.
