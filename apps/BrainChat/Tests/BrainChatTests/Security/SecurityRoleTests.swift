import XCTest
@testable import BrainChat

final class SecurityRoleTests: XCTestCase {
    
    func testRoleDisplayNames() {
        XCTAssertEqual(SecurityRole.admin.displayName, "Admin")
        XCTAssertEqual(SecurityRole.user.displayName, "User")
        XCTAssertEqual(SecurityRole.guest.displayName, "Guest")
    }
    
    func testRoleDescriptions() {
        XCTAssertFalse(SecurityRole.admin.description.isEmpty)
        XCTAssertFalse(SecurityRole.user.description.isEmpty)
        XCTAssertFalse(SecurityRole.guest.description.isEmpty)
    }
    
    func testRoleIcons() {
        XCTAssertEqual(SecurityRole.admin.iconName, "crown.fill")
        XCTAssertEqual(SecurityRole.user.iconName, "person.fill")
        XCTAssertEqual(SecurityRole.guest.iconName, "person.crop.circle")
    }
    
    func testRoleColors() {
        XCTAssertEqual(SecurityRole.admin.color, "#FFD700")
        XCTAssertEqual(SecurityRole.user.color, "#4A90E2")
        XCTAssertEqual(SecurityRole.guest.color, "#95A5A6")
    }
    
    func testAllCases() {
        let roles = SecurityRole.allCases
        XCTAssertEqual(roles.count, 3)
        XCTAssertTrue(roles.contains(.admin))
        XCTAssertTrue(roles.contains(.user))
        XCTAssertTrue(roles.contains(.guest))
    }
}
