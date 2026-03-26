# 🦙 Local LLM Production Setup Guide

**For Consultants Deploying Ollama to Clients**

> This guide covers everything needed to deploy reliable, production-ready local LLMs.
> Follow this exactly and your clients will have stable AI that works every time.

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Hardware Requirements](#hardware-requirements)
4. [Installation](#installation)
5. [Auto-Start Configuration](#auto-start-configuration)
6. [Model Selection](#model-selection)
7. [Health Monitoring](#health-monitoring)
8. [Warm-Up Strategy](#warm-up-strategy)
9. [Testing & Validation](#testing--validation)
10. [Troubleshooting](#troubleshooting)
11. [Client Deployment Checklist](#client-deployment-checklist)

---

## Quick Start

```bash
# 1. Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# 2. Set up auto-start (macOS)
./scripts/setup_autostart.sh

# 3. Pull recommended models
ollama pull llama3.2:3b      # Fast, always-loaded (2GB)
ollama pull llama3.1:8b      # Quality, on-demand (5GB)

# 4. Run health check
./scripts/health_check.sh

# 5. Run smoke tests
./scripts/smoke_test.sh
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL LLM ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   Client     │────▶│   Ollama     │────▶│    Model     │   │
│  │   Request    │     │   Server     │     │   (in RAM)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                    │                    │            │
│         │                    ▼                    │            │
│         │            ┌──────────────┐             │            │
│         │            │   Health     │             │            │
│         │            │   Monitor    │             │            │
│         │            └──────────────┘             │            │
│         │                    │                    │            │
│         ▼                    ▼                    ▼            │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │                    System Resources                      │  │
│  │  • RAM: Model storage (2-8GB per model)                 │  │
│  │  • GPU: Apple Silicon / NVIDIA for acceleration         │  │
│  │  • Disk: Model files (~4GB per 7B model)               │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Hardware Requirements

### Minimum (Basic chatbot, simple tasks)
| Component | Requirement |
|-----------|-------------|
| RAM | 8GB |
| Storage | 20GB free |
| CPU | Any modern 4-core |
| Models | llama3.2:3b only |

### Recommended (Professional use)
| Component | Requirement |
|-----------|-------------|
| RAM | 16GB |
| Storage | 50GB free |
| CPU/GPU | Apple M1/M2/M3 or NVIDIA GPU |
| Models | llama3.2:3b + llama3.1:8b |

### Enterprise (Multiple concurrent users)
| Component | Requirement |
|-----------|-------------|
| RAM | 32GB+ |
| Storage | 100GB+ SSD |
| GPU | NVIDIA with 16GB+ VRAM |
| Models | Multiple 7B-70B models |

### RAM Budget Calculator

```
Available RAM = Total RAM - OS (4GB) - Apps (4GB)

Model Memory Usage:
  - 3B model  = ~2GB RAM
  - 7B model  = ~4-5GB RAM
  - 8B model  = ~5GB RAM
  - 13B model = ~8GB RAM
  - 70B model = ~40GB RAM

Example (16GB Mac):
  Available: 16 - 4 - 4 = 8GB
  Can run: 1x 8B model OR 1x 3B + 1x 7B (tight)
```

---

## Installation

### macOS (Apple Silicon)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Verify installation
ollama --version

# Check GPU acceleration
ollama run llama3.2:3b "What GPU are you using?"
# Should mention "Metal" for Apple Silicon
```

### Linux (with NVIDIA GPU)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Install NVIDIA drivers (if not present)
sudo apt install nvidia-driver-535

# Verify GPU detected
nvidia-smi
ollama run llama3.2:3b "What GPU are you using?"
```

### Docker (Any platform)

```bash
# CPU only
docker run -d -v ollama:/root/.ollama -p 11434:11434 ollama/ollama

# With NVIDIA GPU
docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
```

---

## Auto-Start Configuration

### macOS (LaunchAgent)

The setup script creates `~/Library/LaunchAgents/com.ollama.serve.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ollama.serve</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/ollama</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ollama.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ollama.error.log</string>
</dict>
</plist>
```

**Commands:**
```bash
# Load (start now + auto-start on boot)
launchctl load ~/Library/LaunchAgents/com.ollama.serve.plist

# Unload (stop + disable auto-start)
launchctl unload ~/Library/LaunchAgents/com.ollama.serve.plist

# Check status
launchctl list | grep ollama
```

### Linux (systemd)

Ollama installs its own systemd service:

```bash
# Enable auto-start
sudo systemctl enable ollama

# Start now
sudo systemctl start ollama

# Check status
sudo systemctl status ollama

# View logs
journalctl -u ollama -f
```

---

## Model Selection

### Recommended Models by Use Case

| Use Case | Model | Size | Speed | Quality |
|----------|-------|------|-------|---------|
| **Always On** | llama3.2:3b | 2GB | ⚡⚡⚡ | ★★★☆☆ |
| **Quality Chat** | llama3.1:8b | 5GB | ⚡⚡ | ★★★★☆ |
| **Coding** | codellama:7b | 4GB | ⚡⚡ | ★★★★☆ |
| **Balanced** | mistral:7b | 4.5GB | ⚡⚡ | ★★★★☆ |
| **Best Quality** | llama3.1:70b | 40GB | ⚡ | ★★★★★ |

### Model Strategy

**Two-Tier Approach (Recommended):**

1. **Warm Model** (always loaded): `llama3.2:3b`
   - Instant responses (<1 second)
   - Handles 80% of simple queries
   - Uses only 2GB RAM

2. **Quality Model** (on-demand): `llama3.1:8b`
   - Better reasoning
   - For complex tasks
   - Loads in ~5 seconds when needed

```bash
# Pull both models
ollama pull llama3.2:3b
ollama pull llama3.1:8b

# Keep llama3.2:3b warm (load once, stays in RAM)
curl -s http://localhost:11434/api/generate \
  -d '{"model":"llama3.2:3b","prompt":"warmup","stream":false}'
```

---

## Health Monitoring

### Quick Health Check

```bash
curl -s http://localhost:11434/api/tags | jq '.models | length'
# Returns number of available models
```

### Full Health Check Script

See: `scripts/health_check.sh`

Checks:
- ✅ Ollama process running
- ✅ API responding
- ✅ Models available
- ✅ Model inference working
- ✅ Response time acceptable

### Automated Monitoring (cron)

```bash
# Check every 5 minutes, restart if down
*/5 * * * * /path/to/scripts/health_check.sh --auto-restart >> /tmp/ollama-health.log 2>&1
```

---

## Warm-Up Strategy

**Problem:** First request to a model is slow (5-30 seconds) because the model needs to load into RAM.

**Solution:** Keep frequently-used models "warm" (pre-loaded).

### Manual Warm-Up

```bash
# Send a minimal request to load model into RAM
curl -s http://localhost:11434/api/generate \
  -d '{"model":"llama3.2:3b","prompt":"hi","stream":false}' > /dev/null
```

### Automatic Warm-Up on Boot

The setup script configures a LaunchAgent that:
1. Waits for Ollama to start
2. Loads the default warm model
3. Keeps it in RAM

### Keep-Alive (Prevent Unload)

Ollama unloads models after 5 minutes of inactivity. To prevent:

```bash
# Set longer keep-alive (in seconds)
export OLLAMA_KEEP_ALIVE=3600  # 1 hour

# Or per-request
curl -s http://localhost:11434/api/generate \
  -d '{"model":"llama3.2:3b","prompt":"hi","keep_alive":"1h"}'
```

---

## Testing & Validation

### Test Levels

1. **Bootstrap Test** - Is Ollama installed and running?
2. **Smoke Test** - Can models respond at all?
3. **Performance Test** - Are response times acceptable?
4. **Stress Test** - Can it handle concurrent requests?
5. **Quality Test** - Are responses coherent?

### Running Tests

```bash
# All tests
./scripts/run_all_tests.sh

# Individual tests
./scripts/bootstrap_test.sh
./scripts/smoke_test.sh
./scripts/performance_test.sh
```

### Expected Results

| Test | Pass Criteria |
|------|---------------|
| Bootstrap | Ollama process running, API responds |
| Smoke | Each model returns valid response |
| Performance | 3B model < 2s, 8B model < 5s |
| Stress | 5 concurrent requests complete |
| Quality | Response contains expected keywords |

---

## Troubleshooting

### Ollama Not Starting

```bash
# Check if port in use
lsof -i :11434

# Check logs
cat /tmp/ollama.error.log

# Manual start with debug
OLLAMA_DEBUG=1 ollama serve
```

### Slow First Response

**Cause:** Model loading into RAM

**Solution:** Use warm-up script, increase keep-alive

### Out of Memory

```bash
# Check memory usage
ollama ps

# Unload unused models
curl -X DELETE http://localhost:11434/api/models/unload
```

### Model Not Found

```bash
# List available models
ollama list

# Pull missing model
ollama pull llama3.2:3b
```

---

## Client Deployment Checklist

Use this checklist when deploying to a client:

### Pre-Deployment
- [ ] Verify hardware meets requirements
- [ ] Check available disk space (50GB+ recommended)
- [ ] Confirm RAM available (8GB+ for models)
- [ ] Check for existing Ollama installation

### Installation
- [ ] Install Ollama
- [ ] Run setup script: `./scripts/setup_autostart.sh`
- [ ] Pull required models
- [ ] Configure warm-up model

### Testing
- [ ] Run bootstrap test: `./scripts/bootstrap_test.sh`
- [ ] Run smoke test: `./scripts/smoke_test.sh`
- [ ] Run performance test: `./scripts/performance_test.sh`
- [ ] Verify auto-start works (reboot test)

### Documentation
- [ ] Document installed models
- [ ] Document warm model configuration
- [ ] Provide troubleshooting guide
- [ ] Set up monitoring alerts (if applicable)

### Handoff
- [ ] Train client on basic commands
- [ ] Provide support contact
- [ ] Schedule follow-up check

---

## Quick Reference

### Common Commands

```bash
# Start Ollama
ollama serve

# List models
ollama list

# Pull model
ollama pull llama3.2:3b

# Run model interactively
ollama run llama3.2:3b

# Check what's loaded in RAM
ollama ps

# API health check
curl http://localhost:11434/api/tags
```

### Environment Variables

```bash
OLLAMA_HOST=0.0.0.0:11434    # Listen address
OLLAMA_KEEP_ALIVE=5m          # Model unload timeout
OLLAMA_NUM_PARALLEL=4         # Concurrent requests
OLLAMA_MAX_LOADED_MODELS=2    # Max models in RAM
OLLAMA_DEBUG=1                # Debug logging
```

### File Locations

| File | Path |
|------|------|
| Models | ~/.ollama/models/ |
| Logs (macOS) | /tmp/ollama.log |
| Logs (Linux) | journalctl -u ollama |
| LaunchAgent | ~/Library/LaunchAgents/com.ollama.serve.plist |

---

## Support

For issues with this setup:
1. Check troubleshooting section above
2. Run `./scripts/diagnose.sh` for full system report
3. Contact: [Your consulting contact]

---

*Last Updated: March 2026*
*Version: 1.0.0*
