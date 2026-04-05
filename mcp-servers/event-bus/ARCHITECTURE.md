# Event Bus Architecture

## Overview

The Brain Event Bus is the nerve center of the agentic brain system. It provides a unified event messaging interface that enables all brain components (Claude via MCP, Python services, JHipster backend, LLM providers) to communicate as peers.

```
Claude Desktop
    ↓ (MCP)
Event Bus MCP Server
    ↓
Core Kafka/Redpanda Abstraction
    ↓
Message Broker (Redpanda in dev, Kafka in prod)
    ↓ (subscriptions)
All Brain Services (as independent peers)
```

## Components

### 1. Core Modules

#### `voice_topics.py` (v2 - Enhanced)
Complete voice event system with conversation lifecycle management.

**Features:**
- **Conversation Lifecycle**: started, turn, ended events
- **Lady Communication**: lady_introduced, lady_reaction events
- **Mood Synchronization**: mood_changed event with reasons
- **Turn-Taking**: request, grant, release events
- **Fallback Handling**: fallback_local event for error recovery
- **Voice Queue Management**: added, speaking, empty queue events
- **Event Validation**: Schema-based validation for all events

**Key Classes:**
- `VoiceTopics`: Topic registry with all event topic constants
- `VoiceEventPublisher`: Publish events to the bus
- `VoiceEventSubscriber`: Subscribe to events with callbacks
- `*Event`: Typed dataclasses for each event (e.g., ConversationStartedEvent)

**Voice Ladies:**
- Australian: karen
- Asian: kyoko (Japan), tingting (China), sinji (Hong Kong), linh (Vietnam), kanya (Thailand), yuna (Korea), dewi/sari/wayan (Indonesia)
- European: moira (Ireland), zosia (Poland), flo/shelley (England)

#### `server.py` (v2 - Enhanced)
MCP server that provides direct access to the event bus for Claude.

**Tools:**
- `emit`: Publish events to topics
- `health`: Check event bus status
- `topics`: List all available topics
- `switch_provider`: Switch between Redpanda (dev) and Kafka (prod)
- `send_llm_request`: Route LLM requests with fallback chain
- `broadcast_alert`: Send alerts to all components
- `query_state`: Query current component states

**Architecture:**
```
Claude → MCP (server.py) → Event Bus Abstraction → Broker → Services
```

### 2. Supporting Files

#### `core/kafka_bus.py` (Abstraction Layer)
Located in the parent directory, provides unified interface for both Redpanda and Kafka.

**Classes:**
- `BrainTopics`: Topic registry for all core events
- `BrainEventBus`: Connection and publish/subscribe abstraction

#### Test Suite: `test_voice_topics.py`
Comprehensive tests covering:
- Conversation lifecycle (22 test cases)
- Lady communication
- Mood synchronization
- Turn-taking management
- Fallback handling
- Voice queue management
- Event validation
- Integration workflows

## Event Topics

### Conversation Lifecycle
- `brain.voice.conversation.started` - Start multi-lady conversation
- `brain.voice.conversation.turn` - Lady takes turn speaking
- `brain.voice.conversation.ended` - Conversation ends

### Lady Communication
- `brain.voice.lady.introduced` - New lady introduced
- `brain.voice.lady.reaction` - Lady reacts to another lady

### Mood Management
- `brain.voice.mood.changed` - System mood changes (calm, working, party)

### Turn-Taking
- `brain.voice.turn.requested` - Lady requests speaking turn
- `brain.voice.turn.granted` - Speaking turn granted
- `brain.voice.turn.released` - Speaking turn released

### Error Handling
- `brain.voice.fallback.local` - Fallback to local LLM (rate limit, etc)

### Voice Queue
- `brain.voice.queue.added` - Lady added to queue
- `brain.voice.queue.speaking` - Lady started speaking
- `brain.voice.queue.empty` - Queue is empty

## Event Structure

All events follow this schema:

```python
{
    "id": "uuid",
    "timestamp": "ISO8601",
    "source": "component_name",
    "event_type": "event_class_name",
    "data": {
        # Event-specific fields
    }
}
```

### Example: Conversation Started
```python
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2024-01-15T10:30:00Z",
    "source": "claude",
    "event_type": "ConversationStartedEvent",
    "data": {
        "ladies": ["karen", "moira"],
        "topic": "standup",
        "language": "english",
        "context": {"sprint": "2024-Q1"}
    }
}
```

## Usage Examples

### Publishing Events

```python
from voice_topics import VoiceEventPublisher

# Create publisher
publisher = VoiceEventPublisher(bus)

# Start conversation
publisher.publish_conversation_started(
    ladies=["karen", "moira"],
    topic="standup"
)

# Lady takes turn
publisher.publish_conversation_turn(
    lady="karen",
    text="Let's discuss the sprint progress",
    duration_seconds=30
)

# Mood change
publisher.publish_mood_changed(
    mood="working",
    reason="standup_started"
)

# Turn-taking
publisher.publish_turn_requested(lady="moira")
publisher.publish_turn_granted(lady="moira", granted_by="karen")

# End conversation
publisher.publish_conversation_ended(
    ladies=["karen", "moira"],
    topic="standup",
    duration_seconds=300
)
```

### Subscribing to Events

```python
from voice_topics import VoiceEventSubscriber

# Create subscriber
subscriber = VoiceEventSubscriber(bus)

# Subscribe to conversations
def on_conversation_started(event):
    print(f"Conversation started: {event['data']['topic']}")
    print(f"Ladies: {', '.join(event['data']['ladies'])}")

subscriber.subscribe(
    topic=VoiceTopics.CONVERSATION_STARTED,
    callback=on_conversation_started
)

# Subscribe to mood changes
def on_mood_changed(event):
    print(f"Mood changed to: {event['data']['mood']}")

subscriber.subscribe(
    topic=VoiceTopics.MOOD_CHANGED,
    callback=on_mood_changed
)
```

## Architecture Principles

### 1. **Peer Architecture**
All components are peers on the event bus. No central dispatcher or message queue.

### 2. **Event-Driven**
All communication flows through immutable events on the bus.

### 3. **Loose Coupling**
Publishers don't know subscribers. Subscribers don't know publishers.

### 4. **Schema Validation**
All events are validated against schemas before publishing.

### 5. **Audit Trail**
All events are timestamped and sourced for debugging/replay.

### 6. **Fallback Handling**
Graceful degradation when external services (LLM, APIs) fail.

## Data Flow

### Typical Conversation Flow

```
1. Claude publishes CONVERSATION_STARTED
   ↓
2. All subscribers notified (Python service, JHipster, etc)
   ↓
3. Service publishes LADY_INTRODUCED for each lady
   ↓
4. Ladies start conversation, alternating CONVERSATION_TURN events
   ↓
5. Mood changes triggered by MOOD_CHANGED events
   ↓
6. Turn-taking managed by TURN_REQUESTED/GRANTED/RELEASED
   ↓
7. Conversation ends with CONVERSATION_ENDED
   ↓
8. All subscribers receive final event and clean up
```

## Error Handling

### Rate Limiting
When API rate limits are hit, publish `FALLBACK_LOCAL` event to trigger local LLM fallback.

```python
publisher.publish_fallback_local(
    reason="rate_limit_429",
    service="openai",
    fallback_strategy="local_llama3_8b"
)
```

### Failed Events
Events are validated before publishing. Invalid events raise `ValidationError`.

```python
try:
    publisher.publish_conversation_turn(
        lady="invalid_lady",  # Will fail validation
        text="Hello"
    )
except ValidationError as e:
    print(f"Invalid event: {e}")
```

## Configuration

### Environment Variables
- `EVENT_BUS_PROVIDER`: `redpanda` (dev) or `kafka` (prod), default: `redpanda`
- `KAFKA_BROKER`: Comma-separated broker list, default: `localhost:9092`
- `KAFKA_TOPIC_PREFIX`: Topic prefix, default: `brain`

### Connection Settings
Configured in `core/kafka_bus.py`:
- Redpanda: `localhost:9092` (dev)
- Kafka: Production cluster URL

## Version History

### v2 (Current - Enhanced)
- Conversation lifecycle events
- Turn-taking management
- Cross-lady communication
- Mood synchronization
- Fallback handling
- Voice queue management
- Full event validation
- 22 test cases (all passing)

### v1 (Deprecated - Removed)
- Basic lady speaking events
- Simple mood changes
- Fleet status only
- Limited validation

**Migration Status:** ✅ Complete - v1 files removed, v2 standardized as default

## Testing

Run all tests:
```bash
cd /Users/joe/brain/agentic-brain/mcp-servers/event-bus
python -m pytest test_voice_topics.py -v
```

Expected output: 22 tests pass

## References

- `README_IMPLEMENTATION.md` - Implementation details
- `README_VOICE.md` - Voice system overview
- `VOICE_TOPICS_DOCUMENTATION.md` - Topic documentation
- `VOICE_TOPICS_SUMMARY.txt` - Quick reference
