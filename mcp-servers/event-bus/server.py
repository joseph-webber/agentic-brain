#!/usr/bin/env python3
"""
Brain Event Bus MCP Server - VOICE ENHANCED
===========================================

MCP server with voice integration featuring:
- Conversation lifecycle (started, turn, ended)
- Cross-lady communication and reactions
- Mood synchronization
- Turn-taking management
- Error fallback handling
- Voice queue management

Works with both Redpanda (dev) and Kafka (prod) through abstraction.

Architecture:
  Claude Desktop → MCP → Event Bus → All Services (as peers)
"""

import json
import os
import sys
import uuid
import subprocess
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/brain"))
sys.path.insert(0, os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP

# Import our abstraction layer
from core.kafka_bus import BrainTopics, BrainEventBus

# Import voice topics (enhanced)
try:
    from voice_topics import (
        VoiceTopics,
        VoiceEventPublisher,
        VoiceEventSubscriber,
        ConversationStartedEvent,
        ConversationTurnEvent,
        ConversationEndedEvent,
        LadyIntroducedEvent,
        LadyReactionEvent,
        MoodChangedEvent,
        TurnRequestedEvent,
        TurnGrantedEvent,
        TurnReleasedEvent,
        FallbackLocalEvent,
        QueueAddedEvent,
        QueueSpeakingEvent,
        QueueEmptyEvent,
        validate_voice_event,
    )
except ImportError as e:
    VoiceTopics = None
    VoiceEventPublisher = None
    print(f"Warning: Could not import voice_topics: {e}")

# Voice ladies roster (for backward compatibility)
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
_provider = os.getenv("EVENT_BUS_PROVIDER", "redpanda")

# Global voice publishers and subscribers
_voice_publisher = None
_voice_subscriber = None


def get_bus():
    """Get or create event bus connection."""
    global _bus
    if _bus is None:
        _bus = BrainEventBus()
        _bus.connect()
    return _bus


def get_voice_publisher():
    """Get or create voice event publisher."""
    global _voice_publisher
    if _voice_publisher is None:
        bus = get_bus()
        _voice_publisher = VoiceEventPublisher(bus)
    return _voice_publisher


def get_voice_subscriber():
    """Get or create voice event subscriber."""
    global _voice_subscriber
    if _voice_subscriber is None:
        bus = get_bus()
        _voice_subscriber = VoiceEventSubscriber(bus)
    return _voice_subscriber


# ============================================================================
# CORE EVENT BUS TOOLS (unchanged from v1)
# ============================================================================


@mcp.tool()
def emit(topic: str, event_type: str, data: dict) -> dict:
    """Publish an event to a brain topic. Topics: brain.health, brain.tasks, brain.state, brain.alerts, brain.learning, brain.llm.request, brain.commands"""
    bus = get_bus()

    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "source": "claude-mcp",
    }

    success = bus.emit(topic, event)

    if success:
        return {"success": True, "topic": topic, "event_type": event_type, "data": data}
    else:
        return {"success": False, "error": f"Failed to emit to {topic}"}


@mcp.tool()
def health() -> str:
    """Check event bus health and status. Shows provider (Redpanda/Kafka), topics, and connection status."""
    global _provider
    bus = get_bus()
    health_data = bus.health_check()

    status_emoji = "✅" if health_data.get("status") == "healthy" else "❌"

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

**Voice Topics (ENHANCED):**
| Topic | Purpose |
|-------|---------|
| `brain.voice.conversation.started` | Multi-lady conversation started |
| `brain.voice.conversation.turn` | Lady takes turn in conversation |
| `brain.voice.conversation.ended` | Conversation ended |
| `brain.voice.ladies.introduced` | New lady joins the team |
| `brain.voice.ladies.reaction` | Lady reacts to another lady |
| `brain.voice.mood.changed` | All ladies sync to same mood |
| `brain.voice.turn.requested` | Request to speak |
| `brain.voice.turn.granted` | Turn granted to speak |
| `brain.voice.turn.released` | Turn released |
| `brain.voice.fallback.local` | Fallback to local LLM (rate limit) |
| `brain.voice.queue.added` | Item added to voice queue |
| `brain.voice.queue.speaking` | Lady currently speaking |
| `brain.voice.queue.empty` | Voice queue is empty |

**Usage Examples:**
```
# Start conversation
voice_conversation_started ["karen", "moira"] "standup"

# Lady takes turn
voice_conversation_turn "karen" "Let's discuss the sprint"

# Mood sync (everyone calm)
voice_mood_changed "calm" "spa_time"

# Turn-taking
voice_turn_requested "kyoko"
voice_turn_granted "kyoko"

# Rate limit fallback
voice_fallback_local "429 rate limit"

# Voice queue
voice_queue_added "tingting" "Hello there!"
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
    bus = get_bus()

    request_id = str(uuid.uuid4())

    event = {
        "type": "llm_request",
        "request_id": request_id,
        "prompt": prompt,
        "system": system or "",
        "priority": priority,
        "timestamp": datetime.now().isoformat(),
        "source": "claude-mcp",
        "fallback_chain": ["claude", "openrouter", "emulator"],
    }

    bus.emit(BrainTopics.LLM_REQUEST, event)

    return {
        "request_id": request_id,
        "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt,
        "priority": priority,
        "fallback_chain": ["claude", "openrouter", "emulator"],
        "note": "Response will arrive on brain.llm.response topic",
    }


@mcp.tool()
def broadcast_alert(level: str, message: str, source: str = "claude-mcp") -> dict:
    """Broadcast an alert to all brain components. Levels: info, warning, error, critical"""
    bus = get_bus()

    event = {
        "type": "alert",
        "level": level,
        "message": message,
        "source": source,
        "timestamp": datetime.now().isoformat(),
    }

    bus.emit(BrainTopics.ALERTS, event)

    level_emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}

    return {
        "emoji": level_emoji.get(level, "📢"),
        "level": level.upper(),
        "message": message,
        "source": source,
        "note": "All brain components notified",
    }


@mcp.tool()
def query_state(component: str = "all") -> dict:
    """Query the current state of brain components. Components: llm, bots, jhipster, all"""
    global _provider, _bus
    bus = get_bus()

    event = {
        "type": "state_query",
        "component": component,
        "timestamp": datetime.now().isoformat(),
        "source": "claude-mcp",
    }

    bus.emit(BrainTopics.STATE, event)

    return {
        "component": component,
        "query_sent": True,
        "response_topic": "brain.state",
        "current_bus_state": {
            "provider": _provider,
            "connected": _bus is not None,
            "topics_configured": len(BrainTopics.all()),
        },
    }


# ============================================================================
# ENHANCED VOICE TOOLS
# ============================================================================

if VoiceTopics is not None:

    # =====================================================================
    # CONVERSATION LIFECYCLE TOOLS
    # =====================================================================

    @mcp.tool()
    def voice_conversation_started(
        ladies: list, topic: str = "", speaker_order: list = None, context: dict = None
    ) -> dict:
        """Start a multi-lady conversation. Publishes to brain.voice.conversation.started

        Ladies: karen, kyoko, tingting, sinji, linh, kanya, yuna, dewi, sari, wayan, moira, zosia, flo, shelley

        Example:
            voice_conversation_started ["karen", "moira"] "standup"
        """
        publisher = get_voice_publisher()
        result = publisher.publish_conversation_started(
            ladies=ladies,
            topic=topic,
            speaker_order=speaker_order or ladies,
            context=context or {},
        )

        if result.get("success"):
            return {
                "status": "✅ Conversation Started",
                "ladies": ladies,
                "topic": topic,
                "conversation_id": result.get("conversation_id"),
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.CONVERSATION_STARTED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    @mcp.tool()
    def voice_conversation_turn(
        lady: str,
        text: str,
        voice_name: str = "",
        region: str = "",
        turn_number: int = 0,
    ) -> dict:
        """Lady takes a turn in the conversation. Publishes to brain.voice.conversation.turn

        Example:
            voice_conversation_turn "karen" "Let's discuss the sprint backlog"
        """
        publisher = get_voice_publisher()
        result = publisher.publish_conversation_turn(
            lady=lady,
            text=text,
            voice_name=voice_name,
            region=region,
            turn_number=turn_number,
        )

        if result.get("success"):
            return {
                "status": "✅ Turn Published",
                "lady": lady,
                "text_preview": result.get("text_preview"),
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.CONVERSATION_TURN,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    @mcp.tool()
    def voice_conversation_ended(
        ladies: list,
        total_turns: int = 0,
        duration_seconds: float = 0.0,
        reason: str = "completed",
    ) -> dict:
        """End a conversation. Publishes to brain.voice.conversation.ended

        Reason: "completed", "interrupted", "error"

        Example:
            voice_conversation_ended ["karen", "moira"] 4 30.5 "completed"
        """
        publisher = get_voice_publisher()
        result = publisher.publish_conversation_ended(
            ladies=ladies,
            total_turns=total_turns,
            duration_seconds=duration_seconds,
            reason=reason,
        )

        if result.get("success"):
            return {
                "status": "✅ Conversation Ended",
                "ladies": ladies,
                "total_turns": result.get("total_turns"),
                "duration_seconds": result.get("duration_seconds"),
                "reason": reason,
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.CONVERSATION_ENDED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    # =====================================================================
    # LADY INTRODUCTION AND REACTIONS
    # =====================================================================

    @mcp.tool()
    def voice_lady_introduced(
        lady: str, voice_name: str = "", region: str = "", greeting: str = ""
    ) -> dict:
        """Introduce a new lady to the team. Publishes to brain.voice.ladies.introduced

        Example:
            voice_lady_introduced "iris" "Iris" "San Francisco" "Hello there!"
        """
        publisher = get_voice_publisher()
        result = publisher.publish_lady_introduced(
            lady=lady, voice_name=voice_name, region=region, greeting=greeting
        )

        if result.get("success"):
            return {
                "status": "✅ Lady Introduced",
                "lady": lady,
                "region": result.get("region"),
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.LADY_INTRODUCED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    @mcp.tool()
    def voice_lady_reaction(
        from_lady: str,
        to_lady: str,
        original_text: str = "",
        reaction_text: str = "",
        emotion: str = "",
    ) -> dict:
        """Lady reacts to what another lady said. Publishes to brain.voice.ladies.reaction

        Emotions: "agreement", "disagreement", "question", "excitement", "support"

        Example:
            voice_lady_reaction "moira" "karen" "Let's discuss..." "That sounds great!" "agreement"
        """
        publisher = get_voice_publisher()
        result = publisher.publish_lady_reaction(
            from_lady=from_lady,
            to_lady=to_lady,
            original_text=original_text,
            reaction_text=reaction_text,
            emotion=emotion,
        )

        if result.get("success"):
            return {
                "status": "✅ Reaction Published",
                "from_lady": from_lady,
                "to_lady": to_lady,
                "emotion": emotion,
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.LADY_REACTION,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    # =====================================================================
    # MOOD SYNCHRONIZATION
    # =====================================================================

    @mcp.tool()
    def voice_mood_changed(mood: str, reason: str = "", ladies: list = None) -> dict:
        """Change mood - all ladies sync! Publishes to brain.voice.mood.changed

        Moods: "calm", "working", "party", "focused", "bali_spa", "creative"

        Example:
            voice_mood_changed "calm" "time_for_spa"
            voice_mood_changed "working" "sprint_standup" ["karen", "moira", "tingting"]
        """
        publisher = get_voice_publisher()
        result = publisher.publish_mood_changed(
            mood=mood, reason=reason, ladies=ladies or []
        )

        if result.get("success"):
            return {
                "status": "✅ Mood Changed",
                "mood": mood,
                "previous_mood": result.get("previous_mood"),
                "reason": reason,
                "ladies_synced": result.get("ladies_synced"),
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.MOOD_CHANGED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    # =====================================================================
    # TURN-TAKING EVENTS (prevent overlapping speech)
    # =====================================================================

    @mcp.tool()
    def voice_turn_requested(lady: str, priority: int = 0, reason: str = "") -> dict:
        """Request speaking turn. Publishes to brain.voice.turn.requested

        Priority: 0=normal, 1=high, 2=critical

        Example:
            voice_turn_requested "kyoko" 0 "wants_to_comment"
        """
        publisher = get_voice_publisher()
        result = publisher.publish_turn_requested(
            lady=lady, priority=priority, reason=reason
        )

        if result.get("success"):
            return {
                "status": "✅ Turn Requested",
                "lady": lady,
                "request_id": result.get("request_id"),
                "priority": priority,
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.TURN_REQUESTED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    @mcp.tool()
    def voice_turn_granted(
        lady: str,
        request_id: str = "",
        granted_by: str = "moderator",
        duration_seconds: float = 30.0,
    ) -> dict:
        """Grant speaking turn. Publishes to brain.voice.turn.granted

        Example:
            voice_turn_granted "kyoko" "" "karen" 30.0
        """
        publisher = get_voice_publisher()
        result = publisher.publish_turn_granted(
            lady=lady,
            request_id=request_id,
            granted_by=granted_by,
            duration_seconds=duration_seconds,
        )

        if result.get("success"):
            return {
                "status": "✅ Turn Granted",
                "lady": lady,
                "request_id": result.get("request_id"),
                "duration_seconds": duration_seconds,
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.TURN_GRANTED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    @mcp.tool()
    def voice_turn_released(
        lady: str,
        request_id: str = "",
        reason: str = "finished",
        duration_held_seconds: float = 0.0,
    ) -> dict:
        """Release speaking turn. Publishes to brain.voice.turn.released

        Reason: "finished", "interrupted", "timeout"

        Example:
            voice_turn_released "kyoko" "" "finished" 25.5
        """
        publisher = get_voice_publisher()
        result = publisher.publish_turn_released(
            lady=lady,
            request_id=request_id,
            reason=reason,
            duration_held_seconds=duration_held_seconds,
        )

        if result.get("success"):
            return {
                "status": "✅ Turn Released",
                "lady": lady,
                "reason": reason,
                "duration_held": duration_held_seconds,
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.TURN_RELEASED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    # =====================================================================
    # ERROR HANDLING AND FALLBACK
    # =====================================================================

    @mcp.tool()
    def voice_fallback_local(
        reason: str = "",
        lady: str = "karen",
        error_code: str = "429",
        retry_after_seconds: int = 60,
    ) -> dict:
        """Fallback to local LLM (rate limited). Publishes to brain.voice.fallback.local

        Lady announces switch to local mode automatically!

        Example:
            voice_fallback_local "Rate limit hit" "karen" "429" 60
        """
        publisher = get_voice_publisher()
        result = publisher.publish_fallback_local(
            reason=reason,
            lady=lady,
            error_code=error_code,
            retry_after_seconds=retry_after_seconds,
        )

        if result.get("success"):
            # Also announce it locally
            try:
                voice_name, rate, _ = VOICE_LADIES.get(
                    lady, ("Karen", 165, "Australia")
                )
                subprocess.run(
                    [
                        "say",
                        "-v",
                        voice_name,
                        "-r",
                        str(rate),
                        "I'm switching to local mode. Be right back!",
                    ],
                    timeout=10,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except:
                pass

            return {
                "status": "✅ Fallback Activated",
                "lady": lady,
                "error_code": error_code,
                "retry_after_seconds": retry_after_seconds,
                "announcement": "Lady announced switch to local mode",
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.FALLBACK_LOCAL,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    # =====================================================================
    # VOICE QUEUE MANAGEMENT
    # =====================================================================

    @mcp.tool()
    def voice_queue_added(
        lady: str,
        text: str,
        voice_name: str = "",
        region: str = "",
        queue_position: int = 0,
        queue_length_after: int = 0,
    ) -> dict:
        """Add item to voice queue. Publishes to brain.voice.queue.added

        Example:
            voice_queue_added "tingting" "Hello there!" "" "China" 0 1
        """
        publisher = get_voice_publisher()
        result = publisher.publish_queue_added(
            lady=lady,
            text=text,
            voice_name=voice_name,
            region=region,
            queue_position=queue_position,
            queue_length_after=queue_length_after,
        )

        if result.get("success"):
            return {
                "status": "✅ Added to Queue",
                "lady": lady,
                "queue_position": result.get("queue_position"),
                "queue_length_after": result.get("queue_length_after"),
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.QUEUE_ADDED,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    @mcp.tool()
    def voice_queue_speaking(
        lady: str,
        text: str,
        voice_name: str = "",
        region: str = "",
        queue_remaining: int = 0,
    ) -> dict:
        """Lady is now speaking from queue. Publishes to brain.voice.queue.speaking

        Example:
            voice_queue_speaking "tingting" "Hello there!" "" "China" 0
        """
        publisher = get_voice_publisher()
        result = publisher.publish_queue_speaking(
            lady=lady,
            text=text,
            voice_name=voice_name,
            region=region,
            queue_remaining=queue_remaining,
        )

        if result.get("success"):
            return {
                "status": "✅ Speaking",
                "lady": lady,
                "queue_remaining": result.get("queue_remaining"),
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.QUEUE_SPEAKING,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    @mcp.tool()
    def voice_queue_empty(
        total_processed: int = 0, total_duration_seconds: float = 0.0
    ) -> dict:
        """Voice queue is now empty. Publishes to brain.voice.queue.empty

        Example:
            voice_queue_empty 5 45.3
        """
        publisher = get_voice_publisher()
        result = publisher.publish_queue_empty(
            total_processed=total_processed,
            total_duration_seconds=total_duration_seconds,
        )

        if result.get("success"):
            return {
                "status": "✅ Queue Empty",
                "total_processed": result.get("total_processed"),
                "total_duration_seconds": result.get("total_duration_seconds"),
                "event_id": result.get("event_id"),
                "topic_name": VoiceTopics.QUEUE_EMPTY,
            }
        else:
            return {"status": "❌ Failed", "error": result.get("error")}

    # =====================================================================
    # DOCUMENTATION TOOLS
    # =====================================================================

    @mcp.tool()
    def voice_topics_list() -> str:
        """List all ENHANCED v2 voice event topics and their schemas.

        Features:
        - Conversation lifecycle (started, turn, ended)
        - Cross-lady communication (introductions, reactions)
        - Mood synchronization (all ladies sync)
        - Turn-taking (prevent overlapping speech)
        - Error fallback (graceful degradation)
        - Voice queue management
        """
        output = """🎤 **Voice Topics - ENHANCED**

**NEW EVENT CATEGORIES:**

1️⃣ **CONVERSATION LIFECYCLE**
   - `brain.voice.conversation.started` - Conversation begins
   - `brain.voice.conversation.turn` - Lady takes her turn
   - `brain.voice.conversation.ended` - Conversation finishes
   
   **Schema:**
   ```json
   {
     "conversation_id": "uuid",
     "ladies": ["karen", "moira"],
     "topic": "standup",
     "turn_number": 1,
     "speaker": "karen",
     "text": "Let's discuss...",
     "timestamp": "2024-01-15T10:30:00Z"
   }
   ```

2️⃣ **CROSS-LADY COMMUNICATION**
   - `brain.voice.ladies.introduced` - New lady joins
   - `brain.voice.ladies.reaction` - Lady reacts to another
   
   **Schema:**
   ```json
   {
     "from_lady": "moira",
     "to_lady": "karen",
     "reaction_text": "That sounds good!",
     "emotion": "agreement",
     "timestamp": "2024-01-15T10:30:05Z"
   }
   ```

3️⃣ **MOOD SYNCHRONIZATION**
   - `brain.voice.mood.changed` - All ladies sync mood
   
   **Schema:**
   ```json
   {
     "mood": "calm",
     "reason": "spa_time",
     "ladies_synced": ["karen", "moira", "kyoko"],
     "previous_mood": "working",
     "timestamp": "2024-01-15T10:30:10Z"
   }
   ```

4️⃣ **TURN-TAKING (Prevent Speech Overlap)**
   - `brain.voice.turn.requested` - Request to speak
   - `brain.voice.turn.granted` - Turn granted
   - `brain.voice.turn.released` - Turn released
   
   **Schema:**
   ```json
   {
     "lady": "kyoko",
     "request_id": "uuid",
     "priority": 0,
     "duration_seconds": 30.0,
     "timestamp": "2024-01-15T10:30:15Z"
   }
   ```

5️⃣ **ERROR HANDLING & FALLBACK**
   - `brain.voice.fallback.local` - Rate limit fallback
   
   **Schema:**
   ```json
   {
     "lady": "karen",
     "error_code": "429",
     "reason": "Rate limit hit",
     "retry_after_seconds": 60,
     "announcement": "I'm switching to local mode...",
     "timestamp": "2024-01-15T10:30:20Z"
   }
   ```

6️⃣ **VOICE QUEUE MANAGEMENT**
   - `brain.voice.queue.added` - Item added to queue
   - `brain.voice.queue.speaking` - Lady is speaking
   - `brain.voice.queue.empty` - Queue is empty
   
   **Schema:**
   ```json
   {
     "lady": "tingting",
     "text": "Hello there!",
     "queue_position": 0,
     "queue_length_after": 1,
     "timestamp": "2024-01-15T10:30:25Z"
   }
   ```

**AVAILABLE LADIES:**
- Australia: karen
- Japan: kyoko
- China: tingting
- Hong Kong: sinji
- Vietnam: linh
- Thailand: kanya
- Korea: yuna
- Indonesia: dewi, sari, wayan
- Ireland: moira
- Poland: zosia
- England: flo, shelley

**MOODS:**
- `calm` - Relaxed and peaceful
- `working` - Professional and focused
- `party` - Energetic and excited
- `focused` - Intense concentration
- `bali_spa` - All ladies calm together
- `creative` - Brainstorming mode

**EMOTIONS (for reactions):**
- `agreement` - Lady agrees
- `disagreement` - Lady disagrees
- `question` - Lady has a question
- `excitement` - Lady is excited
- `support` - Lady supports another

**PUBLISHING TOOLS:**
✅ voice_conversation_started(ladies, topic)
✅ voice_conversation_turn(lady, text)
✅ voice_conversation_ended(ladies, total_turns, duration)
✅ voice_lady_introduced(lady, voice_name, region)
✅ voice_lady_reaction(from_lady, to_lady, reaction_text, emotion)
✅ voice_mood_changed(mood, reason, ladies)
✅ voice_turn_requested(lady, priority, reason)
✅ voice_turn_granted(lady, request_id, granted_by, duration)
✅ voice_turn_released(lady, request_id, reason, duration_held)
✅ voice_fallback_local(reason, lady, error_code, retry_after)
✅ voice_queue_added(lady, text, voice_name, region, position, length)
✅ voice_queue_speaking(lady, text, voice_name, region, remaining)
✅ voice_queue_empty(total_processed, total_duration)

**COMPLETE EXAMPLE WORKFLOW:**

```
# Start conversation
voice_conversation_started ["karen", "moira"] "standup"

# Karen takes first turn
voice_turn_granted "karen"
voice_conversation_turn "karen" "Let's discuss the sprint..."

# Karen releases turn
voice_turn_released "karen" "finished"

# Moira requests turn
voice_turn_requested "moira"
voice_turn_granted "moira"
voice_conversation_turn "moira" "I agree, let's focus on..."

# All ladies sync mood
voice_mood_changed "focused" "sprint_time"

# Moira reacts to Karen
voice_lady_reaction "moira" "karen" "Let's discuss..." "Great idea!" "agreement"

# End conversation
voice_conversation_ended ["karen", "moira"] 2 45.5 "completed"

# Empty queue
voice_queue_empty 4 125.3
```
"""
        return output


if __name__ == "__main__":
    print("🧠 Event Bus MCP Server (FastMCP) with ENHANCED voice support starting...")
    mcp.run()
