import XCTest
@testable import BrainChat

@MainActor
final class TestFullConversation: XCTestCase {
    func testEndToEndChatFlowAddsMessagesAndSpeaks() async {
        let http = MockHTTPClient()
        http.nextResult = .success((
            TestFixtures.jsonData(["message": ["content": "Hello there"]]),
            HTTPURLResponse(url: URL(string: "http://localhost")!, statusCode: 200, httpVersion: nil, headerFields: nil)!
        ))
        let voiceSynth = MockVoiceSynthesizer()
        let coordinator = BrainChatCoordinator(
            store: ConversationStore(),
            voiceManager: VoiceManager(synthesizer: voiceSynth),
            speechManager: SpeechManager(controller: MockSpeechRecognizer(), requestAuthorizationOnInit: false),
            aiManager: AIManager(httpClient: http),
            codeAssistant: CodeAssistant(copilot: CopilotBridge(runner: MockCopilotCLI()), system: MockSystemCommands()),
            configuration: TestFixtures.ollamaConfig
        )

        let expectation = expectation(description: "response")
        coordinator.sendUserMessage("Hi") { text in
            XCTAssertEqual(text, "Hello there")
            expectation.fulfill()
        }
        await fulfillment(of: [expectation], timeout: 1)
        XCTAssertEqual(coordinator.store.messages.map(\.content), ["Hi", "Hello there"])
        XCTAssertEqual(voiceSynth.startedTexts, ["Hello there"])
        XCTAssertTrue(coordinator.store.messages[1].accessibilityDescription.contains("Brain said"))
    }
}
