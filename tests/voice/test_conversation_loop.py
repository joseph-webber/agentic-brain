# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Tests for VoiceConversationLoop.

"""Tests for the voice conversation loop orchestrator."""

from __future__ import annotations

import asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.voice.conversation_loop import (
    ConversationConfig,
    ConversationMetrics,
    ConversationState,
    VoiceConversationLoop,
    get_conversation_loop,
)


class TestConversationConfig:
    """Tests for ConversationConfig dataclass."""

    def test_default_config(self) -> None:
        config = ConversationConfig()
        assert config.sample_rate == 16_000
        assert config.channels == 1
        assert config.llm_backend == "ollama"
        assert config.voice == "Karen"
        assert config.rate == 160
        assert config.use_cartesia is False

    def test_custom_config(self) -> None:
        config = ConversationConfig(
            sample_rate=44100,
            llm_backend="claude",
            voice="Moira",
            rate=180,
            use_cartesia=True,
        )
        assert config.sample_rate == 44100
        assert config.llm_backend == "claude"
        assert config.voice == "Moira"
        assert config.rate == 180
        assert config.use_cartesia is True


class TestConversationMetrics:
    """Tests for ConversationMetrics."""

    def test_initial_metrics(self) -> None:
        metrics = ConversationMetrics()
        assert metrics.utterances == 0
        assert metrics.responses == 0
        assert metrics.interruptions == 0
        assert metrics.avg_latency_ms == 0.0

    def test_record_latency(self) -> None:
        metrics = ConversationMetrics()
        metrics.record_latency(100.0)
        metrics.record_latency(200.0)
        assert metrics.avg_latency_ms == 150.0

    def test_to_dict(self) -> None:
        metrics = ConversationMetrics()
        metrics.utterances = 5
        metrics.responses = 4
        metrics.record_latency(250.0)
        
        data = metrics.to_dict()
        assert data["utterances"] == 5
        assert data["responses"] == 4
        assert data["avg_latency_ms"] == 250.0


class TestVoiceConversationLoop:
    """Tests for VoiceConversationLoop."""

    def test_init_default_config(self) -> None:
        loop = VoiceConversationLoop()
        assert loop.config.llm_backend == "ollama"
        assert loop.state == ConversationState.IDLE
        assert not loop.is_running

    def test_init_custom_config(self) -> None:
        config = ConversationConfig(voice="Moira", rate=180)
        loop = VoiceConversationLoop(config)
        assert loop.config.voice == "Moira"
        assert loop.config.rate == 180

    def test_state_transitions(self) -> None:
        loop = VoiceConversationLoop()
        states_observed: List[ConversationState] = []

        def track_state(state: ConversationState) -> None:
            states_observed.append(state)

        loop.on_state_change(track_state)
        loop._set_state(ConversationState.LISTENING)
        loop._set_state(ConversationState.PROCESSING)
        loop._set_state(ConversationState.SPEAKING)
        loop._set_state(ConversationState.IDLE)

        assert states_observed == [
            ConversationState.LISTENING,
            ConversationState.PROCESSING,
            ConversationState.SPEAKING,
            ConversationState.IDLE,
        ]

    def test_metrics_access(self) -> None:
        loop = VoiceConversationLoop()
        metrics = loop.metrics
        assert isinstance(metrics, ConversationMetrics)

    @patch("agentic_brain.voice.conversation_loop._HAS_PYAUDIO", False)
    def test_init_audio_without_pyaudio(self) -> None:
        loop = VoiceConversationLoop()
        result = loop._init_audio()
        assert result is False

    def test_init_vad(self) -> None:
        loop = VoiceConversationLoop()
        loop._init_vad()
        # VAD may or may not be available depending on environment
        # Just ensure no exceptions
        assert True

    def test_init_live_mode(self) -> None:
        loop = VoiceConversationLoop()
        loop._init_live_mode()
        assert loop._live_mode is not None

    def test_callbacks_registered(self) -> None:
        loop = VoiceConversationLoop()
        
        transcript_received: List[str] = []
        response_received: List[str] = []
        
        loop.on_transcript(lambda t: transcript_received.append(t))
        loop.on_response(lambda r: response_received.append(r))
        
        # Trigger callbacks directly
        if loop._on_transcript:
            loop._on_transcript("Hello")
        if loop._on_response:
            loop._on_response("Hi there!")
        
        assert transcript_received == ["Hello"]
        assert response_received == ["Hi there!"]


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_conversation_loop_returns_singleton(self) -> None:
        # Reset singleton for test
        import agentic_brain.voice.conversation_loop as module
        module._conversation_loop = None
        
        loop1 = get_conversation_loop()
        loop2 = get_conversation_loop()
        assert loop1 is loop2


@pytest.mark.asyncio
class TestAsyncMethods:
    """Tests for async methods."""

    async def test_transcribe_without_transcriber(self) -> None:
        loop = VoiceConversationLoop()
        loop._transcriber = None
        result = await loop._transcribe([b"\x00\x00" * 1000])
        assert result is None

    async def test_get_llm_response_with_callback(self) -> None:
        config = ConversationConfig(
            response_callback=lambda t: f"Echo: {t}"
        )
        loop = VoiceConversationLoop(config)
        response = await loop._get_llm_response("Hello")
        assert response == "Echo: Hello"

    async def test_get_llm_response_without_llm(self) -> None:
        loop = VoiceConversationLoop()
        loop._llm_client = None
        response = await loop._get_llm_response("Hello")
        assert response == "I heard: Hello"

    async def test_stop_when_not_running(self) -> None:
        loop = VoiceConversationLoop()
        # Should not raise
        await loop.stop()
        assert loop.state == ConversationState.IDLE
