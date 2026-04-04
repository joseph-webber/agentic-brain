import Foundation

/// Benchmark result for a single LLM provider
struct LLMBenchmarkResult: Codable, Sendable {
    /// Provider name (e.g., "Ollama", "Groq", "OpenAI", "Claude", "Gemini")
    let provider: String
    
    /// Model name used for benchmarking
    let model: String
    
    /// Time to first token in milliseconds
    let timeToFirstToken: Double
    
    /// Total response time in milliseconds
    let totalResponseTime: Double
    
    /// Number of tokens in the response
    let tokenCount: Int
    
    /// Tokens per second throughput
    let tokensPerSecond: Double
    
    /// Total bytes received
    let totalBytes: Int
    
    /// Whether the request succeeded
    let success: Bool
    
    /// Error message if failed
    let errorMessage: String?
    
    /// Timestamp of the benchmark
    let timestamp: Date
    
    /// Target latency for this provider (in ms)
    let targetTTFT: Double
    
    /// Whether this benchmark met the target latency
    var metTarget: Bool {
        timeToFirstToken <= targetTTFT
    }
    
    enum CodingKeys: String, CodingKey {
        case provider, model
        case timeToFirstToken = "ttft_ms"
        case totalResponseTime = "total_time_ms"
        case tokenCount = "tokens"
        case tokensPerSecond = "throughput_tps"
        case totalBytes = "bytes"
        case success
        case errorMessage = "error"
        case timestamp
        case targetTTFT = "target_ttft_ms"
    }
    
    init(
        provider: String,
        model: String,
        timeToFirstToken: Double,
        totalResponseTime: Double,
        tokenCount: Int,
        totalBytes: Int,
        success: Bool = true,
        errorMessage: String? = nil,
        timestamp: Date = Date(),
        targetTTFT: Double
    ) {
        self.provider = provider
        self.model = model
        self.timeToFirstToken = timeToFirstToken
        self.totalResponseTime = totalResponseTime
        self.tokenCount = tokenCount
        self.totalBytes = totalBytes
        self.success = success
        self.errorMessage = errorMessage
        self.timestamp = timestamp
        self.targetTTFT = targetTTFT
        
        // Calculate throughput: tokens / (time in seconds)
        let timeSeconds = totalResponseTime / 1000.0
        self.tokensPerSecond = timeSeconds > 0 ? Double(tokenCount) / timeSeconds : 0
    }
}

/// Collection of benchmark results with analysis
struct BenchmarkResultsCollection: Codable, Sendable {
    /// Array of all benchmark results
    let results: [LLMBenchmarkResult]
    
    /// Timestamp when benchmarks were run
    let runTimestamp: Date
    
    /// Whether all benchmarks completed successfully
    var allSuccessful: Bool {
        results.allSatisfy { $0.success }
    }
    
    /// Count of successful benchmarks
    var successCount: Int {
        results.filter { $0.success }.count
    }
    
    /// Count of failed benchmarks
    var failureCount: Int {
        results.count - successCount
    }
    
    /// Percentage of providers that met target latency
    var targetMetPercentage: Double {
        let successful = results.filter { $0.success }
        guard !successful.isEmpty else { return 0 }
        let metCount = successful.filter { $0.metTarget }.count
        return Double(metCount) / Double(successful.count) * 100.0
    }
    
    /// Average TTFT across all successful benchmarks
    var averageTTFT: Double {
        let successful = results.filter { $0.success }
        guard !successful.isEmpty else { return 0 }
        let sum = successful.map { $0.timeToFirstToken }.reduce(0, +)
        return sum / Double(successful.count)
    }
    
    /// Average throughput across all successful benchmarks
    var averageThroughput: Double {
        let successful = results.filter { $0.success }
        guard !successful.isEmpty else { return 0 }
        let sum = successful.map { $0.tokensPerSecond }.reduce(0, +)
        return sum / Double(successful.count)
    }
    
    /// Fastest TTFT result
    var fastestTTFT: LLMBenchmarkResult? {
        results.filter { $0.success }.min { $0.timeToFirstToken < $1.timeToFirstToken }
    }
    
    /// Slowest TTFT result
    var slowestTTFT: LLMBenchmarkResult? {
        results.filter { $0.success }.max { $0.timeToFirstToken < $1.timeToFirstToken }
    }
    
    /// Best throughput result
    var bestThroughput: LLMBenchmarkResult? {
        results.filter { $0.success }.max { $0.tokensPerSecond < $1.tokensPerSecond }
    }
    
    init(results: [LLMBenchmarkResult], runTimestamp: Date = Date()) {
        self.results = results
        self.runTimestamp = runTimestamp
    }
    
    /// Generate a human-readable summary
    func generateSummary() -> String {
        var summary = "═══════════════════════════════════════════════════════════\n"
        summary += "LLM PERFORMANCE BENCHMARK RESULTS\n"
        summary += "═══════════════════════════════════════════════════════════\n"
        summary += "Run Time: \(ISO8601DateFormatter().string(from: runTimestamp))\n"
        summary += "Results: \(successCount)/\(results.count) successful\n"
        summary += "Target Met: \(String(format: "%.1f", targetMetPercentage))%\n\n"
        
        summary += "SUMMARY STATISTICS\n"
        summary += "─────────────────────────────────────────────────────────────\n"
        summary += "Average TTFT: \(String(format: "%.2f", averageTTFT))ms\n"
        summary += "Average Throughput: \(String(format: "%.2f", averageThroughput))tok/s\n"
        
        if let fastest = fastestTTFT {
            summary += "Fastest: \(fastest.provider) (\(String(format: "%.2f", fastest.timeToFirstToken))ms)\n"
        }
        if let slowest = slowestTTFT {
            summary += "Slowest: \(slowest.provider) (\(String(format: "%.2f", slowest.timeToFirstToken))ms)\n"
        }
        if let best = bestThroughput {
            summary += "Best Throughput: \(best.provider) (\(String(format: "%.2f", best.tokensPerSecond))tok/s)\n"
        }
        
        summary += "\nDETAILED RESULTS\n"
        summary += "─────────────────────────────────────────────────────────────\n"
        
        for result in results.sorted(by: { $0.timeToFirstToken < $1.timeToFirstToken }) {
            let status = result.success ? "✓" : "✗"
            let targetStatus = result.success && result.metTarget ? "TARGET MET" : "target miss"
            summary += "\n[\(status)] \(result.provider) (\(result.model))\n"
            summary += "  TTFT: \(String(format: "%.2f", result.timeToFirstToken))ms / \(String(format: "%.0f", result.targetTTFT))ms target [\(targetStatus)]\n"
            summary += "  Total: \(String(format: "%.2f", result.totalResponseTime))ms\n"
            summary += "  Throughput: \(String(format: "%.2f", result.tokensPerSecond))tok/s (\(result.tokenCount) tokens)\n"
            summary += "  Bytes: \(result.totalBytes)\n"
            
            if !result.success, let error = result.errorMessage {
                summary += "  ERROR: \(error)\n"
            }
        }
        
        summary += "\n═══════════════════════════════════════════════════════════\n"
        return summary
    }
}

/// Manager for running and recording LLM benchmarks
actor LLMBenchmarkRunner: Sendable {
    private let groqAPI: any GroqStreaming
    private let claudeAPI: any ClaudeStreaming
    private let openAIAPI: any OpenAIStreaming
    private let ollamaAPI: any OllamaStreaming
    private let geminiAPI: any GeminiStreaming
    
    private let configuration: AIConfiguration
    
    init(
        groqAPI: any GroqStreaming = GroqClient(),
        claudeAPI: any ClaudeStreaming = ClaudeAPI(),
        openAIAPI: any OpenAIStreaming = OpenAIAPI(),
        ollamaAPI: any OllamaStreaming = OllamaAPI(),
        geminiAPI: any GeminiStreaming = GeminiClient(),
        configuration: AIConfiguration
    ) {
        self.groqAPI = groqAPI
        self.claudeAPI = claudeAPI
        self.openAIAPI = openAIAPI
        self.ollamaAPI = ollamaAPI
        self.geminiAPI = geminiAPI
        self.configuration = configuration
    }
    
    /// Run a single benchmark for a provider
    func benchmarkProvider(
        _ provider: AIProvider,
        prompt: String = "What is machine learning? Provide a detailed explanation."
    ) async -> LLMBenchmarkResult {
        let startTime = Date()
        var firstTokenTime: TimeInterval?
        var tokenCount = 0
        var totalBytes = 0
        var fullResponse = ""
        
        let messages = [AIChatMessage(role: .user, content: prompt)]
        
        do {
            let beforeAPI = Date()
            
            switch provider {
            case .groq:
                _ = try await groqAPI.streamResponse(
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
                _ = try await claudeAPI.streamResponse(
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
                _ = try await openAIAPI.streamResponse(
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
                
            case .ollama:
                _ = try await ollamaAPI.streamResponse(
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
            }
            
            let totalTime = Date().timeIntervalSince(startTime) * 1000
            tokenCount = estimateTokenCount(fullResponse)
            
            let ttft = firstTokenTime ?? totalTime
            let target = Self.targetLatencyFor(provider)
            
            return LLMBenchmarkResult(
                provider: provider.displayName,
                model: modelNameFor(provider),
                timeToFirstToken: ttft,
                totalResponseTime: totalTime,
                tokenCount: tokenCount,
                totalBytes: totalBytes,
                success: true,
                errorMessage: nil,
                timestamp: Date(),
                targetTTFT: target
            )
        } catch {
            let totalTime = Date().timeIntervalSince(startTime) * 1000
            let target = Self.targetLatencyFor(provider)
            
            return LLMBenchmarkResult(
                provider: provider.displayName,
                model: modelNameFor(provider),
                timeToFirstToken: totalTime,
                totalResponseTime: totalTime,
                tokenCount: 0,
                totalBytes: 0,
                success: false,
                errorMessage: error.localizedDescription,
                timestamp: Date(),
                targetTTFT: target
            )
        }
    }
    
    /// Run benchmarks for all providers
    func benchmarkAllProviders(
        providers: [AIProvider] = [.ollama, .groq, .claude, .openAI],
        prompt: String = "What is machine learning? Provide a detailed explanation."
    ) async -> BenchmarkResultsCollection {
        var results: [LLMBenchmarkResult] = []
        
        for provider in providers {
            let result = await benchmarkProvider(provider, prompt: prompt)
            results.append(result)
        }
        
        return BenchmarkResultsCollection(results: results, runTimestamp: Date())
    }
    
    /// Save benchmark results to JSON file
    func saveResults(_ collection: BenchmarkResultsCollection, to path: String) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        encoder.dateEncodingStrategy = .iso8601
        
        let data = try encoder.encode(collection)
        try data.write(to: URL(fileURLWithPath: path))
    }
    
    /// Load benchmark results from JSON file
    func loadResults(from path: String) throws -> BenchmarkResultsCollection {
        let data = try Data(contentsOf: URL(fileURLWithPath: path))
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return try decoder.decode(BenchmarkResultsCollection.self, from: data)
    }
    
    // MARK: - Private Helpers
    
    private static func targetLatencyFor(_ provider: AIProvider) -> Double {
        switch provider {
        case .ollama:
            return 100.0  // Local should be <100ms TTFT
        case .groq:
            return 150.0  // Cloud fast should be <150ms TTFT
        case .claude, .openAI:
            return 300.0  // Other cloud should be <300ms TTFT
        }
    }
    
    private func modelNameFor(_ provider: AIProvider) -> String {
        switch provider {
        case .ollama:
            return configuration.ollamaModel
        case .groq:
            return configuration.groqModel
        case .claude:
            return configuration.claudeModel
        case .openAI:
            return configuration.openAIModel
        }
    }
    
    private func estimateTokenCount(_ text: String) -> Int {
        // Rough estimation: 1 token ≈ 4 characters on average
        // More accurate would be to use the tokenizer, but this is a reasonable approximation
        return max(1, text.count / 4)
    }
}

// MARK: - Target Latencies
extension LLMBenchmarkRunner {
    static let targetLatencies: [String: Double] = [
        "Ollama (Local)": 100.0,           // <100ms TTFT
        "Groq (Fast Cloud)": 150.0,        // <150ms TTFT
        "OpenAI (Cloud)": 300.0,           // <300ms TTFT
        "Claude (Cloud)": 300.0,           // <300ms TTFT
        "Gemini (Cloud)": 300.0            // <300ms TTFT
    ]
}
