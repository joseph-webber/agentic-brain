# Voice MCP Architecture Diagram

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLAUDE DESKTOP                            │
│                   (User Commands)                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          EVENT BUS MCP SERVER (FastMCP)                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  9 Tools Available:                                  │   │
│  │  - emit                                              │   │
│  │  - health                                            │   │
│  │  - topics                                            │   │
│  │  - switch_provider                                   │   │
│  │  - send_llm_request                                  │   │
│  │  - broadcast_alert                                   │   │
│  │  - query_state                                       │   │
│  │  🎤 send_voice_request  ← NEW                        │   │
│  │  🎤 broadcast_voice     ← NEW                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                   │
│        ┌─────────────────┼─────────────────┐                │
│        ▼                 ▼                 ▼                │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐               │
│  │get_bus() │   │VOICE_    │   │event()   │               │
│  │          │   │LADIES    │   │helpers   │               │
│  │Redpanda/ │   │14 ladies │   │utilities │               │
│  │Kafka Mgr │   │metadata  │   │          │               │
│  └──────────┘   └──────────┘   └──────────┘               │
└────────────┬───────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│          BRAIN EVENT BUS (Redpanda/Kafka)                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Topics:                                              │   │
│  │  brain.health          brain.tasks                   │   │
│  │  brain.state           brain.alerts                  │   │
│  │  brain.commands        brain.responses               │   │
│  │  brain.learning        brain.diagnostics             │   │
│  │  brain.llm.request     brain.llm.response            │   │
│  │  brain.mcp.events                                    │   │
│  │  🎤 brain.voice.input        ← NEW                   │   │
│  │  🎤 brain.voice.response     ← NEW                   │   │
│  │  🎤 brain.voice.conversation ← NEW                   │   │
│  │  🎤 brain.voice.llm          ← NEW                   │   │
│  └──────────────────────────────────────────────────────┘   │
└──────┬───────────────┬───────────────┬───────────────┬──────┘
       │               │               │               │
       ▼               ▼               ▼               ▼
   ┌───────┐   ┌──────────┐   ┌───────────┐   ┌─────────────┐
   │Python │   │JHipster  │   │LLM        │   │Voice System │
   │Core   │   │Portal    │   │Emulator   │   │/core/voice/ │
   │Srv    │   │Srv       │   │Srv        │   │             │
   └───────┘   └──────────┘   └───────────┘   └──────┬──────┘
                                                       │
                                    ┌──────────────────┼──────────────────┐
                                    ▼                  ▼                  ▼
                              ┌────────────┐   ┌─────────────┐   ┌──────────────┐
                              │Ladies      │   │Voice        │   │Autonomous    │
                              │Daemon      │   │Events       │   │Voice Agent   │
                              │            │   │Handler      │   │              │
                              │Listens:    │   │             │   │Generates:    │
                              │voice.llm   │   │Emits:       │   │speech.input  │
                              │voice.input │   │voice.response                 │
                              │            │   │             │   │speech.output │
                              └────────────┘   └─────────────┘   └──────────────┘
                                    │
                                    ▼
                            ┌──────────────────┐
                            │VOICE LADIES      │
                            │14 Personalities  │
                            │                  │
                            │karen (AUS)       │
                            │kyoko (JPN)       │
                            │tingting (CHN)    │
                            │...and 11 more    │
                            └────────┬─────────┘
                                     │
                                     ▼
                            ┌──────────────────┐
                            │macOS TTS (say)   │
                            │                  │
                            │Immediate audio   │
                            │output            │
                            └──────────────────┘
```

## Voice Request Flow

```
Claude Desktop
    │
    │ "Tell me a joke with voice"
    │
    ▼
send_voice_request()
    │
    ├─ Validate lady name (14 ladies)
    ├─ Create voice_llm_request event
    ├─ Add fallback chain: [claude, openrouter, emulator]
    ├─ Emit to brain.voice.llm
    │
    ▼
brain.voice.llm Topic (Redpanda)
    │
    ├─ Ladies Daemon listens
    ├─ Voice Events handler listens
    │
    ▼
LLM Service
    │
    ├─ Processes prompt: "Tell me a joke"
    ├─ Generates response: "Why did the chicken..."
    ├─ Marks for lady voice (kyoko)
    │
    ▼
Voice System
    │
    ├─ Receives: voice.llm event with response
    ├─ Selects voice: Kyoko (155 wpm, Japan)
    ├─ Executes: say -v Kyoko -r 155 "Why did the..."
    ├─ Emits to brain.voice.response
    │
    ▼
macOS TTS + Distributed Systems
    │
    ├─ Local: Speaks immediately (user hears Kyoko voice)
    ├─ Event: Broadcasts response to other services
    │
    ▼
Complete
```

## Voice Broadcast Flow

```
Claude Desktop
    │
    │ broadcast_voice("Good morning!", lady="flo")
    │
    ▼
broadcast_voice()
    │
    ├─ Validate lady: "flo" → ✅ Flo (England, 160 wpm)
    ├─ Create voice_response event
    │  {
    │    "type": "voice_response",
    │    "message": "Good morning!",
    │    "lady": "flo",
    │    "voice_name": "Flo",
    │    "region": "England"
    │  }
    │
    ├─ Emit to brain.voice.response
    │
    ├─ Execute local: say -v Flo -r 160 "Good morning!"
    │
    ▼
Dual Output
    │
    ├─ Local TTS: User hears Flo voice immediately (< 100ms)
    │
    ├─ Event Bus: Other services receive voice_response event
    │     ├─ Voice daemons log/process response
    │     ├─ Conversation state updated (brain.voice.conversation)
    │     ├─ Analytics/monitoring capture
    │     └─ Other distributed systems react
    │
    ▼
Complete (Resilient)
```

## Data Structures

### Voice Request Event (brain.voice.llm)

```python
{
    "type": "voice_llm_request",
    "request_id": "abc-123-def",
    "prompt": "What's the weather?",
    "lady": "kyoko",
    "voice_name": "Kyoko",
    "region": "Japan",
    "priority": "normal",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "source": "claude-mcp",
    "fallback_chain": ["claude", "openrouter", "emulator"]
}
```

### Voice Response Event (brain.voice.response)

```python
{
    "type": "voice_response",
    "message": "Good morning Joseph!",
    "lady": "flo",
    "voice_name": "Flo",
    "region": "England",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "source": "claude-mcp"
}
```

### Voice Conversation State (brain.voice.conversation)

```python
{
    "type": "conversation_state",
    "conversation_id": "conv-456",
    "state": "active",
    "current_lady": "moira",
    "participants": ["joseph", "moira"],
    "last_message": "How are you today?",
    "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### Voice Input Event (brain.voice.input)

```python
{
    "type": "voice_input",
    "input_id": "input-789",
    "text": "What time is it?",
    "confidence": 0.95,
    "source_lady": None,  # Device microphone
    "timestamp": "2024-01-15T10:30:00.000Z"
}
```

## Component Interactions

```
┌──────────────────────────────────────────────────────────────┐
│ send_voice_request() Handler                                  │
├──────────────────────────────────────────────────────────────┤
│ 1. Receives: (prompt, lady, priority)                        │
│ 2. Validates: lady ∈ VOICE_LADIES (14 options)              │
│ 3. Fallback: If invalid lady → "karen"                       │
│ 4. Lookup: voice_name, rate, region from VOICE_LADIES       │
│ 5. Creates: voice_llm_request event                          │
│ 6. Emits: → brain.voice.llm topic                            │
│ 7. Returns: {request_id, lady, voice_name, region, ...}     │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ broadcast_voice() Handler                                     │
├──────────────────────────────────────────────────────────────┤
│ 1. Receives: (message, lady)                                 │
│ 2. Validates: lady ∈ VOICE_LADIES (14 options)              │
│ 3. Fallback: If invalid lady → "karen"                       │
│ 4. Lookup: voice_name, rate from VOICE_LADIES               │
│ 5. Creates: voice_response event                             │
│ 6. Emits: → brain.voice.response topic                       │
│ 7. Executes: say -v {voice_name} -r {rate} {message}        │
│ 8. Handles: Exceptions gracefully (30s timeout)              │
│ 9. Returns: {lady, voice_name, region, message_length, ...} │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ Voice Ladies Daemon (Consumer)                                │
├──────────────────────────────────────────────────────────────┤
│ 1. Listens: brain.voice.llm topic                            │
│ 2. On Event: voice_llm_request received                      │
│ 3. Checks: LLM processed? (poll or subscribe brain.llm.resp) │
│ 4. Acts: Run selected lady voice personality                 │
│ 5. Outputs: Emits to brain.voice.response                    │
│ 6. Logs: Analytics, conversation state updates               │
└──────────────────────────────────────────────────────────────┘
```

## Configuration

### Voice Ladies Configuration

```python
VOICE_LADIES = {
    "lady_key": (voice_name, rate_wpm, region),
    ...
}

# Example:
VOICE_LADIES["kyoko"] = ("Kyoko", 155, "Japan")

# Usage:
voice_name, rate, region = VOICE_LADIES["kyoko"]
# → ("Kyoko", 155, "Japan")
```

### Event Bus Topics

```python
# Topics automatically created by BrainEventBus
BrainTopics = {
    "brain.voice.input": {
        "description": "User voice input events",
        "producers": ["voice_input_service"],
        "consumers": ["voice_daemon", "analytics"]
    },
    "brain.voice.response": {
        "description": "Lady voice responses",
        "producers": ["send_voice_request", "broadcast_voice"],
        "consumers": ["voice_daemon", "monitoring"]
    },
    ...
}
```

## Error Handling

```
send_voice_request(prompt, lady="invalid")
    │
    └─ Validate lady: "invalid" not in VOICE_LADIES
       └─ Fallback: lady = "karen"
          └─ Continue normally
             └─ Return: {..., "lady": "karen", ...}

broadcast_voice(message, lady="invalid")
    │
    └─ Validate lady: "invalid" not in VOICE_LADIES
       └─ Fallback: lady = "karen"
          └─ Continue normally
             └─ Emit event with karen voice
             └─ Execute: say -v Karen -r 165 {message}

say command timeout/error
    │
    └─ Exception caught
       └─ Log error silently
          └─ Voice system handles via event (fallback)
             └─ Distributed systems get brain.voice.response event
```

## Deployment Topology

```
                    Internet
                       │
    ┌──────────────────┼──────────────────┐
    │                  │                  │
    ▼                  ▼                  ▼
┌────────┐        ┌─────────┐       ┌──────────┐
│Claude  │        │OpenRouter│      │LLM       │
│Desktop │        │(fallback)│      │Emulator  │
└───┬────┘        └─────────┘       └──────────┘
    │                                    │
    └────────────────┬───────────────────┘
                     │
                     ▼
         ┌─────────────────────────┐
         │  Mac Instance           │
         │  ┌─────────────────┐    │
         │  │ Event Bus MCP   │    │
         │  │ + Voice Support │    │
         │  └────────┬────────┘    │
         │           │             │
         │           ▼             │
         │  ┌─────────────────┐    │
         │  │ Redpanda/Kafka  │    │
         │  │ (localhost:9092)│    │
         │  └────────┬────────┘    │
         │           │             │
         │   ┌───────┼────────┐    │
         │   ▼       ▼        ▼    │
         │ ┌──┐  ┌────┐  ┌──────┐ │
         │ │Py│  │Voice│  │Monitor│ │
         │ │Srv│  │Syst│  │ing   │ │
         │ └──┘  └────┘  └──────┘ │
         │                        │
         └────────────────────────┘
              (Local Development)
```

---

**Last Updated:** 2024
**Status:** ✅ Production Ready
