#!/usr/bin/env python3
"""
Brain Audio MCP Server (FastMCP version)
=========================================

All audio, speech, and accessibility tools.
Optimized for VoiceOver compatibility.
NOW WITH REAL-TIME SYNTHESIS!

Tools: Audio playback, TTS, and real-time synth
"""

import json
import os
import re
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.expanduser('~/brain'))
sys.path.insert(0, os.path.expanduser('~/brain/tools'))

from mcp.server.fastmcp import FastMCP

# Import real-time audio engine
try:
    from realtime_audio_engine import RealtimeAudioEngine, midi_to_freq, note_to_freq
    HAS_REALTIME = True
except ImportError:
    HAS_REALTIME = False

mcp = FastMCP("brain-audio")

# Global engine instance (singleton)
_realtime_engine = None
_engine_lock = threading.Lock()


@mcp.tool()
def audio_speak(text: str, voice: str = "Samantha", rate: int = 175) -> dict:
    """Speak text aloud (accessibility). Waits for completion."""
    subprocess.run(["say", "-v", voice, "-r", str(rate), text])
    return {"spoken": text, "voice": voice}


@mcp.tool()
def audio_announce(message: str, importance: str = "normal") -> dict:
    """Make accessibility announcement with attention sound."""
    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"])
    subprocess.run(["say", "-v", "Samantha", message])
    return {"announced": message, "importance": importance}


@mcp.tool()
def audio_sound(sound: str) -> dict:
    """Play a system sound: hero, glass, ping, funk, basso, purr, pop."""
    sound_map = {
        "hero": "/System/Library/Sounds/Hero.aiff",
        "glass": "/System/Library/Sounds/Glass.aiff",
        "ping": "/System/Library/Sounds/Ping.aiff",
        "funk": "/System/Library/Sounds/Funk.aiff",
        "basso": "/System/Library/Sounds/Basso.aiff",
        "purr": "/System/Library/Sounds/Purr.aiff",
        "pop": "/System/Library/Sounds/Pop.aiff",
    }
    path = sound_map.get(sound, sound_map["glass"])
    subprocess.run(["afplay", path])
    return {"played": sound}


@mcp.tool()
def audio_celebrate(message: str = "Success!", style: str = "simple") -> dict:
    """Play celebration with message."""
    subprocess.run(["afplay", "/System/Library/Sounds/Hero.aiff"])
    subprocess.run(["say", "-v", "Samantha", message])
    return {"celebrated": message}


@mcp.tool()
def audio_notify(message: str, urgency: str = "normal") -> dict:
    """Play notification with message."""
    sound = "Glass.aiff" if urgency == "normal" else "Funk.aiff"
    subprocess.run(["afplay", f"/System/Library/Sounds/{sound}"])
    subprocess.run(["say", "-v", "Samantha", message])
    return {"notified": message, "urgency": urgency}


@mcp.tool()
def audio_voiceover(text: str) -> dict:
    """Format text for VoiceOver (removes emoji, adds section markers)."""
    text = re.sub(r'[^\x00-\x7F]+', '', text)
    text = re.sub(r'^#+\s*(.+)$', r'SECTION: \1', text, flags=re.MULTILINE)
    return {"formatted": text}


@mcp.tool()
def audio_volume(action: str = "get", level: int = None) -> dict:
    """Get or set system volume. Actions: get, set, mute, unmute."""
    if action == "get":
        result = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"], 
                               capture_output=True, text=True)
        return {"volume": int(result.stdout.strip())}
    elif action == "set" and level is not None:
        subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
        return {"volume": level}
    elif action == "mute":
        subprocess.run(["osascript", "-e", "set volume with output muted"])
        return {"muted": True}
    elif action == "unmute":
        subprocess.run(["osascript", "-e", "set volume without output muted"])
        return {"muted": False}
    return {"error": "Invalid action"}


@mcp.tool()
def audio_devices() -> dict:
    """List audio input/output devices."""
    result = subprocess.run(
        ["system_profiler", "SPAudioDataType", "-json"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout) if result.returncode == 0 else {"error": "Could not get devices"}


@mcp.tool()
def audio_voices() -> dict:
    """List available voices and sounds."""
    result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
    voices = [line.split()[0] for line in result.stdout.strip().split("\n")[:20]]
    sounds = ["hero", "glass", "ping", "funk", "basso", "purr", "pop"]
    return {"voices": voices, "sounds": sounds}


# =============================================================================
# REAL-TIME SYNTHESIZER TOOLS
# =============================================================================

def _get_engine():
    """Get or create the singleton real-time engine"""
    global _realtime_engine
    with _engine_lock:
        if _realtime_engine is None and HAS_REALTIME:
            _realtime_engine = RealtimeAudioEngine(
                sample_rate=44100,
                buffer_size=512
            )
            _realtime_engine.start()
        return _realtime_engine


@mcp.tool()
def realtime_status() -> dict:
    """Get real-time audio engine status."""
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available", "has_realtime": False}
    
    engine = _get_engine()
    if engine:
        return engine.get_status()
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_note(freq: float = 440.0, duration: float = 1.0, 
                  waveform: str = "saw", amplitude: float = 0.5,
                  filter_cutoff: float = 5000.0) -> dict:
    """
    Play a note in REAL-TIME (no WAV files!).
    Waveforms: sine, saw, square, triangle
    """
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if engine:
        engine.play_note(freq, duration, amplitude, waveform, 
                        filter_cutoff=filter_cutoff)
        return {
            "playing": True,
            "freq": freq,
            "duration": duration,
            "waveform": waveform,
            "latency_ms": engine.get_status()["latency_ms"]
        }
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_chord(frequencies: list, duration: float = 1.0,
                   waveform: str = "saw", amplitude: float = 0.3) -> dict:
    """Play a chord in real-time (multiple simultaneous notes)."""
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if engine:
        engine.play_chord(frequencies, duration, waveform, amplitude)
        return {
            "playing": True,
            "frequencies": frequencies,
            "duration": duration,
            "waveform": waveform
        }
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_midi_note(midi_note: int, duration: float = 1.0,
                       waveform: str = "saw", amplitude: float = 0.5) -> dict:
    """Play a MIDI note (0-127) in real-time. Middle C = 60."""
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    freq = midi_to_freq(midi_note)
    engine = _get_engine()
    if engine:
        engine.play_note(freq, duration, amplitude, waveform)
        return {
            "playing": True,
            "midi_note": midi_note,
            "freq": freq,
            "duration": duration
        }
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_lfo(rate: float = 5.0, depth: float = 0.5) -> dict:
    """Set LFO for vibrato/modulation. Rate in Hz, depth 0-1."""
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if engine:
        engine.set_lfo(rate, depth)
        return {"lfo_rate": rate, "lfo_depth": depth}
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_reverb(room_size: float = 0.5, wet: float = 0.3) -> dict:
    """Add reverb effect to real-time output."""
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if engine:
        engine.add_reverb(room_size, wet)
        return {"reverb_added": True, "room_size": room_size, "wet": wet}
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_delay(delay_seconds: float = 0.25, feedback: float = 0.4,
                   mix: float = 0.3) -> dict:
    """Add delay effect to real-time output."""
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if engine:
        engine.add_delay(delay_seconds, feedback, mix)
        return {"delay_added": True, "delay_seconds": delay_seconds, 
                "feedback": feedback, "mix": mix}
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_clear_effects() -> dict:
    """Clear all real-time effects."""
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if engine:
        engine.clear_effects()
        return {"effects_cleared": True}
    return {"error": "Engine not initialized"}


@mcp.tool()
def realtime_bass(freq: float = 55.0, duration: float = 1.5,
                  style: str = "standard") -> dict:
    """
    Play a bass note with proper bass settings.
    Styles: standard, hard, soft, filtered
    """
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if not engine:
        return {"error": "Engine not initialized"}
    
    # Style presets
    styles = {
        "standard": {"waveform": "saw", "filter_cutoff": 800, "amplitude": 0.6},
        "hard": {"waveform": "square", "filter_cutoff": 1200, "amplitude": 0.5},
        "soft": {"waveform": "sine", "filter_cutoff": 500, "amplitude": 0.7},
        "filtered": {"waveform": "saw", "filter_cutoff": 400, "amplitude": 0.6},
    }
    
    preset = styles.get(style, styles["standard"])
    engine.play_note(
        freq, duration, 
        amplitude=preset["amplitude"],
        waveform=preset["waveform"],
        filter_cutoff=preset["filter_cutoff"],
        attack=0.01,
        decay=0.2,
        sustain=0.6,
        release=0.3
    )
    
    return {
        "playing": True,
        "freq": freq,
        "duration": duration,
        "style": style,
        **preset
    }


@mcp.tool()
def realtime_dnb_roller(bars: int = 4, bpm: int = 174, 
                        root_note: str = "A") -> dict:
    """
    Play a DnB rolling bassline in real-time!
    Root notes: A, C, D, E, F, G
    """
    if not HAS_REALTIME:
        return {"error": "Real-time engine not available"}
    
    engine = _get_engine()
    if not engine:
        return {"error": "Engine not initialized"}
    
    # Root frequencies
    roots = {"A": 55, "C": 65.41, "D": 73.42, "E": 82.41, "F": 87.31, "G": 98}
    root = roots.get(root_note, 55)
    
    beat = 60 / bpm
    sixteenth = beat / 4
    
    # Pentatonic pattern from root
    pattern = [root, root, root * 1.189, root, root * 1.335, root, root, root * 1.498]
    
    def play_bassline():
        for _ in range(bars):
            for i, note in enumerate(pattern):
                engine.play_note(
                    note,
                    duration=sixteenth * 0.8,
                    waveform="saw",
                    amplitude=0.5,
                    filter_cutoff=600 + (i % 4) * 150,
                    attack=0.005,
                    decay=0.05,
                    sustain=0.6,
                    release=0.1
                )
                time.sleep(sixteenth)
    
    # Play in background thread
    threading.Thread(target=play_bassline, daemon=True).start()
    
    return {
        "playing": True,
        "bars": bars,
        "bpm": bpm,
        "root": root_note,
        "duration_seconds": bars * 4 * beat
    }


if __name__ == "__main__":
    print("🔊 Brain Audio MCP Server (FastMCP) starting...")
    mcp.run()
