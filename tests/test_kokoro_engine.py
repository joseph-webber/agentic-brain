# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

from __future__ import annotations

import os
import sys
import wave
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../src"))

from agentic_brain.voice.kokoro_engine import (
    KOKORO_SAMPLE_RATE,
    LADY_LANGUAGES,
    LADY_VOICE_MAP,
    OFFICIAL_KOKORO_VOICES,
    HybridVoiceRouter,
    KokoroEngine,
    get_official_kokoro_voice_ids,
)


class _FakePipeline:
    def __init__(self, lang_code: str):
        self.lang_code = lang_code
        self.calls = []

    def __call__(self, text: str, voice: str, speed: float = 1.0):
        self.calls.append((text, voice, speed))
        yield ("gs-1", "ps-1", np.array([0.0, 0.25, -0.25], dtype=np.float32))
        yield ("gs-2", "ps-2", np.array([0.5, -0.5], dtype=np.float32))


class TestKokoroCatalogue:
    def test_official_voice_ids_are_documented(self):
        assert "jf_alpha" in OFFICIAL_KOKORO_VOICES["ja"]
        assert "zf_xiaoxiao" in OFFICIAL_KOKORO_VOICES["zh"]
        assert "bf_emma" in OFFICIAL_KOKORO_VOICES["en-gb"]
        assert "if_sara" in OFFICIAL_KOKORO_VOICES["it"]
        assert "ff_siwis" in OFFICIAL_KOKORO_VOICES["fr"]

    def test_voice_catalogue_filter(self):
        filtered = get_official_kokoro_voice_ids("ja")
        assert filtered == {"ja": OFFICIAL_KOKORO_VOICES["ja"]}

    def test_ladies_have_unique_voice_routes(self):
        conversational_voices = {
            name: config.voice
            for name, config in LADY_VOICE_MAP.items()
            if config.engine == "kokoro"
        }
        assert len(conversational_voices) == len(set(conversational_voices.values()))
        assert LADY_LANGUAGES["Kyoko"] == "Japanese"
        assert LADY_LANGUAGES["Alice"] == "Italian"


class TestKokoroEngine:
    @patch("agentic_brain.voice.kokoro_engine.importlib.util.find_spec")
    def test_is_available_requires_model_and_package(self, find_spec_mock, tmp_path):
        find_spec_mock.return_value = object()
        model_path = tmp_path / "kokoro-82m"
        engine = KokoroEngine(model_path=model_path)

        assert engine.is_available() is False

        model_path.mkdir()
        assert engine.is_available() is True

    @patch("agentic_brain.voice.kokoro_engine.importlib.import_module")
    def test_load_downloads_model_when_missing(self, import_module_mock, tmp_path):
        engine = KokoroEngine(model_path=tmp_path / "kokoro-82m")
        engine._download_model = MagicMock()
        import_module_mock.return_value = SimpleNamespace()

        engine.load()

        engine._download_model.assert_called_once()
        import_module_mock.assert_called_with("kokoro")

    @patch("agentic_brain.voice.kokoro_engine.importlib.import_module")
    def test_synthesize_returns_wav_bytes(self, import_module_mock, tmp_path):
        pipeline = _FakePipeline(lang_code="j")
        import_module_mock.return_value = SimpleNamespace(KPipeline=lambda **kwargs: pipeline)

        engine = KokoroEngine(model_path=tmp_path / "kokoro-82m")
        engine.model_path.mkdir()
        audio_bytes = engine.synthesize("こんにちは", voice="jf_alpha", language="ja")

        assert audio_bytes.startswith(b"RIFF")
        assert audio_bytes[8:12] == b"WAVE"
        with wave.open(BytesIO(audio_bytes), "rb") as wav_file:
            assert wav_file.getframerate() == KOKORO_SAMPLE_RATE
            assert wav_file.getnchannels() == 1
        assert pipeline.lang_code == "j"

    @patch("agentic_brain.voice.kokoro_engine.importlib.import_module")
    def test_render_to_path_creates_cached_wav(self, import_module_mock, tmp_path):
        pipeline = _FakePipeline(lang_code="z")
        import_module_mock.return_value = SimpleNamespace(KPipeline=lambda **kwargs: pipeline)

        engine = KokoroEngine(model_path=tmp_path / "kokoro-82m")
        engine.model_path.mkdir()
        output_path = engine.render_to_path("你好", voice="zf_xiaoxiao", language="zh")

        assert output_path.exists()
        with wave.open(str(output_path), "rb") as wav_file:
            assert wav_file.getframerate() == KOKORO_SAMPLE_RATE
            assert wav_file.getnchannels() == 1

    def test_resolve_lang_code_uses_voice_prefix(self, tmp_path):
        engine = KokoroEngine(model_path=tmp_path / "kokoro-82m")
        assert engine._resolve_lang_code("jf_alpha", "unknown") == "j"
        assert engine._resolve_lang_code("bf_emma", "unknown") == "b"


class TestHybridVoiceRouter:
    def test_speak_uses_apple_for_karen(self):
        serializer = SimpleNamespace(
            run_serialized=lambda message, executor, wait: executor(message)
        )
        with patch("agentic_brain.voice.kokoro_engine.get_voice_serializer", return_value=serializer):
            router = HybridVoiceRouter(kokoro=MagicMock())
            with patch.object(router, "_speak_with_apple", return_value=True) as apple_mock:
                assert router.speak("Hello", lady="Karen") is True
                apple_mock.assert_called_once_with("Hello", "Karen (Premium)", 155)

    def test_speak_uses_kokoro_for_supported_lady(self, tmp_path):
        serializer = SimpleNamespace(
            run_serialized=lambda message, executor, wait: executor(message)
        )
        kokoro = MagicMock()
        kokoro.render_to_path.return_value = tmp_path / "kyoko.wav"
        kokoro.render_to_path.return_value.write_bytes(b"wav")
        with patch("agentic_brain.voice.kokoro_engine.get_voice_serializer", return_value=serializer):
            router = HybridVoiceRouter(kokoro=kokoro)
            with patch.object(router, "_play_audio", return_value=True) as play_mock:
                assert router.speak("こんにちは", lady="Kyoko", rate=170) is True
                kokoro.render_to_path.assert_called_once()
                call = kokoro.render_to_path.call_args.kwargs
                assert call["voice"] == "jf_alpha"
                assert call["language"] == "ja"
                assert call["speed"] > 1.0
                play_mock.assert_called_once()

    def test_speak_falls_back_to_apple_when_kokoro_fails(self):
        serializer = SimpleNamespace(
            run_serialized=lambda message, executor, wait: executor(message)
        )
        kokoro = MagicMock()
        kokoro.render_to_path.side_effect = RuntimeError("boom")
        with patch("agentic_brain.voice.kokoro_engine.get_voice_serializer", return_value=serializer):
            router = HybridVoiceRouter(kokoro=kokoro)
            with patch.object(router, "_speak_with_apple", return_value=True) as apple_mock:
                assert router.speak("Cześć", lady="Zosia") is True
                apple_mock.assert_called_once_with("Cześć", "Zosia", 155)

    def test_teach_phrase_uses_native_voice_for_middle_step(self):
        router = HybridVoiceRouter(kokoro=MagicMock())
        with patch.object(router, "speak", side_effect=[True, True, True]) as speak_mock:
            assert router.teach_phrase("Good morning", "おはよう", lady="Kyoko") is True
            assert speak_mock.call_args_list[0].kwargs == {"lady": "Karen"}
            assert speak_mock.call_args_list[1].kwargs == {
                "lady": "Kyoko",
                "use_native_voice": True,
            }
            assert speak_mock.call_args_list[2].kwargs == {"lady": "Karen"}
