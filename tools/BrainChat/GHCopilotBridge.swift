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
