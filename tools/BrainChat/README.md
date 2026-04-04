# BrainChat - Accessible Voice AI Chat

**Version**: 2.1 (Complete Settings UI)  
**Status**: ✅ Production Ready  
**Milestone**: Voice Bidirectional Communication Working!

## Overview

BrainChat is a fully accessible macOS voice chat application that enables blind users to interact with AI assistants using speech. The app was developed specifically for Joseph Webber as part of the Agentic Brain project.

## Key Features

### ♿️ Accessibility First
- Full VoiceOver compatibility
- Keyboard navigation (Enter to talk)
- Accessibility labels on ALL controls
- Karen voice (Australian) as default - optimized for clarity

### 🎤 Voice Input
- Apple SFSpeechRecognizer for dictation
- Support for multiple dictation engines:
  - Apple Speech (default, works offline)
  - Whisper (OpenAI, high accuracy)
  - Deepgram (real-time, ultra-fast)

### 🔊 Voice Output
- macOS `say` command (most reliable)
- Configurable voice selection:
  - Karen (Australian - default)
  - Samantha, Daniel, Moira, Tessa, Fiona, Veena
- Speech rate: 175 WPM (adjustable)
- See [VOICE_BENCHMARKS.md](VOICE_BENCHMARKS.md) for latency measurements

### 🤖 Multi-LLM Support
- **Ollama** (Local, free)
- **Groq** (Fast, free tier)
- **Claude** (Anthropic)
- **Gemini** (Google)
- **OpenAI** (GPT)

### 🔐 Security Roles
- **Developer**: Full system access
- **Admin**: Admin with safety guardrails
- **User**: Standard access
- **Guest**: Read-only

### 📊 RAG Integration
- Neo4j knowledge graph connection
- Conversation history stored and searchable
- Context enrichment from emails, teams, and past conversations

## Installation

### Quick Install

```bash
cd tools/BrainChat
./build_and_install.sh
```

This will:
1. Compile BrainChat.swift with required frameworks
2. Sign with Developer ID certificate
3. Install to /Applications

### Manual Build

```bash
swiftc -o build/BrainChat \
    BrainChat.swift \
    -framework Cocoa \
    -framework Speech \
    -framework AVFoundation
```

## Usage

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Start/stop voice capture |
| Cmd+Q | Quit |

### Chat Commands

| Command | Description |
|---------|-------------|
| `/chat` | Switch to chat mode |
| `/code` | Switch to code mode |
| `/voice` | Switch to voice mode |
| `/yolo` | Switch to YOLO (autonomous) mode |
| `/work` | Switch to work mode (CITB professional) |
| `/rag on` | Enable RAG enrichment |
| `/rag off` | Disable RAG enrichment |
| `/rag health` | Check Neo4j connection |

### AppleScript Support

```applescript
tell application "Brain Chat"
    set current mode to "code"
    set theMode to current mode
    set theStatus to status
    set listening to is listening
end tell
```

## Testing

### Run AppleScript Tests

```bash
osascript test_all_features.applescript
```

Expected output: 7/7 tests pass

### Voice Benchmark

```bash
# See VOICE_BENCHMARKS.md for full results
say -v "Karen (Premium)" -r 175 "Test message"
```

## Architecture

```
BrainChat.swift (4490 lines)
├── Enums
│   ├── ChatMode (chat, code, terminal, yolo, voice, work)
│   ├── LLMMode (single, multiBot, consensus)
│   ├── LLMProvider (ollama, groq, claude, gemini, openai)
│   ├── SecurityRole (developer, admin, user, guest)
│   ├── VoiceEngine (systemSay, avSpeech, cartesia, elevenLabs)
│   ├── VoiceOption (Karen, Samantha, Daniel, ...)
│   └── DictationEngine (apple, whisper, deepgram)
├── Settings Structs
│   ├── ModePreferences
│   ├── SecuritySettings
│   ├── VoiceSettings
│   ├── DictationSettings
│   └── RAGSettings
├── Services
│   ├── SpeechVoice (TTS output)
│   ├── RedpandaBridge (event streaming)
│   ├── RAGService (Neo4j integration)
│   └── LLMStreamingClient
└── AppDelegate (UI and orchestration)
```

## Requirements

- macOS 13.0+
- Xcode Command Line Tools
- Microphone permission
- Speech recognition permission
- (Optional) Developer ID certificate for code signing

## Code Signing

The app is signed with:
```
Developer ID Application: Joseph Webber (H6RKDG4RWN)
```

Entitlements:
- `com.apple.security.device.audio-input`
- `com.apple.security.network.client`

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.1 | 2026-04-06 | Complete settings UI with all dropdowns |
| 2.0 | 2026-04-05 | Voice bidirectional milestone |
| 1.0 | 2026-03-31 | Initial working version |

## Tags

- `brainchat-v2.1-complete-settings`
- `brainchat-v2.0-voice-bidirectional`
- `brainchat-v1.0-working`

## License

Apache 2.0 - See [LICENSE](../../LICENSE)

## Author

Created for Joseph Webber (blind consultant) by Iris Lumina (Agentic Brain AI).

---

**Historic Milestone**: This app proves that programming can be accessible to blind people everywhere. 💜
