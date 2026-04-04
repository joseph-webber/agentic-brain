import XCTest
@testable import BrainChatLib

final class SecurityRoleTests: XCTestCase {
    
    func testAllCases() {
        let roles = SecurityRole.allCases
        XCTAssertEqual(roles.count, 4, "Should have 4 security roles")
        XCTAssertTrue(roles.contains(.fullAdmin))
        XCTAssertTrue(roles.contains(.safeAdmin))
        XCTAssertTrue(roles.contains(.user))
        XCTAssertTrue(roles.contains(.guest))
    }
    
    func testRoleDisplayNames() {
        XCTAssertEqual(SecurityRole.fullAdmin.displayName, "🔓 Full Admin (Unrestricted)")
        XCTAssertEqual(SecurityRole.safeAdmin.displayName, "🛡️ Safe Admin (With Guardrails)")
        XCTAssertEqual(SecurityRole.user.displayName, "👤 User (API Access)")
        XCTAssertEqual(SecurityRole.guest.displayName, "👋 Guest (Help Only)")
    }
    
    func testRoleAccessibilityNames() {
        XCTAssertEqual(SecurityRole.fullAdmin.accessibilityName, "Full Admin")
        XCTAssertEqual(SecurityRole.safeAdmin.accessibilityName, "Safe Admin")
        XCTAssertEqual(SecurityRole.user.accessibilityName, "User")
        XCTAssertEqual(SecurityRole.guest.accessibilityName, "Guest")
    }
    
    func testRoleDescriptions() {
        XCTAssertFalse(SecurityRole.fullAdmin.description.isEmpty)
        XCTAssertFalse(SecurityRole.safeAdmin.description.isEmpty)
        XCTAssertFalse(SecurityRole.user.description.isEmpty)
        XCTAssertFalse(SecurityRole.guest.description.isEmpty)
        
        XCTAssertTrue(SecurityRole.fullAdmin.description.contains("unrestricted"))
        XCTAssertTrue(SecurityRole.safeAdmin.description.contains("confirmation"))
        XCTAssertTrue(SecurityRole.user.description.contains("API"))
        XCTAssertTrue(SecurityRole.guest.description.contains("help"))
    }
    
    func testRoleIcons() {
        XCTAssertEqual(SecurityRole.fullAdmin.iconName, "lock.open.fill")
        XCTAssertEqual(SecurityRole.safeAdmin.iconName, "shield.checkered")
        XCTAssertEqual(SecurityRole.user.iconName, "person.fill")
        XCTAssertEqual(SecurityRole.guest.iconName, "figure.wave")
    }
    
    func testRoleColors() {
        XCTAssertEqual(SecurityRole.fullAdmin.color, "#E74C3C")
        XCTAssertEqual(SecurityRole.safeAdmin.color, "#2ECC71")
        XCTAssertEqual(SecurityRole.user.color, "#F39C12")
        XCTAssertEqual(SecurityRole.guest.color, "#3498DB")
    }
    
    func testRestrictionRank() {
        XCTAssertEqual(SecurityRole.fullAdmin.restrictionRank, 3)
        XCTAssertEqual(SecurityRole.safeAdmin.restrictionRank, 2)
        XCTAssertEqual(SecurityRole.user.restrictionRank, 1)
        XCTAssertEqual(SecurityRole.guest.restrictionRank, 0)
    }
    
    func testCanYolo() {
        XCTAssertTrue(SecurityRole.fullAdmin.canYolo, "Full Admin should have YOLO access")
        XCTAssertTrue(SecurityRole.safeAdmin.canYolo, "Safe Admin should have YOLO access")
        XCTAssertFalse(SecurityRole.user.canYolo, "User should not have YOLO access")
        XCTAssertFalse(SecurityRole.guest.canYolo, "Guest should not have YOLO access")
    }
    
    func testYoloRequiresConfirmation() {
        XCTAssertFalse(SecurityRole.fullAdmin.yoloRequiresConfirmation, "Full Admin should not require confirmation")
        XCTAssertTrue(SecurityRole.safeAdmin.yoloRequiresConfirmation, "Safe Admin should require confirmation")
        XCTAssertFalse(SecurityRole.user.yoloRequiresConfirmation, "User doesn't have YOLO access")
        XCTAssertFalse(SecurityRole.guest.yoloRequiresConfirmation, "Guest doesn't have YOLO access")
    }
    
    func testCanAccessFilesystem() {
        XCTAssertTrue(SecurityRole.fullAdmin.canAccessFilesystem, "Full Admin should access filesystem")
        XCTAssertTrue(SecurityRole.safeAdmin.canAccessFilesystem, "Safe Admin should access filesystem")
        XCTAssertFalse(SecurityRole.user.canAccessFilesystem, "User should not access filesystem")
        XCTAssertFalse(SecurityRole.guest.canAccessFilesystem, "Guest should not access filesystem")
    }
    
    func testCanAccessAPIs() {
        XCTAssertTrue(SecurityRole.fullAdmin.canAccessAPIs, "Full Admin should access APIs")
        XCTAssertTrue(SecurityRole.safeAdmin.canAccessAPIs, "Safe Admin should access APIs")
        XCTAssertTrue(SecurityRole.user.canAccessAPIs, "User should access APIs")
        XCTAssertFalse(SecurityRole.guest.canAccessAPIs, "Guest should not access APIs")
    }
    
    func testStoredValueInit() {
        XCTAssertEqual(SecurityRole(storedValue: "full_admin"), .fullAdmin)
        XCTAssertEqual(SecurityRole(storedValue: "admin"), .fullAdmin, "Should support legacy 'admin' value")
        XCTAssertEqual(SecurityRole(storedValue: "safe_admin"), .safeAdmin)
        XCTAssertEqual(SecurityRole(storedValue: "user"), .user)
        XCTAssertEqual(SecurityRole(storedValue: "guest"), .guest)
        
        XCTAssertEqual(SecurityRole(storedValue: "FULL_ADMIN"), .fullAdmin, "Should be case insensitive")
        XCTAssertEqual(SecurityRole(storedValue: " safe_admin "), .safeAdmin, "Should trim whitespace")
        
        XCTAssertNil(SecurityRole(storedValue: "invalid"), "Invalid values should return nil")
        XCTAssertNil(SecurityRole(storedValue: ""), "Empty string should return nil")
    }
    
    func testCodable() throws {
        let roles: [SecurityRole] = [.fullAdmin, .safeAdmin, .user, .guest]
        
        for role in roles {
            let encoded = try JSONEncoder().encode(role)
            let decoded = try JSONDecoder().decode(SecurityRole.self, from: encoded)
            XCTAssertEqual(role, decoded, "Role \(role.rawValue) should encode/decode correctly")
        }
    }
}
