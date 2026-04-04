import Darwin
import Foundation

enum CopilotError: Error, LocalizedError, Equatable {
    case cliNotFound
    case timeout
    case executionFailed(code: Int32, stderr: String)
    case emptyResponse
    case alreadyRunning
    case sessionNotRunning
    case sessionStartFailed(String)

    var errorDescription: String? {
        switch self {
        case .cliNotFound:
            return "GitHub Copilot CLI not found. Install gh with Copilot extension or the standalone copilot binary."
        case .timeout:
            return "Copilot CLI timed out after 30 seconds."
        case .executionFailed(let code, let stderr):
            return "Copilot exited with code \(code): \(stderr)"
        case .emptyResponse:
            return "Copilot returned an empty response."
        case .alreadyRunning:
            return "A Copilot command is already running."
        case .sessionNotRunning:
            return "No Copilot chat session is running."
        case .sessionStartFailed(let message):
            return "Failed to start Copilot chat: \(message)"
        }
    }
}

struct CopilotResponse: Equatable {
    let text: String
    let duration: TimeInterval
    let isCodeBlock: Bool
    let language: String?
    let codeBlocks: [(language: String?, code: String)]

    static func == (lhs: CopilotResponse, rhs: CopilotResponse) -> Bool {
        lhs.text == rhs.text &&
            lhs.duration == rhs.duration &&
            lhs.isCodeBlock == rhs.isCodeBlock &&
            lhs.language == rhs.language &&
            lhs.codeBlocks.count == rhs.codeBlocks.count &&
            zip(lhs.codeBlocks, rhs.codeBlocks).allSatisfy { left, right in
                left.language == right.language && left.code == right.code
            }
    }
}

enum CopilotCommandMode: String, CaseIterable {
    case chat
    case suggest
    case explain
}

enum CopilotCommand: Equatable {
    case chat(String)
    case suggest(String)
    case explain(String)
    case startSession
    case stopSession
    case restartSession
}

struct CopilotCLIPaths {
    static let pathExtensions: [String] = {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        return ["/opt/homebrew/bin", "/usr/local/bin", "\(home)/.local/bin"]
    }()

    static let ghPath: String? = {
        ["/opt/homebrew/bin/gh", "/usr/local/bin/gh", "/usr/bin/gh"]
            .first(where: { FileManager.default.isExecutableFile(atPath: $0) })
    }()

    static let copilotBinaryPath: String? = {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        return [
            "\(home)/.local/bin/copilot",
            "/usr/local/bin/copilot",
            "/opt/homebrew/bin/copilot"
        ].first(where: { FileManager.default.isExecutableFile(atPath: $0) })
    }()

    static func buildEnvironment(term: String) -> [String: String] {
        var environment = ProcessInfo.processInfo.environment
        let currentPath = environment["PATH"] ?? "/usr/bin:/bin"
        environment["PATH"] = (pathExtensions + [currentPath]).joined(separator: ":")
        environment["TERM"] = term
        environment.removeValue(forKey: "NO_COLOR")
        return environment
    }
}

enum CopilotANSIText {
    static func strip(_ text: String) -> String {
        let patterns = [
            #"\u{001B}\[[0-9;?]*[ -/]*[@-~]"#,
            #"\u{001B}\][^\u{0007}]*\u{0007}"#,
            #"\u{001B}[()][A-Za-z0-9]"#,
            #"\u{0008}"#
        ]

        var cleaned = text.replacingOccurrences(of: "\r\n", with: "\n")
        cleaned = cleaned.replacingOccurrences(of: "\r", with: "\n")

        for pattern in patterns {
            cleaned = cleaned.replacingOccurrences(of: pattern, with: "", options: .regularExpression)
        }

        return cleaned
    }
}

protocol CopilotCLIRunning {
    var isAvailable: Bool { get }
    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> (stdout: String, stderr: String, exitCode: Int32)
    func cancel()
}

final class ProcessCopilotRunner: CopilotCLIRunning {
    private var runningProcess: Process?

    var isAvailable: Bool {
        CopilotCLIPaths.copilotBinaryPath != nil || CopilotCLIPaths.ghPath != nil
    }

    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> (stdout: String, stderr: String, exitCode: Int32) {
        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        if FileManager.default.isExecutableFile(atPath: cliPath) {
            process.executableURL = URL(fileURLWithPath: cliPath)
            process.arguments = ["-p", prompt, "--output-format", "text"]
        } else if let ghPath = CopilotCLIPaths.ghPath {
            process.executableURL = URL(fileURLWithPath: ghPath)
            process.arguments = ["copilot", "--", "suggest", prompt]
        } else {
            throw CopilotError.cliNotFound
        }

        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe
        process.environment = CopilotCLIPaths.buildEnvironment(term: "dumb")

        runningProcess = process
        try process.run()

        let deadline = DispatchTime.now() + timeout
        let semaphore = DispatchSemaphore(value: 0)
        var didTimeout = false

        DispatchQueue.global().async {
            process.waitUntilExit()
            semaphore.signal()
        }

        if semaphore.wait(timeout: deadline) == .timedOut {
            didTimeout = true
            process.terminate()
            usleep(200_000)
            if process.isRunning {
                process.interrupt()
            }
        }

        let stdout = String(data: stdoutPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let stderr = String(data: stderrPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        runningProcess = nil

        if didTimeout {
            throw CopilotError.timeout
        }

        return (CopilotANSIText.strip(stdout), CopilotANSIText.strip(stderr), process.terminationStatus)
    }

    func cancel() {
        if let runningProcess, runningProcess.isRunning {
            runningProcess.terminate()
        }
        runningProcess = nil
    }
}

final class CopilotBridge: @unchecked Sendable {
    static let shared = CopilotBridge()

    enum CopilotStatus {
        case idle
        case thinking(prompt: String)
        case responding
        case error(String)
        case complete(CopilotResponse)
    }

    private let cliPath: String
    private let timeoutSeconds: TimeInterval
    private let runner: CopilotCLIRunning
    private let commandQueue = DispatchQueue(label: "com.brain.copilot.queue")
    private let sessionQueue = DispatchQueue(label: "com.brain.copilot.session")
    private let statusCallback: ((CopilotStatus) -> Void)?

    private var isExecuting = false

    private var chatProcess: Process?
    private var masterFD: Int32 = -1
    private var readChannel: DispatchIO?
    private var responseBuffer = ""
    private var pendingDeltaHandler: ((String) -> Void)?
    private var pendingCompletion: ((Result<CopilotResponse, Error>) -> Void)?
    private var pendingStartedAt: Date?
    private var flushTimer: DispatchSourceTimer?
    private(set) var isSessionActive = false
    private(set) var currentMode: CopilotCommandMode = .chat

    init(
        cliPath: String = CopilotCLIPaths.copilotBinaryPath ?? "",
        timeoutSeconds: TimeInterval = 30,
        runner: CopilotCLIRunning = ProcessCopilotRunner(),
        onStatusChange: ((CopilotStatus) -> Void)? = nil
    ) {
        self.cliPath = cliPath
        self.timeoutSeconds = timeoutSeconds
        self.runner = runner
        self.statusCallback = onStatusChange
    }

    var isAvailable: Bool {
        runner.isAvailable
    }

    var isBusy: Bool {
        commandQueue.sync { isExecuting }
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
            ("/copilot ", { .chat($0) }),
            ("/suggest ", { .suggest($0) }),
            ("/explain ", { .explain($0) })
        ]

        for (prefix, builder) in prefixes where lowered.hasPrefix(prefix) {
            let prompt = String(trimmed.dropFirst(prefix.count)).trimmingCharacters(in: .whitespacesAndNewlines)
            guard !prompt.isEmpty else { return nil }
            return builder(prompt)
        }

        return nil
    }

    func execute(prompt: String, completion: @escaping @Sendable (Result<CopilotResponse, Error>) -> Void) {
        commandQueue.async { [weak self] in
            guard let self else { return }
            guard !self.isExecuting else {
                DispatchQueue.main.async { completion(.failure(CopilotError.alreadyRunning)) }
                return
            }
            guard self.isAvailable else {
                DispatchQueue.main.async { completion(.failure(CopilotError.cliNotFound)) }
                return
            }

            self.isExecuting = true
            self.emitStatus(.thinking(prompt: prompt))
            let started = Date()

            do {
                let result = try self.runner.run(prompt: prompt, cliPath: self.cliPath, timeout: self.timeoutSeconds)
                let output = result.stdout.trimmingCharacters(in: .whitespacesAndNewlines)
                guard result.exitCode == 0 else {
                    throw CopilotError.executionFailed(code: result.exitCode, stderr: result.stderr.isEmpty ? "Unknown error" : result.stderr)
                }
                guard !output.isEmpty else {
                    throw CopilotError.emptyResponse
                }
                self.emitStatus(.responding)
                let response = self.parseResponse(output, duration: Date().timeIntervalSince(started))
                self.isExecuting = false
                self.emitStatus(.complete(response))
                DispatchQueue.main.async { completion(.success(response)) }
            } catch {
                self.isExecuting = false
                self.emitStatus(.error(error.localizedDescription))
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }
    }

    func execute(prompt: String) async throws -> CopilotResponse {
        try await withCheckedThrowingContinuation { continuation in
            execute(prompt: prompt) { result in
                continuation.resume(with: result)
            }
        }
    }

    func executeOneShot(
        mode: CopilotCommandMode,
        prompt: String,
        onDelta: (@Sendable (String) -> Void)? = nil,
        completion: @escaping @Sendable (Result<CopilotResponse, Error>) -> Void
    ) {
        commandQueue.async { [weak self] in
            guard let self else { return }
            guard !self.isExecuting else {
                DispatchQueue.main.async { completion(.failure(CopilotError.alreadyRunning)) }
                return
            }
            guard self.isAvailable else {
                DispatchQueue.main.async { completion(.failure(CopilotError.cliNotFound)) }
                return
            }

            self.isExecuting = true
            self.emitStatus(.thinking(prompt: prompt))
            let started = Date()

            do {
                let process = Process()
                let stdoutPipe = Pipe()
                let stderrPipe = Pipe()

                if let ghPath = CopilotCLIPaths.ghPath {
                    process.executableURL = URL(fileURLWithPath: ghPath)
                    process.arguments = ["copilot", "--", mode.rawValue, prompt]
                } else if FileManager.default.isExecutableFile(atPath: self.cliPath) {
                    process.executableURL = URL(fileURLWithPath: self.cliPath)
                    process.arguments = ["-p", prompt, "--output-format", "text"]
                } else {
                    throw CopilotError.cliNotFound
                }

                process.standardOutput = stdoutPipe
                process.standardError = stderrPipe
                process.environment = CopilotCLIPaths.buildEnvironment(term: "dumb")

                try process.run()

                let semaphore = DispatchSemaphore(value: 0)
                var didTimeout = false

                DispatchQueue.global().async {
                    process.waitUntilExit()
                    semaphore.signal()
                }

                if semaphore.wait(timeout: .now() + self.timeoutSeconds) == .timedOut {
                    didTimeout = true
                    process.terminate()
                    usleep(200_000)
                    if process.isRunning {
                        process.interrupt()
                    }
                }

                let stdout = String(data: stdoutPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                let stderr = String(data: stderrPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
                let cleanedOutput = CopilotANSIText.strip(stdout).trimmingCharacters(in: .whitespacesAndNewlines)
                let cleanedError = CopilotANSIText.strip(stderr).trimmingCharacters(in: .whitespacesAndNewlines)

                self.isExecuting = false

                if didTimeout {
                    throw CopilotError.timeout
                }
                guard process.terminationStatus == 0 else {
                    throw CopilotError.executionFailed(
                        code: process.terminationStatus,
                        stderr: cleanedError.isEmpty ? "Unknown error" : cleanedError
                    )
                }
                guard !cleanedOutput.isEmpty else {
                    throw CopilotError.emptyResponse
                }

                let response = self.parseResponse(cleanedOutput, duration: Date().timeIntervalSince(started))
                self.emitStatus(.complete(response))
                DispatchQueue.main.async {
                    onDelta?(cleanedOutput)
                    completion(.success(response))
                }
            } catch {
                self.isExecuting = false
                self.emitStatus(.error(error.localizedDescription))
                DispatchQueue.main.async { completion(.failure(error)) }
            }
        }
    }

    func executeOneShot(mode: CopilotCommandMode, prompt: String) async throws -> CopilotResponse {
        try await withCheckedThrowingContinuation { continuation in
            executeOneShot(mode: mode, prompt: prompt, completion: { result in
                continuation.resume(with: result)
            })
        }
    }

    func startSession(mode: CopilotCommandMode = .chat) throws {
        try sessionQueue.sync {
            try startSessionLocked(mode: mode)
        }
    }

    func stopSession() {
        sessionQueue.async { [weak self] in
            self?.endSessionLocked()
        }
    }

    func restartSession() throws {
        try sessionQueue.sync {
            try startSessionLocked(mode: currentMode)
        }
    }

    func sendChat(
        _ message: String,
        onDelta: @escaping (String) -> Void,
        completion: @escaping (Result<CopilotResponse, Error>) -> Void
    ) throws {
        try sessionQueue.sync {
            guard isSessionActive, masterFD >= 0 else {
                throw CopilotError.sessionNotRunning
            }
            guard pendingCompletion == nil else {
                throw CopilotError.alreadyRunning
            }

            responseBuffer = ""
            pendingStartedAt = Date()
            pendingDeltaHandler = onDelta
            pendingCompletion = completion

            let payload = Data((message + "\n").utf8)
            let bytesWritten = payload.withUnsafeBytes { buffer in
                guard let baseAddress = buffer.baseAddress else { return -1 }
                return Darwin.write(masterFD, baseAddress, buffer.count)
            }

            if bytesWritten < 0 {
                clearPendingResponseLocked()
                throw CopilotError.executionFailed(code: Int32(errno), stderr: String(cString: strerror(errno)))
            }

            rescheduleFlushLocked()
        }
    }

    func cancelCurrent() {
        runner.cancel()
        sessionQueue.async { [weak self] in
            guard let self else { return }
            self.finishPendingResponseLocked(with: .failure(CopilotError.timeout))
        }
        commandQueue.async { [weak self] in
            self?.isExecuting = false
            self?.emitStatus(.idle)
        }
    }

    func parseResponse(_ raw: String, duration: TimeInterval) -> CopilotResponse {
        let cleaned = CopilotANSIText.strip(raw).trimmingCharacters(in: .whitespacesAndNewlines)
        let blocks = extractCodeBlocks(from: cleaned)
        return CopilotResponse(
            text: cleaned,
            duration: duration,
            isCodeBlock: !blocks.isEmpty,
            language: blocks.first?.language,
            codeBlocks: blocks
        )
    }

    func extractCodeBlocks(from text: String) -> [(language: String?, code: String)] {
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

    private func beginReadLoopLocked() {
        guard masterFD >= 0 else { return }

        let channel = DispatchIO(type: .stream, fileDescriptor: masterFD, queue: sessionQueue) { [weak self] _ in
            self?.closeMasterLocked()
        }
        channel.setLimit(lowWater: 1)
        readChannel = channel

        channel.read(offset: 0, length: Int.max, queue: sessionQueue) { [weak self] done, dispatchData, error in
            guard let self else { return }

            if let dispatchData, !dispatchData.isEmpty, self.pendingCompletion != nil {
                let chunk = String(decoding: Data(dispatchData), as: UTF8.self)
                let cleaned = CopilotANSIText.strip(chunk)
                let trimmed = cleaned.trimmingCharacters(in: .whitespacesAndNewlines)
                if !trimmed.isEmpty {
                    self.responseBuffer += cleaned
                    let onDelta = self.pendingDeltaHandler
                    DispatchQueue.main.async {
                        onDelta?(cleaned)
                    }
                    self.rescheduleFlushLocked()
                }
            }

            if error != 0 || done {
                if done {
                    self.readChannel = nil
                }
                self.handleInteractiveTerminationLocked()
            }
        }
    }

    private func rescheduleFlushLocked() {
        flushTimer?.cancel()
        let timer = DispatchSource.makeTimerSource(queue: sessionQueue)
        timer.schedule(deadline: .now() + 1.0)
        timer.setEventHandler { [weak self] in
            self?.finishPendingResponseLocked()
        }
        flushTimer = timer
        timer.resume()
    }

    private func finishPendingResponseLocked(with forcedResult: Result<CopilotResponse, Error>? = nil) {
        guard let completion = pendingCompletion else { return }

        flushTimer?.cancel()
        flushTimer = nil

        let result: Result<CopilotResponse, Error>
        if let forcedResult {
            result = forcedResult
        } else {
            let startedAt = pendingStartedAt ?? Date()
            let finalText = responseBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            if finalText.isEmpty {
                result = .failure(CopilotError.emptyResponse)
            } else {
                result = .success(parseResponse(finalText, duration: Date().timeIntervalSince(startedAt)))
            }
        }

        clearPendingResponseLocked()

        DispatchQueue.main.async {
            completion(result)
        }
    }

    private func clearPendingResponseLocked() {
        pendingCompletion = nil
        pendingDeltaHandler = nil
        pendingStartedAt = nil
        responseBuffer = ""
    }

    private func handleInteractiveTerminationLocked() {
        isSessionActive = false
        readChannel?.close(flags: .stop)
        readChannel = nil
        closeMasterLocked()

        if pendingCompletion != nil {
            let text = responseBuffer.trimmingCharacters(in: .whitespacesAndNewlines)
            if text.isEmpty {
                finishPendingResponseLocked(with: .failure(CopilotError.sessionNotRunning))
            } else {
                let startedAt = pendingStartedAt ?? Date()
                let response = parseResponse(text, duration: Date().timeIntervalSince(startedAt))
                finishPendingResponseLocked(with: .success(response))
            }
        } else {
            clearPendingResponseLocked()
        }
    }

    private func endSessionLocked() {
        flushTimer?.cancel()
        flushTimer = nil
        readChannel?.close(flags: .stop)
        readChannel = nil

        if let process = chatProcess, process.isRunning, masterFD >= 0 {
            let quitData = Data("/quit\n".utf8)
            _ = quitData.withUnsafeBytes { buffer in
                Darwin.write(masterFD, buffer.baseAddress, buffer.count)
            }
            usleep(200_000)
            if process.isRunning {
                process.terminate()
            }
        }

        chatProcess = nil
        isSessionActive = false
        closeMasterLocked()
        clearPendingResponseLocked()
    }

    private func startSessionLocked(mode: CopilotCommandMode) throws {
        endSessionLocked()
        currentMode = mode

        guard mode == .chat else { return }
        guard let ghPath = CopilotCLIPaths.ghPath else {
            throw CopilotError.cliNotFound
        }

        var masterDescriptor: Int32 = -1
        var slaveDescriptor: Int32 = -1
        guard openpty(&masterDescriptor, &slaveDescriptor, nil, nil, nil) == 0 else {
            throw CopilotError.sessionStartFailed(String(cString: strerror(errno)))
        }

        masterFD = masterDescriptor

        var windowSize = winsize(ws_row: 50, ws_col: 120, ws_xpixel: 0, ws_ypixel: 0)
        _ = ioctl(masterDescriptor, TIOCSWINSZ, &windowSize)

        let process = Process()
        process.executableURL = URL(fileURLWithPath: ghPath)
        process.arguments = ["copilot", "--", "chat"]
        process.currentDirectoryURL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("brain", isDirectory: true)
        process.environment = CopilotCLIPaths.buildEnvironment(term: "xterm-256color")

        let slaveHandle = FileHandle(fileDescriptor: slaveDescriptor, closeOnDealloc: true)
        process.standardInput = slaveHandle
        process.standardOutput = slaveHandle
        process.standardError = slaveHandle

        process.terminationHandler = { [weak self] _ in
            self?.sessionQueue.async {
                self?.handleInteractiveTerminationLocked()
            }
        }

        do {
            try process.run()
        } catch {
            close(masterDescriptor)
            masterFD = -1
            throw CopilotError.sessionStartFailed(error.localizedDescription)
        }

        chatProcess = process
        isSessionActive = true
        beginReadLoopLocked()
    }

    private func closeMasterLocked() {
        guard masterFD >= 0 else { return }
        Darwin.close(masterFD)
        masterFD = -1
    }

    private func emitStatus(_ status: CopilotStatus) {
        DispatchQueue.main.async { [statusCallback] in
            statusCallback?(status)
        }
    }

    deinit {
        endSessionLocked()
    }
}
