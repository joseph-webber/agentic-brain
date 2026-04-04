# BrainChat Swift

BrainChat is the Swift client for the Agentic Brain project, built for accessible macOS interactions with VoiceOver, keyboard-first navigation, and voice features.

**Location:** `apps/BrainChat/` (not `tools/BrainChat`)

## Documentation

- [Comprehensive Accessibility Guide](./docs/ACCESSIBILITY.md) ♿
- [Deployment Guide](./DEPLOYMENT.md)
- [Voice Coding Guide](./docs/VOICE_CODING_GUIDE.md)
- [Security Quick Reference](./SECURITY-QUICK-REFERENCE.md)
- [AppleScript E2E Tests](./Scripts/AppleScript/README.md)

## Security Modes

| Mode | Access |
|------|--------|
| FULL_ADMIN | Unrestricted owner mode |
| SAFE_ADMIN | YOLO allowed with guardrails and confirmations |
| USER | API access only |
| GUEST | Help and FAQ only |

See the [Security Quick Reference](./SECURITY-QUICK-REFERENCE.md) for the full permission matrix.

## ♿ Accessibility

BrainChat is designed for **WCAG 2.1 AAA compliance** — the highest accessibility standard.

**See full guide:** [Comprehensive Accessibility Documentation](./docs/ACCESSIBILITY.md)

### For VoiceOver Users
- All controls are labeled and keyboard accessible
- Use Cmd+L to toggle microphone
- Use Cmd+. to stop voice output
- Navigate with standard VoiceOver gestures
- Press Cmd+? for keyboard shortcuts help

### Keyboard Shortcuts
| Shortcut | Action |
|----------|--------|
| ⌘L | Toggle mic |
| ⌘. | Stop voice |
| ⌘, | Settings |
| ⌘K | Clear chat |
| ⌘? | Show all shortcuts |

**Full reference:** See [KEYBOARD_SHORTCUTS.md](./KEYBOARD_SHORTCUTS.md)

### Response Time
- Text: 51-100ms average
- Voice: <200ms to first word

---

## Build & Test

```bash
# Navigate to BrainChat directory
cd apps/BrainChat

# Build in debug mode
swift build

# Run unit tests (parallel)
swift test --parallel

# Build release version
swift build -c release

# Run specific test suite
swift test --filter SecurityTests
```

## Deployment

For build, install, security mode, CI/CD, and troubleshooting instructions, see the [BrainChat Deployment Guide](./DEPLOYMENT.md).
