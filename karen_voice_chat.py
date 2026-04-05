#!/usr/bin/env python3
"""Simple voice chat with Karen using sox for recording (bypasses TCC)."""

import subprocess
import sys
from pathlib import Path

# Load env
from dotenv import load_dotenv
load_dotenv(Path.home() / "brain" / ".env")

# Use robust audio utilities that fix AirPods Max + Whisper hallucination issues
from audio_utils import (
    record_audio as _record_audio,
    transcribe_audio,
    speak,
    AudioTooQuietError,
)

def record_audio(duration=4):
    """Record via audio_utils (24kHz native capture → 16kHz Whisper WAV)."""
    ts = int(__import__("time").time() * 1000)
    path = Path.home() / "brain" / "agentic-brain" / f".voice_{ts}.wav"
    print(f"🎤 Recording for {duration} seconds...")
    return _record_audio(duration=duration, output_path=path)

def transcribe(audio_path):
    """Transcribe with hallucination guards (energy check + no_speech_threshold)."""
    return transcribe_audio(audio_path)

def get_response(text):
    """Get response from Ollama."""
    import requests
    try:
        resp = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2:3b",
            "prompt": f"""You are Karen, a warm and friendly Australian voice assistant.
Keep responses SHORT (1-2 sentences). Be helpful and conversational.

User said: {text}

Karen's response:""",
            "stream": False
        }, timeout=30)
        return resp.json().get("response", "Sorry, I didn't catch that.")
    except Exception as e:
        return f"Sorry love, having a bit of trouble. {e}"

def main():
    print("🎙️ Karen Voice Chat")
    print("=" * 40)
    print("Using sox for recording (TCC bypass)")
    print("Using audio_utils: 24kHz capture → 16kHz + hallucination guards")
    print("Press Ctrl+C to stop\n")

    speak("G'day! Ready to chat. Just speak after the beep!")

    while True:
        try:
            # Beep to indicate recording starts NOW (after post-TTS delay in speak())
            subprocess.run(["afplay", "/System/Library/Sounds/Tink.aiff"])

            audio_path = record_audio(4)

            print("🔄 Transcribing...")
            text = transcribe(audio_path)

            # Clean up temp file
            try:
                Path(audio_path).unlink(missing_ok=True)
            except Exception:
                pass

            if not text or len(text) < 2:
                print("(no speech detected — silence or noise filtered out)")
                continue

            print(f"📝 You: {text}")

            print("🤔 Karen thinking...")
            response = get_response(text)
            print(f"🗣️ Karen: {response}")

            # speak() already adds post-TTS delay before returning
            speak(response)

        except KeyboardInterrupt:
            speak("Bye! Chat soon!")
            break
        except Exception as e:
            print(f"Error: {e}")
            continue

if __name__ == "__main__":
    main()
