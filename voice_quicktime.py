#!/usr/bin/env python3
"""
voice_quicktime.py - QuickTime mic + Whisper API + Copilot

Uses QuickTime Player for mic (already has permission)
OpenAI Whisper API for transcription (fast, accurate)
GitHub Copilot for response
Karen speaks the result

NO NEW PERMISSIONS NEEDED - uses existing QuickTime mic access.
"""

import subprocess
import tempfile
import time
import os
import sys
import requests
from pathlib import Path

# Load .env
def load_env():
    for env_path in [Path.home() / "brain/.env", Path(__file__).parent / ".env"]:
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.strip() and not line.startswith("#") and "=" in line:
                    k, _, v = line.partition("=")
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))

load_env()

def speak(text: str, voice: str = "Karen (Premium)", rate: int = 160):
    subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=False)

def play_sound(name: str):
    subprocess.run(["afplay", f"/System/Library/Sounds/{name}.aiff"], check=False, capture_output=True)

def record_quicktime(duration: int = 6) -> Path:
    """Record audio via QuickTime Player (has mic permission)."""
    output = Path(tempfile.gettempdir()) / f"voice_{int(time.time())}.m4a"
    
    script = f'''
    tell application "QuickTime Player"
        activate
        set newRec to new audio recording
        delay 0.3
        start newRec
        delay {duration}
        stop newRec
        delay 0.3
        set recDoc to document 1
        export recDoc in POSIX file "{output}" using settings preset "Audio Only"
        close recDoc without saving
    end tell
    tell application "System Events"
        set visible of process "QuickTime Player" to false
    end tell
    '''
    
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    return output

def transcribe_whisper(audio_path: Path) -> str:
    """Transcribe via OpenAI Whisper API."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    
    with open(audio_path, "rb") as f:
        response = requests.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": "whisper-1"},
            files={"file": (audio_path.name, f, "audio/m4a")},
            timeout=30
        )
    
    response.raise_for_status()
    text = response.json().get("text", "").strip()
    
    # Filter hallucinations
    if text.lower() in {"you", "thank you", "thanks", ".", "...", "bye"}:
        return ""
    
    return text

def ask_copilot(prompt: str) -> str:
    """Send to GitHub Copilot CLI."""
    full_prompt = f"{prompt}\n\nRespond briefly in plain English for a blind user, 1-3 sentences max."
    
    result = subprocess.run(
        ["copilot", "-p", full_prompt, "--allow-all-tools"],
        capture_output=True, text=True, timeout=60
    )
    
    if result.returncode != 0:
        # Fallback to Claude if Copilot fails
        return ask_claude(prompt)
    
    return result.stdout.strip()

def ask_claude(prompt: str) -> str:
    """Fallback to Claude API."""
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return "Sorry, couldn't get a response."
    
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": 200,
            "system": "You are Karen, a warm assistant for Joseph who is blind. Be brief, 1-3 sentences.",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    response.raise_for_status()
    content = response.json().get("content", [])
    return content[0].get("text", "") if content else ""

def main():
    speak("Voice ready. Speak after the tone, I'm listening for 6 seconds each time.")
    
    while True:
        try:
            play_sound("Tink")
            print("[RECORDING 6 seconds...]")
            
            audio = record_quicktime(6)
            
            print("[TRANSCRIBING...]")
            text = transcribe_whisper(audio)
            audio.unlink(missing_ok=True)
            
            if not text:
                print("[No speech]")
                continue
            
            print(f"You: {text}")
            
            if text.lower() in {"stop", "quit", "exit", "goodbye", "stop listening"}:
                speak("Goodbye Joseph!")
                play_sound("Funk")
                break
            
            print("[THINKING...]")
            play_sound("Pop")
            
            response = ask_copilot(text)
            print(f"Response: {response}")
            
            speak(response)
            play_sound("Glass")
            
        except KeyboardInterrupt:
            speak("Stopping.")
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            speak("Hit a problem, trying again.")
            play_sound("Basso")

if __name__ == "__main__":
    main()
