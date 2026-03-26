# Agentic Brain - System Requirements

## Minimum Requirements

**The Golden Rule: If you have 4GB RAM, agentic-brain WILL work.**

### Why These Requirements?

Agentic-brain is designed to ALWAYS work. No "configure your LLM" errors. Ever.

- **L1 model (llama3.2:3b)** needs only 2GB RAM
- **OS overhead** varies by platform (1-2GB)
- **Total minimum: 4GB** = L1 always works

If local LLM won't run, agentic-brain guides you to FREE cloud APIs (Gemini, Groq).

---

## Platform Requirements

### Windows

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Windows 10 (64-bit) | Windows 11 |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 5 GB free | 20 GB free |
| **CPU** | Any x64 | 4+ cores |
| **GPU** | Not required | NVIDIA for speed |

**Windows RAM Budget:**
- Windows 10/11: ~1.5-2 GB OS overhead
- L1 model: 2 GB
- Agentic-brain: 0.5 GB
- **Total needed: 4 GB minimum**

**Windows Versions Tested:**
- ✅ Windows 11 23H2
- ✅ Windows 11 22H2
- ✅ Windows 10 22H2
- ⚠️ Windows 10 older versions (should work, not tested)

---

### macOS

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | macOS 12 Monterey | macOS 14 Sonoma |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 5 GB free | 20 GB free |
| **CPU** | Intel or Apple Silicon | Apple M1/M2/M3 |
| **GPU** | Not required | Metal (built-in) |

**macOS RAM Budget:**
- macOS: ~1-1.5 GB OS overhead (efficient!)
- L1 model: 2 GB
- Agentic-brain: 0.5 GB
- **Total needed: 4 GB minimum**

**macOS Versions Tested:**
- ✅ macOS 14 Sonoma (Intel & Apple Silicon)
- ✅ macOS 13 Ventura
- ✅ macOS 12 Monterey
- ⚠️ macOS 11 Big Sur (should work, not tested)

**Apple Silicon Bonus:**
- M1/M2/M3 chips have unified memory = LLMs run FAST
- Metal GPU acceleration automatic
- L2 model (8GB) runs great on 16GB M1/M2/M3

---

### Linux

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **OS** | Ubuntu 20.04 / Debian 11 | Ubuntu 22.04+ |
| **RAM** | 4 GB | 8 GB |
| **Disk** | 5 GB free | 20 GB free |
| **CPU** | Any x64 | 4+ cores |
| **GPU** | Not required | NVIDIA (CUDA) |

**Linux RAM Budget:**
- Linux: ~0.5-1 GB OS overhead (most efficient!)
- L1 model: 2 GB
- Agentic-brain: 0.5 GB
- **Total needed: 3-4 GB minimum**

**Linux Distros Tested:**
- ✅ Ubuntu 22.04 LTS
- ✅ Ubuntu 20.04 LTS
- ✅ Debian 12 Bookworm
- ✅ Debian 11 Bullseye
- ✅ Fedora 39
- ✅ Arch Linux (rolling)
- ⚠️ CentOS/RHEL (should work, not tested)
- ⚠️ Alpine (minimal, needs glibc)

---

## LLM Fallback Chain

Agentic-brain NEVER fails. Here's the automatic fallback:

```
User's Preferred Model (CL, OP, etc.)
         ↓ (if fails)
Cloud Fallback (rate limit, quota, error)
         ↓ (if fails)  
Local L2 (llama3.1:8b - 5GB RAM)
         ↓ (if not enough RAM)
Local L1 (llama3.2:3b - 2GB RAM) ← ALWAYS WORKS
         ↓ (if Ollama won't install)
FREE Cloud: Gemini (GO) or Groq (GR)
```

**There is ALWAYS a path to a working LLM.**

---

## If Local LLM Won't Work

If your system can't run Ollama (old hardware, restricted environment):

### Option 1: Google Gemini (FREE)

1. Go to: https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Click "Create API Key"
4. Copy the key (starts with `AIza...`)
5. Run: `agentic switch GO`

**Gemini FREE tier: 1 million tokens/day** - plenty!

### Option 2: Groq (FREE)

1. Go to: https://console.groq.com/keys
2. Sign up (free account)
3. Create API key
4. Copy the key (starts with `gsk_...`)
5. Run: `agentic switch GR`

**Groq FREE tier: 30 requests/minute** - fast!

---

## Model RAM Requirements

| Model | Code | RAM Needed | Notes |
|-------|------|------------|-------|
| llama3.2:3b | L1 | 2 GB | Fast, always works |
| llama3.1:8b | L2 | 5 GB | Quality, needs 8GB system |
| mistral:7b | L3 | 4.5 GB | Alternative |
| nomic-embed | L4 | 0.5 GB | Embeddings only |

**Recommendation by System RAM:**

| System RAM | Best Local Model | Strategy |
|------------|-----------------|----------|
| 4 GB | L1 only | Use cloud for complex tasks |
| 8 GB | L1 + L2 | L1 fast, L2 quality |
| 16 GB | L1 + L2 + L3 | Full local capability |
| 32 GB+ | All models | Run multiple simultaneously |

---

## Quick Start by Platform

### Windows
```powershell
# Install Ollama
winget install Ollama.Ollama

# Pull minimum model
ollama pull llama3.2:3b

# Install agentic-brain
pip install agentic-brain

# Run
agentic chat
```

### macOS
```bash
# Install Ollama
brew install ollama

# Start Ollama (auto-starts on boot)
brew services start ollama

# Pull minimum model
ollama pull llama3.2:3b

# Install agentic-brain
pip install agentic-brain

# Run
agentic chat
```

### Linux
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull minimum model
ollama pull llama3.2:3b

# Install agentic-brain
pip install agentic-brain

# Run
agentic chat
```

---

## Verification

After setup, verify everything works:

```bash
# Check Ollama
curl http://localhost:11434/api/tags

# Check agentic-brain
agentic models

# Test L1
agentic test-model L1

# Start chatting
agentic chat
```

**If ALL of these pass, you're military-grade ready!** 🎖️

---

## Troubleshooting

### "Not enough RAM"
- Close other applications
- Use L1 instead of L2
- Use cloud models (GO, GR) - they're FREE

### "Ollama won't start"
- Check: `ollama serve` manually
- Check port 11434 not in use
- Reinstall Ollama

### "No LLM configured"
- This should NEVER happen with agentic-brain
- Run: `agentic switch L1` (or GO, or GR)
- Report bug if you see this error!

---

## The Dream

Agentic-brain is designed so that:

1. **It ALWAYS works** - minimum 4GB RAM = success
2. **It guides you** - interactive setup, clear help
3. **It falls back gracefully** - cloud → local → free cloud
4. **It's accessible** - screen reader friendly, simple commands
5. **It's self-improving** - can make PRs to fix itself

**No excuses. No complex setup. Just type `agentic chat` and go.**
