// CopilotIntegration.swift — Extends TerminalChatController and AppDelegate
// with GitHub Copilot CLI integration via GHCopilotBridge.
//
// Merged into BrainChat.swift at build time as a single compilation unit.

private let _sharedCopilotBridge = GHCopilotBridge()

// MARK: - TerminalChatController + Copilot

extension TerminalChatController {

    /// Routes copilot commands. Returns true if handled. Call at top of processInput.
    func tryHandleCopilotInput(_ text: String) -> Bool {
        guard let cmd = GHCopilotBridge.parseCommand(text) else { return false }
        _terminalHandleCopilotCommand(cmd)
        return true
    }

    func cleanupCopilotSession() { _sharedCopilotBridge.endSession() }

    private func _terminalHandleCopilotCommand(_ command: GHCopilotBridge.CopilotCommand) {
        let bridge = _sharedCopilotBridge

        // Helper closures to abstract the output API.
        // These access private members which is allowed in the same file.
        let speak: (String) -> Void = { [weak self] text in
            DispatchQueue.main.async { self?.speaker.speak(text) }
        }
        let output: (String, String, String) -> Void = { [weak self] prefix, text, color in
            self?.writeTranscriptLine(prefix: prefix, text: text, color: color)
        }
        let status: (String) -> Void = { [weak self] text in
            self?.writeStatus(text)
        }
        let prompt: () -> Void = { [weak self] in self?.renderPrompt() }

        switch command {
        case .startSession:
            status("Starting Copilot chat session\u{2026}")
            do {
                try bridge.startSession(mode: .chat)
                let msg = "Copilot chat session started. Use /copilot followed by your message."
                output("Copilot", msg, TerminalANSI.magenta)
                speak(msg); status("Copilot session active.")
            } catch {
                output("Copilot", error.localizedDescription, TerminalANSI.yellow)
            }
            prompt()

        case .stopSession:
            bridge.endSession()
            output("Copilot", "Copilot session ended.", TerminalANSI.magenta)
            speak("Copilot session ended."); status("Ready."); prompt()

        case .restartSession:
            do {
                try bridge.restartSession()
                output("Copilot", "Copilot session restarted.", TerminalANSI.magenta)
                speak("Copilot session restarted.")
            } catch {
                output("Copilot", error.localizedDescription, TerminalANSI.yellow)
            }
            prompt()

        case .chat(let userPrompt):
            output("You (Copilot)", userPrompt, TerminalANSI.cyan)
            if bridge.isSessionActive {
                status("Sending to Copilot\u{2026}")
                streamPrefixShown = false
                bridge.onToken = { [weak self] token in
                    self?.uiQueue.async {
                        guard let self else { return }
                        if !self.streamPrefixShown {
                            self.streamPrefixShown = true
                            if self.promptVisible {
                                self.writeRaw("\r" + (self.richTTYEnabled ? TerminalANSI.clearLine : ""))
                                self.promptVisible = false
                            }
                            self.writeRaw(self.colorize("Copilot> ", color: TerminalANSI.magenta + TerminalANSI.bold))
                        }
                        self.writeRaw(ANSIText.strip(token))
                    }
                }
                bridge.onComplete = { [weak self] fullText, _ in
                    self?.uiQueue.async {
                        guard let self else { return }
                        self.writeRaw("\r\n")
                        self.writeStatus("Ready."); self.streamPrefixShown = false
                        if !fullText.isEmpty { speak(fullText) }
                        self.renderPrompt()
                    }
                }
                do { try bridge.sendChat(userPrompt) } catch {
                    output("Copilot", error.localizedDescription, TerminalANSI.yellow); prompt()
                }
            } else {
                status("Running Copilot one-shot\u{2026}")
                bridge.executeOneShot(mode: .chat, prompt: userPrompt) { [weak self] result in
                    self?.uiQueue.async {
                        switch result {
                        case .success(let text): output("Copilot", text, TerminalANSI.magenta); speak(text)
                        case .failure(let e): output("Copilot", e.localizedDescription, TerminalANSI.yellow)
                        }
                        status("Ready."); prompt()
                    }
                }
            }

        case .suggest(let userPrompt):
            output("You (Suggest)", userPrompt, TerminalANSI.cyan)
            status("Running Copilot suggest\u{2026}")
            bridge.executeOneShot(mode: .suggest, prompt: userPrompt) { [weak self] result in
                self?.uiQueue.async {
                    switch result {
                    case .success(let text): output("Copilot", text, TerminalANSI.magenta); speak(text)
                    case .failure(let e): output("Copilot", e.localizedDescription, TerminalANSI.yellow)
                    }
                    status("Ready."); prompt()
                }
            }

        case .explain(let userPrompt):
            output("You (Explain)", userPrompt, TerminalANSI.cyan)
            status("Running Copilot explain\u{2026}")
            bridge.executeOneShot(mode: .explain, prompt: userPrompt) { [weak self] result in
                self?.uiQueue.async {
                    switch result {
                    case .success(let text): output("Copilot", text, TerminalANSI.magenta); speak(text)
                    case .failure(let e): output("Copilot", e.localizedDescription, TerminalANSI.yellow)
                    }
                    status("Ready."); prompt()
                }
            }
        }
    }
}

// MARK: - AppDelegate + Copilot

extension AppDelegate {

    func tryHandleCopilotInput(_ text: String) -> Bool {
        guard let cmd = GHCopilotBridge.parseCommand(text) else { return false }
        _guiHandleCopilotCommand(cmd)
        return true
    }

    func cleanupCopilotSession() { _sharedCopilotBridge.endSession() }

    private func _guiHandleCopilotCommand(_ command: GHCopilotBridge.CopilotCommand) {
        let bridge = _sharedCopilotBridge
        switch command {
        case .startSession:
            do {
                try bridge.startSession(mode: .chat)
                speakAndLog("Copilot chat session started. Use /copilot followed by your message.", speaker: "Copilot")
                updateStatus("Copilot session active.")
            } catch {
                speakAndLog("Could not start Copilot: \(error.localizedDescription)", speaker: "Copilot")
            }

        case .stopSession:
            bridge.endSession()
            speakAndLog("Copilot session ended.", speaker: "Copilot")
            updateStatus("Ready. Press Enter to talk.")

        case .restartSession:
            do {
                try bridge.restartSession()
                speakAndLog("Copilot session restarted.", speaker: "Copilot")
            } catch {
                speakAndLog("Could not restart: \(error.localizedDescription)", speaker: "Copilot")
            }

        case .chat(let prompt):
            appendTranscript(speaker: "You (Copilot)", text: prompt)
            if bridge.isSessionActive {
                updateStatus("Sending to Copilot\u{2026}")
                bridge.onComplete = { [weak self] fullText, error in
                    guard let self else { return }
                    if let error {
                        self.speakAndLog("Copilot error: \(error.localizedDescription)", speaker: "Copilot")
                    } else if !fullText.isEmpty {
                        self.appendTranscript(speaker: "Copilot", text: fullText)
                        self.speaker.speak(fullText)
                    }
                    self.updateStatus("Ready. Press Enter to talk.")
                }
                do { try bridge.sendChat(prompt) } catch {
                    speakAndLog("Error: \(error.localizedDescription)", speaker: "Copilot")
                }
            } else {
                updateStatus("Running Copilot one-shot\u{2026}")
                bridge.executeOneShot(mode: .chat, prompt: prompt) { [weak self] result in
                    guard let self else { return }
                    switch result {
                    case .success(let text):
                        self.appendTranscript(speaker: "Copilot", text: text)
                        self.speaker.speak(text)
                    case .failure(let error):
                        self.speakAndLog("Copilot failed: \(error.localizedDescription)", speaker: "Copilot")
                    }
                    self.updateStatus("Ready. Press Enter to talk.")
                }
            }

        case .suggest(let prompt):
            appendTranscript(speaker: "You (Suggest)", text: prompt)
            updateStatus("Running Copilot suggest\u{2026}")
            bridge.executeOneShot(mode: .suggest, prompt: prompt) { [weak self] result in
                guard let self else { return }
                switch result {
                case .success(let text): self.appendTranscript(speaker: "Copilot", text: text); self.speaker.speak(text)
                case .failure(let error): self.speakAndLog("Suggest failed: \(error.localizedDescription)", speaker: "Copilot")
                }
                self.updateStatus("Ready. Press Enter to talk.")
            }

        case .explain(let prompt):
            appendTranscript(speaker: "You (Explain)", text: prompt)
            updateStatus("Running Copilot explain\u{2026}")
            bridge.executeOneShot(mode: .explain, prompt: prompt) { [weak self] result in
                guard let self else { return }
                switch result {
                case .success(let text): self.appendTranscript(speaker: "Copilot", text: text); self.speaker.speak(text)
                case .failure(let error): self.speakAndLog("Explain failed: \(error.localizedDescription)", speaker: "Copilot")
                }
                self.updateStatus("Ready. Press Enter to talk.")
            }
        }
    }
}
