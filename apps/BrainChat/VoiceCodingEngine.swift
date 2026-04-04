import Foundation

// =============================================================================
// VoiceCodingEngine — Voice command processor for blind coding workflow
// Parses natural speech into structured coding actions
// =============================================================================

enum VoiceCodingAction: Equatable {
    case readLine(Int)
    case readLines(Int, Int)
    case readFile(String)
    case goToFunction(String)
    case goToLine(Int)
    case explainCode(String?)
    case fixError(String?)
    case refactor(String?)
    case runTests(String?)
    case commitChanges(String)
    case saveToFile(String, String?)
    case searchCode(String)
    case listFunctions(String?)
    case undoLast
    case repeatLast
    case spellIdentifier(String)
    case readClipboard
    case copyCode(Int?)
    case insertLine(Int, String)
    case deleteLine(Int)
    case replaceText(String, String)
    case gitStatus
    case gitDiff
    case createFunction(String, String?)
    case createFile(String, String?)
    case openFile(String)
    case closeFile
    case none

    var spokenConfirmation: String {
        switch self {
        case .readLine(let n):
            return "Reading line \(n)"
        case .readLines(let start, let end):
            return "Reading lines \(start) through \(end)"
        case .readFile(let path):
            return "Reading file \(path)"
        case .goToFunction(let name):
            return "Going to function \(name)"
        case .goToLine(let n):
            return "Going to line \(n)"
        case .explainCode:
            return "Explaining the code"
        case .fixError:
            return "Looking for a fix"
        case .refactor:
            return "Suggesting refactoring"
        case .runTests(let dir):
            return dir != nil ? "Running tests in \(dir!)" : "Running tests"
        case .commitChanges(let msg):
            return "Committing: \(msg)"
        case .saveToFile(let name, _):
            return "Saving to \(name)"
        case .searchCode(let query):
            return "Searching for \(query)"
        case .listFunctions:
            return "Listing functions"
        case .undoLast:
            return "Undoing last change"
        case .repeatLast:
            return "Repeating last action"
        case .spellIdentifier(let name):
            return "Spelling \(name)"
        case .readClipboard:
            return "Reading clipboard"
        case .copyCode(let line):
            return line != nil ? "Copying line \(line!)" : "Copying code"
        case .insertLine(let n, _):
            return "Inserting at line \(n)"
        case .deleteLine(let n):
            return "Deleting line \(n)"
        case .replaceText(let old, _):
            return "Replacing \(old)"
        case .gitStatus:
            return "Checking git status"
        case .gitDiff:
            return "Showing git diff"
        case .createFunction(let name, _):
            return "Creating function \(name)"
        case .createFile(let name, _):
            return "Creating file \(name)"
        case .openFile(let name):
            return "Opening \(name)"
        case .closeFile:
            return "Closing file"
        case .none:
            return ""
        }
    }
}

final class VoiceCodingEngine: @unchecked Sendable {
    static let shared = VoiceCodingEngine()

    private let system = SystemCommands.shared
    private var currentFilePath: String?
    private var currentFileLines: [String] = []
    private var lastAction: VoiceCodingAction = .none
    private let codeSpeaker = CodeSpeaker()

    // MARK: - Command Parsing

    func parse(_ input: String) -> VoiceCodingAction {
        let lower = input.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)

        // Editing commands first (delete/insert/copy line must come before generic line reading)
        if let action = parseEditingCommand(lower, original: input) { return action }

        // Line reading: "read line 10", "what's on line 5"
        if let action = parseLineCommand(lower, original: input) { return action }

        // Navigation: "go to function X", "jump to line X"
        if let action = parseNavigationCommand(lower, original: input) { return action }

        // Code understanding
        if let action = parseUnderstandingCommand(lower, original: input) { return action }

        // File operations
        if let action = parseFileCommand(lower, original: input) { return action }

        // Git operations
        if let action = parseGitCommand(lower) { return action }

        // Meta commands
        if lower == "undo" || lower == "undo last" || lower == "undo that" {
            return .undoLast
        }
        if lower == "repeat" || lower == "again" || lower == "repeat last" || lower == "do it again" {
            return .repeatLast
        }

        return .none
    }

    /// Returns true if the input looks like a voice coding command.
    func isVoiceCodingCommand(_ input: String) -> Bool {
        parse(input) != .none
    }

    // MARK: - Execution

    func execute(_ action: VoiceCodingAction) async -> String {
        if action != .repeatLast {
            lastAction = action
        }

        switch action {
        case .readLine(let n):
            return readLine(n)
        case .readLines(let start, let end):
            return readLines(from: start, to: end)
        case .readFile(let path):
            return await openAndReadFile(path)
        case .goToFunction(let name):
            return findFunction(named: name)
        case .goToLine(let n):
            return readLine(n)
        case .explainCode(let context):
            return buildExplainPrompt(context: context)
        case .fixError(let context):
            return buildFixPrompt(context: context)
        case .refactor(let context):
            return buildRefactorPrompt(context: context)
        case .runTests(let dir):
            return await runTests(directory: dir)
        case .commitChanges(let message):
            return await commitChanges(message: message)
        case .saveToFile(let name, let content):
            return await saveFile(name: name, content: content)
        case .searchCode(let query):
            return await searchCode(query: query)
        case .listFunctions(let path):
            return listFunctions(in: path)
        case .undoLast:
            return "Undo is not yet supported in voice coding mode."
        case .repeatLast:
            if lastAction != .none && lastAction != .repeatLast {
                return await execute(lastAction)
            }
            return "No previous action to repeat."
        case .spellIdentifier(let name):
            return codeSpeaker.spellIdentifier(name)
        case .readClipboard:
            return "Clipboard contains: \(system.readClipboard())"
        case .copyCode(let line):
            return copyCode(line: line)
        case .insertLine(let n, let content):
            return insertLine(at: n, content: content)
        case .deleteLine(let n):
            return deleteLine(at: n)
        case .replaceText(let old, let new):
            return replaceText(old: old, new: new)
        case .gitStatus:
            return await gitStatus()
        case .gitDiff:
            return await gitDiff()
        case .createFunction(let name, let lang):
            return buildCreateFunctionPrompt(name: name, language: lang)
        case .createFile(let name, let lang):
            return await createFile(name: name, language: lang)
        case .openFile(let name):
            return await openAndReadFile(name)
        case .closeFile:
            currentFilePath = nil
            currentFileLines = []
            return "File closed."
        case .none:
            return ""
        }
    }

    /// Format code for accessible speech output.
    func speakCode(_ code: String, language: String? = nil) -> String {
        codeSpeaker.formatForSpeech(code, language: language)
    }

    // MARK: - Parse Helpers

    private func parseLineCommand(_ lower: String, original: String) -> VoiceCodingAction? {
        // Range patterns first (more specific): "read lines 10 to 20"
        let rangePatterns = [
            #"read lines? (\d+) (?:to|through|thru) (\d+)"#,
            #"show lines? (\d+) (?:to|through|thru) (\d+)"#,
            #"lines? (\d+) (?:to|through|thru) (\d+)"#,
        ]
        for pattern in rangePatterns {
            if let (start, end) = lower.firstTwoMatches(of: pattern) {
                return .readLines(start, end)
            }
        }

        // Single line: "read line 10"
        let readLinePatterns = [
            #"read line (\d+)"#,
            #"what's on line (\d+)"#,
            #"what is on line (\d+)"#,
            #"show line (\d+)"#,
            #"^line (\d+)$"#,
            #"go to line (\d+)"#,
            #"jump to line (\d+)"#,
        ]
        for pattern in readLinePatterns {
            if let match = lower.firstMatch(of: pattern), let n = Int(match) {
                return .readLine(n)
            }
        }

        return nil
    }

    private func parseNavigationCommand(_ lower: String, original: String) -> VoiceCodingAction? {
        // "go to function X", "find function X"
        let funcPatterns = [
            #"go to (?:function|method|def) (.+)"#,
            #"find (?:function|method|def) (.+)"#,
            #"jump to (?:function|method|def) (.+)"#,
            #"where is (?:function|method|def) (.+)"#,
        ]
        for pattern in funcPatterns {
            if let name = lower.firstStringMatch(of: pattern) {
                return .goToFunction(name.trimmingCharacters(in: .whitespaces))
            }
        }

        // "list functions"
        if lower.hasPrefix("list functions") || lower.hasPrefix("list all functions") || lower.hasPrefix("show functions") {
            return .listFunctions(currentFilePath)
        }

        // "search for X", "find X"
        let searchPatterns = [
            #"search (?:for |code )(.+)"#,
            #"find (?:where |)(.+)"#,
            #"grep (.+)"#,
        ]
        for pattern in searchPatterns {
            if let query = lower.firstStringMatch(of: pattern) {
                let trimmed = query.trimmingCharacters(in: .whitespaces)
                if !trimmed.isEmpty && trimmed.count > 2 {
                    return .searchCode(trimmed)
                }
            }
        }

        return nil
    }

    private func parseUnderstandingCommand(_ lower: String, original: String) -> VoiceCodingAction? {
        if lower.hasPrefix("explain this") || lower.hasPrefix("explain the code")
            || lower == "explain" || lower.hasPrefix("what does this") {
            let context = lower.replacingOccurrences(of: "explain this code", with: "")
                .replacingOccurrences(of: "explain this", with: "")
                .replacingOccurrences(of: "explain the code", with: "")
                .replacingOccurrences(of: "explain", with: "")
                .trimmingCharacters(in: .whitespaces)
            return .explainCode(context.isEmpty ? nil : context)
        }

        if lower.hasPrefix("fix this") || lower.hasPrefix("fix the error") || lower.hasPrefix("fix error")
            || lower.hasPrefix("debug this") || lower.hasPrefix("what's wrong") {
            let context = lower.replacingOccurrences(of: "fix this error", with: "")
                .replacingOccurrences(of: "fix the error", with: "")
                .replacingOccurrences(of: "fix error", with: "")
                .replacingOccurrences(of: "fix this", with: "")
                .replacingOccurrences(of: "debug this", with: "")
                .replacingOccurrences(of: "what's wrong", with: "")
                .trimmingCharacters(in: .whitespaces)
            return .fixError(context.isEmpty ? nil : context)
        }

        if lower.hasPrefix("refactor") {
            let context = lower.replacingOccurrences(of: "refactor this", with: "")
                .replacingOccurrences(of: "refactor", with: "")
                .trimmingCharacters(in: .whitespaces)
            return .refactor(context.isEmpty ? nil : context)
        }

        if lower.hasPrefix("spell ") || lower.hasPrefix("spell out ") {
            let name = lower.replacingOccurrences(of: "spell out ", with: "")
                .replacingOccurrences(of: "spell ", with: "")
                .trimmingCharacters(in: .whitespaces)
            return name.isEmpty ? nil : .spellIdentifier(name)
        }

        return nil
    }

    private func parseEditingCommand(_ lower: String, original: String) -> VoiceCodingAction? {
        // "delete line 5"
        if let match = lower.firstMatch(of: #"delete line (\d+)"#), let n = Int(match) {
            return .deleteLine(n)
        }

        // "insert at line 5 <code>"
        if let lineMatch = lower.firstMatch(of: #"insert (?:at |on |)line (\d+)"#), let n = Int(lineMatch) {
            let afterPattern = "insert at line \(n) "
            let altPattern = "insert on line \(n) "
            let altPattern2 = "insert line \(n) "
            var content = original
            for prefix in [afterPattern, altPattern, altPattern2] {
                if lower.hasPrefix(prefix) {
                    content = String(original.dropFirst(prefix.count))
                    break
                }
            }
            return .insertLine(n, content.trimmingCharacters(in: .whitespaces))
        }

        // "copy line 5"
        if let match = lower.firstMatch(of: #"copy line (\d+)"#), let n = Int(match) {
            return .copyCode(n)
        }
        if lower == "copy this" || lower == "copy code" || lower == "copy that" {
            return .copyCode(nil)
        }

        // "replace X with Y"
        if let (old, new) = lower.firstReplacePair() {
            return .replaceText(old, new)
        }

        // "create function X" / "create a function called X"
        let createFuncPatterns = [
            #"create (?:a |)(?:function|method|def) (?:called |named |)(\w+)"#,
            #"write (?:a |)(?:function|method|def) (?:called |named |)(\w+)"#,
        ]
        for pattern in createFuncPatterns {
            if let name = lower.firstStringMatch(of: pattern) {
                let lang = detectLanguageFromContext(lower)
                return .createFunction(name, lang)
            }
        }

        return nil
    }

    private func parseFileCommand(_ lower: String, original: String) -> VoiceCodingAction? {
        // "save to X" / "save as X"
        let savePatterns = [
            #"save (?:to|as|in) (.+)"#,
            #"write (?:to|as) (.+)"#,
        ]
        for pattern in savePatterns {
            if let name = lower.firstStringMatch(of: pattern) {
                return .saveToFile(name.trimmingCharacters(in: .whitespaces), nil)
            }
        }

        // "create file X"
        let createPatterns = [
            #"create (?:a |)(?:file|new file) (?:called |named |)(.+)"#,
            #"new file (.+)"#,
        ]
        for pattern in createPatterns {
            if let name = lower.firstStringMatch(of: pattern) {
                let lang = detectLanguageFromContext(lower)
                return .createFile(name.trimmingCharacters(in: .whitespaces), lang)
            }
        }

        // "open file X" / "open X"
        let openPatterns = [
            #"open (?:file |)(.+\.\w+)"#,
            #"read (?:file |)(.+\.\w+)"#,
            #"load (.+\.\w+)"#,
        ]
        for pattern in openPatterns {
            if let name = lower.firstStringMatch(of: pattern) {
                return .openFile(name.trimmingCharacters(in: .whitespaces))
            }
        }

        if lower == "close file" || lower == "close this file" {
            return .closeFile
        }

        // "run tests"
        if lower.hasPrefix("run tests") || lower.hasPrefix("run the tests") || lower.hasPrefix("run pytest") {
            let dir = lower.firstStringMatch(of: #"run (?:the )?tests? (?:in |for )(.+)"#)
            return .runTests(dir)
        }

        return nil
    }

    private func parseGitCommand(_ lower: String) -> VoiceCodingAction? {
        if lower == "git status" || lower == "check status" || lower == "what's changed" {
            return .gitStatus
        }
        if lower == "git diff" || lower == "show diff" || lower == "show changes" || lower == "what changed" {
            return .gitDiff
        }

        // "commit with message X", "commit X"
        let commitPatterns = [
            #"commit (?:with message |changes? |)(.+)"#,
            #"git commit (.+)"#,
        ]
        for pattern in commitPatterns {
            if let msg = lower.firstStringMatch(of: pattern) {
                let message = msg.trimmingCharacters(in: .whitespaces)
                if !message.isEmpty { return .commitChanges(message) }
            }
        }

        return nil
    }

    // MARK: - Execution Helpers

    private func readLine(_ n: Int) -> String {
        guard !currentFileLines.isEmpty else {
            return "No file is open. Say open file followed by the filename."
        }
        guard n > 0, n <= currentFileLines.count else {
            return "Line \(n) is out of range. The file has \(currentFileLines.count) lines."
        }
        let line = currentFileLines[n - 1]
        return codeSpeaker.formatLine(number: n, content: line)
    }

    private func readLines(from start: Int, to end: Int) -> String {
        guard !currentFileLines.isEmpty else {
            return "No file is open. Say open file followed by the filename."
        }
        let clamped = max(1, start)...min(end, currentFileLines.count)
        if clamped.isEmpty {
            return "Lines \(start) to \(end) are out of range. The file has \(currentFileLines.count) lines."
        }
        var result: [String] = []
        for i in clamped {
            result.append(codeSpeaker.formatLine(number: i, content: currentFileLines[i - 1]))
        }
        return result.joined(separator: "\n")
    }

    private func openAndReadFile(_ path: String) async -> String {
        let resolvedPath = resolvePath(path)
        do {
            let content = try system.readFile(at: resolvedPath)
            currentFilePath = resolvedPath
            currentFileLines = content.components(separatedBy: "\n")
            let lineCount = currentFileLines.count
            let filename = (resolvedPath as NSString).lastPathComponent
            let lang = CodeSpeaker.detectLanguageFromFilename(filename)
            var summary = "Opened \(filename). \(lineCount) lines"
            if let lang = lang { summary += " of \(lang)" }
            summary += ". Say read line followed by a number, or list functions."
            return summary
        } catch {
            return "Could not open file: \(error.localizedDescription)"
        }
    }

    private func findFunction(named name: String) -> String {
        guard !currentFileLines.isEmpty else {
            return "No file is open. Open a file first."
        }
        let lowerName = name.lowercased()
        let patterns = [
            "func \(lowerName)", "def \(lowerName)", "function \(lowerName)",
            "fn \(lowerName)", "fun \(lowerName)",
        ]
        for (index, line) in currentFileLines.enumerated() {
            let lowerLine = line.lowercased().trimmingCharacters(in: .whitespaces)
            for pattern in patterns where lowerLine.contains(pattern) {
                let lineNum = index + 1
                let context = readLines(from: max(1, lineNum - 1), to: min(lineNum + 5, currentFileLines.count))
                return "Found \(name) at line \(lineNum).\n\(context)"
            }
        }
        return "Function \(name) not found in the current file."
    }

    private func listFunctions(in path: String?) -> String {
        let lines = currentFileLines.isEmpty ? [] : currentFileLines
        guard !lines.isEmpty else {
            return "No file is open."
        }

        let funcPattern = #"^\s*((?:public |private |internal |fileprivate |open |static |override |@\w+ )*(?:func|def|function|fn|fun|sub|void|int|string|bool)\s+\w+)"#
        var functions: [(Int, String)] = []
        for (index, line) in lines.enumerated() {
            if let regex = try? NSRegularExpression(pattern: funcPattern, options: .caseInsensitive) {
                let range = NSRange(line.startIndex..., in: line)
                if regex.firstMatch(in: line, range: range) != nil {
                    let trimmed = line.trimmingCharacters(in: .whitespaces)
                    functions.append((index + 1, String(trimmed.prefix(80))))
                }
            }
        }

        if functions.isEmpty {
            return "No functions found in the current file."
        }

        var result = "Found \(functions.count) functions:\n"
        for (lineNum, signature) in functions {
            result += "  Line \(lineNum): \(signature)\n"
        }
        return result
    }

    private func runTests(directory: String?) async -> String {
        let dir = directory ?? "/Users/joe/brain"
        do {
            let result = try system.runTests(in: dir)
            return result.succeeded ? "All tests passed.\n\(result.stdout)" : "Tests failed.\n\(result.output)"
        } catch {
            return "Error running tests: \(error.localizedDescription)"
        }
    }

    private func commitChanges(message: String) async -> String {
        do {
            let result = try system.run(
                "cd /Users/joe/brain && git add -A && git commit -m '\(message.replacingOccurrences(of: "'", with: "'\\''"))'",
                timeout: 30, workingDirectory: "/Users/joe/brain")
            return result.succeeded ? "Committed: \(message)" : "Commit failed: \(result.output)"
        } catch {
            return "Commit error: \(error.localizedDescription)"
        }
    }

    private func saveFile(name: String, content: String?) async -> String {
        let resolvedPath = resolvePath(name)
        let fileContent = content ?? currentFileLines.joined(separator: "\n")
        guard !fileContent.isEmpty else {
            return "Nothing to save. The file buffer is empty."
        }
        do {
            try system.writeFile(at: resolvedPath, content: fileContent)
            return "Saved to \(resolvedPath)."
        } catch {
            return "Save failed: \(error.localizedDescription)"
        }
    }

    private func searchCode(query: String) async -> String {
        do {
            let result = try system.run(
                "cd /Users/joe/brain && grep -rn '\(query.replacingOccurrences(of: "'", with: "'\\''"))' --include='*.py' --include='*.swift' --include='*.ts' --include='*.js' -l | head -10",
                timeout: 15, workingDirectory: "/Users/joe/brain")
            if result.stdout.isEmpty {
                return "No matches found for '\(query)'."
            }
            return "Found matches in:\n\(result.stdout)"
        } catch {
            return "Search error: \(error.localizedDescription)"
        }
    }

    private func copyCode(line: Int?) -> String {
        if let line = line {
            guard line > 0, line <= currentFileLines.count else {
                return "Line \(line) is out of range."
            }
            system.writeClipboard(currentFileLines[line - 1])
            return "Copied line \(line) to clipboard."
        }
        guard !currentFileLines.isEmpty else {
            return "No file is open."
        }
        system.writeClipboard(currentFileLines.joined(separator: "\n"))
        return "Copied entire file to clipboard."
    }

    private func insertLine(at n: Int, content: String) -> String {
        guard !currentFileLines.isEmpty else {
            return "No file is open."
        }
        let index = max(0, min(n - 1, currentFileLines.count))
        currentFileLines.insert(content, at: index)
        return "Inserted at line \(n): \(content)"
    }

    private func deleteLine(at n: Int) -> String {
        guard n > 0, n <= currentFileLines.count else {
            return "Line \(n) is out of range."
        }
        let removed = currentFileLines.remove(at: n - 1)
        return "Deleted line \(n): \(removed)"
    }

    private func replaceText(old: String, new: String) -> String {
        guard !currentFileLines.isEmpty else {
            return "No file is open."
        }
        var count = 0
        for i in 0..<currentFileLines.count {
            if currentFileLines[i].contains(old) {
                currentFileLines[i] = currentFileLines[i].replacingOccurrences(of: old, with: new)
                count += 1
            }
        }
        return count > 0 ? "Replaced \(count) occurrence\(count == 1 ? "" : "s") of '\(old)' with '\(new)'." : "'\(old)' not found."
    }

    private func gitStatus() async -> String {
        do {
            let result = try system.gitStatus(in: "/Users/joe/brain")
            return result.stdout.isEmpty ? "Working tree is clean." : "Changes:\n\(result.stdout)"
        } catch {
            return "Git status error: \(error.localizedDescription)"
        }
    }

    private func gitDiff() async -> String {
        do {
            let result = try system.run("cd /Users/joe/brain && git --no-pager diff --stat", timeout: 15, workingDirectory: "/Users/joe/brain")
            return result.stdout.isEmpty ? "No changes." : result.stdout
        } catch {
            return "Git diff error: \(error.localizedDescription)"
        }
    }

    private func createFile(name: String, language: String?) async -> String {
        let path = resolvePath(name)
        let ext = (name as NSString).pathExtension
        let lang = language ?? CodeSpeaker.detectLanguageFromFilename(name) ?? ext
        let template = codeTemplate(for: lang, filename: name)
        do {
            try system.writeFile(at: path, content: template)
            currentFilePath = path
            currentFileLines = template.components(separatedBy: "\n")
            return "Created \(name) with \(lang) template. \(currentFileLines.count) lines."
        } catch {
            return "Could not create file: \(error.localizedDescription)"
        }
    }

    // MARK: - Prompt Builders

    private func buildExplainPrompt(context: String?) -> String {
        var prompt = "Please explain this code in a clear, spoken format suitable for a blind developer using VoiceOver."
        if let ctx = context { prompt += " Context: \(ctx)" }
        if !currentFileLines.isEmpty, let path = currentFilePath {
            let sample = currentFileLines.prefix(30).joined(separator: "\n")
            prompt += "\n\nFile: \(path)\n```\n\(sample)\n```"
        }
        return prompt
    }

    private func buildFixPrompt(context: String?) -> String {
        var prompt = "Please identify and fix any errors in this code. Explain the fix clearly for a blind developer."
        if let ctx = context { prompt += " The error is: \(ctx)" }
        if !currentFileLines.isEmpty, let path = currentFilePath {
            let sample = currentFileLines.prefix(50).joined(separator: "\n")
            prompt += "\n\nFile: \(path)\n```\n\(sample)\n```"
        }
        return prompt
    }

    private func buildRefactorPrompt(context: String?) -> String {
        var prompt = "Please suggest refactoring for this code. Explain changes clearly for a blind developer."
        if let ctx = context { prompt += " Focus on: \(ctx)" }
        if !currentFileLines.isEmpty, let path = currentFilePath {
            let sample = currentFileLines.prefix(50).joined(separator: "\n")
            prompt += "\n\nFile: \(path)\n```\n\(sample)\n```"
        }
        return prompt
    }

    private func buildCreateFunctionPrompt(name: String, language: String?) -> String {
        let lang = language ?? "Python"
        return "Create a \(lang) function called \(name). Write clean, well-documented code. Explain the function signature and what it does, suitable for a blind developer."
    }

    // MARK: - Utilities

    private func resolvePath(_ path: String) -> String {
        if path.hasPrefix("/") || path.hasPrefix("~") {
            return (path as NSString).expandingTildeInPath
        }
        return "/Users/joe/brain/\(path)"
    }

    private func detectLanguageFromContext(_ text: String) -> String? {
        let langKeywords: [(String, String)] = [
            ("python", "Python"), ("swift", "Swift"), ("javascript", "JavaScript"),
            ("typescript", "TypeScript"), ("java", "Java"), ("rust", "Rust"),
            ("go", "Go"), ("ruby", "Ruby"), ("bash", "Bash"), ("shell", "Shell"),
        ]
        for (keyword, lang) in langKeywords where text.contains(keyword) {
            return lang
        }
        return nil
    }

    private func codeTemplate(for language: String, filename: String) -> String {
        let name = (filename as NSString).deletingPathExtension
        switch language.lowercased() {
        case "python", "py":
            return """
            #!/usr/bin/env python3
            \"\"\"
            \(name) - Created via BrainChat voice coding
            \"\"\"


            def main():
                pass


            if __name__ == "__main__":
                main()
            """
        case "swift":
            return """
            import Foundation

            // \(name) - Created via BrainChat voice coding

            func main() {
            }

            main()
            """
        case "javascript", "js":
            return """
            // \(name) - Created via BrainChat voice coding
            "use strict";

            function main() {
            }

            main();
            """
        case "typescript", "ts":
            return """
            // \(name) - Created via BrainChat voice coding

            function main(): void {
            }

            main();
            """
        default:
            return "// \(name) - Created via BrainChat voice coding\n"
        }
    }
}

// MARK: - String pattern matching helpers

private extension String {
    func firstMatch(of pattern: String) -> String? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive) else { return nil }
        let range = NSRange(startIndex..., in: self)
        guard let match = regex.firstMatch(in: self, range: range), match.numberOfRanges > 1 else { return nil }
        guard let captureRange = Range(match.range(at: 1), in: self) else { return nil }
        return String(self[captureRange])
    }

    func firstStringMatch(of pattern: String) -> String? {
        firstMatch(of: pattern)
    }

    func firstTwoMatches(of pattern: String) -> (Int, Int)? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive) else { return nil }
        let range = NSRange(startIndex..., in: self)
        guard let match = regex.firstMatch(in: self, range: range), match.numberOfRanges > 2 else { return nil }
        guard
            let r1 = Range(match.range(at: 1), in: self),
            let r2 = Range(match.range(at: 2), in: self),
            let n1 = Int(self[r1]),
            let n2 = Int(self[r2])
        else { return nil }
        return (n1, n2)
    }

    func firstReplacePair() -> (String, String)? {
        let pattern = #"replace ['"]?(.+?)['"]? with ['"]?(.+?)['"]?$"#
        guard let regex = try? NSRegularExpression(pattern: pattern, options: .caseInsensitive) else { return nil }
        let range = NSRange(startIndex..., in: self)
        guard let match = regex.firstMatch(in: self, range: range), match.numberOfRanges > 2 else { return nil }
        guard
            let r1 = Range(match.range(at: 1), in: self),
            let r2 = Range(match.range(at: 2), in: self)
        else { return nil }
        return (String(self[r1]), String(self[r2]))
    }
}
