import AppKit
import SwiftUI

struct ConversationView: View {
    @EnvironmentObject var store: ConversationStore
    @EnvironmentObject var layeredStore: LayeredMessageStore

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(store.messages) { message in
                        if message.role == .assistant,
                           let state = layeredStore.state(for: message.id) {
                            LayeredMessageBubble(
                                message: message,
                                layeredState: state
                            )
                            .id(message.id)
                        } else if message.role == .assistant, message.weavingPhase != .idle {
                            WeavedMessageBubble(message: message)
                                .id(message.id)
                        } else {
                            MessageBubble(message: message)
                                .id(message.id)
                        }
                    }

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
                        .accessibilityLabel("Brain Chat is thinking, please wait")
                        .id("processingIndicator")
                    }
                }
                .padding()
            }
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
                    postVoiceOverAnnouncement("Response ready")
                }
            }
        }
    }

    private func announceLatestMessage() {
        guard let last = store.messages.last else { return }
        switch last.role {
        case .user:
            postVoiceOverAnnouncement("Message sent")
        case .assistant, .copilot:
            postVoiceOverAnnouncement("New response from \(last.role.rawValue)")
        case .system:
            break
        }
    }

    private func postVoiceOverAnnouncement(_ message: String) {
        NSAccessibility.post(
            element: NSApp as Any,
            notification: .announcementRequested,
            userInfo: [.announcement: message as NSString]
        )
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
    }

    private var bubbleBackground: Color {
        switch message.role {
        case .user:   return Color.accentColor.opacity(0.15)
        case .system: return Color.orange.opacity(0.08)
        default:      return Color.secondary.opacity(0.08)
        }
    }
}
