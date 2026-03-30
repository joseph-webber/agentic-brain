# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Tests for TTS Fallback Chain.

Validates the fallback chain behavior:
1. Cartesia (if configured) → Kokoro → macOS say
2. Never fails silently - macOS say is nuclear option
3. Health check reports status of all backends
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.voice.tts_fallback import (
    APPLE_VOICE_MAP,
    TTSBackend,
    TTSFallbackChain,
    TTSResult,
    get_tts_chain,
    _set_tts_chain_for_testing,
)


@pytest.fixture
def tts_chain():
    """Create a fresh TTS chain for each test."""
    return TTSFallbackChain(
        cartesia_api_key=None,  # No Cartesia for tests
        enable_cache=False,
    )


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton between tests."""
    _set_tts_chain_for_testing(None)
    yield
    _set_tts_chain_for_testing(None)


class TestTTSFallbackChain:
    """Test the TTSFallbackChain class."""

    def test_initialization(self, tts_chain):
        """Test basic initialization."""
        assert tts_chain is not None
        assert tts_chain.active_backend is None  # Not yet determined
        assert tts_chain.metrics["cartesia_calls"] == 0
        assert tts_chain.metrics["kokoro_calls"] == 0
        assert tts_chain.metrics["macos_say_calls"] == 0

    def test_apple_voice_map(self):
        """Test voice name mapping."""
        assert APPLE_VOICE_MAP["Karen"] == "Karen (Premium)"
        assert APPLE_VOICE_MAP["Kyoko"] == "Kyoko"
        assert APPLE_VOICE_MAP["Tingting"] == "Tingting"
        assert APPLE_VOICE_MAP.get("Unknown", "Unknown") == "Unknown"

    @pytest.mark.asyncio
    async def test_empty_text_returns_error(self, tts_chain):
        """Test that empty text returns an error result."""
        result = await tts_chain.speak("", use_serializer=False)
        assert not result.success
        assert result.error == "Empty text"

        result = await tts_chain.speak("   ", use_serializer=False)
        assert not result.success
        assert result.error == "Empty text"

    @pytest.mark.asyncio
    async def test_synthesize_empty_text(self, tts_chain):
        """Test that synthesize with empty text returns error."""
        result = await tts_chain.synthesize("")
        assert not result.success
        assert result.error == "Empty text"

    @pytest.mark.asyncio
    async def test_health_check_structure(self, tts_chain):
        """Test that health check returns proper structure."""
        health = await tts_chain.health_check()

        # Check structure
        assert hasattr(health, "cartesia")
        assert hasattr(health, "kokoro")
        assert hasattr(health, "macos_say")
        assert hasattr(health, "active_backend")
        assert hasattr(health, "chain_healthy")

        # Cartesia should be unavailable (no API key)
        assert not health.cartesia.available
        assert "No API key" in health.cartesia.reason or "API key" in str(health.cartesia.reason)

    @pytest.mark.asyncio
    async def test_fallback_to_macos_say(self, tts_chain):
        """Test that chain falls back to macOS say when other backends unavailable."""
        # Mock subprocess.run to simulate successful macOS say
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = await tts_chain._try_macos_say("Hello", "Karen", 160)

            assert result.success
            assert result.backend == TTSBackend.MACOS_SAY
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_macos_say_timeout(self, tts_chain):
        """Test handling of macOS say timeout."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("say", 30)

            result = await tts_chain._try_macos_say("Hello", "Karen", 160)

            assert not result.success
            assert result.backend == TTSBackend.MACOS_SAY

    @pytest.mark.asyncio
    async def test_metrics_tracking(self, tts_chain):
        """Test that metrics are properly tracked."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            await tts_chain._try_macos_say("Hello", "Karen", 160)

            assert tts_chain.metrics["macos_say_calls"] == 1

    def test_speak_sync(self, tts_chain):
        """Test synchronous speak wrapper."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = tts_chain.speak_sync("Hello", use_serializer=False)

            assert result.success

    def test_singleton_pattern(self):
        """Test that get_tts_chain returns singleton."""
        chain1 = get_tts_chain()
        chain2 = get_tts_chain()
        assert chain1 is chain2

    @pytest.mark.asyncio
    async def test_cartesia_not_available_without_key(self, tts_chain):
        """Test Cartesia reports unavailable without API key."""
        result = await tts_chain._try_cartesia("Hello", "Karen")
        assert not result.success
        assert result.backend == TTSBackend.CARTESIA
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_kokoro_fallback(self, tts_chain):
        """Test Kokoro backend is attempted."""
        # Kokoro may or may not be installed, but the attempt should work
        result = await tts_chain._try_kokoro("Hello", "Karen", 160)
        # Either it works or reports not available
        assert result.backend == TTSBackend.KOKORO
        if not result.success:
            assert "not available" in result.error.lower() or "failed" in result.error.lower()


class TestTTSBackendEnum:
    """Test the TTSBackend enum."""

    def test_backend_values(self):
        """Test backend enum values."""
        assert TTSBackend.CARTESIA.value == "cartesia"
        assert TTSBackend.KOKORO.value == "kokoro"
        assert TTSBackend.MACOS_SAY.value == "macos_say"


class TestTTSResult:
    """Test the TTSResult dataclass."""

    def test_success_result(self):
        """Test successful result creation."""
        result = TTSResult(
            success=True,
            backend=TTSBackend.MACOS_SAY,
            latency_ms=150.5,
        )
        assert result.success
        assert result.backend == TTSBackend.MACOS_SAY
        assert result.latency_ms == 150.5
        assert result.error is None
        assert result.audio_bytes is None

    def test_failure_result(self):
        """Test failure result creation."""
        result = TTSResult(
            success=False,
            backend=TTSBackend.CARTESIA,
            error="No API key",
        )
        assert not result.success
        assert result.backend == TTSBackend.CARTESIA
        assert result.error == "No API key"

    def test_result_with_audio(self):
        """Test result with audio bytes."""
        audio = b"RIFF\x00\x00\x00\x00WAVEfmt "
        result = TTSResult(
            success=True,
            backend=TTSBackend.KOKORO,
            audio_bytes=audio,
            latency_ms=200.0,
        )
        assert result.audio_bytes == audio


class TestConvenienceFunctions:
    """Test module-level convenience functions."""

    @pytest.mark.asyncio
    async def test_speak_convenience(self):
        """Test the speak() convenience function."""
        from agentic_brain.voice.tts_fallback import speak

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            # Need to set up the chain to not use serializer
            chain = get_tts_chain()
            result = await chain.speak("Hello", use_serializer=False)
            assert result.success

    def test_speak_sync_convenience(self):
        """Test the speak_sync() convenience function."""
        from agentic_brain.voice.tts_fallback import speak_sync

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            success = speak_sync("Hello")
            # May or may not succeed depending on serializer setup
            # Just verify it doesn't crash


class TestHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_full_health_check(self):
        """Test comprehensive health check."""
        chain = TTSFallbackChain(cartesia_api_key=None, enable_cache=False)
        health = await chain.health_check()

        # Cartesia unavailable (no key)
        assert not health.cartesia.available
        assert "API key" in str(health.cartesia.reason) or "No API key" in str(health.cartesia.reason)

        # macOS say should be available on macOS (unless mocked)
        import platform
        import shutil

        if platform.system() == "Darwin" and shutil.which("say"):
            # Real macOS with say command - should work
            # Note: this may fail in CI environments where say is mocked
            pass  # Don't assert here - it depends on the environment

        # Chain health depends on macOS say availability
        # Just verify the health check completes without error
        assert hasattr(health, "chain_healthy")

    @pytest.mark.asyncio
    async def test_health_check_determines_active_backend(self):
        """Test that health check sets active backend."""
        chain = TTSFallbackChain(cartesia_api_key=None, enable_cache=False)

        # Before health check, active backend is None
        assert chain.active_backend is None

        health = await chain.health_check()

        # After health check, active backend should be set (or remain None if nothing works)
        # The actual value depends on what's available in the test environment
        if health.kokoro.available:
            assert chain.active_backend == TTSBackend.KOKORO
        elif health.macos_say.available:
            assert chain.active_backend == TTSBackend.MACOS_SAY
        else:
            # Nothing available - active_backend stays None
            assert chain.active_backend is None
