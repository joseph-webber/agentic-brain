import Foundation

protocol ClaudeStreaming: Sendable {
    func streamResponse(apiKey: String, model: String, systemPrompt: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String
}

struct ClaudeAPI: ClaudeStreaming, Sendable {
    let session: URLSession
    let endpoint: URL

    private static let defaultEndpoint: URL = {
        guard let url = URL(string: "https://api.anthropic.com/v1/messages") else {
            fatalError("Invalid hardcoded URL - this is a programming error")
        }
        return url
    }()

    init(session: URLSession = .shared, endpoint: URL = ClaudeAPI.defaultEndpoint) {
        self.session = session
        self.endpoint = endpoint
    }

    func streamResponse(apiKey: String, model: String, systemPrompt: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let trimmedKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedKey.isEmpty else { throw AIServiceError.missingAPIKey("Claude") }
        let request = try makeRequest(apiKey: trimmedKey, model: model, systemPrompt: systemPrompt, messages: messages)
        let (bytes, response) = try await session.bytes(for: request)
        guard let http = response as? HTTPURLResponse else { throw AIServiceError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw await Self.readHTTPError(from: bytes, statusCode: http.statusCode) }
        var full = ""
        for try await rawLine in bytes.lines {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            guard line.hasPrefix("data:") else { continue }
            let payload = line.dropFirst(5).trimmingCharacters(in: .whitespacesAndNewlines)
            guard payload != "[DONE]", !payload.isEmpty else { continue }
            guard let data = payload.data(using: .utf8), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
            if let type = object["type"] as? String, type == "error" {
                let message = (object["error"] as? [String: Any])?["message"] as? String ?? "Claude streaming failed."
                throw AIServiceError.httpStatus(http.statusCode, message)
            }
            if let delta = Self.extractDelta(from: object), !delta.isEmpty { full += delta; onDelta(delta) }
        }
        let text = full.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw AIServiceError.emptyResponse("Claude returned an empty response.") }
        return text
    }

    func makeRequest(apiKey: String, model: String, systemPrompt: String, messages: [AIChatMessage]) throws -> URLRequest {
        let body: [String: Any] = [
            "model": model,
            "max_tokens": 2048,
            "system": systemPrompt,
            "stream": true,
            "messages": messages.filter { $0.role != .system }.map(\.anthropicPayload),
        ]
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(apiKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        request.timeoutInterval = 120
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    static func extractDelta(from object: [String: Any]) -> String? {
        if let delta = object["delta"] as? [String: Any], let text = delta["text"] as? String { return text }
        if let block = object["content_block"] as? [String: Any], let text = block["text"] as? String { return text }
        return nil
    }

    private static func readHTTPError(from bytes: URLSession.AsyncBytes, statusCode: Int) async -> AIServiceError {
        var body = ""
        do {
            for try await line in bytes.lines {
                body += line
                if body.count > 4000 { break }
            }
        } catch {
            return .httpStatus(statusCode, "Anthropic request failed.")
        }
        if let data = body.data(using: .utf8), let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let error = json["error"] as? [String: Any], let message = error["message"] as? String { return .httpStatus(statusCode, message) }
            if let message = json["message"] as? String { return .httpStatus(statusCode, message) }
        }
        return .httpStatus(statusCode, body.trimmingCharacters(in: .whitespacesAndNewlines))
    }
}
