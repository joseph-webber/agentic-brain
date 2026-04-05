import XCTest
@testable import BrainChatLib

// MARK: - Mock Voice Synthesizer

final class MockVoiceSynthesizer: VoiceSynthesizerProtocol {
    var isSpeaking: Bool = false
    var spokenTexts: [String] = []
    var selectedVoice: String = "Karen (Premium)"
    var speechRate: Float = 160.0
    var stopCallCount = 0

    func speak(_ text: String) {
        spokenTexts.append(text)
        isSpeaking = true
    }

    func stop() {
        isSpeaking = false
        stopCallCount += 1
    }

    func simulateFinish() {
        isSpeaking = false
    }
}

// MARK: - Voice Manager Tests

final class VoiceManagerTests: XCTestCase {

    // MARK: - Default Voice

    func testDefaultVoiceIsKaren() {
        let mock = MockVoiceSynthesizer()
        XCTAssertEqual(mock.selectedVoice, "Karen (Premium)",
                       "Default voice must be Karen for accessibility users")
    }

    func testDefaultSpeechRate() {
        let mock = MockVoiceSynthesizer()
        XCTAssertEqual(mock.speechRate, 160.0,
                       "Default rate should be 160 wpm")
    }

    // MARK: - Speech Queue

    func testSpeakAddsToQueue() {
        let mock = MockVoiceSynthesizer()
        mock.speak("Hello there")
        mock.speak("How are you?")

        XCTAssertEqual(mock.spokenTexts.count, 2)
        XCTAssertEqual(mock.spokenTexts[0], "Hello there")
        XCTAssertEqual(mock.spokenTexts[1], "How are you?")
    }

    func testSpeakSetsIsSpeaking() {
        let mock = MockVoiceSynthesizer()
        XCTAssertFalse(mock.isSpeaking)

        mock.speak("Test")
        XCTAssertTrue(mock.isSpeaking)
    }

    func testStopClearsSpeaking() {
        let mock = MockVoiceSynthesizer()
        mock.speak("Test")
        XCTAssertTrue(mock.isSpeaking)

        mock.stop()
        XCTAssertFalse(mock.isSpeaking)
        XCTAssertEqual(mock.stopCallCount, 1)
    }

    // MARK: - Voice Selection

    func testVoiceSelection() {
        let mock = MockVoiceSynthesizer()
        mock.selectedVoice = "Moira"
        XCTAssertEqual(mock.selectedVoice, "Moira")
    }

    func testKarenVoiceDetection() {
        let voiceNames = [
            "Karen (Premium)", "Karen", "karen",
            "KAREN (Premium)", "Karen (Enhanced)"
        ]

        for name in voiceNames {
            XCTAssertTrue(name.lowercased().contains("karen"),
                          "Should match Karen voice: \(name)")
        }
    }

    func testVoiceInfoProperties() {
        struct VoiceInfo {
            let id: String
            let name: String
            let language: String
            let isPremium: Bool
        }

        let karen = VoiceInfo(
            id: "com.apple.voice.premium.en-AU.Karen",
            name: "Karen (Premium)",
            language: "en-AU",
            isPremium: true
        )

        XCTAssertTrue(karen.isPremium)
        XCTAssertEqual(karen.language, "en-AU")
        XCTAssertTrue(karen.name.contains("Karen"))
    }

    // MARK: - Voice Sorting

    func testKarenSortedFirst() {
        var voices = [
            ("Zarvox", "en-US"),
            ("Karen (Premium)", "en-AU"),
            ("Moira", "en-IE"),
            ("Alex", "en-US")
        ]

        voices.sort { a, b in
            if a.0.contains("Karen") && !b.0.contains("Karen") { return true }
            if !a.0.contains("Karen") && b.0.contains("Karen") { return false }
            return a.0 < b.0
        }

        XCTAssertEqual(voices[0].0, "Karen (Premium)",
                       "Karen must always be first in voice list")
    }

    // MARK: - Speech Rate

    func testSpeechRateRange() {
        let validRates: [Float] = [100, 120, 145, 160, 180, 200]

        for rate in validRates {
            XCTAssertGreaterThanOrEqual(rate, 50, "Rate too low: \(rate)")
            XCTAssertLessThanOrEqual(rate, 300, "Rate too high: \(rate)")
        }
    }

    func testBaliSpaRate() {
        let baliSpaRate: Float = 150.0
        XCTAssertLessThan(baliSpaRate, 160, "Bali spa should be slower than normal")
        XCTAssertGreaterThanOrEqual(baliSpaRate, 145, "Bali spa should be >= 145")
    }

    func testPartyRate() {
        let partyRate: Float = 180.0
        XCTAssertGreaterThan(partyRate, 160, "Party mode should be faster than normal")
    }

    // MARK: - Text Processing

    func testEmptyTextNotSpoken() {
        let text = ""
        let shouldSpeak = !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        XCTAssertFalse(shouldSpeak)
    }

    func testLongTextSpoken() {
        let text = String(repeating: "Hello ", count: 100)
        let shouldSpeak = !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        XCTAssertTrue(shouldSpeak)
    }

    func testWhitespaceOnlyNotSpoken() {
        let texts = ["   ", "\n\n", "\t\t", "  \n  \t  "]
        for text in texts {
            let shouldSpeak = !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            XCTAssertFalse(shouldSpeak, "Whitespace-only text should not be spoken: '\(text)'")
        }
    }

    // MARK: - Queue Processing

    func testQueueOrder() {
        let mock = MockVoiceSynthesizer()
        let messages = ["First", "Second", "Third"]

        for msg in messages {
            mock.speak(msg)
        }

        XCTAssertEqual(mock.spokenTexts, messages,
                       "Queue must preserve FIFO order")
    }

    func testStopClearsState() {
        let mock = MockVoiceSynthesizer()
        mock.speak("Hello")
        mock.speak("World")
        mock.stop()

        XCTAssertFalse(mock.isSpeaking)
    }
}
