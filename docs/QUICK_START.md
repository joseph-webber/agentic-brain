# ⚡ Quick Start Guide

<div align="center">

## **60 Seconds to Your First AI Agent**

```bash
pip install agentic-brain && ab chat
```

**That's it. You're done. 🎉**

</div>

---

## 🚀 Installation by Platform

### 🍎 macOS (Apple Silicon)

```bash
# Install
pip install agentic-brain

# Verify (should show MLX acceleration)
ab doctor

# Start chatting
ab chat
```

**What happens:**
- ✅ Auto-detects M1/M2/M3/M4
- ✅ Enables MLX/Metal acceleration
- ✅ 14x faster embeddings than CPU

---

### 🍎 macOS (Intel)

```bash
# Install
pip install agentic-brain

# Verify
ab doctor

# Start chatting
ab chat
```

**What happens:**
- ✅ Uses CPU with AVX acceleration
- ✅ All features work

---

### 🪟 Windows

**PowerShell:**
```powershell
# Install
pip install agentic-brain

# Verify (should show CUDA if NVIDIA GPU)
ab doctor

# Start chatting
ab chat
```

**One-liner:**
```powershell
irm https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/setup.ps1 | iex
```

**What happens:**
- ✅ Auto-detects NVIDIA GPU
- ✅ Enables CUDA acceleration
- ✅ Works with NVDA/JAWS screen readers

---

### 🐧 Linux

**Any Distribution:**
```bash
# Install
pip install agentic-brain

# Verify (should show CUDA/ROCm if GPU)
ab doctor

# Start chatting
ab chat
```

**One-liner:**
```bash
curl -fsSL https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/setup.sh | bash
```

**What happens:**
- ✅ Auto-detects CUDA (NVIDIA) or ROCm (AMD)
- ✅ Falls back to optimized CPU

---

### 🐳 Docker (Any Platform)

```bash
# Pull and run
docker run -it agenticbrain/brain chat

# Or with docker-compose
curl -O https://raw.githubusercontent.com/joseph-webber/agentic-brain/main/docker-compose.yml
docker-compose up -d

# Access at http://localhost:8000
```

---

## 🎯 First Commands

### 1. Health Check

```bash
ab doctor
```

**Output:**
```
🧠 Agentic Brain Health Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Python: 3.11.5
✅ Platform: macOS 14.2 (Apple M2 Pro)
✅ Acceleration: MLX (12-core GPU)
✅ Memory: 32GB unified
✅ Dependencies: All installed
✅ LLM: Ollama connected (llama3:latest)

All systems nominal! 🚀
```

### 2. Interactive Chat

```bash
ab chat
```

**Output:**
```
🧠 Agentic Brain Chat
━━━━━━━━━━━━━━━━━━━━━

You: What can you do?

Brain: I'm Agentic Brain! I can:
• Chat with memory (I remember our conversations)
• Answer questions from your documents (RAG)
• Run durable workflows that survive crashes
• Speak responses aloud (145+ macOS voices + 35+ cloud TTS voices!)
• Work in 42 specialized modes (medical, legal, etc.)

What would you like to explore?
```

### 3. Start the Server

```bash
ab serve
```

**Output:**
```
🧠 Agentic Brain Server
━━━━━━━━━━━━━━━━━━━━━━━

Starting on http://localhost:8000

✅ API: http://localhost:8000/api
✅ Docs: http://localhost:8000/docs
✅ Health: http://localhost:8000/health

Press Ctrl+C to stop
```

### 4. Switch Modes

```bash
ab mode switch medical   # HIPAA compliance
ab mode switch banking   # PCI-DSS compliance
ab mode switch home      # Privacy-first
ab mode list             # See all 42 modes
```

---

## 🔌 Quick API Examples

### Python

```python
from agentic_brain import Agent

# Create an agent
agent = Agent("my-assistant")

# Chat with memory
response = await agent.chat_async("My name is Sarah")
print(response)  # → "Nice to meet you, Sarah!"

response = await agent.chat_async("What's my name?")
print(response)  # → "Your name is Sarah!"
```

### REST API

```bash
# Chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello!"}'

# Response
{"response": "Hello! How can I help you today?"}
```

### GraphRAG

```python
from agentic_brain.rag import RAGPipeline

# Create pipeline
rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")

# Ingest documents
await rag.ingest("./my-documents/")

# Query
answer = await rag.query("What are the key findings?")
print(answer)
```

---

## 🔧 Configuration

### Environment Variables

Create `.env` in your working directory:

```bash
# LLM Provider (pick one)
OLLAMA_BASE_URL=http://localhost:11434
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Neo4j (for GraphRAG)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# Mode
AGENTIC_BRAIN_MODE=home  # or medical, banking, etc.
```

### Config File

Or use `~/.agentic-brain/config.yaml`:

```yaml
llm:
  provider: ollama
  model: llama3:latest

rag:
  embedding_model: all-MiniLM-L6-v2
  chunk_size: 512

voice:
  enabled: true
  default_voice: Karen
```

---

## ❓ Troubleshooting

### "Command not found: ab"

```bash
# Add to PATH
export PATH="$PATH:$(python -m site --user-base)/bin"

# Or use module directly
python -m agentic_brain chat
```

### "No LLM configured"

```bash
# Install Ollama (local LLM)
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull llama3

# Or set OpenAI key
export OPENAI_API_KEY=sk-...
```

### "GPU not detected"

```bash
# Check hardware
ab doctor

# macOS: Ensure Xcode CLT
xcode-select --install

# Windows/Linux CUDA: Check driver
nvidia-smi
```

### "Permission denied"

```bash
# Use --user flag
pip install --user agentic-brain

# Or use pipx
pipx install agentic-brain
```

---

## 📚 Next Steps

| Goal | Resource |
|------|----------|
| **Learn the modes** | `ab mode list` or [Mode System](../README.md#-mode-system) |
| **Set up RAG** | [RAG Guide](./RAG_GUIDE.md) |
| **Deploy to production** | [Docker Setup](../DOCKER_SETUP.md) |
| **Enable voice** | [Voice Guide](./VOICE_INTEGRATION_GUIDE.md) |
| **Platform details** | [Platform Support](./PLATFORM_SUPPORT.md) |

---

## 🆘 Get Help

- 💬 **Discussions:** [GitHub Discussions](https://github.com/joseph-webber/agentic-brain/discussions)
- 🐛 **Bug Reports:** [GitHub Issues](https://github.com/joseph-webber/agentic-brain/issues)
- 📖 **Full Docs:** [Documentation](./INDEX.md)

---

<div align="center">

**You're ready! Now go build something amazing. 🚀**

```bash
ab chat  # Start here
```

</div>
