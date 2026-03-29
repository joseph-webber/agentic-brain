# Live Mode — Project Aria

## Overview

**Project Aria** is the live, hands-free voice conversation feature of Agentic
Brain.  Joseph speaks, the brain listens, transcribes, thinks, and responds
— all with voice.  No typing needed.

### Architecture

```text
microphone
    → wake word detection ("Hey Karen" / "Hey Brain")
    → whisper.cpp transcription (offline, M2-accelerated)
    → agent / response callback
    → VoiceSerializer (safe, no-overlap playback)
```

The output side (serializer, speech lock, spatial routing, event topics) has
been stable since Phase 2.  Project Aria adds the **input side**: microphone
capture, wake-word gating, and speech-to-text.

### Key modules

| Module | Purpose |
|--------|---------|
| `voice/live_session.py` | `LiveVoiceSession` — bidirectional session |
| `voice/transcription.py` | `WhisperTranscriber` / `MacOSDictationTranscriber` |
| `voice/live_daemon.py` | `LiveVoiceDaemon` — background daemon + PID file |
| `cli/voice_commands.py` | `ab voice live` CLI surface |

---

## CLI Usage

### Start a live session

```bash
# Defaults: whisper.cpp, wake words "Hey Karen" / "Hey Brain", 30s timeout
ab voice live start

# Custom wake word
ab voice live start --wake-word "Hey Iris"

# Multiple wake words (comma-separated)
ab voice live start --wake-word "Hey Karen,Hey Brain,Hey Iris"

# Custom timeout (seconds of silence before auto-stop)
ab voice live start --timeout 60

# Use macOS dictation instead of whisper.cpp
ab voice live start --transcriber macos

# Explicit whisper.cpp (the default)
ab voice live start --transcriber whisper

# Custom voice and rate
ab voice live start -v Moira -r 140

# All options combined
ab voice live start --wake-word "Hey Iris" --timeout 45 --transcriber whisper -v Karen -r 155
```

### Stop a live session

```bash
ab voice live stop

# Or use the flag shortcut
ab voice live --stop
```

### Check status

```bash
ab voice live status
ab voice live          # same as "status"
ab voice live --status # flag shortcut
```

### Daemon mode (background)

Run the session as a background daemon with PID file management:

```bash
# Start daemon
ab voice live start --daemon

# Check daemon status
ab voice live status --daemon

# Stop daemon
ab voice live stop --daemon
```

The daemon writes its PID to `~/.agentic-brain/live-voice.pid` and session
state to `~/.agentic-brain/live-voice-state.json`.

### Auto-start at login (launchd)

```bash
# Install the launchd plist
ab voice live install

# Load it now
launchctl load ~/Library/LaunchAgents/com.agentic-brain.live-voice.plist

# Remove it
ab voice live uninstall
```

---

## Transcription backends

### 1. whisper.cpp (preferred)

Local, fast, fully offline transcription via `pywhispercpp`.  Runs on
Apple Silicon with excellent latency.

```bash
pip install pywhispercpp
```

Models are downloaded automatically to `~/.cache/whisper/` on first use.
Default model: `base.en` (good balance of speed and accuracy).

### 2. macOS Dictation (fallback)

When whisper.cpp is not installed, the system falls back to macOS
`SFSpeechRecognizer`.  Requires:
- macOS (Darwin)
- Dictation enabled in System Preferences → Keyboard → Dictation
- Speech recognition permission granted

Use explicitly with `--transcriber macos`.

---

## Wake words

Default wake words: **"Hey Karen"** and **"Hey Brain"**.

Wake word detection works by continuously transcribing short audio chunks
and checking for a match.  This is simple but effective for the offline
use case.

Customise via CLI:

```bash
ab voice live start --wake-word "Hey Iris"
```

---

## Timeout behaviour

- **Utterance silence**: 2 seconds of silence marks end-of-utterance
- **Session timeout**: 30 seconds of silence auto-stops the session
  (configurable with `--timeout`)

---

## Interrupt detection

If Joseph speaks while the brain is talking, the current speech is
immediately terminated.  This is critical for accessibility — the user
must always be able to interrupt.

---

## Troubleshooting

### "Microphone unavailable"

Install PyAudio:

```bash
pip install pyaudio
```

On macOS you may also need:

```bash
brew install portaudio
pip install pyaudio
```

### "pywhispercpp not installed"

```bash
pip install pywhispercpp
```

The system will fall back to macOS dictation, but whisper.cpp is
strongly recommended for offline, low-latency transcription.

### Session stops immediately

Check the timeout value.  The default 30s timeout means the session
ends after 30 seconds with no voice input.  Increase with `--timeout`.

### No wake word detected

Speak clearly and close to the microphone.  The wake word must appear
somewhere in the transcribed text (case-insensitive partial match).

---

## See also

- [Voice system overview](./README.md)
- [Streaming](./STREAMING.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
