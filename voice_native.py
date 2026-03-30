#!/usr/bin/env python3
"""
voice_native.py - Native Swift voice → GitHub Copilot pipeline

Uses VoiceToText.app for mic + transcription (Apple Speech, on-device)
Then pipes text to gh copilot for response
Karen speaks the result

This is the PRODUCTION voice system - fast, native, no workarounds.
"""

import subprocess
import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
VOICE_APP = SCRIPT_DIR / "tools/VoiceToText.app/Contents/MacOS/VoiceToText"
BRAIN_ROOT = SCRIPT_DIR.parent

def speak(text: str, voice: str = "Karen (Premium)", rate: int = 160):
    """Speak via macOS say."""
    subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=False)

def play_sound(name: str):
    """Play system sound."""
    path = f"/System/Library/Sounds/{name}.aiff"
    subprocess.run(["afplay", path], check=False, capture_output=True)

def capture_voice(silence_timeout: float = 1.5, max_duration: float = 15.0) -> str:
    """Capture voice using native Swift app with Apple Speech."""
    if not VOICE_APP.exists():
        raise RuntimeError(f"VoiceToText.app not found at {VOICE_APP}")
    
    result = subprocess.run(
        [str(VOICE_APP), str(silence_timeout), str(max_duration)],
        capture_output=True,
        text=True,
        timeout=max_duration + 5
    )
    
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "SILENCE" in stderr:
            return ""
        raise RuntimeError(f"Voice capture failed: {stderr}")
    
    return result.stdout.strip()

def ask_copilot(prompt: str, repo_path: str = None) -> str:
    """Send prompt to GitHub Copilot CLI."""
    repo = repo_path or str(BRAIN_ROOT)
    
    # Build prompt with accessibility hint
    full_prompt = f"{prompt}\n\nRespond in plain spoken English for a blind user. Keep it brief, 1-3 sentences."
    
    cmd = [
        "copilot",
        "-p", full_prompt,
        "--allow-all-tools",
        "--add-dir", repo,
    ]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=repo
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Copilot failed: {result.stderr.strip()}")
    
    return result.stdout.strip()

def main():
    speak("Native voice ready. Speak after the tone.")
    
    while True:
        try:
            # Capture voice (native Swift)
            print("[LISTENING - speak now]")
            text = capture_voice(silence_timeout=1.5, max_duration=15.0)
            
            if not text:
                print("[No speech detected]")
                continue
            
            print(f"You: {text}")
            
            # Check for stop commands
            if text.lower() in {"stop", "quit", "exit", "goodbye", "stop listening"}:
                speak("Goodbye Joseph!")
                play_sound("Funk")
                break
            
            # Send to Copilot
            print("[Asking Copilot...]")
            play_sound("Pop")
            
            response = ask_copilot(text)
            print(f"Copilot: {response}")
            
            # Speak response
            speak(response)
            play_sound("Glass")
            
        except KeyboardInterrupt:
            speak("Stopping voice.")
            break
        except subprocess.TimeoutExpired:
            speak("Request timed out, try again.")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            speak("I hit an error, trying again.")
            play_sound("Basso")

if __name__ == "__main__":
    main()
