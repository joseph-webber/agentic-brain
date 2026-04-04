import Foundation
import Security

enum APIKeyKind: String, Sendable {
    case claude = "claude-api-key"
    case openAI = "openai-api-key"
    case groq = "groq-api-key"
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
    private let serviceName = "com.brainchat.app"

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

    func loadGroqAPIKey() throws -> String {
        if let environmentValue = environmentValue(named: "GROQ_API_KEY"), !environmentValue.isEmpty {
            return environmentValue
        }

        if let providerValue = key(for: "groq")?.trimmingCharacters(in: .whitespacesAndNewlines), !providerValue.isEmpty {
            return providerValue
        }

        let dedicatedValue = try load(.groq).trimmingCharacters(in: .whitespacesAndNewlines)
        if !dedicatedValue.isEmpty {
            return dedicatedValue
        }

        return try load(.grok).trimmingCharacters(in: .whitespacesAndNewlines)
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

    private func environmentValue(named name: String) -> String? {
        if let processValue = ProcessInfo.processInfo.environment[name]?.trimmingCharacters(in: .whitespacesAndNewlines), !processValue.isEmpty {
            return processValue
        }

        for url in candidateDotEnvURLs() {
            guard let contents = try? String(contentsOf: url, encoding: .utf8) else { continue }
            for line in contents.split(whereSeparator: \.isNewline) {
                let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmed.isEmpty, !trimmed.hasPrefix("#") else { continue }
                let parts = trimmed.split(separator: "=", maxSplits: 1, omittingEmptySubsequences: false)
                guard parts.count == 2 else { continue }
                let key = String(parts[0]).trimmingCharacters(in: .whitespacesAndNewlines)
                guard key == name else { continue }

                var value = String(parts[1]).trimmingCharacters(in: .whitespacesAndNewlines)
                if value.hasPrefix("\""), value.hasSuffix("\""), value.count >= 2 {
                    value.removeFirst()
                    value.removeLast()
                } else if value.hasPrefix("'"), value.hasSuffix("'"), value.count >= 2 {
                    value.removeFirst()
                    value.removeLast()
                }

                if !value.isEmpty {
                    return value
                }
            }
        }

        return nil
    }

    private func candidateDotEnvURLs() -> [URL] {
        let fileManager = FileManager.default
        var urls: [URL] = [fileManager.homeDirectoryForCurrentUser.appending(path: "brain/.env")]
        var currentURL = URL(fileURLWithPath: fileManager.currentDirectoryPath, isDirectory: true)

        while true {
            urls.append(currentURL.appending(path: ".env"))
            let parentURL = currentURL.deletingLastPathComponent()
            if parentURL.path == currentURL.path { break }
            currentURL = parentURL
        }

        var seen = Set<String>()
        return urls.filter { seen.insert($0.path).inserted }
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
            kSecAttrService as String: "com.brainchat.app.providers",
            kSecAttrAccount as String: provider,
        ]
    }

    func setKey(_ value: String, for provider: String) throws {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            removeKey(for: provider)
            return
        }
        let data = Data(trimmed.utf8)
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
