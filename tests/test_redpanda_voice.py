# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import asyncio
import os

import pytest

# Skip voice integration tests on CI - no audio device available
CI_SKIP = pytest.mark.skipif(
    os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true",
    reason="Voice tests require audio device - skip on CI",
)

from agentic_brain.voice.redpanda_queue import (
    RedpandaVoiceQueue,
    VoiceMessage,
    VoicePriority,
)


@pytest.mark.asyncio
async def test_enqueue_memory_backend() -> None:
    """Messages enqueue correctly when using the in-memory backend.

    This test does not require Redpanda or Redis – it exercises the
    "memory" backend used for unit tests and local development.
    """

    queue = RedpandaVoiceQueue(backend="memory")
    await queue.connect()

    assert queue.backend == "memory"

    await queue.enqueue(VoiceMessage(text="hello"))
    length = await queue.queue_length()
    assert length == 1


@pytest.mark.asyncio
async def test_priority_sorting_orders_by_priority_then_timestamp() -> None:
    """_sort_pending uses priority first, then timestamp for ordering."""

    m_low = VoiceMessage(text="low", priority=VoicePriority.LOW, timestamp=10.0)
    m_high = VoiceMessage(text="high", priority=VoicePriority.HIGH, timestamp=5.0)
    m_critical = VoiceMessage(
        text="critical", priority=VoicePriority.CRITICAL, timestamp=1.0
    )

    pending = [m_low, m_high, m_critical]
    RedpandaVoiceQueue._sort_pending(pending)

    assert [m.text for m in pending] == ["critical", "high", "low"]


@CI_SKIP
@pytest.mark.asyncio
async def test_no_overlap_with_resilient_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """process_queue never calls the voice backend concurrently.

    We patch ResilientVoice.speak with a stub that tracks how many concurrent
    invocations are active. The queue must ensure this never exceeds 1.
    """

    import agentic_brain.voice.redpanda_queue as rq

    in_progress = 0
    max_in_progress = 0
    calls: list[tuple[str, str, int]] = []

    async def fake_speak(text: str, voice: str, rate: int) -> bool:
        nonlocal in_progress, max_in_progress
        in_progress += 1
        max_in_progress = max(max_in_progress, in_progress)
        calls.append((text, voice, rate))
        # Simulate short speech
        await asyncio.sleep(0.01)
        in_progress -= 1
        return True

    monkeypatch.setattr(rq.ResilientVoice, "speak", fake_speak, raising=True)

    queue = RedpandaVoiceQueue(backend="memory")
    await queue.connect()

    # Enqueue multiple messages with different priorities
    await queue.speak("one", priority=VoicePriority.LOW)
    await queue.speak("two", priority=VoicePriority.HIGH)

    # Start processor and let it run briefly
    task = asyncio.create_task(queue.process_queue())
    await asyncio.sleep(0.05)
    await queue.stop()
    # Give the loop a chance to exit cleanly
    await asyncio.sleep(0.01)
    task.cancel()

    # Only one speak invocation may run at a time
    assert max_in_progress == 1
    # Higher-priority message must be processed; lower-priority may or may not
    # depending on timing in this test.
    spoken = {c[0] for c in calls}
    assert "two" in spoken


@CI_SKIP
@pytest.mark.asyncio
async def test_redis_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """When configured for Redis, the queue uses the Redis backend.

    We provide a lightweight in-memory stand-in for redis.asyncio so that this
    test has no external dependencies.
    """

    import agentic_brain.voice.redpanda_queue as rq

    class FakeRedisClient:
        def __init__(self) -> None:
            self._items: list[str] = []

        async def ping(self) -> bool:  # pragma: no cover - trivial
            return True

        async def rpush(self, key: str, value: str) -> None:
            self._items.append(value)

        async def blpop(self, key: str, timeout: int = 0):  # pragma: no cover
            if not self._items:
                return None
            value = self._items.pop(0)
            return key, value

        async def llen(self, key: str) -> int:
            return len(self._items)

        async def delete(self, key: str) -> None:
            self._items.clear()

        async def close(self) -> None:  # pragma: no cover - no-op
            return None

    async def fake_connect_redis(self) -> bool:
        self._redis = FakeRedisClient()
        self._backend = "redis"
        return True

    monkeypatch.setattr(
        rq.RedpandaVoiceQueue, "_connect_redis", fake_connect_redis, raising=True
    )

    queue = RedpandaVoiceQueue(backend="redis", redis_url="redis://fake")
    await queue.connect()

    # Backend should be redis after connect
    assert queue.backend == "redis"

    await queue.enqueue(VoiceMessage(text="hello redis"))
    length = await queue.queue_length()
    assert length == 1

    cleared = await queue.clear()
    assert cleared == 1
    assert await queue.queue_length() == 0
