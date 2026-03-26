# 🔊 Resilient Voice System - Quick Reference

## One-Liners

```python
# Speak (automatic fallbacks)
await speak("Hello Joseph")

# Speak with options
await speak("Hello", voice="Moira", rate=140)

# Queue for daemon (async, fire-and-forget)
await speak_via_daemon("Background message")

# Play sound
await play_sound("success")

# Get stats
stats = get_voice_stats()
print(stats['voice'])  # Method stats
print(stats['daemon']) # Daemon stats
```

## Import Everything

```python
from agentic_brain.voice.resilient import (
    # Classes
    ResilientVoice,
    VoiceDaemon,
    SoundEffects,
    VoiceConfig,
    
    # Functions
    speak,
    speak_via_daemon,
    play_sound,
    get_daemon,
    get_voice_stats,
)
```

## Setup & Config

```python
from agentic_brain.voice.resilient import VoiceConfig, ResilientVoice

config = VoiceConfig(
    default_voice="Karen",
    default_rate=155,
    timeout=30,
    enable_fallbacks=True,  # Always use fallbacks
    log_failures=True,      # Log to ~/.brain-voice-failures.log
)

voice = ResilientVoice(config)
```

## Speaking

### Simple Speech
```python
# Uses default voice (Karen) and rate (155)
await speak("Hello World")
```

### Custom Voice & Rate
```python
# Voice: any macOS voice name
# Rate: 100-200 (slower to faster)
await speak("Hello", voice="Moira", rate=140)
await speak("Hi", voice="Tingting", rate=150)
```

### Via Daemon (Non-blocking)
```python
# Queues message to daemon, returns immediately
await speak_via_daemon("Message 1")
await speak_via_daemon("Message 2")
await speak_via_daemon("Message 3")
# Daemon processes them in background
```

## Sound Effects

```python
await play_sound("success")      # Glass.aiff
await play_sound("error")        # Basso.aiff
await play_sound("notification") # Ping.aiff
await play_sound("complete")     # Hero.aiff
await play_sound("alarm")        # Alarm.aiff
await play_sound("alert")        # Alert.aiff
```

## Daemon Control

```python
from agentic_brain.voice.resilient import get_daemon

daemon = await get_daemon()

# Daemon is auto-started, but you can:
await daemon.start()   # Start manually
await daemon.stop()    # Stop gracefully

# Queue messages
await daemon.speak("Message 1")
await daemon.speak("Message 2", voice="Moira")

# Check status
stats = daemon.get_stats()
print(stats['queue_size'])   # Messages waiting
print(stats['processed'])    # Total processed
print(stats['errors'])       # Total errors
```

## Monitoring & Stats

```python
# Get all statistics
stats = get_voice_stats()

# Voice method statistics
voice_stats = stats['voice']
# {
#   'say_with_voice': {
#     'success': 45,
#     'failure': 2,
#     'success_rate': '95.7%',
#     'last_used': '2026-03-25T10:45:32.123456'
#   },
#   ...
# }

# Daemon statistics
daemon_stats = stats['daemon']
# {
#   'running': True,
#   'queue_size': 0,
#   'processed': 52,
#   'error_rate': '3.8%'
# }
```

## Common Patterns

### Pattern 1: Announce Task Start & End
```python
async def do_task():
    await speak("Starting task")
    try:
        # ... do work ...
        await speak("Task complete")
        await play_sound("success")
    except Exception as e:
        await speak(f"Error: {e}")
        await play_sound("error")
```

### Pattern 2: Queue Multiple Messages
```python
async def process():
    for item in items:
        await speak_via_daemon(f"Processing {item}")
        # Do work while voice runs in background
```

### Pattern 3: Long Operation with Progress
```python
async def long_task():
    total = len(items)
    for i, item in enumerate(items):
        await speak_via_daemon(f"Progress: {i+1} of {total}")
        # Process item
        await asyncio.sleep(1)
    await speak("All complete")
```

### Pattern 4: Multi-Voice Conversation
```python
async def conversation():
    await speak("Hello!", voice="Karen", rate=155)
    await asyncio.sleep(1)
    
    await speak("Good morning!", voice="Moira", rate=150)
    await asyncio.sleep(1)
    
    await speak("How are you?", voice="Tingting", rate=145)
```

### Pattern 5: Error Recovery with Fallback Voice
```python
async def speak_resilient(text, voice="Karen"):
    try:
        await speak(text, voice=voice)
    except Exception as e:
        # Try default voice as fallback
        await speak(f"Could not speak with {voice}: {text}")
```

## Available Voices

**Popular choices:**
- Karen (Australian) - default
- Moira (Irish)
- Tingting (Chinese)
- Kyoko (Japanese)
- Linh (Vietnamese)
- Zosia (Polish)
- Damayanti (Indonesian)
- Yuna (Korean)

**Get all voices:**
```bash
say -v ?  # List all macOS voices
```

## Debugging

### Check Failures
```bash
cat ~/.brain-voice-failures.log
```

### Test Direct
```bash
say "Test message"
say -v Moira "Test with voice"
```

### Get System Info
```python
import subprocess
result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
print(result.stdout)  # All available voices
```

### Check Accessibility
- System Settings → Accessibility → Speech
- Verify a voice is installed

## Testing

```bash
# Run all tests
pytest tests/test_voice_resilient.py -v

# Run specific test
pytest tests/test_voice_resilient.py::TestResilientVoice::test_speak_with_default_voice -v

# Run with coverage
pytest tests/test_voice_resilient.py --cov=agentic_brain.voice.resilient
```

## Fallback Chain (In Order)

1. **say -v Karen -r 155** → Preferred method
2. **say** → Simpler version
3. **osascript with voice** → AppleScript alternative
4. **osascript default** → AppleScript fallback
5. **afplay Glass.aiff** → Sound alert (final fallback)

**Result:** If ANY method works, message is delivered.

## Performance Tips

### For Batch Messages
```python
# Instead of this (blocks):
for msg in messages:
    await speak(msg)  # Waits for each to finish

# Do this (non-blocking):
for msg in messages:
    await speak_via_daemon(msg)  # Queues all at once
```

### For User Responsiveness
```python
# Queue first, then do work
await speak_via_daemon("Processing...")
# Do long operation while voice plays
await do_long_operation()
# Status update
await speak_via_daemon("Complete!")
```

## Error Handling

**The system NEVER crashes.** All errors are:
1. Caught and logged
2. Silently skipped to next fallback
3. Tracked in statistics
4. Never interrupt flow

```python
# This never fails - always returns True
success = await speak("Hello", voice="NonexistentVoice")
# System automatically uses fallback methods
```

## Logs & Monitoring

**Failures logged to:**
```
~/.brain-voice-failures.log
```

Each entry:
```json
{
  "timestamp": "2026-03-25T10:45:32.123456",
  "text": "Text that failed",
  "voice": "Karen",
  "rate": 155,
  "fallbacks_tried": 5
}
```

## Status Check

```python
# Is daemon running?
daemon = await get_daemon()
print(daemon.get_stats()['running'])  # True/False

# What's in queue?
print(daemon.get_stats()['queue_size'])

# Success rate?
stats = get_voice_stats()
for method, data in stats['voice'].items():
    print(f"{method}: {data['success_rate']}")
```

## Integration with Main Brain

```python
# In main.py or app initialization:
from agentic_brain.voice.resilient import get_daemon

async def init_voice():
    daemon = await get_daemon()
    return daemon

# Use throughout app:
from agentic_brain.voice.resilient import speak, play_sound

await speak("Application started")
```

---

**Quick Help:**
- Speak: `await speak("text")`
- Sound: `await play_sound("success")`  
- Daemon: `await speak_via_daemon("text")`
- Stats: `get_voice_stats()`

**Docs:** See `RESILIENT_VOICE_SYSTEM.md` for full documentation
