#!/usr/bin/env python3
"""
Test Suite for Enhanced Voice Integration v2
==============================================

Tests all new voice event functionality:
- Conversation lifecycle
- Cross-lady communication
- Mood synchronization
- Turn-taking management
- Error fallback handling
- Voice queue management
"""

import unittest
import sys
import os
from datetime import datetime
from typing import Dict, List, Any

# Add paths
sys.path.insert(0, os.path.expanduser('~/brain'))
sys.path.insert(0, os.path.dirname(__file__))

# Mock event bus for testing
class MockEventBus:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []
        self.subscribers: Dict[str, List] = {}
    
    def emit(self, topic: str, event: dict) -> bool:
        """Mock emit - stores event"""
        self.events.append({
            'topic': topic,
            'event': event,
            'timestamp': datetime.now().isoformat()
        })
        return True
    
    def subscribe(self, topic: str, callback):
        """Mock subscribe"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []
        self.subscribers[topic].append(callback)
        return True
    
    def get_events_by_topic(self, topic: str) -> List[dict]:
        """Get all events for a topic"""
        return [e for e in self.events if e['topic'] == topic]
    
    def clear(self):
        """Clear all events"""
        self.events = []
        self.subscribers = {}


# Import voice topics
from voice_topics_v2 import (
    VoiceTopicsV2, VoiceEventPublisherV2, VoiceEventSubscriberV2,
    ConversationStartedEvent, ConversationTurnEvent, ConversationEndedEvent,
    LadyIntroducedEvent, LadyReactionEvent, MoodChangedEvent,
    TurnRequestedEvent, TurnGrantedEvent, TurnReleasedEvent,
    FallbackLocalEvent, QueueAddedEvent, QueueSpeakingEvent, QueueEmptyEvent,
    validate_voice_event
)


# ============================================================================
# TEST CASES
# ============================================================================

class TestConversationLifecycle(unittest.TestCase):
    """Test conversation lifecycle events"""
    
    def setUp(self):
        self.bus = MockEventBus()
        self.publisher = VoiceEventPublisherV2(self.bus)
    
    def test_conversation_started(self):
        """Test conversation started event"""
        result = self.publisher.publish_conversation_started(
            ladies=["karen", "moira"],
            topic="standup"
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['ladies'], ["karen", "moira"])
        self.assertEqual(result['topic'], "standup")
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.CONVERSATION_STARTED)
        self.assertEqual(len(events), 1)
        
        event_data = events[0]['event']
        self.assertEqual(event_data['ladies'], ["karen", "moira"])
        self.assertEqual(event_data['topic'], "standup")
    
    def test_conversation_turn(self):
        """Test conversation turn event"""
        # Start conversation first
        conv_result = self.publisher.publish_conversation_started(
            ladies=["karen", "moira"]
        )
        
        # Karen takes turn
        result = self.publisher.publish_conversation_turn(
            lady="karen",
            text="Let's discuss the sprint backlog",
            turn_number=1
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "karen")
        self.assertIn("Let's discuss", result['text_preview'])
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.CONVERSATION_TURN)
        self.assertEqual(len(events), 1)
        
        event_data = events[0]['event']
        self.assertEqual(event_data['lady'], "karen")
        self.assertEqual(event_data['turn_number'], 1)
    
    def test_conversation_ended(self):
        """Test conversation ended event"""
        # Start and conduct conversation
        self.publisher.publish_conversation_started(
            ladies=["karen", "moira"]
        )
        self.publisher.publish_conversation_turn("karen", "Let's start", turn_number=1)
        self.publisher.publish_conversation_turn("moira", "I agree", turn_number=2)
        
        # End conversation
        result = self.publisher.publish_conversation_ended(
            ladies=["karen", "moira"],
            total_turns=2,
            duration_seconds=45.5,
            reason="completed"
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_turns'], 2)
        self.assertEqual(result['duration_seconds'], 45.5)
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.CONVERSATION_ENDED)
        self.assertEqual(len(events), 1)


class TestLadyCommunication(unittest.TestCase):
    """Test cross-lady communication"""
    
    def setUp(self):
        self.bus = MockEventBus()
        self.publisher = VoiceEventPublisherV2(self.bus)
    
    def test_lady_introduced(self):
        """Test lady introduction event"""
        result = self.publisher.publish_lady_introduced(
            lady="iris",
            voice_name="Iris",
            region="San Francisco",
            greeting="Hello Joseph!"
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "iris")
        self.assertEqual(result['region'], "San Francisco")
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.LADY_INTRODUCED)
        self.assertEqual(len(events), 1)
        
        event_data = events[0]['event']
        self.assertEqual(event_data['lady'], "iris")
        self.assertEqual(event_data['greeting'], "Hello Joseph!")
    
    def test_lady_reaction(self):
        """Test lady reaction event"""
        result = self.publisher.publish_lady_reaction(
            from_lady="moira",
            to_lady="karen",
            original_text="Let's discuss the sprint",
            reaction_text="That sounds great!",
            emotion="agreement"
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['from_lady'], "moira")
        self.assertEqual(result['to_lady'], "karen")
        self.assertEqual(result['emotion'], "agreement")
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.LADY_REACTION)
        self.assertEqual(len(events), 1)
        
        event_data = events[0]['event']
        self.assertEqual(event_data['emotion'], "agreement")


class TestMoodSync(unittest.TestCase):
    """Test mood synchronization"""
    
    def setUp(self):
        self.bus = MockEventBus()
        self.publisher = VoiceEventPublisherV2(self.bus)
    
    def test_mood_changed(self):
        """Test mood changed event"""
        result = self.publisher.publish_mood_changed(
            mood="calm",
            reason="spa_time",
            ladies=["karen", "moira", "kyoko"]
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['mood'], "calm")
        self.assertEqual(result['previous_mood'], "calm")  # Initial mood
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.MOOD_CHANGED)
        self.assertEqual(len(events), 1)
        
        event_data = events[0]['event']
        self.assertEqual(event_data['mood'], "calm")
        self.assertEqual(event_data['reason'], "spa_time")
        self.assertEqual(len(event_data['ladies_synced']), 3)
    
    def test_mood_changed_sequence(self):
        """Test sequence of mood changes"""
        # Start with calm
        self.publisher.publish_mood_changed("calm")
        
        # Change to working
        result = self.publisher.publish_mood_changed("working", reason="standup")
        self.assertEqual(result['previous_mood'], "calm")
        self.assertEqual(result['mood'], "working")
        
        # Change to party
        result = self.publisher.publish_mood_changed("party", reason="sprint_complete")
        self.assertEqual(result['previous_mood'], "working")
        self.assertEqual(result['mood'], "party")
        
        # Verify all events
        events = self.bus.get_events_by_topic(VoiceTopicsV2.MOOD_CHANGED)
        self.assertEqual(len(events), 3)


class TestTurnTaking(unittest.TestCase):
    """Test turn-taking events to prevent speech overlap"""
    
    def setUp(self):
        self.bus = MockEventBus()
        self.publisher = VoiceEventPublisherV2(self.bus)
    
    def test_turn_requested(self):
        """Test turn requested event"""
        result = self.publisher.publish_turn_requested(
            lady="kyoko",
            priority=0,
            reason="wants_to_comment"
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "kyoko")
        self.assertEqual(result['priority'], 0)
        self.assertIn('request_id', result)
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.TURN_REQUESTED)
        self.assertEqual(len(events), 1)
    
    def test_turn_granted(self):
        """Test turn granted event"""
        # First request turn
        request_result = self.publisher.publish_turn_requested("kyoko")
        request_id = request_result['request_id']
        
        # Grant turn
        result = self.publisher.publish_turn_granted(
            lady="kyoko",
            request_id=request_id,
            granted_by="karen",
            duration_seconds=30.0
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "kyoko")
        self.assertEqual(result['request_id'], request_id)
        self.assertEqual(result['duration_seconds'], 30.0)
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.TURN_GRANTED)
        self.assertEqual(len(events), 1)
    
    def test_turn_released(self):
        """Test turn released event"""
        # Request and grant
        request_result = self.publisher.publish_turn_requested("kyoko")
        request_id = request_result['request_id']
        
        self.publisher.publish_turn_granted(
            lady="kyoko",
            request_id=request_id
        )
        
        # Release turn
        result = self.publisher.publish_turn_released(
            lady="kyoko",
            request_id=request_id,
            reason="finished",
            duration_held_seconds=25.5
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "kyoko")
        self.assertEqual(result['reason'], "finished")
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.TURN_RELEASED)
        self.assertEqual(len(events), 1)
    
    def test_turn_taking_sequence(self):
        """Test complete turn-taking sequence"""
        # Karen has turn
        karen_req = self.publisher.publish_turn_requested("karen", priority=1)
        self.publisher.publish_turn_granted("karen", karen_req['request_id'])
        
        # Kyoko requests higher priority
        kyoko_req = self.publisher.publish_turn_requested("kyoko", priority=2)
        
        # Karen releases
        self.publisher.publish_turn_released("karen", karen_req['request_id'], "interrupted")
        
        # Kyoko gets turn
        self.publisher.publish_turn_granted("kyoko", kyoko_req['request_id'])
        
        # Verify sequence
        req_events = self.bus.get_events_by_topic(VoiceTopicsV2.TURN_REQUESTED)
        grant_events = self.bus.get_events_by_topic(VoiceTopicsV2.TURN_GRANTED)
        release_events = self.bus.get_events_by_topic(VoiceTopicsV2.TURN_RELEASED)
        
        self.assertEqual(len(req_events), 2)
        self.assertEqual(len(grant_events), 2)
        self.assertEqual(len(release_events), 1)


class TestFallback(unittest.TestCase):
    """Test error handling and fallback"""
    
    def setUp(self):
        self.bus = MockEventBus()
        self.publisher = VoiceEventPublisherV2(self.bus)
    
    def test_fallback_local(self):
        """Test fallback to local LLM event"""
        result = self.publisher.publish_fallback_local(
            reason="Rate limit hit",
            lady="karen",
            error_code="429",
            retry_after_seconds=60
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "karen")
        self.assertEqual(result['retry_after_seconds'], 60)
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.FALLBACK_LOCAL)
        self.assertEqual(len(events), 1)
        
        event_data = events[0]['event']
        self.assertEqual(event_data['error_code'], "429")
        self.assertIn("local", event_data['announcement'])


class TestVoiceQueue(unittest.TestCase):
    """Test voice queue management"""
    
    def setUp(self):
        self.bus = MockEventBus()
        self.publisher = VoiceEventPublisherV2(self.bus)
    
    def test_queue_added(self):
        """Test queue added event"""
        result = self.publisher.publish_queue_added(
            lady="tingting",
            text="Hello Joseph!",
            voice_name="Tingting",
            region="China",
            queue_position=0,
            queue_length_after=1
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "tingting")
        self.assertEqual(result['queue_length_after'], 1)
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.QUEUE_ADDED)
        self.assertEqual(len(events), 1)
    
    def test_queue_speaking(self):
        """Test queue speaking event"""
        result = self.publisher.publish_queue_speaking(
            lady="tingting",
            text="Hello Joseph!",
            voice_name="Tingting",
            region="China",
            queue_remaining=0
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['lady'], "tingting")
        self.assertEqual(result['queue_remaining'], 0)
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.QUEUE_SPEAKING)
        self.assertEqual(len(events), 1)
    
    def test_queue_empty(self):
        """Test queue empty event"""
        result = self.publisher.publish_queue_empty(
            total_processed=5,
            total_duration_seconds=125.3
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['total_processed'], 5)
        self.assertEqual(result['total_duration_seconds'], 125.3)
        
        # Check event was emitted
        events = self.bus.get_events_by_topic(VoiceTopicsV2.QUEUE_EMPTY)
        self.assertEqual(len(events), 1)
    
    def test_queue_sequence(self):
        """Test complete queue sequence"""
        # Add multiple items
        self.publisher.publish_queue_added("karen", "First", queue_position=0, queue_length_after=1)
        self.publisher.publish_queue_added("moira", "Second", queue_position=1, queue_length_after=2)
        
        # Karen speaking
        self.publisher.publish_queue_speaking("karen", "First", queue_remaining=1)
        
        # Queue empty
        self.publisher.publish_queue_empty(total_processed=2, total_duration_seconds=45.0)
        
        # Verify sequence
        add_events = self.bus.get_events_by_topic(VoiceTopicsV2.QUEUE_ADDED)
        speak_events = self.bus.get_events_by_topic(VoiceTopicsV2.QUEUE_SPEAKING)
        empty_events = self.bus.get_events_by_topic(VoiceTopicsV2.QUEUE_EMPTY)
        
        self.assertEqual(len(add_events), 2)
        self.assertEqual(len(speak_events), 1)
        self.assertEqual(len(empty_events), 1)


class TestEventValidation(unittest.TestCase):
    """Test event validation"""
    
    def test_validate_conversation_started(self):
        """Test conversation started event validation"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_id": "123",
            "source": "voice-system",
            "ladies": ["karen", "moira"],
            "topic": "standup"
        }
        
        is_valid, msg = validate_voice_event(event, VoiceTopicsV2.CONVERSATION_STARTED)
        self.assertTrue(is_valid)
    
    def test_validate_missing_fields(self):
        """Test validation of event with missing fields"""
        event = {
            "ladies": ["karen"]
            # Missing timestamp, event_id, source
        }
        
        is_valid, msg = validate_voice_event(event, VoiceTopicsV2.CONVERSATION_STARTED)
        self.assertFalse(is_valid)
        self.assertIn("timestamp", msg)
    
    def test_validate_conversation_turn(self):
        """Test conversation turn validation"""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_id": "123",
            "source": "voice-system",
            "lady": "karen",
            "text": "Hello!"
        }
        
        is_valid, msg = validate_voice_event(event, VoiceTopicsV2.CONVERSATION_TURN)
        self.assertTrue(is_valid)


class TestTopicsRegistry(unittest.TestCase):
    """Test voice topics registry"""
    
    def test_all_topics(self):
        """Test getting all topics"""
        topics = VoiceTopicsV2.all()
        
        self.assertGreater(len(topics), 10)
        self.assertIn(VoiceTopicsV2.CONVERSATION_STARTED, topics)
        self.assertIn(VoiceTopicsV2.TURN_REQUESTED, topics)
        self.assertIn(VoiceTopicsV2.MOOD_CHANGED, topics)
    
    def test_topic_descriptions(self):
        """Test topic descriptions"""
        for topic in VoiceTopicsV2.all():
            description = VoiceTopicsV2.get_description(topic)
            self.assertIsNotNone(description)
            self.assertGreater(len(description), 0)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        self.bus = MockEventBus()
        self.publisher = VoiceEventPublisherV2(self.bus)
    
    def test_complete_standup_workflow(self):
        """Test complete standup meeting workflow"""
        # Start standup
        self.publisher.publish_conversation_started(
            ladies=["karen", "moira", "kyoko"],
            topic="standup"
        )
        
        # Sync mood to working
        self.publisher.publish_mood_changed("working", "standup_time", ["karen", "moira", "kyoko"])
        
        # Karen takes turn
        self.publisher.publish_turn_granted("karen")
        self.publisher.publish_conversation_turn("karen", "I worked on auth", turn_number=1)
        self.publisher.publish_turn_released("karen", reason="finished")
        
        # Moira requests and takes turn
        self.publisher.publish_turn_requested("moira")
        self.publisher.publish_turn_granted("moira")
        self.publisher.publish_conversation_turn("moira", "I fixed the UI bug", turn_number=2)
        self.publisher.publish_lady_reaction("kyoko", "moira", "I fixed the UI bug", "Nice work!", "agreement")
        self.publisher.publish_turn_released("moira")
        
        # Kyoko takes turn
        self.publisher.publish_turn_granted("kyoko")
        self.publisher.publish_conversation_turn("kyoko", "Blocked on deployment", turn_number=3)
        self.publisher.publish_turn_released("kyoko")
        
        # End standup
        self.publisher.publish_conversation_ended(
            ladies=["karen", "moira", "kyoko"],
            total_turns=3,
            duration_seconds=900.0,
            reason="completed"
        )
        
        # Verify all events were created
        self.assertEqual(len(self.bus.events), 14)
        
        # Verify specific events
        conv_events = self.bus.get_events_by_topic(VoiceTopicsV2.CONVERSATION_STARTED)
        self.assertEqual(len(conv_events), 1)
        
        turn_events = self.bus.get_events_by_topic(VoiceTopicsV2.CONVERSATION_TURN)
        self.assertEqual(len(turn_events), 3)
        
        reaction_events = self.bus.get_events_by_topic(VoiceTopicsV2.LADY_REACTION)
        self.assertEqual(len(reaction_events), 1)


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConversationLifecycle))
    suite.addTests(loader.loadTestsFromTestCase(TestLadyCommunication))
    suite.addTests(loader.loadTestsFromTestCase(TestMoodSync))
    suite.addTests(loader.loadTestsFromTestCase(TestTurnTaking))
    suite.addTests(loader.loadTestsFromTestCase(TestFallback))
    suite.addTests(loader.loadTestsFromTestCase(TestVoiceQueue))
    suite.addTests(loader.loadTestsFromTestCase(TestEventValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestTopicsRegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("🎤 ENHANCED VOICE INTEGRATION v2 - TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
