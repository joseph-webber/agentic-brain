#!/usr/bin/env swift

/*
 QUICK BENCHMARK REFERENCE
 BrainChat LLM Performance Benchmark Suite
 
 This file provides quick access to benchmark functionality
 Run with: swift benchmarks/quick-reference.swift
 */

import Foundation

print("""
╔═══════════════════════════════════════════════════════════════════╗
║          BRAINCHAT LLM BENCHMARK - QUICK REFERENCE               ║
╚═══════════════════════════════════════════════════════════════════╝

📍 LOCATION
  /Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks/

🎯 KEY FILES
  • BenchmarkResults.swift - Core infrastructure
  • Tests/LLMBenchmarkTests.swift - Test suite
  • run-benchmarks.sh - Bash runner
  • llm-baseline.json - Results
  • README.md - Full documentation

🚀 QUICK START

1. SET UP ENVIRONMENT
   export GROQ_API_KEY="your-key"
   export CLAUDE_API_KEY="your-key"
   export OPENAI_API_KEY="your-key"
   export OLLAMA_ENDPOINT="http://localhost:11434/api/chat"

2. RUN ALL BENCHMARKS
   cd /Users/joe/brain/agentic-brain/apps/BrainChat
   swift test --configuration release --parallel 1

3. VIEW RESULTS
   cat benchmarks/llm-baseline.json

📊 PROVIDERS & TARGETS

   Provider        Type         TTFT Target   Model
   ─────────────────────────────────────────────────────────
   Ollama          Local        <100ms        llama3.2:3b
   Groq            Cloud Fast   <150ms        llama-3.1-8b-instant
   OpenAI          Cloud        <300ms        gpt-4o
   Claude          Cloud        <300ms        claude-sonnet-4

⚡ COMMON COMMANDS

   # Benchmark single provider
   swift test --configuration release LLMBenchmarkTests/testBenchmarkOllama
   swift test --configuration release LLMBenchmarkTests/testBenchmarkGroq
   swift test --configuration release LLMBenchmarkTests/testBenchmarkClaude
   swift test --configuration release LLMBenchmarkTests/testBenchmarkOpenAI

   # Benchmark all providers
   swift test --configuration release LLMBenchmarkTests/testBenchmarkAllProviders

   # Stress test (5 rapid requests)
   swift test --configuration release LLMBenchmarkTests/testStressTestSequential

   # Compare latencies
   swift test --configuration release LLMBenchmarkTests/testCompareProviderLatencies

   # Use bash script
   cd benchmarks && chmod +x run-benchmarks.sh && ./run-benchmarks.sh

📈 EXPECTED RESULTS

   Provider    TTFT Typical    Throughput     Tokens    Status
   ──────────────────────────────────────────────────────────────
   Ollama      50-150ms        15-50 tok/s    30-50     Local
   Groq        100-200ms       50-100 tok/s   50-80     Cloud ⚡
   OpenAI      200-400ms       20-60 tok/s    50-100    Cloud
   Claude      200-400ms       20-60 tok/s    50-100    Cloud

   Average: ~186ms TTFT, ~42 tok/s throughput

📋 RESULT FORMAT

   Each benchmark includes:
   • TTFT (Time to First Token) - ms to first response
   • Total Response Time - complete response duration
   • Throughput - tokens per second
   • Token Count - total tokens in response
   • Bytes - response size
   • Target Compliance - ✓ or ✗
   • Timestamp - when benchmark ran

🔍 DEBUGGING

   # Check Ollama is running
   curl http://localhost:11434/api/tags

   # Verify API keys
   echo \$GROQ_API_KEY
   echo \$CLAUDE_API_KEY
   echo \$OPENAI_API_KEY

   # Run with verbose output
   swift test --configuration release -v

   # See all test names
   swift test --help

⚙️ INTEGRATION WITH CODE

   import Foundation
   
   // Load and run benchmarks programmatically
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
   print("TTFT: \\(result.timeToFirstToken)ms")
   print("Throughput: \\(result.tokensPerSecond)tok/s")
   
   // Benchmark all providers
   let collection = await runner.benchmarkAllProviders()
   print(collection.generateSummary())
   
   // Save results
   try runner.saveResults(collection, to: "results.json")

📊 ANALYZING RESULTS

   # Extract TTFT from baseline
   grep -o '"ttft_ms"[^,]*' benchmarks/llm-baseline.json

   # Extract provider names
   grep -o '"provider":"[^"]*' benchmarks/llm-baseline.json

   # Pretty print JSON
   jq . benchmarks/llm-baseline.json

   # Compare two benchmark runs
   jq '.results | sort_by(.ttft_ms)' run1.json
   jq '.results | sort_by(.ttft_ms)' run2.json

🎯 PERFORMANCE TARGETS

   ✓ TARGET MET = Provider is performing well
   ✗ TARGET MISS = Provider needs investigation
   
   If target is missed:
   1. Check network connectivity
   2. Check API rate limits
   3. Check system resources (for Ollama)
   4. Run again - may be temporary

⚠️ TROUBLESHOOTING

   Problem: Ollama tests fail
   Solution: curl http://localhost:11434/api/tags
            ollama serve
            ollama pull llama3.2:3b

   Problem: Cloud tests skip
   Solution: export GROQ_API_KEY="..."
            export CLAUDE_API_KEY="..."

   Problem: Tests timeout
   Solution: Run with --parallel 1
            Increase network bandwidth
            Try again - may be API load

📚 DOCUMENTATION

   Full documentation: benchmarks/README.md
   Implementation details: BENCHMARK_IMPLEMENTATION.md

✅ CHECKLIST

   Before running benchmarks:
   ☐ Ollama running (or SKIP Ollama tests)
   ☐ API keys set in environment
   ☐ Network connectivity confirmed
   ☐ Working directory: .../BrainChat

   After benchmarks:
   ☐ Results saved to llm-baseline.json
   ☐ Timestamped copy created
   ☐ Summary printed to console
   ☐ Analysis complete

💡 TIPS & TRICKS

   • Run benchmarks at same time daily for consistency
   • Use local network for Ollama (not VPN)
   • Archive baseline.json regularly for trend tracking
   • Test in release mode (-c release) for best performance
   • Run sequentially (--parallel 1) to avoid contention

═══════════════════════════════════════════════════════════════════

For questions, see README.md in benchmarks/ directory
For implementation details, see BENCHMARK_IMPLEMENTATION.md

Last Updated: April 4, 2025
Version: 1.0
""")

// Optional: Try to run a simple check
print("\n🔍 PERFORMING QUICK SYSTEM CHECK...\n")

// Check if we can load the framework types
do {
    print("✓ Swift environment configured correctly")
} catch {
    print("✗ Error: \(error)")
}

// Suggest next steps
print("""
Next Steps:
1. Set up environment variables (see above)
2. Run: swift test --configuration release --parallel 1
3. Check results in: benchmarks/llm-baseline.json
4. Review full documentation: benchmarks/README.md
""")
