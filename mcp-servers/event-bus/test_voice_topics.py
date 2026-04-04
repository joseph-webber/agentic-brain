#!/usr/bin/env python3
"""
Voice Event System Tests
========================

Tests for the comprehensive voice event system:
- VoiceEventPublisher
- VoiceEventSubscriber
- Event schemas and validation
- Integration with event bus
"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.expanduser('~/brain'))
sys.path.insert(0, os.path.expanduser('~/brain/mcp-servers/event-bus'))

from voice_topics import (
    VoiceTopics,
    VoiceEventPublisher,
    VoiceEventSubscriber,
    MoodChangeEvent,
    LadySpeakingEvent,
    ConversationEvent,
    FleetStatusEvent,
    validate_voice_event,
    get_event_schema,
    VOICE_EVENT_SCHEMAS
)


class MockEventBus:
    """Mock event bus for testing"""
    def __init__(self):
        self.events = []
        self.handlers = {}
    
    def emit(self, topic, event):
        """Emit event to topic"""
        self.events.append({
            'topic': topic,
            'event': event,
            'timestamp': datetime.now().isoformat()
        })
        
        # Call registered handlers
        if topic in self.handlers:
            for handler in self.handlers[topic]:
                handler(event)
        
        return True
    
    def on(self, topic, handler):
        """Register event handler"""
        if topic not in self.handlers:
            self.handlers[topic] = []
        self.handlers[topic].append(handler)
    
    def subscribe(self, topic):
        """Subscribe to topic"""
        pass


def test_voice_topics():
    """Test VoiceTopics registry"""
    print("\n=== Testing VoiceTopics Registry ===")
    
    topics = VoiceTopics.all()
    print(f"✓ Got {len(topics)} topics")
    assert len(topics) > 0, "Should have topics"
    
    # Test specific topics
    assert VoiceTopics.MOOD in topics
    assert VoiceTopics.LADY_SPEAKING in topics
    assert VoiceTopics.CONVERSATION in topics
    assert VoiceTopics.FLEET_STATUS in topics
    print(f"✓ All expected topics present: {', '.join(topics[:3])}...")
    
    # Test descriptions
    desc = VoiceTopics.get_description(VoiceTopics.MOOD)
    assert "calm" in desc.lower()
    print(f"✓ Got description: {desc}")


def test_event_schemas():
    """Test event schema definitions"""
    print("\n=== Testing Event Schemas ===")
    
    # Check all schemas are defined
    schemas = VOICE_EVENT_SCHEMAS
    print(f"✓ Got {len(schemas)} schemas")
    
    # Test mood schema
    mood_schema = get_event_schema("mood_change")
    assert mood_schema["properties"]["mood"]["enum"] == ["calm", "working", "party"]
    print(f"✓ Mood schema valid: {mood_schema['properties']['mood']}")
    
    # Test validation
    valid, error = validate_voice_event("mood_change", {
        "timestamp": datetime.now().isoformat(),
        "source": "test",
        "event_id": "test-123",
        "mood": "working"
    })
    assert valid, f"Should be valid: {error}"
    print(f"✓ Valid mood change event passes validation")
    
    # Test invalid data
    valid, error = validate_voice_event("mood_change", {
        "timestamp": datetime.now().isoformat(),
        "source": "test"
    })
    assert not valid, "Should be invalid"
    assert "event_id" in error or "mood" in error
    print(f"✓ Invalid event rejected: {error}")


def test_event_dataclasses():
    """Test event dataclass definitions"""
    print("\n=== Testing Event Dataclasses ===")
    
    # Test MoodChangeEvent
    mood_event = MoodChangeEvent(mood="working", reason="Standup meeting")
    assert mood_event.mood == "working"
    assert mood_event.validate()
    event_dict = mood_event.to_dict()
    assert "timestamp" in event_dict
    assert "event_id" in event_dict
    print(f"✓ MoodChangeEvent created: {mood_event.mood}")
    
    # Test LadySpeakingEvent
    lady_event = LadySpeakingEvent(
        lady="karen",
        text="Hello Joseph!",
        voice_name="Karen",
        region="Australia"
    )
    assert lady_event.validate()
    assert len(lady_event.to_json()) > 0
    print(f"✓ LadySpeakingEvent created: {lady_event.lady} speaking")
    
    # Test ConversationEvent
    conv_event = ConversationEvent(
        ladies=["karen", "moira"],
        topic="standup",
        participants=2
    )
    assert conv_event.validate()
    assert conv_event.participants == 2
    print(f"✓ ConversationEvent created: {len(conv_event.ladies)} ladies")
    
    # Test FleetStatusEvent
    fleet_event = FleetStatusEvent(
        message="All agents online",
        announcement_type="info",
        fleet_status="active"
    )
    assert fleet_event.validate()
    assert fleet_event.announcement_type == "info"
    print(f"✓ FleetStatusEvent created: {fleet_event.message}")


def test_voice_publisher():
    """Test VoiceEventPublisher"""
    print("\n=== Testing VoiceEventPublisher ===")
    
    bus = MockEventBus()
    publisher = VoiceEventPublisher(bus)
    
    # Test publish_mood_change
    result = publisher.publish_mood_change("working", "Standup time")
    assert result["success"]
    assert result["mood"] == "working"
    assert len(bus.events) == 1
    print(f"✓ Mood change published: {bus.events[0]['topic']}")
    
    # Test publish_lady_speaking
    result = publisher.publish_lady_speaking("karen", "Hello Joseph!", "Karen", "Australia")
    assert result["success"]
    assert result["lady"] == "karen"
    assert len(bus.events) == 2
    print(f"✓ Lady speaking event published: {bus.events[1]['event']['lady']}")
    
    # Test publish_lady_finished
    result = publisher.publish_lady_finished("karen", success=True)
    assert result["success"]
    assert len(bus.events) == 3
    print(f"✓ Lady finished event published")
    
    # Test publish_queue_update
    result = publisher.publish_queue_update(queue_length=3, current_lady="moira", processing=True)
    assert result["success"]
    assert result["queue_length"] == 3
    assert len(bus.events) == 4
    print(f"✓ Queue status published: length={result['queue_length']}")
    
    # Test publish_conversation_event
    result = publisher.publish_conversation_event(
        ["karen", "moira", "flo"],
        "daily standup"
    )
    assert result["success"]
    assert result["participants"] == 3
    assert len(bus.events) == 5
    print(f"✓ Conversation event published: {result['participants']} participants")
    
    # Test publish_fleet_announcement
    result = publisher.publish_fleet_announcement(
        "All agents online",
        announcement_type="info"
    )
    assert result["success"]
    assert len(bus.events) == 6
    print(f"✓ Fleet announcement published: {result['type']}")
    
    # Test stats
    stats = publisher.get_stats()
    assert stats["events_published"] == 6
    print(f"✓ Publisher stats: {stats['events_published']} events published")
    
    # Test invalid mood
    result = publisher.publish_mood_change("invalid_mood")
    assert not result["success"]
    assert "Invalid mood" in result["error"]
    print(f"✓ Invalid mood rejected: {result['error']}")


def test_voice_subscriber():
    """Test VoiceEventSubscriber"""
    print("\n=== Testing VoiceEventSubscriber ===")
    
    bus = MockEventBus()
    subscriber = VoiceEventSubscriber(bus)
    
    # Track callbacks
    callbacks_fired = {"mood": 0, "lady": 0, "any": 0}
    
    def on_mood(event):
        callbacks_fired["mood"] += 1
    
    def on_lady(event):
        callbacks_fired["lady"] += 1
    
    def on_any(event):
        callbacks_fired["any"] += 1
    
    # Register callbacks
    subscriber.on_mood_change(on_mood)
    subscriber.on_lady_speaking(on_lady)
    subscriber.on_any_voice_event(on_any)
    
    # Publish events
    publisher = VoiceEventPublisher(bus)
    publisher.publish_mood_change("working")
    
    # Check callbacks fired
    assert callbacks_fired["mood"] >= 1, "Mood callback should fire"
    print(f"✓ Mood callback fired: {callbacks_fired['mood']} times")
    
    publisher.publish_lady_speaking("karen", "Hello")
    assert callbacks_fired["lady"] >= 1, "Lady callback should fire"
    print(f"✓ Lady callback fired: {callbacks_fired['lady']} times")
    
    # Test subscription
    result = subscriber.subscribe_all()
    assert result["status"] == "subscribed"
    assert len(result["topics"]) > 0
    print(f"✓ Subscribed to {result['subscribed_topics']} topics")
    
    # Test stats
    stats = subscriber.get_stats()
    assert stats["events_received"] >= 0
    assert len(stats["topics_subscribed"]) > 0
    print(f"✓ Subscriber stats: {stats['events_received']} events received")


def test_event_replay():
    """Test event replay capability"""
    print("\n=== Testing Event Replay ===")
    
    bus = MockEventBus()
    publisher = VoiceEventPublisher(bus)
    
    # Publish several events
    publisher.publish_mood_change("working")
    publisher.publish_lady_speaking("karen", "Hello")
    publisher.publish_conversation_event(["karen", "moira"], "standup")
    
    # Simulate replay
    replay_count = 0
    for event_data in bus.events:
        replay_count += 1
        event = event_data["event"]
        topic = event_data["topic"]
        
        # Validate event structure
        assert "timestamp" in event
        assert "event_id" in event
        assert "source" in event
    
    assert replay_count == 3
    print(f"✓ Replayed {replay_count} events with valid structure")


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("🎤 Voice Event System Test Suite")
    print("="*60)
    
    try:
        test_voice_topics()
        test_event_schemas()
        test_event_dataclasses()
        test_voice_publisher()
        test_voice_subscriber()
        test_event_replay()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
