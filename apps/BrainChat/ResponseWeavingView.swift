import AppKit
import SwiftUI

// MARK: - Thinking Indicator

/// Animated three-dot indicator shown while the deep LLM is processing.
struct ThinkingIndicator: View {
    @State private var phase: Int = 0
    private let timer = Timer.publish(every: 0.45, on: .main, in: .common).autoconnect()

    var body: some View {
        HStack(spacing: 5) {
            ForEach(0..<3) { index in
                Circle()
                    .frame(width: 7, height: 7)
                    .foregroundColor(.secondary.opacity(phase == index ? 1.0 : 0.3))
                    .scaleEffect(phase == index ? 1.25 : 1.0)
                    .animation(.easeInOut(duration: 0.35), value: phase)
            }
            Text("Thinking deeper…")
                .font(.caption)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Thinking deeper, please wait")
        .accessibilityValue("Working")
        .accessibilityHint("An enhanced response will be announced when it is ready")
        .accessibilityAddTraits(.updatesFrequently)
        .onReceive(timer) { _ in
            phase = (phase + 1) % 3
        }
    }
}

// MARK: - Woven Layer View

/// Displays a deeper (Layer 2+) response with a subtle fade-in entrance.
struct WeavedLayerView: View {
    let layer: ResponseLayer
    @State private var visible = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            if !layer.weavingPrefix.isEmpty {
                Text(layer.weavingPrefix)
                    .font(.subheadline.italic())
                    .foregroundColor(.secondary)
                    .accessibilityHidden(true)
            }
            Text(layer.content.isEmpty ? "…" : layer.content)
                .foregroundColor(.primary.opacity(0.85))
                .textSelection(.enabled)
        }
        .padding(.top, 6)
        .opacity(visible ? 1 : 0)
        .offset(y: visible ? 0 : 6)
        .animation(.easeOut(duration: 0.5), value: visible)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(layer.accessibilityLabel)
        .accessibilityValue(layer.content)
        .accessibilityHint("Additional detail for the current answer")
        .onAppear { visible = true }
    }
}

// MARK: - Message Bubble

/// Unified message bubble supporting both plain (single-layer) and woven (multi-layer) messages.
struct WeavedMessageBubble: View {
    let message: ChatMessage

    @State private var previousPhase: WeavingPhase = .idle

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            roleLine

            if message.weavingPhase == .idle {
                // Standard single-layer display.
                Text(message.content.isEmpty ? "…" : message.content)
                    .textSelection(.enabled)
                    .accessibilityLabel(message.accessibilityDescription)
            } else {
                weavedContent
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.secondary.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .contain)
        .accessibilityLabel(message.accessibilityDescription)
        .accessibilityValue(message.weavingPhase.accessibilityAnnouncement ?? "Single response")
        .onChange(of: message.weavingPhase) { _, newPhase in
            announcePhaseChange(newPhase)
            previousPhase = newPhase
        }
    }

    // MARK: Private

    @ViewBuilder
    private var roleLine: some View {
        Text(message.role.rawValue)
            .font(.caption)
            .foregroundColor(.secondary)
    }

    @ViewBuilder
    private var weavedContent: some View {
        // Layer 1 — instant response.
        if let instant = message.layers.first(where: { $0.isInstant }) {
            Text(instant.content.isEmpty ? "…" : instant.content)
                .textSelection(.enabled)
                .accessibilityLabel(instant.accessibilityLabel + ": " + instant.content)
        } else {
            // Streaming phase before Layer 1 is committed to layers yet.
            Text(message.content.isEmpty ? "…" : message.content)
                .textSelection(.enabled)
        }

        // Thinking indicator — shown between Layer 1 finishing and Layer 2 starting.
        if message.weavingPhase == .thinking {
            ThinkingIndicator()
        }

        // Layer 2+ — woven enhancements.
        ForEach(message.layers.filter { $0.isDeeper }) { layer in
            WeavedLayerView(layer: layer)
        }
    }

    private func announcePhaseChange(_ phase: WeavingPhase) {
        guard let announcement = phase.accessibilityAnnouncement else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            let userInfo: [NSAccessibility.NotificationUserInfoKey: Any] = [
                .announcement: announcement,
                .priority: NSAccessibilityPriorityLevel.high.rawValue
            ]
            NSAccessibility.post(element: NSApp as Any, notification: .announcementRequested, userInfo: userInfo)
        }
    }
}

// MARK: - Preview

#if DEBUG
struct ResponseWeavingPreviews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 16) {
            // Plain message
            WeavedMessageBubble(
                message: ChatMessage(role: .assistant, content: "Hello Joseph, how can I help?")
            )

            // Weaved message — thinking phase
            WeavedMessageBubble(
                message: {
                    var m = ChatMessage(role: .assistant, content: "Swift uses value types for structs.")
                    m.weavingPhase = .thinking
                    m.layers = [
                        ResponseLayer(layerNumber: 1, provider: "Ollama", content: "Swift uses value types for structs.")
                    ]
                    return m
                }()
            )

            // Weaved message — complete
            WeavedMessageBubble(
                message: {
                    var m = ChatMessage(role: .assistant, content: "Swift uses value types for structs.")
                    m.weavingPhase = .complete
                    m.layers = [
                        ResponseLayer(layerNumber: 1, provider: "Ollama", content: "Swift uses value types for structs."),
                        ResponseLayer(layerNumber: 2, provider: "Claude", content: "This means mutations don't propagate through references, which avoids many common bugs in concurrent code.")
                    ]
                    return m
                }()
            )

            ThinkingIndicator()
        }
        .padding()
    }
}
#endif
