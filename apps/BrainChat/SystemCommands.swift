import Foundation

// =============================================================================
// SystemCommands - Safe shell execution, clipboard, URLs, and AppleScript
// Provides system integration for BrainChat with permission checks
// =============================================================================

enum SystemCommandError: Error, LocalizedError {
    case executionFailed(code: Int32, output: String)
    case timeout
    case fileNotFound(String)
    case permissionDenied(String)
    case invalidPath(String)

    var errorDescription: String? {
        switch self {
        case .executionFailed(let code, let output):
            return "Command failed (exit \(code)): \(output)"
        case .timeout:
            return "Command timed out."
        case .fileNotFound(let path):
            return "File not found: \(path)"
        case .permissionDenied(let reason):
            return "Permission denied: \(reason)"
        case .invalidPath(let path):
            return "Invalid or unsafe path: \(path)"
        }
    }
}

struct CommandResult {
    let stdout: String
    let stderr: String
    let exitCode: Int32
    let duration: TimeInterval

    var succeeded: Bool { exitCode == 0 }
    var output: String { stdout.isEmpty ? stderr : stdout }
}

final class SystemCommands: @unchecked Sendable {
    static let shared = SystemCommands()

    private let defaultTimeout: TimeInterval = 15
    private let maxTimeout: TimeInterval = 60

    /// When registered, speak() routes through VoiceManager instead of macOS say.
    private var speechDelegate: (@Sendable (String) -> Void)?

    func registerSpeechDelegate(_ handler: @escaping @Sendable (String) -> Void) {
        speechDelegate = handler
    }

    func unregisterSpeechDelegate() {
        speechDelegate = nil
    }

    // Directories the app is allowed to read/write
    private let allowedRoots: [String] = [
        NSHomeDirectory(),
        NSHomeDirectory() + "/brain",
        NSHomeDirectory() + "/Desktop",
        NSHomeDirectory() + "/Documents",
        NSHomeDirectory() + "/Downloads"
    ]

    // Commands that are never allowed
    private let blockedCommands: Set<String> = [
        "rm -rf /", "rm -rf ~", "mkfs", "dd if=",
        "shutdown", "reboot", "halt",
        "passwd", "sudo rm", "chmod -R 777 /"
    ]

    // MARK: - Shell Execution

    /// Run a shell command with timeout and safety checks.
    func run(
        _ command: String,
        timeout: TimeInterval? = nil,
        workingDirectory: String? = nil
    ) throws -> CommandResult {
        // Safety: reject dangerous commands
        let lower = command.lowercased()
        for blocked in blockedCommands {
            if lower.contains(blocked) {
                throw SystemCommandError.permissionDenied(
                    "Command contains blocked pattern: \(blocked)"
                )
            }
        }

        let effectiveTimeout = min(timeout ?? defaultTimeout, maxTimeout)
        let startTime = Date()

        let process = Process()
        let stdoutPipe = Pipe()
        let stderrPipe = Pipe()

        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = ["-lc", command]
        process.standardOutput = stdoutPipe
        process.standardError = stderrPipe

        if let dir = workingDirectory {
            process.currentDirectoryURL = URL(fileURLWithPath: dir)
        }

        // Inherit environment with safe PATH
        var env = ProcessInfo.processInfo.environment
        let homeBin = NSHomeDirectory() + "/.local/bin"
        let extraPaths = ["/opt/homebrew/bin", "/usr/local/bin", homeBin]
        let currentPath = env["PATH"] ?? "/usr/bin:/bin"
        env["PATH"] = (extraPaths + [currentPath]).joined(separator: ":")
        process.environment = env

        try process.run()

        let deadline = DispatchTime.now() + effectiveTimeout
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
            throw SystemCommandError.timeout
        }

        let stdoutData = stdoutPipe.fileHandleForReading.readDataToEndOfFile()
        let stderrData = stderrPipe.fileHandleForReading.readDataToEndOfFile()

        let stdout = String(data: stdoutData, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        let stderr = String(data: stderrData, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

        let duration = Date().timeIntervalSince(startTime)

        return CommandResult(
            stdout: stdout,
            stderr: stderr,
            exitCode: process.terminationStatus,
            duration: duration
        )
    }

    // MARK: - Clipboard

    /// Read the current clipboard contents.
    func readClipboard() -> String {
        let result = try? run("pbpaste")
        return result?.stdout ?? ""
    }

    /// Write text to the clipboard.
    func writeClipboard(_ text: String) {
        let escaped = text
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "'", with: "'\\''")
        _ = try? run("printf '%s' '\(escaped)' | pbcopy")
    }

    // MARK: - URL / App Launching

    /// Open a URL in the default browser.
    func openURL(_ urlString: String) throws {
        guard let _ = URL(string: urlString) else {
            throw SystemCommandError.invalidPath(urlString)
        }
        _ = try run("open '\(urlString)'")
    }

    /// Launch a macOS application by name.
    func openApp(_ appName: String) throws {
        let sanitized = appName.replacingOccurrences(of: "'", with: "")
        _ = try run("open -a '\(sanitized)'")
    }

    // MARK: - File Operations (with permission guard)

    /// Read a file's contents. Path must be within allowed roots.
    func readFile(at path: String) throws -> String {
        let resolved = (path as NSString).expandingTildeInPath
        try validatePath(resolved)

        guard FileManager.default.fileExists(atPath: resolved) else {
            throw SystemCommandError.fileNotFound(resolved)
        }

        return try String(contentsOfFile: resolved, encoding: .utf8)
    }

    /// Write content to a file. Path must be within allowed roots.
    func writeFile(at path: String, content: String) throws {
        let resolved = (path as NSString).expandingTildeInPath
        try validatePath(resolved)

        let directory = (resolved as NSString).deletingLastPathComponent
        try FileManager.default.createDirectory(
            atPath: directory,
            withIntermediateDirectories: true
        )

        try content.write(toFile: resolved, atomically: true, encoding: .utf8)
    }

    /// Check if a path is within allowed roots.
    private func validatePath(_ path: String) throws {
        let resolved = (path as NSString).standardizingPath
        let isAllowed = allowedRoots.contains { root in
            resolved.hasPrefix((root as NSString).standardizingPath)
        }
        guard isAllowed else {
            throw SystemCommandError.permissionDenied(
                "Path outside allowed directories: \(path)"
            )
        }
    }

    // MARK: - AppleScript

    /// Execute an AppleScript string and return the result.
    func runAppleScript(_ script: String) throws -> String {
        let escaped = script
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "'", with: "'\\''")
        let result = try run("osascript -e '\(escaped)'")
        if result.succeeded {
            return result.stdout
        }
        throw SystemCommandError.executionFailed(
            code: result.exitCode,
            output: result.stderr
        )
    }

    /// Speak text using the selected TTS engine via VoiceManager when registered,
    /// falling back to macOS say command when no delegate is available.
    func speak(_ text: String, voice: String = "Karen (Premium)", rate: Int = 160) {
        if let delegate = speechDelegate {
            delegate(text)
            return
        }
        let sanitized = text
            .replacingOccurrences(of: "'", with: "")
            .replacingOccurrences(of: "\"", with: "")
        _ = try? run("say -v '\(voice)' '\(sanitized)' -r \(rate)")
    }

    /// Get the frontmost application name.
    func frontmostApp() -> String {
        let script = """
            tell application "System Events" to get name of first application process \
            whose frontmost is true
            """
        return (try? runAppleScript(script)) ?? "Unknown"
    }

    /// Post a macOS notification.
    func notify(title: String, message: String) {
        let safeTitle = title.replacingOccurrences(of: "\"", with: "\\\"")
        let safeMsg = message.replacingOccurrences(of: "\"", with: "\\\"")
        let script = """
            display notification "\(safeMsg)" with title "\(safeTitle)"
            """
        _ = try? runAppleScript(script)
    }

    // MARK: - Convenience Runners

    /// Run pytest in a directory.
    func runTests(in directory: String? = nil) throws -> CommandResult {
        let targetDir = directory ?? NSHomeDirectory() + "/brain"
        return try run("cd '\(targetDir)' && python3 -m pytest --tb=short -q 2>&1 | head -50",
                timeout: 60,
                workingDirectory: targetDir)
    }

    /// Run a Python script.
    func runPython(_ script: String) throws -> CommandResult {
        let escaped = script.replacingOccurrences(of: "'", with: "'\\''")
        return try run("python3 -c '\(escaped)'", timeout: 30)
    }

    /// Get git status for a repo.
    func gitStatus(in directory: String? = nil) throws -> CommandResult {
        let targetDir = directory ?? NSHomeDirectory() + "/brain"
        return try run("cd '\(targetDir)' && git --no-pager status --short",
                workingDirectory: targetDir)
    }
}
