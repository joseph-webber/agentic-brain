# Live Chat Quickstart

Get a fully-functional AI chat running in 60 seconds.

No configuration. No API keys. No Docker. Just install and talk.

---

## Beginner Mode (Zero Config)

```bash
pip install agentic-brain
ab chat
```

That's it. You now have:

- ✅ **Multi-LLM intelligence** — auto-selects the best available model
- ✅ **Voice input/output** — speak to chat, hear responses
- ✅ **Memory** — remembers your conversations across sessions
- ✅ **Self-healing** — auto-recovers from errors, reconnects on failure
- ✅ **Self-configuring** — detects your hardware and adapts automatically

> **First time?** Agentic Brain will detect what's available on your system
> (local Ollama models, API keys in env, Apple Silicon GPU) and configure
> itself. You don't need to set anything up.

---

## What You Get Out of the Box

### 1. Terminal Chat

```bash
ab chat                        # Start chatting instantly
ab chat --voice                # Voice mode (speak + listen)
ab chat --mode airlocked       # 100% offline, no internet
```

The chat is persistent — close your terminal, come back later, and it
remembers everything.

### 2. API Server

```bash
ab serve                       # Start REST + WebSocket server
```

Then from any app:

```bash
curl http://localhost:8000/chat -d '{"message": "Hello!"}'
```

Or connect via WebSocket for real-time streaming:

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/chat");
ws.send(JSON.stringify({ message: "Hello!" }));
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

### 3. Voice Chat

```bash
ab voice speak "Hello world"   # Text-to-speech
ab chat --voice                # Full voice conversation
```

### 4. Python API

```python
from agentic_brain.chat import Chatbot

bot = Chatbot("assistant")
response = bot.chat("Hello! What can you do?")
print(response)
```

Three lines. Production-ready chatbot.

---

## Deployment Modes

Agentic Brain runs in three modes. Pick the one that fits your environment:

| Mode | Internet | Use Case |
|------|----------|----------|
| **airlocked** | ❌ None | Defense, air-gapped networks, total privacy |
| **hybrid** | ⚡ Smart | Local-first with cloud fallback **(default)** |
| **cloud** | ✅ Full | Maximum power, all cloud APIs |

```bash
ab chat --mode airlocked       # Fully offline — nothing leaves your machine
ab chat --mode hybrid          # Best of both worlds (default)
ab chat --mode cloud           # All cloud APIs enabled
```

### Airlocked Mode — For When Nothing Leaves the Box

Perfect for defense, medical, legal, or any environment where data cannot
touch the internet. Uses local Ollama models only. No DNS lookups, no
telemetry, no exceptions.

```bash
# Install Ollama first (one-time)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b        # Fast model (~2GB)
ollama pull llama3.1:8b        # Quality model (~5GB)

# Now chat with zero network access
ab chat --mode airlocked
```

---

## Response Layers (Auto-managed)

Agentic Brain automatically layers responses for speed + quality.
You get the fast answer **immediately** while deeper analysis runs in the
background:

| Layer | Latency | Source | What It Does |
|-------|---------|--------|--------------|
| ⚡ Instant | <500ms | Groq / Ollama | Immediate acknowledgment |
| 🏃 Fast | 1–2s | Local LLMs | Full response from local model |
| 🧠 Deep | 2–10s | Claude / GPT | High-quality refined answer |
| ✅ Consensus | 10s+ | Multi-LLM vote | Cross-verified, hallucination <1% |

**You don't configure this.** It happens automatically based on what's
available. In airlocked mode, only local layers activate.

---

## Self-Healing Features

Agentic Brain is **polymorphic** — it adapts its behavior in real-time:

- 🔄 **Auto-reconnect** — network drops? It queues messages and retries
- 🔀 **LLM failover** — if Claude is down, it routes to GPT, Groq, or local
- 💾 **Message queuing** — nothing is lost during outages
- 🩺 **Health monitoring** — continuously checks its own components
- 🔧 **Self-configuring** — detects new models, GPUs, and API keys automatically
- 🧬 **Polymorphic personas** — adapts communication style to context

```bash
# Check what Agentic Brain auto-detected on your system
ab check
```

---

## Enterprise / Defense Features

For regulated industries, enable enterprise mode:

```bash
pip install agentic-brain[enterprise]
ab chat --mode enterprise
```

This activates:

- 🔒 **Compliance modes** — SOC 2, ISO 27001, HIPAA-ready audit controls
- 📊 **Audit logging** — every interaction logged with timestamps and provenance
- 🛡️ **Multi-LLM consensus** — 3/5 model voting, hallucination rate <1%
- 🔐 **End-to-end encryption** — data encrypted at rest and in transit
- 📋 **Data sovereignty** — control where data is processed and stored
- 🧬 **Polymorphic personas** — industry-specific AI operators (defense, healthcare, legal, finance) with pre-tuned guardrails

### Consensus Verification

For critical decisions, Agentic Brain can cross-verify answers across
multiple LLMs:

```python
from agentic_brain import AgenticBrain

brain = AgenticBrain()
result = brain.consensus_task(
    "Is this contract clause enforceable in NSW?",
    min_agreement=3,
    models=["claude", "gpt", "gemini", "llama", "mistral"]
)

print(f"Answer: {result['consensus']}")
print(f"Confidence: {result['confidence']}")
print(f"Agreement: {result['agreement']}/{result['total']}")
```

---

## Configuration (Optional)

Everything works without config. But if you want to customize, use ADL
(Agentic Definition Language):

```
# brain.adl — Human-readable brain configuration
brain MyAssistant {
  mode hybrid
  voice Karen
  memory neo4j
}

llm primary {
  provider ollama
  model llama3.1:8b
}

llm fallback {
  provider groq
  model llama-3.3-70b-versatile
}
```

```bash
ab init --name my-project      # Generate starter config
```

---

## Common Workflows

### Personal AI Assistant

```bash
pip install agentic-brain
ab chat
# That's it. Start talking.
```

### Add to Your Python App

```python
from agentic_brain.chat import Chatbot

bot = Chatbot("support-agent")

# Single user
response = bot.chat("How do I reset my password?")

# Multi-user (B2B / SaaS)
response = bot.chat("Help with order #123", user_id="customer_456")
response = bot.chat("Check my invoice", user_id="customer_789")  # Isolated
```

### Embed in a Web App

```bash
ab serve --port 8000
```

Then connect from any frontend (React, Vue, vanilla JS) via the
[WebSocket API](./WEBSOCKET_API.md).

### Air-Gapped Deployment

```bash
# On a machine with internet — download everything
pip download agentic-brain -d ./packages
ollama pull llama3.1:8b

# Transfer ./packages and ollama models to air-gapped machine
# On the air-gapped machine:
pip install --no-index --find-links=./packages agentic-brain
ab chat --mode airlocked
```

---

## Troubleshooting

### "No LLM provider found"

```bash
# Option A: Install Ollama (free, local)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2:3b

# Option B: Set a cloud API key
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."

# Then retry
ab chat
```

### "Voice not working"

```bash
# macOS — works out of the box (uses system voices)
ab voice list

# Linux/Windows — install TTS engine
pip install pyttsx3
ab voice list
```

### Check Your Setup

```bash
ab check                       # Shows what's detected and ready
ab version                     # Show version info
```

---

## Next Steps

| Guide | What You'll Learn |
|-------|-------------------|
| [Full API Reference](./API_REFERENCE.md) | Every endpoint and parameter |
| [WebSocket Streaming](./WEBSOCKET_API.md) | Real-time chat in web apps |
| [Voice Configuration](./VOICE_INTEGRATION_GUIDE.md) | Cross-platform voice setup |
| [ADL Configuration](./ADL.md) | Human-readable brain config files |
| [Graph RAG](./GRAPHRAG.md) | Knowledge graphs for smarter answers |
| [Chat Module Deep Dive](./chat.md) | Sessions, memory, hooks, multi-user |
| [Enterprise Compliance](./COMPLIANCE.md) | SOC 2, HIPAA, ISO 27001 details |

---

*Agentic Brain — Install. Run. Create. Zero to AI in 60 seconds.*
