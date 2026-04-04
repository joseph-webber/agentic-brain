import XCTest
@testable import BrainChatLib

@MainActor
final class SecurityModeTests: XCTestCase {
    override func setUp() {
        super.setUp()
        SecurityManager.shared.switchRole(to: .fullAdmin)
    }

    override func tearDown() {
        SecurityManager.shared.switchRole(to: .fullAdmin)
        super.tearDown()
    }

    func testModeSwitchingUpdatesCurrentRole() {
        let securityManager = SecurityManager.shared

        securityManager.switchRole(to: .user)
        XCTAssertEqual(securityManager.currentRole, .user)

        securityManager.switchRole(to: .guest)
        XCTAssertEqual(securityManager.currentRole, .guest)

        securityManager.switchRole(to: .safeAdmin)
        XCTAssertEqual(securityManager.currentRole, .safeAdmin)

        securityManager.switchRole(to: .fullAdmin)
        XCTAssertEqual(securityManager.currentRole, .fullAdmin)
    }

    func testPermissionChecksReflectSelectedRole() {
        let securityManager = SecurityManager.shared

        securityManager.switchRole(to: .fullAdmin)
        XCTAssertTrue(securityManager.canUseYolo())
        XCTAssertTrue(securityManager.canWriteFiles())
        XCTAssertTrue(securityManager.canExecuteCode())

        securityManager.switchRole(to: .safeAdmin)
        XCTAssertTrue(securityManager.canUseYolo())
        XCTAssertTrue(securityManager.canWriteFiles())
        XCTAssertTrue(securityManager.canExecuteCode())

        securityManager.switchRole(to: .user)
        XCTAssertFalse(securityManager.canUseYolo())
        XCTAssertFalse(securityManager.canWriteFiles())
        XCTAssertFalse(securityManager.canExecuteCode())

        securityManager.switchRole(to: .guest)
        XCTAssertFalse(securityManager.canUseYolo())
        XCTAssertFalse(securityManager.canWriteFiles())
        XCTAssertFalse(securityManager.canExecuteCode())
    }

    func testYoloPromptIsBlockedForNonAdminUsers() async {
        let securityManager = SecurityManager.shared
        let yolo = YoloMode(securityManager: securityManager)

        securityManager.switchRole(to: .user)

        let response = await yolo.submitPrompt("Delete the operating system", targetLLM: "Copilot")

        XCTAssertEqual(response, securityManager.yoloAccessDeniedMessage())
        XCTAssertFalse(yolo.isActive)
    }
}
