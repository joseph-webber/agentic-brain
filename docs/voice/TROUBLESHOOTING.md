# Voice Troubleshooting

This guide focuses on the most common voice-system failures after the Phase 2 upgrade.

## Quick checks

Start with these questions:

1. Is the serializer running?
2. Is Redis reachable?
3. Is the voice backend `native`, `sox`, or `mono`?
4. Are there overlapping `say` processes?
5. Did the watchdog restart the worker?

## Common issues

### Voices overlap

**Symptoms**

- two voices speak at once
- words are hard to understand
- speech sounds doubled or clipped

**What normally prevents this**

- `VoiceSerializer` queues speech on one worker thread
- `audit_no_concurrent_say()` checks for multiple `say` processes
- `_speech_lock.py` holds the Redis key `voice:speaking`

**Fixes**

1. Route speech through the serializer instead of spawning `say` directly.
2. Check whether `VOICE_AUDIT_DISABLED` is set by mistake.
3. Confirm Redis is up so cross-process locking works.
4. If Redis is down, remember only process-local locking remains.

### Speech never starts

**Symptoms**

- queue depth grows
- no sound plays
- state may still show pending items

**Fixes**

1. Check the serializer worker and watchdog logs.
2. Check Redis state in `voice:state`.
3. Verify the selected output path works:
   - `native`
   - `sox`
   - `mono`
4. If debugging, force a simpler backend such as `mono`.

### Lock issues

The distributed speech lock uses:

- key: `voice:speaking`
- TTL: `30s`
- heartbeat renewal: every `10s`

**Common causes**

- Redis unavailable
- one process held the lock and then stalled
- another process bypassed the serializer

**Fixes**

1. Verify Redis connectivity and credentials.
2. Wait for the TTL to expire if a process crashed mid-speech.
3. Restart the stalled process if it still owns the lock.
4. Do not add direct `say` calls outside the serializer path.

### Redis connection failures

**Symptoms**

- queue falls back to memory
- cross-process lock protection disappears
- shared voice state is empty or stale

**Relevant settings**

```text
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=BrainRedis2026
REDIS_DB=0
```

**Fixes**

1. Confirm Redis is running.
2. Confirm the password matches the deployment.
3. Confirm the client can `PING`.
4. Recheck whether your app is using `REDIS_URL` or the host/port/password fields.

### Watchdog alerts

The serializer starts `VoiceWatchdog` with:

- stall timeout: `15s`
- check interval: `5s`
- alert threshold: `3` consecutive failures

**Symptoms**

- log messages about worker restarts
- repeated “voice may be degraded” messages
- optional Redis publishes on `brain.voice.watchdog`

**Fixes**

1. Check for a blocked or dead worker thread.
2. Look for backend commands hanging, especially `say`, `sox`, or `afplay`.
3. Reduce moving parts while debugging:
   - force `mono`
   - disable event publishing
   - test Redis separately

### Spatial audio is not working

**Symptoms**

- all voices sound centered
- AirPods are connected but head tracking is not active

**Fixes**

1. Inspect `router.status()` from `SpatialAudioRouter`.
2. Confirm whether the backend is `native`, `sox`, or `mono`.
3. If you expected native mode, verify:
   - Apple toolchain is available
   - Swift bridge files exist
   - AirPods are connected
4. If you expected Sox mode, verify `sox`, `say`, and `afplay` are installed.

### Redpanda is unavailable

**Symptoms**

- durable queueing is missing
- backend drops from `redpanda` to `redis` or `memory`

**Fixes**

1. Confirm `KAFKA_BOOTSTRAP_SERVERS` is correct.
2. Confirm the broker is listening.
3. Check the Redpanda admin health endpoint if infrastructure monitoring is enabled.
4. If needed, force `redis` or `memory` while you repair the broker.

### Voice events are missing

**Symptoms**

- no `brain.voice.*` messages appear

**Fixes**

1. Check `AGENTIC_BRAIN_ENABLE_VOICE_EVENTS`.
2. Confirm Kafka connectivity.
3. Confirm the producer can be created lazily without import errors.

### Live mode commands are missing

That is expected.
Live mode, wake word handling, and whisper.cpp are not implemented in this repo today.

## Useful inspection points

### Queue state

`RedisVoiceQueue.get_state()` exposes:

- `is_speaking`
- `current_text`
- `current_voice`
- `current_voice`
- `queue_depth`
- `priority_depth`
- `normal_depth`

### Spatial router status

```python
from agentic_brain.audio.spatial_audio import get_spatial_router

print(get_spatial_router().status())
```

### Voice event topics

- `brain.voice.request`
- `brain.voice.status`
- `brain.voice.input`
- `brain.voice.control`
- `brain.llm.streaming`

## Recovery strategy summary

| Problem | First fallback | Final fallback |
| --- | --- | --- |
| Redpanda down | Redis | memory queue |
| Redis down | local thread lock | same-process safety only |
| Native spatial down | Sox stereo pan | mono |
| Sox unavailable | mono | mono |

## Related docs

- [Voice system overview](./README.md)
- [Spatial audio](./SPATIAL_AUDIO.md)
- [Streaming](./STREAMING.md)
- [Live mode](./LIVE_MODE.md)
