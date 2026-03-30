import Foundation

protocol OllamaStreaming: Sendable {
    func streamResponse(endpoint: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String
}

struct OllamaAPI: OllamaStreaming, Sendable {
    let session: URLSession
    let timeoutInterval: TimeInterval

    init(session: URLSession = .shared, timeoutInterval: TimeInterval = 120) {
        self.session = session
        self.timeoutInterval = timeoutInterval
    }

    func streamResponse(endpoint: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String {
        guard let url = URL(string: endpoint.trimmingCharacters(in: .whitespacesAndNewlines)) else { throw AIServiceError.invalidURL(endpoint) }
        let resolvedModel = model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "llama3.2:3b" : model
        let request = try makeRequest(url: url, model: resolvedModel, messages: messages)
        let (bytes, response) = try await session.bytes(for: request)
        guard let http = response as? HTTPURLResponse else { throw AIServiceError.invalidResponse }
        guard (200..<300).contains(http.statusCode) else { throw await Self.readHTTPError(from: bytes, statusCode: http.statusCode) }
        var full = ""
        for try await rawLine in bytes.lines {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !line.isEmpty else { continue }
            guard let data = line.data(using: .utf8), let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { continue }
            if let error = object["error"] as? String, !error.isEmpty { throw AIServiceError.httpStatus(http.statusCode, error) }
            if let message = object["message"] as? [String: Any], let text = message["content"] as? String, !text.isEmpty { full += text; onDelta(text) }
            else if let responseText = object["response"] as? String, !responseText.isEmpty { full += responseText; onDelta(responseText) }
            if let done = object["done"] as? Bool, done { break }
        }
        let text = full.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { throw AIServiceError.emptyResponse("Ollama returned an empty response. Make sure Ollama is running and model \(resolvedModel) is installed.") }
        return text
    }

    func makeRequest(url: URL, model: String, messages: [AIChatMessage]) throws -> URLRequest {
        let body: [String: Any] = ["model": model, "stream": true, "messages": messages.map(\.openAIPayload)]
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = timeoutInterval
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    private static func readHTTPError(from bytes: URLSession.AsyncBytes, statusCode: Int) async -> AIServiceError {
        var body = ""
        do {
            for try await line in bytes.lines { body += line; if body.count > 4000 { break } }
        } catch {
            return .httpStatus(statusCode, "Ollama request failed.")
        }
        if let data = body.data(using: .utf8), let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let error = json["error"] as? String {
            return .httpStatus(statusCode, error)
        }
        return .httpStatus(statusCode, body.trimmingCharacters(in: .whitespacesAndNewlines))
    }
}
