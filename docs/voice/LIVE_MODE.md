# Live Mode

## Current status

**Project Aria live mode is not implemented in this repository today.**

Phase 2 added strong output-side foundations:

- serialized speech
- distributed speech locking
- spatial routing
- durable queueing
- event topics for voice requests and status

But the repo does **not** currently ship:

- microphone capture
- wake word detection
- streaming speech-to-text
- whisper.cpp integration
- an always-listening conversation loop

This document exists so the current state is clear and future work has a home.

## What “Project Aria” would mean here

In Agentic Brain terms, live mode would be a hands-free voice loop:

1. listen for a wake word
2. capture speech
3. transcribe it
4. route it into the agent
5. speak the answer back through the existing safe voice stack

The output side of that pipeline already exists.
The input side does not.

## What is already in place

### Conversation modes

`src/agentic_brain/voice/conversation.py` provides:

- `WORK`
- `LIFE`
- `QUIET`

These are **speaker selection modes**, not live listening modes.

### Voice event topics

`src/agentic_brain/events/voice_events.py` defines:

- `brain.voice.request`
- `brain.voice.status`
- `brain.voice.input`
- `brain.voice.control`
- `brain.llm.streaming`

`brain.voice.input` is useful as a future hook for speech-to-text events, but the repo
does not currently publish microphone transcripts into it.

## Wake word usage

There is **no built-in wake word command or configuration** in the current codebase.

That means:

- no “Hey Brain” style trigger is available
- no wake-word model is configured
- no always-on microphone loop is present

If you need hands-free input today, it must be added outside the current shipped modules.

## Current conversation flow

What exists today is an **output-first** flow:

```text
CLI / app / agent
    -> queue or serializer
    -> speech lock
    -> optional spatial router
    -> playback
```

There is no built-in input flow like this yet:

```text
microphone
    -> wake word
    -> speech-to-text
    -> agent
    -> serializer
    -> playback
```

## whisper.cpp setup

There is **no whisper.cpp setup in this repository** right now.

That means:

- no dependency entry for whisper.cpp
- no wrapper module
- no CLI command
- no documented model directory

If you are planning live mode, treat whisper.cpp as future integration work rather than
something already supported.

## Recommended approach if you add live mode later

Use the current voice stack as the output layer:

- publish transcribed input into `brain.voice.input`
- publish generated speech requests into `brain.voice.request`
- keep final playback routed through `VoiceSerializer`
- keep overlap protection in `_speech_lock.py`

That way, live mode inherits the accessibility work already done in Phase 2.

## Troubleshooting

### “I can’t find live mode commands”

That is expected.
The feature is not implemented yet.

### “Where is the wake word config?”

There is none in the current tree.

### “Where is whisper.cpp configured?”

It is not wired into the repo at this time.

### “What should I use today instead?”

Use:

- `ab voice speak ...`
- `ab voice conversation --demo`
- queue and event-based voice output

For current voice behavior, see:

- [Voice system overview](./README.md)
- [Streaming](./STREAMING.md)
- [Troubleshooting](./TROUBLESHOOTING.md)
