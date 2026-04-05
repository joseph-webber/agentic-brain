# 🤖 Local LLM Fallback System

**Status**: ✅ OPERATIONAL  
**Location**: brain-core (private)  
**Target**: Port reliable fallback to agentic-brain (public)

---

## Overview

When cloud LLM APIs get rate limited (429 errors), the system automatically falls back to local Ollama models. This ensures zero downtime for on-premise deployments.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLOUD LLMs                               │
│  (Claude, GPT-4, etc via GitHub Copilot / OpenRouter)       │
└─────────────────────────────────────────────────────────────┘
                           │
                           │ Rate Limited (429)?
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 FALLBACK ROUTER                             │
│  openrouter_report_429() → activates fallback mode          │
│  openrouter_reset_fallback() → returns to cloud             │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 LOCAL LLMs (Ollama)                         │
│  • llama3.2:3b     - Fast, simple tasks                     │
│  • llama3.1:8b     - Quality, complex tasks                 │
│  • claude-emulator - Brain-aware responses                  │
└─────────────────────────────────────────────────────────────┘
```

## MCP Tools Available

| Tool | Purpose | Speed |
|------|---------|-------|
| `openrouter_quick_local` | Fast queries (llama3.2:3b) | ~500ms target |
| `openrouter_ask_local` | Quality queries (llama3.1:8b) | ~1000ms target |
| `openrouter_report_429` | Activate fallback mode | instant |
| `openrouter_reset_fallback` | Return to cloud mode | instant |
| `openrouter_auto_fallback_status` | Check current mode | instant |

## Current Performance (2026-03-21)

| Model | Current | Target | Status |
|-------|---------|--------|--------|
| llama3.2:3b | ~4000ms (cold) | 500ms | ⚠️ Needs warmup |
| llama3.1:8b | ~9700ms (cold) | 1000ms | ⚠️ Needs warmup |
| claude-emulator | ~15000ms (cold) | 3000ms | ⚠️ Needs optimization |

**Note**: Cold start times are high. After warmup, latency drops significantly.

## Files

| File | Purpose |
|------|---------|
| `server.py` | Main MCP server with fallback functions (lines 670-850) |
| `autonomous_optimizer.py` | Self-improving daemon (brain-core SECRET) |
| `tests/test_fallback_system.py` | 24 unit tests |
| `tests/test_fallback_profiling.py` | pytest-benchmark profiling |
| `tests/PERFORMANCE_BASELINE.md` | SLA targets |

## CI Pipeline

**Workflow**: `.github/workflows/test-local-fallback.yml`

Tests:
1. Unit tests (no Ollama needed)
2. Integration tests with Ollama
3. Performance benchmarks
4. Threshold checks

## What Goes to agentic-brain (PUBLIC)

✅ **Include**:
- Fallback routing logic
- `quick_local` and `ask_local` functions
- Basic health checks
- CI tests for fallback

❌ **Exclude** (brain-core SECRET):
- `autonomous_optimizer.py` (time machine)
- Self-modifying code
- Aggressive M2 optimizations
- Learning/scheduling system

## Usage

### Automatic Fallback
```python
# When rate limited, system auto-switches
# Just use the tools normally - fallback is transparent
```

### Manual Control
```bash
# Check status
openrouter_auto_fallback_status

# Force local mode
openrouter_report_429

# Return to cloud
openrouter_reset_fallback
```

### Quick Local Query
```python
# Fast response from local LLM
openrouter_quick_local(prompt="What is 2+2?")
```

## TODO for agentic-brain Port

- [ ] Extract core fallback logic from server.py
- [ ] Create `agentic_brain/fallback/` module
- [ ] Add Ollama provider to router.py
- [ ] Create fallback configuration options
- [ ] Write tests without time machine dependency
- [ ] Document in agentic-brain README
- [ ] Add to CI pipeline

## Performance Optimization (brain-core only)

The autonomous optimizer daemon handles:
1. M2 Metal GPU acceleration
2. Model warmup and preloading
3. Quantized model selection
4. Context window tuning
5. Self-modifying improvements

This stays in brain-core. agentic-brain gets a simpler, stable version.

---

**Author**: user Webber + Iris Lumina  
**Created**: 2026-03-21  
**Philosophy**: "On-premise reliability - cloud optional"
