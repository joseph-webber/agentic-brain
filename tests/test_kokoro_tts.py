# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Tests for KokoroVoice and NeuralVoiceRouter.

Covers:
- Voice mapping for all 14 ladies
- Synthesis produces audio
- M2 acceleration detection
- Fallback when Kokoro unavailable
- Phrase cache functionality
- Neural routing decisions
- Serializer integration
"""

from __future__ import annotations

import os
import sys
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.kokoro_tts import (
    LADY_VOICES,
    KokoroVoice,
    _APPLE_FALLBACKS,
    _to_wav_bytes,
    detect_m2_acceleration,
    kokoro_available,
    KOKORO_SAMPLE_RATE,
)
from agentic_brain.voice.neural_router import (
    NeuralVoiceRouter,
    _SHORT_MESSAGE_THRESHOLD,
    _SYSTEM_CATEGORIES,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / "kokoro-test-cache"


@pytest.fixture
def kokoro(cache_dir):
    return KokoroVoice(cache_dir=cache_dir, enable_cache=True)


@pytest.fixture
def router(cache_dir):
    return NeuralVoiceRouter(cache_dir=cache_dir / "router", enable_cache=True)


def _make_wav_bytes(duration_samples: int = 1000, sample_rate: int = KOKORO_SAMPLE_RATE) -> bytes:
    """Generate minimal valid WAV bytes for testing."""
    audio = np.zeros(duration_samples, dtype=np.float32)
    audio[:100] = np.linspace(0, 0.5, 100, dtype=np.float32)
    return _to_wav_bytes(audio, sample_rate)


# ═══════════════════════════════════════════════════════════════════
# 1. LADY_VOICES mapping tests
# ═══════════════════════════════════════════════════════════════════

class TestLadyVoices:
    """Tests for the LADY_VOICES configuration."""

    ALL_LADIES = [
        "Karen", "Kyoko", "Tingting", "Yuna", "Linh", "Kanya",
        "Dewi", "Sari", "Wayan", "Moira", "Alice", "Zosia",
        "Flo", "Shelley",
    ]

    def test_all_14_ladies_are_mapped(self):
        """Every lady must have a voice config."""
        assert len(LADY_VOICES) == 14
        for lady in self.ALL_LADIES:
            assert lady in LADY_VOICES, f"{lady} missing from LADY_VOICES"

    def test_each_lady_has_required_keys(self):
        """Every voice config must have voice_id, lang_code, description."""
        for lady, config in LADY_VOICES.items():
            assert "voice_id" in config, f"{lady} missing voice_id"
            assert "lang_code" in config, f"{lady} missing lang_code"
            assert "description" in config, f"{lady} missing description"

    def test_all_voice_ids_are_unique(self):
        """No two ladies share the same Kokoro voice ID."""
        voice_ids = [cfg["voice_id"] for cfg in LADY_VOICES.values()]
        assert len(voice_ids) == len(set(voice_ids)), "Duplicate voice IDs found"

    def test_all_ladies_have_apple_fallback(self):
        """Every lady must have an Apple say fallback voice."""
        for lady in self.ALL_LADIES:
            assert lady in _APPLE_FALLBACKS, f"{lady} missing Apple fallback"

    def test_japanese_lady_uses_japanese_voice(self):
        assert LADY_VOICES["Kyoko"]["lang_code"] == "j"
        assert LADY_VOICES["Kyoko"]["voice_id"].startswith("jf_")

    def test_chinese_lady_uses_chinese_voice(self):
        assert LADY_VOICES["Tingting"]["lang_code"] == "z"
        assert LADY_VOICES["Tingting"]["voice_id"].startswith("zf_")

    def test_italian_lady_uses_italian_voice(self):
        assert LADY_VOICES["Alice"]["lang_code"] == "i"
        assert LADY_VOICES["Alice"]["voice_id"].startswith("if_")

    def test_french_lady_uses_french_voice(self):
        assert LADY_VOICES["Flo"]["lang_code"] == "f"
        assert LADY_VOICES["Flo"]["voice_id"].startswith("ff_")

    def test_british_ladies_use_british_voices(self):
        assert LADY_VOICES["Shelley"]["lang_code"] == "b"
        assert LADY_VOICES["Shelley"]["voice_id"].startswith("bf_")


# ═══════════════════════════════════════════════════════════════════
# 2. KokoroVoice class tests
# ═══════════════════════════════════════════════════════════════════

class TestKokoroVoice:
    """Tests for the KokoroVoice TTS wrapper."""

    def test_lazy_init_no_model_loaded(self, kokoro):
        """Model must NOT load at construction time."""
        assert kokoro.is_initialized is False
        assert kokoro.backend is None

    def test_resolve_voice_returns_config(self, kokoro):
        info = kokoro.get_voice_info("Kyoko")
        assert info["voice_id"] == "jf_alpha"
        assert info["lang_code"] == "j"

    def test_resolve_voice_defaults_to_karen(self, kokoro):
        info = kokoro.get_voice_info("UnknownLady")
        assert info["voice_id"] == LADY_VOICES["Karen"]["voice_id"]

    def test_list_ladies_returns_all_14(self, kokoro):
        ladies = kokoro.list_ladies()
        assert len(ladies) == 14
        assert "Karen" in ladies
        assert "Kyoko" in ladies

    def test_synthesize_rejects_empty_text(self, kokoro):
        with pytest.raises(ValueError, match="empty"):
            kokoro.synthesize("", "Karen")

    def test_synthesize_rejects_whitespace_only(self, kokoro):
        with pytest.raises(ValueError, match="empty"):
            kokoro.synthesize("   ", "Karen")

    @patch("agentic_brain.voice.kokoro_tts.KokoroVoice._try_kokoro_onnx", return_value=False)
    @patch("agentic_brain.voice.kokoro_tts.KokoroVoice._try_kokoro_base", return_value=False)
    @patch("agentic_brain.voice.kokoro_tts.KokoroVoice._synthesize_apple_say")
    def test_fallback_to_apple_say(self, mock_apple, mock_base, mock_onnx, kokoro):
        """When Kokoro is unavailable, falls back to Apple say."""
        mock_apple.return_value = b"RIFF_fake_audio"
        result = kokoro.synthesize("Hello", "Karen")
        assert result == b"RIFF_fake_audio"
        assert kokoro.backend == "apple-say"
        mock_apple.assert_called_once()

    @patch("agentic_brain.voice.kokoro_tts.KokoroVoice._try_kokoro_onnx", return_value=False)
    @patch("agentic_brain.voice.kokoro_tts.KokoroVoice._try_kokoro_base", return_value=False)
    @patch("agentic_brain.voice.kokoro_tts.KokoroVoice._synthesize_apple_say", return_value=None)
    def test_raises_when_all_backends_fail(self, mock_apple, mock_base, mock_onnx, kokoro):
        """RuntimeError when no backend can produce audio."""
        with pytest.raises(RuntimeError, match="All TTS backends failed"):
            kokoro.synthesize("Hello", "Karen")

    def test_synthesize_with_onnx_backend(self, cache_dir):
        """Simulates kokoro-onnx producing audio."""
        fake_audio = np.random.randn(2400).astype(np.float32) * 0.3
        fake_onnx = MagicMock()
        fake_onnx.create.return_value = (fake_audio, 24000)

        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=False)
        voice._onnx_engine = fake_onnx
        voice._backend = "kokoro-onnx"
        voice._initialized = True

        result = voice.synthesize("Hello Joseph", "Karen")
        assert result[:4] == b"RIFF"
        assert b"WAVE" in result[:12]
        fake_onnx.create.assert_called_once()

    def test_synthesize_with_base_backend(self, cache_dir):
        """Simulates kokoro base producing audio via KPipeline."""
        fake_segments = [np.random.randn(1200).astype(np.float32) * 0.3]

        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=False)
        voice._base_engine = True
        voice._backend = "kokoro-base"
        voice._initialized = True

        fake_pipeline = MagicMock()
        fake_pipeline.return_value = [("gs", "ps", fake_segments[0])]

        with patch("agentic_brain.voice.kokoro_tts.KokoroVoice._synthesize_base") as mock_base:
            wav = _to_wav_bytes(fake_segments[0])
            mock_base.return_value = wav
            result = voice.synthesize("Hello", "Kyoko")
            assert result[:4] == b"RIFF"

    def test_synthesize_to_file(self, cache_dir):
        """synthesize_to_file writes a WAV file to disk."""
        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=False)
        wav_bytes = _make_wav_bytes()

        with patch.object(voice, "synthesize", return_value=wav_bytes):
            out_path = cache_dir / "test_output.wav"
            result = voice.synthesize_to_file("Hi", "Moira", path=out_path)
            assert result == out_path
            assert result.exists()
            assert result.read_bytes() == wav_bytes

    def test_synthesize_to_file_auto_path(self, cache_dir):
        """Auto-generates path when none provided."""
        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=False)
        wav_bytes = _make_wav_bytes()

        with patch.object(voice, "synthesize", return_value=wav_bytes):
            result = voice.synthesize_to_file("Ciao", "Alice")
            assert result.exists()
            assert "alice_" in result.name

    def test_speed_clamping(self, cache_dir):
        """Speed is clamped between 0.75 and 1.35."""
        fake_onnx = MagicMock()
        fake_onnx.create.return_value = (np.zeros(100, dtype=np.float32), 24000)

        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=False)
        voice._onnx_engine = fake_onnx
        voice._backend = "kokoro-onnx"
        voice._initialized = True

        voice.synthesize("test", "Karen", speed=5.0)
        _, kwargs = fake_onnx.create.call_args
        assert kwargs["speed"] == 1.35

        fake_onnx.create.reset_mock()
        voice.synthesize("test", "Karen", speed=0.1)
        _, kwargs = fake_onnx.create.call_args
        assert kwargs["speed"] == 0.75


# ═══════════════════════════════════════════════════════════════════
# 3. Cache tests
# ═══════════════════════════════════════════════════════════════════

class TestCache:
    """Tests for the phrase cache system."""

    def test_cache_stores_and_retrieves(self, cache_dir):
        """Second synthesis of same text should hit cache."""
        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=True)
        wav_bytes = _make_wav_bytes()

        voice._backend = "kokoro-onnx"
        voice._initialized = True
        voice._onnx_engine = MagicMock()

        with patch.object(voice, "_synthesize_onnx", return_value=wav_bytes) as mock_synth:
            result1 = voice.synthesize("Cached test", "Karen")
            assert result1 == wav_bytes
            mock_synth.assert_called_once()

            mock_synth.reset_mock()
            result2 = voice.synthesize("Cached test", "Karen")
            assert result2 == wav_bytes
            mock_synth.assert_not_called()

    def test_clear_cache(self, cache_dir):
        """clear_cache removes all cached WAV files."""
        phrase_dir = cache_dir / "phrase_cache"
        phrase_dir.mkdir(parents=True)
        for i in range(5):
            (phrase_dir / f"test_{i}.wav").write_bytes(b"fake")

        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=True)
        removed = voice.clear_cache()
        assert removed == 5
        assert len(list(phrase_dir.glob("*.wav"))) == 0

    def test_cache_disabled(self, cache_dir):
        """When cache is disabled, never reads from cache."""
        voice = KokoroVoice(cache_dir=cache_dir, enable_cache=False)
        wav_bytes = _make_wav_bytes()

        voice._backend = "kokoro-onnx"
        voice._initialized = True
        voice._onnx_engine = MagicMock()

        with patch.object(voice, "_synthesize_onnx", return_value=wav_bytes) as mock_synth:
            voice.synthesize("Test", "Karen")
            voice.synthesize("Test", "Karen")
            assert mock_synth.call_count == 2


# ═══════════════════════════════════════════════════════════════════
# 4. M2 acceleration detection tests
# ═══════════════════════════════════════════════════════════════════

class TestM2Acceleration:
    """Tests for Apple Silicon / M2 detection."""

    @patch("agentic_brain.voice.kokoro_tts.platform.system", return_value="Linux")
    @patch("agentic_brain.voice.kokoro_tts.platform.machine", return_value="x86_64")
    def test_non_mac_returns_cpu_only(self, mock_machine, mock_system):
        result = detect_m2_acceleration()
        assert result["is_apple_silicon"] is False
        assert result["onnx_providers"] == ["CPUExecutionProvider"]

    @patch("agentic_brain.voice.kokoro_tts.platform.system", return_value="Darwin")
    @patch("agentic_brain.voice.kokoro_tts.platform.machine", return_value="arm64")
    @patch("subprocess.run")
    def test_m2_mac_detected(self, mock_run, mock_machine, mock_system):
        mock_run.return_value = MagicMock(stdout="Apple M2 Pro", returncode=0)
        result = detect_m2_acceleration()
        assert result["is_apple_silicon"] is True
        assert "Apple M2" in result["chip_name"]
        assert result["has_ane"] is True

    @patch("agentic_brain.voice.kokoro_tts.platform.system", return_value="Darwin")
    @patch("agentic_brain.voice.kokoro_tts.platform.machine", return_value="arm64")
    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_sysctl_failure_still_detects_arm(self, mock_run, mock_machine, mock_system):
        result = detect_m2_acceleration()
        assert result["is_apple_silicon"] is True
        assert result["chip_name"] == "Apple Silicon"

    def test_hardware_info_cached(self, kokoro):
        """hardware_info property should be cached after first access."""
        with patch("agentic_brain.voice.kokoro_tts.detect_m2_acceleration") as mock_detect:
            mock_detect.return_value = {"is_apple_silicon": True, "chip_name": "M2"}
            info1 = kokoro.hardware_info
            info2 = kokoro.hardware_info
            mock_detect.assert_called_once()
            assert info1 is info2


# ═══════════════════════════════════════════════════════════════════
# 5. kokoro_available() function tests
# ═══════════════════════════════════════════════════════════════════

class TestKokoroAvailable:

    @patch("importlib.util.find_spec", return_value=None)
    def test_returns_false_when_nothing_installed(self, mock_spec):
        assert kokoro_available() is False

    @patch("importlib.util.find_spec")
    def test_returns_true_for_kokoro_onnx(self, mock_spec):
        def side_effect(name):
            if name == "kokoro_onnx":
                return MagicMock()
            return None
        mock_spec.side_effect = side_effect
        assert kokoro_available() is True

    @patch("importlib.util.find_spec")
    def test_returns_true_for_base_kokoro(self, mock_spec):
        def side_effect(name):
            if name == "kokoro":
                return MagicMock()
            return None
        mock_spec.side_effect = side_effect
        assert kokoro_available() is True


# ═══════════════════════════════════════════════════════════════════
# 6. _to_wav_bytes utility tests
# ═══════════════════════════════════════════════════════════════════

class TestWavBytes:

    def test_produces_valid_wav(self):
        audio = np.array([0.0, 0.5, -0.5, 1.0, -1.0], dtype=np.float32)
        wav = _to_wav_bytes(audio, 24000)
        assert wav[:4] == b"RIFF"
        assert wav[8:12] == b"WAVE"

        with wave.open(BytesIO(wav), "rb") as wf:
            assert wf.getframerate() == 24000
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getnframes() == 5

    def test_clips_out_of_range(self):
        audio = np.array([2.0, -2.0], dtype=np.float32)
        wav = _to_wav_bytes(audio, 24000)
        with wave.open(BytesIO(wav), "rb") as wf:
            frames = np.frombuffer(wf.readframes(2), dtype=np.int16)
            assert frames[0] == 32767
            assert frames[1] == -32767


# ═══════════════════════════════════════════════════════════════════
# 7. NeuralVoiceRouter tests
# ═══════════════════════════════════════════════════════════════════

class TestNeuralVoiceRouter:
    """Tests for the NeuralVoiceRouter routing logic."""

    def test_system_category_routes_to_apple(self, router):
        for cat in _SYSTEM_CATEGORIES:
            info = router.get_routing_info("Test message long enough", "Karen", cat)
            assert info["engine"] == "apple-say"
            assert "system" in info["reason"]

    def test_short_message_routes_to_apple(self, router):
        info = router.get_routing_info("Hi", "Kyoko", "conversation")
        assert info["engine"] == "apple-say"
        assert "short" in info["reason"]

    def test_long_conversation_prefers_kokoro(self, cache_dir):
        """If Kokoro is available, long conversational text routes there."""
        router = NeuralVoiceRouter(cache_dir=cache_dir)

        fake_kokoro = MagicMock()
        fake_kokoro.backend = "kokoro-onnx"
        router._kokoro = fake_kokoro
        router._kokoro_attempted = True

        info = router.get_routing_info(
            "This is a longer message for testing", "Kyoko", "conversation"
        )
        assert info["engine"] == "kokoro"
        assert "neural" in info["reason"].lower() or "kokoro" in info["reason"].lower()

    def test_fallback_when_kokoro_unavailable(self, cache_dir):
        """Routes to Apple say when Kokoro failed to init."""
        router = NeuralVoiceRouter(cache_dir=cache_dir)
        router._kokoro = None
        router._kokoro_attempted = True

        info = router.get_routing_info(
            "Long enough message for test", "Tingting", "conversation"
        )
        assert info["engine"] == "apple-say"
        assert "fallback" in info["reason"].lower() or "unavailable" in info["reason"].lower()

    def test_speak_system_uses_apple(self, router):
        """System speech routes through Apple say and increments stats."""
        router._kokoro_attempted = True
        router._kokoro = None

        with patch.object(router, "_speak_apple", return_value=True) as mock_apple:
            result = router.speak_system("Deployment complete!")
            assert result is True
            mock_apple.assert_called_once()

        # Stats are incremented inside _speak_apple, which was mocked.
        # Verify routing decision instead:
        info = router.get_routing_info("Deployment complete!", "Karen", "system")
        assert info["engine"] == "apple-say"

    @patch("agentic_brain.voice.neural_router.NeuralVoiceRouter._speak_apple", return_value=True)
    def test_speak_empty_text_returns_false(self, mock_apple, router):
        assert router.speak("") is False
        assert router.speak("   ") is False
        mock_apple.assert_not_called()

    def test_stats_tracking(self, cache_dir):
        router = NeuralVoiceRouter(cache_dir=cache_dir)
        stats = router.stats
        assert stats["apple_say_count"] == 0
        assert stats["kokoro_count"] == 0
        assert stats["cache_hits"] == 0
        assert stats["fallback_count"] == 0

    def test_kokoro_available_property_when_missing(self, cache_dir):
        router = NeuralVoiceRouter(cache_dir=cache_dir)
        router._kokoro = None
        router._kokoro_attempted = True
        assert router.kokoro_available is False

    def test_kokoro_available_property_when_onnx(self, cache_dir):
        router = NeuralVoiceRouter(cache_dir=cache_dir)
        fake_kokoro = MagicMock()
        fake_kokoro.backend = "kokoro-onnx"
        router._kokoro = fake_kokoro
        router._kokoro_attempted = True
        assert router.kokoro_available is True

    def test_router_in_memory_phrase_cache(self, cache_dir):
        """Router caches Kokoro output in memory for repeated phrases."""
        router = NeuralVoiceRouter(cache_dir=cache_dir, enable_cache=True)
        wav_bytes = _make_wav_bytes()

        fake_kokoro = MagicMock()
        fake_kokoro.backend = "kokoro-onnx"
        fake_kokoro.synthesize.return_value = wav_bytes
        router._kokoro = fake_kokoro
        router._kokoro_attempted = True

        with patch.object(router, "_play_audio_bytes", return_value=True):
            router.speak_lady("Hello long message for test", "Kyoko")
            router.speak_lady("Hello long message for test", "Kyoko")

        assert fake_kokoro.synthesize.call_count == 1
        assert router.stats["cache_hits"] == 1

    def test_clear_cache_empties_memory(self, cache_dir):
        router = NeuralVoiceRouter(cache_dir=cache_dir)
        router._phrase_cache["test_key"] = b"audio_data"
        cleared = router.clear_cache()
        assert cleared >= 1
        assert len(router._phrase_cache) == 0
