import Foundation

enum CopilotError: Error, LocalizedError, Equatable {
    case cliNotFound
    case timeout
    case executionFailed(code: Int32, stderr: String)
    case emptyResponse
    case alreadyRunning

    var errorDescription: String? {
        switch self {
        case .cliNotFound:
            return "Copilot CLI not found at expected path."
        case .timeout:
            return "Copilot CLI timed out after 30 seconds."
        case .executionFailed(let code, let stderr):
            return "Copilot exited with code \(code): \(stderr)"
        case .emptyResponse:
            return "Copilot returned an empty response."
        case .alreadyRunning:
            return "A Copilot command is already running."
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

protocol CopilotCLIRunning {
    var isAvailable: Bool { get }
    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> (stdout: String, stderr: String, exitCode: Int32)
    func cancel()
}

final class ProcessCopilotRunner: CopilotCLIRunning {
    private var runningProcess: Process?

    var isAvailable: Bool {
        FileManager.default.isExecutableFile(atPath: "/Users/joe/.local/bin/copilot")
    }

    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> (stdout: String, stderr: String, exitCode: Int32) {
        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        process.executableURL = URL(fileURLWithPath: cliPath)
        process.arguments = ["-p", prompt, "--output-format", "text"]
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        var env = ProcessInfo.processInfo.environment
        let extraPaths = ["/opt/homebrew/bin", "/usr/local/bin", "/Users/joe/.local/bin"]
        let currentPath = env["PATH"] ?? "/usr/bin:/bin"
        env["PATH"] = (extraPaths + [currentPath]).joined(separator: ":")
        process.environment = env

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

        let stdout = String(data: stdoutPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let stderr = String(data: stderrPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        runningProcess = nil

        if didTimeout {
            throw CopilotError.timeout
        }

        return (stdout, stderr, process.terminationStatus)
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
    private let statusCallback: ((CopilotStatus) -> Void)?
    private var isExecuting = false

    init(
        cliPath: String = "/Users/joe/.local/bin/copilot",
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

    func execute(prompt: String, completion: @escaping (Result<CopilotResponse, Error>) -> Void) {
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

    func cancelCurrent() {
        runner.cancel()
        commandQueue.async { [weak self] in
            self?.isExecuting = false
            self?.emitStatus(.idle)
        }
    }

    func parseResponse(_ raw: String, duration: TimeInterval) -> CopilotResponse {
        let blocks = extractCodeBlocks(from: raw)
        return CopilotResponse(
            text: raw,
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

    private func emitStatus(_ status: CopilotStatus) {
        DispatchQueue.main.async { [statusCallback] in
            statusCallback?(status)
        }
    }
}
