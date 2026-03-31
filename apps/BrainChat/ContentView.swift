import AppKit
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: ConversationStore
    @EnvironmentObject var speechManager: SpeechManager
    @EnvironmentObject var voiceManager: VoiceManager
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var llmRouter: LLMRouter

    @State private var textInput = ""
    @State private var isMicLive = false  // Toggle state - muted by default
    @FocusState private var isTextFieldFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                LLMSelector()
                    .environmentObject(llmRouter)
                    .environmentObject(settings)
                
                SpeechEngineSelector()
                    .environmentObject(settings)
                
                Spacer()
                
                // Mic toggle button - ONE CLICK to toggle live/muted
                Button(action: toggleMic) {
                    HStack(spacing: 4) {
                        Image(systemName: isMicLive ? "mic.fill" : "mic.slash.fill")
                            .foregroundColor(isMicLive ? .green : .red)
                        Text(isMicLive ? "Live" : "Muted")
                            .font(.caption)
                    }
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(isMicLive ? Color.green.opacity(0.2) : Color.red.opacity(0.2))
                    .cornerRadius(8)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Microphone")
                .accessibilityValue(isMicLive ? "Live" : "Muted")
                .accessibilityHint(isMicLive ? "Double tap to mute" : "Double tap to go live")
                
                Button(action: { store.clear() }) { 
                    Image(systemName: "trash") 
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Clear conversation")
                .accessibilityHint("Deletes all messages in the current conversation")
            }
            .padding(12)

            Divider()
            ConversationView().frame(maxWidth: .infinity, maxHeight: .infinity)
            Divider()

            // Show live transcript when mic is active
            if isMicLive && !speechManager.currentTranscript.isEmpty {
                HStack {
                    Text("Hearing: \(speechManager.currentTranscript)")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 4)
                .background(Color.green.opacity(0.1))
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Live transcript")
                .accessibilityValue(speechManager.currentTranscript)
            }

            HStack(spacing: 10) {
                TextField("Type a message…", text: $textInput)
                    .textFieldStyle(.roundedBorder)
                    .focused($isTextFieldFocused)
                    .onSubmit { sendTextMessage() }
                    .accessibilityLabel("Message")
                    .accessibilityHint("Type your message and press Return to send")
                Button(action: sendTextMessage) { Image(systemName: "paperplane.fill") }
                    .buttonStyle(.borderedProminent)
                    .disabled(textInput.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .accessibilityLabel("Send message")
            }
            .padding(12)
        }
        .onAppear {
            isTextFieldFocused = true
            voiceManager.selectVoice(named: settings.voiceName)
            voiceManager.speechRate = Float(settings.speechRate)
            speechManager.requestMicrophoneAccess()
            speechManager.onTranscriptFinalized = { transcript in
                Task { @MainActor in 
                    handleUserMessage(transcript)
                    // Keep mic live after sending (continuous listening)
                    if isMicLive {
                        speechManager.startListening()
                    }
                }
            }
            if store.messages.isEmpty {
                store.addMessage(role: .system, content: "Brain Chat ready. Click the mic button to go live, or type below.")
                voiceManager.speak("Brain Chat ready. Click the mic button to go live, or type a message.")
            }
        }
    }

    // Simple toggle - click once to go live, click again to mute
    private func toggleMic() {
        isMicLive.toggle()
        
        if isMicLive {
            speechManager.startListening()
            voiceManager.speak("Mic is live")
            store.addMessage(role: .system, content: "🎤 Microphone is now LIVE - speak anytime")
        } else {
            speechManager.stopListening()
            voiceManager.speak("Mic muted")
            store.addMessage(role: .system, content: "🔇 Microphone muted")
        }
    }

    private func sendTextMessage() {
        let text = textInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        textInput = ""
        handleUserMessage(text)
        isTextFieldFocused = true
    }

    private func handleUserMessage(_ text: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if trimmed == "/yolo" {
            llmRouter.yoloMode.toggle()
            store.addMessage(role: .system, content: "YOLO mode \(llmRouter.yoloMode ? "ON" : "OFF")")
            return
        }

        store.addMessage(role: .user, content: text)
        let history = store.recentConversation
        let configuration = settings.routerConfiguration(provider: llmRouter.selectedProvider, yoloMode: llmRouter.yoloMode)
        let assistantMessageID = store.beginStreamingAssistantMessage()
        store.isProcessing = true

        Task {
            let response = await llmRouter.streamReply(history: history, configuration: configuration) { event in
                switch event {
                case .providerChanged:
                    break
                case .reset:
                    Task { @MainActor in store.replaceMessageContent(id: assistantMessageID, content: "") }
                case .delta(let delta):
                    Task { @MainActor in store.appendToMessage(id: assistantMessageID, delta: delta) }
                }
            }
            await MainActor.run {
                store.finishStreamingMessage(id: assistantMessageID, fallbackContent: response)
                store.isProcessing = false
                if settings.autoSpeak { voiceManager.speak(response) }
            }
        }
    }
}

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
