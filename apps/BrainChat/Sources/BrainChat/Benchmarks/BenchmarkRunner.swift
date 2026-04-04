import Foundation

/// Main benchmark orchestrator - runs all benchmarks and generates reports
class BenchmarkRunner {
    static let shared = BenchmarkRunner()
    
    private let config: BenchmarkConfig
    private let outputDir: URL
    private var results: [BenchmarkResult] = []
    private var startTime: Date?
    
    private let llmBenchmarks = LLMBenchmarks()
    private let voiceBenchmarks = VoiceBenchmarks()
    private let sttBenchmarks = STTBenchmarks()
    private let uiBenchmarks = UIBenchmarks()
    
    init(config: BenchmarkConfig = BenchmarkConfig()) {
        self.config = config
        
        // Setup output directory
        let benchmarkDir = URL(fileURLWithPath: "/Users/joe/brain/agentic-brain/apps/BrainChat/Sources/BrainChat/Benchmarks/benchmarks")
        self.outputDir = benchmarkDir
        
        // Create directory if needed
        try? FileManager.default.createDirectory(at: benchmarkDir, withIntermediateDirectories: true)
    }
    
    // MARK: - Main Benchmark Methods
    
    /// Run all benchmarks
    func runAllBenchmarks() async -> BenchmarkReport {
        startTime = Date()
        results = []
        
        print("🏃 BrainChat Benchmark Suite Starting...")
        print("📊 Configuration: \(config.testIterations) iterations, \(config.warmupIterations) warmups")
        print("⏱️  Regression threshold: \(config.regressionThreshold)%")
        print("")
        
        // Run all benchmark suites
        print("📱 Running LLM Benchmarks...")
        let llmResults = await llmBenchmarks.runBenchmarks()
        results.append(contentsOf: llmResults)
        
        print("🎤 Running Voice Engine Benchmarks...")
        let voiceResults = await voiceBenchmarks.runBenchmarks()
        results.append(contentsOf: voiceResults)
        
        print("🗣️  Running Speech-to-Text Benchmarks...")
        let sttResults = await sttBenchmarks.runBenchmarks()
        results.append(contentsOf: sttResults)
        
        print("🖥️  Running UI Performance Benchmarks...")
        let uiResults = await uiBenchmarks.runBenchmarks()
        results.append(contentsOf: uiResults)
        
        return generateReport()
    }
    
    /// Run specific category benchmarks
    func runCategory(_ category: BenchmarkConfig.Category) async -> BenchmarkReport {
        startTime = Date()
        results = []
        
        print("🏃 Running \(category.rawValue) Benchmarks...")
        print("")
        
        switch category {
        case .llm:
            let llmResults = await llmBenchmarks.runBenchmarks()
            results.append(contentsOf: llmResults)
        case .voice:
            let voiceResults = await voiceBenchmarks.runBenchmarks()
            results.append(contentsOf: voiceResults)
        case .stt:
            let sttResults = await sttBenchmarks.runBenchmarks()
            results.append(contentsOf: sttResults)
        case .ui:
            let uiResults = await uiBenchmarks.runBenchmarks()
            results.append(contentsOf: uiResults)
        case .network, .memory:
            print("⚠️  Category \(category.rawValue) not yet implemented")
        }
        
        return generateReport()
    }
    
    // MARK: - Report Generation
    
    private func generateReport() -> BenchmarkReport {
        let duration = Date().timeIntervalSince(startTime ?? Date())
        
        let summary = generateSummary()
        let report = BenchmarkReport(
            version: "1.0.0",
            appVersion: appVersion,
            platform: "macOS",
            date: Date(),
            duration: duration,
            results: results,
            summary: summary
        )
        
        // Print console report
        printConsoleReport(report)
        
        // Save reports
        saveJSONReport(report)
        saveHistoryEntry(report)
        
        return report
    }
    
    private func generateSummary() -> ReportSummary {
        let passedTests = results.count
        let failedTests = 0 // Can be tracked if benchmarks fail
        
        let categoryStats = Dictionary(grouping: results, by: { $0.category }).mapValues { results in
            CategoryStats(
                category: results.first?.category ?? "",
                testCount: results.count,
                avgLatencyMs: results.averageLatency,
                minLatencyMs: results.minLatency,
                maxLatencyMs: results.maxLatency
            )
        }
        
        let providerStats = Dictionary(grouping: results, by: { $0.provider }).mapValues { results in
            let avgTTFT = results.compactMap { $0.ttftMs }.isEmpty ? nil : results.compactMap { $0.ttftMs }.reduce(0, +) / Double(results.compactMap { $0.ttftMs }.count)
            let avgThroughput = results.compactMap { $0.throughput }.isEmpty ? nil : results.compactMap { $0.throughput }.reduce(0, +) / Double(results.compactMap { $0.throughput }.count)
            
            return ProviderStats(
                provider: results.first?.provider ?? "",
                testCount: results.count,
                avgLatencyMs: results.averageLatency,
                avgTTFTMs: avgTTFT,
                avgThroughput: avgThroughput
            )
        }
        
        return ReportSummary(
            totalTests: results.count,
            passedTests: passedTests,
            failedTests: failedTests,
            avgLatencyMs: results.averageLatency,
            minLatencyMs: results.minLatency,
            maxLatencyMs: results.maxLatency,
            categoryStats: categoryStats,
            providerStats: providerStats
        )
    }
    
    // MARK: - Console Output
    
    private func printConsoleReport(_ report: BenchmarkReport) {
        print("")
        print("=" * 80)
        print("📊 BrainChat Benchmark Report")
        print("=" * 80)
        print("📅 Date: \(formatDate(report.date))")
        print("⏱️  Duration: \(String(format: "%.2f", report.duration))s")
        print("🔢 Total Tests: \(report.summary.totalTests)")
        print("")
        
        // Summary statistics
        print("📈 Summary Statistics:")
        print("  Average Latency: \(String(format: "%.2f ms", report.summary.avgLatencyMs))")
        print("  Min Latency: \(String(format: "%.2f ms", report.summary.minLatencyMs))")
        print("  Max Latency: \(String(format: "%.2f ms", report.summary.maxLatencyMs))")
        print("  P50 Latency: \(String(format: "%.2f ms", results.p50Latency))")
        print("  P95 Latency: \(String(format: "%.2f ms", results.p95Latency))")
        print("  P99 Latency: \(String(format: "%.2f ms", results.p99Latency))")
        print("")
        
        // Category breakdown
        print("📂 Results by Category:")
        for (category, stats) in report.summary.categoryStats.sorted(by: { $0.key < $1.key }) {
            print("  \(category):")
            print("    Tests: \(stats.testCount)")
            print("    Avg: \(String(format: "%.2f ms", stats.avgLatencyMs))")
            print("    Range: \(String(format: "%.2f", stats.minLatencyMs))-\(String(format: "%.2f", stats.maxLatencyMs)) ms")
        }
        print("")
        
        // Provider breakdown
        print("🔌 Results by Provider:")
        for (provider, stats) in report.summary.providerStats.sorted(by: { $0.key < $1.key }) {
            print("  \(provider):")
            print("    Tests: \(stats.testCount)")
            print("    Avg Latency: \(String(format: "%.2f ms", stats.avgLatencyMs))")
            if let ttft = stats.avgTTFTMs {
                print("    Avg TTFT: \(String(format: "%.2f ms", ttft))")
            }
            if let throughput = stats.avgThroughput {
                print("    Avg Throughput: \(String(format: "%.2f tokens/sec", throughput))")
            }
        }
        print("")
        
        // Top 10 fastest
        print("⚡ Top 10 Fastest Tests:")
        let fastest = results.sorted { $0.latencyMs < $1.latencyMs }.prefix(10)
        for (index, result) in fastest.enumerated() {
            print("  \(index + 1). \(result.name) (\(result.provider)): \(String(format: "%.2f ms", result.latencyMs))")
        }
        print("")
        
        // Top 10 slowest
        print("🐢 Top 10 Slowest Tests:")
        let slowest = results.sorted { $0.latencyMs > $1.latencyMs }.prefix(10)
        for (index, result) in slowest.enumerated() {
            print("  \(index + 1). \(result.name) (\(result.provider)): \(String(format: "%.2f ms", result.latencyMs))")
        }
        print("")
        
        print("✅ Benchmark Complete!")
        print("📁 Results saved to: \(outputDir.path)")
        print("=" * 80)
        print("")
    }
    
    // MARK: - File Operations
    
    private func saveJSONReport(_ report: BenchmarkReport) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        
        do {
            let jsonData = try encoder.encode(report)
            
            // Save as current report
            let reportURL = outputDir.appendingPathComponent("benchmark-report.json")
            try jsonData.write(to: reportURL)
            print("✅ Saved: \(reportURL.lastPathComponent)")
            
            // Also save timestamped version
            let timestamp = ISO8601DateFormatter().string(from: report.date).replacingOccurrences(of: ":", with: "-")
            let timestampURL = outputDir.appendingPathComponent("benchmark-\(timestamp).json")
            try jsonData.write(to: timestampURL)
            
        } catch {
            print("❌ Error saving JSON report: \(error)")
        }
    }
    
    private func saveHistoryEntry(_ report: BenchmarkReport) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted]
        
        do {
            let jsonData = try encoder.encode(report)
            
            let timestamp = ISO8601DateFormatter().string(from: report.date).replacingOccurrences(of: ":", with: "-")
            let historyURL = outputDir.appendingPathComponent("history/\(timestamp).json")
            
            try FileManager.default.createDirectory(
                at: historyURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            
            try jsonData.write(to: historyURL)
            print("📁 Saved to history: \(timestamp).json")
            
        } catch {
            print("❌ Error saving history: \(error)")
        }
    }
    
    // MARK: - Comparison
    
    func compareWithBaseline(_ report: BenchmarkReport) async -> BenchmarkComparison? {
        let baselineURL = outputDir.appendingPathComponent("baseline.json")
        
        guard FileManager.default.fileExists(atPath: baselineURL.path) else {
            print("⚠️  No baseline found. Creating baseline from current report...")
            saveBaseline(report)
            return nil
        }
        
        do {
            let baselineData = try Data(contentsOf: baselineURL)
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            let baseline = try decoder.decode(BenchmarkReport.self, from: baselineData)
            
            let differences = computeDifferences(baseline: baseline, current: report)
            let regressions = differences.filter { $0.isRegression && abs($0.percentChange) > config.regressionThreshold }
            
            let comparison = BenchmarkComparison(
                baseline: baseline,
                current: report,
                differences: differences,
                regressions: regressions
            )
            
            printComparisonReport(comparison)
            
            return comparison
        } catch {
            print("❌ Error loading baseline: \(error)")
            return nil
        }
    }
    
    private func saveBaseline(_ report: BenchmarkReport) {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        
        do {
            let jsonData = try encoder.encode(report)
            let baselineURL = outputDir.appendingPathComponent("baseline.json")
            try jsonData.write(to: baselineURL)
            print("✅ Baseline created: \(baselineURL.lastPathComponent)")
        } catch {
            print("❌ Error saving baseline: \(error)")
        }
    }
    
    private func computeDifferences(
        baseline: BenchmarkReport,
        current: BenchmarkReport
    ) -> [BenchmarkDifference] {
        var differences: [BenchmarkDifference] = []
        
        let baselineMap = Dictionary(grouping: baseline.results) { "\($0.name):\($0.provider)" }
        let currentMap = Dictionary(grouping: current.results) { "\($0.name):\($0.provider)" }
        
        for (key, currentResults) in currentMap {
            guard let baselineResults = baselineMap[key], !baselineResults.isEmpty else { continue }
            
            let baselineLatency = baselineResults[0].latencyMs
            let currentLatency = currentResults[0].latencyMs
            let percentChange = ((currentLatency - baselineLatency) / baselineLatency) * 100
            
            let difference = BenchmarkDifference(
                testName: currentResults[0].name,
                provider: currentResults[0].provider,
                baselineLatencyMs: baselineLatency,
                currentLatencyMs: currentLatency,
                percentChange: percentChange,
                isRegression: currentLatency > baselineLatency
            )
            
            differences.append(difference)
        }
        
        return differences
    }
    
    private func printComparisonReport(_ comparison: BenchmarkComparison) {
        print("")
        print("=" * 80)
        print("📊 Benchmark Comparison Report")
        print("=" * 80)
        print("📅 Baseline: \(formatDate(comparison.baseline.date))")
        print("📅 Current: \(formatDate(comparison.current.date))")
        print("")
        
        if comparison.hasRegressions {
            print("⚠️  REGRESSIONS DETECTED!")
            print("")
            for regression in comparison.regressions {
                print("  ❌ \(regression.testName) (\(regression.provider))")
                print("     Baseline: \(String(format: "%.2f ms", regression.baselineLatencyMs))")
                print("     Current: \(String(format: "%.2f ms", regression.currentLatencyMs))")
                print("     Change: \(String(format: "+%.2f%%", regression.actualRegression))")
                print("     Message: \(regression.message)")
            }
        } else {
            print("✅ No regressions detected!")
        }
        print("")
        
        print("📈 Overall Improvement: \(String(format: "%.2f%%", comparison.improvementPercentage))")
        print("")
        
        print("📊 Changes (Top 10):")
        let topChanges = comparison.differences.sorted { abs($0.percentChange) > abs($1.percentChange) }.prefix(10)
        for (index, diff) in topChanges.enumerated() {
            let direction = diff.isRegression ? "↑" : "↓"
            print("  \(index + 1). \(direction) \(diff.testName) (\(diff.provider)): \(diff.formattedChange)")
        }
        print("")
        
        print("=" * 80)
    }
    
    // MARK: - Helpers
    
    private var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "Unknown"
    }
    
    private func formatDate(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .medium
        return formatter.string(from: date)
    }
}

// String helper for repeating characters
private extension String {
    static func * (lhs: String, rhs: Int) -> String {
        return String(repeating: lhs, count: rhs)
    }
}
