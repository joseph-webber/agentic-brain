import Foundation

// MARK: - LLM Orchestration Mode

/// Defines how BrainChat routes LLM queries.
enum LLMMode: String, CaseIterable, Identifiable {
    case single = "single"
    case multiBot = "multi_bot"
    case consensus = "consensus"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .single:    return "Single LLM"
        case .multiBot:  return "Multi-Bot"
        case .consensus: return "Consensus"
        }
    }

    var accessibilityDescription: String {
        switch self {
        case .single:    return "Single LLM mode. All queries go to one provider."
        case .multiBot:  return "Multi-bot mode. Primary LLM orchestrates others."
        case .consensus: return "Consensus mode. All LLMs vote and majority wins."
        }
    }

    var iconName: String {
        switch self {
        case .single:    return "brain.head.profile"
        case .multiBot:  return "person.3.fill"
        case .consensus: return "checkmark.seal.fill"
        }
    }
}

/// Persisted settings for LLM orchestration. Stored in UserDefaults (not in repo).
struct LLMOrchestratorSettings {
    private static let modeKey = "brainchat.llm_mode"
    private static let primaryKey = "brainchat.primary_llm"
    private static let secondaryKey = "brainchat.secondary_llms"

    static var mode: LLMMode {
        get {
            if let raw = UserDefaults.standard.string(forKey: modeKey),
               let m = LLMMode(rawValue: raw) { return m }
            return .single
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: modeKey) }
    }

    static var primaryLLM: LLMProvider {
        get {
            if let raw = UserDefaults.standard.string(forKey: primaryKey),
               let p = LLMProvider(rawValue: raw) { return p }
            return .ollama
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: primaryKey) }
    }

    static var secondaryLLMs: [LLMProvider] {
        get {
            guard let data = UserDefaults.standard.data(forKey: secondaryKey),
                  let decoded = try? JSONDecoder().decode([LLMProvider].self, from: data) else {
                return []
            }
            return decoded
        }
        set {
            if let encoded = try? JSONEncoder().encode(newValue) {
                UserDefaults.standard.set(encoded, forKey: secondaryKey)
            }
        }
    }
}

/// Orchestrates multiple LLM providers with single, multi-bot, and consensus modes.
/// Thread-safe and designed for accessibility (VoiceOver-friendly status updates).
@MainActor
final class LLMOrchestrator: ObservableObject {
    static let shared = LLMOrchestrator()

    @Published var primaryLLM: LLMProvider {
        didSet { LLMOrchestratorSettings.primaryLLM = primaryLLM }
    }
    @Published var secondaryLLMs: [LLMProvider] {
        didSet { LLMOrchestratorSettings.secondaryLLMs = secondaryLLMs }
    }
    @Published var mode: LLMMode {
        didSet { LLMOrchestratorSettings.mode = mode }
    }
    @Published private(set) var statusMessage = "Ready"

    private let llmRouter: LLMRouter

    private init() {
        self.mode = LLMOrchestratorSettings.mode
        self.primaryLLM = LLMOrchestratorSettings.primaryLLM
        self.secondaryLLMs = LLMOrchestratorSettings.secondaryLLMs
        self.llmRouter = LLMRouter()
    }

    // MARK: - Query Routing

    /// Main entry point for queries. Routes based on current mode.
    func query(
        _ prompt: String,
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async -> String {
        switch mode {
        case .single:
            return await querySingle(prompt, history: history, configuration: configuration, onEvent: onEvent)
        case .multiBot:
            return await queryMultiBot(prompt, history: history, configuration: configuration, onEvent: onEvent)
        case .consensus:
            return await queryConsensus(prompt, history: history, configuration: configuration, onEvent: onEvent)
        }
    }

    // MARK: - Single LLM Mode

    private func querySingle(
        _ prompt: String,
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async -> String {
        statusMessage = "Querying \(primaryLLM.shortName)…"
        onEvent(.providerChanged(primaryLLM.rawValue))

        // Use the existing LLMRouter with the primary provider
        let config = LLMRouterConfiguration(
            provider: primaryLLM,
            systemPrompt: configuration.systemPrompt,
            yoloMode: configuration.yoloMode,
            bridgeWebSocketURL: configuration.bridgeWebSocketURL,
            fallbackProviders: configuration.fallbackProviders,
            backend: configuration.backend,
            profile: configuration.profile,
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

        let response = await llmRouter.streamReply(history: history, configuration: config, onEvent: onEvent)
        statusMessage = "Ready"
        return response
    }

    // MARK: - Multi-Bot Mode (Primary Routes to Others)

    private func queryMultiBot(
        _ prompt: String,
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async -> String {
        statusMessage = "Primary \(primaryLLM.shortName) analyzing request…"
        onEvent(.providerChanged("Multi-Bot: \(primaryLLM.shortName)"))

        // Primary decides if it should delegate
        let routingPrompt = """
        You are an LLM orchestrator. Analyze this user request and decide which LLM should handle it.
        Available LLMs: \(secondaryLLMs.map(\.shortName).joined(separator: ", "))
        
        For simple questions, respond directly.
        For complex tasks, specify which LLM to delegate to by responding with:
        [DELEGATE:\(secondaryLLMs.first?.rawValue ?? "ollama")] then your delegation instructions.
        
        User request: \(prompt)
        """

        // Query primary first
        var routingHistory = history
        routingHistory.append(ChatMessage(role: .user, content: routingPrompt))

        let primaryConfig = LLMRouterConfiguration(
            provider: primaryLLM,
            systemPrompt: configuration.systemPrompt,
            yoloMode: false,
            backend: configuration.backend,
            profile: configuration.profile,
            claudeAPIKey: configuration.claudeAPIKey,
            openAIAPIKey: configuration.openAIAPIKey,
            groqAPIKey: configuration.groqAPIKey,
            grokAPIKey: configuration.grokAPIKey,
            geminiAPIKey: configuration.geminiAPIKey,
            ollamaEndpoint: configuration.ollamaEndpoint,
            ollamaModel: configuration.ollamaModel
        )

        let primaryResponse = await llmRouter.streamReply(history: routingHistory, configuration: primaryConfig) { _ in }

        // Check if primary wants to delegate
        if let delegateMatch = primaryResponse.range(of: #"\[DELEGATE:(\w+)\]"#, options: .regularExpression) {
            let delegateInfo = String(primaryResponse[delegateMatch])
            let providerName = delegateInfo.replacingOccurrences(of: "[DELEGATE:", with: "")
                .replacingOccurrences(of: "]", with: "").lowercased()

            if let targetProvider = LLMProvider(rawValue: providerName),
               secondaryLLMs.contains(targetProvider) {
                statusMessage = "Delegating to \(targetProvider.shortName)…"
                onEvent(.providerChanged("Delegated: \(targetProvider.shortName)"))

                let delegateConfig = LLMRouterConfiguration(
                    provider: targetProvider,
                    systemPrompt: configuration.systemPrompt,
                    yoloMode: configuration.yoloMode,
                    backend: configuration.backend,
                    profile: configuration.profile,
                    claudeAPIKey: configuration.claudeAPIKey,
                    openAIAPIKey: configuration.openAIAPIKey,
                    groqAPIKey: configuration.groqAPIKey,
                    grokAPIKey: configuration.grokAPIKey,
                    geminiAPIKey: configuration.geminiAPIKey,
                    ollamaEndpoint: configuration.ollamaEndpoint,
                    ollamaModel: configuration.ollamaModel
                )

                let response = await llmRouter.streamReply(history: history, configuration: delegateConfig, onEvent: onEvent)
                statusMessage = "Ready"
                return response
            }
        }

        // Primary handled it directly - now stream it properly
        statusMessage = "Ready"
        return await llmRouter.streamReply(history: history, configuration: primaryConfig, onEvent: onEvent)
    }

    // MARK: - Consensus Mode (All LLMs Vote)

    private func queryConsensus(
        _ prompt: String,
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async -> String {
        let allProviders = [primaryLLM] + secondaryLLMs
        guard !allProviders.isEmpty else {
            return "No LLM providers configured."
        }

        statusMessage = "Querying \(allProviders.count) LLMs for consensus…"
        onEvent(.providerChanged("Consensus: \(allProviders.count) LLMs"))

        // Query all providers in parallel
        var responses: [(provider: LLMProvider, response: String)] = []

        await withTaskGroup(of: (LLMProvider, String).self) { group in
            for provider in allProviders {
                group.addTask { [configuration] in
                    let providerConfig = LLMRouterConfiguration(
                        provider: provider,
                        systemPrompt: configuration.systemPrompt,
                        yoloMode: false,
                        backend: configuration.backend,
                        profile: configuration.profile,
                        claudeAPIKey: configuration.claudeAPIKey,
                        openAIAPIKey: configuration.openAIAPIKey,
                        groqAPIKey: configuration.groqAPIKey,
                        grokAPIKey: configuration.grokAPIKey,
                        geminiAPIKey: configuration.geminiAPIKey,
                        ollamaEndpoint: configuration.ollamaEndpoint,
                        ollamaModel: configuration.ollamaModel
                    )

                    let response = await self.llmRouter.streamReply(
                        history: history,
                        configuration: providerConfig
                    ) { _ in }

                    return (provider, response)
                }
            }

            for await result in group {
                if !result.1.isEmpty {
                    responses.append(result)
                }
            }
        }

        if responses.isEmpty {
            statusMessage = "All providers failed"
            return "All LLM providers failed to respond."
        }

        // Synthesize consensus
        statusMessage = "Synthesizing \(responses.count) responses…"
        let synthesis = await synthesizeConsensus(responses, originalPrompt: prompt, configuration: configuration)
        statusMessage = "Consensus reached from \(responses.count) providers"
        return synthesis
    }

    private func synthesizeConsensus(
        _ responses: [(provider: LLMProvider, response: String)],
        originalPrompt: String,
        configuration: LLMRouterConfiguration
    ) async -> String {
        guard responses.count > 1 else {
            return responses.first?.response ?? ""
        }

        // Use primary LLM to combine responses
        let synthesisPrompt = """
        You are synthesizing responses from multiple AI assistants to find consensus.
        Original question: \(originalPrompt)
        
        Responses:
        \(responses.map { "[\($0.provider.shortName)]: \($0.response)" }.joined(separator: "\n\n"))
        
        Provide a unified response that captures the consensus. Note any disagreements.
        """

        let synthesisHistory = [ChatMessage(role: .user, content: synthesisPrompt)]
        let synthesisConfig = LLMRouterConfiguration(
            provider: primaryLLM,
            systemPrompt: "You synthesize multiple AI responses into coherent consensus.",
            yoloMode: false,
            backend: configuration.backend,
            profile: configuration.profile,
            claudeAPIKey: configuration.claudeAPIKey,
            openAIAPIKey: configuration.openAIAPIKey,
            groqAPIKey: configuration.groqAPIKey,
            grokAPIKey: configuration.grokAPIKey,
            geminiAPIKey: configuration.geminiAPIKey,
            ollamaEndpoint: configuration.ollamaEndpoint,
            ollamaModel: configuration.ollamaModel
        )

        let result = await llmRouter.streamReply(history: synthesisHistory, configuration: synthesisConfig) { _ in }
        return result.isEmpty ? responses.first?.response ?? "" : result
    }

    // MARK: - AppleScript Support

    /// Set LLM mode via AppleScript command.
    func setLLMMode(_ modeString: String) -> Bool {
        guard let newMode = LLMMode(rawValue: modeString.lowercased()) else { return false }
        mode = newMode
        return true
    }

    /// Set primary LLM via AppleScript command.
    func setPrimaryLLM(_ providerString: String) -> Bool {
        guard let provider = LLMProvider(rawValue: providerString) else { return false }
        primaryLLM = provider
        return true
    }

    /// Add a secondary LLM via AppleScript command.
    func addSecondaryLLM(_ providerString: String) -> Bool {
        guard let provider = LLMProvider(rawValue: providerString) else { return false }
        if !secondaryLLMs.contains(provider) {
            secondaryLLMs.append(provider)
        }
        return true
    }

    /// Remove a secondary LLM via AppleScript command.
    func removeSecondaryLLM(_ providerString: String) -> Bool {
        guard let provider = LLMProvider(rawValue: providerString) else { return false }
        secondaryLLMs.removeAll { $0 == provider }
        return true
    }

    /// Get current orchestrator status for AppleScript.
    func getStatus() -> String {
        "mode=\(mode.rawValue), primary=\(primaryLLM.rawValue), secondary=[\(secondaryLLMs.map(\.rawValue).joined(separator: ","))]"
    }
}
