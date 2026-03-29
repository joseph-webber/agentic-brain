# Voice Queue Integration Guide

## Quick Start

### Import and Use
```python
from agentic_brain.voice import speak, VoiceQueue

# Simple: Just speak!
speak("Hello there!")

# Advanced: Control voice and rate
speak("温度是一百度", voice="Tingting", rate=140)

# Get the queue for more control
queue = VoiceQueue.get_instance()
queue.speak("Message 1", voice="Karen", pause_after=2.0)
queue.speak("Message 2", voice="Moira")
```

### Convenience Functions
```python
from agentic_brain.voice import (
    speak,              # Queue a message
    clear_queue,        # Emergency clear
    is_speaking,        # Check if busy
    get_queue_size,     # How many queued
)

speak("Working on task...")
print(f"Queue size: {get_queue_size()}")
print(f"Speaking: {is_speaking()}")
clear_queue()  # Emergency stop
```

---

## Architecture

### The Voice Module Stack

```
agentic_brain.voice (public API)
    ├── speak()              ← Convenience function
    ├── clear_queue()        ← Emergency clear
    ├── VoiceQueue           ← Singleton queue manager
    ├── VoiceMessage         ← Message dataclass
    ├── ASIAN_VOICE_CONFIG   ← Number spelling rules
    └── WESTERN_VOICE_CONFIG ← Rate/lang rules
        │
        ├── Uses: threading.Semaphore (safety)
        ├── Uses: subprocess.Popen (macOS say)
        ├── Uses: re.sub (number conversion)
        └── Uses: time.sleep (pauses)

    Also imports from agentic_brain.voice.config
        ├── VoiceConfig
        ├── VoiceQuality
        ├── LanguagePack
        └── LANGUAGE_PACKS
```

### How It Works

```
User calls: speak("Hello", voice="Karen")
    ↓
VoiceQueue.speak() creates VoiceMessage
    ↓
Message added to queue (thread-safe)
    ↓
_process_queue() starts (if not running)
    ↓
While queue not empty:
    Get next message
    _prepare_text() (number spelling for Asian voices)
    subprocess.run(["say", "-v", voice, "-r", rate, text])
    Wait for completion
    time.sleep(pause_after)  ← Prevents overlapping!
    ↓
Message added to history
    ↓
Process next message
```

**Key Safety Point**: Semaphore ensures only ONE thread processes at a time.

---

## Configuration

### Asian Voices (Auto-spell Numbers)
```python
ASIAN_VOICE_CONFIG = {
    "Kyoko":    {"spell_numbers": True, "default_rate": 145},
    "Tingting": {"spell_numbers": True, "default_rate": 140},
    "Yuna":     {"spell_numbers": True, "default_rate": 142},
    "Sinji":    {"spell_numbers": True, "default_rate": 138},
    "Linh":     {"spell_numbers": True, "default_rate": 140},
}
```

### Western Voices (Keep Numbers)
```python
WESTERN_VOICE_CONFIG = {
    "Karen":      {"default_rate": 155},  # the default voice!
    "Moira":      {"default_rate": 150},  # Irish
    "Shelley":    {"default_rate": 148},  # English
    "Zosia":      {"default_rate": 150},  # Polish
    "Damayanti":  {"default_rate": 145},  # Indonesian
}
```

### Custom Rates
```python
# Override default rate
speak("Quick message", voice="Karen", rate=170)      # Faster
speak("Important info", voice="Kyoko", rate=130)     # Slower
```

---

## Examples

### Basic Usage
```python
from agentic_brain.voice import speak

speak("Processing your request")
speak("Found 100 results", voice="Kyoko")  # → "one hundred results"
speak("Done!", voice="Moira")
```

### In Agents
```python
from agentic_brain.voice import speak

async def process_task(task):
    speak(f"Starting: {task.name}")
    try:
        result = await execute(task)
        speak(f"Success: {result}", voice="Moira")
    except Exception as e:
        speak(f"Error: {e}", voice="Shelley")
```

### With Callbacks
```python
from agentic_brain.voice import VoiceQueue

queue = VoiceQueue.get_instance()

def log_speech(msg):
    print(f"🔊 {msg.voice}: {msg.text[:50]}...")

def log_error(err, exc):
    print(f"❌ Voice error: {err}")
    # Could also log to Neo4j, send alert, etc.

queue.add_speech_callback(log_speech)
queue.add_error_callback(log_error)

queue.speak("Hello from logged system")
```

### Multiple Voices in Sequence
```python
from agentic_brain.voice import speak

# Conversation-like effect
speak("Hello, I'm Karen", voice="Karen")
speak("And I'm Moira", voice="Moira", pause_after=2.0)
speak("Together we help the user", voice="Kyoko", pause_after=1.5)
```

---

## Number Spelling Details

### When Numbers Are Converted
- ✅ **Kyoko** speaks English with Japanese accent → converts "100" to "one hundred"
- ✅ **Tingting** speaks English with Mandarin accent → converts numbers
- ✅ **Yuna** speaks English with Korean accent → converts numbers
- ✅ **Sinji** speaks English with Cantonese accent → converts numbers
- ✅ **Linh** speaks English with Vietnamese accent → converts numbers
- ❌ **Karen** speaks English natively → keeps numbers (pronounces "100" clearly)
- ❌ **Moira** speaks English (Irish) → keeps numbers
- ❌ **Other Western voices** → keep numbers

### Examples
```python
from agentic_brain.voice import VoiceQueue

queue = VoiceQueue.get_instance()

# For Asian voices:
queue.speak("100 apples", voice="Kyoko")        # Speaks: "one hundred apples"
queue.speak("Temperature 25C", voice="Tingting") # Speaks: "Temperature twenty five C"

# For Western voices:
queue.speak("100 apples", voice="Karen")        # Speaks: "100 apples" (clear)
queue.speak("25 degrees", voice="Moira")        # Speaks: "25 degrees" (clear)
```

---

## Thread Safety

### Concurrent Queue Access
```python
from concurrent.futures import ThreadPoolExecutor
from agentic_brain.voice import speak

def agent_speaks(agent_id):
    speak(f"Agent {agent_id} reporting", voice="Karen")

# 5 agents speaking at once (safely!)
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(agent_speaks, i) for i in range(5)]

# Result: All messages queued and spoken sequentially
# Output:
#   Agent 0 reporting
#   [pause 1.5s]
#   Agent 1 reporting
#   [pause 1.5s]
#   ...
```

**Safety Mechanism**: Semaphore ensures only one thread modifies queue at a time.

---

## Error Handling

### Graceful Degradation
```python
from agentic_brain.voice import speak, VoiceQueue

queue = VoiceQueue.get_instance()

# Register error handler
def handle_voice_error(error_msg: str, exception: Exception):
    print(f"Voice system error: {error_msg}")
    # Log to Neo4j, send notification, etc.

queue.add_error_callback(handle_voice_error)

# Even if voice command fails:
queue.speak("Message 1")  # This fails
queue.speak("Message 2")  # But this still speaks!
# Error is logged via callback, queue continues
```

### Recovery
```python
from agentic_brain.voice import VoiceQueue

queue = VoiceQueue.get_instance()

# Emergency clear
queue.reset()

# Verify state
print(f"Speaking: {queue.is_speaking()}")       # False
print(f"Queue size: {queue.get_queue_size()}")  # 0
```

---

## Testing

### Run All Tests
```bash
cd /Users/joe/brain/agentic-brain
python3 -m pytest tests/test_voice_safety.py -v

# Output:
# tests/test_voice_safety.py::TestVoiceMessage::... PASSED [3%]
# tests/test_voice_safety.py::TestVoiceQueueSafety::... PASSED [20%]
# tests/test_voice_safety.py::TestNumberSpelling::... PASSED [40%]
# ...
# 30 passed in 18.96s ✅
```

### Test Specific Feature
```bash
# Only safety tests
python3 -m pytest tests/test_voice_safety.py::TestVoiceQueueSafety -v

# Only number spelling
python3 -m pytest tests/test_voice_safety.py::TestNumberSpelling -v

# With coverage
python3 -m pytest tests/test_voice_safety.py --cov=agentic_brain.voice.queue
```

---

## Common Questions

### Q: Why thread-safe?
**A**: Agents run in multiple threads. If two agents try to speak simultaneously, we don't want overlapping voices confusing the user. The semaphore ensures sequential access.

### Q: Why number spelling?
**A**: Kyoko (Japanese speaker) can't pronounce "100" clearly when speaking English. She needs to hear "one hundred" spelled out. Western voices (Karen) pronounce numbers naturally.

### Q: How fast is it?
**A**: `say` command takes ~2-3 seconds for typical sentence. Plus 1.5s pause = ~3.5s per message. Queue processes as fast as macOS can speak.

### Q: What if voice is missing?
**A**: macOS falls back to default voice (usually Samantha). Add error callback to detect issues.

### Q: Can I interrupt speaking?
**A**: Not directly. Call `queue.reset()` to clear queue and stop current speech. This is an emergency operation.

### Q: How do I test without sound?
**A**: Mock subprocess.Popen in your tests (see `test_voice_safety.py` for examples).

---

## Debugging

### Enable Logging
```python
import logging

# Show all voice system logs
logging.getLogger('agentic_brain.voice.queue').setLevel(logging.DEBUG)

# Now you'll see:
# [DEBUG] Queued voice message: Karen - Hello there...
# [INFO] 🔊 Speaking [Karen] @155wpm: Hello there...
```

### Check Queue Status
```python
from agentic_brain.voice import VoiceQueue

queue = VoiceQueue.get_instance()

# Print full status
print(queue)
# Output: VoiceQueue(speaking=True, queue_size=3, history_size=12)

# Check each attribute
print(f"Currently speaking: {queue.is_speaking()}")
print(f"Messages queued: {queue.get_queue_size()}")
print(f"Recent messages: {queue.get_history(5)}")
```

### Manual Test
```python
from agentic_brain.voice import speak

# Test each voice
speak("Hello from Karen", voice="Karen")
speak("Konnichiwa from Kyoko", voice="Kyoko")
speak("Ni hao from Tingting", voice="Tingting")
speak("Annyong from Yuna", voice="Yuna")
```

---

## Production Deployment

### Before Going Live
- ✅ Run `pytest tests/test_voice_safety.py` (30 tests must pass)
- ✅ Test on target Mac hardware (M1/M2/M3)
- ✅ Verify macOS `say` command available
- ✅ Set logging level appropriately (INFO in production)
- ✅ Register error callbacks for monitoring

### Monitoring
```python
from agentic_brain.voice import VoiceQueue

queue = VoiceQueue.get_instance()

def monitor_errors(msg: str, exc: Exception):
    # Send to monitoring system
    monitoring.record({
        'event': 'voice_error',
        'message': msg,
        'exception': str(exc),
        'timestamp': datetime.now()
    })

queue.add_error_callback(monitor_errors)
```

### Performance
- Queue operations: O(1) add, O(1) remove
- Threading: Semaphore-based, no contention
- Memory: Stores last 100 messages (~10KB)
- CPU: Minimal (just queuing, not synthesis)

---

## Future Enhancements

### Planned Features
- [ ] Audio file playback (for alerts/jingles)
- [ ] Voice emotion control
- [ ] Real-time speech recognition
- [ ] Multi-voice mixing in single sentence
- [ ] Speech analytics dashboard

### Potential Improvements
- [ ] Prioritize urgent messages (move to front of queue)
- [ ] Rate adaptation (slower for complex info)
- [ ] Accent selection (e.g., "speak slowly for Tingting")
- [ ] Regional voice variants

---

## Support & Issues

**Need help?**
1. Check this guide first
2. Review `VOICE_SAFETY_SYSTEM.md` (full documentation)
3. Look at test examples in `tests/test_voice_safety.py`
4. Check logs: `logging.getLogger('agentic_brain.voice.queue')`

**Found a bug?**
- If voices overlap: **CRITICAL** - file issue immediately
- If message doesn't speak: Check `queue.get_queue_size()` and logs
- If error callback doesn't fire: Verify callback is registered

---

Created for **Agentic Brain Contributors** ❤️  
AGENTIC-BRAIN Voice Safety System - Integration Guide  
Status: Production Ready ✅
