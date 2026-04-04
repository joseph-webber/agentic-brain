import Foundation

// MARK: - Core Benchmark Models

/// Represents a single benchmark measurement
struct BenchmarkResult: Codable, Identifiable {
    let id: String
    let category: String
    let name: String
    let provider: String
    let latencyMs: Double
    let throughput: Double?
    let ttftMs: Double? // Time to First Token (for LLMs)
    let accuracy: Double? // For STT engines
    let timestamp: Date
    let metadata: [String: String]?
    
    var formattedLatency: String {
        String(format: "%.2f ms", latencyMs)
    }
    
    var formattedThroughput: String {
        guard let throughput = throughput else { return "N/A" }
        return String(format: "%.2f tokens/sec", throughput)
    }
    
    var formattedTTFT: String {
        guard let ttft = ttftMs else { return "N/A" }
        return String(format: "%.2f ms", ttft)
    }
}

/// Aggregated benchmark report
struct BenchmarkReport: Codable {
    let version: String
    let appVersion: String
    let platform: String
    let date: Date
    let duration: TimeInterval
    let results: [BenchmarkResult]
    let summary: ReportSummary
    
    var resultsByCategory: [String: [BenchmarkResult]] {
        Dictionary(grouping: results, by: { $0.category })
    }
    
    var resultsByProvider: [String: [BenchmarkResult]] {
        Dictionary(grouping: results, by: { $0.provider })
    }
}

/// Summary statistics for a report
struct ReportSummary: Codable {
    let totalTests: Int
    let passedTests: Int
    let failedTests: Int
    let avgLatencyMs: Double
    let minLatencyMs: Double
    let maxLatencyMs: Double
    let categoryStats: [String: CategoryStats]
    let providerStats: [String: ProviderStats]
}

/// Category-level statistics
struct CategoryStats: Codable {
    let category: String
    let testCount: Int
    let avgLatencyMs: Double
    let minLatencyMs: Double
    let maxLatencyMs: Double
}

/// Provider-level statistics
struct ProviderStats: Codable {
    let provider: String
    let testCount: Int
    let avgLatencyMs: Double
    let avgTTFTMs: Double? // For LLM providers
    let avgThroughput: Double? // For LLM providers
}

/// Benchmark comparison between two reports
struct BenchmarkComparison: Codable {
    let baseline: BenchmarkReport
    let current: BenchmarkReport
    let differences: [BenchmarkDifference]
    let regressions: [BenchmarkRegression]
    
    var hasRegressions: Bool {
        !regressions.isEmpty
    }
    
    var improvementPercentage: Double {
        guard !baseline.results.isEmpty, !current.results.isEmpty else { return 0 }
        let baselineAvg = baseline.summary.avgLatencyMs
        let currentAvg = current.summary.avgLatencyMs
        return ((baselineAvg - currentAvg) / baselineAvg) * 100
    }
}

/// Individual benchmark difference
struct BenchmarkDifference: Codable {
    let testName: String
    let provider: String
    let baselineLatencyMs: Double
    let currentLatencyMs: Double
    let percentChange: Double
    let isRegression: Bool
    
    var direction: String {
        isRegression ? "↑ REGRESSION" : "↓ IMPROVEMENT"
    }
    
    var formattedChange: String {
        String(format: "%+.2f%%", percentChange)
    }
}

/// Regression details
struct BenchmarkRegression: Codable {
    let testName: String
    let provider: String
    let threshold: Double // Acceptable regression threshold in percent
    let actualRegression: Double
    let baselineLatencyMs: Double
    let currentLatencyMs: Double
    let message: String
}

// MARK: - Benchmark Configuration

/// Configuration for benchmark runs
struct BenchmarkConfig {
    let warmupIterations: Int = 3
    let testIterations: Int = 10
    let regressionThreshold: Double = 10.0 // 10% regression threshold
    let timeoutSeconds: TimeInterval = 60
    let enableDetailedLogging: Bool = false
    
    enum Category: String {
        case llm = "LLM Providers"
        case voice = "Voice Engines"
        case stt = "Speech-to-Text"
        case ui = "UI Performance"
        case network = "Network"
        case memory = "Memory"
    }
}

// MARK: - Benchmark Errors

enum BenchmarkError: LocalizedError {
    case timeout
    case providerUnavailable(String)
    case invalidConfiguration
    case measurementFailed(String)
    case fileIOError(String)
    
    var errorDescription: String? {
        switch self {
        case .timeout:
            return "Benchmark test timed out"
        case .providerUnavailable(let provider):
            return "Provider not available: \(provider)"
        case .invalidConfiguration:
            return "Invalid benchmark configuration"
        case .measurementFailed(let reason):
            return "Measurement failed: \(reason)"
        case .fileIOError(let reason):
            return "File I/O error: \(reason)"
        }
    }
}

// MARK: - Benchmark Statistics Helpers

extension Array where Element == BenchmarkResult {
    var averageLatency: Double {
        guard !isEmpty else { return 0 }
        return map { $0.latencyMs }.reduce(0, +) / Double(count)
    }
    
    var minLatency: Double {
        map { $0.latencyMs }.min() ?? 0
    }
    
    var maxLatency: Double {
        map { $0.latencyMs }.max() ?? 0
    }
    
    var p50Latency: Double {
        let sorted = map { $0.latencyMs }.sorted()
        guard !sorted.isEmpty else { return 0 }
        return sorted[sorted.count / 2]
    }
    
    var p95Latency: Double {
        let sorted = map { $0.latencyMs }.sorted()
        guard !sorted.isEmpty else { return 0 }
        let index = Int(Double(sorted.count) * 0.95)
        return sorted[min(index, sorted.count - 1)]
    }
    
    var p99Latency: Double {
        let sorted = map { $0.latencyMs }.sorted()
        guard !sorted.isEmpty else { return 0 }
        let index = Int(Double(sorted.count) * 0.99)
        return sorted[min(index, sorted.count - 1)]
    }
}
