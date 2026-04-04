import AppKit
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: ConversationStore
    @EnvironmentObject var speechManager: SpeechManager
    @EnvironmentObject var voiceManager: VoiceManager
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var llmRouter: LLMRouter

    @StateObject private var viewModel = ChatViewModel()
    @State private var showClearConfirmation = false
    @FocusState private var isTextFieldFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            toolbar
                .accessibilityIdentifier("statusSection")
                .accessibilityLabel("Status and controls")
            Divider()
            ConversationView()
                .environmentObject(viewModel.layeredMessageStore)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityIdentifier("conversationSection")
            YoloActionFeed(yolo: viewModel.yolo)
            Divider()

            if viewModel.isMicLive && !viewModel.liveTranscript.isEmpty {
                liveTranscriptView
            }

            inputBar
        }
        .overlay {
            if viewModel.yolo.pendingConfirmation != nil {
                ZStack {
                    Color.black.opacity(0.15)
                        .ignoresSafeArea()
                    YoloConfirmationDialog(yolo: viewModel.yolo)
                        .frame(maxWidth: 360)
                }
            }
        }
        .onAppear {
            viewModel.configure(
                store: store,
                speechManager: speechManager,
                voiceManager: voiceManager,
                settings: settings,
                llmRouter: llmRouter
            )
            viewModel.handleAppear()
            isTextFieldFocused = true
        }
        .onDisappear {
            viewModel.handleDisappear()
        }
        .onChange(of: viewModel.error) { _, error in
            guard let error else { return }
            postAccessibilityAnnouncement(error, priority: NSAccessibilityPriorityLevel.high.rawValue)
        }
    }

    private var toolbar: some View {
        HStack(spacing: 8) {
            LLMSelector()
                .environmentObject(llmRouter)
                .environmentObject(settings)

            YoloModeSelector(yolo: viewModel.yolo) { enabled in
                viewModel.setYoloEnabled(enabled)
            }

            SpeechEngineSelector()
                .environmentObject(settings)
                .environmentObject(speechManager)

            Spacer()

            YoloStatusBadge(yolo: viewModel.yolo)

            HStack(spacing: 4) {
                Image(systemName: viewModel.isCopilotSessionActive ? "bolt.horizontal.circle.fill" : "bolt.horizontal.circle")
                    .foregroundColor(viewModel.isCopilotSessionActive ? .blue : .secondary)
                Text(viewModel.copilotStatusText)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
            .accessibilityElement(children: .combine)
            .accessibilityLabel("Copilot session status")
            .accessibilityValue(viewModel.copilotStatusText)
            .accessibilityIdentifier("statusIndicator")

            ProgressView(value: Double(speechManager.audioLevel), total: 1)
                .frame(width: 56)
                .accessibilityIdentifier("audioLevelView")
                .accessibilityLabel("Microphone input level")
                .accessibilityValue(audioLevelDescription)
                .accessibilityHint("Shows how much audio Brain Chat is hearing right now")

            Button(action: viewModel.toggleMic) {
                HStack(spacing: 4) {
                    Image(systemName: viewModel.isMicLive ? "mic.fill" : "mic.slash.fill")
                        .foregroundColor(viewModel.isMicLive ? .green : .red)
                    Text(viewModel.isMicLive ? "Live" : "Muted")
                        .font(.caption)
                }
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(viewModel.isMicLive ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                .cornerRadius(8)
            }
            .buttonStyle(.plain)
            .keyboardShortcut("l", modifiers: .command)
            .accessibilityIdentifier("microphoneButton")
            .accessibilityLabel("Microphone")
            .accessibilityValue(viewModel.isMicLive ? "Live" : "Muted")
            .accessibilityHint(viewModel.isMicLive ? "Double tap to mute" : "Double tap to go live")

            Button(action: voiceManager.stop) {
                Image(systemName: "speaker.slash.fill")
            }
            .buttonStyle(.plain)
            .keyboardShortcut(".", modifiers: .command)
            .accessibilityIdentifier("stopButton")
            .accessibilityLabel("Stop speaking")
            .accessibilityValue(voiceManager.isSpeaking ? "Speaking" : "Idle")
            .accessibilityHint("Stops any spoken response immediately")

            Button(action: openSettings) {
                Image(systemName: "gearshape")
            }
            .buttonStyle(.plain)
            .keyboardShortcut(",", modifiers: .command)
            .accessibilityIdentifier("settingsButton")
            .accessibilityLabel("Open settings")
            .accessibilityHint("Opens Brain Chat settings")

            Button(action: { showClearConfirmation = true }) {
                Image(systemName: "trash")
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("clearButton")
            .accessibilityLabel("Clear conversation")
            .accessibilityHint("Double tap to delete all messages. A confirmation dialog will appear.")
            .confirmationDialog(
                "Clear all messages?",
                isPresented: $showClearConfirmation,
                titleVisibility: .visible
            ) {
                Button("Clear Conversation", role: .destructive) {
                    viewModel.clearConversation()
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("This will permanently delete all messages in this conversation.")
            }
        }
        .padding(12)
    }

    private var liveTranscriptView: some View {
        HStack {
            Text("Hearing: \(viewModel.liveTranscript)")
                .font(.caption)
                .foregroundColor(.secondary)
            Spacer()
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 4)
        .background(Color.green.opacity(0.1))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Live transcript")
        .accessibilityValue(viewModel.liveTranscript)
        .accessibilityHint("Updates while Brain Chat is listening")
        .accessibilityIdentifier("liveTranscript")
    }

    private var inputBar: some View {
        HStack(spacing: 10) {
            TextField("Type a message…", text: $viewModel.inputText)
                .textFieldStyle(.roundedBorder)
                .focused($isTextFieldFocused)
                .onSubmit { sendCurrentInput() }
                .accessibilityIdentifier("messageInput")
                .accessibilityLabel("Message input")
                .accessibilityHint("Type your message. Press Return or Command Return to send. Press Escape to clear.")
                .onEscapeKey { viewModel.inputText = "" }

            Button(action: sendCurrentInput) {
                Image(systemName: "paperplane.fill")
            }
            .buttonStyle(.borderedProminent)
            .disabled(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .accessibilityIdentifier("sendButton")
            .accessibilityLabel("Send message")
            .accessibilityValue(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "No message entered" : "Ready to send")
            .accessibilityHint("Send your typed message to Brain Chat")
            .keyboardShortcut(.return, modifiers: .command)
        }
        .padding(12)
        .accessibilityIdentifier("inputSection")
        .accessibilityLabel("Message composer")
    }

    private func sendCurrentInput() {
        Task {
            await viewModel.sendMessage()
            await MainActor.run {
                isTextFieldFocused = true
            }
        }
    }

    private var audioLevelDescription: String {
        let level = speechManager.audioLevel
        switch level {
        case ..<0.05:
            return "Silent"
        case ..<0.3:
            return "Low"
        case ..<0.7:
            return "Moderate"
        default:
            return "High"
        }
    }

    private func openSettings() {
        if !NSApp.sendAction(Selector(("showSettingsWindow:")), to: nil, from: nil) {
            _ = NSApp.sendAction(Selector(("showPreferencesWindow:")), to: nil, from: nil)
        }
    }

    private func postAccessibilityAnnouncement(_ message: String, priority: Int = 50) {
        NSAccessibility.post(
            element: NSApp as Any,
            notification: .announcementRequested,
            userInfo: [
                .announcement: message,
                .priority: priority
            ]
        )
    }
}

// MARK: - Keyboard helpers

struct KeyEventHandlerView: NSViewRepresentable {
    let onSpaceDown: () -> Void
    let onSpaceUp: () -> Void

    func makeNSView(context: Context) -> KeyEventNSView {
        let view = KeyEventNSView()
        view.onSpaceDown = onSpaceDown
        view.onSpaceUp = onSpaceUp
        return view
    }

    func updateNSView(_ nsView: KeyEventNSView, context: Context) {
        nsView.onSpaceDown = onSpaceDown
        nsView.onSpaceUp = onSpaceUp
    }
}

class KeyEventNSView: NSView {
    var onSpaceDown: (() -> Void)?
    var onSpaceUp: (() -> Void)?
    private var spaceIsDown = false

    override var acceptsFirstResponder: Bool { true }

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 49 && !event.isARepeat && !spaceIsDown {
            spaceIsDown = true
            onSpaceDown?()
        } else {
            super.keyDown(with: event)
        }
    }

    override func keyUp(with event: NSEvent) {
        if event.keyCode == 49 {
            spaceIsDown = false
            onSpaceUp?()
        } else {
            super.keyUp(with: event)
        }
    }
}

// MARK: - onEscapeKey modifier

extension View {
    @ViewBuilder
    func onEscapeKey(action: @escaping () -> Void) -> some View {
        if #available(macOS 14.0, iOS 17.0, *) {
            self.onKeyPress(.escape) { action(); return .handled }
        } else {
            self
        }
    }
}
