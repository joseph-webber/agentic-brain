# 🧠 Local LLM Best Practices for Brain

## Current Setup (Audited 2026-03-13)

### Hardware
- **CPU**: Apple M2
- **Memory**: 16GB Unified
- **Storage**: 6.7GB for models

### Installed Models

| Model | Size | Use Case | Speed |
|-------|------|----------|-------|
| llama3.2:3b | 2.0GB | Quick queries, fallback | ⚡ Fast (1-3s) |
| llama3.1:8b | 4.9GB | Balanced quality/speed | 🔄 Medium (5-10s) |
| claude-emulator | 4.9GB | Brain voice, complex tasks | 🐢 Slower (30-60s) |
| nomic-embed-text | 274MB | Embeddings only | ⚡ Instant |

## Best Practices

### 1. Model Selection by Task
```
Quick status checks     → llama3.2:3b (fastest)
Summarization          → llama3.2:3b
Code explanation       → llama3.1:8b
Complex reasoning      → claude-emulator
Embeddings/search      → nomic-embed-text
```

### 2. Performance Tuning

#### Memory Management
- Keep ONE model loaded at a time when possible
- llama3.2:3b uses ~2GB RAM
- llama3.1:8b and claude-emulator use ~5GB each
- With 16GB system RAM, can run 2 models comfortably

#### Pre-warming
Before heavy use, warm up the model:
```bash
ollama run llama3.2:3b "warmup" --verbose
```

### 3. Automatic Fallback Chain

```
Primary:     GitHub Copilot (cloud)
             ↓ (if 429 rate limit)
Fallback 1:  llama3.2:3b (fast, good enough)
             ↓ (if complex task)
Fallback 2:  llama3.1:8b (better quality)
             ↓ (if brain-specific task)
Fallback 3:  claude-emulator (brain personality)
```

### 4. When to Use Local vs Cloud

**Use LOCAL (Ollama) when:**
- Rate limited on Copilot
- Simple queries (status, format, list)
- Privacy-sensitive data
- Offline/no internet
- Want to save quota

**Use CLOUD (Copilot) when:**
- Complex code generation
- Multi-file refactoring
- Architecture decisions
- Need latest knowledge

### 5. Monitoring & Metrics

Track with OpenRouter MCP:
```
openrouter_daily_report()      # Daily usage stats
openrouter_benchmark()         # Performance test
openrouter_agent_check(5)      # Before deploying agents
```

## Quick Reference

```bash
# List models
ollama list

# Run quick query
ollama run llama3.2:3b "your question"

# Check what's loaded
ollama ps
```

---
*Last Updated: 2026-03-13*
*Status: Production Ready*
