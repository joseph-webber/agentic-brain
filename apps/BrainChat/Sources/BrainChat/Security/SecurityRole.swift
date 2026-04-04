import Foundation

enum SecurityRole: String, CaseIterable, Codable, Sendable {
    case fullAdmin = "full_admin"
    case safeAdmin = "safe_admin"
    case user = "user"
    case guest = "guest"

    init?(storedValue: String) {
        switch storedValue.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
        case SecurityRole.fullAdmin.rawValue, "admin": self = .fullAdmin
        case SecurityRole.safeAdmin.rawValue: self = .safeAdmin
        case SecurityRole.user.rawValue: self = .user
        case SecurityRole.guest.rawValue: self = .guest
        default: return nil
        }
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        let raw = try container.decode(String.self)
        guard let role = SecurityRole(storedValue: raw) else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "Invalid security role: \(raw)")
        }
        self = role
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }

    var displayName: String {
        switch self {
        case .fullAdmin: return "🔓 Full Admin (Unrestricted)"
        case .safeAdmin: return "🛡️ Safe Admin (With Guardrails)"
        case .user: return "👤 User (API Access)"
        case .guest: return "👋 Guest (Help Only)"
        }
    }

    var description: String {
        switch self {
        case .fullAdmin: return "Complete unrestricted access - all YOLO commands execute immediately"
        case .safeAdmin: return "Full access with confirmation dialogs for dangerous operations"
        case .user: return "API-only access - can use LLM providers, no code execution or filesystem access"
        case .guest: return "FAQ and help only - cannot use external APIs or execute code"
        }
    }

    var accessibilityName: String {
        switch self {
        case .fullAdmin: return "Full Admin"
        case .safeAdmin: return "Safe Admin"
        case .user: return "User"
        case .guest: return "Guest"
        }
    }

    var iconName: String {
        switch self {
        case .fullAdmin: return "lock.open.fill"
        case .safeAdmin: return "shield.checkered"
        case .user: return "person.fill"
        case .guest: return "figure.wave"
        }
    }

    var color: String {
        switch self {
        case .fullAdmin: return "#E74C3C"
        case .safeAdmin: return "#2ECC71"
        case .user: return "#F39C12"
        case .guest: return "#3498DB"
        }
    }

    var restrictionRank: Int {
        switch self {
        case .fullAdmin: return 3
        case .safeAdmin: return 2
        case .user: return 1
        case .guest: return 0
        }
    }

    var canYolo: Bool {
        switch self {
        case .fullAdmin, .safeAdmin: return true
        case .user, .guest: return false
        }
    }

    var yoloRequiresConfirmation: Bool {
        return self == .safeAdmin
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
}

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
            return "YOLO mode not allowed for role: \(role.accessibilityName). Requires Admin mode."
        case .dangerousCommand(let cmd):
            return "Dangerous command blocked: \(cmd)"
        case .llmProviderNotAllowed(let provider, let role):
            return "LLM provider '\(provider)' not allowed for role: \(role.accessibilityName)"
        case .rateLimitExceeded(let provider, let limit, let period):
            return "Rate limit exceeded for \(provider): \(limit) requests per \(period)"
        case .codeExecutionBlocked(let role):
            return "Code execution not allowed for role: \(role.accessibilityName)"
        case .pathAccessDenied(let path):
            return "Access denied to path: \(path)"
        }
    }
}
