import Foundation

// =============================================================================
// YoloSession - Session state tracking with undo, progress, and error recovery
// Each YOLO session maintains a timeline of actions that can be rewound
// =============================================================================

// MARK: - Action Record (for undo)

struct YoloAction: Identifiable, Codable, Sendable {
    let id: UUID
    let timestamp: Date
    let category: ActionCategory
    let description: String
    let command: String
    let undoCommand: String?
    let backup: ActionBackup?
    var status: ActionStatus

    enum ActionStatus: String, Codable, Sendable {
        case pending   = "pending"
        case running   = "running"
        case succeeded = "succeeded"
        case failed    = "failed"
        case undone    = "undone"
    }

    init(
        category: ActionCategory,
        description: String,
        command: String,
        undoCommand: String? = nil,
        backup: ActionBackup? = nil
    ) {
        self.id = UUID()
        self.timestamp = Date()
        self.category = category
        self.description = description
        self.command = command
        self.undoCommand = undoCommand
        self.backup = backup
        self.status = .pending
    }
}

// MARK: - Backup State (for file undo)

struct ActionBackup: Codable, Sendable {
    let filePath: String
    let originalContent: String?
    let fileExisted: Bool

    /// Create a backup of a file before modifying it.
    static func forFile(at path: String) -> ActionBackup {
        let resolved = (path as NSString).expandingTildeInPath
        let exists = FileManager.default.fileExists(atPath: resolved)
        let content = exists ? (try? String(contentsOfFile: resolved, encoding: .utf8)) : nil
        return ActionBackup(
            filePath: resolved,
            originalContent: content,
            fileExisted: exists
        )
    }
}

// MARK: - Session Statistics

struct SessionStats: Sendable {
    let totalActions: Int
    let succeeded: Int
    let failed: Int
    let undone: Int
    let filesCreated: Int
    let filesEdited: Int
    let filesDeleted: Int
    let shellCommands: Int
    let gitOperations: Int
    let duration: TimeInterval

    var successRate: Double {
        guard totalActions > 0 else { return 0 }
        return Double(succeeded) / Double(totalActions) * 100
    }

    var summary: String {
        let mins = Int(duration / 60)
        let secs = Int(duration.truncatingRemainder(dividingBy: 60))
        return """
        YOLO Session: \(totalActions) actions in \(mins)m \(secs)s
        Succeeded: \(succeeded) | Failed: \(failed) | Undone: \(undone)
        Files: \(filesCreated) created, \(filesEdited) edited, \(filesDeleted) deleted
        Shell: \(shellCommands) | Git: \(gitOperations)
        Success rate: \(String(format: "%.0f", successRate))%
        """
    }

    /// Short spoken summary for Karen.
    var spokenSummary: String {
        if totalActions == 0 {
            return "No actions taken this session."
        }
        var parts: [String] = []
        parts.append("\(totalActions) actions completed")
        if failed > 0 { parts.append("\(failed) failed") }
        if undone > 0 { parts.append("\(undone) undone") }
        parts.append("success rate \(String(format: "%.0f", successRate)) percent")
        return parts.joined(separator: ", ") + "."
    }
}

// MARK: - YoloSession

@MainActor
final class YoloSession: ObservableObject {
    let sessionID: UUID
    let startTime: Date

    @Published private(set) var actions: [YoloAction] = []
    @Published private(set) var isActive: Bool = true
    @Published var lastError: String?
    @Published var progressMessage: String = ""

    /// Maximum actions allowed per session (safety limit)
    let maxActions: Int

    private let system = SystemCommands.shared
    private let guard_ = SafetyGuard.shared

    init(maxActions: Int = 50) {
        self.sessionID = UUID()
        self.startTime = Date()
        self.maxActions = maxActions
    }

    // MARK: - Session Lifecycle

    var canExecute: Bool {
        isActive && actions.count < maxActions
    }

    var actionsRemaining: Int {
        max(0, maxActions - actions.count)
    }

    func end() {
        isActive = false
        progressMessage = "Session ended."
    }

    // MARK: - Record Actions

    /// Add an action to the session timeline. Returns the action ID.
    @discardableResult
    func recordAction(
        category: ActionCategory,
        description: String,
        command: String,
        undoCommand: String? = nil,
        backup: ActionBackup? = nil
    ) -> UUID {
        let action = YoloAction(
            category: category,
            description: description,
            command: command,
            undoCommand: undoCommand,
            backup: backup
        )
        actions.append(action)
        progressMessage = "[\(actions.count)/\(maxActions)] \(description)"
        return action.id
    }

    /// Update an action's status.
    func updateStatus(_ actionID: UUID, status: YoloAction.ActionStatus) {
        guard let index = actions.firstIndex(where: { $0.id == actionID }) else { return }
        actions[index].status = status
    }

    /// Mark an action as succeeded.
    func markSucceeded(_ actionID: UUID) {
        updateStatus(actionID, status: .succeeded)
        lastError = nil
    }

    /// Mark an action as failed with an error message.
    func markFailed(_ actionID: UUID, error: String) {
        updateStatus(actionID, status: .failed)
        lastError = error
    }

    // MARK: - Undo System

    /// Undo the last successful action. Returns a description of what was undone.
    func undoLastAction() -> String? {
        // Find the most recent successful action that hasn't been undone
        guard let index = actions.lastIndex(where: {
            $0.status == .succeeded && $0.undoCommand != nil || $0.backup != nil
        }) else {
            return nil
        }

        let action = actions[index]
        var undoDescription = ""

        // Try file backup restoration first
        if let backup = action.backup {
            do {
                if backup.fileExisted {
                    if let content = backup.originalContent {
                        try content.write(
                            toFile: backup.filePath,
                            atomically: true,
                            encoding: .utf8
                        )
                        undoDescription = "Restored \(shortPath(backup.filePath))"
                    }
                } else {
                    // File didn't exist before - remove it
                    try FileManager.default.removeItem(atPath: backup.filePath)
                    undoDescription = "Removed \(shortPath(backup.filePath))"
                }
                actions[index].status = .undone
            } catch {
                return "Failed to undo: \(error.localizedDescription)"
            }
        }
        // Try undo command
        else if let undoCmd = action.undoCommand {
            do {
                let result = try system.run(undoCmd, timeout: 15)
                if result.succeeded {
                    actions[index].status = .undone
                    undoDescription = "Undid: \(action.description)"
                } else {
                    return "Undo command failed: \(result.output)"
                }
            } catch {
                return "Undo failed: \(error.localizedDescription)"
            }
        }

        // Log the undo
        guard_.logAction(
            category: action.category,
            command: "UNDO: \(action.command)",
            verdict: .allowed,
            outcome: "undone",
            sessionID: sessionID
        )

        return undoDescription
    }

    /// Check if undo is possible.
    var canUndo: Bool {
        actions.contains { action in
            action.status == .succeeded && (action.undoCommand != nil || action.backup != nil)
        }
    }

    /// Get the description of what would be undone.
    var undoPreview: String? {
        guard let action = actions.last(where: {
            $0.status == .succeeded && ($0.undoCommand != nil || $0.backup != nil)
        }) else {
            return nil
        }
        return action.description
    }

    // MARK: - Progress & Reporting

    /// Detailed list of all actions taken this session.
    func actionReport() -> String {
        guard !actions.isEmpty else { return "No actions taken." }

        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm:ss"

        var lines: [String] = ["=== YOLO Session Actions ===", ""]
        for (i, action) in actions.enumerated() {
            let time = formatter.string(from: action.timestamp)
            let icon: String
            switch action.status {
            case .succeeded: icon = "✅"
            case .failed:    icon = "❌"
            case .undone:    icon = "↩️"
            case .running:   icon = "⏳"
            case .pending:   icon = "⏸️"
            }
            lines.append("\(i + 1). \(icon) [\(time)] \(action.description)")
            if action.status == .failed {
                lines.append("     Error: \(lastError ?? "unknown")")
            }
        }

        lines.append("")
        lines.append(statistics.summary)

        return lines.joined(separator: "\n")
    }

    /// Compute session statistics.
    var statistics: SessionStats {
        let succeeded = actions.filter { $0.status == .succeeded }.count
        let failed = actions.filter { $0.status == .failed }.count
        let undone = actions.filter { $0.status == .undone }.count

        return SessionStats(
            totalActions: actions.count,
            succeeded: succeeded,
            failed: failed,
            undone: undone,
            filesCreated: actions.filter { $0.category == .fileCreate && $0.status == .succeeded }.count,
            filesEdited: actions.filter { $0.category == .fileEdit && $0.status == .succeeded }.count,
            filesDeleted: actions.filter { $0.category == .fileDelete && $0.status == .succeeded }.count,
            shellCommands: actions.filter { $0.category == .shellCommand }.count,
            gitOperations: actions.filter { $0.category == .gitOperation }.count,
            duration: Date().timeIntervalSince(startTime)
        )
    }

    // MARK: - Error Recovery

    /// Attempt to recover from the last error by undoing the failed action.
    func recoverFromError() -> String {
        guard let failedIndex = actions.lastIndex(where: { $0.status == .failed }) else {
            return "No failed actions to recover from."
        }

        let action = actions[failedIndex]

        // If there's a backup, restore it
        if let backup = action.backup {
            do {
                if backup.fileExisted, let content = backup.originalContent {
                    try content.write(
                        toFile: backup.filePath,
                        atomically: true,
                        encoding: .utf8
                    )
                } else if !backup.fileExisted {
                    try? FileManager.default.removeItem(atPath: backup.filePath)
                }
                actions[failedIndex].status = .undone
                lastError = nil
                return "Recovered: restored \(shortPath(backup.filePath))"
            } catch {
                return "Recovery failed: \(error.localizedDescription)"
            }
        }

        // If there's an undo command, try it
        if let undoCmd = action.undoCommand {
            do {
                let result = try system.run(undoCmd, timeout: 15)
                if result.succeeded {
                    actions[failedIndex].status = .undone
                    lastError = nil
                    return "Recovered via undo command."
                }
            } catch {
                // Fall through to generic recovery
            }
        }

        // Mark as acknowledged even if we can't fully recover
        lastError = nil
        return "Acknowledged error for: \(action.description). Manual cleanup may be needed."
    }

    // MARK: - Helpers

    /// Shorten a path for display.
    private func shortPath(_ path: String) -> String {
        let home = NSHomeDirectory()
        if path.hasPrefix(home) {
            return "~" + path.dropFirst(home.count)
        }
        return (path as NSString).lastPathComponent
    }
}
