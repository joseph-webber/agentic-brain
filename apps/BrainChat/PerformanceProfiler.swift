import Foundation
import os.log

/// Performance profiling and measurement utility for BrainChat
/// Tracks startup time, memory usage, UI responsiveness, and custom metrics
final class PerformanceProfiler: Sendable {
    static let shared = PerformanceProfiler()
    
    private let logger = Logger(subsystem: "com.brainchat.performance", category: "Profiler")
    private let metrics = OSSignpostID(log: .default)
    private var startTimes: [String: Date] = [:]
    private var measurements: [String: [TimeInterval]] = [:]
    private var memorySnapshots: [String: (timestamp: Date, bytes: UInt64)] = [:]
    
    // MARK: - Initialization Tracking
    
    /// Mark the beginning of an initialization phase
    func markInitStart(_ phase: String) {
        let timestamp = Date()
        startTimes[phase] = timestamp
        os_signpost(.begin, log: .default, name: "InitPhase", signpostID: metrics, "%{public}s", phase)
    }
    
    /// Mark the end of an initialization phase and log the duration
    func markInitEnd(_ phase: String) -> TimeInterval {
        guard let startTime = startTimes.removeValue(forKey: phase) else {
            logger.warning("No start time recorded for phase: \(phase)")
            return 0
        }
        
        let duration = Date().timeIntervalSince(startTime)
        os_signpost(.end, log: .default, name: "InitPhase", signpostID: metrics, "%{public}s: %.1fms", phase, duration * 1000)
        
        var durations = measurements[phase] ?? []
        durations.append(duration)
        measurements[phase] = durations
        
        logger.log("✓ \(phase): \(String(format: "%.1f", duration * 1000))ms")
        
        if duration > 0.1 {
            logger.warning("⚠️ Slow initialization phase: \(phase) took \(String(format: "%.1f", duration * 1000))ms")
        }
        
        return duration
    }
    
    // MARK: - Memory Profiling
    
    /// Capture current memory usage snapshot
    func captureMemorySnapshot(_ label: String) -> UInt64 {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info>.size)/4
        
        let result = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: 1) { ptr in
                task_info(
                    mach_task_self_,
                    task_flavor_t(TASK_VM_INFO),
                    ptr,
                    &count
                )
            }
        }
        
        guard result == KERN_SUCCESS else {
            logger.error("Failed to get task info")
            return 0
        }
        
        let memoryBytes = UInt64(info.phys_footprint)
        let memoryMB = Double(memoryBytes) / (1024 * 1024)
        
        memorySnapshots[label] = (Date(), memoryBytes)
        
        logger.log("📊 Memory [\(label)]: \(String(format: "%.1f", memoryMB))MB")
        
        if memoryBytes > 100 * 1024 * 1024 {
            logger.warning("⚠️ High memory usage: \(String(format: "%.1f", memoryMB))MB")
        }
        
        return memoryBytes
    }
    
    /// Get memory delta between two snapshots
    func memoryDelta(from: String, to: String) -> Int64? {
        guard let fromSnapshot = memorySnapshots[from],
              let toSnapshot = memorySnapshots[to] else {
            return nil
        }
        
        return Int64(toSnapshot.bytes) - Int64(fromSnapshot.bytes)
    }
    
    // MARK: - UI Responsiveness Tracking
    
    /// Measure and track UI frame duration
    func trackFrameDuration(_ duration: TimeInterval, operation: String) {
        let durationMs = duration * 1000
        
        if durationMs > 16.67 {  // 60fps threshold
            logger.warning("⚠️ Dropped frame in \(operation): \(String(format: "%.1f", durationMs))ms")
        }
        
        var frameTimes = measurements[operation] ?? []
        frameTimes.append(duration)
        measurements[operation] = frameTimes
    }
    
    // MARK: - Custom Measurements
    
    /// Start measuring a custom operation
    func measureStart(_ operation: String) -> Date {
        let timestamp = Date()
        startTimes[operation] = timestamp
        return timestamp
    }
    
    /// End measuring a custom operation and return duration
    func measureEnd(_ operation: String) -> TimeInterval {
        guard let startTime = startTimes.removeValue(forKey: operation) else {
            logger.warning("No start time recorded for operation: \(operation)")
            return 0
        }
        
        let duration = Date().timeIntervalSince(startTime)
        var durations = measurements[operation] ?? []
        durations.append(duration)
        measurements[operation] = durations
        
        return duration
    }
    
    // MARK: - Reporting
    
    /// Generate performance report
    func generateReport() -> PerformanceReport {
        var report = PerformanceReport(
            timestamp: Date(),
            startupMetrics: [:],
            memoryMetrics: [:],
            uiMetrics: [:]
        )
        
        // Collect startup metrics
        for (phase, durations) in measurements where phase.contains("Init") || phase.contains("startup") {
            report.startupMetrics[phase] = PhaseMeasurement(
                min: durations.min() ?? 0,
                max: durations.max() ?? 0,
                average: durations.isEmpty ? 0 : durations.reduce(0, +) / Double(durations.count),
                count: durations.count
            )
        }
        
        // Collect memory metrics
        for (label, snapshot) in memorySnapshots {
            let mb = Double(snapshot.bytes) / (1024 * 1024)
            report.memoryMetrics[label] = mb
        }
        
        // Collect UI metrics
        for (operation, durations) in measurements where operation.contains("UI") || operation.contains("Frame") {
            let droppedFrames = durations.filter { $0 > 0.01667 }.count
            report.uiMetrics[operation] = UIMetric(
                averageMs: (durations.reduce(0, +) / Double(durations.count)) * 1000,
                droppedFrames: droppedFrames,
                totalFrames: durations.count
            )
        }
        
        return report
    }
    
    /// Print detailed performance summary
    func printSummary() {
        let report = generateReport()
        
        print("\n" + String(repeating: "=", count: 60))
        print("PERFORMANCE REPORT - \(ISO8601DateFormatter().string(from: report.timestamp))")
        print(String(repeating: "=", count: 60))
        
        // Startup metrics
        if !report.startupMetrics.isEmpty {
            print("\n📱 STARTUP METRICS:")
            var totalStartup: TimeInterval = 0
            for (phase, metric) in report.startupMetrics.sorted(by: { $0.key < $1.key }) {
                print(String(format: "  %-40s: avg=%.1fms | min=%.1fms | max=%.1fms",
                            phase,
                            metric.average * 1000,
                            metric.min * 1000,
                            metric.max * 1000))
                totalStartup += metric.average
            }
            print(String(format: "  %-40s: %.1fms", "TOTAL STARTUP", totalStartup * 1000))
        }
        
        // Memory metrics
        if !report.memoryMetrics.isEmpty {
            print("\n💾 MEMORY USAGE:")
            var peakMemory: Double = 0
            for (label, mb) in report.memoryMetrics.sorted(by: { $0.value < $1.value }).reversed() {
                print(String(format: "  %-40s: %.1fMB", label, mb))
                peakMemory = max(peakMemory, mb)
            }
            print(String(format: "  %-40s: %.1fMB", "PEAK", peakMemory))
        }
        
        // UI metrics
        if !report.uiMetrics.isEmpty {
            print("\n📊 UI RESPONSIVENESS:")
            for (operation, metric) in report.uiMetrics.sorted(by: { $0.key < $1.key }) {
                let fpsPercentage = Double(metric.totalFrames - metric.droppedFrames) / Double(metric.totalFrames) * 100
                print(String(format: "  %-40s: avg=%.2fms | 60fps=%.1f%% | dropped=%d/%d",
                            operation,
                            metric.averageMs,
                            fpsPercentage,
                            metric.droppedFrames,
                            metric.totalFrames))
            }
        }
        
        print("\n" + String(repeating: "=", count: 60) + "\n")
    }
}

// MARK: - Supporting Types

struct PerformanceReport {
    let timestamp: Date
    var startupMetrics: [String: PhaseMeasurement]
    var memoryMetrics: [String: Double]
    var uiMetrics: [String: UIMetric]
}

struct PhaseMeasurement {
    let min: TimeInterval
    let max: TimeInterval
    let average: TimeInterval
    let count: Int
}

struct UIMetric {
    let averageMs: Double
    let droppedFrames: Int
    let totalFrames: Int
}
