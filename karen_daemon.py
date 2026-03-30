#!/usr/bin/env python3
"""
Karen Voice Daemon - Standalone voice chat with Redis coordination.
Runs independently, communicates via Redis pub/sub.
"""
import subprocess
import tempfile
import os
import sys
import json
import time
import redis
from pathlib import Path
from datetime import datetime

# Load env
from dotenv import load_dotenv
load_dotenv(Path.home() / "brain" / ".env")

# Redis connection
r = redis.Redis(host='localhost', port=6379, password='BrainRedis2026', decode_responses=True)

def log(msg):
    """Log to Redis and console."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    print(full_msg)
    r.lpush("karen:logs", full_msg)
    r.ltrim("karen:logs", 0, 100)
    r.set("karen:status", msg)

def speak(text, voice="Karen (Premium)", rate=160):
    """Speak using macOS say."""
    log(f"Speaking: {text[:50]}...")
    r.set("karen:state", "speaking")
    subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=True)
    r.set("karen:state", "idle")

def record_audio(duration=5):
    """Record using sox with AirPods Max."""
    audio_path = Path.home() / "brain" / "agentic-brain" / ".voice_input.wav"
    r.set("karen:state", "listening")
    log(f"🎤 Listening for {duration}s...")
    
    # Use coreaudio driver for better Mac compatibility
    cmd = [
        "sox", "-d",
        "-r", "16000", "-c", "1", "-b", "16",
        str(audio_path),
        "trim", "0", str(duration),
        "silence", "1", "0.5", "1%",  # Start when speech detected
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    r.set("karen:state", "processing")
    return str(audio_path)

def transcribe(audio_path):
    """Transcribe with faster-whisper."""
    log("🔄 Transcribing...")
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("tiny.en", compute_type="int8")
        segments, _ = model.transcribe(audio_path)
        text = " ".join(s.text for s in segments).strip()
        return text
    except Exception as e:
        log(f"Transcribe error: {e}")
        return ""

def get_response(text):
    """Get response from Ollama."""
    log("🤔 Thinking...")
    r.set("karen:state", "thinking")
    import requests
    try:
        resp = requests.post("http://localhost:11434/api/generate", json={
            "model": "llama3.2:3b",
            "prompt": f"""You are Karen, a warm Australian woman helping Joseph (who is blind).
Keep responses SHORT (1-2 sentences). Be helpful and conversational.

Joseph said: {text}

Karen's response:""",
            "stream": False
        }, timeout=30)
        return resp.json().get("response", "Sorry, I didn't catch that.")
    except Exception as e:
        return f"Sorry love, having a bit of trouble. {e}"

def main():
    log("🚀 Karen Voice Daemon starting...")
    r.set("karen:state", "starting")
    r.set("karen:pid", str(os.getpid()))
    
    # Announce start
    speak("G'day Joseph! Karen's voice daemon is running. Just talk to me!")
    
    # Play ready sound
    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
    
    r.set("karen:state", "ready")
    log("✅ Ready - listening for your voice")
    
    while True:
        try:
            # Check for stop command
            if r.get("karen:command") == "stop":
                log("Stop command received")
                r.delete("karen:command")
                break
            
            # Record
            subprocess.run(["afplay", "/System/Library/Sounds/Tink.aiff"])
            audio_path = record_audio(5)
            
            # Transcribe
            text = transcribe(audio_path)
            
            if not text or len(text) < 2:
                log("(no speech detected)")
                continue
            
            # Publish what was heard
            r.set("karen:last_heard", text)
            r.publish("karen:heard", text)
            log(f"📝 Heard: {text}")
            
            # Check for stop words
            if any(word in text.lower() for word in ["stop", "quit", "exit", "goodbye"]):
                speak("Bye Joseph! Chat soon!")
                break
            
            # Get response
            response = get_response(text)
            r.set("karen:last_response", response)
            r.publish("karen:response", response)
            log(f"🗣️ Response: {response}")
            
            # Speak
            speak(response)
            
        except KeyboardInterrupt:
            speak("Bye Joseph!")
            break
        except Exception as e:
            log(f"Error: {e}")
            time.sleep(1)
    
    r.set("karen:state", "stopped")
    log("👋 Karen daemon stopped")

if __name__ == "__main__":
    main()
