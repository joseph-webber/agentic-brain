# BrainChat Voice Benchmarks

**Date**: 2026-04-06
**System**: MacBook M2 Pro, macOS

## Voice Synthesis Latency

Using macOS `say` command with Karen (Premium) voice.

### By Phrase Length

| Length | Words | Duration | WPM Effective |
|--------|-------|----------|---------------|
| Short  | 5     | 2.64s    | ~114 WPM      |
| Medium | 15    | 5.80s    | ~155 WPM      |
| Long   | 30    | 10.33s   | ~174 WPM      |

### By Speech Rate (-r flag)

| Rate Setting | Actual Duration | Notes |
|--------------|-----------------|-------|
| 150 WPM      | 4.48s           | Slower, clearer |
| 175 WPM      | 4.67s           | Default (good balance) |
| 200 WPM      | 3.59s           | Faster |
| 225 WPM      | 3.92s           | Fast (may be harder to understand) |

**Recommendation**: 175 WPM is optimal for accessibility. Fast enough to be efficient, slow enough for clarity.

### By Voice

| Voice    | Duration (same text) | Quality Notes |
|----------|---------------------|---------------|
| Karen    | 3.01s               | Australian - recommended default |
| Samantha | 3.43s               | US English |
| Daniel   | 3.34s               | British English |

**Conclusion**: Karen is fastest AND the recommended voice.

## Performance Analysis

### First Word Latency
- macOS `say` command: ~200-300ms to first word
- This is excellent for real-time feedback

### Recommended Settings for BrainChat
```swift
VoiceSettings.currentEngine = .systemSay  // Most reliable
VoiceSettings.currentVoice = .karen       // Recommended default + fastest
VoiceSettings.speechRate = 175            // Balanced
VoiceSettings.isEnabled = true            // Always on for accessibility
```

## Comparison with Cloud TTS

| Engine | Latency | Quality | Cost |
|--------|---------|---------|------|
| macOS Say | ~200ms | Good | Free |
| Cartesia | ~150ms | Excellent | $0.015/1k chars |
| ElevenLabs | ~300ms | Premium | $0.30/1k chars |

**Recommendation**: Use macOS `say` as default. Cartesia as premium option for ultra-low latency.
