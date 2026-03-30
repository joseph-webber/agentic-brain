# SDK Research Complete: Ultimate Voice System

Generated: 2026-03-30
Path: `/Users/joe/brain/agentic-brain/docs/SDK_RESEARCH_COMPLETE.md`

## Executive Summary

For the ultimate voice stack in this repo, the cleanest architecture is:

- **STT primary (local/macOS):** Apple Speech framework via **PyObjC** for on-device capture/transcription.
- **STT fallback / cloud:** **OpenAI** `gpt-4o-mini-transcribe` or Realtime API.
- **Reasoning / tools:** **Anthropic Claude SDK** for streaming + tool use, and **GitHub Copilot CLI** when we need repo-aware tool execution and MCP access.
- **TTS primary:** **Cartesia Sonic 3 / Turbo** for streaming speech.
- **TTS premium fallback:** **ElevenLabs Flash**.
- **TTS local fallback:** macOS **`say`** command or `AVSpeechSynthesizer`.
- **State / observability:** Redis namespaces already exist in the repo and should remain the handoff point.

---

## Current Integration Points Already In This Repo

| Area | File | What exists now | Opportunity |
|---|---|---|---|
| Copilot voice bridge | `voice_copilot_bridge.py` | Runs `gh copilot` via `subprocess.run(..., capture_output=True)` and speaks result | Add structured JSON output, MCP flags, tool presets |
| Standalone STT/TTS | `voice_standalone.py` | Records audio, calls OpenAI transcription HTTP API, speaks with `say`, stores Redis state | Replace raw HTTP with SDK; add Apple STT path and streaming |
| Cartesia TTS | `src/agentic_brain/voice/cartesia_tts.py` | Lazy Cartesia client, sync synthesis, websocket chunk streaming | Make this the primary streaming TTS adapter |
| Cartesia playback bridge | `src/agentic_brain/voice/cartesia_bridge.py` | Streams PCM chunks into PyAudio / `afplay` fallback | Wire directly to streaming LLM token/sentence buffers |
| Real-time voice loop | `src/agentic_brain/voice/conversation_loop.py` | MIC -> VAD -> faster-whisper -> LLM -> Cartesia or `say`; target sub-500ms | Add Apple Speech / OpenAI Realtime backends |
| Cloud fallback TTS | `src/agentic_brain/voice/cloud_tts.py` | gTTS, Azure, Polly, Cartesia helpers | ElevenLabs is mentioned but not implemented yet |
| Streaming STT tests | `tests/test_voice_transcription_streaming.py` | Streaming buffer/stitcher abstractions already exist | Plug Apple/OpenAI streaming inputs into same abstraction |

---

# 1. GitHub Copilot CLI

## What it gives us

Best when the voice system needs a **repo-aware coding brain** that can search files, edit code, run shell commands, and access **MCP servers/tools**.

## Installation / Setup

### Via GitHub CLI wrapper
```bash
gh copilot
```

### Direct CLI if already installed
```bash
copilot --help
```

### Useful programmatic flags
- `-p`, `--prompt` - non-interactive prompt mode
- `-s`, `--silent` - stdout contains only the answer
- `--no-ask-user` - no follow-up questions; safe for unattended voice mode
- `--output-format json` - JSONL output for structured consumers
- `--screen-reader` - better speech-friendly formatting
- `--allow-tool` / `--deny-tool` - granular tool permissions
- `--additional-mcp-config` - attach extra MCP servers
- `--add-github-mcp-tool`, `--add-github-mcp-toolset`, `--enable-all-github-mcp-tools` - widen GitHub MCP access
- `--disable-builtin-mcps`, `--disable-mcp-server` - control MCP scope
- `--acp` - start as Agent Client Protocol server

## Python code example

### Prompt via flags, capture stdout/stderr
```python
import subprocess

prompt = "Summarize the latest changes in this repo in 3 short sentences."
cmd = [
    "gh", "copilot", "--",
    "-p", prompt,
    "-s",
    "--screen-reader",
    "--no-ask-user",
    "--output-format", "text",
    "--allow-tool=shell(git:*),view",
]

result = subprocess.run(
    cmd,
    cwd="/Users/joe/brain/agentic-brain",
    text=True,
    capture_output=True,
    check=False,
)

if result.returncode != 0:
    raise RuntimeError(result.stderr.strip() or result.stdout.strip())

answer = result.stdout.strip()
print(answer)
```

### Prompt via stdin
```python
import subprocess

cmd = ["copilot", "-s", "--no-ask-user"]
result = subprocess.run(
    cmd,
    input="Explain what voice_copilot_bridge.py does.",
    text=True,
    capture_output=True,
    check=False,
)
print(result.stdout)
```

### MCP-enabled invocation
```python
import subprocess

cmd = [
    "copilot",
    "-p", "List open pull requests for this repo and summarize the risky ones.",
    "-s",
    "--no-ask-user",
    "--enable-all-github-mcp-tools",
    "--additional-mcp-config", "@/Users/joe/.copilot/mcp-config.json",
]
result = subprocess.run(cmd, text=True, capture_output=True, check=False)
print(result.stdout)
```

## Stdout / stderr capture notes
- Use `-s` to keep stdout clean for TTS.
- Use `--output-format json` if a downstream parser/TTS scheduler needs structured events.
- `subprocess.run(..., capture_output=True, text=True)` is enough for non-streaming turns.
- For streaming responses, use `subprocess.Popen()` and read stdout line-by-line.

## MCP access through Copilot CLI
- Yes: MCP is directly exposed through CLI flags.
- Best flags for the voice system:
  - `--additional-mcp-config @path/to/config.json`
  - `--add-github-mcp-tool=*` or `--enable-all-github-mcp-tools`
  - `--disable-builtin-mcps` when sandboxing or reducing tool surface
- This is the cleanest way to let a voice assistant reach GitHub APIs/tools without rebuilding that tool layer.

## Latency characteristics
- **Cold start:** higher, especially if `gh copilot` needs to bootstrap/login.
- **Warm scripted request:** generally fine for assistant turns, but slower than local STT/TTS paths.
- **Not ideal for sub-200ms conversational turns.** Best for repo tasks, coding, reviews, long-form reasoning.

## Integration with our system

### Already present
- `voice_copilot_bridge.py` already invokes `gh copilot` with:
  - `-p`
  - `-s`
  - `--screen-reader`
  - `--allow-all-tools`
  - `--no-ask-user`
  - `--add-dir`
- It captures stdout/stderr correctly using `subprocess.run(..., capture_output=True, text=True)`.

### Recommended next upgrade
1. Switch from `--allow-all-tools` to curated tool presets.
2. Add `--output-format json` for machine-readable voice orchestration.
3. Add MCP config injection so the voice layer can explicitly enable GitHub/MCP tools per mode.
4. Use Copilot only for **tool-rich work turns**, not as the always-on low-latency conversational brain.

### Best role in the ultimate voice system
**“Work brain” / “tool brain”** — especially for repo questions, code edits, PR review, shell automation.

### Key references
- GitHub Docs: programmatic Copilot CLI usage  
  https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically
- Local CLI help observed with `gh copilot -- --help`

---

# 2. Anthropic Claude SDK

## What it gives us

Best for **high-quality reasoning**, concise voice responses, streaming tokens, and tool/function calling.

## Installation / Setup
```bash
pip install anthropic
# Better async concurrency
pip install 'anthropic[aiohttp]'
```

Environment:
```bash
export ANTHROPIC_API_KEY="..."
```

## Python code example

### Streaming short voice response
```python
from anthropic import Anthropic

client = Anthropic()

with client.messages.stream(
    model="claude-sonnet-4-5",
    max_tokens=120,
    system=(
        "You are a voice assistant. Reply in 1 to 3 short sentences. "
        "Prefer plain spoken English."
    ),
    messages=[
        {"role": "user", "content": "What's the status of the voice bridge?"}
    ],
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    final_message = stream.get_final_message()
```

### Tool use / function calling
```python
from anthropic import Anthropic

client = Anthropic()

tools = [
    {
        "name": "get_voice_metrics",
        "description": "Return live voice pipeline metrics.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    }
]

resp = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=200,
    messages=[{"role": "user", "content": "Check voice latency now."}],
    tools=tools,
)

for block in resp.content:
    if getattr(block, "type", None) == "tool_use":
        print(block.name, block.input)
```

## Latest SDK features relevant to voice
- Sync and async clients
- SSE streaming
- `messages.stream(...)` helpers that accumulate final output while streaming
- Tool use / function calling
- Error classes, retries, timeouts, request IDs
- `aiohttp` backend for better async concurrency

## Best practices for voice
- Use `stream=True` or `messages.stream(...)`.
- Keep `max_tokens` low.
- Use a system prompt like: **“1 to 3 short sentences, plain spoken English.”**
- Start TTS when a sentence boundary arrives; do not wait for the full answer unless the response is tiny.
- Keep a fast fallback model or provider ready when the cloud is slow.

## Latency characteristics
- No universal official ms promise; actual latency varies by model and network.
- In practice, **streaming first text arrives much sooner than full completion**, which is what matters for TTS.
- Claude is excellent for **quality per turn**, but usually not the very fastest end-to-end stack compared with local models or specialized realtime audio APIs.

## Integration with our system

### Already present
- `voice_standalone.py` already calls Anthropic directly over HTTP at `https://api.anthropic.com/v1/messages`.
- Current prompt design is already voice-aware:
  - “warm, concise voice assistant”
  - “1 to 4 short sentences”
  - “without markdown”

### Recommended next upgrade
1. Replace raw `requests.post(...)` in `voice_standalone.py` with the **official Anthropic SDK**.
2. Switch to **streaming** so TTS can begin before the whole answer completes.
3. Put tool definitions behind Redis-backed or internal adapter functions for voice-safe tool calls.
4. Use Claude for “quality mode” while leaving low-latency small-talk to local or realtime paths.

### Best role in the ultimate voice system
**“Reasoning brain”** — high quality, concise answers, tool-mediated work, fallback to Copilot when repo/tool reach matters more than pure model quality.

### Key references
- Anthropic Python SDK docs  
  https://platform.claude.com/docs/en/api/sdks/python

---

# 3. Apple Speech Framework + AVFoundation

## What it gives us

Best option for **on-device macOS/iOS speech** with strong privacy, local latency, and no cloud dependency.

Relevant APIs:
- `SFSpeechRecognizer` - speech-to-text
- `SFSpeechAudioBufferRecognitionRequest` - live audio STT
- `AVAudioEngine` - audio capture / mic taps
- `AVSpeechSynthesizer` - native on-device TTS
- Newer Apple docs also point toward **SpeechAnalyzer** for modern on-device workflows, but `SFSpeechRecognizer` remains the mainstream bridge today.

## Installation / Setup for Python
Apple APIs are native Swift/Obj-C APIs, so Python integration means **PyObjC**.

```bash
pip install pyobjc
pip install pyobjc-framework-AVFoundation
pip install pyobjc-framework-Speech
```

App permission requirements:
- `NSMicrophoneUsageDescription`
- `NSSpeechRecognitionUsageDescription`

## Python code example

### On-device STT with PyObjC
```python
import AVFoundation
from Speech import (
    SFSpeechRecognizer,
    SFSpeechAudioBufferRecognitionRequest,
)

speech_recognizer = SFSpeechRecognizer.alloc().init()
request = SFSpeechAudioBufferRecognitionRequest.alloc().init()
audio_engine = AVFoundation.AVAudioEngine.alloc().init()

input_node = audio_engine.inputNode()
audio_format = input_node.inputFormatForBus_(0)

input_node.installTapOnBus_bufferSize_format_block_(
    0,
    1024,
    audio_format,
    lambda buffer, when: request.appendAudioPCMBuffer_(buffer),
)

def handle_result(result, error):
    if result is not None:
        print(result.bestTranscription().formattedString())
    if error is not None:
        print("STT error:", error)

speech_recognizer.recognitionTaskWithRequest_resultHandler_(request, handle_result)
audio_engine.prepare()
audio_engine.startAndReturnError_(None)
```

### Native Apple TTS from Python
```python
from AVFoundation import AVSpeechSynthesizer, AVSpeechUtterance, AVSpeechSynthesisVoice

synth = AVSpeechSynthesizer.alloc().init()
utterance = AVSpeechUtterance.speechUtteranceWithString_("Hello Joseph, I'm ready.")
utterance.setVoice_(AVSpeechSynthesisVoice.voiceWithLanguage_("en-AU"))
utterance.setRate_(0.48)
synth.speakUtterance_(utterance)
```

## AirPods Max mic handling
- On Apple platforms, the **system audio route** usually selects the active AirPods Max microphone automatically.
- On iOS, use `AVAudioSession.availableInputs` and `setPreferredInput(...)`.
- On macOS, enumerate/select capture devices with `AVCaptureDevice` or use the system-selected default input.
- Apple’s newer speech stack is designed to benefit from far-field and beamformed microphone setups, so AirPods Max are a good fit.

## Latency characteristics
- **Strong for local UX** because there is no cloud round-trip.
- Actual latency depends on hardware and model availability, but on-device transcription is usually the best privacy/availability tradeoff.
- `AVSpeechSynthesizer` is responsive but not as flexible as Cartesia/ElevenLabs for voice styling.

## Integration with our system

### What exists now
- No direct Apple Speech/PyObjC adapter found in `agentic-brain` yet.
- Current local audio paths use `sox`, `PyAudio`, `afplay`, and `say` rather than native Speech framework bindings.

### Recommended next upgrade
1. Add `agentic_brain/voice/apple_speech.py` adapter using PyObjC.
2. Implement a common `Transcriber` interface so Apple STT can drop into the same place as `faster-whisper` / OpenAI transcription.
3. Use Apple local STT as **the always-on local path**, with OpenAI Realtime or transcription as cloud fallback.
4. Consider `AVSpeechSynthesizer` as a **native fallback TTS** when `say` is too limited or shell-based orchestration is undesirable.

### Best role in the ultimate voice system
**“Local ears”** — primary on-device STT on macOS, especially for accessibility, privacy, and resilience.

### Key references
- Apple Speech docs  
  https://developer.apple.com/documentation/speech/  
  https://developer.apple.com/documentation/speech/sfspeechrecognizer
- Apple speech synthesis docs  
  https://developer.apple.com/documentation/avfoundation/speech-synthesis
- PyObjC AVFoundation notes  
  https://pyobjc.readthedocs.io/en/latest/apinotes/AVFoundation.html

---

# 4. OpenAI Audio APIs

## What it gives us

Best for:
- Fast cloud STT (`gpt-4o-mini-transcribe`, `gpt-4o-transcribe`)
- Realtime voice-to-voice sessions
- Audio-capable GPT-4o / GPT-audio style workflows
- Chained STT -> LLM -> TTS or native speech-in/speech-out

## Installation / Setup
```bash
pip install openai
```

Environment:
```bash
export OPENAI_API_KEY="..."
```

## Python code examples

### File transcription
```python
from openai import OpenAI

client = OpenAI()
with open("sample.wav", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="gpt-4o-mini-transcribe",
        file=f,
    )
print(transcript.text)
```

### Text-to-speech
```python
from openai import OpenAI

client = OpenAI()
audio = client.audio.speech.create(
    model="gpt-4o-mini-tts",
    voice="alloy",
    input="Voice system online.",
)
with open("output.wav", "wb") as f:
    f.write(audio.audio)
```

### Realtime voice-to-voice (conceptual websocket skeleton)
```python
import json
import websocket

ws = websocket.create_connection(
    "wss://api.openai.com/v1/realtime",
    header=["Authorization: Bearer YOUR_OPENAI_API_KEY"],
)

ws.send(json.dumps({
    "type": "session.update",
    "session": {
        "modalities": ["audio", "text"],
        "instructions": "Reply briefly, in 1 to 2 short sentences.",
    }
}))

# Then stream PCM audio frames in and read transcript/audio events out.
```

## Relevant models / capabilities
- `gpt-4o-mini-transcribe`
- `gpt-4o-transcribe`
- `gpt-4o-transcribe-diarize`
- `whisper-1`
- `gpt-4o-mini-tts`
- Realtime speech-capable models via Realtime API

## Latency characteristics
- **Transcription API:** good for turn-based STT, but still request/response oriented.
- **Realtime API:** best OpenAI option for low-latency speech streaming; docs position it for voice agents.
- **Chat/audio chaining:** more controllable, but adds latency compared with direct realtime speech-to-speech.

## Integration with our system

### Already present
- `voice_standalone.py` directly POSTs to `/v1/audio/transcriptions`.
- Default model there is already `gpt-4o-mini-transcribe`.
- `voice_copilot_bridge.py` reuses the same transcription setting for spoken prompts.
- `voice_test_all.py` and other tests already point at OpenAI audio usage patterns.

### Recommended next upgrade
1. Replace raw `requests.post(...)` transcription calls with the official `openai` SDK.
2. Add a **Realtime API adapter** under `agentic_brain/voice/` for truly streaming speech input/output.
3. Feed Realtime partial transcripts into the existing streaming buffer/stitcher abstractions from `tests/test_voice_transcription_streaming.py`.
4. Keep OpenAI as the **cloud STT fallback** even if Apple Speech becomes the local primary.

### Best role in the ultimate voice system
**“Cloud ears”** and optionally **“speech-native cloud turn handler.”**

### Key references
- OpenAI audio overview  
  https://developers.openai.com/api/docs/guides/audio
- OpenAI speech-to-text guide  
  https://developers.openai.com/api/docs/guides/speech-to-text
- OpenAI realtime transcription guide  
  https://developers.openai.com/api/docs/guides/realtime-transcription

---

# 5. Real-Time TTS Options

## 5.1 Cartesia

## Installation / Setup
```bash
pip install cartesia
# For websocket streaming
pip install 'cartesia[websockets]'
```

Environment:
```bash
export CARTESIA_API_KEY="..."
export CARTESIA_VOICE_ID="..."
```

## Python code example
```python
from cartesia import Cartesia
import os

client = Cartesia(api_key=os.environ["CARTESIA_API_KEY"])

with client.tts.websocket_connect() as connection:
    ctx = connection.context(
        model_id="sonic-3",
        voice={"mode": "id", "id": os.environ["CARTESIA_VOICE_ID"]},
        output_format={
            "container": "raw",
            "encoding": "pcm_f32le",
            "sample_rate": 44100,
        },
    )
    ctx.push("Hello Joseph, this is Cartesia streaming audio.")
    ctx.no_more_inputs()

    for response in ctx.receive():
        if getattr(response, "type", None) == "chunk" and getattr(response, "audio", None):
            chunk = response.audio
            # Send chunk to PyAudio, afplay bridge, or serializer
```

## Latency characteristics
- Cartesia docs explicitly claim:
  - **Sonic 3:** first byte in about **90ms**
  - **Sonic Turbo:** first byte in about **40ms**
- This is the strongest fit for **real-time conversational TTS** in this stack.

## Integration with our system

### Already present
- `src/agentic_brain/voice/cartesia_tts.py` already supports:
  - lazy init
  - sync synthesis
  - websocket chunk streaming
- `src/agentic_brain/voice/cartesia_bridge.py` already turns those chunks into live playback.
- `src/agentic_brain/voice/conversation_loop.py` already treats Cartesia as the preferred streaming TTS path.

### Recommended next upgrade
1. Make Cartesia the default TTS when API key is present.
2. Feed Claude/Copilot sentence chunks directly into `CartesiaLiveMode`.
3. Keep `say` as automatic fallback when Cartesia or network fails.

### Best role in the ultimate voice system
**Primary streaming TTS.**

### Key references
- Cartesia docs  
  https://docs.cartesia.ai/
- Sonic 3 docs  
  https://docs.cartesia.ai/build-with-cartesia/tts-models/latest

---

## 5.2 ElevenLabs

## Installation / Setup
```bash
pip install elevenlabs
# Optional realtime playback helpers
pip install 'elevenlabs[pyaudio]'
```

Environment:
```bash
export ELEVENLABS_API_KEY="..."
export ELEVENLABS_VOICE_ID="..."
```

## Python code example
```python
from elevenlabs import stream
from elevenlabs.client import ElevenLabs
import os

client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
audio_stream = client.text_to_speech.stream(
    text="Hello Joseph, this is ElevenLabs streaming audio.",
    voice_id=os.environ["ELEVENLABS_VOICE_ID"],
    model_id="eleven_flash_v2_5",
)

for chunk in audio_stream:
    if isinstance(chunk, bytes):
        # hand chunk to playback layer
        pass

# Or play locally:
# stream(audio_stream)
```

## Latency characteristics
- ElevenLabs docs position **`eleven_flash_v2_5`** as the low-latency realtime model.
- Claimed latency is about **75ms** excluding network/application overhead.
- Great quality, very competitive speed, but Cartesia is still the cleaner fit for ultra-low-latency chunk streaming in this repo.

## Integration with our system

### Current state
- `src/agentic_brain/voice/cloud_tts.py` mentions ElevenLabs in the module docstring.
- I did **not** find a concrete ElevenLabs adapter implementation in `agentic-brain` yet.

### Recommended next upgrade
1. Add `src/agentic_brain/voice/elevenlabs_tts.py`.
2. Match the Cartesia adapter interface:
   - `synthesize(text) -> bytes`
   - `synthesize_streaming(text) -> Iterator[bytes]`
3. Add provider selection logic in `cloud_tts.py` and/or `tts_fallback.py`.
4. Use ElevenLabs as the **premium expressive fallback** when Cartesia is unavailable or a specific voice is preferred.

### Best role in the ultimate voice system
**Premium fallback / alternative persona TTS.**

### Key references
- ElevenLabs docs  
  https://elevenlabs.io/docs
- Overview / intro  
  https://elevenlabs.io/docs/overview/intro

---

## 5.3 macOS native `say`

## Installation / Setup
None. Built into macOS.

## Python code example
```python
import subprocess

subprocess.run(
    ["say", "-v", "Karen", "-r", "160", "Voice system online."],
    check=False,
    capture_output=True,
)
```

## Latency characteristics
- Low setup cost, instant availability, local-only.
- Good fallback behavior, but **not true chunk-streaming TTS**.
- Better for resilient fallback than for premium conversational UX.

## Integration with our system

### Already present
- `voice_standalone.py` speaks with `say` directly.
- `voice_copilot_bridge.py` uses `VoiceIO.speak(...)`, which routes to `say`.
- `conversation_loop.py` already treats macOS `say` as the fallback if Cartesia is disabled/unavailable.

### Recommended next upgrade
- Keep it exactly as the **final local fallback**.
- If shell orchestration becomes awkward, replace with a Python `AVSpeechSynthesizer` bridge while keeping `say` as the zero-dependency emergency path.

### Best role in the ultimate voice system
**Always-available local fallback TTS.**

---

# Recommended Final Architecture for This Repo

## Lowest-latency production path
1. **Mic capture:** `AVAudioEngine` (Apple) or existing PyAudio/Sox path
2. **Primary STT:** Apple Speech / SpeechAnalyzer on-device
3. **Fallback STT:** OpenAI Realtime or `gpt-4o-mini-transcribe`
4. **Fast conversational LLM:** local / existing LLM path for trivial turns
5. **Quality reasoning LLM:** Anthropic Claude SDK streaming
6. **Tool-rich work turns:** GitHub Copilot CLI with MCP enabled
7. **Primary TTS:** Cartesia streaming
8. **Fallback TTS:** ElevenLabs Flash
9. **Emergency fallback:** macOS `say`
10. **State bus:** Redis namespaces (`voice:*`), already proven in repo

## File-level implementation plan
- Add `src/agentic_brain/voice/apple_speech.py`
- Add `src/agentic_brain/voice/openai_realtime.py`
- Add `src/agentic_brain/voice/anthropic_streaming.py`
- Add `src/agentic_brain/voice/elevenlabs_tts.py`
- Upgrade `voice_standalone.py` to SDK-backed adapters instead of raw HTTP
- Upgrade `voice_copilot_bridge.py` to structured JSON + MCP presets
- Keep `cartesia_tts.py`, `cartesia_bridge.py`, and `conversation_loop.py` as the core output pipeline

---

# Practical Recommendations

## Best-by-role
- **Best repo/tool brain:** GitHub Copilot CLI
- **Best reasoning brain:** Anthropic Claude SDK
- **Best local STT:** Apple Speech framework
- **Best cloud STT / realtime audio:** OpenAI audio APIs
- **Best real-time TTS:** Cartesia
- **Best expressive fallback TTS:** ElevenLabs
- **Best zero-dependency fallback:** macOS `say`

## If building this tomorrow
- Keep current Redis state model.
- Make Cartesia the default speaking path.
- Add Apple Speech for local ears.
- Add OpenAI SDK fallback for transcription.
- Move Anthropic to streaming.
- Use Copilot only when tool execution / repo awareness is needed.

---

# Sources

## Official / primary sources used
- GitHub Copilot CLI programmatic docs  
  https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically
- Local `copilot --help` / `gh copilot -- --help`
- Anthropic Python SDK docs  
  https://platform.claude.com/docs/en/api/sdks/python
- OpenAI audio docs  
  https://developers.openai.com/api/docs/guides/audio
- OpenAI speech-to-text docs  
  https://developers.openai.com/api/docs/guides/speech-to-text
- OpenAI realtime transcription docs  
  https://developers.openai.com/api/docs/guides/realtime-transcription
- Apple Speech docs  
  https://developer.apple.com/documentation/speech/
- Apple AVFoundation speech docs  
  https://developer.apple.com/documentation/avfoundation/speech-synthesis
- PyObjC AVFoundation notes  
  https://pyobjc.readthedocs.io/en/latest/apinotes/AVFoundation.html
- Cartesia docs  
  https://docs.cartesia.ai/
- ElevenLabs docs  
  https://elevenlabs.io/docs

## Repo files inspected
- `/Users/joe/brain/agentic-brain/voice_copilot_bridge.py`
- `/Users/joe/brain/agentic-brain/voice_standalone.py`
- `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/cartesia_tts.py`
- `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/cartesia_bridge.py`
- `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/cloud_tts.py`
- `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/conversation_loop.py`
- `/Users/joe/brain/agentic-brain/tests/test_voice_transcription_streaming.py`
