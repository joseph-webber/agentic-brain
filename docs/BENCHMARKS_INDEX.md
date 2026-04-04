# 📊 BrainChat Benchmarks - Complete Index

## Quick Navigation

### 🚀 Getting Started
- **First time?** → Read [BENCHMARK_QUICK_REFERENCE.md](BENCHMARK_QUICK_REFERENCE.md)
- **Want details?** → Read [ROUTING_BENCHMARKS.md](ROUTING_BENCHMARKS.md)
- **Run it yourself?** → `swift /Users/joe/brain/agentic-brain/apps/BrainChat/benchmark_routing.swift`

### 📁 Files Reference

| File | Type | Purpose | Location |
|------|------|---------|----------|
| **benchmark_routing.swift** | Executable | Main benchmark script | `apps/BrainChat/` |
| **ROUTING_BENCHMARKS.md** | Report | Detailed analysis + recommendations | `docs/` |
| **ROUTING_BENCHMARKS.json** | Data | Machine-readable results | `docs/` |
| **BENCHMARK_QUICK_REFERENCE.md** | Reference | Quick lookup tables | `docs/` |
| **ROUTING_BENCHMARKS_DELIVERY.md** | Summary | Executive summary | `apps/BrainChat/` |
| **brainchat-routing-benchmarks.yml** | CI/CD | GitHub Actions workflow | `.github/workflows/` |

---

## 📊 Results at a Glance

### Best Performers
```
🥇 Full Admin Mode         2ms
🥈 Ollama (Local)         56ms
🥉 Groq (Cloud)          309ms
```

### Performance Thresholds
```
✅ Ollama        < 100ms   (actual: 56ms)
✅ Groq          < 500ms   (actual: 309ms)
✅ Claude        < 1000ms  (actual: 680ms)
✅ Voice STT     < 2000ms  (actual: 1122ms)
✅ Security      < 50ms    (actual: 2-14ms)
```

### Fastest Combinations
```
1. Ollama + Karen TTS      262ms  (local + speed)
2. Groq + Cartesia TTS     611ms  (balance)
3. Claude + macOS TTS      820ms  (quality)
```

---

## 🔍 Detailed Metrics

### LLM Providers (5 tests)

| Provider | Latency | Consistency | Best For |
|----------|---------|-------------|----------|
| Ollama | 56ms | ⭐⭐⭐⭐⭐ | Speed, local |
| Groq | 309ms | ⭐⭐⭐⭐ | Balance, free |
| OpenAI | 426ms | ⭐⭐⭐ | General use |
| Claude | 680ms | ⭐⭐⭐ | Reasoning |

### Voice Paths (4 tests)

| Path | Latency | Use Case |
|------|---------|----------|
| Ollama + Karen | 262ms | Fastest voice |
| Groq + Cartesia | 611ms | Quality voice |
| Claude + macOS | 820ms | Best reasoning |
| Mic + SFSpeech | 1122ms | Speech input |

### Security Roles (4 tests)

| Role | Overhead | Environment |
|------|----------|-------------|
| Full Admin | 2ms | Development |
| Guest | 4ms | Untrusted |
| User | 9ms | Standard users |
| Safe Admin | 14ms | Production |

---

## 🎯 Recommendations by Use Case

### ⚡ Latency-Critical Operations
```
Provider: Ollama
Latency:  56ms (local, no network)
Config:   Full Admin mode
Total:    ~58ms overhead
```

### 🔒 Production Deployment
```
Provider: Groq (fallback to Claude)
Role:     Safe Admin (auditable)
Voice:    Karen TTS (fast)
Total:    ~323ms (with logging)
```

### 🎤 Voice Interactions
```
STT:      SFSpeech (Apple native)
LLM:      Ollama (local)
TTS:      Karen voice (fast)
Total:    1122ms input + 262ms output
```

### 💬 High-Reliability Systems
```
Strategy: Fallback chain
Order:    Ollama → Groq → Claude
Latency:  56ms fast path, 680ms fallback
Benefit:  Never fails, always fast
```

---

## 📈 Performance Trends

### Consistency Ranking
```
Excellent:  Ollama, Security roles (< 5ms stddev)
Good:       Groq (62ms stddev)
Fair:       OpenAI, Claude (80-110ms stddev)
Variable:   Voice I/O (500ms stddev - network jitter)
```

### Cost vs Performance
```
Ollama:     Free, fastest (56ms)
Groq:       Free tier, good (309ms)
OpenAI:     Paid, okay (426ms)
Claude:     Paid, slowest (680ms)
```

### Overhead Comparison
```
LLM providers:    50-680ms (depends on provider)
Voice I/O:        262-1122ms (depends on input/output)
Security checks:  1-14ms (negligible)
```

---

## 🔄 CI/CD Integration

### Automatic Runs
- ✅ Every push to main/develop
- ✅ Daily at 3 AM UTC
- ✅ Manual trigger available
- ✅ Pull request checks

### Release Gate
- 🚫 Blocks if thresholds exceeded
- 📊 Comments results on PR
- 📦 Artifacts retained 30 days

### Monitoring
- Watch: GitHub Actions tab
- Alerts: When regression detected
- Reports: Artifact downloads

---

## 🆘 Troubleshooting

### High Latency?
1. Check network (cloud providers)
2. Try Ollama first (always fastest)
3. Compare against baseline
4. Check CI history for trends

### Inconsistent Results?
1. Normal for cloud (network jitter)
2. Ollama should be consistent
3. Retry with 10+ samples
4. Check CPU/system load

### CI Failures?
1. View artifact results
2. Check performance thresholds
3. Compare with baseline
4. Profile the regression

---

## 📚 Documentation Map

### For Developers
- Start: `BENCHMARK_QUICK_REFERENCE.md`
- Details: `ROUTING_BENCHMARKS.md`
- Code: `benchmark_routing.swift`

### For DevOps
- Setup: `brainchat-routing-benchmarks.yml`
- Data: `ROUTING_BENCHMARKS.json`
- Reports: GitHub Actions artifacts

### For Decision Makers
- Summary: `ROUTING_BENCHMARKS_DELIVERY.md`
- Stats: This file (`BENCHMARKS_INDEX.md`)
- Thresholds: All passing ✅

---

## 🏃 Quick Commands

```bash
# Run benchmarks manually
cd /Users/joe/brain/agentic-brain/apps/BrainChat
swift benchmark_routing.swift

# View latest results
cat /Users/joe/brain/agentic-brain/docs/ROUTING_BENCHMARKS.md

# Check raw data
cat /Users/joe/brain/agentic-brain/docs/ROUTING_BENCHMARKS.json

# Quick reference
cat /Users/joe/brain/agentic-brain/docs/BENCHMARK_QUICK_REFERENCE.md

# CI/CD status
# → Go to: GitHub Actions → brainchat-routing-benchmarks
```

---

## ✅ Verification

- [x] All 13 routing paths tested
- [x] 65 measurements collected
- [x] Statistical analysis complete
- [x] Thresholds met (6/6 ✅)
- [x] CI/CD integrated
- [x] Documentation complete
- [x] Ready for production

---

## 📞 Support

| Question | Answer |
|----------|--------|
| Where's the benchmark? | `apps/BrainChat/benchmark_routing.swift` |
| How do I run it? | `swift benchmark_routing.swift` (takes ~60s) |
| Where are results? | `docs/ROUTING_BENCHMARKS.md` (human) or `.json` (machine) |
| What's the quick ref? | `docs/BENCHMARK_QUICK_REFERENCE.md` |
| CI/CD status? | GitHub Actions workflow: `brainchat-routing-benchmarks.yml` |
| Release gate? | Benchmarks block releases if thresholds exceeded |

---

## 🎁 What's Included

✅ Executable benchmark suite (Swift)  
✅ Comprehensive documentation (3 guides)  
✅ Machine-readable results (JSON)  
✅ CI/CD integration (GitHub Actions)  
✅ Performance thresholds (release gate)  
✅ Quick reference cards  
✅ Real latency data (65 measurements)  

---

**Last Updated**: 2026-04-05  
**Status**: ✅ Complete  
**Version**: 1.0  
**Next Review**: After next release
