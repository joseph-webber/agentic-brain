#!/usr/bin/env python3
"""
voice_input.py — Python wrapper for VoiceInput.app

Usage:
    text = voice_input.transcribe(timeout=10)
    python3 voice_input.py [timeout_seconds]

Exit codes from the Swift app:
    0  = transcript printed to stdout
    1  = permission denied or audio engine error
    2  = no speech detected within timeout
"""
import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
VOICE_BINARY = os.path.join(_DIR, "VoiceInput.app", "Contents", "MacOS", "VoiceInput")


def transcribe(timeout: int = 10) -> str | None:
    """
    Listen for speech and return the transcript string.
    Returns None if no speech was detected or on error.
    Diagnostic messages go to stderr; only the transcript comes via stdout.
    """
    if not os.path.isfile(VOICE_BINARY):
        print(
            f"VoiceInput binary not found: {VOICE_BINARY}\n"
            f"Run:  cd {_DIR} && ./build.sh",
            file=sys.stderr,
        )
        return None

    try:
        result = subprocess.run(
            [VOICE_BINARY, str(timeout)],
            capture_output=True,
            text=True,
        )
        # Mirror stderr (debug/status lines) to our stderr
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)

        if result.returncode == 0:
            return result.stdout.strip() or None
        elif result.returncode == 2:
            return None  # timeout / no speech — not an error
        else:
            return None
    except Exception as exc:
        print(f"voice_input error: {exc}", file=sys.stderr)
        return None


if __name__ == "__main__":
    timeout_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    transcript = transcribe(timeout_arg)
    if transcript:
        print(transcript)
        sys.exit(0)
    else:
        sys.exit(2)
