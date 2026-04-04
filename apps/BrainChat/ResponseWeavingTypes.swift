import Foundation

// MARK: - Response Layer

/// One layer of a woven multi-LLM response.
/// Layer 1 is the instant answer from the fast LLM; layers 2+ are deeper enhancements.
struct ResponseLayer: Identifiable, Equatable {
    let id: UUID
    /// 1 = instant (fast LLM), 2+ = deeper enhancements
    let layerNumber: Int
    let provider: String
    var content: String
    let timestamp: Date

    init(id: UUID = UUID(), layerNumber: Int, provider: String, content: String = "") {
        self.id = id
        self.layerNumber = layerNumber
        self.provider = provider
        self.content = content
        self.timestamp = Date()
    }

    var isInstant: Bool { layerNumber == 1 }
    var isDeeper: Bool { layerNumber > 1 }

    /// Conversational prefix shown before a deeper layer so it reads naturally.
    var weavingPrefix: String {
        guard layerNumber > 1 else { return "" }
        let prefixes = [
            "Let me expand on that…",
            "Actually, I should clarify…",
            "One thing worth adding…",
            "To go a bit deeper…"
        ]
        return prefixes[(layerNumber - 2) % prefixes.count]
    }

    var accessibilityLabel: String {
        isInstant
            ? "Quick response from \(provider)"
            : "Enhanced response from \(provider): \(weavingPrefix)"
    }
}

/// Alias used by the weaving system for readability.
typealias WeavingLayer = ResponseLayer

// MARK: - Weaving Phase

/// Tracks where the response weaving lifecycle is for a given message.
enum WeavingPhase: Equatable {
    /// Ordinary single-layer message — no weaving.
    case idle
    /// Layer 1 is actively streaming in from the fast LLM.
    case streaming
    /// Layer 1 complete; waiting for the deep LLM to respond.
    case thinking
    /// Deep layer is streaming / being woven in.
    case weaving
    /// All layers delivered; final state.
    case complete

    var isActive: Bool { self != .idle && self != .complete }

    var accessibilityAnnouncement: String? {
        switch self {
        case .thinking: return "Thinking deeper"
        case .weaving:  return "Enhanced response available"
        case .complete: return "Response complete"
        default: return nil
        }
    }
}
