# Performance Benchmarks

## LLM Provider Performance (Time to First Token)

| Provider | Model | TTFT (ms) | Target | Total (ms) | Tokens/sec | Status |
|----------|-------|-----------|--------|------------|------------|--------|
| **Ollama** | llama3.2:3b | **87ms** | <100ms | 1,245ms | 32.14 | ✅ PASS |
| **Groq** | llama-3.1-8b | **134ms** | <150ms | 756ms | 68.90 | ✅ PASS |
| **OpenAI** | gpt-4o | **234ms** | <300ms | 1,568ms | 38.45 | ✅ PASS |
| **Claude** | claude-sonnet | **289ms** | <300ms | 2,135ms | 31.23 | ✅ PASS |
| **Gemini** | gemini-2.5-flash | ~250ms | <300ms | ~1,800ms | ~35 | ✅ PASS |

### Quick Recommendations

Choose your provider based on your priorities:

- **🚀 Fastest Response**: Use **Ollama** (87ms TTFT)
  - Best for: Interactive tools, voice responses, real-time applications
  - Runs locally, no API calls, no latency from cloud

- **⚡ Best Cloud Speed**: Use **Groq** (134ms TTFT, 68.90 tokens/sec)
  - Best for: High-throughput batch processing, speed-critical applications
  - Excellent token throughput for generating longer responses

- **🧠 Complex Reasoning**: Use **Claude** (289ms, highest quality)
  - Best for: Multi-step reasoning, coding assistance, nuanced analysis
  - Quality over speed for complex problems

- **💰 Cost-Conscious**: Use **Groq** (cheapest with best performance)
  - Good performance-to-cost ratio
  - Fast enough for most applications

- **🎯 Balanced**: Use **OpenAI** (234ms, good quality and speed)
  - Reliable, well-tested, good all-around choice
  - Familiar API ecosystem

### Understanding LLM Performance Metrics

#### Time to First Token (TTFT)
The time from sending your request until the first token of the response arrives.

- **Why it matters**: Users perceive this as "how fast does the AI respond?"
- **Good target**: < 200ms for interactive applications
- **Excellent**: < 100ms (feels instant)
- **Acceptable**: < 300ms (noticeable delay, but not frustrating)

#### Total Response Time
Complete time to generate the full response (all tokens).

- **Why it matters**: Determines how long users wait for complete results
- **Factors affecting it**: 
  - Number of tokens in response
  - Provider's throughput (tokens/second)
  - Network latency (for cloud providers)

#### Tokens/Sec Throughput
How many tokens the provider generates per second.

- **Why it matters**: Determines total response time once first token arrives
- **Groq leads** at 68.90 tok/s (fastest token generation)
- **Local (Ollama)** at 32.14 tok/s (still fast, runs locally)

### LLM Target Latencies

These targets balance responsiveness with practical constraints:

| Use Case | Target TTFT | Rationale |
|----------|------------|-----------|
| Voice responses | <100ms | Audio output delays compound latency perception |
| Chat/Interactive | <200ms | Users notice delays >200ms |
| Batch processing | <300ms | Background tasks are less latency-sensitive |
| Reasoning tasks | <300ms | Complex computation takes time |

All providers in our benchmarks meet practical targets. Choose based on throughput and quality needs.

### How to Run LLM Benchmarks

#### Using the Built-in Benchmark Tool

agentic-brain includes a benchmark suite. Run it with:

```bash
npm run bench
# or
npm run benchmark
```

This will:
1. Send test prompts to each configured provider
2. Measure TTFT and total response time
3. Calculate throughput (tokens/second)
4. Display results in a summary table
5. Save detailed results to `benchmarks/results-{timestamp}.json`

#### Benchmarking a Specific Provider

```bash
npm run bench -- --provider groq
npm run bench -- --provider ollama
npm run bench -- --provider claude
```

#### Using OpenRouter's Smart Route Tool

OpenRouter includes performance benchmarking:

```bash
# Compare all available models
openrouter-openrouter_benchmark

# Get provider health status
openrouter-openrouter_status

# Route to fastest provider for your task
openrouter-openrouter_route --task "simple"
```

### Interpreting LLM Results

#### Expected Performance Ranges

**Local Providers (Ollama)**
- TTFT: 50-150ms (depends on hardware)
- Most consistent (no network variance)
- Throughput: 20-40 tok/s (varies by model)

**Cloud Providers**
- TTFT: 100-300ms (includes network latency)
- Network latency typically 20-50ms of total
- Throughput: 30-80+ tok/s

#### Performance Variations

Results will vary based on:

1. **Network conditions** (cloud providers)
   - Good WiFi: ±5-10ms TTFT
   - 4G/mobile: ±20-50ms TTFT
   - Congested networks: ±100-200ms TTFT

2. **Time of day** (cloud providers)
   - Peak hours: +10-20% latency
   - Off-peak: baseline performance

3. **System load** (local providers)
   - Fresh start: fastest
   - Under load: +20-40% latency
   - Memory pressure: potential degradation

4. **Prompt complexity**
   - Token encoding time: +5-15ms
   - Large system prompts: +10-20ms

### Tracking LLM Performance Regressions

#### Setting Up Regression Testing

Monitor performance to catch regressions early:

```bash
# Baseline benchmark (commit this to git)
npm run bench > benchmarks/baseline.txt

# In your CI/CD pipeline
npm run bench > benchmarks/current.txt

# Compare
diff benchmarks/baseline.txt benchmarks/current.txt
```

#### What to Watch For

⚠️ **Performance Regression Alert** if:
- TTFT increases by >10% (consistent)
- Throughput decreases by >5% (consistent)
- Total response time increases noticeably

#### Causes of Regressions

1. **Code changes** that add overhead
2. **Provider updates** (usually improvements, sometimes slower models)
3. **Network configuration** changes
4. **System resource constraints**

#### When to Investigate

- New provider slower than baseline? Test network connectivity
- Local (Ollama) slower? Check system resources
- Intermittent slowness? Look for network congestion or system load spikes

### Using Results for LLM Decision-Making

#### Choose Provider Based On:

1. **Response Speed**
   ```
   Ollama (87ms) > Groq (134ms) > OpenAI (234ms) > Gemini (250ms) > Claude (289ms)
   ```

2. **Token Throughput** (for longer responses)
   ```
   Groq (68.90 tok/s) > OpenAI (38.45) > Gemini (35) > Ollama (32.14) > Claude (31.23)
   ```

3. **Quality (estimated)**
   ```
   Claude > GPT-4o > Gemini > Groq's 70B > Groq's 8B > Llama3.2:3b
   ```

#### Decision Matrix

| Priority | Best Provider | Rationale |
|----------|---------------|-----------|
| Speed | Ollama | Lowest latency (87ms) |
| Cloud Speed | Groq | Best cloud option (134ms) |
| Throughput | Groq | 68.90 tok/s |
| Quality | Claude | Best reasoning capabilities |
| Cost | Groq | Fast + cheap |
| Reliability | OpenAI | Most stable, mature |
| Privacy | Ollama | Everything local |

---

## Speech-to-Text Performance (Dictation)

| Engine | Model | Latency (ms) | Target | Status | Notes |
|--------|-------|--------------|--------|--------|-------|
| **Apple Speech** | Native | **150ms** | <200ms | ✅ PASS | Real-time, on-device |
| **whisper.cpp** | base | **1,200ms** | <1,500ms | ✅ PASS | Offline, accurate |
| **Whisper API** | large-v3 | **2,000ms** | <3,000ms | ✅ PASS | Cloud, most accurate |
| **faster-whisper** | tiny | 2,401ms | <500ms | ⚠️ Needs GPU | CPU-bound |
| **faster-whisper** | base | 3,584ms | <1,000ms | ⚠️ Needs GPU | CPU-bound |
| **faster-whisper** | small | 2,917ms | <2,000ms | ⚠️ Needs GPU | CPU-bound |

**Recommendations:**
- Real-time voice: Apple Speech (150ms) - production ready
- Offline processing: whisper.cpp (1,200ms) - production ready
- Maximum accuracy: Whisper API (2,000ms) - production ready

**Whisper Model Sizes:**
| Model | Parameters | VRAM | Speed | Accuracy |
|-------|------------|------|-------|----------|
| tiny | 39M | ~1GB | Fastest | Good |
| base | 74M | ~1GB | Fast | Better |
| small | 244M | ~2GB | Medium | Great |
| medium | 769M | ~5GB | Slow | Excellent |
| large-v3 | 1.5B | ~10GB | Slowest | Best |

### Model Selection by Use Case

**For Real-Time Applications (< 200ms):**
- Use Apple Speech on macOS/iOS
- Best latency, lowest resource usage
- Perfect for live dictation and immediate transcription feedback

**For Offline Processing (Balance Speed/Accuracy):**
- Use whisper.cpp with base model (1,200ms, 74M params)
- Provides good accuracy without excessive resource consumption
- Suitable for batch transcription and background processing

**For Maximum Accuracy (Highest Quality):**
- Use Whisper API with large-v3 model (2,000ms, 1.5B params)
- Best transcription quality for challenging audio
- Use when accuracy is more important than latency

**For Resource-Constrained Environments:**
- Use whisper.cpp with tiny model
- Lowest memory footprint (~1GB)
- Acceptable accuracy for less critical transcription needs

**GPU Acceleration Notes:**
- faster-whisper models require GPU for acceptable performance
- CPU-only performance is currently 3-5x slower than targets
- Consider GPU deployment if using faster-whisper at scale

---

## Voice Engine Performance (Text-to-Speech)

| Engine | First Audio (ms) | 10-word (ms) | 50-word (ms) | Cached (ms) | Quality |
|--------|-----------------|--------------|--------------|-------------|---------|
| **macOS** | **32ms** ✅ | 28ms | 46ms | **6ms** | Good |
| **Cartesia** | **92ms** ✅ | 119ms | 156ms | 96ms | Excellent ⭐ |
| **Piper** | **142ms** ✅ | 168ms | 246ms | 78ms | Good |
| **ElevenLabs** | **179ms** ✅ | 215ms | 329ms | 182ms | Premium |

### Performance Targets

All targets **ACHIEVED** ✅

- **macOS**: <50ms ✅ (actual: 32ms)
- **Cartesia streaming**: <100ms ✅ (actual: 92ms)
- **Cached phrases**: <10ms ✅ (actual: 6ms)

### Recommended Configuration

Select the appropriate engine based on your use case:

1. **PRIMARY: Cartesia** (92ms, excellent quality, streaming)
   - Best overall quality with acceptable latency
   - Streaming support for real-time audio
   - Recommended for most interactive scenarios

2. **QUICK: macOS cached phrases** (6ms for "Got it", "OK")
   - Fastest option for pre-recorded acknowledgments
   - No external dependencies
   - Use for time-critical acknowledgments and confirmations

3. **FALLBACK: Piper** (142ms, fully offline)
   - Full offline capability
   - No API dependencies
   - Use when external services are unavailable
   - Good quality for asynchronous messages

4. **PREMIUM: ElevenLabs** (179ms, highest quality)
   - Highest audio quality
   - Use for premium experiences
   - Best for marketing/professional content

### Voice Selection (Australian)

Users with VoiceOver on Australian English systems. Recommended voice configuration:

- **Karen** (macOS native)
  - Fastest response (leverages system acceleration)
  - Best for real-time interaction
  
- **Australian Narrator Lady** (Cartesia)
  - Best quality for longer messages
  - Premium experience
  
- **en-AU model** (Piper)
  - Offline backup option
  - Full regional locale support

### Usage Guidelines by Engine

**macOS Native (32ms)**
- System acknowledgments ("Got it", "OK", "Done")
- Cached pre-recorded phrases
- Time-critical responses
- VoiceOver integration

**Cartesia (92ms)**
- Interactive conversations
- Real-time feedback
- Streaming content
- When quality matters more than speed

**Piper (142ms)**
- Offline-first deployments
- Privacy-critical scenarios
- Fully local processing
- Asynchronous messages

**ElevenLabs (179ms)**
- Premium user experiences
- Professional narration
- Marketing content
- Special occasions

### Cache Strategy

Implement caching for frequently-used phrases to achieve 6ms response times:

```
Cached phrases (6ms latency):
- "Got it"
- "OK"
- "Sure"
- "Done"
- "Ready"
- "Processing"
- "Error occurred"
```

This strategy reduces latency dramatically for common responses while keeping the system lightweight.
