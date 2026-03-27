# SPDX-License-Identifier: Apache-2.0
"""Tests for Redis Voice Summary feature."""

# Import the module
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Skip voice integration tests on CI - no audio device available
CI_SKIP = pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
    reason="Voice tests require audio device - skip on CI",
)

sys.path.insert(0, "/Users/joe/brain/agentic-brain/src")

from agentic_brain.voice.redis_summary import (
    RedisSummary,
    RedisVoiceSummary,
)


class TestRedisSummary:
    """Tests for RedisSummary dataclass."""

    def test_default_values(self):
        """Summary has sensible defaults."""
        summary = RedisSummary()
        assert summary.connected is False
        assert summary.queue_length == 0
        assert summary.recent_events == 0
        assert summary.error == ""

    def test_with_values(self):
        """Summary stores values correctly."""
        summary = RedisSummary(
            connected=True,
            queue_length=5,
            recent_events=42,
            last_event_type="voice_played",
        )
        assert summary.connected is True
        assert summary.queue_length == 5
        assert summary.recent_events == 42
        assert summary.last_event_type == "voice_played"


class TestRedisVoiceSummary:
    """Tests for RedisVoiceSummary class."""

    def test_init_default_url(self):
        """Uses default Redis URL."""
        summary = RedisVoiceSummary()
        assert "redis://" in summary.redis_url

    def test_init_custom_url(self):
        """Accepts custom Redis URL."""
        summary = RedisVoiceSummary(redis_url="redis://custom:6379/1")
        assert summary.redis_url == "redis://custom:6379/1"

    def test_format_summary_disconnected(self):
        """Formats disconnected state."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(connected=False, error="Connection refused")
        )
        assert "not connected" in result.lower()
        assert "Connection refused" in result

    def test_format_summary_empty_queue(self):
        """Formats empty queue state."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(connected=True, queue_length=0)
        )
        assert "empty" in result.lower()
        assert "caught up" in result.lower()

    def test_format_summary_with_messages(self):
        """Formats queue with messages."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(connected=True, queue_length=5)
        )
        assert "5" in result
        assert "messages" in result.lower()

    def test_format_summary_with_events(self):
        """Formats event information."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(
                connected=True,
                queue_length=0,
                recent_events=10,
                last_event_type="voice_played",
            )
        )
        assert "10" in result
        assert "events" in result.lower()
        assert "voice played" in result.lower()

    def test_format_summary_recent_event(self):
        """Formats recent event time correctly."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(
                connected=True,
                queue_length=0,
                recent_events=1,
                last_event_type="test",
                last_event_time=datetime.now() - timedelta(seconds=30),
            )
        )
        assert "just now" in result.lower()

    def test_format_summary_old_event(self):
        """Formats older event time correctly."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(
                connected=True,
                queue_length=0,
                recent_events=1,
                last_event_type="test",
                last_event_time=datetime.now() - timedelta(minutes=30),
            )
        )
        assert "30 minutes ago" in result.lower()

    def test_format_summary_with_memory(self):
        """Includes memory usage."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(connected=True, queue_length=0, memory_usage="2.5MB")
        )
        assert "2.5MB" in result
        assert "memory" in result.lower()

    def test_format_summary_with_uptime(self):
        """Includes uptime."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(connected=True, queue_length=0, uptime="5 hours 30 minutes")
        )
        assert "5 hours" in result
        assert "30 minutes" in result


class TestRedisVoiceSummaryAsync:
    """Async tests for Redis operations."""

    @pytest.mark.asyncio
    async def test_connect_no_redis(self):
        """Handles missing Redis gracefully."""
        with patch.dict("sys.modules", {"redis.asyncio": None}):
            # Reload to pick up the patched import
            summary = RedisVoiceSummary()
            # Should not crash even without Redis
            assert summary._redis is None

    @pytest.mark.asyncio
    async def test_get_summary_not_connected(self):
        """Returns error summary when not connected."""
        summary = RedisVoiceSummary(redis_url="redis://nonexistent:9999/0")
        result = await summary.get_summary()
        assert result.connected is False or result.error != ""

    @CI_SKIP
    @pytest.mark.asyncio
    async def test_speak_summary_calls_resilient_voice(self):
        """Speak summary uses ResilientVoice."""
        summary = RedisVoiceSummary()

        with patch.object(summary, "get_summary", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = RedisSummary(connected=True, queue_length=0)

            with patch(
                "agentic_brain.voice.redis_summary.ResilientVoice.speak",
                new_callable=AsyncMock,
            ) as mock_speak:
                mock_speak.return_value = True
                await summary.speak_summary()

                mock_speak.assert_called_once()
                assert "Karen" in str(mock_speak.call_args)


class TestAccessibility:
    """Accessibility-focused tests."""

    def test_summary_text_no_jargon(self):
        """Summary text avoids technical jargon."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(connected=True, queue_length=3, recent_events=10)
        )

        # Should use human-friendly language
        assert "what's happening" in result.lower() or "brain" in result.lower()
        # Should not use technical terms
        assert "redis" not in result.lower()
        assert "llen" not in result.lower()

    def test_summary_text_speakable(self):
        """Summary text is suitable for TTS."""
        summary = RedisVoiceSummary()
        result = summary._format_summary_text(
            RedisSummary(
                connected=True,
                queue_length=5,
                recent_events=10,
                uptime="2 hours 30 minutes",
            )
        )

        # No special characters that TTS might mispronounce
        assert "{" not in result
        assert "}" not in result
        assert "[" not in result
        assert "]" not in result

        # Numbers should be speakable
        assert "5" in result or "five" in result.lower()
