#!/usr/bin/env python3
"""
Brain Voice Event System - ENHANCED
===================================

Comprehensive voice event system for multi-lady conversations with:
- Conversation lifecycle events (started, turn, ended)
- Cross-lady communication and reactions
- Mood synchronization
- Turn-taking management
- Graceful fallback handling
- Voice queue management

Provides:
- VoiceTopics: Complete registry of all voice event topics
- VoiceEventPublisher: Enhanced publisher with conversation & turn-taking
- VoiceEventSubscriber: Subscribe with callbacks
- VoiceEvent schemas: Validated event structures

Voice Ladies:
  karen (Australia), kyoko (Japan), tingting (China), sinji (Hong Kong),
  linh (Vietnam), kanya (Thailand), yuna (Korea), dewi (Indonesia),
  sari (Indonesia), wayan (Indonesia), moira (Ireland), zosia (Poland),
  flo (England), shelley (England)

Example:
  publisher = VoiceEventPublisher(bus)
  
  # Start conversation
  publisher.publish_conversation_started(["karen", "moira"], "standup")
  
  # Lady takes turn
  publisher.publish_conversation_turn("karen", "Let's discuss the sprint...")
  
  # Lady responds to another
  publisher.publish_lady_reaction("moira", "karen", "That sounds good!")
  
  # Mood sync
  publisher.publish_mood_changed("calm", reason="spa_time")
  
  # Turn-taking
  publisher.publish_turn_requested("kyoko")
  publisher.publish_turn_granted("kyoko")
  
  # Fallback
  publisher.publish_fallback_local("Rate limit hit")
  
  # Queue
  publisher.publish_queue_event("added", lady="tingting", text="Hello!")
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
    """Enhanced brain voice event topics"""

    # =========================================================================
    # CONVERSATION LIFECYCLE EVENTS
    # =========================================================================
    CONVERSATION_STARTED = "brain.voice.conversation.started"
    CONVERSATION_TURN = "brain.voice.conversation.turn"
    CONVERSATION_ENDED = "brain.voice.conversation.ended"

    # =========================================================================
    # LADY INTRODUCTION AND REACTIONS
    # =========================================================================
    LADY_INTRODUCED = "brain.voice.ladies.introduced"  # New lady joins
    LADY_REACTION = "brain.voice.ladies.reaction"  # Lady reacts to another

    # =========================================================================
    # MOOD SYNCHRONIZATION
    # =========================================================================
    MOOD_CHANGED = "brain.voice.mood.changed"  # All ladies sync mood

    # =========================================================================
    # TURN-TAKING EVENTS
    # =========================================================================
    TURN_REQUESTED = "brain.voice.turn.requested"  # Request to speak
    TURN_GRANTED = "brain.voice.turn.granted"  # Granted turn
    TURN_RELEASED = "brain.voice.turn.released"  # Release turn

    # =========================================================================
    # ERROR HANDLING AND FALLBACK
    # =========================================================================
    FALLBACK_LOCAL = "brain.voice.fallback.local"  # Switch to local LLM

    # =========================================================================
    # VOICE QUEUE MANAGEMENT
    # =========================================================================
    QUEUE_ADDED = "brain.voice.queue.added"  # Item added to queue
    QUEUE_SPEAKING = "brain.voice.queue.speaking"  # Lady is speaking
    QUEUE_EMPTY = "brain.voice.queue.empty"  # Queue is empty

    # =========================================================================
    # LEGACY TOPICS (kept for compatibility)
    # =========================================================================
    MOOD = "brain.voice.mood"
    LADY_SPEAKING = "brain.voice.lady.speaking"
    LADY_FINISHED = "brain.voice.lady.finished"
    QUEUE_STATUS = "brain.voice.queue.status"
    CONVERSATION = "brain.voice.conversation"
    FLEET_STATUS = "brain.voice.fleet.status"
    INPUT = "brain.voice.input"
    RESPONSE = "brain.voice.response"
    LLM = "brain.voice.llm"

    @classmethod
    def all(cls) -> List[str]:
        """Get all voice topics"""
        return [
            # New v2 topics
            cls.CONVERSATION_STARTED,
            cls.CONVERSATION_TURN,
            cls.CONVERSATION_ENDED,
            cls.LADY_INTRODUCED,
            cls.LADY_REACTION,
            cls.MOOD_CHANGED,
            cls.TURN_REQUESTED,
            cls.TURN_GRANTED,
            cls.TURN_RELEASED,
            cls.FALLBACK_LOCAL,
            cls.QUEUE_ADDED,
            cls.QUEUE_SPEAKING,
            cls.QUEUE_EMPTY,
            # Legacy topics
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
            # New v2 topics
            cls.CONVERSATION_STARTED: "Multi-lady conversation started",
            cls.CONVERSATION_TURN: "Lady takes turn in conversation",
            cls.CONVERSATION_ENDED: "Conversation ended",
            cls.LADY_INTRODUCED: "New lady joins the team",
            cls.LADY_REACTION: "Lady reacts to what another said",
            cls.MOOD_CHANGED: "All ladies sync to same mood",
            cls.TURN_REQUESTED: "Lady requests speaking turn",
            cls.TURN_GRANTED: "Speaking turn granted to lady",
            cls.TURN_RELEASED: "Lady releases speaking turn",
            cls.FALLBACK_LOCAL: "Switch to local LLM (rate limit)",
            cls.QUEUE_ADDED: "Voice item added to queue",
            cls.QUEUE_SPEAKING: "Lady currently speaking",
            cls.QUEUE_EMPTY: "Voice queue is empty",
            # Legacy
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
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = "voice-system"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)


# =========================================================================
# CONVERSATION LIFECYCLE EVENTS
# =========================================================================


@dataclass
class ConversationStartedEvent(VoiceEventBase):
    """Conversation started event"""

    ladies: List[str] = field(default_factory=list)
    conversation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    speaker_order: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationTurnEvent(VoiceEventBase):
    """Lady takes a turn in conversation"""

    conversation_id: str = ""
    lady: str = ""
    text: str = ""
    voice_name: str = ""
    region: str = ""
    turn_number: int = 0
    duration_ms: int = 0


@dataclass
class ConversationEndedEvent(VoiceEventBase):
    """Conversation ended"""

    conversation_id: str = ""
    ladies: List[str] = field(default_factory=list)
    total_turns: int = 0
    duration_seconds: float = 0.0
    reason: str = ""  # "completed", "interrupted", "error"


# =========================================================================
# LADY INTRODUCTION AND REACTIONS
# =========================================================================


@dataclass
class LadyIntroducedEvent(VoiceEventBase):
    """New lady joins the team"""

    lady: str = ""
    voice_name: str = ""
    region: str = ""
    greeting: str = ""
    personality: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LadyReactionEvent(VoiceEventBase):
    """Lady reacts to what another lady said"""

    from_lady: str = ""
    to_lady: str = ""
    original_text: str = ""
    reaction_text: str = ""
    emotion: str = ""  # "agreement", "disagreement", "question", "excitement"
    reaction_duration_ms: int = 0


# =========================================================================
# MOOD SYNCHRONIZATION
# =========================================================================


@dataclass
class MoodChangedEvent(VoiceEventBase):
    """All ladies sync to same mood"""

    mood: str = ""  # "calm", "working", "party", "focused", "bali_spa"
    reason: str = ""
    previous_mood: str = ""
    ladies_synced: List[str] = field(default_factory=list)
    sync_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# =========================================================================
# TURN-TAKING EVENTS
# =========================================================================


@dataclass
class TurnRequestedEvent(VoiceEventBase):
    """Lady requests speaking turn"""

    lady: str = ""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    priority: int = 0  # 0=normal, 1=high, 2=critical
    reason: str = ""


@dataclass
class TurnGrantedEvent(VoiceEventBase):
    """Speaking turn granted to lady"""

    lady: str = ""
    request_id: str = ""
    granted_by: str = ""
    duration_seconds: float = 30.0


@dataclass
class TurnReleasedEvent(VoiceEventBase):
    """Lady releases speaking turn"""

    lady: str = ""
    request_id: str = ""
    reason: str = ""  # "finished", "interrupted", "timeout"
    duration_held_seconds: float = 0.0


# =========================================================================
# ERROR HANDLING AND FALLBACK
# =========================================================================


@dataclass
class FallbackLocalEvent(VoiceEventBase):
    """Switch to local LLM (rate limited)"""

    reason: str = ""
    lady: str = "karen"
    voice_name: str = "Karen"
    announcement: str = ""
    error_code: str = ""
    retry_after_seconds: int = 0


# =========================================================================
# VOICE QUEUE MANAGEMENT
# =========================================================================


@dataclass
class QueueAddedEvent(VoiceEventBase):
    """Voice item added to queue"""

    lady: str = ""
    text: str = ""
    voice_name: str = ""
    region: str = ""
    queue_position: int = 0
    queue_length_after: int = 0


@dataclass
class QueueSpeakingEvent(VoiceEventBase):
    """Lady is currently speaking"""

    lady: str = ""
    text: str = ""
    voice_name: str = ""
    region: str = ""
    queue_remaining: int = 0
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class QueueEmptyEvent(VoiceEventBase):
    """Voice queue is empty"""

    total_processed: int = 0
    total_duration_seconds: float = 0.0


# ============================================================================
# Voice Event Publisher v2
# ============================================================================


class VoiceEventPublisher:
    """Enhanced voice event publisher with all v2 events"""

    def __init__(self, bus):
        """Initialize publisher with event bus"""
        self.bus = bus
        self.current_conversation_id = None
        self.current_mood = "calm"

    # =====================================================================
    # CONVERSATION LIFECYCLE EVENTS
    # =====================================================================

    def publish_conversation_started(
        self,
        ladies: List[str],
        topic: str = "",
        speaker_order: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Publish conversation started event"""
        conversation_id = str(uuid.uuid4())
        self.current_conversation_id = conversation_id

        event = ConversationStartedEvent(
            ladies=ladies,
            conversation_id=conversation_id,
            topic=topic,
            speaker_order=speaker_order or ladies,
            context=context or {},
        )

        success = self.bus.emit(VoiceTopics.CONVERSATION_STARTED, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "conversation_id": conversation_id,
            "ladies": ladies,
            "topic": topic,
        }

    def publish_conversation_turn(
        self,
        lady: str,
        text: str,
        voice_name: str = "",
        region: str = "",
        turn_number: int = 0,
        duration_ms: int = 0,
    ) -> dict:
        """Publish conversation turn event"""
        event = ConversationTurnEvent(
            conversation_id=self.current_conversation_id or str(uuid.uuid4()),
            lady=lady,
            text=text,
            voice_name=voice_name,
            region=region,
            turn_number=turn_number,
            duration_ms=duration_ms,
        )

        success = self.bus.emit(VoiceTopics.CONVERSATION_TURN, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "text_preview": text[:50] + "..." if len(text) > 50 else text,
        }

    def publish_conversation_ended(
        self,
        ladies: List[str],
        total_turns: int = 0,
        duration_seconds: float = 0.0,
        reason: str = "completed",
    ) -> dict:
        """Publish conversation ended event"""
        event = ConversationEndedEvent(
            conversation_id=self.current_conversation_id or str(uuid.uuid4()),
            ladies=ladies,
            total_turns=total_turns,
            duration_seconds=duration_seconds,
            reason=reason,
        )

        success = self.bus.emit(VoiceTopics.CONVERSATION_ENDED, event.to_dict())
        self.current_conversation_id = None

        return {
            "success": success,
            "event_id": event.event_id,
            "ladies": ladies,
            "total_turns": total_turns,
            "duration_seconds": duration_seconds,
        }

    # =====================================================================
    # LADY INTRODUCTION AND REACTIONS
    # =====================================================================

    def publish_lady_introduced(
        self,
        lady: str,
        voice_name: str = "",
        region: str = "",
        greeting: str = "",
        personality: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Publish lady introduced event"""
        event = LadyIntroducedEvent(
            lady=lady,
            voice_name=voice_name,
            region=region,
            greeting=greeting,
            personality=personality or {},
        )

        success = self.bus.emit(VoiceTopics.LADY_INTRODUCED, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "region": region,
        }

    def publish_lady_reaction(
        self,
        from_lady: str,
        to_lady: str,
        original_text: str = "",
        reaction_text: str = "",
        emotion: str = "",
        reaction_duration_ms: int = 0,
    ) -> dict:
        """Publish lady reaction event"""
        event = LadyReactionEvent(
            from_lady=from_lady,
            to_lady=to_lady,
            original_text=original_text,
            reaction_text=reaction_text,
            emotion=emotion,
            reaction_duration_ms=reaction_duration_ms,
        )

        success = self.bus.emit(VoiceTopics.LADY_REACTION, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "from_lady": from_lady,
            "to_lady": to_lady,
            "emotion": emotion,
        }

    # =====================================================================
    # MOOD SYNCHRONIZATION
    # =====================================================================

    def publish_mood_changed(
        self, mood: str, reason: str = "", ladies: Optional[List[str]] = None
    ) -> dict:
        """Publish mood changed event - all ladies sync!"""
        event = MoodChangedEvent(
            mood=mood,
            reason=reason,
            previous_mood=self.current_mood,
            ladies_synced=ladies or [],
            sync_timestamp=datetime.now().isoformat(),
        )

        self.current_mood = mood
        success = self.bus.emit(VoiceTopics.MOOD_CHANGED, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "mood": mood,
            "previous_mood": event.previous_mood,
            "ladies_synced": event.ladies_synced,
        }

    # =====================================================================
    # TURN-TAKING EVENTS
    # =====================================================================

    def publish_turn_requested(
        self, lady: str, priority: int = 0, reason: str = ""
    ) -> dict:
        """Publish turn requested event"""
        request_id = str(uuid.uuid4())
        event = TurnRequestedEvent(
            lady=lady, request_id=request_id, priority=priority, reason=reason
        )

        success = self.bus.emit(VoiceTopics.TURN_REQUESTED, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "request_id": request_id,
            "lady": lady,
            "priority": priority,
        }

    def publish_turn_granted(
        self,
        lady: str,
        request_id: str = "",
        granted_by: str = "moderator",
        duration_seconds: float = 30.0,
    ) -> dict:
        """Publish turn granted event"""
        event = TurnGrantedEvent(
            lady=lady,
            request_id=request_id or str(uuid.uuid4()),
            granted_by=granted_by,
            duration_seconds=duration_seconds,
        )

        success = self.bus.emit(VoiceTopics.TURN_GRANTED, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "request_id": event.request_id,
            "duration_seconds": duration_seconds,
        }

    def publish_turn_released(
        self,
        lady: str,
        request_id: str = "",
        reason: str = "finished",
        duration_held_seconds: float = 0.0,
    ) -> dict:
        """Publish turn released event"""
        event = TurnReleasedEvent(
            lady=lady,
            request_id=request_id or str(uuid.uuid4()),
            reason=reason,
            duration_held_seconds=duration_held_seconds,
        )

        success = self.bus.emit(VoiceTopics.TURN_RELEASED, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "reason": reason,
        }

    # =====================================================================
    # ERROR HANDLING AND FALLBACK
    # =====================================================================

    def publish_fallback_local(
        self,
        reason: str = "",
        lady: str = "karen",
        voice_name: str = "Karen",
        error_code: str = "429",
        retry_after_seconds: int = 60,
    ) -> dict:
        """Publish fallback to local LLM event"""
        announcement = f"I'm switching to local mode - be right back!"

        event = FallbackLocalEvent(
            reason=reason,
            lady=lady,
            voice_name=voice_name,
            announcement=announcement,
            error_code=error_code,
            retry_after_seconds=retry_after_seconds,
        )

        success = self.bus.emit(VoiceTopics.FALLBACK_LOCAL, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "reason": reason,
            "error_code": error_code,
            "retry_after_seconds": retry_after_seconds,
        }

    # =====================================================================
    # VOICE QUEUE MANAGEMENT
    # =====================================================================

    def publish_queue_added(
        self,
        lady: str,
        text: str,
        voice_name: str = "",
        region: str = "",
        queue_position: int = 0,
        queue_length_after: int = 0,
    ) -> dict:
        """Publish queue added event"""
        event = QueueAddedEvent(
            lady=lady,
            text=text,
            voice_name=voice_name,
            region=region,
            queue_position=queue_position,
            queue_length_after=queue_length_after,
        )

        success = self.bus.emit(VoiceTopics.QUEUE_ADDED, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "queue_position": queue_position,
            "queue_length_after": queue_length_after,
        }

    def publish_queue_speaking(
        self,
        lady: str,
        text: str,
        voice_name: str = "",
        region: str = "",
        queue_remaining: int = 0,
    ) -> dict:
        """Publish queue speaking event"""
        event = QueueSpeakingEvent(
            lady=lady,
            text=text,
            voice_name=voice_name,
            region=region,
            queue_remaining=queue_remaining,
            started_at=datetime.now().isoformat(),
        )

        success = self.bus.emit(VoiceTopics.QUEUE_SPEAKING, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "lady": lady,
            "queue_remaining": queue_remaining,
        }

    def publish_queue_empty(
        self, total_processed: int = 0, total_duration_seconds: float = 0.0
    ) -> dict:
        """Publish queue empty event"""
        event = QueueEmptyEvent(
            total_processed=total_processed,
            total_duration_seconds=total_duration_seconds,
        )

        success = self.bus.emit(VoiceTopics.QUEUE_EMPTY, event.to_dict())

        return {
            "success": success,
            "event_id": event.event_id,
            "total_processed": total_processed,
            "total_duration_seconds": total_duration_seconds,
        }


# ============================================================================
# Voice Event Subscriber v2
# ============================================================================


class VoiceEventSubscriber:
    """Subscribe to voice events with callbacks"""

    def __init__(self, bus):
        """Initialize subscriber with event bus"""
        self.bus = bus
        self.handlers = {}

    def subscribe(self, topic: str, callback: Callable):
        """Subscribe to a topic"""
        if topic not in self.handlers:
            self.handlers[topic] = []

        self.handlers[topic].append(callback)
        self.bus.subscribe(topic, callback)

        return {"success": True, "topic": topic, "handlers": len(self.handlers[topic])}

    def unsubscribe(self, topic: str, callback: Callable):
        """Unsubscribe from a topic"""
        if topic in self.handlers and callback in self.handlers[topic]:
            self.handlers[topic].remove(callback)
            return {"success": True, "topic": topic}

        return {"success": False, "error": "Handler not found"}


# ============================================================================
# Event Validation
# ============================================================================


def validate_voice_event(event: dict, topic: str) -> tuple[bool, str]:
    """Validate a voice event against its schema"""
    try:
        required_fields = ["timestamp", "event_id", "source"]
        for field in required_fields:
            if field not in event:
                return False, f"Missing required field: {field}"

        # Topic-specific validation
        if topic == VoiceTopics.CONVERSATION_STARTED:
            if "ladies" not in event or not isinstance(event["ladies"], list):
                return False, "ladies must be a non-empty list"

        elif topic == VoiceTopics.CONVERSATION_TURN:
            if not event.get("lady"):
                return False, "lady field required"
            if not event.get("text"):
                return False, "text field required"

        elif topic == VoiceTopics.TURN_REQUESTED:
            if not event.get("lady"):
                return False, "lady field required"

        return True, "Valid"

    except Exception as e:
        return False, f"Validation error: {str(e)}"


if __name__ == "__main__":
    # Print all topics and their descriptions
    print("🎤 Voice Topics v2 - Complete Registry")
    print("=" * 60)

    for topic in VoiceTopics.all():
        description = VoiceTopics.get_description(topic)
        print(f"\n📌 {topic}")
        print(f"   {description}")
