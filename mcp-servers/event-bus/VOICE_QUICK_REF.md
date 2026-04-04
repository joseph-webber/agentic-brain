# Voice MCP Quick Reference

## 🎤 New Tools

### `send_voice_request(prompt, lady="karen", priority="normal")`
Generate a spoken response from LLM via voice lady.

```
send_voice_request("What's the weather?", lady="kyoko")
→ Request sent to brain.voice.llm topic
→ LLM processes + lady speaks response
```

**Ladies:** karen, kyoko, tingting, yuna, moira, zosia, flo, shelley, etc.

### `broadcast_voice(message, lady="karen")`
Speak a message immediately with lady voice.

```
broadcast_voice("Good morning Joseph!", lady="flo")
→ Emits to brain.voice.response topic
→ Speaks locally + broadcasts for other systems
```

## 📬 Voice Topics

| Topic | Used By |
|-------|---------|
| `brain.voice.input` | Voice input capture systems |
| `brain.voice.response` | Output from broadcast_voice() |
| `brain.voice.conversation` | Conversation state tracking |
| `brain.voice.llm` | LLM voice requests from send_voice_request() |

## 👩 Voice Ladies

| Lady | Country | Voice | Speed |
|------|---------|-------|-------|
| karen | Australia | Karen | 165 wpm |
| kyoko | Japan | Kyoko | 155 wpm |
| tingting | China | Tingting | 155 wpm |
| sinji | Hong Kong | Sinji | 155 wpm |
| linh | Vietnam | Linh | 155 wpm |
| kanya | Thailand | Kanya | 155 wpm |
| yuna | Korea | Yuna | 155 wpm |
| dewi | Indonesia | Dewi | 155 wpm |
| sari | Indonesia | Sari | 155 wpm |
| wayan | Indonesia | Wayan | 155 wpm |
| moira | Ireland | Moira | 160 wpm |
| zosia | Poland | Zosia | 155 wpm |
| flo | England | Flo | 160 wpm |
| shelley | England | Shelley | 158 wpm |

## 🔌 Integration Diagram

```
Claude Desktop
    ↓
event-bus MCP (send_voice_request, broadcast_voice)
    ↓
Redpanda/Kafka Event Bus
    ├─ brain.voice.input
    ├─ brain.voice.response
    ├─ brain.voice.conversation
    └─ brain.voice.llm
    ↓
Voice System (/core/voice/)
    ├─ Voice Daemons (ladies_daemon.py, iris_voice_daemon.py)
    ├─ Voice Engine (voice_engine.py)
    └─ Voice Events (voice_events.py)
    ↓
Mac TTS (say command) + Other Services
```

## 💡 Usage Patterns

### Response to User Query with Voice
```
send_voice_request(
    prompt="Summarize the top 3 PR reviews today",
    lady="moira",
    priority="normal"
)
```

### Notification/Alert with Voice
```
broadcast_voice(
    message="You have a new Jira ticket to review",
    lady="karen"
)
```

### Regional Voice Selection
```
# Use lady from specific region
send_voice_request(
    prompt="Tell me about the import regulations",
    lady="linh"  # Vietnam
)
```

## 🔄 Event Flow Example

### send_voice_request() Flow
```
send_voice_request("Hello kyoko")
→ Validates lady='kyoko' exists
→ Creates event with:
   - type: 'voice_llm_request'
   - prompt: "Hello kyoko"
   - lady: 'kyoko'
   - voice_name: 'Kyoko'
   - region: 'Japan'
   - fallback_chain: ['claude', 'openrouter', 'emulator']
→ Emits to brain.voice.llm topic
→ Voice daemons/LLM services consume event
→ LLM generates response
→ Voice system speaks response via kyoko voice
→ Emits to brain.voice.response topic
```

### broadcast_voice() Flow
```
broadcast_voice("Good morning!", lady="flo")
→ Validates lady='flo' exists
→ Creates event:
   - type: 'voice_response'
   - message: 'Good morning!'
   - lady: 'flo'
   - voice_name: 'Flo'
   - region: 'England'
→ Emits to brain.voice.response topic
→ Executes: say -v Flo -r 160 "Good morning!"
→ Local audio plays immediately
→ Other services receive event for distributed processing
```

## ✅ Changes at a Glance

- ✅ 4 new voice topics documented
- ✅ 2 new MCP tools (send_voice_request, broadcast_voice)
- ✅ 14-lady roster integrated
- ✅ Redpanda event emission for all voice actions
- ✅ Graceful fallback if local speech unavailable
- ✅ Automatic validation of lady names
- ✅ Minimal, focused changes (no breaking changes)

## 📝 Files

- Modified: `/Users/joe/brain/mcp-servers/event-bus/server.py`
- Added: `/Users/joe/brain/mcp-servers/event-bus/VOICE_ENHANCEMENT.md`
