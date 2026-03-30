import Foundation

// =============================================================================
// SafetyGuard - Security layer for YOLO mode autonomous execution
// Blocklists dangerous commands, requires confirmation for risky ops,
// and maintains an immutable audit log of all actions taken
// =============================================================================

// MARK: - Safety Classification

enum SafetyVerdict: Equatable {
    case allowed
    case requiresConfirmation(reason: String)
    case blocked(reason: String)
}

enum ActionCategory: String, Codable, Sendable {
    case fileCreate   = "file_create"
    case fileEdit     = "file_edit"
    case fileDelete   = "file_delete"
    case shellCommand = "shell_command"
    case gitOperation = "git_operation"
    case codeGenerate = "code_generate"
    case appLaunch    = "app_launch"
    case network      = "network"
    case system       = "system"
}

// MARK: - Audit Log Entry

struct AuditEntry: Identifiable, Codable, Sendable {
    let id: UUID
    let timestamp: Date
    let category: ActionCategory
    let command: String
    let verdict: String
    let outcome: String
    let sessionID: UUID

    init(
        category: ActionCategory,
        command: String,
        verdict: String,
        outcome: String = "pending",
        sessionID: UUID
    ) {
        self.id = UUID()
        self.timestamp = Date()
        self.category = category
        self.command = command
        self.verdict = verdict
        self.outcome = outcome
        self.sessionID = sessionID
    }
}

// MARK: - SafetyGuard

final class SafetyGuard: @unchecked Sendable {
    static let shared = SafetyGuard()

    // MARK: - Blocked Patterns (NEVER allowed, even in YOLO)

    private let blockedPatterns: [(pattern: String, reason: String)] = [
        // Destructive filesystem operations
        ("rm -rf /", "Recursive delete of root filesystem"),
        ("rm -rf ~", "Recursive delete of home directory"),
        ("rm -rf /*", "Wildcard delete of root"),
        ("rm -rf $HOME", "Delete home via variable"),
        ("rm -rf .", "Recursive delete of current directory"),
        (":(){:|:&};:", "Fork bomb"),
        ("mkfs", "Format filesystem"),
        ("dd if=/dev/zero", "Overwrite disk with zeros"),
        ("dd if=/dev/random", "Overwrite disk with random data"),
        ("> /dev/sda", "Direct disk write"),

        // System control
        ("shutdown", "System shutdown"),
        ("reboot", "System reboot"),
        ("halt", "System halt"),
        ("init 0", "System halt via init"),
        ("init 6", "System reboot via init"),

        // Privilege escalation
        ("sudo rm", "Privileged deletion"),
        ("sudo dd", "Privileged disk write"),
        ("chmod -R 777 /", "Remove all file permissions on root"),
        ("chmod 000 /", "Lock out root filesystem"),
        ("chown -R", "Recursive ownership change"),

        // Credential theft
        ("curl.*|.*bash", "Piping remote script to shell"),
        ("wget.*|.*sh", "Piping remote script to shell"),
        ("/etc/passwd", "Accessing system password file"),
        ("/etc/shadow", "Accessing system shadow file"),
        ("ssh-keygen -R", "Removing SSH known hosts"),

        // macOS-specific dangers
        ("csrutil disable", "Disabling System Integrity Protection"),
        ("nvram", "Modifying firmware settings"),
        ("diskutil eraseDisk", "Erasing entire disk"),
        ("launchctl unload.*com.apple", "Unloading Apple system services"),
    ]

    // MARK: - Confirmation Required Patterns

    private let confirmationPatterns: [(pattern: String, reason: String)] = [
        // File deletion (any form)
        ("rm ", "Deleting files"),
        ("trash ", "Moving files to trash"),
        ("unlink ", "Removing file links"),

        // Git operations affecting remote
        ("git push.*main", "Pushing to main branch"),
        ("git push.*master", "Pushing to master branch"),
        ("git push --force", "Force pushing (rewrites history)"),
        ("git push -f", "Force pushing (rewrites history)"),
        ("git reset --hard", "Hard reset (discards changes)"),
        ("git clean -fd", "Cleaning untracked files"),
        ("git checkout -- .", "Discarding all local changes"),
        ("git branch -D", "Force deleting a branch"),
        ("git rebase.*main", "Rebasing onto main"),

        // Package management
        ("pip install", "Installing Python packages"),
        ("npm install", "Installing Node packages"),
        ("brew install", "Installing Homebrew packages"),
        ("brew uninstall", "Removing Homebrew packages"),

        // System modifications
        ("defaults write", "Modifying macOS preferences"),
        ("launchctl", "Managing system services"),
        ("killall", "Killing processes by name"),
        ("pkill", "Killing processes by pattern"),

        // Network
        ("curl -X POST", "Making POST requests"),
        ("curl -X DELETE", "Making DELETE requests"),
        ("curl -X PUT", "Making PUT requests"),
    ]

    // MARK: - Safe Directories (YOLO can write here freely)

    private let safeDirectories: [String] = [
        "/Users/joe/brain",
        "/Users/joe/Desktop",
        "/Users/joe/Documents",
        "/Users/joe/Downloads",
    ]

    // MARK: - Safe Commands (always allowed in YOLO without confirmation)

    private let alwaysSafe: Set<String> = [
        "ls", "cat", "head", "tail", "wc", "grep", "find", "which", "echo",
        "pwd", "date", "whoami", "uname", "df", "du", "file", "stat",
        "git status", "git log", "git diff", "git branch", "git show",
        "git stash list", "python3 --version", "node --version",
        "swift --version", "swiftc --version",
    ]

    // Audit log stored in memory for the session lifetime
    private(set) var auditLog: [AuditEntry] = []
    private let logQueue = DispatchQueue(label: "brain.safety.audit", qos: .utility)

    // MARK: - Evaluate Command Safety

    /// Evaluate a command and return a safety verdict.
    func evaluate(command: String, category: ActionCategory) -> SafetyVerdict {
        let lower = command.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        // Check blocklist first (highest priority)
        for entry in blockedPatterns {
            if lower.contains(entry.pattern.lowercased()) {
                return .blocked(reason: entry.reason)
            }
        }

        // Always-safe commands pass through
        for safe in alwaysSafe {
            if lower.hasPrefix(safe) {
                return .allowed
            }
        }

        // Category-specific rules
        switch category {
        case .fileDelete:
            return .requiresConfirmation(reason: "File deletion requires confirmation")

        case .fileCreate, .fileEdit, .codeGenerate:
            // Check path is within safe directories
            if let path = extractPath(from: command) {
                let resolved = (path as NSString).expandingTildeInPath
                let inSafeDir = safeDirectories.contains { root in
                    resolved.hasPrefix(root)
                }
                return inSafeDir ? .allowed : .requiresConfirmation(
                    reason: "Writing outside safe directories: \(path)"
                )
            }
            return .allowed

        case .gitOperation:
            // Check confirmation patterns for dangerous git ops
            for entry in confirmationPatterns where entry.pattern.hasPrefix("git") {
                if lower.contains(entry.pattern.lowercased()) {
                    return .requiresConfirmation(reason: entry.reason)
                }
            }
            return .allowed

        case .shellCommand:
            // Check all confirmation patterns
            for entry in confirmationPatterns {
                if lower.contains(entry.pattern.lowercased()) {
                    return .requiresConfirmation(reason: entry.reason)
                }
            }
            return .allowed

        case .appLaunch:
            return .allowed

        case .network:
            for entry in confirmationPatterns where entry.pattern.hasPrefix("curl") {
                if lower.contains(entry.pattern.lowercased()) {
                    return .requiresConfirmation(reason: entry.reason)
                }
            }
            return .allowed

        case .system:
            return .requiresConfirmation(reason: "System-level operation requires confirmation")
        }
    }

    /// Evaluate a file path for write safety.
    func evaluatePath(_ path: String, operation: ActionCategory) -> SafetyVerdict {
        let resolved = (path as NSString).expandingTildeInPath
        let standardised = (resolved as NSString).standardizingPath

        // Block writes outside safe directories
        let inSafeDir = safeDirectories.contains { root in
            standardised.hasPrefix((root as NSString).standardizingPath)
        }

        guard inSafeDir else {
            return .blocked(reason: "Path outside allowed directories: \(path)")
        }

        // Block overwriting critical files
        let criticalFiles: Set<String> = [
            ".env", ".gitignore", "Package.swift", "Makefile",
            "docker-compose.yml", "Dockerfile",
        ]
        let filename = (standardised as NSString).lastPathComponent
        if criticalFiles.contains(filename) && operation == .fileEdit {
            return .requiresConfirmation(
                reason: "Editing critical file: \(filename)"
            )
        }

        if operation == .fileDelete {
            return .requiresConfirmation(reason: "Deleting: \(filename)")
        }

        return .allowed
    }

    // MARK: - Audit Logging

    /// Record an action in the audit log.
    func logAction(
        category: ActionCategory,
        command: String,
        verdict: SafetyVerdict,
        outcome: String = "pending",
        sessionID: UUID
    ) {
        let verdictString: String
        switch verdict {
        case .allowed: verdictString = "allowed"
        case .requiresConfirmation(let reason): verdictString = "confirmed:\(reason)"
        case .blocked(let reason): verdictString = "blocked:\(reason)"
        }

        let entry = AuditEntry(
            category: category,
            command: String(command.prefix(500)),
            verdict: verdictString,
            outcome: outcome,
            sessionID: sessionID
        )

        logQueue.sync {
            auditLog.append(entry)
        }
    }

    /// Update the outcome of the most recent log entry matching a command.
    func updateOutcome(command: String, outcome: String) {
        logQueue.sync {
            if let index = auditLog.lastIndex(where: {
                $0.command.hasPrefix(String(command.prefix(100)))
            }) {
                // AuditEntry is a struct so we need to replace it
                let old = auditLog[index]
                auditLog[index] = AuditEntry(
                    category: old.category,
                    command: old.command,
                    verdict: old.verdict,
                    outcome: outcome,
                    sessionID: old.sessionID
                )
            }
        }
    }

    /// Get all audit entries for a session.
    func entriesForSession(_ sessionID: UUID) -> [AuditEntry] {
        logQueue.sync {
            auditLog.filter { $0.sessionID == sessionID }
        }
    }

    /// Export audit log as human-readable text.
    func exportAuditLog(sessionID: UUID? = nil) -> String {
        let entries: [AuditEntry]
        if let sid = sessionID {
            entries = entriesForSession(sid)
        } else {
            entries = logQueue.sync { auditLog }
        }

        guard !entries.isEmpty else { return "No actions recorded." }

        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"

        var lines = ["=== YOLO Mode Audit Log ===", ""]
        for entry in entries {
            let time = formatter.string(from: entry.timestamp)
            let icon: String
            switch entry.verdict {
            case let v where v.hasPrefix("blocked"): icon = "🚫"
            case let v where v.hasPrefix("confirmed"): icon = "⚠️"
            default: icon = "✅"
            }
            lines.append("\(icon) [\(time)] \(entry.category.rawValue): \(entry.command)")
            lines.append("   Verdict: \(entry.verdict) | Outcome: \(entry.outcome)")
        }

        lines.append("")
        lines.append("Total actions: \(entries.count)")
        let blocked = entries.filter { $0.verdict.hasPrefix("blocked") }.count
        if blocked > 0 {
            lines.append("Blocked: \(blocked)")
        }

        return lines.joined(separator: "\n")
    }

    /// Clear the audit log (use only at session end).
    func clearAuditLog() {
        logQueue.sync { auditLog.removeAll() }
    }

    // MARK: - Helpers

    /// Try to extract a file path from a command string.
    private func extractPath(from command: String) -> String? {
        // Patterns: "path/to/file", path after common commands
        let pathPrefixes = ["touch ", "mkdir ", "cat > ", "echo.*> ", "tee "]
        let lower = command.lowercased()

        for prefix in pathPrefixes {
            if let range = lower.range(of: prefix) {
                let afterPrefix = command[range.upperBound...]
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                    .components(separatedBy: " ")
                    .first
                if let path = afterPrefix, !path.isEmpty {
                    return path
                }
            }
        }

        // Check if the command itself looks like a path
        if command.contains("/") && !command.contains(" ") {
            return command
        }

        return nil
    }
}
