# BrainChat Deployment Guide

## Quick Start

### Build Release
```bash
cd apps/BrainChat
swift build -c release
```

### Install CLI
```bash
cp .build/release/BrainChat /usr/local/bin/brainchat
```

### Run
```bash
brainchat
```

## Security Modes

BrainChat supports 4 security modes:

| Mode | Access | Use Case |
|------|--------|----------|
| FULL_ADMIN | Unrestricted | Joseph (owner) |
| SAFE_ADMIN | Guardrails | Developers |
| USER | API-only | Customers |
| GUEST | Help only | Anonymous demos |

### Switch Modes
```bash
brainchat --mode guest
brainchat --mode admin
```

## CI/CD

GitHub Actions workflow at `.github/workflows/brainchat.yml`

### Triggered On
- Push to apps/BrainChat/**
- Pull requests

### Jobs
- Build (release)
- Test (parallel)
- Security audit
- Artifact upload

## Requirements

- macOS 13.0+
- Swift 5.9+
- Xcode Command Line Tools

## Accessibility

BrainChat is built with accessibility first:
- Full VoiceOver support
- Keyboard navigation
- Voice input/output

## Troubleshooting

### Build Fails
```bash
rm -rf .build
swift package resolve
swift build
```

### Tests Fail
```bash
swift test --verbose
```
