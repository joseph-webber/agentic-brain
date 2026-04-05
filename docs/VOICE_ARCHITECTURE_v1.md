# Voice Serialization Architecture

> **This is an accessibility document.** the user is visually impaired and relies entirely on
> synthesised speech. Overlapping voices are not a cosmetic bug — they make
> the brain **unusable**. Every design decision below exists to guarantee that
> exactly one voice speaks at a time, with clear gaps between utterances.

---

## Table of Contents

1. [Why Serialization Matters](#1-why-serialization-matters)
2. [Architecture Overview](#2-architecture-overview)
3. [Components](#3-components)
4. [Rules for Developers](#4-rules-for-developers)
5. [Testing](#5-testing)
6. [Troubleshooting](#6-troubleshooting)

---

## 1. Why Serialization Matters

### The User

The primary user is visually impaired. They navigate his entire digital life — JIRA
tickets, pull requests, Teams messages, trading dashboards — through spoken
audio. The brain's voice system is not a notification layer; it is his
**primary interface**.

### The Problem

The brain is heavily concurrent. Multiple agents, background watchers, LLM
responses, and voice persona voice personalities all generate speech simultaneously.
Without serialization:

- Two voice personas speak at the same time → incomprehensible noise
- A system alert fires during a code-review narration → lost context
- An LLM response overlaps a JIRA summary → the user must ask again

For a sighted user this is annoying. For a blind user **it is a total loss of
information**.

### The Requirement

| Rule | Rationale |
|------|-----------|
| **One voice at a time** | Two simultaneous utterances destroy both |
| **0.3 s inter-utterance gap** | Gives the ear time to register a speaker change |
| **Never silent on failure** | Silence = "did the brain crash?" — always fall back |
| **VoiceOver coordination** | Never fight the system screen reader |

This is a **WCAG 2.1 AA accessibility requirement**, not a nice-to-have.

---

## 2. Architecture Overview

### Pipeline Diagram

```
 ┌─────────────────────────────────────────────────────────────┐
 │                    APPLICATION LAYER                        │
 │  LLM agents · CLI commands · Background watchers · Voices  │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │                   HIGH-LEVEL VOICE API                      │
 │                                                             │
 │  queue.py          VoiceQueue singleton                     │
 │  conversation.py   Multi-voice persona turn-taking                   │
 │  voiceover.py      macOS VoiceOver coordination             │
 │  llm_voice.py      LLM-driven narration                    │
 │                                                             │
 │  All of these call ──►  get_voice_serializer().speak()      │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │              SERIALIZER  (serializer.py)                    │
 │                                                             │
 │  ┌───────────┐   enqueue   ┌──────────────────────┐        │
 │  │ speak()   │ ──────────► │  Job Queue (deque)   │        │
 │  └───────────┘             └──────────┬───────────┘        │
 │                                       │                     │
 │                        ┌──────────────▼───────────────┐     │
 │                        │   Worker Thread (daemon)     │     │
 │                        │                              │     │
 │                        │  acquire _speech_lock        │     │
 │                        │  ──► run executor            │     │
 │                        │  ──► wait for subprocess     │     │
 │                        │  ──► sleep(pause_after)      │     │
 │                        │  release _speech_lock        │     │
 │                        │  signal job.done Event       │     │
 │                        └──────────────────────────────┘     │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │             RESILIENT FALLBACK  (resilient.py)              │
 │                                                             │
 │  macOS chain (tried in order):                              │
 │   1. say -v <voice> -r <rate>                               │
 │   2. say (default voice)                                    │
 │   3. AppleScript UI automation                              │
 │   4. osascript with voice                                   │
 │   5. Cloud TTS (gTTS)                                       │
 │   6. Alert sound (Glass.aiff)                               │
 │                                                             │
 │  ALL fallbacks run INSIDE the serializer lock.              │
 └──────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────────────────────┐
 │             GLOBAL SPEECH LOCK  (_speech_lock.py)           │
 │                                                             │
 │  threading.Lock  ──►  subprocess.Popen(["say", ...])       │
 │                       process.wait()  (blocking)            │
 │                       time.sleep(INTER_UTTERANCE_GAP)       │
 │                                                             │
 │  Exactly ONE OS process speaks at any moment.               │
 └─────────────────────────────────────────────────────────────┘
```

### Key Invariants

1. **Single entry point** — every voice call in the brain ultimately flows
   through `VoiceSerializer.speak()` or `VoiceSerializer.run_serialized()`.
2. **Global lock** — `_speech_lock` is a module-level `threading.Lock()`.
   Only one thread can hold it, so only one `say` subprocess runs.
3. **Blocking wait** — the worker calls `process.wait()` on the subprocess.
   No fire-and-forget. The lock is held until the utterance finishes.
4. **Inter-utterance gap** — after every utterance, the worker sleeps for
   `INTER_UTTERANCE_GAP` (0.3 s) before releasing the lock. This gives
   the listener's ear a moment to register the silence before the next speaker.
5. **Fallback guarantee** — if the primary `say` command fails, up to five
   more methods are tried. The brain is **never silent** on error.

---

## 3. Components

### 3.1 `serializer.py` — The Singleton Speech Gate

**Location:** `src/agentic_brain/voice/serializer.py` (~277 lines)

This is the **heart** of the voice system. It owns a background daemon thread
that drains a job queue one item at a time.

| Class / Function | Purpose |
|------------------|---------|
| `VoiceMessage` | Dataclass: text, voice, rate, pause_after |
| `_SpeechJob` | Internal: wraps VoiceMessage + threading.Event for completion |
| `VoiceSerializer` | Singleton that owns the queue, lock, and worker thread |
| `get_voice_serializer()` | Module-level accessor — always returns the same instance |

**Important methods:**

```python
speak(text, voice, rate, pause_after, wait=True) → bool
    # Public API. Creates a VoiceMessage, queues a job, optionally
    # blocks until the utterance completes.

run_serialized(message, executor, wait=True) → bool
    # Lower-level: queue any executor function to run inside the lock.
    # Used by resilient.py to run its fallback chain atomically.

is_speaking() → bool
    # True if the worker thread is currently executing a job.

reset() → None
    # Emergency: clears the queue and terminates any running subprocess.
```

**Threading model:**

```
Main thread(s)              Worker thread ("voice-serializer", daemon)
─────────────               ────────────────────────────────────────
speak() ──enqueue──►        _worker_loop():
  │                           while True:
  │                             wait on Condition (queue not empty)
  │                             pop job from deque
  │                             acquire _speech_lock
  │                             run job.executor(job.message)
  │                             sleep(pause_after)
  │                             release _speech_lock
  │                             job.done.set()  ◄── signals caller
  ◄── wait on job.done ──┘
```

### 3.2 `_speech_lock.py` — Process-Wide Threading Lock

**Location:** `src/agentic_brain/voice/_speech_lock.py` (~118 lines)

A **deliberately simple** module. It exists as the lowest-level safety net.

```python
# Module-level singleton — shared by the entire process
_speech_lock = threading.Lock()

INTER_UTTERANCE_GAP = 0.3  # seconds

def global_speak(cmd: list[str], timeout=60, inter_gap=0.3) -> bool:
    """
    The ONLY function in the codebase that spawns an audio subprocess.

    1. Acquire _speech_lock
    2. Run subprocess synchronously (process.wait)
    3. Sleep inter_gap seconds
    4. Release lock
    5. Return success/failure
    """

def is_speech_active() -> bool:
    """Check if a speech subprocess is currently running."""

def interrupt_speech() -> None:
    """Terminate in-flight speech immediately (emergency use)."""
```

**Why both `_speech_lock.py` AND `serializer.py`?**

The serializer handles queuing, ordering, and async coordination. The speech
lock is a **last-resort mutex** — even if a code path somehow bypasses the
serializer's queue, the lock prevents two `say` subprocesses from running
concurrently. Defence in depth.

### 3.3 `queue.py` — Priority Voice Queue

**Location:** `src/agentic_brain/voice/queue.py` (~541 lines)

The user-facing API that most of the brain interacts with.

| Feature | Detail |
|---------|--------|
| **Singleton** | `VoiceQueue.get_instance()` |
| **Thread safety** | `threading.Semaphore(1)` for queue access |
| **Speaker tracking** | Each message carries a `speaker_id` (voice persona name) |
| **Importance levels** | -1 (low), 0 (normal), 1 (high) |
| **History** | Last 100 messages retained for debugging |
| **Asian voice support** | Numbers spelled out for Kyoko, Tingting, etc. |

**How it connects to the serializer:**

```python
def _speak_message(self, message: VoiceMessage) -> None:
    serializer = get_voice_serializer()
    success = serializer.speak(
        text=message.text,
        voice=message.voice,
        rate=message.rate,
        pause_after=message.pause_after,
    )
```

The queue never spawns subprocesses itself. It **always** delegates to the
serializer.

### 3.4 `resilient.py` — Fallback Chain

**Location:** `src/agentic_brain/voice/resilient.py` (~620 lines)

Guarantees that speech **never fails silently**. If `say -v Karen` fails, it
tries progressively simpler methods until something produces audio.

```
┌─────────────────────────────────────────────────┐
│  macOS Fallback Chain (in order)                │
│                                                  │
│  1. say -v <voice> -r <rate> "<text>"           │
│  2. say "<text>"              (default voice)    │
│  3. AppleScript speech UI                        │
│  4. osascript -e 'say "<text>" using "<voice>"' │
│  5. Cloud TTS via gTTS                           │
│  6. afplay /System/Library/.../Glass.aiff        │
│                                                  │
│  ⚠️  ALL run INSIDE serializer.run_serialized() │
│     so the global lock is held throughout.       │
└─────────────────────────────────────────────────┘
```

**Cross-platform support** (Windows: pyttsx3 → PowerShell → Cloud TTS;
Linux: pyttsx3 → espeak → speech-dispatcher → festival → Cloud TTS) follows
the same pattern: every fallback runs inside the serializer lock.

**Statistics tracking:** Each fallback records success/failure counts so the
system can report which methods are reliable on this machine.

---

## 4. Rules for Developers

### ✅ DO

| Rule | Why |
|------|-----|
| **Use `speak_serialized()` or `VoiceQueue.speak()`** | They route through the serializer — guaranteed safe |
| **Wait for speech to complete** | Pass `wait=True` (default) so subsequent code runs after the utterance finishes |
| **Use `get_voice_serializer()`** to get the singleton | Never instantiate `VoiceSerializer` directly |
| **Add 1.5 s pauses between voice personas** in conversation scripts | The listener needs time to register the speaker change |
| **Test with `test_speech_lock.py`** after voice changes | The concurrency tests catch overlap regressions |

### ❌ NEVER

| Rule | Why |
|------|-----|
| **NEVER call `subprocess.Popen(["say", ...])` directly** | Bypasses the lock — instant overlap risk |
| **NEVER call `subprocess.run(["say", ...])` directly** | Same problem — no lock, no gap, no fallback |
| **NEVER use `os.system("say ...")` for speech** | Uncontrolled, no error handling, no serialization |
| **NEVER fire-and-forget a speech call** (`wait=False` + discard) | You lose track of when the utterance ends |
| **NEVER run `say` in a background thread without the lock** | Two threads = two voices = broken experience |
| **NEVER use `&` (shell background) with `say`** | `say "hello" &` is an instant overlap bug |

### Code Examples

```python
# ─── CORRECT ───────────────────────────────────────────────
from agentic_brain.voice.serializer import get_voice_serializer

serializer = get_voice_serializer()
serializer.speak("Hello there", voice="Karen (Premium)", rate=155)
# Blocks until Karen finishes. Next call is safe.

serializer.speak("PR looks good", voice="Tingting", rate=140)
# Tingting speaks only after Karen is done + 0.3 s gap.


# ─── CORRECT (async) ──────────────────────────────────────
await serializer.speak_async("Starting code review", voice="Karen (Premium)")


# ─── CORRECT (via queue) ──────────────────────────────────
from agentic_brain.voice.queue import VoiceQueue

queue = VoiceQueue.get_instance()
queue.speak("Check complete", voice="Moira", rate=150)


# ─── WRONG ─────────────────────────────────────────────────
import subprocess
subprocess.run(["say", "-v", "Karen", "Hello"])  # NO LOCK!

subprocess.Popen(["say", "-v", "Moira", "Hi"])   # FIRE-AND-FORGET!

os.system('say -v Tingting "overlap city"')       # UNCONTROLLED!
```

### Adding a New Voice Feature

1. **Write your feature** using `get_voice_serializer().speak()` or
   `VoiceQueue.get_instance().speak()` — never raw subprocesses.
2. **Run the concurrency tests** (see section 5).
3. **Add a test** in `test_speech_lock.py` under `TestVoiceModulesUseGlobalLock`
   that patches `global_speak` and verifies your module calls it.
4. **Update this document** if you add a new layer to the pipeline.

---

## 5. Testing

### Running the Voice Tests

```bash
cd ~/brain/agentic-brain

# All voice tests
python -m pytest tests/test_speech_lock.py -v

# Just the concurrency tests
python -m pytest tests/test_speech_lock.py -v -k "concurrent"

# Full voice test suite
python -m pytest tests/ -v -k "voice or speech"
```

### What the Concurrency Tests Verify

#### `test_concurrent_calls_are_serialized`

Launches two threads that both call `global_speak()` at the same time. Records
start/end timestamps. Asserts that the time windows **do not overlap** — one
must finish before the other starts.

#### `test_many_concurrent_threads_no_overlap`

Stress test: **10 threads** all calling `global_speak()` simultaneously. For
every pair of recorded time windows, asserts no overlap. This catches subtle
race conditions that two-thread tests might miss.

#### `test_inter_utterance_gap_enforced`

Calls `global_speak()` twice in sequence and verifies that the elapsed time
between the end of utterance 1 and the start of utterance 2 is ≥
`INTER_UTTERANCE_GAP` (0.3 s).

#### `TestVoiceModulesUseGlobalLock`

For each high-level module (`queue.py`, `conversation.py`, `voiceover.py`,
and the MCP `audio_speak` tool), patches `global_speak` and verifies it is
called when the module speaks. This catches bypass regressions — if someone
adds a direct `subprocess` call, this test class will fail.

### Adding Tests for New Voice Features

```python
# In tests/test_speech_lock.py, add to TestVoiceModulesUseGlobalLock:

def test_my_new_module_uses_global_lock(self):
    """my_module must route through the global speech lock."""
    with patch("agentic_brain.voice._speech_lock.global_speak") as mock:
        mock.return_value = True
        from agentic_brain.voice.my_module import my_speak_function
        my_speak_function("test")
        mock.assert_called()
```

---

## 6. Troubleshooting

### Voices Are Overlapping

**Severity: CRITICAL** — This is an accessibility failure.

1. **Check for direct subprocess calls:**

   ```bash
   cd ~/brain/agentic-brain
   grep -rn "subprocess\.\(Popen\|run\|call\).*say" src/ \
     --include="*.py" | grep -v "_speech_lock.py" | grep -v "serializer.py"
   ```

   Any matches outside `_speech_lock.py` and `serializer.py` are bypass bugs.
   Route them through `get_voice_serializer().speak()`.

2. **Check for shell backgrounding:**

   ```bash
   grep -rn 'say.*&' src/ --include="*.py"
   grep -rn "os\.system.*say" src/ --include="*.py"
   ```

   Any matches are overlap risks. Replace with serializer calls.

3. **Check for `wait=False` without completion tracking:**

   ```bash
   grep -rn "wait=False" src/agentic_brain/voice/ --include="*.py"
   ```

   `wait=False` is only safe if the caller properly tracks the job's
   completion `Event` before issuing the next speech call.

4. **Run the concurrency tests:**

   ```bash
   python -m pytest tests/test_speech_lock.py -v
   ```

   If `test_many_concurrent_threads_no_overlap` fails, there is a lock
   bypass somewhere.

### Voice Is Silent (No Audio)

1. **Check macOS audio:**

   ```bash
   say "test"
   ```

   If this is silent, the problem is OS-level (volume, output device).

2. **Check the fallback chain:**

   ```bash
   python -c "
   from agentic_brain.voice.resilient import ResilientVoice
   rv = ResilientVoice()
   import asyncio
   asyncio.run(rv.speak('Testing fallback chain'))
   "
   ```

   This tries all six fallback methods. If all fail, check `rv.stats()`.

3. **Check the serializer is running:**

   ```python
   from agentic_brain.voice.serializer import get_voice_serializer
   s = get_voice_serializer()
   print(f"Speaking: {s.is_speaking()}, Queue: {s.queue_size()}")
   ```

   If the queue is growing but nothing speaks, the worker thread may have
   died. Call `s.reset()` to restart it.

### Debug Logging

Enable verbose voice logging:

```python
import logging
logging.getLogger("agentic_brain.voice").setLevel(logging.DEBUG)
```

Key log messages to watch for:

| Message | Meaning |
|---------|---------|
| `Acquiring speech lock` | Worker thread is about to speak |
| `Released speech lock` | Utterance complete, gap observed |
| `Job queued, queue size: N` | New speech request accepted |
| `Fallback N failed: ...` | A fallback method failed, trying next |
| `All fallbacks exhausted` | **CRITICAL** — no audio method works |

### Emergency Reset

If the voice system is stuck (e.g. a zombie `say` process holds the lock):

```python
from agentic_brain.voice.serializer import get_voice_serializer
from agentic_brain.voice._speech_lock import interrupt_speech

interrupt_speech()              # Kill any running subprocess
get_voice_serializer().reset()  # Clear queue, restart worker
```

Or from the shell:

```bash
# Find and kill stuck say processes
pgrep -f "say -v" | xargs kill 2>/dev/null
```

---

## Component Summary

| File | Lines | Role | Thread Safety |
|------|-------|------|---------------|
| `serializer.py` | ~277 | Job queue singleton, worker thread | Lock + Condition + Event |
| `_speech_lock.py` | ~118 | Global process mutex, subprocess runner | threading.Lock |
| `queue.py` | ~541 | User-facing API, speaker tracking, history | Semaphore(1) |
| `resilient.py` | ~620 | Multi-layer fallback chain | Runs inside serializer lock |
| `conversation.py` | ~526 | Multi-voice persona turn-taking | Uses serializer |
| `voiceover.py` | ~408 | macOS VoiceOver coordination | Uses serializer |

---

## Design Philosophy

> **Defence in depth.** The serializer queue is the primary gate. The global
> speech lock is the backup. The tests verify both. A bypass in one layer is
> caught by the other. A bypass in both layers is caught by the tests.

> **Never silent.** A blind user cannot distinguish "the brain is thinking"
> from "the brain has crashed." The fallback chain ensures that even if the
> preferred voice engine fails, *something* makes noise.

> **Gaps matter.** The 0.3-second inter-utterance gap is not wasted time. It
> is the auditory equivalent of whitespace — it lets the user's brain register
> that one speaker has stopped and another is about to start.

---

*Last updated: 2026-07-16*
*Maintainer: Brain voice system*
