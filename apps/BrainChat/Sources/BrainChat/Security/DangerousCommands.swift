import Foundation

/// Database of dangerous command patterns and system paths
struct DangerousCommands {
    
    // MARK: - Blocked Command Patterns
    
    static let blocked: Set<String> = [
        "rm -rf",
        "sudo",
        "chmod 777",
        "chown",
        "dd if=",
        "mkfs",
        "format",
        "> /dev/",
        ":(){ :|:& };:",  // fork bomb
        "shutdown",
        "reboot",
        "halt",
        "init 0",
        "init 6",
        "|.*bash",  // piping to shell
        "|.*sh",
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
        
        // Check blocked patterns with proper word boundaries
        for pattern in blocked {
            // Escape special regex characters in the pattern
            let escaped = NSRegularExpression.escapedPattern(for: pattern)
            
            // Use word boundary for patterns that should be whole words
            let regexPattern: String
            if pattern.contains(" ") || pattern.contains("(") || pattern.contains("|") {
                // For multi-word patterns or special patterns, match anywhere
                regexPattern = escaped
            } else {
                // For single words, use word boundaries
                regexPattern = "\\b\(escaped)"
            }
            
            if trimmed.range(of: regexPattern, options: .regularExpression) != nil {
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
}
