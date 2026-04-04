import Foundation
import Combine

enum LLMProvider: String, CaseIterable, Codable, Sendable, Identifiable, Hashable {
    case ollama = "Ollama (Local)"
    case groq = "Groq (Instant)"
    case claude = "Claude (Anthropic)"
    case gpt = "GPT (OpenAI)"
    case grok = "Grok (xAI)"
    case gemini = "Gemini (Google)"
    case copilot = "GitHub Copilot"

    var id: String { rawValue }
    var shortName: String {
        switch self {
        case .ollama: return "Ollama"
        case .groq: return "Groq"
        case .claude: return "Claude"
        case .gpt: return "GPT"
        case .grok: return "Grok"
        case .gemini: return "Gemini"
        case .copilot: return "Copilot"
        }
    }

    var iconName: String {
        switch self {
        case .ollama: return "desktopcomputer"
        case .groq: return "hare.fill"
        case .claude: return "brain.head.profile"
        case .gpt: return "sparkles"
        case .grok: return "bolt.fill"
        case .gemini: return "diamond.fill"
        case .copilot: return "chevron.left.forwardslash.chevron.right"
        }
    }

    var defaultModel: String {
        switch self {
        case .ollama: return "llama3.2:3b"
        case .groq: return "llama-3.1-8b-instant"
        case .claude: return "claude-sonnet-4-20250514"
        case .gpt: return "gpt-4o"
        case .grok: return "grok-3-latest"
        case .gemini: return "gemini-2.5-flash"
        case .copilot: return "copilot-cli"
        }
    }

    var requiresAPIKey: Bool {
        switch self {
        case .ollama, .copilot: return false
        case .groq, .claude, .gpt, .grok, .gemini: return true
        }
    }

    var keyKind: APIKeyKind? {
        switch self {
        case .groq: return .groq
        case .claude: return .claude
        case .gpt: return .openAI
        case .grok: return .grok
        case .gemini: return .gemini
        case .ollama, .copilot: return nil
        }
    }

    var yoloSystemPrompt: String {
        """
        AUTONOMOUS MODE ACTIVE. You are in YOLO mode.
        - Execute tasks immediately without asking for confirmation.
        - Make decisions autonomously using best judgment.
        - Write complete, working code — never leave TODOs or placeholders.
        - If something fails, try a different approach automatically.
        - Be bold, be decisive, get it done.
        """
    }

    // MARK: - Cost tracking

    /// Whether this provider is free (no per-token charge).
    var isFree: Bool {
        switch self {
        case .ollama, .groq: return true
        case .copilot, .claude, .gpt, .grok, .gemini: return false
        }
    }

    /// Approximate cost in USD per 1 000 input tokens. Zero means free or subscription-based.
    var estimatedCostPer1kTokens: Double {
        switch self {
        case .ollama: return 0.0
        case .groq:   return 0.0     // free tier; paid tier ~$0.05/1M = $0.00005/1k
        case .gemini: return 0.00015 // Gemini 2.5 Flash ~$0.15/1M input
        case .grok:   return 0.002   // Grok 3 ~$2/1M input
        case .gpt:    return 0.0025  // GPT-4o ~$2.50/1M input
        case .claude: return 0.003   // Claude Sonnet 4 ~$3/1M input
        case .copilot: return 0.0    // subscription, no per-token cost
        }
    }

    /// Human-readable pricing label for the LLMSelector UI.
    var displayPricing: String {
        switch self {
        case .ollama: return "Free (local)"
        case .groq:   return "Free tier"
        case .copilot: return "Subscription"
        default:
            let perM = estimatedCostPer1kTokens * 1_000
            return String(format: "$%.2f/1M tokens", perM)
        }
    }
}

struct LLMRouterConfiguration: Sendable {
    let provider: LLMProvider
    let systemPrompt: String
    let yoloMode: Bool
    let bridgeWebSocketURL: String
    let claudeAPIKey: String
    let openAIAPIKey: String
    let groqAPIKey: String
    let grokAPIKey: String
    let geminiAPIKey: String
    let ollamaEndpoint: String
    let ollamaModel: String
    let claudeModel: String
    let openAIModel: String
    let groqModel: String
    let grokModel: String
    let geminiModel: String

    init(
        provider: LLMProvider,
        systemPrompt: String,
        yoloMode: Bool = false,
        bridgeWebSocketURL: String = "",
        claudeAPIKey: String = "",
        openAIAPIKey: String = "",
        groqAPIKey: String = "",
        grokAPIKey: String = "",
        geminiAPIKey: String = "",
        ollamaEndpoint: String = "http://localhost:11434/api/chat",
        ollamaModel: String = "llama3.2:3b",
        claudeModel: String = "claude-sonnet-4-20250514",
        openAIModel: String = "gpt-4o",
        groqModel: String = "llama-3.1-8b-instant",
        grokModel: String = "grok-3-latest",
        geminiModel: String = "gemini-2.5-flash"
    ) {
        self.provider = provider
        self.systemPrompt = systemPrompt
        self.yoloMode = yoloMode
        self.bridgeWebSocketURL = bridgeWebSocketURL
        self.claudeAPIKey = claudeAPIKey
        self.openAIAPIKey = openAIAPIKey
        self.groqAPIKey = groqAPIKey
        self.grokAPIKey = grokAPIKey
        self.geminiAPIKey = geminiAPIKey
        self.ollamaEndpoint = ollamaEndpoint
        self.ollamaModel = ollamaModel
        self.claudeModel = claudeModel
        self.openAIModel = openAIModel
        self.groqModel = groqModel
        self.grokModel = grokModel
        self.geminiModel = geminiModel
    }

    var hasGroqConfiguration: Bool {
        !groqAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var effectiveSystemPrompt: String {
        yoloMode ? systemPrompt + "\n\n" + provider.yoloSystemPrompt : systemPrompt
    }
}

enum LLMRequestType: Equatable {
    case coding
    case quick
    case chat
}

@MainActor
final class LLMRouter: ObservableObject {
    @Published var selectedProvider: LLMProvider { didSet { UserDefaults.standard.set(selectedProvider.rawValue, forKey: "selectedLLMProvider") } }
    @Published var yoloMode: Bool { didSet { UserDefaults.standard.set(yoloMode, forKey: "yoloModeEnabled") } }
    @Published private(set) var activeProviderName = "Idle"
    @Published private(set) var statusMessage = "Ready"
    @Published private(set) var lastErrorMessage: String?
    @Published private(set) var connectionTestResult: ConnectionTestResult?

    private let claudeAPI: any ClaudeStreaming
    private let openAIAPI: any OpenAIStreaming
    private let ollamaAPI: any OllamaStreaming
    private let groqClient: any GroqStreaming
    private let grokClient: any GrokStreaming
    private let geminiClient: any GeminiStreaming
    private let copilotClient: any CopilotStreaming

    init(
        claudeAPI: any ClaudeStreaming = ClaudeAPI(),
        openAIAPI: any OpenAIStreaming = OpenAIAPI(),
        ollamaAPI: any OllamaStreaming = OllamaAPI(),
        groqClient: any GroqStreaming = GroqClient(),
        grokClient: any GrokStreaming = GrokClient(),
        geminiClient: any GeminiStreaming = GeminiClient(),
        copilotClient: any CopilotStreaming = CopilotClient()
    ) {
        self.claudeAPI = claudeAPI
        self.openAIAPI = openAIAPI
        self.ollamaAPI = ollamaAPI
        self.groqClient = groqClient
        self.grokClient = grokClient
        self.geminiClient = geminiClient
        self.copilotClient = copilotClient
        if let savedProvider = UserDefaults.standard.string(forKey: "selectedLLMProvider"),
           let provider = LLMProvider(rawValue: savedProvider) {
            self.selectedProvider = provider
        } else {
            self.selectedProvider = .ollama
        }
        self.yoloMode = UserDefaults.standard.bool(forKey: "yoloModeEnabled")
    }

    func streamReply(history: [ChatMessage], configuration: LLMRouterConfiguration, onEvent: @escaping @Sendable (AIStreamEvent) -> Void) async -> String {
        let messages = Self.buildContext(from: history, systemPrompt: configuration.effectiveSystemPrompt)
        let prompt = messages.last(where: { $0.role == .user })?.content ?? ""
        let primary = Self.recommendedProvider(
            for: Self.classifyRequestType(for: prompt),
            selectedProvider: configuration.provider,
            hasGroqConfiguration: configuration.hasGroqConfiguration
        )
        let providers = buildFallbackChain(primary: primary, configuration: configuration)
        var failures: [String] = []
        for (index, provider) in providers.enumerated() {
            if index > 0 { onEvent(.reset) }
            activeProviderName = provider.rawValue
            statusMessage = "Thinking with \(provider.shortName)…"
            onEvent(.providerChanged(provider.rawValue))
            do {
                let response = try await call(provider: provider, configuration: configuration, messages: messages, onEvent: onEvent)
                lastErrorMessage = nil
                statusMessage = "Ready"
                return response
            } catch {
                let failure = "\(provider.shortName): \(error.localizedDescription)"
                failures.append(failure)
                lastErrorMessage = failure
                statusMessage = "\(provider.shortName) failed, trying fallback…"
            }
        }
        activeProviderName = "Unavailable"
        statusMessage = "All LLM backends unavailable"
        return "Sorry Joseph, all LLM providers are unavailable right now.\n\(failures.joined(separator: "\n"))"
    }

    func testConnection(provider: LLMProvider, configuration: LLMRouterConfiguration) async {
        connectionTestResult = nil
        statusMessage = "Testing \(provider.shortName)…"
        let started = Date()
        do {
            _ = try await call(provider: provider, configuration: configuration, messages: [AIChatMessage(role: .user, content: "Say hello in one sentence.")]) { _ in }
            let duration = Date().timeIntervalSince(started)
            connectionTestResult = ConnectionTestResult(provider: provider, success: true, message: "Connected in \(String(format: "%.1f", duration))s", latency: duration)
            statusMessage = "Ready"
        } catch {
            let duration = Date().timeIntervalSince(started)
            connectionTestResult = ConnectionTestResult(provider: provider, success: false, message: error.localizedDescription, latency: duration)
            statusMessage = "Test failed"
        }
    }

    func buildFallbackChain(primary: LLMProvider, configuration: LLMRouterConfiguration) -> [LLMProvider] {
        var chain: [LLMProvider] = [primary]
        if primary == .groq, configuration.provider != .groq {
            chain.append(configuration.provider)
        }
        if primary == .claude, !configuration.openAIAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            chain.append(.gpt)
        }
        if primary == .groq, !configuration.openAIAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            chain.append(.gpt)
        }
        if primary != .ollama {
            chain.append(.ollama)
        }
        var seen = Set<LLMProvider>()
        return chain.filter { seen.insert($0).inserted }
    }

    static func buildContext(from history: [ChatMessage], systemPrompt: String) -> [AIChatMessage] {
        var messages = [AIChatMessage(role: .system, content: systemPrompt)]
        let trimmedHistory = history
            .filter { $0.role != .system && !$0.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            .suffix(10)
            .map { AIChatMessage(role: $0.role.aiRole, content: $0.content) }
        messages.append(contentsOf: trimmedHistory)
        return messages
    }

    static func classifyRequestType(for prompt: String) -> LLMRequestType {
        let trimmed = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return .chat }
        let lower = trimmed.lowercased()
        let codingHints = ["write code", "implement", "function", "class", "refactor", "debug", "fix bug", "unit test", "swift", "python", "typescript", "javascript", "api", "endpoint", "database", "sql", "regex"]
        if codingHints.contains(where: { lower.contains($0) }) {
            return .coding
        }

        let quickHints = ["hi", "hello", "hey", "thanks", "thank you", "summarize", "one sentence", "quick", "briefly"]
        let wordCount = trimmed.split(whereSeparator: \.isWhitespace).count
        if wordCount <= 12 || quickHints.contains(where: { lower.contains($0) }) {
            return .quick
        }

        return .chat
    }

    static func recommendedProvider(for requestType: LLMRequestType, selectedProvider: LLMProvider, hasGroqConfiguration: Bool = false) -> LLMProvider {
        switch requestType {
        case .coding:
            return .copilot
        case .quick where hasGroqConfiguration && ![LLMProvider.groq, .grok, .gemini].contains(selectedProvider):
            return .groq
        case .quick, .chat:
            return selectedProvider
        }
    }

    /// Stream a response from a specific provider directly. Used by ResponseWeavingCoordinator.
    /// Returns the full response text, or empty string on failure.
    func streamProvider(
        _ provider: LLMProvider,
        configuration: LLMRouterConfiguration,
        messages: [AIChatMessage],
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async -> String {
        do {
            return try await call(provider: provider, configuration: configuration, messages: messages, onEvent: onEvent)
        } catch {
            return ""
        }
    }

    private func call(provider: LLMProvider, configuration: LLMRouterConfiguration, messages: [AIChatMessage], onEvent: @escaping @Sendable (AIStreamEvent) -> Void) async throws -> String {
        switch provider {
        case .groq:
            return try await groqClient.streamResponse(apiKey: configuration.groqAPIKey, model: configuration.groqModel, messages: messages, onDelta: { onEvent(.delta($0)) })
        case .claude:
            return try await claudeAPI.streamResponse(apiKey: configuration.claudeAPIKey, model: configuration.claudeModel, systemPrompt: configuration.effectiveSystemPrompt, messages: messages, onDelta: { onEvent(.delta($0)) })
        case .gpt:
            return try await openAIAPI.streamResponse(apiKey: configuration.openAIAPIKey, model: configuration.openAIModel, messages: messages, onDelta: { onEvent(.delta($0)) })
        case .grok:
            return try await grokClient.streamResponse(apiKey: configuration.grokAPIKey, model: configuration.grokModel, messages: messages, onDelta: { onEvent(.delta($0)) })
        case .gemini:
            return try await geminiClient.streamResponse(apiKey: configuration.geminiAPIKey, model: configuration.geminiModel, systemPrompt: configuration.effectiveSystemPrompt, messages: messages, onDelta: { onEvent(.delta($0)) })
        case .ollama:
            return try await ollamaAPI.streamResponse(endpoint: configuration.ollamaEndpoint, model: configuration.ollamaModel, messages: messages, onDelta: { onEvent(.delta($0)) })
        case .copilot:
            let prompt = messages.last(where: { $0.role == .user })?.content ?? ""
            return try await copilotClient.streamResponse(prompt: prompt, yoloMode: configuration.yoloMode, onDelta: { onEvent(.delta($0)) })
        }
    }
}

struct ConnectionTestResult: Identifiable, Sendable {
    let id: UUID
    let provider: LLMProvider
    let success: Bool
    let message: String
    let latency: TimeInterval

    init(id: UUID = UUID(), provider: LLMProvider, success: Bool, message: String, latency: TimeInterval) {
        self.id = id
        self.provider = provider
        self.success = success
        self.message = message
        self.latency = latency
    }
}
