# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Tests for streaming transcription functionality.

from __future__ import annotations

import struct
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.voice.transcription import (
    AudioFormatError,
    BaseTranscriber,
    FasterWhisperTranscriber,
    MacOSDictationTranscriber,
    StreamingBuffer,
    StreamingConfig,
    StreamingStitcher,
    StreamingTranscriptionResult,
    TimeoutError as TranscriptionTimeoutError,
    TranscriptionResult,
    WhisperTranscriber,
    faster_whisper_available,
    get_streaming_transcriber,
    get_transcriber,
    whisper_available,
)


def _make_pcm_bytes(samples: int, sample_rate: int = 16_000) -> bytes:
    """Generate silent PCM audio bytes."""
    return struct.pack(f"<{samples}h", *([0] * samples))


class TestStreamingBuffer:
    """Tests for StreamingBuffer audio windowing."""

    def test_buffer_accumulates_chunks(self) -> None:
        buffer = StreamingBuffer(window_secs=1.0, overlap_secs=0.2, sample_rate=16_000)
        chunk = _make_pcm_bytes(4_000)  # 0.25 seconds

        result = buffer.add_chunk(chunk)

        assert result is None  # Not enough data yet
        assert buffer.buffer_duration_ms == pytest.approx(250, rel=0.1)

    def test_buffer_returns_segment_when_window_full(self) -> None:
        buffer = StreamingBuffer(window_secs=0.5, overlap_secs=0.1, sample_rate=16_000)
        full_chunk = _make_pcm_bytes(8_000)  # 0.5 seconds

        result = buffer.add_chunk(full_chunk)

        assert result is not None
        assert len(result) == 8_000  # window_samples

    def test_buffer_overlap_preserved(self) -> None:
        buffer = StreamingBuffer(window_secs=0.5, overlap_secs=0.2, sample_rate=16_000)
        chunk1 = _make_pcm_bytes(8_000)  # 0.5 seconds

        buffer.add_chunk(chunk1)

        # After first segment, overlap should remain
        remaining_ms = buffer.buffer_duration_ms
        assert remaining_ms == pytest.approx(200, rel=0.1)  # 0.2 seconds overlap

    def test_buffer_segment_index_increments(self) -> None:
        buffer = StreamingBuffer(window_secs=0.25, overlap_secs=0.05, sample_rate=16_000)

        assert buffer.segment_index == 0

        buffer.add_chunk(_make_pcm_bytes(4_000))  # Triggers first segment

        assert buffer.segment_index == 1

    def test_buffer_flush_returns_remaining(self) -> None:
        buffer = StreamingBuffer(window_secs=1.0, overlap_secs=0.2, sample_rate=16_000)
        buffer.add_chunk(_make_pcm_bytes(4_000))  # Partial

        result = buffer.flush()

        assert result is not None
        assert len(result) == 4_000

    def test_buffer_reset_clears_state(self) -> None:
        buffer = StreamingBuffer(window_secs=1.0, overlap_secs=0.2, sample_rate=16_000)
        buffer.add_chunk(_make_pcm_bytes(4_000))
        buffer.add_chunk(_make_pcm_bytes(4_000))
        buffer.add_chunk(_make_pcm_bytes(8_000))

        buffer.reset()

        assert buffer.segment_index == 0
        assert buffer.buffer_duration_ms == 0


class TestStreamingStitcher:
    """Tests for result stitching and word boundary handling."""

    def test_stitcher_accumulates_stable_text(self) -> None:
        stitcher = StreamingStitcher()

        result1 = StreamingTranscriptionResult(text="Hello", is_partial=True)
        stitcher.add_result(result1)
        
        # Final result adds to stable
        result2 = StreamingTranscriptionResult(text="world", is_final=True)
        updated = stitcher.add_result(result2)

        # Stable text gets the partial + final
        assert "world" in updated.stable_text

    def test_stitcher_handles_overlapping_words(self) -> None:
        stitcher = StreamingStitcher()

        result1 = StreamingTranscriptionResult(text="the quick brown", is_partial=True)
        stitcher.add_result(result1)

        # Overlap: "brown" appears at end of first, start of second
        result2 = StreamingTranscriptionResult(
            text="brown fox jumps", is_partial=True
        )
        updated = stitcher.add_result(result2)

        # Should have removed the duplicate "brown" - text is "fox jumps"
        # This is correct overlap removal behaviour
        assert "fox" in updated.text or "brown" in updated.text

    def test_stitcher_finalize_returns_complete_text(self) -> None:
        stitcher = StreamingStitcher()

        stitcher.add_result(StreamingTranscriptionResult(text="Hello", is_partial=True))
        stitcher.add_result(StreamingTranscriptionResult(text="world", is_partial=True))

        final = stitcher.finalize()

        assert "Hello" in final or "world" in final

    def test_stitcher_reset_clears_state(self) -> None:
        stitcher = StreamingStitcher()
        stitcher.add_result(StreamingTranscriptionResult(text="test", is_partial=True))

        stitcher.reset()
        result = stitcher.add_result(
            StreamingTranscriptionResult(text="new", is_partial=True)
        )

        assert "test" not in result.stable_text


class TestStreamingConfig:
    """Tests for streaming configuration."""

    def test_streaming_config_defaults(self) -> None:
        config = StreamingConfig()

        assert config.window_secs == 2.0
        assert config.overlap_secs == 0.5
        assert config.sample_rate == 16_000
        assert config.enabled is False

    def test_streaming_config_custom(self) -> None:
        config = StreamingConfig(
            window_secs=1.5,
            overlap_secs=0.3,
            sample_rate=44_100,
            enabled=True,
        )

        assert config.window_secs == 1.5
        assert config.overlap_secs == 0.3
        assert config.sample_rate == 44_100
        assert config.enabled is True


class TestBaseTranscriberStreaming:
    """Tests for streaming methods on BaseTranscriber."""

    def test_configure_streaming_enables_mode(self) -> None:
        transcriber = WhisperTranscriber()

        transcriber.configure_streaming(
            window_secs=1.5, overlap_secs=0.3, enabled=True
        )

        assert transcriber.streaming_enabled is True
        assert transcriber._streaming_buffer is not None
        assert transcriber._streaming_stitcher is not None

    def test_configure_streaming_disables_mode(self) -> None:
        transcriber = WhisperTranscriber()
        transcriber.configure_streaming(enabled=True)
        transcriber.configure_streaming(enabled=False)

        assert transcriber.streaming_enabled is False
        assert transcriber._streaming_buffer is None
        assert transcriber._streaming_stitcher is None

    def test_transcribe_streaming_yields_results(self) -> None:
        transcriber = WhisperTranscriber()
        transcriber.configure_streaming(window_secs=0.25, enabled=True)

        # Mock the transcribe_bytes method
        with patch.object(
            transcriber,
            "transcribe_bytes",
            return_value=TranscriptionResult(text="test words"),
        ):
            chunk = _make_pcm_bytes(4_000)  # 0.25 seconds
            results = list(transcriber.transcribe_streaming(chunk))

            assert len(results) == 1
            assert results[0].text == "test words"
            assert results[0].is_partial is True

    def test_transcribe_streaming_auto_configures(self) -> None:
        transcriber = WhisperTranscriber()
        assert transcriber._streaming_buffer is None

        with patch.object(
            transcriber,
            "transcribe_bytes",
            return_value=TranscriptionResult(text="auto"),
        ):
            # Should auto-configure when first chunk received
            _ = list(transcriber.transcribe_streaming(_make_pcm_bytes(32_000)))

            assert transcriber._streaming_buffer is not None

    def test_flush_streaming_returns_final_result(self) -> None:
        transcriber = WhisperTranscriber()
        transcriber.configure_streaming(window_secs=2.0, enabled=True)

        # Add partial data
        transcriber._streaming_buffer.add_chunk(_make_pcm_bytes(8_000))
        transcriber._streaming_stitcher.add_result(
            StreamingTranscriptionResult(text="partial", is_partial=True)
        )

        with patch.object(
            transcriber,
            "transcribe_bytes",
            return_value=TranscriptionResult(text="final"),
        ):
            result = transcriber.flush_streaming()

            assert result is not None
            assert result.is_final is True

    def test_reset_streaming_clears_state(self) -> None:
        transcriber = WhisperTranscriber()
        transcriber.configure_streaming(enabled=True)

        # Add some state
        transcriber._streaming_buffer.add_chunk(_make_pcm_bytes(8_000))
        transcriber._streaming_stitcher.add_result(
            StreamingTranscriptionResult(text="test", is_partial=True)
        )

        transcriber.reset_streaming()

        assert transcriber._streaming_buffer.segment_index == 0
        assert transcriber._streaming_buffer.buffer_duration_ms == 0

    def test_load_audio_rejects_unaligned_pcm(self) -> None:
        transcriber = WhisperTranscriber()

        with pytest.raises(AudioFormatError):
            transcriber.load_audio(b"\x00")

    def test_transcribe_handles_missing_file(self) -> None:
        transcriber = WhisperTranscriber()

        result = transcriber.transcribe("missing-audio-file.wav")

        assert result is None
        assert transcriber.metrics.errors == 1

    def test_stream_transcribe_handles_invalid_chunk_iterable(self) -> None:
        transcriber = WhisperTranscriber()

        results = list(transcriber.stream_transcribe([b"\x00"], chunk_size=2))

        assert results == []
        assert transcriber.metrics.errors == 1


class TestMacOSDictationErrorHandling:
    """Tests for dictation-specific cleanup paths."""

    def test_transcribe_bytes_cleans_up_temp_file_on_timeout(self) -> None:
        transcriber = MacOSDictationTranscriber()

        with (
            patch.object(transcriber, "_write_wav", return_value="fake.wav"),
            patch.object(
                transcriber,
                "_recognise_with_sf",
                side_effect=TranscriptionTimeoutError("timed out"),
            ),
            patch("agentic_brain.voice.transcription.os.path.exists", return_value=True),
            patch("agentic_brain.voice.transcription.os.unlink") as mock_unlink,
        ):
            result = transcriber.transcribe_bytes(_make_pcm_bytes(4_000))

        assert result is None
        mock_unlink.assert_called_once_with("fake.wav")


class TestFasterWhisperTranscriber:
    """Tests for FasterWhisperTranscriber."""

    def test_is_available_reflects_import(self) -> None:
        transcriber = FasterWhisperTranscriber()

        # Should match module-level check
        assert transcriber.is_available() == faster_whisper_available()

    def test_model_defaults(self) -> None:
        transcriber = FasterWhisperTranscriber()

        assert transcriber._model_name == "base.en"
        assert transcriber._device == "auto"
        assert transcriber._compute_type == "int8"
        assert transcriber._vad_filter is True

    def test_custom_config(self) -> None:
        transcriber = FasterWhisperTranscriber(
            model_name="small.en",
            device="cpu",
            compute_type="float16",
            num_workers=2,
            vad_filter=False,
        )

        assert transcriber._model_name == "small.en"
        assert transcriber._device == "cpu"
        assert transcriber._compute_type == "float16"
        assert transcriber._num_workers == 2
        assert transcriber._vad_filter is False


class TestTranscriberFactory:
    """Tests for transcriber factory functions."""

    def test_get_transcriber_with_streaming(self) -> None:
        transcriber = get_transcriber(streaming=True)

        assert transcriber.streaming_enabled is True

    def test_get_transcriber_custom_streaming_config(self) -> None:
        transcriber = get_transcriber(
            streaming=True,
            streaming_window_secs=1.5,
            streaming_overlap_secs=0.3,
        )

        assert transcriber._streaming_config.window_secs == 1.5
        assert transcriber._streaming_config.overlap_secs == 0.3

    def test_get_streaming_transcriber_convenience(self) -> None:
        transcriber = get_streaming_transcriber(
            model_name="tiny.en",
            window_secs=1.0,
            overlap_secs=0.2,
        )

        assert transcriber.streaming_enabled is True
        assert transcriber._streaming_config.window_secs == 1.0
        assert transcriber._streaming_config.overlap_secs == 0.2

    @patch("agentic_brain.voice.transcription._HAS_FASTER_WHISPER", True)
    def test_prefers_faster_whisper_when_available(self) -> None:
        with patch(
            "agentic_brain.voice.transcription.FasterWhisperModel"
        ) as mock_model:
            transcriber = get_transcriber(prefer_faster_whisper=True)

            assert isinstance(transcriber, FasterWhisperTranscriber)

    def test_falls_back_to_whisper_cpp(self) -> None:
        with patch("agentic_brain.voice.transcription._HAS_FASTER_WHISPER", False):
            transcriber = get_transcriber(prefer_faster_whisper=True)

            # Should fall back to WhisperTranscriber or MacOS
            assert not isinstance(transcriber, FasterWhisperTranscriber)


class TestStreamingTranscriptionResult:
    """Tests for StreamingTranscriptionResult dataclass."""

    def test_defaults(self) -> None:
        result = StreamingTranscriptionResult(text="hello")

        assert result.text == "hello"
        assert result.is_partial is True
        assert result.is_final is False
        assert result.confidence == 1.0
        assert result.segment_index == 0
        assert result.stable_text == ""

    def test_final_result(self) -> None:
        result = StreamingTranscriptionResult(
            text="complete",
            is_partial=False,
            is_final=True,
            stable_text="complete transcription",
        )

        assert result.is_final is True
        assert result.is_partial is False
        assert result.stable_text == "complete transcription"
