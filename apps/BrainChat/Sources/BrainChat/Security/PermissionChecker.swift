import Foundation

struct PermissionChecker {
    static func canUseYolo(role: SecurityRole) -> Bool {
        switch role {
        case .fullAdmin, .safeAdmin:
            return true
        case .user, .guest:
            return false
        }
    }

    static func requiresSafetyChecksInYolo(role: SecurityRole) -> Bool {
        role == .safeAdmin
    }

    static func canUseProvider(_ provider: LLMProvider, role: SecurityRole) -> Bool {
        switch role {
        case .fullAdmin, .safeAdmin:
            return true
        case .user:
            return true
        case .guest:
            return false
        }
    }

    static func providerRateLimit(for provider: LLMProvider, role: SecurityRole) -> (limit: Int, period: String)? {
        switch role {
        case .fullAdmin, .safeAdmin:
            return nil
        case .user:
            switch provider {
            case .ollama, .copilot:
                return nil
            case .groq:
                return (limit: 100, period: "hour")
            case .claude, .gpt, .grok, .gemini:
                return (limit: 50, period: "hour")
            }
        case .guest:
            return nil
        }
    }

    static func canExecuteCode(role: SecurityRole) -> Bool {
        role == .fullAdmin || role == .safeAdmin
    }

    static func canExecuteShellCommand(_ command: String, role: SecurityRole) -> Bool {
        guard canExecuteCode(role: role) else {
            return false
        }

        if role == .fullAdmin {
            return true
        }

        return isCommandSafeForUser(command)
    }

    static func canAccessPath(_ path: String, role: SecurityRole, operation: FileOperation) -> Bool {
        let resolved = (path as NSString).expandingTildeInPath
        let standardized = (resolved as NSString).standardizingPath

        switch role {
        case .fullAdmin, .safeAdmin:
            return SafetyGuard.shared.evaluatePath(standardized, operation: operation.toActionCategory()) == .allowed
        case .user, .guest:
            return false
        }
    }

    private static func isCommandSafeForUser(_ command: String) -> Bool {
        let lower = command.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        let userBlockedPatterns = [
            "sudo",
            "rm -rf",
            "chmod 777",
            "chown",
            "dd if=",
            "mkfs",
            "format",
            "> /dev/",
            "shutdown",
            "reboot",
            "halt",
        ]

        for pattern in userBlockedPatterns where lower.contains(pattern) {
            return false
        }

        return true
    }
}

enum FileOperation {
    case read
    case write
    case delete
    case execute

    func toActionCategory() -> ActionCategory {
        switch self {
        case .read:
            return .fileCreate
        case .write:
            return .fileEdit
        case .delete:
            return .fileDelete
        case .execute:
            return .shellCommand
        }
    }
}
