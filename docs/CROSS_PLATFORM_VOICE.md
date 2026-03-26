# Cross-Platform Voice Support

Complete voice synthesis support for **macOS, Windows, and Linux** with automatic cloud fallback.

## Features

✅ **Platform Detection** - Automatically detects OS and available voice systems  
✅ **Native Voice Support** - Uses platform-specific TTS engines  
✅ **Cloud Fallback** - Google TTS, Azure Speech, AWS Polly  
✅ **Graceful Degradation** - Multiple fallback layers ensure voice NEVER fails  
✅ **Unified API** - Same code works across all platforms  

---

## Quick Start

```python
from agentic_brain.voice.resilient import speak

# Works on macOS, Windows, Linux!
await speak("Hello! Cross-platform voice working!")
```

That's it! The system automatically:
1. Detects your platform
2. Tries native voice first
3. Falls back to cloud TTS if needed
4. Returns True when voice succeeded

---

## Platform Support

### macOS
**Native**: `say` command (built-in, no install needed)  
**Fallback Chain**:
1. `say` with voice and rate
2. `say` with default voice
3. AppleScript voice
4. Cloud TTS (gTTS)
5. Alert sound

```python
# macOS-specific (optional)
await speak("G'day mate!", voice="Karen (Premium)", rate=155)
```

### Windows
**Native**: Windows Speech API (SAPI)  
**Libraries**: `pyttsx3` (recommended)  
**Fallback Chain**:
1. pyttsx3 (SAPI wrapper)
2. PowerShell SAPI commands
3. Cloud TTS (gTTS)

**Install**:
```bash
pip install pyttsx3
```

**Usage**:
```python
await speak("Hello from Windows!", voice="Microsoft Zira", rate=150)
```

**List Available Voices**:
```python
from agentic_brain.voice.windows import list_windows_voices

voices = await list_windows_voices()
for voice in voices:
    print(f"{voice['name']} - {voice['language']}")
```

### Linux
**Native**: espeak, espeak-ng, festival, speech-dispatcher  
**Libraries**: `pyttsx3` (uses espeak backend)  
**Fallback Chain**:
1. pyttsx3 (espeak backend)
2. espeak/espeak-ng direct
3. speech-dispatcher (spd-say)
4. festival
5. Cloud TTS (gTTS)

**Install** (Ubuntu/Debian):
```bash
# espeak (recommended)
sudo apt install espeak espeak-ng

# OR speech-dispatcher
sudo apt install speech-dispatcher

# OR festival
sudo apt install festival

# Python library
pip install pyttsx3
```

**Install** (Fedora/RHEL):
```bash
sudo dnf install espeak-ng
pip install pyttsx3
```

**Usage**:
```python
await speak("Hello from Linux!", voice="en", rate=175)
```

**List Available Voices**:
```python
from agentic_brain.voice.linux import list_linux_voices

voices = await list_linux_voices()
for voice in voices:
    print(f"{voice['name']} - {voice['language']}")
```

---

## Cloud TTS Fallback

When local voice fails, automatically falls back to cloud providers.

### Google TTS (gTTS) - FREE
**No API key needed!** Only requires internet connection.

```bash
pip install gTTS
```

Supports 50+ languages:
```python
from agentic_brain.voice.cloud_tts import speak_cloud

await speak_cloud("Hello!", provider="gtts", lang="en")
await speak_cloud("Bonjour!", provider="gtts", lang="fr")
await speak_cloud("こんにちは", provider="gtts", lang="ja")
```

### Azure Cognitive Services Speech
High-quality neural voices.

**Setup**:
```bash
pip install azure-cognitiveservices-speech

export AZURE_SPEECH_KEY="your_key"
export AZURE_SPEECH_REGION="eastus"
```

**Usage**:
```python
await speak_cloud("Hello!", provider="azure", voice="en-US-JennyNeural")
```

### AWS Polly
Amazon's neural TTS engine.

**Setup**:
```bash
pip install boto3

export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
```

**Usage**:
```python
await speak_cloud("Hello!", provider="polly", voice="Joanna")
```

---

## API Reference

### Main Functions

#### `speak(text, voice=None, rate=155)`
Universal speech function with automatic platform detection and fallback.

```python
await speak("Hello world!")
await speak("Hello world!", voice="Karen", rate=180)
```

**Returns**: `bool` - True if voice succeeded (or fallback succeeded)

#### Platform-Specific Functions

```python
from agentic_brain.voice.windows import speak_windows
from agentic_brain.voice.linux import speak_linux
from agentic_brain.voice.cloud_tts import speak_cloud

# Windows only
await speak_windows("Windows voice", voice="Microsoft Zira", rate=150)

# Linux only
await speak_linux("Linux voice", voice="en-us", rate=175)

# Cloud TTS only
await speak_cloud("Cloud voice", provider="gtts", lang="en")
```

### Platform Detection

```python
from agentic_brain.voice.platform import (
    detect_platform,
    check_voice_available,
    get_recommended_voice_method,
    get_platform_info
)

# Detect current platform
platform = detect_platform()
print(f"Running on: {platform.value}")

# Check what's available
availability = check_voice_available()
print(f"macOS say: {availability['macos_say']}")
print(f"Windows SAPI: {availability['windows_sapi']}")
print(f"Linux espeak: {availability['linux_espeak']}")
print(f"pyttsx3: {availability['pyttsx3']}")
print(f"gTTS: {availability['gtts']}")

# Get recommended method
method = get_recommended_voice_method()
print(f"Recommended: {method}")

# Full platform info
info = get_platform_info()
print(info)
```

### Voice Configuration

```python
from agentic_brain.voice.resilient import VoiceConfig, ResilientVoice

config = VoiceConfig(
    default_voice="Karen",
    default_rate=155,
    timeout=30,
    max_retries=5,
    enable_fallbacks=True,
    log_failures=True
)

voice = ResilientVoice(config)
await voice.speak("Custom configuration!")
```

### Voice Statistics

```python
from agentic_brain.voice.resilient import get_voice_stats

# Speak some text
await speak("Test 1")
await speak("Test 2")

# Get stats
stats = get_voice_stats()
print(f"Success rate: {stats['voice']['say_with_voice']['success_rate']}")
print(f"Total processed: {stats['daemon']['processed']}")
```

---

## Installation

### Minimal (macOS only)
```bash
pip install agentic-brain
```
macOS `say` command works out of the box!

### Windows Support
```bash
pip install agentic-brain[voice]
# OR manually:
pip install pyttsx3
```

### Linux Support
```bash
# Install system TTS engine
sudo apt install espeak-ng  # Ubuntu/Debian
# OR
sudo dnf install espeak-ng  # Fedora/RHEL

# Install Python library
pip install agentic-brain[voice]
# OR manually:
pip install pyttsx3
```

### Full Installation (All Platforms + Cloud)
```bash
pip install agentic-brain[voice,cloud]
# OR manually:
pip install pyttsx3 gTTS azure-cognitiveservices-speech boto3
```

---

## Testing

Run the test suite:

```bash
# All tests
pytest tests/voice/test_cross_platform_voice.py -v

# Platform-specific only
pytest tests/voice/test_cross_platform_voice.py::TestWindowsVoice -v
pytest tests/voice/test_cross_platform_voice.py::TestLinuxVoice -v

# Integration tests (require actual voice systems)
pytest tests/voice/test_cross_platform_voice.py -v -m integration

# Skip integration tests
pytest tests/voice/test_cross_platform_voice.py -v -m "not integration"
```

Test individual modules:

```bash
# Platform detection
python -m agentic_brain.voice.platform

# Windows voice
python -m agentic_brain.voice.windows

# Linux voice
python -m agentic_brain.voice.linux

# Cloud TTS
python -m agentic_brain.voice.cloud_tts

# Resilient voice system
python -m agentic_brain.voice.resilient
```

---

## Troubleshooting

### No Voice Available

**Problem**: `No voice system available on this platform!`

**Solutions**:

**Windows**:
```bash
pip install pyttsx3
```

**Linux**:
```bash
# Try espeak
sudo apt install espeak-ng
pip install pyttsx3

# OR try speech-dispatcher
sudo apt install speech-dispatcher

# OR try festival
sudo apt install festival
```

**All Platforms** (cloud fallback):
```bash
pip install gTTS
```

### Windows - "No module named 'win32com'"

**Problem**: pyttsx3 requires pywin32

**Solution**:
```bash
pip install pywin32
```

### Linux - "espeak: command not found"

**Problem**: espeak not installed

**Solution**:
```bash
# Ubuntu/Debian
sudo apt install espeak espeak-ng

# Fedora/RHEL
sudo dnf install espeak-ng

# Arch Linux
sudo pacman -S espeak-ng
```

### Audio Player Not Found (for gTTS)

**Problem**: No audio player available to play MP3 files

**Solutions**:

**macOS**: Already has `afplay` (built-in)

**Linux**:
```bash
# Try mpg123
sudo apt install mpg123

# OR mpg321
sudo apt install mpg321

# OR ffmpeg
sudo apt install ffmpeg
```

**Windows**: Already has Windows Media Player (built-in)

### Cloud TTS Not Working

**Problem**: gTTS fails with network error

**Solutions**:
1. Check internet connection
2. Check firewall settings
3. Try different provider:
   ```python
   await speak_cloud("Test", provider="azure")
   ```

---

## Architecture

```
Resilient Voice System
│
├── Platform Detection
│   └── Detect OS and available voice systems
│
├── Native Voice Engines
│   ├── macOS: say command
│   ├── Windows: pyttsx3 → PowerShell SAPI
│   └── Linux: pyttsx3 → espeak → spd-say → festival
│
├── Cloud Fallback
│   ├── Google TTS (free, no key)
│   ├── Azure Speech (paid, high quality)
│   └── AWS Polly (paid, neural voices)
│
└── Emergency Fallback
    └── System alert sounds
```

### Fallback Priority

Each platform has optimized fallback chain:

**macOS** (6 fallbacks):
```
say (voice+rate) → say (default) → AppleScript (voice) → 
AppleScript (default) → Cloud TTS → Alert Sound
```

**Windows** (2 fallbacks):
```
pyttsx3 → Cloud TTS
```

**Linux** (4 fallbacks):
```
pyttsx3 → espeak → spd-say → festival → Cloud TTS
```

---

## Performance

| Platform | Method | Latency | Quality | Notes |
|----------|--------|---------|---------|-------|
| **macOS** | `say` | ~50ms | Excellent | Native, best quality |
| **Windows** | pyttsx3 | ~100ms | Good | Uses SAPI |
| **Linux** | espeak | ~80ms | Fair | Robotic but fast |
| **Linux** | pyttsx3 | ~100ms | Fair | Wrapper around espeak |
| **Cloud** | gTTS | ~500ms | Good | Requires internet |
| **Cloud** | Azure | ~300ms | Excellent | Neural voices |
| **Cloud** | Polly | ~400ms | Excellent | Neural voices |

---

## Examples

### Basic Usage

```python
import asyncio
from agentic_brain.voice.resilient import speak

async def main():
    # Simple speak
    await speak("Hello world!")
    
    # With voice and rate
    await speak("Fast speech", rate=200)
    await speak("Slow speech", rate=100)

asyncio.run(main())
```

### Platform-Specific

```python
from agentic_brain.voice.platform import detect_platform, VoicePlatform
from agentic_brain.voice.resilient import speak

async def platform_specific():
    platform = detect_platform()
    
    if platform == VoicePlatform.MACOS:
        await speak("Running on Mac!", voice="Karen (Premium)")
    elif platform == VoicePlatform.WINDOWS:
        await speak("Running on Windows!", voice="Microsoft Zira")
    elif platform == VoicePlatform.LINUX:
        await speak("Running on Linux!", voice="en-us")
```

### Cloud TTS with Language

```python
from agentic_brain.voice.cloud_tts import speak_cloud

async def multilingual():
    # English
    await speak_cloud("Hello!", lang="en")
    
    # Spanish
    await speak_cloud("¡Hola!", lang="es")
    
    # French
    await speak_cloud("Bonjour!", lang="fr")
    
    # Japanese
    await speak_cloud("こんにちは", lang="ja")
```

### Voice Daemon (Background)

```python
from agentic_brain.voice.resilient import get_daemon

async def use_daemon():
    # Get daemon (starts automatically)
    daemon = await get_daemon()
    
    # Queue multiple messages (non-blocking)
    await daemon.speak("First message")
    await daemon.speak("Second message")
    await daemon.speak("Third message")
    
    # Get stats
    stats = daemon.get_stats()
    print(f"Processed: {stats['processed']}")
    
    # Stop daemon
    await daemon.stop()
```

---

## Contributing

Contributions welcome! Please test on your platform before submitting PR.

### Adding New Platform

1. Create `src/agentic_brain/voice/your_platform.py`
2. Implement `speak_your_platform(text, voice, rate) -> bool`
3. Update `platform.py` to detect your platform
4. Add fallback in `resilient.py`
5. Add tests in `tests/voice/`

### Adding New Cloud Provider

1. Add function in `cloud_tts.py`
2. Update `speak_cloud()` fallback chain
3. Document setup and usage
4. Add tests

---

## License

Apache-2.0 - See LICENSE file for details

## Author

Joseph Webber - joseph.webber@me.com

Built with ❤️ for accessibility - ensuring voice works EVERYWHERE!
