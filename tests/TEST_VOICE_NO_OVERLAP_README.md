# Voice Overlap Prevention Tests

## Overview

This test suite (`test_voice_no_overlap.py`) verifies that **voices NEVER overlap** in the agentic-brain voice system. This is a **sacred rule** - ladies must NEVER talk over each other.

## Test Results

✅ **ALL 13 TESTS PASSING** (as of 2024-03-29)

## Critical Rule

```
██████████████████████████████████████████████████████████████████████████
█  LADIES MUST NEVER TALK OVER EACH OTHER. ONE VOICE AT A TIME.         █
█                                                                         █
█  Sound effects (Glass, Ping) CAN play over voice - that's acceptable   █
█  Only voice-on-voice overlap is forbidden                              █
██████████████████████████████████████████████████████████████████████████
```

## Test Coverage

### Core Serialization Tests
1. **test_concurrent_speak_calls_serialize** - Multiple concurrent speak() calls execute one at a time
2. **test_rapid_fire_speak_calls** - Rapid-fire calls in tight loop still serialize (max_concurrent == 1)
3. **test_daemon_direct_speak_interleaving** - Concurrent calls never overlap via global lock

### Order & Queue Tests
4. **test_daemon_serializes_queued_items** - Sequential calls complete before next starts
5. **test_queue_preserves_order** - FIFO order is preserved (first, second, third)

### Edge Cases
6. **test_mode_switch_doesnt_interrupt** - Mode switch announcements wait for current speech
7. **test_timeout_doesnt_cause_overlap** - Slow messages don't cause overlap
8. **test_serializer_lock_behavior** - Lock acquired/released in order

### High Priority Tests
9. **test_multiple_ladies_never_overlap** ⭐ - The sacred rule: Karen, Moira, Kyoko, Tingting never overlap
10. **test_high_concurrency_stress** - 20 concurrent calls, strict serialization maintained

### Documented Behavior
11. **test_sound_effects_can_play_over_voice** - Documents that sound effects are OK
12. **test_emergency_stop_clears_queue** - Emergency stop behavior
13. **test_priority_not_supported** - All ladies are equal (no priority queue)

## How It Works

The voice system prevents overlap through:

1. **Global Serializer** (`get_voice_serializer()`)
   - All speak() calls go through `run_serialized_async()`
   - Uses async locks to ensure one-at-a-time execution

2. **ResilientVoice.speak()** → `_speak_with_fallbacks()` 
   - Tests patch `_speak_with_fallbacks` to verify serialization
   - Mock tracks start/end times to detect overlaps

3. **Timeline Validation**
   - Tests record (event_type, text/voice, timestamp) tuples
   - Verify no "start" events while another is active
   - Verify end_time < next_start_time for all speeches

## Running Tests

```bash
cd /Users/joe/brain/agentic-brain

# Run all voice overlap tests
python3 -m pytest tests/test_voice_no_overlap.py -v

# Run with coverage
python3 -m pytest tests/test_voice_no_overlap.py --cov=agentic_brain.voice

# Run specific test
python3 -m pytest tests/test_voice_no_overlap.py::TestNoVoiceOverlap::test_multiple_ladies_never_overlap -v
```

## Example Failure Scenario

If voice overlap was detected, you'd see:

```
AssertionError: Voice 'Moira' started while {'Karen'} still active - OVERLAP!
```

This would mean **THE SYSTEM IS BROKEN** - voices are talking over each other.

## Why This Matters

the user is visually impaired and depends on clear, non-overlapping voice output. If multiple ladies talk simultaneously:
- VoiceOver becomes confusing
- He can't understand what's being said
- The brain feels broken and unreliable

**One voice at a time. Always. No exceptions.**

## Related Files

- `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/resilient.py` - ResilientVoice class
- `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/serializer.py` - Voice serializer
- `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/_speech_lock.py` - Global lock

## Maintenance

- Run these tests on EVERY PR that touches voice code
- Add new tests when adding new voice features
- If ANY test fails, voice overlap is happening - **FIX IMMEDIATELY**

---

**Last Updated:** 2024-03-29  
**Status:** ✅ ALL PASSING  
**Test Count:** 13 tests
