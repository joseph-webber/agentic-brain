# Streaming

The voice system supports event streaming and durable queueing so audio can survive
process boundaries and temporary backend failures.

## Architecture

There are two related layers:

1. **Durable voice queue** in `src/agentic_brain/voice/redpanda_queue.py`
2. **Voice event bus** in `src/agentic_brain/events/voice_events.py`

```text
producer code / agents / app
          |
          v
+---------------------------+
| RedpandaVoiceQueue        |
| backend=auto              |
| redpanda -> redis -> mem  |
+-------------+-------------+
              |
              v
+---------------------------+
| voice processor           |
| - sorts by priority       |
| - speaks one item at time |
| - publishes status        |
+-------------+-------------+
              |
              v
+---------------------------+
| VoiceSerializer           |
| speech lock + watchdog    |
+-------------+-------------+
              |
              v
           playback

Parallel event path:

brain.voice.request  <- speech requested
brain.voice.status   <- started/completed/error
brain.voice.control  <- pause/resume/cancel-style messages
brain.voice.input    <- reserved for future input events
brain.llm.streaming  <- streamed LLM text
```

## Queue backends

`RedpandaVoiceQueue` supports:

- `auto` - try Redpanda, then Redis, then memory
- `redpanda`
- `redis`
- `memory`

Queue topic:

```text
agentic-brain-voice-queue
```

Default connection settings:

- `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`
- `REDIS_URL=redis://localhost:6379/0`

## Event topics

`voice_events.py` defines these topics:

| Topic | Purpose |
| --- | --- |
| `brain.voice.request` | New text-to-speech requests |
| `brain.voice.status` | Lifecycle updates such as started, completed, and error |
| `brain.voice.input` | Reserved for future speech input events |
| `brain.voice.control` | Control messages such as pause, resume, or cancel |
| `brain.llm.streaming` | LLM token or chunk streaming |

## Request and status payloads

### `VoiceRequest`

Important fields:

- `text`
- `voice`
- `rate`
- `priority` (0-100 in the event payload model)
- `spatial_position`
- `request_id`
- `timestamp`
- `wait_for_voiceover`
- `metadata`

### `VoiceStatus`

Important fields:

- `event`
- `text`
- `voice`
- `queue_depth`
- `request_id`
- `error`
- `timestamp`
- `metadata`

## Priority system

The durable queue uses `VoicePriority` from `redpanda_queue.py`.

| Level | Value | Typical use |
| --- | ---: | --- |
| `CRITICAL` | 15 | emergency speech |
| `URGENT` | 10 | warnings and immediate updates |
| `HIGH` | 8 | important notifications |
| `NORMAL` | 5 | standard conversation |
| `LOW` | 1 | background information |

Sorting rule:

1. higher priority first
2. older timestamp first within the same priority

## Redis queue details

`src/agentic_brain/voice/redis_queue.py` adds a simpler Redis queue with:

- `voice:queue` for normal jobs
- `voice:queue:priority` for high and urgent jobs
- `voice:state` for shared state such as speaking status and queue depth

This queue also exposes:

- `current_text`
- `current_voice`
- `current_voice`
- `queue_depth`
- `priority_depth`
- `normal_depth`

## Monitoring

### Voice worker watchdog

`src/agentic_brain/voice/watchdog.py` monitors the serializer worker.

Defaults:

- stall timeout: `15s`
- check interval: `5s`
- max restarts before alert: `3`

If a Redis client is attached, restart alerts are published to:

```text
brain.voice.watchdog
```

### Infrastructure health monitor

`src/agentic_brain/infra/health_monitor.py` monitors:

- Redis
- Neo4j
- Redpanda

Useful Redpanda detail:

- admin API port: `9644`

## Example: enqueue speech

```python
import asyncio

from agentic_brain.voice.redpanda_queue import RedpandaVoiceQueue, VoicePriority

async def main():
    queue = RedpandaVoiceQueue(backend="auto")
    await queue.connect()
    await queue.speak(
        "Deployment completed successfully.",
        voice="Karen",
        priority=VoicePriority.HIGH,
    )

asyncio.run(main())
```

## Example: publish events

```python
from agentic_brain.events.voice_events import VoiceRequest, get_voice_event_producer

producer = get_voice_event_producer()
producer.request_speech(
    VoiceRequest(
        text="Tingting is reviewing the pull request.",
        voice="Tingting",
        rate=155,
        priority=70,
    )
)
```

## Configuration

| Setting | Default | Purpose |
| --- | --- | --- |
| `AGENTIC_BRAIN_ENABLE_VOICE_EVENTS` | `false` | Enable the shared event producer |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Redpanda or Kafka bootstrap servers |
| `REDIS_URL` | `redis://localhost:6379/0` | Async Redis queue fallback |

## Failure behavior

- If Redpanda is unavailable, the queue falls back to Redis.
- If Redis is also unavailable, it falls back to memory.
- Memory mode keeps the app usable but removes durability across restarts.

See [Troubleshooting](./TROUBLESHOOTING.md) for queue, lock, and watchdog problems.
