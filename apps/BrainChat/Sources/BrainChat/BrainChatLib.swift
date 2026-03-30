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

// MARK: - Comprehensive test support types

import AVFoundation
import Combine
import Speech

public struct ChatMessage: Identifiable, Equatable {
    public let id: UUID
    public let role: Role
    public let content: String
    public let timestamp: Date

    public enum Role: String {
        case user = "You"
        case assistant = "Brain"
        case system = "System"
    }

    public init(id: UUID = UUID(), role: Role, content: String, timestamp: Date = Date()) {
        self.id = id
        self.role = role
        self.content = content
        self.timestamp = timestamp
    }

    public var accessibilityDescription: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return "\(role.rawValue) said at \(formatter.string(from: timestamp)): \(content)"
    }
}

@MainActor
public final class ConversationStore: ObservableObject {
    @Published public var messages: [ChatMessage] = []
    @Published public var isProcessing = false

    public init() {}

    public func addMessage(role: ChatMessage.Role, content: String) {
        messages.append(ChatMessage(role: role, content: content))
    }

    public func clear() {
        messages.removeAll()
        messages.append(ChatMessage(role: .system, content: "Conversation cleared. Ready for new chat."))
    }
}

public struct AudioDevice: Identifiable, Hashable {
    public let id: String
    public let name: String
    public let isAirPodsMax: Bool

    public init(id: String, name: String, isAirPodsMax: Bool = false) {
        self.id = id
        self.name = name
        self.isAirPodsMax = isAirPodsMax
    }
}

public protocol SecureKeyValueStore {
    func set(value: String, service: String, account: String) throws
    func get(service: String, account: String) -> String?
    func remove(service: String, account: String)
}

public protocol APIKeyManaging {
    func setKey(_ value: String, for provider: String) throws
    func key(for provider: String) -> String?
    func removeKey(for provider: String)
    func hasKey(for provider: String) -> Bool
}

public final class APIKeyManager: APIKeyManaging {
    public enum APIKeyError: LocalizedError, Equatable {
        case saveFailed(OSStatus)

        public var errorDescription: String? {
            switch self {
            case .saveFailed(let status):
                return "Could not save API key to Keychain (status \(status))."
            }
        }
    }

    public static let shared = APIKeyManager()

    private let store: SecureKeyValueStore?
    private let service: String
    private static var defaultsStore: [String: String] = [:]

    public init(store: SecureKeyValueStore? = nil, service: String = "BrainChat.APIKeys") {
        self.store = store
        self.service = service
    }

    public func setKey(_ value: String, for provider: String) throws {
        if let store {
            try store.set(value: value, service: service, account: provider)
        } else {
            Self.defaultsStore["\(service)::\(provider)"] = value
        }
    }

    public func key(for provider: String) -> String? {
        if let store {
            return store.get(service: service, account: provider)
        }
        return Self.defaultsStore["\(service)::\(provider)"]
    }

    public func removeKey(for provider: String) {
        if let store {
            store.remove(service: service, account: provider)
        } else {
            Self.defaultsStore.removeValue(forKey: "\(service)::\(provider)")
        }
    }

    public func hasKey(for provider: String) -> Bool {
        key(for: provider)?.isEmpty == false
    }
}

public struct AIServiceConfig: Equatable {
    public var claudeAPIKey: String = ""
    public var openAIKey: String = ""
    public var ollamaEndpoint: String = "http://localhost:11434/api/chat"
    public var ollamaModel: String = "llama3.2:3b"
    public var useOpenAI: Bool = false
    public var accessibilitySystemPrompt: String = "You are Brain, Joseph's AI assistant. Be helpful, concise, and warm. Joseph is blind and uses VoiceOver, so keep responses clear and well-structured."

    public init(claudeAPIKey: String = "", openAIKey: String = "", ollamaEndpoint: String = "http://localhost:11434/api/chat", ollamaModel: String = "llama3.2:3b", useOpenAI: Bool = false, accessibilitySystemPrompt: String = "You are Brain, Joseph's AI assistant. Be helpful, concise, and warm. Joseph is blind and uses VoiceOver, so keep responses clear and well-structured.") {
        self.claudeAPIKey = claudeAPIKey
        self.openAIKey = openAIKey
        self.ollamaEndpoint = ollamaEndpoint
        self.ollamaModel = ollamaModel
        self.useOpenAI = useOpenAI
        self.accessibilitySystemPrompt = accessibilitySystemPrompt
    }
}

public enum AIBackend: String, Equatable {
    case claude
    case gpt
    case ollama
}

public struct AIChatResponse: Equatable {
    public let text: String
    public let backend: AIBackend

    public init(text: String, backend: AIBackend) {
        self.text = text
        self.backend = backend
    }
}

public protocol HTTPClient {
    func send(request: URLRequest, completion: @escaping (Result<(Data, HTTPURLResponse), Error>) -> Void)
}

public final class AIManager {
    public struct PayloadMessage: Equatable {
        public let role: String
        public let content: String
    }

    private let httpClient: HTTPClient

    public init(httpClient: HTTPClient) {
        self.httpClient = httpClient
    }

    public func route(for config: AIServiceConfig) -> AIBackend {
        if !config.claudeAPIKey.isEmpty { return .claude }
        if config.useOpenAI && !config.openAIKey.isEmpty { return .gpt }
        return .ollama
    }

    public func buildHistory(from messages: [ChatMessage]) -> [PayloadMessage] {
        messages.suffix(10).map { PayloadMessage(role: roleName(for: $0.role), content: $0.content) }
    }

    public func makeOpenAIRequest(message: String, history: [ChatMessage], config: AIServiceConfig) throws -> URLRequest {
        let url = URL(string: "https://api.openai.com/v1/chat/completions")!
        let historyPayload = buildHistory(from: history).map { ["role": $0.role, "content": $0.content] }
        let body: [String: Any] = [
            "model": "gpt-4o",
            "messages": [["role": "system", "content": config.accessibilitySystemPrompt]] + historyPayload + [["role": "user", "content": message]],
            "max_tokens": 1024,
        ]
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(config.openAIKey)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    public func makeClaudeRequest(message: String, history: [ChatMessage], config: AIServiceConfig) throws -> URLRequest {
        let url = URL(string: "https://api.anthropic.com/v1/messages")!
        let historyPayload = buildHistory(from: history).map { ["role": $0.role, "content": $0.content] }
        let body: [String: Any] = [
            "model": "claude-3-7-sonnet-latest",
            "max_tokens": 1024,
            "system": config.accessibilitySystemPrompt,
            "messages": historyPayload + [["role": "user", "content": message]],
        ]
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(config.claudeAPIKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    public func makeOllamaRequest(message: String, history: [ChatMessage], config: AIServiceConfig) throws -> URLRequest {
        guard let url = URL(string: config.ollamaEndpoint) else { throw URLError(.badURL) }
        let historyPayload = buildHistory(from: history).map { ["role": $0.role, "content": $0.content] }
        let body: [String: Any] = [
            "model": config.ollamaModel,
            "messages": historyPayload + [["role": "user", "content": message]],
            "stream": false,
        ]
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    public func send(message: String, history: [ChatMessage], config: AIServiceConfig, completion: @escaping (AIChatResponse) -> Void) {
        let backend = route(for: config)
        let request = try? (backend == .claude ? makeClaudeRequest(message: message, history: history, config: config) : backend == .gpt ? makeOpenAIRequest(message: message, history: history, config: config) : makeOllamaRequest(message: message, history: history, config: config))
        guard let request else {
            completion(AIChatResponse(text: "Error: invalid request", backend: backend))
            return
        }
        httpClient.send(request: request) { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure(let error):
                let prefix = backend == .ollama ? "Connection error" : "API error"
                completion(AIChatResponse(text: "\(prefix): \(error.localizedDescription)", backend: backend))
            case .success(let (data, response)):
                completion(self.parseResponse(data: data, response: response, backend: backend, endpoint: request.url))
            }
        }
    }

    public func send(message: String, history: [ChatMessage], config: AIServiceConfig) async -> AIChatResponse {
        await withCheckedContinuation { continuation in
            send(message: message, history: history, config: config) { continuation.resume(returning: $0) }
        }
    }

    public func parseResponse(data: Data, response: HTTPURLResponse, backend: AIBackend, endpoint: URL?) -> AIChatResponse {
        guard (200..<300).contains(response.statusCode) else {
            return AIChatResponse(text: "Request failed", backend: backend)
        }
        let parsed: String?
        switch backend {
        case .ollama:
            parsed = (try? JSONSerialization.jsonObject(with: data) as? [String: Any]).flatMap { ($0["message"] as? [String: Any])?["content"] as? String }
        case .gpt:
            parsed = (try? JSONSerialization.jsonObject(with: data) as? [String: Any]).flatMap { (($0["choices"] as? [[String: Any]])?.first?["message"] as? [String: Any])?["content"] as? String }
        case .claude:
            parsed = ((try? JSONSerialization.jsonObject(with: data) as? [String: Any])?["content"] as? [[String: Any]])?.compactMap { $0["text"] as? String }.joined(separator: "\n")
        }
        return AIChatResponse(text: parsed ?? "Could not parse response from \(endpoint?.absoluteString ?? "endpoint")", backend: backend)
    }

    private func roleName(for role: ChatMessage.Role) -> String {
        switch role {
        case .user: return "user"
        case .assistant: return "assistant"
        case .system: return "system"
        }
    }
}

public protocol VoiceSynthesizerDelegate: AnyObject {
    func voiceSynthesizerDidFinishSpeaking(_ synthesizer: VoiceSynthesizing, successfully: Bool)
}

public protocol VoiceSynthesizing: AnyObject {
    var delegate: VoiceSynthesizerDelegate? { get set }
    var rate: Float { get set }
    func availableVoices() -> [VoiceManager.VoiceInfo]
    func setVoice(id: String)
    func startSpeaking(_ text: String)
    func stopSpeaking()
}

public final class VoiceManager: ObservableObject {
    public struct VoiceInfo: Identifiable, Hashable {
        public let id: String
        public let name: String
        public let language: String
        public let isPremium: Bool

        public init(id: String, name: String, language: String, isPremium: Bool) {
            self.id = id
            self.name = name
            self.language = language
            self.isPremium = isPremium
        }
    }

    @Published public var isSpeaking = false
    @Published public var availableVoices: [VoiceInfo] = []
    @Published public var selectedVoiceName = "Karen (Premium)"
    @Published public var speechRate: Float = 160.0

    private let synthesizer: VoiceSynthesizing
    private var queue: [String] = []
    private var processing = false

    public init(synthesizer: VoiceSynthesizing) {
        self.synthesizer = synthesizer
        self.synthesizer.delegate = self
        loadVoices()
        selectVoice(named: selectedVoiceName)
    }

    public func loadVoices() {
        availableVoices = synthesizer.availableVoices().sorted { lhs, rhs in
            if lhs.name.contains("Karen") && !rhs.name.contains("Karen") { return true }
            if !lhs.name.contains("Karen") && rhs.name.contains("Karen") { return false }
            return lhs.name < rhs.name
        }
    }

    public func selectVoice(named name: String) {
        selectedVoiceName = name
        if let match = availableVoices.first(where: { $0.name.localizedCaseInsensitiveContains(name.replacingOccurrences(of: " (Premium)", with: "")) }) {
            synthesizer.setVoice(id: match.id)
        } else if let karen = synthesizer.availableVoices().first(where: { $0.name.contains("Karen") }) {
            synthesizer.setVoice(id: karen.id)
        }
    }

    public func speak(_ text: String) {
        queue.append(text)
        processQueue()
    }

    public func speakImmediately(_ text: String) {
        stop()
        synthesizer.rate = speechRate
        synthesizer.startSpeaking(text)
        isSpeaking = true
    }

    public func stop() {
        synthesizer.stopSpeaking()
        queue.removeAll()
        processing = false
        isSpeaking = false
    }

    private func processQueue() {
        guard !processing, !queue.isEmpty else { return }
        processing = true
        synthesizer.rate = speechRate
        synthesizer.startSpeaking(queue.removeFirst())
        isSpeaking = true
    }

    public func handleSpeechFinished(successfully _: Bool = true) {
        processing = false
        if queue.isEmpty {
            isSpeaking = false
        } else {
            processQueue()
        }
    }
}

extension VoiceManager: VoiceSynthesizerDelegate {
    public func voiceSynthesizerDidFinishSpeaking(_ synthesizer: VoiceSynthesizing, successfully: Bool) {
        handleSpeechFinished(successfully: successfully)
    }
}

public protocol SpeechRecognitionControlling {
    var currentAuthorizationStatus: SFSpeechRecognizerAuthorizationStatus { get }
    var isRecognizerAvailable: Bool { get }
    func requestAuthorization(_ completion: @escaping (SFSpeechRecognizerAuthorizationStatus) -> Void)
    func availableInputDevices() -> [AudioDevice]
    func startRecognition(handler: @escaping (SpeechRecognitionUpdate) -> Void) throws
    func stopRecognition()
}

public final class SpeechManager: ObservableObject {
    @Published public var isListening = false
    @Published public var currentTranscript = ""
    @Published public var authorizationStatus: SFSpeechRecognizerAuthorizationStatus = .notDetermined
    @Published public var errorMessage: String?
    @Published public var inputDevices: [AudioDevice] = []
    @Published public var selectedDevice: AudioDevice?
    @Published public var audioLevel: Float = 0

    public var onTranscriptFinalized: ((String) -> Void)?

    private let controller: SpeechRecognitionControlling

    public init(controller: SpeechRecognitionControlling, requestAuthorizationOnInit: Bool = true) {
        self.controller = controller
        authorizationStatus = controller.currentAuthorizationStatus
        if requestAuthorizationOnInit { requestAuthorization() }
        refreshDevices()
    }

    public func requestAuthorization() {
        controller.requestAuthorization { status in
            self.authorizationStatus = status
            self.errorMessage = status == .authorized ? nil : "Speech recognition not authorized. Enable in System Settings > Privacy > Speech Recognition."
        }
    }

    public func refreshDevices() {
        let devices = controller.availableInputDevices()
        inputDevices = devices.isEmpty ? [AudioDevice(id: "default", name: "Built-in Microphone")] : devices
        selectedDevice = inputDevices.first(where: { $0.isAirPodsMax }) ?? inputDevices.first
    }

    public func startListening() {
        guard authorizationStatus == .authorized else {
            errorMessage = "Speech recognition not authorized."
            return
        }
        guard controller.isRecognizerAvailable else {
            errorMessage = "Speech recognizer is not available."
            return
        }
        isListening = true
        do {
            try controller.startRecognition { [weak self] update in self?.handle(update) }
        } catch {
            isListening = false
            errorMessage = "Failed to start: \(error.localizedDescription)"
        }
    }

    public func stopListening() {
        controller.stopRecognition()
        isListening = false
        audioLevel = 0
    }

    public func handle(_ update: SpeechRecognitionUpdate) {
        switch update {
        case .partial(let text): currentTranscript = text
        case .final(let text):
            currentTranscript = text
            isListening = false
            audioLevel = 0
            onTranscriptFinalized?(text)
        case .failure(let message):
            errorMessage = message
            isListening = false
            audioLevel = 0
        case .level(let value):
            audioLevel = min(max(value, 0), 1)
        }
    }
}

public struct CommandResult {
    public let stdout: String
    public let stderr: String
    public let exitCode: Int32
    public let duration: TimeInterval
    public var succeeded: Bool { exitCode == 0 }
    public var output: String { stdout.isEmpty ? stderr : stdout }

    public init(stdout: String = "", stderr: String = "", exitCode: Int32 = 0, duration: TimeInterval = 0.1) {
        self.stdout = stdout
        self.stderr = stderr
        self.exitCode = exitCode
        self.duration = duration
    }
}

public protocol SystemCommandProviding {
    func speak(_ text: String, voice: String, rate: Int)
    func runTests(in directory: String) throws -> CommandResult
    func readClipboard() -> String
    func writeClipboard(_ text: String)
    func openApp(_ appName: String) throws
    func openURL(_ urlString: String) throws
    func gitStatus(in directory: String) throws -> CommandResult
    func frontmostApp() -> String
    func run(_ command: String, timeout: TimeInterval?, workingDirectory: String?) throws -> CommandResult
}

public enum AssistantRoute: Equatable {
    case copilot
    case system
    case general
}

public struct AssistantResponse: Equatable {
    public let text: String
    public let route: AssistantRoute
    public let duration: TimeInterval
    public let codeBlocks: [(language: String?, code: String)]
    public var hasCode: Bool { !codeBlocks.isEmpty }

    public init(text: String, route: AssistantRoute, duration: TimeInterval, codeBlocks: [(language: String?, code: String)]) {
        self.text = text
        self.route = route
        self.duration = duration
        self.codeBlocks = codeBlocks
    }

    public static func == (lhs: AssistantResponse, rhs: AssistantResponse) -> Bool {
        lhs.text == rhs.text && lhs.route == rhs.route && lhs.duration == rhs.duration && lhs.codeBlocks.count == rhs.codeBlocks.count
    }
}

public protocol CopilotCLIRunning {
    var isAvailable: Bool { get }
    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> (stdout: String, stderr: String, exitCode: Int32)
    func cancel()
}

public enum CopilotError: Error, LocalizedError, Equatable {
    case cliNotFound
    case timeout
    case executionFailed(code: Int32, stderr: String)
    case emptyResponse
    case alreadyRunning

    public var errorDescription: String? {
        switch self {
        case .cliNotFound: return "Copilot CLI not found at expected path."
        case .timeout: return "Copilot CLI timed out after 30 seconds."
        case .executionFailed(let code, let stderr): return "Copilot exited with code \(code): \(stderr)"
        case .emptyResponse: return "Copilot returned an empty response."
        case .alreadyRunning: return "A Copilot command is already running."
        }
    }
}

public struct CopilotResponse: Equatable {
    public let text: String
    public let duration: TimeInterval
    public let isCodeBlock: Bool
    public let language: String?
    public let codeBlocks: [(language: String?, code: String)]

    public init(text: String, duration: TimeInterval, isCodeBlock: Bool, language: String?, codeBlocks: [(language: String?, code: String)]) {
        self.text = text
        self.duration = duration
        self.isCodeBlock = isCodeBlock
        self.language = language
        self.codeBlocks = codeBlocks
    }

    public static func == (lhs: CopilotResponse, rhs: CopilotResponse) -> Bool {
        lhs.text == rhs.text && lhs.duration == rhs.duration && lhs.isCodeBlock == rhs.isCodeBlock && lhs.language == rhs.language && lhs.codeBlocks.count == rhs.codeBlocks.count
    }
}

public final class CopilotBridge {
    private let runner: CopilotCLIRunning

    public init(runner: CopilotCLIRunning) {
        self.runner = runner
    }

    public func parseResponse(_ raw: String, duration: TimeInterval) -> CopilotResponse {
        let blocks = CodeBlockParser().extractCodeBlocks(from: raw)
        return CopilotResponse(text: raw, duration: duration, isCodeBlock: !blocks.isEmpty, language: blocks.first?.language, codeBlocks: blocks)
    }

    public func execute(prompt: String) async throws -> CopilotResponse {
        guard runner.isAvailable else { throw CopilotError.cliNotFound }
        let result = try runner.run(prompt: prompt, cliPath: "copilot", timeout: 30)
        guard result.exitCode == 0 else { throw CopilotError.executionFailed(code: result.exitCode, stderr: result.stderr) }
        guard !result.stdout.isEmpty else { throw CopilotError.emptyResponse }
        return parseResponse(result.stdout, duration: 0.1)
    }

    public func execute(prompt: String, completion: @escaping (Result<CopilotResponse, Error>) -> Void) {
        Task {
            do { completion(.success(try await execute(prompt: prompt))) }
            catch { completion(.failure(error)) }
        }
    }
}

public protocol CopilotExecuting {
    var isAvailable: Bool { get }
    func execute(prompt: String, completion: @escaping (Result<CopilotResponse, Error>) -> Void)
}

extension CopilotBridge: CopilotExecuting {
    public var isAvailable: Bool { runner.isAvailable }
}

public final class CodeAssistant {
    private let copilot: CopilotExecuting
    private let system: SystemCommandProviding

    public init(copilot: CopilotExecuting, system: SystemCommandProviding) {
        self.copilot = copilot
        self.system = system
    }

    public func process(_ message: String, completion: @escaping (AssistantResponse) -> Void) {
        let route = detectRoute(for: message)
        switch route {
        case .copilot:
            copilot.execute(prompt: message) { result in
                switch result {
                case .success(let response): completion(AssistantResponse(text: response.text, route: .copilot, duration: response.duration, codeBlocks: response.codeBlocks))
                case .failure(let error): completion(AssistantResponse(text: error.localizedDescription, route: .copilot, duration: 0, codeBlocks: []))
                }
            }
        case .system:
            completion(AssistantResponse(text: system.readClipboard(), route: .system, duration: 0, codeBlocks: []))
        case .general:
            completion(AssistantResponse(text: message, route: .general, duration: 0, codeBlocks: []))
        }
    }

    private func detectRoute(for message: String) -> AssistantRoute {
        switch RouteDetector().detectRoute(for: message) {
        case .copilot: return .copilot
        case .system: return .system
        case .general: return .general
        }
    }
}

public enum NoiseControlMode: String, Codable, Equatable {
    case unknown
    case off
    case noiseCancellation = "noise-cancellation"
    case transparency
    case adaptive
}

public struct AudioHardwareDevice: Equatable {
    public let id: Int
    public let name: String
    public let sampleRate: Double
    public let hasInput: Bool
    public let hasOutput: Bool

    public init(id: Int, name: String, sampleRate: Double, hasInput: Bool, hasOutput: Bool) {
        self.id = id
        self.name = name
        self.sampleRate = sampleRate
        self.hasInput = hasInput
        self.hasOutput = hasOutput
    }
}

public struct AirPodsState: Equatable {
    public let connected: Bool
    public let outputDevice: AudioHardwareDevice?
    public let inputDevice: AudioHardwareDevice?
    public let batteryPercent: Int?
    public let noiseControlMode: NoiseControlMode

    public init(connected: Bool, outputDevice: AudioHardwareDevice?, inputDevice: AudioHardwareDevice?, batteryPercent: Int?, noiseControlMode: NoiseControlMode) {
        self.connected = connected
        self.outputDevice = outputDevice
        self.inputDevice = inputDevice
        self.batteryPercent = batteryPercent
        self.noiseControlMode = noiseControlMode
    }

    public var isAirPodsMaxActive: Bool { connected && ((outputDevice?.name ?? "").contains("AirPods") || (inputDevice?.name ?? "").contains("AirPods")) }
}

public protocol AirPodsHardwareControlling {
    func currentState() -> AirPodsState
    func routeAllAudioToAirPods(preferredOutputName: String?) throws
    func routeAirPodsInput(preferredName: String?) throws
    func startMonitoring(changeHandler: @escaping () -> Void)
    func stopMonitoring()
}

public final class AirPodsManager {
    private let hardware: AirPodsHardwareControlling
    public private(set) var state: AirPodsState
    public var onStateChange: ((AirPodsState) -> Void)?
    public var onNotification: ((String) -> Void)?
    public var onDisconnected: (() -> Void)?
    public var onReconnected: (() -> Void)?

    public init(hardware: AirPodsHardwareControlling) {
        self.hardware = hardware
        self.state = hardware.currentState()
    }

    public func refreshState(reason: String = "manual") -> AirPodsState {
        let previous = state
        let next = hardware.currentState()
        state = next
        if previous != next { onStateChange?(next) }
        if previous.connected && !next.connected {
            onDisconnected?()
            onNotification?("AirPods Max disconnected. Listening is paused until they reconnect.")
        } else if !previous.connected && next.connected {
            try? hardware.routeAllAudioToAirPods(preferredOutputName: next.outputDevice?.name)
            onReconnected?()
            onNotification?("AirPods Max connected. Audio is routed and ready again.")
        } else if reason == "manual", next.connected, !next.isAirPodsMaxActive {
            onNotification?("AirPods are connected but not currently active for both input and output.")
        }
        return next
    }

    public func useAirPodsMicrophone() throws -> AirPodsState {
        try hardware.routeAirPodsInput(preferredName: state.outputDevice?.name)
        return refreshState(reason: "routed-input")
    }

    public func prefersNoiseCancellation() -> Bool {
        switch state.noiseControlMode {
        case .noiseCancellation, .adaptive: return true
        default: return false
        }
    }
}

public struct CartesiaVoiceOption: Identifiable, Hashable, Codable {
    public let voiceID: String
    public let name: String
    public let accentDescription: String
    public let fallbackVoiceName: String
    public let isDefault: Bool
    public var id: String { voiceID }

    public init(voiceID: String, name: String, accentDescription: String, fallbackVoiceName: String, isDefault: Bool) {
        self.voiceID = voiceID
        self.name = name
        self.accentDescription = accentDescription
        self.fallbackVoiceName = fallbackVoiceName
        self.isDefault = isDefault
    }

    public static let curated: [CartesiaVoiceOption] = [
        .init(voiceID: "voice-1", name: "Australian Narrator Lady", accentDescription: "Warm Australian female voice", fallbackVoiceName: "Karen", isDefault: true)
    ]
    public static let defaultOption = curated[0]
}

public protocol CartesiaAudioPlaying: AnyObject {
    var onStreamFinished: ((UUID) -> Void)? { get set }
    func prepareStream(id: UUID, sampleRate: Double, channels: AVAudioChannelCount)
    func appendPCMChunk(_ data: Data, for id: UUID) throws
    func finishStream(id: UUID)
    func cancelCurrentSpeech()
}

public final class AudioPlayer: CartesiaAudioPlaying {
    public var onStreamFinished: ((UUID) -> Void)?
    public init() {}
    public func prepareStream(id: UUID, sampleRate: Double, channels: AVAudioChannelCount) {}
    public func appendPCMChunk(_ data: Data, for id: UUID) throws {}
    public func finishStream(id: UUID) { onStreamFinished?(id) }
    public func cancelCurrentSpeech() {}
}

public protocol FallbackSpeechRunning {
    func speak(text: String, voice: String, rate: Int, completion: @escaping (Int32) -> Void) throws
    func cancel()
}

public final class CartesiaVoice: NSObject {
    @Published public private(set) var statusMessage = "Cartesia ready"
    @Published public private(set) var hasStoredAPIKey = false
    public var selectedVoiceID: String = CartesiaVoiceOption.defaultOption.voiceID

    private let audioOutput: CartesiaAudioPlaying
    private let keyManager: APIKeyManaging
    private let fallbackSpeaker: FallbackSpeechRunning
    private let sessionFactory: (URLSessionDataDelegate) -> URLSession
    private lazy var session: URLSession = sessionFactory(self)
    private var activeID: UUID?

    public init(audioPlayer: AnyObject? = nil, audioOutput: CartesiaAudioPlaying = AudioPlayer(), keyManager: APIKeyManaging, fallbackSpeaker: FallbackSpeechRunning, sessionFactory: @escaping (URLSessionDataDelegate) -> URLSession = { _ in URLSession.shared }) {
        self.audioOutput = audioOutput
        self.keyManager = keyManager
        self.fallbackSpeaker = fallbackSpeaker
        self.sessionFactory = sessionFactory
        super.init()
        self.audioOutput.onStreamFinished = { [weak self] _ in self?.activeID = nil }
        hasStoredAPIKey = keyManager.hasKey(for: "cartesia")
    }

    public func setAPIKey(_ apiKey: String) throws {
        try keyManager.setKey(apiKey, for: "cartesia")
        hasStoredAPIKey = true
    }

    public func removeAPIKey() {
        keyManager.removeKey(for: "cartesia")
        hasStoredAPIKey = false
    }

    public func enqueue(_ text: String, voiceID: String? = nil) {
        let id = UUID()
        activeID = id
        guard keyManager.hasKey(for: "cartesia") else {
            statusMessage = "Using macOS Fallback voice because Cartesia failed: missing Cartesia API key"
            try? fallbackSpeaker.speak(text: text, voice: "Karen", rate: 170) { _ in }
            return
        }
        audioOutput.prepareStream(id: id, sampleRate: 24_000, channels: 1)
        let task = session.dataTask(with: URLRequest(url: URL(string: "https://api.cartesia.ai/tts/bytes")!))
        task.resume()
    }
}

extension CartesiaVoice: URLSessionDataDelegate {
    public func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse, completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        completionHandler(.allow)
    }

    public func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard let activeID else { return }
        try? audioOutput.appendPCMChunk(data, for: activeID)
    }

    public func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard let activeID else { return }
        if error == nil {
            audioOutput.finishStream(id: activeID)
            statusMessage = "Finishing Cartesia audio playback"
        }
    }
}

@MainActor
public final class BrainChatCoordinator {
    public let store: ConversationStore
    public let voiceManager: VoiceManager
    public let speechManager: SpeechManager
    public let aiManager: AIManager
    public let codeAssistant: CodeAssistant
    public var configuration: AIServiceConfig
    public var autoSpeak = true
    public var continuousListening = false

    public init(store: ConversationStore, voiceManager: VoiceManager, speechManager: SpeechManager, aiManager: AIManager, codeAssistant: CodeAssistant, configuration: AIServiceConfig) {
        self.store = store
        self.voiceManager = voiceManager
        self.speechManager = speechManager
        self.aiManager = aiManager
        self.codeAssistant = codeAssistant
        self.configuration = configuration
        self.speechManager.onTranscriptFinalized = { [weak self] transcript in
            self?.sendUserMessage(transcript)
        }
    }

    public func sendUserMessage(_ text: String, completion: ((String) -> Void)? = nil) {
        store.addMessage(role: .user, content: text)
        store.isProcessing = true
        aiManager.send(message: text, history: store.messages, config: configuration) { response in
            Task { @MainActor in
                self.store.isProcessing = false
                self.store.addMessage(role: .assistant, content: response.text)
                if self.autoSpeak { self.voiceManager.speak(response.text) }
                if self.continuousListening { self.speechManager.startListening() }
                completion?(response.text)
            }
        }
    }

    public func runCopilotWorkflow(prompt: String, completion: @escaping (AssistantResponse) -> Void) {
        store.addMessage(role: .user, content: prompt)
        store.isProcessing = true
        codeAssistant.process(prompt) { response in
            Task { @MainActor in
                self.store.isProcessing = false
                self.store.addMessage(role: .assistant, content: response.text)
                completion(response)
            }
        }
    }
}
