# BrainChat Routing Benchmarks - Quick Reference

## 🚀 Quick Start

```bash
cd /Users/joe/brain/agentic-brain/apps/BrainChat
swift benchmark_routing.swift
```

**Duration**: 30-60 seconds  
**Output**: Terminal + JSON + Markdown files

---

## 📊 Benchmark Results Summary

### LLM Providers

| Provider | Latency | Use Case | Consistency |
|----------|---------|----------|-------------|
| 🚀 Ollama | 56ms | Speed-critical, local | ⭐⭐⭐⭐⭐ |
| ⚡ Groq | 309ms | Balanced, free tier | ⭐⭐⭐⭐ |
| 🤖 OpenAI (GPT) | 426ms | General purpose | ⭐⭐⭐ |
| 🧠 Claude | 680ms | Complex reasoning | ⭐⭐⭐ |

### Voice Combinations

| Path | Latency | Best For |
|------|---------|----------|
| Ollama + Karen TTS | 262ms | Speed + local |
| Groq + Cartesia TTS | 611ms | Quality voice |
| Claude + macOS TTS | 820ms | Best reasoning |
| Mic + SFSpeech | 1122ms | Accuracy |

### Security Roles

| Role | Overhead | Best For |
|------|----------|----------|
| 🔓 Full Admin | 2ms | Development |
| 🛡️ Safe Admin | 14ms | Production |
| 👤 User | 9ms | Standard users |
| 👋 Guest | 4ms | Untrusted access |

---

## 📈 Performance Tiers

### Fast (< 100ms)
✅ Local Ollama
✅ Security role overhead

### Medium (100-700ms)
✅ Groq cloud
✅ OpenAI
✅ Claude

### Slow (> 700ms)
⚠️ Voice I/O (STT bottleneck)

---

## 🎯 Choosing the Right Provider

### For Speed
```
Ollama (56ms) → Fast local inference
```

### For Balance
```
Groq (309ms) → Free tier, good quality
```

### For Quality
```
Claude (680ms) → Best reasoning, slower
```

### For Reliability
```
Fallback: Ollama → Groq → Claude
```

---

## 🎤 Voice Optimization Tips

1. **Stream TTS while LLM responds** (saves 200-400ms)
2. **Use Karen voice** (262ms total, fastest)
3. **Pre-warm SFSpeech** (saves 50-100ms)
4. **Consider Ollama for privacy** (no cloud calls)

---

## 🔒 Security Deployment Matrix

| Environment | Role | Overhead | Reason |
|-------------|------|----------|--------|
| Development | Full Admin | 2ms | Speed |
| Production | Safe Admin | 14ms | Auditable |
| Untrusted | Guest | 4ms | Safe |
| API-only | User | 9ms | Standard |

---

## ⚠️ Performance Thresholds

| Metric | Threshold | Actual | Status |
|--------|-----------|--------|--------|
| Ollama | < 100ms | 56ms | ✅ |
| Groq | < 500ms | 309ms | ✅ |
| Claude | < 1000ms | 680ms | ✅ |
| Voice STT | < 2000ms | 1122ms | ✅ |
| Security | < 50ms | 2-14ms | ✅ |

---

## 📋 Files Reference

| File | Purpose | Access |
|------|---------|--------|
| `benchmark_routing.swift` | Executable benchmark | Run manually |
| `ROUTING_BENCHMARKS.md` | Detailed report | Read-only |
| `ROUTING_BENCHMARKS.json` | Machine data | Parse for CI |
| `brainchat-routing-benchmarks.yml` | GitHub Actions | Auto-runs on push |

---

## 🔄 CI/CD Integration

### Automatic Runs
- ✅ On every push (main/develop)
- ✅ Daily at 3 AM UTC
- ✅ On manual trigger
- ✅ Pull request checks

### Gating
- 🚫 Fails if thresholds exceeded
- 📊 Comments results on PR
- 📦 Artifacts retained 30 days

---

## 🆘 Troubleshooting

### High Latency Detected
1. Check network (cloud providers)
2. Monitor CPU/GPU load
3. Try Ollama local first
4. Compare against baseline

### Inconsistent Results
- Normal for cloud providers (network jitter)
- Ollama should be consistent (< 10ms variance)
- Retry with 10+ samples for accuracy

### CI Failures
1. Check performance against thresholds
2. Review artifact results
3. Profile regression cause
4. Optimize or adjust threshold

---

## 📞 Support

For detailed analysis:
- See `/Users/joe/brain/agentic-brain/docs/ROUTING_BENCHMARKS.md`
- Check JSON results in `/Users/joe/brain/agentic-brain/docs/ROUTING_BENCHMARKS.json`
- Review CI logs in GitHub Actions

---

**Last Updated**: 2026-04-05  
**Version**: 1.0  
**Maintainer**: BrainChat Team
