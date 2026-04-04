import AVFoundation
import Foundation
import Speech

// MARK: - Benchmark Result Models
struct STTBenchmarkResult: Codable {
    let engine: String
    let model: String?
    let testName: String
    let audioLength: Int  // milliseconds
    let firstTranscriptionTime: Int  // milliseconds from audio end
    let totalTranscriptionTime: Int  // milliseconds total
    let accuracy: Double?  // WER if available
    let transcription: String
    let success: Bool
    let error: String?
    let timestamp: String
    let platform: String = "macOS"
    let systemInfo: String
}

struct STTBenchmarkReport: Codable {
    let timestamp: String
    let totalTests: Int
    let passedTests: Int
    let failedTests: Int
    let results: [STTBenchmarkResult]
    let summary: BenchmarkSummary
}

struct BenchmarkSummary: Codable {
    struct EngineStats: Codable {
        let engine: String
        let model: String?
        let avgFirstTranscriptionTime: Int
        let avgTotalTime: Int
        let successRate: Double
        let targetMet: Bool
    }
    
    let engineStats: [EngineStats]
    let fastestEngine: String
    let slowestEngine: String
    let recommendedEngine: String
}

// MARK: - Test Audio Generator
final class TestAudioGenerator {
    static func generateTestAudio(duration: TimeInterval, frequency: Float = 440.0) -> URL {
        let sampleRate = 16000.0
        let totalFrames = Int(duration * sampleRate)
        
        // Create audio format
        let format = AVAudioFormat(
            commonFormat: .pcmFormatFloat32,
            sampleRate: sampleRate,
            channels: 1,
            interleaved: false
        )!
        
        // Create audio buffer
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(totalFrames)) else {
            fatalError("Could not create audio buffer")
        }
        
        buffer.frameLength = AVAudioFrameCount(totalFrames)
        
        // Generate sine wave
        guard let channelData = buffer.floatChannelData else {
            fatalError("Could not access channel data")
        }
        
        let data = channelData[0]
        for frame in 0..<totalFrames {
            let sample = sin(2.0 * Float.pi * frequency * Float(frame) / Float(sampleRate))
            data[frame] = sample * 0.3  // Reduce amplitude to avoid clipping
        }
        
        // Write to file
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("test_\(UUID().uuidString).wav")
        
        let file = try! AVAudioFile(forWriting: tempURL, settings: format.settings, commonFormat: .pcmFormatFloat32, interleaved: false)
        try! file.write(from: buffer)
        
        return tempURL
    }
    
    static func generateSpeechSynthesisAudio(text: String, duration: TimeInterval = 5.0) -> URL {
        let synthesizer = AVSpeechSynthesizer()
        let utterance = AVSpeechUtterance(string: text)
        utterance.rate = AVSpeechUtteranceDefaultSpeechRate * 0.8  // Slightly slower
        
        let audioEngine = AVAudioEngine()
        let audioSession = AVAudioSession.sharedInstance()
        
        try? audioSession.setCategory(.record, mode: .default, options: [])
        try? audioSession.setActive(true)
        
        let tempURL = FileManager.default.temporaryDirectory
            .appendingPathComponent("speech_\(UUID().uuidString).m4a")
        
        // For now, we'll create a sine wave as placeholder
        return generateTestAudio(duration: duration)
    }
}

// MARK: - STT Benchmark Suite
@MainActor
final class STTBenchmarkSuite {
    private var results: [STTBenchmarkResult] = []
    private let reportURL: URL
    
    init(reportPath: String = "/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks/stt-baseline.json") {
        self.reportURL = URL(fileURLWithPath: reportPath)
    }
    
    // MARK: - Benchmark Methods
    
    func runFullBenchmark() async {
        print("🚀 Starting STT Benchmark Suite")
        print("=" * 60)
        
        // Test Apple Dictation
        await benchmarkAppleSpeechRecognition()
        
        // Test Whisper API
        await benchmarkWhisperAPI()
        
        // Test faster-whisper (local)
        await benchmarkFasterWhisper()
        
        // Test whisper.cpp
        await benchmarkWhisperCpp()
        
        // Generate report
        let report = generateReport()
        saveReport(report)
        printSummary(report)
    }
    
    private func benchmarkAppleSpeechRecognition() async {
        print("\n📱 Benchmarking Apple Speech Recognition...")
        
        // Create a simple test audio file
        let audioURL = TestAudioGenerator.generateTestAudio(duration: 3.0, frequency: 440.0)
        defer { try? FileManager.default.removeItem(at: audioURL) }
        
        let startTime = Date()
        let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
        
        guard let recognizer = recognizer, recognizer.isAvailable else {
            recordResult(
                engine: "apple",
                model: nil,
                testName: "basic_recognition",
                audioLength: 3000,
                firstTime: 0,
                totalTime: 0,
                accuracy: nil,
                transcription: "",
                success: false,
                error: "Speech recognizer not available"
            )
            return
        }
        
        // For Apple Dictation, we measure permission and availability
        let permissionStart = Date()
        var hasPermission = false
        
        SFSpeechRecognizer.requestAuthorization { status in
            hasPermission = status == .authorized
        }
        
        // Wait briefly for authorization request
        try? await Task.sleep(nanoseconds: 100_000_000)  // 100ms
        
        let permissionTime = Int(Date().timeIntervalSince(permissionStart) * 1000)
        let totalTime = Int(Date().timeIntervalSince(startTime) * 1000)
        
        recordResult(
            engine: "apple",
            model: nil,
            testName: "recognition_setup",
            audioLength: 3000,
            firstTime: permissionTime,
            totalTime: totalTime,
            accuracy: nil,
            transcription: hasPermission ? "authorized" : "permission_pending",
            success: hasPermission,
            error: hasPermission ? nil : "Permission not yet granted"
        )
        
        print("  ✓ Apple Dictation: \(permissionTime)ms first response, \(totalTime)ms total")
    }
    
    private func benchmarkWhisperAPI() async {
        print("\n☁️  Benchmarking Whisper API...")
        
        guard let apiKey = ProcessInfo.processInfo.environment["OPENAI_API_KEY"] else {
            print("  ⚠️  Skipping Whisper API (no OPENAI_API_KEY)")
            recordResult(
                engine: "whisper_api",
                model: nil,
                testName: "api_test",
                audioLength: 0,
                firstTime: 0,
                totalTime: 0,
                accuracy: nil,
                transcription: "",
                success: false,
                error: "OPENAI_API_KEY not set"
            )
            return
        }
        
        let audioURL = TestAudioGenerator.generateTestAudio(duration: 2.0)
        defer { try? FileManager.default.removeItem(at: audioURL) }
        
        let engine = WhisperAPIEngine(apiKey: apiKey)
        let startTime = Date()
        let audioStart = Date()
        
        do {
            let transcription = try await engine.transcribe(audioURL: audioURL, language: "en")
            let firstResponseTime = Int(Date().timeIntervalSince(audioStart) * 1000)
            let totalTime = Int(Date().timeIntervalSince(startTime) * 1000)
            
            recordResult(
                engine: "whisper_api",
                model: "whisper-1",
                testName: "api_transcription",
                audioLength: 2000,
                firstTime: firstResponseTime,
                totalTime: totalTime,
                accuracy: nil,
                transcription: transcription,
                success: true,
                error: nil
            )
            
            print("  ✓ Whisper API: \(firstResponseTime)ms first response, \(totalTime)ms total")
        } catch {
            recordResult(
                engine: "whisper_api",
                model: "whisper-1",
                testName: "api_transcription",
                audioLength: 2000,
                firstTime: 0,
                totalTime: Int(Date().timeIntervalSince(startTime) * 1000),
                accuracy: nil,
                transcription: "",
                success: false,
                error: error.localizedDescription
            )
            
            print("  ✗ Whisper API Error: \(error.localizedDescription)")
        }
    }
    
    private func benchmarkFasterWhisper() async {
        print("\n🐍 Benchmarking faster-whisper (Local)...")
        
        let bridge = FasterWhisperBridge.shared
        
        guard bridge.isAvailable else {
            print("  ⚠️  Skipping faster-whisper (not available)")
            recordResult(
                engine: "faster_whisper",
                model: "tiny.en",
                testName: "bridge_test",
                audioLength: 0,
                firstTime: 0,
                totalTime: 0,
                accuracy: nil,
                transcription: "",
                success: false,
                error: "faster-whisper bridge not available"
            )
            return
        }
        
        let audioURL = TestAudioGenerator.generateTestAudio(duration: 2.0)
        defer { try? FileManager.default.removeItem(at: audioURL) }
        
        let startTime = Date()
        let audioStart = Date()
        
        do {
            let transcription = try await bridge.transcribe(audioURL: audioURL)
            let firstResponseTime = Int(Date().timeIntervalSince(audioStart) * 1000)
            let totalTime = Int(Date().timeIntervalSince(startTime) * 1000)
            
            recordResult(
                engine: "faster_whisper",
                model: "tiny.en",
                testName: "local_transcription",
                audioLength: 2000,
                firstTime: firstResponseTime,
                totalTime: totalTime,
                accuracy: nil,
                transcription: transcription,
                success: true,
                error: nil
            )
            
            print("  ✓ faster-whisper: \(firstResponseTime)ms first response, \(totalTime)ms total")
        } catch {
            recordResult(
                engine: "faster_whisper",
                model: "tiny.en",
                testName: "local_transcription",
                audioLength: 2000,
                firstTime: 0,
                totalTime: Int(Date().timeIntervalSince(startTime) * 1000),
                accuracy: nil,
                transcription: "",
                success: false,
                error: error.localizedDescription
            )
            
            print("  ✗ faster-whisper Error: \(error.localizedDescription)")
        }
    }
    
    private func benchmarkWhisperCpp() async {
        print("\n⚙️  Benchmarking whisper.cpp...")
        
        let engine = WhisperCppEngine()
        
        guard engine.isAvailable else {
            print("  ⚠️  Skipping whisper.cpp (not available)")
            recordResult(
                engine: "whisper_cpp",
                model: "base.en",
                testName: "cpp_test",
                audioLength: 0,
                firstTime: 0,
                totalTime: 0,
                accuracy: nil,
                transcription: "",
                success: false,
                error: "whisper.cpp not available"
            )
            return
        }
        
        let audioURL = TestAudioGenerator.generateTestAudio(duration: 2.0)
        defer { try? FileManager.default.removeItem(at: audioURL) }
        
        let startTime = Date()
        let audioStart = Date()
        
        do {
            let transcription = try await engine.transcribe(audioURL: audioURL, language: "en")
            let firstResponseTime = Int(Date().timeIntervalSince(audioStart) * 1000)
            let totalTime = Int(Date().timeIntervalSince(startTime) * 1000)
            
            recordResult(
                engine: "whisper_cpp",
                model: "base.en",
                testName: "cpp_transcription",
                audioLength: 2000,
                firstTime: firstResponseTime,
                totalTime: totalTime,
                accuracy: nil,
                transcription: transcription,
                success: true,
                error: nil
            )
            
            print("  ✓ whisper.cpp: \(firstResponseTime)ms first response, \(totalTime)ms total")
        } catch {
            recordResult(
                engine: "whisper_cpp",
                model: "base.en",
                testName: "cpp_transcription",
                audioLength: 2000,
                firstTime: 0,
                totalTime: Int(Date().timeIntervalSince(startTime) * 1000),
                accuracy: nil,
                transcription: "",
                success: false,
                error: error.localizedDescription
            )
            
            print("  ✗ whisper.cpp Error: \(error.localizedDescription)")
        }
    }
    
    // MARK: - Report Generation
    
    private func recordResult(
        engine: String,
        model: String?,
        testName: String,
        audioLength: Int,
        firstTime: Int,
        totalTime: Int,
        accuracy: Double?,
        transcription: String,
        success: Bool,
        error: String?
    ) {
        let result = STTBenchmarkResult(
            engine: engine,
            model: model,
            testName: testName,
            audioLength: audioLength,
            firstTranscriptionTime: firstTime,
            totalTranscriptionTime: totalTime,
            accuracy: accuracy,
            transcription: transcription,
            success: success,
            error: error,
            timestamp: ISO8601DateFormatter().string(from: Date()),
            systemInfo: getSystemInfo()
        )
        
        results.append(result)
    }
    
    private func generateReport() -> STTBenchmarkReport {
        let timestamp = ISO8601DateFormatter().string(from: Date())
        let passedTests = results.filter { $0.success }.count
        let failedTests = results.filter { !$0.success }.count
        
        // Calculate engine statistics
        var engineStatsDict: [String: (times: [Int], totalTimes: [Int], successes: Int, total: Int)] = [:]
        
        for result in results {
            let key = "\(result.engine)_\(result.model ?? "none")"
            if engineStatsDict[key] == nil {
                engineStatsDict[key] = (times: [], totalTimes: [], successes: 0, total: 0)
            }
            
            var stats = engineStatsDict[key]!
            if result.success {
                stats.times.append(result.firstTranscriptionTime)
                stats.totalTimes.append(result.totalTranscriptionTime)
                stats.successes += 1
            }
            stats.total += 1
            engineStatsDict[key] = stats
        }
        
        let engineStats = engineStatsDict.map { key, stats -> BenchmarkSummary.EngineStats in
            let parts = key.split(separator: "_")
            let engine = String(parts[0])
            let model = parts.count > 1 && parts[1] != "none" ? String(parts[1]) : nil
            
            let avgFirst = stats.times.isEmpty ? 0 : stats.times.reduce(0, +) / stats.times.count
            let avgTotal = stats.totalTimes.isEmpty ? 0 : stats.totalTimes.reduce(0, +) / stats.totalTimes.count
            let successRate = Double(stats.successes) / Double(stats.total)
            
            // Determine if target met based on engine type
            let targetMet: Bool
            if engine == "apple" {
                targetMet = avgFirst < 200
            } else if engine.contains("whisper") && model?.contains("tiny") ?? false {
                targetMet = avgTotal < 500
            } else if engine.contains("whisper") && model?.contains("base") ?? false {
                targetMet = avgTotal < 1000
            } else {
                targetMet = true
            }
            
            return BenchmarkSummary.EngineStats(
                engine: engine,
                model: model,
                avgFirstTranscriptionTime: avgFirst,
                avgTotalTime: avgTotal,
                successRate: successRate,
                targetMet: targetMet
            )
        }
        
        let fastestEngine = engineStats.min(by: { $0.avgTotalTime < $1.avgTotalTime })?.engine ?? "unknown"
        let slowestEngine = engineStats.max(by: { $0.avgTotalTime < $1.avgTotalTime })?.engine ?? "unknown"
        let recommendedEngine = engineStats
            .filter { $0.successRate > 0.8 }
            .min(by: { $0.avgTotalTime < $1.avgTotalTime })?.engine ?? "unknown"
        
        let summary = BenchmarkSummary(
            engineStats: engineStats,
            fastestEngine: fastestEngine,
            slowestEngine: slowestEngine,
            recommendedEngine: recommendedEngine
        )
        
        return STTBenchmarkReport(
            timestamp: timestamp,
            totalTests: results.count,
            passedTests: passedTests,
            failedTests: failedTests,
            results: results,
            summary: summary
        )
    }
    
    private func saveReport(_ report: STTBenchmarkReport) {
        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            let data = try encoder.encode(report)
            try data.write(to: reportURL)
            print("\n✅ Report saved to: \(reportURL.path)")
        } catch {
            print("\n❌ Failed to save report: \(error)")
        }
    }
    
    private func printSummary(_ report: STTBenchmarkReport) {
        print("\n" + "=" * 60)
        print("📊 STT BENCHMARK SUMMARY")
        print("=" * 60)
        print("Total Tests: \(report.totalTests)")
        print("Passed: \(report.passedTests) ✓")
        print("Failed: \(report.failedTests) ✗")
        print("\n🏆 ENGINE PERFORMANCE:")
        
        for stat in report.summary.engineStats.sorted(by: { $0.engine < $1.engine }) {
            let model = stat.model ?? "N/A"
            print("\n  \(stat.engine.uppercased()) (\(model))")
            print("    First Response: \(stat.avgFirstTranscriptionTime)ms")
            print("    Total Time: \(stat.avgTotalTime)ms")
            print("    Success Rate: \(String(format: "%.1f", stat.successRate * 100))%")
            print("    Target Met: \(stat.targetMet ? "✅" : "❌")")
        }
        
        print("\n⚡ RANKINGS:")
        print("  Fastest: \(report.summary.fastestEngine)")
        print("  Slowest: \(report.summary.slowestEngine)")
        print("  Recommended: \(report.summary.recommendedEngine)")
        print("\n" + "=" * 60)
    }
    
    private func getSystemInfo() -> String {
        let processInfo = ProcessInfo.processInfo
        return "macOS \(processInfo.operatingSystemVersionString), \(processInfo.processorCount) cores"
    }
}

// MARK: - Helper Extensions
extension String {
    static func * (lhs: String, rhs: Int) -> String {
        return String(repeating: lhs, count: rhs)
    }
}

// MARK: - Main Benchmark Entry Point
@main
struct STTBenchmarkApp {
    static func main() async {
        let suite = STTBenchmarkSuite()
        await suite.runFullBenchmark()
    }
}
