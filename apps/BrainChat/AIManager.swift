import Foundation
import Combine

// Types (AIRole, AIChatMessage, AIStreamEvent, AIServiceError) are in Models.swift

struct AIConfiguration: Sendable {
    let systemPrompt: String
    let claudeAPIKey: String
    let claudeModel: String
    let openAIAPIKey: String
    let openAIModel: String
    let groqAPIKey: String
    let groqModel: String
    let ollamaEndpoint: String
    let ollamaModel: String

    init(
        systemPrompt: String,
        claudeAPIKey: String = "",
        claudeModel: String = "claude-sonnet-4-20250514",
        openAIAPIKey: String = "",
        openAIModel: String = "gpt-4o",
        groqAPIKey: String = "",
        groqModel: String = "llama-3.1-8b-instant",
        ollamaEndpoint: String = "http://localhost:11434/api/chat",
        ollamaModel: String = "llama3.2:3b"
    ) {
        self.systemPrompt = systemPrompt
        self.claudeAPIKey = claudeAPIKey
        self.claudeModel = claudeModel
        self.openAIAPIKey = openAIAPIKey
        self.openAIModel = openAIModel
        self.groqAPIKey = groqAPIKey
        self.groqModel = groqModel
        self.ollamaEndpoint = ollamaEndpoint
        self.ollamaModel = ollamaModel
    }
}

enum AIProvider: Sendable {
    case groq, claude, openAI, ollama

    var displayName: String {
        switch self {
        case .groq:   return "Groq (Instant)"
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

    private let groqAPI: any GroqStreaming
    private let claudeAPI: any ClaudeStreaming
    private let openAIAPI: any OpenAIStreaming
    private let ollamaAPI: any OllamaStreaming

    init(
        groqAPI: any GroqStreaming = GroqClient(),
        claudeAPI: any ClaudeStreaming = ClaudeAPI(),
        openAIAPI: any OpenAIStreaming = OpenAIAPI(),
        ollamaAPI: any OllamaStreaming = OllamaAPI()
    ) {
        self.groqAPI = groqAPI
        self.claudeAPI = claudeAPI
        self.openAIAPI = openAIAPI
        self.ollamaAPI = ollamaAPI
    }

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
                case .groq:
                    response = try await groqAPI.streamResponse(apiKey: configuration.groqAPIKey, model: configuration.groqModel, messages: messages, onDelta: { onEvent(.delta($0)) })
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
        return "Sorry, all AI providers are unavailable right now. \(failures.last ?? "Unknown failure")"
    }

    private func routedProviders(for configuration: AIConfiguration) -> [AIProvider] {
        var providers: [AIProvider] = []
        // Fast path: Groq first when configured (500+ tok/s)
        if !configuration.groqAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            providers.append(.groq)
        }
        if !configuration.claudeAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            providers.append(.claude)
        }
        if !configuration.openAIAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            providers.append(.openAI)
        }
        // Always include Ollama as the local fallback
        providers.append(.ollama)
        return providers
    }

    private static func buildContext(from history: [ChatMessage], systemPrompt: String) -> [AIChatMessage] {
        var messages = [AIChatMessage(role: .system, content: systemPrompt)]
        messages.append(contentsOf: history
            .filter { $0.role != .system && !$0.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            .suffix(10)
            .map { AIChatMessage(role: $0.role.aiRole, content: $0.content) })
        return messages
    }
}
