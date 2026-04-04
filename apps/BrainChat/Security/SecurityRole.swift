import Foundation

/// Security roles for BrainChat - 4-tier model matching Python backend
enum SecurityRole: String, Codable, Sendable, CaseIterable {
    case fullAdmin = "full_admin"
    case safeAdmin = "safe_admin"
    case user = "user"
    case guest = "guest"
    
    var displayName: String {
        switch self {
        case .fullAdmin: return "Full Admin"
        case .safeAdmin: return "Safe Admin"
        case .user: return "User"
        case .guest: return "Guest"
        }
    }
    
    var description: String {
        switch self {
        case .fullAdmin:
            return "Tier 1: Complete unrestricted access (Joseph only) - Full YOLO, no confirmations, infinite rate limit"
        case .safeAdmin:
            return "Tier 2: Full access with guardrails (Developers/Trusted admins) - YOLO with confirmations, 1000/min rate limit"
        case .user:
            return "Tier 3: API-only access (Customers/Employees) - NO machine access, only APIs, 60/min rate limit"
        case .guest:
            return "Tier 4: Very restricted (Anonymous visitors) - Read-only FAQ/docs, 10/min rate limit"
        }
    }
    
    var iconName: String {
        switch self {
        case .fullAdmin: return "crown.fill"
        case .safeAdmin: return "shield.fill"
        case .user: return "person.fill"
        case .guest: return "person.crop.circle"
        }
    }
    
    var color: String {
        switch self {
        case .fullAdmin: return "#FFD700"  // gold - unlimited power
        case .safeAdmin: return "#4A90E2"  // blue - safe but powerful
        case .user: return "#2ECC71"       // green - API access
        case .guest: return "#95A5A6"      // gray - limited
        }
    }
    
    var rateLimit: Int {
        switch self {
        case .fullAdmin: return Int.max  // infinite
        case .safeAdmin: return 1000
        case .user: return 60
        case .guest: return 10
        }
    }
    
    var canYolo: Bool {
        switch self {
        case .fullAdmin, .safeAdmin: return true
        case .user, .guest: return false
        }
    }
    
    var yoloRequiresConfirmation: Bool {
        switch self {
        case .fullAdmin: return false  // No confirmations for Joseph
        case .safeAdmin: return true   // Confirm dangerous ops
        case .user, .guest: return false  // Can't YOLO at all
        }
    }
    
    var canAccessFilesystem: Bool {
        switch self {
        case .fullAdmin, .safeAdmin: return true
        case .user, .guest: return false
        }
    }
    
    var canAccessAPIs: Bool {
        switch self {
        case .fullAdmin, .safeAdmin, .user: return true
        case .guest: return false
        }
    }
    
    var allowedAPIScopes: Set<String> {
        switch self {
        case .fullAdmin: return ["read", "write", "delete", "admin"]
        case .safeAdmin: return ["read", "write", "delete"]
        case .user: return ["read", "write"]
        case .guest: return []
        }
    }
}

/// Errors related to security and permissions
enum SecurityError: LocalizedError {
    case yoloNotAllowed(currentRole: SecurityRole)
    case dangerousCommand(String)
    case llmProviderNotAllowed(provider: String, currentRole: SecurityRole)
    case rateLimitExceeded(provider: String, limit: Int, period: String)
    case codeExecutionBlocked(currentRole: SecurityRole)
    case pathAccessDenied(path: String)
    
    var errorDescription: String? {
        switch self {
        case .yoloNotAllowed(let role):
            return "YOLO mode not allowed for role: \(role.rawValue). Requires Admin or User role."
        case .dangerousCommand(let cmd):
            return "Dangerous command blocked: \(cmd)"
        case .llmProviderNotAllowed(let provider, let role):
            return "LLM provider '\(provider)' not allowed for role: \(role.rawValue)"
        case .rateLimitExceeded(let provider, let limit, let period):
            return "Rate limit exceeded for \(provider): \(limit) requests per \(period)"
        case .codeExecutionBlocked(let role):
            return "Code execution not allowed for role: \(role.rawValue)"
        case .pathAccessDenied(let path):
            return "Access denied to path: \(path)"
        }
    }
}
