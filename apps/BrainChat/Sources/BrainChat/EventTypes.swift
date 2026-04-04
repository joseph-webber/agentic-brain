import Foundation

enum BrainTopic: String, Sendable {
    case voiceInput = "brain.voice.input"
    case voiceResponse = "brain.voice.response"
    case llmRequest = "brain.llm.request"
    case llmResponseFast = "brain.llm.response.fast"
    case llmResponseDeep = "brain.llm.response.deep"
    case llmResponseConsensus = "brain.llm.response.consensus"
}

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

enum LLMRequestPriority: String, Codable, Sendable, Equatable {
    case instant
    case normal
    case deep
}

enum LLMOrchestrationLayer: String, Codable, Sendable, Equatable, CaseIterable {
    case fast
    case deep
    case consensus

    init?(topic: String) {
        switch topic {
        case BrainTopic.llmResponseFast.rawValue:
            self = .fast
        case BrainTopic.llmResponseDeep.rawValue:
            self = .deep
        case BrainTopic.llmResponseConsensus.rawValue:
            self = .consensus
        default:
            return nil
        }
    }
}

struct LLMRequest: Codable, Sendable, Equatable, Identifiable {
    let requestID: String
    let prompt: String
    let timestamp: Date
    let source: String
    let priority: LLMRequestPriority
    let layers: [LLMOrchestrationLayer]

    var id: String { requestID }

    init(
        requestID: String = UUID().uuidString,
        prompt: String,
        timestamp: Date = Date(),
        source: String = "brainchat",
        priority: LLMRequestPriority,
        layers: [LLMOrchestrationLayer]
    ) {
        self.requestID = requestID
        self.prompt = prompt
        self.timestamp = timestamp
        self.source = source
        self.priority = priority
        self.layers = layers
    }

    private enum CodingKeys: String, CodingKey {
        case requestID
        case request_id
        case prompt
        case timestamp
        case source
        case priority
        case layers
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(requestID, forKey: .request_id)
        try container.encode(prompt, forKey: .prompt)
        try container.encode(timestamp, forKey: .timestamp)
        try container.encode(source, forKey: .source)
        try container.encode(priority, forKey: .priority)
        try container.encode(layers, forKey: .layers)
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        requestID = try Self.decodeString(from: container, keys: [.request_id, .requestID]) ?? UUID().uuidString
        prompt = try Self.decodeString(from: container, keys: [.prompt]) ?? ""
        timestamp = try Self.decodeDate(from: container, keys: [.timestamp]) ?? Date()
        source = try Self.decodeString(from: container, keys: [.source]) ?? "brainchat"
        priority = try Self.decodePriority(from: container, keys: [.priority]) ?? .normal
        layers = try Self.decodeLayers(from: container, keys: [.layers]) ?? [.fast]
    }

    private static func decodeString(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> String? {
        for key in keys {
            if let value = try container.decodeIfPresent(String.self, forKey: key) {
                return value
            }
        }
        return nil
    }

    private static func decodeDate(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> Date? {
        let decoder = PandaproxyClient.makeDecoder()

        for key in keys {
            if let value = try container.decodeIfPresent(Date.self, forKey: key) {
                return value
            }
            if let stringValue = try container.decodeIfPresent(String.self, forKey: key),
               let date = try? decoder.decode(Date.self, from: Data("\"\(stringValue)\"".utf8)) {
                return date
            }
        }
        return nil
    }

    private static func decodePriority(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> LLMRequestPriority? {
        for key in keys {
            if let value = try container.decodeIfPresent(LLMRequestPriority.self, forKey: key) {
                return value
            }
            if let stringValue = try container.decodeIfPresent(String.self, forKey: key),
               let value = LLMRequestPriority(rawValue: stringValue.lowercased()) {
                return value
            }
        }
        return nil
    }

    private static func decodeLayers(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> [LLMOrchestrationLayer]? {
        for key in keys {
            if let value = try container.decodeIfPresent([LLMOrchestrationLayer].self, forKey: key) {
                return value
            }
            if let stringValues = try container.decodeIfPresent([String].self, forKey: key) {
                let values = stringValues.compactMap { LLMOrchestrationLayer(rawValue: $0.lowercased()) }
                if !values.isEmpty {
                    return values
                }
            }
        }
        return nil
    }
}

struct LLMResponse: Codable, Sendable, Equatable, Identifiable {
    let requestID: String
    let text: String
    let provider: String
    let model: String?
    let latencyMs: Int?
    let success: Bool
    let timestamp: Date
    private(set) var layer: LLMOrchestrationLayer?
    private(set) var sourceTopic: String?

    var id: String { requestID.isEmpty ? "llm-response" : requestID }

    mutating func apply(topic: String) {
        sourceTopic = topic
        if layer == nil {
            layer = LLMOrchestrationLayer(topic: topic)
        }
    }

    private enum CodingKeys: String, CodingKey {
        case requestID
        case request_id
        case text
        case answer
        case response
        case content
        case provider
        case model
        case latencyMs
        case latency_ms
        case success
        case status
        case timestamp
        case completedAt = "completedAt"
        case completed_at
        case layer
        case topic
        case sourceTopic = "source_topic"
    }

    init(
        requestID: String = "",
        text: String,
        provider: String,
        model: String? = nil,
        latencyMs: Int? = nil,
        success: Bool = true,
        timestamp: Date = Date(),
        layer: LLMOrchestrationLayer? = nil,
        sourceTopic: String? = nil
    ) {
        self.requestID = requestID
        self.text = text
        self.provider = provider
        self.model = model
        self.latencyMs = latencyMs
        self.success = success
        self.timestamp = timestamp
        self.layer = layer
        self.sourceTopic = sourceTopic
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)

        requestID = try Self.decodeString(from: container, keys: [.request_id, .requestID]) ?? ""
        text = try Self.decodeString(from: container, keys: [.text, .answer, .response, .content]) ?? ""
        provider = try Self.decodeString(from: container, keys: [.provider]) ?? "unknown"
        model = try Self.decodeString(from: container, keys: [.model])
        latencyMs = try Self.decodeInt(from: container, keys: [.latencyMs, .latency_ms])
        timestamp = try Self.decodeDate(from: container, keys: [.timestamp, .completedAt, .completed_at]) ?? Date()
        sourceTopic = try Self.decodeString(from: container, keys: [.sourceTopic, .topic])
        layer = try Self.decodeLayer(from: container, keys: [.layer])
            ?? sourceTopic.flatMap(LLMOrchestrationLayer.init(topic:))

        if let value = try Self.decodeBool(from: container, keys: [.success]) {
            success = value
        } else if let status = try Self.decodeString(from: container, keys: [.status])?.lowercased() {
            success = !["failed", "error", "cancelled"].contains(status)
        } else {
            success = true
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(requestID, forKey: .requestID)
        try container.encode(text, forKey: .text)
        try container.encode(provider, forKey: .provider)
        try container.encodeIfPresent(model, forKey: .model)
        try container.encodeIfPresent(latencyMs, forKey: .latencyMs)
        try container.encode(success, forKey: .success)
        try container.encode(timestamp, forKey: .timestamp)
        try container.encodeIfPresent(layer, forKey: .layer)
        try container.encodeIfPresent(sourceTopic, forKey: .sourceTopic)
    }

    private static func decodeString(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> String? {
        for key in keys {
            if let value = try container.decodeIfPresent(String.self, forKey: key) {
                return value
            }
        }
        return nil
    }

    private static func decodeInt(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> Int? {
        for key in keys {
            if let value = try container.decodeIfPresent(Int.self, forKey: key) {
                return value
            }
            if let stringValue = try container.decodeIfPresent(String.self, forKey: key),
               let value = Int(stringValue) {
                return value
            }
        }
        return nil
    }

    private static func decodeBool(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> Bool? {
        for key in keys {
            if let value = try container.decodeIfPresent(Bool.self, forKey: key) {
                return value
            }
            if let stringValue = try container.decodeIfPresent(String.self, forKey: key) {
                switch stringValue.lowercased() {
                case "true", "ok", "success", "completed":
                    return true
                case "false", "failed", "error", "cancelled":
                    return false
                default:
                    break
                }
            }
        }
        return nil
    }

    private static func decodeDate(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> Date? {
        let decoder = PandaproxyClient.makeDecoder()

        for key in keys {
            if let value = try container.decodeIfPresent(Date.self, forKey: key) {
                return value
            }
            if let stringValue = try container.decodeIfPresent(String.self, forKey: key),
               let date = try? decoder.decode(Date.self, from: Data("\"\(stringValue)\"".utf8)) {
                return date
            }
        }
        return nil
    }

    private static func decodeLayer(
        from container: KeyedDecodingContainer<CodingKeys>,
        keys: [CodingKeys]
    ) throws -> LLMOrchestrationLayer? {
        for key in keys {
            if let value = try container.decodeIfPresent(LLMOrchestrationLayer.self, forKey: key) {
                return value
            }
            if let stringValue = try container.decodeIfPresent(String.self, forKey: key),
               let value = LLMOrchestrationLayer(rawValue: stringValue.lowercased()) {
                return value
            }
        }
        return nil
    }
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
