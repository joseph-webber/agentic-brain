# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import sys
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import patch

import pytest

from agentic_brain.voice.transcription import (
    StreamingTranscriptionResult,
    TranscriptionResult,
    VADStreamingTranscriber,
    get_streaming_transcriber,
    get_vad_streaming_transcriber,
)

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a project dependency
    np = None  # type: ignore[assignment]

try:
    import pyaudio  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - manual script only
    pyaudio = None  # type: ignore[assignment]


SAMPLE_RATE = 16_000
CHUNK_SAMPLES = 1_600  # 100ms @ 16kHz


def _pcm_chunk(amplitude: int = 0, samples: int = CHUNK_SAMPLES) -> bytes:
    if np is None:
        raise RuntimeError("numpy is required for the VAD/whisper integration tests")
    return (np.full(samples, amplitude, dtype=np.int16)).tobytes()


class FakeStreamingTranscriber:
    def __init__(self) -> None:
        self.streaming_calls: list[bytes] = []
        self.reset_calls = 0
        self.transcribe_bytes_calls: list[bytes] = []
        self.config: dict[str, Any] = {}

    def configure_streaming(
        self,
        window_secs: float = 0.5,
        overlap_secs: float = 0.1,
        sample_rate: int = SAMPLE_RATE,
        enabled: bool = True,
    ) -> None:
        self.config = {
            "window_secs": window_secs,
            "overlap_secs": overlap_secs,
            "sample_rate": sample_rate,
            "enabled": enabled,
        }

    def transcribe_streaming(
        self,
        audio_chunk: bytes,
        sample_rate: int = SAMPLE_RATE,
    ) -> Iterable[StreamingTranscriptionResult]:
        self.streaming_calls.append(audio_chunk)
        yield StreamingTranscriptionResult(
            text=f"partial-{len(self.streaming_calls)}",
            confidence=0.91,
            segment_index=len(self.streaming_calls),
        )

    def transcribe_bytes(
        self,
        audio_data: bytes,
        sample_rate: int = SAMPLE_RATE,
    ) -> TranscriptionResult:
        self.transcribe_bytes_calls.append(audio_data)
        return TranscriptionResult(
            text="final transcript",
            confidence=0.97,
            duration_ms=(len(audio_data) / 2 / sample_rate) * 1000,
        )

    def reset_streaming(self) -> None:
        self.reset_calls += 1


class FakeVAD:
    def __init__(self, *, min_silence_duration_ms: int = 100) -> None:
        self.config = SimpleNamespace(
            min_silence_duration_ms=min_silence_duration_ms,
            window_size_samples=512,
        )

    def detect_speech(self, audio: Any):
        if np is None:
            return iter(())
        has_speech = bool(np.max(np.abs(audio)) > 0)
        return iter(({"start": 0, "end": len(audio)},) if has_speech else ())


def test_vad_streaming_transcriber_starts_on_speech_and_finalizes_on_end() -> None:
    transcriber = FakeStreamingTranscriber()
    vad = FakeVAD(min_silence_duration_ms=100)
    integration = VADStreamingTranscriber(
        transcriber=transcriber,
        vad=vad,
        sample_rate=SAMPLE_RATE,
        window_secs=0.5,
        overlap_secs=0.1,
        min_speech_duration_ms=100,
        min_silence_duration_ms=100,
        vad_window_ms=100,
    )

    start = integration.process_chunk(_pcm_chunk(amplitude=6_000))
    assert start.speech_started is True
    assert integration.speech_active is True
    assert len(start.partials) == 1
    assert transcriber.streaming_calls

    middle = integration.process_chunk(_pcm_chunk(amplitude=6_000))
    assert middle.speech_started is False
    assert len(middle.partials) == 1

    end = integration.process_chunk(_pcm_chunk(amplitude=0))
    assert end.speech_ended is True
    assert end.final is not None
    assert end.final.text == "final transcript"
    assert end.final.is_final is True
    assert end.final.stable_text == "final transcript"
    assert integration.speech_active is False
    assert transcriber.transcribe_bytes_calls


def test_get_streaming_transcriber_defaults_to_low_latency_settings() -> None:
    with patch("agentic_brain.voice.transcription.get_transcriber") as mock_get:
        mock_get.return_value = object()

        get_streaming_transcriber()

        kwargs = mock_get.call_args.kwargs
        assert kwargs["model_name"] == "tiny.en"
        assert kwargs["streaming_window_secs"] == pytest.approx(0.5)
        assert kwargs["streaming_overlap_secs"] == pytest.approx(0.1)
        assert kwargs["prefer_faster_whisper"] is True


def test_get_vad_streaming_transcriber_uses_vad_and_streaming_defaults() -> None:
    fake = FakeStreamingTranscriber()

    with patch(
        "agentic_brain.voice.transcription.get_streaming_transcriber",
        return_value=fake,
    ):
        integration = get_vad_streaming_transcriber()

    assert isinstance(integration, VADStreamingTranscriber)
    assert fake.config["window_secs"] == pytest.approx(0.5)
    assert fake.config["overlap_secs"] == pytest.approx(0.1)
    assert fake.config["sample_rate"] == SAMPLE_RATE


def _run_manual_microphone_demo() -> int:
    if pyaudio is None:
        print("PyAudio is not installed. Install with: pip install pyaudio", flush=True)
        return 1
    if np is None:
        print("NumPy is not installed.", flush=True)
        return 1

    pa = pyaudio.PyAudio()
    stream = None
    integration = None

    try:
        integration = get_vad_streaming_transcriber(
            model_name="tiny.en",
            sample_rate=SAMPLE_RATE,
            window_secs=0.5,
            overlap_secs=0.1,
            vad_threshold=0.5,
            min_speech_duration_ms=100,
            min_silence_duration_ms=200,
        )
        stream = pa.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SAMPLES,
        )

        print("Speak into your microphone. Press Ctrl+C to stop.", flush=True)
        while True:
            chunk = stream.read(CHUNK_SAMPLES, exception_on_overflow=False)
            update = integration.process_chunk(chunk)

            if update.speech_started:
                print("\n[Speech start]", flush=True)

            for partial in update.partials:
                if partial.text.strip():
                    print(f"[partial] {partial.text}", flush=True)

            if update.speech_ended:
                print("[Speech end]", flush=True)
                if update.final and update.final.text.strip():
                    print(f"[final] {update.final.text}", flush=True)

    except KeyboardInterrupt:
        print("\nStopping VAD/whisper integration demo.", flush=True)
        if integration is not None:
            final = integration.finalize()
            if final and final.text.strip():
                print(f"[final] {final.text}", flush=True)
        return 0
    finally:
        if stream is not None:
            stream.stop_stream()
            stream.close()
        pa.terminate()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manual Silero VAD + faster-whisper streaming integration demo.",
    )
    parser.parse_args(argv)
    return _run_manual_microphone_demo()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
