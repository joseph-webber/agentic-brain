import XCTest
@testable import BrainChat

@MainActor
final class TestCopilotWorkflow: XCTestCase {
    func testCodeGenerationWorkflowUsesCopilotRoute() async {
        let runner = MockCopilotCLI()
        runner.runResult = .success(("```swift\nlet x = 1\n```", "", 0))
        let system = MockSystemCommands()
        let assistant = CodeAssistant(copilot: CopilotBridge(runner: runner), system: system)
        let coordinator = BrainChatCoordinator(
            store: ConversationStore(),
            voiceManager: VoiceManager(synthesizer: MockVoiceSynthesizer()),
            speechManager: SpeechManager(controller: MockSpeechRecognizer(), requestAuthorizationOnInit: false),
            aiManager: AIManager(httpClient: MockHTTPClient()),
            codeAssistant: assistant,
            configuration: TestFixtures.ollamaConfig
        )

        let expectation = expectation(description: "copilot")
        coordinator.runCopilotWorkflow(prompt: "Write a swift function") { response in
            XCTAssertEqual(response.route, .copilot)
            XCTAssertTrue(response.hasCode)
            expectation.fulfill()
        }
        await fulfillment(of: [expectation], timeout: 1)
        XCTAssertEqual(runner.prompts, ["Write a swift function"])
        XCTAssertEqual(coordinator.store.messages.last?.content, "```swift\nlet x = 1\n```")
    }
}
