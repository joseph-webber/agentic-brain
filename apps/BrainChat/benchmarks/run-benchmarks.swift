#!/usr/bin/env swift

import Foundation

// MARK: - Benchmark Entry Point
print("""
╔═══════════════════════════════════════════════════════════════════╗
║                 LLM PERFORMANCE BENCHMARK SUITE                   ║
║                     BrainChat Swift App v1.0                      ║
╚═══════════════════════════════════════════════════════════════════╝
""")

// Create configuration from environment
let claudeKey = ProcessInfo.processInfo.environment["CLAUDE_API_KEY"] ?? ""
let openAIKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] ?? ""
let groqKey = ProcessInfo.processInfo.environment["GROQ_API_KEY"] ?? ""
let geminiKey = ProcessInfo.processInfo.environment["GEMINI_API_KEY"] ?? ""
let ollamaEndpoint = ProcessInfo.processInfo.environment["OLLAMA_ENDPOINT"] ?? "http://localhost:11434/api/chat"

print("\n📋 CONFIGURATION")
print("─────────────────────────────────────────────────────────────")
print("Ollama Endpoint: \(ollamaEndpoint)")
print("Claude API Key: \(claudeKey.isEmpty ? "❌ Not set" : "✓ Configured")")
print("OpenAI API Key: \(openAIKey.isEmpty ? "❌ Not set" : "✓ Configured")")
print("Groq API Key: \(groqKey.isEmpty ? "❌ Not set" : "✓ Configured")")
print("Gemini API Key: \(geminiKey.isEmpty ? "❌ Not set" : "✓ Configured")")

let configuration = AIConfiguration(
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

// Determine which providers to test
var providersToTest: [AIProvider] = []

if !ollamaEndpoint.isEmpty {
    providersToTest.append(.ollama)
    print("\n✓ Will benchmark Ollama (local)")
}

if !groqKey.isEmpty {
    providersToTest.append(.groq)
    print("✓ Will benchmark Groq (cloud)")
}

if !claudeKey.isEmpty {
    providersToTest.append(.claude)
    print("✓ Will benchmark Claude (cloud)")
}

if !openAIKey.isEmpty {
    providersToTest.append(.openAI)
    print("✓ Will benchmark OpenAI (cloud)")
}

if providersToTest.isEmpty {
    print("\n⚠️ WARNING: No providers configured!")
    print("Set environment variables to enable benchmarks:")
    print("  export OLLAMA_ENDPOINT='http://localhost:11434/api/chat'")
    print("  export GROQ_API_KEY='your-key'")
    print("  export CLAUDE_API_KEY='your-key'")
    print("  export OPENAI_API_KEY='your-key'")
}

print("\n🚀 BENCHMARK RESULTS")
print("═════════════════════════════════════════════════════════════")

// Create benchmark results
var results: [LLMBenchmarkResult] = []

// Test each provider
for provider in providersToTest {
    print("\n⏱️  Benchmarking \(provider.displayName)...")
    
    let startTime = Date()
    var firstTokenTime: TimeInterval?
    var tokenCount = 0
    var totalBytes = 0
    var fullResponse = ""
    
    let prompt = "Explain machine learning in one sentence."
    let messages = [AIChatMessage(role: .user, content: prompt)]
    
    var success = false
    var errorMessage: String?
    
    let runBenchmark = { (testProvider: AIProvider) async -> Void in
        let beforeAPI = Date()
        
        do {
            switch testProvider {
            case .ollama:
                _ = try await OllamaAPI().streamResponse(
                    endpoint: configuration.ollamaEndpoint,
                    model: configuration.ollamaModel,
                    messages: messages
                ) { delta in
                    if firstTokenTime == nil {
                        firstTokenTime = Date().timeIntervalSince(beforeAPI) * 1000
                    }
                    fullResponse += delta
                    totalBytes += delta.utf8.count
                }
                
            case .groq:
                _ = try await GroqClient().streamResponse(
                    apiKey: configuration.groqAPIKey,
                    model: configuration.groqModel,
                    messages: messages
                ) { delta in
                    if firstTokenTime == nil {
                        firstTokenTime = Date().timeIntervalSince(beforeAPI) * 1000
                    }
                    fullResponse += delta
                    totalBytes += delta.utf8.count
                }
                
            case .claude:
                _ = try await ClaudeAPI().streamResponse(
                    apiKey: configuration.claudeAPIKey,
                    model: configuration.claudeModel,
                    systemPrompt: configuration.systemPrompt,
                    messages: messages
                ) { delta in
                    if firstTokenTime == nil {
                        firstTokenTime = Date().timeIntervalSince(beforeAPI) * 1000
                    }
                    fullResponse += delta
                    totalBytes += delta.utf8.count
                }
                
            case .openAI:
                _ = try await OpenAIAPI().streamResponse(
                    apiKey: configuration.openAIAPIKey,
                    model: configuration.openAIModel,
                    messages: messages
                ) { delta in
                    if firstTokenTime == nil {
                        firstTokenTime = Date().timeIntervalSince(beforeAPI) * 1000
                    }
                    fullResponse += delta
                    totalBytes += delta.utf8.count
                }
            }
            success = true
        } catch {
            success = false
            errorMessage = error.localizedDescription
        }
    }
    
    // Run the benchmark synchronously using a sync task
    Task {
        await runBenchmark(provider)
    }
    
    // Give async tasks time to complete
    RunLoop.current.run(until: Date(timeIntervalSinceNow: 30))
    
    let totalTime = Date().timeIntervalSince(startTime) * 1000
    tokenCount = max(1, fullResponse.count / 4)
    
    let ttft = firstTokenTime ?? totalTime
    let target = targetLatencyFor(provider)
    
    let result = LLMBenchmarkResult(
        provider: provider.displayName,
        model: modelNameFor(provider, config: configuration),
        timeToFirstToken: ttft,
        totalResponseTime: totalTime,
        tokenCount: tokenCount,
        totalBytes: totalBytes,
        success: success,
        errorMessage: errorMessage,
        timestamp: Date(),
        targetTTFT: target
    )
    
    results.append(result)
    
    if success {
        let targetStatus = result.metTarget ? "✓ TARGET MET" : "✗ TARGET MISS"
        print("   TTFT: \(String(format: "%.2f", ttft))ms / \(Int(target))ms target [\(targetStatus)]")
        print("   Total: \(String(format: "%.2f", totalTime))ms")
        print("   Throughput: \(String(format: "%.2f", result.tokensPerSecond))tok/s")
        print("   Tokens: \(tokenCount)")
    } else {
        print("   ❌ FAILED: \(errorMessage ?? "Unknown error")")
    }
}

// Generate summary
print("\n📊 SUMMARY STATISTICS")
print("═════════════════════════════════════════════════════════════")

let successCount = results.filter { $0.success }.count
let failureCount = results.count - successCount

print("Total Tests: \(results.count)")
print("Successful: \(successCount) ✓")
print("Failed: \(failureCount) ✗")

if !results.isEmpty {
    let successful = results.filter { $0.success }
    
    if !successful.isEmpty {
        let avgTTFT = successful.map { $0.timeToFirstToken }.reduce(0, +) / Double(successful.count)
        let avgThroughput = successful.map { $0.tokensPerSecond }.reduce(0, +) / Double(successful.count)
        let targetMet = successful.filter { $0.metTarget }.count
        
        print("Average TTFT: \(String(format: "%.2f", avgTTFT))ms")
        print("Average Throughput: \(String(format: "%.2f", avgThroughput))tok/s")
        print("Target Met: \(targetMet)/\(successful.count) (\(String(format: "%.1f", Double(targetMet)/Double(successful.count)*100))%)")
        
        if let fastest = successful.min(by: { $0.timeToFirstToken < $1.timeToFirstToken }) {
            print("Fastest: \(fastest.provider) (\(String(format: "%.2f", fastest.timeToFirstToken))ms TTFT)")
        }
        
        if let slowest = successful.max(by: { $0.timeToFirstToken < $1.timeToFirstToken }) {
            print("Slowest: \(slowest.provider) (\(String(format: "%.2f", slowest.timeToFirstToken))ms TTFT)")
        }
    }
}

// Save results
print("\n💾 SAVING RESULTS")
print("─────────────────────────────────────────────────────────────")

let collection = BenchmarkResultsCollection(results: results, runTimestamp: Date())

let baselineDir = "/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks"
try? FileManager.default.createDirectory(atPath: baselineDir, withIntermediateDirectories: true, attributes: nil)

let baselinePath = "\(baselineDir)/llm-baseline.json"
let dateFormatter = ISO8601DateFormatter()
let timestamp = dateFormatter.string(from: Date()).replacingOccurrences(of: ":", with: "-")
let timestampedPath = "\(baselineDir)/llm-benchmark-\(timestamp).json"

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
encoder.dateEncodingStrategy = .iso8601

do {
    let jsonData = try encoder.encode(collection)
    try jsonData.write(to: URL(fileURLWithPath: baselinePath))
    print("✓ Baseline saved: \(baselinePath)")
    
    try jsonData.write(to: URL(fileURLWithPath: timestampedPath))
    print("✓ Timestamped saved: \(timestampedPath)")
} catch {
    print("✗ Failed to save results: \(error)")
}

print("\n✅ Benchmark complete!")
print("═════════════════════════════════════════════════════════════")

// MARK: - Helper Functions
func targetLatencyFor(_ provider: AIProvider) -> Double {
    switch provider {
    case .ollama: return 100.0
    case .groq: return 150.0
    case .claude, .openAI: return 300.0
    }
}

func modelNameFor(_ provider: AIProvider, config: AIConfiguration) -> String {
    switch provider {
    case .ollama: return config.ollamaModel
    case .groq: return config.groqModel
    case .claude: return config.claudeModel
    case .openAI: return config.openAIModel
    }
}
