import Foundation

// =============================================================================
// CodeSpeaker — Accessible code-to-speech formatting for blind developers
// Converts raw code into clear, spoken descriptions with line numbers,
// identifier spelling, and language-aware pronunciation
// =============================================================================

final class CodeSpeaker: @unchecked Sendable {

    // MARK: - Line Formatting

    /// Format a single line for speech with line number prefix.
    func formatLine(number: Int, content: String) -> String {
        let trimmed = content.trimmingCharacters(in: .whitespaces)
        if trimmed.isEmpty {
            return "Line \(number): blank"
        }
        let spoken = pronounceCode(trimmed)
        return "Line \(number): \(spoken)"
    }

    // MARK: - Code Block Formatting

    /// Format a full code block for speech output.
    func formatForSpeech(_ code: String, language: String? = nil) -> String {
        let lines = code.components(separatedBy: "\n")
        let lineCount = lines.count

        var result: [String] = []

        if let lang = language ?? Self.detectLanguageFromFilename(code) ?? Self.detectLanguageFromCode(code) {
            result.append("\(lang) code, \(lineCount) line\(lineCount == 1 ? "" : "s").")
        } else {
            result.append("Code block, \(lineCount) line\(lineCount == 1 ? "" : "s").")
        }

        for (index, line) in lines.enumerated() {
            let lineNum = index + 1
            result.append(formatLine(number: lineNum, content: line))
        }

        result.append("End of code.")
        return result.joined(separator: "\n")
    }

    /// Format code with context for a specific range.
    func formatRange(lines: [String], from start: Int, to end: Int) -> String {
        var result: [String] = []
        let clamped = max(0, start - 1)..<min(end, lines.count)
        for index in clamped {
            result.append(formatLine(number: index + 1, content: lines[index]))
        }
        return result.joined(separator: "\n")
    }

    // MARK: - Identifier Spelling

    /// Spell out an identifier character by character for clarity.
    func spellIdentifier(_ name: String) -> String {
        var parts: [String] = []

        if name.contains("_") {
            // snake_case
            let segments = name.components(separatedBy: "_")
            parts.append("\(name) is snake case with \(segments.count) parts:")
            for segment in segments {
                parts.append("  \(segment): \(spellWord(segment))")
            }
        } else if name.contains(where: { $0.isUppercase }) && name.contains(where: { $0.isLowercase }) {
            // PascalCase or camelCase
            let segments = splitCamelCase(name)
            let caseType = name.first!.isUppercase ? "Pascal case" : "camel case"
            parts.append("\(name) is \(caseType) with \(segments.count) parts:")
            for segment in segments {
                parts.append("  \(segment)")
            }
        } else {
            parts.append("\(name) spelled: \(spellWord(name))")
        }

        return parts.joined(separator: "\n")
    }

    // MARK: - Code Pronunciation

    /// Convert code symbols and syntax to spoken words.
    func pronounceCode(_ code: String) -> String {
        var result = code

        // Pronounce common operators and symbols
        let replacements: [(String, String)] = [
            ("!==", " not identical to "),
            ("===", " identical to "),
            ("??", " nil coalescing "),
            ("!=", " not equal to "),
            ("==", " equals equals "),
            (">=", " greater than or equal to "),
            ("<=", " less than or equal to "),
            ("=>", " arrow "),
            ("->", " returns "),
            ("+=", " plus equals "),
            ("-=", " minus equals "),
            ("*=", " times equals "),
            ("/=", " divide equals "),
            ("&&", " and "),
            ("||", " or "),
            ("...", " dot dot dot "),
            ("..<", " up to "),
            ("::", " scope "),
        ]

        for (symbol, spoken) in replacements {
            result = result.replacingOccurrences(of: symbol, with: spoken)
        }

        // Pronounce common keywords more clearly
        let keywordReplacements: [(String, String)] = [
            ("def ", "define function "),
            ("func ", "function "),
            ("elif ", "else if "),
            ("impl ", "implement "),
            ("pub fn ", "public function "),
            ("async fn ", "async function "),
        ]
        for (keyword, spoken) in keywordReplacements {
            if result.hasPrefix(keyword) {
                result = spoken + result.dropFirst(keyword.count)
            }
        }

        return pronounceStandaloneSymbols(in: result)
    }

    // MARK: - Language Detection

    /// Detect programming language from filename extension.
    static func detectLanguageFromFilename(_ filename: String) -> String? {
        let ext = (filename as NSString).pathExtension.lowercased()
        return extensionToLanguage[ext]
    }

    /// Detect programming language from code content.
    static func detectLanguageFromCode(_ code: String) -> String? {
        // Check code heuristics
        if code.contains("def ") && code.contains(":") && !code.contains("{") {
            return "Python"
        }
        if code.contains("func ") && code.contains("->") {
            return "Swift"
        }
        if code.contains("function") && (code.contains("const ") || code.contains("let ") || code.contains("var ")) {
            return "JavaScript"
        }
        if code.contains("fn ") && code.contains("->") && code.contains("let mut") {
            return "Rust"
        }
        if code.contains("package ") && code.contains("func ") && !code.contains("->") {
            return "Go"
        }
        return nil
    }

    // MARK: - Private Helpers

    private func spellWord(_ word: String) -> String {
        word.map { char -> String in
            if char.isUppercase {
                return "capital \(char)"
            }
            if char == "_" { return "underscore" }
            if char == "-" { return "dash" }
            if char == "." { return "dot" }
            return String(char)
        }.joined(separator: ", ")
    }

    private func splitCamelCase(_ name: String) -> [String] {
        var segments: [String] = []
        var current = ""
        for char in name {
            if char.isUppercase && !current.isEmpty {
                segments.append(current)
                current = String(char)
            } else {
                current.append(char)
            }
        }
        if !current.isEmpty { segments.append(current) }
        return segments
    }

    private func pronounceStandaloneSymbols(in code: String) -> String {
        let symbols: [Character: String] = [
            "{": "open brace",
            "}": "close brace",
            "(": "open paren",
            ")": "close paren",
            "[": "open bracket",
            "]": "close bracket",
            "=": "equals",
            "+": "plus",
            "-": "minus",
            "*": "times",
            "/": "slash",
            "%": "modulo",
            "<": "less than",
            ">": "greater than",
            "!": "bang",
            "?": "question mark",
            ":": "colon",
            ";": "semicolon",
            ",": "comma",
            ".": "dot",
            "#": "hash",
            "@": "at sign",
            "$": "dollar sign",
            "&": "ampersand",
            "|": "pipe",
            "\\": "backslash"
        ]

        var parts: [String] = []
        var currentText = ""

        func flushCurrentText() {
            let trimmed = currentText.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty {
                parts.append(trimmed)
            }
            currentText = ""
        }

        for character in code {
            if let spoken = symbols[character] {
                flushCurrentText()
                parts.append(spoken)
            } else {
                currentText.append(character)
            }
        }

        flushCurrentText()
        return parts
            .joined(separator: " ")
            .replacingOccurrences(of: #"\s+"#, with: " ", options: .regularExpression)
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static let extensionToLanguage: [String: String] = [
        "py": "Python",
        "swift": "Swift",
        "js": "JavaScript",
        "ts": "TypeScript",
        "tsx": "TypeScript React",
        "jsx": "JavaScript React",
        "java": "Java",
        "kt": "Kotlin",
        "rs": "Rust",
        "go": "Go",
        "rb": "Ruby",
        "php": "PHP",
        "c": "C",
        "cpp": "C++",
        "h": "C header",
        "cs": "C Sharp",
        "sh": "Shell",
        "bash": "Bash",
        "zsh": "Z Shell",
        "sql": "SQL",
        "html": "HTML",
        "css": "CSS",
        "json": "JSON",
        "yaml": "YAML",
        "yml": "YAML",
        "xml": "XML",
        "md": "Markdown",
        "r": "R",
        "m": "Objective-C",
        "lua": "Lua",
        "pl": "Perl",
        "ex": "Elixir",
        "exs": "Elixir Script",
    ]
}
