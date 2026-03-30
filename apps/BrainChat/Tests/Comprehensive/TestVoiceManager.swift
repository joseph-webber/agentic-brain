import XCTest
@testable import BrainChatLib

final class TestVoiceManager: XCTestCase {
    func testKarenVoiceIsSortedFirst() async {
        let synth = MockVoiceSynthesizer(voices: [
            .init(id: "sam", name: "Samantha", language: "en_US", isPremium: false),
            .init(id: "karen", name: "Karen (Premium)", language: "en_AU", isPremium: true),
        ])
        let manager = VoiceManager(synthesizer: synth)
        await flushMainQueue()
        XCTAssertEqual(manager.availableVoices.first?.name, "Karen (Premium)")
    }

    func testSpeakQueuesMessages() async {
        let synth = MockVoiceSynthesizer()
        let manager = VoiceManager(synthesizer: synth)
        manager.speak("One")
        manager.speak("Two")
        await flushMainQueue()
        XCTAssertEqual(synth.startedTexts, ["One"])
        synth.finish()
        await flushMainQueue()
        XCTAssertEqual(synth.startedTexts, ["One", "Two"])
    }

    func testSpeakImmediatelyStopsCurrentSpeech() async {
        let synth = MockVoiceSynthesizer()
        let manager = VoiceManager(synthesizer: synth)
        manager.speakImmediately("Urgent")
        await flushMainQueue()
        XCTAssertEqual(synth.stopCallCount, 1)
        XCTAssertEqual(synth.startedTexts.last, "Urgent")
        XCTAssertTrue(manager.isSpeaking)
    }
}
