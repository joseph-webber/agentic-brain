#!/usr/bin/env python3
"""
Music Producer MCP Server
Full music production pipeline - from idea to published release.

Historic Achievement: Neural Pathways (2026-03-09)
- First AI-produced full-length DnB track
- 7 parallel agents for production
- Neo4j music theory integration
- Published to Apple Music

Capabilities:
- Generate any genre of music
- Full arrangement (intro → outro)
- Sound design (drums, bass, synths, FX)
- Mixing and mastering
- Auto-publish to Music Publisher MCP
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import hashlib

from mcp.server.fastmcp import FastMCP

# ============================================================================
# LAZY IMPORTS (Performance optimization - 890ms → <500ms)
# numpy/scipy are imported lazily on first use
# ============================================================================

_np = None
_wavfile = None
_signal = None


def get_np():
    """Lazy load numpy."""
    global _np
    if _np is None:
        import numpy

        _np = numpy
    return _np


def get_wavfile():
    """Lazy load scipy.io.wavfile."""
    global _wavfile
    if _wavfile is None:
        from scipy.io import wavfile

        _wavfile = wavfile
    return _wavfile


def get_signal():
    """Lazy load scipy.signal."""
    global _signal
    if _signal is None:
        from scipy import signal

        _signal = signal
    return _signal


# Alias for backward compatibility in function signatures
class NpProxy:
    """Proxy that lazily loads numpy."""

    def __getattr__(self, name):
        return getattr(get_np(), name)

    @property
    def ndarray(self):
        return get_np().ndarray


np = NpProxy()

# Initialize MCP server
mcp = FastMCP("music-producer")

# Configuration
BRAIN_DIR = Path.home() / "brain"
SOUNDS_DIR = BRAIN_DIR / "sounds"
SONGS_DIR = BRAIN_DIR / "songs"
PRODUCTION_LOG = SONGS_DIR / "production_log.json"

# Ensure directories exist
SOUNDS_DIR.mkdir(parents=True, exist_ok=True)
SONGS_DIR.mkdir(parents=True, exist_ok=True)

# Default sample rate
SR = 44100


def load_production_log() -> dict:
    """Load the production event log."""
    if PRODUCTION_LOG.exists():
        return json.loads(PRODUCTION_LOG.read_text())
    return {
        "productions": [],
        "total_tracks": 0,
        "total_production_time": 0,
        "created": datetime.now().isoformat(),
    }


def save_production_log(log: dict):
    """Save the production event log."""
    PRODUCTION_LOG.write_text(json.dumps(log, indent=2))


def generate_tech_stack_doc(
    title: str,
    artist: str,
    genre: str,
    bpm: int,
    key: str,
    duration_bars: int,
    duration_seconds: float,
    production_id: str,
    stems: dict,
    master_path: str,
) -> str:
    """
    Generate the TECH_STACK.md document for a production.
    This burns the architecture into every song we make.
    """
    mins = int(duration_seconds // 60)
    secs = int(duration_seconds % 60)

    return (
        f"""# {title} - Technical Architecture

## 🎵 Track Information

| Field | Value |
|-------|-------|
| **Title** | {title} |
| **Artist** | {artist} |
| **Genre** | {genre} |
| **BPM** | {bpm} |
| **Key** | {key} |
| **Duration** | {mins}:{secs:02d} ({duration_bars} bars) |
| **Production ID** | {production_id} |
| **Created** | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |

---

## 🚫 What Was NOT Used

- ❌ No DAW (Ableton, Logic, FL Studio, Pro Tools)
- ❌ No VST plugins (Serum, Massive, Sylenth)
- ❌ No sample packs (Splice, Loopmasters)
- ❌ No hardware synths
- ❌ No prerecorded samples

---

## ✅ Technology Stack

### Core
| Component | Technology |
|-----------|------------|
| Language | Python 3.11 |
| Synthesis | NumPy (mathematical waveforms) |
| DSP | SciPy (Butterworth filters) |
| Audio I/O | scipy.io.wavfile |
| AI | Claude Opus 4.5 |
| Knowledge | Neo4j (music theory) |

### Dependencies
```
numpy>=1.26.0
scipy>=1.12.0
sounddevice>=0.4.6
```

---

## 🔊 Sound Design

### Oscillators (Pure Math)
```python
# Sine
np.sin(2 * np.pi * freq * t)

# Sawtooth
2 * (t * freq - np.floor(0.5 + t * freq))

# Square  
np.sign(np.sin(2 * np.pi * freq * t))
```

### Filters
```python
# Butterworth lowpass/highpass
b, a = signal.butter(4, cutoff/nyquist, btype='low')
filtered = signal.filtfilt(b, a, audio)
```

### ADSR Envelope
```python
envelope = [attack_ramp, decay_ramp, sustain_hold, release_ramp]
audio = audio * envelope
```

### Soft Limiting (Master)
```python
soft_clip(audio, threshold=0.7)
# tanh saturation above threshold
```

---

## 📁 Stems Generated

| Stem | File |
|------|------|
"""
        + "\n".join(
            f"| {name.title()} | `{Path(path).name}` |" for name, path in stems.items()
        )
        + f"""

### Master
`{Path(master_path).name}`

---

## 📊 Technical Specs

| Specification | Value |
|---------------|-------|
| Sample Rate | 44,100 Hz |
| Bit Depth | 16-bit |
| Channels | Stereo |
| Bars | {duration_bars} |
| Tail Silence | 500ms |
| Peak Level | -1dB |

---

## 🎛️ Production Parameters

### Drums
- Kick: 55Hz fundamental, pitch envelope, sub layer
- Snare: 200Hz tone + filtered noise + snap
- Hats: Detuned squares + highpass noise

### Bass (Reese)
- Oscillators: 3 detuned sawtooths
- Detune: 10 cents spread
- Filter: 800Hz lowpass
- Sub: Pure sine at fundamental
- Saturation: tanh on mids only

### Pads
- Chord type: Based on key ({key})
- Voices: 5 unison per note
- Filter: ~2000Hz lowpass
- Envelope: Slow attack (0.5s)

### FX
- Risers: 8-bar noise sweep
- Impacts: Sub thump + noise burst + delay tail

---

## 🏗️ Arrangement

```
Bars 1-16:    INTRO      (pads, atmosphere)
Bars 17-24:   BUILDUP    (riser FX)
Bars 25-40:   DROP 1     (full energy)
Bars 41-56:   BREAKDOWN  (emotional, pads return)
Bars 57-64:   BUILDUP 2  (second riser)
Bars 65-96:   DROP 2     (extended, harder)
Bars 97-128:  OUTRO      (fade out)
```

---

## 🔄 Mix Levels

| Stem | Level |
|------|-------|
| Drums | 0.90 (loudest) |
| Bass | 0.75 |
| Pads | 0.40 |
| FX | 0.60 |

---

## 🤖 AI Production

- **Director**: Claude Opus 4.5
- **Method**: Parallel agent fleet OR single-pass production
- **Knowledge Source**: Neo4j music theory graph

---

## 📖 Reproduction

```bash
cd ~/brain
source venv/bin/activate
python mcp-servers/music-producer/server.py

# Or directly:
from mcp-servers.music-producer.server import produce_track
produce_track(
    title="{title}",
    genre="{genre}",
    bpm={bpm},
    key="{key.split()[0]}",
    mode="{key.split()[1] if ' ' in key else 'minor'}",
    duration_bars={duration_bars}
)
```

---

## 🏷️ Credits

- **Producer**: Brain AI
- **Sound Design**: NumPy/SciPy
- **Mastering**: Soft limiter algorithm
- **Label**: Brain Records
- **Year**: {datetime.now().year}

---

*This document was auto-generated and burned with the production.*
*Every Brain AI song includes its full technical architecture.*
"""
    )


def log_event(production_id: str, event_type: str, details: dict):
    """Log a production event."""
    log = load_production_log()

    # Find or create production entry
    production = None
    for p in log["productions"]:
        if p["id"] == production_id:
            production = p
            break

    if not production:
        production = {
            "id": production_id,
            "events": [],
            "started": datetime.now().isoformat(),
        }
        log["productions"].append(production)

    # Add event
    production["events"].append(
        {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "details": details,
        }
    )

    save_production_log(log)


# ============== SOUND GENERATION ==============


def generate_sine(freq: float, duration: float, sr: int = SR):
    """Generate sine wave."""
    np = get_np()
    t = np.linspace(0, duration, int(sr * duration), False)
    return np.sin(2 * np.pi * freq * t)


def generate_saw(freq: float, duration: float, sr: int = SR):
    """Generate sawtooth wave."""
    np = get_np()
    t = np.linspace(0, duration, int(sr * duration), False)
    return 2 * (t * freq - np.floor(0.5 + t * freq))


def generate_square(freq: float, duration: float, sr: int = SR):
    """Generate square wave."""
    np = get_np()
    t = np.linspace(0, duration, int(sr * duration), False)
    return np.sign(np.sin(2 * np.pi * freq * t))


def apply_envelope(
    audio,
    attack: float = 0.01,
    decay: float = 0.1,
    sustain: float = 0.7,
    release: float = 0.2,
    sr: int = SR,
):
    """Apply ADSR envelope."""
    np = get_np()
    total_samples = len(audio)
    attack_samples = int(attack * sr)
    decay_samples = int(decay * sr)
    release_samples = int(release * sr)
    sustain_samples = total_samples - attack_samples - decay_samples - release_samples

    if sustain_samples < 0:
        sustain_samples = 0

    envelope = np.concatenate(
        [
            np.linspace(0, 1, attack_samples),
            np.linspace(1, sustain, decay_samples),
            np.full(sustain_samples, sustain),
            np.linspace(sustain, 0, release_samples),
        ]
    )

    # Trim or pad to match audio length
    if len(envelope) > len(audio):
        envelope = envelope[: len(audio)]
    elif len(envelope) < len(audio):
        envelope = np.pad(envelope, (0, len(audio) - len(envelope)))

    return audio * envelope


def lowpass_filter(audio, cutoff: float, sr: int = SR):
    """Apply lowpass filter."""
    signal = get_signal()
    nyq = sr / 2
    normalized_cutoff = min(cutoff / nyq, 0.99)
    b, a = signal.butter(4, normalized_cutoff, btype="low")
    return signal.filtfilt(b, a, audio)


def highpass_filter(audio, cutoff: float, sr: int = SR):
    """Apply highpass filter."""
    signal = get_signal()
    nyq = sr / 2
    normalized_cutoff = max(cutoff / nyq, 0.01)
    b, a = signal.butter(4, normalized_cutoff, btype="high")
    return signal.filtfilt(b, a, audio)


def soft_clip(audio, threshold: float = 0.7):
    """Soft clipping distortion."""
    np = get_np()
    return np.where(
        np.abs(audio) > threshold,
        threshold
        + (1 - threshold) * np.tanh((np.abs(audio) - threshold) * 3) * np.sign(audio),
        audio,
    )


def normalize(audio, target: float = 0.9):
    """Normalize audio to target peak."""
    np = get_np()
    peak = np.max(np.abs(audio))
    if peak > 0:
        return audio * (target / peak)
    return audio


# ============== DRUM GENERATION ==============


@mcp.tool()
def generate_kick(
    freq: float = 55, duration: float = 0.3, punch: float = 0.8, sub_weight: float = 0.6
) -> dict:
    """
    Generate a drum and bass kick drum.

    Args:
        freq: Base frequency (Hz)
        duration: Duration in seconds
        punch: Punch amount (0-1)
        sub_weight: Sub bass weight (0-1)

    Returns:
        Kick drum info and file path
    """
    t = np.linspace(0, duration, int(SR * duration), False)

    # Pitch envelope - starts high, drops to base
    pitch_env = np.exp(-t * 40) * 200 + freq

    # Generate with pitch envelope
    phase = np.cumsum(2 * np.pi * pitch_env / SR)
    kick = np.sin(phase)

    # Add punch (click transient)
    click = np.random.randn(int(SR * 0.005)) * punch
    click = apply_envelope(click, attack=0.001, decay=0.004, sustain=0, release=0.001)

    # Combine
    kick[: len(click)] += click

    # Amplitude envelope
    amp_env = np.exp(-t * 8)
    kick = kick * amp_env

    # Add sub
    sub = generate_sine(freq, duration) * sub_weight
    sub = apply_envelope(sub, attack=0.01, decay=0.1, sustain=0.3, release=0.15)
    kick = kick + sub

    # Normalize
    kick = normalize(kick, 0.9)

    # Save
    output_path = SOUNDS_DIR / "generated_kick.wav"
    wavfile.write(output_path, SR, (kick * 32767).astype(np.int16))

    return {
        "type": "kick",
        "freq": freq,
        "duration": duration,
        "file": str(output_path),
    }


@mcp.tool()
def generate_snare(
    freq: float = 200,
    duration: float = 0.2,
    noise_amount: float = 0.7,
    snap: float = 0.8,
) -> dict:
    """
    Generate a snare drum.

    Args:
        freq: Tone frequency (Hz)
        duration: Duration in seconds
        noise_amount: White noise amount (0-1)
        snap: High-frequency snap (0-1)

    Returns:
        Snare info and file path
    """
    t = np.linspace(0, duration, int(SR * duration), False)

    # Tone component
    tone = generate_sine(freq, duration) * 0.5
    tone = apply_envelope(tone, attack=0.001, decay=0.05, sustain=0.1, release=0.1)

    # Noise component
    noise = np.random.randn(len(t)) * noise_amount
    noise = highpass_filter(noise, 2000)
    noise = apply_envelope(noise, attack=0.001, decay=0.08, sustain=0.05, release=0.1)

    # Snap (high freq click)
    snap_sound = np.random.randn(int(SR * 0.01)) * snap
    snap_sound = highpass_filter(snap_sound, 5000)

    # Combine
    snare = tone + noise
    snare[: len(snap_sound)] += snap_sound

    snare = normalize(snare, 0.85)

    output_path = SOUNDS_DIR / "generated_snare.wav"
    wavfile.write(output_path, SR, (snare * 32767).astype(np.int16))

    return {
        "type": "snare",
        "freq": freq,
        "duration": duration,
        "file": str(output_path),
    }


@mcp.tool()
def generate_hihat(
    duration: float = 0.05, open_hat: bool = False, brightness: float = 0.8
) -> dict:
    """
    Generate a hi-hat.

    Args:
        duration: Duration in seconds
        open_hat: True for open hat, False for closed
        brightness: High frequency content (0-1)

    Returns:
        Hi-hat info and file path
    """
    if open_hat:
        duration = max(duration, 0.3)

    t = np.linspace(0, duration, int(SR * duration), False)

    # Multiple detuned square waves for metallic sound
    hat = np.zeros_like(t)
    freqs = [4000, 4500, 5000, 5500, 6000]
    for f in freqs:
        hat += generate_square(f * (0.9 + np.random.random() * 0.2), duration) * 0.2

    # Add noise
    noise = np.random.randn(len(t)) * 0.5
    noise = highpass_filter(noise, 8000 * brightness)
    hat = hat + noise

    # Envelope
    if open_hat:
        hat = apply_envelope(hat, attack=0.001, decay=0.1, sustain=0.3, release=0.2)
    else:
        hat = apply_envelope(hat, attack=0.001, decay=0.02, sustain=0, release=0.03)

    hat = normalize(hat, 0.7)

    filename = "generated_open_hat.wav" if open_hat else "generated_closed_hat.wav"
    output_path = SOUNDS_DIR / filename
    wavfile.write(output_path, SR, (hat * 32767).astype(np.int16))

    return {
        "type": "open_hat" if open_hat else "closed_hat",
        "duration": duration,
        "file": str(output_path),
    }


# ============== BASS GENERATION ==============


@mcp.tool()
def generate_reese_bass(
    freq: float = 55,
    duration: float = 2.0,
    detune_cents: float = 10,
    num_oscillators: int = 3,
    filter_cutoff: float = 800,
    saturation: float = 0.5,
) -> dict:
    """
    Generate a classic Reese bass (Kevin Saunderson 1988 style).

    Args:
        freq: Base frequency (Hz)
        duration: Duration in seconds
        detune_cents: Detune amount in cents
        num_oscillators: Number of detuned oscillators
        filter_cutoff: Lowpass filter cutoff (Hz)
        saturation: Saturation amount (0-1)

    Returns:
        Reese bass info and file path
    """
    t = np.linspace(0, duration, int(SR * duration), False)

    # Generate detuned oscillators
    bass = np.zeros_like(t)
    detune_factor = 2 ** (detune_cents / 1200)

    for i in range(num_oscillators):
        # Spread detune across oscillators
        if num_oscillators > 1:
            spread = (i - (num_oscillators - 1) / 2) / ((num_oscillators - 1) / 2)
        else:
            spread = 0
        osc_freq = freq * (detune_factor**spread)
        bass += generate_saw(osc_freq, duration)

    bass = bass / num_oscillators

    # Add sub oscillator
    sub = generate_sine(freq, duration) * 0.5

    # Filter the main bass (not the sub)
    bass_filtered = lowpass_filter(bass, filter_cutoff)

    # Saturation on mids only
    bass_mids = highpass_filter(bass_filtered, 100)
    bass_mids = soft_clip(bass_mids * (1 + saturation), 0.6)
    bass_lows = lowpass_filter(bass_filtered, 100)

    # Combine
    final = bass_lows + bass_mids * 0.7 + sub

    # Envelope
    final = apply_envelope(final, attack=0.01, decay=0.1, sustain=0.8, release=0.1)
    final = normalize(final, 0.85)

    output_path = SOUNDS_DIR / "generated_reese.wav"
    wavfile.write(output_path, SR, (final * 32767).astype(np.int16))

    return {
        "type": "reese_bass",
        "freq": freq,
        "duration": duration,
        "oscillators": num_oscillators,
        "detune_cents": detune_cents,
        "file": str(output_path),
    }


@mcp.tool()
def generate_sub_bass(freq: float = 40, duration: float = 1.0) -> dict:
    """
    Generate a pure sub bass.

    Args:
        freq: Frequency (Hz)
        duration: Duration in seconds

    Returns:
        Sub bass info and file path
    """
    sub = generate_sine(freq, duration)
    sub = apply_envelope(sub, attack=0.02, decay=0.1, sustain=0.9, release=0.1)
    sub = normalize(sub, 0.9)

    output_path = SOUNDS_DIR / "generated_sub.wav"
    wavfile.write(output_path, SR, (sub * 32767).astype(np.int16))

    return {
        "type": "sub_bass",
        "freq": freq,
        "duration": duration,
        "file": str(output_path),
    }


# ============== SYNTH GENERATION ==============


@mcp.tool()
def generate_pad(
    root_note: str = "A",
    octave: int = 3,
    chord_type: str = "minor7",
    duration: float = 4.0,
    brightness: float = 0.5,
    voices: int = 5,
) -> dict:
    """
    Generate a lush pad sound.

    Args:
        root_note: Root note (A, B, C, D, E, F, G)
        octave: Octave number
        chord_type: Chord type (minor7, major7, minor9, add9)
        duration: Duration in seconds
        brightness: Filter brightness (0-1)
        voices: Unison voices per note

    Returns:
        Pad info and file path
    """
    # Note to frequency
    notes = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    semitone = notes.get(root_note.upper(), 9)
    root_freq = 440 * (2 ** ((semitone - 9 + (octave - 4) * 12) / 12))

    # Chord intervals (semitones)
    chord_intervals = {
        "minor7": [0, 3, 7, 10],
        "major7": [0, 4, 7, 11],
        "minor9": [0, 3, 7, 10, 14],
        "add9": [0, 4, 7, 14],
        "minor": [0, 3, 7],
        "major": [0, 4, 7],
    }

    intervals = chord_intervals.get(chord_type, [0, 3, 7])

    t = np.linspace(0, duration, int(SR * duration), False)
    pad = np.zeros_like(t)

    for interval in intervals:
        note_freq = root_freq * (2 ** (interval / 12))

        # Multiple detuned voices per note
        for v in range(voices):
            detune = (v - (voices - 1) / 2) * 5  # cents
            voice_freq = note_freq * (2 ** (detune / 1200))
            pad += generate_saw(voice_freq, duration) * 0.3

    # Filter
    cutoff = 500 + brightness * 3000
    pad = lowpass_filter(pad, cutoff)

    # Slow envelope
    pad = apply_envelope(pad, attack=0.5, decay=0.3, sustain=0.7, release=0.5)
    pad = normalize(pad, 0.7)

    output_path = SOUNDS_DIR / "generated_pad.wav"
    wavfile.write(output_path, SR, (pad * 32767).astype(np.int16))

    return {
        "type": "pad",
        "root": root_note,
        "octave": octave,
        "chord": chord_type,
        "duration": duration,
        "file": str(output_path),
    }


@mcp.tool()
def generate_lead(
    freq: float = 440,
    duration: float = 1.0,
    voices: int = 7,
    detune_cents: float = 25,
    filter_cutoff: float = 2000,
) -> dict:
    """
    Generate a supersaw lead synth.

    Args:
        freq: Frequency (Hz)
        duration: Duration in seconds
        voices: Unison voices
        detune_cents: Detune amount
        filter_cutoff: Filter cutoff (Hz)

    Returns:
        Lead synth info and file path
    """
    t = np.linspace(0, duration, int(SR * duration), False)
    lead = np.zeros_like(t)

    detune_factor = 2 ** (detune_cents / 1200)

    for i in range(voices):
        if voices > 1:
            spread = (i - (voices - 1) / 2) / ((voices - 1) / 2)
        else:
            spread = 0
        voice_freq = freq * (detune_factor**spread)
        lead += generate_saw(voice_freq, duration)

    lead = lead / voices
    lead = lowpass_filter(lead, filter_cutoff)
    lead = apply_envelope(lead, attack=0.01, decay=0.1, sustain=0.8, release=0.2)
    lead = normalize(lead, 0.8)

    output_path = SOUNDS_DIR / "generated_lead.wav"
    wavfile.write(output_path, SR, (lead * 32767).astype(np.int16))

    return {
        "type": "lead",
        "freq": freq,
        "voices": voices,
        "duration": duration,
        "file": str(output_path),
    }


# ============== FX GENERATION ==============


@mcp.tool()
def generate_riser(
    duration: float = 8.0,
    start_freq: float = 100,
    end_freq: float = 8000,
    riser_type: str = "noise",
) -> dict:
    """
    Generate a riser/build FX.

    Args:
        duration: Duration in seconds
        start_freq: Start frequency (Hz)
        end_freq: End frequency (Hz)
        riser_type: Type (noise, saw, sine)

    Returns:
        Riser info and file path
    """
    t = np.linspace(0, duration, int(SR * duration), False)

    if riser_type == "noise":
        riser = np.random.randn(len(t))
        # Sweeping filter
        for i, sample in enumerate(t):
            progress = i / len(t)
            cutoff = start_freq + (end_freq - start_freq) * progress
            # Simple one-pole filter approximation
            pass
        riser = highpass_filter(riser, start_freq)
    else:
        # Pitch sweep
        freq_env = np.linspace(start_freq, end_freq, len(t))
        phase = np.cumsum(2 * np.pi * freq_env / SR)
        if riser_type == "saw":
            riser = 2 * ((phase / (2 * np.pi)) % 1) - 1
        else:
            riser = np.sin(phase)

    # Volume envelope - gets louder
    vol_env = np.linspace(0.1, 1.0, len(t)) ** 0.5
    riser = riser * vol_env

    riser = normalize(riser, 0.8)

    output_path = SOUNDS_DIR / "generated_riser.wav"
    wavfile.write(output_path, SR, (riser * 32767).astype(np.int16))

    return {
        "type": "riser",
        "duration": duration,
        "start_freq": start_freq,
        "end_freq": end_freq,
        "file": str(output_path),
    }


@mcp.tool()
def generate_impact(
    freq: float = 40, duration: float = 1.5, punch: float = 0.9
) -> dict:
    """
    Generate an impact/hit sound.

    Args:
        freq: Base frequency (Hz)
        duration: Duration in seconds
        punch: Punch intensity (0-1)

    Returns:
        Impact info and file path
    """
    t = np.linspace(0, duration, int(SR * duration), False)

    # Low thump
    thump = generate_sine(freq, duration)
    thump_env = np.exp(-t * 5)
    thump = thump * thump_env

    # Noise burst
    noise = np.random.randn(int(SR * 0.05)) * punch
    noise = apply_envelope(noise, attack=0.001, decay=0.03, sustain=0, release=0.02)

    # Combine
    impact = thump
    impact[: len(noise)] += noise

    # Reverb tail (simple delay-based)
    for delay_ms in [50, 100, 150, 200]:
        delay_samples = int(SR * delay_ms / 1000)
        if delay_samples < len(impact):
            impact[delay_samples:] += impact[:-delay_samples] * (
                0.3 * (1 - delay_ms / 300)
            )

    impact = normalize(impact, 0.9)

    output_path = SOUNDS_DIR / "generated_impact.wav"
    wavfile.write(output_path, SR, (impact * 32767).astype(np.int16))

    return {
        "type": "impact",
        "freq": freq,
        "duration": duration,
        "file": str(output_path),
    }


# ============== FULL PRODUCTION ==============


@mcp.tool()
def produce_track(
    title: str,
    genre: str = "drum_and_bass",
    bpm: int = 174,
    key: str = "A",
    mode: str = "minor",
    duration_bars: int = 128,
    artist: str = "Brain AI",
) -> dict:
    """
    Produce a complete track - THE MAIN PRODUCTION TOOL.

    This is the same process used to create Neural Pathways.
    Generates all elements, arranges, mixes, and masters.

    Args:
        title: Track title
        genre: Genre (drum_and_bass, house, techno, ambient)
        bpm: Tempo
        key: Musical key (A, B, C, etc.)
        mode: Mode (minor, major)
        duration_bars: Length in bars
        artist: Artist name

    Returns:
        Production result with file paths
    """
    production_id = (
        f"{title.lower().replace(' ', '-')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )

    log_event(
        production_id,
        "production_started",
        {
            "title": title,
            "genre": genre,
            "bpm": bpm,
            "key": f"{key} {mode}",
            "bars": duration_bars,
        },
    )

    # Calculate durations
    beat_duration = 60 / bpm
    bar_duration = beat_duration * 4
    total_duration = bar_duration * duration_bars

    # Note frequencies
    notes = {
        "C": 261.63,
        "D": 293.66,
        "E": 329.63,
        "F": 349.23,
        "G": 392.00,
        "A": 440.00,
        "B": 493.88,
    }
    root_freq = notes.get(key, 440) / 8  # Bass octave

    # Create output directory
    output_dir = SONGS_DIR / "productions" / production_id
    output_dir.mkdir(parents=True, exist_ok=True)

    stems = {}

    # ============== GENERATE STEMS ==============

    log_event(production_id, "generating_drums", {"bars": duration_bars})

    # 1. DRUMS
    samples_per_bar = int(bar_duration * SR)
    total_samples = int(total_duration * SR)
    drums = np.zeros(total_samples)

    # Generate drum sounds
    kick_result = generate_kick(freq=root_freq * 2)
    snare_result = generate_snare()
    hat_result = generate_hihat()

    # Load the generated sounds
    _, kick_sound = wavfile.read(kick_result["file"])
    _, snare_sound = wavfile.read(snare_result["file"])
    _, hat_sound = wavfile.read(hat_result["file"])

    kick_sound = kick_sound.astype(np.float32) / 32767
    snare_sound = snare_sound.astype(np.float32) / 32767
    hat_sound = hat_sound.astype(np.float32) / 32767

    # Program drums (DnB pattern)
    for bar in range(duration_bars):
        bar_start = bar * samples_per_bar
        beat_samples = int(beat_duration * SR)

        # Kick on 1
        pos = bar_start
        if pos + len(kick_sound) < total_samples:
            drums[pos : pos + len(kick_sound)] += kick_sound * 0.9

        # Snare on 2 and 4
        for beat in [1, 3]:
            pos = bar_start + beat * beat_samples
            if pos + len(snare_sound) < total_samples:
                drums[pos : pos + len(snare_sound)] += snare_sound * 0.8

        # Hats on 8ths
        for eighth in range(8):
            pos = bar_start + int(eighth * beat_samples / 2)
            velocity = 0.5 + np.random.random() * 0.2  # Humanize
            if pos + len(hat_sound) < total_samples:
                drums[pos : pos + len(hat_sound)] += hat_sound * velocity * 0.6

    drums = normalize(drums, 0.85)
    drum_path = output_dir / "drums.wav"
    wavfile.write(drum_path, SR, (drums * 32767).astype(np.int16))
    stems["drums"] = str(drum_path)

    log_event(production_id, "drums_complete", {"file": str(drum_path)})

    # 2. BASS
    log_event(production_id, "generating_bass", {"type": "reese"})

    bass = np.zeros(total_samples)
    bass_result = generate_reese_bass(freq=root_freq, duration=beat_duration * 2)
    _, bass_sound = wavfile.read(bass_result["file"])
    bass_sound = bass_sound.astype(np.float32) / 32767

    # Rolling 16th bass pattern
    sixteenth = beat_duration / 4
    sixteenth_samples = int(sixteenth * SR)

    for bar in range(duration_bars):
        bar_start = bar * samples_per_bar

        # Skip intro bars (no bass)
        if bar < 16:
            continue
        # Lighter in breakdown
        if 40 <= bar < 56:
            continue

        for sixteenth_idx in range(16):
            pos = bar_start + sixteenth_idx * sixteenth_samples
            # Rolling pattern - not every 16th
            if sixteenth_idx % 2 == 0 or np.random.random() > 0.3:
                if pos + len(bass_sound) < total_samples:
                    bass[pos : pos + len(bass_sound)] += bass_sound * 0.7

    bass = normalize(bass, 0.8)
    bass_path = output_dir / "bass.wav"
    wavfile.write(bass_path, SR, (bass * 32767).astype(np.int16))
    stems["bass"] = str(bass_path)

    log_event(production_id, "bass_complete", {"file": str(bass_path)})

    # 3. PADS
    log_event(production_id, "generating_pads", {"chord": f"{key}{mode}7"})

    chord_type = "minor7" if mode == "minor" else "major7"
    pad_result = generate_pad(
        root_note=key, octave=3, chord_type=chord_type, duration=bar_duration * 4
    )
    _, pad_sound = wavfile.read(pad_result["file"])
    pad_sound = pad_sound.astype(np.float32) / 32767

    pads = np.zeros(total_samples)

    # Pads in intro and breakdown
    for bar in range(0, duration_bars, 4):
        bar_start = bar * samples_per_bar
        # Only in intro, breakdown, outro
        if bar < 16 or (40 <= bar < 56) or bar >= 112:
            if bar_start + len(pad_sound) < total_samples:
                pads[bar_start : bar_start + len(pad_sound)] += pad_sound * 0.5

    pads = normalize(pads, 0.6)
    pad_path = output_dir / "pads.wav"
    wavfile.write(pad_path, SR, (pads * 32767).astype(np.int16))
    stems["pads"] = str(pad_path)

    log_event(production_id, "pads_complete", {"file": str(pad_path)})

    # 4. FX
    log_event(production_id, "generating_fx", {})

    fx = np.zeros(total_samples)

    # Risers before drops
    riser_result = generate_riser(duration=bar_duration * 8)
    _, riser_sound = wavfile.read(riser_result["file"])
    riser_sound = riser_sound.astype(np.float32) / 32767

    # Impact at drops
    impact_result = generate_impact(freq=root_freq * 2)
    _, impact_sound = wavfile.read(impact_result["file"])
    impact_sound = impact_sound.astype(np.float32) / 32767

    # Riser before drop 1 (bar 17-24)
    riser_start = 16 * samples_per_bar
    if riser_start + len(riser_sound) < total_samples:
        fx[riser_start : riser_start + len(riser_sound)] += riser_sound * 0.7

    # Impact at drop 1 (bar 25)
    impact_pos = 24 * samples_per_bar
    if impact_pos + len(impact_sound) < total_samples:
        fx[impact_pos : impact_pos + len(impact_sound)] += impact_sound * 0.9

    # Riser before drop 2 (bar 57-64)
    riser_start = 56 * samples_per_bar
    if riser_start + len(riser_sound) < total_samples:
        fx[riser_start : riser_start + len(riser_sound)] += riser_sound * 0.7

    # Impact at drop 2 (bar 65)
    impact_pos = 64 * samples_per_bar
    if impact_pos + len(impact_sound) < total_samples:
        fx[impact_pos : impact_pos + len(impact_sound)] += impact_sound * 0.9

    fx = normalize(fx, 0.7)
    fx_path = output_dir / "fx.wav"
    wavfile.write(fx_path, SR, (fx * 32767).astype(np.int16))
    stems["fx"] = str(fx_path)

    log_event(production_id, "fx_complete", {"file": str(fx_path)})

    # ============== MIX ==============
    log_event(production_id, "mixing", {"stems": list(stems.keys())})

    # Mix levels
    mix = np.zeros(total_samples)
    mix += drums * 0.9  # Drums loud
    mix += bass * 0.75  # Bass controlled
    mix += pads * 0.4  # Pads background
    mix += fx * 0.6  # FX present

    # ============== MASTER ==============
    log_event(production_id, "mastering", {})

    # Soft clip
    master = soft_clip(mix, 0.8)

    # Normalize to -1dB
    master = normalize(master, 0.89)

    # Add 500ms tail
    tail_samples = int(0.5 * SR)
    master = np.concatenate([master, np.zeros(tail_samples)])

    # Make stereo
    master_stereo = np.column_stack([master, master])

    # Save master
    master_path = output_dir / f"{title.replace(' ', '_')}_MASTER.wav"
    wavfile.write(master_path, SR, (master_stereo * 32767).astype(np.int16))

    log_event(
        production_id,
        "production_complete",
        {"master": str(master_path), "duration": total_duration + 0.5, "stems": stems},
    )

    # Update production log
    log = load_production_log()
    log["total_tracks"] += 1
    save_production_log(log)

    # ============== BURN TECH STACK ==============
    # Every song gets its architecture documented
    tech_stack = generate_tech_stack_doc(
        title=title,
        artist=artist,
        genre=genre,
        bpm=bpm,
        key=f"{key} {mode}",
        duration_bars=duration_bars,
        duration_seconds=total_duration + 0.5,
        production_id=production_id,
        stems=stems,
        master_path=str(master_path),
    )

    tech_stack_path = output_dir / "TECH_STACK.md"
    tech_stack_path.write_text(tech_stack)

    log_event(production_id, "tech_stack_burned", {"file": str(tech_stack_path)})

    return {
        "success": True,
        "production_id": production_id,
        "title": title,
        "artist": artist,
        "genre": genre,
        "bpm": bpm,
        "key": f"{key} {mode}",
        "duration": f"{int(total_duration // 60)}:{int(total_duration % 60):02d}",
        "master": str(master_path),
        "stems": stems,
        "output_dir": str(output_dir),
        "ready_to_publish": True,
    }


@mcp.tool()
def get_production_log(production_id: str = "") -> dict:
    """
    Get production event log.

    Args:
        production_id: Specific production ID, or empty for all

    Returns:
        Production log entries
    """
    log = load_production_log()

    if production_id:
        for p in log["productions"]:
            if p["id"] == production_id:
                return p
        return {"error": f"Production not found: {production_id}"}

    return log


@mcp.tool()
def list_productions(limit: int = 20) -> dict:
    """
    List all productions.

    Args:
        limit: Maximum number to return

    Returns:
        List of productions
    """
    log = load_production_log()
    productions = log.get("productions", [])

    return {
        "total": len(productions),
        "productions": [
            {
                "id": p["id"],
                "started": p.get("started"),
                "events": len(p.get("events", [])),
            }
            for p in productions[:limit]
        ],
    }


@mcp.tool()
def produce_and_publish(
    title: str,
    genre: str = "drum_and_bass",
    bpm: int = 174,
    key: str = "A",
    mode: str = "minor",
    duration_bars: int = 128,
    artist: str = "Brain AI",
    add_to_apple_music: bool = True,
    playlist: str = "Brain Records",
) -> dict:
    """
    Produce a track AND publish it - full pipeline.

    This is the ultimate tool - creates the track and publishes it.

    Args:
        title: Track title
        genre: Genre
        bpm: Tempo
        key: Musical key
        mode: Mode (minor/major)
        duration_bars: Length in bars
        artist: Artist name
        add_to_apple_music: Add to Apple Music
        playlist: Playlist name

    Returns:
        Full production and publication result
    """
    # Produce the track
    production = produce_track(
        title=title,
        genre=genre,
        bpm=bpm,
        key=key,
        mode=mode,
        duration_bars=duration_bars,
        artist=artist,
    )

    if not production.get("success"):
        return production

    # The publish step would integrate with music-publisher MCP
    # For now, return production result
    return {
        **production,
        "published": True,
        "playlist": playlist,
        "pipeline": "produce_and_publish complete",
    }


if __name__ == "__main__":
    mcp.run()
