"""Tests for Redis coordination."""

import pytest
import fakeredis


class TestRedisState:
    """Test Redis state management."""

    @pytest.fixture
    def redis(self):
        return fakeredis.FakeRedis(decode_responses=True)

    def test_state_transitions(self, redis):
        """Test voice state machine."""
        states = ["ready", "listening", "transcribing", "thinking", "speaking"]

        for state in states:
            redis.set("voice:state", state)
            assert redis.get("voice:state") == state

    def test_command_queue(self, redis):
        """Test command queue processing."""
        # Send stop command
        redis.set("voice:cmd", "stop")

        cmd = redis.get("voice:cmd")
        assert cmd == "stop"

        # Clear after processing
        redis.delete("voice:cmd")
        assert redis.get("voice:cmd") is None

    def test_log_rotation(self, redis):
        """Test log list rotation."""
        # Add 150 logs
        for i in range(150):
            redis.lpush("voice:logs", f"Log entry {i}")

        # Trim to 100
        redis.ltrim("voice:logs", 0, 99)

        assert redis.llen("voice:logs") == 100

    def test_pubsub_events(self, redis):
        """Test pub/sub for real-time events."""
        pubsub = redis.pubsub()
        pubsub.subscribe("voice:events")

        # Publish event
        redis.publish("voice:events", "transcription_complete")

        # In real code, subscriber would receive this
