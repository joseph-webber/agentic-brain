# BrainChat Swift

BrainChat is the Swift client for the Agentic Brain project, built for accessible macOS interactions with VoiceOver, keyboard-first navigation, and voice features.

**Location:** `apps/BrainChat/` (not `tools/BrainChat`)

## Documentation

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
