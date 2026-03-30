import Foundation
import Combine

// Types (AIRole, AIChatMessage, AIStreamEvent, AIServiceError) are in Models.swift

struct AIConfiguration: Sendable {
    let systemPrompt: String
    let claudeAPIKey: String
    let claudeModel: String
    let openAIAPIKey: String
    let openAIModel: String
    let ollamaEndpoint: String
    let ollamaModel: String
}

enum AIProvider: Sendable {
    case claude, openAI, ollama
    var displayName: String {
        switch self {
        case .claude: return "Claude Sonnet 4"
        case .openAI: return "OpenAI GPT-4o"
        case .ollama: return "Ollama llama3.2"
        }
    }
}

extension AIChatMessage {
    var openAIPayload: [String: String] { ["role": role.rawValue, "content": content] }
    var anthropicPayload: [String: Any] { ["role": role.rawValue, "content": [["type": "text", "text": content]]] }
}

@MainActor
final class AIManager: ObservableObject {
    @Published private(set) var activeProviderName = "Idle"
    @Published private(set) var statusMessage = "Ready"
    @Published private(set) var lastErrorMessage: String?
    private let claudeAPI = ClaudeAPI()
    private let openAIAPI = OpenAIAPI()
    private let ollamaAPI = OllamaAPI()

    func streamReply(history: [ChatMessage], configuration: AIConfiguration, onEvent: @escaping @Sendable (AIStreamEvent) -> Void) async -> String {
        let messages = Self.buildContext(from: history, systemPrompt: configuration.systemPrompt)
        let providers = routedProviders(for: configuration)
        var failures: [String] = []
        for (index, provider) in providers.enumerated() {
            if index > 0 { onEvent(.reset) }
            activeProviderName = provider.displayName
            statusMessage = "Thinking with \(provider.displayName)..."
            onEvent(.providerChanged(provider.displayName))
            do {
                let response: String
                switch provider {
                case .claude:
                    response = try await claudeAPI.streamResponse(apiKey: configuration.claudeAPIKey, model: configuration.claudeModel, systemPrompt: configuration.systemPrompt, messages: messages, onDelta: { onEvent(.delta($0)) })
                case .openAI:
                    response = try await openAIAPI.streamResponse(apiKey: configuration.openAIAPIKey, model: configuration.openAIModel, messages: messages, onDelta: { onEvent(.delta($0)) })
                case .ollama:
                    response = try await ollamaAPI.streamResponse(endpoint: configuration.ollamaEndpoint, model: configuration.ollamaModel, messages: messages, onDelta: { onEvent(.delta($0)) })
                }
                lastErrorMessage = nil
                statusMessage = "Ready"
                return response
            } catch {
                let failure = "\(provider.displayName): \(error.localizedDescription)"
                failures.append(failure)
                lastErrorMessage = failure
                statusMessage = "\(provider.displayName) failed, trying fallback..."
            }
        }
        activeProviderName = "Unavailable"
        statusMessage = "All AI backends unavailable"
        return "Sorry Joseph, Claude, GPT, and Ollama are all unavailable right now. \(failures.last ?? "Unknown failure")"
    }

    private func routedProviders(for configuration: AIConfiguration) -> [AIProvider] {
        var providers: [AIProvider] = []
        if !configuration.claudeAPIKey.isEmpty { providers.append(.claude) }
        if !configuration.openAIAPIKey.isEmpty { providers.append(.openAI) }
        providers.append(.ollama)
        return providers
    }

    private static func buildContext(from history: [ChatMessage], systemPrompt: String) -> [AIChatMessage] {
        var messages = [AIChatMessage(role: .system, content: systemPrompt)]
        messages.append(contentsOf: history.filter { $0.role != .system && !$0.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.suffix(10).map { AIChatMessage(role: $0.role.aiRole, content: $0.content) })
        return messages
    }
}
