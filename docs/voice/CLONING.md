# Voice Cloning with F5-TTS

Voice cloning is **local-only** in Agentic Brain.

- Reference audio stays on your device.
- Cloned voice metadata is stored in `~/.agentic-brain/voices/`.
- No voice samples are uploaded to cloud services.

## What this feature does

`VoiceCloner` wraps the optional [F5-TTS](https://github.com/SWivid/F5-TTS) zero-shot cloning flow.

F5-TTS does not require a heavy training step for each new voice. Instead, Agentic Brain stores:

- a reference audio sample
- optional reference transcript text
- lady assignment metadata
- validation details and fallback settings

At synthesis time, the stored sample is passed to F5-TTS.

## Installation

F5-TTS is optional. The rest of the voice stack works without it.

### Apple Silicon / M2

```bash
pip install torch torchaudio
pip install f5-tts
```

F5-TTS also expects FFmpeg to be available for reliable audio handling:

```bash
brew install ffmpeg
```

Official F5-TTS guidance also recommends:

- Python 3.10+
- reference audio under about 12 seconds
- providing reference text when possible for best results

## Storage layout

By default, clones are stored here:

```text
~/.agentic-brain/voices/
```

You can override that location for development or testing:

```bash
export AGENTIC_BRAIN_VOICE_CLONE_DIR=/path/to/custom/voice-store
```

Each voice gets its own folder with:

- `profile.json`
- copied reference audio
- generated renders

## CLI usage

Create a clone:

```bash
ab voice clone /path/to/sample.wav --name "custom_karen"
```

List clones:

```bash
ab voice clone --list
```

Delete a clone:

```bash
ab voice clone --delete custom-karen-1234abcd
```

Assign a clone to a lady persona:

```bash
ab voice clone --assign custom-karen-1234abcd --lady karen
```

## Python usage

```python
from agentic_brain.voice.voice_cloning import VoiceCloner

cloner = VoiceCloner()

voice_id = cloner.clone_voice(
    "samples/karen.wav",
    name="custom_karen",
    reference_text="Hello there, I'm ready when you are.",
    assigned_lady="karen",
)

audio_path = cloner.synthesize_with_voice(
    "This is a local cloned voice test.",
    voice_id,
)

print(audio_path)
```

## Validation rules

Agentic Brain validates reference audio before storing it.

Current checks:

- file exists and is non-empty
- WAV metadata can be read when available
- warns on audio shorter than 1 second
- warns on audio longer than 12 seconds
- warns on sample rates below 16 kHz
- warns when audio appears almost silent

## Graceful fallback

If F5-TTS is not installed or inference fails:

1. the cloned voice profile is still stored locally
2. Agentic Brain falls back to a local lady/system voice when possible
3. if no system synthesis path is available, it generates a tiny local WAV fallback instead of failing hard

This keeps the voice workflow usable even before F5-TTS is installed.

## Privacy notes

- Voice samples remain local.
- Export/import uses local archive files only.
- There is no cloud sync in the cloning path.

## Export and import

`VoiceLibrary` supports local archive workflows:

```python
from agentic_brain.voice.voice_library import VoiceLibrary

library = VoiceLibrary()
archive = library.export_voice(voice_id, "exports/custom_karen.zip")
restored = library.import_voice(archive)
```

This is useful for moving a clone between local machines you control.
