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

extension AIChatMessage {
    var openAIPayload: [String: String] {
        ["role": role.rawValue, "content": content]
    }

    var anthropicPayload: [String: Any] {
        [
            "role": role.rawValue,
            "content": [["type": "text", "text": content]],
        ]
    }
}

enum AIStreamEvent: Sendable { case providerChanged(String), reset, delta(String) }

// MARK: - Speech-to-Text Engines
enum SpeechEngine: String, CaseIterable, Identifiable {
    case apple = "Apple Dictation"
    case whisperKit = "WhisperKit (Local)"
    case whisperAPI = "OpenAI Whisper API"
    case whisperCpp = "whisper.cpp (Local)"
    
    var id: String { rawValue }
    
    var description: String {
        switch self {
        case .apple: return "Native macOS - fast, requires internet"
        case .whisperKit: return "Local Python faster-whisper bridge - private and offline"
        case .whisperAPI: return "Cloud API - highest accuracy, uses OpenAI key"
        case .whisperCpp: return "Local C++ - works offline, very fast"
        }
    }
    
    var icon: String {
        switch self {
        case .apple: return "apple.logo"
        case .whisperKit: return "cpu"
        case .whisperAPI: return "cloud"
        case .whisperCpp: return "terminal"
        }
    }
    
    var requiresAPIKey: Bool {
        self == .whisperAPI
    }
    
    var isLocal: Bool {
        self == .whisperKit || self == .whisperCpp
    }
}

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

// @MainActor
// final class ConversationStore: ObservableObject {
//     @Published var messages: [ChatMessage] = []
//     @Published var isProcessing = false
// 
//     @discardableResult
//     func addMessage(role: ChatMessage.Role, content: String) -> UUID {
//         let message = ChatMessage(role: role, content: content)
//         messages.append(message)
//         return message.id
//     }
// 
//     @discardableResult
//     func beginStreamingAssistantMessage() -> UUID {
//         let message = ChatMessage(role: .assistant, content: "")
//         messages.append(message)
//         return message.id
//     }
// 
//     func replaceMessageContent(id: UUID, content: String) {
//         guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
//         messages[index].content = content
//     }
// 
//     func appendToMessage(id: UUID, delta: String) {
//         guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
//         messages[index].content += delta
//     }
// 
//     func finishStreamingMessage(id: UUID, fallbackContent: String) {
//         guard let index = messages.firstIndex(where: { $0.id == id }) else { return }
//         if messages[index].content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
//             messages[index].content = fallbackContent
//         }
//     }
// 
//     func clear() {
//         messages.removeAll()
//         messages.append(ChatMessage(role: .system, content: "Conversation cleared. Ready for new chat."))
//     }
// 
//     var recentConversation: [ChatMessage] {
//         Array(messages.filter { $0.role != .system }.suffix(10))
//     }
// }

// @MainActor
// final class AppSettings: ObservableObject {
//     @AppStorage("bridgeWebSocketURL") var bridgeWebSocketURL: String = "ws://127.0.0.1:8765"
//     @AppStorage("apiEndpoint") var apiEndpoint: String = "http://localhost:11434/api/chat"
//     @AppStorage("modelName") var modelName: String = "llama3.2:3b"
//     @AppStorage("voiceName") var voiceName: String = "Karen (Premium)"
//     @AppStorage("speechRate") var speechRate: Double = 160
//     @AppStorage("continuousListening") var continuousListening: Bool = false
//     @AppStorage("autoSpeak") var autoSpeak: Bool = true
//     @AppStorage("speechEngineRaw") private var speechEngineRaw: String = SpeechEngine.apple.rawValue
//     
//     var speechEngine: SpeechEngine {
//         get { SpeechEngine(rawValue: speechEngineRaw) ?? .apple }
//         set { speechEngineRaw = newValue.rawValue }
//     }
//     
//     @Published var claudeAPIKey: String = ""
//     @Published var openAIKey: String = ""
//     @Published var grokAPIKey: String = ""
//     @Published var geminiAPIKey: String = ""
//     @Published var keychainStatusMessage: String = ""
//     @Published var showSettings = false
// 
//     init() { loadAPIKeys() }
// 
//     func loadAPIKeys() {
//         do {
//             claudeAPIKey = try APIKeyManager.shared.load(.claude)
//             openAIKey = try APIKeyManager.shared.load(.openAI)
//             grokAPIKey = try APIKeyManager.shared.load(.grok)
//             geminiAPIKey = try APIKeyManager.shared.load(.gemini)
//             keychainStatusMessage = ""
//         } catch {
//             keychainStatusMessage = error.localizedDescription
//         }
//     }
// 
//     func saveAPIKeys() {
//         do {
//             try APIKeyManager.shared.save(claudeAPIKey, for: .claude)
//             try APIKeyManager.shared.save(openAIKey, for: .openAI)
//             try APIKeyManager.shared.save(grokAPIKey, for: .grok)
//             try APIKeyManager.shared.save(geminiAPIKey, for: .gemini)
//             keychainStatusMessage = "API keys saved securely in Keychain."
//         } catch {
//             keychainStatusMessage = error.localizedDescription
//         }
//     }
// 
//     func clearAPIKeys() {
//         do {
//             try APIKeyManager.shared.delete(.claude)
//             try APIKeyManager.shared.delete(.openAI)
//             try APIKeyManager.shared.delete(.grok)
//             try APIKeyManager.shared.delete(.gemini)
//             claudeAPIKey = ""
//             openAIKey = ""
//             grokAPIKey = ""
//             geminiAPIKey = ""
//             keychainStatusMessage = "API keys removed from Keychain."
//         } catch {
//             keychainStatusMessage = error.localizedDescription
//         }
//     }
// 
//     func routerConfiguration(provider: LLMProvider, yoloMode: Bool) -> LLMRouterConfiguration {
//         let brainSystemPrompt = """
// You are Karen, an Australian AI assistant helping Joseph code. Joseph is a blind developer who uses VoiceOver.
// 
// ## CODEBASE KNOWLEDGE
// 
// You have access to Joseph's brain codebase at ~/brain with these key directories:
// 
// ### agentic-brain/ (Main AI Framework)
// - src/agentic_brain/voice/ - Voice system with Karen and 13 other ladies
// - src/agentic_brain/audio/ - Audio processing, spatial audio, earcons
// - src/agentic_brain/llm/ - LLM routing (Claude, GPT, Ollama, Grok, Gemini)
// - src/agentic_brain/memory/ - Memory systems (episodic, procedural, working)
// - src/agentic_brain/core/ - Neo4j, Redis, Redpanda integrations
// - apps/BrainChat/ - This native Swift macOS app
// 
// ### brain-core/ (Shared Modules - Open Source)
// - core/ - 37 shared modules: Continuity, HotMemory, FuzzySearch, DepsManager
// - voice/ - Voice framework (not the ladies, just the engine)
// 
// ### Key Technologies
// - Python 3.14 with FastAPI
// - Swift 6 for native macOS apps
// - Neo4j for knowledge graph
// - Redis for caching and voice queue
// - Redpanda for event streaming
// - MLX for M2 GPU acceleration
// 
// ### Voice System
// - Karen (Australian) is the main voice
// - 13 other ladies for different tasks (Kyoko, Tingting, Moira, etc.)
// - Cartesia TTS for high-quality synthesis
// - Apple Speech for recognition
// 
// ## CODING STYLE
// - Always use type hints in Python
// - Use @MainActor for Swift UI code
// - Keep responses concise for VoiceOver
// - Test with pytest in Python, swift test in Swift
// 
// ## ACCESSIBILITY
// Joseph is BLIND. Always:
// - Be concise and clear
// - Speak important info aloud
// - Consider VoiceOver compatibility
// - Never rely on visual formatting alone
// 
// Respond in a friendly Australian manner. Keep responses SHORT - Joseph listens to them!
// """
//         
//         return LLMRouterConfiguration(
//             provider: provider,
//             systemPrompt: brainSystemPrompt,
//             yoloMode: yoloMode,
//             bridgeWebSocketURL: bridgeWebSocketURL.trimmingCharacters(in: .whitespacesAndNewlines),
//             claudeAPIKey: claudeAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
//             openAIAPIKey: openAIKey.trimmingCharacters(in: .whitespacesAndNewlines),
//             grokAPIKey: grokAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
//             geminiAPIKey: geminiAPIKey.trimmingCharacters(in: .whitespacesAndNewlines),
//             ollamaEndpoint: apiEndpoint.trimmingCharacters(in: .whitespacesAndNewlines),
//             ollamaModel: modelName.trimmingCharacters(in: .whitespacesAndNewlines),
//             claudeModel: "claude-sonnet-4-20250514",
//             openAIModel: "gpt-4o",
//             grokModel: "grok-3-latest",
//             geminiModel: "gemini-2.5-flash"
//         )
//     }
// }

// AudioDevice is defined in SpeechManager.swift
