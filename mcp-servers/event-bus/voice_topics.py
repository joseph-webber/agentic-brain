#!/usr/bin/env python3
"""
Brain Voice Event System
========================

Comprehensive voice event system for multi-lady conversations and mood management.

Provides:
- VoiceTopics: Central registry of all voice-related topics
- VoiceEventPublisher: Publish voice events to the event bus
- VoiceEventSubscriber: Subscribe to voice events with callbacks
- VoiceEvent schemas: Validated event structures with timestamps

Voice Ladies:
  karen (Australia), kyoko (Japan), tingting (China), sinji (Hong Kong),
  linh (Vietnam), kanya (Thailand), yuna (Korea), dewi (Indonesia),
  sari (Indonesia), wayan (Indonesia), moira (Ireland), zosia (Poland),
  flo (England), shelley (England)

Example:
  publisher = VoiceEventPublisher(bus)
  
  # Mood changes
  publisher.publish_mood_change("working")
  
  # Lady speaking
  publisher.publish_lady_speaking("karen", "Hello Joseph!")
  
  # Multi-lady conversation
  publisher.publish_conversation_event({
    "ladies": ["karen", "moira"],
    "topic": "standup",
    "participants": 2
  })
"""

import json
import uuid
from datetime import datetime
from typing import Callable, Dict, Optional, Any, List
from dataclasses import dataclass, asdict, field
from enum import Enum


# ============================================================================
# Voice Topics Registry
# ============================================================================

class VoiceTopics:
    """Standard brain voice event topics"""
    
    # Core voice topics
    MOOD = 'brain.voice.mood'                    # Mood changes: calm, working, party
    LADY_SPEAKING = 'brain.voice.lady.speaking' # Which lady is currently speaking
    LADY_FINISHED = 'brain.voice.lady.finished' # Lady finished speaking
    
    # Queue and status
    QUEUE_STATUS = 'brain.voice.queue.status'    # Voice queue state updates
    CONVERSATION = 'brain.voice.conversation'    # Multi-lady conversation events
    FLEET_STATUS = 'brain.voice.fleet.status'    # Agent announcements and fleet status
    
    # Legacy (kept for compatibility)
    INPUT = 'brain.voice.input'                  # User voice input events
    RESPONSE = 'brain.voice.response'            # Lady voice responses
    LLM = 'brain.voice.llm'                      # LLM requests for voice responses
    
    @classmethod
    def all(cls) -> List[str]:
        """Get all voice topics"""
        return [
            cls.MOOD,
            cls.LADY_SPEAKING,
            cls.LADY_FINISHED,
            cls.QUEUE_STATUS,
            cls.CONVERSATION,
            cls.FLEET_STATUS,
            cls.INPUT,
            cls.RESPONSE,
            cls.LLM,
        ]
    
    @classmethod
    def get_description(cls, topic: str) -> str:
        """Get human-readable description of a topic"""
        descriptions = {
            cls.MOOD: "Current mood state (calm, working, party)",
            cls.LADY_SPEAKING: "Which lady is currently speaking",
            cls.LADY_FINISHED: "Lady finished speaking notification",
            cls.QUEUE_STATUS: "Voice queue state and processing status",
            cls.CONVERSATION: "Multi-lady conversation events",
            cls.FLEET_STATUS: "Agent fleet announcements and status",
            cls.INPUT: "User voice input events",
            cls.RESPONSE: "Lady voice responses to user",
            cls.LLM: "LLM requests for voice responses",
        }
        return descriptions.get(topic, "Unknown topic")


# ============================================================================
# Voice Event Data Classes and Schemas
# ============================================================================

@dataclass
class VoiceEventBase:
    """Base class for all voice events"""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "voice-system"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


@dataclass
class MoodChangeEvent(VoiceEventBase):
    """Event when mood changes"""
    mood: str = "calm"  # calm, working, party
    reason: str = ""
    previous_mood: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate mood is valid"""
        valid_moods = ["calm", "working", "party"]
        return self.mood in valid_moods


@dataclass
class LadySpeakingEvent(VoiceEventBase):
    """Event when lady starts speaking"""
    lady: str = ""
    text: str = ""
    voice_name: str = ""
    region: str = ""
    duration_ms: Optional[int] = None
    
    def validate(self) -> bool:
        """Validate lady and text are present"""
        return bool(self.lady and self.text)


@dataclass
class LadyFinishedEvent(VoiceEventBase):
    """Event when lady finishes speaking"""
    lady: str = ""
    duration_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate lady is present"""
        return bool(self.lady)


@dataclass
class QueueStatusEvent(VoiceEventBase):
    """Event for queue state updates"""
    queue_length: int = 0
    pending_ladies: List[str] = field(default_factory=list)
    current_lady: Optional[str] = None
    processing: bool = False
    queue_items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ConversationEvent(VoiceEventBase):
    """Event for multi-lady conversations"""
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ladies: List[str] = field(default_factory=list)
    topic: str = ""
    participants: int = 0
    speaker_order: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def validate(self) -> bool:
        """Validate conversation has ladies and topic"""
        return bool(self.ladies and self.topic)


@dataclass
class FleetStatusEvent(VoiceEventBase):
    """Event for agent fleet announcements"""
    message: str = ""
    agent_name: Optional[str] = None
    fleet_status: str = ""  # active, paused, error
    announcement_type: str = "info"  # info, warning, error, critical
    affected_agents: List[str] = field(default_factory=list)
    
    def validate(self) -> bool:
        """Validate message is present"""
        return bool(self.message)


@dataclass
class VoiceResponseEvent(VoiceEventBase):
    """Legacy voice response event"""
    lady: str = ""
    message: str = ""
    voice_name: str = ""
    region: str = ""
    request_id: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate lady and message are present"""
        return bool(self.lady and self.message)


# ============================================================================
# Voice Event Publisher
# ============================================================================

class VoiceEventPublisher:
    """
    Publish voice events to the event bus.
    
    Handles all voice-related event publishing with validation and timestamps.
    """
    
    def __init__(self, bus):
        """
        Initialize publisher with event bus connection.
        
        Args:
            bus: BrainEventBus instance
        """
        self.bus = bus
        self.event_count = 0
    
    def publish_mood_change(self, mood: str, reason: str = "", previous_mood: Optional[str] = None) -> Dict[str, Any]:
        """
        Publish mood change event.
        
        Args:
            mood: New mood (calm, working, party)
            reason: Optional reason for mood change
            previous_mood: Optional previous mood
            
        Returns:
            Event details
        """
        event = MoodChangeEvent(
            mood=mood,
            reason=reason,
            previous_mood=previous_mood
        )
        
        if not event.validate():
            return {
                "success": False,
                "error": f"Invalid mood: {mood}. Must be one of: calm, working, party"
            }
        
        success = self.bus.emit(VoiceTopics.MOOD, event.to_dict())
        self.event_count += 1
        
        return {
            "success": success,
            "event_id": event.event_id,
            "mood": mood,
            "topic": VoiceTopics.MOOD,
            "timestamp": event.timestamp
        }
    
    def publish_lady_speaking(self, lady: str, text: str, voice_name: str = "", region: str = "", duration_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Publish lady speaking event.
        
        Args:
            lady: Lady identifier (karen, moira, etc.)
            text: The text being spoken
            voice_name: Full voice name
            region: Voice region
            duration_ms: Optional duration in milliseconds
            
        Returns:
            Event details
        """
        event = LadySpeakingEvent(
            lady=lady,
            text=text,
            voice_name=voice_name,
            region=region,
            duration_ms=duration_ms
        )
        
        if not event.validate():
            return {
                "success": False,
                "error": f"Lady and text are required"
            }
        
        success = self.bus.emit(VoiceTopics.LADY_SPEAKING, event.to_dict())
        self.event_count += 1
        
        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "text_length": len(text),
            "topic": VoiceTopics.LADY_SPEAKING,
            "timestamp": event.timestamp
        }
    
    def publish_lady_finished(self, lady: str, duration_ms: Optional[int] = None, success: bool = True, error_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Publish lady finished speaking event.
        
        Args:
            lady: Lady identifier
            duration_ms: Optional duration in milliseconds
            success: Whether speaking was successful
            error_message: Optional error message if failed
            
        Returns:
            Event details
        """
        event = LadyFinishedEvent(
            lady=lady,
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        
        if not event.validate():
            return {
                "success": False,
                "error": f"Lady is required"
            }
        
        success_result = self.bus.emit(VoiceTopics.LADY_FINISHED, event.to_dict())
        self.event_count += 1
        
        return {
            "success": success_result,
            "event_id": event.event_id,
            "lady": lady,
            "success": success,
            "topic": VoiceTopics.LADY_FINISHED,
            "timestamp": event.timestamp
        }
    
    def publish_queue_update(self, queue_length: int = 0, pending_ladies: List[str] = None, current_lady: Optional[str] = None, processing: bool = False, queue_items: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Publish queue status update.
        
        Args:
            queue_length: Number of items in queue
            pending_ladies: List of ladies waiting to speak
            current_lady: Currently speaking lady
            processing: Whether queue is being processed
            queue_items: Detailed queue items
            
        Returns:
            Event details
        """
        event = QueueStatusEvent(
            queue_length=queue_length,
            pending_ladies=pending_ladies or [],
            current_lady=current_lady,
            processing=processing,
            queue_items=queue_items or []
        )
        
        success = self.bus.emit(VoiceTopics.QUEUE_STATUS, event.to_dict())
        self.event_count += 1
        
        return {
            "success": success,
            "event_id": event.event_id,
            "queue_length": queue_length,
            "current_lady": current_lady,
            "processing": processing,
            "topic": VoiceTopics.QUEUE_STATUS,
            "timestamp": event.timestamp
        }
    
    def publish_conversation_event(self, ladies: List[str], topic: str, speaker_order: List[str] = None, context: Dict[str, Any] = None, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Publish multi-lady conversation event.
        
        Args:
            ladies: List of lady identifiers
            topic: Conversation topic
            speaker_order: Optional order of speakers
            context: Optional conversation context
            conversation_id: Optional existing conversation ID
            
        Returns:
            Event details
        """
        event = ConversationEvent(
            conversation_id=conversation_id or str(uuid.uuid4()),
            ladies=ladies,
            topic=topic,
            participants=len(ladies),
            speaker_order=speaker_order or ladies,
            context=context or {}
        )
        
        if not event.validate():
            return {
                "success": False,
                "error": f"Ladies and topic are required"
            }
        
        success = self.bus.emit(VoiceTopics.CONVERSATION, event.to_dict())
        self.event_count += 1
        
        return {
            "success": success,
            "event_id": event.event_id,
            "conversation_id": event.conversation_id,
            "ladies": ladies,
            "topic": topic,
            "participants": len(ladies),
            "topic": VoiceTopics.CONVERSATION,
            "timestamp": event.timestamp
        }
    
    def publish_fleet_announcement(self, message: str, announcement_type: str = "info", agent_name: Optional[str] = None, fleet_status: str = "", affected_agents: List[str] = None) -> Dict[str, Any]:
        """
        Publish fleet/agent announcement.
        
        Args:
            message: Announcement message
            announcement_type: Type of announcement (info, warning, error, critical)
            agent_name: Optional specific agent
            fleet_status: Fleet status (active, paused, error)
            affected_agents: Optional list of affected agents
            
        Returns:
            Event details
        """
        event = FleetStatusEvent(
            message=message,
            agent_name=agent_name,
            fleet_status=fleet_status,
            announcement_type=announcement_type,
            affected_agents=affected_agents or []
        )
        
        if not event.validate():
            return {
                "success": False,
                "error": f"Message is required"
            }
        
        success = self.bus.emit(VoiceTopics.FLEET_STATUS, event.to_dict())
        self.event_count += 1
        
        return {
            "success": success,
            "event_id": event.event_id,
            "message_length": len(message),
            "type": announcement_type,
            "topic": VoiceTopics.FLEET_STATUS,
            "timestamp": event.timestamp
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get publisher statistics"""
        return {
            "events_published": self.event_count,
            "bus_connected": self.bus is not None
        }


# ============================================================================
# Voice Event Subscriber
# ============================================================================

class VoiceEventSubscriber:
    """
    Subscribe to voice events with callbacks.
    
    Handles subscribing to voice topics and executing callbacks when events arrive.
    """
    
    def __init__(self, bus):
        """
        Initialize subscriber with event bus connection.
        
        Args:
            bus: BrainEventBus instance
        """
        self.bus = bus
        self.callbacks = {}
        self.event_count = 0
    
    def on_mood_change(self, callback: Callable) -> None:
        """
        Register callback for mood change events.
        
        Args:
            callback: Function to call when mood changes
        """
        if VoiceTopics.MOOD not in self.callbacks:
            self.callbacks[VoiceTopics.MOOD] = []
        self.callbacks[VoiceTopics.MOOD].append(callback)
        
        # Register with bus
        if hasattr(self.bus, 'on'):
            self.bus.on(VoiceTopics.MOOD, self._make_handler(callback, VoiceTopics.MOOD))
    
    def on_lady_speaking(self, callback: Callable) -> None:
        """
        Register callback for lady speaking events.
        
        Args:
            callback: Function to call when lady speaks
        """
        if VoiceTopics.LADY_SPEAKING not in self.callbacks:
            self.callbacks[VoiceTopics.LADY_SPEAKING] = []
        self.callbacks[VoiceTopics.LADY_SPEAKING].append(callback)
        
        if hasattr(self.bus, 'on'):
            self.bus.on(VoiceTopics.LADY_SPEAKING, self._make_handler(callback, VoiceTopics.LADY_SPEAKING))
    
    def on_lady_finished(self, callback: Callable) -> None:
        """
        Register callback for lady finished events.
        
        Args:
            callback: Function to call when lady finishes
        """
        if VoiceTopics.LADY_FINISHED not in self.callbacks:
            self.callbacks[VoiceTopics.LADY_FINISHED] = []
        self.callbacks[VoiceTopics.LADY_FINISHED].append(callback)
        
        if hasattr(self.bus, 'on'):
            self.bus.on(VoiceTopics.LADY_FINISHED, self._make_handler(callback, VoiceTopics.LADY_FINISHED))
    
    def on_queue_status(self, callback: Callable) -> None:
        """
        Register callback for queue status events.
        
        Args:
            callback: Function to call on queue updates
        """
        if VoiceTopics.QUEUE_STATUS not in self.callbacks:
            self.callbacks[VoiceTopics.QUEUE_STATUS] = []
        self.callbacks[VoiceTopics.QUEUE_STATUS].append(callback)
        
        if hasattr(self.bus, 'on'):
            self.bus.on(VoiceTopics.QUEUE_STATUS, self._make_handler(callback, VoiceTopics.QUEUE_STATUS))
    
    def on_conversation(self, callback: Callable) -> None:
        """
        Register callback for conversation events.
        
        Args:
            callback: Function to call on conversation events
        """
        if VoiceTopics.CONVERSATION not in self.callbacks:
            self.callbacks[VoiceTopics.CONVERSATION] = []
        self.callbacks[VoiceTopics.CONVERSATION].append(callback)
        
        if hasattr(self.bus, 'on'):
            self.bus.on(VoiceTopics.CONVERSATION, self._make_handler(callback, VoiceTopics.CONVERSATION))
    
    def on_fleet_status(self, callback: Callable) -> None:
        """
        Register callback for fleet status events.
        
        Args:
            callback: Function to call on fleet announcements
        """
        if VoiceTopics.FLEET_STATUS not in self.callbacks:
            self.callbacks[VoiceTopics.FLEET_STATUS] = []
        self.callbacks[VoiceTopics.FLEET_STATUS].append(callback)
        
        if hasattr(self.bus, 'on'):
            self.bus.on(VoiceTopics.FLEET_STATUS, self._make_handler(callback, VoiceTopics.FLEET_STATUS))
    
    def on_any_voice_event(self, callback: Callable) -> None:
        """
        Register callback for any voice event.
        
        Args:
            callback: Function to call for any voice event
        """
        for topic in VoiceTopics.all():
            if topic not in self.callbacks:
                self.callbacks[topic] = []
            self.callbacks[topic].append(callback)
            
            if hasattr(self.bus, 'on'):
                self.bus.on(topic, self._make_handler(callback, topic))
    
    def subscribe_all(self) -> Dict[str, Any]:
        """
        Subscribe to all voice topics.
        
        Returns:
            Subscription summary
        """
        topics = VoiceTopics.all()
        for topic in topics:
            if hasattr(self.bus, 'subscribe'):
                self.bus.subscribe(topic)
        
        return {
            "subscribed_topics": len(topics),
            "topics": topics,
            "status": "subscribed"
        }
    
    def _make_handler(self, callback: Callable, topic: str) -> Callable:
        """Create a handler that wraps the callback"""
        def handler(event):
            self.event_count += 1
            try:
                callback(event)
            except Exception as e:
                print(f"Error in voice event callback for {topic}: {e}")
        
        return handler
    
    def get_stats(self) -> Dict[str, Any]:
        """Get subscriber statistics"""
        return {
            "events_received": self.event_count,
            "callbacks_registered": len(self.callbacks),
            "topics_subscribed": list(self.callbacks.keys()),
            "bus_connected": self.bus is not None
        }


# ============================================================================
# Voice Event Schemas (for validation and documentation)
# ============================================================================

VOICE_EVENT_SCHEMAS = {
    "mood_change": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "string", "format": "date-time"},
            "source": {"type": "string"},
            "event_id": {"type": "string", "format": "uuid"},
            "mood": {"type": "string", "enum": ["calm", "working", "party"]},
            "reason": {"type": "string"},
            "previous_mood": {"type": ["string", "null"]}
        },
        "required": ["timestamp", "source", "event_id", "mood"]
    },
    "lady_speaking": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "string", "format": "date-time"},
            "source": {"type": "string"},
            "event_id": {"type": "string", "format": "uuid"},
            "lady": {"type": "string"},
            "text": {"type": "string"},
            "voice_name": {"type": "string"},
            "region": {"type": "string"},
            "duration_ms": {"type": ["integer", "null"]}
        },
        "required": ["timestamp", "source", "event_id", "lady", "text"]
    },
    "lady_finished": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "string", "format": "date-time"},
            "source": {"type": "string"},
            "event_id": {"type": "string", "format": "uuid"},
            "lady": {"type": "string"},
            "duration_ms": {"type": ["integer", "null"]},
            "success": {"type": "boolean"},
            "error_message": {"type": ["string", "null"]}
        },
        "required": ["timestamp", "source", "event_id", "lady"]
    },
    "queue_status": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "string", "format": "date-time"},
            "source": {"type": "string"},
            "event_id": {"type": "string", "format": "uuid"},
            "queue_length": {"type": "integer"},
            "pending_ladies": {"type": "array", "items": {"type": "string"}},
            "current_lady": {"type": ["string", "null"]},
            "processing": {"type": "boolean"},
            "queue_items": {"type": "array"}
        },
        "required": ["timestamp", "source", "event_id", "queue_length"]
    },
    "conversation": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "string", "format": "date-time"},
            "source": {"type": "string"},
            "event_id": {"type": "string", "format": "uuid"},
            "conversation_id": {"type": "string", "format": "uuid"},
            "ladies": {"type": "array", "items": {"type": "string"}},
            "topic": {"type": "string"},
            "participants": {"type": "integer"},
            "speaker_order": {"type": "array", "items": {"type": "string"}},
            "context": {"type": "object"}
        },
        "required": ["timestamp", "source", "event_id", "conversation_id", "ladies", "topic"]
    },
    "fleet_status": {
        "type": "object",
        "properties": {
            "timestamp": {"type": "string", "format": "date-time"},
            "source": {"type": "string"},
            "event_id": {"type": "string", "format": "uuid"},
            "message": {"type": "string"},
            "agent_name": {"type": ["string", "null"]},
            "fleet_status": {"type": "string"},
            "announcement_type": {"type": "string", "enum": ["info", "warning", "error", "critical"]},
            "affected_agents": {"type": "array", "items": {"type": "string"}}
        },
        "required": ["timestamp", "source", "event_id", "message"]
    }
}


def get_event_schema(event_type: str) -> Dict[str, Any]:
    """Get JSON schema for a voice event type"""
    return VOICE_EVENT_SCHEMAS.get(event_type, {})


def validate_voice_event(event_type: str, event_data: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate voice event data against schema.
    
    Returns:
        (is_valid, error_message)
    """
    schema = get_event_schema(event_type)
    if not schema:
        return False, f"Unknown event type: {event_type}"
    
    # Check required fields
    required = schema.get("required", [])
    for field in required:
        if field not in event_data:
            return False, f"Missing required field: {field}"
    
    return True, ""
