import XCTest
@testable import BrainChatLib

// =============================================================================
// E2E Tests — Full conversational flows through the polymorphic system
//
// Each test simulates a complete user→system→response cycle:
//   1. User sends a prompt
//   2. LLMRouter classifies it (coding / quick / chat)
//   3. Provider is selected polymorphically
//   4. Fallback chain activates on failure
//   5. Response streams back with events
//   6. ConversationStore records the exchange
//
// These prove the entire pipeline works end-to-end with all 7 providers
// and the 4-tier layered response system.
// =============================================================================

// MARK: - Full Conversation Flow E2E

final class ConversationFlowE2ETests: XCTestCase {

    /// Simulates: User asks a chat question → Claude responds → stored in conversation
    @MainActor
    func testChatQuestionFlowClaudeToConversation() async {
        let store = ConversationStore()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "G'day user! Here's a fun fact." },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )

        let userContent = "tell me a fun fact about Adelaide and its history as a colonial settlement in South Australia"
        store.addMessage(role: .user, content: userContent)
        let streamID = store.beginStreamingAssistantMessage()

        let deltaBox = StringArrayBox()

        let response = await router.streamReply(
            history: store.messages,
            configuration: makeConfig(provider: .claude, groqAPIKey: ""),
            onEvent: { event in
                if case .delta(let text) = event {
                    deltaBox.values.append(text)
                }
            }
        )

        store.replaceMessageContent(id: streamID, content: response)

        XCTAssertEqual(store.messages.count, 2)
        XCTAssertEqual(store.messages[0].role, .user)
        XCTAssertEqual(store.messages[1].role, .assistant)
        XCTAssertTrue(store.messages[1].content.contains("G'day user"))
    }

    /// Simulates: Coding request → auto-routes to Copilot via polymorphic dispatch
    @MainActor
    func testCodingRequestRoutesToCopilot() async {
        let box = CopilotRunnerBox()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude answer" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt answer" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama answer" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: box, result: .success("func hello() { print(\"Hello!\") }"))
        )

        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "write a Swift function for hello world")],
            configuration: makeConfig(provider: .claude),
            onEvent: { _ in }
        )

        XCTAssertTrue(result.contains("func hello"))
        XCTAssertEqual(box.capturedPrompt, "write a Swift function for hello world")
    }

    /// Simulates: Claude + GPT both fail → Ollama (local) saves the conversation
    @MainActor
    func testGracefulDegradationToLocalLLM() async {
        let store = ConversationStore()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in throw AIServiceError.httpStatus(500, "overloaded") },
            openAIAPI: MockOpenAIStreamer { _, _, _ in throw AIServiceError.httpStatus(429, "rate limited") },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "Ollama to the rescue!" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )

        store.addMessage(role: .user, content: "explain the theory of general relativity and how it relates to space-time curvature in detail")
        let streamID = store.beginStreamingAssistantMessage()

        let eventBox = StringArrayBox()
        let response = await router.streamReply(
            history: store.messages,
            configuration: makeConfig(provider: .claude, groqAPIKey: ""),
            onEvent: {
                if case .providerChanged(let name) = $0 { eventBox.values.append(name) }
            }
        )

        store.replaceMessageContent(id: streamID, content: response)

        XCTAssertEqual(response, "Ollama to the rescue!")
        XCTAssertTrue(eventBox.values.contains(LLMProvider.claude.rawValue))
        XCTAssertTrue(eventBox.values.contains(LLMProvider.ollama.rawValue))
    }
}

// MARK: - YOLO Mode E2E

final class YoloModeE2ETests: XCTestCase {

    /// Full YOLO flow: autonomous prompt → Copilot executes with /yolo prefix
    @MainActor
    func testYoloModeRoutesToCopilotWithPrefix() async {
        let box = CopilotRunnerBox()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "gpt" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "gemini" },
            copilotClient: MockCopilotStreamer(box: box, result: .success("Files created successfully"))
        )

        let config = makeConfig(provider: .claude, yoloMode: true)
        let result = await router.streamReply(
            history: [ChatMessage(role: .user, content: "create a REST API scaffold")],
            configuration: config,
            onEvent: { _ in }
        )

        // "create" + "api" are coding keywords → routes to Copilot
        XCTAssertEqual(result, "Files created successfully")
        XCTAssertEqual(box.capturedPrompt, "/yolo create a REST API scaffold")
        XCTAssertTrue(config.effectiveSystemPrompt.contains("AUTONOMOUS MODE ACTIVE"))
    }

    /// YOLO mode system prompt is appended to all providers
    func testYoloSystemPromptAppliedToAllProviders() {
        for provider in LLMProvider.allCases {
            let config = makeConfig(provider: provider, yoloMode: true)
            XCTAssertTrue(config.effectiveSystemPrompt.contains("AUTONOMOUS MODE ACTIVE"),
                          "\(provider) must include YOLO prompt when yoloMode=true")
        }
    }
}

// MARK: - Multi-Provider E2E

final class MultiProviderE2ETests: XCTestCase {

    /// Dispatches through each provider in sequence — proves polymorphic routing
    @MainActor
    func testAllSevenProvidersProduceResponses() async {
        let box = CopilotRunnerBox()
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "Claude response" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "GPT response" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "Ollama response" },
            groqClient: MockGroqStreamer { _, _, _ in "Groq response" },
            grokClient: MockGrokStreamer { _, _, _ in "Grok response" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "Gemini response" },
            copilotClient: MockCopilotStreamer(box: box, result: .success("Copilot response"))
        )

        // Use a chat-length prompt that won't get reclassified as "quick" or "coding"
        let chatPrompt = "explain the theory of relativity in detail and how it relates to space-time curvature"

        let providers: [LLMProvider] = [.claude, .gpt, .ollama, .groq, .grok, .gemini]
        let expected = ["Claude response", "GPT response", "Ollama response",
                        "Groq response", "Grok response", "Gemini response"]

        for (provider, expectedResponse) in zip(providers, expected) {
            // Disable groq override so each provider is used directly
            let config = makeConfig(provider: provider, groqAPIKey: "")
            let result = await router.streamReply(
                history: [ChatMessage(role: .user, content: chatPrompt)],
                configuration: config,
                onEvent: { _ in }
            )
            XCTAssertEqual(result, expectedResponse, "Provider \(provider) must return its response")
        }

        // Copilot: coding prompt routes to copilot automatically
        let codingResult = await router.streamReply(
            history: [ChatMessage(role: .user, content: "write a Swift function for hello world")],
            configuration: makeConfig(provider: .claude),
            onEvent: { _ in }
        )
        XCTAssertEqual(codingResult, "Copilot response")
    }

    /// Provider events are emitted correctly during streaming
    @MainActor
    func testStreamEventsReportProviderChanges() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "Claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "GPT" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "Ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "Grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "Gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )

        let providerBox = StringArrayBox()
        _ = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time curvature")],
            configuration: makeConfig(provider: .gemini, groqAPIKey: ""),
            onEvent: {
                if case .providerChanged(let name) = $0 { providerBox.values.append(name) }
            }
        )

        XCTAssertEqual(providerBox.values.last, LLMProvider.gemini.rawValue)
    }

    /// Delta events contain actual response text
    @MainActor
    func testStreamDeltaEventsContainText() async {
        let router = LLMRouter(
            claudeAPI: MockClaudeStreamer { _, _, _, _ in "Hello from Claude" },
            openAIAPI: MockOpenAIStreamer { _, _, _ in "GPT" },
            ollamaAPI: MockOllamaStreamer { _, _, _ in "Ollama" },
            grokClient: MockGrokStreamer { _, _, _ in "Grok" },
            geminiClient: MockGeminiStreamer { _, _, _, _ in "Gemini" },
            copilotClient: MockCopilotStreamer(box: CopilotRunnerBox())
        )

        let deltaBox = StringArrayBox()
        _ = await router.streamReply(
            history: [ChatMessage(role: .user, content: "explain the theory of relativity in detail and how it relates to space-time curvature")],
            configuration: makeConfig(provider: .claude, groqAPIKey: ""),
            onEvent: {
                if case .delta(let text) = $0 { deltaBox.values.append(text) }
            }
        )

        XCTAssertTrue(deltaBox.values.contains("Hello from Claude"))
    }
}

// MARK: - Layered Response E2E

final class LayeredResponseE2ETests: XCTestCase {

    func testLayerTierOrderingIsCorrect() {
        let tiers: [LayerTier] = [.consensus, .instant, .deep, .fastLocal]
        let sorted = tiers.sorted()
        XCTAssertEqual(sorted, [.instant, .fastLocal, .deep, .consensus])
    }

    func testLayerTimeoutsIncreaseWithTier() {
        let tiers: [LayerTier] = [.instant, .fastLocal, .deep, .consensus]
        for i in tiers.indices.dropLast() {
            XCTAssertLessThan(tiers[i].timeoutSeconds, tiers[i + 1].timeoutSeconds)
        }
    }

    /// Simulates the full 4-layer lifecycle in ConversationStore
    @MainActor
    func testFullLayeredResponseLifecycle() {
        let store = ConversationStore()
        store.addMessage(role: .user, content: "What's the weather?")
        let msgID = store.beginStreamingMessage(role: .assistant)

        // Phase 1: Streaming instant response
        store.setWeavingPhase(id: msgID, phase: .streaming)
        let l1 = ResponseLayer(layerNumber: 1, provider: "Groq", content: "Sunny today!")
        store.addLayer(messageID: msgID, layer: l1)
        store.appendToMessage(id: msgID, delta: "Sunny today!")
        XCTAssertEqual(store.messages.last?.weavingPhase, .streaming)

        // Phase 2: Thinking
        store.setWeavingPhase(id: msgID, phase: .thinking)
        XCTAssertEqual(store.messages.last?.weavingPhase.accessibilityAnnouncement, "Thinking deeper")

        // Phase 3: Weaving deeper response
        store.setWeavingPhase(id: msgID, phase: .weaving)
        let l3 = ResponseLayer(layerNumber: 3, provider: "Claude", content: "")
        store.addLayer(messageID: msgID, layer: l3)
        store.appendToLayer(messageID: msgID, layerID: l3.id, delta: "Actually, ")
        store.appendToLayer(messageID: msgID, layerID: l3.id, delta: "scattered clouds expected.")

        // Phase 4: Complete
        store.setWeavingPhase(id: msgID, phase: .complete)
        XCTAssertEqual(store.messages.last?.weavingPhase, .complete)
        XCTAssertEqual(store.messages.last?.layers.count, 2)
        XCTAssertEqual(store.messages.last?.layers[0].content, "Sunny today!")
        XCTAssertEqual(store.messages.last?.layers[1].content, "Actually, scattered clouds expected.")
    }

    func testLayeredChunkCreation() {
        let chunk = LayeredChunk(layer: .instant, source: "groq", content: "Fast!")
        XCTAssertEqual(chunk.layer, .instant)
        XCTAssertEqual(chunk.source, "groq")
        XCTAssertFalse(chunk.isFinal)
    }

    func testLayerResultSortsByTier() {
        let results: [LayerResult] = [
            LayerResult(layer: .deep, source: "claude", fullText: "deep", latencyMs: 3000, succeeded: true, error: nil),
            LayerResult(layer: .instant, source: "groq", fullText: "fast", latencyMs: 200, succeeded: true, error: nil),
        ]
        let sorted = results.sorted { $0.layer < $1.layer }
        XCTAssertEqual(sorted[0].source, "groq")
        XCTAssertEqual(sorted[1].source, "claude")
    }
}

// MARK: - Accessibility E2E

final class AccessibilityE2ETests: XCTestCase {

    func testChatMessageAccessibilityContainsAllInfo() {
        let msg = ChatMessage(role: .assistant, content: "G'day!")
        let desc = msg.accessibilityDescription
        XCTAssertTrue(desc.contains("Karen"))
        XCTAssertTrue(desc.contains("G'day!"))
    }

    func testWeavingPhaseAccessibilityAnnouncements() {
        let phases: [(WeavingPhase, String?)] = [
            (.idle, nil),
            (.streaming, nil),
            (.thinking, "Thinking deeper"),
            (.weaving, "Enhanced response available"),
            (.complete, "Response complete"),
        ]
        for (phase, expected) in phases {
            XCTAssertEqual(phase.accessibilityAnnouncement, expected)
        }
    }

    func testResponseLayerAccessibilityLabels() {
        let instant = ResponseLayer(layerNumber: 1, provider: "Groq")
        let deep = ResponseLayer(layerNumber: 3, provider: "Claude")
        XCTAssertTrue(instant.accessibilityLabel.contains("Quick response"))
        XCTAssertTrue(deep.accessibilityLabel.contains("Enhanced response"))
    }

    func testLayerTierIcons() {
        let tiers: [LayerTier] = [.instant, .fastLocal, .deep, .consensus]
        for tier in tiers {
            XCTAssertFalse(tier.icon.isEmpty, "\(tier) must have a SF Symbol icon for VoiceOver")
        }
    }

    func testLayerTierDescriptions() {
        XCTAssertEqual(LayerTier.instant.description, "Instant")
        XCTAssertEqual(LayerTier.fastLocal.description, "Local")
        XCTAssertEqual(LayerTier.deep.description, "Deep")
        XCTAssertEqual(LayerTier.consensus.description, "Consensus")
    }
}

// MARK: - Event Codec E2E

final class EventCodecE2ETests: XCTestCase {

    func testVoiceInputRoundTrip() throws {
        let original = VoiceInputEvent(
            text: "G'day Brain!",
            timestamp: Date(timeIntervalSince1970: 1_700_000_000),
            source: "brainchat", targetLLM: "claude", yoloMode: false)
        let data = try PandaproxyClient.makeEncoder().encode(original)
        let decoded = try PandaproxyClient.makeDecoder().decode(VoiceInputEvent.self, from: data)
        XCTAssertEqual(decoded.text, original.text)
        XCTAssertEqual(decoded.source, original.source)
        XCTAssertEqual(decoded.targetLLM, original.targetLLM)
        XCTAssertEqual(decoded.yoloMode, original.yoloMode)
    }

    func testVoiceResponseRoundTrip() throws {
        let original = VoiceResponseEvent(
            text: "Hello user", provider: "ollama", latencyMs: 500, success: true)
        let data = try PandaproxyClient.makeEncoder().encode(original)
        let decoded = try PandaproxyClient.makeDecoder().decode(VoiceResponseEvent.self, from: data)
        XCTAssertEqual(decoded.text, original.text)
        XCTAssertEqual(decoded.provider, original.provider)
        XCTAssertEqual(decoded.latencyMs, original.latencyMs)
        XCTAssertEqual(decoded.success, original.success)
    }

    func testVoiceInputYoloFlagEncodesCorrectly() throws {
        let event = VoiceInputEvent(
            text: "deploy", source: "brainchat", targetLLM: "claude", yoloMode: true)
        let data = try PandaproxyClient.makeEncoder().encode(event)
        let json = try XCTUnwrap(JSONSerialization.jsonObject(with: data) as? [String: Any])
        XCTAssertEqual(json["yoloMode"] as? Bool, true)
    }
}

// MARK: - Helpers

private func makeConfig(
    provider: LLMProvider = .claude,
    yoloMode: Bool = false,
    groqAPIKey: String = "groq-key"
) -> LLMRouterConfiguration {
    LLMRouterConfiguration(
        provider: provider,
        systemPrompt: "System prompt",
        yoloMode: yoloMode,
        bridgeWebSocketURL: "ws://localhost:8765",
        claudeAPIKey: "claude-key",
        openAIAPIKey: "openai-key",
        groqAPIKey: groqAPIKey,
        grokAPIKey: "grok-key",
        geminiAPIKey: "gemini-key",
        ollamaEndpoint: "http://localhost:11434/api/chat",
        ollamaModel: "llama3.2:3b",
        claudeModel: "claude-sonnet-4-20250514",
        openAIModel: "gpt-4o",
        groqModel: "llama-3.1-8b-instant",
        grokModel: "grok-3-latest",
        geminiModel: "gemini-2.5-flash"
    )
}
