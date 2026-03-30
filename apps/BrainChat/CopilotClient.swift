import Foundation

protocol CopilotStreaming: Sendable {
    func streamResponse(
        prompt: String,
        yoloMode: Bool,
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String
}

protocol CopilotCommandRunning: Sendable {
    func isAvailable(atPath path: String) -> Bool
    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> String
}

struct ProcessCopilotCommandRunner: CopilotCommandRunning {
    func isAvailable(atPath path: String) -> Bool {
        FileManager.default.isExecutableFile(atPath: path)
    }

    func run(prompt: String, cliPath: String, timeout: TimeInterval) throws -> String {
        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        process.executableURL = URL(fileURLWithPath: cliPath)
        process.arguments = ["-p", prompt]
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        var env = ProcessInfo.processInfo.environment
        let extraPaths = ["/opt/homebrew/bin", "/usr/local/bin", "/Users/joe/.local/bin"]
        let currentPath = env["PATH"] ?? "/usr/bin:/bin"
        env["PATH"] = (extraPaths + [currentPath]).joined(separator: ":")
        process.environment = env

        try process.run()

        let deadline = DispatchTime.now() + timeout
        let done = DispatchSemaphore(value: 0)
        var timedOut = false

        DispatchQueue.global().async {
            process.waitUntilExit()
            done.signal()
        }

        if done.wait(timeout: deadline) == .timedOut {
            timedOut = true
            process.terminate()
            usleep(200_000)
            if process.isRunning { process.interrupt() }
        }

        if timedOut {
            throw AIServiceError.httpStatus(408, "Copilot CLI timed out after \(Int(timeout)) seconds.")
        }

        let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()

        let stdout = String(data: stdoutData, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let stderr = String(data: stderrData, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        guard process.terminationStatus == 0 else {
            throw AIServiceError.httpStatus(
                Int(process.terminationStatus),
                stderr.isEmpty ? "Copilot CLI failed." : stderr
            )
        }

        return stdout
    }
}

struct CopilotClient: CopilotStreaming, Sendable {
    let cliPath: String
    let timeout: TimeInterval
    private let runner: any CopilotCommandRunning

    init(
        cliPath: String = "/Users/joe/.local/bin/copilot",
        timeout: TimeInterval = 30,
        runner: any CopilotCommandRunning = ProcessCopilotCommandRunner()
    ) {
        self.cliPath = cliPath
        self.timeout = timeout
        self.runner = runner
    }

    var isAvailable: Bool {
        runner.isAvailable(atPath: cliPath)
    }

    func streamResponse(
        prompt: String,
        yoloMode: Bool,
        onDelta: @escaping @Sendable (String) -> Void
    ) async throws -> String {
        guard isAvailable else {
            throw AIServiceError.missingAPIKey("GitHub Copilot CLI not installed at \(cliPath)")
        }

        let fullPrompt = yoloMode ? "/yolo \(prompt)" : prompt

        return try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                do {
                    let output = try runner.run(prompt: fullPrompt, cliPath: cliPath, timeout: timeout)
                    guard !output.isEmpty else {
                        continuation.resume(throwing: AIServiceError.emptyResponse("Copilot CLI returned an empty response."))
                        return
                    }
                    onDelta(output)
                    continuation.resume(returning: output)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }
}
