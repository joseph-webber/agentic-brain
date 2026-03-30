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

enum AIStreamEvent: Sendable { case providerChanged(String), reset, delta(String) }

struct ChatMessage: Identifiable, Equatable {
    let id: UUID
    let role: Role
    var content: String
    let timestamp: Date

    enum Role: String {
        case user = "You"
        case assistant = "Karen"
        case system = "System"

        var aiRole: AIRole {
            switch self {
            case .user: return .user
            case .assistant: return .assistant
            case .system: return .system
            }
        }
    }

    var accessibilityDescription: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return "\(role.rawValue) said at \(formatter.string(from: timestamp)): \(content)"
    }

    init(id: UUID = UUID(), role: Role, content: String, timestamp: Date = Date()) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
    }

    var accessibilityDescription: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return "\(role.rawValue) said at \(formatter.string(from: timestamp)): \(content)"
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
        let message = ChatMessage(role: .assistant, content: "")
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
    @AppStorage("bridgeWebSocketURL") var bridgeWebSocketURL: String = "ws://127.0.0.1:8765"
    @AppStorage("apiEndpoint") var apiEndpoint: String = "http://localhost:11434/api/chat"
    @AppStorage("modelName") var modelName: String = "llama3.2:3b"
    @AppStorage("voiceName") var voiceName: String = "Karen (Premium)"
    @AppStorage("speechRate") var speechRate: Double = 160
    @AppStorage("continuousListening") var continuousListening: Bool = false
    @AppStorage("autoSpeak") var autoSpeak: Bool = true
    @Published var claudeAPIKey: String = ""
    @Published var openAIKey: String = ""
    @Published var keychainStatusMessage: String = ""
    @Published var showSettings = false

    init() { loadAPIKeys() }

    func loadAPIKeys() {
        do {
            claudeAPIKey = try APIKeyManager.shared.load(.claude)
            openAIKey = try APIKeyManager.shared.load(.openAI)
            keychainStatusMessage = ""
        } catch {
            keychainStatusMessage = error.localizedDescription
        }
    }

    func saveAPIKeys() {
        do {
            try APIKeyManager.shared.save(claudeAPIKey, for: .claude)
            try APIKeyManager.shared.save(openAIKey, for: .openAI)
            keychainStatusMessage = "API keys saved securely in Keychain."
        } catch {
            keychainStatusMessage = error.localizedDescription
        }
    }

    func clearAPIKeys() {
        do {
            try APIKeyManager.shared.delete(.claude)
            try APIKeyManager.shared.delete(.openAI)
            claudeAPIKey = ""
            openAIKey = ""
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
            ollamaEndpoint: apiEndpoint.trimmingCharacters(in: .whitespacesAndNewlines),
            ollamaModel: modelName.trimmingCharacters(in: .whitespacesAndNewlines),
            claudeModel: "claude-sonnet-4-20250514",
            openAIModel: "gpt-4o"
        )
    }
}

struct AudioDevice: Identifiable, Hashable {
    let id: String
    let name: String
    let isAirPodsMax: Bool
}
