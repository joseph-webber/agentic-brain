import XCTest
@testable import BrainChatLib

final class LLMRouterTests: XCTestCase {


    @MainActor
    func testProviderMetadataCoversAllComputedProperties() {
        let providers = LLMProvider.allCases
        XCTAssertEqual(providers.map(\.id), providers.map(\.rawValue))
        XCTAssertEqual(LLMProvider.ollama.iconName, "desktopcomputer")
        XCTAssertEqual(LLMProvider.claude.defaultModel, "claude-sonnet-4-20250514")
        XCTAssertTrue(LLMProvider.gpt.requiresAPIKey)
        XCTAssertFalse(LLMProvider.copilot.requiresAPIKey)
        XCTAssertEqual(LLMProvider.grok.keyKind, .grok)
        XCTAssertNil(LLMProvider.ollama.keyKind)
    }



    @MainActor
    func testProviderMetadataCoversRemainingCases() {
        XCTAssertEqual(LLMProvider.claude.iconName, "brain.head.profile")
        XCTAssertEqual(LLMProvider.gpt.iconName, "sparkles")
        XCTAssertEqual(LLMProvider.grok.iconName, "bolt.fill")
        XCTAssertEqual(LLMProvider.gemini.iconName, "diamond.fill")
        XCTAssertEqual(LLMProvider.copilot.iconName, "chevron.left.forwardslash.chevron.right")
        XCTAssertEqual(LLMProvider.ollama.defaultModel, "llama3.2:3b")
        XCTAssertEqual(LLMProvider.gpt.defaultModel, "gpt-4o")
        XCTAssertEqual(LLMProvider.grok.defaultModel, "grok-3-latest")
        XCTAssertEqual(LLMProvider.gemini.defaultModel, "gemini-2.5-flash")
        XCTAssertEqual(LLMProvider.copilot.defaultModel, "copilot-cli")
        XCTAssertEqual(LLMProvider.claude.keyKind, .claude)
        XCTAssertEqual(LLMProvider.gpt.keyKind, .openAI)
        XCTAssertEqual(LLMProvider.gemini.keyKind, .gemini)
    }



    @MainActor
    func testInitFallsBackToOllamaForInvalidSavedProvider() {
        UserDefaults.standard.set("invalid-provider", forKey: "selectedLLMProvider")
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "ok" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "ok" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ok" },
            grokClient: MockGrokStreamer { _, _, _ in "ok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "ok" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        XCTAssertEqual(router.selectedProvider, .ollama)
    }

    @MainActor
    func testInitReadsSavedProviderFromUserDefaults() {
        UserDefaults.standard.set(LLMProvider.gpt.rawValue, forKey: "selectedLLMProvider")
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "ok" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "ok" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ok" },
            grokClient: MockGrokStreamer { _, _, _ in "ok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "ok" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        XCTAssertEqual(router.selectedProvider, .gpt)
    }

    @MainActor
    func testEmptyHistoryUsesSelectedGPTAndEmptyCopilotPromptPath() async {
        let box = CopilotRunnerBox()
        let gptRouter = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt direct" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: box)
        )
        let gptResponse = await gptRouter.streamReply(history: [], configuration: makeConfig(provider: .gpt), onEvent: { _ in })
        XCTAssertEqual(gptResponse, "gpt direct")

        let copilotRouter = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: box, result: .success("copilot empty"))
        )
        let copilotResponse = await copilotRouter.streamReply(history: [], configuration: makeConfig(provider: .copilot), onEvent: { _ in })
        XCTAssertEqual(copilotResponse, "copilot empty")
        XCTAssertEqual(box.capturedPrompt, "")
    }

    @MainActor
    func testSelectedProviderAndYoloPersistToUserDefaults() {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "ok" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "ok" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ok" },
            grokClient: MockGrokStreamer { _, _, _ in "ok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "ok" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        router.selectedProvider = .gemini
        router.yoloMode = true
        XCTAssertEqual(UserDefaults.standard.string(forKey: "selectedLLMProvider"), LLMProvider.gemini.rawValue)
        XCTAssertEqual(UserDefaults.standard.bool(forKey: "yoloModeEnabled"), true)
    }

    @MainActor
    func testFallbackChainForOllamaStaysSingleProvider() {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "ok" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "ok" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ok" },
            grokClient: MockGrokStreamer { _, _, _ in "ok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "ok" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        XCTAssertEqual(router.buildFallbackChain(primary: .ollama, configuration: makeConfig(provider: .ollama)), [.ollama])
    }

    @MainActor
    func testAllProvidersUnavailableReturnsFailureSummary() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.httpStatus(500, "claude down") },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.httpStatus(429, "gpt limited") },
            ollamaAPI: MockOllamaStreamer { _, _, _ in throw AIServiceError.httpStatus(503, "ollama offline") },
            grokClient: MockGrokStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            geminiClient: MockGeminiStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox(), result: .failure(AIServiceError.invalidResponse))
        )
        let response = await router.streamReply(history: [ChatMessage(role: .user, content: "tell me a joke")], configuration: makeConfig(provider: .claude), onEvent: { _ in })
        XCTAssertEqual(router.activeProviderName, "Unavailable")
        XCTAssertEqual(router.statusMessage, "All LLM backends unavailable")
        XCTAssertTrue(response.contains("all LLM providers are unavailable"))
        XCTAssertTrue(response.contains("Claude:"))
        XCTAssertTrue(response.contains("GPT:"))
        XCTAssertTrue(response.contains("Ollama:"))
    }

    func testConnectionTestResultCreatesStableMetadata() {
        let result = ConnectionTestResult(provider: .claude, success: true, message: "ok", latency: 1.2)
        XCTAssertNotNil(result.id)
        XCTAssertEqual(result.provider, .claude)
        XCTAssertEqual(result.message, "ok")
    }

    @MainActor
    func testProviderSelection() {
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "write a Swift function"), .coding)
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "tell me a joke"), .chat)
        XCTAssertEqual(LLMRouter.recommendedProvider(for: .coding, selectedProvider: .claude), .copilot)
        XCTAssertEqual(LLMRouter.recommendedProvider(for: .chat, selectedProvider: .claude), .claude)
    }

    @MainActor
    func testFallbackChainClaudeToGPTToOllama() {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        XCTAssertEqual(router.buildFallbackChain(primary: .claude, configuration: makeConfig(provider: .claude)), [.claude, .gpt, .ollama])
    }

    @MainActor
    func testYoloModeActivation() async {
        let box = CopilotRunnerBox()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            ollamaAPI: MockOllamaStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            grokClient: MockGrokStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            geminiClient: MockGeminiStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            copilotClient: MockCopilotStreamer(box: box, result: .success("done"))
        )
        let config = makeConfig(provider: .claude, yoloMode: true)
        let response = await router.streamReply(history: [ChatMessage(role: .user, content: "implement a parser")], configuration: config, onEvent: { _ in })
        XCTAssertEqual(response, "done")
        XCTAssertEqual(box.capturedPrompt, "/yolo implement a parser")
        XCTAssertTrue(config.effectiveSystemPrompt.contains("AUTONOMOUS MODE ACTIVE"))
    }

    @MainActor
    func testCodingVsChatRouting() async {
        let box = CopilotRunnerBox()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "chat reply" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: box, result: .success("code reply"))
        )
        let codingResponse = await router.streamReply(history: [ChatMessage(role: .user, content: "write code in swift")], configuration: makeConfig(provider: .claude), onEvent: { _ in })
        XCTAssertEqual(codingResponse, "code reply")
        XCTAssertEqual(box.capturedPrompt, "write code in swift")
        let chatResponse = await router.streamReply(history: [ChatMessage(role: .user, content: "tell me a joke")], configuration: makeConfig(provider: .claude), onEvent: { _ in })
        XCTAssertEqual(chatResponse, "chat reply")
    }

    @MainActor
    func testStreamReplyFallsBackThroughChain() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.httpStatus(500, "claude down") },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.httpStatus(429, "gpt limited") },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama save" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        let box = StringArrayBox()
        let response = await router.streamReply(history: [ChatMessage(role: .user, content: "tell me a joke")], configuration: makeConfig(provider: .claude), onEvent: {
            if case .providerChanged(let name) = $0 { box.values.append(name) }
            if case .reset = $0 { box.values.append("RESET") }
        })
        XCTAssertEqual(response, "ollama save")
        XCTAssertTrue(box.values.contains(LLMProvider.claude.rawValue))
        XCTAssertTrue(box.values.contains(LLMProvider.gpt.rawValue))
        XCTAssertTrue(box.values.contains(LLMProvider.ollama.rawValue))
        XCTAssertEqual(box.values.filter { $0 == "RESET" }.count, 2)
    }

    @MainActor
    func testBuildContextTrimsHistoryToTenMessages() {
        let history = (0..<12).map { ChatMessage(role: $0.isMultiple(of: 2) ? .user : .assistant, content: "m\($0)") }
        let messages = LLMRouter.buildContext(from: history, systemPrompt: "system")
        XCTAssertEqual(messages.count, 11)
        XCTAssertEqual(messages.first?.role, .system)
        XCTAssertEqual(messages[1].content, "m2")
        XCTAssertEqual(messages.last?.content, "m11")
    }

    @MainActor
    func testTestConnectionSuccessAndFailureUpdateState() async {
        let successRouter = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "ok" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "ok" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ok" },
            grokClient: MockGrokStreamer { _, _, _ in "ok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "ok" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox(), result: .success("ok"))
        )
        await successRouter.testConnection(provider: .grok, configuration: makeConfig(provider: .grok))
        XCTAssertEqual(successRouter.connectionTestResult?.provider, .grok)
        XCTAssertEqual(successRouter.connectionTestResult?.success, true)

        let failureRouter = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            ollamaAPI: MockOllamaStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            grokClient: MockGrokStreamer { _, _, _ in throw AIServiceError.httpStatus(500, "down") },
            geminiClient: MockGeminiStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox(), result: .failure(AIServiceError.invalidResponse))
        )
        await failureRouter.testConnection(provider: .grok, configuration: makeConfig(provider: .grok))
        XCTAssertEqual(failureRouter.connectionTestResult?.success, false)
        XCTAssertEqual(failureRouter.statusMessage, "Test failed")
    }

    @MainActor
    func testProviderDispatchForGeminiAndGrok() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok reply" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini reply" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        let grok = await router.streamReply(history: [ChatMessage(role: .user, content: "hello there")], configuration: makeConfig(provider: .grok), onEvent: { _ in })
        XCTAssertEqual(grok, "grok reply")
        let gemini = await router.streamReply(history: [ChatMessage(role: .user, content: "hello there")], configuration: makeConfig(provider: .gemini), onEvent: { _ in })
        XCTAssertEqual(gemini, "gemini reply")
    }
}
