import Combine
import SwiftUI

enum AIRole: String, Codable, Sendable {
    case system
    case user
    case assistant
}

struct AIChatMessage: Codable, Sendable {
    let role: AIRole
    let content: String
}

enum AIServiceError: LocalizedError {
    case missingAPIKey(String)
    case invalidURL(String)
    case invalidResponse
    case httpStatus(Int, String)
    case emptyResponse(String)

    static func == (lhs: AIServiceError, rhs: AIServiceError) -> Bool {
        switch (lhs, rhs) {
        case let (.missingAPIKey(a), .missingAPIKey(b)): return a == b
        case let (.invalidURL(a), .invalidURL(b)): return a == b
        case (.invalidResponse, .invalidResponse): return true
        case let (.httpStatus(a1, a2), .httpStatus(b1, b2)): return a1 == b1 && a2 == b2
        case let (.emptyResponse(a), .emptyResponse(b)): return a == b
        default: return false
        }
    }

    var errorDescription: String? {
        switch self {
        case .missingAPIKey(let provider): return "Missing API key for \(provider)."
        case .invalidURL(let value): return "Invalid URL: \(value)"
        case .invalidResponse: return "The AI service returned an invalid response."
        case .httpStatus(let status, let message): return "HTTP \(status): \(message)"
        case .emptyResponse(let message): return message
        }
    }
}

enum AIStreamEvent: Sendable {
    case providerChanged(String)
    case reset
    case delta(String)
}

struct ChatMessage: Identifiable, Equatable {
    let id: UUID
    let role: Role
    var content: String
    let timestamp: Date
    /// Response layers for woven multi-LLM messages. Empty for standard messages.
    var layers: [ResponseLayer]
    /// Current weaving lifecycle phase. `.idle` for standard messages.
    var weavingPhase: WeavingPhase

    enum Role: String {
        case user = "You"
        case assistant = "Karen"
        case copilot = "Copilot"
        case system = "System"

        var aiRole: AIRole {
            switch self {
            case .user: return .user
            case .assistant, .copilot: return .assistant
            case .system: return .system
            }
        }
    }

    init(
        id: UUID = UUID(),
        role: Role,
        content: String,
        timestamp: Date = Date(),
        layers: [ResponseLayer] = [],
        weavingPhase: WeavingPhase = .idle
    ) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
        self.layers = layers
        self.weavingPhase = weavingPhase
    }

    var accessibilityDescription: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        let base = "\(role.rawValue) said at \(formatter.string(from: timestamp)): \(content)"
        if let statusNote = weavingPhase.accessibilityAnnouncement {
            return "\(base). \(statusNote)"
        }
        return base
    }
}

@MainActor
final class ConversationStore: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var isProcessing = false

    @discardableResult
    func addMessage(role: ChatMessage.Role, content: String) -> UUID {
        let message = ChatMessage(role: role, content: content)
        messages.append(message)
        return message.id
    }

    @discardableResult
    func beginStreamingAssistantMessage() -> UUID {
        beginStreamingMessage(role: .assistant)
    }

    @discardableResult
    func beginStreamingMessage(role: ChatMessage.Role) -> UUID {
        let message = ChatMessage(role: role, content: "")
        messages.append(message)
        return message.id
    }

    func replaceMessageContent(id: UUID, content: String) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
        messages[index].content = content
    }

    func appendToMessage(id: UUID, delta: String) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
        messages[index].content += delta
    }

    func finishStreamingMessage(id: UUID, fallbackContent: String) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
        if messages[index].content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            messages[index].content = fallbackContent
        }
    }

    // MARK: - Response Weaving

    func setWeavingPhase(id: UUID, phase: WeavingPhase) {
        guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
        messages[index].weavingPhase = phase
    }

    func addLayer(messageID: UUID, layer: ResponseLayer) {
        guard let index = messages.firstIndex(where: { $0.id == messageID }) else { return }
        messages[index].layers.append(layer)
    }

    func appendToLayer(messageID: UUID, layerID: UUID, delta: String) {
        guard let msgIndex = messages.firstIndex(where: { $0.id == messageID }),
              let layerIndex = messages[msgIndex].layers.firstIndex(where: { $0.id == layerID }) else { return }
        messages[msgIndex].layers[layerIndex].content += delta
    }

    func setLayerContent(messageID: UUID, layerID: UUID, content: String) {
        guard let msgIndex = messages.firstIndex(where: { $0.id == messageID }),
              let layerIndex = messages[msgIndex].layers.firstIndex(where: { $0.id == layerID }) else { return }
        messages[msgIndex].layers[layerIndex].content = content
    }

    func clear() {
        messages.removeAll()
        messages.append(ChatMessage(role: .system, content: "Conversation cleared. Ready for new chat."))
    }

    var recentConversation: [ChatMessage] {
        Array(messages.filter { $0.role != .system }.suffix(10))
    }
}

@MainActor
final class AppSettings: ObservableObject {
    @AppStorage("apiEndpoint") var apiEndpoint: String = "http://localhost:11434/api/chat"
    @AppStorage("modelName") var modelName: String = "llama3.2:3b"
    @AppStorage("voiceName") var voiceName: String = "Karen (Premium)"
    @AppStorage("speechRate") var speechRate: Double = 160
    @AppStorage("bridgeWebSocketURL") var bridgeWebSocketURL: String = "ws://localhost:8765"
    @AppStorage("continuousListening") var continuousListening: Bool = false
    @AppStorage("autoSpeak") var autoSpeak: Bool = true
    @AppStorage("speechEngineRaw") private var speechEngineRaw: String = SpeechEngine.appleDictation.rawValue
    @AppStorage("voiceOutputEngineRaw") private var voiceOutputEngineRaw: String = VoiceOutputEngine.macOS.rawValue
    @AppStorage("agenticBrainEnabled") var agenticBrainEnabled: Bool = false
    @AppStorage("agenticBrainAPIBaseURL") var agenticBrainAPIBaseURL: String = "http://localhost:8000"
    @AppStorage("agenticBrainWebSocketURL") var agenticBrainWebSocketURL: String = ""
    @AppStorage("agenticBrainSessionID") var agenticBrainSessionID: String = ""
    @AppStorage("agenticBrainUserID") var agenticBrainUserID: String = ""
    @AppStorage("graphRAGEnabled") var graphRAGEnabled: Bool = true
    @AppStorage("graphRAGScope") var graphRAGScope: String = "session"
    @AppStorage("adlConfigPath") var adlConfigPath: String = ""
    @AppStorage("brainChatSystemPrompt") var systemPromptOverride: String = ""
    @AppStorage("brainChatFallbackProviders") private var fallbackProvidersRaw: String = ""
    @AppStorage("agenticBrainModeRaw") private var agenticBrainModeRaw: String = AgenticBrainConnectionMode.hybrid.rawValue
    @AppStorage("brainChatProfileRaw") private var brainChatProfileRaw: String = BrainChatBehaviorProfile.developer.rawValue
    @Published var speechEngine: SpeechEngine = .appleDictation {
        didSet {
            speechEngineRaw = speechEngine.rawValue
        }
    }
    @Published var voiceOutputEngine: VoiceOutputEngine = .macOS {
        didSet {
            voiceOutputEngineRaw = voiceOutputEngine.rawValue
        }
    }

    @Published var claudeAPIKey: String = ""
    @Published var openAIKey: String = ""
    @Published var grokAPIKey: String = ""
    @Published var geminiAPIKey: String = ""
    @Published var groqAPIKey: String = ""
    @Published var agenticBrainAPIKey: String = ""
    @Published var agenticBrainBearerToken: String = ""
    @Published var keychainStatusMessage: String = ""
    @Published var showSettings = false
    @Published var agenticBrainMode: AgenticBrainConnectionMode = .hybrid {
        didSet {
            agenticBrainModeRaw = agenticBrainMode.rawValue
        }
    }
    @Published var behaviorProfile: BrainChatBehaviorProfile = .developer {
        didSet {
            brainChatProfileRaw = behaviorProfile.rawValue
            applyProfileDefaults()
        }
    }

    // Layered response settings
    @AppStorage("layeredModeEnabled") var layeredModeEnabled: Bool = true
    @AppStorage("layeredStrategyRaw") private var layeredStrategyRaw: Int = 0
    var layeredStrategy: LayeredStrategy {
        get {
            switch layeredStrategyRaw {
            case 1: return .qualityFirst
            case 2: return .consensusOnly
            default: return .speedFirst
            }
        }
        set {
            switch newValue {
            case .speedFirst: layeredStrategyRaw = 0
            case .qualityFirst: layeredStrategyRaw = 1
            case .consensusOnly: layeredStrategyRaw = 2
            case .singleLayer: layeredStrategyRaw = 0
            }
        }
    }

    init() {
        loadAPIKeys()
        if let persisted = SpeechEngine(storedValue: speechEngineRaw) {
            speechEngine = persisted
        }
        if let persisted = VoiceOutputEngine(rawValue: voiceOutputEngineRaw) {
            voiceOutputEngine = persisted
        }
        if let persisted = AgenticBrainConnectionMode(rawValue: agenticBrainModeRaw) {
            agenticBrainMode = persisted
        }
        if let persisted = BrainChatBehaviorProfile(rawValue: brainChatProfileRaw) {
            behaviorProfile = persisted
        }
        applyProfileDefaults()
    }

    func loadAPIKeys() {
        do {
            claudeAPIKey = try APIKeyManager.shared.load(.claude)
            openAIKey = try APIKeyManager.shared.load(.openAI)
            grokAPIKey = try APIKeyManager.shared.load(.grok)
            geminiAPIKey = try APIKeyManager.shared.load(.gemini)
            groqAPIKey = try APIKeyManager.shared.loadGroqAPIKey()
            agenticBrainAPIKey = APIKeyManager.shared.key(for: "agentic-brain-api-key") ?? ""
            agenticBrainBearerToken = APIKeyManager.shared.key(for: "agentic-brain-bearer-token") ?? ""
            keychainStatusMessage = ""
        } catch {
            keychainStatusMessage = error.localizedDescription
        }
    }

    func saveAPIKeys() {
        do {
            try APIKeyManager.shared.save(claudeAPIKey, for: .claude)
            try APIKeyManager.shared.save(openAIKey, for: .openAI)
            try APIKeyManager.shared.save(grokAPIKey, for: .grok)
            try APIKeyManager.shared.save(geminiAPIKey, for: .gemini)
            try APIKeyManager.shared.save(groqAPIKey, for: .groq)
            try APIKeyManager.shared.setKey(agenticBrainAPIKey, for: "agentic-brain-api-key")
            try APIKeyManager.shared.setKey(agenticBrainBearerToken, for: "agentic-brain-bearer-token")
            keychainStatusMessage = "API keys saved securely in Keychain."
        } catch {
            keychainStatusMessage = error.localizedDescription
        }
    }

    func clearAPIKeys() {
        do {
            try APIKeyManager.shared.delete(.claude)
            try APIKeyManager.shared.delete(.openAI)
            try APIKeyManager.shared.delete(.grok)
            try APIKeyManager.shared.delete(.gemini)
            try APIKeyManager.shared.delete(.groq)
            APIKeyManager.shared.removeKey(for: "agentic-brain-api-key")
            APIKeyManager.shared.removeKey(for: "agentic-brain-bearer-token")
            claudeAPIKey = ""
            openAIKey = ""
            grokAPIKey = ""
            geminiAPIKey = ""
            groqAPIKey = ""
            agenticBrainAPIKey = ""
            agenticBrainBearerToken = ""
            keychainStatusMessage = "API keys removed from Keychain."
        } catch {
            keychainStatusMessage = error.localizedDescription
        }
    }

    func loadADLConfiguration() {
        let trimmedPath = adlConfigPath.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedPath.isEmpty else {
            keychainStatusMessage = "Enter an ADL file path first."
            return
        }

        do {
            let summary = try ADLConfigurationLoader.load(from: URL(fileURLWithPath: trimmedPath))
            behaviorProfile = summary.profile
            agenticBrainMode = summary.mode
            graphRAGEnabled = summary.graphRAGEnabled
            if let systemPrompt = summary.systemPrompt, !systemPrompt.isEmpty {
                systemPromptOverride = systemPrompt
            } else {
                systemPromptOverride = behaviorProfile.systemPrompt
            }
            fallbackProviders = summary.fallbackProviders
            keychainStatusMessage = "Loaded ADL settings for \(behaviorProfile.displayName.lowercased()) mode."
        } catch {
            keychainStatusMessage = "Couldn't load ADL configuration. \(error.localizedDescription)"
        }
    }

    func routerConfiguration(provider: LLMProvider, yoloMode: Bool) -> LLMRouterConfiguration {
        let effectiveProvider: LLMProvider = agenticBrainMode == .airlocked ? .ollama : provider
        let effectivePrompt = systemPromptOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? behaviorProfile.systemPrompt
            : systemPromptOverride.trimmingCharacters(in: .whitespacesAndNewlines)
        return LLMRouterConfiguration(
            provider: effectiveProvider,
            systemPrompt: effectivePrompt,
            yoloMode: yoloMode,
            bridgeWebSocketURL: bridgeWebSocketURL.trimmingCharacters(in: .whitespacesAndNewlines),
            fallbackProviders: effectiveFallbackProviders(for: effectiveProvider),
            backend: AgenticBrainBackendConfiguration(
                enabled: agenticBrainEnabled,
                restBaseURL: agenticBrainAPIBaseURL.trimmingCharacters(in: .whitespacesAndNewlines),
                webSocketURL: agenticBrainWebSocketURL.trimmingCharacters(in: .whitespacesAndNewlines),
                apiKey: agenticBrainAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
                bearerToken: agenticBrainBearerToken.trimmingCharacters(in: .whitespacesAndNewlines),
                sessionID: agenticBrainSessionID.trimmingCharacters(in: .whitespacesAndNewlines),
                userID: agenticBrainUserID.trimmingCharacters(in: .whitespacesAndNewlines),
                mode: agenticBrainMode,
                graphRAGEnabled: graphRAGEnabled,
                graphRAGScope: graphRAGScope.trimmingCharacters(in: .whitespacesAndNewlines)
            ),
            profile: behaviorProfile,
            claudeAPIKey: claudeAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            openAIAPIKey: openAIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            groqAPIKey: groqAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            grokAPIKey: grokAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            geminiAPIKey: geminiAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            ollamaEndpoint: apiEndpoint.trimmingCharacters(in: .whitespacesAndNewlines),
            ollamaModel: modelName.trimmingCharacters(in: .whitespacesAndNewlines),
            claudeModel: "claude-sonnet-4-20250514",
            openAIModel: "gpt-4o",
            groqModel: "llama-3.1-8b-instant",
            grokModel: "grok-3-latest",
            geminiModel: "gemini-2.5-flash"
        )
    }

    func layeredConfiguration(provider: LLMProvider, yoloMode: Bool) -> LayeredResponseConfiguration {
        let routerConfig = routerConfiguration(provider: provider, yoloMode: yoloMode)
        return LayeredResponseConfiguration.from(
            settings: routerConfig,
            groqAPIKey: groqAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            strategy: layeredStrategy
        )
    }

    var fallbackProviders: [LLMProvider] {
        get {
            fallbackProvidersRaw
                .split(separator: ",")
                .compactMap { LLMProvider(rawValue: String($0)) }
        }
        set {
            fallbackProvidersRaw = newValue.map(\.rawValue).joined(separator: ",")
        }
    }

    private func effectiveFallbackProviders(for provider: LLMProvider) -> [LLMProvider] {
        if agenticBrainMode == .airlocked {
            return [.ollama]
        }

        let configured = fallbackProviders.isEmpty ? behaviorProfile.fallbackProviders : fallbackProviders
        let withoutSelected = configured.filter { $0 != provider }
        return withoutSelected.isEmpty ? behaviorProfile.fallbackProviders.filter { $0 != provider } : withoutSelected
    }

    private func applyProfileDefaults() {
        if systemPromptOverride.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            systemPromptOverride = behaviorProfile.systemPrompt
        }
        speechEngine = behaviorProfile.preferredSpeechEngine
        voiceOutputEngine = behaviorProfile.preferredVoiceOutput
        if fallbackProviders.isEmpty {
            fallbackProviders = behaviorProfile.fallbackProviders
        }
    }
}

// AudioDevice is defined in SpeechManager.swift
