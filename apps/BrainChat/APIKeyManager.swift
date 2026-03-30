import Foundation
import Security

enum APIKeyKind: String, Sendable {
    case claude = "claude-api-key"
    case openAI = "openai-api-key"
    case grok = "grok-api-key"
    case gemini = "gemini-api-key"
}

enum KeychainError: LocalizedError {
    case unexpectedStatus(OSStatus)
    case invalidData

    var errorDescription: String? {
        switch self {
        case .unexpectedStatus(let status):
            return SecCopyErrorMessageString(status, nil) as String? ?? "Keychain error \(status)."
        case .invalidData:
            return "The keychain returned unreadable data."
        }
    }
}

struct APIKeyManager: Sendable {
    static let shared = APIKeyManager()
    private let serviceName = "com.josephwebber.brainchat"

    func save(_ value: String, for kind: APIKeyKind) throws {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            try delete(kind)
            return
        }
        let data = Data(trimmed.utf8)
        let query = baseQuery(for: kind)
        SecItemDelete(query as CFDictionary)
        var attributes = query
        attributes[kSecValueData as String] = data
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        let status = SecItemAdd(attributes as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainError.unexpectedStatus(status) }
    }

    func load(_ kind: APIKeyKind) throws -> String {
        var query = baseQuery(for: kind)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound { return "" }
        guard status == errSecSuccess else { throw KeychainError.unexpectedStatus(status) }
        guard let data = result as? Data, let value = String(data: data, encoding: .utf8) else {
            throw KeychainError.invalidData
        }
        return value
    }

    func delete(_ kind: APIKeyKind) throws {
        let status = SecItemDelete(baseQuery(for: kind) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw KeychainError.unexpectedStatus(status)
        }
    }

    private func baseQuery(for kind: APIKeyKind) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: serviceName,
            kSecAttrAccount as String: kind.rawValue,
        ]
    }
}

protocol APIKeyManaging {
    func setKey(_ value: String, for provider: String) throws
    func key(for provider: String) -> String?
    func removeKey(for provider: String)
    func hasKey(for provider: String) -> Bool
}

extension APIKeyManager: APIKeyManaging {
    private func providerQuery(_ provider: String) -> [String: Any] {
        [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "com.josephwebber.brainchat.providers",
            kSecAttrAccount as String: provider,
        ]
    }

    func setKey(_ value: String, for provider: String) throws {
        let data = Data(value.utf8)
        let query = providerQuery(provider)
        SecItemDelete(query as CFDictionary)
        var attributes = query
        attributes[kSecValueData as String] = data
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlock
        let status = SecItemAdd(attributes as CFDictionary, nil)
        guard status == errSecSuccess else { throw KeychainError.unexpectedStatus(status) }
    }

    func key(for provider: String) -> String? {
        var query = providerQuery(provider)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func removeKey(for provider: String) {
        SecItemDelete(providerQuery(provider) as CFDictionary)
    }

    func hasKey(for provider: String) -> Bool {
        key(for: provider).map { !$0.isEmpty } ?? false
    }
}
