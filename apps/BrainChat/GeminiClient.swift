import Foundation

protocol GeminiStreaming: Sendable {
    func streamResponse(
        apiKey: String,
        model: String,
        systemPrompt: String,
        messages: [AIChatMessage],
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String
}

struct GeminiClient: GeminiStreaming, Sendable {
    let session: URLSession
    let baseURL: String

    init(
        session: URLSession = .shared,
        baseURL: String = "https://generativelanguage.googleapis.com/v1beta/models"
    ) {
        self.session = session
        self.baseURL = baseURL
    }

    func streamResponse(
        apiKey: String,
        model: String,
        systemPrompt: String,
        messages: [AIChatMessage],
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String {
        let trimmedKey = apiKey.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedKey.isEmpty else {
            throw AIServiceError.missingAPIKey("Gemini")
        }

        let resolvedModel = model.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "gemini-2.5-flash"
            : model

        let urlString = "\(baseURL)/\(resolvedModel):streamGenerateContent?alt=sse&key=\(trimmedKey)"
        guard let url = URL(string: urlString) else {
            throw AIServiceError.invalidURL(urlString)
        }

        let request = try makeRequest(url: url, systemPrompt: systemPrompt, messages: messages)
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
            guard !payload.isEmpty, payload != "[DONE]" else { continue }
            guard let data = payload.data(using: .utf8),
                  let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                continue
            }

            if let error = object["error"] as? [String: Any],
               let message = error["message"] as? String {
                throw AIServiceError.httpStatus(httpResponse.statusCode, message)
            }

            if let candidates = object["candidates"] as? [[String: Any]] {
                for candidate in candidates {
                    guard let content = candidate["content"] as? [String: Any],
                          let parts = content["parts"] as? [[String: Any]] else {
                        continue
                    }
                    for part in parts {
                        if let text = part["text"] as? String, !text.isEmpty {
                            fullText += text
                            onDelta(text)
                        }
                    }
                }
            }
        }

        let responseText = fullText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !responseText.isEmpty else {
            throw AIServiceError.emptyResponse("Gemini returned an empty response.")
        }
        return responseText
    }

    func makeRequest(url: URL, systemPrompt: String, messages: [AIChatMessage]) throws -> URLRequest {
        let contents = buildContents(from: messages)
        var body: [String: Any] = ["contents": contents]
        if !systemPrompt.isEmpty {
            body["systemInstruction"] = [
                "parts": [["text": systemPrompt]]
            ]
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 120
        request.httpBody = try JSONSerialization.data(withJSONObject: body)
        return request
    }

    func buildContents(from messages: [AIChatMessage]) -> [[String: Any]] {
        messages
            .filter { $0.role != .system }
            .map { message in
                let role: String = message.role == .user ? "user" : "model"
                return [
                    "role": role,
                    "parts": [["text": message.content]]
                ] as [String: Any]
            }
    }

    private static func readHTTPError(from bytes: URLSession.AsyncBytes, statusCode: Int) async -> AIServiceError {
        var body = ""
        do {
            for try await line in bytes.lines {
                body += line
                if body.count > 4000 { break }
            }
        } catch {
            return .httpStatus(statusCode, "Google Gemini request failed.")
        }

        if let data = body.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let error = json["error"] as? [String: Any],
               let message = error["message"] as? String {
                return .httpStatus(statusCode, message)
            }
        }

        let cleaned = body.trimmingCharacters(in: .whitespacesAndNewlines)
        return .httpStatus(statusCode, cleaned.isEmpty ? "Google Gemini request failed." : cleaned)
    }
}
