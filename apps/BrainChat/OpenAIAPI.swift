import Foundation

protocol OpenAIStreaming: Sendable {
    func streamResponse(apiKey: String, model: String, messages: [AIChatMessage], onDelta: @escaping @Sendable (String) -> Void) async throws -> String
}

struct OpenAIAPI: OpenAIStreaming, Sendable {
    let session: URLSession
    let endpoint: URL

    private static let defaultEndpoint: URL = {
        guard let url = URL(string: "https://api.openai.com/v1/chat/completions") else {
            fatalError("Invalid hardcoded URL - this is a programming error")
        }
        return url
    }()

    init(session: URLSession = .shared, endpoint: URL = OpenAIAPI.defaultEndpoint) {
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
            guard let payload = SSEStreamParser.parseDataLine(line) else { continue }
            
            if SSEStreamParser.isComplete(payload) { break }
            
            if let delta = SSEStreamParser.extractDelta(payload) {
                full += delta
                onDelta(delta)
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
        let body = await SSEStreamParser.readHTTPErrorBody(from: bytes)
        return .httpStatus(statusCode, body.isEmpty ? "OpenAI request failed." : body)
    }
}
