import AppKit
import Foundation

// MARK: - Response Weaving Coordinator

/// Orchestrates dual-LLM response weaving:
/// 1. Fires a fast LLM (Ollama) immediately and streams Layer 1.
/// 2. Concurrently fires a deep LLM (selected provider) for a richer Layer 2.
/// 3. Weaves Layer 2 into the existing message naturally.
///
/// If both layers would use the same provider the coordinator falls back to
/// standard single-layer streaming so there is no redundant network call.
@MainActor
final class ResponseWeavingCoordinator {

    // MARK: - Configuration

    /// Provider used for the fast (instant) Layer 1.
    static let fastProvider: LLMProvider = .ollama

    /// Returns `true` when weaving makes sense for the given configuration.
    static func shouldWeave(configuration: LLMRouterConfiguration) -> Bool {
        let deep = deepProvider(for: configuration)
        return deep != fastProvider && hasKey(for: deep, configuration: configuration)
    }

    // MARK: - Main Entry Point

    /// Sends a woven reply: Layer 1 from Ollama, Layer 2 from the deep LLM.
    ///
    /// Falls back to ordinary streaming when weaving is not possible.
    func sendWeavedReply(
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        store: ConversationStore,
        llmRouter: LLMRouter,
        voiceManager: VoiceManager,
        autoSpeak: Bool
    ) async {
        guard Self.shouldWeave(configuration: configuration) else {
            await sendSingleLayerReply(
                history: history,
                configuration: configuration,
                store: store,
                llmRouter: llmRouter,
                voiceManager: voiceManager,
                autoSpeak: autoSpeak
            )
            return
        }

        let deep = Self.deepProvider(for: configuration)
        let messageID = store.beginStreamingAssistantMessage()
        store.setWeavingPhase(id: messageID, phase: .streaming)
        store.isProcessing = true

        // Announce the quick-response arrival to VoiceOver.
        postAccessibilityAnnouncement("Quick response loading")

        // --- Layer 1: fast LLM ---
        let fastConfig = fastConfiguration(from: configuration)
        let fastMessages = LLMRouter.buildContext(from: history, systemPrompt: configuration.effectiveSystemPrompt)
        let fastLayerID = UUID()

        var layer1Content = ""
        let layer1 = ResponseLayer(id: fastLayerID, layerNumber: 1, provider: Self.fastProvider.shortName, content: "")
        store.addLayer(messageID: messageID, layer: layer1)

        let fastResult = await llmRouter.streamProvider(
            Self.fastProvider,
            configuration: fastConfig,
            messages: fastMessages
        ) { @Sendable event in
            Task { @MainActor [weak store] in
                if case .delta(let delta) = event {
                    store?.appendToLayer(messageID: messageID, layerID: fastLayerID, delta: delta)
                    store?.appendToMessage(id: messageID, delta: delta)
                }
            }
        }

        layer1Content = fastResult
        store.setLayerContent(messageID: messageID, layerID: fastLayerID, content: fastResult)
        store.setWeavingPhase(id: messageID, phase: .thinking)

        // Speak Layer 1 immediately.
        if autoSpeak && !layer1Content.isEmpty {
            voiceManager.speak(layer1Content)
        }
        postAccessibilityAnnouncement("Quick response delivered. Thinking deeper.")

        // --- Layer 2: deep LLM ---
        let deepConfig = configuration
        let deepMessages = LLMRouter.buildContext(from: history, systemPrompt: configuration.effectiveSystemPrompt)
        let deepLayerID = UUID()
        let layer2 = ResponseLayer(id: deepLayerID, layerNumber: 2, provider: deep.shortName, content: "")
        store.addLayer(messageID: messageID, layer: layer2)
        store.setWeavingPhase(id: messageID, phase: .weaving)

        let deepResult = await llmRouter.streamProvider(
            deep,
            configuration: deepConfig,
            messages: deepMessages
        ) { @Sendable event in
            Task { @MainActor [weak store] in
                if case .delta(let delta) = event {
                    store?.appendToLayer(messageID: messageID, layerID: deepLayerID, delta: delta)
                }
            }
        }

        store.setLayerContent(messageID: messageID, layerID: deepLayerID, content: deepResult)
        store.setWeavingPhase(id: messageID, phase: .complete)
        store.isProcessing = false

        // Speak Layer 2 additions (not repeating Layer 1).
        if autoSpeak && !deepResult.isEmpty {
            let addition = extractAddition(deepResult, comparedTo: layer1Content)
            if !addition.isEmpty {
                // Brief pause before the enhancement.
                try? await Task.sleep(nanoseconds: 800_000_000)
                voiceManager.speak(addition)
            }
        }
        postAccessibilityAnnouncement("Enhanced response available")
    }

    // MARK: - Fallback: Single-Layer

    private func sendSingleLayerReply(
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        store: ConversationStore,
        llmRouter: LLMRouter,
        voiceManager: VoiceManager,
        autoSpeak: Bool
    ) async {
        let assistantMessageID = store.beginStreamingAssistantMessage()
        store.isProcessing = true

        let response = await llmRouter.streamReply(history: history, configuration: configuration) { event in
            switch event {
            case .reset:
                Task { @MainActor in store.replaceMessageContent(id: assistantMessageID, content: "") }
            case .delta(let delta):
                Task { @MainActor in store.appendToMessage(id: assistantMessageID, delta: delta) }
            case .providerChanged:
                break
            }
        }

        store.finishStreamingMessage(id: assistantMessageID, fallbackContent: response)
        store.isProcessing = false
        if autoSpeak { voiceManager.speak(response) }
    }

    // MARK: - Helpers

    /// Picks the deep (quality) provider based on what API keys are configured.
    static func deepProvider(for configuration: LLMRouterConfiguration) -> LLMProvider {
        // Prefer the user's selected provider if it differs from Ollama.
        if configuration.provider != fastProvider {
            return configuration.provider
        }
        // Fallback priority: Claude > GPT > Grok > Gemini.
        if !configuration.claudeAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return .claude
        }
        if !configuration.openAIAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return .gpt
        }
        if !configuration.grokAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return .grok
        }
        if !configuration.geminiAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return .gemini
        }
        return fastProvider  // No deep provider available → single-layer fallback.
    }

    private static func hasKey(for provider: LLMProvider, configuration: LLMRouterConfiguration) -> Bool {
        switch provider {
        case .ollama, .copilot: return true
        case .claude:   return !configuration.claudeAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case .gpt:      return !configuration.openAIAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case .groq:     return !configuration.groqAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case .grok:     return !configuration.grokAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case .gemini:   return !configuration.geminiAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }

    /// Returns an Ollama-only configuration derived from the main configuration.
    private func fastConfiguration(from configuration: LLMRouterConfiguration) -> LLMRouterConfiguration {
        LLMRouterConfiguration(
            provider: .ollama,
            systemPrompt: configuration.systemPrompt,
            yoloMode: configuration.yoloMode,
            bridgeWebSocketURL: configuration.bridgeWebSocketURL,
            claudeAPIKey: configuration.claudeAPIKey,
            openAIAPIKey: configuration.openAIAPIKey,
            groqAPIKey: configuration.groqAPIKey,
            grokAPIKey: configuration.grokAPIKey,
            geminiAPIKey: configuration.geminiAPIKey,
            ollamaEndpoint: configuration.ollamaEndpoint,
            ollamaModel: configuration.ollamaModel,
            claudeModel: configuration.claudeModel,
            openAIModel: configuration.openAIModel,
            groqModel: configuration.groqModel,
            grokModel: configuration.grokModel,
            geminiModel: configuration.geminiModel
        )
    }

    /// Extracts sentences from `deep` that meaningfully differ from `quick`.
    /// Used to avoid re-speaking content the user already heard.
    private func extractAddition(_ deep: String, comparedTo quick: String) -> String {
        let deepSentences = sentences(from: deep)
        let quickWords = Set(quick.lowercased().components(separatedBy: .whitespacesAndNewlines))

        let novel = deepSentences.filter { sentence in
            let words = Set(sentence.lowercased().components(separatedBy: .whitespacesAndNewlines))
            let overlap = words.intersection(quickWords).count
            let novelRatio = Double(words.count - overlap) / Double(max(words.count, 1))
            return novelRatio > 0.45  // sentence is at least 45% new words
        }
        return novel.prefix(3).joined(separator: " ")
    }

    private func sentences(from text: String) -> [String] {
        var result: [String] = []
        text.enumerateSubstrings(in: text.startIndex..., options: .bySentences) { sub, _, _, _ in
            if let s = sub?.trimmingCharacters(in: .whitespacesAndNewlines), !s.isEmpty {
                result.append(s)
            }
        }
        return result
    }

    private func postAccessibilityAnnouncement(_ message: String) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            let userInfo: [NSAccessibility.NotificationUserInfoKey: Any] = [
                .announcement: message,
                .priority: NSAccessibilityPriorityLevel.high.rawValue
            ]
            NSAccessibility.post(element: NSApp as Any, notification: .announcementRequested, userInfo: userInfo)
        }
    }
}
