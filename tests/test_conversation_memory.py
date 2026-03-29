# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for conversation memory and repeat detection.

Covers:
  - ConversationMemory recording, retrieval, search
  - Redis backend + in-memory fallback
  - RepeatDetector fuzzy matching
  - Thread safety
  - Edge cases
"""

from __future__ import annotations

import json
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.voice.conversation_memory import (
    ConversationMemory,
    Utterance,
    get_conversation_memory,
    reset_conversation_memory,
)
from agentic_brain.voice.repeat_detector import (
    RepeatAction,
    RepeatDetector,
    RepeatResult,
    get_repeat_detector,
    reset_repeat_detector,
)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def mem():
    """Fresh in-memory ConversationMemory (no Redis)."""
    return ConversationMemory(use_redis=False, ttl_seconds=3600)


@pytest.fixture()
def detector():
    """Fresh RepeatDetector with default settings."""
    return RepeatDetector(threshold=0.8, window=20, action=RepeatAction.WARN)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Ensure singletons are fresh for each test."""
    reset_conversation_memory()
    reset_repeat_detector()
    yield
    reset_conversation_memory()
    reset_repeat_detector()


# ═══════════════════════════════════════════════════════════════════
# ConversationMemory tests
# ═══════════════════════════════════════════════════════════════════


class TestUtterance:
    """Test the Utterance dataclass."""

    def test_create_utterance(self):
        utt = Utterance(lady="karen", text="Hello Joseph")
        assert utt.lady == "karen"
        assert utt.text == "Hello Joseph"
        assert utt.timestamp > 0

    def test_utterance_to_dict(self):
        utt = Utterance(lady="moira", text="Top of the morning", timestamp=100.0)
        d = utt.to_dict()
        assert d["lady"] == "moira"
        assert d["text"] == "Top of the morning"
        assert d["timestamp"] == 100.0

    def test_utterance_from_dict(self):
        data = {"lady": "kyoko", "text": "Konnichiwa", "timestamp": 200.0}
        utt = Utterance.from_dict(data)
        assert utt.lady == "kyoko"
        assert utt.text == "Konnichiwa"
        assert utt.timestamp == 200.0

    def test_utterance_age(self):
        utt = Utterance(lady="karen", text="test", timestamp=time.time() - 10)
        assert utt.age_seconds() >= 9.0


class TestConversationMemoryRecord:
    """Test recording utterances."""

    def test_record_single(self, mem: ConversationMemory):
        utt = mem.record("karen", "Good morning")
        assert utt.lady == "karen"
        assert utt.text == "Good morning"

    def test_record_multiple_ladies(self, mem: ConversationMemory):
        mem.record("karen", "Hello")
        mem.record("moira", "Hi there")
        mem.record("kyoko", "Konnichiwa")
        assert mem.count() == 3
        assert mem.count("karen") == 1
        assert mem.count("moira") == 1

    def test_record_preserves_order(self, mem: ConversationMemory):
        for i in range(5):
            mem.record("karen", f"Message {i}")
        recent = mem.get_recent("karen", count=5)
        assert [u.text for u in recent] == [f"Message {i}" for i in range(5)]

    def test_record_with_voice_and_rate(self, mem: ConversationMemory):
        utt = mem.record("karen", "Test", voice="Karen (Premium)", rate=160)
        assert utt.voice == "Karen (Premium)"
        assert utt.rate == 160

    def test_record_custom_timestamp(self, mem: ConversationMemory):
        utt = mem.record("karen", "Old message", timestamp=1000.0)
        assert utt.timestamp == 1000.0


class TestConversationMemoryRetrieval:
    """Test retrieving utterances."""

    def test_get_recent_empty(self, mem: ConversationMemory):
        assert mem.get_recent("karen") == []

    def test_get_recent_by_lady(self, mem: ConversationMemory):
        mem.record("karen", "A")
        mem.record("moira", "B")
        mem.record("karen", "C")
        recent = mem.get_recent("karen", count=10)
        assert len(recent) == 2
        assert recent[0].text == "A"
        assert recent[1].text == "C"

    def test_get_recent_global(self, mem: ConversationMemory):
        mem.record("karen", "First")
        mem.record("moira", "Second")
        mem.record("kyoko", "Third")
        recent = mem.get_recent(count=10)
        assert len(recent) == 3
        assert recent[0].text == "First"
        assert recent[2].text == "Third"

    def test_get_recent_respects_count(self, mem: ConversationMemory):
        for i in range(20):
            mem.record("karen", f"Msg {i}")
        recent = mem.get_recent("karen", count=5)
        assert len(recent) == 5
        assert recent[-1].text == "Msg 19"

    def test_get_last(self, mem: ConversationMemory):
        mem.record("karen", "First")
        mem.record("moira", "Second")
        last = mem.get_last()
        assert last is not None
        assert last.text == "Second"

    def test_get_last_by_lady(self, mem: ConversationMemory):
        mem.record("karen", "Karen first")
        mem.record("moira", "Moira thing")
        mem.record("karen", "Karen second")
        last = mem.get_last("karen")
        assert last is not None
        assert last.text == "Karen second"

    def test_get_last_empty(self, mem: ConversationMemory):
        assert mem.get_last() is None
        assert mem.get_last("karen") is None


class TestConversationMemorySearch:
    """Test search functionality."""

    def test_search_basic(self, mem: ConversationMemory):
        mem.record("karen", "Working on JIRA ticket SD-1330")
        mem.record("moira", "The PR looks good")
        mem.record("karen", "JIRA comment posted")
        results = mem.search("JIRA")
        assert len(results) == 2

    def test_search_case_insensitive(self, mem: ConversationMemory):
        mem.record("karen", "Hello Joseph")
        results = mem.search("hello")
        assert len(results) == 1
        results = mem.search("HELLO")
        assert len(results) == 1

    def test_search_no_results(self, mem: ConversationMemory):
        mem.record("karen", "Hello")
        assert mem.search("Goodbye") == []

    def test_search_respects_limit(self, mem: ConversationMemory):
        for i in range(30):
            mem.record("karen", f"JIRA message {i}")
        results = mem.search("JIRA", limit=5)
        assert len(results) == 5


class TestConversationMemoryManagement:
    """Test count, clear, ladies list."""

    def test_get_ladies(self, mem: ConversationMemory):
        mem.record("karen", "Hi")
        mem.record("moira", "Hey")
        mem.record("kyoko", "Konnichi wa")
        ladies = mem.get_ladies()
        assert ladies == ["karen", "kyoko", "moira"]

    def test_clear_by_lady(self, mem: ConversationMemory):
        mem.record("karen", "A")
        mem.record("moira", "B")
        removed = mem.clear("karen")
        assert removed == 1
        assert mem.count("karen") == 0
        assert mem.count("moira") == 1

    def test_clear_all(self, mem: ConversationMemory):
        mem.record("karen", "A")
        mem.record("moira", "B")
        removed = mem.clear()
        assert removed == 2
        assert mem.count() == 0

    def test_health(self, mem: ConversationMemory):
        mem.record("karen", "Hi")
        h = mem.health()
        assert h["redis_available"] is False
        assert h["in_memory_count"] == 1
        assert "karen" in h["ladies"]


class TestConversationMemoryThreadSafety:
    """Verify thread safety under concurrent writes."""

    def test_concurrent_records(self, mem: ConversationMemory):
        errors: list = []

        def writer(lady: str, n: int):
            try:
                for i in range(n):
                    mem.record(lady, f"{lady} msg {i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=("karen", 50)),
            threading.Thread(target=writer, args=("moira", 50)),
            threading.Thread(target=writer, args=("kyoko", 50)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not errors
        assert mem.count() == 150
        assert mem.count("karen") == 50


class TestConversationMemoryRedisFallback:
    """Verify graceful fallback when Redis is unavailable."""

    def test_no_redis_still_works(self):
        mem = ConversationMemory(use_redis=False)
        assert not mem.redis_available
        mem.record("karen", "Fallback works")
        assert mem.get_last().text == "Fallback works"

    @patch("agentic_brain.core.redis_pool.get_redis_pool")
    def test_redis_import_error_fallback(self, mock_pool):
        mock_pool.side_effect = ImportError("no redis")
        mem = ConversationMemory(use_redis=True)
        assert not mem.redis_available
        mem.record("karen", "Still works")
        assert mem.count() == 1

    def test_redis_client_injected(self):
        mock_client = MagicMock()
        mem = ConversationMemory(redis_client=mock_client)
        assert mem.redis_available

    def test_redis_push_failure_degrades_gracefully(self):
        mock_client = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.execute.side_effect = ConnectionError("Redis gone")
        mock_client.pipeline.return_value = mock_pipe
        mem = ConversationMemory(redis_client=mock_client)
        # Should not raise – falls back to in-memory
        mem.record("karen", "Survives Redis failure")
        assert mem.count() == 1  # in-memory count

    def test_redis_read_failure_falls_back(self):
        mock_client = MagicMock()
        mock_client.lrange.side_effect = ConnectionError("Redis gone")
        mem = ConversationMemory(redis_client=mock_client, use_redis=True)
        mem.record("karen", "Test")
        # get_recent should fall back to in-memory
        recent = mem.get_recent("karen")
        assert len(recent) == 1


class TestConversationMemorySingleton:
    """Test singleton lifecycle."""

    def test_singleton_returns_same(self):
        a = get_conversation_memory(use_redis=False)
        b = get_conversation_memory()
        assert a is b

    def test_reset_clears_singleton(self):
        a = get_conversation_memory(use_redis=False)
        reset_conversation_memory()
        b = get_conversation_memory(use_redis=False)
        assert a is not b


# ═══════════════════════════════════════════════════════════════════
# RepeatDetector tests
# ═══════════════════════════════════════════════════════════════════


class TestRepeatDetectorBasic:
    """Core repeat detection logic."""

    def test_no_history_no_repeat(self, detector: RepeatDetector):
        result = detector.check("Hello")
        assert not result.is_repeat
        assert result.similarity == 0.0

    def test_exact_repeat(self, detector: RepeatDetector):
        detector.record("Good morning Joseph")
        result = detector.check("Good morning Joseph")
        assert result.is_repeat
        assert result.similarity == 1.0

    def test_near_duplicate(self, detector: RepeatDetector):
        detector.record("Starting work on JIRA now")
        result = detector.check("Starting work on JIRA now.")
        assert result.is_repeat
        assert result.similarity > 0.9

    def test_different_text_not_repeat(self, detector: RepeatDetector):
        detector.record("Good morning")
        result = detector.check("PR #209 approved")
        assert not result.is_repeat

    def test_case_insensitive(self, detector: RepeatDetector):
        detector.record("PR APPROVED")
        result = detector.check("pr approved")
        assert result.is_repeat

    def test_punctuation_insensitive(self, detector: RepeatDetector):
        detector.record("Hello, Joseph!")
        result = detector.check("Hello Joseph")
        assert result.is_repeat

    def test_is_repeat_convenience(self, detector: RepeatDetector):
        detector.record("Test message")
        assert detector.is_repeat("Test message")
        assert not detector.is_repeat("Completely different")

    def test_custom_threshold(self, detector: RepeatDetector):
        detector.record("Alpha Beta")
        # With very high threshold, small differences matter
        result = detector.check("Alpha Beta Gamma", threshold=0.99)
        assert not result.is_repeat
        # With low threshold, they match
        result = detector.check("Alpha Beta Gamma", threshold=0.5)
        assert result.is_repeat


class TestRepeatDetectorWindow:
    """Test the sliding window behaviour."""

    def test_window_eviction(self):
        detector = RepeatDetector(window=3, action=RepeatAction.WARN)
        detector.record("A")
        detector.record("B")
        detector.record("C")
        # "A" should still be in window
        assert detector.is_repeat("A")
        # Add one more → "A" evicted
        detector.record("D")
        assert not detector.is_repeat("A")

    def test_recent_returns_correct(self, detector: RepeatDetector):
        detector.record("First")
        detector.record("Second")
        detector.record("Third")
        recent = detector.recent(2)
        assert recent == ["Second", "Third"]

    def test_clear_resets(self, detector: RepeatDetector):
        detector.record("Hello")
        detector.clear()
        assert not detector.is_repeat("Hello")
        assert detector.recent() == []


class TestRepeatDetectorActions:
    """Test ALLOW / WARN / BLOCK actions."""

    def test_block_action(self):
        detector = RepeatDetector(action=RepeatAction.BLOCK)
        detector.record("Hello")
        result = detector.check("Hello")
        assert result.is_repeat
        assert result.should_block

    def test_warn_action(self):
        detector = RepeatDetector(action=RepeatAction.WARN)
        detector.record("Hello")
        result = detector.check("Hello")
        assert result.is_repeat
        assert not result.should_block

    def test_allow_action(self):
        detector = RepeatDetector(action=RepeatAction.ALLOW)
        detector.record("Hello")
        result = detector.check("Hello")
        assert result.is_repeat
        assert not result.should_block

    @patch.dict("os.environ", {"AGENTIC_BRAIN_VOICE_NO_REPEATS": "true"})
    def test_env_var_sets_block(self):
        detector = RepeatDetector()
        assert detector.action == RepeatAction.BLOCK


class TestRepeatDetectorConfig:
    """Test configuration methods."""

    def test_set_threshold(self, detector: RepeatDetector):
        detector.set_threshold(0.95)
        assert detector.threshold == 0.95

    def test_threshold_clamped(self, detector: RepeatDetector):
        detector.set_threshold(2.0)
        assert detector.threshold == 1.0
        detector.set_threshold(-1.0)
        assert detector.threshold == 0.0

    def test_set_window(self, detector: RepeatDetector):
        for i in range(30):
            detector.record(f"Msg {i}")
        detector.set_window(5)
        assert len(detector.recent(100)) == 5


class TestRepeatDetectorSingleton:
    """Test singleton lifecycle."""

    def test_singleton(self):
        a = get_repeat_detector()
        b = get_repeat_detector()
        assert a is b

    def test_reset(self):
        a = get_repeat_detector()
        reset_repeat_detector()
        b = get_repeat_detector()
        assert a is not b


class TestRepeatResult:
    """Test RepeatResult dataclass."""

    def test_should_block_only_when_block_and_repeat(self):
        r = RepeatResult(
            is_repeat=True, similarity=1.0, matched_text="x", action=RepeatAction.BLOCK
        )
        assert r.should_block
        r2 = RepeatResult(
            is_repeat=False, similarity=0.0, matched_text="", action=RepeatAction.BLOCK
        )
        assert not r2.should_block
        r3 = RepeatResult(
            is_repeat=True, similarity=1.0, matched_text="x", action=RepeatAction.WARN
        )
        assert not r3.should_block
