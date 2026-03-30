import Foundation

enum CopilotBridgeError: Error, LocalizedError {
    case missingWhisperAPIKey
    case missingClaudeAPIKey
    case transcriptionFailed
    case responseFailed

    var errorDescription: String? {
        switch self {
        case .missingWhisperAPIKey:
            return "WHISPER_API_KEY is not configured."
        case .missingClaudeAPIKey:
            return "CLAUDE_API_KEY is not configured."
        case .transcriptionFailed:
            return "Transcription request failed."
        case .responseFailed:
            return "Claude response request failed."
        }
    }
}

final class CopilotBridge {
    private let environment = ProcessInfo.processInfo.environment

    private var whisperAPIURL: URL {
        URL(string: environment["WHISPER_API_URL"] ?? "https://api.openai.com/v1/audio/transcriptions")!
    }

    private var whisperAPIKey: String? {
        environment["WHISPER_API_KEY"] ?? environment["OPENAI_API_KEY"]
    }

    private var whisperModel: String {
        environment["WHISPER_MODEL"] ?? "whisper-1"
    }

    private var claudeAPIURL: URL {
        URL(string: environment["CLAUDE_API_URL"] ?? "https://api.anthropic.com/v1/messages")!
    }

    private var claudeAPIKey: String? {
        environment["CLAUDE_API_KEY"]
    }

    private var claudeModel: String {
        environment["CLAUDE_MODEL"] ?? "claude-3-5-sonnet-latest"
    }

    private var systemPrompt: String {
        environment["VOICE_DAEMON_SYSTEM_PROMPT"]
            ?? "You are a concise macOS voice daemon. Reply briefly, clearly, and in spoken language."
    }

    func transcribeAudio(fileURL: URL) async throws -> String {
        guard let apiKey = whisperAPIKey, !apiKey.isEmpty else {
            throw CopilotBridgeError.missingWhisperAPIKey
        }

        let boundary = "Boundary-\(UUID().uuidString)"
        var request = URLRequest(url: whisperAPIURL)
        request.httpMethod = "POST"
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")

        let body = try multipartBody(
            boundary: boundary,
            fileURL: fileURL,
            fields: [
                "model": whisperModel,
                "response_format": "json",
            ]
        )

        let (data, response) = try await URLSession.shared.upload(for: request, from: body)
        try validate(response: response, data: data)

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw CopilotBridgeError.transcriptionFailed
        }

        if let text = json["text"] as? String {
            return text.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        if let transcription = json["transcript"] as? String {
            return transcription.trimmingCharacters(in: .whitespacesAndNewlines)
        }

        throw CopilotBridgeError.transcriptionFailed
    }

    func generateResponse(for transcript: String, mode: String) async throws -> String {
        if mode == "copilot",
           let command = environment["COPILOT_BRIDGE_COMMAND"],
           !command.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            let bridged = try runShellBridge(command: command, prompt: transcript)
            if !bridged.isEmpty {
                return bridged
            }
        }

        return try await generateClaudeResponse(for: transcript)
    }

    private func generateClaudeResponse(for transcript: String) async throws -> String {
        guard let apiKey = claudeAPIKey, !apiKey.isEmpty else {
            throw CopilotBridgeError.missingClaudeAPIKey
        }

        let payload: [String: Any] = [
            "model": claudeModel,
            "max_tokens": 300,
            "system": systemPrompt,
            "messages": [
                [
                    "role": "user",
                    "content": transcript,
                ],
            ],
        ]

        let requestData = try JSONSerialization.data(withJSONObject: payload, options: [])
        var request = URLRequest(url: claudeAPIURL)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")

        let (data, response) = try await URLSession.shared.upload(for: request, from: requestData)
        try validate(response: response, data: data)

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let content = json["content"] as? [[String: Any]] else {
            throw CopilotBridgeError.responseFailed
        }

        let text = content
            .compactMap { item -> String? in
                guard let type = item["type"] as? String, type == "text" else { return nil }
                return item["text"] as? String
            }
            .joined(separator: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        guard !text.isEmpty else {
            throw CopilotBridgeError.responseFailed
        }

        return text
    }

    private func runShellBridge(command: String, prompt: String) throws -> String {
        let task = Process()
        let inputPipe = Pipe()
        let outputPipe = Pipe()

        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["-lc", command]
        task.standardInput = inputPipe
        task.standardOutput = outputPipe
        task.standardError = outputPipe

        try task.run()
        if let data = "\(prompt)\n".data(using: .utf8) {
            inputPipe.fileHandleForWriting.write(data)
        }
        inputPipe.fileHandleForWriting.closeFile()
        task.waitUntilExit()

        let data = outputPipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        guard task.terminationStatus == 0 else {
            throw CopilotBridgeError.responseFailed
        }

        return output
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse,
              (200...299).contains(http.statusCode) else {
            if let body = String(data: data, encoding: .utf8), !body.isEmpty {
                fputs("HTTP error body: \(body)\n", stderr)
            }
            throw CopilotBridgeError.responseFailed
        }
    }

    private func multipartBody(boundary: String, fileURL: URL, fields: [String: String]) throws -> Data {
        var data = Data()
        let lineBreak = "\r\n"

        for (name, value) in fields {
            data.append("--\(boundary)\(lineBreak)".data(using: .utf8)!)
            data.append("Content-Disposition: form-data; name=\"\(name)\"\(lineBreak)\(lineBreak)".data(using: .utf8)!)
            data.append("\(value)\(lineBreak)".data(using: .utf8)!)
        }

        let fileData = try Data(contentsOf: fileURL)
        data.append("--\(boundary)\(lineBreak)".data(using: .utf8)!)
        data.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileURL.lastPathComponent)\"\(lineBreak)".data(using: .utf8)!)
        data.append("Content-Type: audio/wav\(lineBreak)\(lineBreak)".data(using: .utf8)!)
        data.append(fileData)
        data.append(lineBreak.data(using: .utf8)!)
        data.append("--\(boundary)--\(lineBreak)".data(using: .utf8)!)

        return data
    }
}
