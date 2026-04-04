import XCTest
@testable import BrainChatLib

final class PermissionTests: XCTestCase {
    
    // MARK: - YOLO Permissions
    
    func testYoloPermissions() {
        XCTAssertTrue(PermissionChecker.canUseYolo(role: .fullAdmin), "Full Admin should have YOLO access")
        XCTAssertTrue(PermissionChecker.canUseYolo(role: .safeAdmin), "Safe Admin should have YOLO access")
        XCTAssertFalse(PermissionChecker.canUseYolo(role: .user), "User should not have YOLO access")
        XCTAssertFalse(PermissionChecker.canUseYolo(role: .guest), "Guest should not have YOLO access")
    }
    
    func testYoloSafetyChecks() {
        XCTAssertFalse(PermissionChecker.requiresSafetyChecksInYolo(role: .fullAdmin), "Full Admin should not require safety checks")
        XCTAssertTrue(PermissionChecker.requiresSafetyChecksInYolo(role: .safeAdmin), "Safe Admin should require safety checks")
        XCTAssertFalse(PermissionChecker.requiresSafetyChecksInYolo(role: .user), "User doesn't have YOLO access")
        XCTAssertFalse(PermissionChecker.requiresSafetyChecksInYolo(role: .guest), "Guest doesn't have YOLO access")
    }
    
    // MARK: - LLM Provider Permissions
    
    func testFullAdminProviderAccess() {
        // Full Admin can use all providers
        XCTAssertTrue(PermissionChecker.canUseProvider(.ollama, role: .fullAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.groq, role: .fullAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.claude, role: .fullAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gpt, role: .fullAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.grok, role: .fullAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gemini, role: .fullAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.copilot, role: .fullAdmin))
    }
    
    func testSafeAdminProviderAccess() {
        // Safe Admin can use all providers
        XCTAssertTrue(PermissionChecker.canUseProvider(.ollama, role: .safeAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.groq, role: .safeAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.claude, role: .safeAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gpt, role: .safeAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.grok, role: .safeAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gemini, role: .safeAdmin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.copilot, role: .safeAdmin))
    }
    
    func testUserProviderAccess() {
        // User can use all providers
        XCTAssertTrue(PermissionChecker.canUseProvider(.ollama, role: .user))
        XCTAssertTrue(PermissionChecker.canUseProvider(.groq, role: .user))
        XCTAssertTrue(PermissionChecker.canUseProvider(.claude, role: .user))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gpt, role: .user))
        XCTAssertTrue(PermissionChecker.canUseProvider(.grok, role: .user))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gemini, role: .user))
        XCTAssertTrue(PermissionChecker.canUseProvider(.copilot, role: .user))
    }
    
    func testGuestProviderAccess() {
        // Guest cannot use any providers (help-only mode)
        XCTAssertFalse(PermissionChecker.canUseProvider(.ollama, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.groq, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.claude, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.gpt, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.grok, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.gemini, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.copilot, role: .guest))
    }
    
    // MARK: - Rate Limits
    
    func testFullAdminNoRateLimits() {
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .ollama, role: .fullAdmin))
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .groq, role: .fullAdmin))
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .claude, role: .fullAdmin))
    }
    
    func testSafeAdminNoRateLimits() {
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .ollama, role: .safeAdmin))
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .groq, role: .safeAdmin))
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .claude, role: .safeAdmin))
    }
    
    func testUserRateLimits() {
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .ollama, role: .user))
        
        let groqLimit = PermissionChecker.providerRateLimit(for: .groq, role: .user)
        XCTAssertNotNil(groqLimit)
        XCTAssertEqual(groqLimit?.limit, 100)
        XCTAssertEqual(groqLimit?.period, "hour")
        
        let claudeLimit = PermissionChecker.providerRateLimit(for: .claude, role: .user)
        XCTAssertNotNil(claudeLimit)
        XCTAssertEqual(claudeLimit?.limit, 50)
    }
    
    func testGuestRateLimits() {
        // Guest has no API access, so no rate limits
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .ollama, role: .guest))
    }
    
    // MARK: - Code Execution
    
    func testCodeExecutionPermissions() {
        XCTAssertTrue(PermissionChecker.canExecuteCode(role: .fullAdmin), "Full Admin should execute code")
        XCTAssertTrue(PermissionChecker.canExecuteCode(role: .safeAdmin), "Safe Admin should execute code")
        XCTAssertFalse(PermissionChecker.canExecuteCode(role: .user), "User should not execute code")
        XCTAssertFalse(PermissionChecker.canExecuteCode(role: .guest), "Guest should not execute code")
    }
    
    func testShellCommandPermissions() {
        // Safe commands
        XCTAssertTrue(PermissionChecker.canExecuteShellCommand("ls -la", role: .fullAdmin))
        XCTAssertTrue(PermissionChecker.canExecuteShellCommand("cat file.txt", role: .safeAdmin))
        
        // Dangerous commands - full admin can execute (SafetyGuard will still block)
        XCTAssertTrue(PermissionChecker.canExecuteShellCommand("sudo rm -rf /", role: .fullAdmin))
        
        // Dangerous commands - safe admin cannot execute directly
        XCTAssertFalse(PermissionChecker.canExecuteShellCommand("sudo rm -rf /", role: .safeAdmin))
        XCTAssertFalse(PermissionChecker.canExecuteShellCommand("rm -rf ~/important", role: .safeAdmin))
        
        // User and guest cannot execute anything
        XCTAssertFalse(PermissionChecker.canExecuteShellCommand("ls", role: .user))
        XCTAssertFalse(PermissionChecker.canExecuteShellCommand("ls", role: .guest))
    }
    
    // MARK: - File System Permissions
    
    func testFileReadPermissions() {
        let safePath = "/Users/joe/brain/test.txt"
        
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .fullAdmin, operation: .read))
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .safeAdmin, operation: .read))
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .user, operation: .read), "User has no filesystem access")
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .guest, operation: .read), "Guest has no filesystem access")
    }
    
    func testFileWritePermissions() {
        let safePath = "/Users/joe/brain/test.txt"
        
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .fullAdmin, operation: .write))
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .safeAdmin, operation: .write))
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .user, operation: .write))
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .guest, operation: .write))
    }
    
    func testFileDeletePermissions() {
        let safePath = "/Users/joe/brain/test.txt"
        
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .fullAdmin, operation: .delete))
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .safeAdmin, operation: .delete))
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .user, operation: .delete))
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .guest, operation: .delete))
    }
}
