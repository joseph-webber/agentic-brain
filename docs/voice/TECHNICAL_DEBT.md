# Voice Engine Technical Debt

**Created**: 2026-03-29
**Status**: Known Issue - Flagged for Future Rebuild

## The Problem: Voice Overlap

Despite extensive work on the voice serialization system, there remains a persistent
voice-on-voice overlap issue that occurs:

1. **When**: During daemon startup, mode switching (work ↔ life mode)
2. **Where**: Around "daemon is awake" and "tide" test phrases
3. **Symptom**: Multiple voices speak simultaneously instead of sequentially

## Current Architecture Limitations

The voice system has multiple entry points that are difficult to fully serialize:

- `VoiceSerializer` (singleton) - Main speech gate
- `VoiceDaemon` (async queue) - Background voice daemon
- `ResilientVoice` (fallback chain) - 5-layer fallback system
- `EarconPlayer` (sound effects) - Intentionally non-blocking
- `ConversationalVoice` (mode switching) - Triggers announcements

The problem is that these systems evolved independently and have subtle race conditions
when they interact, especially during state transitions.

## What Works

- ✅ Basic serial speech (one message at a time)
- ✅ Sound effects over voice (intentional, useful)
- ✅ 120+ voice tests passing
- ✅ Phase 3 features (neural TTS, earcons, emotions, etc.)

## What Doesn't Work

- ❌ Voice-on-voice overlap during mode switching
- ❌ Overlap during daemon startup sequence
- ❌ Multiple ladies speaking simultaneously in edge cases

## Future Solution: Voice Engine Rebuild

When time permits, the voice engine should be rebuilt with:

1. **Single Entry Point**: ALL voice output through ONE function
2. **Hardware-Level Lock**: Use macOS audio session exclusivity
3. **Queue-First Architecture**: Everything queues, nothing speaks directly
4. **State Machine**: Explicit states (IDLE, SPEAKING, SWITCHING, STARTING)
5. **No Parallel Paths**: Remove all the legacy speech paths

## Workaround

For now, the overlap is cosmetic - it doesn't break functionality.
Users may hear occasional voice overlap during mode switches.

## Files Involved

- `src/agentic_brain/voice/serializer.py` - Main serializer
- `src/agentic_brain/voice/resilient.py` - VoiceDaemon
- `src/agentic_brain/voice/conversation.py` - Mode switching
- `src/agentic_brain/voice/_speech_lock.py` - Global lock

---

*Flagged by Agentic Brain Contributors on 2026-03-29 for future rebuild.*
