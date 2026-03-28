# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

from dataclasses import asdict

import pytest

fakeredis = pytest.importorskip("fakeredis")

from agentic_brain.cache.voice_cache import VoiceCache, VoiceState
from agentic_brain.voice.serializer import VoiceMessage, get_voice_serializer


def test_cache_audio_round_trip_with_binary_payload():
    client = fakeredis.FakeRedis(decode_responses=True)
    cache = VoiceCache(client=client)

    audio_bytes = b"\x00\xffvoice-audio\x10"
    key = cache.cache_audio("Hello Joseph", "Karen", audio_bytes, ttl=60)

    assert key.startswith("voice:audio:")
    assert cache.get_cached_audio("Hello Joseph", "Karen") == audio_bytes


def test_queue_orders_by_priority_and_preserves_duplicates():
    client = fakeredis.FakeRedis(decode_responses=True)
    cache = VoiceCache(client=client)

    cache.enqueue_speech("duplicate", "Karen", priority=10)
    high = cache.enqueue_speech("urgent", "Moira", priority=80)
    cache.enqueue_speech("duplicate", "Karen", priority=10)

    assert cache.get_queue_depth() == 3

    first = cache.dequeue_speech()
    second = cache.dequeue_speech()
    third = cache.dequeue_speech()

    assert first is not None
    assert first["id"] == high["id"]
    assert second is not None and second["text"] == "duplicate"
    assert third is not None and third["text"] == "duplicate"
    assert second["id"] != third["id"]
    assert cache.get_queue_depth() == 0


def test_state_round_trip_and_phrase_metrics():
    client = fakeredis.FakeRedis(decode_responses=True)
    cache = VoiceCache(client=client)

    state = VoiceState(
        is_speaking=True,
        current_text="Working on it",
        current_voice="Karen",
        queue_depth=2,
    )
    cache.set_state(state)
    cache.cache_audio("Working on it", "Karen", b"abc", ttl=60)
    cache.cache_audio("Working on it", "Karen", b"def", ttl=60)

    assert cache.get_state() == state
    phrases = cache.get_top_phrases(limit=1)
    assert phrases[0][0] == "Working on it"
    assert phrases[0][1] == 2.0


def test_serializer_updates_redis_voice_state():
    serializer = get_voice_serializer()
    serializer.reset()
    serializer.set_pause_between(0)

    class FakeVoiceCache:
        def __init__(self):
            self.states: list[VoiceState] = []

        def set_state(self, state: VoiceState) -> None:
            self.states.append(VoiceState(**asdict(state)))

    fake_cache = FakeVoiceCache()
    original_cache = serializer._voice_cache
    serializer._voice_cache = fake_cache

    try:
        result = serializer.run_serialized(
            VoiceMessage(text="Serializer cache integration", voice="Karen", rate=155),
            executor=lambda message: True,
        )
    finally:
        serializer._voice_cache = original_cache
        serializer.reset()
        serializer.set_pause_between(0.3)

    assert result is True
    assert any(state.queue_depth >= 1 for state in fake_cache.states)
    assert any(
        state.is_speaking and state.current_text == "Serializer cache integration"
        for state in fake_cache.states
    )
    assert fake_cache.states[-1] == VoiceState()
