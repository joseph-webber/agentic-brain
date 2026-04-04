import Foundation

/// Guards actions by checking permissions before execution
@MainActor
struct SecurityGuard {
    
    // MARK: - YOLO Mode Guards
    
    static func checkYoloPermission() throws {
        guard SecurityManager.shared.canUseYolo() else {
            throw SecurityError.yoloNotAllowed(currentRole: SecurityManager.shared.currentRole)
        }
    }
    
    static func checkCommandSafety(_ command: String) throws {
        let role = SecurityManager.shared.currentRole
        
        // Full Admin bypasses user-level safety (but SafetyGuard still applies)
        if role == .fullAdmin {
            return
        }
        
        // Check if command is safe for this role
        guard SecurityManager.shared.canExecuteShellCommand(command) else {
            throw SecurityError.dangerousCommand(command)
        }
        
        // Additional check using DangerousCommands
        if DangerousCommands.isCommandDangerous(command) {
            throw SecurityError.dangerousCommand(command)
        }
    }
    
    // MARK: - LLM Provider Guards
    
    static func checkProviderPermission(_ provider: LLMProvider) throws {
        let role = SecurityManager.shared.currentRole
        
        guard SecurityManager.shared.canUseProvider(provider) else {
            throw SecurityError.llmProviderNotAllowed(
                provider: provider.rawValue,
                currentRole: role
            )
        }
    }
    
    static func checkRateLimit(for provider: LLMProvider) throws {
        // For now, just check if rate limit exists
        // TODO: Implement actual rate tracking
        if let limit = SecurityManager.shared.providerRateLimit(for: provider) {
            // In a real implementation, track requests and throw if exceeded
            print("ℹ️ Rate limit for \(provider.rawValue): \(limit.limit)/\(limit.period)")
        }
    }
    
    // MARK: - Code Execution Guards
    
    static func checkCodeExecutionPermission() throws {
        guard SecurityManager.shared.canExecuteCode() else {
            throw SecurityError.codeExecutionBlocked(
                currentRole: SecurityManager.shared.currentRole
            )
        }
    }
    
    // MARK: - File System Guards
    
    static func checkPathAccess(_ path: String, operation: FileOperation) throws {
        guard SecurityManager.shared.canAccessPath(path, operation: operation) else {
            throw SecurityError.pathAccessDenied(path: path)
        }
    }
}
