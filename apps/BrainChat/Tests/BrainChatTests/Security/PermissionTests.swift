import XCTest
@testable import BrainChat

final class PermissionTests: XCTestCase {
    
    // MARK: - YOLO Permissions
    
    func testYoloPermissions() {
        XCTAssertTrue(PermissionChecker.canUseYolo(role: .admin))
        XCTAssertTrue(PermissionChecker.canUseYolo(role: .user))
        XCTAssertFalse(PermissionChecker.canUseYolo(role: .guest))
    }
    
    func testYoloSafetyChecks() {
        XCTAssertFalse(PermissionChecker.requiresSafetyChecksInYolo(role: .admin))
        XCTAssertTrue(PermissionChecker.requiresSafetyChecksInYolo(role: .user))
        XCTAssertTrue(PermissionChecker.requiresSafetyChecksInYolo(role: .guest))
    }
    
    // MARK: - LLM Provider Permissions
    
    func testAdminProviderAccess() {
        // Admin can use all providers
        XCTAssertTrue(PermissionChecker.canUseProvider(.ollama, role: .admin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.groq, role: .admin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.claude, role: .admin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gpt, role: .admin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.grok, role: .admin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.gemini, role: .admin))
        XCTAssertTrue(PermissionChecker.canUseProvider(.copilot, role: .admin))
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
        // Guest can only use Ollama
        XCTAssertTrue(PermissionChecker.canUseProvider(.ollama, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.groq, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.claude, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.gpt, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.grok, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.gemini, role: .guest))
        XCTAssertFalse(PermissionChecker.canUseProvider(.copilot, role: .guest))
    }
    
    // MARK: - Rate Limits
    
    func testAdminNoRateLimits() {
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .ollama, role: .admin))
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .groq, role: .admin))
        XCTAssertNil(PermissionChecker.providerRateLimit(for: .claude, role: .admin))
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
        let limit = PermissionChecker.providerRateLimit(for: .ollama, role: .guest)
        XCTAssertNotNil(limit)
        XCTAssertEqual(limit?.limit, 10)
        XCTAssertEqual(limit?.period, "hour")
    }
    
    // MARK: - Code Execution
    
    func testCodeExecutionPermissions() {
        XCTAssertTrue(PermissionChecker.canExecuteCode(role: .admin))
        XCTAssertTrue(PermissionChecker.canExecuteCode(role: .user))
        XCTAssertFalse(PermissionChecker.canExecuteCode(role: .guest))
    }
    
    func testShellCommandPermissions() {
        // Safe commands
        XCTAssertTrue(PermissionChecker.canExecuteShellCommand("ls -la", role: .admin))
        XCTAssertTrue(PermissionChecker.canExecuteShellCommand("cat file.txt", role: .user))
        
        // Dangerous commands - admin can execute (SafetyGuard will still block)
        XCTAssertTrue(PermissionChecker.canExecuteShellCommand("sudo rm -rf /", role: .admin))
        
        // Dangerous commands - user cannot
        XCTAssertFalse(PermissionChecker.canExecuteShellCommand("sudo rm -rf /", role: .user))
        XCTAssertFalse(PermissionChecker.canExecuteShellCommand("rm -rf ~/important", role: .user))
        
        // Guest cannot execute anything
        XCTAssertFalse(PermissionChecker.canExecuteShellCommand("ls", role: .guest))
    }
    
    // MARK: - File System Permissions
    
    func testFileReadPermissions() {
        let safePath = "/Users/joe/brain/test.txt"
        
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .admin, operation: .read))
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .user, operation: .read))
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .guest, operation: .read))
    }
    
    func testFileWritePermissions() {
        let safePath = "/Users/joe/brain/test.txt"
        
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .admin, operation: .write))
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .user, operation: .write))
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .guest, operation: .write))
    }
    
    func testFileDeletePermissions() {
        let safePath = "/Users/joe/brain/test.txt"
        
        // Delete requires confirmation for all roles except guest (who can't delete at all)
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .admin, operation: .delete))
        XCTAssertTrue(PermissionChecker.canAccessPath(safePath, role: .user, operation: .delete))
        XCTAssertFalse(PermissionChecker.canAccessPath(safePath, role: .guest, operation: .delete))
    }
}
