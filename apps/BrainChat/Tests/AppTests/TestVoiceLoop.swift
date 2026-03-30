import XCTest
@testable import BrainChat

@MainActor
final class TestVoiceLoop: XCTestCase {
    func testSpeechInToSpeechOutLoop() async {
        let http = MockHTTPClient()
        http.nextResult = .success((
            TestFixtures.jsonData(["message": ["content": "Voice reply"]]),
            HTTPURLResponse(url: URL(string: "http://localhost")!, statusCode: 200, httpVersion: nil, headerFields: nil)!
        ))
        let speech = MockSpeechRecognizer()
        let synth = MockVoiceSynthesizer()
        let coordinator = BrainChatCoordinator(
            store: ConversationStore(),
            voiceManager: VoiceManager(synthesizer: synth),
            speechManager: SpeechManager(controller: speech, requestAuthorizationOnInit: false),
            aiManager: AIManager(httpClient: http),
            codeAssistant: CodeAssistant(copilot: CopilotBridge(runner: MockCopilotCLI()), system: MockSystemCommands()),
            configuration: TestFixtures.ollamaConfig
        )

        coordinator.speechManager.authorizationStatus = .authorized
        coordinator.continuousListening = true
        coordinator.speechManager.handle(.final("How are you?"))
        try? await Task.sleep(nanoseconds: 100_000_000)
        XCTAssertEqual(coordinator.store.messages.count, 2)
        XCTAssertEqual(coordinator.store.messages.last?.content, "Voice reply")
        XCTAssertEqual(synth.startedTexts.last, "Voice reply")
        XCTAssertEqual(speech.startCallCount, 1)
    }
}
