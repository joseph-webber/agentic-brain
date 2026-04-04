import XCTest
@testable import BrainChatLib

@MainActor
final class YoloSecurityTests: XCTestCase {
    
    var yoloMode: YoloMode!
    var securityManager: SecurityManager!
    
    override func setUp() async throws {
        try await super.setUp()
        yoloMode = YoloMode.shared
        securityManager = SecurityManager.shared
        
        // Reset to admin for tests
        securityManager.setModeSwitching(enabled: true)
        securityManager.resetToDefault()
        
        // Deactivate YOLO if active
        if yoloMode.isActive {
            yoloMode.deactivate()
        }
    }
    
    // MARK: - YOLO Activation Tests
    
    func testAdminCanActivateYolo() async {
        securityManager.switchRole(to: .admin)
        
        yoloMode.activate()
        
        XCTAssertTrue(yoloMode.isActive)
        XCTAssertNotNil(yoloMode.session)
    }
    
    func testUserCanActivateYolo() async {
        securityManager.switchRole(to: .user)
        
        yoloMode.activate()
        
        XCTAssertTrue(yoloMode.isActive)
        XCTAssertNotNil(yoloMode.session)
    }
    
    func testGuestCannotActivateYolo() async {
        securityManager.switchRole(to: .guest)
        
        yoloMode.activate()
        
        XCTAssertFalse(yoloMode.isActive)
        XCTAssertNil(yoloMode.session)
    }
    
    // MARK: - Command Safety Tests
    
    func testAdminBypassesUserSafetyChecks() {
        securityManager.switchRole(to: .admin)
        
        // Admin doesn't require safety checks in YOLO
        XCTAssertFalse(securityManager.requiresSafetyChecksInYolo())
    }
    
    func testUserRequiresSafetyChecks() {
        securityManager.switchRole(to: .user)
        
        // User requires safety checks in YOLO
        XCTAssertTrue(securityManager.requiresSafetyChecksInYolo())
    }
    
    func testDangerousCommandDetection() {
        let dangerousCommands = [
            "rm -rf /",
            "sudo rm -rf /var",
            "chmod 777 /etc",
            "dd if=/dev/zero of=/dev/sda",
            ":(){ :|:& };:",  // fork bomb
        ]
        
        for cmd in dangerousCommands {
            XCTAssertTrue(
                DangerousCommands.isCommandDangerous(cmd),
                "Command should be detected as dangerous: \(cmd)"
            )
        }
    }
    
    func testSafeCommandsAllowed() {
        let safeCommands = [
            "ls -la",
            "cat README.md",
            "git status",
            "python3 test.py",
            "echo 'hello'",
        ]
        
        for cmd in safeCommands {
            XCTAssertFalse(
                DangerousCommands.isCommandDangerous(cmd),
                "Command should be allowed: \(cmd)"
            )
        }
    }
    
    func testRegexWordBoundaries() {
        // Test that "form" doesn't trigger "format" block
        XCTAssertFalse(DangerousCommands.isCommandDangerous("transform data"))
        
        // But "format" should be blocked
        XCTAssertTrue(DangerousCommands.isCommandDangerous("format /dev/sda"))
    }
    
    // MARK: - Security Guard Tests
    
    func testSecurityGuardBlocksYoloForGuest() {
        securityManager.switchRole(to: .guest)
        
        XCTAssertThrowsError(try SecurityGuard.checkYoloPermission()) { error in
            XCTAssertTrue(error is SecurityError)
            if case SecurityError.yoloNotAllowed(let role) = error {
                XCTAssertEqual(role, .guest)
            } else {
                XCTFail("Wrong error type")
            }
        }
    }
    
    func testSecurityGuardAllowsYoloForAdmin() {
        securityManager.switchRole(to: .admin)
        
        XCTAssertNoThrow(try SecurityGuard.checkYoloPermission())
    }
    
    func testSecurityGuardBlocksDangerousCommands() {
        securityManager.switchRole(to: .user)
        
        XCTAssertThrowsError(try SecurityGuard.checkCommandSafety("sudo rm -rf /")) { error in
            XCTAssertTrue(error is SecurityError)
            if case SecurityError.dangerousCommand(let cmd) = error {
                XCTAssertTrue(cmd.contains("sudo"))
            } else {
                XCTFail("Wrong error type")
            }
        }
    }
    
    func testSecurityGuardAllowsSafeCommands() {
        securityManager.switchRole(to: .user)
        
        XCTAssertNoThrow(try SecurityGuard.checkCommandSafety("ls -la"))
        XCTAssertNoThrow(try SecurityGuard.checkCommandSafety("git status"))
    }
    
    // MARK: - Provider Permission Tests
    
    func testSecurityGuardBlocksProvidersForGuest() {
        securityManager.switchRole(to: .guest)
        
        XCTAssertThrowsError(try SecurityGuard.checkProviderPermission(.claude))
        XCTAssertThrowsError(try SecurityGuard.checkProviderPermission(.gpt))
        XCTAssertNoThrow(try SecurityGuard.checkProviderPermission(.ollama))
    }
    
    func testSecurityGuardAllowsProvidersForAdmin() {
        securityManager.switchRole(to: .admin)
        
        XCTAssertNoThrow(try SecurityGuard.checkProviderPermission(.claude))
        XCTAssertNoThrow(try SecurityGuard.checkProviderPermission(.gpt))
        XCTAssertNoThrow(try SecurityGuard.checkProviderPermission(.ollama))
    }
}
