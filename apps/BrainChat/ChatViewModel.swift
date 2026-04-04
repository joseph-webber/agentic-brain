import Combine
import AppKit
import SwiftUI

enum ChatMode {
    case chat
    case copilot
    case suggest
    case explain
    case yolo
}

@MainActor
final class ChatViewModel: ObservableObject {
    // MARK: - Published State
    @Published var inputText = ""
    @Published var liveTranscript = ""
    @Published var isMicLive = false
    @Published var isProcessing = false
    @Published var currentMode: ChatMode = .chat
    @Published var error: String?
    @Published private(set) var isCopilotSessionActive = false
    @Published private(set) var copilotStatusText = "Copilot offline"

    // MARK: - Dependencies
    let yolo: YoloMode
    let layeredMessageStore: LayeredMessageStore

    private var store: ConversationStore?
    private var voiceManager: VoiceManager?
    private var settings: AppSettings?
    private var llmRouter: LLMRouter?
    private let securityManager: SecurityManager

    private let copilotBridge: CopilotBridge
    private let layeredManager: LayeredResponseManager
    private var speechManager: SpeechManager?
    private var hasAnnouncedStreaming = false

    // MARK: - Cancellables
    private var cancellables = Set<AnyCancellable>()

    init(
        copilotBridge: CopilotBridge = .shared,
        layeredManager: LayeredResponseManager? = nil,
        layeredMessageStore: LayeredMessageStore? = nil,
        yolo: YoloMode? = nil,
        securityManager: SecurityManager? = nil
    ) {
        self.copilotBridge = copilotBridge
        self.layeredManager = layeredManager ?? LayeredResponseManager()
        self.layeredMessageStore = layeredMessageStore ?? LayeredMessageStore()
        self.securityManager = securityManager ?? .shared
        self.yolo = yolo ?? YoloMode.shared
    }

    func configure(
        store: ConversationStore,
        speechManager: SpeechManager,
        voiceManager: VoiceManager,
        settings: AppSettings,
        llmRouter: LLMRouter
    ) {
        guard needsConfiguration(
            store: store,
            speechManager: speechManager,
            voiceManager: voiceManager,
            settings: settings,
            llmRouter: llmRouter
        ) else {
            return
        }

        self.store = store
        self.speechManager = speechManager
        self.voiceManager = voiceManager
        self.settings = settings
        self.llmRouter = llmRouter
        setupBindings()
        applyCurrentSettings()
        updateCopilotSessionState(
            active: copilotBridge.isSessionActive,
            status: copilotBridge.isSessionActive ? "Copilot chat live" : "Copilot offline"
        )
        if !securityManager.canUseYolo(), llmRouter.yoloMode {
            llmRouter.yoloMode = false
        }
        setYoloEnabled(llmRouter.yoloMode, announceBlocked: false)
        isMicLive = speechManager.isListening
        liveTranscript = speechManager.currentTranscript
        isProcessing = store.isProcessing
    }

    func handleAppear() {
        guard let store else { return }

        applyCurrentSettings()
        
        // Check Copilot CLI status on startup
        Task {
            await checkCopilotStatus()
        }
        
        if store.messages.isEmpty {
            store.addMessage(
                role: .system,
                content: "Brain Chat ready for voice coding. Click the mic or type below. Voice commands: read line, go to function, explain this, fix error, save to file, commit changes. Use /copilot for GitHub Copilot."
            )
            voiceManager?.speak(
                "Brain Chat ready for voice coding. Click the mic button to go live. You can say things like, read line 10, go to function main, explain this code, or fix this error."
            )
        }
    }
    
    /// Check if GitHub Copilot CLI is installed and working
    private func checkCopilotStatus() async {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["gh", "copilot", "--version"]
        
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        
        do {
            try process.run()
            process.waitUntilExit()
            
            if process.terminationStatus == 0 {
                await MainActor.run {
                    updateCopilotSessionState(active: true, status: "Copilot ready")
                }
            } else {
                await MainActor.run {
                    updateCopilotSessionState(active: false, status: "Copilot not installed")
                }
            }
        } catch {
            await MainActor.run {
                updateCopilotSessionState(active: false, status: "Copilot offline")
            }
        }
    }

    func handleDisappear() {
        copilotBridge.stopSession()
        updateCopilotSessionState(active: false, status: "Copilot offline")
    }

    func clearConversation() {
        store?.clear()
        layeredMessageStore.clear()
        announce("Conversation cleared")
    }

    // MARK: - Actions
    func toggleMic() {
        guard let speechManager, let store else { return }

        if isMicLive {
            isMicLive = false
            liveTranscript = ""
            speechManager.stopListening()
            voiceManager?.speak("Mic muted")
            store.addMessage(role: .system, content: "🔇 Microphone muted")
            announce("Microphone muted")
            return
        }

        speechManager.requestMicrophonePermissionWithCompletion { [weak self] granted in
            guard let self else { return }
            Task { @MainActor in
                if granted {
                    self.isMicLive = true
                    speechManager.startListening()
                    self.voiceManager?.speak("Mic is live")
                    store.addMessage(role: .system, content: "🎤 Microphone is now LIVE - speak anytime")
                    self.announce("Microphone live")
                } else {
                    let message = "⚠️ Microphone permission denied. Enable in System Settings > Privacy & Security > Microphone"
                    self.error = message
                    store.addMessage(role: .system, content: message)
                    self.voiceManager?.speak("Please enable microphone access in System Settings")
                }
            }
        }
    }

    func sendMessage() async {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        await handleInput(text)
    }

    func handleCommand(_ command: String) async {
        _ = await processCommand(command, originalText: command)
    }

    func sendToLLM(_ text: String) async {
        guard let store, let settings, let llmRouter else { return }

        let history = store.recentConversation
        let configuration = settings.routerConfiguration(
            provider: llmRouter.selectedProvider,
            yoloMode: llmRouter.yoloMode
        )
        let assistantMessageID = store.beginStreamingAssistantMessage()
        hasAnnouncedStreaming = false
        updateProcessing(true)
        currentMode = yolo.isActive ? .yolo : .chat

        if settings.layeredModeEnabled {
            await streamLayeredResponse(
                assistantMessageID: assistantMessageID,
                history: history,
                configuration: configuration,
                userText: text
            )
            return
        }

        let response = await llmRouter.streamReply(history: history, configuration: configuration) { [weak self] event in
            guard let self else { return }
            Task { @MainActor in
                switch event {
                case .providerChanged:
                    break
                case .reset:
                    store.replaceMessageContent(id: assistantMessageID, content: "")
                case .delta(let delta):
                    if !self.hasAnnouncedStreaming, !delta.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        self.hasAnnouncedStreaming = true
                        self.announce("Response streaming")
                    }
                    store.appendToMessage(id: assistantMessageID, delta: delta)
                }
                self.isProcessing = store.isProcessing
            }
        }

        store.finishStreamingMessage(id: assistantMessageID, fallbackContent: response)
        updateProcessing(false)
        speakIfEnabled(response)
    }

    @discardableResult
    func setYoloEnabled(_ enabled: Bool, announceBlocked: Bool = true) -> Bool {
        if enabled, !securityManager.canUseYolo() {
            if llmRouter?.yoloMode == true {
                llmRouter?.yoloMode = false
            }
            currentMode = .chat
            if announceBlocked {
                presentSecurityMessage(securityManager.yoloAccessDeniedMessage())
            }
            return false
        }

        if enabled {
            if !yolo.isActive {
                yolo.activate()
            }
        } else if yolo.isActive {
            yolo.deactivate()
        }

        if llmRouter?.yoloMode != enabled {
            llmRouter?.yoloMode = enabled
        }
        currentMode = enabled ? .yolo : .chat
        return true
    }

    // MARK: - Private
    private func needsConfiguration(
        store: ConversationStore,
        speechManager: SpeechManager,
        voiceManager: VoiceManager,
        settings: AppSettings,
        llmRouter: LLMRouter
    ) -> Bool {
        self.store !== store ||
        self.speechManager !== speechManager ||
        self.voiceManager !== voiceManager ||
        self.settings !== settings ||
        self.llmRouter !== llmRouter
    }

    private func handleInput(_ text: String) async {
        let normalizedText = normalizeCopilotCommand(text)
        if await processCommand(normalizedText, originalText: text) {
            return
        }

        store?.addMessage(role: .user, content: text)

        if yolo.isActive {
            await sendToYolo(normalizedText)
        } else {
            await sendToLLM(normalizedText)
        }
    }

    private func processCommand(_ text: String, originalText: String) async -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()

        if trimmed == "/yolo" {
            let enabling = !yolo.isActive
            if setYoloEnabled(enabling) {
                store?.addMessage(role: .system, content: "YOLO mode \(yolo.isActive ? "ON" : "OFF")")
            }
            return true
        }

        if yolo.handleVoiceCommand(text) {
            _ = setYoloEnabled(yolo.isActive, announceBlocked: false)
            if let lastFeedItem = yolo.actionsFeed.last {
                store?.addMessage(role: .system, content: lastFeedItem.text)
                if lastFeedItem.type == .error {
                    error = lastFeedItem.text
                    announce(lastFeedItem.text)
                }
            }
            return true
        }

        guard let command = CopilotBridge.parseCommand(text) else {
            return false
        }

        handleCopilotCommand(command, sourceText: normalizeCopilotCommand(originalText))
        return true
    }

    private func sendToYolo(_ text: String) async {
        guard let store, let llmRouter else { return }
        guard securityManager.canUseYolo() else {
            presentSecurityMessage(securityManager.yoloAccessDeniedMessage())
            return
        }

        let assistantMessageID = store.beginStreamingAssistantMessage()
        store.replaceMessageContent(id: assistantMessageID, content: "Dispatching to YOLO agents…")
        updateProcessing(true)
        currentMode = .yolo

        let response = await yolo.submitPrompt(text, targetLLM: llmRouter.selectedProvider.shortName)
        store.replaceMessageContent(id: assistantMessageID, content: response)
        updateProcessing(false)
        speakIfEnabled(response)
    }

    private func streamLayeredResponse(
        assistantMessageID: UUID,
        history: [ChatMessage],
        configuration: LLMRouterConfiguration,
        userText: String
    ) async {
        guard let store, let settings, let llmRouter else { return }

        let layeredConfig = settings.layeredConfiguration(
            provider: llmRouter.selectedProvider,
            yoloMode: llmRouter.yoloMode
        )
        let messages = LLMRouter.buildContext(
            from: history,
            systemPrompt: configuration.effectiveSystemPrompt
        )
        let layeredState = layeredMessageStore.getOrCreate(for: assistantMessageID)
        hasAnnouncedStreaming = false

        let response = await layeredManager.getLayeredResponse(
            messages: messages,
            configuration: layeredConfig
        ) { [weak self] event in
            guard let self else { return }
            Task { @MainActor in
                switch event {
                case .layerStarted:
                    break
                case .layerDelta(let chunk):
                    switch chunk.layer {
                    case .instant:
                        if !self.hasAnnouncedStreaming, !chunk.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            self.hasAnnouncedStreaming = true
                            self.announce("Response streaming")
                        }
                        layeredState.appendInstant(chunk.content)
                        store.replaceMessageContent(id: assistantMessageID, content: layeredState.instantText)
                        
                        // OPTIMIZATION: Start voice on FIRST chunk immediately (< 100ms)
                        if settings.autoSpeak, !layeredState.spokenInstant, !layeredState.instantText.isEmpty, 
                           layeredState.instantText.count > 20 {  // Wait for meaningful content
                            layeredState.spokenInstant = true
                            self.voiceManager?.speak(layeredState.instantText)
                        }
                    case .fastLocal:
                        layeredState.appendLocal(chunk.content)
                    case .deep, .consensus:
                        break
                    }
                case .deepThinkingStarted:
                    layeredState.setThinkingDeeper(true)
                    self.announce("Thinking deeper")
                    if settings.autoSpeak, !layeredState.instantText.isEmpty, !layeredState.spokenInstant {
                        layeredState.spokenInstant = true
                        self.voiceManager?.speak(layeredState.instantText)
                    }
                case .enhancedResponseReady(let deepText):
                    layeredState.setDeepResponse(deepText)
                    store.replaceMessageContent(id: assistantMessageID, content: deepText)
                    self.announce("Enhanced response available")
                    if settings.autoSpeak, layeredState.spokenInstant {
                        self.voiceManager?.speak("Let me add to that. " + String(deepText.prefix(400)))
                    }
                case .layerCompleted:
                    break
                case .consensusResult:
                    break
                case .allLayersComplete(let results):
                    layeredState.results = results
                }
            }
        }

        store.finishStreamingMessage(id: assistantMessageID, fallbackContent: response)
        updateProcessing(false)
        if settings.autoSpeak, !layeredState.spokenInstant {
            voiceManager?.speak(response)
        }
        currentMode = yolo.isActive ? .yolo : .chat
    }

    private func handleTranscript(_ transcript: String) async {
        await handleInput(transcript)
        if isMicLive {
            speechManager?.startListening()
        }
    }

    private func handleCopilotCommand(_ command: CopilotCommand, sourceText: String) {
        store?.addMessage(role: .user, content: sourceText)

        switch command {
        case .startSession:
            currentMode = .copilot
            do {
                try copilotBridge.startSession()
                updateCopilotSessionState(active: true, status: "Copilot chat live")
                store?.addMessage(role: .system, content: "GitHub Copilot chat session started.")
                speakIfEnabled("Copilot chat is ready.")
            } catch {
                updateCopilotSessionState(active: false, status: "Copilot failed")
                let message = friendlyErrorMessage(for: error, context: "starting Copilot")
                self.error = message
                store?.addMessage(role: .system, content: message)
                speakIfEnabled("Couldn't start Copilot. \(message)")
            }
        case .stopSession:
            copilotBridge.stopSession()
            updateCopilotSessionState(active: false, status: "Copilot offline")
            currentMode = .chat
            store?.addMessage(role: .system, content: "GitHub Copilot chat session stopped.")
            speakIfEnabled("Copilot stopped.")
        case .restartSession:
            currentMode = .copilot
            do {
                try copilotBridge.restartSession()
                updateCopilotSessionState(active: true, status: "Copilot chat live")
                store?.addMessage(role: .system, content: "GitHub Copilot chat session restarted.")
                speakIfEnabled("Copilot restarted.")
            } catch {
                updateCopilotSessionState(active: false, status: "Copilot failed")
                let message = friendlyErrorMessage(for: error, context: "restarting Copilot")
                self.error = message
                store?.addMessage(role: .system, content: message)
                speakIfEnabled("Couldn't restart Copilot. \(message)")
            }
        case .chat(let prompt):
            currentMode = .copilot
            runCopilotChat(prompt: prompt)
        case .suggest(let prompt):
            currentMode = .suggest
            runCopilotOneShot(mode: .suggest, prompt: prompt)
        case .explain(let prompt):
            currentMode = .explain
            runCopilotOneShot(mode: .explain, prompt: prompt)
        }
    }

    private func runCopilotChat(prompt: String) {
        guard let store else { return }

        do {
            if !copilotBridge.isSessionActive {
                try copilotBridge.startSession()
                updateCopilotSessionState(active: true, status: "Copilot chat live")
                store.addMessage(role: .system, content: "GitHub Copilot chat session started.")
            }
        } catch {
            updateCopilotSessionState(active: false, status: "Copilot failed")
            let message = friendlyErrorMessage(for: error, context: "starting Copilot")
            self.error = message
            store.addMessage(role: .system, content: message)
            speakIfEnabled("Couldn't start Copilot. \(message)")
            currentMode = .chat
            return
        }

        let messageID = store.beginStreamingMessage(role: .copilot)
        hasAnnouncedStreaming = false
        updateProcessing(true)
        updateCopilotSessionState(active: true, status: "Copilot thinking")

        do {
            try copilotBridge.sendChat(
                prompt,
                onDelta: { [weak self] delta in
                    guard let self else { return }
                    Task { @MainActor in
                        if !self.hasAnnouncedStreaming, !delta.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            self.hasAnnouncedStreaming = true
                            self.announce("Copilot response streaming")
                        }
                        store.appendToMessage(id: messageID, delta: delta)
                        self.isProcessing = store.isProcessing
                    }
                },
                completion: { [weak self] result in
                    guard let self else { return }
                    Task { @MainActor in
                        self.updateProcessing(false)
                        switch result {
                        case .success(let response):
                            self.updateCopilotSessionState(active: true, status: "Copilot chat live")
                            store.finishStreamingMessage(id: messageID, fallbackContent: response.text)
                            self.speakIfEnabled(self.spokenPreview(for: response.text))
                        case .failure(let error):
                            let isActive = self.copilotBridge.isSessionActive
                            self.updateCopilotSessionState(
                                active: isActive,
                                status: isActive ? "Copilot chat live" : "Copilot offline"
                            )
                            let message = self.friendlyErrorMessage(for: error, context: "Copilot chat")
                            self.error = message
                            store.replaceMessageContent(id: messageID, content: message)
                            self.speakIfEnabled(message)
                            self.currentMode = self.yolo.isActive ? .yolo : .chat
                        }
                    }
                }
            )
        } catch {
            updateProcessing(false)
            let isActive = copilotBridge.isSessionActive
            updateCopilotSessionState(
                active: isActive,
                status: isActive ? "Copilot chat live" : "Copilot offline"
            )
            let message = friendlyErrorMessage(for: error, context: "Copilot chat")
            self.error = message
            store.replaceMessageContent(id: messageID, content: message)
            speakIfEnabled(message)
            currentMode = yolo.isActive ? .yolo : .chat
        }
    }

    private func runCopilotOneShot(mode: CopilotCommandMode, prompt: String) {
        guard let store else { return }

        let messageID = store.beginStreamingMessage(role: .copilot)
        hasAnnouncedStreaming = false
        updateProcessing(true)
        updateCopilotSessionState(
            active: copilotBridge.isSessionActive,
            status: mode == .suggest ? "Copilot suggesting" : "Copilot explaining"
        )

        copilotBridge.executeOneShot(
            mode: mode,
            prompt: prompt,
            onDelta: { [weak self] delta in
                guard let self else { return }
                Task { @MainActor in
                    if !self.hasAnnouncedStreaming, !delta.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                        self.hasAnnouncedStreaming = true
                        self.announce("Copilot response streaming")
                    }
                    store.appendToMessage(id: messageID, delta: delta)
                    self.isProcessing = store.isProcessing
                }
            },
            completion: { [weak self] result in
                guard let self else { return }
                Task { @MainActor in
                    self.updateProcessing(false)
                    switch result {
                    case .success(let response):
                        let isActive = self.copilotBridge.isSessionActive
                        self.updateCopilotSessionState(
                            active: isActive,
                            status: isActive ? "Copilot chat live" : "Copilot ready"
                        )
                        store.finishStreamingMessage(id: messageID, fallbackContent: response.text)
                        self.speakIfEnabled(self.spokenPreview(for: response.text))
                    case .failure(let error):
                        let isActive = self.copilotBridge.isSessionActive
                        self.updateCopilotSessionState(
                            active: isActive,
                            status: isActive ? "Copilot chat live" : "Copilot failed"
                        )
                        let context = mode == .suggest ? "Copilot suggestion" : "Copilot explanation"
                        let message = self.friendlyErrorMessage(for: error, context: context)
                        self.error = message
                        store.replaceMessageContent(id: messageID, content: message)
                        self.speakIfEnabled(message)
                    }
                    self.currentMode = self.yolo.isActive ? .yolo : .chat
                }
            }
        )
    }

    private func setupBindings() {
        guard let speechManager, let store, let settings, let llmRouter else { return }

        cancellables.removeAll()

        speechManager.$currentTranscript
            .sink { [weak self] transcript in
                guard let self else { return }
                Task { @MainActor in
                    self.liveTranscript = transcript
                    if self.isMicLive {
                        self.inputText = transcript
                    }
                }
            }
            .store(in: &cancellables)

        store.$isProcessing
            .sink { [weak self] value in
                guard let self else { return }
                Task { @MainActor in
                    self.isProcessing = value
                }
            }
            .store(in: &cancellables)

        settings.$speechEngine
            .sink { [weak self] engine in
                guard let self else { return }
                Task { @MainActor in
                    self.speechManager?.setEngine(engine)
                }
            }
            .store(in: &cancellables)

        settings.$openAIKey
            .sink { [weak self] openAIKey in
                guard let self else { return }
                Task { @MainActor in
                    self.speechManager?.setOpenAIKey(openAIKey)
                }
            }
            .store(in: &cancellables)

        settings.$voiceOutputEngine
            .sink { [weak self] engine in
                guard let self else { return }
                Task { @MainActor in
                    self.voiceManager?.setOutputEngine(engine)
                }
            }
            .store(in: &cancellables)

        securityManager.$currentRole
            .sink { [weak self] role in
                guard let self else { return }
                Task { @MainActor in
                    guard !self.securityManager.canUseYolo() else { return }
                    let wasActive = self.yolo.isActive || self.llmRouter?.yoloMode == true
                    _ = self.setYoloEnabled(false, announceBlocked: false)
                    guard wasActive else { return }
                    let message = "Security mode switched to \(role.accessibilityName). YOLO mode has been turned off."
                    self.store?.addMessage(role: .system, content: message)
                    self.error = message
                    self.speakIfEnabled(message)
                    self.announce(message)
                }
            }
            .store(in: &cancellables)

        llmRouter.$yoloMode
            .sink { [weak self] enabled in
                guard let self else { return }
                Task { @MainActor in
                    if self.yolo.isActive != enabled {
                        self.setYoloEnabled(enabled)
                    }
                }
            }
            .store(in: &cancellables)

        yolo.$isActive
            .sink { [weak self] active in
                guard let self else { return }
                Task { @MainActor in
                    if self.llmRouter?.yoloMode != active {
                        self.llmRouter?.yoloMode = active
                    }
                    if !active, self.currentMode == .yolo {
                        self.currentMode = .chat
                    }
                }
            }
            .store(in: &cancellables)

        speechManager.onTranscriptFinalized = { [weak self] transcript in
            guard let self else { return }
            Task { [weak self] in
                await self?.handleTranscript(transcript)
            }
        }
    }

    private func applyCurrentSettings() {
        guard let settings, let speechManager else { return }
        voiceManager?.selectVoice(named: settings.voiceName)
        voiceManager?.speechRate = Float(settings.speechRate)
        voiceManager?.setOutputEngine(settings.voiceOutputEngine)
        voiceManager?.refreshEngineStatus()
        speechManager.setEngine(settings.speechEngine)
        speechManager.setOpenAIKey(settings.openAIKey)

        // Route SystemCommands.speak() through VoiceManager so CodeAssistant,
        // YoloMode, and YoloExecutor respect the selected TTS engine.
        if let vm = voiceManager {
            SystemCommands.shared.registerSpeechDelegate { text in
                Task { @MainActor in
                    vm.speak(text)
                }
            }
        }
    }

    private func updateProcessing(_ processing: Bool) {
        if processing, !isProcessing {
            announce("Loading response")
        }
        store?.isProcessing = processing
        isProcessing = processing
    }

    private func speakIfEnabled(_ text: String) {
        // CRITICAL: Joseph is BLIND - always speak responses unless explicitly disabled
        // Log for debugging
        let autoSpeakEnabled = settings?.autoSpeak ?? true
        let hasVoiceManager = voiceManager != nil
        print("🔊 speakIfEnabled: autoSpeak=\(autoSpeakEnabled), hasVoiceManager=\(hasVoiceManager), text=\(text.prefix(50))...")
        
        // Default to speaking if settings not configured (accessibility first)
        guard autoSpeakEnabled else { 
            print("🔇 Speaking disabled by settings")
            return 
        }
        
        if let vm = voiceManager {
            vm.speak(text)
        } else {
            // FALLBACK: Use system speech directly if VoiceManager not available
            print("⚠️ VoiceManager nil, using system fallback")
            speakWithSystemFallback(text)
        }
    }
    
    /// Emergency fallback speech for when VoiceManager is unavailable
    private func speakWithSystemFallback(_ text: String) {
        Task {
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/say")
            process.arguments = ["-v", "Karen", "-r", "180", text]
            try? process.run()
        }
    }

    private func presentSecurityMessage(_ message: String) {
        error = message
        store?.addMessage(role: .system, content: message)
        speakIfEnabled(message)
        announce(message)
    }

    private func normalizeCopilotCommand(_ text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return text }

        let lower = trimmed.lowercased()

        // Normalize coding terminology from speech
        var normalized = trimmed
        let codingTermNormalizations: [(String, String)] = [
            ("curly brace", "{"),
            ("open curly", "{"),
            ("close curly", "}"),
            ("open bracket", "["),
            ("close bracket", "]"),
            ("open paren", "("),
            ("close paren", ")"),
            ("equals sign", "="),
            ("double equals", "=="),
            ("not equals", "!="),
            ("colon", ":"),
            ("semicolon", ";"),
            ("hashtag", "#"),
            ("hash", "#"),
            ("dollar sign", "$"),
            ("at sign", "@"),
            ("ampersand", "&"),
            ("pipe", "|"),
            ("backslash", "\\"),
            ("forward slash", "/"),
            ("underscore", "_"),
            ("new line", "\n"),
            ("tab", "\t"),
        ]

        // Only apply coding term normalization when it looks like code dictation
        if lower.hasPrefix("type ") || lower.hasPrefix("insert ") || lower.hasPrefix("write ") {
            for (spoken, code) in codingTermNormalizations {
                normalized = normalized.replacingOccurrences(of: spoken, with: code, options: .caseInsensitive)
            }
        }

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

        return normalized
    }

    private func spokenPreview(for text: String) -> String {
        let cleaned = text
            .replacingOccurrences(of: "```", with: "")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        // If the response contains code blocks, format for accessible speech
        if text.contains("```") {
            let codeSpeaker = CodeSpeaker()
            let blocks = extractCodeBlocks(from: text)
            if !blocks.isEmpty {
                var parts: [String] = []
                for block in blocks {
                    let lang = block.language ?? "code"
                    let lineCount = block.code.components(separatedBy: "\n").count
                    parts.append("Generated \(lang) block with \(lineCount) lines.")
                    // Read first few lines
                    let preview = block.code.components(separatedBy: "\n").prefix(5)
                    for (i, line) in preview.enumerated() {
                        parts.append(codeSpeaker.formatLine(number: i + 1, content: line))
                    }
                    if lineCount > 5 {
                        parts.append("And \(lineCount - 5) more lines. Say read line to hear more.")
                    }
                }
                return parts.joined(separator: " ")
            }
        }

        return String(cleaned.prefix(400))
    }

    private func extractCodeBlocks(from text: String) -> [(language: String?, code: String)] {
        var blocks: [(language: String?, code: String)] = []
        let lines = text.components(separatedBy: "\n")
        var inBlock = false
        var currentLanguage: String?
        var currentCode: [String] = []

        for line in lines {
            if line.hasPrefix("```") && !inBlock {
                inBlock = true
                let lang = String(line.dropFirst(3)).trimmingCharacters(in: .whitespaces)
                currentLanguage = lang.isEmpty ? nil : lang
                currentCode = []
            } else if line.hasPrefix("```") && inBlock {
                inBlock = false
                let code = currentCode.joined(separator: "\n")
                if !code.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    blocks.append((currentLanguage, code))
                }
                currentLanguage = nil
                currentCode = []
            } else if inBlock {
                currentCode.append(line)
            }
        }

        return blocks
    }

    private func updateCopilotSessionState(active: Bool, status: String) {
        if copilotStatusText != status {
            announce(status)
        }
        isCopilotSessionActive = active
        copilotStatusText = status
    }

    private func announce(_ message: String, priority: Int = 50) {
        guard !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        NSAccessibility.post(
            element: NSApp as Any,
            notification: .announcementRequested,
            userInfo: [
                .announcement: message,
                .priority: priority
            ]
        )
    }

    private func friendlyErrorMessage(for error: Error, context: String) -> String {
        let raw = error.localizedDescription
        if raw.contains("401") || raw.contains("Unauthorized") || raw.contains("API key") {
            return "Couldn't complete \(context): the API key appears to be invalid or missing. Check the API tab in Settings."
        }
        if raw.contains("429") || raw.contains("rate limit") || raw.contains("quota") {
            return "Couldn't complete \(context): you've reached the rate limit. Please wait a moment and try again."
        }
        if raw.contains("timeout") || raw.contains("timed out") {
            return "Couldn't complete \(context): the request timed out. Check your internet connection and try again."
        }
        if raw.contains("offline") || raw.contains("network") || raw.contains("connection") {
            return "Couldn't complete \(context): no network connection. Check your Wi-Fi or cable and try again."
        }
        if raw.contains("not found") || raw.contains("404") {
            return "Couldn't complete \(context): the AI service wasn't found. It may be down or the URL may be wrong."
        }
        return "Couldn't complete \(context). Please try again, or check the Settings if the problem continues."
    }
}
