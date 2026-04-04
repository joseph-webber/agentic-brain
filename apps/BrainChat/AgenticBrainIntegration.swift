import Foundation

enum AgenticBrainConnectionMode: String, CaseIterable, Codable, Identifiable, Sendable {
    case airlocked
    case hybrid
    case cloud

    var id: String { rawValue }

    var accessibilityLabel: String {
        switch self {
        case .airlocked:
            return "Airlocked mode"
        case .hybrid:
            return "Hybrid mode"
        case .cloud:
            return "Cloud mode"
        }
    }

    var description: String {
        switch self {
        case .airlocked:
            return "Local-only inference. Remote APIs stay disabled."
        case .hybrid:
            return "Prefer the agentic-brain backend, then recover to local models."
        case .cloud:
            return "Prefer remote orchestration and cloud providers."
        }
    }
}

enum BrainChatBehaviorProfile: String, CaseIterable, Codable, Identifiable, Sendable {
    case beginner
    case developer
    case enterprise

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .beginner:
            return "Beginner"
        case .developer:
            return "Developer"
        case .enterprise:
            return "Enterprise"
        }
    }

    var systemPrompt: String {
        switch self {
        case .beginner:
            return "You are Karen, an accessibility-first assistant. Use plain language, announce steps clearly, and keep responses easy to follow with VoiceOver."
        case .developer:
            return "You are Karen, an Australian AI assistant helping Joseph code. Be direct, technical, and produce complete working solutions."
        case .enterprise:
            return "You are Karen, an enterprise AI assistant. Be concise, risk-aware, and explain operational impact clearly."
        }
    }

    var fallbackProviders: [LLMProvider] {
        switch self {
        case .beginner:
            return [.ollama, .gpt]
        case .developer:
            return [.claude, .gpt, .ollama]
        case .enterprise:
            return [.claude, .gpt, .ollama]
        }
    }

    var preferredSpeechEngine: SpeechEngine {
        switch self {
        case .beginner, .enterprise:
            return .appleDictation
        case .developer:
            return .whisperCpp
        }
    }

    var preferredVoiceOutput: VoiceOutputEngine {
        switch self {
        case .enterprise:
            return .cartesia
        case .beginner, .developer:
            return .macOS
        }
    }
}

struct AgenticBrainBackendConfiguration: Sendable, Equatable {
    let enabled: Bool
    let restBaseURL: String
    let webSocketURL: String
    let apiKey: String
    let bearerToken: String
    let sessionID: String
    let userID: String
    let mode: AgenticBrainConnectionMode
    let graphRAGEnabled: Bool
    let graphRAGScope: String

    static let disabled = AgenticBrainBackendConfiguration(
        enabled: false,
        restBaseURL: "",
        webSocketURL: "",
        apiKey: "",
        bearerToken: "",
        sessionID: "",
        userID: "",
        mode: .airlocked,
        graphRAGEnabled: false,
        graphRAGScope: "session"
    )

    var shouldUseRemoteInference: Bool {
        enabled && mode != .airlocked && restURL != nil
    }

    var restURL: URL? {
        Self.normalizedBaseURL(restBaseURL)
    }

    var chatURL: URL? {
        restURL?.appending(path: "chat")
    }

    var healthURL: URL? {
        restURL?.appending(path: "health")
    }

    var webSocketEndpoint: URL? {
        if let explicit = Self.normalizedWebSocketURL(webSocketURL) {
            return explicit
        }

        guard let restURL else {
            return nil
        }

        var components = URLComponents(url: restURL.appending(path: "ws/chat"), resolvingAgainstBaseURL: false)
        if components?.scheme == "http" {
            components?.scheme = "ws"
        } else if components?.scheme == "https" {
            components?.scheme = "wss"
        }
        return components?.url
    }

    var requestHeaders: [String: String] {
        var headers: [String: String] = [:]
        let trimmedAPIKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        let trimmedBearer = bearerToken.trimmingCharacters(in: .whitespacesAndNewlines)
        if !trimmedAPIKey.isEmpty {
            headers["X-API-Key"] = trimmedAPIKey
        }
        if !trimmedBearer.isEmpty {
            headers["Authorization"] = "Bearer \(trimmedBearer)"
        }
        return headers
    }

    private static func normalizedBaseURL(_ value: String) -> URL? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return URL(string: trimmed.hasSuffix("/") ? String(trimmed.dropLast()) : trimmed)
    }

    private static func normalizedWebSocketURL(_ value: String) -> URL? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return URL(string: trimmed)
    }
}

struct AgenticBrainHealthResponse: Codable, Sendable, Equatable {
    let status: String
    let version: String?
    let sessionsActive: Int?

    private enum CodingKeys: String, CodingKey {
        case status
        case version
        case sessionsActive = "sessions_active"
    }
}

struct AgenticBrainChatResponse: Codable, Sendable, Equatable {
    let response: String
    let sessionID: String
    let messageID: String

    private enum CodingKeys: String, CodingKey {
        case response
        case sessionID = "session_id"
        case messageID = "message_id"
    }
}

struct AgenticBrainSessionMessage: Codable, Sendable, Equatable {
    let role: String
    let content: String
}

struct AgenticBrainIssue: Identifiable, Sendable, Equatable {
    let id: UUID
    let component: String
    let message: String
    let timestamp: Date

    init(id: UUID = UUID(), component: String, message: String, timestamp: Date = Date()) {
        self.id = id
        self.component = component
        self.message = message
        self.timestamp = timestamp
    }
}

actor SelfHealingMonitor {
    private(set) var issues: [AgenticBrainIssue] = []

    func record(component: String, error: Error) {
        issues.append(AgenticBrainIssue(component: component, message: error.localizedDescription))
    }

    func recover<T: Sendable>(
        component: String,
        attempts: Int = 2,
        initialDelay: TimeInterval = 0.25,
        operation: @escaping @Sendable () async throws -> T
    ) async throws -> T {
        var lastError: Error?
        for attempt in 0..<max(attempts, 1) {
            do {
                return try await operation()
            } catch {
                lastError = error
                record(component: component, error: error)
                guard attempt < attempts - 1 else { break }
                let delay = initialDelay * pow(2, Double(attempt))
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
            }
        }
        throw lastError ?? AIServiceError.invalidResponse
    }
}

enum AgenticBrainBackendError: LocalizedError, Equatable {
    case unavailable(String)
    case invalidConfiguration(String)
    case server(String)
    case websocket(String)

    var errorDescription: String? {
        switch self {
        case .unavailable(let message):
            return "Agentic Brain backend unavailable. \(message)"
        case .invalidConfiguration(let message):
            return "Invalid Agentic Brain configuration. \(message)"
        case .server(let message):
            return message
        case .websocket(let message):
            return "WebSocket error. \(message)"
        }
    }
}

struct ADLConfigurationSummary: Sendable, Equatable {
    let profile: BrainChatBehaviorProfile
    let mode: AgenticBrainConnectionMode
    let fallbackProviders: [LLMProvider]
    let systemPrompt: String?
    let routingStrategy: String?
    let graphRAGEnabled: Bool
}

enum ADLConfigurationLoader {
    static func load(from url: URL) throws -> ADLConfigurationSummary {
        let contents = try String(contentsOf: url, encoding: .utf8)
        return parse(contents)
    }

    static func parse(_ contents: String) -> ADLConfigurationSummary {
        let lower = contents.lowercased()
        let persona = firstMatch(in: lower, pattern: #"persona\s+([a-z_]+)"#)
        let profile = mapProfile(persona: persona)
        let routingStrategy = firstMatch(in: lower, pattern: #"routing\s+([a-z-]+)"#)
        let fallbackProviders = parseFallbackProviders(from: lower)
        let systemPrompt = firstMatch(in: contents, pattern: #"systemPrompt\s+"([^"]+)""#)
        let graphRAGEnabled = lower.contains("vectorstore neo4j")
            || lower.contains("graphrag")
            || lower.contains("knowledge graph")

        let mode: AgenticBrainConnectionMode
        if lower.contains("airlocked") {
            mode = .airlocked
        } else if lower.contains("hybrid") {
            mode = .hybrid
        } else if lower.contains("cloud") {
            mode = .cloud
        } else if fallbackProviders == [.ollama] {
            mode = .airlocked
        } else if fallbackProviders.contains(.ollama) {
            mode = .hybrid
        } else {
            mode = .cloud
        }

        return ADLConfigurationSummary(
            profile: profile,
            mode: mode,
            fallbackProviders: fallbackProviders.isEmpty ? profile.fallbackProviders : fallbackProviders,
            systemPrompt: systemPrompt,
            routingStrategy: routingStrategy,
            graphRAGEnabled: graphRAGEnabled
        )
    }

    private static func mapProfile(persona: String?) -> BrainChatBehaviorProfile {
        switch persona {
        case "professional":
            return .enterprise
        case "technical", "developer":
            return .developer
        case "accessibility", "home", "beginner":
            return .beginner
        default:
            return .developer
        }
    }

    private static func parseFallbackProviders(from text: String) -> [LLMProvider] {
        guard let fallbackText = firstMatch(in: text, pattern: #"fallback\s*\[([^\]]+)\]"#) else {
            return []
        }

        let mappings: [String: LLMProvider] = [
            "ollama": .ollama,
            "openai": .gpt,
            "gpt": .gpt,
            "anthropic": .claude,
            "claude": .claude,
            "groq": .groq,
            "grok": .grok,
            "gemini": .gemini,
            "copilot": .copilot,
        ]

        var providers: [LLMProvider] = []
        for token in fallbackText.split(separator: ",") {
            let normalized = token
                .replacingOccurrences(of: "\"", with: "")
                .replacingOccurrences(of: "'", with: "")
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if let provider = mappings[normalized], !providers.contains(provider) {
                providers.append(provider)
            }
        }
        return providers
    }

    private static func firstMatch(in text: String, pattern: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else {
            return nil
        }
        let range = NSRange(text.startIndex..., in: text)
        guard
            let match = regex.firstMatch(in: text, range: range),
            match.numberOfRanges > 1,
            let captureRange = Range(match.range(at: 1), in: text)
        else {
            return nil
        }
        return String(text[captureRange])
    }
}

protocol AgenticBrainBackendServing: Sendable {
    func streamReply(
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async throws -> String
}

actor AgenticBrainBackendClient: AgenticBrainBackendServing {
    private let session: URLSession
    private let monitor: SelfHealingMonitor

    init(session: URLSession = .shared, monitor: SelfHealingMonitor = SelfHealingMonitor()) {
        self.session = session
        self.monitor = monitor
    }

    func health(configuration: AgenticBrainBackendConfiguration) async throws -> AgenticBrainHealthResponse {
        guard let url = configuration.healthURL else {
            throw AgenticBrainBackendError.invalidConfiguration("Missing backend health URL.")
        }

        let data = try await requestData(url: url, method: "GET", configuration: configuration, body: nil)
        return try JSONDecoder().decode(AgenticBrainHealthResponse.self, from: data)
    }

    func chat(
        prompt: String,
        configuration: AgenticBrainBackendConfiguration,
        provider: LLMProvider,
        model: String,
        metadata: [String: Any]
    ) async throws -> AgenticBrainChatResponse {
        guard let url = configuration.chatURL else {
            throw AgenticBrainBackendError.invalidConfiguration("Missing backend chat URL.")
        }

        let body = try payload(message: prompt, configuration: configuration, provider: provider, model: model, metadata: metadata)
        let data = try await requestData(url: url, method: "POST", configuration: configuration, body: body)
        return try JSONDecoder().decode(AgenticBrainChatResponse.self, from: data)
    }

    func streamReply(
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async throws -> String {
        let prompt = history.last(where: { $0.role == .user })?.content.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !prompt.isEmpty else {
            throw AgenticBrainBackendError.invalidConfiguration("Cannot send an empty prompt to the backend.")
        }

        let backend = configuration.backend
        let provider = configuration.provider
        nonisolated(unsafe) let metadata = makeMetadata(history: history, configuration: configuration)
        let model = modelName(for: configuration)

        do {
            return try await monitor.recover(component: "backend-websocket") {
                try await self.streamViaWebSocket(prompt: prompt, configuration: backend, provider: provider, model: model, metadata: metadata, onEvent: onEvent)
            }
        } catch {
            return try await monitor.recover(component: "backend-rest") {
                let response = try await self.chat(prompt: prompt, configuration: backend, provider: provider, model: model, metadata: metadata)
                onEvent(.delta(response.response))
                return response.response
            }
        }
    }

    private func streamViaWebSocket(
        prompt: String,
        configuration: AgenticBrainBackendConfiguration,
        provider: LLMProvider,
        model: String,
        metadata: [String: Any],
        onEvent: @escaping @Sendable (AIStreamEvent) -> Void
    ) async throws -> String {
        guard let url = configuration.webSocketEndpoint else {
            throw AgenticBrainBackendError.invalidConfiguration("Missing backend WebSocket URL.")
        }

        var request = URLRequest(url: url)
        for (name, value) in configuration.requestHeaders {
            request.setValue(value, forHTTPHeaderField: name)
        }

        let socket = session.webSocketTask(with: request)
        socket.resume()
        defer { socket.cancel(with: .goingAway, reason: nil) }

        let body = try payload(message: prompt, configuration: configuration, provider: provider, model: model, metadata: metadata)
        try await socket.send(.data(body))

        var response = ""
        while true {
            let message = try await socket.receive()
            let data: Data
            switch message {
            case .data(let payload):
                data = payload
            case .string(let payload):
                data = Data(payload.utf8)
            @unknown default:
                throw AgenticBrainBackendError.websocket("Unsupported WebSocket frame.")
            }

            let event = try JSONDecoder().decode(AgenticBrainWebSocketEvent.self, from: data)
            if let error = event.error ?? event.errorCode {
                throw AgenticBrainBackendError.server(error)
            }

            if !event.token.isEmpty {
                response += event.token
                onEvent(.delta(event.token))
            }

            if event.isEnd {
                return response
            }
        }
    }

    private func requestData(
        url: URL,
        method: String,
        configuration: AgenticBrainBackendConfiguration,
        body: Data?
    ) async throws -> Data {
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if body != nil {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }
        for (name, value) in configuration.requestHeaders {
            request.setValue(value, forHTTPHeaderField: name)
        }
        request.httpBody = body

        do {
            let (data, response) = try await session.data(for: request)
            guard let httpResponse = response as? HTTPURLResponse else {
                throw AgenticBrainBackendError.unavailable("Non-HTTP response.")
            }
            guard (200...299).contains(httpResponse.statusCode) else {
                let payload = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw AgenticBrainBackendError.server("HTTP \(httpResponse.statusCode): \(payload)")
            }
            return data
        } catch let error as AgenticBrainBackendError {
            throw error
        } catch {
            throw AgenticBrainBackendError.unavailable(error.localizedDescription)
        }
    }

    private func payload(
        message: String,
        configuration: AgenticBrainBackendConfiguration,
        provider: LLMProvider,
        model: String,
        metadata: [String: Any]
    ) throws -> Data {
        var json: [String: Any] = [
            "message": message,
            "provider": provider.shortName.lowercased(),
            "model": model,
            "metadata": metadata,
        ]
        if !configuration.sessionID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            json["session_id"] = configuration.sessionID
        }
        if !configuration.userID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            json["user_id"] = configuration.userID
        }
        return try JSONSerialization.data(withJSONObject: json)
    }

    private func makeMetadata(history: [ChatMessage], configuration: LLMRouterConfiguration) -> [String: Any] {
        var metadata: [String: Any] = [
            "brainchat_profile": configuration.profile.rawValue,
            "brainchat_mode": configuration.backend.mode.rawValue,
            "history_count": history.count,
        ]
        if configuration.backend.graphRAGEnabled {
            metadata["rag"] = [
                "enabled": true,
                "scope": configuration.backend.graphRAGScope,
                "operation": "chat",
            ]
        }
        return metadata
    }

    private func modelName(for configuration: LLMRouterConfiguration) -> String {
        switch configuration.provider {
        case .claude:
            return configuration.claudeModel
        case .gpt:
            return configuration.openAIModel
        case .groq:
            return configuration.groqModel
        case .grok:
            return configuration.grokModel
        case .gemini:
            return configuration.geminiModel
        case .copilot:
            return configuration.provider.defaultModel
        case .ollama:
            return configuration.ollamaModel
        }
    }
}

private struct AgenticBrainWebSocketEvent: Codable, Sendable {
    let token: String
    let isEnd: Bool
    let error: String?
    let errorCode: String?

    private enum CodingKeys: String, CodingKey {
        case token
        case isEnd = "is_end"
        case error
        case errorCode = "error_code"
    }
}
