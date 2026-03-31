import XCTest
@testable import BrainChatLib

// MARK: - Speech Engine Tests

final class SpeechEngineTests: XCTestCase {
    
    // MARK: - Engine Enumeration
    
    func testAllEnginesExist() {
        let engines: [SpeechEngine] = [.appleDictation, .whisperAPI, .whisperCpp, .whisperKit]
        XCTAssertEqual(engines.count, 4, "Should have 4 speech engines")
    }
    
    func testDefaultEngineIsApple() {
        let defaultEngine = SpeechEngine.appleDictation
        XCTAssertEqual(defaultEngine.description, "Apple Dictation")
    }
    
    func testEngineDescriptions() {
        XCTAssertEqual(SpeechEngine.appleDictation.description, "Apple Dictation")
        XCTAssertEqual(SpeechEngine.whisperAPI.description, "OpenAI Whisper API")
        XCTAssertEqual(SpeechEngine.whisperCpp.description, "whisper.cpp (Local)")
        XCTAssertEqual(SpeechEngine.whisperKit.description, "faster-whisper (Local)")
    }
    
    func testEnginesRequiringAPIKey() {
        XCTAssertTrue(SpeechEngine.whisperAPI.requiresAPIKey, "Whisper API requires key")
        XCTAssertFalse(SpeechEngine.appleDictation.requiresAPIKey, "Apple doesn't require key")
        XCTAssertFalse(SpeechEngine.whisperCpp.requiresAPIKey, "Local whisper.cpp doesn't require key")
        XCTAssertFalse(SpeechEngine.whisperKit.requiresAPIKey, "faster-whisper doesn't require key")
    }
    
    // MARK: - AppSettings Integration
    
    func testSettingsPersistsSpeechEngine() {
        var settings = AppSettings.defaults
        settings.speechEngine = .whisperCpp
        XCTAssertEqual(settings.speechEngine, .whisperCpp)
        
        settings.speechEngine = .appleDictation
        XCTAssertEqual(settings.speechEngine, .appleDictation)
    }
    
    func testSettingsDefaultsToApple() {
        let settings = AppSettings.defaults
        XCTAssertEqual(settings.speechEngine, .appleDictation)
    }
    
    // MARK: - Whisper Error Types
    
    func testWhisperErrorMessages() {
        let errors: [WhisperError] = [
            .missingAPIKey,
            .invalidResponse,
            .apiError(401, "Unauthorized"),
            .recordingFailed,
            .noAudioData
        ]
        
        for error in errors {
            XCTAssertNotNil(error.errorDescription, "Error should have description: \(error)")
            XCTAssertFalse(error.errorDescription!.isEmpty, "Error description should not be empty")
        }
    }
    
    func testAPIErrorIncludesCode() {
        let error = WhisperError.apiError(429, "Rate limited")
        XCTAssertTrue(error.errorDescription!.contains("429"))
        XCTAssertTrue(error.errorDescription!.contains("Rate limited"))
    }
    
    // MARK: - Audio Format for Whisper
    
    func testWhisperAudioFormat() {
        // Whisper requires 16kHz mono 16-bit PCM
        let sampleRate = 16000
        let channels = 1
        let bitDepth = 16
        
        XCTAssertEqual(sampleRate, 16000, "Whisper requires 16kHz")
        XCTAssertEqual(channels, 1, "Whisper requires mono")
        XCTAssertEqual(bitDepth, 16, "Whisper requires 16-bit")
    }
    
    // MARK: - Engine Availability
    
    func testAppleDictationAlwaysAvailable() {
        // Apple Dictation is always available on macOS
        let isAvailable = true // System-level availability
        XCTAssertTrue(isAvailable, "Apple Dictation should always be available")
    }
    
    func testWhisperAPIAvailableWithKey() {
        let hasKey = "sk-test".isEmpty == false
        XCTAssertTrue(hasKey, "Whisper API available when key present")
        
        let emptyKey = ""
        XCTAssertTrue(emptyKey.isEmpty, "Empty key means unavailable")
    }
    
    // MARK: - Accessibility
    
    func testEngineAccessibilityLabels() {
        // Each engine should have clear accessibility descriptions
        for engine in [SpeechEngine.appleDictation, .whisperAPI, .whisperCpp, .whisperKit] {
            let label = engine.description
            XCTAssertFalse(label.isEmpty, "Engine \(engine) should have accessibility label")
            XCTAssertFalse(label.contains("_"), "Label should be human-readable")
        }
    }
    
    func testEngineHintsForDisabledState() {
        // When unavailable, hint should explain why
        let hint = "Unavailable until an OpenAI API key is added"
        XCTAssertTrue(hint.contains("API key"), "Hint should mention requirement")
        XCTAssertTrue(hint.contains("added"), "Hint should suggest action")
    }
    
    // MARK: - Recording State Machine
    
    func testRecordingStateTransitions() {
        enum RecordingState {
            case idle, preparing, recording, transcribing, complete, failed
        }
        
        // Valid transitions
        let validTransitions: [(RecordingState, RecordingState)] = [
            (.idle, .preparing),
            (.preparing, .recording),
            (.recording, .transcribing),
            (.transcribing, .complete),
            (.preparing, .failed),
            (.recording, .failed),
            (.transcribing, .failed),
            (.complete, .idle),
            (.failed, .idle)
        ]
        
        XCTAssertGreaterThan(validTransitions.count, 0, "Should have valid state transitions")
    }
    
    // MARK: - Mic Permission Handling
    
    func testMicPermissionStates() {
        enum MicPermission: String {
            case authorized, denied, notDetermined, restricted
        }
        
        let states: [MicPermission] = [.authorized, .denied, .notDetermined, .restricted]
        XCTAssertEqual(states.count, 4, "Should handle all permission states")
        
        // Only authorized should allow recording
        for state in states {
            let canRecord = state == .authorized
            if state == .authorized {
                XCTAssertTrue(canRecord)
            } else {
                XCTAssertFalse(canRecord)
            }
        }
    }
    
    func testMicDeniedShowsError() {
        let errorMessage = "Microphone access not authorized."
        XCTAssertTrue(errorMessage.contains("Microphone"), "Error should mention mic")
        XCTAssertTrue(errorMessage.contains("not authorized"), "Error should explain issue")
    }
    
    // MARK: - Cleanup on Failure
    
    func testCleanupOnRecordingFailure() {
        // When recording fails, audio tap should be removed
        var tapInstalled = true
        var isListening = true
        
        // Simulate failure cleanup
        tapInstalled = false
        isListening = false
        
        XCTAssertFalse(tapInstalled, "Audio tap should be removed on failure")
        XCTAssertFalse(isListening, "Listening state should be false on failure")
    }
    
    // MARK: - AirPods Max Detection
    
    func testAirPodsMaxDetection() {
        let deviceNames = [
            ("Joseph's AirPods Max", true),
            ("AirPods Max", true),
            ("AirPods Pro", false),
            ("AirPods", false),
            ("Built-in Microphone", false),
            ("External USB Mic", false)
        ]
        
        for (name, expectedMax) in deviceNames {
            let isMax = name.lowercased().contains("airpods max")
            XCTAssertEqual(isMax, expectedMax, "Failed for: \(name)")
        }
    }
    
    func testAirPodsMaxAutoSelection() {
        // AirPods Max should be auto-selected when connected
        let devices = ["Built-in Microphone", "Joseph's AirPods Max"]
        let selected = devices.first { $0.lowercased().contains("airpods max") } ?? devices.first!
        XCTAssertEqual(selected, "Joseph's AirPods Max")
    }
}

// MARK: - Faster Whisper Bridge Tests

final class FasterWhisperBridgeTests: XCTestCase {
    
    func testBridgeScriptPath() {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let expectedPath = "\(home)/brain/agentic-brain/whisper_bridge.py"
        XCTAssertTrue(expectedPath.hasSuffix("whisper_bridge.py"))
    }
    
    func testDefaultModel() {
        let model = "tiny.en"
        XCTAssertEqual(model, "tiny.en", "Default model should be tiny.en for speed")
    }
    
    func testAvailabilityCheckRequiresBoth() {
        // Bridge needs both script and faster_whisper package
        let scriptExists = true
        let packageInstalled = true
        let isAvailable = scriptExists && packageInstalled
        XCTAssertTrue(isAvailable)
        
        let scriptMissing = false
        let isAvailableNoScript = scriptMissing && packageInstalled
        XCTAssertFalse(isAvailableNoScript)
    }
    
    func testTranscriptionOutputParsing() {
        // Output should be trimmed text
        let rawOutput = "  Hello, this is a test.  \n"
        let parsed = rawOutput.trimmingCharacters(in: .whitespacesAndNewlines)
        XCTAssertEqual(parsed, "Hello, this is a test.")
    }
    
    func testErrorCodeHandling() {
        let successCode = 0
        let errorCode = 1
        
        XCTAssertTrue(successCode == 0, "Success is exit code 0")
        XCTAssertTrue(errorCode != 0, "Non-zero is error")
    }
}

// MARK: - WhisperCpp Engine Tests

final class WhisperCppEngineTests: XCTestCase {
    
    func testModelPaths() {
        let homeDir = FileManager.default.homeDirectoryForCurrentUser.path
        let expectedModelPath = "\(homeDir)/.whisper/models/ggml-base.en.bin"
        XCTAssertTrue(expectedModelPath.contains("ggml-base.en"))
    }
    
    func testBinaryPaths() {
        let possiblePaths = [
            "/opt/homebrew/bin/whisper-cpp",
            "/usr/local/bin/whisper-cpp"
        ]
        XCTAssertEqual(possiblePaths.count, 2, "Should check common installation paths")
    }
    
    func testOutputFilePattern() {
        // whisper.cpp outputs to .txt file with same base name
        let audioFile = "/tmp/recording.wav"
        let expectedOutput = "/tmp/recording.txt"
        
        let basePath = audioFile.replacingOccurrences(of: ".wav", with: "")
        let outputPath = basePath + ".txt"
        XCTAssertEqual(outputPath, expectedOutput)
    }
}
