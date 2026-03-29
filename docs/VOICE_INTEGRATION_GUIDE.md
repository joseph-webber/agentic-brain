# Cross-Platform Voice Integration Guide

Quick guide for integrating cross-platform voice into your application.

## Installation

### Option 1: Basic (macOS only)
```bash
pip install agentic-brain
```

### Option 2: Cross-Platform
```bash
pip install agentic-brain pyttsx3 gTTS
```

### Option 3: Full Featured
```bash
pip install agentic-brain pyttsx3 gTTS azure-cognitiveservices-speech boto3
```

## Quick Integration

### 1. Basic Usage
```python
from agentic_brain.voice.resilient import speak

async def my_function():
    # Just speak - works everywhere!
    await speak("Hello world!")
```

### 2. Custom Configuration
```python
from agentic_brain.voice.resilient import ResilientVoice, VoiceConfig

config = VoiceConfig(
    default_voice="Karen",
    default_rate=155,
    timeout=30,
    enable_fallbacks=True
)

voice = ResilientVoice(config)
await voice.speak("Custom configuration!")
```

### 3. Platform Detection
```python
from agentic_brain.voice.platform import detect_platform, VoicePlatform

platform = detect_platform()

if platform == VoicePlatform.MACOS:
    await speak("Mac detected", voice="Karen")
elif platform == VoicePlatform.WINDOWS:
    await speak("Windows detected", voice="Microsoft Zira")
elif platform == VoicePlatform.LINUX:
    await speak("Linux detected", voice="en-us")
```

### 4. Error Handling
```python
try:
    success = await speak("Important message")
    if not success:
        # Even if all voice methods fail, this rarely happens
        # due to multiple fallback layers
        logger.warning("Voice failed (very rare!)")
except Exception as e:
    logger.error(f"Voice error: {e}")
```

### 5. Background Voice Daemon
```python
from agentic_brain.voice.resilient import get_daemon

# Start daemon
daemon = await get_daemon()

# Queue messages (non-blocking)
await daemon.speak("First message")
await daemon.speak("Second message")
await daemon.speak("Third message")

# Check stats
stats = daemon.get_stats()
print(f"Processed: {stats['processed']}")

# Stop daemon
await daemon.stop()
```

### 6. Voice Statistics
```python
from agentic_brain.voice.resilient import get_voice_stats

# After speaking some text
stats = get_voice_stats()

for method, data in stats['voice'].items():
    print(f"{method}: {data['success_rate']}")
```

## Platform-Specific Instructions

### Windows Users
1. Install pyttsx3:
   ```bash
   pip install pyttsx3
   ```

2. If you get "No module named 'win32com'":
   ```bash
   pip install pywin32
   ```

3. List available voices:
   ```python
   from agentic_brain.voice.windows import list_windows_voices
   voices = await list_windows_voices()
   for voice in voices:
       print(voice['name'])
   ```

### Linux Users
1. Install espeak (recommended):
   ```bash
   # Ubuntu/Debian
   sudo apt install espeak-ng
   
   # Fedora/RHEL
   sudo dnf install espeak-ng
   
   # Arch
   sudo pacman -S espeak-ng
   ```

2. Install Python library:
   ```bash
   pip install pyttsx3
   ```

3. Alternative: speech-dispatcher
   ```bash
   sudo apt install speech-dispatcher
   ```

4. List available voices:
   ```python
   from agentic_brain.voice.linux import list_linux_voices
   voices = await list_linux_voices()
   for voice in voices:
       print(voice['name'])
   ```

### macOS Users
No installation needed! The `say` command is built-in.

Optional: Install cloud fallback for redundancy:
```bash
pip install gTTS
```

## Cloud TTS Setup (Optional)

### Google TTS (Free)
```bash
pip install gTTS
```

No API key needed! Just works with internet connection.

```python
from agentic_brain.voice.cloud_tts import speak_cloud
await speak_cloud("Hello!", provider="gtts")
```

### Azure Speech
```bash
pip install azure-cognitiveservices-speech

export AZURE_SPEECH_KEY="your_key"
export AZURE_SPEECH_REGION="eastus"
```

```python
await speak_cloud("Hello!", provider="azure", voice="en-US-JennyNeural")
```

### AWS Polly
```bash
pip install boto3

export AWS_ACCESS_KEY_ID="your_key"
export AWS_SECRET_ACCESS_KEY="your_secret"
```

```python
await speak_cloud("Hello!", provider="polly", voice="Joanna")
```

## Testing

### Test Your Integration
```python
# Simple test
await speak("Testing voice integration")

# Check platform detection
from agentic_brain.voice.platform import check_voice_available
availability = check_voice_available()
print("Available systems:", [k for k, v in availability.items() if v])
```

### Run Demo Script
```bash
cd examples
python3 demo_cross_platform_voice.py
```

### Run Tests
```bash
# All tests
pytest tests/voice/test_cross_platform_voice.py -v

# Quick tests only (no integration)
pytest tests/voice/test_cross_platform_voice.py -v -m "not integration"
```

## Common Issues

### "No voice system available"
**Solution**: Install platform-specific TTS:
- Windows: `pip install pyttsx3`
- Linux: `sudo apt install espeak-ng && pip install pyttsx3`
- Fallback: `pip install gTTS` (requires internet)

### Windows: "pyttsx3 init failed"
**Solution**: Install pywin32:
```bash
pip install pywin32
```

### Linux: "espeak: command not found"
**Solution**: Install espeak:
```bash
sudo apt install espeak-ng
```

### Cloud TTS: "Network error"
**Solution**: 
1. Check internet connection
2. Check firewall settings
3. Verify API keys (for Azure/AWS)

## Best Practices

### 1. Always Use Async
```python
# Good
await speak("Hello")

# Bad
speak("Hello")  # This won't work!
```

### 2. Handle Long Text
```python
# For very long text, consider splitting
long_text = "..." * 1000
chunks = [long_text[i:i+500] for i in range(0, len(long_text), 500)]
for chunk in chunks:
    await speak(chunk)
```

### 3. Platform Detection Once
```python
# Detect once at startup
from agentic_brain.voice.platform import detect_platform
PLATFORM = detect_platform()

# Use throughout app
if PLATFORM == VoicePlatform.WINDOWS:
    # Windows-specific code
```

### 4. Use Voice Daemon for Multiple Messages
```python
# Bad (blocks on each message)
await speak("Message 1")
await speak("Message 2")
await speak("Message 3")

# Good (queues all messages)
daemon = await get_daemon()
await daemon.speak("Message 1")
await daemon.speak("Message 2")
await daemon.speak("Message 3")
```

### 5. Log Voice Failures
```python
success = await speak("Important message")
if not success:
    logger.warning("Voice failed - user may not have heard message")
```

## Example: Accessibility Application

```python
import asyncio
from agentic_brain.voice.resilient import speak, get_daemon
from agentic_brain.voice.platform import detect_platform, VoicePlatform

class AccessibleApp:
    def __init__(self):
        self.platform = detect_platform()
        self.daemon = None
    
    async def start(self):
        """Initialize voice system"""
        self.daemon = await get_daemon()
        
        # Welcome message
        if self.platform == VoicePlatform.MACOS:
            await speak("Welcome to the accessible app on Mac")
        elif self.platform == VoicePlatform.WINDOWS:
            await speak("Welcome to the accessible app on Windows")
        elif self.platform == VoicePlatform.LINUX:
            await speak("Welcome to the accessible app on Linux")
        else:
            await speak("Welcome to the accessible app")
    
    async def notify(self, message: str, urgent: bool = False):
        """Send voice notification"""
        rate = 180 if urgent else 155
        await speak(message, rate=rate)
    
    async def stop(self):
        """Clean shutdown"""
        if self.daemon:
            await self.daemon.stop()

# Usage
async def main():
    app = AccessibleApp()
    await app.start()
    
    # Regular notification
    await app.notify("You have a new message")
    
    # Urgent notification
    await app.notify("Alert! Action required!", urgent=True)
    
    await app.stop()

asyncio.run(main())
```

## Support

- **Documentation**: See `docs/CROSS_PLATFORM_VOICE.md`
- **Issues**: Report at github.com/agentic-brain-project/agentic-brain/issues
- **Examples**: Check `examples/demo_cross_platform_voice.py`

## License

Apache-2.0

Built with ❤️ for accessibility by Agentic Brain Contributors
