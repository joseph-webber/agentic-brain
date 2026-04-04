import Foundation

protocol GroqStreaming: Sendable {
    func streamResponse(
        apiKey: String,
        model: String,
        messages: [AIChatMessage],
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String
}

struct GroqClient: GroqStreaming, Sendable {
    static let defaultEndpoint: URL = {
        guard let url = URL(string: "https://api.groq.com/openai/v1/chat/completions") else {
            fatalError("Invalid hardcoded URL - this is a programming error")
        }
        return url
    }()

    let session: URLSession
    let endpoint: URL

    init(
        session: URLSession = .shared,
        endpoint: URL = GroqClient.defaultEndpoint
    ) {
        self.session = session
        self.endpoint = endpoint
    }

    func stream(prompt: String, apiKey: String, model: String = "llama-3.1-8b-instant") -> AsyncThrowingStream<String, Error> {
        AsyncThrowingStream { continuation in
            Task {
                do {
                    _ = try await streamResponse(
                        apiKey: apiKey,
                        model: model,
                        messages: [AIChatMessage(role: .user, content: prompt)],
                        onDelta: { continuation.yield($0) }
                    )
                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    func streamResponse(
        apiKey: String,
        model: String,
        messages: [AIChatMessage],
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String {
        let trimmedKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedKey.isEmpty else {
            throw AIServiceError.missingAPIKey("Groq")
        }

        let resolvedModel = model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "llama-3.1-8b-instant"
            : model

        let request = try makeRequest(apiKey: trimmedKey, model: resolvedModel, messages: messages)
        let (bytes, response) = try await session.bytes(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw AIServiceError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            throw await Self.readHTTPError(from: bytes, statusCode: httpResponse.statusCode)
        }

        var fullText = ""
        for try await rawLine in bytes.lines {
            let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
            guard let payload = SSEStreamParser.parseDataLine(line) else { continue }
            
            if SSEStreamParser.isComplete(payload) { break }
            
            if let delta = SSEStreamParser.extractDelta(payload) {
                fullText += delta
                onDelta(delta)
            }
        }

        let responseText = fullText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !responseText.isEmpty else {
            throw AIServiceError.emptyResponse("Groq returned an empty response.")
        }
        return responseText
    }

    func makeRequest(
        apiKey: String,
        model: String,
        messages: [AIChatMessage]
    ) throws -> URLRequest {
        let body: [String: Any] = [
            "model": model,
            "stream": true,
            "messages": messages.map(\.openAIPayload),
        ]

        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.timeoutInterval = 30
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    private static func readHTTPError(from bytes: URLSession.AsyncBytes, statusCode: Int) async -> AIServiceError {
        let body = await SSEStreamParser.readHTTPErrorBody(from: bytes)
        return .httpStatus(statusCode, body.isEmpty ? "Groq request failed." : body)
    }
}
