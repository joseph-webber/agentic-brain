# Voice System

Agentic Brain's voice stack is built for accessible, low-friction audio output.
Phase 2 strengthened four areas:

- **Safety:** one speaker at a time through the global serializer and speech lock
- **Orientation:** optional stereo and spatial positioning so each lady has a place
- **Durability:** Redis and Redpanda-backed queueing with memory fallback
- **Recovery:** watchdog monitoring so stalled voice workers restart automatically

This guide is the entry point for the voice docs set:

- [Spatial audio](./SPATIAL_AUDIO.md)
- [Live mode status](./LIVE_MODE.md)
- [Streaming and events](./STREAMING.md)
- [Troubleshooting](./TROUBLESHOOTING.md)

## Accessibility-first goals

The voice system is designed so a blind user can:

- hear status updates clearly
- tell who is speaking
- avoid overlapping speech
- recover from backend failures without losing all audio

## Quick start

### CLI

```bash
ab voice list --primary
ab voice speak "Hello Joseph" -v "Karen (Premium)"
ab voice mode work
ab voice conversation --demo
```

### Demo script

```bash
python demo_voice_system.py
```

### Python

```python
from agentic_brain.voice.serializer import speak_serialized

speak_serialized("Voice system ready", voice="Karen", rate=155)
```

## Architecture

```text
CLI / app code / agents
        |
        v
+---------------------------+
| Conversation + mode layer |
| - work / life / quiet     |
| - topic-based speaker     |
+-------------+-------------+
              |
              v
+---------------------------+
| VoiceSerializer           |
| - single worker thread    |
| - queue                   |
| - overlap audit           |
| - watchdog heartbeat      |
+-------------+-------------+
              |
              v
+---------------------------+
| Global speech lock        |
| - Redis distributed lock  |
| - local lock fallback     |
+------+------+-------------+
       |      |
       |      +-------------------------------+
       v                                      v
+----------------------+          +------------------------------+
| Spatial / stereo     |          | Durable queueing + events    |
| - native AirPods     |          | - Redpanda voice queue       |
| - Sox panning        |          | - Redis queue fallback       |
| - mono fallback      |          | - brain.voice.* topics       |
+----------+-----------+          +---------------+--------------+
           |                                          |
           +-------------------+----------------------+
                               v
                    +----------------------+
                    | TTS / playback path  |
                    | - Apple voices       |
                    | - Kokoro voices      |
                    | - Resilient fallback |
                    +----------------------+
```

## Core modules

| Module | Purpose |
| --- | --- |
| `src/agentic_brain/voice/serializer.py` | Single serialized speech path with overlap auditing and watchdog integration |
| `src/agentic_brain/voice/_speech_lock.py` | Cross-process Redis lock on `voice:speaking`, with local lock fallback |
| `src/agentic_brain/voice/conversation.py` | Work, life, and quiet modes plus speaker selection |
| `src/agentic_brain/audio/spatial_audio.py` | 3D lady positions and backend selection: `native`, `sox`, `mono` |
| `src/agentic_brain/audio/stereo_pan.py` | Left/right panning for any stereo output |
| `src/agentic_brain/audio/airpods.py` | AirPods discovery, routing, battery, and head-tracking support |
| `src/agentic_brain/voice/redpanda_queue.py` | Durable async queue with Redpanda → Redis → memory fallback |
| `src/agentic_brain/voice/redis_queue.py` | Redis queue, shared state, and audio cache |
| `src/agentic_brain/events/voice_events.py` | Event topics and request/status payloads |
| `src/agentic_brain/voice/kokoro_engine.py` | Kokoro-82M neural voice routing for the ladies |
| `src/agentic_brain/voice/watchdog.py` | Worker heartbeat monitoring and restart alerts |

## The 14 spatial ladies

The spatial ring in `audio/spatial_audio.py` places **14 ladies** around the listener.
These are the fixed positions used by the spatial router.

| Lady | Position | Voice mapping | Documented role or note |
| --- | ---: | --- | --- |
| Karen | 0° | `Karen (Premium)` | Lead host, center front |
| Kyoko | 30° | `Kyoko` | Quality and JIRA; fun/travel only |
| Tingting | 55° | `Ting-Ting` | Analytics and PR review |
| Yuna | 80° | `Yuna` | Tech and social; fun/travel only |
| Linh | 110° | `Linh` | GitHub operations |
| Kanya | 140° | `Kanya` | Wellness and mindfulness |
| Dewi | 165° | `Damayanti` | Indonesian trio, Jakarta-side position |
| Sari | 180° | `Damayanti` | Indonesian trio, directly behind |
| Wayan | 195° | `Damayanti` | Indonesian trio, Bali-side position |
| Moira | 225° | `Moira` | Creative and debugging |
| Alice | 255° | `Alice` | Italian persona in the left arc |
| Zosia | 285° | `Zosia` | Security and quality |
| Flo | 315° | `Amelie` | Code review specialist |
| Shelley | 345° | `Shelley` | Deployment and production |

### Important roster note

The wider voice registry also contains **Damayanti** and **Sinji**.
They are valid personas in `voice/registry.py` and `voice/kokoro_engine.py`, but they are
**not part of the 14-position spatial ring** defined in `audio/spatial_audio.py`.

## Configuration

### Core voice settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `AGENTIC_BRAIN_VOICE` | `Karen` | Default voice name |
| `AGENTIC_BRAIN_LANGUAGE` | `en-AU` | Default language pack |
| `AGENTIC_BRAIN_RATE` | `160` | Speaking rate |
| `AGENTIC_BRAIN_PITCH` | `1.0` | Pitch multiplier |
| `AGENTIC_BRAIN_VOLUME` | `0.8` | Playback volume hint |
| `AGENTIC_BRAIN_VOICE_PROVIDER` | `system` | Voice backend: `system`, `azure`, `google`, `aws`, `elevenlabs` |
| `AGENTIC_BRAIN_VOICE_QUALITY` | `premium` | `standard`, `premium`, `neural` |
| `AGENTIC_BRAIN_VOICE_ENABLED` | `true` | Master enable flag |

### Spatial and audio routing

| Setting | Default | Purpose |
| --- | --- | --- |
| `AGENTIC_BRAIN_STEREO_PAN_ENABLED` | `true` | Enable stereo panning in supported paths |
| `AGENTIC_BRAIN_STEREO_PAN_DIR` | repo `.cache/stereo_pan` | Where panned audio files are generated |
| `AGENTIC_BRAIN_AUDIO_SCRATCH` | `~/.cache/agentic-brain/spatial` | Scratch area for spatial audio rendering |

### Streaming and backend settings

| Setting | Default | Purpose |
| --- | --- | --- |
| `AGENTIC_BRAIN_ENABLE_VOICE_EVENTS` | `false` | Enable shared voice event producer |
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Redpanda/Kafka bootstrap servers |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for async queue fallback |
| `REDIS_HOST` | `localhost` | Redis host for the distributed speech lock |
| `REDIS_PORT` | `6379` | Redis port for the distributed speech lock |
| `REDIS_PASSWORD` | `BrainRedis2026` | Redis password used by the lock and queue |
| `REDIS_DB` | `0` | Redis database number |
| `VOICE_AUDIT_DISABLED` | unset | Disables process-table overlap auditing when set truthy |
| `VOICE_LOCK_TIMEOUT_SECONDS` | `30` | How long the serializer waits for the shared speech lock |
| `VOICE_STARTUP_SILENCE_SECONDS` | serializer default | Delay before the worker begins speaking after startup |

### Mode file

Conversation mode is also stored in:

```text
~/.brain-voice-mode
```

Supported values:

- `work`
- `life`
- `quiet`

## Related docs

- [Spatial audio](./SPATIAL_AUDIO.md)
- [Live mode](./LIVE_MODE.md)
- [Streaming](./STREAMING.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
