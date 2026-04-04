import Foundation

actor CopilotVoiceRouter {
    static let shared = CopilotVoiceRouter()

    private let copilotCLIPath = {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/bin/copilot").path
    }()
    private let copilotWorkingDirectory = {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("brain")
    }()
    private let anthropicEndpoint = URL(string: "https://api.anthropic.com/v1/messages")!
    private let openAIEndpoint = URL(string: "https://api.openai.com/v1/chat/completions")!

    private let codingKeywords = [
        "code", "swift", "python", "javascript", "typescript", "java", "kotlin",
        "rust", "golang", "go ", "fix", "debug", "refactor", "function",
        "class", "method", "compile", "build", "test", "cli", "shell",
        "script", "api", "endpoint", "regex", "sql", "database", "websocket"
    ]

    func handle(_ request: VoiceBridgeRequest) async -> VoiceBridgeResponse {
        let startedAt = Date()
        let primaryRoute = resolveRoute(for: request)
        let attempts = routesToTry(primary: primaryRoute, request: request)
        let prompt = cleanedPrompt(from: request.message)
        var lastError: String?

        for route in attempts {
            do {
                let reply = try await execute(route: route, prompt: prompt, request: request)
                let duration = Date().timeIntervalSince(startedAt)
                return VoiceBridgeResponse(
                    id: request.id,
                    success: true,
                    route: route,
                    provider: providerName(for: route, request: request),
                    reply: reply,
                    mode: request.yolo ? "yolo" : "standard",
                    duration: duration,
                    error: lastError
                )
            } catch {
                lastError = error.localizedDescription
            }
        }

        let duration = Date().timeIntervalSince(startedAt)
        return VoiceBridgeResponse(
            id: request.id,
            success: false,
            route: .ollama,
            provider: providerName(for: .ollama, request: request),
            reply: "Sorry Joseph, the voice bridge could not get a response. \(lastError ?? "No backend was available.")",
            mode: request.yolo ? "yolo" : "standard",
            duration: duration,
            error: lastError
        )
    }

    private func resolveRoute(for request: VoiceBridgeRequest) -> VoiceBridgeRoute {
        let lower = request.message.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        if request.yolo || lower.hasPrefix("/yolo") {
            return .copilot
        }
        if lower.hasPrefix("/copilot") {
            return .copilot
        }
        if lower.hasPrefix("/claude") {
            return .claude
        }
        if lower.hasPrefix("/gpt") || lower.contains("chatgpt") || lower.contains("openai") {
            return .gpt
        }
        if lower.hasPrefix("/ollama") {
            return .ollama
        }
        if containsCodingIntent(lower) {
            return .copilot
        }

        switch request.preferredTarget {
        case .copilot:
            return .copilot
        case .claude:
            return .claude
        case .gpt:
            return .gpt
        case .ollama:
            return .ollama
        case .auto:
            return request.claudeAPIKey.isEmpty ? .ollama : .claude
        }
    }

    private func routesToTry(primary: VoiceBridgeRoute, request: VoiceBridgeRequest) -> [VoiceBridgeRoute] {
        var routes: [VoiceBridgeRoute] = [primary]
        switch primary {
        case .copilot:
            routes.append(.ollama)
        case .claude:
            if request.claudeAPIKey.isEmpty {
                routes = [.ollama]
            } else {
                routes.append(.ollama)
            }
        case .gpt:
            if request.openAIAPIKey.isEmpty {
                routes = [.ollama]
            } else {
                routes.append(.ollama)
            }
        case .ollama:
            break
        }
        return Array(NSOrderedSet(array: routes)) as? [VoiceBridgeRoute] ?? routes
    }

    private func containsCodingIntent(_ message: String) -> Bool {
        codingKeywords.contains { message.contains($0) }
    }

    private func cleanedPrompt(from raw: String) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        let commands = ["/yolo", "/copilot", "/claude", "/gpt", "/ollama"]
        for command in commands where trimmed.lowercased().hasPrefix(command) {
            let cleaned = String(trimmed.dropFirst(command.count)).trimmingCharacters(in: .whitespacesAndNewlines)
            return cleaned.isEmpty ? trimmed : cleaned
        }
        return trimmed
    }

    private func providerName(for route: VoiceBridgeRoute, request: VoiceBridgeRequest) -> String {
        switch route {
        case .copilot:
            return request.yolo ? "GitHub Copilot CLI /yolo" : "GitHub Copilot CLI"
        case .claude:
            return request.claudeModel
        case .gpt:
            return request.openAIModel
        case .ollama:
            return request.ollamaModel
        }
    }

    private func execute(route: VoiceBridgeRoute, prompt: String, request: VoiceBridgeRequest) async throws -> String {
        switch route {
        case .copilot:
            return try runCopilot(prompt: prompt, yolo: request.yolo)
        case .claude:
            return try await runClaude(prompt: prompt, request: request)
        case .gpt:
            return try await runOpenAI(prompt: prompt, request: request)
        case .ollama:
            return try await runOllama(prompt: prompt, request: request)
        }
    }

    private func runCopilot(prompt: String, yolo: Bool) throws -> String {
        guard FileManager.default.isExecutableFile(atPath: copilotCLIPath) else {
            throw NSError(domain: "VoiceBridge", code: 1, userInfo: [NSLocalizedDescriptionKey: "Copilot CLI not found at \(copilotCLIPath)."])
        }

        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        process.executableURL = URL(fileURLWithPath: copilotCLIPath)
        process.currentDirectoryURL = copilotWorkingDirectory
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        var arguments = ["-p", prompt, "--output-format", "text"]
        if yolo {
            arguments.append(contentsOf: ["--yolo", "--autopilot", "--max-autopilot-continues", "6"])
        } else {
            arguments.append("--allow-all")
        }
        process.arguments = arguments

        var environment = ProcessInfo.processInfo.environment
        let localBinPath = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent(".local/bin").path
        let extraPaths = ["/opt/homebrew/bin", "/usr/local/bin", localBinPath]
        let currentPath = environment["PATH"] ?? "/usr/bin:/bin"
        environment["PATH"] = (extraPaths + [currentPath]).joined(separator: ":")
        process.environment = environment

        try process.run()
        let finished = DispatchSemaphore(value: 0)
        var timedOut = false

        DispatchQueue.global().async {
            process.waitUntilExit()
            finished.signal()
        }

        if finished.wait(timeout: .now() + 120) == .timedOut {
            timedOut = true
            process.terminate()
        }

        let stdout = String(data: stdoutPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let stderr = String(data: stderrPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        if timedOut {
            throw NSError(domain: "VoiceBridge", code: 2, userInfo: [NSLocalizedDescriptionKey: "Copilot CLI timed out."])
        }

        guard process.terminationStatus == 0 else {
            throw NSError(domain: "VoiceBridge", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: stderr.isEmpty ? "Copilot CLI failed." : stderr])
        }
        guard !stdout.isEmpty else {
            throw NSError(domain: "VoiceBridge", code: 3, userInfo: [NSLocalizedDescriptionKey: "Copilot CLI returned an empty response."])
        }
        return stdout
    }

    private func runClaude(prompt: String, request: VoiceBridgeRequest) async throws -> String {
        guard !request.claudeAPIKey.isEmpty else {
            throw NSError(domain: "VoiceBridge", code: 4, userInfo: [NSLocalizedDescriptionKey: "Claude API key is missing."])
        }

        var urlRequest = URLRequest(url: anthropicEndpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue(request.claudeAPIKey, forHTTPHeaderField: "x-api-key")
        urlRequest.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")

        let body: [String: Any] = [
            "model": request.claudeModel,
            "max_tokens": 1024,
            "system": request.systemPrompt,
            "messages": anthropicMessages(from: request.history, fallbackPrompt: prompt)
        ]
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        try validateHTTP(response: response, data: data)
        guard
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            let content = json["content"] as? [[String: Any]]
        else {
            throw AIServiceError.invalidResponse
        }

        let text = content
            .compactMap { $0["text"] as? String }
            .joined()
            .trimmingCharacters(in: .whitespacesAndNewlines)

        guard !text.isEmpty else {
            throw AIServiceError.emptyResponse("Claude returned an empty response.")
        }
        return text
    }

    private func runOpenAI(prompt: String, request: VoiceBridgeRequest) async throws -> String {
        guard !request.openAIAPIKey.isEmpty else {
            throw NSError(domain: "VoiceBridge", code: 5, userInfo: [NSLocalizedDescriptionKey: "OpenAI API key is missing."])
        }

        var urlRequest = URLRequest(url: openAIEndpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")
        urlRequest.setValue("Bearer \(request.openAIAPIKey)", forHTTPHeaderField: "Authorization")

        let body: [String: Any] = [
            "model": request.openAIModel,
            "messages": openAIMessages(systemPrompt: request.systemPrompt, history: request.history, fallbackPrompt: prompt),
            "max_tokens": 1024
        ]
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        try validateHTTP(response: response, data: data)
        guard
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            let choices = json["choices"] as? [[String: Any]],
            let first = choices.first,
            let message = first["message"] as? [String: Any],
            let text = message["content"] as? String
        else {
            throw AIServiceError.invalidResponse
        }

        let cleaned = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else {
            throw AIServiceError.emptyResponse("GPT returned an empty response.")
        }
        return cleaned
    }

    private func runOllama(prompt: String, request: VoiceBridgeRequest) async throws -> String {
        guard let endpoint = URL(string: request.ollamaEndpoint) else {
            throw AIServiceError.invalidURL(request.ollamaEndpoint)
        }

        var urlRequest = URLRequest(url: endpoint)
        urlRequest.httpMethod = "POST"
        urlRequest.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body: [String: Any] = [
            "model": request.ollamaModel,
            "messages": openAIMessages(systemPrompt: request.systemPrompt, history: request.history, fallbackPrompt: prompt),
            "stream": false
        ]
        urlRequest.httpBody = try JSONSerialization.data(withJSONObject: body)

        let (data, response) = try await URLSession.shared.data(for: urlRequest)
        try validateHTTP(response: response, data: data)
        guard
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
            let message = json["message"] as? [String: Any],
            let text = message["content"] as? String
        else {
            throw AIServiceError.invalidResponse
        }

        let cleaned = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else {
            throw AIServiceError.emptyResponse("Ollama returned an empty response.")
        }
        return cleaned
    }

    private func anthropicMessages(from history: [AIChatMessage], fallbackPrompt: String) -> [[String: Any]] {
        let cleanedHistory = history.filter { $0.role != .system }
        let messages = cleanedHistory.isEmpty
            ? [AIChatMessage(role: .user, content: fallbackPrompt)]
            : cleanedHistory

        return messages.map { message in
            [
                "role": message.role.rawValue,
                "content": [["type": "text", "text": message.content]]
            ]
        }
    }

    private func openAIMessages(systemPrompt: String, history: [AIChatMessage], fallbackPrompt: String) -> [[String: String]] {
        var messages = [["role": "system", "content": systemPrompt]]
        let cleanedHistory = history.filter { $0.role != .system }
        let payload = cleanedHistory.isEmpty
            ? [AIChatMessage(role: .user, content: fallbackPrompt)]
            : cleanedHistory

        messages.append(contentsOf: payload.map { ["role": $0.role.rawValue, "content": $0.content] })
        return messages
    }

    private func validateHTTP(response: URLResponse, data: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw AIServiceError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? "Request failed."
            throw AIServiceError.httpStatus(httpResponse.statusCode, message)
        }
    }
}
