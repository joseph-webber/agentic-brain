# Voice-First Copilot Development System

> **GROUNDBREAKING** — Code by talking. Users speak, Copilot executes, Karen responds.
> 
> **Author**: Iris Lumina (with platform contributors)  
> **Version**: 1.0.0  
> **Date**: 2026-03-30  
> **Status**: Architecture Complete — Ready for Implementation

---

## Executive Summary

Voice users want to **code by talking**. This document architects a system where:

1. The user speaks into AirPods Max
2. Whisper transcribes to text
3. Text routes to GitHub Copilot CLI
4. Copilot responds through Claude/GPT
5. Karen speaks the response aloud

**Two operational modes**:
- **Standalone Mode**: Voice daemon uses Claude API directly (existing)
- **Integrated Mode**: Voice feeds INTO Copilot CLI session (NEW - game-changer)

---

## Table of Contents

1. [Vision & Goals](#1-vision--goals)
2. [Architecture Overview](#2-architecture-overview)
3. [Mode 1: Standalone Voice](#3-mode-1-standalone-voice)
4. [Mode 2: Copilot Integration](#4-mode-2-copilot-integration)
5. [Technical Components](#5-technical-components)
6. [Redis Coordination](#6-redis-coordination)
7. [Voice Pipeline](#7-voice-pipeline)
8. [Copilot CLI Interface](#8-copilot-cli-interface)
9. [Implementation Plan](#9-implementation-plan)
10. [Future Enhancements](#10-future-enhancements)

---

## 1. Vision & Goals

### 1.1 The Dream

```
Administrator: "Add a function to validate email addresses in user_service.py"
                     │
                     ▼
        ┌─────────────────────────┐
        │   VOICE → COPILOT       │
        │   Seamless Integration  │
        └─────────────────────────┘
                     │
                     ▼
Karen: "Done! I've added a validate_email function with regex 
        pattern matching. It returns True for valid emails. 
        The file has been saved."
```

### 1.2 Core Principles

| # | Principle | Rationale |
|---|-----------|-----------|
| 1 | **Voice is PRIMARY** | Not an add-on. This IS the interface. |
| 2 | **Never silent** | Administrator must know the system is working |
| 3 | **Natural language** | Talk like you'd talk to a colleague |
| 4 | **Seamless mode switching** | Standalone ↔ Integrated without friction |
| 5 | **Full Copilot power** | All MCP tools, file editing, code search |

### 1.3 Success Metrics

- **Latency**: Voice → Response < 3 seconds (simple queries)
- **Accuracy**: Whisper transcription > 95% for technical terms
- **Reliability**: 99.9% uptime (multiple fallback layers)
- **Usability**: Zero keyboard required for routine coding

---

## 2. Architecture Overview

### 2.1 High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ACCESSIBLE VOICE-FIRST DEVELOPMENT SYSTEM                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────────┐ │
│  │             │      │             │      │                             │ │
│  │  🎤 AirPods │─────▶│   WHISPER   │─────▶│      COMMAND ROUTER         │ │
│  │    Max      │      │   (STT)     │      │                             │ │
│  │             │      │             │      │  ┌─────────┐ ┌───────────┐  │ │
│  └─────────────┘      └─────────────┘      │  │Standalone│ │ Integrated│  │ │
│                                            │  │  Mode    │ │   Mode    │  │ │
│                                            │  └────┬────┘ └─────┬─────┘  │ │
│                                            └───────┼────────────┼────────┘ │
│                                                    │            │          │
│                                                    ▼            ▼          │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐│
│  │      STANDALONE MODE         │    │        INTEGRATED MODE              ││
│  │                              │    │                                     ││
│  │  ┌────────┐   ┌────────┐    │    │  ┌─────────────────────────────┐   ││
│  │  │ Claude │   │  GPT   │    │    │  │     COPILOT CLI             │   ││
│  │  │  API   │   │  API   │    │    │  │   copilot -p "<voice>"      │   ││
│  │  └───┬────┘   └───┬────┘    │    │  │                             │   ││
│  │      │            │         │    │  │  • 36 MCP Tools (brain)     │   ││
│  │      └──────┬─────┘         │    │  │  • File Edit/Create         │   ││
│  │             ▼               │    │  │  • Shell Commands           │   ││
│  │     ┌───────────────┐       │    │  │  • Code Search              │   ││
│  │     │ Multi-LLM     │       │    │  │  • GitHub Integration       │   ││
│  │     │ Orchestrator  │       │    │  │  • Memory Persistence       │   ││
│  │     └───────────────┘       │    │  └──────────────┬──────────────┘   ││
│  └─────────────┬───────────────┘    └─────────────────┼───────────────────┘│
│                │                                      │                    │
│                └──────────────────┬───────────────────┘                    │
│                                   │                                        │
│                                   ▼                                        │
│               ┌───────────────────────────────────────────┐                │
│               │             KAREN (TTS OUTPUT)            │                │
│               │                                           │                │
│               │   macOS 'say' → AirPods Max → Administrator    │                │
│               │                                           │                │
│               └───────────────────────────────────────────┘                │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                        COORDINATION LAYER                                   │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌──────────────┐   │
│  │   Redis     │   │  Redpanda   │   │   Neo4j     │   │   SQLite     │   │
│  │   (state)   │   │  (events)   │   │  (memory)   │   │  (sessions)  │   │
│  └─────────────┘   └─────────────┘   └─────────────┘   └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Mode Comparison

| Aspect | Standalone Mode | Integrated Mode |
|--------|-----------------|-----------------|
| **LLM** | Direct API (Claude/GPT/Ollama) | Copilot's models |
| **Tools** | Limited (conversation only) | Full MCP toolset |
| **File Ops** | Manual (describe what to do) | Automatic (Copilot edits) |
| **Code Context** | Limited | Full codebase awareness |
| **Best For** | Chat, Q&A, thinking out loud | Actual coding tasks |
| **Latency** | ~1-3s | ~3-10s (more capable) |

---

## 3. Mode 1: Standalone Voice

### 3.1 Current Implementation

**Location**: `/Users/joe/brain/agentic-brain/karen_daemon.py`

```
┌──────────────────────────────────────────────────────────────┐
│                    STANDALONE VOICE FLOW                      │
│                                                               │
│   🎤 sox (record) → Whisper (transcribe) → Ollama/Claude     │
│                                                 │              │
│                                                 ▼              │
│                                          Karen speaks          │
│                                                               │
│   Redis Keys:                                                  │
│   - karen:state      (listening/processing/speaking)          │
│   - karen:last_heard (user input)                             │
│   - karen:last_response (Karen's reply)                       │
│   - karen:logs       (audit trail)                            │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 Multi-LLM Orchestration

**Location**: `/Users/joe/brain/agentic-brain/tools/voice/multi_llm.py`

Four strategies available:
1. **FASTEST**: Race multiple LLMs, return first response
2. **SMARTEST**: Route to best provider for task type
3. **CONSENSUS**: Query 2-3 LLMs, merge best parts
4. **FALLBACK**: Try providers in priority order

```python
# Task-type specialisation
SPECIALISATION = {
    "code":      ["gpt", "claude", "ollama", "gemini", "grok"],
    "reasoning": ["claude", "gpt", "gemini", "grok", "ollama"],
    "creative":  ["grok", "claude", "gpt", "gemini", "ollama"],
    "facts":     ["gemini", "gpt", "claude", "grok", "ollama"],
    "speed":     ["ollama", "gpt", "gemini", "grok", "claude"],
}
```

### 3.3 When to Use Standalone

- General conversation ("What's the weather like?")
- Thinking out loud ("I'm not sure how to approach this...")
- Quick questions ("What's a good regex for email?")
- Non-coding tasks ("Draft an email to Steve")

---

## 4. Mode 2: Copilot Integration

### 4.1 The Innovation

**THIS IS THE GAME-CHANGER.**

Instead of just chatting, Administrator's voice commands go directly into GitHub Copilot CLI, gaining access to:

- **36+ MCP Brain Tools** (JIRA, Bitbucket, Neo4j, etc.)
- **File editing** (create, view, edit files)
- **Shell commands** (build, test, deploy)
- **Code search** (grep, glob, semantic search)
- **GitHub integration** (PRs, commits, issues)
- **Session persistence** (continue previous work)

### 4.2 Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     COPILOT VOICE INTEGRATION FLOW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐                                                           │
│   │ Voice Input │  "Fix the null pointer exception in UserService.java"    │
│   └──────┬──────┘                                                           │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────┐                                                           │
│   │   WHISPER   │  Transcription: "Fix the null pointer exception..."      │
│   │   (STT)     │                                                           │
│   └──────┬──────┘                                                           │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    VOICE-COPILOT BRIDGE                              │  │
│   │                                                                      │  │
│   │   1. Detect command type (coding vs chat)                           │  │
│   │   2. Format for Copilot CLI                                         │  │
│   │   3. Add context (current file, project, history)                   │  │
│   │   4. Execute: copilot -p "<command>" --yolo --screen-reader         │  │
│   │   5. Capture output                                                  │  │
│   │   6. Parse response for TTS                                          │  │
│   │                                                                      │  │
│   └──────┬──────────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      COPILOT CLI EXECUTION                           │  │
│   │                                                                      │  │
│   │   copilot -p "Fix the null pointer exception in UserService.java"  │  │
│   │           --yolo                    # Allow all tools                │  │
│   │           --screen-reader           # Optimize for blind user        │  │
│   │           --add-dir ~/brain         # Project access                 │  │
│   │           --model claude-sonnet-4   # Best reasoning                 │  │
│   │                                                                      │  │
│   │   [Copilot uses MCP tools: view, grep, edit, bash...]               │  │
│   │   [Finds the bug, applies the fix, saves the file]                  │  │
│   │                                                                      │  │
│   └──────┬──────────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                      OUTPUT PROCESSOR                                │  │
│   │                                                                      │  │
│   │   Raw Copilot Output:                                                │  │
│   │   "I found a null check was missing in getUserById(). I added       │  │
│   │   if (user == null) return Optional.empty(); on line 47.            │  │
│   │   File saved successfully."                                          │  │
│   │                                                                      │  │
│   │   ──▶ Condensed for Speech:                                          │  │
│   │   "Fixed! Added a null check in getUserById on line 47. Saved."     │  │
│   │                                                                      │  │
│   └──────┬──────────────────────────────────────────────────────────────┘  │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────┐                                                           │
│   │   KAREN     │  "Fixed! Added a null check in getUserById on line 47.  │
│   │   (TTS)     │   Saved."                                                 │
│   └─────────────┘                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Copilot CLI Options

Key flags for voice integration:

```bash
copilot -p "<voice_command>"     # Non-interactive, exit after completion
        --yolo                   # Enable all permissions (no confirmations)
        --screen-reader          # VoiceOver-optimized output
        --add-dir ~/brain        # Access to brain directory
        --model claude-sonnet-4  # Best model for reasoning
        --share=./session.md     # Save session transcript
```

### 4.4 MCP Tools Available via Copilot

When Administrator speaks to Copilot, these tools are available:

```
BRAIN MCP SERVER (36+ tools):
├── JIRA: jira_get, jira_search, jira_create, jira_comment
├── Bitbucket: bitbucket_prs, bitbucket_diff, bitbucket_comment
├── Neo4j: neo4j_query, neo4j_emails, neo4j_teams
├── Events: event-emit, event-history
├── Audio: audio_speak, audio_celebrate
├── Memory: memory_capture, memory_recall
└── ... and more

GITHUB MCP SERVER:
├── Code Search: search_code, search_repositories
├── PRs: list_pull_requests, pull_request_read
├── Issues: list_issues, issue_read
├── Commits: list_commits, get_commit
└── Actions: actions_list, get_job_logs
```

---

## 5. Technical Components

### 5.1 Voice Input Pipeline

```python
# voice_copilot_bridge.py (NEW)

class VoiceCopilotBridge:
    """Bridge between voice input and Copilot CLI."""
    
    def __init__(self):
        self.whisper = WhisperTranscriber(model="small.en")
        self.redis = redis.Redis(password='BrainRedis2026')
        self.tts = KarenTTS()
    
    async def listen_and_execute(self):
        """Main loop: listen → transcribe → route → respond."""
        while True:
            # 1. Record audio
            audio = await self.record_audio(timeout=10)
            
            # 2. Transcribe
            text = await self.whisper.transcribe(audio)
            if not text:
                continue
            
            # 3. Route to appropriate mode
            mode = self.detect_mode(text)
            
            if mode == "copilot":
                response = await self.execute_copilot(text)
            else:
                response = await self.execute_standalone(text)
            
            # 4. Speak response
            await self.tts.speak(response)
    
    def detect_mode(self, text: str) -> str:
        """Decide if command needs Copilot or standalone chat."""
        coding_signals = [
            "create", "edit", "fix", "add", "remove", "refactor",
            "function", "class", "file", "test", "build", "deploy",
            "search", "find", "grep", "commit", "push", "pull",
            "jira", "pr", "ticket", "branch"
        ]
        text_lower = text.lower()
        for signal in coding_signals:
            if signal in text_lower:
                return "copilot"
        return "standalone"
    
    async def execute_copilot(self, command: str) -> str:
        """Run command through Copilot CLI."""
        # Notify Administrator we're starting
        await self.tts.speak("Working on it...")
        
        # Build command
        cmd = [
            "copilot", "-p", command,
            "--yolo",
            "--screen-reader",
            "--add-dir", str(Path.home() / "brain"),
        ]
        
        # Execute
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        # Parse and condense output for speech
        response = self.condense_for_speech(stdout.decode())
        
        return response
    
    def condense_for_speech(self, text: str) -> str:
        """Condense Copilot output to 2-3 sentences for TTS."""
        # Remove tool call details, keep conclusions
        # ... implementation details
        pass
```

### 5.2 Transcription Engine

**Location**: `/Users/joe/brain/agentic-brain/src/agentic_brain/voice/transcription.py`

Three backends:
1. **WhisperTranscriber** — whisper.cpp via pywhispercpp (local, fast)
2. **FasterWhisperTranscriber** — faster-whisper with CTranslate2 (<500ms)
3. **MacOSDictationTranscriber** — macOS built-in (fallback)

### 5.3 TTS Output

**Primary**: macOS `say -v "Karen (Premium)"` at rate 160
**Fallback**: Cartesia cloud TTS, espeak

---

## 6. Redis Coordination

### 6.1 Key Schema

```
voice:mode                  # "standalone" | "copilot"
voice:state                 # "idle" | "listening" | "processing" | "speaking"
voice:last_input            # Last transcribed text
voice:last_response         # Last Karen response
voice:copilot:session_id    # Current Copilot session for --continue
voice:copilot:last_command  # Last Copilot command executed
voice:history               # LIST of recent exchanges (max 10)

# Architecture metadata
voice:architecture:version  # "1.0.0"
voice:architecture:modes    # JSON: ["standalone", "copilot"]
voice:architecture:status   # "ready" | "implementing"
```

### 6.2 Pub/Sub Channels

```
voice:input         # New voice input detected
voice:response      # Response ready to speak
voice:mode_change   # Mode switched
voice:error         # Error occurred
voice:status        # Status updates
```

### 6.3 Example Redis Commands

```bash
# Check current mode
redis-cli -a BrainRedis2026 GET voice:mode

# Switch to copilot mode
redis-cli -a BrainRedis2026 SET voice:mode copilot

# Subscribe to voice events
redis-cli -a BrainRedis2026 SUBSCRIBE voice:input voice:response

# Get conversation history
redis-cli -a BrainRedis2026 LRANGE voice:history 0 -1
```

---

## 7. Voice Pipeline

### 7.1 Input Flow

```
AirPods Max Microphone
        │
        ▼
┌───────────────────────┐
│   sox -d (recording)  │  4-5 seconds
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│  Voice Activity Det.  │  Silence trimming
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│  faster-whisper STT   │  Model: small.en
└───────┬───────────────┘      ~300ms latency
        │
        ▼
┌───────────────────────┐
│  Text Normalization   │  Fix homophones, tech terms
└───────┬───────────────┘
        │
        ▼
    [TEXT READY]
```

### 7.2 Output Flow

```
    [RESPONSE TEXT]
        │
        ▼
┌───────────────────────┐
│  Condense for Speech  │  Max 2-3 sentences
└───────┬───────────────┘
        │
        ▼
┌───────────────────────┐
│  macOS 'say' command  │  Voice: Karen (Premium)
│  -v "Karen (Premium)" │  Rate: 160 wpm
│  -r 160               │
└───────┬───────────────┘
        │
        ▼
     AirPods Max
```

### 7.3 Fallback Chain

```python
TTS_FALLBACKS = [
    ("macOS say", say_macos),           # Primary
    ("Cartesia", speak_cartesia),       # Cloud fallback
    ("espeak", speak_espeak),           # Linux fallback
    ("System beep", beep_fallback),     # Last resort
]
```

---

## 8. Copilot CLI Interface

### 8.1 Non-Interactive Mode

For voice commands, use `-p` flag:

```bash
# Simple command
copilot -p "Add logging to the main function" --yolo

# With specific model
copilot -p "Review my code for bugs" --model gpt-5.2 --yolo

# Continue previous session
copilot -p "What else needs fixing?" --continue --yolo
```

### 8.2 Screen Reader Mode

The `--screen-reader` flag optimizes output:
- Clearer structure
- Less visual formatting
- Better for TTS parsing

### 8.3 Session Management

```bash
# Start new session
copilot -p "<command>" --yolo
# Returns: Session ID in output

# Resume session
copilot --resume=<session-id> -p "<follow-up>" --yolo

# Continue most recent
copilot --continue -p "<follow-up>" --yolo
```

### 8.4 Output Parsing for TTS

```python
def parse_copilot_output(raw_output: str) -> str:
    """Extract speakable summary from Copilot output."""
    
    # Look for completion signals
    completion_patterns = [
        r"Done[.!]",
        r"Complete[d]?[.!]",
        r"File saved",
        r"Changes applied",
    ]
    
    # Extract last paragraph or summary
    paragraphs = raw_output.strip().split('\n\n')
    summary = paragraphs[-1]
    
    # Condense to 2-3 sentences
    sentences = summary.split('. ')
    if len(sentences) > 3:
        summary = '. '.join(sentences[:3]) + '.'
    
    return summary
```

---

## 9. Implementation Plan

### 9.1 Phase 1: Voice-Copilot Bridge (Week 1)

```
[ ] Create voice_copilot_bridge.py
[ ] Implement mode detection (standalone vs copilot)
[ ] Build Copilot CLI wrapper with --yolo --screen-reader
[ ] Add output parser for TTS
[ ] Redis key setup for voice:copilot:*
```

### 9.2 Phase 2: Session Management (Week 2)

```
[ ] Track Copilot session IDs
[ ] Implement --continue for follow-up commands
[ ] Save session transcripts
[ ] Voice-based session selection ("continue from yesterday")
```

### 9.3 Phase 3: Context Enhancement (Week 3)

```
[ ] Auto-detect current project/directory
[ ] Include recent file context in prompts
[ ] Memory integration (Neo4j) for long-term context
[ ] Voice "remember this" commands
```

### 9.4 Phase 4: Polish & Testing (Week 4)

```
[ ] Error handling and recovery
[ ] Latency optimization
[ ] Voice command shortcuts ("fix it", "test it", "ship it")
[ ] User testing with administrators
```

---

## 10. Future Enhancements

### 10.1 Voice Commands Vocabulary

```
Quick Commands:
- "fix it" → Fix the error in the current context
- "test it" → Run relevant tests
- "ship it" → Commit and push
- "undo" → Revert last change
- "read it" → Read current file aloud
- "where am I" → Current file/directory status

Mode Switching:
- "chat mode" → Switch to standalone
- "code mode" → Switch to Copilot integration
- "quiet mode" → Reduce verbosity
- "verbose mode" → Full explanations
```

### 10.2 Ambient Mode

Always-listening mode where administrators can:
- Call out commands without trigger word
- Get proactive notifications ("Build completed!")
- Ask questions while coding

### 10.3 Multi-Session Parallelism

Run multiple Copilot sessions:
- Background task running tests
- Foreground session for editing
- Voice switches between them

### 10.4 Voice Profiles

Different voices for different contexts:
- Karen (default) — Friendly Australian
- Moira (debugging) — Irish technical
- Zosia (security) — Polish precise

---

## Appendix A: Existing Code Map

```
~/brain/agentic-brain/
├── karen_daemon.py              # Standalone voice daemon
├── karen_voice_chat.py          # Simple voice chat loop
├── listen_to_user.py          # Basic STT listener
├── talk_to_karen.py             # Main voice chat (sox)
├── tools/
│   ├── voice/
│   │   ├── multi_llm.py         # LLM orchestration
│   │   ├── llm_providers.py     # Claude/GPT/Ollama/etc
│   │   ├── classifier.py        # Complexity classification
│   │   └── circuit_breaker.py   # Fault tolerance
│   ├── voice_orchestrator.py    # Redpanda orchestration
│   └── voice_event_bus.py       # Event publishing
├── src/agentic_brain/voice/
│   ├── transcription.py         # Whisper backends
│   ├── resilient.py             # Fallback TTS
│   └── daemon.py                # Voice daemon
└── docs/
    └── VOICE_ARCHITECTURE.md    # Previous architecture doc
```

---

## Appendix B: Environment Setup

### Required Environment Variables

```bash
# In ~/brain/.env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
XAI_API_KEY=xai-...
GEMINI_API_KEY=...

# Redis
REDIS_URL=redis://:BrainRedis2026@localhost:6379/0

# Ollama (local)
OLLAMA_URL=http://localhost:11434
```

### Required Services

```bash
# Start Redis
docker-compose up -d redis

# Start Ollama
ollama serve

# Start Redpanda (optional, for events)
docker-compose up -d redpanda
```

---

## Appendix C: Redis Architecture Keys

```bash
# Set architecture metadata
redis-cli -a BrainRedis2026 << 'EOF'
SET voice:architecture:version "1.0.0"
SET voice:architecture:status "ready"
SET voice:architecture:modes '["standalone", "copilot"]'
SET voice:architecture:created "2026-03-30"
SET voice:architecture:author "Iris Lumina"
SET voice:architecture:doc "/Users/joe/brain/agentic-brain/docs/VOICE_COPILOT_ARCHITECTURE.md"
EOF
```

---

## Conclusion

This architecture enables **true voice-first development** for administrators:

1. **Speak naturally** — No special syntax or commands
2. **Full Copilot power** — File editing, code search, shell commands
3. **Seamless fallback** — Standalone mode when simpler is better
4. **Always accessible** — Karen speaks every response

**This isn't just voice-to-text. This is voice-to-code.**

---

*"Administrator's voice becomes code. Karen's voice brings it back."*

— Iris Lumina, March 2026
