# BrainChat Benchmark Suite - Deployment & Integration Guide

## Quick Integration (5 minutes)

### Step 1: Copy Benchmarks Folder
Already created at:
```
/Users/joe/brain/agentic-brain/apps/BrainChat/Sources/BrainChat/Benchmarks/
```

No additional setup needed - pure Swift, no dependencies!

### Step 2: Import in Your Code
```swift
import Foundation

// In your view or view model:
let runner = BenchmarkRunner.shared
let report = await runner.runAllBenchmarks()
```

### Step 3: Add to Settings (Optional)
```swift
struct SettingsView: View {
    @State private var isRunningBenchmarks = false
    
    var body: some View {
        VStack {
            Button(action: {
                isRunningBenchmarks = true
                Task {
                    let runner = BenchmarkRunner.shared
                    let report = await runner.runAllBenchmarks()
                    print("✅ Benchmarks complete")
                }
            }) {
                if isRunningBenchmarks {
                    ProgressView()
                } else {
                    Label("Run Benchmarks", systemImage: "speedometer")
                }
            }
            .disabled(isRunningBenchmarks)
        }
    }
}
```

## Full Integration Guide

### Integration Points

#### 1. App Startup (Debug Mode)
```swift
@main
struct BrainChatApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .onAppear {
                    #if DEBUG
                    // Run benchmarks on startup in debug mode
                    Task {
                        let runner = BenchmarkRunner.shared
                        let report = await runner.runAllBenchmarks()
                    }
                    #endif
                }
        }
    }
}
```

#### 2. Settings Menu
```swift
struct SettingsView: View {
    @State private var benchmarkResults: String = ""
    @State private var showBenchmarkResults = false
    
    var body: some View {
        List {
            Section("Performance") {
                Button("Run Performance Benchmarks") {
                    Task {
                        let runner = BenchmarkRunner.shared
                        let report = await runner.runAllBenchmarks()
                        benchmarkResults = formatResults(report)
                        showBenchmarkResults = true
                    }
                }
                
                Button("Run LLM Benchmarks") {
                    Task {
                        let runner = BenchmarkRunner.shared
                        let report = await runner.runCategory(.llm)
                        benchmarkResults = formatResults(report)
                        showBenchmarkResults = true
                    }
                }
                
                Button("Compare with Baseline") {
                    Task {
                        let runner = BenchmarkRunner.shared
                        let report = await runner.runAllBenchmarks()
                        if let comparison = await runner.compareWithBaseline(report) {
                            if comparison.hasRegressions {
                                benchmarkResults = "⚠️ REGRESSIONS DETECTED"
                            } else {
                                benchmarkResults = "✅ No regressions"
                            }
                            showBenchmarkResults = true
                        }
                    }
                }
            }
        }
        .sheet(isPresented: $showBenchmarkResults) {
            Text(benchmarkResults)
                .padding()
        }
    }
    
    private func formatResults(_ report: BenchmarkReport) -> String {
        """
        📊 Benchmark Report
        Date: \(DateFormatter.localizedString(from: report.date, dateStyle: .medium, timeStyle: .medium))
        Tests: \(report.results.count)
        Duration: \(String(format: "%.1f", report.duration))s
        
        📈 Summary:
        Avg Latency: \(String(format: "%.1f ms", report.summary.avgLatencyMs))
        Min: \(String(format: "%.1f ms", report.summary.minLatencyMs))
        Max: \(String(format: "%.1f ms", report.summary.maxLatencyMs))
        """
    }
}
```

#### 3. Menu Bar Option (macOS)
```swift
@main
struct BrainChatApp: App {
    var body: some Scene {
        MenuBarExtra("BrainChat", systemImage: "brain.head.profile") {
            VStack {
                Button("Run Benchmarks") {
                    Task {
                        let runner = BenchmarkRunner.shared
                        let report = await runner.runAllBenchmarks()
                    }
                }
                
                Button("Show Results") {
                    // Open benchmarks folder
                    NSWorkspace.shared.open(
                        URL(fileURLWithPath: "/Users/joe/brain/agentic-brain/apps/BrainChat/Sources/BrainChat/Benchmarks/benchmarks")
                    )
                }
                
                Divider()
                
                Button("Quit") {
                    NSApplication.shared.terminate(nil)
                }
            }
            .padding()
        }
    }
}
```

#### 4. Debug Menu
```swift
struct DebugMenu: View {
    var body: some View {
        List {
            Section("Benchmarks") {
                NavigationLink("Run All", destination: BenchmarkRunnerView())
                NavigationLink("LLM Only", destination: BenchmarkRunnerView(category: .llm))
                NavigationLink("Voice Only", destination: BenchmarkRunnerView(category: .voice))
                NavigationLink("STT Only", destination: BenchmarkRunnerView(category: .stt))
                NavigationLink("UI Only", destination: BenchmarkRunnerView(category: .ui))
            }
            
            Section("Analysis") {
                NavigationLink("Performance Analysis", destination: PerformanceAnalysisView())
                NavigationLink("Trend Analysis", destination: TrendAnalysisView())
                NavigationLink("Compare to Baseline", destination: ComparisonView())
            }
        }
    }
}
```

### CI/CD Integration

#### GitHub Actions
```yaml
name: Performance Benchmarks

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  benchmark:
    runs-on: macos-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Swift
      uses: swift-actions/setup-swift@v1
      with:
        swift-version: '5.9'
    
    - name: Run Benchmarks
      run: |
        cd /Users/joe/brain/agentic-brain/apps/BrainChat
        swift run BrainChat --benchmark all --json
    
    - name: Upload Results
      uses: actions/upload-artifact@v3
      with:
        name: benchmark-results
        path: Sources/BrainChat/Benchmarks/benchmarks/
    
    - name: Compare with Baseline
      run: |
        cd /Users/joe/brain/agentic-brain/apps/BrainChat
        swift run BrainChat --benchmark compare --baseline
    
    - name: Fail on Regression
      if: failure()
      run: exit 1
```

#### Azure Pipelines
```yaml
trigger:
  - main

pool:
  vmImage: 'macOS-latest'

steps:
- task: SwiftBuild@1
  inputs:
    projectPath: $(Build.SourcesDirectory)

- task: Bash@3
  displayName: 'Run Benchmarks'
  inputs:
    targetType: 'inline'
    script: |
      cd $(Build.SourcesDirectory)
      swift run benchmarks --all --json --output results.json

- task: PublishBuildArtifacts@1
  inputs:
    pathToPublish: '$(Build.SourcesDirectory)/results.json'
    artifactName: 'benchmark-results'

- task: Bash@3
  displayName: 'Compare Results'
  inputs:
    targetType: 'inline'
    script: |
      cd $(Build.SourcesDirectory)
      swift run benchmarks --compare baseline.json --fail-on-regression
```

## Monitoring Performance

### Automated Monitoring
```swift
class PerformanceMonitor {
    static let shared = PerformanceMonitor()
    
    private var timer: Timer?
    
    func startMonitoring(interval: TimeInterval = 3600) { // 1 hour
        timer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { _ in
            Task {
                let runner = BenchmarkRunner.shared
                let report = await runner.runAllBenchmarks()
                
                // Log to analytics
                self.logMetrics(report)
                
                // Check for regressions
                if let comparison = await runner.compareWithBaseline(report) {
                    if comparison.hasRegressions {
                        self.alertRegressions(comparison)
                    }
                }
            }
        }
    }
    
    func stopMonitoring() {
        timer?.invalidate()
    }
    
    private func logMetrics(_ report: BenchmarkReport) {
        // Send to analytics service
        print("📊 Logged metrics: \(report.results.count) tests")
    }
    
    private func alertRegressions(_ comparison: BenchmarkComparison) {
        // Send alert/notification
        print("⚠️ Performance regressions detected")
    }
}
```

### Manual Review
```swift
// Check results periodically
Task {
    let url = URL(fileURLWithPath: "/Users/joe/brain/agentic-brain/apps/BrainChat/Sources/BrainChat/Benchmarks/benchmarks/history")
    let files = try FileManager.default.contentsOfDirectory(at: url, includingPropertiesForKeys: nil)
    
    // Analyze trends
    for file in files.sorted().suffix(10) {
        // Review performance
    }
}
```

## Performance Targets

Set these before deployment:

```swift
let performanceTargets = [
    "LLM Request": 500.0,        // ms
    "Voice TTS": 200.0,          // ms
    "STT": 1000.0,               // ms
    "View Load": 200.0,          // ms
    "Scroll FPS": 60.0,          // fps
]
```

## Troubleshooting

### Benchmarks Not Running
```swift
// Check if providers are available
do {
    let runner = BenchmarkRunner.shared
    let report = await runner.runAllBenchmarks()
    print("✅ Success: \(report.results.count) tests")
} catch {
    print("❌ Error: \(error)")
    // Check provider connectivity
    // Verify local services running
}
```

### High Variance
```swift
// Use custom config for more stable results
var config = BenchmarkConfig()
config.warmupIterations = 10  // More warmups
config.testIterations = 20    // More iterations
config.enableDetailedLogging = true

let runner = BenchmarkRunner(config: config)
let report = await runner.runAllBenchmarks()
```

### Memory Issues
```swift
// Run categories separately
let llmReport = await runner.runCategory(.llm)
let voiceReport = await runner.runCategory(.voice)
let sttReport = await runner.runCategory(.stt)
let uiReport = await runner.runCategory(.ui)
```

## Maintenance

### Weekly
- Review benchmark results
- Check for trends
- Monitor for regressions

### Monthly
- Analyze 4-week trends
- Update baselines if needed
- Identify optimization opportunities

### Quarterly
- Comprehensive performance review
- Set new targets
- Plan optimizations

## Support Resources

1. **README.md** - Quick start guide
2. **BENCHMARKING.md** - Complete documentation
3. **BenchmarkExamples.swift** - 10 usage examples
4. **BenchmarkModels.swift** - Data structure reference
5. **BenchmarkRunner.swift** - Core implementation

## Next Steps

1. ✅ Copy Benchmarks folder (done)
2. ⬜ Integrate into BrainChat app
3. ⬜ Establish baseline measurements
4. ⬜ Add to CI/CD pipeline
5. ⬜ Set performance targets
6. ⬜ Monitor trends monthly
7. ⬜ Optimize based on results

## Version History

- **1.0.0** (Jan 2024) - Initial release
  - LLM provider benchmarks
  - Voice engine benchmarks
  - STT benchmarks
  - UI performance benchmarks
  - Regression detection
  - Historical tracking
  - CI/CD integration ready

---

**Status**: Production Ready  
**Dependencies**: None (pure Swift)  
**Last Updated**: January 2024  
**Maintenance**: Quarterly reviews recommended
