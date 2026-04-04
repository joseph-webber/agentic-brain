# BrainChat Benchmark Suite

Complete performance benchmarking system for BrainChat - tracks LLM providers, voice engines, speech-to-text, and UI responsiveness over time.

## Overview

The BrainChat benchmark suite provides comprehensive performance metrics for:

- **LLM Providers**: Ollama, Groq, OpenAI, Claude, Gemini
- **Voice Engines**: Apple, Cartesia, ElevenLabs, Piper
- **Speech-to-Text**: Apple, OpenAI Whisper, Deepgram, AssemblyAI
- **UI Performance**: View loading, scrolling, input latency, animations, memory

## Quick Start

### Run All Benchmarks

```swift
let runner = BenchmarkRunner.shared
let report = await runner.runAllBenchmarks()
```

### Run Specific Category

```swift
let report = await runner.runCategory(.llm)
let report = await runner.runCategory(.voice)
let report = await runner.runCategory(.stt)
let report = await runner.runCategory(.ui)
```

### Compare Against Baseline

```swift
let runner = BenchmarkRunner.shared
let report = await runner.runAllBenchmarks()
let comparison = await runner.compareWithBaseline(report)

if comparison?.hasRegressions ?? false {
    print("⚠️ Regressions detected!")
}
```

## Benchmark Metrics

### LLM Benchmarks

**Metrics:**
- `latencyMs` - Total request latency
- `ttftMs` - Time to First Token
- `throughput` - Tokens per second
- `provider` - LLM provider (Ollama, Groq, etc.)

**Key Tests:**
- Completion requests with different providers
- Streaming vs non-streaming performance
- Token count scaling (10-500 tokens)
- Concurrent requests

**Typical Results:**
- Ollama (local): 100-500ms
- Groq: 200-400ms (fastest)
- Claude: 1000-2000ms
- OpenAI: 800-1500ms

### Voice Engine Benchmarks

**Metrics:**
- `latencyMs` - Total synthesis time
- `ttftMs` - Time to First Audio (TTFA)
- `throughput` - Characters per second
- `accuracy` - Voice quality/naturalness (0-1)

**Key Tests:**
- Short/medium/long text synthesis
- Different voices per engine
- Concurrent synthesis
- Voice quality ratings
- Audio quality (sample rate, bitrate)

**Typical Results:**
- Apple TTS: 50-150ms (local, good quality)
- Cartesia: 150-350ms (streaming, natural)
- ElevenLabs: 300-600ms (network, very natural)
- Piper: 100-300ms (local, decent quality)

### Speech-to-Text Benchmarks

**Metrics:**
- `latencyMs` - Transcription latency
- `throughput` - Real-time factor (1.0 = real-time)
- `accuracy` - Transcription accuracy (WER)
- `ttftMs` - Time to first transcription result

**Key Tests:**
- Different audio lengths (3s, 15s, 60s)
- Real-time factor (RTF)
- Language detection
- Noise robustness
- Different speaker profiles

**Typical Results:**
- Apple: 100-400ms, 92-98% accuracy
- Whisper: 1000-6000ms, 90-96% accuracy
- Deepgram: 800-1500ms, 88-95% accuracy
- AssemblyAI: 1000-2500ms, 91-97% accuracy

### UI Performance Benchmarks

**Metrics:**
- `latencyMs` - Operation latency
- `throughput` - FPS or operations per second
- `accuracy` - Performance efficiency (0-1)

**Key Tests:**
- View load times (init, layout, render)
- Scroll performance (FPS at different list sizes)
- Input latency (text, buttons, sliders)
- Animation performance
- Memory usage by scenario
- CPU usage during different activities
- Network condition UI responsiveness
- Accessibility feature performance

**Performance Targets:**
- View load: < 200ms
- Scroll FPS: 60 fps constant
- Input latency: < 16.67ms (60 FPS)
- Memory baseline: < 100MB
- CPU idle: < 2%

## File Structure

```
Sources/BrainChat/Benchmarks/
├── BenchmarkModels.swift       # Core data structures
├── BenchmarkRunner.swift        # Main orchestrator
├── LLMBenchmarks.swift          # LLM provider tests
├── VoiceBenchmarks.swift        # TTS engine tests
├── STTBenchmarks.swift          # Speech-to-text tests
├── UIBenchmarks.swift           # UI performance tests
└── benchmarks/
    ├── baseline.json            # Baseline measurements
    ├── benchmark-report.json    # Latest report
    └── history/
        └── *.json               # Historical reports
```

## Output Examples

### Console Output

```
================================================================================
📊 BrainChat Benchmark Report
================================================================================
📅 Date: Jan 15, 2024 at 2:30 PM
⏱️  Duration: 45.23s
🔢 Total Tests: 150

📈 Summary Statistics:
  Average Latency: 325.41 ms
  Min Latency: 15.32 ms
  Max Latency: 2145.67 ms
  P50 Latency: 280.15 ms
  P95 Latency: 1200.45 ms
  P99 Latency: 1890.32 ms

📂 Results by Category:
  LLM Providers:
    Tests: 50
    Avg: 645.23 ms
    Range: 180.00-2145.67 ms
  
  Voice Engines:
    Tests: 40
    Avg: 185.45 ms
    Range: 50.00-600.00 ms
  
  Speech-to-Text:
    Tests: 40
    Avg: 1234.56 ms
    Range: 100.00-2500.00 ms
  
  UI Performance:
    Tests: 20
    Avg: 12.34 ms
    Range: 5.00-45.00 ms

🔌 Results by Provider:
  Ollama:
    Tests: 10
    Avg Latency: 250.45 ms
    Avg TTFT: 120.32 ms
    Avg Throughput: 45.67 tokens/sec
  
  Groq:
    Tests: 10
    Avg Latency: 300.23 ms
    Avg TTFT: 50.12 ms
    Avg Throughput: 150.45 tokens/sec
  
  Claude:
    Tests: 10
    Avg Latency: 1200.34 ms
    Avg TTFT: 500.23 ms
    Avg Throughput: 80.12 tokens/sec

⚡ Top 10 Fastest Tests:
  1. Chat View Load (UIKit): 8.23 ms
  2. Input Latency (button_tap): 5.67 ms
  3. Apple TTS (short) (Apple): 50.12 ms
  4. Scroll (50 items): 14.34 ms
  5. Input Latency (keyboard_input): 12.45 ms
  ...

🐢 Top 10 Slowest Tests:
  1. Claude Request (Claude): 2145.67 ms
  2. AssemblyAI (long audio): 2500.00 ms
  3. Whisper (small model): 2000.45 ms
  4. Multiple LLM Requests: 1890.23 ms
  5. Voice Recording Scenario: 800.00 ms
  ...

✅ Benchmark Complete!
📁 Results saved to: /Users/joe/brain/agentic-brain/apps/BrainChat/Sources/BrainChat/Benchmarks/benchmarks
================================================================================
```

### Comparison Report

```
================================================================================
📊 Benchmark Comparison Report
================================================================================
📅 Baseline: Jan 10, 2024 at 3:45 PM
📅 Current: Jan 15, 2024 at 2:30 PM

✅ No regressions detected!

📈 Overall Improvement: +8.45%

📊 Changes (Top 10):
  1. ↓ Groq Request (Groq): -5.32%
  2. ↓ Ollama Request (Ollama): -3.21%
  3. ↓ Apple TTS (Apple): -2.15%
  4. ↑ Scroll Performance (UIKit): +1.23%
  5. ↓ Claude Request (Claude): -1.45%
  ...

================================================================================
```

## JSON Report Format

```json
{
  "version": "1.0.0",
  "appVersion": "1.0.0",
  "platform": "macOS",
  "date": "2024-01-15T14:30:00Z",
  "duration": 45.23,
  "results": [
    {
      "id": "uuid",
      "category": "LLM Providers",
      "name": "Groq Request",
      "provider": "Groq",
      "latencyMs": 325.45,
      "throughput": 150.23,
      "ttftMs": 50.12,
      "accuracy": null,
      "timestamp": "2024-01-15T14:30:00Z",
      "metadata": {
        "model": "llama-3.1-70b",
        "tokens": "120"
      }
    }
  ],
  "summary": {
    "totalTests": 150,
    "passedTests": 150,
    "failedTests": 0,
    "avgLatencyMs": 325.41,
    "minLatencyMs": 15.32,
    "maxLatencyMs": 2145.67,
    "categoryStats": {},
    "providerStats": {}
  }
}
```

## Configuration

### BenchmarkConfig

```swift
BenchmarkConfig(
    warmupIterations: 3,           // Pre-test iterations
    testIterations: 10,            // Actual test runs per benchmark
    regressionThreshold: 10.0,     // 10% regression threshold
    timeoutSeconds: 60,            // Test timeout
    enableDetailedLogging: true    // Verbose output
)
```

### Custom Configuration

```swift
var config = BenchmarkConfig()
config.testIterations = 20         // More iterations for stability
config.regressionThreshold = 5.0   // Stricter threshold

let runner = BenchmarkRunner(config: config)
let report = await runner.runAllBenchmarks()
```

## Interpreting Results

### Key Metrics

1. **Latency (ms)**
   - Lower is better
   - Should be consistent (low variance)
   - Watch for regressions across releases

2. **TTFT/TTFA (ms)**
   - Time to first token/audio
   - Critical for user experience
   - Lower = more responsive

3. **Throughput (tokens/sec, chars/sec)**
   - Higher is better
   - Indicates streaming efficiency
   - Compare across similar configurations

4. **Accuracy (0-1)**
   - For STT: WER (Word Error Rate)
   - For Voice: Naturalness rating
   - Consistency important

5. **Percentiles (P50, P95, P99)**
   - P50: Median latency
   - P95: 95% of requests complete by this time
   - P99: 99% complete by this time
   - Watch P95/P99 for regressions

### Performance Targets

| Category | Metric | Target | Alert |
|----------|--------|--------|-------|
| LLM | Latency | < 500ms | > 1000ms |
| LLM | TTFT | < 150ms | > 300ms |
| Voice | TTFA | < 100ms | > 200ms |
| STT | Latency | < 1s/sec audio | > 5s/sec audio |
| UI | View Load | < 200ms | > 500ms |
| UI | Scroll FPS | 60 fps | < 45 fps |
| UI | Input Latency | < 16.67ms | > 33ms |

## Regression Detection

Regressions are flagged when:
- Test latency exceeds baseline by > threshold (default 10%)
- TTFT/TTFA increases significantly
- Accuracy drops
- Memory usage spikes

Example regression in report:
```
⚠️ REGRESSIONS DETECTED!

  ❌ Groq Request (Groq)
     Baseline: 300.45 ms
     Current: 360.54 ms
     Change: +20.00%
     Message: Exceeds 10% regression threshold
```

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Run BrainChat Benchmarks
  run: |
    swift run BrainChatBenchmarks \
      --all \
      --format json \
      --output results.json

- name: Compare Against Baseline
  run: |
    swift run BrainChatBenchmarks \
      --compare baseline.json \
      --output comparison.json

- name: Fail on Regressions
  if: failure()
  run: exit 1
```

## Advanced Usage

### Benchmark Specific Components

```swift
// Just LLM providers
let runner = BenchmarkRunner.shared
let report = await runner.runCategory(.llm)

// Just voice engines
let report = await runner.runCategory(.voice)
```

### Custom Benchmarks

```swift
let llmBench = LLMBenchmarks()
let results = await llmBench.benchmarkTokenCountScaling()

let voiceBench = VoiceBenchmarks()
let results = await voiceBench.benchmarkConcurrentSynthesis()

let uiBench = UIBenchmarks()
let results = await uiBench.benchmarkAccessibility()
```

### Export Results

```swift
let report = await runner.runAllBenchmarks()

// Automatically saved to:
// - /benchmarks/benchmark-report.json (latest)
// - /benchmarks/benchmark-2024-01-15T14-30-00.json (timestamped)
// - /benchmarks/history/2024-01-15T14-30-00.json (history)
```

## Troubleshooting

### No Results Generated

- Check provider connectivity (Groq, OpenAI, etc.)
- Verify local services running (Ollama)
- Check timeout configuration

### High Variance in Results

- Increase `warmupIterations`
- Run fewer benchmarks at once
- Check system load
- Disable background processes

### Memory Issues

- Reduce `testIterations`
- Break benchmarks into categories
- Run UI benchmarks separately

### Network Timeouts

- Increase `timeoutSeconds`
- Check network connectivity
- Verify API keys
- Check rate limits

## Maintenance

### Regular Tasks

- Run benchmarks before/after major changes
- Update baseline after optimization
- Review history trends monthly
- Archive old reports

### Updating Benchmarks

When adding new providers/engines:
1. Add to corresponding Benchmarks class
2. Update BenchmarkConfig.Category if needed
3. Add tests to runBenchmarks()
4. Document expected performance

### Performance Optimization

Based on benchmark results, optimize:
1. High-latency operations
2. High-variance results
3. Memory-intensive features
4. UI responsiveness issues

## References

- [Benchmark Models](BenchmarkModels.swift)
- [Benchmark Runner](BenchmarkRunner.swift)
- [LLM Benchmarks](LLMBenchmarks.swift)
- [Voice Benchmarks](VoiceBenchmarks.swift)
- [STT Benchmarks](STTBenchmarks.swift)
- [UI Benchmarks](UIBenchmarks.swift)

## Support

For questions or issues with benchmarking:
1. Check this documentation
2. Review example benchmark runs
3. Check historical trends
4. Contact performance team
