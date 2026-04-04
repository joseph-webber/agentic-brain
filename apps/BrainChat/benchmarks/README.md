# BrainChat LLM Performance Benchmark Suite

This directory contains comprehensive benchmarking tools for measuring the performance of all LLM providers integrated into BrainChat.

## Overview

The benchmark suite measures:
- **TTFT (Time to First Token)** - Latency until first response arrives (milliseconds)
- **Total Response Time** - Complete response duration (milliseconds)
- **Throughput** - Tokens per second generation rate
- **Reliability** - Success/failure rates
- **Target Compliance** - Whether each provider meets latency targets

## Providers Benchmarked

| Provider | Type | Target TTFT | Model |
|----------|------|------------|--------|
| **Ollama** | Local | <100ms | llama3.2:3b |
| **Groq** | Cloud Fast | <150ms | llama-3.1-8b-instant |
| **OpenAI** | Cloud | <300ms | gpt-4o |
| **Claude** | Cloud | <300ms | claude-sonnet-4-20250514 |

## Files

### Core Benchmark Infrastructure
- **BenchmarkResults.swift** - Data structures and runner for benchmarks
  - `LLMBenchmarkResult` - Individual benchmark result
  - `BenchmarkResultsCollection` - Results collection with analysis
  - `LLMBenchmarkRunner` - Main benchmark executor

### Test Files
- **Tests/LLMBenchmarkTests.swift** - XCTest-based benchmark tests
  - Individual provider tests
  - Concurrent request testing
  - Stress testing
  - Comparison tests

### Scripts
- **run-benchmarks.sh** - Bash runner for benchmarks
- **run-benchmarks.swift** - Standalone Swift runner

### Results
- **llm-baseline.json** - Current baseline results
- **llm-benchmark-*.json** - Historical timestamped results

## Setup

### Prerequisites
1. Xcode 15+ or Swift 5.9+
2. Ollama (for local testing): `brew install ollama`
3. API keys for cloud providers

### Environment Configuration

Set the following environment variables:

```bash
# Local (Ollama)
export OLLAMA_ENDPOINT="http://localhost:11434/api/chat"

# Cloud Providers
export GROQ_API_KEY="your-groq-api-key"
export CLAUDE_API_KEY="your-claude-api-key"
export OPENAI_API_KEY="your-openai-api-key"
export GEMINI_API_KEY="your-gemini-api-key"
```

Or configure in `../local-config.json`:
```json
{
  "ollama_endpoint": "http://localhost:11434/api/chat",
  "groq_key": "your-key",
  "claude_key": "your-key",
  "openai_key": "your-key",
  "gemini_key": "your-key"
}
```

## Running Benchmarks

### Option 1: Using XCTest (Recommended)
```bash
cd /Users/joe/brain/agentic-brain/apps/BrainChat
swift test --configuration release --parallel 1
```

### Option 2: Using Bash Script
```bash
cd /Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks
chmod +x run-benchmarks.sh
./run-benchmarks.sh
```

### Option 3: Direct Swift Execution
```bash
cd /Users/joe/brain/agentic-brain/apps/BrainChat
swift benchmarks/run-benchmarks.swift
```

## Individual Tests

### Benchmark Single Provider
```bash
swift test --configuration release LLMBenchmarkTests/testBenchmarkOllama
swift test --configuration release LLMBenchmarkTests/testBenchmarkGroq
swift test --configuration release LLMBenchmarkTests/testBenchmarkClaude
swift test --configuration release LLMBenchmarkTests/testBenchmarkOpenAI
```

### Run All Providers
```bash
swift test --configuration release LLMBenchmarkTests/testBenchmarkAllProviders
```

### Stress Testing
```bash
swift test --configuration release LLMBenchmarkTests/testStressTestSequential
```

### Compare Latencies
```bash
swift test --configuration release LLMBenchmarkTests/testCompareProviderLatencies
```

## Understanding Results

### Benchmark Output Example
```
═══════════════════════════════════════════════════════════
LLM PERFORMANCE BENCHMARK RESULTS
═══════════════════════════════════════════════════════════
Run Time: 2025-04-04T14:30:00Z
Results: 4/4 successful
Target Met: 75.0%

SUMMARY STATISTICS
─────────────────────────────────────────────────────────────
Average TTFT: 145.23ms
Average Throughput: 45.67tok/s
Fastest: Ollama (llama3.2:3b) (87.45ms)
Slowest: Claude (claude-sonnet-4-20250514) (289.12ms)
Best Throughput: Groq (llama-3.1-8b-instant) (68.90tok/s)

DETAILED RESULTS
─────────────────────────────────────────────────────────────

[✓] Ollama (llama3.2:3b)
  TTFT: 87.45ms / 100ms target [TARGET MET]
  Total: 1245.67ms
  Throughput: 32.14tok/s (40 tokens)
  Bytes: 856

[✓] Groq (llama-3.1-8b-instant)
  TTFT: 134.56ms / 150ms target [TARGET MET]
  Total: 756.23ms
  Throughput: 68.90tok/s (52 tokens)
  Bytes: 912

[✓] OpenAI (gpt-4o)
  TTFT: 234.12ms / 300ms target [TARGET MET]
  Total: 1567.89ms
  Throughput: 38.45tok/s (60 tokens)
  Bytes: 1024

[✓] Claude (claude-sonnet-4-20250514)
  TTFT: 289.12ms / 300ms target [TARGET MET]
  Total: 2134.56ms
  Throughput: 31.23tok/s (66 tokens)
  Bytes: 1152

═══════════════════════════════════════════════════════════
```

### Metrics Explained

| Metric | Unit | Meaning |
|--------|------|---------|
| TTFT | ms | Time until first token appears (key for responsiveness) |
| Total Response Time | ms | Complete response duration |
| Throughput | tok/s | Generation speed (higher = faster) |
| Target Met | % | Percentage of providers meeting latency goals |
| Tokens | count | Number of tokens in response |

## Interpreting Target Latencies

- **✓ TARGET MET**: Provider met its latency goal
  - Ollama: <100ms
  - Groq: <150ms
  - Cloud: <300ms

- **✗ TARGET MISS**: Provider exceeded its goal
  - May indicate network issues
  - May indicate server load
  - May indicate model complexity

## Performance Expectations

### Typical TTFT Values (Healthy System)

```
Local (Ollama):     50-150ms   (varies by CPU/RAM)
Groq:              100-200ms   (cloud CDN)
OpenAI:            200-400ms   (API latency)
Claude:            200-400ms   (API latency)
```

### Performance Factors

1. **Network Latency**
   - Ollama: None (local)
   - Cloud: 50-200ms round-trip

2. **Model Size**
   - Smaller models: Faster TTFT
   - Larger models: Better quality but slower

3. **Server Load**
   - High load increases latency
   - Queue time affects TTFT
   - Retry mechanisms may add delays

4. **System Resources**
   - Ollama depends on local CPU/GPU
   - RAM affects model loading
   - Disk I/O for model weights

## Continuous Monitoring

### Historical Tracking
Results are timestamped and saved to:
- `llm-baseline.json` - Latest baseline
- `llm-benchmark-YYYY-MM-DDTHH-MM-SS.json` - Historical records

### Analyzing Trends
```bash
# Compare baseline vs latest
diff llm-baseline.json llm-benchmark-*.json | tail -50

# Extract TTFT from all benchmarks
grep -h "ttft_ms" llm-benchmark-*.json | sort
```

### Creating Performance Reports
```swift
let runner = LLMBenchmarkRunner(configuration: config)
let latest = try runner.loadResults(from: "llm-baseline.json")
print(latest.generateSummary())
```

## Troubleshooting

### Ollama Benchmark Fails
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve

# Ensure model is installed
ollama list
ollama pull llama3.2:3b
```

### Cloud Provider Tests Skip
```bash
# Verify API key is set
echo $GROQ_API_KEY
echo $CLAUDE_API_KEY
echo $OPENAI_API_KEY

# Test API connectivity
curl -H "Authorization: Bearer $GROQ_API_KEY" \
  https://api.groq.com/openai/v1/models
```

### Tests Timeout
- Increase timeout: Add `BENCHMARK_TIMEOUT=300` env var
- Use wired network instead of WiFi
- Check API rate limits
- Run one provider at a time with `--parallel 1`

## Performance Optimization Tips

### Improving TTFT

1. **For Local (Ollama)**
   - Use smaller models (3b vs 7b)
   - Enable GPU acceleration
   - Increase system RAM

2. **For Cloud**
   - Use fast models (Groq is optimized for speed)
   - Retry with different endpoints
   - Cache results when possible

3. **Network**
   - Use wired connection instead of WiFi
   - Choose closest CDN endpoint
   - Reduce payload size

## Integration with CI/CD

### GitHub Actions Example
```yaml
- name: Run LLM Benchmarks
  env:
    GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
    CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
  run: |
    cd apps/BrainChat
    swift test --configuration release
```

## API Reference

### Running Benchmarks Programmatically

```swift
let config = AIConfiguration(
    systemPrompt: "Help me",
    claudeAPIKey: "...",
    openAIAPIKey: "...",
    groqAPIKey: "...",
    ollamaEndpoint: "http://localhost:11434/api/chat"
)

let runner = LLMBenchmarkRunner(configuration: config)

// Benchmark single provider
let result = await runner.benchmarkProvider(.ollama)
print("TTFT: \(result.timeToFirstToken)ms")

// Benchmark all providers
let collection = await runner.benchmarkAllProviders()
print(collection.generateSummary())

// Save results
try runner.saveResults(collection, to: "results.json")
```

## Contributing

When adding new LLM providers:

1. Create client class (e.g., `NewProviderClient.swift`)
2. Add to `AIProvider` enum
3. Add case to `AIManager.streamReply()`
4. Create benchmark test in `LLMBenchmarkTests.swift`
5. Update target latencies in `BenchmarkResults.swift`

## License

Same as BrainChat project.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review recent benchmark logs
3. Run with `--verbose` flag for debugging
