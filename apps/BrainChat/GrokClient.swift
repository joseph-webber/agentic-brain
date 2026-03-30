import Foundation

protocol GrokStreaming: Sendable {
    func streamResponse(
        apiKey: String,
        model: String,
        messages: [AIChatMessage],
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String
}

struct GrokClient: GrokStreaming, Sendable {
    let session: URLSession
    let endpoint: URL

    init(
        session: URLSession = .shared,
        endpoint: URL = URL(string: "https://api.x.ai/v1/chat/completions")!
    ) {
        self.session = session
        self.endpoint = endpoint
    }

    func streamResponse(
        apiKey: String,
        model: String,
        messages: [AIChatMessage],
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String {
        let trimmedKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedKey.isEmpty else {
            throw AIServiceError.missingAPIKey("Grok")
        }

        let resolvedModel = model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "grok-3-latest"
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
            guard line.hasPrefix("data:") else { continue }

            let payload = line.dropFirst(5).trimmingCharacters(in: .whitespacesAndNewlines)
            if payload == "[DONE]" { break }
            guard let data = payload.data(using: .utf8),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let choices = object["choices"] as? [[String: Any]] else {
                continue
            }

            for choice in choices {
                guard let delta = choice["delta"] as? [String: Any],
                      let text = delta["content"] as? String,
                      !text.isEmpty else {
                    continue
                }
                fullText += text
                onDelta(text)
            }
        }

        let responseText = fullText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !responseText.isEmpty else {
            throw AIServiceError.emptyResponse("Grok returned an empty response.")
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
            return .httpStatus(statusCode, "xAI Grok request failed.")
        }

        if let data = body.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let error = json["error"] as? [String: Any],
               let message = error["message"] as? String {
                return .httpStatus(statusCode, message)
            }
            if let message = json["message"] as? String {
                return .httpStatus(statusCode, message)
            }
        }

        let cleaned = body.trimmingCharacters(in: .whitespacesAndNewlines)
        return .httpStatus(statusCode, cleaned.isEmpty ? "xAI Grok request failed." : cleaned)
    }
}
