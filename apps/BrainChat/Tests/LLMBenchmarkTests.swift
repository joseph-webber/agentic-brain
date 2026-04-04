import Foundation
import XCTest

// This test file runs comprehensive benchmarks on all LLM providers
// To run: swift test --configuration release --parallel 1 or use Xcode's Test runner

class LLMBenchmarkTests: XCTestCase {
    var benchmarkRunner: LLMBenchmarkRunner?
    var configuration: AIConfiguration?
    
    override func setUp() async throws {
        try await super.setUp()
        
        // Load API keys from environment or local config
        let claudeKey = ProcessInfo.processInfo.environment["CLAUDE_API_KEY"] ?? ""
        let openAIKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] ?? ""
        let groqKey = ProcessInfo.processInfo.environment["GROQ_API_KEY"] ?? ""
        let ollamaEndpoint = ProcessInfo.processInfo.environment["OLLAMA_ENDPOINT"] ?? "http://localhost:11434/api/chat"
        
        configuration = AIConfiguration(
            systemPrompt: "You are a helpful AI assistant.",
            claudeAPIKey: claudeKey,
            claudeModel: "claude-sonnet-4-20250514",
            openAIAPIKey: openAIKey,
            openAIModel: "gpt-4o",
            groqAPIKey: groqKey,
            groqModel: "llama-3.1-8b-instant",
            ollamaEndpoint: ollamaEndpoint,
            ollamaModel: "llama3.2:3b"
        )
        
        benchmarkRunner = LLMBenchmarkRunner(configuration: configuration!)
    }
    
    /// Test: Benchmark Ollama (Local)
    func testBenchmarkOllama() async throws {
        guard let runner = benchmarkRunner else { return }
        
        let result = await runner.benchmarkProvider(
            .ollama,
            prompt: "What is machine learning? Provide a concise explanation in 2-3 sentences."
        )
        
        XCTAssertTrue(result.success, "Ollama benchmark should succeed")
        XCTAssertGreaterThan(result.timeToFirstToken, 0, "TTFT should be positive")
        XCTAssertGreaterThan(result.totalResponseTime, 0, "Total response time should be positive")
        XCTAssertGreaterThanOrEqual(result.totalResponseTime, result.timeToFirstToken, "Total time should be >= TTFT")
        
        print("✓ Ollama Benchmark Results:")
        print("  TTFT: \(String(format: "%.2f", result.timeToFirstToken))ms (target: <\(Int(result.targetTTFT))ms)")
        print("  Total: \(String(format: "%.2f", result.totalResponseTime))ms")
        print("  Throughput: \(String(format: "%.2f", result.tokensPerSecond))tok/s")
        print("  Tokens: \(result.tokenCount)")
    }
    
    /// Test: Benchmark Groq (Fast Cloud)
    func testBenchmarkGroq() async throws {
        guard let runner = benchmarkRunner, let config = configuration else { return }
        guard !config.groqAPIKey.isEmpty else {
            print("⊘ Groq benchmark skipped (no API key)")
            return
        }
        
        let result = await runner.benchmarkProvider(
            .groq,
            prompt: "What is machine learning? Provide a concise explanation in 2-3 sentences."
        )
        
        if result.success {
            XCTAssertGreaterThan(result.timeToFirstToken, 0, "TTFT should be positive")
            XCTAssertGreaterThan(result.totalResponseTime, 0, "Total response time should be positive")
            
            print("✓ Groq Benchmark Results:")
            print("  TTFT: \(String(format: "%.2f", result.timeToFirstToken))ms (target: <\(Int(result.targetTTFT))ms)")
            print("  Total: \(String(format: "%.2f", result.totalResponseTime))ms")
            print("  Throughput: \(String(format: "%.2f", result.tokensPerSecond))tok/s")
            print("  Tokens: \(result.tokenCount)")
        } else {
            print("✗ Groq benchmark failed: \(result.errorMessage ?? "Unknown error")")
        }
    }
    
    /// Test: Benchmark Claude (Anthropic Cloud)
    func testBenchmarkClaude() async throws {
        guard let runner = benchmarkRunner, let config = configuration else { return }
        guard !config.claudeAPIKey.isEmpty else {
            print("⊘ Claude benchmark skipped (no API key)")
            return
        }
        
        let result = await runner.benchmarkProvider(
            .claude,
            prompt: "What is machine learning? Provide a concise explanation in 2-3 sentences."
        )
        
        if result.success {
            XCTAssertGreaterThan(result.timeToFirstToken, 0, "TTFT should be positive")
            XCTAssertGreaterThan(result.totalResponseTime, 0, "Total response time should be positive")
            
            print("✓ Claude Benchmark Results:")
            print("  TTFT: \(String(format: "%.2f", result.timeToFirstToken))ms (target: <\(Int(result.targetTTFT))ms)")
            print("  Total: \(String(format: "%.2f", result.totalResponseTime))ms")
            print("  Throughput: \(String(format: "%.2f", result.tokensPerSecond))tok/s")
            print("  Tokens: \(result.tokenCount)")
        } else {
            print("✗ Claude benchmark failed: \(result.errorMessage ?? "Unknown error")")
        }
    }
    
    /// Test: Benchmark OpenAI (GPT Cloud)
    func testBenchmarkOpenAI() async throws {
        guard let runner = benchmarkRunner, let config = configuration else { return }
        guard !config.openAIAPIKey.isEmpty else {
            print("⊘ OpenAI benchmark skipped (no API key)")
            return
        }
        
        let result = await runner.benchmarkProvider(
            .openAI,
            prompt: "What is machine learning? Provide a concise explanation in 2-3 sentences."
        )
        
        if result.success {
            XCTAssertGreaterThan(result.timeToFirstToken, 0, "TTFT should be positive")
            XCTAssertGreaterThan(result.totalResponseTime, 0, "Total response time should be positive")
            
            print("✓ OpenAI Benchmark Results:")
            print("  TTFT: \(String(format: "%.2f", result.timeToFirstToken))ms (target: <\(Int(result.targetTTFT))ms)")
            print("  Total: \(String(format: "%.2f", result.totalResponseTime))ms")
            print("  Throughput: \(String(format: "%.2f", result.tokensPerSecond))tok/s")
            print("  Tokens: \(result.tokenCount)")
        } else {
            print("✗ OpenAI benchmark failed: \(result.errorMessage ?? "Unknown error")")
        }
    }
    
    /// Test: Benchmark All Providers and Generate Report
    func testBenchmarkAllProviders() async throws {
        guard let runner = benchmarkRunner else { return }
        
        let providers: [AIProvider] = [.ollama, .groq, .claude, .openAI]
        let prompt = "What is artificial intelligence? Provide a brief explanation."
        
        print("\n🚀 Starting comprehensive LLM benchmark suite...\n")
        
        let collection = await runner.benchmarkAllProviders(
            providers: providers,
            prompt: prompt
        )
        
        let summary = collection.generateSummary()
        print(summary)
        
        // Try to save results
        let baselinePath = "/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks/llm-baseline.json"
        let dateFormatter = ISO8601DateFormatter()
        let timestamp = dateFormatter.string(from: Date())
        let timestampedPath = "/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks/llm-benchmark-\(timestamp).json"
        
        do {
            try runner.saveResults(collection, to: baselinePath)
            print("✓ Baseline results saved to: \(baselinePath)")
            
            try runner.saveResults(collection, to: timestampedPath)
            print("✓ Timestamped results saved to: \(timestampedPath)")
        } catch {
            print("⚠ Failed to save results: \(error)")
        }
    }
    
    /// Test: Stress test - rapid sequential requests
    func testStressTestSequential() async throws {
        guard let runner = benchmarkRunner else { return }
        
        print("\n⚡ Starting sequential stress test (5 requests)...\n")
        
        var results: [LLMBenchmarkResult] = []
        for i in 1...5 {
            let result = await runner.benchmarkProvider(
                .ollama,
                prompt: "Question \(i): What is AI?"
            )
            results.append(result)
            print("Request \(i): TTFT=\(String(format: "%.2f", result.timeToFirstToken))ms")
        }
        
        let avgTTFT = results.map { $0.timeToFirstToken }.reduce(0, +) / Double(results.count)
        print("\nAverage TTFT across 5 requests: \(String(format: "%.2f", avgTTFT))ms")
    }
    
    /// Test: Compare provider latencies
    func testCompareProviderLatencies() async throws {
        guard let runner = benchmarkRunner else { return }
        
        print("\n📊 Comparing provider latencies...\n")
        
        let providers: [AIProvider] = [.ollama, .groq, .claude, .openAI]
        let prompt = "What is the weather like?"
        
        var results: [AIProvider: LLMBenchmarkResult] = [:]
        
        for provider in providers {
            let result = await runner.benchmarkProvider(provider, prompt: prompt)
            results[provider] = result
        }
        
        // Sort by TTFT
        let sorted = results.sorted { $0.value.timeToFirstToken < $1.value.timeToFirstToken }
        
        print("Provider Latency Rankings:")
        for (index, (provider, result)) in sorted.enumerated() {
            let rank = index + 1
            let status = result.success ? "✓" : "✗"
            let targetMet = result.metTarget ? "✓" : "✗"
            print("\(rank). [\(status)] \(provider.displayName)")
            print("   TTFT: \(String(format: "%.2f", result.timeToFirstToken))ms")
            print("   Target: \(String(format: "%.0f", result.targetTTFT))ms [\(targetMet)]")
        }
    }
}

// MARK: - Performance Benchmarking Tests
class LLMPerformanceTests: XCTestCase {
    var benchmarkRunner: LLMBenchmarkRunner?
    var configuration: AIConfiguration?
    
    override func setUp() async throws {
        try await super.setUp()
        
        configuration = AIConfiguration(
            systemPrompt: "You are a helpful AI assistant.",
            claudeAPIKey: ProcessInfo.processInfo.environment["CLAUDE_API_KEY"] ?? "",
            openAIAPIKey: ProcessInfo.processInfo.environment["OPENAI_API_KEY"] ?? "",
            groqAPIKey: ProcessInfo.processInfo.environment["GROQ_API_KEY"] ?? "",
            ollamaEndpoint: ProcessInfo.processInfo.environment["OLLAMA_ENDPOINT"] ?? "http://localhost:11434/api/chat"
        )
        
        benchmarkRunner = LLMBenchmarkRunner(configuration: configuration!)
    }
    
    /// Measure: Ollama TTFT
    func testMeasureOllamaTTFT() async throws {
        guard let runner = benchmarkRunner else { return }
        
        self.measure {
            let result = Task {
                await runner.benchmarkProvider(
                    .ollama,
                    prompt: "Say hello."
                )
            }
            _ = try! result.value // This is a simplified measurement
        }
    }
    
    /// Test that multiple concurrent requests work
    func testConcurrentRequests() async throws {
        guard let runner = benchmarkRunner else { return }
        
        print("\n⚙️ Testing concurrent requests...\n")
        
        async let result1 = runner.benchmarkProvider(.ollama, prompt: "What is AI?")
        async let result2 = runner.benchmarkProvider(.ollama, prompt: "What is ML?")
        
        let (r1, r2) = await (result1, result2)
        
        XCTAssertTrue(r1.success, "First request should succeed")
        XCTAssertTrue(r2.success, "Second request should succeed")
        
        print("✓ Concurrent request 1: \(String(format: "%.2f", r1.timeToFirstToken))ms TTFT")
        print("✓ Concurrent request 2: \(String(format: "%.2f", r2.timeToFirstToken))ms TTFT")
    }
}
