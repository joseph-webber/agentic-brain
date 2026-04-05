# 🎤 Voice MCP Enhancement

Complete voice conversation support for the Event Bus MCP server with integration to 14 regional voice personas and Redpanda event streaming.

## 🚀 Quick Start

```python
# Broadcast a spoken message
broadcast_voice("Good morning!", voice="flo")

# Request LLM response with voice
send_voice_request("What's the weather?", voice="kyoko")
```

## 📚 Documentation

| Document | Purpose | Time |
|----------|---------|------|
| **[VOICE_QUICK_REF.md](./VOICE_QUICK_REF.md)** | Quick reference guide with examples | 5 min |
| **[VOICE_ENHANCEMENT.md](./VOICE_ENHANCEMENT.md)** | Detailed implementation docs | 15 min |
| **[VOICE_ARCHITECTURE.md](./VOICE_ARCHITECTURE.md)** | System architecture & diagrams | 10 min |
| **[VOICE_INTEGRATION_TEST.md](./VOICE_INTEGRATION_TEST.md)** | Testing & verification guide | 20 min |

## ✨ Features

### New MCP Tools
- **`send_voice_request(prompt, voice, priority)`** - Generate spoken LLM response
- **`broadcast_voice(message, voice)`** - Broadcast spoken message

### New Event Topics
- **`brain.voice.input`** - User voice input events
- **`brain.voice.response`** - Voice responses
- **`brain.voice.conversation`** - Conversation state changes
- **`brain.voice.llm`** - LLM requests for voice responses

### Voice Personas (14 regional voices)
- **Australia**: karen (165 wpm)
- **Asia**: kyoko, tingting, sinji, linh, kanya, yuna, dewi, sari, wayan
- **Europe**: moira, zosia, flo, shelley

## 🔌 Integration

```
Claude Desktop
  ↓
send_voice_request() / broadcast_voice()
  ↓
brain.voice.llm / brain.voice.response
  ↓
Redpanda Event Bus
  ↓
Voice System (/core/voice/)
  ↓
macOS TTS + Distributed Services
```

## 💡 Usage Examples

### Example 1: Spoken Query Response
```python
send_voice_request(
    prompt="Tell me about today's tasks",
    voice="moira",
    priority="normal"
)
# → Creates voice_llm_request event
# → LLM generates response
# → Moira (Irish) voice speaks the answer
```

### Example 2: Simple Announcement
```python
broadcast_voice(
    message="You have a new message from the team",
    voice="flo"
)
# → Emits voice_response event
# → Flo (English) voice speaks immediately
# → Event broadcast to other services
```

### Example 3: Regional Voice Selection
```python
# Kyoko answers in Japanese context
send_voice_request(
    prompt="Japanese business etiquette",
    voice="kyoko"  # From Japan, 155 wpm
)

# Linh answers about Southeast Asia
send_voice_request(
    prompt="Vietnam's economic growth",
    voice="linh"   # From Vietnam, 155 wpm
)
```

## 🧪 Verification

All components verified:
- ✅ Python syntax validated
- ✅ 14 voice personas loaded
- ✅ Events emit to Redpanda
- ✅ Local TTS working
- ✅ Error handling in place
- ✅ No breaking changes

Run verification:
```bash
python3 -m py_compile server.py
python3 -c "from server import send_voice_request, broadcast_voice, VOICE_PERSONAS; print(f'✅ {len(VOICE_PERSONAS)} voices loaded')"
```

## 📊 What Changed

**Modified Files:**
- `server.py` (+150 lines)
  - Added: 2 voice functions, 14-voice roster, imports
  - Enhanced: topics() documentation with voice topics

**No Breaking Changes:**
- All 7 existing tools unchanged
- Consistent API patterns
- Backward compatible

## 🔗 Related Files

- `/core/voice/` - Voice system integration
- `/core/kafka_bus.py` - Event bus abstraction
- `/mcp-servers/event-bus/server.py` - Main implementation

## 📞 Support

For issues or questions:
1. Check [VOICE_QUICK_REF.md](./VOICE_QUICK_REF.md) for quick answers
2. See [VOICE_ENHANCEMENT.md](./VOICE_ENHANCEMENT.md) for detailed info
3. Review [VOICE_INTEGRATION_TEST.md](./VOICE_INTEGRATION_TEST.md) for testing
4. Examine [VOICE_ARCHITECTURE.md](./VOICE_ARCHITECTURE.md) for system design

## 📋 Checklist

- ✅ Voice functions implemented and tested
- ✅ 14 voice personas integrated
- ✅ 4 voice topics added to event bus
- ✅ Redpanda/Kafka integration working
- ✅ Comprehensive documentation
- ✅ Production ready

---

**Status:** ✅ Ready for Production
**Version:** 1.0
**Last Updated:** 2024
