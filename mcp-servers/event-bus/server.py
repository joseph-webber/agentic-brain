#!/usr/bin/env python3
"""
Brain Event Bus MCP Server (FastMCP version)
=============================================

MCP server that provides direct access to the brain's event bus.
Works with both Redpanda (dev) and Kafka (prod) through abstraction.

This is the NERVE CENTER of the brain - Claude talks directly to 
the event bus, and all services (Python, JHipster, LLM) are peers.

Architecture:
  Claude Desktop → MCP → Event Bus → All Services (as peers)

Tools:
  - emit: Publish event to topic
  - health: Check event bus status
  - topics: List all topics
  - switch_provider: Switch between Redpanda/Kafka
  - send_llm_request: Send LLM request with fallback chain
  - broadcast_alert: Broadcast alert to all components
  - query_state: Query brain component states
"""

import json
import os
import sys
import uuid
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.expanduser('~/brain'))
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

# Lazy-loaded imports - heavy modules loaded on first use
_kafka_bus = None
_voice_topics = None
BrainTopics = None
BrainEventBus = None
VoiceTopics = None
VoiceEventPublisher = None
VoiceEventSubscriber = None
validate_voice_event = None


def _get_kafka_bus_module():
    """Lazy load kafka_bus module."""
    global BrainTopics, BrainEventBus
    if BrainTopics is None:
        from core.kafka_bus import BrainTopics as BT, BrainEventBus as BEB
        BrainTopics = BT
        BrainEventBus = BEB
    return BrainTopics, BrainEventBus


def _get_voice_topics():
    """Lazy load voice_topics module."""
    global VoiceTopics, VoiceEventPublisher, VoiceEventSubscriber, validate_voice_event
    if VoiceTopics is None:
        try:
            from voice_topics import (
                VoiceTopics as VT, VoiceEventPublisher as VEP, 
                VoiceEventSubscriber as VES, validate_voice_event as vve
            )
            VoiceTopics = VT
            VoiceEventPublisher = VEP
            VoiceEventSubscriber = VES
            validate_voice_event = vve
        except ImportError:
            try:
                from mcp_servers.event_bus.voice_topics import (
                    VoiceTopics as VT, VoiceEventPublisher as VEP,
                    VoiceEventSubscriber as VES, validate_voice_event as vve
                )
                VoiceTopics = VT
                VoiceEventPublisher = VEP
                VoiceEventSubscriber = VES
                validate_voice_event = vve
            except ImportError:
                pass  # voice_topics not available
    return VoiceTopics, VoiceEventPublisher, VoiceEventSubscriber, validate_voice_event

# Voice ladies roster
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

mcp = FastMCP("event-bus")

# Global bus connection
_bus = None
_provider = os.getenv('EVENT_BUS_PROVIDER', 'redpanda')

# Global voice event publisher and subscriber
_voice_publisher = None
_voice_subscriber = None


def get_bus():
    """Get or create event bus connection."""
    global _bus
    if _bus is None:
        _, BrainEventBus = _get_kafka_bus_module()
        _bus = BrainEventBus()
        _bus.connect()
    return _bus


def get_voice_publisher():
    """Get or create voice event publisher."""
    global _voice_publisher
    if _voice_publisher is None:
        VoiceTopics, VoiceEventPublisher, _, _ = _get_voice_topics()
        if VoiceEventPublisher:
            bus = get_bus()
            _voice_publisher = VoiceEventPublisher(bus)
    return _voice_publisher


def get_voice_subscriber():
    """Get or create voice event subscriber."""
    global _voice_subscriber
    if _voice_subscriber is None:
        VoiceTopics, _, VoiceEventSubscriber, _ = _get_voice_topics()
        if VoiceEventSubscriber:
            bus = get_bus()
            _voice_subscriber = VoiceEventSubscriber(bus)
    return _voice_subscriber


@mcp.tool()
def emit(topic: str, event_type: str, data: dict) -> dict:
    """Publish an event to a brain topic. Topics: brain.health, brain.tasks, brain.state, brain.alerts, brain.learning, brain.llm.request, brain.commands"""
    bus = get_bus()
    
    event = {
        'type': event_type,
        'data': data,
        'timestamp': datetime.now().isoformat(),
        'source': 'claude-mcp'
    }
    
    success = bus.emit(topic, event)
    
    if success:
        return {
            "success": True,
            "topic": topic,
            "event_type": event_type,
            "data": data
        }
    else:
        return {"success": False, "error": f"Failed to emit to {topic}"}


@mcp.tool()
def health() -> str:
    """Check event bus health and status. Shows provider (Redpanda/Kafka), topics, and connection status."""
    global _provider
    bus = get_bus()
    health_data = bus.health_check()
    
    status_emoji = "✅" if health_data.get('status') == 'healthy' else "❌"
    
    return f"""🧠 **Brain Event Bus Status**

{status_emoji} Status: {health_data.get('status', 'unknown')}
📡 Provider: {_provider.upper()}
🔌 Broker: {health_data.get('broker', 'unknown')}
📬 Topics: {health_data.get('brain_topics', 0)} brain topics
🎧 Handlers: {health_data.get('handlers_registered', 0)} registered
⚡ Consuming: {health_data.get('consuming', False)}

**Architecture:**
```
Claude ──► MCP ──► Event Bus ({_provider})
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
      Python       JHipster       LLM
       Core         Portal      Emulator
```
"""


@mcp.tool()
def topics() -> str:
    """List all brain event bus topics with descriptions."""
    return """📬 **Brain Event Bus Topics**

**Core Topics:**
| Topic | Purpose |
|-------|---------|
| `brain.health` | Health checks from all components |
| `brain.tasks` | Task queue between services |
| `brain.state` | State machine transitions |
| `brain.alerts` | Alerts and notifications |
| `brain.commands` | Commands to process |
| `brain.responses` | Responses from services |
| `brain.learning` | Training data collection |
| `brain.diagnostics` | Performance & debug info |
| `brain.llm.request` | LLM requests (with fallback) |
| `brain.llm.response` | LLM responses |
| `brain.mcp.events` | MCP server events |

**Voice Topics (NEW):**
| Topic | Purpose |
|-------|---------|
| `brain.voice.mood` | Current mood (calm, working, party) |
| `brain.voice.lady.speaking` | Which lady is currently speaking |
| `brain.voice.lady.finished` | Lady finished speaking notification |
| `brain.voice.queue.status` | Voice queue state and processing |
| `brain.voice.conversation` | Multi-lady conversation events |
| `brain.voice.fleet.status` | Agent announcements and fleet status |
| `brain.voice.input` | User voice input events (legacy) |
| `brain.voice.response` | Lady voice responses |
| `brain.voice.llm` | LLM requests for voice responses |

**Usage:**
```
emit brain.tasks task_created {"action": "process_ticket", "id": 123}
emit brain.voice.mood mood_changed {"mood": "working"}
voice_mood_change working
voice_lady_speaking karen "Hello Joseph!"
```
"""


@mcp.tool()
def switch_provider(provider: str) -> str:
    """Switch between Redpanda (dev) and Kafka (prod). Same API, different backend."""
    global _bus, _provider
    
    old_provider = _provider
    
    # Disconnect old bus
    if _bus:
        _bus.disconnect()
        _bus = None
    
    # Switch provider
    _provider = provider
    
    # Connect new bus
    bus = get_bus()
    health_data = bus.health_check()
    
    return f"""🔄 **Provider Switched**

From: {old_provider}
To: {provider}
Status: {health_data.get('status', 'unknown')}

Same Kafka API - all services continue working!"""


@mcp.tool()
def send_llm_request(prompt: str, system: str = None, priority: str = "normal") -> dict:
    """Send a request to the LLM pool (Claude → OpenRouter → Emulator fallback chain)."""
    BrainTopics, _ = _get_kafka_bus_module()
    bus = get_bus()
    
    request_id = str(uuid.uuid4())
    
    event = {
        'type': 'llm_request',
        'request_id': request_id,
        'prompt': prompt,
        'system': system or '',
        'priority': priority,
        'timestamp': datetime.now().isoformat(),
        'source': 'claude-mcp',
        'fallback_chain': ['claude', 'openrouter', 'emulator']
    }
    
    bus.emit(BrainTopics.LLM_REQUEST, event)
    
    return {
        "request_id": request_id,
        "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        "priority": priority,
        "fallback_chain": ['claude', 'openrouter', 'emulator'],
        "note": "Response will arrive on brain.llm.response topic"
    }


@mcp.tool()
def broadcast_alert(level: str, message: str, source: str = "claude-mcp") -> dict:
    """Broadcast an alert to all brain components. Levels: info, warning, error, critical"""
    BrainTopics, _ = _get_kafka_bus_module()
    bus = get_bus()
    
    event = {
        'type': 'alert',
        'level': level,
        'message': message,
        'source': source,
        'timestamp': datetime.now().isoformat()
    }
    
    bus.emit(BrainTopics.ALERTS, event)
    
    level_emoji = {'info': 'ℹ️', 'warning': '⚠️', 'error': '❌', 'critical': '🚨'}
    
    return {
        "emoji": level_emoji.get(level, '📢'),
        "level": level.upper(),
        "message": message,
        "source": source,
        "note": "All brain components notified"
    }


@mcp.tool()
def send_voice_request(prompt: str, lady: str = "karen", priority: str = "normal") -> dict:
    """Send a voice LLM request - generates spoken response from lady voice.
    Ladies: karen, kyoko, tingting, yuna, moira, zosia, flo, shelley, and more."""
    bus = get_bus()
    
    # Validate lady exists
    if lady not in VOICE_LADIES:
        lady = "karen"
    
    request_id = str(uuid.uuid4())
    voice_name, rate, region = VOICE_LADIES[lady]
    
    event = {
        'type': 'voice_llm_request',
        'request_id': request_id,
        'prompt': prompt,
        'lady': lady,
        'voice_name': voice_name,
        'region': region,
        'priority': priority,
        'timestamp': datetime.now().isoformat(),
        'source': 'claude-mcp',
        'fallback_chain': ['claude', 'openrouter', 'emulator']
    }
    
    bus.emit('brain.voice.llm', event)
    
    return {
        "request_id": request_id,
        "lady": lady,
        "voice_name": voice_name,
        "region": region,
        "prompt_preview": prompt[:80] + "..." if len(prompt) > 80 else prompt,
        "priority": priority,
        "note": "Voice response will arrive on brain.voice.response topic"
    }


@mcp.tool()
def broadcast_voice(message: str, lady: str = "karen") -> dict:
    """Broadcast a spoken message with lady voice. Emits to brain.voice.response topic.
    Ladies available: karen, kyoko, tingting, yuna, moira, zosia, flo, shelley, and more."""
    bus = get_bus()
    
    # Validate lady exists
    if lady not in VOICE_LADIES:
        lady = "karen"
    
    voice_name, rate, region = VOICE_LADIES[lady]
    
    # Emit voice response event
    event = {
        'type': 'voice_response',
        'message': message,
        'lady': lady,
        'voice_name': voice_name,
        'region': region,
        'timestamp': datetime.now().isoformat(),
        'source': 'claude-mcp'
    }
    
    bus.emit('brain.voice.response', event)
    
    # Also speak it immediately (local Mac)
    try:
        subprocess.run(
            ["say", "-v", voice_name, "-r", str(rate), message],
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        # If local speech fails, voice system will handle it via event
        pass
    
    return {
        "lady": lady,
        "voice_name": voice_name,
        "region": region,
        "message": message,
        "message_length": len(message),
        "note": "Broadcast via brain.voice.response topic + local voice"
    }


@mcp.tool()
def query_state(component: str = "all") -> dict:
    """Query the current state of brain components. Components: llm, bots, jhipster, all"""
    global _provider, _bus
    BrainTopics, _ = _get_kafka_bus_module()
    bus = get_bus()
    
    event = {
        'type': 'state_query',
        'component': component,
        'timestamp': datetime.now().isoformat(),
        'source': 'claude-mcp'
    }
    
    bus.emit(BrainTopics.STATE, event)
    
    return {
        "component": component,
        "query_sent": True,
        "response_topic": "brain.state",
        "current_bus_state": {
            "provider": _provider,
            "connected": _bus is not None,
            "topics_configured": len(BrainTopics.all())
        }
    }


# ============================================================================
# New Voice Event Publishing Tools
# ============================================================================

# Voice tools - registered dynamically when first used
_voice_tools_registered = False


def _ensure_voice_tools():
    """Register voice tools on first use."""
    global _voice_tools_registered
    if _voice_tools_registered:
        return
    
    VoiceTopics, _, _, _ = _get_voice_topics()
    if VoiceTopics is None:
        return
    
    _voice_tools_registered = True


@mcp.tool()
def voice_mood_change(mood: str, reason: str = "") -> dict:
    """Publish a mood change event. Moods: calm, working, party"""
    VoiceTopics, _, _, _ = _get_voice_topics()
    if not VoiceTopics:
        return {"status": "❌ Failed", "error": "Voice topics not available"}
    
    publisher = get_voice_publisher()
    if not publisher:
        return {"status": "❌ Failed", "error": "Voice publisher not available"}
    
    result = publisher.publish_mood_change(mood, reason)
    
    if result.get("success"):
        return {
            "status": "✅ Published",
            "mood": mood,
            "reason": reason or "(no reason)",
            "topic": VoiceTopics.MOOD,
            "event_id": result.get("event_id")
        }
    else:
        return {
            "status": "❌ Failed",
            "error": result.get("error"),
            "mood": mood
        }


@mcp.tool()
def voice_lady_speaking(lady: str, text: str, voice_name: str = "", region: str = "") -> dict:
    """Publish lady speaking event.
    Ladies: karen, kyoko, tingting, sinji, linh, kanya, yuna, dewi, sari, wayan, moira, zosia, flo, shelley"""
    VoiceTopics, _, _, _ = _get_voice_topics()
    if not VoiceTopics:
        return {"status": "❌ Failed", "error": "Voice topics not available"}
    
    publisher = get_voice_publisher()
    if not publisher:
        return {"status": "❌ Failed", "error": "Voice publisher not available"}
    
    result = publisher.publish_lady_speaking(lady, text, voice_name, region)
    
    if result.get("success"):
        return {
            "status": "✅ Published",
            "lady": lady,
            "text_preview": text[:50] + "..." if len(text) > 50 else text,
            "text_length": result.get("text_length"),
            "topic": VoiceTopics.LADY_SPEAKING,
            "event_id": result.get("event_id")
        }
    else:
        return {
            "status": "❌ Failed",
            "error": result.get("error"),
            "lady": lady
        }


@mcp.tool()
def voice_lady_finished(lady: str, success: bool = True, error_message: str = "") -> dict:
    """Publish lady finished speaking event."""
    VoiceTopics, _, _, _ = _get_voice_topics()
    if not VoiceTopics:
        return {"status": "❌ Failed", "error": "Voice topics not available"}
    
    publisher = get_voice_publisher()
    if not publisher:
        return {"status": "❌ Failed", "error": "Voice publisher not available"}
    
    result = publisher.publish_lady_finished(lady, success=success, error_message=error_message if error_message else None)
    
    if result.get("success"):
        return {
            "status": "✅ Published",
            "lady": lady,
            "success": success,
            "topic": VoiceTopics.LADY_FINISHED,
            "event_id": result.get("event_id")
        }
    else:
        return {
            "status": "❌ Failed",
            "error": result.get("error"),
            "lady": lady
        }


@mcp.tool()
def voice_queue_status(queue_length: int = 0, current_lady: str = "", processing: bool = False) -> dict:
    """Publish voice queue status update."""
    VoiceTopics, _, _, _ = _get_voice_topics()
    if not VoiceTopics:
        return {"status": "❌ Failed", "error": "Voice topics not available"}
    
    publisher = get_voice_publisher()
    if not publisher:
        return {"status": "❌ Failed", "error": "Voice publisher not available"}
    
    result = publisher.publish_queue_update(
        queue_length=queue_length,
        current_lady=current_lady if current_lady else None,
        processing=processing
    )
    
    if result.get("success"):
        return {
            "status": "✅ Published",
            "queue_length": queue_length,
            "current_lady": current_lady or "none",
            "processing": processing,
            "topic": VoiceTopics.QUEUE_STATUS,
            "event_id": result.get("event_id")
        }
    else:
        return {
            "status": "❌ Failed",
            "error": result.get("error")
        }


@mcp.tool()
def voice_conversation(ladies: list[str], topic: str, context: dict = None) -> dict:
    """Publish multi-lady conversation event.
    Ladies: karen, kyoko, tingting, moira, zosia, flo, and others"""
    VoiceTopics, _, _, _ = _get_voice_topics()
    if not VoiceTopics:
        return {"status": "❌ Failed", "error": "Voice topics not available"}
    
    publisher = get_voice_publisher()
    if not publisher:
        return {"status": "❌ Failed", "error": "Voice publisher not available"}
    
    result = publisher.publish_conversation_event(ladies, topic, context=context)
    
    if result.get("success"):
        return {
            "status": "✅ Published",
            "ladies": ladies,
            "topic": topic,
            "participants": len(ladies),
            "topic_voice": VoiceTopics.CONVERSATION,
            "conversation_id": result.get("conversation_id"),
            "event_id": result.get("event_id")
        }
    else:
        return {
            "status": "❌ Failed",
            "error": result.get("error"),
            "topic": topic
        }


@mcp.tool()
def voice_fleet_announcement(message: str, announcement_type: str = "info", agent_name: str = "") -> dict:
    """Publish fleet/agent announcement. Types: info, warning, error, critical"""
    VoiceTopics, _, _, _ = _get_voice_topics()
    if not VoiceTopics:
        return {"status": "❌ Failed", "error": "Voice topics not available"}
    
    publisher = get_voice_publisher()
    if not publisher:
        return {"status": "❌ Failed", "error": "Voice publisher not available"}
    
    result = publisher.publish_fleet_announcement(
        message,
        announcement_type=announcement_type,
        agent_name=agent_name if agent_name else None
    )
    
    if result.get("success"):
        type_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🚨"
        }
        return {
            "status": "✅ Published",
            "emoji": type_emoji.get(announcement_type, "📢"),
            "type": announcement_type.upper(),
            "message": message[:60] + "..." if len(message) > 60 else message,
            "agent": agent_name or "fleet",
            "topic": VoiceTopics.FLEET_STATUS,
            "event_id": result.get("event_id")
        }
    else:
        return {
            "status": "❌ Failed",
            "error": result.get("error"),
            "type": announcement_type
        }


@mcp.tool()
def voice_topics_list() -> str:
    """List all voice event topics and schemas."""
    VoiceTopics, _, _, _ = _get_voice_topics()
    if not VoiceTopics:
        return "Voice topics not available"
    
    topics_list = "\n".join([f"- `{topic}`: {VoiceTopics.get_description(topic)}" for topic in VoiceTopics.all()])
    return f"""🎤 **Voice Event Topics & Schemas**

**Topics:**
{topics_list}

**Event Schemas:**

1. **brain.voice.mood** - Mood change events
   ```json
   {{
     "timestamp": "2024-01-15T10:30:00.123456",
     "source": "voice-system",
     "event_id": "uuid",
     "mood": "working",
     "reason": "Starting standup",
     "previous_mood": "calm"
   }}
   ```

2. **brain.voice.lady.speaking** - Lady speaking events
   ```json
   {{
     "timestamp": "2024-01-15T10:30:00.123456",
     "source": "voice-system",
     "event_id": "uuid",
     "lady": "karen",
     "text": "Good morning Joseph",
     "voice_name": "Karen",
     "region": "Australia",
     "duration_ms": 2500
   }}
   ```

3. **brain.voice.conversation** - Multi-lady conversation
   ```json
   {{
     "timestamp": "2024-01-15T10:30:00.123456",
     "source": "voice-system",
     "event_id": "uuid",
     "conversation_id": "uuid",
     "ladies": ["karen", "moira"],
     "topic": "standup",
     "participants": 2,
     "speaker_order": ["karen", "moira"],
     "context": {{}}
   }}
   ```

4. **brain.voice.fleet.status** - Fleet announcements
   ```json
   {{
     "timestamp": "2024-01-15T10:30:00.123456",
     "source": "voice-system",
     "event_id": "uuid",
     "message": "All agents online",
     "announcement_type": "info",
     "agent_name": "jane-bot",
     "fleet_status": "active"
   }}
   ```

**Publishing Tools:**
- `voice_mood_change(mood, reason)` - Change mood
- `voice_lady_speaking(lady, text)` - Lady speaks
- `voice_lady_finished(lady, success)` - Lady done
- `voice_queue_status(length, current)` - Queue update
- `voice_conversation(ladies, topic)` - Start multi-lady chat
- `voice_fleet_announcement(message, type)` - Fleet announcement
"""


if __name__ == "__main__":
    print("🧠 Event Bus MCP Server (FastMCP) starting...")
    mcp.run()
