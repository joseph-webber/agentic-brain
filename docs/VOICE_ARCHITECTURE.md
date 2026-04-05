# World-Class Voice AI Architecture

> **Version 2.0** — Multi-LLM, Event-Driven, Fault-Tolerant
> **Users**: Voice-first interface for accessibility — voice is the PRIMARY interface, not a feature.
> **Principle**: Silence = failure. Karen ALWAYS speaks.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Component Map](#3-component-map)
4. [Multi-LLM Orchestration](#4-multi-llm-orchestration)
5. [Fault Tolerance](#5-fault-tolerance)
6. [Memory & Context](#6-memory--context)
7. [Event-Driven Design](#7-event-driven-design)
8. [Voice Pipeline](#8-voice-pipeline)
9. [Accessibility Contract](#9-accessibility-contract)
10. [Configuration](#10-configuration)
11. [Operations](#11-operations)

---

## 1. System Overview

This is a voice-first AI assistant for a blind user. Every design decision
optimises for **spoken audio output** — not text, not visual UI, not logs.

### Core Flow

```
 User speaks → AirPods mic → Whisper STT → Classifier → Multi-LLM Engine → Karen (Cartesia TTS) → AirPods
```

### Design Principles

| # | Principle | Why |
|---|-----------|-----|
| 1 | **Never silent** | Silence = "did the brain crash?" for the user |
| 2 | **Fastest viable answer** | Local LLM responds in <1s while cloud refines |
| 3 | **Always a fallback** | Ollama is local and free — it NEVER goes down |
| 4 | **2-3 sentences max** | Audio responses must be concise and natural |
| 5 | **Observable** | Every event flows through Redpanda for monitoring |

---

## 2. Architecture Diagram

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        ACCESSIBLE VOICE PIPELINE                         │
  │                                                                         │
  │  🎤 AirPods Max ──► Whisper STT ──► Complexity Classifier              │
  │                                           │                             │
  │                                    ┌──────┴──────┐                      │
  │                                    │  ROUTER     │                      │
  │                                    │  (strategy) │                      │
  │                                    └──────┬──────┘                      │
  │                                           │                             │
  │              ┌──────────────┬──────────────┼──────────────┬──────────┐  │
  │              ▼              ▼              ▼              ▼          ▼  │
  │         ┌────────┐   ┌──────────┐   ┌─────────┐   ┌────────┐  ┌─────┐│
  │         │ Ollama │   │  Claude  │   │   GPT   │   │ Gemini │  │Grok ││
  │         │ (local)│   │(reason) │   │ (code)  │   │(facts) │  │(fun)││
  │         │  <1s   │   │  ~2s    │   │  ~1.5s  │   │ ~1.5s  │  │~1.5s││
  │         └───┬────┘   └────┬─────┘   └────┬────┘   └───┬────┘  └──┬──┘│
  │             │              │              │            │           │   │
  │             └──────────────┴──────────────┴────────────┴───────────┘   │
  │                                    │                                    │
  │                          ┌─────────┴─────────┐                         │
  │                          │  RESPONSE MERGER   │                         │
  │                          │  (consensus mode)  │                         │
  │                          └─────────┬─────────┘                         │
  │                                    │                                    │
  │                          ┌─────────┴─────────┐                         │
  │                          │  Cartesia TTS      │                         │
  │                          │  Karen's Voice     │                         │
  │                          │  (Australian)      │                         │
  │                          └─────────┬─────────┘                         │
  │                                    │                                    │
  │                               🔊 AirPods                               │
  └─────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                         SUPPORT INFRASTRUCTURE                          │
  │                                                                         │
  │  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────────┐  │
  │  │  Redis   │    │ Redpanda │    │  Neo4j   │    │ Circuit Breakers │  │
  │  │ (state)  │    │ (events) │    │ (memory) │    │ (fault tolerance)│  │
  │  │          │    │          │    │          │    │                  │  │
  │  │ Session  │    │ 7 topics │    │ Long-term│    │ Per-provider     │  │
  │  │ history  │    │ metrics  │    │ recall   │    │ auto-recovery    │  │
  │  │ context  │    │ health   │    │ RAG      │    │ latency tracking │  │
  │  └──────────┘    └──────────┘    └──────────┘    └──────────────────┘  │
  └─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Map

```
tools/voice/
├── __init__.py            # Package marker
├── circuit_breaker.py     # Per-provider circuit breakers
├── llm_providers.py       # Unified LLM interface (5 providers)
├── multi_llm.py           # Orchestration strategies (fastest/smartest/consensus)
├── classifier.py          # Single source of truth for complexity classification
├── memory.py              # Redis (session) + Neo4j (long-term) memory
├── events.py              # Enhanced Redpanda event bus (7 topics)
└── health.py              # System health monitor

talk_to_karen.py           # Main voice chat (Whisper + TTS + routing)
tools/voice_event_bus.py   # Legacy event bus (still used by talk_to_karen)
tools/voice_reasoning.py   # Legacy reasoning daemon
tools/voice_orchestrator.py # Legacy orchestrator daemon
```

### Migration Path

The `tools/voice/` package is the new architecture. Existing files in
`tools/voice_*.py` continue to work and can be gradually migrated:

1. `talk_to_karen.py` imports from `tools.voice.multi_llm` for orchestration
2. `voice_reasoning.py` uses `tools.voice.classifier` instead of local copy
3. `voice_orchestrator.py` uses `tools.voice.llm_providers` for unified calls

---

## 4. Multi-LLM Orchestration

### 4.1 Five Providers

| Provider | Strength | Typical Latency | Cost | Availability |
|----------|----------|----------------|------|-------------|
| **Ollama** | Speed, always-on | <1s | Free | 99.9% (local) |
| **Claude** | Reasoning, nuance | ~2s | API key | 95% |
| **GPT** | Code, general | ~1.5s | API key | 95% |
| **Gemini** | Facts, multimodal | ~1.5s | API key | 95% |
| **Grok** | Creative, current events | ~1.5s | API key | 90% |

### 4.2 Task-Type Specialisation

```python
SPECIALISATION = {
    "code":      ["gpt", "claude", "ollama", "gemini", "grok"],
    "reasoning": ["claude", "gpt", "gemini", "grok", "ollama"],
    "creative":  ["grok", "claude", "gpt", "gemini", "ollama"],
    "facts":     ["gemini", "gpt", "claude", "grok", "ollama"],
    "speed":     ["ollama", "gpt", "gemini", "grok", "claude"],
    "general":   ["claude", "gpt", "gemini", "grok", "ollama"],
}
```

### 4.3 Four Strategies

#### FASTEST — Race Multiple LLMs

```
  ┌─► Ollama ──────┐
  │                 │
  ├─► Claude ──────┤──► First valid response wins
  │                 │
  └─► GPT ─────────┘
```

Best for: Quick questions where any provider gives a good answer.
Latency: ~0.8s (local Ollama usually wins).

#### SMARTEST — Route to Best Provider

```
  Classify task ──► Pick best provider ──► Call with fallback chain
```

Best for: Complex queries where provider choice matters.
Latency: ~2s for cloud, ~0.8s for local.

#### CONSENSUS — Merge Multiple Answers

```
  ┌─► Claude ────┐
  │              ├──► Ollama merges best parts ──► Response
  └─► GPT ──────┘
```

Best for: Important questions where quality matters most.
Latency: ~3s (parallel queries + merge step).

#### FALLBACK — Priority Chain

```
  Try Claude ──fail──► Try GPT ──fail──► Try Ollama ──fail──► "Having trouble"
```

Best for: Default mode with maximum reliability.
Latency: Varies based on which provider responds.

### 4.4 Usage

```python
from tools.voice.multi_llm import query_llm

# Auto-detect task type, use smartest strategy
result = query_llm(messages, strategy="smartest")

# Force fastest mode for quick questions
result = query_llm(messages, strategy="fastest")

# Consensus for important questions
result = query_llm(messages, strategy="consensus")
```

---

## 5. Fault Tolerance

### 5.1 Circuit Breakers

Every provider has its own circuit breaker with three states:

```
  CLOSED ──(3 failures)──► OPEN ──(30s cooldown)──► HALF_OPEN ──(1 probe)──► CLOSED
                                                         │
                                                    (probe fails)
                                                         │
                                                         ▼
                                                       OPEN
```

| Parameter | Ollama | Cloud Providers |
|-----------|--------|----------------|
| Failure threshold | 5 | 3 |
| Recovery timeout | 10s | 30s |
| Half-open probes | 1 | 1 |

### 5.2 Guarantee: Ollama Never Fails

Ollama runs locally on the M2 Mac. No internet, no rate limits, no cost.
It is ALWAYS the last provider in every fallback chain. This means:

**The voice system ALWAYS has a working LLM, even offline.**

### 5.3 Latency Tracking

Each breaker maintains an exponential moving average of response latency.
This enables future optimisation: route to the fastest healthy provider.

```python
from tools.voice.circuit_breaker import CircuitBreakerRegistry
stats = CircuitBreakerRegistry.get().all_stats()
# [{"name": "ollama", "state": "closed", "avg_latency_ms": 450}, ...]
```

---

## 6. Memory & Context

### 6.1 Two-Tier Architecture

```
  ┌─────────────────────┐     ┌─────────────────────┐
  │   REDIS (Hot)       │     │   NEO4J (Cold)       │
  │                     │     │                      │
  │  Last 20 messages   │     │  ALL conversations   │
  │  Session context    │     │  Searchable          │
  │  Provider state     │     │  RAG-ready           │
  │                     │     │  Cross-session        │
  │  Latency: <1ms      │     │  Latency: ~5ms       │
  └─────────────────────┘     └─────────────────────┘
```

### 6.2 RAG Pipeline

Before every LLM call, the system enriches context:

```
1. Get last 6 messages from Redis (session continuity)
2. Search Neo4j for relevant past conversations (long-term recall)
3. Combine into enriched context for the LLM
```

This gives Karen the ability to say: "You asked about that last week, and I said..."

### 6.3 Node Schema (Neo4j)

```
(:VoiceConversation {id, created, timestamp})
   -[:HAS_MESSAGE]->
(:VoiceMessage {session_id, role, content, timestamp, provider, complexity, latency_ms, strategy})
```

---

## 7. Event-Driven Design

### 7.1 Seven Redpanda Topics

```
brain.voice.input          ◄── Whisper transcription result
brain.voice.reasoning      ◄── Complexity + routing decision
brain.voice.response       ◄── LLM response for TTS
brain.voice.coordination   ◄── Inter-agent messages
brain.voice.health         ◄── Component health events
brain.voice.memory         ◄── Conversation stored to Neo4j
brain.voice.metrics        ◄── Latency, usage, quality metrics
```

### 7.2 Event Flow

```
  User speaks
      │
      ▼
  brain.voice.input ──────────────────────────────────────────┐
      │                                                        │
      ▼                                                        │
  brain.voice.reasoning (classifier output)                    │
      │                                                        │
      ▼                                                        │
  [Multi-LLM Engine] ── brain.voice.metrics ──────────────────┤
      │                                                        │
      ▼                                                        │
  brain.voice.response ──► Cartesia TTS ──► User hears    │
      │                                                        │
      ▼                                                        │
  brain.voice.memory ──► Neo4j (stored for future recall)      │
      │                                                        │
      ▼                                                        │
  brain.voice.health ◄── periodic health checks ──────────────┘
```

### 7.3 Adding New Components

To add a new LLM or feature, you only need to:

1. Implement `LLMProvider` subclass in `llm_providers.py`
2. Add to `_ALL_PROVIDERS` list
3. Add specialisation preference in `multi_llm.py`
4. Set API key in environment

Everything else (circuit breakers, events, health checks) is automatic.

---

## 8. Voice Pipeline

### 8.1 Speech-to-Text (Whisper)

```
AirPods mic ──► sounddevice (16kHz) ──► VAD (energy threshold) ──► faster-whisper ──► text
```

- Model: `tiny.en` (fast) or `base.en` (accurate)
- VAD: Energy-based with pre-buffer for capturing speech start
- Max utterance: 12 seconds
- Silence detection: 0.9s pause ends utterance

### 8.2 Text-to-Speech (Cartesia)

```
LLM response text ──► Cartesia WebSocket ──► PCM audio ──► sounddevice ──► AirPods
```

- Voice: Karen (Australian female, Grace voice ID)
- Model: `sonic-3`
- Format: Raw PCM float32 @ 44.1kHz
- Streaming: WebSocket for low-latency first-byte

### 8.3 Serialisation Rule

**One voice at a time.** WCAG 2.1 AA requirement.

```
  Karen speaks ──► 0.3s gap ──► Karen speaks ──► 0.3s gap ──► ...
                 (never overlap)
```

---

## 9. Accessibility Contract

These are not suggestions. They are requirements.

| # | Rule | Enforcement |
|---|------|-------------|
| 1 | Karen speaks every response | `speak()` is mandatory in main loop |
| 2 | Max 2-3 sentences per response | System prompt enforces this |
| 3 | No markdown, bullets, or formatting | System prompt enforces this |
| 4 | No silence > 3 seconds during processing | Progress announcements |
| 5 | Error messages are spoken, not logged | Catch-all in main loop |
| 6 | One voice at a time | `speaking` flag blocks mic |
| 7 | Graceful degradation always speaks | Fallback to macOS `say` |

### Emergency Fallback

If Cartesia TTS fails completely, the system falls back to macOS `say`:

```python
import subprocess
subprocess.run(["say", "-v", "Karen (Premium)", "-r", "160", text])
```

---

## 10. Configuration

### Environment Variables

```bash
# LLM Providers
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2:3b
CLAUDE_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AI...
XAI_API_KEY=xai-...

# Voice
CARTESIA_API_KEY=sk-cart-...
CARTESIA_VOICE_ID=a4a16c5e-5902-4732-b9b6-2a48efd2e11b

# Infrastructure
VOICE_REDIS_URL=redis://:BrainRedis2026@localhost:6379/0
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Brain2026
REDPANDA_BOOTSTRAP_SERVERS=localhost:9092
```

### Redis Keys

| Key | Purpose |
|-----|---------|
| `voice:history` | Last 20 messages (LIST) |
| `voice:session_context` | Current session state (JSON) |
| `voice:health` | Latest health check (JSON) |
| `voice:health_status` | "healthy" or "degraded" |
| `voice:architect_progress` | Build progress |
| `voice:world_class_ready` | "true" when complete |

---

## 11. Operations

### Start Voice Chat

```bash
cd ~/brain/agentic-brain
python talk_to_karen.py
```

### Health Check

```bash
python -m tools.voice.health
```

### Monitor Events

```bash
docker exec agentic-brain-redpanda rpk topic consume brain.voice.metrics --format json
```

### View Circuit Breaker Status

```python
from tools.voice.circuit_breaker import CircuitBreakerRegistry
for stat in CircuitBreakerRegistry.get().all_stats():
    print(f"{stat['name']}: {stat['state']} ({stat['avg_latency_ms']}ms avg)")
```

### Query Voice Memory

```python
from tools.voice.memory import recall_relevant, get_conversation_stats
memories = recall_relevant("deployment process")
stats = get_conversation_stats()
```

---

## Architecture Decision Records

### ADR-001: Why 5 LLMs?

Each LLM has a strength. Using one LLM means accepting its weaknesses.
By routing to specialists and having parallel/consensus modes, we get the
best possible answer for every question type.

### ADR-002: Why Ollama as Guaranteed Fallback?

Ollama runs on the local M2 Mac with no internet, no API key, no cost,
and no rate limits. It is the only provider that truly cannot fail (unless
the Mac itself is down, in which case nothing works anyway).

### ADR-003: Why Circuit Breakers per Provider?

Without circuit breakers, a slow Claude API (10s timeout) blocks every
query. With breakers, after 3 failures the circuit opens and the system
instantly routes to the next provider. Recovery is automatic.

### ADR-004: Why Two-Tier Memory?

Redis is fast but volatile. Neo4j is persistent but slower. Together they
give us sub-millisecond access to recent context AND permanent storage of
all conversations for RAG and long-term recall.

### ADR-005: Why Redpanda Events?

Every component communicates through events. This means:
- New features plug in by subscribing to topics
- Health monitoring sees everything
- Metrics are automatic
- Components are decoupled and independently deployable

---

*Architecture designed for accessibility. Built with heart.*
*Every component exists to make the voice assistant the best in the world.*
