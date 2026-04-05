import Foundation
@testable import BrainChatLib

enum TestFixtures {
    static let history: [ChatMessage] = [
        ChatMessage(role: .system, content: "Welcome"),
        ChatMessage(role: .user, content: "Hello"),
        ChatMessage(role: .assistant, content: "Hi there"),
    ]

    static let ollamaConfig = AIServiceConfig(
        claudeAPIKey: "",
        openAIKey: "",
        ollamaEndpoint: "http://localhost:11434/api/chat",
        ollamaModel: "llama3.2:3b",
        useOpenAI: false,
        accessibilitySystemPrompt: "Accessible prompt"
    )

    static let openAIConfig = AIServiceConfig(
        claudeAPIKey: "",
        openAIKey: "openai-key",
        ollamaEndpoint: "http://localhost:11434/api/chat",
        ollamaModel: "llama3.2:3b",
        useOpenAI: true,
        accessibilitySystemPrompt: "Accessible prompt"
    )

    static let claudeConfig = AIServiceConfig(
        claudeAPIKey: "claude-key",
        openAIKey: "openai-key",
        ollamaEndpoint: "http://localhost:11434/api/chat",
        ollamaModel: "llama3.2:3b",
        useOpenAI: true,
        accessibilitySystemPrompt: "Accessible prompt"
    )

    static func jsonData(_ object: Any) -> Data {
        try! JSONSerialization.data(withJSONObject: object)
    }
}
