#!/usr/bin/env python3
"""Bridge script for faster-whisper transcription from Swift app."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from faster_whisper import WhisperModel

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_DIR = SCRIPT_DIR / ".cache" / "whisper"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe audio with faster-whisper.")
    parser.add_argument("audio_file", help="Path to audio file to transcribe")
    parser.add_argument("--model", default="tiny.en", help="faster-whisper model name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        print(f"Audio file not found: {audio_path}", file=sys.stderr)
        raise SystemExit(1)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8",
        download_root=str(CACHE_DIR),
    )

    segments, _ = model.transcribe(
        str(audio_path),
        language="en",
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=True,
        without_timestamps=True,
    )

    text = " ".join(segment.text for segment in segments).strip()
    print(text)


if __name__ == "__main__":
    main()
