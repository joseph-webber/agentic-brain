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

    private struct SafetyRule {
        let pattern: String
        let reason: String
        let isRegex: Bool
    }

    // MARK: - Blocked Patterns (NEVER allowed, even in YOLO)

    private let blockedPatterns: [SafetyRule] = [
        // Destructive filesystem operations
        .init(pattern: "rm -rf /", reason: "Recursive delete of root filesystem", isRegex: false),
        .init(pattern: "rm -rf ~", reason: "Recursive delete of home directory", isRegex: false),
        .init(pattern: "rm -rf /*", reason: "Wildcard delete of root", isRegex: false),
        .init(pattern: "rm -rf $HOME", reason: "Delete home via variable", isRegex: false),
        .init(pattern: "rm -rf .", reason: "Recursive delete of current directory", isRegex: false),
        .init(pattern: ":(){:|:&};:", reason: "Fork bomb", isRegex: false),
        .init(pattern: "mkfs", reason: "Format filesystem", isRegex: false),
        .init(pattern: "dd if=/dev/zero", reason: "Overwrite disk with zeros", isRegex: false),
        .init(pattern: "dd if=/dev/random", reason: "Overwrite disk with random data", isRegex: false),
        .init(pattern: "> /dev/sda", reason: "Direct disk write", isRegex: false),

        // System control
        .init(pattern: "shutdown", reason: "System shutdown", isRegex: false),
        .init(pattern: "reboot", reason: "System reboot", isRegex: false),
        .init(pattern: "halt", reason: "System halt", isRegex: false),
        .init(pattern: "init 0", reason: "System halt via init", isRegex: false),
        .init(pattern: "init 6", reason: "System reboot via init", isRegex: false),

        // Privilege escalation
        .init(pattern: "sudo rm", reason: "Privileged deletion", isRegex: false),
        .init(pattern: "sudo dd", reason: "Privileged disk write", isRegex: false),
        .init(pattern: "chmod -R 777 /", reason: "Remove all file permissions on root", isRegex: false),
        .init(pattern: "chmod 000 /", reason: "Lock out root filesystem", isRegex: false),
        .init(pattern: "chown -R", reason: "Recursive ownership change", isRegex: false),

        // Credential theft
        .init(pattern: #"\b(?:curl|wget)\b.*\|\s*(?:bash|sh)\b"#, reason: "Piping remote script to shell", isRegex: true),
        .init(pattern: "/etc/passwd", reason: "Accessing system password file", isRegex: false),
        .init(pattern: "/etc/shadow", reason: "Accessing system shadow file", isRegex: false),
        .init(pattern: "ssh-keygen -R", reason: "Removing SSH known hosts", isRegex: false),

        // macOS-specific dangers
        .init(pattern: "csrutil disable", reason: "Disabling System Integrity Protection", isRegex: false),
        .init(pattern: "nvram", reason: "Modifying firmware settings", isRegex: false),
        .init(pattern: "diskutil eraseDisk", reason: "Erasing entire disk", isRegex: false),
        .init(pattern: #"launchctl unload.*com\.apple"#, reason: "Unloading Apple system services", isRegex: true),
    ]

    // MARK: - Confirmation Required Patterns

    private let confirmationPatterns: [SafetyRule] = [
        // File deletion (any form)
        .init(pattern: "rm ", reason: "Deleting files", isRegex: false),
        .init(pattern: "trash ", reason: "Moving files to trash", isRegex: false),
        .init(pattern: "unlink ", reason: "Removing file links", isRegex: false),

        // Git operations affecting remote
        .init(pattern: #"git push.*main"#, reason: "Pushing to main branch", isRegex: true),
        .init(pattern: #"git push.*master"#, reason: "Pushing to master branch", isRegex: true),
        .init(pattern: "git push --force", reason: "Force pushing (rewrites history)", isRegex: false),
        .init(pattern: "git push -f", reason: "Force pushing (rewrites history)", isRegex: false),
        .init(pattern: "git reset --hard", reason: "Hard reset (discards changes)", isRegex: false),
        .init(pattern: "git clean -fd", reason: "Cleaning untracked files", isRegex: false),
        .init(pattern: "git checkout -- .", reason: "Discarding all local changes", isRegex: false),
        .init(pattern: "git branch -D", reason: "Force deleting a branch", isRegex: false),
        .init(pattern: #"git rebase.*main"#, reason: "Rebasing onto main", isRegex: true),

        // Package management
        .init(pattern: "pip install", reason: "Installing Python packages", isRegex: false),
        .init(pattern: "npm install", reason: "Installing Node packages", isRegex: false),
        .init(pattern: "brew install", reason: "Installing Homebrew packages", isRegex: false),
        .init(pattern: "brew uninstall", reason: "Removing Homebrew packages", isRegex: false),

        // System modifications
        .init(pattern: "defaults write", reason: "Modifying macOS preferences", isRegex: false),
        .init(pattern: "launchctl", reason: "Managing system services", isRegex: false),
        .init(pattern: "killall", reason: "Killing processes by name", isRegex: false),
        .init(pattern: "pkill", reason: "Killing processes by pattern", isRegex: false),

        // Network
        .init(pattern: "curl -X POST", reason: "Making POST requests", isRegex: false),
        .init(pattern: "curl -X DELETE", reason: "Making DELETE requests", isRegex: false),
        .init(pattern: "curl -X PUT", reason: "Making PUT requests", isRegex: false),
    ]

    // MARK: - Safe Directories (YOLO can write here freely)

    private let safeDirectories: [String] = [
        NSHomeDirectory() + "/brain",
        NSHomeDirectory() + "/Desktop",
        NSHomeDirectory() + "/Documents",
        NSHomeDirectory() + "/Downloads",
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

        for entry in blockedPatterns where matches(lower, rule: entry) {
                return .blocked(reason: entry.reason)
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
            for entry in confirmationPatterns where entry.pattern.hasPrefix("git") {
                if matches(lower, rule: entry) {
                    return .requiresConfirmation(reason: entry.reason)
                }
            }
            return .allowed

        case .shellCommand:
            for entry in confirmationPatterns {
                if matches(lower, rule: entry) {
                    return .requiresConfirmation(reason: entry.reason)
                }
            }
            return .allowed

        case .appLaunch:
            return .allowed

        case .network:
            for entry in confirmationPatterns where entry.pattern.hasPrefix("curl") {
                if matches(lower, rule: entry) {
                    return .requiresConfirmation(reason: entry.reason)
                }
            }
            return .allowed

        case .system:
            return .requiresConfirmation(reason: "System-level operation requires confirmation")
        }
    }

    /// Evaluate a file path for write safety.
    /// SECURITY FIX: Now resolves symlinks to prevent symlink attacks
    func evaluatePath(_ path: String, operation: ActionCategory) -> SafetyVerdict {
        let resolved = (path as NSString).expandingTildeInPath
        let standardised = (resolved as NSString).standardizingPath
        
        // SECURITY FIX: Resolve symlinks to prevent symlink attacks
        let realPath = (standardised as NSString).resolvingSymlinksInPath

        // Block writes outside safe directories
        let inSafeDir = safeDirectories.contains { root in
            // SECURITY FIX: Standardize both root and path for accurate comparison
            let standardizedRoot = (root as NSString).standardizingPath
            return realPath.hasPrefix(standardizedRoot)
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

    private func matches(_ command: String, rule: SafetyRule) -> Bool {
        let regexPattern: String
        if rule.isRegex {
            regexPattern = rule.pattern.lowercased()
        } else {
            let escaped = NSRegularExpression.escapedPattern(for: rule.pattern.lowercased())
            let useWordBoundaries = rule.pattern.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
            regexPattern = useWordBoundaries ? "\\b\(escaped)\\b" : escaped
        }

        return command.range(of: regexPattern, options: .regularExpression) != nil
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
