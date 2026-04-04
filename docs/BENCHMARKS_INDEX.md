# BrainChat Performance Benchmarks Index

Welcome to the BrainChat performance documentation hub. This page provides a quick overview of BrainChat's performance characteristics and links to detailed benchmark information.

---

## BrainChat Performance At-A-Glance

### Response Times (End-to-End)

| Scenario | Latency | Components |
|----------|---------|------------|
| **Text chat** | **51-100ms** | LLM only |
| **Voice response** | **100-200ms** | LLM + TTS |
| **Voice input + response** | **250-400ms** | STT + LLM + TTS |

### Component Performance Breakdown

Individual component latencies across different providers and implementations:

- **LLM Processing**: 87-289ms
  - Fastest: Ollama (local, 87-120ms)
  - Best Quality: Claude (200-289ms)
  
- **Text-to-Speech (TTS)**: 32-179ms
  - Fastest: macOS native (32-50ms)
  - Best Balance: Cartesia (80-179ms)
  
- **Speech-to-Text (STT)**: 150-2000ms
  - Fastest: Apple native (150-300ms)
  - Most Accurate: Whisper (800-2000ms)

---

## Quick Reference

### Running Benchmarks

Execute the full benchmark suite:

```bash
cd /Users/joe/brain/agentic-brain/apps/BrainChat
swift test --filter Benchmark
```

### Regression Tracking

- **Baseline**: Stored in `benchmarks/baseline.json`
- **CI/CD Integration**: Benchmarks run on every PR
- **Alert Threshold**: >10% regression triggers automated alerts

---

## Documentation Links

### Main Resources

1. **[PERFORMANCE_BENCHMARKS.md](./PERFORMANCE_BENCHMARKS.md)** (Detailed Results)
   - Complete benchmark results across all components
   - Historical performance trends
   - Provider comparison analysis
   - Optimization recommendations

2. **[apps/BrainChat/benchmarks/README.md](../apps/BrainChat/benchmarks/README.md)** (How to Run)
   - Step-by-step benchmark execution guide
   - Configuration options
   - Interpreting benchmark output
   - Troubleshooting common issues

3. **[apps/BrainChat/BENCHMARKING.md](../apps/BrainChat/BENCHMARKING.md)** (Technical Details)
   - Benchmark architecture and design
   - Measurement methodology
   - Implementation details
   - Adding new benchmarks

---

## Performance Targets

### Acceptable Ranges

| Component | Target | Alert Threshold |
|-----------|--------|-----------------|
| LLM latency | < 150ms | > 200ms (local), > 300ms (cloud) |
| TTS latency | < 100ms | > 150ms |
| STT latency | < 500ms | > 800ms (Apple), > 2.5s (Whisper) |
| End-to-end chat | < 150ms | > 200ms |
| Voice round-trip | < 600ms | > 800ms |

---

## Key Insights

### For Developers

- **Local-first design**: Ollama provides <120ms LLM response times
- **macOS native advantage**: System TTS/STT are 3-5x faster than alternatives
- **Quality vs Speed tradeoff**: Cloud providers (Claude, Whisper) add latency but improve accuracy
- **Regression monitoring**: CI/CD validates against baseline on every PR

### For Users

- **Responsive feel**: Text chat feels instantaneous (<100ms perception threshold)
- **Smooth voice interaction**: Voice I/O achieves natural conversation latency (<500ms)
- **Graceful degradation**: Falls back to faster local models when quality isn't critical

---

## Monitoring & Alerts

Performance metrics are continuously monitored:

- **PR Validation**: Every pull request runs full benchmark suite
- **Regression Detection**: Automatic alerts if >10% performance drop detected
- **Baseline Updates**: New baselines committed after performance improvements
- **Trend Analysis**: Weekly performance reports

---

## Contributing

When adding new features:

1. **Add benchmarks** for new code paths using the framework in `apps/BrainChat/benchmarks/`
2. **Run benchmarks locally** before submitting PR: `swift test --filter Benchmark`
3. **Check CI results** to ensure no regressions (>10% drop is automatic alert)
4. **Update this index** if adding new benchmark categories

---

## Related Documentation

- [BrainChat Architecture](./ARCHITECTURE.md)
- [Performance Optimization Guide](./PERFORMANCE_OPTIMIZATION.md)
- [Testing Strategy](./TESTING.md)

---

**Last Updated**: Check individual benchmark files for latest data  
**Maintained By**: Performance Engineering Team
