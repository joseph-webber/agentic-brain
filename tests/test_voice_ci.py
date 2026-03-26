# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
"""
Voice System CI Tests

Comprehensive tests for voice features:
- Latency and performance
- Queue and priority
- Regional expressions
- Fallback chains
- Never-overlap guarantee
"""

import asyncio
import threading
import time
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.voice.australian_regions import (
    AUSTRALIAN_CITIES,
    get_local_knowledge,
)
from agentic_brain.voice.conversation import ConversationalVoice
from agentic_brain.voice.queue import VoiceMessage
from agentic_brain.voice.queue import VoiceQueue as LocalVoiceQueue
from agentic_brain.voice.redpanda_queue import (
    RedpandaVoiceQueue,
    VoicePriority,
)
from agentic_brain.voice.redpanda_queue import (
    VoiceMessage as DurableVoiceMessage,
)
from agentic_brain.voice.resilient import (
    ResilientVoice,
    SoundEffects,
    play_sound,
)
from agentic_brain.voice.resilient import (
    VoiceConfig as ResilientConfig,
)
from agentic_brain.voice.resilient import (
    speak as resilient_speak,
)


class TestVoiceLatency:
    """Voice response time tests"""

    @pytest.mark.asyncio
    async def test_voice_queue_latency_under_100ms(self):
        """Queueing a message should be fast (< 100ms)."""
        queue = RedpandaVoiceQueue(backend="memory")

        start = time.perf_counter()
        await queue.connect()
        await queue.enqueue(
            DurableVoiceMessage(text="Quick latency test", voice="Karen", rate=155)
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < 100, f"Enqueue took {elapsed_ms:.2f}ms, expected < 100ms"

    @pytest.mark.asyncio
    async def test_voice_fallback_latency_under_500ms(self):
        """Fallback chain should respond quickly (< 500ms).

        We patch the fallback methods to be fast so we are only
        measuring the orchestration overhead of the chain itself.
        """
        config = ResilientConfig(timeout=1)
        ResilientVoice(config)

        async def fast_fallback(
            text: str, voice: str, rate: int
        ) -> bool:  # pragma: no cover - trivial
            await asyncio.sleep(0)
            return True

        # Replace all fallback methods with a fast implementation
        for fb in ResilientVoice._fallbacks:  # type: ignore[attr-defined]
            fb.method = fast_fallback

        start = time.perf_counter()
        result = await resilient_speak("Fallback latency check")
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert isinstance(result, bool)
        assert (
            elapsed_ms < 500
        ), f"Fallback chain took {elapsed_ms:.2f}ms, expected < 500ms"


class TestVoicePriority:
    """Priority system tests"""

    def test_critical_priority_plays_first(self):
        """CRITICAL messages jump the queue ahead of others."""
        now = time.time()
        normal = DurableVoiceMessage(
            text="normal",
            voice="Karen",
            rate=155,
            priority=VoicePriority.NORMAL,
            timestamp=now,
        )
        critical = DurableVoiceMessage(
            text="critical",
            voice="Karen",
            rate=155,
            priority=VoicePriority.CRITICAL,
            timestamp=now - 10,  # older, but higher priority
        )
        high = DurableVoiceMessage(
            text="high",
            voice="Karen",
            rate=155,
            priority=VoicePriority.HIGH,
            timestamp=now + 10,
        )

        pending: List[DurableVoiceMessage] = [normal, critical, high]
        RedpandaVoiceQueue._sort_pending(pending)

        assert pending[0].priority is VoicePriority.CRITICAL

    def test_priority_ordering_correct(self):
        """Messages ordered by priority then timestamp (FIFO within same priority)."""
        now = time.time()
        low_early = DurableVoiceMessage(
            text="low early",
            voice="Karen",
            rate=155,
            priority=VoicePriority.LOW,
            timestamp=now - 5,
        )
        low_late = DurableVoiceMessage(
            text="low late",
            voice="Karen",
            rate=155,
            priority=VoicePriority.LOW,
            timestamp=now + 5,
        )
        high = DurableVoiceMessage(
            text="high",
            voice="Karen",
            rate=155,
            priority=VoicePriority.HIGH,
            timestamp=now,
        )

        pending: List[DurableVoiceMessage] = [low_late, high, low_early]
        RedpandaVoiceQueue._sort_pending(pending)

        priorities = [m.priority for m in pending]
        assert priorities == [VoicePriority.HIGH, VoicePriority.LOW, VoicePriority.LOW]
        # Within LOW priority, the earlier message should come first
        low_messages = [m for m in pending if m.priority is VoicePriority.LOW]
        assert low_messages[0].timestamp <= low_messages[1].timestamp


class TestVoiceNeverOverlap:
    """Guarantee voices never talk over each other"""

    @patch("agentic_brain.voice.queue.subprocess.Popen")
    @patch("agentic_brain.voice.queue.time.sleep")
    def test_sequential_voices_have_gap(self, sleep_mock, popen_mock):
        """At least 0.5s gap between voices via VoiceQueue.pause_after."""
        # Stub subprocess so we do not actually call `say`
        process = MagicMock()
        process.wait.return_value = 0
        popen_mock.return_value = process

        queue = LocalVoiceQueue.get_instance()
        queue.reset()

        # Two sequential messages with explicit pauses
        queue.speak("First message", voice="Karen", pause_after=0.5)
        queue.speak("Second message", voice="Karen", pause_after=0.75)

        # sleep() should be called for each message with configured pauses
        pauses = [call.args[0] for call in sleep_mock.call_args_list]
        assert len(pauses) >= 2
        assert all(p >= 0.5 for p in pauses)

    def test_concurrent_requests_queue_properly(self):
        """Multiple requests from different threads must not overlap."""
        queue = LocalVoiceQueue.get_instance()
        queue.reset()

        concurrency = 0
        max_concurrency = 0

        def fake_speak(self, message: VoiceMessage) -> None:
            nonlocal concurrency, max_concurrency
            concurrency += 1
            max_concurrency = max(max_concurrency, concurrency)
            time.sleep(0.01)
            concurrency -= 1

        with patch.object(LocalVoiceQueue, "_speak_message", new=fake_speak):
            threads = []
            for i in range(5):
                t = threading.Thread(
                    target=lambda idx=i: queue.speak(f"Message {idx}", voice="Karen")
                )
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

        # Even under concurrent callers, only one "speaker" should run at a time
        assert max_concurrency == 1


class TestVoiceRegional:
    """Regional expression tests using Australian city database."""

    def test_adelaide_expressions(self):
        """Adelaide slang is mapped correctly."""
        adelaide = AUSTRALIAN_CITIES["adelaide"]
        slang = adelaide["slang"]

        assert slang["great"] == "heaps good"
        assert slang["very"] == "heaps"
        assert "bottle shop" in slang
        assert slang["bottle shop"] == "bottle-o"

    def test_melbourne_expressions(self):
        """Melbourne slang is mapped correctly."""
        melbourne = AUSTRALIAN_CITIES["melbourne"]
        slang = melbourne["slang"]

        assert slang["great"] == "ripper"
        assert slang["very"] == "bloody"
        assert "service_station" in slang

    def test_unknown_region_fallback(self):
        """Unknown regions fall back to a safe default message."""
        msg = get_local_knowledge("unknown_city", "slang")
        assert "don't have data" in msg.lower()


class TestVoiceFallback:
    """Fallback chain tests"""

    @pytest.mark.asyncio
    async def test_fallback_chain_order(self):
        """Fallback tries methods in configured order."""
        config = ResilientConfig()
        ResilientVoice(config)

        priorities = [fb.priority for fb in ResilientVoice._fallbacks]  # type: ignore[attr-defined]
        assert priorities == sorted(priorities)

        names = [fb.name for fb in ResilientVoice._fallbacks]  # type: ignore[attr-defined]
        # Sanity-check the ends of the chain
        # First fallback depends on platform: macOS uses say_with_voice, Linux uses linux_voice
        assert names[0] in ("say_with_voice", "linux_voice", "windows_voice")
        # Last fallback: macOS has alert_sound (6 methods), others end with cloud_tts (2 methods)
        assert names[-1] in ("alert_sound", "cloud_tts")

    @pytest.mark.asyncio
    async def test_sound_effect_fallback(self):
        """At minimum, a sound effect is played as fallback."""
        # Patch SoundEffects.play so we do not hit the real OS
        with patch.object(
            SoundEffects, "play", new=AsyncMock(return_value=True)
        ) as play_mock:
            result = await play_sound("success")

        play_mock.assert_awaited_once()
        assert result is True


class TestVoiceRobotHuman:
    """Robot-human hybrid features"""

    @patch("agentic_brain.voice.queue.subprocess.Popen")
    @patch("agentic_brain.voice.queue.time.sleep")
    def test_thinking_announcement(self, sleep_mock, popen_mock):
        """Announces when thinking/processing via queued speech."""
        process = MagicMock()
        process.wait.return_value = 0
        popen_mock.return_value = process

        queue = LocalVoiceQueue.get_instance()
        queue.reset()

        message = queue.speak("Thinking about the next step...", voice="Karen")
        assert isinstance(message, VoiceMessage)
        assert "thinking" in message.text.lower()

    def test_natural_pauses(self):
        """Natural pauses are added to connector phrases."""
        conv = ConversationalVoice()
        text = "However this is good"
        paused = conv.add_natural_pauses(text)

        assert paused != text
        # Expect a pause after the discourse marker
        assert "However," in paused
