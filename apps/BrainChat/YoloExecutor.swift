import Foundation

// =============================================================================
// YoloExecutor - Autonomous action executor for YOLO mode
// Handles file operations, shell commands, git operations, and code generation
// All actions pass through SafetyGuard and are tracked in YoloSession
// =============================================================================

// MARK: - Execution Result

struct YoloResult: Sendable {
    let success: Bool
    let output: String
    let actionID: UUID
    let category: ActionCategory

    var spokenSummary: String {
        if success {
            return String(output.prefix(200))
        }
        return "Failed: \(String(output.prefix(150)))"
    }
}

// MARK: - YOLO Command (parsed from AI response)

struct YoloCommand: Sendable {
    let category: ActionCategory
    let description: String
    let command: String
    let filePath: String?
    let fileContent: String?
    let undoHint: String?

    /// Parse action blocks from an AI response.
    /// Expected format:
    /// ```yolo
    /// ACTION: create_file
    /// PATH: ~/brain/utils.py
    /// CONTENT:
    /// def hello():
    ///     print("hello")
    /// ```
    static func parse(from text: String) -> [YoloCommand] {
        var commands: [YoloCommand] = []

        // Split on yolo code blocks
        let blocks = text.components(separatedBy: "```yolo")
        for block in blocks.dropFirst() {
            guard let endIndex = block.range(of: "```")?.lowerBound else { continue }
            let content = String(block[block.startIndex..<endIndex])
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if let cmd = parseBlock(content) {
                commands.append(cmd)
            }
        }

        // Also check for inline shell commands: `$ command`
        let lines = text.components(separatedBy: "\n")
        for line in lines {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("$ ") {
                let shellCmd = String(trimmed.dropFirst(2))
                commands.append(YoloCommand(
                    category: .shellCommand,
                    description: "Run: \(String(shellCmd.prefix(60)))",
                    command: shellCmd,
                    filePath: nil,
                    fileContent: nil,
                    undoHint: nil
                ))
            }
        }

        return commands
    }

    private static func parseBlock(_ block: String) -> YoloCommand? {
        var action = ""
        var path: String?
        var content: String?
        var description = ""
        var command = ""

        let lines = block.components(separatedBy: "\n")
        var inContent = false
        var contentLines: [String] = []

        for line in lines {
            if inContent {
                contentLines.append(line)
                continue
            }

            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.uppercased().hasPrefix("ACTION:") {
                action = trimmed.replacingOccurrences(
                    of: "ACTION:", with: "", options: .caseInsensitive
                ).trimmingCharacters(in: .whitespaces).lowercased()
            } else if trimmed.uppercased().hasPrefix("PATH:") {
                path = trimmed.replacingOccurrences(
                    of: "PATH:", with: "", options: .caseInsensitive
                ).trimmingCharacters(in: .whitespaces)
            } else if trimmed.uppercased().hasPrefix("COMMAND:") || trimmed.uppercased().hasPrefix("CMD:") {
                command = trimmed
                    .replacingOccurrences(of: "COMMAND:", with: "", options: .caseInsensitive)
                    .replacingOccurrences(of: "CMD:", with: "", options: .caseInsensitive)
                    .trimmingCharacters(in: .whitespaces)
            } else if trimmed.uppercased().hasPrefix("DESC:") || trimmed.uppercased().hasPrefix("DESCRIPTION:") {
                description = trimmed
                    .replacingOccurrences(of: "DESCRIPTION:", with: "", options: .caseInsensitive)
                    .replacingOccurrences(of: "DESC:", with: "", options: .caseInsensitive)
                    .trimmingCharacters(in: .whitespaces)
            } else if trimmed.uppercased().hasPrefix("CONTENT:") {
                inContent = true
                let inline = trimmed.replacingOccurrences(
                    of: "CONTENT:", with: "", options: .caseInsensitive
                ).trimmingCharacters(in: .whitespaces)
                if !inline.isEmpty { contentLines.append(inline) }
            }
        }

        if !contentLines.isEmpty {
            content = contentLines.joined(separator: "\n")
        }

        guard !action.isEmpty else { return nil }

        let category: ActionCategory
        switch action {
        case "create_file", "create": category = .fileCreate
        case "edit_file", "edit", "modify": category = .fileEdit
        case "delete_file", "delete", "remove": category = .fileDelete
        case "shell", "run", "exec", "execute": category = .shellCommand
        case "git": category = .gitOperation
        case "generate", "code", "codegen": category = .codeGenerate
        default: category = .shellCommand
        }

        if description.isEmpty {
            description = "\(action): \(path ?? command)"
        }
        if command.isEmpty && path != nil {
            command = action
        }

        return YoloCommand(
            category: category,
            description: description,
            command: command,
            filePath: path,
            fileContent: content,
            undoHint: nil
        )
    }
}

// MARK: - YoloExecutor

@MainActor
final class YoloExecutor: ObservableObject {
    @Published var isExecuting = false
    @Published var currentAction: String = ""
    @Published var lastResult: YoloResult?

    private let system = SystemCommands.shared
    private let safety = SafetyGuard.shared

    // MARK: - Execute a Single Command

    /// Execute a YOLO command within a session. Returns the result.
    func execute(
        command: YoloCommand,
        session: YoloSession,
        confirmationHandler: ((String) async -> Bool)? = nil
    ) async -> YoloResult {
        // Security check: Can this role use YOLO?
        do {
            try SecurityGuard.checkYoloPermission()
        } catch {
            let msg = error.localizedDescription
            speak("YOLO permission denied. \(msg)")
            return YoloResult(success: false, output: msg, actionID: UUID(), category: command.category)
        }
        
        // Security check: Is this command safe for the current role?
        if SecurityManager.shared.requiresSafetyChecksInYolo() {
            do {
                try SecurityGuard.checkCommandSafety(command.command)
            } catch {
                let msg = error.localizedDescription
                speak("Command blocked by security policy. \(msg)")
                safety.logAction(
                    category: command.category,
                    command: command.command,
                    verdict: .blocked(reason: msg),
                    outcome: "security_blocked",
                    sessionID: session.sessionID
                )
                return YoloResult(success: false, output: msg, actionID: UUID(), category: command.category)
            }
        }
        
        // Safe Admin mode: Require confirmation for dangerous operations
        if SecurityManager.shared.requiresYoloConfirmation() && isDangerousOperation(command) {
            speak("Safe Admin mode: This operation requires confirmation.")
            if let handler = confirmationHandler {
                let confirmed = await handler("Safe Admin: \(command.description)")
                if !confirmed {
                    safety.logAction(
                        category: command.category,
                        command: command.command,
                        verdict: .requiresConfirmation(reason: "Safe Admin mode"),
                        outcome: "denied_by_safe_admin",
                        sessionID: session.sessionID
                    )
                    return YoloResult(
                        success: false,
                        output: "Operation cancelled by Safe Admin confirmation",
                        actionID: UUID(),
                        category: command.category
                    )
                }
            } else {
                safety.logAction(
                    category: command.category,
                    command: command.command,
                    verdict: .requiresConfirmation(reason: "Safe Admin mode"),
                    outcome: "skipped_no_handler",
                    sessionID: session.sessionID
                )
                return YoloResult(
                    success: false,
                    output: "Skipped (Safe Admin requires confirmation)",
                    actionID: UUID(),
                    category: command.category
                )
            }
        }
        
        guard session.canExecute else {
            let msg = "Session limit reached (\(session.maxActions) actions). Deactivate and restart YOLO."
            speak("Session limit reached. Cannot execute more actions.")
            return YoloResult(success: false, output: msg, actionID: UUID(), category: command.category)
        }

        isExecuting = true
        currentAction = command.description
        defer { isExecuting = false; currentAction = "" }

        // Safety check
        let verdict = safety.evaluate(command: command.command, category: command.category)

        switch verdict {
        case .blocked(let reason):
            let msg = "Blocked: \(reason)"
            speak("Action blocked. \(reason)")
            safety.logAction(
                category: command.category,
                command: command.command,
                verdict: verdict,
                outcome: "blocked",
                sessionID: session.sessionID
            )
            return YoloResult(success: false, output: msg, actionID: UUID(), category: command.category)

        case .requiresConfirmation(let reason):
            speak("This action needs confirmation. \(reason)")
            if let handler = confirmationHandler {
                let confirmed = await handler(reason)
                if !confirmed {
                    safety.logAction(
                        category: command.category,
                        command: command.command,
                        verdict: verdict,
                        outcome: "denied_by_user",
                        sessionID: session.sessionID
                    )
                    return YoloResult(
                        success: false,
                        output: "User denied: \(reason)",
                        actionID: UUID(),
                        category: command.category
                    )
                }
            } else {
                // No confirmation handler in pure YOLO - skip risky ops
                safety.logAction(
                    category: command.category,
                    command: command.command,
                    verdict: verdict,
                    outcome: "skipped_no_handler",
                    sessionID: session.sessionID
                )
                return YoloResult(
                    success: false,
                    output: "Skipped (requires confirmation): \(reason)",
                    actionID: UUID(),
                    category: command.category
                )
            }

        case .allowed:
            break
        }

        // Execute based on category
        let result: YoloResult
        switch command.category {
        case .fileCreate:
            result = await executeFileCreate(command: command, session: session)
        case .fileEdit:
            result = await executeFileEdit(command: command, session: session)
        case .fileDelete:
            result = await executeFileDelete(command: command, session: session)
        case .shellCommand:
            result = await executeShell(command: command, session: session)
        case .gitOperation:
            result = await executeGit(command: command, session: session)
        case .codeGenerate:
            result = await executeCodeGen(command: command, session: session)
        case .appLaunch:
            result = await executeAppLaunch(command: command, session: session)
        case .network, .system:
            result = await executeShell(command: command, session: session)
        }

        lastResult = result

        // Log to safety audit
        safety.logAction(
            category: command.category,
            command: command.command,
            verdict: .allowed,
            outcome: result.success ? "success" : "failed",
            sessionID: session.sessionID
        )

        return result
    }

    // MARK: - Execute Multiple Commands

    /// Execute a batch of YOLO commands sequentially.
    func executeBatch(
        commands: [YoloCommand],
        session: YoloSession,
        confirmationHandler: ((String) async -> Bool)? = nil,
        onProgress: ((Int, Int, YoloResult) -> Void)? = nil
    ) async -> [YoloResult] {
        var results: [YoloResult] = []

        for (index, command) in commands.enumerated() {
            speak(command.description)

            let result = await execute(
                command: command,
                session: session,
                confirmationHandler: confirmationHandler
            )
            results.append(result)

            onProgress?(index + 1, commands.count, result)

            // Stop on failure unless it's a non-critical category
            if !result.success && command.category != .shellCommand {
                speak("Stopping batch due to failure.")
                break
            }
        }

        return results
    }

    // MARK: - File Create

    private func executeFileCreate(command: YoloCommand, session: YoloSession) async -> YoloResult {
        guard let path = command.filePath else {
            return fail("No file path specified", command: command)
        }
        guard let content = command.fileContent else {
            return fail("No file content provided", command: command)
        }

        let resolved = (path as NSString).expandingTildeInPath

        // Check path safety
        let pathVerdict = safety.evaluatePath(resolved, operation: .fileCreate)
        if case .blocked(let reason) = pathVerdict {
            return fail("Path blocked: \(reason)", command: command)
        }

        // Back up if file exists
        let backup = ActionBackup.forFile(at: resolved)

        let actionID = session.recordAction(
            category: .fileCreate,
            description: "Create \(shortPath(resolved))",
            command: "create:\(resolved)",
            undoCommand: nil,
            backup: backup
        )
        session.updateStatus(actionID, status: .running)

        do {
            // Create parent directories
            let dir = (resolved as NSString).deletingLastPathComponent
            try FileManager.default.createDirectory(
                atPath: dir,
                withIntermediateDirectories: true
            )

            try content.write(toFile: resolved, atomically: true, encoding: .utf8)
            session.markSucceeded(actionID)

            let msg = "Created \(shortPath(resolved)) (\(content.count) chars)"
            speak(msg)
            return YoloResult(success: true, output: msg, actionID: actionID, category: .fileCreate)
        } catch {
            let msg = "Failed to create file: \(error.localizedDescription)"
            session.markFailed(actionID, error: msg)
            return YoloResult(success: false, output: msg, actionID: actionID, category: .fileCreate)
        }
    }

    // MARK: - File Edit

    private func executeFileEdit(command: YoloCommand, session: YoloSession) async -> YoloResult {
        guard let path = command.filePath else {
            return fail("No file path specified", command: command)
        }

        let resolved = (path as NSString).expandingTildeInPath

        guard FileManager.default.fileExists(atPath: resolved) else {
            return fail("File not found: \(shortPath(resolved))", command: command)
        }

        // Back up original content
        let backup = ActionBackup.forFile(at: resolved)

        let actionID = session.recordAction(
            category: .fileEdit,
            description: "Edit \(shortPath(resolved))",
            command: "edit:\(resolved)",
            undoCommand: nil,
            backup: backup
        )
        session.updateStatus(actionID, status: .running)

        if let newContent = command.fileContent {
            do {
                try newContent.write(toFile: resolved, atomically: true, encoding: .utf8)
                session.markSucceeded(actionID)

                let msg = "Edited \(shortPath(resolved))"
                speak(msg)
                return YoloResult(success: true, output: msg, actionID: actionID, category: .fileEdit)
            } catch {
                let msg = "Edit failed: \(error.localizedDescription)"
                session.markFailed(actionID, error: msg)
                return YoloResult(success: false, output: msg, actionID: actionID, category: .fileEdit)
            }
        }

        let msg = "No content provided for edit"
        session.markFailed(actionID, error: msg)
        return YoloResult(success: false, output: msg, actionID: actionID, category: .fileEdit)
    }

    // MARK: - File Delete

    private func executeFileDelete(command: YoloCommand, session: YoloSession) async -> YoloResult {
        guard let path = command.filePath else {
            return fail("No file path specified", command: command)
        }

        let resolved = (path as NSString).expandingTildeInPath

        guard FileManager.default.fileExists(atPath: resolved) else {
            return fail("File not found: \(shortPath(resolved))", command: command)
        }

        // Always backup before delete
        let backup = ActionBackup.forFile(at: resolved)

        let actionID = session.recordAction(
            category: .fileDelete,
            description: "Delete \(shortPath(resolved))",
            command: "delete:\(resolved)",
            undoCommand: nil,
            backup: backup
        )
        session.updateStatus(actionID, status: .running)

        do {
            // Move to trash instead of permanent delete (safer)
            let trashResult = try system.run(
                "osascript -e 'tell application \"Finder\" to delete POSIX file \"\(resolved)\"'",
                timeout: 10
            )
            if trashResult.succeeded {
                session.markSucceeded(actionID)
                let msg = "Moved \(shortPath(resolved)) to Trash"
                speak(msg)
                return YoloResult(success: true, output: msg, actionID: actionID, category: .fileDelete)
            } else {
                throw SystemCommandError.executionFailed(
                    code: trashResult.exitCode,
                    output: trashResult.output
                )
            }
        } catch {
            let msg = "Delete failed: \(error.localizedDescription)"
            session.markFailed(actionID, error: msg)
            return YoloResult(success: false, output: msg, actionID: actionID, category: .fileDelete)
        }
    }

    // MARK: - Shell Command

    private func executeShell(command: YoloCommand, session: YoloSession) async -> YoloResult {
        let actionID = session.recordAction(
            category: .shellCommand,
            description: command.description,
            command: command.command,
            undoCommand: nil,
            backup: nil
        )
        session.updateStatus(actionID, status: .running)

        do {
            let result = try system.run(
                command.command,
                timeout: 30,
                workingDirectory: "/Users/joe/brain"
            )

            if result.succeeded {
                session.markSucceeded(actionID)
                let output = result.output.isEmpty ? "Command completed." : result.output
                return YoloResult(
                    success: true,
                    output: String(output.prefix(2000)),
                    actionID: actionID,
                    category: .shellCommand
                )
            } else {
                let msg = "Exit code \(result.exitCode): \(result.output)"
                session.markFailed(actionID, error: msg)
                return YoloResult(
                    success: false,
                    output: String(msg.prefix(2000)),
                    actionID: actionID,
                    category: .shellCommand
                )
            }
        } catch {
            let msg = "Shell error: \(error.localizedDescription)"
            session.markFailed(actionID, error: msg)
            return YoloResult(success: false, output: msg, actionID: actionID, category: .shellCommand)
        }
    }

    // MARK: - Git Operations

    private func executeGit(command: YoloCommand, session: YoloSession) async -> YoloResult {
        let gitCmd = command.command.hasPrefix("git ")
            ? command.command
            : "git \(command.command)"

        let actionID = session.recordAction(
            category: .gitOperation,
            description: "Git: \(command.description)",
            command: gitCmd,
            undoCommand: inferGitUndo(gitCmd),
            backup: nil
        )
        session.updateStatus(actionID, status: .running)

        do {
            let result = try system.run(
                gitCmd,
                timeout: 30,
                workingDirectory: "/Users/joe/brain"
            )

            if result.succeeded {
                session.markSucceeded(actionID)
                let output = result.output.isEmpty ? "Git command completed." : result.output
                speak("Git operation done.")
                return YoloResult(
                    success: true,
                    output: String(output.prefix(2000)),
                    actionID: actionID,
                    category: .gitOperation
                )
            } else {
                let msg = "Git error: \(result.output)"
                session.markFailed(actionID, error: msg)
                return YoloResult(
                    success: false,
                    output: String(msg.prefix(2000)),
                    actionID: actionID,
                    category: .gitOperation
                )
            }
        } catch {
            let msg = "Git failed: \(error.localizedDescription)"
            session.markFailed(actionID, error: msg)
            return YoloResult(success: false, output: msg, actionID: actionID, category: .gitOperation)
        }
    }

    // MARK: - Code Generation

    private func executeCodeGen(command: YoloCommand, session: YoloSession) async -> YoloResult {
        guard let path = command.filePath, let content = command.fileContent else {
            return fail("Code generation requires PATH and CONTENT", command: command)
        }

        // Code gen is essentially file create with announcement
        speak("Generating code for \(shortPath(path))")

        let createCmd = YoloCommand(
            category: .fileCreate,
            description: "Generate \(shortPath(path))",
            command: "codegen:\(path)",
            filePath: path,
            fileContent: content,
            undoHint: nil
        )

        return await executeFileCreate(command: createCmd, session: session)
    }

    // MARK: - App Launch

    private func executeAppLaunch(command: YoloCommand, session: YoloSession) async -> YoloResult {
        let actionID = session.recordAction(
            category: .appLaunch,
            description: command.description,
            command: command.command,
            undoCommand: nil,
            backup: nil
        )
        session.updateStatus(actionID, status: .running)

        do {
            try system.openApp(command.command)
            session.markSucceeded(actionID)
            return YoloResult(
                success: true,
                output: "Opened \(command.command)",
                actionID: actionID,
                category: .appLaunch
            )
        } catch {
            let msg = "Failed to open app: \(error.localizedDescription)"
            session.markFailed(actionID, error: msg)
            return YoloResult(success: false, output: msg, actionID: actionID, category: .appLaunch)
        }
    }

    // MARK: - Helpers

    private func fail(_ message: String, command: YoloCommand) -> YoloResult {
        YoloResult(success: false, output: message, actionID: UUID(), category: command.category)
    }

    private func speak(_ text: String) {
        system.speak(text, voice: "Karen (Premium)", rate: 160)
    }

    private func shortPath(_ path: String) -> String {
        let home = NSHomeDirectory()
        if path.hasPrefix(home) {
            return "~" + path.dropFirst(home.count)
        }
        return (path as NSString).lastPathComponent
    }

    /// Infer an undo command for common git operations.
    private func inferGitUndo(_ command: String) -> String? {
        let lower = command.lowercased()
        if lower.contains("git add") {
            let files = command.replacingOccurrences(of: "git add ", with: "")
            return "git reset HEAD \(files)"
        }
        if lower.contains("git commit") {
            return "git reset --soft HEAD~1"
        }
        if lower.contains("git stash") && !lower.contains("pop") {
            return "git stash pop"
        }
        if lower.contains("git checkout -b") {
            let branch = command.replacingOccurrences(of: "git checkout -b ", with: "")
                .trimmingCharacters(in: .whitespaces)
            return "git branch -d \(branch)"
        }
        return nil
    }

    /// Check if a command is dangerous and requires confirmation in Safe Admin mode
    private func isDangerousOperation(_ command: YoloCommand) -> Bool {
        switch command.category {
        case .fileDelete, .gitOperation:
            return true
        case .shellCommand:
            let lower = command.command.lowercased()
            return lower.contains("rm ") || 
                   lower.contains("delete") ||
                   lower.contains("sudo") ||
                   lower.contains("chmod") ||
                   lower.contains("chown") ||
                   lower.contains("git push") ||
                   lower.contains("git reset --hard")
        case .fileEdit:
            // Editing system files or configuration is dangerous
            if let path = command.filePath {
                let lower = path.lowercased()
                return lower.contains("/etc/") ||
                       lower.contains("/system/") ||
                       lower.contains("/library/") ||
                       lower.contains(".plist") ||
                       lower.contains("package.json") ||
                       lower.contains("requirements.txt")
            }
            return false
        case .network, .system:
            return true
        case .fileCreate, .codeGenerate, .appLaunch:
            return false
        }
    }
}
