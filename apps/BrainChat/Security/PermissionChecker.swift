import Foundation

/// Detailed permission logic for each security role
struct PermissionChecker {
    
    // MARK: - YOLO Mode Permissions
    
    static func canUseYolo(role: SecurityRole) -> Bool {
        switch role {
        case .fullAdmin, .safeAdmin:
            return true
        case .user, .guest:
            return false
        }
    }
    
    static func requiresSafetyChecksInYolo(role: SecurityRole) -> Bool {
        switch role {
        case .fullAdmin:
            return false  // Full Admin has complete trust, no confirmations
        case .safeAdmin:
            return true   // Safe Admin needs confirmations for dangerous ops
        case .user, .guest:
            return true   // Can't use YOLO anyway
        }
    }
    
    // MARK: - LLM Provider Permissions
    
    static func canUseProvider(_ provider: LLMProvider, role: SecurityRole) -> Bool {
        switch role {
        case .fullAdmin, .safeAdmin:
            return true  // Admins can use any provider
            
        case .user:
            return true  // User can use all providers (rate limited)
            
        case .guest:
            // Guest can only use Ollama (local, free)
            return provider == .ollama
        }
    }
    
    static func providerRateLimit(for provider: LLMProvider, role: SecurityRole) -> (limit: Int, period: String)? {
        switch role {
        case .fullAdmin:
            return nil  // No rate limits for Joseph
            
        case .safeAdmin:
            // Generous limits for developers
            switch provider {
            case .ollama:
                return nil  // Local is unlimited
            case .groq:
                return (limit: 500, period: "hour")
            case .claude, .gpt, .grok, .gemini:
                return (limit: 200, period: "hour")
            case .copilot:
                return nil  // Copilot manages its own limits
            }
            
        case .user:
            // Moderate limits for users
            switch provider {
            case .ollama:
                return nil  // Local is unlimited
            case .groq:
                return (limit: 100, period: "hour")
            case .claude, .gpt, .grok, .gemini:
                return (limit: 50, period: "hour")
            case .copilot:
                return nil  // Copilot manages its own limits
            }
            
        case .guest:
            // Strict limits, but can only use Ollama anyway
            return (limit: 10, period: "hour")
        }
    }
    
    // MARK: - Code Execution Permissions
    
    static func canExecuteCode(role: SecurityRole) -> Bool {
        switch role {
        case .fullAdmin, .safeAdmin:
            return true
        case .user, .guest:
            return false  // No code execution for user/guest
        }
    }
    
    static func canExecuteShellCommand(_ command: String, role: SecurityRole) -> Bool {
        guard canExecuteCode(role: role) else {
            return false
        }
        
        // Full Admin can execute any command (SafetyGuard still applies)
        if role == .fullAdmin {
            return true
        }
        
        // Safe Admin needs additional safety checks
        return isCommandSafeForUser(command)
    }
    
    // MARK: - File System Permissions
    
    static func canAccessPath(_ path: String, role: SecurityRole, operation: FileOperation) -> Bool {
        let resolved = (path as NSString).expandingTildeInPath
        let standardized = (resolved as NSString).standardizingPath
        
        switch role {
        case .fullAdmin:
            // Full Admin can access anywhere within safe directories
            return SafetyGuard.shared.evaluatePath(standardized, operation: operation.toActionCategory()) == .allowed
            
        case .safeAdmin:
            // Safe Admin has same access as Full Admin (SafetyGuard provides boundaries)
            return SafetyGuard.shared.evaluatePath(standardized, operation: operation.toActionCategory()) == .allowed
            
        case .user, .guest:
            // No file system access for user/guest
            return false
        }
    }
    
    // MARK: - Helper Functions
    
    private static func isCommandSafeForUser(_ command: String) -> Bool {
        let lower = command.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        
        // Block dangerous user commands
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
        
        for pattern in userBlockedPatterns {
            if lower.contains(pattern) {
                return false
            }
        }
        
        return true
    }
}

// MARK: - Supporting Types

enum FileOperation {
    case read
    case write
    case delete
    case execute
    
    func toActionCategory() -> ActionCategory {
        switch self {
        case .read:
            return .fileCreate  // SafetyGuard doesn't have read-only, use create as proxy
        case .write:
            return .fileEdit
        case .delete:
            return .fileDelete
        case .execute:
            return .shellCommand
        }
    }
}
