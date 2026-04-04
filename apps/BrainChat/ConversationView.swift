import AppKit
import SwiftUI

struct ConversationView: View {
    @EnvironmentObject var store: ConversationStore
    @EnvironmentObject var layeredStore: LayeredMessageStore

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    // MARK: Empty State
                    if store.messages.isEmpty && !store.isProcessing {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("No messages yet")
                                .font(.headline)
                            Text("Type a message or turn on the microphone to start a conversation.")
                                .foregroundColor(.secondary)
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(12)
                        .background(Color.secondary.opacity(0.06))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .accessibilityElement(children: .combine)
                        .accessibilityIdentifier("emptyState")
                        .accessibilityLabel("Empty")
                        .accessibilityHint("Start conversation")
                    }

                    // MARK: Messages List - with rotor support
                    ForEach(store.messages, id: \.id) { message in
                        let msgId = String(describing: message.id)
                        if message.role == .assistant,
                           let state = layeredStore.state(for: message.id) {
                            LayeredMessageBubble(
                                message: message,
                                layeredState: state
                            )
                            .id(message.id)
                            .accessibilityIdentifier("message-" + msgId)
                            .accessibilityAddTraits(.isButton)
                        } else if message.role == .assistant, message.weavingPhase != .idle {
                            WeavedMessageBubble(message: message)
                                .id(message.id)
                                .accessibilityIdentifier("message-" + msgId)
                                .accessibilityAddTraits(.isButton)
                        } else {
                            MessageBubble(message: message)
                                .id(message.id)
                                .accessibilityIdentifier("message-" + msgId)
                                .accessibilityAddTraits(.isButton)
                        }
                    }

                    // MARK: Processing Indicator
                    if store.isProcessing {
                        HStack(spacing: 8) {
                            ProgressView().scaleEffect(0.75)
                            Text("Thinking…")
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .accessibilityElement(children: .combine)
                        .accessibilityShortLabel("Processing")
                        .accessibilityHint("Thinking…")
                        .accessibilityAddTraits(.updatesFrequently)
                        .id("processingIndicator")
                    }
                }
                .padding()
            }
            .accessibilityIdentifier("conversationSection")
            .accessibilityElement(children: .contain)
            .accessibilityLabel("Messages")
            .accessibilityHint("Conversation thread")
            .onChange(of: store.messages.count) { _, _ in
                if let last = store.messages.last?.id {
                    withAnimation { proxy.scrollTo(last, anchor: .bottom) }
                }
                announceLatestMessage()
            }
            .onChange(of: store.isProcessing) { _, isProcessing in
                if isProcessing {
                    withAnimation { proxy.scrollTo("processingIndicator", anchor: .bottom) }
                } else {
                    if let last = store.messages.last?.id {
                        withAnimation { proxy.scrollTo(last, anchor: .bottom) }
                    }
                    AccessibilityHelpers.announceNormal("Response ready")
                }
            }
        }
    }

    private func announceLatestMessage() {
        guard let last = store.messages.last else { return }
        switch last.role {
        case .user:
            AccessibilityHelpers.announceNormal("Message sent")
        case .assistant, .copilot:
            AccessibilityHelpers.announceNormal("New \(last.role.accessibilityName)")
        case .system:
            break
        }
    }
}

// MARK: - Plain message bubble (non-weaved, non-layered)

struct MessageBubble: View {
    let message: ChatMessage

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(message.role.rawValue)
                .font(.caption)
                .foregroundColor(.secondary)
                .accessibilityHidden(true)
            Text(message.content.isEmpty ? "…" : message.content)
                .textSelection(.enabled)
                .dynamicTypeSize(.small ... .accessibility3)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
        .background(bubbleBackground)
        .clipShape(RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
        .accessibilityLabel(message.accessibilityDescription)
        .accessibilityHint("Message")
    }

    private var bubbleBackground: Color {
        switch message.role {
        case .user:   return Color.accentColor.opacity(0.15)
        case .system: return Color.orange.opacity(0.08)
        default:      return Color.secondary.opacity(0.08)
        }
    }
}
