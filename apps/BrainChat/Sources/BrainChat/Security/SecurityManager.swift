import Foundation
import Combine
import SwiftUI

@MainActor
final class SecurityManager: ObservableObject {
    static let shared = SecurityManager()
    static let guestBlockedOperations: Set<String> = [
        "web_search",
        "execute_code",
        "file_access",
        "shell_command",
    ]
    static let guestAllowedOperations: Set<String> = [
        "help",
        "faq",
    ]

    @Published private(set) var currentRole: SecurityRole
    @Published private(set) var modeSwitchingEnabled: Bool
    @AppStorage("securityRole") private var storedRole: String = SecurityRole.fullAdmin.rawValue

    private let defaults: UserDefaults
    private let defaultRoleForJoseph: SecurityRole = .fullAdmin

    private init(defaults: UserDefaults = .standard) {
        self.defaults = defaults

        let restoredRole = SecurityRole(storedValue: defaults.string(forKey: "securityRole") ?? SecurityRole.fullAdmin.rawValue) ?? defaultRoleForJoseph
        self.currentRole = restoredRole
        self.modeSwitchingEnabled = defaults.object(forKey: "modeSwitchingEnabled") as? Bool ?? true

        storedRole = restoredRole.rawValue
        defaults.set(restoredRole.rawValue, forKey: "securityRole")
        defaults.set(modeSwitchingEnabled, forKey: "modeSwitchingEnabled")
    }

    func switchRole(to newRole: SecurityRole) {
        guard modeSwitchingEnabled else {
            print("⚠️ Mode switching is disabled")
            return
        }

        currentRole = newRole
        storedRole = newRole.rawValue
        defaults.set(newRole.rawValue, forKey: "securityRole")
        print("🔐 Security role changed to: \(newRole.rawValue)")
    }

    func setRole(_ newRole: SecurityRole) {
        switchRole(to: newRole)
    }

    func resetToDefault() {
        switchRole(to: defaultRoleForJoseph)
    }

    func setModeSwitching(enabled: Bool) {
        modeSwitchingEnabled = enabled
        defaults.set(enabled, forKey: "modeSwitchingEnabled")

        if !enabled {
            resetToDefault()
        }
    }

    func canUseYolo() -> Bool {
        PermissionChecker.canUseYolo(role: currentRole)
    }

    func requiresSafetyChecksInYolo() -> Bool {
        PermissionChecker.requiresSafetyChecksInYolo(role: currentRole)
    }

    func canUseProvider(_ provider: LLMProvider) -> Bool {
        PermissionChecker.canUseProvider(provider, role: currentRole)
    }

    func providerRateLimit(for provider: LLMProvider) -> (limit: Int, period: String)? {
        PermissionChecker.providerRateLimit(for: provider, role: currentRole)
    }

    func canWriteFiles() -> Bool {
        currentRole.canAccessFilesystem
    }

    func canExecuteCode() -> Bool {
        PermissionChecker.canExecuteCode(role: currentRole)
    }

    func canExecuteShellCommand(_ command: String) -> Bool {
        PermissionChecker.canExecuteShellCommand(command, role: currentRole)
    }

    func canAccessPath(_ path: String, operation: FileOperation) -> Bool {
        PermissionChecker.canAccessPath(path, role: currentRole, operation: operation)
    }

    func requiresRestrictionConfirmation(for role: SecurityRole) -> Bool {
        role.restrictionRank < currentRole.restrictionRank
    }

    func canPerformOperation(_ operation: String) -> Bool {
        switch currentRole {
        case .fullAdmin, .safeAdmin:
            return true
        case .user:
            return !Self.guestBlockedOperations.contains(operation)
        case .guest:
            return Self.guestAllowedOperations.contains(operation)
        }
    }

    func yoloAccessDeniedMessage() -> String {
        switch currentRole {
        case .fullAdmin, .safeAdmin:
            return "YOLO mode is available."
        case .user:
            return "YOLO mode is blocked in User mode. Switch Security Mode to Full Admin or Safe Admin for autonomous actions."
        case .guest:
            return "YOLO mode is blocked in Guest mode. Switch Security Mode to Full Admin or Safe Admin for autonomous actions."
        }
    }

    func requiresYoloConfirmation() -> Bool {
        currentRole.yoloRequiresConfirmation
    }
}
