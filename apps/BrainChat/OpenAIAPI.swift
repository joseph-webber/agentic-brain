import Foundation

protocol OpenAIStreaming: Sendable {
    func streamResponse(apiKey: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String
}

struct OpenAIAPI: OpenAIStreaming, Sendable {
    let session: URLSession
    let endpoint: URL

    init(session: URLSession = .shared, endpoint: URL = URL(string: "https://api.openai.com/v1/chat/completions")!) {
        self.session = session
        self.endpoint = endpoint
    }

    func streamResponse(apiKey: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        let trimmedKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedKey.isEmpty else { throw AIServiceError.missingAPIKey("OpenAI") }
        let request = try makeRequest(apiKey: trimmedKey, model: model, messages: messages)
        let (bytes, response) = try await session.bytes(for: request)
        guard let http = response as? HTTPURLResponse else { throw AIServiceError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw await Self.readHTTPError(from: bytes, statusCode: http.statusCode) }
        var full = ""
        for try await rawLine in bytes.lines {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            guard line.hasPrefix("data:") else { continue }
            let payload = line.dropFirst(5).trimmingCharacters(in: .whitespacesAndNewlines)
            if payload == "[DONE]" { break }
            guard let data = payload.data(using: .utf8), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let choices = object["choices"] as? [[String: Any]] else { continue }
            for choice in choices {
                if let delta = choice["delta"] as? [String: Any], let text = delta["content"] as? String, !text.isEmpty { full += text; onDelta(text) }
            }
        }
        let text = full.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw AIServiceError.emptyResponse("OpenAI returned an empty response.") }
        return text
    }

    func makeRequest(apiKey: String, model: String, messages: [AIChatMessage]) throws -> URLRequest {
        let body: [String: Any] = ["model": model, "stream": true, "messages": messages.map(\.openAIPayload)]
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 120
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    private static func readHTTPError(from bytes: URLSession.AsyncBytes, statusCode: Int) async -> AIServiceError {
        var body = ""
        do {
            for try await line in bytes.lines {
                body += line
                if body.count > 4000 { break }
            }
        } catch {
            return .httpStatus(statusCode, "OpenAI request failed.")
        }
        if let data = body.data(using: .utf8), let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let error = json["error"] as? [String: Any], let message = error["message"] as? String { return .httpStatus(statusCode, message) }
            if let message = json["message"] as? String { return .httpStatus(statusCode, message) }
        }
        return .httpStatus(statusCode, body.trimmingCharacters(in: .whitespacesAndNewlines))
    }
}
