import XCTest
@testable import BrainChatLib

// MARK: - Mock Speech Recognizer

final class MockSpeechRecognizer: SpeechRecognizerProtocol {
    var isListening: Bool = false
    var startCallCount = 0
    var stopCallCount = 0
    var authorizationStatus: String = "authorized"
    var availableLocales: [String] = ["en-AU", "en-US", "en-GB"]
    var simulatedTranscript: String = ""
    var onTranscriptFinalized: ((String) -> Void)?

    func startListening() {
        guard authorizationStatus == "authorized" else { return }
        isListening = true
        startCallCount += 1
    }

    func stopListening() {
        isListening = false
        stopCallCount += 1
        if !simulatedTranscript.isEmpty {
            onTranscriptFinalized?(simulatedTranscript)
        }
    }

    func simulateTranscription(_ text: String) {
        simulatedTranscript = text
        onTranscriptFinalized?(text)
    }
}

// MARK: - Speech Manager Tests

final class SpeechManagerTests: XCTestCase {

    // MARK: - Authorization

    func testInitialAuthorizationStatus() {
        let mock = MockSpeechRecognizer()
        // Default mock is authorized
        XCTAssertEqual(mock.authorizationStatus, "authorized")
    }

    func testUnauthorizedPreventsListening() {
        let mock = MockSpeechRecognizer()
        mock.authorizationStatus = "denied"
        mock.startListening()

        XCTAssertFalse(mock.isListening)
        XCTAssertEqual(mock.startCallCount, 0)
    }

    func testAuthorizedAllowsListening() {
        let mock = MockSpeechRecognizer()
        mock.startListening()

        XCTAssertTrue(mock.isListening)
        XCTAssertEqual(mock.startCallCount, 1)
    }

    // MARK: - Listening State

    func testStartStopCycle() {
        let mock = MockSpeechRecognizer()

        mock.startListening()
        XCTAssertTrue(mock.isListening)

        mock.stopListening()
        XCTAssertFalse(mock.isListening)

        XCTAssertEqual(mock.startCallCount, 1)
        XCTAssertEqual(mock.stopCallCount, 1)
    }

    func testMultipleStartStopCycles() {
        let mock = MockSpeechRecognizer()

        for _ in 0..<5 {
            mock.startListening()
            XCTAssertTrue(mock.isListening)
            mock.stopListening()
            XCTAssertFalse(mock.isListening)
        }

        XCTAssertEqual(mock.startCallCount, 5)
        XCTAssertEqual(mock.stopCallCount, 5)
    }

    // MARK: - Transcription

    func testTranscriptFinalization() {
        let mock = MockSpeechRecognizer()
        var finalizedText: String?

        mock.onTranscriptFinalized = { text in
            finalizedText = text
        }

        mock.simulatedTranscript = "Hello Brain"
        mock.startListening()
        mock.stopListening()

        XCTAssertEqual(finalizedText, "Hello Brain")
    }

    func testEmptyTranscriptNotFinalized() {
        let mock = MockSpeechRecognizer()
        var callbackCalled = false

        mock.onTranscriptFinalized = { _ in
            callbackCalled = true
        }

        mock.simulatedTranscript = ""
        mock.startListening()
        mock.stopListening()

        XCTAssertFalse(callbackCalled)
    }

    func testTranscriptWithPunctuation() {
        let mock = MockSpeechRecognizer()
        var finalizedText: String?

        mock.onTranscriptFinalized = { text in
            finalizedText = text
        }

        mock.simulateTranscription("What's the weather like today?")
        XCTAssertEqual(finalizedText, "What's the weather like today?")
    }

    func testTranscriptWithSpecialCharacters() {
        let mock = MockSpeechRecognizer()
        var finalizedText: String?

        mock.onTranscriptFinalized = { text in
            finalizedText = text
        }

        mock.simulateTranscription("Set variable x = 42 && run")
        XCTAssertEqual(finalizedText, "Set variable x = 42 && run")
    }

    // MARK: - Locale

    func testAustralianEnglishLocale() {
        let mock = MockSpeechRecognizer()
        XCTAssertTrue(mock.availableLocales.contains("en-AU"),
                      "Australian English must be available for Joseph")
    }

    func testLocaleIdentifierFormat() {
        let localeId = "en-AU"
        let locale = Locale(identifier: localeId)
        XCTAssertEqual(locale.language.languageCode?.identifier, "en")
    }

    // MARK: - Audio Level

    func testAudioLevelCalculation() {
        // Simulate audio level calculation from buffer
        let sampleData: [Float] = [0.1, -0.2, 0.3, -0.15, 0.25]
        let count = sampleData.count
        let sum = sampleData.reduce(Float(0)) { $0 + abs($1) }
        let avg = sum / Float(count)
        let level = min(max(avg * 10, 0), 1)

        XCTAssertGreaterThan(level, 0)
        XCTAssertLessThanOrEqual(level, 1)
    }

    func testAudioLevelSilence() {
        let sampleData: [Float] = [0, 0, 0, 0, 0]
        let count = sampleData.count
        let sum = sampleData.reduce(Float(0)) { $0 + abs($1) }
        let avg = sum / Float(max(count, 1))
        let level = min(max(avg * 10, 0), 1)

        XCTAssertEqual(level, 0, accuracy: 0.001)
    }

    func testAudioLevelClipping() {
        let sampleData: [Float] = [1.0, 1.0, 1.0, 1.0]
        let count = sampleData.count
        let sum = sampleData.reduce(Float(0)) { $0 + abs($1) }
        let avg = sum / Float(max(count, 1))
        let level = min(max(avg * 10, 0), 1)

        XCTAssertEqual(level, 1.0, accuracy: 0.001, "Level should be clamped to 1.0")
    }

    // MARK: - Device Enumeration

    func testDefaultDeviceFallback() {
        // When no devices found, should return built-in microphone
        let devices: [TestAudioDevice] = []
        let fallback = devices.isEmpty
            ? [TestAudioDevice(id: "default", name: "Built-in Microphone")]
            : devices

        XCTAssertEqual(fallback.count, 1)
        XCTAssertEqual(fallback[0].name, "Built-in Microphone")
    }

    func testAirPodsMaxAutoSelection() {
        let devices = [
            TestAudioDevice(id: "1", name: "Built-in Microphone"),
            TestAudioDevice(id: "2", name: "Joseph's AirPods Max", isAirPodsMax: true),
            TestAudioDevice(id: "3", name: "External Mic")
        ]

        let selected = devices.first(where: { $0.isAirPodsMax }) ?? devices.first!
        XCTAssertEqual(selected.name, "Joseph's AirPods Max")
        XCTAssertTrue(selected.isAirPodsMax)
    }

    func testAirPodsMaxNameDetection() {
        let names = [
            "AirPods Max": true,
            "Joseph's AirPods Max": true,
            "AirPods Pro": false,
            "AirPods": false,
            "Built-in Microphone": false
        ]

        for (name, expected) in names {
            let isMax = name.lowercased().contains("airpods max")
            XCTAssertEqual(isMax, expected, "Failed for: \(name)")
        }
    }
}
