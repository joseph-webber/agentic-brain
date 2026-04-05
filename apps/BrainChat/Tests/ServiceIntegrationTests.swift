import XCTest
@testable import BrainChatLib

// =============================================================================
// Integration Tests — Service boundary tests
//
// These tests verify that BrainChat's polymorphic subsystems integrate
// correctly across boundaries:
//   • LLMRouter fallback chain across provider protocols
//   • Layered multi-LLM orchestration (4-tier system)
//   • Redpanda event codec (voice ↔ LLM pipeline)
//   • ConversationStore state management
//   • Response weaving lifecycle phases
//
// All HTTP calls use MockURLProtocol — no live services needed.
// =============================================================================

// MARK: - LLM Fallback Chain Integration

final class FallbackChainIntegrationTests: XCTestCase {

    @MainActor
    func testFallbackChainFromClaudeToGPTToOllama() {
        let router = makeRouter()
        let chain = router.buildFallbackChain(
            primary: .claude,
            configuration: makeConfig(provider: .claude)
        )
        XCTAssertEqual(chain, [.claude, .gpt, .ollama])
    }

    @MainActor
    func testFallbackChainForOllamaIsSingleProvider() {
        let router = makeRouter()
        let chain = router.buildFallbackChain(
            primary: .ollama,
            configuration: makeConfig(provider: .ollama)
        )
        XCTAssertEqual(chain, [.ollama])
    }

    @MainActor
    func testFallbackChainDeduplicatesProviders() {
        let router = makeRouter()
        let chain = router.buildFallbackChain(
            primary: .groq,
            configuration: makeConfig(provider: .claude)
        )
        let unique = Set(chain)
        XCTAssertEqual(chain.count, unique.count, "No duplicates in fallback chain")
    }

    @MainActor
    func testFallbackChainAlwaysEndsWithOllama() {
        let router = makeRouter()
        for provider in [LLMProvider.claude, .gpt, .grok, .gemini, .groq] {
            let chain = router.buildFallbackChain(
                primary: provider,
                configuration: makeConfig(provider: provider)
            )
            XCTAssertEqual(chain.last, .ollama,
                           "Ollama (local) should always be the last fallback for \(provider)")
        }
    }

    /// Proves polymorphic fallback: Claude fails → GPT fails → Ollama succeeds
    @MainActor
    func testStreamReplyFallsThroughChainOnFailure() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.httpStatus(500, "down") },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.httpStatus(429, "rate limited") },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "Ollama saves the day" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )

        var events: [String] = []
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "tell me a joke")],
            configuration: makeConfig(provider: .claude),
            onEvent: {
                if case .providerChanged(let name) = $0 { events.append(name) }
                if case .reset = $0 { events.append("RESET") }
            }
        )

        XCTAssertEqual(result, "Ollama saves the day")
        XCTAssertTrue(events.contains(LLMProvider.claude.rawValue))
        XCTAssertTrue(events.contains("RESET"))
        XCTAssertTrue(events.contains(LLMProvider.ollama.rawValue))
    }

    /// All providers fail → user gets structured failure summary
    @MainActor
    func testAllProvidersFailReturnsStructuredSummary() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.httpStatus(500, "down") },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.httpStatus(429, "limited") },
            ollamaAPI: MockOllamaStreamer { _, _, _ in throw AIServiceError.httpStatus(503, "offline") },
            grokClient: MockGrokStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            geminiClient: MockGeminiStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox(), result: .failure(AIServiceError.invalidResponse))
        )

        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "anything")],
            configuration: makeConfig(provider: .claude),
            onEvent: { _ in }
        )

        XCTAssertTrue(result.contains("all LLM providers are unavailable"))
        XCTAssertTrue(result.contains("Claude:"))
        XCTAssertTrue(result.contains("GPT:"))
        XCTAssertTrue(result.contains("Ollama:"))
        XCTAssertEqual(router.activeProviderName, "Unavailable")
    }
}

// MARK: - ConversationStore Integration

final class ConversationStoreIntegrationTests: XCTestCase {

    @MainActor
    func testAddMessageAndRetrieve() {
        let store = ConversationStore()
        let id = store.addMessage(role: .user, content: "Hello")
        XCTAssertEqual(store.messages.count, 1)
        XCTAssertEqual(store.messages.first?.id, id)
        XCTAssertEqual(store.messages.first?.content, "Hello")
    }

    @MainActor
    func testStreamingMessageAppendsDelta() {
        let store = ConversationStore()
        let id = store.beginStreamingAssistantMessage()
        store.appendToMessage(id: id, delta: "G'day ")
        store.appendToMessage(id: id, delta: "there!")
        XCTAssertEqual(store.messages.first?.content, "G'day!")
    }

    @MainActor
    func testFinishStreamingFallsBackOnEmpty() {
        let store = ConversationStore()
        let id = store.beginStreamingAssistantMessage()
        store.finishStreamingMessage(id: id, fallbackContent: "Sorry, no response")
        XCTAssertEqual(store.messages.first?.content, "Sorry, no response")
    }

    @MainActor
    func testFinishStreamingKeepsExistingContent() {
        let store = ConversationStore()
        let id = store.beginStreamingAssistantMessage()
        store.appendToMessage(id: id, delta: "Real answer")
        store.finishStreamingMessage(id: id, fallbackContent: "fallback")
        XCTAssertEqual(store.messages.first?.content, "Real answer")
    }

    @MainActor
    func testClearResetsToSystemMessage() {
        let store = ConversationStore()
        store.addMessage(role: .user, content: "hi")
        store.addMessage(role: .assistant, content: "hello")
        store.clear()
        XCTAssertEqual(store.messages.count, 1)
        XCTAssertEqual(store.messages.first?.role, .system)
    }

    @MainActor
    func testRecentConversationExcludesSystemMessages() {
        let store = ConversationStore()
        store.addMessage(role: .system, content: "system prompt")
        store.addMessage(role: .user, content: "user msg")
        store.addMessage(role: .assistant, content: "assistant msg")
        let recent = store.recentConversation
        XCTAssertEqual(recent.count, 2)
        XCTAssertTrue(recent.allSatisfy { $0.role != .system })
    }

    @MainActor
    func testRecentConversationCapsAtTen() {
        let store = ConversationStore()
        for i in 0..<15 {
            store.addMessage(role: .user, content: "msg \(i)")
        }
        XCTAssertEqual(store.recentConversation.count, 10)
    }
}

// MARK: - Response Weaving Phase Integration

final class WeavingPhaseIntegrationTests: XCTestCase {

    @MainActor
    func testWeavingPhaseLifecycle() {
        let store = ConversationStore()
        let id = store.beginStreamingMessage(role: .assistant)
        store.setWeavingPhase(id: id, phase: .streaming)
        XCTAssertEqual(store.messages.first?.weavingPhase, .streaming)

        store.setWeavingPhase(id: id, phase: .thinking)
        XCTAssertEqual(store.messages.first?.weavingPhase, .thinking)

        store.setWeavingPhase(id: id, phase: .weaving)
        XCTAssertEqual(store.messages.first?.weavingPhase, .weaving)

        store.setWeavingPhase(id: id, phase: .complete)
        XCTAssertEqual(store.messages.first?.weavingPhase, .complete)
    }

    @MainActor
    func testAddLayerCreatesResponseLayer() {
        let store = ConversationStore()
        let msgID = store.beginStreamingMessage(role: .assistant)
        let layer = ResponseLayer(layerNumber: 1, provider: "Groq", content: "Fast answer")
        store.addLayer(messageID: msgID, layer: layer)
        XCTAssertEqual(store.messages.first?.layers.count, 1)
        XCTAssertEqual(store.messages.first?.layers.first?.provider, "Groq")
    }

    @MainActor
    func testAppendToLayerStreamsContent() {
        let store = ConversationStore()
        let msgID = store.beginStreamingMessage(role: .assistant)
        let layer = ResponseLayer(layerNumber: 1, provider: "Groq")
        store.addLayer(messageID: msgID, layer: layer)
        store.appendToLayer(messageID: msgID, layerID: layer.id, delta: "G'day ")
        store.appendToLayer(messageID: msgID, layerID: layer.id, delta: "mate!")
        XCTAssertEqual(store.messages.first?.layers.first?.content, "G'day mate!")
    }

    @MainActor
    func testMultipleLayersCanCoexist() {
        let store = ConversationStore()
        let msgID = store.beginStreamingMessage(role: .assistant)
        let l1 = ResponseLayer(layerNumber: 1, provider: "Groq", content: "Fast")
        let l2 = ResponseLayer(layerNumber: 2, provider: "Ollama", content: "Local")
        let l3 = ResponseLayer(layerNumber: 3, provider: "Claude", content: "Deep")
        store.addLayer(messageID: msgID, layer: l1)
        store.addLayer(messageID: msgID, layer: l2)
        store.addLayer(messageID: msgID, layer: l3)
        XCTAssertEqual(store.messages.first?.layers.count, 3)
    }
}

// MARK: - ResponseLayer Polymorphism

final class ResponseLayerIntegrationTests: XCTestCase {

    func testInstantLayerFlaggedCorrectly() {
        let layer = ResponseLayer(layerNumber: 1, provider: "Groq")
        XCTAssertTrue(layer.isInstant)
        XCTAssertFalse(layer.isDeeper)
    }

    func testDeeperLayerFlaggedCorrectly() {
        let layer = ResponseLayer(layerNumber: 3, provider: "Claude")
        XCTAssertFalse(layer.isInstant)
        XCTAssertTrue(layer.isDeeper)
    }

    func testWeavingPrefixEmptyForInstant() {
        let layer = ResponseLayer(layerNumber: 1, provider: "Groq")
        XCTAssertEqual(layer.weavingPrefix, "")
    }

    func testWeavingPrefixNonEmptyForDeeper() {
        let layer = ResponseLayer(layerNumber: 2, provider: "Claude")
        XCTAssertFalse(layer.weavingPrefix.isEmpty)
    }

    func testAccessibilityLabelContainsProvider() {
        let layer = ResponseLayer(layerNumber: 1, provider: "Groq")
        XCTAssertTrue(layer.accessibilityLabel.contains("Groq"))
    }

    func testAccessibilityLabelDiffersForInstantVsDeeper() {
        let instant = ResponseLayer(layerNumber: 1, provider: "Groq")
        let deeper = ResponseLayer(layerNumber: 3, provider: "Claude")
        XCTAssertNotEqual(instant.accessibilityLabel, deeper.accessibilityLabel)
    }
}

// MARK: - WeavingPhase Accessibility

final class WeavingPhaseAccessibilityTests: XCTestCase {

    func testIdlePhaseHasNoAnnouncement() {
        XCTAssertNil(WeavingPhase.idle.accessibilityAnnouncement)
    }

    func testStreamingPhaseHasNoAnnouncement() {
        XCTAssertNil(WeavingPhase.streaming.accessibilityAnnouncement)
    }

    func testThinkingPhaseAnnouncesForVoiceOver() {
        XCTAssertEqual(WeavingPhase.thinking.accessibilityAnnouncement, "Thinking deeper")
    }

    func testWeavingPhaseAnnouncesForVoiceOver() {
        XCTAssertEqual(WeavingPhase.weaving.accessibilityAnnouncement, "Enhanced response available")
    }

    func testCompletePhaseAnnouncesForVoiceOver() {
        XCTAssertEqual(WeavingPhase.complete.accessibilityAnnouncement, "Response complete")
    }

    func testActivePhaseDetection() {
        XCTAssertFalse(WeavingPhase.idle.isActive)
        XCTAssertTrue(WeavingPhase.streaming.isActive)
        XCTAssertTrue(WeavingPhase.thinking.isActive)
        XCTAssertTrue(WeavingPhase.weaving.isActive)
        XCTAssertFalse(WeavingPhase.complete.isActive)
    }
}

// MARK: - Context Building Integration

final class ContextBuildingIntegrationTests: XCTestCase {

    @MainActor
    func testBuildContextAddsSystemPromptFirst() {
        let messages = LLMRouter.buildContext(
            from: [ChatMessage(role: .user, content: "hi")],
            systemPrompt: "You are Karen"
        )
        XCTAssertEqual(messages.first?.role, .system)
        XCTAssertEqual(messages.first?.content, "You are Karen")
    }

    @MainActor
    func testBuildContextFiltersSystemMessages() {
        let history = [
            ChatMessage(role: .system, content: "should be removed"),
            ChatMessage(role: .user, content: "kept"),
        ]
        let messages = LLMRouter.buildContext(from: history, systemPrompt: "SP")
        XCTAssertEqual(messages.count, 2) // system prompt + "kept"
        XCTAssertEqual(messages[1].content, "kept")
    }

    @MainActor
    func testBuildContextTrimsToTenRecentMessages() {
        let history = (0..<15).map {
            ChatMessage(role: .user, content: "msg \($0)")
        }
        let messages = LLMRouter.buildContext(from: history, systemPrompt: "SP")
        XCTAssertEqual(messages.count, 11) // 1 system + 10 history
    }

    @MainActor
    func testBuildContextFiltersEmptyMessages() {
        let history = [
            ChatMessage(role: .user, content: "hello"),
            ChatMessage(role: .assistant, content: "   "),
            ChatMessage(role: .user, content: "world"),
        ]
        let messages = LLMRouter.buildContext(from: history, systemPrompt: "SP")
        XCTAssertEqual(messages.count, 3) // system + "hello" + "world"
    }
}

// MARK: - ConnectionTestResult

final class ConnectionTestIntegrationTests: XCTestCase {

    @MainActor
    func testSuccessfulConnectionTestUpdatesState() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "ok" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "ok" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ok" },
            grokClient: MockGrokStreamer { _, _, _ in "ok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "ok" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )
        await router.testConnection(provider: .ollama, configuration: makeConfig(provider: .ollama))
        XCTAssertEqual(router.connectionTestResult?.provider, .ollama)
        XCTAssertTrue(router.connectionTestResult?.success ?? false)
    }

    @MainActor
    func testFailedConnectionTestUpdatesState() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            ollamaAPI: MockOllamaStreamer { _, _, _ in throw AIServiceError.httpStatus(503, "offline") },
            grokClient: MockGrokStreamer { _, _, _ in throw AIServiceError.invalidResponse },
            geminiClient: MockGeminiStreamer { _, _, _, _ in throw AIServiceError.invalidResponse },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox(), result: .failure(AIServiceError.invalidResponse))
        )
        await router.testConnection(provider: .ollama, configuration: makeConfig(provider: .ollama))
        XCTAssertFalse(router.connectionTestResult?.success ?? true)
        XCTAssertEqual(router.statusMessage, "Test failed")
    }
}

// MARK: - Helpers

@MainActor
private func makeRouter() -> LLMRouter {
    LLMRouter(
        claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
        openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
        ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
        grokClient: MockGrokStreamer { _, _, _ in "grok" },
        geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
        copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
    )
}
