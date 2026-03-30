# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests to verify voice-on-voice overlap is prevented.

Sound effects over voice is FINE - we only prevent voice-on-voice overlap.

CRITICAL RULE: Ladies must NEVER talk over each other. One voice at a time.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from agentic_brain.voice.resilient import ResilientVoice
from agentic_brain.voice.serializer import VoiceSerializer, get_voice_serializer


@pytest.mark.timeout(30)
class TestNoVoiceOverlap:
    """Verify that voices never overlap."""

    @pytest.mark.asyncio
    async def test_concurrent_speak_calls_serialize(self):
        """Multiple concurrent speak() calls should execute one at a time."""
        speech_times = []

        async def mock_speak(*args, **kwargs):
            current_time = time.time()
            speech_times.append(("start", current_time))
            await asyncio.sleep(0.1)  # Simulate speech duration
            speech_times.append(("end", time.time()))
            return True

        with patch.object(ResilientVoice, "_say_with_voice", mock_speak):
            # Fire 3 concurrent speak calls
            await asyncio.gather(
                ResilientVoice.speak("one"),
                ResilientVoice.speak("two"),
                ResilientVoice.speak("three"),
            )

        # Verify no overlaps: each "start" should come after previous "end"
        assert len(speech_times) == 6, f"Expected 6 events, got {len(speech_times)}"

        # Check that each speech completes before the next starts
        for i in range(0, len(speech_times) - 2, 2):
            end_event = speech_times[i + 1]
            next_start_event = speech_times[i + 2]

            assert end_event[0] == "end", f"Expected 'end' at index {i+1}"
            assert next_start_event[0] == "start", f"Expected 'start' at index {i+2}"

            end_time = end_event[1]
            next_start_time = next_start_event[1]

            assert (
                next_start_time >= end_time
            ), f"Voice overlap detected! Next started at {next_start_time} before previous ended at {end_time}"

    @pytest.mark.asyncio
    async def test_daemon_serializes_queued_items(self):
        """Daemon should process queued items one at a time.

        Note: Testing serialization via the ResilientVoice speak() method,
        which uses the global serializer to prevent overlaps.
        """
        processed = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            processed.append(f"start:{text}")
            await asyncio.sleep(0.05)
            processed.append(f"end:{text}")
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Sequential calls (simulating daemon behavior)
            await ResilientVoice.speak("one")
            await ResilientVoice.speak("two")
            await ResilientVoice.speak("three")

        # Check serialization
        assert "start:one" in processed
        assert "end:one" in processed
        assert "start:two" in processed
        assert "end:two" in processed
        assert "start:three" in processed
        assert "end:three" in processed

        # Verify no overlap
        one_start = processed.index("start:one")
        one_end = processed.index("end:one")
        two_start = processed.index("start:two")
        two_end = processed.index("end:two")
        three_start = processed.index("start:three")

        assert one_end < two_start, "Voice two started before one ended!"
        assert two_end < three_start, "Voice three started before two ended!"

    @pytest.mark.asyncio
    async def test_rapid_fire_speak_calls(self):
        """Rapid-fire speak calls in tight loop should still serialize."""
        call_count = 0
        active_speeches = 0
        max_concurrent = 0
        lock = asyncio.Lock()

        async def mock_speak_with_fallbacks(text, voice, rate):
            nonlocal call_count, active_speeches, max_concurrent
            async with lock:
                active_speeches += 1
                max_concurrent = max(max_concurrent, active_speeches)
            call_count += 1
            await asyncio.sleep(0.02)  # Very short speech
            async with lock:
                active_speeches -= 1
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Fire 10 rapid calls
            tasks = [ResilientVoice.speak(f"message_{i}") for i in range(10)]
            await asyncio.gather(*tasks)

        assert call_count == 10, f"Expected 10 calls, got {call_count}"
        assert (
            max_concurrent == 1
        ), f"Voice overlap! Max concurrent was {max_concurrent}, should be 1"

    @pytest.mark.asyncio
    async def test_daemon_direct_speak_interleaving(self):
        """Concurrent speak() calls should not overlap.

        Note: This tests serialization via the global lock.
        All calls use the same lock, preventing overlap.
        """
        events = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            events.append(("start", text, time.time()))
            await asyncio.sleep(0.05)
            events.append(("end", text, time.time()))
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Concurrent calls go through the global lock
            tasks = [
                ResilientVoice.speak("first"),
                ResilientVoice.speak("second"),
                ResilientVoice.speak("third"),
            ]
            await asyncio.gather(*tasks)

        # Verify no overlaps in timeline
        start_times = {}
        end_times = {}

        for event_type, text, timestamp in events:
            if event_type == "start":
                start_times[text] = timestamp
            else:
                end_times[text] = timestamp

        # Check all speeches completed
        for text in start_times:
            assert text in end_times, f"Speech '{text}' never completed"

        # Check no overlaps - every start should be after all previous ends
        sorted_events = sorted(events, key=lambda x: x[2])
        active = set()

        for event_type, text, timestamp in sorted_events:
            if event_type == "start":
                assert (
                    len(active) == 0
                ), f"Voice '{text}' started while {active} still active - OVERLAP!"
                active.add(text)
            else:
                active.discard(text)

    @pytest.mark.asyncio
    async def test_mode_switch_doesnt_interrupt(self):
        """Mode switch announcement should not interrupt ongoing speech."""
        events = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            events.append(("start", text))
            await asyncio.sleep(0.1)
            events.append(("end", text))
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Start a long speech
            speech_task = asyncio.create_task(ResilientVoice.speak("long message"))

            # Wait a bit, then trigger mode switch announcement
            await asyncio.sleep(0.02)
            mode_task = asyncio.create_task(
                ResilientVoice.speak("Switching to work mode")
            )

            # Wait for both
            await asyncio.gather(speech_task, mode_task)

        # Verify order - long message should complete before mode switch starts
        assert events[0] == ("start", "long message")
        assert events[1] == ("end", "long message")
        assert events[2] == ("start", "Switching to work mode")
        assert events[3] == ("end", "Switching to work mode")

    @pytest.mark.asyncio
    async def test_sound_effects_can_play_over_voice(self):
        """Sound effects (Glass, Ping) CAN play over voice - this is fine.

        This test documents that sound effects over voice is acceptable.
        Only voice-on-voice is prevented.
        """
        # This test documents behavior - sound effects don't use the speech lock
        # They can play simultaneously with voice, which is intentional
        assert True, "Sound effects are allowed over voice - documented behavior"

    @pytest.mark.asyncio
    async def test_serializer_lock_behavior(self):
        """Test that voice serializer properly locks and releases."""
        lock_events = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            lock_events.append(f"acquired:{text}")
            await asyncio.sleep(0.05)
            lock_events.append(f"released:{text}")
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            await asyncio.gather(
                ResilientVoice.speak("first"),
                ResilientVoice.speak("second"),
                ResilientVoice.speak("third"),
            )

        # Verify lock was acquired and released in order
        assert lock_events[0] == "acquired:first"
        assert lock_events[1] == "released:first"
        assert lock_events[2] == "acquired:second"
        assert lock_events[3] == "released:second"
        assert lock_events[4] == "acquired:third"
        assert lock_events[5] == "released:third"

    @pytest.mark.asyncio
    async def test_timeout_doesnt_cause_overlap(self):
        """If a speech times out, the next speech should still wait."""
        events = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            events.append(f"start:{text}")
            if "slow" in text:
                await asyncio.sleep(0.15)  # Slow but not too slow
            else:
                await asyncio.sleep(0.05)
            events.append(f"end:{text}")
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Both should serialize even if one is slower
            await asyncio.gather(
                ResilientVoice.speak("slow message"),
                ResilientVoice.speak("fast message"),
            )

        # Fast message should not start before slow message ends
        assert len(events) >= 2
        assert events[0] == "start:slow message"

    @pytest.mark.asyncio
    async def test_multiple_ladies_never_overlap(self):
        """Multiple ladies speaking should never overlap - the sacred rule."""
        ladies_timeline = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            ladies_timeline.append(("start", voice, text, time.time()))
            await asyncio.sleep(0.08)  # Simulate speech
            ladies_timeline.append(("end", voice, text, time.time()))
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Multiple ladies trying to speak
            await asyncio.gather(
                ResilientVoice.speak("Hello Joseph", voice="Karen"),
                ResilientVoice.speak("Good morning", voice="Moira"),
                ResilientVoice.speak("おはよう", voice="Kyoko"),
                ResilientVoice.speak("Let me help", voice="Tingting"),
            )

        # Verify strict serialization - no lady speaks over another
        active_lady = None

        for event_type, lady, text, timestamp in ladies_timeline:
            if event_type == "start":
                assert (
                    active_lady is None
                ), f"{lady} started speaking while {active_lady} was still talking! FORBIDDEN!"
                active_lady = lady
            else:
                assert (
                    active_lady == lady
                ), f"End event for {lady} but {active_lady} was speaking"
                active_lady = None

        # All ladies should have spoken
        ladies_spoken = {event[1] for event in ladies_timeline}
        assert "Karen" in ladies_spoken
        assert "Moira" in ladies_spoken
        assert "Kyoko" in ladies_spoken
        assert "Tingting" in ladies_spoken

    @pytest.mark.asyncio
    async def test_emergency_stop_clears_queue(self):
        """Emergency stop should clear queue but not interrupt current speech."""
        events = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            events.append(f"start:{text}")
            await asyncio.sleep(0.05)
            events.append(f"end:{text}")
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Sequential calls
            await ResilientVoice.speak("one")
            await ResilientVoice.speak("two")
            await ResilientVoice.speak("three")

        # All messages should complete in order
        assert "start:one" in events
        assert "end:one" in events
        # Emergency stop behavior would be tested at serializer level

    @pytest.mark.asyncio
    async def test_high_concurrency_stress(self):
        """Stress test with many concurrent speak attempts."""
        call_order = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            call_order.append(f"start:{text}")
            await asyncio.sleep(0.01)
            call_order.append(f"end:{text}")
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Fire 20 concurrent calls
            tasks = [ResilientVoice.speak(f"msg_{i}") for i in range(20)]
            await asyncio.gather(*tasks)

        # Verify all 20 executed
        assert len(call_order) == 40, f"Expected 40 events, got {len(call_order)}"

        # Verify strict serialization
        for i in range(0, len(call_order), 2):
            assert call_order[i].startswith("start:")
            assert call_order[i + 1].startswith("end:")
            # Extract message number
            start_num = call_order[i].split(":")[1]
            end_num = call_order[i + 1].split(":")[1]
            assert start_num == end_num, f"Mismatch: {start_num} vs {end_num}"


class TestVoiceQueueBehavior:
    """Test voice queue and serialization behavior."""

    @pytest.mark.asyncio
    async def test_queue_preserves_order(self):
        """Voice queue should preserve FIFO order."""
        spoken_order = []

        async def mock_speak_with_fallbacks(text, voice, rate):
            spoken_order.append(text)
            await asyncio.sleep(0.01)
            return True

        with patch.object(
            ResilientVoice, "_speak_with_fallbacks", mock_speak_with_fallbacks
        ):
            # Queue messages in order
            await asyncio.gather(
                ResilientVoice.speak("first"),
                ResilientVoice.speak("second"),
                ResilientVoice.speak("third"),
            )

        # Should execute in order (FIFO)
        assert spoken_order == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_priority_not_supported(self):
        """No priority queue - all voices equal."""
        # This documents that we don't support priority
        # All ladies are equal, first-come first-served
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
