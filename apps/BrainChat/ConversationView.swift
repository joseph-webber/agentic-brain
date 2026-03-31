import SwiftUI

struct ConversationView: View {
    @EnvironmentObject var store: ConversationStore

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    ForEach(store.messages) { message in
                        VStack(alignment: .leading, spacing: 4) {
                            Text(message.role.rawValue)
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Text(message.content.isEmpty ? "…" : message.content)
                                .textSelection(.enabled)
                        }
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: message.role == .user ? .trailing : .leading)
                        .background(message.role == .user ? Color.accentColor.opacity(0.15) : Color.secondary.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                        .id(message.id)
                        .accessibilityElement(children: .combine)
                        .accessibilityLabel(message.accessibilityDescription)
                    }
                }
                .padding()
            }
            .onChange(of: store.messages.count) { _, _ in
                if let last = store.messages.last?.id {
                    withAnimation { proxy.scrollTo(last, anchor: .bottom) }
                }
            }
        }
    }
}
