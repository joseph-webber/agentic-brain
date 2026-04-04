import Foundation

/// Shared SSE (Server-Sent Events) stream parser
/// Used by OpenAI, Groq, Grok and other streaming APIs
struct SSEStreamParser {
    
    /// Parse a single SSE line and extract its data payload
    static func parseDataLine(_ line: String) -> String? {
        guard line.hasPrefix("data:") else { return nil }
        return line.dropFirst(5).trimmingCharacters(in: .whitespacesAndNewlines)
    }
    
    /// Check if stream is complete
    static func isComplete(_ payload: String) -> Bool {
        payload == "[DONE]"
    }
    
    /// Extract content delta from OpenAI-format JSON
    static func extractDelta(_ payload: String) -> String? {
        guard let data = payload.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let choices = object["choices"] as? [[String: Any]] else {
            return nil
        }
        
        for choice in choices {
            if let delta = choice["delta"] as? [String: Any],
               let text = delta["content"] as? String,
               !text.isEmpty {
                return text
            }
        }
        return nil
    }
    
    /// Read HTTP error response body
    static func readHTTPErrorBody(from bytes: URLSession.AsyncBytes) async -> String {
        var body = ""
        do {
            for try await line in bytes.lines {
                body += line
                if body.count > 4000 { break }
            }
        } catch {
            return ""
        }
        
        if let data = body.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let error = json["error"] as? [String: Any],
               let message = error["message"] as? String {
                return message
            }
            if let message = json["message"] as? String {
                return message
            }
        }
        
        return body.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
