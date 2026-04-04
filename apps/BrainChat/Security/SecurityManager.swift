import Foundation
import Combine

/// Manages current security role and provides permission checking
@MainActor
final class SecurityManager: ObservableObject {
    static let shared = SecurityManager()
    
    @Published private(set) var currentRole: SecurityRole
    @Published private(set) var modeSwitchingEnabled: Bool
    
    private let defaults: UserDefaults
    private let defaultRoleForJoseph: SecurityRole = .fullAdmin
    
    private init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        
        // Load saved role, default to Admin for Joseph
        if let savedRole = defaults.string(forKey: "securityRole"),
           let role = SecurityRole(rawValue: savedRole) {
            self.currentRole = role
        } else {
            self.currentRole = defaultRoleForJoseph
            defaults.set(defaultRoleForJoseph.rawValue, forKey: "securityRole")
        }
        
        // Mode switching is for testing - default to enabled
        self.modeSwitchingEnabled = defaults.bool(forKey: "modeSwitchingEnabled")
        if defaults.object(forKey: "modeSwitchingEnabled") == nil {
            self.modeSwitchingEnabled = true
            defaults.set(true, forKey: "modeSwitchingEnabled")
        }
    }
    
    // MARK: - Role Management
    
    func switchRole(to newRole: SecurityRole) {
        guard modeSwitchingEnabled else {
            print("⚠️ Mode switching is disabled")
            return
        }
        
        currentRole = newRole
        defaults.set(newRole.rawValue, forKey: "securityRole")
        print("🔐 Security role changed to: \(newRole.rawValue)")
    }
    
    func resetToDefault() {
        switchRole(to: defaultRoleForJoseph)
    }
    
    func setModeSwitching(enabled: Bool) {
        modeSwitchingEnabled = enabled
        defaults.set(enabled, forKey: "modeSwitchingEnabled")
        
        if !enabled {
            // If disabling mode switching, reset to default
            resetToDefault()
        }
    }
    
    // MARK: - YOLO Permissions
    
    func canUseYolo() -> Bool {
        PermissionChecker.canUseYolo(role: currentRole)
    }
    
    func requiresSafetyChecksInYolo() -> Bool {
        PermissionChecker.requiresSafetyChecksInYolo(role: currentRole)
    }
    
    // MARK: - LLM Permissions
    
    func canUseProvider(_ provider: LLMProvider) -> Bool {
        PermissionChecker.canUseProvider(provider, role: currentRole)
    }
    
    func providerRateLimit(for provider: LLMProvider) -> (limit: Int, period: String)? {
        PermissionChecker.providerRateLimit(for: provider, role: currentRole)
    }
    
    // MARK: - Code Execution Permissions
    
    func canExecuteCode() -> Bool {
        PermissionChecker.canExecuteCode(role: currentRole)
    }
    
    func canExecuteShellCommand(_ command: String) -> Bool {
        PermissionChecker.canExecuteShellCommand(command, role: currentRole)
    }
    
    // MARK: - File System Permissions
    
    func canAccessPath(_ path: String, operation: FileOperation) -> Bool {
        PermissionChecker.canAccessPath(path, role: currentRole, operation: operation)
    }
}
