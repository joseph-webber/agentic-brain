# Voice Enhancement - Event Bus MCP Server

## Summary
Enhanced the Redpanda MCP server to add voice conversation topics and handlers. The enhancement integrates with the voice ladies system for spoken responses.

## Changes Made

### 1. New Voice Topics
Added four voice-related topics to the event bus:

| Topic | Purpose |
|-------|---------|
| `brain.voice.input` | User voice input events |
| `brain.voice.response` | Lady voice responses (text to speech) |
| `brain.voice.conversation` | Conversation state changes |
| `brain.voice.llm` | LLM requests for voice responses |

### 2. New Helper Functions

#### `send_voice_request(prompt, lady="karen", priority="normal")`
Sends a voice LLM request that will generate a spoken response.

**Parameters:**
- `prompt` (str) - The prompt to send to LLM
- `lady` (str) - Voice lady name (default: "karen")
- `priority` (str) - Request priority: "normal", "high", "low"

**Flow:**
1. Validates lady name (14 ladies available)
2. Creates event with LLM prompt + voice metadata
3. Emits to `brain.voice.llm` topic
4. Returns request ID for tracking

**Available Ladies:**
- **Australia**: karen (165 wpm)
- **Asia**: kyoko, tingting, sinji, linh, kanya, yuna, dewi, sari, wayan
- **Europe**: moira, zosia, flo, shelley

#### `broadcast_voice(message, lady="karen")`
Broadcasts a spoken message immediately with lady voice.

**Parameters:**
- `message` (str) - Message to speak
- `lady` (str) - Voice lady name (default: "karen")

**Flow:**
1. Validates lady name
2. Creates `voice_response` event
3. Emits to `brain.voice.response` topic
4. Speaks locally via macOS `say` command
5. Falls back to event-based delivery if local speech fails

**Output:**
- Spoken audio (immediate on local Mac)
- Event broadcast for distributed voice systems

### 3. Voice Ladies Roster
Embedded the complete 14-lady roster as module constant:

```python
VOICE_LADIES = {
    "karen": ("Karen", 165, "Australia"),
    "kyoko": ("Kyoko", 155, "Japan"),
    "tingting": ("Tingting", 155, "China"),
    "sinji": ("Sinji", 155, "Hong Kong"),
    "linh": ("Linh", 155, "Vietnam"),
    "kanya": ("Kanya", 155, "Thailand"),
    "yuna": ("Yuna", 155, "Korea"),
    "dewi": ("Dewi", 155, "Indonesia"),
    "sari": ("Sari", 155, "Indonesia"),
    "wayan": ("Wayan", 155, "Indonesia"),
    "moira": ("Moira", 160, "Ireland"),
    "zosia": ("Zosia", 155, "Poland"),
    "flo": ("Flo", 160, "England"),
    "shelley": ("Shelley", 158, "England"),
}
```

### 4. Integration Architecture

```
Claude Desktop
    ↓
MCP Event Bus (9 tools)
    ↓
BrainEventBus (Redpanda/Kafka)
    ├─ brain.voice.input
    ├─ brain.voice.response  ← broadcast_voice emits here
    ├─ brain.voice.conversation
    └─ brain.voice.llm       ← send_voice_request emits here
    ↓
Voice System (/core/voice/)
    ├─ ladies_daemon.py
    ├─ autonomous_voice_agent.py
    ├─ iris_voice_daemon.py
    └─ voice_events.py
```

## Usage Examples

### Send LLM Request for Voice Response
```python
send_voice_request(
    prompt="Tell me about the weather today",
    lady="kyoko",
    priority="normal"
)
```

Event sent to `brain.voice.llm`:
```json
{
    "type": "voice_llm_request",
    "request_id": "abc123...",
    "prompt": "Tell me about the weather today",
    "lady": "kyoko",
    "voice_name": "Kyoko",
    "region": "Japan",
    "priority": "normal",
    "fallback_chain": ["claude", "openrouter", "emulator"]
}
```

### Broadcast Spoken Message
```python
broadcast_voice(
    message="Good morning Joseph! Time to start the day.",
    lady="flo"
)
```

Event sent to `brain.voice.response`:
```json
{
    "type": "voice_response",
    "message": "Good morning Joseph! Time to start the day.",
    "lady": "flo",
    "voice_name": "Flo",
    "region": "England"
}
```

## Design Principles

1. **Minimal & Focused**: Only voice-related additions, no changes to existing functionality
2. **Event-Driven**: All voice actions emit events for distributed processing
3. **Fault-Tolerant**: Graceful degradation if local speech unavailable
4. **Lady Validation**: Automatically falls back to Karen if invalid lady specified
5. **Consistent API**: Follows same patterns as existing MCP tools (send_llm_request, broadcast_alert)

## Integration Points

### With Voice Ladies System
- Uses ladies roster from `/core/voice/ladies.py`
- Compatible with voice personalities from `/core/voice/voice_engine.py`
- Events consumed by voice daemons for distributed audio

### With Core Event Bus
- `brain.voice.input` - For voice input capture (ready for expansion)
- `brain.voice.response` - For voice output distribution
- `brain.voice.conversation` - For conversation state tracking
- `brain.voice.llm` - For voice-specific LLM processing

## Files Modified

- `/Users/joe/brain/mcp-servers/event-bus/server.py` (+150 lines)
  - Added voice imports (subprocess)
  - Added VOICE_LADIES roster
  - Added `send_voice_request()` function
  - Added `broadcast_voice()` function
  - Updated `topics()` to document 4 new voice topics

## Testing

Run syntax check:
```bash
python3 -m py_compile server.py
# ✅ Syntax check passed
```

## Future Enhancements

1. Voice input recognition handlers
2. Conversation state machine in `brain.voice.conversation` topic
3. Voice mood/emotion detection
4. Multi-lady conversation support
5. Voice persistence across sessions via brain.voice.input topic
