# `agentic_brain.voice`

High‑reliability, accessibility‑first voice stack for Agentic Brain. This package provides cross‑platform text‑to‑speech, live conversational audio, cloud TTS backends, and event‑driven streaming while guaranteeing that speech never overlaps.

The module is designed so applications can start with a single safe `speak_safe()` call and scale up to low‑latency, bi‑directional voice conversations.

---

## Architecture overview

### Public entry points

- **`agentic_brain.voice.speak_safe()`** – primary synchronous TTS API; routes all speech through `VoiceSerializer`.
- **`agentic_brain.voice.unified.UnifiedVoiceSystem`** – façade that wires serializer, watchdog, daemon gate, live mode, and stream consumer behind a single object.
- **`agentic_brain.voice.stream`** – async voice event producer/consumer for Redpanda/Kafka.
- **`agentic_brain.voice.streaming_api.VoiceStreamingAPI`** – optional WebSocket server for raw‑audio → transcription.
- **Project Aria live stack** – `live_session`, `conversation_loop`, `transcription`, `vad`, and `live_daemon` for full duplex voice conversations.

### Core layers

1. **Global speech lock (`_speech_lock.RedisVoiceLock`)**  
   Distributed mutex (Redis + local fallback) guaranteeing that only one process may speak at a time.

2. **Serializer (`serializer.VoiceSerializer`)**  
   Process‑local singleton with a worker thread and queue, responsible for:
   - Sequential execution of TTS jobs
   - Overlap audits using `audit_no_concurrent_say()`
   - Optional async APIs and integration with a Redis‑backed queue

3. **Queue and resilient fallback**  
   - `queue.VoiceQueue` – higher‑level queue with per‑voice policies (e.g. number spelling for some languages).  
   - `resilient.ResilientVoice` – cross‑platform fallback chain (macOS, Windows, Linux, cloud) that is used when system‑level speech fails.

4. **Event streaming and observability**  
   - `events` and `stream` – strongly‑typed voice events and Redpanda/Kafka producer/consumer wrappers.  
   - `redis_queue` / `redis_summary` – queueing and summary statistics in Redis.  
   - `watchdog.VoiceWatchdog` – monitors worker threads and restarts them when necessary.

5. **Live and conversational voice**  
   - `live_mode.LiveVoiceMode` – low‑latency text‑stream → sentence → TTS pipeline.  
   - `live_session.LiveVoiceSession` – microphone‑driven live session with wake‑words, VAD and silence detection.  
   - `live_daemon.LiveVoiceDaemon` – background daemon wrapper around `LiveVoiceSession`.  
   - `conversation_loop.VoiceConversationLoop` – end‑to‑end real‑time conversation loop (mic → VAD → transcription → LLM → TTS).  
   - `conversation.ConversationalVoice` – multi‑voice conversation helper used for non‑critical interactions.

6. **Analysis, memory and adaptation**  
   - `transcription` – pluggable STT engines (whisper.cpp, faster‑whisper, macOS dictation) with accuracy metrics.  
   - `vad` – Silero‑based voice activity detection.  
   - `memory` – Neo4j‑backed long‑term voice memory and semantic retrieval.  
   - `speed_profiles` – adaptive speaking‑rate profiles and content‑aware speed tiers.  
   - `user_regions` – regional language and phrasing preferences.

7. **Engines and bridges**  
   - `platform`, `linux`, `windows` – platform detection and native TTS helpers.  
   - `cloud_tts`, `cartesia_tts`, `kokoro_engine`, `kokoro_tts`, `tts_fallback` – neural and cloud engines plus a robust fallback chain.  
   - `cartesia_bridge` – connects `LiveVoiceMode` to Cartesia streaming for ultra‑low‑latency playback.  
   - `neural_router` – routes between Apple system voices and Kokoro neural TTS.

---

## Quick start

### 1. Basic text‑to‑speech

```python
from agentic_brain.voice import speak_safe

# Speak a short message using the configured system voice
speak_safe("Hello world")
``` 

`sp
eak_safe()` automatically:

- Chooses the active speaking rate from `speed_profiles`
- Acquires the global speech lock
- Queues the utterance through `VoiceSerializer`

### 2. Unified voice façade

```python
from agentic_brain.voice.unified import get_unified

uv = get_unified()
uv.speak("System check complete")

# Optional live mode
uv.start_live()
uv.feed_live("This sentence will be spoken as soon as it is complete.")
uv.flush_live()
uv.stop_live()

# Status and health
status = uv.status()["summary"]
print(status)
```

### 3. Asynchronous speech via event streaming

```python
from agentic_brain.voice import get_voice_event_producer
from agentic_brain.voice.events import VoiceSpeechRequested

producer = get_voice_event_producer()
request = VoiceSpeechRequested(text="Background notification")
producer.publish(request)
```

A corresponding `VoiceEventConsumer` (usually running in a daemon) picks up the request and routes it into `VoiceSerializer`.

### 4. WebSocket streaming API (speech‑to‑text)

```python
import asyncio
from agentic_brain.voice.streaming_api import VoiceStreamingAPI

api = VoiceStreamingAPI()

async def transcribe(audio: bytes):
    # Replace with real STT integration; this echo shows the protocol.
    return {"text": f"{len(audio)} bytes received", "is_final": False}

api.set_transcriber(transcribe)

asyncio.run(api.start())
```

Clients can stream raw audio over WebSockets and receive JSON transcription updates.

---

## Configuration

### Environment variables

The voice system is primarily configured via environment variables and the `VoiceConfig` dataclass in `voice.config`.

#### Core voice settings

- `AGENTIC_BRAIN_VOICE` – default TTS voice name (macOS voice on Apple platforms).  
- `AGENTIC_BRAIN_LANGUAGE` – BCP‑47 language code (for example `en-AU`, `en-US`).  
- `AGENTIC_BRAIN_RATE` – speaking rate in words per minute.  
- `AGENTIC_BRAIN_PITCH` – pitch multiplier (1.0 = normal).  
- `AGENTIC_BRAIN_VOLUME` – volume multiplier (0.0–1.0).  
- `AGENTIC_BRAIN_VOICE_PROVIDER` – high‑level provider hint (`system`, `azure`, `google`, `aws`, `elevenlabs`, etc.).  
- `AGENTIC_BRAIN_VOICE_ENABLED` – set to `0`/`false` to disable speech (for CI or headless servers).  
- `AGENTIC_BRAIN_VOICE_QUALITY` – `standard`, `premium`, or `neural`.

#### Routing and infrastructure

- `AGENTIC_BRAIN_STEREO_PAN_ENABLED` – enable per‑persona stereo panning when available.  
- `AGENTIC_BRAIN_VOICE_USE_REDPANDA` – publish async speech through Redpanda/Kafka instead of speaking in‑process.  
- `KAFKA_BOOTSTRAP_SERVERS` – comma‑separated list of brokers for `VoiceEventProducer`/`VoiceStreamConsumer`.

#### Cartesia Sonic 3

Used by `cartesia_tts` and `cloud_tts.speak_cartesia`:

- `CARTESIA_API_KEY` – required API key.  
- `CARTESIA_VOICE_ID` – default Cartesia voice identifier.  

#### Cloud TTS providers

Used by `cloud_tts.speak_cloud`:

- **gTTS** – no configuration required beyond network access.  
- **Azure Speech**:  
  - `AZURE_SPEECH_KEY` – subscription key.  
  - `AZURE_SPEECH_REGION` – region identifier.  
- **AWS Polly**:  
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional `AWS_REGION`.  

#### Local LLM voice and conversation

- `OLLAMA_HOST` – base URL for the local Ollama instance used by `llm_voice` and some conversation flows.  

#### Voice memory and storage

- `AGENTIC_BRAIN_VOICE_CLONE_DIR` – root directory for `voice_library` cloned‑voice data.  
- Neo4j and Redis configuration is inherited from core Agentic Brain settings and used by `memory` and `_speech_lock` respectively.

### `VoiceConfig` and `LanguagePack`

`voice.config` exposes two core dataclasses:

```python
from agentic_brain.voice.config import VoiceConfig, LANGUAGE_PACKS

config = VoiceConfig()
print(config.voice_name, config.language, config.rate)

au_pack = LANGUAGE_PACKS["en-AU"]
print(au_pack.code, au_pack.default_voice)
```

`VoiceConfig` binds environment variables into a strongly‑typed configuration object, while `LANGUAGE_PACKS` maps language codes to default and fallback voices.

---

## Voice engines

The stack is designed to integrate several engines. Some are fully implemented today; others are planned and wired via configuration.

### macOS system voices

- Implemented via the built‑in `say` command.  
- Used by `serializer.VoiceSerializer`, `queue.VoiceQueue`, `resilient.ResilientVoice`, and `tts_fallback.TTSFallbackChain`.  
- Voice metadata is defined in `registry.ALL_MACOS_VOICES` and related helpers.

### Cartesia Sonic 3

- Implemented in `cartesia_tts.CartesiaTTS` and `cloud_tts.speak_cartesia`.  
- Provides low‑latency neural TTS with optional streaming output.  
- Used directly by `tts_fallback` and the Cartesia bridge for live mode.

### Piper (planned)

- The architecture allows adding a local Piper backend as another neural engine.  
- A typical integration would mirror `kokoro_tts.KokoroVoice`, implementing a small synth class that returns raw audio bytes and wiring it into `tts_fallback` and/or `neural_router`.

### ElevenLabs (planned)

- `VoiceConfig.provider` accepts `"elevenlabs"` as a provider hint.  
- A future engine can consume an ElevenLabs API key and voice ID, then be wired through `cloud_tts.speak_cloud` and `tts_fallback` similarly to Cartesia.  
- Until such an engine is implemented, ElevenLabs should be treated as an extension point rather than an active backend.

### Other engines and helpers

- **Kokoro** – neural TTS implementation in `kokoro_engine` / `kokoro_tts`, used by `neural_router` and `tts_fallback`.  
- **Linux / Windows** – native speech support via `linux.speak_linux` and `windows.speak_windows`, always called from within serializer‑controlled executors.  
- **Cloud fallbacks** – gTTS, Azure Speech, and AWS Polly in `cloud_tts`.

---

## Usage examples

### Synchronous speech

```python
from agentic_brain.voice import speak_safe

speak_safe("Build completed successfully")
```

### Asynchronous, event‑driven speech

```python
from agentic_brain.voice import speak_async

# Queue speech to be handled by a background consumer
speak_async("Background task finished")
```

### Live text streaming (LLM token stream)

```python
from agentic_brain.voice.live_mode import LiveVoiceMode

live = LiveVoiceMode()
live.start()

for token in ["This ", "sentence ", "will ", "be ", "spoken."]:
    live.feed(token)

live.flush()
live.stop()
```

### Live voice session (microphone + wake word)

```python
from agentic_brain.voice.live_session import LiveSessionConfig, LiveVoiceSession

config = LiveSessionConfig()
session = LiveVoiceSession(config=config)

if session.start():
    # Session runs until stopped or times out
    status = session.status()
    print(status)
    session.stop()
```

### Inspecting availability and health

```python
from agentic_brain.voice.platform import check_voice_available, get_platform_info
from agentic_brain.voice.cloud_tts import check_cloud_tts_available

platform_info = get_platform_info()
local_voices = check_voice_available()
cloud_voices = check_cloud_tts_available()

print(platform_info["detected_platform"], local_voices, cloud_voices)
```

This README is intended as a high‑level guide. For deeper details, see the individual module docstrings in the `agentic_brain.voice` package.
