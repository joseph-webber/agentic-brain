// BrainChatLib.swift - SPM entry point re-exporting all BrainChat modules
// This file exists to make the library buildable via Swift Package Manager
// for testing. The actual app is built with build.sh using swiftc directly.

// Re-export Foundation for all dependents
@_exported import Foundation

// MARK: - Test Helpers

/// Protocol for mockable API clients
public protocol AIClientProtocol {
    func sendMessage(_ message: String, model: String, endpoint: String,
                     completion: @escaping (Result<String, Error>) -> Void)
}

/// Protocol for mockable speech recognition
public protocol SpeechRecognizerProtocol {
    var isListening: Bool { get }
    func startListening()
    func stopListening()
}

/// Protocol for mockable voice synthesis
public protocol VoiceSynthesizerProtocol {
    var isSpeaking: Bool { get }
    func speak(_ text: String)
    func stop()
}

/// Protocol for mockable shell execution
public protocol CommandExecutorProtocol {
    func run(_ command: String, timeout: TimeInterval?) throws -> ShellResult
}

/// Shell command result for testing
public struct ShellResult {
    public let stdout: String
    public let stderr: String
    public let exitCode: Int32
    public let duration: TimeInterval

    public var succeeded: Bool { exitCode == 0 }
    public var output: String { stdout.isEmpty ? stderr : stdout }

    public init(stdout: String = "", stderr: String = "",
                exitCode: Int32 = 0, duration: TimeInterval = 0.1) {
        self.stdout = stdout
        self.stderr = stderr
        self.exitCode = exitCode
        self.duration = duration
    }
}

/// Copilot response model for testing
public struct TestCopilotResponse {
    public let text: String
    public let duration: TimeInterval
    public let isCodeBlock: Bool
    public let language: String?
    public let codeBlocks: [(language: String?, code: String)]

    public init(text: String, duration: TimeInterval = 0.5,
                isCodeBlock: Bool = false, language: String? = nil,
                codeBlocks: [(language: String?, code: String)] = []) {
        self.text = text
        self.duration = duration
        self.isCodeBlock = isCodeBlock
        self.language = language
        self.codeBlocks = codeBlocks
    }
}

/// Chat message model for testing
public struct TestChatMessage: Identifiable, Equatable {
    public let id: UUID
    public let role: Role
    public let content: String
    public let timestamp: Date

    public enum Role: String {
        case user = "You"
        case assistant = "Brain"
        case system = "System"
    }

    public var accessibilityDescription: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return "\(role.rawValue) said at \(formatter.string(from: timestamp)): \(content)"
    }

    public init(role: Role, content: String, timestamp: Date = Date()) {
        self.id = UUID()
        self.role = role
        self.content = content
        self.timestamp = timestamp
    }

    public static func == (lhs: TestChatMessage, rhs: TestChatMessage) -> Bool {
        lhs.id == rhs.id
    }
}

/// Conversation store for testing
public class TestConversationStore {
    public var messages: [TestChatMessage] = []
    public var isProcessing: Bool = false

    public init() {}

    public func addMessage(role: TestChatMessage.Role, content: String) {
        let msg = TestChatMessage(role: role, content: content)
        messages.append(msg)
    }

    public func clear() {
        messages.removeAll()
        messages.append(TestChatMessage(
            role: .system,
            content: "Conversation cleared. Ready for new chat."
        ))
    }
}

/// Audio device model for testing
public struct TestAudioDevice: Identifiable, Hashable {
    public let id: String
    public let name: String
    public let isAirPodsMax: Bool

    public init(id: String, name: String, isAirPodsMax: Bool = false) {
        self.id = id
        self.name = name
        self.isAirPodsMax = isAirPodsMax
    }
}

/// Route classification for code assistant
public enum TestAssistantRoute: String {
    case copilot = "copilot"
    case system = "system"
    case general = "general"
}

/// Code block extraction utility
public struct CodeBlockParser {
    public init() {}

    public func extractCodeBlocks(from text: String) -> [(language: String?, code: String)] {
        var blocks: [(language: String?, code: String)] = []
        let lines = text.components(separatedBy: "\n")
        var inBlock = false
        var currentLang: String?
        var currentCode: [String] = []

        for line in lines {
            if line.hasPrefix("```") && !inBlock {
                inBlock = true
                let lang = String(line.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                currentLang = lang.isEmpty ? nil : lang
                currentCode = []
            } else if line.hasPrefix("```") && inBlock {
                inBlock = false
                let code = currentCode.joined(separator: "\n")
                if !code.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    blocks.append((language: currentLang, code: code))
                }
                currentLang = nil
                currentCode = []
            } else if inBlock {
                currentCode.append(line)
            }
        }

        return blocks
    }
}

/// Route detector for code assistant testing
public struct RouteDetector {
    private let codingPatterns: [(pattern: String, weight: Int)] = [
        ("create.*python", 10),
        ("create.*rest api", 10),
        ("hello world", 6),
        ("write.*code", 10), ("create.*function", 10), ("implement", 9),
        ("fix.*bug", 9), ("refactor", 8), ("debug", 8),
        ("how.*to.*code", 7), ("algorithm", 7), ("function", 6),
        ("class", 6), ("variable", 5), ("swift", 5),
        ("python", 5), ("javascript", 5), ("api", 4),
        ("database", 4), ("error", 3), ("exception", 3)
    ]

    private let systemKeywords: [String] = [
        "clipboard", "run test", "open app", "open url",
        "git status", "frontmost", "shell", "terminal"
    ]

    public init() {}

    public func detectRoute(for message: String) -> TestAssistantRoute {
        let lower = message.lowercased()

        // Check system keywords first
        for keyword in systemKeywords {
            if lower.contains(keyword) {
                return .system
            }
        }

        // Score coding patterns
        var codingScore = 0
        for (pattern, weight) in codingPatterns {
            if lower.range(of: pattern, options: .regularExpression) != nil {
                codingScore += weight
            }
        }

        if codingScore >= 6 {
            return .copilot
        }

        return .general
    }
}

/// Path validator for system commands testing
public struct PathValidator {
    public let allowedRoots: [String]

    public init(allowedRoots: [String] = []) {
        self.allowedRoots = allowedRoots.isEmpty
            ? [NSHomeDirectory(), "/Users/joe/brain", NSHomeDirectory() + "/Desktop",
               NSHomeDirectory() + "/Documents", NSHomeDirectory() + "/Downloads"]
            : allowedRoots
    }

    public func validate(_ path: String) -> Bool {
        let resolved = (path as NSString).standardizingPath
        return allowedRoots.contains { resolved.hasPrefix($0) }
    }
}

/// Speech recognition update for voice testing
public enum SpeechRecognitionUpdate {
    case partial(String)
    case final(String)
    case failure(String)
    case level(Float)

    public enum Kind { case partial, final, failure, level }

    public var kind: Kind {
        switch self {
        case .partial: return .partial
        case .final: return .final
        case .failure: return .failure
        case .level: return .level
        }
    }

    public var text: String {
        switch self {
        case .partial(let t), .final(let t), .failure(let t): return t
        case .level: return ""
        }
    }

    public var level: Float {
        switch self {
        case .level(let l): return l
        default: return 0
        }
    }
}

/// Blocked commands set for system commands testing
public struct CommandSafety {
    public static let blockedCommands: Set<String> = [
        "rm -rf /", "rm -rf /*", "mkfs", "reboot",
        "shutdown", "halt", "init 0", "init 6",
        "dd if=/dev/zero", ":(){ :|:& };:"
    ]

    public init() {}

    public func isBlocked(_ command: String) -> Bool {
        let lower = command.lowercased().trimmingCharacters(in: .whitespaces)
        return Self.blockedCommands.contains { lower.hasPrefix($0) || lower == $0 }
    }
}

// MARK: - Speech Engine Types

/// Speech engine options for STT
public enum SpeechEngine: String, CaseIterable, Identifiable {
    case appleDictation = "apple"
    case whisperAPI = "whisperAPI"
    case whisperCpp = "whisperCpp"
    case whisperKit = "whisperKit"  // Actually faster-whisper Python
    
    public var id: String { rawValue }
    
    public var description: String {
        switch self {
        case .appleDictation: return "Apple Dictation"
        case .whisperAPI: return "OpenAI Whisper API"
        case .whisperCpp: return "whisper.cpp (Local)"
        case .whisperKit: return "faster-whisper (Local)"
        }
    }
    
    public var requiresAPIKey: Bool {
        switch self {
        case .whisperAPI: return true
        default: return false
        }
    }
}

/// Whisper-related errors
public enum WhisperError: LocalizedError {
    case missingAPIKey
    case invalidResponse
    case apiError(Int, String)
    case recordingFailed
    case noAudioData
    
    public var errorDescription: String? {
        switch self {
        case .missingAPIKey: return "OpenAI API key required for Whisper API"
        case .invalidResponse: return "Invalid response from Whisper API"
        case .apiError(let code, let message): return "Whisper API error \(code): \(message)"
        case .recordingFailed: return "Failed to record audio"
        case .noAudioData: return "No audio data captured"
        }
    }
}

/// App settings for testing
public struct AppSettings {
    public var speechEngine: SpeechEngine
    public var voiceOutputEngine: VoiceOutputEngine
    public var openAIKey: String
    public var ollamaModel: String
    public var claudeModel: String
    public var openAIModel: String
    public var grokModel: String
    public var geminiModel: String
    
    public init(
        speechEngine: SpeechEngine = .appleDictation,
        voiceOutputEngine: VoiceOutputEngine = .macOS,
        openAIKey: String = "",
        ollamaModel: String = "llama3.2:3b",
        claudeModel: String = "claude-sonnet-4-20250514",
        openAIModel: String = "gpt-4o",
        grokModel: String = "grok-3-latest",
        geminiModel: String = "gemini-2.5-flash"
    ) {
        self.speechEngine = speechEngine
        self.voiceOutputEngine = voiceOutputEngine
        self.openAIKey = openAIKey
        self.ollamaModel = ollamaModel
        self.claudeModel = claudeModel
        self.openAIModel = openAIModel
        self.grokModel = grokModel
        self.geminiModel = geminiModel
    }
    
    public static var defaults: AppSettings {
        AppSettings()
    }
}

// MARK: - Voice Output Engine (TTS)

public enum VoiceOutputEngine: String, CaseIterable, Identifiable {
    case macOS = "macOS Native"
    case cartesia = "Cartesia"
    case piper = "Piper TTS"
    case elevenLabs = "ElevenLabs"

    public var id: String { rawValue }

    public var icon: String {
        switch self {
        case .macOS: return "apple.logo"
        case .cartesia: return "bolt.fill"
        case .piper: return "cpu"
        case .elevenLabs: return "star.fill"
        }
    }

    public var description: String {
        switch self {
        case .macOS: return "AVSpeechSynthesizer - Karen voice, works offline"
        case .cartesia: return "Cloud TTS - high quality, low latency"
        case .piper: return "Local neural TTS - cross-platform, offline, open source"
        case .elevenLabs: return "Cloud TTS - premium quality voices"
        }
    }

    public var requiresAPIKey: Bool {
        switch self {
        case .macOS, .piper: return false
        case .cartesia, .elevenLabs: return true
        }
    }

    public var isOffline: Bool {
        switch self {
        case .macOS, .piper: return true
        case .cartesia, .elevenLabs: return false
        }
    }

    public var crossPlatform: Bool {
        switch self {
        case .macOS: return false
        case .cartesia, .piper, .elevenLabs: return true
        }
    }

    public static var platformDefault: VoiceOutputEngine { .macOS }
}

// MARK: - Layered Response System

public typealias LayerTier = LLMResponseLayer

public enum LLMResponseLayer: Int, Comparable, Sendable, CustomStringConvertible {
    case instant = 1
    case fastLocal = 2
    case deep = 3
    case consensus = 4

    public static func < (lhs: LLMResponseLayer, rhs: LLMResponseLayer) -> Bool {
        lhs.rawValue < rhs.rawValue
    }

    public var description: String {
        switch self {
        case .instant:   return "Instant"
        case .fastLocal: return "Local"
        case .deep:      return "Deep"
        case .consensus: return "Consensus"
        }
    }

    public var icon: String {
        switch self {
        case .instant:   return "bolt.fill"
        case .fastLocal: return "desktopcomputer"
        case .deep:      return "brain.head.profile"
        case .consensus: return "checkmark.shield.fill"
        }
    }

    public var timeoutSeconds: TimeInterval {
        switch self {
        case .instant:   return 5
        case .fastLocal: return 10
        case .deep:      return 30
        case .consensus: return 45
        }
    }
}

public struct LayeredChunk: Sendable {
    public let layer: LLMResponseLayer
    public let source: String
    public let content: String
    public let isFinal: Bool
    public let timestamp: Date

    public init(layer: LLMResponseLayer, source: String, content: String, isFinal: Bool = false) {
        self.layer = layer
        self.source = source
        self.content = content
        self.isFinal = isFinal
        self.timestamp = Date()
    }
}

public struct LayerResult: Sendable {
    public let layer: LLMResponseLayer
    public let source: String
    public let fullText: String
    public let latencyMs: Int
    public let succeeded: Bool
    public let error: String?

    public init(layer: LLMResponseLayer, source: String, fullText: String,
                latencyMs: Int, succeeded: Bool, error: String? = nil) {
        self.layer = layer
        self.source = source
        self.fullText = fullText
        self.latencyMs = latencyMs
        self.succeeded = succeeded
        self.error = error
    }
}

public enum LayeredResponseEvent: Sendable {
    case layerStarted(LLMResponseLayer, String)
    case layerDelta(LayeredChunk)
    case layerCompleted(LayerResult)
    case deepThinkingStarted
    case enhancedResponseReady(String)
    case consensusResult(agreed: Bool, sources: [String])
    case allLayersComplete([LayerResult])
}

public enum LayeredStrategy: Sendable {
    case speedFirst
    case qualityFirst
    case consensusOnly
    case singleLayer(LLMResponseLayer)
}

// MARK: - Mock speech recognition controller for testing
public class MockSpeechRecognitionController {
    public var isRecognising: Bool = false
    public var startCallCount: Int = 0
    public var stopCallCount: Int = 0
    public var authorizationStatus: String = "authorized"
    public var isRecognizerAvailable: Bool = true
    public var authorizationRequestCount: Int = 0
    
    public init() {}
    
    public func startRecognition() throws {
        guard authorizationStatus == "authorized" else {
            throw NSError(domain: "SpeechAuth", code: 1, userInfo: [NSLocalizedDescriptionKey: "Not authorized"])
        }
        guard isRecognizerAvailable else {
            throw NSError(domain: "SpeechAvail", code: 2, userInfo: [NSLocalizedDescriptionKey: "Recognizer unavailable"])
        }
        isRecognising = true
        startCallCount += 1
    }
    
    public func stopRecognition() {
        isRecognising = false
        stopCallCount += 1
    }
    
    public func requestAuthorization(_ completion: @escaping (String) -> Void) {
        authorizationRequestCount += 1
        completion(authorizationStatus)
    }
}
