import Foundation

/// Example integration of benchmarking into BrainChat app
/// This shows various ways to use the benchmark suite

class BenchmarkExamples {
    
    // MARK: - Example 1: Run All Benchmarks
    
    /// Run complete benchmark suite
    static func runFullBenchmarks() async {
        print("🏃 Starting full benchmark suite...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runAllBenchmarks()
        
        print("✅ Benchmarks complete!")
        print("📁 Results: \(report.results.count) tests")
        print("⏱️  Duration: \(String(format: "%.2f", report.duration))s")
    }
    
    // MARK: - Example 2: Category-Specific Benchmarks
    
    /// Run only LLM provider benchmarks
    static func benchmarkLLMProviders() async {
        print("📊 Benchmarking LLM Providers...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runCategory(.llm)
        
        // Print results
        for result in report.results {
            print("\(result.name): \(String(format: "%.1f", result.latencyMs))ms")
        }
    }
    
    /// Run only voice engine benchmarks
    static func benchmarkVoiceEngines() async {
        print("🎤 Benchmarking Voice Engines...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runCategory(.voice)
        
        // Find fastest voice engine
        if let fastest = report.results.min(by: { $0.latencyMs < $1.latencyMs }) {
            print("⚡ Fastest: \(fastest.provider) (\(String(format: "%.1f", fastest.latencyMs))ms)")
        }
    }
    
    /// Run only UI performance benchmarks
    static func benchmarkUIPerformance() async {
        print("🖥️  Benchmarking UI Performance...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runCategory(.ui)
        
        // Check for performance issues
        let slowTests = report.results.filter { $0.latencyMs > 100 }
        if !slowTests.isEmpty {
            print("⚠️  Slow UI operations detected:")
            for test in slowTests {
                print("  - \(test.name): \(String(format: "%.1f", test.latencyMs))ms")
            }
        } else {
            print("✅ All UI operations within acceptable latency")
        }
    }
    
    // MARK: - Example 3: Regression Detection
    
    /// Run benchmarks and detect regressions
    static func detectRegressions() async {
        print("🔍 Running benchmarks with regression detection...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runAllBenchmarks()
        
        // Compare with baseline
        if let comparison = await runner.compareWithBaseline(report) {
            if comparison.hasRegressions {
                print("❌ REGRESSIONS DETECTED!")
                for regression in comparison.regressions {
                    print("  \(regression.testName):")
                    print("    - Change: \(String(format: "+%.1f%%", regression.actualRegression))")
                    print("    - Message: \(regression.message)")
                }
            } else {
                print("✅ No regressions detected")
                print("📈 Overall improvement: \(String(format: "+%.1f%%", comparison.improvementPercentage))")
            }
        }
    }
    
    // MARK: - Example 4: Performance Analysis
    
    /// Analyze performance and identify bottlenecks
    static func analyzePerformance() async {
        print("📊 Analyzing performance...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runAllBenchmarks()
        
        // Top slowest operations
        print("\n🐢 Top 10 Slowest Operations:")
        let slowest = report.results.sorted { $0.latencyMs > $1.latencyMs }.prefix(10)
        for (index, result) in slowest.enumerated() {
            print("  \(index + 1). \(result.name)")
            print("     Provider: \(result.provider)")
            print("     Latency: \(String(format: "%.1f ms", result.latencyMs))")
            if let throughput = result.throughput {
                print("     Throughput: \(String(format: "%.1f ops/s", throughput))")
            }
        }
        
        // Category analysis
        print("\n📂 Performance by Category:")
        let byCategory = Dictionary(grouping: report.results) { $0.category }
        for (category, results) in byCategory.sorted(by: { $0.key < $1.key }) {
            let avg = results.averageLatency
            let p95 = results.p95Latency
            print("  \(category):")
            print("    - Avg: \(String(format: "%.1f ms", avg))")
            print("    - P95: \(String(format: "%.1f ms", p95))")
            print("    - Count: \(results.count)")
        }
        
        // Provider analysis
        print("\n🔌 Performance by Provider:")
        let byProvider = Dictionary(grouping: report.results) { $0.provider }
        for (provider, results) in byProvider.sorted(by: { $0.key < $1.key }) {
            let avg = results.averageLatency
            print("  \(provider):")
            print("    - Avg: \(String(format: "%.1f ms", avg))")
            print("    - Tests: \(results.count)")
        }
    }
    
    // MARK: - Example 5: Custom Configuration
    
    /// Run benchmarks with custom configuration
    static func runWithCustomConfig() async {
        print("⚙️  Running with custom configuration...")
        
        // Create custom config for strict testing
        var config = BenchmarkConfig()
        config.testIterations = 20        // More iterations for stability
        config.warmupIterations = 5       // More warmups
        config.regressionThreshold = 5.0  // Stricter threshold
        config.enableDetailedLogging = true
        
        let runner = BenchmarkRunner(config: config)
        let report = await runner.runAllBenchmarks()
        
        print("✅ Completed with \(report.results.count) tests")
        print("📊 Avg latency: \(String(format: "%.1f ms", report.summary.avgLatencyMs))")
    }
    
    // MARK: - Example 6: Scheduled Benchmarking
    
    /// Schedule benchmarks to run periodically
    static func schedulePeriodicBenchmarking() {
        print("📅 Setting up periodic benchmarking...")
        
        // Run benchmarks every hour
        Timer.scheduledTimer(withTimeInterval: 3600, repeats: true) { _ in
            Task {
                let runner = BenchmarkRunner.shared
                let report = await runner.runAllBenchmarks()
                
                // Log results
                print("📊 Periodic benchmark: \(report.results.count) tests in \(String(format: "%.1f", report.duration))s")
                
                // Check for issues
                if report.summary.avgLatencyMs > 500 {
                    print("⚠️  Average latency elevated: \(String(format: "%.1f ms", report.summary.avgLatencyMs))")
                }
            }
        }
    }
    
    // MARK: - Example 7: Provider Comparison
    
    /// Compare performance across different providers
    static func compareProviders() async {
        print("🔀 Comparing providers...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runCategory(.llm)
        
        let byProvider = Dictionary(grouping: report.results) { $0.provider }
        
        print("\nProvider Comparison (LLM):")
        print("Provider\t\tLatency\t\tTTFT\t\tThroughput")
        print("─" * 60)
        
        for (provider, results) in byProvider.sorted(by: { $0.key < $1.key }) {
            let avgLatency = results.averageLatency
            let avgTTFT = results.compactMap { $0.ttftMs }.isEmpty ? 0 :
                results.compactMap { $0.ttftMs }.reduce(0, +) / Double(results.compactMap { $0.ttftMs }.count)
            let avgThroughput = results.compactMap { $0.throughput }.isEmpty ? 0 :
                results.compactMap { $0.throughput }.reduce(0, +) / Double(results.compactMap { $0.throughput }.count)
            
            print("\(provider)\t\t\(String(format: "%.0f ms", avgLatency))\t\(String(format: "%.0f ms", avgTTFT))\t\(String(format: "%.1f", avgThroughput))")
        }
    }
    
    // MARK: - Example 8: Export Results
    
    /// Export benchmark results for external analysis
    static func exportResults() async {
        print("📤 Exporting results...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runAllBenchmarks()
        
        // Results are automatically saved to:
        // - benchmark-report.json (latest)
        // - benchmark-YYYY-MM-DD...json (timestamped)
        // - history/*.json (all historical)
        
        print("✅ Results saved to:")
        print("   /benchmarks/benchmark-report.json")
        print("   /benchmarks/history/")
        
        // Can also manually encode for external tools
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        if let json = try? encoder.encode(report),
           let jsonString = String(data: json, encoding: .utf8) {
            print("\n✅ JSON Ready for export (\(json.count) bytes)")
        }
    }
    
    // MARK: - Example 9: Performance Alerts
    
    /// Check for performance degradation
    static func checkPerformanceAlerts() async {
        print("🚨 Checking performance alerts...")
        
        let runner = BenchmarkRunner.shared
        let report = await runner.runAllBenchmarks()
        
        // Check against targets
        let targets: [(String, Double)] = [
            ("LLM Latency", 500),
            ("Voice Latency", 150),
            ("STT Latency", 1000),
            ("UI Latency", 200)
        ]
        
        var alerts: [String] = []
        
        for (name, target) in targets {
            let matching = report.results.filter { $0.name.contains(name.split(separator: " ")[0]) }
            let exceeding = matching.filter { $0.latencyMs > target }
            
            if !exceeding.isEmpty {
                alerts.append("⚠️  \(name) target exceeded: \(exceeding.count) tests > \(target)ms")
            }
        }
        
        if alerts.isEmpty {
            print("✅ All performance targets met!")
        } else {
            for alert in alerts {
                print(alert)
            }
        }
    }
    
    // MARK: - Example 10: Trend Analysis
    
    /// Analyze performance trends over time
    static func analyzeTrends() {
        print("📈 Analyzing performance trends...")
        
        let benchmarkDir = URL(fileURLWithPath: "/Users/joe/brain/agentic-brain/apps/BrainChat/Sources/BrainChat/Benchmarks/benchmarks/history")
        
        do {
            let files = try FileManager.default.contentsOfDirectory(at: benchmarkDir, includingPropertiesForKeys: nil)
                .filter { $0.pathExtension == "json" }
                .sorted { $0.lastPathComponent < $1.lastPathComponent }
            
            print("📊 Found \(files.count) historical reports")
            
            let decoder = JSONDecoder()
            decoder.dateDecodingStrategy = .iso8601
            
            var reports: [BenchmarkReport] = []
            
            for file in files.suffix(10) {  // Last 10 reports
                if let data = try? Data(contentsOf: file),
                   let report = try? decoder.decode(BenchmarkReport.self, from: data) {
                    reports.append(report)
                }
            }
            
            if reports.count >= 2 {
                // Compare first and last
                let first = reports.first!
                let last = reports.last!
                
                let improvement = ((first.summary.avgLatencyMs - last.summary.avgLatencyMs) / first.summary.avgLatencyMs) * 100
                
                if improvement > 0 {
                    print("✅ Performance improving: \(String(format: "+%.1f%%", improvement))")
                } else if improvement < -5 {
                    print("⚠️  Performance degrading: \(String(format: "%.1f%%", improvement))")
                } else {
                    print("➡️  Performance stable: \(String(format: "%+.1f%%", improvement))")
                }
            }
            
        } catch {
            print("❌ Error analyzing trends: \(error)")
        }
    }
}

// MARK: - Usage in BrainChat App

/// Integration points for BrainChat app:
/// 
/// 1. On app startup:
///    ```swift
///    if isDebugMode {
///        Task { await BenchmarkExamples.runFullBenchmarks() }
///    }
///    ```
///
/// 2. In Settings view:
///    ```swift
///    Button("Run Benchmarks") {
///        Task { await BenchmarkExamples.runFullBenchmarks() }
///    }
///    ```
///
/// 3. In CI/CD pipeline:
///    ```swift
///    Task { await BenchmarkExamples.detectRegressions() }
///    ```
///
/// 4. For performance monitoring:
///    ```swift
///    BenchmarkExamples.schedulePeriodicBenchmarking()
///    ```
///
/// 5. For debugging specific issues:
///    ```swift
///    Task { await BenchmarkExamples.analyzePerformance() }
///    ```

// String helper
private extension String {
    static func * (lhs: String, rhs: Int) -> String {
        return String(repeating: lhs, count: rhs)
    }
}
