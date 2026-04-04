# BrainChat Swift

BrainChat is the Swift client for the Agentic Brain project, built for accessible macOS interactions with VoiceOver, keyboard-first navigation, and voice features.

## Documentation

- [Deployment Guide](./DEPLOYMENT.md)
- [Voice Coding Guide](./docs/VOICE_CODING_GUIDE.md)
- [Security Quick Reference](./SECURITY-QUICK-REFERENCE.md)

## Security Modes

| Mode | Access |
|------|--------|
| FULL_ADMIN | Unrestricted owner mode |
| SAFE_ADMIN | YOLO allowed with guardrails and confirmations |
| USER | API access only |
| GUEST | Help and FAQ only |

See the [Security Quick Reference](./SECURITY-QUICK-REFERENCE.md) for the full permission matrix.

## Verification

```bash
swift build
swift test --parallel
swift build -c release
```

## Deployment

For build, install, security mode, CI/CD, and troubleshooting instructions, see the [BrainChat Deployment Guide](./DEPLOYMENT.md).
