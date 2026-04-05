# Voice Event System - Complete Implementation Guide

## 📋 Table of Contents

1. [Overview](#overview)
2. [Files Created/Modified](#files-createdmodified)
3. [Core Components](#core-components)
4. [Quick Start](#quick-start)
5. [API Reference](#api-reference)
6. [Integration](#integration)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

## Overview

A comprehensive voice event system for the Brain that enables:

- **Mood Management**: Track emotional state (calm, working, party)
- **Multi-Voice Conversations**: Coordinate complex voice interactions
- **Real-Time Notifications**: Voice speaking/finished events
- **Queue Management**: Track voice processing queue
- **Fleet Announcements**: Broadcast system-wide voice updates
- **Event Validation**: JSON schema validation for all events
- **Event Replay**: Full event history for debugging

### Architecture

```
Claude Desktop
    ↓
Event Bus MCP Server (voice_topics.py integration)
    ↓
Redpanda/Kafka Event Bus
    ├─ brain.voice.mood
    ├─ brain.voice.voice.speaking
    ├─ brain.voice.voice.finished
    ├─ brain.voice.queue.status
    ├─ brain.voice.conversation
    └─ brain.voice.fleet.status
    ↓
Consumer Services (Python, JHipster, LLM, Voice Daemon)
```

## Files Created/Modified

### New Files Created

#### 1. `voice_topics.py` (25,636 bytes)
**Core voice event system**

Components:
- `VoiceTopics`: Topic registry and descriptions
- `VoiceEventPublisher`: Publishing voice events
- `VoiceEventSubscriber`: Subscribing to voice events
- Event dataclasses: `MoodChangeEvent`, `VoiceSpeakingEvent`, `ConversationEvent`, `FleetStatusEvent`, etc.
- JSON schemas for validation
- Event replay support

#### 2. `test_voice_topics.py` (10,111 bytes)
**Comprehensive test suite**

Tests:
- ✅ Voice topics registry
- ✅ Event schemas and validation
- ✅ Event dataclass creation
- ✅ Publisher functionality (all 6 event types)
- ✅ Subscriber functionality
- ✅ Event replay capability
- ✅ Invalid data rejection

**Run tests:**
```bash
cd /Users/joe/brain/mcp-servers/event-bus
python3 test_voice_topics.py
```

#### 3. `VOICE_TOPICS_DOCUMENTATION.md` (16,602 bytes)
**Full system documentation**

Includes:
- Architecture diagrams
- Topic specifications with examples
- API reference for all methods
- MCP tool descriptions
- Usage examples and patterns
- Event schemas
- Voice voices roster
- Integration points
- Performance considerations

#### 4. `VOICE_QUICK_REF.md` (4,156 bytes)
**Quick reference guide**

Contents:
- Topics at a glance
- Quick start code
- Available voices
- Event schemas
- Common patterns
- File structure
- Testing info
- Integration checklist

### Modified Files

#### 1. `server.py`
**MCP server integration**

Changes:
- Added imports for voice_topics module (with fallback handling)
- Added global `_voice_publisher` and `_voice_subscriber` globals
- Added `get_voice_publisher()` and `get_voice_subscriber()` helper functions
- Updated `topics()` function with new voice topics documentation
- Added 6 new MCP tools:
  - `voice_mood_change()`
  - `voice_voice_speaking()`
  - `voice_voice_finished()`
  - `voice_queue_status()`
  - `voice_conversation()`
  - `voice_fleet_announcement()`
  - `voice_topics_list()`

## Core Components

### 1. VoiceTopics Registry

Centralized registry of all voice-related topics:

```python
from voice_topics import VoiceTopics

# Get all topics
topics = VoiceTopics.all()  # Returns list of 9 topics

# Get topic descriptions
desc = VoiceTopics.get_description(VoiceTopics.MOOD)
# "Current mood state (calm, working, party)"
```

**Available Topics:**
- `brain.voice.mood` - Mood changes
- `brain.voice.voice.speaking` - Voice speaking events
- `brain.voice.voice.finished` - Voice finished events
- `brain.voice.queue.status` - Queue updates
- `brain.voice.conversation` - Multi-voice chats
- `brain.voice.fleet.status` - Fleet announcements

### 2. VoiceEventPublisher

Publish events to the event bus:

```python
from voice_topics import VoiceEventPublisher
from core.kafka_bus import BrainEventBus

bus = BrainEventBus()
bus.connect()
pub = VoiceEventPublisher(bus)

# Publish mood change
result = pub.publish_mood_change("working", reason="Meeting time")
# Returns: {"success": True, "mood": "working", "event_id": "...", ...}

# Publish voice speaking
result = pub.publish_voice_speaking("karen", "Hello!", "Karen", "Australia")
# Returns: {"success": True, "voice": "karen", "text_length": 6, ...}

# Publish multi-voice conversation
result = pub.publish_conversation_event(
    voices=["karen", "moira"],
    topic="standup"
)
# Returns: {"success": True, "conversation_id": "...", "participants": 2, ...}
```

**All Methods:**
- `publish_mood_change(mood, reason, previous_mood)` → Dict
- `publish_voice_speaking(voice, text, voice_name, region)` → Dict
- `publish_voice_finished(voice, duration_ms, success, error_message)` → Dict
- `publish_queue_update(queue_length, pending_voices, current_voice, processing)` → Dict
- `publish_conversation_event(voices, topic, speaker_order, context)` → Dict
- `publish_fleet_announcement(message, announcement_type, agent_name)` → Dict
- `get_stats()` → Dict

### 3. VoiceEventSubscriber

Subscribe to voice events with callbacks:

```python
from voice_topics import VoiceEventSubscriber

sub = VoiceEventSubscriber(bus)

# Register callbacks
def on_mood(event):
    print(f"Mood: {event['mood']}")

sub.on_mood_change(on_mood)
sub.on_voice_speaking(lambda e: print(f"{e['voice']}: {e['text']}"))
sub.on_any_voice_event(lambda e: print(f"Event: {e}"))

# Subscribe to all topics
sub.subscribe_all()

# Get stats
stats = sub.get_stats()
# {"events_received": 0, "callbacks_registered": 3, "topics_subscribed": [9 topics]}
```

**All Methods:**
- `on_mood_change(callback)` → None
- `on_voice_speaking(callback)` → None
- `on_voice_finished(callback)` → None
- `on_queue_status(callback)` → None
- `on_conversation(callback)` → None
- `on_fleet_status(callback)` → None
- `on_any_voice_event(callback)` → None
- `subscribe_all()` → Dict
- `get_stats()` → Dict

### 4. Event Dataclasses

Type-safe event definitions with validation:

```python
from voice_topics import MoodChangeEvent, VoiceSpeakingEvent

# Create and validate
mood_event = MoodChangeEvent(mood="working", reason="Meeting")
if mood_event.validate():
    event_dict = mood_event.to_dict()
    event_json = mood_event.to_json()

# All events include:
# - timestamp (ISO 8601)
# - source (voice-system, claude-mcp, etc.)
# - event_id (UUID)
```

### 5. Event Validation

Validate events against JSON schemas:

```python
from voice_topics import validate_voice_event, get_event_schema

# Check schema
schema = get_event_schema("mood_change")

# Validate data
valid, error = validate_voice_event("mood_change", {
    "timestamp": "2024-01-15T...",
    "source": "test",
    "event_id": "uuid",
    "mood": "working"
})

if not valid:
    print(f"Invalid: {error}")
```

## Quick Start

### Installation

Voice topics system is already installed at:
```
/Users/joe/brain/mcp-servers/event-bus/voice_topics.py
```

### Basic Usage

```python
# 1. Import modules
from voice_topics import VoiceEventPublisher, VoiceEventSubscriber
from core.kafka_bus import BrainEventBus

# 2. Connect to event bus
bus = BrainEventBus()
bus.connect()

# 3. Create publisher
pub = VoiceEventPublisher(bus)

# 4. Publish events
pub.publish_mood_change("working")
pub.publish_voice_speaking("karen", "Good morning!")
pub.publish_voice_finished("karen")

# 5. Create subscriber (optional)
sub = VoiceEventSubscriber(bus)
sub.on_voice_speaking(lambda e: print(f"{e['voice']}: {e['text']}"))
sub.subscribe_all()
```

### Using with MCP Tools

```bash
# From Claude or MCP CLI
voice_mood_change working "Meeting time"
voice_voice_speaking karen "Hello everyone!"
voice_voice_finished karen
voice_conversation ["karen", "moira"] "standup"
voice_fleet_announcement "All agents online" info
voice_topics_list
```

## API Reference

### VoiceEventPublisher

All methods return `Dict[str, Any]` with:
- `success` (bool)
- `event_id` (str)
- `topic` (str)
- Event-specific fields

#### `publish_mood_change(mood, reason="", previous_mood=None)`

**Parameters:**
- `mood` (str): `calm`, `working`, or `party`
- `reason` (str, optional): Reason for change
- `previous_mood` (str, optional): Previous state

**Returns:**
```python
{
    "success": True,
    "mood": "working",
    "reason": "Meeting",
    "event_id": "uuid",
    "topic": "brain.voice.mood",
    "timestamp": "2024-01-15T..."
}
```

#### `publish_voice_speaking(voice, text, voice_name="", region="")`

**Parameters:**
- `voice` (str): Voice ID (karen, moira, etc.)
- `text` (str): Text being spoken
- `voice_name` (str, optional): Full voice name
- `region` (str, optional): Voice region

**Returns:**
```python
{
    "success": True,
    "voice": "karen",
    "text_length": 18,
    "event_id": "uuid",
    "topic": "brain.voice.voice.speaking",
    "timestamp": "2024-01-15T..."
}
```

#### `publish_conversation_event(voices, topic, speaker_order=None, context=None, conversation_id=None)`

**Parameters:**
- `voices` (list): List of voice IDs
- `topic` (str): Conversation topic
- `speaker_order` (list, optional): Order of speakers
- `context` (dict, optional): Conversation context
- `conversation_id` (str, optional): Use existing ID

**Returns:**
```python
{
    "success": True,
    "voices": ["karen", "moira"],
    "topic": "standup",
    "participants": 2,
    "conversation_id": "uuid",
    "event_id": "uuid",
    "topic_voice": "brain.voice.conversation",
    "timestamp": "2024-01-15T..."
}
```

## Integration

### With Voice Rendering Service

```python
# Voice rendering daemon subscribes to voice.speaking
sub = VoiceEventSubscriber(bus)

def render_voice(event):
    voice = event['voice']
    text = event['text']
    # Use macOS say command or other TTS
    subprocess.run(['say', '-v', voice, text])
    
    # Publish finished event
    pub.publish_voice_finished(voice, success=True)

sub.on_voice_speaking(render_voice)
sub.subscribe_all()
```

### With LLM Service

```python
# LLM service subscribes to mood for context
def get_tone_adjustment(event):
    mood = event['mood']
    if mood == "party":
        return "enthusiastic and celebratory"
    elif mood == "working":
        return "focused and professional"
    else:
        return "calm and measured"

sub = VoiceEventSubscriber(bus)
sub.on_mood_change(lambda e: print(f"Tone: {get_tone_adjustment(e)}"))
```

### With Voice Queue Manager

```python
# Queue manager publishes status updates
def process_queue(items):
    for i, item in enumerate(items):
        pub.publish_queue_update(
            queue_length=len(items) - i,
            current_voice="karen",
            processing=True
        )
        # Process item...
        pub.publish_voice_finished("karen")
```

## Testing

### Run Full Test Suite

```bash
cd /Users/joe/brain/mcp-servers/event-bus
python3 test_voice_topics.py
```

**Expected Output:**
```
============================================================
🎤 Voice Event System Test Suite
============================================================

=== Testing VoiceTopics Registry ===
✓ Got 9 topics
✓ All expected topics present...
✓ Got description...

=== Testing Event Schemas ===
✓ Got 6 schemas
✓ Mood schema valid...
✓ Valid mood change event passes validation
✓ Invalid event rejected...

=== Testing Event Dataclasses ===
✓ MoodChangeEvent created...
✓ VoiceSpeakingEvent created...
✓ ConversationEvent created...
✓ FleetStatusEvent created...

=== Testing VoiceEventPublisher ===
✓ Mood change published...
✓ Voice speaking event published...
✓ Voice finished event published
✓ Queue status published...
✓ Conversation event published...
✓ Fleet announcement published
✓ Publisher stats...
✓ Invalid mood rejected...

=== Testing VoiceEventSubscriber ===
✓ Mood callback fired...
✓ Voice callback fired...
✓ Subscribed to 9 topics
✓ Subscriber stats...

=== Testing Event Replay ===
✓ Replayed 3 events with valid structure

============================================================
✅ ALL TESTS PASSED
============================================================
```

### Test Individual Components

```python
# Test publisher
from voice_topics import VoiceEventPublisher
from test_voice_topics import MockEventBus

bus = MockEventBus()
pub = VoiceEventPublisher(bus)

result = pub.publish_mood_change("working")
assert result["success"]
assert result["mood"] == "working"
print("✓ Publisher working!")

# Test subscriber
from voice_topics import VoiceEventSubscriber

sub = VoiceEventSubscriber(bus)
sub.on_mood_change(lambda e: print(f"Got mood: {e['mood']}"))

# Subscribe and test
events_received = []
sub.on_any_voice_event(lambda e: events_received.append(e))
sub.subscribe_all()

pub.publish_mood_change("party")
assert len(events_received) > 0
print(f"✓ Subscriber working! Received {len(events_received)} events")
```

## Troubleshooting

### Import Errors

**Problem:** `ModuleNotFoundError: No module named 'voice_topics'`

**Solution:**
- Ensure voice_topics.py is in `/Users/joe/brain/mcp-servers/event-bus/`
- Check sys.path includes the directory
- Verify Python version (3.7+)

### Connection Issues

**Problem:** Events not being published

**Solution:**
```python
# Check bus connection
bus = BrainEventBus()
if not bus.connect():
    print("Failed to connect to event bus")
    # Check Redpanda/Kafka is running
    # Check connection parameters

# Verify bus is healthy
health = bus.health_check()
if health['status'] != 'healthy':
    print(f"Bus unhealthy: {health}")
```

### Validation Failures

**Problem:** "Invalid mood: xyz"

**Solution:**
```python
# Only use valid moods
VALID_MOODS = ["calm", "working", "party"]

mood = user_input
if mood not in VALID_MOODS:
    mood = "calm"  # Default

pub.publish_mood_change(mood)
```

**Problem:** "Voice and text are required"

**Solution:**
```python
# Ensure both voice and text are provided
if not voice or not text:
    print("Error: voice and text required")
    return

pub.publish_voice_speaking(voice, text)
```

### Performance Issues

**Problem:** Events publishing slowly

**Solution:**
```python
# Check bus performance
stats = pub.get_stats()
print(f"Events published: {stats['events_published']}")

# Monitor queue
result = pub.publish_queue_update(queue_length=100, processing=True)
if not result["success"]:
    print(f"Queue update failed: {result['error']}")

# Consider batching events
# Instead of publishing one at a time, batch publish related events
```

## Files Summary

| File | Size | Purpose |
|------|------|---------|
| `voice_topics.py` | 25,636 B | Core voice event system |
| `server.py` | ~800 B additions | MCP tool integration |
| `test_voice_topics.py` | 10,111 B | Comprehensive tests |
| `VOICE_TOPICS_DOCUMENTATION.md` | 16,602 B | Full documentation |
| `VOICE_QUICK_REF.md` | 4,156 B | Quick reference |
| `README_IMPLEMENTATION.md` | This file | Implementation guide |

## Next Steps

1. **Deploy**
   ```bash
   # Restart MCP server to load new tools
   killall claude-mcp-server
   # Or via Claude Desktop: Restart extension
   ```

2. **Test with MCP**
   ```bash
   voice_mood_change working
   voice_voice_speaking karen "Testing voice system"
   voice_topics_list
   ```

3. **Integrate Services**
   - Voice rendering: subscribe to `voice.speaking`
   - LLM: subscribe to `mood` for tone context
   - Queue manager: publish `queue.status`
   - Fleet monitor: publish/subscribe `fleet.status`

4. **Monitor Events**
   ```python
   from voice_topics import VoiceEventSubscriber
   
   sub = VoiceEventSubscriber(bus)
   sub.on_any_voice_event(lambda e: print(f"Event: {e}"))
   sub.subscribe_all()
   ```

## Support

- Full documentation: `VOICE_TOPICS_DOCUMENTATION.md`
- Quick reference: `VOICE_QUICK_REF.md`
- Test suite: `test_voice_topics.py`
- Example code: Throughout this file

All events are:
- ✅ Timestamped (ISO 8601)
- ✅ Unique ID (UUID)
- ✅ Validated against schema
- ✅ Replayed for debugging
- ✅ Exported for analytics
