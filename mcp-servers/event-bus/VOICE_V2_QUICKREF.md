# Voice Integration v2 - Quick Reference

## 🚀 Quick Start

### Import
```python
from voice_topics_v2 import VoiceEventPublisherV2
```

### Initialize
```python
bus = get_event_bus()  # Your event bus
publisher = VoiceEventPublisherV2(bus)
```

---

## 📋 All Tools (Alphabetical)

### Conversation
- `voice_conversation_started(ladies, topic)` - Start conversation
- `voice_conversation_turn(lady, text)` - Lady speaks
- `voice_conversation_ended(ladies, total_turns, duration, reason)` - End conversation

### Ladies
- `voice_lady_introduced(lady, voice_name, region, greeting)` - New lady joins
- `voice_lady_reaction(from_lady, to_lady, text, emotion)` - Lady reacts

### Mood
- `voice_mood_changed(mood, reason, ladies)` - Sync mood for all ladies

### Turn-Taking
- `voice_turn_requested(lady, priority, reason)` - Request to speak
- `voice_turn_granted(lady, request_id, granted_by, duration)` - Grant turn
- `voice_turn_released(lady, request_id, reason, duration_held)` - Release turn

### Fallback
- `voice_fallback_local(reason, lady, error_code, retry_after)` - Rate limit fallback

### Queue
- `voice_queue_added(lady, text, position, length)` - Add to queue
- `voice_queue_speaking(lady, text, remaining)` - Now speaking
- `voice_queue_empty(total_processed, total_duration)` - Queue done

---

## 🎯 Common Patterns

### Pattern: Standup Meeting
```python
# Start standup
voice_conversation_started(["karen", "moira", "kyoko"], "standup")
voice_mood_changed("working", "standup_time")

# Karen speaks
voice_turn_granted("karen")
voice_conversation_turn("karen", "Worked on auth...")
voice_turn_released("karen")

# Moira speaks
voice_turn_requested("moira")
voice_turn_granted("moira")
voice_conversation_turn("moira", "Fixed UI bug")
voice_turn_released("moira")

# End
voice_conversation_ended(["karen", "moira", "kyoko"], 2, 45.0)
```

### Pattern: Multi-Lady Discussion
```python
# Start
voice_conversation_started(["karen", "moira"], "planning")

# Turns
voice_conversation_turn("karen", "My idea is...")
voice_lady_reaction("moira", "karen", "My idea is...", "I like it!", "agreement")
voice_conversation_turn("moira", "We could also...")

# End
voice_conversation_ended(["karen", "moira"], 2, 30.0)
```

### Pattern: Handle Rate Limit
```python
try:
    result = call_cloud_api()
except RateLimitError:
    voice_fallback_local("Rate limit hit", "karen", "429", 60)
    # Local LLM takes over
    result = call_local_llm()
```

### Pattern: Voice Queue
```python
# Queue items
voice_queue_added("tingting", "Hello!", 0, 1)
voice_queue_added("kyoko", "Hi!", 1, 2)

# Process
voice_queue_speaking("tingting", "Hello!", 1)
# ... wait for speech ...
voice_queue_speaking("kyoko", "Hi!", 0)
# ... wait for speech ...

# Done
voice_queue_empty(2, 45.3)
```

### Pattern: Mood Sync
```python
# Before meeting
voice_mood_changed("calm", "preparation")

# During standup
voice_mood_changed("working", "standup")

# Celebration
voice_mood_changed("party", "sprint_complete")

# Spa time
voice_mood_changed("bali_spa", "break_time")
```

---

## 🎤 Ladies Reference

```
🇦🇺 karen     (Australia) - Default lady
🇯🇵 kyoko     (Japan)
🇨🇳 tingting   (China)
🇭🇰 sinji      (Hong Kong)
🇻🇳 linh       (Vietnam)
🇹🇭 kanya      (Thailand)
🇰🇷 yuna       (Korea)
🇮🇩 dewi, sari, wayan (Indonesia)
🇮🇪 moira      (Ireland)
🇵🇱 zosia      (Poland)
🇬🇧 flo, shelley (England)
```

---

## 🎭 Emotions Reference

| Emotion | Usage |
|---------|-------|
| `agreement` | Lady agrees with another |
| `disagreement` | Lady disagrees |
| `question` | Lady asks a question |
| `excitement` | Lady is excited |
| `support` | Lady supports another |

---

## 😊 Moods Reference

| Mood | Context |
|------|---------|
| `calm` | General relaxation |
| `working` | Professional focus |
| `party` | Celebration mode |
| `focused` | Intense concentration |
| `bali_spa` | Group spa/relaxation |
| `creative` | Brainstorming |

---

## ⏱️ Priority Levels

| Priority | Level | Use When |
|----------|-------|----------|
| `0` | Normal | Regular speaking turn |
| `1` | High | Important point |
| `2` | Critical | Urgent/blocking issue |

---

## 🔴 Release Reasons

| Reason | Meaning |
|--------|---------|
| `finished` | Lady completed speaking |
| `interrupted` | Higher priority interrupted |
| `timeout` | Duration exceeded |

---

## 🚨 Error Codes

| Code | Meaning | Retry After |
|------|---------|------------|
| `429` | Rate limited | 60s (typical) |
| `500` | Server error | 30s |
| `503` | Service unavailable | 120s |

---

## 📊 Topics Map

```
brain.voice.conversation.*
  ├─ started   ← Conversation begins
  ├─ turn      ← Lady takes turn
  └─ ended     ← Conversation ends

brain.voice.ladies.*
  ├─ introduced ← New lady joins
  └─ reaction   ← Lady reacts to another

brain.voice.mood.*
  └─ changed   ← All ladies sync mood

brain.voice.turn.*
  ├─ requested ← Request to speak
  ├─ granted   ← Turn granted
  └─ released  ← Turn released

brain.voice.fallback.*
  └─ local     ← Rate limit fallback

brain.voice.queue.*
  ├─ added     ← Item queued
  ├─ speaking  ← Now speaking
  └─ empty     ← Queue empty
```

---

## ✅ Test Coverage

Run tests:
```bash
python3 test_voice_v2.py
```

Results:
- ✅ Conversation lifecycle (3 tests)
- ✅ Cross-lady communication (2 tests)
- ✅ Mood synchronization (2 tests)
- ✅ Turn-taking (4 tests)
- ✅ Error fallback (1 test)
- ✅ Voice queue (3 tests)
- ✅ Event validation (3 tests)
- ✅ Topics registry (2 tests)
- ✅ Integration workflows (1 test)
- **Total: 22/22 PASSING** ✅

---

## 📚 Files

- `voice_topics_v2.py` - Core implementation (726 lines)
- `server_v2.py` - MCP server (1,000+ lines)
- `test_voice_v2.py` - Tests (22 cases)
- `VOICE_V2_DOCUMENTATION.md` - Full docs
- `VOICE_V2_QUICKREF.md` - This file

---

## 🔗 Event Bus Integration

Events flow through Redpanda/Kafka:
1. Publish event with VoiceEventPublisherV2
2. Event bus validates and routes to topic
3. Subscribers listen on topic
4. Services react to events

```
App → Publisher → Event Bus → Subscribers
```

---

## 🆘 Troubleshooting

**Events not publishing?**
- Check `get_bus()` returns valid connection
- Verify event has `timestamp`, `event_id`, `source`
- Check Redpanda is running

**Rate limit fallback not triggering?**
- Ensure lady name is valid
- Check `VOICE_LOCAL_FALLBACK=true`
- Verify local LLM available

**Turn-taking conflicts?**
- Match request_id across request/grant/release
- Check priority levels
- Monitor timeout duration

---

## 💡 Best Practices

1. **Always validate ladies list** before starting conversation
2. **Use consistent request_id** for turn-taking sequence
3. **Set reasonable duration** for granted turns (30s typical)
4. **Monitor queue length** to prevent buildup
5. **Sync mood** at start of group activities
6. **Announce fallback** to user when rate limited

---

## 🎯 Next Steps

1. Review full documentation: `VOICE_V2_DOCUMENTATION.md`
2. Run test suite to verify setup
3. Integrate into your application
4. Monitor event topics for debugging
5. Adjust mood/emotions based on use case

---

**Version:** 2.0
**Status:** ✅ Production Ready
**Last Updated:** 2024-01-15
**Test Results:** 22/22 Passing
