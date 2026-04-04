import Foundation

/// Database of dangerous command patterns and system paths
struct DangerousCommands {

    private struct BlockedPattern {
        let pattern: String
        let isRegex: Bool
    }

    // MARK: - Blocked Command Patterns

    private static let blockedPatterns: [BlockedPattern] = [
        .init(pattern: "rm -rf", isRegex: false),
        .init(pattern: "sudo", isRegex: false),
        .init(pattern: "chmod 777", isRegex: false),
        .init(pattern: "chown", isRegex: false),
        .init(pattern: "dd if=", isRegex: false),
        .init(pattern: "mkfs", isRegex: false),
        .init(pattern: "format", isRegex: false),
        .init(pattern: "> /dev/", isRegex: false),
        .init(pattern: ":(){ :|:& };:", isRegex: false),
        .init(pattern: "shutdown", isRegex: false),
        .init(pattern: "reboot", isRegex: false),
        .init(pattern: "halt", isRegex: false),
        .init(pattern: "init 0", isRegex: false),
        .init(pattern: "init 6", isRegex: false),
        .init(pattern: #"\|\s*(?:bash|sh)\b"#, isRegex: true),
    ]
    
    // MARK: - Protected System Paths
    
    static let systemPaths: Set<String> = [
        "/etc/",
        "/usr/",
        "/bin/",
        "/sbin/",
        "/System/",
        "/Library/",
        "/private/",
        "/var/",
    ]
    
    // MARK: - Sensitive Files
    
    static let sensitiveFiles: Set<String> = [
        "/etc/passwd",
        "/etc/shadow",
        "/etc/hosts",
        "/etc/ssh/",
        "~/.ssh/",
        "~/.aws/",
        "~/.env",
        ".git/config",
    ]
    
    // MARK: - Command Safety Checks
    
    /// Check if a command contains dangerous patterns using proper regex
    static func isCommandDangerous(_ command: String) -> Bool {
        let trimmed = command.trimmingCharacters(in: .whitespacesAndNewlines)

        for blockedPattern in blockedPatterns {
            if matches(trimmed, pattern: blockedPattern) {
                return true
            }
        }

        // Check if accessing sensitive files
        for file in sensitiveFiles {
            let expanded = (file as NSString).expandingTildeInPath
            if trimmed.contains(expanded) {
                return true
            }
        }
        
        // Check if accessing system paths
        if isAccessingSystemPath(trimmed) {
            return true
        }
        
        return false
    }
    
    /// Check if a command accesses protected system paths
    static func isAccessingSystemPath(_ command: String) -> Bool {
        for path in systemPaths {
            if command.contains(path) {
                return true
            }
        }
        return false
    }
    
    /// Check if a file path is in a sensitive location
    static func isSensitivePath(_ path: String) -> Bool {
        let expanded = (path as NSString).expandingTildeInPath
        let standardized = (expanded as NSString).standardizingPath
        
        // Check system paths
        for systemPath in systemPaths {
            if standardized.hasPrefix(systemPath) {
                return true
            }
        }
        
        // Check sensitive files
        for sensitiveFile in sensitiveFiles {
            let expandedSensitive = (sensitiveFile as NSString).expandingTildeInPath
            if standardized.hasPrefix(expandedSensitive) || standardized == expandedSensitive {
                return true
            }
        }
        
        return false
    }
    
    /// Get safe command alternatives for common dangerous patterns
    static func safeAlternative(for command: String) -> String? {
        let lower = command.lowercased()
        
        if lower.contains("rm -rf") {
            return "Use 'trash' command or move to ~/.Trash instead"
        }
        
        if lower.contains("sudo") {
            return "Request explicit permission for privileged operations"
        }
        
        if lower.contains("chmod 777") {
            return "Use more restrictive permissions like 755 or 644"
        }
        
        if lower.contains("shutdown") || lower.contains("reboot") {
            return "System power operations require manual confirmation"
        }
        
        return nil
    }

    private static func matches(_ command: String, pattern: BlockedPattern) -> Bool {
        let regexPattern: String
        if pattern.isRegex {
            regexPattern = pattern.pattern
        } else {
            let escaped = NSRegularExpression.escapedPattern(for: pattern.pattern)
            let useWordBoundaries = pattern.pattern.rangeOfCharacter(from: .whitespacesAndNewlines) == nil
            regexPattern = useWordBoundaries ? "\\b\(escaped)\\b" : escaped
        }

        return command.range(of: regexPattern, options: .regularExpression) != nil
    }
}
