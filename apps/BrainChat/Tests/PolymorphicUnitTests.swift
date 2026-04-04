import XCTest
@testable import BrainChatLib

// =============================================================================
// Unit Tests — Fast, isolated, no I/O
//
// Polymorphism is at the heart of BrainChat:
//   • 7 LLM providers behind protocol-based streaming interfaces
//   • 4 speech-to-text engines via SpeechEngine enum
//   • 4 voice-output engines via VoiceOutputEngine enum
//   • 4 layered response tiers via LayerTier
//
// Every test here validates that polymorphic dispatch works correctly
// through mock implementations of the Streaming protocols.
// =============================================================================

// MARK: - Protocol Polymorphism: All 7 LLM providers

final class PolymorphicLLMDispatchTests: XCTestCase {

    /// Proves each provider dispatches through its own protocol-conforming type.
    /// The LLMRouter holds `any ClaudeStreaming`, `any OpenAIStreaming`, etc.
    /// — textbook protocol-oriented polymorphism.
    @MainActor
    func testClaudeDispatchesViaMockProtocol() async {
        let router = makeRouter(
            claudeHandler: { _, _, _, _ in "Claude via protocol" }
        )
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time")],
            configuration: makeConfig(provider: .claude, groqAPIKey: ""),
            onEvent: { _ in }
        )
        XCTAssertEqual(result, "Claude via protocol")
    }

    @MainActor
    func testGPTDispatchesViaMockProtocol() async {
        let router = makeRouter(
            gptHandler: { _, _, _ in "GPT via protocol" }
        )
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time")],
            configuration: makeConfig(provider: .gpt, groqAPIKey: ""),
            onEvent: { _ in }
        )
        XCTAssertEqual(result, "GPT via protocol")
    }

    @MainActor
    func testOllamaDispatchesViaMockProtocol() async {
        let router = makeRouter(
            ollamaHandler: { _, _, _ in "Ollama via protocol" }
        )
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time")],
            configuration: makeConfig(provider: .ollama, groqAPIKey: ""),
            onEvent: { _ in }
        )
        XCTAssertEqual(result, "Ollama via protocol")
    }

    @MainActor
    func testGroqDispatchesViaMockProtocol() async {
        let router = makeRouter(
            groqHandler: { _, _, _ in "Groq via protocol" }
        )
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time")],
            configuration: makeConfig(provider: .groq),
            onEvent: { _ in }
        )
        XCTAssertEqual(result, "Groq via protocol")
    }

    @MainActor
    func testGrokDispatchesViaMockProtocol() async {
        let router = makeRouter(
            grokHandler: { _, _, _ in "Grok via protocol" }
        )
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time")],
            configuration: makeConfig(provider: .grok, groqAPIKey: ""),
            onEvent: { _ in }
        )
        XCTAssertEqual(result, "Grok via protocol")
    }

    @MainActor
    func testGeminiDispatchesViaMockProtocol() async {
        let router = makeRouter(
            geminiHandler: { _, _, _, _ in "Gemini via protocol" }
        )
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time")],
            configuration: makeConfig(provider: .gemini, groqAPIKey: ""),
            onEvent: { _ in }
        )
        XCTAssertEqual(result, "Gemini via protocol")
    }

    @MainActor
    func testCopilotDispatchesViaMockProtocol() async {
        let box = CopilotRunnerBox()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: box, result: .success("Copilot via protocol"))
        )
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "write a function")],
            configuration: makeConfig(provider: .copilot),
            onEvent: { _ in }
        )
        XCTAssertEqual(result, "Copilot via protocol")
    }
}

// MARK: - LLMProvider Enum Polymorphism

final class LLMProviderPolymorphismTests: XCTestCase {

    func testAllProvidersHaveUniqueRawValues() {
        let rawValues = LLMProvider.allCases.map(\.rawValue)
        XCTAssertEqual(Set(rawValues).count, rawValues.count, "Every provider must have a unique rawValue")
    }

    func testAllProvidersHaveIcon() {
        for provider in LLMProvider.allCases {
            XCTAssertFalse(provider.iconName.isEmpty, "\(provider) must have an icon")
        }
    }

    func testAllProvidersHaveDefaultModel() {
        for provider in LLMProvider.allCases {
            XCTAssertFalse(provider.defaultModel.isEmpty, "\(provider) must have a default model")
        }
    }

    func testFreeProvidersDoNotRequireAPIKey() {
        XCTAssertFalse(LLMProvider.ollama.requiresAPIKey)
        XCTAssertFalse(LLMProvider.copilot.requiresAPIKey)
    }

    func testPaidProvidersRequireAPIKey() {
        let paid: [LLMProvider] = [.claude, .gpt, .grok, .gemini, .groq]
        for p in paid {
            XCTAssertTrue(p.requiresAPIKey, "\(p) must require an API key")
        }
    }

    func testKeyKindNilForFreeProviders() {
        XCTAssertNil(LLMProvider.ollama.keyKind)
        XCTAssertNil(LLMProvider.copilot.keyKind)
    }

    func testKeyKindMapsCorrectlyForPaidProviders() {
        XCTAssertEqual(LLMProvider.claude.keyKind, .claude)
        XCTAssertEqual(LLMProvider.gpt.keyKind, .openAI)
        XCTAssertEqual(LLMProvider.grok.keyKind, .grok)
        XCTAssertEqual(LLMProvider.gemini.keyKind, .gemini)
        XCTAssertEqual(LLMProvider.groq.keyKind, .groq)
    }

    func testCostHierarchyIsMonotonicallyNonDecreasing() {
        let costs = [
            LLMProvider.ollama.estimatedCostPer1kTokens,
            LLMProvider.groq.estimatedCostPer1kTokens,
            LLMProvider.gemini.estimatedCostPer1kTokens,
            LLMProvider.grok.estimatedCostPer1kTokens,
            LLMProvider.gpt.estimatedCostPer1kTokens,
            LLMProvider.claude.estimatedCostPer1kTokens,
        ]
        for i in costs.indices.dropLast() {
            XCTAssertLessThanOrEqual(costs[i], costs[i + 1])
        }
    }

    func testDisplayPricingIsNonEmpty() {
        for provider in LLMProvider.allCases {
            XCTAssertFalse(provider.displayPricing.isEmpty)
        }
    }

    func testYoloSystemPromptContainsAutonomous() {
        for provider in LLMProvider.allCases {
            XCTAssertTrue(provider.yoloSystemPrompt.contains("AUTONOMOUS"))
        }
    }
}

// MARK: - SpeechEngine Polymorphism (STT)

final class SpeechEnginePolymorphismTests: XCTestCase {

    func testAllSpeechEnginesHaveUniqueRawValues() {
        let rawValues = SpeechEngine.allCases.map(\.rawValue)
        XCTAssertEqual(Set(rawValues).count, rawValues.count)
    }

    func testAllSpeechEnginesHaveDescription() {
        for engine in SpeechEngine.allCases {
            XCTAssertFalse(engine.description.isEmpty)
        }
    }

    func testAllSpeechEnginesHaveIcon() {
        for engine in SpeechEngine.allCases {
            XCTAssertFalse(engine.icon.isEmpty)
        }
    }

    func testOnlyWhisperAPIRequiresAPIKey() {
        for engine in SpeechEngine.allCases {
            if engine == .whisperAPI {
                XCTAssertTrue(engine.requiresAPIKey)
            } else {
                XCTAssertFalse(engine.requiresAPIKey)
            }
        }
    }

    func testLocalEnginesAreFlagged() {
        XCTAssertTrue(SpeechEngine.whisperKit.isLocal)
        XCTAssertTrue(SpeechEngine.whisperCpp.isLocal)
        XCTAssertFalse(SpeechEngine.appleDictation.isLocal)
        XCTAssertFalse(SpeechEngine.whisperAPI.isLocal)
    }

    func testStoredValueInitializerHandlesLegacyNames() {
        XCTAssertEqual(SpeechEngine(storedValue: "Apple Dictation"), .appleDictation)
        XCTAssertEqual(SpeechEngine(storedValue: "WhisperKit (Local)"), .whisperKit)
        XCTAssertEqual(SpeechEngine(storedValue: "faster-whisper (Local)"), .whisperKit)
        XCTAssertEqual(SpeechEngine(storedValue: "OpenAI Whisper API"), .whisperAPI)
        XCTAssertEqual(SpeechEngine(storedValue: "whisper.cpp (Local)"), .whisperCpp)
        XCTAssertNil(SpeechEngine(storedValue: "nonexistent"))
    }
}

// MARK: - VoiceOutputEngine Polymorphism (TTS)

final class VoiceOutputEnginePolymorphismTests: XCTestCase {

    func testAllVoiceOutputEnginesHaveUniqueRawValues() {
        let rawValues = VoiceOutputEngine.allCases.map(\.rawValue)
        XCTAssertEqual(Set(rawValues).count, rawValues.count)
    }

    func testOfflineEnginesDoNotRequireKey() {
        for engine in VoiceOutputEngine.allCases where engine.isOffline {
            XCTAssertFalse(engine.requiresAPIKey, "\(engine) is offline, shouldn't need API key")
        }
    }

    func testCloudEnginesRequireKey() {
        for engine in VoiceOutputEngine.allCases where !engine.isOffline {
            XCTAssertTrue(engine.requiresAPIKey, "\(engine) is cloud, should need API key")
        }
    }

    func testCrossPlatformFlagExcludesMacOSNative() {
        XCTAssertFalse(VoiceOutputEngine.macOS.crossPlatform)
        XCTAssertTrue(VoiceOutputEngine.cartesia.crossPlatform)
        XCTAssertTrue(VoiceOutputEngine.piper.crossPlatform)
        XCTAssertTrue(VoiceOutputEngine.elevenLabs.crossPlatform)
    }

    func testPlatformDefaultIsValid() {
        let defaultEngine = VoiceOutputEngine.platformDefault
        XCTAssertTrue(VoiceOutputEngine.allCases.contains(defaultEngine))
    }
}

// MARK: - SafetyVerdict Polymorphism

final class SafetyVerdictTests: XCTestCase {

    func testAllowedEquality() {
        XCTAssertEqual(SafetyVerdict.allowed, .allowed)
    }

    func testBlockedCarriesReason() {
        let verdict = SafetyVerdict.blocked(reason: "rm -rf /")
        if case .blocked(let reason) = verdict {
            XCTAssertEqual(reason, "rm -rf /")
        } else {
            XCTFail("Expected .blocked")
        }
    }

    func testRequiresConfirmationCarriesReason() {
        let verdict = SafetyVerdict.requiresConfirmation(reason: "git push --force")
        if case .requiresConfirmation(let reason) = verdict {
            XCTAssertEqual(reason, "git push --force")
        } else {
            XCTFail("Expected .requiresConfirmation")
        }
    }

    func testAllActionCategoriesHaveRawValue() {
        let categories: [ActionCategory] = [
            .fileCreate, .fileEdit, .fileDelete,
            .shellCommand, .gitOperation, .codeGenerate,
            .appLaunch, .network, .system
        ]
        for cat in categories {
            XCTAssertFalse(cat.rawValue.isEmpty)
        }
    }
}

// MARK: - ChatMessage & ConversationStore

final class ChatMessageTests: XCTestCase {

    func testAccessibilityDescriptionIncludesRoleAndContent() {
        let msg = ChatMessage(role: .user, content: "Hello Karen")
        XCTAssertTrue(msg.accessibilityDescription.contains("You"))
        XCTAssertTrue(msg.accessibilityDescription.contains("Hello Karen"))
    }

    func testAccessibilityDescriptionIncludesWeavingPhase() {
        let msg = ChatMessage(role: .assistant, content: "Answer", weavingPhase: .thinking)
        XCTAssertTrue(msg.accessibilityDescription.contains("Thinking deeper"))
    }

    func testRoleToAIRoleMapping() {
        XCTAssertEqual(ChatMessage.Role.user.aiRole, .user)
        XCTAssertEqual(ChatMessage.Role.assistant.aiRole, .assistant)
        XCTAssertEqual(ChatMessage.Role.copilot.aiRole, .assistant)
        XCTAssertEqual(ChatMessage.Role.system.aiRole, .system)
    }
}

// MARK: - SSE Stream Parser

final class SSEStreamParserTests: XCTestCase {

    func testParseDataLineExtractsPayload() {
        let result = SSEStreamParser.parseDataLine("data: {\"text\":\"hello\"}")
        XCTAssertEqual(result, "{\"text\":\"hello\"}")
    }

    func testParseDataLineReturnsNilForNonDataLine() {
        XCTAssertNil(SSEStreamParser.parseDataLine("event: message"))
        XCTAssertNil(SSEStreamParser.parseDataLine(""))
        XCTAssertNil(SSEStreamParser.parseDataLine(": comment"))
    }

    func testIsCompleteDetectsDONE() {
        XCTAssertTrue(SSEStreamParser.isComplete("[DONE]"))
        XCTAssertFalse(SSEStreamParser.isComplete("{\"text\":\"hi\"}"))
    }

    func testExtractDeltaFromOpenAIFormat() {
        let json = """
        {"choices":[{"delta":{"content":"Hello"}}]}
        """
        XCTAssertEqual(SSEStreamParser.extractDelta(json), "Hello")
    }

    func testExtractDeltaReturnsNilForEmptyContent() {
        let json = """
        {"choices":[{"delta":{"content":""}}]}
        """
        XCTAssertNil(SSEStreamParser.extractDelta(json))
    }

    func testExtractDeltaReturnsNilForMalformedJSON() {
        XCTAssertNil(SSEStreamParser.extractDelta("not json"))
    }
}

// MARK: - Request Classification

final class RequestClassificationTests: XCTestCase {

    @MainActor
    func testCodingRequestsDetected() {
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "write code in Swift"), .coding)
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "implement a parser"), .coding)
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "refactor this function"), .coding)
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "debug this crash"), .coding)
    }

    @MainActor
    func testQuickRequestsDetected() {
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "hi"), .quick)
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "thanks"), .quick)
        XCTAssertEqual(LLMRouter.classifyRequestType(for: "hey"), .quick)
    }

    @MainActor
    func testChatRequestsDetected() {
        // Long enough to not be classified as "quick" (>40 chars typically)
        let result = LLMRouter.classifyRequestType(for: "explain the theory of relativity in detail and how it relates to space-time curvature")
        XCTAssertEqual(result, .chat)
    }

    @MainActor
    func testEmptyPromptDefaultsToChat() {
        XCTAssertEqual(LLMRouter.classifyRequestType(for: ""), .chat)
    }

    @MainActor
    func testCodingRoutesToCopilot() {
        XCTAssertEqual(LLMRouter.recommendedProvider(for: .coding, selectedProvider: .claude), .copilot)
    }

    @MainActor
    func testChatRoutesToSelectedProvider() {
        XCTAssertEqual(LLMRouter.recommendedProvider(for: .chat, selectedProvider: .gemini), .gemini)
    }

    @MainActor
    func testQuickRoutesToGroqWhenConfigured() {
        XCTAssertEqual(LLMRouter.recommendedProvider(for: .quick, selectedProvider: .claude, hasGroqConfiguration: true), .groq)
    }
}

// MARK: - LLMRouterConfiguration

final class LLMRouterConfigurationTests: XCTestCase {

    func testEffectiveSystemPromptIncludesYoloWhenEnabled() {
        let config = makeConfig(provider: .claude, yoloMode: true)
        XCTAssertTrue(config.effectiveSystemPrompt.contains("AUTONOMOUS MODE ACTIVE"))
    }

    func testEffectiveSystemPromptOmitsYoloWhenDisabled() {
        let config = makeConfig(provider: .claude, yoloMode: false)
        XCTAssertFalse(config.effectiveSystemPrompt.contains("AUTONOMOUS MODE ACTIVE"))
    }

    func testHasGroqConfigurationDetectsKey() {
        let withKey = LLMRouterConfiguration(provider: .groq, systemPrompt: "", groqAPIKey: "gsk-test")
        let withoutKey = LLMRouterConfiguration(provider: .groq, systemPrompt: "", groqAPIKey: "")
        XCTAssertTrue(withKey.hasGroqConfiguration)
        XCTAssertFalse(withoutKey.hasGroqConfiguration)
    }
}

// MARK: - AIServiceError

final class AIServiceErrorTests: XCTestCase {

    func testMissingAPIKeyDescription() {
        let error = AIServiceError.missingAPIKey("Claude")
        XCTAssertTrue(error.errorDescription!.contains("Claude"))
    }

    func testHTTPStatusEquality() {
        XCTAssertTrue(AIServiceError.httpStatus(429, "rate limited") == .httpStatus(429, "rate limited"))
        XCTAssertFalse(AIServiceError.httpStatus(429, "a") == .httpStatus(500, "a"))
    }

    func testInvalidResponseEquality() {
        XCTAssertTrue(AIServiceError.invalidResponse == .invalidResponse)
    }
}

// MARK: - Helpers

@MainActor
private func makeRouter(
    claudeHandler: @escaping @Sendable (String, String, String, [AIChatMessage]) async throws -> String = { _, _, _, _ in "claude" },
    gptHandler: @escaping @Sendable (String, String, [AIChatMessage]) async throws -> String = { _, _, _ in "gpt" },
    ollamaHandler: @escaping @Sendable (String, String, [AIChatMessage]) async throws -> String = { _, _, _ in "ollama" },
    groqHandler: @escaping @Sendable (String, String, [AIChatMessage]) async throws -> String = { _, _, _ in "groq" },
    grokHandler: @escaping @Sendable (String, String, [AIChatMessage]) async throws -> String = { _, _, _ in "grok" },
    geminiHandler: @escaping @Sendable (String, String, String, [AIChatMessage]) async throws -> String = { _, _, _, _ in "gemini" }
) -> LLMRouter {
    LLMRouter(
        claudeAPI: MockClaudeStreamer(handler: claudeHandler),
        openAIAPI: MockOpenAIStreamer(handler: gptHandler),
        ollamaAPI: MockOllamaStreamer(handler: ollamaHandler),
        groqClient: MockGroqStreamer(handler: groqHandler),
        grokClient: MockGrokStreamer(handler: grokHandler),
        geminiClient: MockGeminiStreamer(handler: geminiHandler),
        copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
    )
}
