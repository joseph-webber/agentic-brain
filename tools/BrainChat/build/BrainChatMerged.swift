import Foundation

// MARK: - GitHub Copilot Bridge

/// Manages interactive `gh copilot` CLI sessions via PTY subprocess.
///
/// Supports three modes:
///   - `.chat`    → `gh copilot chat` (interactive session, persistent)
///   - `.suggest` → one-shot suggestion via copilot binary or `gh copilot suggest`
///   - `.explain` → one-shot explanation via copilot binary or `gh copilot explain`
///
/// Uses a PTY so the copilot CLI believes it has a real terminal,
/// which is required for its interactive ANSI output.
final class GHCopilotBridge {

    enum CopilotMode: String, CaseIterable {
        case chat    = "chat"
        case suggest = "suggest"
        case explain = "explain"
    }

    enum BridgeError: Error, LocalizedError {
        case ghNotFound
        case sessionNotRunning
        case spawnFailed(String)
        case timeout

        var errorDescription: String? {
            switch self {
            case .ghNotFound:         return "gh CLI not found. Install with: brew install gh"
            case .sessionNotRunning:  return "No copilot session is running."
            case .spawnFailed(let m): return "Failed to spawn copilot: \(m)"
            case .timeout:            return "Copilot response timed out."
            }
        }
    }

    /// Callback with each chunk of cleaned response text (main thread).
    var onToken: ((String) -> Void)?
    /// Callback when a full response is assembled (main thread).
    var onComplete: ((String, Error?) -> Void)?

    private(set) var isSessionActive = false
    private(set) var currentMode: CopilotMode = .chat

    private let processQueue = DispatchQueue(label: "brainchat.copilot.bridge")
    private var chatProcess: Process?
    private var masterFD: Int32 = -1
    private var readChannel: DispatchIO?
    private var responseBuffer = ""
    private var isWaitingForResponse = false

    private static let ghPath: String? = {
        let candidates = ["/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/usr/bin/gh"]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }()

    private static let copilotBinPath: String? = {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        let candidates = [
            "\(home)/.local/bin/copilot",
            "/usr/local/bin/copilot",
        ]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
    }()

    var isAvailable: Bool { Self.ghPath != nil || Self.copilotBinPath != nil }

    private static var pathExtension: [String] {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        return ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin"]
    }

    // MARK: - Session Lifecycle

    /// Starts an interactive `gh copilot chat` session with a PTY.
    func startSession(mode: CopilotMode = .chat) throws {
        endSession()
        currentMode = mode
        guard mode == .chat else { return }
        guard let gh = Self.ghPath else { throw BridgeError.ghNotFound }

        var masterDescriptor: Int32 = -1
        var slaveDescriptor: Int32 = -1
        guard openpty(&masterDescriptor, &slaveDescriptor, nil, nil, nil) == 0 else {
            throw BridgeError.spawnFailed(String(cString: strerror(errno)))
        }
        masterFD = masterDescriptor

        // Set a reasonable terminal size so copilot doesn't wrap oddly.
        var winSize = winsize(ws_row: 50, ws_col: 120, ws_xpixel: 0, ws_ypixel: 0)
        _ = ioctl(masterDescriptor, TIOCSWINSZ, &winSize)

        let process = Process()
        process.executableURL = URL(fileURLWithPath: gh)
        process.arguments = ["copilot", "chat"]

        var env = ProcessInfo.processInfo.environment
        env["PATH"] = (Self.pathExtension + [env["PATH"] ?? "/usr/bin:/bin"]).joined(separator: ":")
        env["TERM"] = "xterm-256color"
        env.removeValue(forKey: "NO_COLOR")
        process.environment = env

        let slaveHandle = FileHandle(fileDescriptor: slaveDescriptor, closeOnDealloc: true)
        process.standardInput  = slaveHandle
        process.standardOutput = slaveHandle
        process.standardError  = slaveHandle

        process.terminationHandler = { [weak self] _ in
            self?.processQueue.async { self?.handleTermination() }
        }

        do {
            try process.run()
        } catch {
            closeMaster()
            throw BridgeError.spawnFailed(error.localizedDescription)
        }

        chatProcess = process
        isSessionActive = true
        beginReadLoop()
    }

    /// Ends the current copilot session.
    func endSession() {
        readChannel?.close(flags: .stop)
        readChannel = nil
        if let p = chatProcess, p.isRunning {
            let quitData = Data("/quit\n".utf8)
            _ = quitData.withUnsafeBytes { Darwin.write(masterFD, $0.baseAddress!, $0.count) }
            usleep(200_000)
            if p.isRunning { p.terminate() }
        }
        chatProcess = nil
        closeMaster()
        isSessionActive = false
        responseBuffer = ""
        isWaitingForResponse = false
    }

    /// Restarts the interactive session.
    func restartSession() throws {
        endSession()
        try startSession(mode: currentMode)
    }

    // MARK: - Sending Messages

    /// Sends a message to the running copilot chat session.
    func sendChat(_ message: String) throws {
        guard isSessionActive, masterFD >= 0 else { throw BridgeError.sessionNotRunning }
        responseBuffer = ""
        isWaitingForResponse = true

        let payload = Data((message + "\n").utf8)
        payload.withUnsafeBytes { buf in
            _ = Darwin.write(masterFD, buf.baseAddress!, buf.count)
        }
    }

    /// Runs a one-shot copilot command (suggest/explain) and calls `completion` on main.
    func executeOneShot(mode: CopilotMode, prompt: String,
                        timeout: TimeInterval = 60,
                        completion: @escaping (Result<String, Error>) -> Void) {
        processQueue.async {
            let process = Process()
            let stdoutPipe = Pipe()
            let stderrPipe = Pipe()

            // Prefer standalone copilot binary; fall back to gh copilot.
            if let copilotBin = Self.copilotBinPath {
                process.executableURL = URL(fileURLWithPath: copilotBin)
                process.arguments = ["-p", prompt, "--output-format", "text"]
            } else if let gh = Self.ghPath {
                process.executableURL = URL(fileURLWithPath: gh)
                process.arguments = ["copilot", mode.rawValue, "--", prompt]
            } else {
                DispatchQueue.main.async { completion(.failure(BridgeError.ghNotFound)) }
                return
            }

            process.standardOutput = stdoutPipe
            process.standardError  = stderrPipe

            var env = ProcessInfo.processInfo.environment
            env["PATH"] = (Self.pathExtension + [env["PATH"] ?? "/usr/bin:/bin"]).joined(separator: ":")
            env["TERM"] = "dumb"
            process.environment = env

            do {
                try process.run()
            } catch {
                DispatchQueue.main.async {
                    completion(.failure(BridgeError.spawnFailed(error.localizedDescription)))
                }
                return
            }

            let semaphore = DispatchSemaphore(value: 0)
            var didTimeout = false

            DispatchQueue.global().async {
                process.waitUntilExit()
                semaphore.signal()
            }

            if semaphore.wait(timeout: .now() + timeout) == .timedOut {
                didTimeout = true
                process.terminate()
                usleep(200_000)
                if process.isRunning { process.interrupt() }
            }

            let stdout = String(
                data: stdoutPipe.fileHandleForReading.readDataToEndOfFile(),
                encoding: .utf8
            )?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let stderr = String(
                data: stderrPipe.fileHandleForReading.readDataToEndOfFile(),
                encoding: .utf8
            )?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

            DispatchQueue.main.async {
                if didTimeout {
                    completion(.failure(BridgeError.timeout))
                } else if process.terminationStatus != 0 {
                    let msg = stderr.isEmpty
                        ? "Exit code \(process.terminationStatus)"
                        : stderr
                    completion(.failure(BridgeError.spawnFailed(msg)))
                } else {
                    let clean = ANSIText.strip(stdout)
                    completion(.success(clean.isEmpty ? "(no output)" : clean))
                }
            }
        }
    }

    // MARK: - PTY Read Loop

    private func beginReadLoop() {
        guard masterFD >= 0 else { return }

        let channel = DispatchIO(
            type: .stream,
            fileDescriptor: masterFD,
            queue: processQueue
        ) { [weak self] _ in
            self?.closeMaster()
        }
        channel.setLimit(lowWater: 1)
        readChannel = channel

        channel.read(offset: 0, length: Int.max, queue: processQueue) {
            [weak self] done, dispatchData, error in
            guard let self else { return }

            if let dispatchData, !dispatchData.isEmpty {
                let chunk = String(decoding: Data(dispatchData), as: UTF8.self)
                let clean = ANSIText.strip(chunk)
                if !clean.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    self.responseBuffer += clean
                    DispatchQueue.main.async { self.onToken?(clean) }
                }
            }

            if error != 0 || done {
                if self.isWaitingForResponse {
                    self.isWaitingForResponse = false
                    let finalText = self.responseBuffer
                        .trimmingCharacters(in: .whitespacesAndNewlines)
                    self.responseBuffer = ""
                    DispatchQueue.main.async { self.onComplete?(finalText, nil) }
                }
                if done { self.readChannel = nil }
            }
        }

        scheduleResponseFlush()
    }

    /// Waits for copilot output to settle, then delivers the accumulated buffer.
    private func scheduleResponseFlush() {
        processQueue.asyncAfter(deadline: .now() + 2.0) { [weak self] in
            guard let self, self.isSessionActive else { return }
            if self.isWaitingForResponse, !self.responseBuffer.isEmpty {
                self.isWaitingForResponse = false
                let finalText = self.responseBuffer
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                self.responseBuffer = ""
                DispatchQueue.main.async { self.onComplete?(finalText, nil) }
            }
            if self.isSessionActive { self.scheduleResponseFlush() }
        }
    }

    private func handleTermination() {
        isSessionActive = false
        if isWaitingForResponse {
            isWaitingForResponse = false
            let text = responseBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            responseBuffer = ""
            DispatchQueue.main.async { [weak self] in
                self?.onComplete?(text, text.isEmpty ? BridgeError.sessionNotRunning : nil)
            }
        }
    }

    private func closeMaster() {
        guard masterFD >= 0 else { return }
        Darwin.close(masterFD)
        masterFD = -1
    }

    deinit { endSession() }

    // MARK: - Command Parsing

    /// Parses user input to detect copilot commands.
    ///
    /// Supported prefixes:
    ///   - `/copilot <message>`   - chat mode
    ///   - `/suggest <prompt>`    - suggest mode (one-shot)
    ///   - `/explain <prompt>`    - explain mode (one-shot)
    ///   - `/copilot-start`       - start persistent chat session
    ///   - `/copilot-stop`        - end the session
    ///   - `/copilot-restart`     - restart the session
    enum CopilotCommand {
        case chat(String)
        case suggest(String)
        case explain(String)
        case startSession
        case stopSession
        case restartSession
    }

    static func parseCommand(_ input: String) -> CopilotCommand? {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowered = trimmed.lowercased()

        if lowered == "/copilot-start" || lowered == "/copilot start" {
            return .startSession
        }
        if lowered == "/copilot-stop" || lowered == "/copilot stop" {
            return .stopSession
        }
        if lowered == "/copilot-restart" || lowered == "/copilot restart" {
            return .restartSession
        }

        let prefixes: [(String, (String) -> CopilotCommand)] = [
            ("/copilot ",  { .chat($0) }),
            ("/suggest ",  { .suggest($0) }),
            ("/explain ",  { .explain($0) }),
        ]
        for (prefix, factory) in prefixes {
            if lowered.hasPrefix(prefix) {
                let prompt = String(trimmed.dropFirst(prefix.count))
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                guard !prompt.isEmpty else { return nil }
                return factory(prompt)
            }
        }
        return nil
    }
}

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

import Cocoa
import Speech
import AVFoundation
import Darwin

struct BridgeResponse {
    let text: String
    let requestID: String?
    let isPartial: Bool
    let isFinal: Bool
    let containsANSI: Bool

    init(text: String, requestID: String?, isPartial: Bool = false, isFinal: Bool = true) {
        self.text = text
        self.requestID = requestID
        self.isPartial = isPartial
        self.isFinal = isFinal
        self.containsANSI = text.contains("\u{001B}")
    }
}

final class ANSIText {
    private static let ansiRegex = try? NSRegularExpression(pattern: "\\u{001B}\\[[0-9;?]*[ -/]*[@-~]", options: [])

    static func strip(_ text: String) -> String {
        guard let ansiRegex else { return text }
        let range = NSRange(text.startIndex..., in: text)
        return ansiRegex.stringByReplacingMatches(in: text, options: [], range: range, withTemplate: "")
    }
}

final class LocalFallbackResponder {
    private let formatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .full
        formatter.timeStyle = .short
        formatter.locale = Locale(identifier: "en_AU")
        return formatter
    }()

    func response(for input: String, reason: String?) -> String {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowercased = trimmed.lowercased()
        let prefix = reason.map { "Redpanda is unavailable right now (\($0)). " } ?? "Using local fallback mode. "

        if lowercased.contains("time") || lowercased.contains("date") {
            return prefix + "The current local time is \(formatter.string(from: Date()))."
        }

        if lowercased.contains("status") || lowercased.contains("are you there") {
            return prefix + "Brain Chat is ready for voice commands and can keep listening locally until the backend reconnects."
        }

        if lowercased.contains("hello") || lowercased.contains("hi") || lowercased.contains("hey") {
            return prefix + "Hello Joseph. I heard \"\(trimmed)\"."
        }

        if trimmed.isEmpty {
            return prefix + "I did not catch any words. Please try again."
        }

        return prefix + "I heard \"\(trimmed)\". Once Redpanda comes back, I will send your request to the wider brain."
    }
}

final class SpeechVoice {
    private let synthesizer = AVSpeechSynthesizer()

    init() {}

    func speak(_ text: String) {
        let cleanText = ANSIText.strip(text)
        guard !cleanText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }

        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }

        let utterance = AVSpeechUtterance(string: cleanText)
        utterance.rate = 0.48
        utterance.voice = Self.preferredVoice()
        synthesizer.speak(utterance)
    }

    private static func preferredVoice() -> AVSpeechSynthesisVoice? {
        let voices = AVSpeechSynthesisVoice.speechVoices()
        if let karen = voices.first(where: { $0.name.localizedCaseInsensitiveContains("Karen") && $0.language.hasPrefix("en-AU") }) {
            return karen
        }
        return voices.first(where: { $0.language.hasPrefix("en-AU") })
    }
}

final class RedpandaBridge: NSObject {
    enum Availability {
        case connected
        case unavailable(String)
    }

    var onAvailabilityChanged: ((Availability) -> Void)?
    var onResponse: ((BridgeResponse) -> Void)?

    private let bootstrapServers = "localhost:9092"
    private let inputTopic = "brain.voice.input"
    private let responseTopic = "brain.voice.response"
    private let clientID = "brain-chat-macos-swift"
    private let consumerQueue = DispatchQueue(label: "brainchat.consumer.pty")

    private var consumerProcess: Process?
    private var consumerReadChannel: DispatchIO?
    private var consumerMasterFD: Int32 = -1
    private var consumerSlaveHandle: FileHandle?
    private var consumerBuffer = ""

    func start() {
        guard consumerProcess == nil else { return }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = ["-u", "-c", consumerScript]
        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        environment["BRAINCHAT_BROKERS"] = bootstrapServers
        environment["BRAINCHAT_RESPONSE_TOPIC"] = responseTopic
        environment["BRAINCHAT_CLIENT_ID"] = clientID
        process.environment = environment

        do {
            try prepareConsumerPTY()
            process.standardOutput = consumerSlaveHandle
            process.standardError = consumerSlaveHandle
            process.terminationHandler = { [weak self] process in
                self?.handleConsumerTermination(status: process.terminationStatus)
            }
            try process.run()
            consumerProcess = process
            beginConsumerReadLoop()
        } catch {
            cleanupConsumerResources()
            onAvailabilityChanged?(.unavailable(error.localizedDescription))
        }
    }

    func stop() {
        consumerReadChannel?.close(flags: .stop)
        consumerReadChannel = nil
        consumerProcess?.terminate()
        consumerProcess = nil
        cleanupConsumerResources()
    }

    func publish(text: String, requestID: String, completion: @escaping (Bool, String?) -> Void) {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = ["-c", producerScript, requestID, clientID, text]
        var environment = ProcessInfo.processInfo.environment
        environment["BRAINCHAT_BROKERS"] = bootstrapServers
        environment["BRAINCHAT_INPUT_TOPIC"] = inputTopic
        process.environment = environment

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        process.terminationHandler = { process in
            let outData = stdout.fileHandleForReading.readDataToEndOfFile()
            let errData = stderr.fileHandleForReading.readDataToEndOfFile()
            let outText = String(data: outData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let errText = String(data: errData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

            DispatchQueue.main.async {
                if process.terminationStatus == 0 {
                    completion(true, nil)
                } else {
                    let message = Self.extractError(from: outText) ?? Self.extractError(from: errText) ?? "Could not publish to Redpanda"
                    completion(false, message)
                }
            }
        }

        do {
            try process.run()
        } catch {
            completion(false, error.localizedDescription)
        }
    }

    private func prepareConsumerPTY() throws {
        cleanupConsumerResources()

        var masterFD: Int32 = -1
        var slaveFD: Int32 = -1
        guard openpty(&masterFD, &slaveFD, nil, nil, nil) == 0 else {
            throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno), userInfo: [NSLocalizedDescriptionKey: String(cString: strerror(errno))])
        }

        consumerMasterFD = masterFD
        consumerSlaveHandle = FileHandle(fileDescriptor: slaveFD, closeOnDealloc: true)
    }

    private func beginConsumerReadLoop() {
        guard consumerMasterFD >= 0 else { return }

        let channel = DispatchIO(type: .stream, fileDescriptor: consumerMasterFD, queue: consumerQueue) { [weak self] _ in
            self?.closeConsumerMasterFD()
        }
        channel.setLimit(lowWater: 1)
        channel.setLimit(highWater: 1)
        consumerReadChannel = channel

        channel.read(offset: 0, length: Int.max, queue: consumerQueue) { [weak self] done, dispatchData, error in
            guard let self else { return }

            if let dispatchData, !dispatchData.isEmpty {
                self.handleConsumerData(Data(dispatchData))
            }

            if error != 0 {
                DispatchQueue.main.async {
                    self.onAvailabilityChanged?(.unavailable(String(cString: strerror(error))))
                }
            }

            if done {
                self.consumerReadChannel = nil
            }
        }
    }

    private func handleConsumerData(_ data: Data) {
        let chunk = String(decoding: data, as: UTF8.self)
        consumerBuffer += chunk
        let lines = consumerBuffer.components(separatedBy: "\n")
        consumerBuffer = lines.last ?? ""

        for line in lines.dropLast() {
            handleLine(line)
        }
    }

    private func handleConsumerTermination(status: Int32) {
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.consumerProcess = nil
            if status != 0 {
                self.onAvailabilityChanged?(.unavailable("consumer exited with status \(status)"))
            }
        }
    }

    private func cleanupConsumerResources() {
        consumerSlaveHandle?.closeFile()
        consumerSlaveHandle = nil
        closeConsumerMasterFD()
        consumerBuffer = ""
    }

    private func closeConsumerMasterFD() {
        guard consumerMasterFD >= 0 else { return }
        close(consumerMasterFD)
        consumerMasterFD = -1
    }

    private func handleLine(_ rawLine: String) {
        let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !line.isEmpty else { return }

        if line.hasPrefix("__STATUS__:") {
            let payload = String(line.dropFirst("__STATUS__:".count))
            if let data = payload.data(using: .utf8),
               let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
               let state = object["state"] as? String {
                if state == "connected" {
                    onAvailabilityChanged?(.connected)
                } else {
                    let reason = object["reason"] as? String ?? "Redpanda unavailable"
                    onAvailabilityChanged?(.unavailable(reason))
                }
            }
            return
        }

        if let response = Self.parseResponse(from: line) {
            onResponse?(response)
        }
    }

    private static func parseResponse(from raw: String) -> BridgeResponse? {
        guard let data = raw.data(using: .utf8) else {
            return BridgeResponse(text: raw, requestID: nil)
        }

        guard let object = try? JSONSerialization.jsonObject(with: data) else {
            return BridgeResponse(text: raw, requestID: nil)
        }

        if let dictionary = object as? [String: Any] {
            let requestID = firstString(in: dictionary, keys: ["request_id", "requestId", "correlation_id", "correlationId", "id"])
            let isPartial = dictionary["partial"] as? Bool
                ?? dictionary["streaming"] as? Bool
                ?? dictionary["stream"] as? Bool
                ?? dictionary["is_partial"] as? Bool
                ?? (dictionary["delta"] != nil || dictionary["chunk"] != nil)
            let isFinal = dictionary["final"] as? Bool
                ?? dictionary["done"] as? Bool
                ?? dictionary["is_final"] as? Bool
                ?? !isPartial
            let text = extractResponseText(from: dictionary)
            return text.map {
                BridgeResponse(text: $0, requestID: requestID, isPartial: isPartial, isFinal: isFinal)
            }
        }

        if let array = object as? [Any] {
            let combined = array.compactMap { item -> String? in
                if let text = item as? String { return text }
                if let dict = item as? [String: Any] { return extractResponseText(from: dict) }
                return nil
            }.joined(separator: "\n")
            return combined.isEmpty ? nil : BridgeResponse(text: combined, requestID: nil)
        }

        return BridgeResponse(text: raw, requestID: nil)
    }

    private static func extractResponseText(from dictionary: [String: Any]) -> String? {
        for key in ["delta", "chunk", "text", "response", "message", "content"] {
            if let value = dictionary[key] as? String, !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                return value
            }
            if let nested = dictionary[key] as? [String: Any], let nestedText = extractResponseText(from: nested) {
                return nestedText
            }
        }
        return nil
    }

    private static func firstString(in dictionary: [String: Any], keys: [String]) -> String? {
        for key in keys {
            if let value = dictionary[key] as? String, !value.isEmpty {
                return value
            }
        }
        return nil
    }

    private static func extractError(from raw: String) -> String? {
        guard !raw.isEmpty else { return nil }
        if let data = raw.data(using: .utf8),
           let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let reason = object["reason"] as? String {
            return reason
        }
        return raw
    }

    private var producerScript: String {
        #"""
import json
import os
import sys
from datetime import datetime, timezone

try:
    from kafka import KafkaProducer
except Exception as exc:
    print(json.dumps({"ok": False, "reason": f"kafka-python unavailable: {exc}"}))
    sys.exit(2)

request_id = sys.argv[1]
client_id = sys.argv[2]
text = sys.argv[3]
bootstrap = os.environ.get("BRAINCHAT_BROKERS", "localhost:9092")
topic = os.environ.get("BRAINCHAT_INPUT_TOPIC", "brain.voice.input")

payload = {
    "request_id": request_id,
    "client_id": client_id,
    "source": "brain-chat",
    "platform": "macOS",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "text": text,
}

try:
    producer = KafkaProducer(
        bootstrap_servers=bootstrap,
        value_serializer=lambda value: json.dumps(value).encode("utf-8"),
        retries=1,
        acks="all",
    )
    future = producer.send(topic, payload)
    future.get(timeout=5)
    producer.flush(timeout=5)
    producer.close()
    print(json.dumps({"ok": True}))
except Exception as exc:
    print(json.dumps({"ok": False, "reason": str(exc)}))
    sys.exit(1)
"""#
    }

    private var consumerScript: String {
        #"""
import json
import os
import sys
import time

bootstrap = os.environ.get("BRAINCHAT_BROKERS", "localhost:9092")
topic = os.environ.get("BRAINCHAT_RESPONSE_TOPIC", "brain.voice.response")
client_id = os.environ.get("BRAINCHAT_CLIENT_ID", "brain-chat-macos-swift")

try:
    from kafka import KafkaConsumer
except Exception as exc:
    print("__STATUS__:" + json.dumps({"state": "unavailable", "reason": f"kafka-python unavailable: {exc}"}), flush=True)
    sys.exit(2)

while True:
    consumer = None
    try:
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=bootstrap,
            client_id=client_id,
            group_id=f"{client_id}-responses",
            auto_offset_reset="latest",
            enable_auto_commit=True,
            consumer_timeout_ms=1000,
            value_deserializer=lambda value: value.decode("utf-8"),
        )
        consumer.topics()
        print("__STATUS__:" + json.dumps({"state": "connected"}), flush=True)

        while True:
            for message in consumer:
                print(message.value, flush=True)
    except Exception as exc:
        print("__STATUS__:" + json.dumps({"state": "unavailable", "reason": str(exc)}), flush=True)
        time.sleep(3)
    finally:
        if consumer is not None:
            try:
                consumer.close()
            except Exception:
                pass
"""#
    }
}

enum TerminalANSI {
    static let escape = "\u{001B}["
    static let reset = escape + "0m"
    static let bold = escape + "1m"
    static let dim = escape + "2m"
    static let red = escape + "31m"
    static let green = escape + "32m"
    static let yellow = escape + "33m"
    static let blue = escape + "34m"
    static let magenta = escape + "35m"
    static let cyan = escape + "36m"
    static let white = escape + "37m"
    static let clearLine = escape + "2K"
    static let saveCursor = escape + "s"
    static let restoreCursor = escape + "u"
    static let hideCursor = escape + "?25l"
    static let showCursor = escape + "?25h"
}

// MARK: - Chat Modes

enum ChatMode: String, CaseIterable {
    case chat     = "chat"
    case code     = "code"
    case terminal = "terminal"
    case yolo     = "yolo"
    case voice    = "voice"
    case work     = "work"

    var displayName: String {
        switch self {
        case .chat:     return "Chat"
        case .code:     return "Code"
        case .terminal: return "Terminal"
        case .yolo:     return "YOLO"
        case .voice:    return "Voice"
        case .work:     return "Work"
        }
    }

    var switchCommand: String { "/\(rawValue)" }

    var promptANSIColor: String {
        switch self {
        case .chat:     return TerminalANSI.cyan
        case .code:     return TerminalANSI.yellow
        case .terminal: return TerminalANSI.magenta
        case .yolo:     return TerminalANSI.red
        case .voice:    return TerminalANSI.green
        case .work:     return TerminalANSI.blue
        }
    }

    var systemPrompt: String {
        switch self {
        case .chat:     return "You are Iris Lumina, a concise AI assistant for Joseph (blind, VoiceOver user). Be brief and clear."
        case .code:     return "You are an expert coding assistant. Use triple-backtick code blocks with language names. Support: explain, suggest, fix."
        case .terminal: return "You are a macOS terminal expert. Provide exact shell commands, one sentence explanation each."
        case .yolo:     return "You are an autonomous task executor. List all steps, flag destructive operations before proceeding."
        case .voice:    return "You respond to voice commands. Max 2 sentences. No markdown or code blocks. Speak naturally."
        case .work:     return "You are a professional CITB development assistant. Be formal. Help with JIRA, PRs, and technical docs."
        }
    }

    var llmModel: String {
        switch self {
        case .chat, .terminal, .voice: return "llama3.2:3b"
        case .code, .yolo, .work:      return "llama3.1:8b"
        }
    }

    var speaksResponses: Bool {
        switch self {
        case .chat, .voice, .work:    return true
        case .code, .terminal, .yolo: return false
        }
    }

    var modeDescription: String {
        switch self {
        case .chat:     return "General conversation with voice responses"
        case .code:     return "Code assistance (explain / suggest / fix)"
        case .terminal: return "Shell command help — prefix ! to execute"
        case .yolo:     return "Autonomous task execution via brain.yolo.commands"
        case .voice:    return "Short voice-optimised responses for hands-free use"
        case .work:     return "CITB professional mode: JIRA, PRs, formal tone"
        }
    }
}

struct ModePreferences {
    private static let key = "brainchat.current_mode"
    static func load() -> ChatMode {
        if let raw = UserDefaults.standard.string(forKey: key),
           let mode = ChatMode(rawValue: raw) { return mode }
        return .chat
    }
    static func save(_ mode: ChatMode) {
        UserDefaults.standard.set(mode.rawValue, forKey: key)
    }
}

// MARK: - LLM Streaming

protocol LLMRequestHandle: AnyObject {
    var isStreaming: Bool { get }
    func cancel()
}

enum LLMAPIStyle {
    case openAICompatible
    case ollamaChat
    case anthropic
}

enum LLMProvider: String, CaseIterable {
    case groq
    case ollamaFast
    case ollamaQuality
    case claude
    case githubCopilot

    var displayName: String {
        switch self {
        case .groq: return "Groq"
        case .ollamaFast: return "Ollama 3B"
        case .ollamaQuality: return "Ollama 8B"
        case .claude: return "Claude"
        case .githubCopilot: return "GitHub Copilot"
        }
    }
}

enum LLMConversationType: String {
    case simple
    case code
    case reasoning
    case general
}

struct LLMProviderHealth {
    var isAvailable: Bool
    var latency: TimeInterval?
    var error: String?
    var checkedAt: Date?

    static let unknown = LLMProviderHealth(isAvailable: false, latency: nil, error: "Not checked yet", checkedAt: nil)
}

struct LLMRoutingDecision {
    let normalizedText: String
    let conversationType: LLMConversationType
    let manualOverride: LLMProvider?
    let offlineOnly: Bool
    let providers: [LLMProvider]
    let shouldRace: Bool
}

struct LLMConfig {
    let provider: LLMProvider
    let url: URL
    let model: String
    let systemPrompt: String
    let apiStyle: LLMAPIStyle
    var apiKey: String?
    var temperature: Double
    var maxTokens: Int

    init(provider: LLMProvider, url: URL, model: String, systemPrompt: String, apiStyle: LLMAPIStyle,
         apiKey: String? = nil, temperature: Double = 0.7, maxTokens: Int = 1024) {
        self.provider = provider
        self.url = url
        self.model = model
        self.systemPrompt = systemPrompt
        self.apiStyle = apiStyle
        self.apiKey = apiKey
        self.temperature = temperature
        self.maxTokens = maxTokens
    }

    static let `default` = LLMConfig(
        provider: .ollamaFast,
        url: URL(string: "http://localhost:11434/api/chat")!,
        model: "llama3.2:3b",
        systemPrompt: "You are Iris Lumina, an AI assistant for Joseph, who is blind and uses VoiceOver on macOS. Keep responses concise and clear. No filler phrases.",
        apiStyle: .ollamaChat
    )

    static func mode(_ chatMode: ChatMode) -> LLMConfig {
        let provider: LLMProvider = chatMode.llmModel == "llama3.1:8b" ? .ollamaQuality : .ollamaFast
        return LLMConfig(
            provider: provider,
            url: URL(string: "http://localhost:11434/api/chat")!,
            model: chatMode.llmModel,
            systemPrompt: chatMode.systemPrompt,
            apiStyle: .ollamaChat
        )
    }
}

final class LLMStreamingClient: NSObject, URLSessionDataDelegate, LLMRequestHandle {
    enum StreamError: LocalizedError {
        case httpError(Int)
        case connectionFailed(Error)
        case invalidConfiguration(String)

        var errorDescription: String? {
            switch self {
            case .httpError(let code): return "HTTP \(code)"
            case .connectionFailed(let error): return error.localizedDescription
            case .invalidConfiguration(let message): return message
            }
        }
    }

    private(set) var isStreaming = false
    var onToken: ((String) -> Void)?
    var onComplete: ((String, Error?) -> Void)?

    private lazy var session: URLSession = {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        config.timeoutIntervalForResource = 120
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        return URLSession(configuration: config, delegate: self, delegateQueue: nil)
    }()

    private var currentTask: URLSessionDataTask?
    private var utf8Tail = Data()
    private var lineBuffer = ""
    private var accumulated = ""
    private var pendingConfig: LLMConfig?
    private var pendingMessages: [[String: String]] = []
    private var retries = 0
    private let maxRetries = 3

    func stream(config: LLMConfig, userText: String,
                onToken: @escaping (String) -> Void,
                onComplete: @escaping (String, Error?) -> Void) {
        pendingConfig = config
        pendingMessages = [["role": "user", "content": userText]]
        self.onToken = onToken
        self.onComplete = onComplete
        retries = 0
        accumulated = ""
        utf8Tail = Data()
        lineBuffer = ""
        isStreaming = true
        sendRequest()
    }

    func cancel() {
        isStreaming = false
        currentTask?.cancel()
        currentTask = nil
        session.invalidateAndCancel()
    }

    private func sendRequest() {
        guard let config = pendingConfig else { return }

        var request = URLRequest(url: config.url)
        request.httpMethod = "POST"
        request.timeoutInterval = 45
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("text/event-stream, application/json", forHTTPHeaderField: "Accept")

        switch config.apiStyle {
        case .openAICompatible:
            if let key = config.apiKey {
                request.setValue("Bearer \(key)", forHTTPHeaderField: "Authorization")
            }
        case .anthropic:
            if let key = config.apiKey {
                request.setValue(key, forHTTPHeaderField: "x-api-key")
            }
            request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        case .ollamaChat:
            break
        }

        let body: [String: Any]
        switch config.apiStyle {
        case .openAICompatible:
            let messages = [["role": "system", "content": config.systemPrompt]] + pendingMessages
            body = [
                "model": config.model,
                "messages": messages,
                "stream": true,
                "temperature": config.temperature,
                "max_tokens": config.maxTokens,
            ]
        case .ollamaChat:
            let messages = [["role": "system", "content": config.systemPrompt]] + pendingMessages
            body = [
                "model": config.model,
                "messages": messages,
                "stream": true,
                "options": [
                    "temperature": config.temperature,
                    "num_predict": config.maxTokens,
                ],
            ]
        case .anthropic:
            body = [
                "model": config.model,
                "system": config.systemPrompt,
                "messages": pendingMessages,
                "stream": true,
                "temperature": config.temperature,
                "max_tokens": config.maxTokens,
            ]
        }

        guard let bodyData = try? JSONSerialization.data(withJSONObject: body) else {
            finish(error: StreamError.invalidConfiguration("Request serialization failed"))
            return
        }
        request.httpBody = bodyData
        utf8Tail = Data()
        lineBuffer = ""

        let task = session.dataTask(with: request)
        currentTask = task
        task.resume()
    }

    func urlSession(_ session: URLSession,
                    dataTask: URLSessionDataTask,
                    didReceive response: URLResponse,
                    completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard let http = response as? HTTPURLResponse else {
            completionHandler(.cancel)
            finish(error: StreamError.httpError(-1))
            return
        }
        if (200..<300).contains(http.statusCode) {
            completionHandler(.allow)
        } else {
            completionHandler(.cancel)
            finish(error: StreamError.httpError(http.statusCode))
        }
    }

    func urlSession(_ session: URLSession,
                    dataTask: URLSessionDataTask,
                    didReceive data: Data) {
        utf8Tail.append(data)
        var validLength = utf8Tail.count
        while validLength > 0, String(data: utf8Tail.prefix(validLength), encoding: .utf8) == nil {
            validLength -= 1
        }
        guard validLength > 0,
              let decoded = String(data: utf8Tail.prefix(validLength), encoding: .utf8) else { return }

        utf8Tail = validLength < utf8Tail.count ? Data(utf8Tail.suffix(utf8Tail.count - validLength)) : Data()
        lineBuffer += decoded
        while let range = lineBuffer.range(of: "\n") {
            let line = String(lineBuffer[lineBuffer.startIndex..<range.lowerBound])
            lineBuffer = String(lineBuffer[range.upperBound...])
            processLine(line)
        }
    }

    func urlSession(_ session: URLSession,
                    task: URLSessionTask,
                    didCompleteWithError error: Error?) {
        if !lineBuffer.isEmpty {
            processLine(lineBuffer)
            lineBuffer = ""
        }
        if let nsError = error as NSError?, nsError.code != NSURLErrorCancelled {
            let retriable = [NSURLErrorCannotConnectToHost, NSURLErrorNotConnectedToInternet, NSURLErrorTimedOut, NSURLErrorNetworkConnectionLost]
            if retriable.contains(nsError.code), accumulated.isEmpty, retries < maxRetries {
                retries += 1
                let delay = pow(2.0, Double(retries - 1)) * 0.5
                DispatchQueue.global().asyncAfter(deadline: .now() + delay) { [weak self] in
                    guard let self, self.isStreaming else { return }
                    self.sendRequest()
                }
                return
            }
            finish(error: accumulated.isEmpty ? StreamError.connectionFailed(nsError) : nil)
        } else {
            finish(error: nil)
        }
    }

    func urlSession(_ session: URLSession, didBecomeInvalidWithError error: Error?) {}

    private func processLine(_ rawLine: String) {
        let line = rawLine.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !line.isEmpty else { return }
        if line.hasPrefix("event: ") { return }
        let jsonText: String
        if line.hasPrefix("data: ") {
            let payload = String(line.dropFirst("data: ".count))
            if payload == "[DONE]" { return }
            jsonText = payload
        } else {
            jsonText = line
        }
        guard let data = jsonText.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return }
        if let choices = json["choices"] as? [[String: Any]],
           let delta = choices.first?["delta"] as? [String: Any],
           let content = delta["content"] as? String,
           !content.isEmpty {
            emit(content)
            return
        }
        if let message = json["message"] as? [String: Any],
           let content = message["content"] as? String,
           !content.isEmpty {
            emit(content)
            return
        }
        if let response = json["response"] as? String, !response.isEmpty {
            emit(response)
            return
        }
        if let delta = json["delta"] as? [String: Any],
           let text = delta["text"] as? String,
           !text.isEmpty {
            emit(text)
            return
        }
        if let content = json["content"] as? [[String: Any]] {
            let text = content.compactMap { $0["text"] as? String }.joined()
            if !text.isEmpty { emit(text) }
        }
    }

    private func emit(_ content: String) {
        accumulated += content
        DispatchQueue.main.async { [weak self] in self?.onToken?(content) }
    }

    private func finish(error: Error?) {
        isStreaming = false
        session.finishTasksAndInvalidate()
        let text = accumulated
        DispatchQueue.main.async { [weak self] in self?.onComplete?(text, error) }
    }
}

final class GitHubCopilotRequest: LLMRequestHandle {
    private(set) var isStreaming = false
    private var process: Process?
    private let onComplete: (String, Error?) -> Void

    init(prompt: String, onComplete: @escaping (String, Error?) -> Void) {
        self.onComplete = onComplete
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["gh", "copilot", "-p", prompt]
        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr
        self.process = process
        isStreaming = true

        process.terminationHandler = { [weak self] process in
            let output = String(data: stdout.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let errorText = String(data: stderr.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let trimmedOutput = output.trimmingCharacters(in: .whitespacesAndNewlines)
            let trimmedError = errorText.trimmingCharacters(in: .whitespacesAndNewlines)
            DispatchQueue.main.async {
                guard let self else { return }
                self.isStreaming = false
                self.process = nil
                if process.terminationStatus == 0, !trimmedOutput.isEmpty {
                    self.onComplete(trimmedOutput, nil)
                } else {
                    let message = trimmedError.isEmpty ? "gh copilot did not return a response" : trimmedError
                    self.onComplete("", NSError(domain: "BrainChat.Copilot", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: message]))
                }
            }
        }

        do {
            try process.run()
        } catch {
            isStreaming = false
            self.process = nil
            DispatchQueue.main.async { onComplete("", error) }
        }
    }

    func cancel() {
        isStreaming = false
        process?.terminate()
        process = nil
    }
}

final class LLMRouter {
    private let systemPrompt = "You are Iris Lumina, an AI assistant for Joseph, who is blind and uses VoiceOver on macOS. Keep responses concise and clear. Prefer short paragraphs and explicit wording."
    private let defaults = UserDefaults.standard
    private let healthQueue = DispatchQueue(label: "brainchat.llmrouter.health", attributes: .concurrent)
    private let session: URLSession
    private var health: [LLMProvider: LLMProviderHealth] = Dictionary(uniqueKeysWithValues: LLMProvider.allCases.map { ($0, .unknown) })

    init() {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 4
        config.timeoutIntervalForResource = 6
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        session = URLSession(configuration: config)
    }

    func startHealthChecks(_ onStatus: @escaping (String) -> Void) {
        for provider in LLMProvider.allCases {
            ping(provider) { [weak self] in
                guard let self else { return }
                DispatchQueue.main.async { onStatus(self.healthSummary()) }
            }
        }
    }

    func streamResponse(for text: String,
                        onStatus: @escaping (String) -> Void,
                        onToken: @escaping (String) -> Void,
                        onComplete: @escaping (String, Error?, LLMProvider?) -> Void) -> LLMRequestHandle {
        let decision = route(text)
        if let manual = decision.manualOverride {
            rememberPreference(manual, for: decision.conversationType)
            onStatus("Manual override: \(manual.displayName) for \(decision.conversationType.rawValue) requests")
        } else if decision.offlineOnly {
            onStatus("Offline mode enabled. Using local Ollama only.")
        }
        let request = LLMRouterRequest(router: self, decision: decision, onStatus: onStatus, onToken: onToken, onComplete: onComplete)
        request.start()
        return request
    }

    func createRequest(for provider: LLMProvider,
                       text: String,
                       onToken: @escaping (String) -> Void,
                       onComplete: @escaping (String, Error?) -> Void) -> LLMRequestHandle? {
        switch provider {
        case .githubCopilot:
            return GitHubCopilotRequest(prompt: text, onComplete: onComplete)
        default:
            guard let config = config(for: provider) else { return nil }
            let client = LLMStreamingClient()
            client.stream(config: config, userText: text, onToken: onToken, onComplete: onComplete)
            return client
        }
    }

    func recordSuccess(provider: LLMProvider, latency: TimeInterval) {
        updateHealth(provider: provider, available: true, latency: latency, error: nil)
    }

    func recordFailure(provider: LLMProvider, error: String) {
        updateHealth(provider: provider, available: false, latency: nil, error: error)
    }

    func healthSnapshot(for provider: LLMProvider) -> LLMProviderHealth {
        var snapshot = LLMProviderHealth.unknown
        healthQueue.sync {
            snapshot = health[provider] ?? .unknown
        }
        return snapshot
    }

    private func config(for provider: LLMProvider) -> LLMConfig? {
        let env = ProcessInfo.processInfo.environment
        switch provider {
        case .groq:
            guard let key = env["GROQ_API_KEY"], !key.isEmpty else { return nil }
            return LLMConfig(provider: provider, url: URL(string: "https://api.groq.com/openai/v1/chat/completions")!, model: "llama-3.1-8b-instant", systemPrompt: systemPrompt, apiStyle: .openAICompatible, apiKey: key, temperature: 0.4, maxTokens: 900)
        case .ollamaFast:
            return LLMConfig(provider: provider, url: URL(string: "http://localhost:11434/api/chat")!, model: "llama3.2:3b", systemPrompt: systemPrompt, apiStyle: .ollamaChat, temperature: 0.4, maxTokens: 900)
        case .ollamaQuality:
            return LLMConfig(provider: provider, url: URL(string: "http://localhost:11434/api/chat")!, model: "llama3.1:8b", systemPrompt: systemPrompt, apiStyle: .ollamaChat, temperature: 0.35, maxTokens: 1200)
        case .claude:
            guard let key = env["ANTHROPIC_API_KEY"], !key.isEmpty else { return nil }
            return LLMConfig(provider: provider, url: URL(string: "https://api.anthropic.com/v1/messages")!, model: "claude-3-7-sonnet-latest", systemPrompt: systemPrompt, apiStyle: .anthropic, apiKey: key, temperature: 0.3, maxTokens: 1400)
        case .githubCopilot:
            return nil
        }
    }

    private func route(_ input: String) -> LLMRoutingDecision {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowered = trimmed.lowercased()
        let offlineOnly = lowered.hasPrefix("offline:") || lowered.hasPrefix("offline mode") || lowered.hasPrefix("use offline") || ProcessInfo.processInfo.environment["BRAINCHAT_OFFLINE"] == "1"
        let conversationType = classify(trimmed)
        var normalizedText = trimmed
        var manualOverride: LLMProvider?
        let overrides: [(String, LLMProvider)] = [
            ("use groq", .groq),
            ("use claude", .claude),
            ("use copilot", .githubCopilot),
            ("use local 8b", .ollamaQuality),
            ("use local", .ollamaFast),
            ("use ollama 8b", .ollamaQuality),
            ("use ollama", .ollamaFast),
        ]
        for (prefix, provider) in overrides where lowered.hasPrefix(prefix) {
            manualOverride = provider
            normalizedText = trimmed.dropFirst(prefix.count).trimmingCharacters(in: CharacterSet(charactersIn: " :,-\n\t"))
            break
        }
        if normalizedText.isEmpty { normalizedText = trimmed }

        var providers = baseProviders(for: conversationType, offlineOnly: offlineOnly)
        if let preferred = storedPreference(for: conversationType), providers.contains(preferred) {
            providers.removeAll { $0 == preferred }
            providers.insert(preferred, at: 0)
        }
        if let manualOverride {
            providers.removeAll { $0 == manualOverride }
            providers.insert(manualOverride, at: 0)
        }
        providers = reorderByHealth(providers)
        let shouldRace = !offlineOnly && manualOverride == nil && conversationType == .simple && providers.prefix(2).contains(.groq) && providers.prefix(2).contains(.ollamaFast)
        return LLMRoutingDecision(normalizedText: normalizedText, conversationType: conversationType, manualOverride: manualOverride, offlineOnly: offlineOnly, providers: providers, shouldRace: shouldRace)
    }

    private func classify(_ text: String) -> LLMConversationType {
        let lowered = text.lowercased()
        let wordCount = lowered.split(whereSeparator: { $0.isWhitespace || $0.isNewline }).count
        let codeHints = ["swift", "python", "javascript", "typescript", "regex", "compile", "build", "debug", "function", "class", "struct", "array", "json", "bash", "shell", "code", "stack trace", "terminal", "xcode"]
        if codeHints.contains(where: lowered.contains) || lowered.contains("func ") || lowered.contains("def ") || lowered.contains("```") {
            return .code
        }
        let reasoningHints = ["compare", "tradeoff", "analyse", "analyze", "reason", "architecture", "design", "why", "step by step", "plan", "strategy"]
        if reasoningHints.contains(where: lowered.contains) || wordCount > 28 {
            return .reasoning
        }
        let simpleHints = ["hello", "hi", "hey", "thanks", "thank you", "time", "date", "status", "ping", "who are you"]
        if wordCount <= 10 || simpleHints.contains(where: lowered.contains) {
            return .simple
        }
        return .general
    }

    private func baseProviders(for type: LLMConversationType, offlineOnly: Bool) -> [LLMProvider] {
        if offlineOnly { return [.ollamaFast, .ollamaQuality] }
        switch type {
        case .simple, .general: return [.groq, .ollamaFast, .ollamaQuality, .claude, .githubCopilot]
        case .code: return [.claude, .githubCopilot, .groq, .ollamaQuality, .ollamaFast]
        case .reasoning: return [.claude, .groq, .ollamaQuality, .ollamaFast, .githubCopilot]
        }
    }

    private func reorderByHealth(_ providers: [LLMProvider]) -> [LLMProvider] {
        let indices = Dictionary(uniqueKeysWithValues: providers.enumerated().map { ($1, $0) })
        return providers.sorted { lhs, rhs in
            let lh = healthSnapshot(for: lhs)
            let rh = healthSnapshot(for: rhs)
            if lh.isAvailable != rh.isAvailable { return lh.isAvailable && !rh.isAvailable }
            let ll = lh.latency ?? 999
            let rl = rh.latency ?? 999
            if ll != rl { return ll < rl }
            return (indices[lhs] ?? 0) < (indices[rhs] ?? 0)
        }
    }

    private func storedPreference(for type: LLMConversationType) -> LLMProvider? {
        guard let raw = defaults.string(forKey: preferenceKey(for: type)) else { return nil }
        return LLMProvider(rawValue: raw)
    }

    private func rememberPreference(_ provider: LLMProvider, for type: LLMConversationType) {
        defaults.set(provider.rawValue, forKey: preferenceKey(for: type))
    }

    private func preferenceKey(for type: LLMConversationType) -> String {
        return "brainchat.llm.preference.\(type.rawValue)"
    }

    private func ping(_ provider: LLMProvider, completion: @escaping () -> Void) {
        switch provider {
        case .githubCopilot:
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
            process.arguments = ["gh", "copilot", "--help"]
            let stdout = Pipe()
            let stderr = Pipe()
            process.standardOutput = stdout
            process.standardError = stderr
            let started = Date()
            process.terminationHandler = { [weak self] process in
                let output = String(data: stdout.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                let errorText = String(data: stderr.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                let reachable = process.terminationStatus == 0 && (!output.isEmpty || !errorText.isEmpty)
                self?.updateHealth(provider: provider, available: reachable, latency: Date().timeIntervalSince(started), error: reachable ? nil : "gh copilot unavailable")
                completion()
            }
            do {
                try process.run()
            } catch {
                updateHealth(provider: provider, available: false, latency: nil, error: error.localizedDescription)
                completion()
            }
        case .ollamaFast, .ollamaQuality:
            simplePing(provider: provider, url: URL(string: "http://localhost:11434/api/tags")!, headers: [:], completion: completion)
        case .groq:
            guard let key = ProcessInfo.processInfo.environment["GROQ_API_KEY"], !key.isEmpty else {
                updateHealth(provider: provider, available: false, latency: nil, error: "Missing GROQ_API_KEY")
                completion()
                return
            }
            simplePing(provider: provider, url: URL(string: "https://api.groq.com/openai/v1/models")!, headers: ["Authorization": "Bearer \(key)"], completion: completion)
        case .claude:
            guard let key = ProcessInfo.processInfo.environment["ANTHROPIC_API_KEY"], !key.isEmpty else {
                updateHealth(provider: provider, available: false, latency: nil, error: "Missing ANTHROPIC_API_KEY")
                completion()
                return
            }
            simplePing(provider: provider, url: URL(string: "https://api.anthropic.com/v1/messages")!, headers: ["x-api-key": key, "anthropic-version": "2023-06-01"], completion: completion)
        }
    }

    private func simplePing(provider: LLMProvider, url: URL, headers: [String: String], completion: @escaping () -> Void) {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 4
        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }
        let started = Date()
        session.dataTask(with: request) { [weak self] _, response, error in
            defer { completion() }
            guard let self else { return }
            if let error = error {
                self.updateHealth(provider: provider, available: false, latency: nil, error: error.localizedDescription)
                return
            }
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            let reachable = (200..<500).contains(status)
            self.updateHealth(provider: provider, available: reachable, latency: Date().timeIntervalSince(started), error: reachable ? nil : "HTTP \(status)")
        }.resume()
    }

    private func updateHealth(provider: LLMProvider, available: Bool, latency: TimeInterval?, error: String?) {
        let snapshot = LLMProviderHealth(isAvailable: available, latency: latency, error: error, checkedAt: Date())
        healthQueue.async(flags: .barrier) {
            self.health[provider] = snapshot
        }
    }

    private func healthSummary() -> String {
        let parts = LLMProvider.allCases.map { provider -> String in
            let snapshot = healthSnapshot(for: provider)
            if snapshot.isAvailable {
                if let latency = snapshot.latency {
                    return "\(provider.displayName) \(Int(latency * 1000))ms"
                }
                return "\(provider.displayName) ready"
            }
            return "\(provider.displayName) \(snapshot.error ?? "down")"
        }
        return "LLM health: " + parts.joined(separator: " · ")
    }
}

final class LLMRouterRequest: LLMRequestHandle {
    private final class Execution {
        let provider: LLMProvider
        let startedAt: Date
        let handle: LLMRequestHandle

        init(provider: LLMProvider, handle: LLMRequestHandle) {
            self.provider = provider
            self.startedAt = Date()
            self.handle = handle
        }

        func cancel() {
            handle.cancel()
        }
    }

    private let router: LLMRouter
    private let decision: LLMRoutingDecision
    private let onStatus: (String) -> Void
    private let onToken: (String) -> Void
    private let onComplete: (String, Error?, LLMProvider?) -> Void

    private var remainingProviders: [LLMProvider]
    private var executions: [LLMProvider: Execution] = [:]
    private var winner: LLMProvider?
    private var lastError: Error?
    private var didFinish = false
    private(set) var isStreaming = false

    init(router: LLMRouter,
         decision: LLMRoutingDecision,
         onStatus: @escaping (String) -> Void,
         onToken: @escaping (String) -> Void,
         onComplete: @escaping (String, Error?, LLMProvider?) -> Void) {
        self.router = router
        self.decision = decision
        self.onStatus = onStatus
        self.onToken = onToken
        self.onComplete = onComplete
        self.remainingProviders = decision.providers
    }

    func start() {
        isStreaming = true
        launchNextBatch()
    }

    func cancel() {
        isStreaming = false
        executions.values.forEach { $0.cancel() }
        executions.removeAll()
    }

    private func launchNextBatch() {
        guard !didFinish else { return }
        if remainingProviders.isEmpty {
            finish(text: "", error: lastError ?? NSError(domain: "BrainChat.Router", code: -1, userInfo: [NSLocalizedDescriptionKey: "No LLM providers were available"]), provider: nil)
            return
        }
        let batch: [LLMProvider]
        if decision.shouldRace, winner == nil, remainingProviders.count >= 2 {
            batch = Array(remainingProviders.prefix(2))
            remainingProviders.removeFirst(min(2, remainingProviders.count))
            onStatus("Racing \(batch[0].displayName) and \(batch[1].displayName)…")
        } else {
            let next = remainingProviders.removeFirst()
            batch = [next]
            onStatus("Routing \(decision.conversationType.rawValue) request to \(next.displayName)…")
        }
        for provider in batch { start(provider: provider) }
    }

    private func start(provider: LLMProvider) {
        guard let handle = router.createRequest(for: provider, text: decision.normalizedText, onToken: { [weak self] token in
            self?.receiveToken(token, from: provider)
        }, onComplete: { [weak self] text, error in
            self?.complete(provider: provider, text: text, error: error)
        }) else {
            router.recordFailure(provider: provider, error: "Provider is not configured")
            if executions.isEmpty { launchNextBatch() }
            return
        }
        executions[provider] = Execution(provider: provider, handle: handle)
    }

    private func receiveToken(_ token: String, from provider: LLMProvider) {
        guard !didFinish, let execution = executions[provider] else { return }
        if winner == nil {
            winner = provider
            router.recordSuccess(provider: provider, latency: Date().timeIntervalSince(execution.startedAt))
            onStatus("Using \(provider.displayName)")
            cancelAllExcept(provider)
        }
        guard winner == provider else { return }
        onToken(token)
    }

    private func complete(provider: LLMProvider, text: String, error: Error?) {
        guard !didFinish else { return }
        let execution = executions.removeValue(forKey: provider)
        let latency = execution.map { Date().timeIntervalSince($0.startedAt) } ?? 0
        if let error {
            lastError = error
            router.recordFailure(provider: provider, error: error.localizedDescription)
        }
        if winner == provider {
            if !text.isEmpty { router.recordSuccess(provider: provider, latency: latency) }
            finish(text: text, error: error, provider: provider)
            return
        }
        if winner == nil, !text.isEmpty {
            winner = provider
            router.recordSuccess(provider: provider, latency: latency)
            onStatus("Using \(provider.displayName)")
            cancelAllExcept(provider)
            onToken(text)
            finish(text: text, error: error, provider: provider)
            return
        }
        if executions.isEmpty && winner == nil { launchNextBatch() }
    }

    private func cancelAllExcept(_ provider: LLMProvider?) {
        for (candidate, execution) in executions where candidate != provider {
            execution.cancel()
            executions.removeValue(forKey: candidate)
        }
    }

    private func finish(text: String, error: Error?, provider: LLMProvider?) {
        guard !didFinish else { return }
        didFinish = true
        isStreaming = false
        cancelAllExcept(provider)
        onComplete(text, error, provider)
    }
}

final class TerminalMode {
    private var original: termios?
    private(set) var isEnabled = false

    func enableRawMode() throws {
        guard isatty(STDIN_FILENO) == 1 else { return }
        guard !isEnabled else { return }

        var attributes = termios()
        guard tcgetattr(STDIN_FILENO, &attributes) == 0 else {
            throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno), userInfo: [NSLocalizedDescriptionKey: String(cString: strerror(errno))])
        }

        original = attributes
        cfmakeraw(&attributes)
        attributes.c_oflag |= tcflag_t(OPOST)

        guard tcsetattr(STDIN_FILENO, TCSAFLUSH, &attributes) == 0 else {
            throw NSError(domain: NSPOSIXErrorDomain, code: Int(errno), userInfo: [NSLocalizedDescriptionKey: String(cString: strerror(errno))])
        }

        isEnabled = true
    }

    func restore() {
        guard isEnabled, var original else { return }
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &original)
        isEnabled = false
    }

    deinit {
        restore()
    }
}

final class TerminalChatController {
    private struct QueuedChunk {
        let requestID: String?
        let text: String
        let finishesMessage: Bool
        let speechText: String?
    }

    static var shouldRunInTerminal: Bool {
        CommandLine.arguments.contains("--terminal") || isatty(STDIN_FILENO) == 1 || isatty(STDOUT_FILENO) == 1
    }

    private let bridge = RedpandaBridge()
    private let fallbackResponder = LocalFallbackResponder()
    private let speaker = SpeechVoice()
    private let terminalMode = TerminalMode()
    private var currentMode: ChatMode = ModePreferences.load()
    private let uiQueue = DispatchQueue(label: "brainchat.terminal.ui")
    private let stdoutHandle = FileHandle.standardOutput

    private var inputSource: DispatchSourceRead?
    private var pendingFallbacks: [String: DispatchWorkItem] = [:]
    private var pendingRequestOrder: [String] = []
    private var availability: RedpandaBridge.Availability = .unavailable("Connecting…")
    private var inputBuffer = ""
    private var pendingChunks: [QueuedChunk] = []
    private var isAnimatingChunk = false
    private var activeResponseRequestID: String?
    private var promptVisible = false
    private var shuttingDown = false
    private var escapeSequencePending = false
    // MARK: - UI Proxy (for CopilotIntegration compatibility)

    enum LogLevel { case info, warning, error }

    struct UIProxy {
        weak var c: TerminalChatController?
        func setStatus(_ text: String)  { c?.writeStatus(text) }
        func speak(_ text: String)      { DispatchQueue.main.async { self.c?.speaker.speak(text) } }
        func log(_ text: String, level: LogLevel = .info) { c?.writeLine(text) }
        func appendChat(role: String, text: String, requestID: String? = nil) {
            c?.writeTranscriptLine(prefix: role, text: text, color: role == "You" ? TerminalANSI.cyan : TerminalANSI.green)
        }
        func appendChatFragment(role: String, requestID: String, text: String) {
            c?.uiQueue.async { self.c?.writeRaw(ANSIText.strip(text)) }
        }
    }

    var ui: UIProxy { UIProxy(c: self) }



    // LLM streaming state
    private var streamingClient: LLMStreamingClient?
    private var currentStreamID: String?
    private var streamPrefixShown = false   // true once "Brain> " has been written

    private lazy var richTTYEnabled: Bool = {
        guard isatty(STDOUT_FILENO) == 1 else { return false }
        let environment = ProcessInfo.processInfo.environment
        if environment["TERM"] == "dumb" { return false }
        if environment["BRAINCHAT_ACCESSIBLE_TERMINAL"] == "1" { return false }
        return true
    }()

    func run() -> Never {
        uiQueue.async { [weak self] in
            self?.bootstrap()
        }
        dispatchMain()
    }

    private func bootstrap() {
        do {
            try terminalMode.enableRawMode()
        } catch {
            writeLine("Brain Chat could not enable raw mode: \(error.localizedDescription)")
        }

        if richTTYEnabled {
            writeRaw(TerminalANSI.hideCursor)
        }

        configureBridge()
        setupInputSource()
        renderWelcome()
        bridge.start()
        renderPrompt()
    }

    private func configureBridge() {
        bridge.onAvailabilityChanged = { [weak self] availability in
            self?.uiQueue.async {
                self?.availability = availability
                switch availability {
                case .connected:
                    self?.writeStatus("Connected to Redpanda at localhost:9092")
                case .unavailable(let reason):
                    self?.writeStatus("Fallback mode: \(reason)")
                }
            }
        }

        bridge.onResponse = { [weak self] response in
            self?.uiQueue.async {
                self?.handleRemoteResponse(response)
            }
        }
    }

    private func setupInputSource() {
        guard isatty(STDIN_FILENO) == 1 else {
            writeLine("Brain Chat terminal mode requires interactive stdin.")
            shutdown(exitCode: 1)
            return
        }

        let source = DispatchSource.makeReadSource(fileDescriptor: STDIN_FILENO, queue: uiQueue)
        source.setEventHandler { [weak self] in
            self?.consumeInput()
        }
        source.setCancelHandler {}
        inputSource = source
        source.resume()
    }

    private func consumeInput() {
        var buffer = [UInt8](repeating: 0, count: 256)
        let bytesRead = Darwin.read(STDIN_FILENO, &buffer, buffer.count)
        guard bytesRead > 0 else {
            shutdown(exitCode: 0)
            return
        }

        for byte in buffer.prefix(bytesRead) {
            handleInputByte(byte)
        }
    }

    private func handleInputByte(_ byte: UInt8) {
        if escapeSequencePending {
            if (64...126).contains(byte) {
                escapeSequencePending = false
            }
            return
        }

        switch byte {
        case 3, 4:
            shutdown(exitCode: 0)
        case 27:
            escapeSequencePending = true
        case 10, 13:
            let text = inputBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            inputBuffer = ""
            promptVisible = false
            writeRaw("\r\n")
            guard !text.isEmpty else {
                renderPrompt()
                return
            }
            processInput(text)
        case 8, 127:
            guard !inputBuffer.isEmpty else { return }
            inputBuffer.removeLast()
            renderPrompt()
        default:
            guard let scalar = UnicodeScalar(Int(byte)), !CharacterSet.controlCharacters.contains(scalar) else {
                return
            }
            inputBuffer.append(Character(scalar))
            if !isAnimatingChunk {
                renderPrompt()
            }
        }
    }

    private func renderWelcome() {
        writeLine(colorize("Brain Chat — terminal mode. Ctrl+C exits.", color: TerminalANSI.bold + TerminalANSI.magenta))
        writeLine("Mode: " + colorize(currentMode.displayName, color: currentMode.promptANSIColor + TerminalANSI.bold)
                  + "  " + currentMode.modeDescription)
        writeLine("Switch: /chat  /code  /terminal  /yolo  /voice  /work   (/modes for list)")
        writeLine("Tip: set BRAINCHAT_ACCESSIBLE_TERMINAL=1 to disable ANSI colours.")
        DispatchQueue.main.async {
            self.speaker.speak("Brain Chat ready in \(self.currentMode.displayName) mode. Type a message and press Return.")
        }
    }

    private func processInput(_ text: String) {
        if tryHandleCopilotInput(text) { return }
        if text.hasPrefix("/") { handleModeCommand(text); return }
        if currentMode == .yolo { handleYOLOCommand(text); return }
        if currentMode == .terminal, text.hasPrefix("!") {
            let cmd = String(text.dropFirst()).trimmingCharacters(in: .whitespacesAndNewlines)
            if !cmd.isEmpty { executeShellCommand(cmd); return }
        }
        // Cancel any in-progress stream before starting a new request.
        streamingClient?.cancel()
        streamingClient = nil

        writeTranscriptLine(prefix: "You", text: text, color: currentMode.promptANSIColor)
        let requestID = UUID().uuidString
        currentStreamID = requestID
        streamPrefixShown = false
        writeStatus("Connecting to local AI…")

        let client = LLMStreamingClient()
        streamingClient = client

        client.stream(
            config: .mode(currentMode),
            userText: text,
            onToken: { [weak self] token in
                self?.uiQueue.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    if !self.streamPrefixShown {
                        self.streamPrefixShown = true
                        // Clear the prompt line before printing the Brain prefix.
                        if self.promptVisible {
                            self.writeRaw("\r" + (self.richTTYEnabled ? TerminalANSI.clearLine : ""))
                            self.promptVisible = false
                        }
                        self.writeRaw(self.colorize("Brain> ", color: TerminalANSI.green + TerminalANSI.bold))
                    }
                    self.writeRaw(ANSIText.strip(token))
                }
            },
            onComplete: { [weak self] fullText, error in
                self?.uiQueue.async {
                    guard let self, self.currentStreamID == requestID else { return }
                    self.streamingClient = nil
                    if fullText.isEmpty {
                        // Stream produced nothing — fall back to Redpanda then local.
                        self.writeStatus("Local AI unavailable. Trying Redpanda…")
                        self.useRedpandaPath(text: text, requestID: requestID)
                    } else {
                        self.writeRaw("\r\n")
                        self.writeStatus("Ready. \(self.currentMode.displayName) mode.")
                        if self.currentMode.speaksResponses {
                            DispatchQueue.main.async { self.speaker.speak(fullText) }
                        }
                        self.renderPrompt()
                    }
                }
            }
        )
    }

    private func useRedpandaPath(text: String, requestID: String) {
        pendingRequestOrder.append(requestID)
        bridge.publish(text: text, requestID: requestID) { [weak self] success, reason in
            self?.uiQueue.async {
                guard let self else { return }
                if success {
                    self.writeStatus("Waiting for AI response on brain.voice.response…")
                    self.scheduleFallback(for: requestID, originalText: text)
                } else {
                    self.writeStatus("Redpanda publish failed. Using local fallback.")
                    self.respondLocally(to: text, requestID: requestID, reason: reason ?? "publish failed")
                }
            }
        }
    }

    private func scheduleFallback(for requestID: String, originalText: String) {
        let workItem = DispatchWorkItem { [weak self] in
            self?.respondLocally(to: originalText, requestID: requestID, reason: self?.availabilityReason ?? "no response received")
        }
        pendingFallbacks[requestID] = workItem
        uiQueue.asyncAfter(deadline: .now() + 7, execute: workItem)
    }

    private func handleRemoteResponse(_ response: BridgeResponse) {
        if let requestID = response.requestID {
            resolvePendingRequest(id: requestID)
        } else if let next = pendingRequestOrder.first {
            resolvePendingRequest(id: next)
        }

        writeStatus(response.isPartial && !response.isFinal ? "Streaming AI response…" : "Received AI response")

        let cleanText = richTTYEnabled ? response.text : ANSIText.strip(response.text)
        let spokenText = ANSIText.strip(response.text)
        let chunk = QueuedChunk(
            requestID: response.requestID,
            text: cleanText,
            finishesMessage: response.isFinal,
            speechText: response.isFinal ? spokenText : nil
        )
        pendingChunks.append(chunk)
        pumpChunkQueue()
    }

    private func respondLocally(to text: String, requestID: String, reason: String) {
        resolvePendingRequest(id: requestID)
        let response = fallbackResponder.response(for: text, reason: reason)
        writeStatus("Responding locally")
        pendingChunks.append(QueuedChunk(requestID: requestID, text: response, finishesMessage: true, speechText: response))
        pumpChunkQueue()
    }

    private func pumpChunkQueue() {
        guard !isAnimatingChunk, !pendingChunks.isEmpty else { return }
        isAnimatingChunk = true
        let chunk = pendingChunks.removeFirst()

        if activeResponseRequestID != chunk.requestID {
            if activeResponseRequestID != nil {
                writeRaw("\r\n")
            }
            activeResponseRequestID = chunk.requestID
            writeRaw(colorize("Brain> ", color: TerminalANSI.green + TerminalANSI.bold))
        }

        stream(chunk.text, at: chunk.text.startIndex, finishesMessage: chunk.finishesMessage) { [weak self] in
            guard let self else { return }
            if chunk.finishesMessage {
                self.writeRaw("\r\n")
                self.activeResponseRequestID = nil
                if let speechText = chunk.speechText {
                    DispatchQueue.main.async {
                        self.speaker.speak(speechText)
                    }
                }
            }
            self.isAnimatingChunk = false
            self.renderPrompt()
            self.pumpChunkQueue()
        }
    }

    private func stream(_ text: String, at index: String.Index, finishesMessage: Bool, completion: @escaping () -> Void) {
        guard index < text.endIndex else {
            completion()
            return
        }

        let nextIndex = text.index(after: index)
        let character = String(text[index])
        writeRaw(character)

        let delay: DispatchTimeInterval = character == "\n" ? .milliseconds(0) : .milliseconds(8)
        uiQueue.asyncAfter(deadline: .now() + delay) { [weak self] in
            self?.stream(text, at: nextIndex, finishesMessage: finishesMessage, completion: completion)
        }
    }

    private func resolvePendingRequest(id: String) {
        pendingFallbacks[id]?.cancel()
        pendingFallbacks[id] = nil
        pendingRequestOrder.removeAll { $0 == id }
    }

    private var availabilityReason: String {
        switch availability {
        case .connected:
            return "broker is connected but no response arrived"
        case .unavailable(let reason):
            return reason
        }
    }

    private func renderPrompt() {
        guard !shuttingDown else { return }
        guard !isAnimatingChunk else { return }

        let label = currentMode == .chat ? "You> " : "[\(currentMode.displayName)]> "
        let prompt = colorize(label, color: currentMode.promptANSIColor + TerminalANSI.bold) + inputBuffer
        if richTTYEnabled {
            writeRaw("\r" + TerminalANSI.clearLine + prompt)
        } else {
            writeRaw(promptVisible ? "\r\(label)\(inputBuffer)" : prompt)
        }
        promptVisible = true
    }

    private func writeStatus(_ text: String) {
        writeLine(colorize("Status: \(ANSIText.strip(text))", color: TerminalANSI.dim + TerminalANSI.yellow))
        renderPrompt()
    }

    private func writeTranscriptLine(prefix: String, text: String, color: String) {
        writeLine(colorize("\(prefix)> ", color: color + TerminalANSI.bold) + ANSIText.strip(text))
    }

    private func writeLine(_ text: String) {
        if promptVisible {
            writeRaw("\r" + (richTTYEnabled ? TerminalANSI.clearLine : ""))
            promptVisible = false
        }
        writeRaw(text)
        if !text.hasSuffix("\n") {
            writeRaw("\r\n")
        }
    }

    private func writeRaw(_ text: String) {
        stdoutHandle.write(Data(text.utf8))
    }

    private func colorize(_ text: String, color: String) -> String {
        guard richTTYEnabled else { return ANSIText.strip(text) }
        return color + text + TerminalANSI.reset
    }


    // MARK: - Mode Commands

    private func handleModeCommand(_ input: String) {
        let cmd = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        if cmd == "/modes" || cmd == "/help" || cmd == "/?" {
            writeLine(colorize("Available modes:", color: TerminalANSI.bold))
            for mode in ChatMode.allCases {
                let m = mode == currentMode ? "> " : "  "
                writeLine(colorize(m + mode.switchCommand, color: mode.promptANSIColor + TerminalANSI.bold)
                          + "  " + mode.modeDescription)
            }
            renderPrompt(); return
        }
        if let mode = ChatMode.allCases.first(where: { cmd == $0.switchCommand }) {
            currentMode = mode
            ModePreferences.save(mode)
            writeLine(colorize("Switched to \(mode.displayName) — \(mode.modeDescription)",
                               color: mode.promptANSIColor + TerminalANSI.bold))
            DispatchQueue.main.async { self.speaker.speak("Switched to \(mode.displayName) mode.") }
            renderPrompt()
        } else {
            writeLine(colorize("Unknown command: \(input). Type /modes for help.", color: TerminalANSI.yellow))
            renderPrompt()
        }
    }

    private func handleYOLOCommand(_ command: String) {
        writeTranscriptLine(prefix: "YOLO", text: command, color: TerminalANSI.red)
        writeStatus("Publishing to brain.yolo.commands…")
        let reqID = UUID().uuidString
        pendingRequestOrder.append(reqID)
        bridge.publish(text: "yolo: \(command)", requestID: reqID) { [weak self] success, reason in
            self?.uiQueue.async {
                guard let self else { return }                
                if success {
                    self.writeStatus("YOLO command published.")
                    DispatchQueue.main.async { self.speaker.speak("YOLO command published.") }
                } else {
                    self.writeStatus("YOLO failed: \(reason ?? "unknown")")
                    self.pendingRequestOrder.removeAll { $0 == reqID }
                }
                self.renderPrompt()
            }
        }
    }

    private func executeShellCommand(_ command: String) {
        writeTranscriptLine(prefix: "Shell", text: "$ \(command)", color: TerminalANSI.magenta)
        writeStatus("Executing…")
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/zsh")
        p.arguments = ["-c", command]
        let o = Pipe(); let e = Pipe()
        p.standardOutput = o; p.standardError = e
        p.terminationHandler = { [weak self] proc in
            let out = String(data: o.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let err = String(data: e.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
            let combined = (out + err).trimmingCharacters(in: .whitespacesAndNewlines)
            DispatchQueue.main.async {
                self?.uiQueue.async {
                    guard let self else { return }
                    if !combined.isEmpty { self.writeLine(combined) }
                    self.writeStatus(proc.terminationStatus == 0 ? "Done (exit 0)" : "Exit \(proc.terminationStatus)")
                    self.renderPrompt()
                }
            }
        }
        do { try p.run() } catch {
            writeStatus("Shell error: \(error.localizedDescription)"); renderPrompt()
        }
    }

    private func shutdown(exitCode: Int32) {
        guard !shuttingDown else { return }
        shuttingDown = true; cleanupCopilotSession()
        pendingFallbacks.values.forEach { $0.cancel() }
        pendingFallbacks.removeAll()
        bridge.stop()
        inputSource?.cancel()
        inputSource = nil
        if richTTYEnabled {
            writeRaw("\r\n" + TerminalANSI.showCursor)
        } else {
            writeRaw("\r\n")
        }
        terminalMode.restore()
        Darwin.exit(exitCode)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let listenButton = NSButton(title: "Press Enter to Talk", target: nil, action: nil)
    private let statusLabel = NSTextField(labelWithString: "Starting Brain Chat…")
    private let transcriptView = NSTextView()
    private let scrollView = NSScrollView()

    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en_AU"))
    private let audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var didProcessFinalResult = false
    private var isListening = false
    private var lastHeardText = ""
    private var speechPermissionGranted = false
    private var microphonePermissionGranted = false

    private let speaker = SpeechVoice()
    private let fallbackResponder = LocalFallbackResponder()
    private let bridge = RedpandaBridge()
    private var currentMode: ChatMode = ModePreferences.load()
    private let modeBadgeLabel = NSTextField(labelWithString: "Chat Mode")
    private var bridgeAvailability: RedpandaBridge.Availability = .unavailable("Connecting…")
    private var pendingFallbacks: [String: DispatchWorkItem] = [:]
    private var pendingRequestOrder: [String] = []

    // LLM streaming state
    private var streamingClient: LLMStreamingClient?
    private var currentStreamID: String?           // ID of the in-flight stream request
    private var streamHeaderShown = false          // true once "Brain: " has been appended
    private var pendingTokens = ""                 // tokens buffered for the next 30-fps flush
    private var tokenFlushTimer: Timer?            // coalescing display timer (~30 fps)

    func applicationDidFinishLaunching(_ notification: Notification) {
        setupWindow()
        configureBridge()
        requestPermissions()
        bridge.start()

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
            self.speakAndLog("Brain Chat is ready. Press Enter to talk.", speaker: "Brain")
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        cleanupCopilotSession()
        streamingClient?.cancel()
        streamingClient = nil
        tokenFlushTimer?.invalidate()
        bridge.stop()
        stopListeningSession(cancelRecognition: true)
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func setupWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 820, height: 560),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Brain Chat"
        window.minSize = NSSize(width: 720, height: 480)
        window.center()

        let contentView = NSView(frame: window.contentView?.bounds ?? .zero)
        contentView.autoresizingMask = [.width, .height]
        window.contentView = contentView

        let titleLabel = NSTextField(labelWithString: "Brain Chat")
        titleLabel.font = NSFont.systemFont(ofSize: 32, weight: .bold)
        titleLabel.frame = NSRect(x: 40, y: 490, width: 300, height: 40)
        titleLabel.setAccessibilityLabel("Brain Chat")
        contentView.addSubview(titleLabel)

        modeBadgeLabel.font = NSFont.systemFont(ofSize: 13, weight: .medium)
        modeBadgeLabel.frame = NSRect(x: 580, y: 496, width: 200, height: 20)
        modeBadgeLabel.alignment = .right
        modeBadgeLabel.stringValue = "\(currentMode.displayName) Mode"
        modeBadgeLabel.setAccessibilityLabel("Current mode: \(currentMode.displayName)")
        contentView.addSubview(modeBadgeLabel)

        let instructionsLabel = NSTextField(wrappingLabelWithString: "Accessible voice chat for Joseph. Press Enter on the big button, speak your command, and Brain Chat will send it to Redpanda or answer locally if the broker is unavailable.")
        instructionsLabel.font = NSFont.systemFont(ofSize: 17)
        instructionsLabel.frame = NSRect(x: 40, y: 430, width: 740, height: 50)
        instructionsLabel.setAccessibilityLabel("Instructions")
        contentView.addSubview(instructionsLabel)

        listenButton.frame = NSRect(x: 40, y: 350, width: 740, height: 64)
        listenButton.bezelStyle = .regularSquare
        listenButton.font = NSFont.systemFont(ofSize: 28, weight: .bold)
        listenButton.target = self
        listenButton.action = #selector(toggleListening)
        listenButton.keyEquivalent = "\r"
        listenButton.keyEquivalentModifierMask = []
        listenButton.setAccessibilityLabel("Press Enter to talk")
        listenButton.setAccessibilityHelp("Starts and stops voice capture")
        contentView.addSubview(listenButton)

        statusLabel.frame = NSRect(x: 40, y: 312, width: 740, height: 24)
        statusLabel.font = NSFont.systemFont(ofSize: 16, weight: .medium)
        statusLabel.setAccessibilityLabel("Status")
        contentView.addSubview(statusLabel)

        let transcriptLabel = NSTextField(labelWithString: "Conversation")
        transcriptLabel.font = NSFont.systemFont(ofSize: 18, weight: .semibold)
        transcriptLabel.frame = NSRect(x: 40, y: 280, width: 200, height: 24)
        contentView.addSubview(transcriptLabel)

        scrollView.frame = NSRect(x: 40, y: 40, width: 740, height: 230)
        scrollView.hasVerticalScroller = true
        scrollView.borderType = .bezelBorder
        scrollView.autoresizingMask = [.width, .height]

        transcriptView.frame = scrollView.bounds
        transcriptView.isEditable = false
        transcriptView.isSelectable = true
        transcriptView.font = NSFont.monospacedSystemFont(ofSize: 15, weight: .regular)
        transcriptView.textContainerInset = NSSize(width: 12, height: 12)
        transcriptView.backgroundColor = NSColor.textBackgroundColor
        transcriptView.string = "Brain: Launching Brain Chat…\n"
        transcriptView.setAccessibilityLabel("Conversation transcript")
        scrollView.documentView = transcriptView
        contentView.addSubview(scrollView)

        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(listenButton)
        NSApp.activate(ignoringOtherApps: true)
    }

    private func configureBridge() {
        bridge.onAvailabilityChanged = { [weak self] availability in
            guard let self else { return }
            self.bridgeAvailability = availability
            switch availability {
            case .connected:
                self.updateStatus("Connected to Redpanda at localhost:9092")
            case .unavailable(let reason):
                self.updateStatus("Fallback mode: \(reason)")
            }
        }

        bridge.onResponse = { [weak self] response in
            guard let self else { return }
            self.handleRemoteResponse(response)
        }
    }

    private func requestPermissions() {
        listenButton.isEnabled = false
        updateStatus("Requesting microphone and speech recognition permissions…")

        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            DispatchQueue.main.async {
                self?.microphonePermissionGranted = granted
                self?.refreshPermissionState()
            }
        }

        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                self?.speechPermissionGranted = (status == .authorized)
                self?.refreshPermissionState()
            }
        }
    }

    private func refreshPermissionState() {
        let ready = microphonePermissionGranted && speechPermissionGranted && (speechRecognizer?.isAvailable ?? false)
        listenButton.isEnabled = ready

        if ready {
            updateStatus("Ready. Press Enter to talk.")
        } else if !microphonePermissionGranted {
            updateStatus("Microphone access is required. Enable it in System Settings.")
        } else if !speechPermissionGranted {
            updateStatus("Speech recognition access is required. Enable it in System Settings.")
        }
    }

    @objc private func toggleListening() {
        if isListening {
            let text = lastHeardText.trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty && !didProcessFinalResult {
                didProcessFinalResult = true
                finishListening(with: text)
            } else {
                stopListeningSession(cancelRecognition: true)
                if text.isEmpty {
                    speakAndLog("I didn't hear anything. Please try again.", speaker: "Brain")
                }
            }
        } else {
            startListening()
        }
    }

    private func startListening() {
        guard listenButton.isEnabled else {
            speakAndLog("Microphone or speech recognition permissions are not ready yet.", speaker: "Brain")
            return
        }

        guard let speechRecognizer, speechRecognizer.isAvailable else {
            speakAndLog("Speech recognition is not available right now.", speaker: "Brain")
            return
        }

        stopListeningSession(cancelRecognition: true, updateButton: false)
        didProcessFinalResult = false
        lastHeardText = ""
        isListening = true
        listenButton.title = "Listening… Press Enter to Stop"
        updateStatus("Listening…")

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.taskHint = .dictation
        recognitionRequest = request

        let inputNode = audioEngine.inputNode
        inputNode.removeTap(onBus: 0)

        recognitionTask = speechRecognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }

            if let result {
                let text = result.bestTranscription.formattedString.trimmingCharacters(in: .whitespacesAndNewlines)
                self.updateStatus(text.isEmpty ? "Listening…" : "Heard: \(text)")

                if !text.isEmpty {
                    self.lastHeardText = text
                }

                if result.isFinal, !text.isEmpty, !self.didProcessFinalResult {
                    self.didProcessFinalResult = true
                    self.finishListening(with: text)
                    return
                }
            }

            if let error, !self.didProcessFinalResult {
                self.stopListeningSession(cancelRecognition: true)
                self.speakAndLog("I could not understand that. Please try again.", speaker: "Brain")
                self.updateStatus("Speech recognition error: \(error.localizedDescription)")
            }
        }

        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        audioEngine.prepare()
        do {
            try audioEngine.start()
            speaker.speak("Listening")
        } catch {
            stopListeningSession(cancelRecognition: true)
            speakAndLog("Audio capture could not start.", speaker: "Brain")
            updateStatus("Audio error: \(error.localizedDescription)")
        }
    }

    private func finishListening(with text: String) {
        stopListeningSession(cancelRecognition: false)
        processInput(text)
    }

    private func stopListeningSession(cancelRecognition: Bool, updateButton: Bool = true) {
        if audioEngine.isRunning {
            audioEngine.stop()
        }

        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        if cancelRecognition {
            recognitionTask?.cancel()
        }
        recognitionRequest = nil
        recognitionTask = nil
        isListening = false

        if updateButton {
            listenButton.title = "Press Enter to Talk"
        }
    }

    private func processInput(_ text: String) {
        if tryHandleCopilotInput(text) { return }
        if text.hasPrefix("/") { handleAppModeCommand(text); return }
        if currentMode == .yolo { handleAppYOLOCommand(text); return }
        // Cancel any previous stream before starting a fresh one.
        streamingClient?.cancel()
        streamingClient = nil
        tokenFlushTimer?.invalidate()
        tokenFlushTimer = nil
        pendingTokens = ""

        appendTranscript(speaker: "You", text: text)
        let requestID = UUID().uuidString
        currentStreamID = requestID
        streamHeaderShown = false
        updateStatus("Connecting to local AI…")

        let client = LLMStreamingClient()
        streamingClient = client

        client.stream(
            config: .mode(currentMode),
            userText: text,
            onToken: { [weak self] token in
                guard let self, self.currentStreamID == requestID else { return }
                self.handleIncomingToken(token)
            },
            onComplete: { [weak self] fullText, error in
                guard let self, self.currentStreamID == requestID else { return }
                self.handleStreamCompletion(fullText: fullText, error: error,
                                            originalText: text, requestID: requestID)
            }
        )
    }

    private func scheduleFallback(for requestID: String, originalText: String) {
        let workItem = DispatchWorkItem { [weak self] in
            self?.respondLocally(to: originalText, requestID: requestID, reason: self?.availabilityReason ?? "no response received")
        }
        pendingFallbacks[requestID] = workItem
        DispatchQueue.main.asyncAfter(deadline: .now() + 7, execute: workItem)
    }

    private func handleRemoteResponse(_ response: BridgeResponse) {
        if let requestID = response.requestID {
            resolvePendingRequest(id: requestID)
        } else if let next = pendingRequestOrder.first {
            resolvePendingRequest(id: next)
        }

        updateStatus(response.isPartial && !response.isFinal ? "Streaming AI response…" : "Received AI response from brain.voice.response")
        appendTranscript(speaker: "Brain", text: ANSIText.strip(response.text))
        if response.isFinal {
            speaker.speak(response.text)
        }
    }

    private func respondLocally(to text: String, requestID: String, reason: String) {
        resolvePendingRequest(id: requestID)
        let response = fallbackResponder.response(for: text, reason: reason)
        updateStatus("Responding locally")
        appendTranscript(speaker: "Brain", text: response)
        speaker.speak(response)
    }

    // MARK: - Streaming Display

    private func handleIncomingToken(_ token: String) {
        // Defer adding the "Brain: " label until the first real token arrives —
        // so nothing appears in the transcript if the stream fails immediately.
        if !streamHeaderShown {
            streamHeaderShown = true
            appendRaw("Brain: ")
        }
        pendingTokens += token
        updateStatus("Receiving response…")
        scheduleTokenFlush()
    }

    /// Coalesces rapid token arrivals into ~30-fps display batches, reducing
    /// NSTextView layout passes and keeping the output smooth without flickering.
    private func scheduleTokenFlush() {
        guard tokenFlushTimer == nil else { return }
        tokenFlushTimer = Timer.scheduledTimer(withTimeInterval: 1.0 / 30.0, repeats: false) { [weak self] _ in
            self?.tokenFlushTimer = nil
            self?.flushPendingTokens()
        }
    }

    private func flushPendingTokens() {
        guard !pendingTokens.isEmpty else { return }
        let chunk = pendingTokens
        pendingTokens = ""
        appendRaw(chunk)
        transcriptView.scrollToEndOfDocument(nil)
    }

    private func handleStreamCompletion(fullText: String, error: Error?,
                                         originalText: String, requestID: String) {
        // Flush any tokens still held in the coalescing buffer.
        tokenFlushTimer?.invalidate()
        tokenFlushTimer = nil
        flushPendingTokens()
        streamingClient = nil

        if fullText.isEmpty {
            // Stream produced no content — fall through to Redpanda then local fallback.
            updateStatus("Local AI unavailable. Trying Redpanda…")
            useRedpandaPath(text: originalText, requestID: requestID)
        } else {
            // Finalize the streamed entry with a blank separator line and speak it.
            appendRaw("\n\n")
            transcriptView.scrollToEndOfDocument(nil)
            if currentMode.speaksResponses { speaker.speak(fullText) }
            updateStatus("Ready. \(currentMode.displayName) mode. Press Enter to talk.")
        }
    }

    /// Falls back to the Redpanda bridge when direct LLM streaming is unavailable.
    private func useRedpandaPath(text: String, requestID: String) {
        pendingRequestOrder.append(requestID)
        updateStatus("Sending your voice command to Redpanda…")
        bridge.publish(text: text, requestID: requestID) { [weak self] success, reason in
            guard let self else { return }
            if success {
                self.updateStatus("Waiting for AI response on brain.voice.response…")
                self.scheduleFallback(for: requestID, originalText: text)
            } else {
                self.updateStatus("Redpanda publish failed. Using local fallback.")
                self.respondLocally(to: text, requestID: requestID, reason: reason ?? "publish failed")
            }
        }
    }

    /// Appends text directly to the transcript storage using the view's current font.
    /// Must be called on the main thread.
    private func appendRaw(_ text: String) {
        guard let storage = transcriptView.textStorage else { return }
        let font = transcriptView.font ?? NSFont.monospacedSystemFont(ofSize: 15, weight: .regular)
        storage.beginEditing()
        storage.append(NSAttributedString(string: ANSIText.strip(text), attributes: [.font: font]))
        storage.endEditing()
    }

    private func resolvePendingRequest(id: String) {
        pendingFallbacks[id]?.cancel()
        pendingFallbacks[id] = nil
        pendingRequestOrder.removeAll { $0 == id }
    }

    private var availabilityReason: String {
        switch bridgeAvailability {
        case .connected:
            return "broker is connected but no response arrived"
        case .unavailable(let reason):
            return reason
        }
    }

    private func updateStatus(_ text: String) {
        statusLabel.stringValue = text
    }

    private func appendTranscript(speaker: String, text: String) {
        let entry = "\(speaker): \(ANSIText.strip(text))\n\n"
        let attributed = NSAttributedString(string: entry)
        transcriptView.textStorage?.append(attributed)
        transcriptView.scrollToEndOfDocument(nil)
    }


    // MARK: - Mode Management

    private func handleAppModeCommand(_ input: String) {
        let cmd = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        if cmd == "/modes" || cmd == "/help" {
            var lines = ["Available modes:"]
            for mode in ChatMode.allCases {
                lines.append((mode == currentMode ? "> " : "  ")
                             + mode.switchCommand + ": " + mode.modeDescription)
            }
            speakAndLog(lines.joined(separator: "\n"), speaker: "Brain")
            return
        }
        if let mode = ChatMode.allCases.first(where: { cmd == $0.switchCommand }) {
            currentMode = mode
            ModePreferences.save(mode)
            modeBadgeLabel.stringValue = "\(mode.displayName) Mode"
            modeBadgeLabel.setAccessibilityLabel("Current mode: \(mode.displayName)")
            speakAndLog("Switched to \(mode.displayName) mode. \(mode.modeDescription)", speaker: "Brain")
            updateStatus("Mode: \(mode.displayName)")
        } else {
            speakAndLog("Unknown command: \(input). Say slash modes for help.", speaker: "Brain")
        }
    }

    private func handleAppYOLOCommand(_ command: String) {
        appendTranscript(speaker: "You", text: "yolo: \(command)")
        updateStatus("Publishing YOLO command to brain.yolo.commands…")
        let reqID = UUID().uuidString
        bridge.publish(text: "yolo: \(command)", requestID: reqID) { [weak self] success, reason in
            guard let self else { return }
            if success {
                self.speakAndLog("YOLO command published: \(command)", speaker: "Brain")
                self.updateStatus("Ready. Press Enter to talk.")
            } else {
                self.speakAndLog("YOLO publish failed: \(reason ?? "unknown error")", speaker: "Brain")
                self.updateStatus("YOLO publish failed.")
            }
        }
    }

    private func speakAndLog(_ text: String, speaker: String) {
        appendTranscript(speaker: speaker, text: text)
        self.speaker.speak(text)
    }
}

if TerminalChatController.shouldRunInTerminal {
    let terminalChat = TerminalChatController()
    terminalChat.run()
} else {
    let app = NSApplication.shared
    let delegate = AppDelegate()
    app.setActivationPolicy(.regular)
    app.delegate = delegate
    app.run()
}
