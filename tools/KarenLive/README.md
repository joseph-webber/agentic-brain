# KarenLive - Native Swift Voice Chat

A menu bar app that provides voice conversation with Claude using Karen voice.

## Features
- 🧠 Brain icon in menu bar
- Click to start/stop listening
- Uses macOS native SFSpeechRecognizer (no Whisper needed)
- Calls Claude API for responses
- Speaks responses with Karen (Australian) voice
- 2-second silence detection triggers processing

## Requirements
- macOS 13.0+
- Microphone permission
- Speech Recognition permission
- Claude API key in `~/.anthropic_api_key` or `ANTHROPIC_API_KEY` env var

## Usage

### Launch
```bash
./run.sh
# or
open KarenLive.app
```

### Operation
1. Click the 🧠 brain icon in menu bar
2. Icon changes to 🎤 - now listening
3. Speak your question
4. After 2 seconds of silence, it processes
5. Karen speaks the response
6. Click again to stop/start new conversation

### Quit
- Right-click menu bar icon → Quit
- Or Cmd+Q when focused

## Building from Source

```bash
swiftc -o KarenLive.app/Contents/MacOS/KarenLive KarenLive.swift \
    -framework AVFoundation \
    -framework Speech \
    -framework Cocoa \
    -parse-as-library \
    -O

codesign --force --deep --sign - KarenLive.app
```

## Files
- `KarenLive.swift` - Main source code
- `KarenLive.app/` - Built application bundle
- `run.sh` - Launch script

## Accessibility
Built with accessibility in mind:
- Audio-first interface
- Announces state changes
- Uses Karen voice for clarity
- No visual-only feedback

## API Key Setup
```bash
# Option 1: Environment variable
export ANTHROPIC_API_KEY="sk-ant-..."

# Option 2: File (more reliable for GUI apps)
echo "sk-ant-..." > ~/.anthropic_api_key
chmod 600 ~/.anthropic_api_key
```
