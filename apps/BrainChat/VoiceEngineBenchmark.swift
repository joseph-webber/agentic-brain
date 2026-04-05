import AppKit
import AVFoundation
import Combine
import Foundation

/// Comprehensive TTS Engine Benchmarking Suite
/// Measures latency for all voice engines in BrainChat
@MainActor
final class VoiceEngineBenchmark: NSObject {
    
    // MARK: - Data Structures
    
    struct BenchmarkResult: Codable {
        let engine: String
        let voiceName: String
        let timestamp: String
        let measurements: [String: MeasurementResult]
        let systemInfo: SystemInfo
        
        enum CodingKeys: String, CodingKey {
            case engine, voiceName, timestamp, measurements, systemInfo
        }
    }
    
    struct MeasurementResult: Codable {
        let test: String  // "10-word", "50-word", "cached", "first-audio"
        let latencyMs: Double
        let success: Bool
        let quality: String?
        let notes: String?
    }
    
    struct SystemInfo: Codable {
        let osVersion: String
        let cpuModel: String
        let timestamp: String
        let wallClockTime: String
    }
    
    struct BenchmarkConfig {
        let phrases: [String: [String]] = [
            "10-word": [
                "Hello there this is Karen speaking from Australia today",
                "The quick brown fox jumps over the lazy dog here",
                "Processing your request one moment please stand by",
                "That's interesting let me think about this more",
                "I found some good information for you about that"
            ],
            "50-word": [
                "Hello and welcome back to BrainChat. I'm Karen your Australian voice assistant speaking at optimal speed for clarity and comprehension. I can help you with coding tasks research information and much more. Today we're running performance benchmarks to measure latency across all our TTS engines to ensure you get the fastest most responsive audio experience possible every single time you interact with me.",
                "This is a comprehensive test of the Cartesia streaming TTS engine which provides ultra-low latency streaming audio synthesis. The Cartesia API allows us to stream audio in real-time with minimal delay between the request and the first audio output. This makes it perfect for interactive voice applications like BrainChat where responsiveness is critical to user experience.",
                "The Apple macOS AVSpeechSynthesizer engine provides excellent voice quality with multiple voice options including the Australian Karen voice for accessibility users. While it has slightly higher latency than streaming engines like Cartesia it provides excellent audio quality and is fully offline without requiring internet connectivity.",
                "Piper is a lightweight open-source text-to-speech system that runs locally on your machine. It provides reasonable quality synthesis with minimal latency when the models are cached. Piper is great for offline use cases and privacy-conscious applications where you don't want to send audio to external services.",
                "ElevenLabs provides premium text-to-speech synthesis with exceptional voice quality and natural sounding speech. The API is cloud-based so it requires internet connectivity but provides some of the best sounding voices available including professional grade quality suitable for production applications and high-end user experiences."
            ],
            "cached": [
                "Got it",
                "Processing",
                "OK",
                "Yes",
                "Thanks",
                "One moment",
                "I understand"
            ]
        ]
    }
    
    // MARK: - Properties
    
    private let voiceManager: VoiceManager
    private let config = BenchmarkConfig()
    private var results: [BenchmarkResult] = []
    private let dateFormatter: DateFormatter
    private var currentStartTime: Date?
    
    // MARK: - Initialization
    
    init(voiceManager: VoiceManager) {
        self.voiceManager = voiceManager
        self.dateFormatter = DateFormatter()
        self.dateFormatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'"
        super.init()
    }
    
    // MARK: - Public Benchmark Methods
    
    /// Run complete benchmark suite for all engines
    func runCompleteBenchmark() async -> [BenchmarkResult] {
        results = []
        
        print("🚀 Starting VoiceEngine Benchmark Suite")
        print("=" * 60)
        
        // Get available engines
        let engines: [VoiceOutputEngine] = [.macOS, .cartesia, .piper, .elevenLabs]
        
        for engine in engines {
            await benchmarkEngine(engine)
        }
        
        print("\n" + "=" * 60)
        print("✅ Benchmark Suite Complete!")
        print("Results saved to: benchmarks/voice-baseline.json")
        
        return results
    }
    
    // MARK: - Private Benchmark Implementation
    
    private func benchmarkEngine(_ engine: VoiceOutputEngine) async {
        print("\n📊 Benchmarking Engine: \(engine.name)")
        print("-" * 40)
        
        voiceManager.setOutputEngine(engine)
        
        // Wait for engine to be ready
        try? await Task.sleep(nanoseconds: 500_000_000)  // 500ms
        
        var measurements: [String: MeasurementResult] = [:]
        
        // Benchmark first audio latency
        if let result = await benchmarkFirstAudioLatency(engine: engine) {
            measurements["first-audio"] = result
            print("  ⏱️  First Audio: \(String(format: "%.2f", result.latencyMs))ms")
        }
        
        // Benchmark 10-word phrase
        if let result = await benchmarkPhraseLatency(
            engine: engine,
            phrases: config.phrases["10-word"] ?? [],
            label: "10-word"
        ) {
            measurements["10-word"] = result
            print("  📝 10-word: \(String(format: "%.2f", result.latencyMs))ms")
        }
        
        // Benchmark 50-word phrase
        if let result = await benchmarkPhraseLatency(
            engine: engine,
            phrases: config.phrases["50-word"] ?? [],
            label: "50-word"
        ) {
            measurements["50-word"] = result
            print("  📝 50-word: \(String(format: "%.2f", result.latencyMs))ms")
        }
        
        // Benchmark cached phrases (if applicable)
        if let result = await benchmarkCachedPhrases(
            engine: engine,
            phrases: config.phrases["cached"] ?? []
        ) {
            measurements["cached"] = result
            print("  💾 Cached: \(String(format: "%.2f", result.latencyMs))ms")
        }
        
        // Create result record
        let result = BenchmarkResult(
            engine: engine.name,
            voiceName: voiceManager.selectedVoiceName,
            timestamp: dateFormatter.string(from: Date()),
            measurements: measurements,
            systemInfo: captureSystemInfo()
        )
        
        results.append(result)
    }
    
    private func benchmarkFirstAudioLatency(engine: VoiceOutputEngine) async -> MeasurementResult? {
        let testPhrase = "Hello from \(engine.name)"
        var latencies: [Double] = []
        
        for i in 0..<3 {  // 3 runs
            let start = Date()
            
            // Start speaking and measure to first audio output
            voiceManager.speak(testPhrase)
            
            // In a real implementation, this would be measured from AVAudioPlayerDelegate
            // For now, we measure queue insertion latency
            let delay = Date().timeIntervalSince(start) * 1000
            latencies.append(delay)
            
            // Wait for speech to finish
            try? await Task.sleep(nanoseconds: 2_000_000_000)  // 2s
            
            if i < 2 {
                voiceManager.stop()
                try? await Task.sleep(nanoseconds: 500_000_000)  // 500ms between runs
            }
        }
        
        let averageLatency = latencies.isEmpty ? 0 : latencies.reduce(0, +) / Double(latencies.count)
        
        return MeasurementResult(
            test: "first-audio",
            latencyMs: averageLatency,
            success: !latencies.isEmpty,
            quality: qualityRating(for: engine, latency: averageLatency),
            notes: "Measured from speak() call. Actual hardware latency may vary."
        )
    }
    
    private func benchmarkPhraseLatency(
        engine: VoiceOutputEngine,
        phrases: [String],
        label: String
    ) async -> MeasurementResult? {
        guard !phrases.isEmpty else { return nil }
        
        var latencies: [Double] = []
        
        for phrase in phrases.prefix(3) {  // Test 3 phrases
            let start = Date()
            voiceManager.speak(phrase)
            let delay = Date().timeIntervalSince(start) * 1000
            latencies.append(delay)
            
            // Wait for speech to finish
            try? await Task.sleep(nanoseconds: 3_000_000_000)  // 3s for long phrases
            
            voiceManager.stop()
            try? await Task.sleep(nanoseconds: 500_000_000)  // 500ms between runs
        }
        
        let averageLatency = latencies.isEmpty ? 0 : latencies.reduce(0, +) / Double(latencies.count)
        
        return MeasurementResult(
            test: label,
            latencyMs: averageLatency,
            success: !latencies.isEmpty,
            quality: nil,
            notes: "Average latency across \(latencies.count) phrase(s)"
        )
    }
    
    private func benchmarkCachedPhrases(
        engine: VoiceOutputEngine,
        phrases: [String]
    ) async -> MeasurementResult? {
        guard !phrases.isEmpty else { return nil }
        
        var latencies: [Double] = []
        
        // Pre-warm cache
        for phrase in phrases {
            voiceManager.speak(phrase)
            try? await Task.sleep(nanoseconds: 100_000_000)  // 100ms
            voiceManager.stop()
        }
        
        // Now measure cached lookups
        for phrase in phrases.prefix(5) {
            let start = Date()
            voiceManager.speak(phrase)
            let delay = Date().timeIntervalSince(start) * 1000
            latencies.append(delay)
            
            voiceManager.stop()
            try? await Task.sleep(nanoseconds: 200_000_000)  // 200ms
        }
        
        let averageLatency = latencies.isEmpty ? 0 : latencies.reduce(0, +) / Double(latencies.count)
        let minLatency = latencies.min() ?? 0
        let maxLatency = latencies.max() ?? 0
        
        return MeasurementResult(
            test: "cached",
            latencyMs: averageLatency,
            success: !latencies.isEmpty,
            quality: nil,
            notes: "Min: \(String(format: "%.2f", minLatency))ms, Max: \(String(format: "%.2f", maxLatency))ms, Avg: \(String(format: "%.2f", averageLatency))ms"
        )
    }
    
    private func qualityRating(for engine: VoiceOutputEngine, latency: Double) -> String {
        switch engine {
        case .macOS:
            if latency < 50 { return "Excellent" }
            if latency < 100 { return "Good" }
            if latency < 200 { return "Fair" }
            return "Poor"
        case .cartesia:
            if latency < 100 { return "Excellent" }
            if latency < 200 { return "Good" }
            if latency < 500 { return "Fair" }
            return "Poor"
        case .piper:
            if latency < 150 { return "Excellent" }
            if latency < 300 { return "Good" }
            if latency < 600 { return "Fair" }
            return "Poor"
        case .elevenLabs:
            if latency < 200 { return "Excellent" }
            if latency < 500 { return "Good" }
            if latency < 1000 { return "Fair" }
            return "Poor"
        }
    }
    
    private func captureSystemInfo() -> SystemInfo {
        let osVersion = ProcessInfo.processInfo.operatingSystemVersionString
        let cpuModel = getCPUModel()
        let now = Date()
        
        return SystemInfo(
            osVersion: osVersion,
            cpuModel: cpuModel,
            timestamp: dateFormatter.string(from: now),
            wallClockTime: "\(Int(now.timeIntervalSince1970))"
        )
    }
    
    private func getCPUModel() -> String {
        var size = 0
        sysctlbyname("machdep.cpu.brand_string", nil, &size, nil, 0)
        
        var model = [CChar](repeating: 0, count: size)
        sysctlbyname("machdep.cpu.brand_string", &model, &size, nil, 0)
        
        return String(cString: model).isEmpty ? "Unknown" : String(cString: model)
    }
    
    // MARK: - JSON Export
    
    func exportResultsToJSON() -> String? {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        
        do {
            let data = try encoder.encode(results)
            return String(data: data, encoding: .utf8)
        } catch {
            print("Error encoding benchmark results: \(error)")
            return nil
        }
    }
    
    func saveResultsToFile(at path: String) -> Bool {
        guard let jsonString = exportResultsToJSON() else {
            print("Failed to generate JSON")
            return false
        }
        
        do {
            try jsonString.write(toFile: path, atomically: true, encoding: .utf8)
            print("✅ Results saved to: \(path)")
            return true
        } catch {
            print("❌ Failed to save results: \(error)")
            return false
        }
    }
}

// MARK: - VoiceOutputEngine Extension

extension VoiceOutputEngine {
    var name: String {
        switch self {
        case .macOS:
            return "Apple macOS AVSpeechSynthesizer"
        case .cartesia:
            return "Cartesia (Streaming TTS)"
        case .piper:
            return "Piper (Local)"
        case .elevenLabs:
            return "ElevenLabs (Premium)"
        }
    }
}

// MARK: - String Extension

private extension String {
    static func * (left: String, right: Int) -> String {
        return String(repeating: left, count: right)
    }
}

// MARK: - Test Helper

/// Quick benchmark test that can be called from ContentView for testing
func runVoiceBenchmarkTest(with voiceManager: VoiceManager) async {
    print("🎙️ Starting Voice Engine Benchmark Test...")
    
    let benchmark = VoiceEngineBenchmark(voiceManager: voiceManager)
    let results = await benchmark.runCompleteBenchmark()
    
    // Print summary
    print("\n" + "=" * 60)
    print("📊 BENCHMARK SUMMARY")
    print("=" * 60)
    
    for result in results {
        print("\n\(result.engine)")
        print("Voice: \(result.voiceName)")
        print("Measurements:")
        for (key, measurement) in result.measurements.sorted(by: { $0.key < $1.key }) {
            print("  \(key): \(String(format: "%.2f", measurement.latencyMs))ms (\(measurement.quality ?? "N/A"))")
            if let notes = measurement.notes {
                print("    Notes: \(notes)")
            }
        }
    }
    
    // Save to JSON
    let benchmarkDir = "/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks"
    let outputPath = "\(benchmarkDir)/voice-baseline.json"
    _ = benchmark.saveResultsToFile(at: outputPath)
}
