# Voice Event System Documentation

## Overview

The Brain Voice Event System provides a comprehensive event-driven architecture for managing multi-lady voice conversations, mood tracking, and agent fleet announcements through a Redpanda/Kafka event bus.

### Key Features

- **Mood Management**: Track and broadcast mood changes (calm, working, party)
- **Lady Speaking Events**: Real-time tracking of which lady is speaking
- **Multi-Lady Conversations**: Coordinate complex conversations between multiple ladies
- **Queue Management**: Monitor voice queue status and pending items
- **Fleet Announcements**: Broadcast agent/fleet status across the system
- **Event Validation**: JSON schema validation for all event types
- **Event Replay**: Full event history for debugging and recovery

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Brain Voice Event System                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  VoiceEventPublisher       VoiceEventSubscriber             │
│  ├─ publish_mood_change()  ├─ on_mood_change()             │
│  ├─ publish_lady_speaking()├─ on_lady_speaking()           │
│  ├─ publish_conversation() ├─ on_conversation()            │
│  └─ publish_fleet_status() └─ on_any_voice_event()         │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│              BrainEventBus (Redpanda/Kafka)                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  VoiceTopics Registry                                        │
│  ├─ brain.voice.mood                                         │
│  ├─ brain.voice.lady.speaking                               │
│  ├─ brain.voice.lady.finished                               │
│  ├─ brain.voice.queue.status                                │
│  ├─ brain.voice.conversation                                │
│  └─ brain.voice.fleet.status                                │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│           Consumer Services (All Registered)                │
├─────────────────────────────────────────────────────────────┤
│  Python Core │ JHipster Portal │ LLM Emulator │ Others      │
└─────────────────────────────────────────────────────────────┘
```

## Voice Topics

### 1. `brain.voice.mood`
**Mood Changes - Current emotional state of the voice system**

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "source": "voice-system",
  "event_id": "uuid",
  "mood": "working",           // calm, working, party
  "reason": "Starting standup",
  "previous_mood": "calm"
}
```

**Usage:**
```python
publisher.publish_mood_change("working", reason="Daily standup")
```

### 2. `brain.voice.lady.speaking`
**Lady Speaking - Which lady is currently speaking**

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "source": "voice-system",
  "event_id": "uuid",
  "lady": "karen",
  "text": "Good morning Joseph",
  "voice_name": "Karen",
  "region": "Australia",
  "duration_ms": 2500
}
```

**Usage:**
```python
publisher.publish_lady_speaking(
    "karen",
    "Good morning everyone!",
    voice_name="Karen",
    region="Australia"
)
```

### 3. `brain.voice.lady.finished`
**Lady Finished - Lady completed speaking**

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "source": "voice-system",
  "event_id": "uuid",
  "lady": "karen",
  "duration_ms": 2500,
  "success": true,
  "error_message": null
}
```

**Usage:**
```python
publisher.publish_lady_finished("karen", success=True)
```

### 4. `brain.voice.queue.status`
**Queue Status - Voice queue state updates**

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "source": "voice-system",
  "event_id": "uuid",
  "queue_length": 3,
  "pending_ladies": ["moira", "flo"],
  "current_lady": "karen",
  "processing": true,
  "queue_items": []
}
```

**Usage:**
```python
publisher.publish_queue_update(
    queue_length=3,
    pending_ladies=["moira", "flo"],
    current_lady="karen",
    processing=True
)
```

### 5. `brain.voice.conversation`
**Conversation - Multi-lady conversation coordination**

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "source": "voice-system",
  "event_id": "uuid",
  "conversation_id": "uuid",
  "ladies": ["karen", "moira", "flo"],
  "topic": "daily-standup",
  "participants": 3,
  "speaker_order": ["karen", "moira", "flo"],
  "context": {
    "duration_target": 300,
    "category": "meeting"
  }
}
```

**Usage:**
```python
publisher.publish_conversation_event(
    ladies=["karen", "moira", "flo"],
    topic="daily-standup",
    speaker_order=["karen", "moira", "flo"],
    context={"duration_target": 300}
)
```

### 6. `brain.voice.fleet.status`
**Fleet Status - Agent/fleet announcements and status**

```json
{
  "timestamp": "2024-01-15T10:30:00.123456",
  "source": "voice-system",
  "event_id": "uuid",
  "message": "All agents online and ready",
  "announcement_type": "info",
  "agent_name": "voice-renderer",
  "fleet_status": "active",
  "affected_agents": ["renderer-1", "renderer-2"]
}
```

**Usage:**
```python
publisher.publish_fleet_announcement(
    "All voice agents online",
    announcement_type="info",
    agent_name="voice-renderer",
    fleet_status="active",
    affected_agents=["renderer-1", "renderer-2"]
)
```

## VoiceEventPublisher API

### Methods

#### `publish_mood_change(mood, reason="", previous_mood=None)`
Publish a mood change event.

**Parameters:**
- `mood` (str, required): `calm`, `working`, or `party`
- `reason` (str, optional): Reason for mood change
- `previous_mood` (str, optional): Previous mood state

**Returns:** Dict with `success`, `event_id`, `mood`, `topic`, `timestamp`

#### `publish_lady_speaking(lady, text, voice_name="", region="")`
Publish lady speaking event.

**Parameters:**
- `lady` (str, required): Lady identifier (karen, moira, etc.)
- `text` (str, required): The text being spoken
- `voice_name` (str, optional): Full voice name
- `region` (str, optional): Voice region
- `duration_ms` (int, optional): Duration in milliseconds

**Returns:** Dict with `success`, `event_id`, `lady`, `text_length`, `topic`

#### `publish_lady_finished(lady, duration_ms=None, success=True, error_message=None)`
Publish lady finished speaking event.

**Parameters:**
- `lady` (str, required): Lady identifier
- `duration_ms` (int, optional): Duration in milliseconds
- `success` (bool, optional): Whether speaking was successful
- `error_message` (str, optional): Error message if failed

**Returns:** Dict with `success`, `event_id`, `lady`, `topic`

#### `publish_queue_update(queue_length, pending_ladies=None, current_lady=None, processing=False)`
Publish queue status update.

**Parameters:**
- `queue_length` (int): Number of items in queue
- `pending_ladies` (list, optional): List of pending ladies
- `current_lady` (str, optional): Currently speaking lady
- `processing` (bool, optional): Whether queue is being processed
- `queue_items` (list, optional): Detailed queue items

**Returns:** Dict with `success`, `event_id`, `queue_length`, `current_lady`, `processing`

#### `publish_conversation_event(ladies, topic, speaker_order=None, context=None, conversation_id=None)`
Publish multi-lady conversation event.

**Parameters:**
- `ladies` (list, required): List of lady identifiers
- `topic` (str, required): Conversation topic
- `speaker_order` (list, optional): Speaker order
- `context` (dict, optional): Conversation context
- `conversation_id` (str, optional): Use existing conversation ID

**Returns:** Dict with `success`, `event_id`, `conversation_id`, `ladies`, `participants`

#### `publish_fleet_announcement(message, announcement_type="info", agent_name="", affected_agents=None)`
Publish fleet/agent announcement.

**Parameters:**
- `message` (str, required): Announcement message
- `announcement_type` (str, optional): `info`, `warning`, `error`, `critical`
- `agent_name` (str, optional): Specific agent name
- `fleet_status` (str, optional): Fleet status
- `affected_agents` (list, optional): Affected agents list

**Returns:** Dict with `success`, `event_id`, `type`, `emoji`, `topic`

#### `get_stats()`
Get publisher statistics.

**Returns:** Dict with `events_published`, `bus_connected`

## VoiceEventSubscriber API

### Methods

#### `on_mood_change(callback)`
Register callback for mood change events.

**Parameters:**
- `callback` (callable): Function to call when mood changes

#### `on_lady_speaking(callback)`
Register callback for lady speaking events.

**Parameters:**
- `callback` (callable): Function to call when lady speaks

#### `on_lady_finished(callback)`
Register callback for lady finished events.

**Parameters:**
- `callback` (callable): Function to call when lady finishes

#### `on_queue_status(callback)`
Register callback for queue status events.

**Parameters:**
- `callback` (callable): Function to call on queue updates

#### `on_conversation(callback)`
Register callback for conversation events.

**Parameters:**
- `callback` (callable): Function to call on conversation events

#### `on_fleet_status(callback)`
Register callback for fleet status events.

**Parameters:**
- `callback` (callable): Function to call on fleet announcements

#### `on_any_voice_event(callback)`
Register callback for any voice event.

**Parameters:**
- `callback` (callable): Function to call for any voice event

#### `subscribe_all()`
Subscribe to all voice topics.

**Returns:** Dict with `subscribed_topics`, `topics`, `status`

#### `get_stats()`
Get subscriber statistics.

**Returns:** Dict with `events_received`, `callbacks_registered`, `topics_subscribed`

## MCP Server Integration

The voice event system is integrated into the Brain Event Bus MCP server at `/Users/joe/brain/mcp-servers/event-bus/server.py`

### Available MCP Tools

#### `voice_mood_change(mood, reason="")`
Publish a mood change event via MCP.

#### `voice_lady_speaking(lady, text, voice_name="", region="")`
Publish lady speaking event via MCP.

#### `voice_lady_finished(lady, success=True, error_message="")`
Publish lady finished event via MCP.

#### `voice_queue_status(queue_length, current_lady="", processing=False)`
Publish queue status via MCP.

#### `voice_conversation(ladies, topic, context=None)`
Publish conversation event via MCP.

#### `voice_fleet_announcement(message, announcement_type="info", agent_name="")`
Publish fleet announcement via MCP.

#### `voice_topics_list()`
List all voice topics and their schemas via MCP.

## Event Schemas

All events include:
- `timestamp` (ISO 8601): When event was created
- `source` (str): Source of event (voice-system, claude-mcp, etc.)
- `event_id` (UUID): Unique event identifier

JSON schemas are available in `VOICE_EVENT_SCHEMAS` dictionary for validation.

## Voice Ladies Roster

Available voice ladies (from server.py):

| ID | Name | Rate | Region |
|----|----|------|--------|
| karen | Karen | 165 | Australia |
| kyoko | Kyoko | 155 | Japan |
| tingting | Tingting | 155 | China |
| sinji | Sinji | 155 | Hong Kong |
| linh | Linh | 155 | Vietnam |
| kanya | Kanya | 155 | Thailand |
| yuna | Yuna | 155 | Korea |
| dewi | Dewi | 155 | Indonesia |
| sari | Sari | 155 | Indonesia |
| wayan | Wayan | 155 | Indonesia |
| moira | Moira | 160 | Ireland |
| zosia | Zosia | 155 | Poland |
| flo | Flo | 160 | England |
| shelley | Shelley | 158 | England |

## Usage Examples

### Example 1: Publishing Mood Changes

```python
from voice_topics import VoiceEventPublisher
from core.kafka_bus import BrainEventBus

# Initialize
bus = BrainEventBus()
bus.connect()
publisher = VoiceEventPublisher(bus)

# Publish mood change
result = publisher.publish_mood_change(
    mood="working",
    reason="Starting daily standup meeting"
)

print(f"Mood changed: {result['mood']}")
# Output: Mood changed: working
```

### Example 2: Multi-Lady Conversation

```python
# Coordinate a conversation between three ladies
result = publisher.publish_conversation_event(
    ladies=["karen", "moira", "flo"],
    topic="daily-standup",
    speaker_order=["karen", "moira", "flo"],
    context={
        "duration_target": 600,  # 10 minutes
        "category": "standup"
    }
)

print(f"Conversation started: {result['conversation_id']}")

# Publish each lady speaking
publisher.publish_lady_speaking("karen", "Karen here, starting the standup")
publisher.publish_lady_finished("karen", duration_ms=2500)

publisher.publish_lady_speaking("moira", "Moira here, my updates...")
publisher.publish_lady_finished("moira", duration_ms=3200)

publisher.publish_lady_speaking("flo", "Flo here, my updates...")
publisher.publish_lady_finished("flo", duration_ms=2800)
```

### Example 3: Subscribing to Events

```python
from voice_topics import VoiceEventSubscriber

subscriber = VoiceEventSubscriber(bus)

# Define callbacks
def on_mood_changed(event):
    print(f"Mood changed to: {event['mood']}")

def on_lady_speaking(event):
    print(f"{event['lady']} is speaking: {event['text']}")

# Register callbacks
subscriber.on_mood_change(on_mood_changed)
subscriber.on_lady_speaking(on_lady_speaking)

# Subscribe to all voice topics
subscriber.subscribe_all()

# Now events will trigger callbacks when published
publisher.publish_mood_change("working")
# Output: Mood changed to: working
```

### Example 4: Fleet Announcements

```python
# Announce fleet status
result = publisher.publish_fleet_announcement(
    message="All voice agents are online and ready",
    announcement_type="info",
    agent_name="voice-renderer",
    fleet_status="active",
    affected_agents=["renderer-1", "renderer-2", "renderer-3"]
)

print(f"Fleet announcement published: {result['type']}")
```

### Example 5: Queue Management

```python
# Update queue status
result = publisher.publish_queue_update(
    queue_length=5,
    pending_ladies=["moira", "flo", "zosia"],
    current_lady="karen",
    processing=True
)

print(f"Queue status: {result['queue_length']} items, current: {result['current_lady']}")
```

## Testing

Run the comprehensive test suite:

```bash
cd /Users/joe/brain/mcp-servers/event-bus
python3 test_voice_topics.py
```

Tests include:
- Topic registry validation
- Event schema validation
- Event dataclass creation
- Publisher functionality
- Subscriber functionality
- Event replay capability

## Event Replay and Debugging

All events are timestamped and have unique IDs, enabling:

1. **Event Replay**: Re-publish events for debugging
2. **Event History**: Track all voice system activity
3. **State Reconstruction**: Rebuild system state from event log
4. **Analytics**: Analyze conversation patterns and metrics

## Performance Considerations

- Events are published asynchronously to Redpanda/Kafka
- Subscribers receive events in publication order
- Queue length and processing status help track backlog
- Fleet announcements broadcast to all subscribers immediately

## Error Handling

All publish methods return structured results with:
- `success` (bool): Whether publication succeeded
- `error` (str): Error message if failed
- `event_id` (str): Unique event identifier
- Other event-specific fields

```python
result = publisher.publish_mood_change("invalid_mood")

if not result["success"]:
    print(f"Error: {result['error']}")
    # Output: Error: Invalid mood: invalid_mood. Must be one of: calm, working, party
```

## Integration Points

The voice event system integrates with:

1. **Event Bus MCP Server** (`server.py`)
   - MCP tools for all voice operations
   - Health checks
   - Provider switching (Redpanda/Kafka)

2. **Voice Rendering Services**
   - Subscribers consume speaking events
   - Publish finished events when done
   - Handle errors gracefully

3. **LLM Services**
   - Request voice LLM responses
   - Receive mood context for tone adjustment
   - Coordinate multi-lady conversation prompts

4. **Voice Cockpit UI**
   - Subscribe to all voice events
   - Display mood, speaker, queue status in real-time
   - Allow manual queue management

## Future Enhancements

Potential expansions:

- Voice recording and transcription events
- Emotion detection from speech
- Multi-language support
- Voice similarity analysis
- Conversation sentiment tracking
- Speaker interruption handling
- Dynamic speaker selection based on context
- Voice quality metrics
- Latency measurement
- Fallback voice handling
