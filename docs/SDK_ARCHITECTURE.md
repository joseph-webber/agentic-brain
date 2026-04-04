# Agentic Brain SDK

Universal AI orchestration SDK for building intelligent applications.

## Core Features

### 1. Multi-LLM Layered Responses
- **Instant Layer** (0-500ms): Groq, local Ollama
- **Fast Layer** (500ms-2s): Claude Haiku, GPT-4o-mini
- **Deep Layer** (2-10s): Claude Opus, GPT-4, Gemini Pro
- **Consensus Layer** (10s+): Multi-LLM verification

### 2. Deployment Modes
- **Airlocked**: 100% local (Ollama, whisper.cpp, Piper TTS)
- **Cloud**: Remote APIs only (OpenAI, Anthropic, Google)
- **Hybrid**: Local-first with cloud fallback (recommended)

### 3. Interface Types
- **Terminal Chat**: CLI-based interaction
- **Live Chat**: Real-time voice + text
- **API Server**: REST/WebSocket endpoints
- **SDK Library**: Embeddable in any app

### 4. Autonomous Agents
- Self-healing error recovery
- Background task orchestration
- Event-driven via Redpanda/Kafka

## SDK Structure

```
agentic-brain/
├── sdk/
│   ├── python/           # Python SDK
│   │   ├── agentic_brain/
│   │   │   ├── __init__.py
│   │   │   ├── client.py      # Main SDK client
│   │   │   ├── llm/           # LLM providers
│   │   │   ├── voice/         # Voice I/O
│   │   │   ├── agents/        # Autonomous agents
│   │   │   └── chat/          # Chat interfaces
│   │   └── pyproject.toml
│   ├── swift/            # Swift SDK (macOS/iOS)
│   │   └── AgenticBrain/
│   ├── typescript/       # TypeScript SDK (Node/Browser)
│   │   └── agentic-brain/
│   └── rust/             # Rust SDK (high-performance)
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Application                     │
├─────────────────────────────────────────────────┤
│              AgenticBrain Client                 │
│  ┌───────────┬────────────┬───────────────────┐ │
│  │ Terminal   │ Live Chat  │ API Server        │ │
│  │ Chat SDK   │ SDK        │ (REST/WS)         │ │
│  └─────┬─────┴─────┬──────┴────────┬──────────┘ │
│        │           │               │             │
│  ┌─────▼───────────▼───────────────▼──────────┐ │
│  │          Agent Orchestrator                 │ │
│  │  ┌─────────┐ ┌──────────┐ ┌─────────────┐  │ │
│  │  │ Self-   │ │ Task     │ │ Event-      │  │ │
│  │  │ Healing │ │ Scheduler│ │ Driven Bus  │  │ │
│  │  └─────────┘ └──────────┘ └─────────────┘  │ │
│  └────────────────────┬────────────────────────┘ │
│                       │                          │
│  ┌────────────────────▼────────────────────────┐ │
│  │            LLM Layer Orchestrator            │ │
│  │  ┌────────┐ ┌───────┐ ┌──────┐ ┌─────────┐ │ │
│  │  │Instant │ │ Fast  │ │ Deep │ │Consensus│ │ │
│  │  │<500ms  │ │<2s    │ │<10s  │ │  10s+   │ │ │
│  │  │Groq    │ │Haiku  │ │Opus  │ │Multi-LLM│ │ │
│  │  │Ollama  │ │GPT-4m │ │GPT-4 │ │Verify   │ │ │
│  │  └────────┘ └───────┘ └──────┘ └─────────┘ │ │
│  └─────────────────────────────────────────────┘ │
│                       │                          │
│  ┌────────────────────▼────────────────────────┐ │
│  │           Voice Manager                      │ │
│  │  ┌──────────┐  ┌───────────┐  ┌──────────┐  │ │
│  │  │ STT      │  │ TTS       │  │ Voice    │  │ │
│  │  │ Whisper  │  │ Piper     │  │ Activity │  │ │
│  │  │ Groq     │  │ Cartesia  │  │ Detect   │  │ │
│  │  │ Deepgram │  │ ElevenLabs│  │          │  │ │
│  │  └──────────┘  └───────────┘  └──────────┘  │ │
│  └─────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│              Deployment Mode Router              │
│  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Airlocked│  │  Cloud   │  │    Hybrid     │  │
│  │ (Local)  │  │ (Remote) │  │ (Local+Cloud) │  │
│  └──────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────┘
```

## Deployment Modes Detail

### Airlocked Mode (100% Local)
No network calls. Everything runs on-device.

| Component | Local Provider |
|-----------|---------------|
| LLM | Ollama (llama3, mistral, phi-3) |
| STT | whisper.cpp (Apple Neural Engine) |
| TTS | Piper TTS, macOS `say` |
| Embeddings | nomic-embed-text via Ollama |
| Event Bus | In-process queue |

### Cloud Mode (100% Remote)
All processing via cloud APIs. Minimal local compute.

| Component | Cloud Provider |
|-----------|---------------|
| LLM | OpenAI, Anthropic, Google, Groq |
| STT | Groq Whisper, Deepgram |
| TTS | Cartesia, ElevenLabs |
| Embeddings | OpenAI, Cohere |
| Event Bus | Redpanda Cloud / Confluent |

### Hybrid Mode (Recommended)
Local-first with intelligent cloud fallback.

| Priority | Provider | Fallback |
|----------|----------|----------|
| 1st | Ollama (local) | → Groq (fast cloud) |
| 2nd | Groq (cloud, free) | → Claude Haiku |
| 3rd | Claude Opus | → GPT-4 |
| 4th | Multi-LLM consensus | All available |

## Quick Start

### Python
```python
from agentic_brain import AgenticBrain

brain = AgenticBrain(mode="hybrid")
response = await brain.chat("Hello!", layers=["instant", "deep"])
```

### Swift
```swift
import AgenticBrain

let brain = AgenticBrain(mode: .hybrid)
let response = try await brain.chat("Hello!", layers: [.instant, .deep])
```

### TypeScript
```typescript
import { AgenticBrain } from 'agentic-brain';

const brain = new AgenticBrain({ mode: 'hybrid' });
const response = await brain.chat('Hello!', { layers: ['instant', 'deep'] });
```

## Event System

The SDK uses an event-driven architecture for agent communication:

```python
from agentic_brain import AgenticBrain
from agentic_brain.agents import Agent

brain = AgenticBrain(mode="hybrid")

@brain.on("user.message")
async def handle_message(event):
    response = await brain.chat(event.text, layers=["instant"])
    await brain.emit("bot.response", response)

@brain.on("agent.error")
async def handle_error(event):
    await brain.agents.self_heal(event.agent_id, event.error)
```

## Configuration

```yaml
# brain-config.yaml
agentic_brain:
  mode: hybrid
  layers:
    instant:
      providers: [ollama, groq]
      timeout_ms: 500
    fast:
      providers: [claude-haiku, gpt-4o-mini]
      timeout_ms: 2000
    deep:
      providers: [claude-opus, gpt-4, gemini-pro]
      timeout_ms: 10000
    consensus:
      min_providers: 3
      agreement_threshold: 0.8
  voice:
    stt: [whisper-local, groq-whisper]
    tts: [piper, cartesia, macos-say]
  agents:
    self_heal: true
    max_retries: 3
    event_bus: redpanda
```
