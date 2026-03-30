import Foundation

struct VoiceInputEvent: Codable, Sendable, Equatable {
    let text: String
    let timestamp: Date
    let source: String
    let targetLLM: String
    let yoloMode: Bool

    init(
        text: String,
        timestamp: Date = Date(),
        source: String = "brainchat",
        targetLLM: String,
        yoloMode: Bool
    ) {
        self.text = text
        self.timestamp = timestamp
        self.source = source
        self.targetLLM = targetLLM
        self.yoloMode = yoloMode
    }
}

struct VoiceResponseEvent: Codable, Sendable, Equatable {
    let text: String
    let provider: String
    let latencyMs: Int
    let success: Bool
}

struct RedpandaBridgeConfiguration: Sendable {
    let enabled: Bool
    let pandaproxyURL: String
    let responseTimeout: TimeInterval
}

enum RedpandaBridgeError: LocalizedError, Sendable {
    case invalidBaseURL(String)
    case unavailable(String)
    case consumerNotReady
    case requestTimedOut(TimeInterval)
    case responseFailed(provider: String, message: String)
    case cancelled

    var errorDescription: String? {
        switch self {
        case .invalidBaseURL(let value):
            return "Invalid Pandaproxy URL: \(value)"
        case .unavailable(let message):
            return "Redpanda bridge unavailable. \(message)"
        case .consumerNotReady:
            return "Pandaproxy consumer is not ready."
        case .requestTimedOut(let seconds):
            return "Timed out waiting for brain.voice.response after \(Int(seconds)) seconds."
        case .responseFailed(let provider, let message):
            return "\(provider) returned an unsuccessful event response. \(message)"
        case .cancelled:
            return "The Redpanda bridge request was cancelled."
        }
    }
}
