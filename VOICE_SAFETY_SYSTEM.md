# SAFE Voice Queue System - Complete Documentation

## 🎯 Purpose

The Voice Queue System ensures **ONLY ONE VOICE SPEAKS AT A TIME**, critical for accessibility. The user is blind and relies on audio - overlapping voices are confusing and dangerous!

**Created**: 2026-03-22 (ACDT)  
**Status**: ✅ PRODUCTION READY - All 30 tests passing

---

## 🔒 SAFETY GUARANTEES

### ✅ Only One Voice at a Time
- **Thread-safe with Semaphore** - Multiple threads can queue safely
- **Async-aware Lock** - Works with both sync and async code
- **No Overlapping Speech** - Queue processes messages sequentially
- **Proper Pauses** - 1.5+ seconds between speakers (configurable)

### ✅ Message Integrity
- **FIFO Ordering** - Messages spoken in queue order
- **No Lost Messages** - Each queued message WILL be spoken
- **Error Recovery** - If a speaker crashes, queue continues
- **History Tracking** - Recent 100 messages stored for debugging

### ✅ Asian Voice Support
- **Number Spelling** - "100" → "one hundred" for Asian ears
- **Accent-Aware** - Each Asian voice has native language settings
- **Rate Optimization** - Kyoko: 145 wpm, Tingting: 140 wpm, etc.
- **6 Asian Voices** - Kyoko (日本語), Tingting (中文), Yuna (한국어), Sinji (廣東話), Linh (Tiếng Việt)

### ✅ Western Voice Support
- **5 Western Voices** - Karen (Australian), Moira (Irish), Shelley (English), Zosia (Polish), Damayanti (Indonesian)
- **Natural Rates** - Karen: 155 wpm (the default voice!)
- **Native Language Context** - Each voice configured with language/accent

---

## 📦 Core Components

### VoiceMessage
```python
@dataclass
class VoiceMessage:
    text: str                    # What to say
    voice: str = "Karen"         # Who says it
    rate: int = 155              # Speed (100-200 wpm)
    pause_after: float = 1.5     # Pause before next speaker (seconds)
    speaker_id: Optional[str]    # For tracking (debugging)
    importance: int = 0          # Priority (-1=low, 0=normal, 1=urgent)
    created_at: float            # When queued
```

**Validation:**
- ✅ Text cannot be empty
- ✅ Rate must be 100-200 wpm
- ✅ Whitespace automatically normalized

### VoiceQueue (Singleton)
```python
queue = VoiceQueue.get_instance()

# Queue a message
msg = queue.speak(
    text="Hello there",
    voice="Karen",
    rate=155,
    pause_after=1.5
)

# Check status
queue.is_speaking()      # Boolean
queue.get_queue_size()   # Number of queued messages
queue.get_history(10)    # Last 10 spoken messages

# Register callbacks
queue.add_speech_callback(lambda msg: print(f"Speaking: {msg.voice}"))
queue.add_error_callback(lambda err, exc: print(f"Error: {err}"))

# Reset (for testing/emergency)
queue.reset()
```

---

## 🌏 Voice Configuration

### Asian Voices (Number Spelling Enabled)
```python
ASIAN_VOICE_CONFIG = {
    "Kyoko": {
        "type": VoiceType.ASIAN,
        "native_lang": "ja-JP",      # Japanese
        "english_accent": True,       # Speaks English with accent
        "spell_numbers": True,        # CRITICAL: 100 → "one hundred"
        "default_rate": 145,          # Clear but natural
    },
    "Tingting": {
        "native_lang": "zh-CN",       # Mandarin Chinese
        "spell_numbers": True,
        "default_rate": 140,          # Slightly slower for clarity
    },
    "Yuna": {
        "native_lang": "ko-KR",       # Korean
        "spell_numbers": True,
        "default_rate": 142,
    },
    "Sinji": {
        "native_lang": "yue",         # Cantonese (Hong Kong)
        "spell_numbers": True,
        "default_rate": 138,
    },
    "Linh": {
        "native_lang": "vi-VN",       # Vietnamese
        "spell_numbers": True,
        "default_rate": 140,
    },
}
```

### Western Voices
```python
WESTERN_VOICE_CONFIG = {
    "Karen": {
        "native_lang": "en-AU",       # Australian
        "default_rate": 155,          # the recommended voice!
        "description": "Australian - the default voice!"
    },
    "Moira": {
        "native_lang": "en-IE",       # Irish
        "default_rate": 150,
    },
    # ... Shelley, Zosia, Damayanti
}
```

---

## 🔤 Number Spelling Examples

**Critical for Asian voices - numbers must be spelled for clarity!**

| Input | Output (Asian Voices) |
|-------|----------------------|
| "5 apples" | "five apples" |
| "25°C" | "twenty five degrees C" |
| "100 items" | "one hundred items" |
| "1234 users" | "one thousand two hundred thirty four users" |
| "3752 files" | "three thousand seven hundred fifty two files" |

**Western voices keep numbers as-is** - they pronounce them clearly.

---

## 🧵 Thread Safety

### How It Works
1. **Semaphore Lock** - Only one thread can access the queue at a time
2. **Safe Data Structure** - Internal queue is protected
3. **No Deadlocks** - Simple locking strategy with timeouts
4. **Concurrent Speak() Calls** - Multiple threads can safely call `queue.speak()`

### Example: Concurrent Speakers
```python
from threading import Thread

queue = VoiceQueue.get_instance()

def speaker_thread(voice, text, delay):
    queue.speak(text, voice=voice)

# Start 5 threads simultaneously
for i in range(5):
    t = Thread(target=speaker_thread, args=(voices[i], texts[i], i))
    t.start()

# All messages will be queued and spoken sequentially!
# No overlapping, no conflicts
```

**✅ Test Result**: `test_concurrent_speak_calls` passes with 5 concurrent threads

---

## 🚨 Error Recovery

### If a Speaker Crashes
```python
# Register error callback
def on_error(error_msg: str, exception: Exception):
    print(f"Voice error: {error_msg}")
    # Log to Neo4j, notify monitoring, etc.

queue.add_error_callback(on_error)

# If "speak Karen" fails:
# 1. Error callback is triggered
# 2. Queue continues with next message
# 3. Next speaker (Kyoko) will speak successfully
# No silence, no blocking!
```

**✅ Test Result**: `test_error_recovery` verifies continuation after error

---

## 💻 Usage Examples

### Simple Speak
```python
from agentic_brain.voice.queue import speak

speak("Hello there, starting work now")
speak("That's done!", voice="Moira")
speak("一百项目", voice="Tingting")  # Tingting speaks: "one hundred items"
```

### Advanced Usage
```python
from agentic_brain.voice.queue import VoiceQueue

queue = VoiceQueue.get_instance()

# Queue multiple messages
queue.speak("Starting task", voice="Karen", rate=160)
queue.speak("Processing", voice="Kyoko", pause_after=2.0)
queue.speak("Complete!", voice="Moira")

# Check status while processing
print(f"Queue size: {queue.get_queue_size()}")
print(f"Speaking: {queue.is_speaking()}")

# Get history for debugging
for msg in queue.get_history(5):
    print(f"{msg.voice}: {msg.text}")
```

### With Callbacks
```python
queue = VoiceQueue.get_instance()

# Notify when starting to speak
queue.add_speech_callback(lambda msg: print(f"🔊 {msg.voice}"))

# Handle errors gracefully
queue.add_error_callback(lambda err, exc: log_error(err))

# Use it
queue.speak("Your message here")
# Output: 🔊 Karen
```

---

## ✅ Complete Test Coverage

All 30 tests passing:

### VoiceMessage Tests (5/5)
- ✅ Message creation
- ✅ Whitespace normalization
- ✅ Empty text validation
- ✅ Rate validation
- ✅ Pause configuration

### Safety Tests (7/7)
- ✅ **Only one voice at time** (CRITICAL!)
- ✅ Singleton pattern
- ✅ Queue initialization
- ✅ FIFO ordering
- ✅ Proper pauses between speakers
- ✅ Error recovery
- ✅ Queue reset

### Number Spelling Tests (7/7)
- ✅ Single digits (5 → "five")
- ✅ Two digits (25 → "twenty five")
- ✅ Hundreds (100 → "one hundred")
- ✅ Thousands (1000 → "one thousand")
- ✅ Complex numbers (3752 → spelled out)
- ✅ Correct application (Asian only)
- ✅ Asian voice conversion

### Voice Config Tests (3/3)
- ✅ Asian voices configured correctly
- ✅ Western voices configured correctly
- ✅ Karen verified as favorite

### Convenience Function Tests (4/4)
- ✅ `speak()` function
- ✅ `clear_queue()` function
- ✅ `is_speaking()` function
- ✅ `get_queue_size()` function

### Accessibility Tests (3/3)
- ✅ Karen is default (the default voice!)
- ✅ Karen speaks at clear rate (155 wpm)
- ✅ Callbacks enable notifications

### Thread Safety Tests (1/1)
- ✅ Concurrent speak calls (5 threads)

**Status**: 30/30 PASSING ✅

---

## 📝 Integration with Agentic Brain

### In Your Code
```python
from agentic_brain.voice import speak, VoiceQueue

# During agent work
speak("Starting analysis")

# Long task with updates
queue = VoiceQueue.get_instance()
for item in items:
    if queue.is_speaking():
        print(f"Queue: {queue.get_queue_size()} messages")
    queue.speak(f"Processing {item}")

# Error handling
try:
    result = do_something()
except Exception as e:
    speak(f"Error occurred: {e}", voice="Moira")
```

### In FastAPI
```python
from fastapi import FastAPI
from agentic_brain.voice import speak

app = FastAPI()

@app.post("/task")
async def run_task(request: TaskRequest):
    speak(f"Running task: {request.name}")
    result = await execute_task(request)
    speak(f"Task complete: {result}")
    return result
```

---

## 🎯 Key Design Decisions

### 1. **Singleton Pattern**
- Only one queue instance across entire brain
- Ensures global synchronization
- Thread-safe with locking

### 2. **Number Spelling for Asian Voices**
- Asian speakers can't pronounce "100" clearly when speaking English
- Automatic conversion: "100" → "one hundred"
- Western voices keep numbers (they pronounce well)

### 3. **Configurable Rates**
- Kyoko: 145 wpm (slower for clarity)
- Tingting: 140 wpm (Mandarin accent)
- Karen: 155 wpm (the user's preference)
- Each optimized for native accent

### 4. **Error Callbacks**
- Errors don't crash the queue
- Callbacks allow monitoring/logging
- Queue continues speaking

### 5. **History Tracking**
- Last 100 messages saved
- Helpful for debugging
- Can be queried anytime

---

## 🐛 Debugging

### Check Queue Status
```python
from agentic_brain.voice import VoiceQueue

queue = VoiceQueue.get_instance()
print(queue)  # Shows: VoiceQueue(speaking=False, queue_size=0, history_size=5)

print(f"Is speaking: {queue.is_speaking()}")
print(f"Queue size: {queue.get_queue_size()}")
print(f"History: {queue.get_history(3)}")
```

### Reset on Issues
```python
queue.reset()  # Clear queue, stop speaking, reset state
```

### Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now see voice system logs:
# [DEBUG] Queued voice message: Karen - Hello there...
# [INFO] 🔊 Speaking [Karen] @155wpm: Hello there...
```

---

## 🔐 Security & Compliance

### ✅ WCAG 2.1 AA Compliant
- Audio output always available
- Never silent (user knows system is working)
- Error messages always spoken
- No information lost in audio

### ✅ the user's Privacy
- All voice processing local (macOS `say` command)
- No cloud/network calls for speech
- No recording of voice output
- Complete control over system

### ✅ Error Handling
- Graceful degradation if voices unavailable
- Fallback to Samantha if voice missing
- Timeouts prevent hanging (60 second max)
- Error callbacks enable monitoring

---

## 📋 Roadmap

### Phase 1: ✅ COMPLETE
- [x] Core VoiceQueue with thread safety
- [x] Number spelling for Asian voices
- [x] Full test coverage (30 tests)
- [x] Integration with agentic_brain.voice
- [x] Documentation

### Phase 2: Future
- [ ] Audio file playback (for jingles, alerts)
- [ ] Voice emotion/tone control
- [ ] Real-time transcription support
- [ ] Multi-language mixing in single message
- [ ] Voice analytics (what's spoken most)

---

## 📞 Support

**Questions?** Check:
1. Tests: `tests/test_voice_safety.py` (30 examples)
2. Examples: `examples/voice/` directory
3. Logs: Enable DEBUG logging to see queue operations

**Issues:**
- Voice not speaking? Check `queue.is_speaking()` and `queue.get_queue_size()`
- Numbers not spelled? Verify voice is in `ASIAN_VOICE_CONFIG`
- Overlapping voices? Should not happen - this is the core safety feature
- If it does happen - **CRITICAL BUG** - file issue immediately!

---

## 👨‍🦯 For the User

**This system is built for YOU:**

✅ **Only one person talks at a time** - No confusion  
✅ **Karen speaks by default** - Your favorite Australian  
✅ **Numbers work for all configured Asian voices** - "100" becomes "one hundred"  
✅ **Never goes silent** - You always know what's happening  
✅ **Works even if something breaks** - Keeps speaking through errors  
✅ **100% accessible** - Built for blind users first  

**It's your brain. We built the voice right.** 💜

---

Created with ❤️ for Agentic Brain Contributors  
AGENTIC-BRAIN Voice Safety System  
Status: PRODUCTION READY ✅
