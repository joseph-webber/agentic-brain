import SwiftUI

// =============================================================================
// LayeredResponseView — Visual display of multi-layer LLM responses
//
// Shows instant responses immediately with a "thinking deeper" indicator,
// then smoothly weaves in enhanced responses from deeper layers.
// Fully accessible with VoiceOver support.
// =============================================================================

struct LayeredResponseView: View {
    let instantText: String
    let deepText: String?
    let isThinkingDeeper: Bool
    let layerResults: [LayerResult]

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            // Instant response (always visible first)
            if !instantText.isEmpty {
                HStack(alignment: .top, spacing: 6) {
                    Image(systemName: LayerTier.instant.icon)
                        .foregroundColor(.orange)
                        .font(.caption)
                        .accessibilityHidden(true)
                    Text(instantText)
                        .textSelection(.enabled)
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Quick response")
                .accessibilityValue(instantText)
                .accessibilityHint(isThinkingDeeper ? "An enhanced response is still on the way" : "This is the current response")
            }

            // Thinking deeper indicator
            if isThinkingDeeper && deepText == nil {
                ThinkingDeeperIndicator()
            }

            // Deep response (weaves in when ready)
            if let deep = deepText, !deep.isEmpty {
                Divider()
                    .padding(.vertical, 4)

                HStack(alignment: .top, spacing: 6) {
                    Image(systemName: LayerTier.deep.icon)
                        .foregroundColor(.purple)
                        .font(.caption)
                        .accessibilityHidden(true)
                    Text(deep)
                        .textSelection(.enabled)
                }
                .transition(.opacity.combined(with: .move(edge: .bottom)))
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Enhanced response")
                .accessibilityValue(deep)
                .accessibilityHint("This adds more detail to the quick response")
            }

            // Layer performance badges
            if !layerResults.isEmpty {
                LayerPerformanceBadges(results: layerResults)
            }
        }
    }
}

// MARK: - Thinking Deeper Indicator

struct ThinkingDeeperIndicator: View {
    @State private var dotCount = 0
    private let timer = Timer.publish(every: 0.4, on: .main, in: .common).autoconnect()

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "brain.head.profile")
                .foregroundColor(.purple.opacity(0.7))
                .font(.caption)
                .symbolEffect(.pulse.wholeSymbol, options: .repeating)
                .accessibilityHidden(true)

            Text("Thinking deeper" + String(repeating: ".", count: dotCount))
                .font(.caption)
                .foregroundColor(.secondary)
                .animation(.easeInOut(duration: 0.2), value: dotCount)
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Thinking deeper, please wait")
        .accessibilityHint("Brain Chat is preparing a more detailed response")
        .accessibilityAddTraits(.updatesFrequently)
        .onReceive(timer) { _ in
            dotCount = (dotCount + 1) % 4
        }
    }
}

// MARK: - Layer Performance Badges

struct LayerPerformanceBadges: View {
    let results: [LayerResult]

    var body: some View {
        HStack(spacing: 6) {
            ForEach(results.sorted(by: { $0.layer < $1.layer }), id: \.source) { result in
                LayerBadge(result: result)
            }
        }
        .padding(.top, 4)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Response layer performance")
        .accessibilityValue(results.sorted(by: { $0.layer < $1.layer }).map { "\($0.source) \($0.latencyMs) milliseconds" }.joined(separator: ", "))
    }
}

struct LayerBadge: View {
    let result: LayerResult

    var body: some View {
        HStack(spacing: 3) {
            Image(systemName: result.layer.icon)
                .font(.system(size: 9))
                .accessibilityHidden(true)
            Text("\(result.source) \(result.latencyMs)ms")
                .font(.system(size: 10, weight: .medium, design: .monospaced))
        }
        .padding(.horizontal, 6)
        .padding(.vertical, 2)
        .background(badgeColor.opacity(0.15))
        .foregroundColor(badgeColor)
        .clipShape(Capsule())
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(result.source), \(result.layer.description) layer, \(result.latencyMs) milliseconds, \(result.succeeded ? "succeeded" : "failed")")
    }

    private var badgeColor: Color {
        guard result.succeeded else { return .red }
        switch result.layer {
        case .instant:   return .orange
        case .fastLocal: return .green
        case .deep:      return .purple
        case .consensus: return .blue
        }
    }
}

// MARK: - Layered Conversation Bubble

/// A complete conversation bubble that handles layered responses.
/// Replaces the simple Text() in ConversationView for assistant messages.
struct LayeredMessageBubble: View {
    let message: ChatMessage
    let layeredState: LayeredMessageState?

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(message.role.rawValue)
                .font(.caption)
                .foregroundColor(.secondary)

            if let state = layeredState {
                LayeredResponseView(
                    instantText: state.instantText,
                    deepText: state.deepText,
                    isThinkingDeeper: state.isThinkingDeeper,
                    layerResults: state.results
                )
            } else {
                Text(message.content.isEmpty ? "…" : message.content)
                    .textSelection(.enabled)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
        .background(backgroundColor)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(message.accessibilityDescription)
        .accessibilityValue(layeredAccessibilityValue)
        .accessibilityHint("VoiceOver will announce when deeper layers arrive")
    }

    private var backgroundColor: Color {
        switch message.role {
        case .user:
            return Color.accentColor.opacity(0.15)
        case .copilot:
            return Color.blue.opacity(0.12)
        case .assistant, .system:
            return Color.secondary.opacity(0.08)
        }
    }

    private var layeredAccessibilityValue: String {
        guard let layeredState else {
            return "Single response"
        }
        if let deepText = layeredState.deepText, !deepText.isEmpty {
            return "Enhanced response ready"
        }
        if layeredState.isThinkingDeeper {
            return "Thinking deeper"
        }
        return "Quick response ready"
    }
}

// MARK: - Layered Message State

/// Tracks the state of a layered response for a specific message.
@MainActor
final class LayeredMessageState: ObservableObject, Identifiable {
    let id: UUID
    @Published var instantText: String = ""
    @Published var localText: String = ""
    @Published var deepText: String? = nil
    @Published var isThinkingDeeper: Bool = false
    @Published var results: [LayerResult] = []

    init(id: UUID) {
        self.id = id
    }

    func appendInstant(_ text: String) {
        instantText += text
    }

    func appendLocal(_ text: String) {
        localText += text
    }

    func setDeepResponse(_ text: String) {
        withAnimation(.easeIn(duration: 0.3)) {
            deepText = text
            isThinkingDeeper = false
        }
    }

    func setThinkingDeeper(_ thinking: Bool) {
        withAnimation { isThinkingDeeper = thinking }
    }

    func addResult(_ result: LayerResult) {
        results.append(result)
    }
}

// MARK: - Layered Message State Store

/// Manages layered states for all messages in a conversation.
@MainActor
final class LayeredMessageStore: ObservableObject {
    @Published var states: [UUID: LayeredMessageState] = [:]

    func getOrCreate(for messageId: UUID) -> LayeredMessageState {
        if let existing = states[messageId] { return existing }
        let state = LayeredMessageState(id: messageId)
        states[messageId] = state
        return state
    }

    func state(for messageId: UUID) -> LayeredMessageState? {
        states[messageId]
    }

    func clear() {
        states.removeAll()
    }
}

// MARK: - Layer Strategy Picker (for Settings)

struct LayerStrategyPicker: View {
    @Binding var strategy: LayeredStrategy
    @Binding var layeredModeEnabled: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle("Layered Responses", isOn: $layeredModeEnabled)
                .accessibilityLabel("Enable layered responses")
                .accessibilityHint("When enabled, multiple AI models respond in parallel for faster and deeper answers")

            if layeredModeEnabled {
                Picker("Strategy", selection: $strategy) {
                    Text("Speed First").tag(LayeredStrategy.speedFirst)
                        .accessibilityLabel("Speed first strategy")
                    Text("Quality First").tag(LayeredStrategy.qualityFirst)
                        .accessibilityLabel("Quality first strategy")
                }
                .pickerStyle(.segmented)
                .accessibilityLabel("Response strategy")

                Text(strategyDescription)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }
        }
    }

    private var strategyDescription: String {
        switch strategy {
        case .speedFirst:
            return "Shows instant response first, then enhances with deeper analysis"
        case .qualityFirst:
            return "Waits for full analysis, uses instant response as preview"
        case .consensusOnly:
            return "Multiple models must agree before responding"
        case .singleLayer:
            return "Uses only one model layer"
        }
    }
}

// Make LayeredStrategy conform to Hashable for use with Picker
extension LayeredStrategy: Hashable {
    static func == (lhs: LayeredStrategy, rhs: LayeredStrategy) -> Bool {
        switch (lhs, rhs) {
        case (.speedFirst, .speedFirst): return true
        case (.qualityFirst, .qualityFirst): return true
        case (.consensusOnly, .consensusOnly): return true
        case (.singleLayer(let a), .singleLayer(let b)): return a == b
        default: return false
        }
    }

    func hash(into hasher: inout Hasher) {
        switch self {
        case .speedFirst: hasher.combine(0)
        case .qualityFirst: hasher.combine(1)
        case .consensusOnly: hasher.combine(2)
        case .singleLayer(let l): hasher.combine(3); hasher.combine(l.rawValue)
        }
    }
}
