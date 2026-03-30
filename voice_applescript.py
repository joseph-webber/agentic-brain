#!/usr/bin/env python3
"""Voice chat using AppleScript + QuickTime for mic access (bypasses TCC)."""

import subprocess
import tempfile
import time
import os
from pathlib import Path

def record_via_quicktime(duration_seconds: int = 5) -> Path:
    """Record audio using QuickTime Player (has mic permission)."""
    output_path = Path(tempfile.gettempdir()) / f"voice_{int(time.time())}.m4a"
    
    script = f'''
    tell application "QuickTime Player"
        activate
        set newRecording to new audio recording
        delay 0.3
        start newRecording
        delay {duration_seconds}
        stop newRecording
        delay 0.2
        export document 1 in POSIX file "{output_path}" using settings preset "Audio Only"
        close document 1 without saving
    end tell
    '''
    
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
    return output_path

def transcribe_whisper(audio_path: Path) -> str:
    """Transcribe using faster-whisper."""
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio_path), 
                                       no_speech_threshold=0.6,
                                       log_prob_threshold=-1.0)
    text = " ".join(seg.text.strip() for seg in segments)
    return text.strip()

def speak(text: str, voice: str = "Karen (Premium)", rate: int = 160):
    """Speak via macOS say."""
    subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=False)

def ask_claude(prompt: str) -> str:
    """Get response from Claude API."""
    import requests
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        return "Claude API key not set"
    
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
            "system": "You are Karen, a warm voice assistant for Joseph who is blind. Respond in 1-3 short sentences, no markdown.",
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=30,
    )
    response.raise_for_status()
    content = response.json().get("content", [])
    return content[0].get("text", "") if content else ""

def main():
    speak("Voice chat ready. Recording now via QuickTime.")
    
    # Play ready tone
    subprocess.run(["afplay", "/System/Library/Sounds/Tink.aiff"], check=False)
    
    while True:
        try:
            print("[RECORDING via QuickTime...]")
            audio_path = record_via_quicktime(5)
            
            print("[TRANSCRIBING...]")
            text = transcribe_whisper(audio_path)
            audio_path.unlink(missing_ok=True)
            
            if not text or text.lower() in {"you", "thank you", "thanks", "."}:
                print("[IDLE] No speech detected")
                continue
            
            print(f"You: {text}")
            
            if text.lower() in {"stop", "quit", "goodbye", "exit"}:
                speak("Goodbye Joseph!")
                break
            
            print("[THINKING...]")
            subprocess.run(["afplay", "/System/Library/Sounds/Pop.aiff"], check=False)
            
            response = ask_claude(text)
            print(f"Karen: {response}")
            speak(response)
            
            subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)
            time.sleep(0.5)
            
        except KeyboardInterrupt:
            speak("Stopping voice chat.")
            break
        except Exception as e:
            print(f"Error: {e}")
            speak("I hit a problem, trying again.")

if __name__ == "__main__":
    main()
