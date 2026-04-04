import AppKit
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var store: ConversationStore
    @EnvironmentObject var speechManager: SpeechManager
    @EnvironmentObject var voiceManager: VoiceManager
    @EnvironmentObject var settings: AppSettings
    @EnvironmentObject var llmRouter: LLMRouter
    @StateObject private var yolo = YoloMode.shared

    private let copilotBridge = CopilotBridge.shared
    @State private var textInput = ""
    @State private var isMicLive = false  // Toggle state - muted by default
    @State private var isCopilotSessionActive = false
    @State private var copilotStatusText = "Copilot offline"
    @FocusState private var isTextFieldFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                LLMSelector()
                    .environmentObject(llmRouter)
                    .environmentObject(settings)

                YoloModeSelector(yolo: yolo) { enabled in
                    setYoloEnabled(enabled)
                }

                SpeechEngineSelector()
                    .environmentObject(settings)
                    .environmentObject(speechManager)

                Spacer()

                YoloStatusBadge(yolo: yolo)

                HStack(spacing: 4) {
                    Image(systemName: isCopilotSessionActive ? "bolt.horizontal.circle.fill" : "bolt.horizontal.circle")
                        .foregroundColor(isCopilotSessionActive ? .blue : .secondary)
                    Text(copilotStatusText)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .accessibilityElement(children: .combine)
                .accessibilityLabel("Copilot session status")
                .accessibilityValue(copilotStatusText)
                
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
                .accessibilityIdentifier("micButton")
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
            YoloActionFeed(yolo: yolo)
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
        .overlay {
            if yolo.pendingConfirmation != nil {
                ZStack {
                    Color.black.opacity(0.15)
                        .ignoresSafeArea()
                    YoloConfirmationDialog(yolo: yolo)
                        .frame(maxWidth: 360)
                }
            }
        }
        .onAppear {
            setYoloEnabled(llmRouter.yoloMode)
            isTextFieldFocused = true
            voiceManager.selectVoice(named: settings.voiceName)
            voiceManager.speechRate = Float(settings.speechRate)
            speechManager.setEngine(settings.speechEngine)
            speechManager.setOpenAIKey(settings.openAIKey)
            // Don't request permission here - wait for user to click mic button
            // This prevents race condition: request on launch, then check on button click
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
                store.addMessage(role: .system, content: "Brain Chat ready. Click the mic button to go live, or type below. Use /copilot, /suggest, or /explain for GitHub Copilot.")
                voiceManager.speak("Brain Chat ready. Click the mic button to go live, or say copilot followed by your coding question.")
            }
        }
        .onChange(of: settings.speechEngine) { _, newValue in
            speechManager.setEngine(newValue)
        }
        .onChange(of: settings.openAIKey) { _, newValue in
            speechManager.setOpenAIKey(newValue)
        }
        .onDisappear {
            copilotBridge.stopSession()
            updateCopilotSessionState(active: false, status: "Copilot offline")
        }
        .onChange(of: llmRouter.yoloMode) { _, enabled in
            if enabled != yolo.isActive {
                setYoloEnabled(enabled)
            }
        }
        .onChange(of: yolo.isActive) { _, active in
            if llmRouter.yoloMode != active {
                llmRouter.yoloMode = active
            }
        }
    }

    // Simple toggle - click once to go live, click again to mute
    private func toggleMic() {
        NSLog("BRAINCHAT: toggleMic() CALLED - isMicLive=\(isMicLive)")
        // If turning OFF, just stop
        if isMicLive {
            isMicLive = false
            speechManager.stopListening()
            voiceManager.speak("Mic muted")
            store.addMessage(role: .system, content: "🔇 Microphone muted")
            return
        }
        
        // Turning ON - check permission FIRST (like KarenVoice does)
        speechManager.requestMicrophonePermissionWithCompletion { [self] granted in
            Task { @MainActor in
                if granted {
                    isMicLive = true
                    speechManager.startListening()
                    voiceManager.speak("Mic is live")
                    store.addMessage(role: .system, content: "🎤 Microphone is now LIVE - speak anytime")
                } else {
                    store.addMessage(role: .system, content: "⚠️ Microphone permission denied. Enable in System Settings > Privacy & Security > Microphone")
                    voiceManager.speak("Please enable microphone access in System Settings")
                }
            }
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
        let normalizedText = normalizeCopilotCommand(text)
        let trimmed = normalizedText.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if trimmed == "/yolo" {
            setYoloEnabled(!yolo.isActive)
            store.addMessage(role: .system, content: "YOLO mode \(yolo.isActive ? "ON" : "OFF")")
            return
        }

        if yolo.handleVoiceCommand(normalizedText) {
            setYoloEnabled(yolo.isActive)
            if let lastFeedItem = yolo.actionsFeed.last {
                store.addMessage(role: .system, content: lastFeedItem.text)
            }
            return
        }

        if let command = CopilotBridge.parseCommand(normalizedText) {
            handleCopilotCommand(command, sourceText: normalizedText)
            return
        }

        store.addMessage(role: .user, content: text)

        if yolo.isActive {
            let assistantMessageID = store.beginStreamingAssistantMessage()
            store.replaceMessageContent(id: assistantMessageID, content: "Dispatching to YOLO agents…")
            store.isProcessing = true

            Task {
                let response = await yolo.submitPrompt(normalizedText, targetLLM: llmRouter.selectedProvider.shortName)
                await MainActor.run {
                    store.replaceMessageContent(id: assistantMessageID, content: response)
                    store.isProcessing = false
                    if settings.autoSpeak {
                        voiceManager.speak(response)
                    }
                }
            }
            return
        }

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

    private func setYoloEnabled(_ enabled: Bool) {
        if enabled {
            if !yolo.isActive {
                yolo.activate()
            }
        } else if yolo.isActive {
            yolo.deactivate()
        }

        if llmRouter.yoloMode != enabled {
            llmRouter.yoloMode = enabled
        }
    }

    private func handleCopilotCommand(_ command: CopilotCommand, sourceText: String) {
        store.addMessage(role: .user, content: sourceText)

        switch command {
        case .startSession:
            do {
                try copilotBridge.startSession()
                updateCopilotSessionState(active: true, status: "Copilot chat live")
                store.addMessage(role: .system, content: "GitHub Copilot chat session started.")
                if settings.autoSpeak { voiceManager.speak("Copilot chat is ready.") }
            } catch {
                updateCopilotSessionState(active: false, status: "Copilot failed")
                store.addMessage(role: .system, content: "Copilot start failed: \(error.localizedDescription)")
                if settings.autoSpeak { voiceManager.speak("Copilot start failed.") }
            }
        case .stopSession:
            copilotBridge.stopSession()
            updateCopilotSessionState(active: false, status: "Copilot offline")
            store.addMessage(role: .system, content: "GitHub Copilot chat session stopped.")
            if settings.autoSpeak { voiceManager.speak("Copilot stopped.") }
        case .restartSession:
            do {
                try copilotBridge.restartSession()
                updateCopilotSessionState(active: true, status: "Copilot chat live")
                store.addMessage(role: .system, content: "GitHub Copilot chat session restarted.")
                if settings.autoSpeak { voiceManager.speak("Copilot restarted.") }
            } catch {
                updateCopilotSessionState(active: false, status: "Copilot failed")
                store.addMessage(role: .system, content: "Copilot restart failed: \(error.localizedDescription)")
                if settings.autoSpeak { voiceManager.speak("Copilot restart failed.") }
            }
        case .chat(let prompt):
            runCopilotChat(prompt: prompt)
        case .suggest(let prompt):
            runCopilotOneShot(mode: .suggest, prompt: prompt)
        case .explain(let prompt):
            runCopilotOneShot(mode: .explain, prompt: prompt)
        }
    }

    private func runCopilotChat(prompt: String) {
        do {
            if !copilotBridge.isSessionActive {
                try copilotBridge.startSession()
                updateCopilotSessionState(active: true, status: "Copilot chat live")
                store.addMessage(role: .system, content: "GitHub Copilot chat session started.")
            }
        } catch {
            updateCopilotSessionState(active: false, status: "Copilot failed")
            store.addMessage(role: .system, content: "Copilot start failed: \(error.localizedDescription)")
            if settings.autoSpeak { voiceManager.speak("Copilot start failed.") }
            return
        }

        let messageID = store.beginStreamingMessage(role: .copilot)
        store.isProcessing = true
        updateCopilotSessionState(active: true, status: "Copilot thinking")

        do {
            try copilotBridge.sendChat(prompt, onDelta: { delta in
                Task { @MainActor in
                    store.appendToMessage(id: messageID, delta: delta)
                }
            }, completion: { result in
                Task { @MainActor in
                    store.isProcessing = false
                    switch result {
                    case .success(let response):
                        updateCopilotSessionState(active: true, status: "Copilot chat live")
                        store.finishStreamingMessage(id: messageID, fallbackContent: response.text)
                        if settings.autoSpeak {
                            voiceManager.speak(spokenPreview(for: response.text))
                        }
                    case .failure(let error):
                        updateCopilotSessionState(active: copilotBridge.isSessionActive, status: copilotBridge.isSessionActive ? "Copilot chat live" : "Copilot offline")
                        store.replaceMessageContent(id: messageID, content: "Copilot error: \(error.localizedDescription)")
                        if settings.autoSpeak {
                            voiceManager.speak("Copilot error.")
                        }
                    }
                }
            })
        } catch {
            store.isProcessing = false
            updateCopilotSessionState(active: copilotBridge.isSessionActive, status: copilotBridge.isSessionActive ? "Copilot chat live" : "Copilot offline")
            store.replaceMessageContent(id: messageID, content: "Copilot error: \(error.localizedDescription)")
            if settings.autoSpeak { voiceManager.speak("Copilot error.") }
        }
    }

    private func runCopilotOneShot(mode: CopilotCommandMode, prompt: String) {
        let messageID = store.beginStreamingMessage(role: .copilot)
        store.isProcessing = true
        updateCopilotSessionState(active: copilotBridge.isSessionActive, status: mode == .suggest ? "Copilot suggesting" : "Copilot explaining")

        copilotBridge.executeOneShot(mode: mode, prompt: prompt, onDelta: { delta in
            store.appendToMessage(id: messageID, delta: delta)
        }, completion: { result in
            store.isProcessing = false
            switch result {
            case .success(let response):
                updateCopilotSessionState(active: copilotBridge.isSessionActive, status: copilotBridge.isSessionActive ? "Copilot chat live" : "Copilot ready")
                store.finishStreamingMessage(id: messageID, fallbackContent: response.text)
                if settings.autoSpeak {
                    voiceManager.speak(spokenPreview(for: response.text))
                }
            case .failure(let error):
                updateCopilotSessionState(active: copilotBridge.isSessionActive, status: copilotBridge.isSessionActive ? "Copilot chat live" : "Copilot failed")
                store.replaceMessageContent(id: messageID, content: "Copilot error: \(error.localizedDescription)")
                if settings.autoSpeak {
                    voiceManager.speak("Copilot error.")
                }
            }
        })
    }

    private func normalizeCopilotCommand(_ text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return text }

        let lower = trimmed.lowercased()
        let mappings: [(prefix: String, replacement: String)] = [
            ("slash copilot start", "/copilot start"),
            ("slash copilot stop", "/copilot stop"),
            ("slash copilot restart", "/copilot restart"),
            ("slash copilot suggest ", "/suggest "),
            ("slash copilot explain ", "/explain "),
            ("slash copilot ", "/copilot "),
            ("copilot start", "/copilot start"),
            ("copilot stop", "/copilot stop"),
            ("copilot restart", "/copilot restart"),
            ("copilot suggest ", "/suggest "),
            ("copilot explain ", "/explain "),
            ("copilot ", "/copilot ")
        ]

        for mapping in mappings where lower.hasPrefix(mapping.prefix) {
            if lower == mapping.prefix {
                return mapping.replacement
            }
            let suffix = String(trimmed.dropFirst(mapping.prefix.count))
            return mapping.replacement + suffix
        }

        return text
    }

    private func spokenPreview(for text: String) -> String {
        let cleaned = text
            .replacingOccurrences(of: "```", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return String(cleaned.prefix(400))
    }

    private func updateCopilotSessionState(active: Bool, status: String) {
        isCopilotSessionActive = active
        copilotStatusText = status
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
