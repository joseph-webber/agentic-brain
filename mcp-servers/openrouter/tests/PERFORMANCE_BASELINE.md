# 📊 Local LLM Fallback System - Performance Baseline

> **Purpose**: This document establishes performance baselines for the Local LLM Fallback System.
> These baselines are used by CI to detect performance regressions.

---

## 🖥️ Baseline Hardware Specification

| Component | Specification |
|-----------|---------------|
| **Machine** | MacBook Pro (2022/2023) |
| **Chip** | Apple M2 Pro / M2 Max |
| **RAM** | 16GB - 32GB Unified Memory |
| **Storage** | 512GB+ SSD |
| **OS** | macOS Sonoma 14.x+ |

> **Note**: CI runs on GitHub Actions (Linux), which may have different performance characteristics.
> CI thresholds are set more conservatively to account for this.

---

## 📈 Model Performance Baselines

### llama3.2:3b (Quick Model)

| Metric | M2 Mac Baseline | CI Threshold | Notes |
|--------|-----------------|--------------|-------|
| **Cold Start** | 5-10s | 30s | First query after model load |
| **Warm Response** | 2-5s | 15s | Subsequent queries |
| **Memory Usage** | 2-4GB | 6GB | Peak during inference |
| **Throughput** | 10-15 req/min | 5 req/min | Sequential queries |

**Use Case**: Fast responses, simple tasks, real-time fallback

### llama3.1:8b (Quality Model)

| Metric | M2 Mac Baseline | CI Threshold | Notes |
|--------|-----------------|--------------|-------|
| **Cold Start** | 15-30s | 60s | First query after model load |
| **Warm Response** | 5-15s | 45s | Subsequent queries |
| **Memory Usage** | 4-8GB | 12GB | Peak during inference |
| **Throughput** | 4-8 req/min | 2 req/min | Sequential queries |

**Use Case**: Complex reasoning, code analysis, detailed responses

### claude-emulator (Brain-Aware Model)

| Metric | M2 Mac Baseline | CI Threshold | Notes |
|--------|-----------------|--------------|-------|
| **Cold Start** | 30-60s | 120s | First query after model load |
| **Warm Response** | 15-45s | 120s | Subsequent queries |
| **Memory Usage** | 6-10GB | 16GB | Peak during inference |
| **Throughput** | 2-4 req/min | 1 req/min | Sequential queries |

**Use Case**: Brain context-aware responses, user assistant mode

---

## 🚦 CI Performance Thresholds

These thresholds trigger CI failures when exceeded:

```yaml
thresholds:
  llama3.2:3b:
    max_latency_seconds: 30
    max_memory_gb: 6
    min_success_rate: 0.8
  
  llama3.1:8b:
    max_latency_seconds: 60
    max_memory_gb: 12
    min_success_rate: 0.7
  
  claude-emulator:
    max_latency_seconds: 180
    max_memory_gb: 16
    min_success_rate: 0.6
```

---

## 📊 Benchmark Test Prompts

These standardized prompts are used for consistent benchmarking:

### Simple (Latency Test)
```
Reply with just: OK
```
**Expected**: 1-5 word response, measures raw latency

### Medium (Typical Use)
```
What is Python? One sentence.
```
**Expected**: 10-30 word response, measures typical task

### Complex (Stress Test)
```
Explain the difference between a list and a tuple in Python. Be brief.
```
**Expected**: 50-100 word response, measures complex reasoning

---

## 📈 Performance History

### Recent Measurements (Update after each release)

| Date | Model | Avg Latency | Notes |
|------|-------|-------------|-------|
| 2026-03-21 | llama3.2:3b | 3.2s | M2 Mac baseline |
| 2026-03-21 | llama3.1:8b | 12.5s | M2 Mac baseline |
| 2026-03-21 | claude-emulator | 35.0s | M2 Mac baseline |

---

## 🔧 Performance Tuning Tips

### For Better Latency:
1. Keep models loaded (avoid cold starts)
2. Use llama3.2:3b for real-time responses
3. Increase Ollama memory allocation
4. Use SSD for model storage

### For Better Throughput:
1. Enable Ollama GPU acceleration
2. Use smaller models for high-volume tasks
3. Implement request queuing
4. Consider model sharding for large models

### For Lower Memory:
1. Use quantized models (Q4_K_M)
2. Unload unused models
3. Set `OLLAMA_NUM_PARALLEL=1`
4. Monitor with `ollama ps`

---

## 🎯 SLA Targets for Enterprise Demo

For enterprise client demonstrations, commit to these SLAs:

| Model | Response Time SLA | Availability |
|-------|-------------------|--------------|
| Quick (3B) | < 15 seconds | 99.9% |
| Quality (8B) | < 45 seconds | 99.5% |
| Brain-Aware | < 2 minutes | 99.0% |

> **Fallback Guarantee**: When Claude/Copilot is rate limited, users will receive
> a response from local LLM within the above timeframes, ensuring zero productivity loss.

---

## 📝 Updating This Baseline

When to update:
- New model versions released
- Hardware changes
- Significant performance improvements
- After major code changes

How to update:
1. Run full benchmark suite on reference hardware
2. Calculate new averages from 10+ runs
3. Update tables above
4. Commit with message: "📊 Update performance baseline YYYY-MM-DD"

---

## 🔗 Related Files

- `test_fallback_profiling.py` - Benchmark test suite
- `test_fallback_system.py` - Integration tests
- `test_local_llm.py` - Unit tests
- `.github/workflows/test-local-fallback.yml` - CI pipeline

---

*Last Updated: 2026-03-21*
*Baseline Hardware: M2 MacBook Pro*
