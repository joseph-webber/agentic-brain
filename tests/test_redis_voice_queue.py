# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

from __future__ import annotations

import time

import pytest

fakeredis = pytest.importorskip("fakeredis")

from agentic_brain.cache.voice_cache import VoiceState
from agentic_brain.voice.redis_queue import RedisVoiceQueue, VoiceAudioCache, VoiceJob
from agentic_brain.voice.serializer import VoiceMessage, get_voice_serializer


def _shared_client(*, decode_responses: bool = True):
    server = fakeredis.FakeServer()
    return fakeredis.FakeRedis(server=server, decode_responses=decode_responses)


def test_priority_lane_orders_urgent_and_high_before_normal():
    client = _shared_client()
    queue = RedisVoiceQueue(client=client)

    queue.enqueue(VoiceJob(text="normal-1", priority="normal"))
    queue.enqueue(VoiceJob(text="high-1", priority="high"))
    queue.enqueue(VoiceJob(text="normal-2", priority="normal"))
    queue.enqueue(VoiceJob(text="urgent-1", priority="urgent"))

    assert queue.depth == 4
    assert queue.dequeue().text == "urgent-1"
    assert queue.dequeue().text == "high-1"
    assert queue.dequeue().text == "normal-1"
    assert queue.dequeue().text == "normal-2"
    assert queue.dequeue() is None


def test_queue_survives_restart_with_shared_redis_state():
    server = fakeredis.FakeServer()
    producer = fakeredis.FakeRedis(server=server, decode_responses=True)
    consumer = fakeredis.FakeRedis(server=server, decode_responses=True)

    RedisVoiceQueue(client=producer).enqueue(VoiceJob(text="Persist me"))

    restarted_queue = RedisVoiceQueue(client=consumer)
    recovered = restarted_queue.dequeue()

    assert recovered is not None
    assert recovered.text == "Persist me"
    assert restarted_queue.depth == 0


def test_voice_state_is_visible_across_processes():
    server = fakeredis.FakeServer()
    client_a = fakeredis.FakeRedis(server=server, decode_responses=True)
    client_b = fakeredis.FakeRedis(server=server, decode_responses=True)

    queue_a = RedisVoiceQueue(client=client_a)
    queue_b = RedisVoiceQueue(client=client_b)

    queue_a.enqueue(VoiceJob(text="queued"))
    queue_a.set_speaking("Karen", "Speaking now")

    state = queue_b.get_state()
    assert state["is_speaking"] is True
    assert state["current_lady"] == "Karen"
    assert state["current_text"] == "Speaking now"
    assert state["queue_depth"] == 1

    queue_a.clear_speaking()
    cleared = queue_b.get_state()
    assert cleared["is_speaking"] is False
    assert cleared["current_text"] == ""


def test_audio_cache_hit_miss_and_lru_eviction():
    client = _shared_client()
    cache = VoiceAudioCache(client=client, max_entries=1)

    assert cache.get("hello", "Karen") is None

    first_key = cache.set("hello", "Karen", b"audio-1")
    assert cache.get("hello", "Karen") == b"audio-1"

    second_key = cache.set("goodbye", "Karen", b"audio-2")
    assert cache.get("goodbye", "Karen") == b"audio-2"
    assert cache.get("hello", "Karen") is None
    assert first_key != second_key


def test_serializer_drains_redis_queue_after_restart(monkeypatch):
    serializer = get_voice_serializer()
    serializer.reset()
    serializer.set_pause_between(0)

    client = _shared_client()
    redis_queue = RedisVoiceQueue(client=client)
    spoken: list[str] = []

    original_queue = serializer._redis_queue
    original_cache = serializer._voice_cache
    original_speak = serializer._speak_with_say

    class FakeVoiceCache:
        def __init__(self):
            self.states: list[VoiceState] = []

        def set_state(self, state: VoiceState) -> None:
            self.states.append(state)

    fake_cache = FakeVoiceCache()

    try:
        serializer._redis_queue = redis_queue
        serializer._voice_cache = fake_cache
        monkeypatch.setattr(
            serializer,
            "_speak_with_say",
            lambda message: spoken.append(message.text) is None or True,
        )

        redis_queue.enqueue(VoiceJob(text="Recovered speech", voice="Karen", rate=155))
        with serializer._queue_ready:
            serializer._queue_ready.notify_all()

        deadline = time.time() + 2
        while time.time() < deadline and (redis_queue.depth > 0 or not spoken):
            time.sleep(0.01)
    finally:
        serializer._redis_queue = original_queue
        serializer._voice_cache = original_cache
        monkeypatch.setattr(serializer, "_speak_with_say", original_speak)
        serializer.reset()
        serializer.set_pause_between(0.3)

    assert spoken == ["Recovered speech"]
    assert redis_queue.depth == 0
    assert any(state.is_speaking for state in fake_cache.states)
    assert fake_cache.states[-1] == VoiceState()


def test_serializer_queues_new_messages_in_redis():
    serializer = get_voice_serializer()
    serializer.reset()
    serializer.set_pause_between(0)

    client = _shared_client()
    redis_queue = RedisVoiceQueue(client=client)

    original_queue = serializer._redis_queue
    try:
        serializer._redis_queue = redis_queue
        result = serializer.run_serialized(
            VoiceMessage(text="Queued in redis", voice="Karen", rate=155),
            executor=lambda message: True,
        )
    finally:
        serializer._redis_queue = original_queue
        serializer.reset()
        serializer.set_pause_between(0.3)

    assert result is True
    assert redis_queue.depth == 0
