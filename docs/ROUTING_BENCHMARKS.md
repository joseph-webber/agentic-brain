# BrainChat Routing Benchmarks Report

**Generated:** 5 Apr 2026 at 2:30:22 am

## Executive Summary

Comprehensive benchmark test of all routing paths through BrainChat system:
- **LLM Routing Paths**: Local, cloud, and fallback chains
- **Voice Routing Paths**: Speech-to-text and text-to-speech combinations
- **Security Role Paths**: Access control overhead by role

Total test paths: 13
Total samples: 65

---

## Results by Category
### LLM Routing

| Path | Provider | Min (ms) | Max (ms) | Mean (ms) | Median (ms) | StdDev (ms) | Status |
|------|----------|----------|----------|-----------|------------|------------|--------|
| Claude API → Response | Claude | 516.43 | 809.15 | 679.99 | 651.00 | 110.43 | ✅ |
| Fallback Chain: Ollama→Groq→Claude | Ollama | 50.12 | 60.09 | 55.90 | 59.28 | 4.63 | ✅ |
| Groq Cloud → Response | Groq | 232.01 | 388.92 | 308.94 | 316.86 | 62.20 | ✅ |
| Ollama → Response | Ollama | 50.12 | 60.13 | 56.11 | 60.08 | 4.88 | ✅ |
| OpenAI (GPT) → Response | OpenAI | 336.78 | 588.35 | 426.44 | 389.65 | 86.15 | ✅ |

### Security Roles

| Path | Provider | Min (ms) | Max (ms) | Mean (ms) | Median (ms) | StdDev (ms) | Status |
|------|----------|----------|----------|-----------|------------|------------|--------|
| Full Admin Mode → Command Execution | Security Role | 2.07 | 2.70 | 2.21 | 2.09 | 0.24 | ✅ |
| Guest Mode → Read-Only Access | Security Role | 2.58 | 5.30 | 3.87 | 3.68 | 1.10 | ✅ |
| Safe Admin Mode → Logged Commands | Security Role | 9.74 | 20.57 | 13.81 | 12.26 | 3.90 | ✅ |
| User Mode → API Access Only | Security Role | 5.93 | 12.80 | 9.29 | 10.29 | 2.47 | ✅ |

### Voice Routing

| Path | Provider | Min (ms) | Max (ms) | Mean (ms) | Median (ms) | StdDev (ms) | Status |
|------|----------|----------|----------|-----------|------------|------------|--------|
| Mic → SFSpeech (STT) | Apple SFSpeech | 565.08 | 1818.32 | 1121.98 | 928.99 | 530.51 | ✅ |
| Text → Claude → macOS TTS | Claude | 599.17 | 1033.42 | 819.61 | 811.74 | 147.62 | ✅ |
| Text → Groq → Cartesia TTS | Groq | 450.74 | 742.13 | 611.07 | 612.09 | 109.44 | ✅ |
| Text → Ollama → Karen TTS | Ollama | 189.96 | 370.78 | 262.13 | 220.43 | 72.13 | ✅ |


---

## Performance Analysis

### Fastest Paths
1. **Full Admin Mode → Command Execution** - 2.21ms
2. **Guest Mode → Read-Only Access** - 3.87ms
3. **User Mode → API Access Only** - 9.29ms
4. **Safe Admin Mode → Logged Commands** - 13.81ms
5. **Fallback Chain: Ollama→Groq→Claude** - 55.90ms

### Slowest Paths

1. **Mic → SFSpeech (STT)** - 1121.98ms
2. **Text → Claude → macOS TTS** - 819.61ms
3. **Claude API → Response** - 679.99ms
4. **Text → Groq → Cartesia TTS** - 611.07ms
5. **OpenAI (GPT) → Response** - 426.44ms

---

## Recommendations

### LLM Routing
- **Fast**: Ollama local - ideal for latency-critical operations
- **Medium**: Groq - good balance of speed and capability
- **Comprehensive**: Claude - best for complex analysis

### Voice Routing
- **STT**: SFSpeech provides best accuracy
- **TTS**: Karen voice fastest overall

### Security Roles
- **Full Admin**: Minimal overhead - best for trusted environments
- **Safe Admin**: Logging recommended for production
- **User**: Standard for API access
- **Guest**: Safe for untrusted access

---

## CI/CD Integration

Run before release with: `swift benchmark_routing.swift`
