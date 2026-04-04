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
    @Published var keychainStatusMessage: String = ""
    @Published var showSettings = false

    init() {
        loadAPIKeys()
        if let persisted = SpeechEngine(storedValue: speechEngineRaw) {
            speechEngine = persisted
        }
        if let persisted = VoiceOutputEngine(rawValue: voiceOutputEngineRaw) {
            voiceOutputEngine = persisted
        }
    }

    func loadAPIKeys() {
        do {
            claudeAPIKey = try APIKeyManager.shared.load(.claude)
            openAIKey = try APIKeyManager.shared.load(.openAI)
            grokAPIKey = try APIKeyManager.shared.load(.grok)
            geminiAPIKey = try APIKeyManager.shared.load(.gemini)
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
            claudeAPIKey = ""
            openAIKey = ""
            grokAPIKey = ""
            geminiAPIKey = ""
            keychainStatusMessage = "API keys removed from Keychain."
        } catch {
            keychainStatusMessage = error.localizedDescription
        }
    }

    func routerConfiguration(provider: LLMProvider, yoloMode: Bool) -> LLMRouterConfiguration {
        LLMRouterConfiguration(
            provider: provider,
            systemPrompt: "You are Karen, an Australian AI assistant helping Joseph code",
            yoloMode: yoloMode,
            bridgeWebSocketURL: bridgeWebSocketURL.trimmingCharacters(in: .whitespacesAndNewlines),
            claudeAPIKey: claudeAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            openAIAPIKey: openAIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            grokAPIKey: grokAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            geminiAPIKey: geminiAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
            ollamaEndpoint: apiEndpoint.trimmingCharacters(in: .whitespacesAndNewlines),
            ollamaModel: modelName.trimmingCharacters(in: .whitespacesAndNewlines),
            claudeModel: "claude-sonnet-4-20250514",
            openAIModel: "gpt-4o",
            grokModel: "grok-3-latest",
            geminiModel: "gemini-2.5-flash"
        )
    }
}

// AudioDevice is defined in SpeechManager.swift
