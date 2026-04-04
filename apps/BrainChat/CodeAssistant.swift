import Foundation

enum AssistantRoute {
    case copilot
    case system
    case general
}

struct AssistantResponse {
    let text: String
    let route: AssistantRoute
    let duration: TimeInterval
    let codeBlocks: [(language: String?, code: String)]

    var hasCode: Bool { !codeBlocks.isEmpty }

    var spokenSummary: String {
        switch route {
        case .copilot:
            if codeBlocks.count == 1, let lang = codeBlocks.first?.language {
                return "Generated \(lang) code. \(previewLine)"
            }
            if codeBlocks.count > 1 {
                return "Generated \(codeBlocks.count) code blocks. \(previewLine)"
            }
            return previewLine
        case .system:
            return text.isEmpty ? "Done." : String(text.prefix(200))
        case .general:
            return String(text.prefix(300))
        }
    }

    private var previewLine: String {
        let plain = text.components(separatedBy: "\n")
            .filter { !$0.hasPrefix("```") }
            .first(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty }) ?? ""
        return String(plain.prefix(120))
    }
}

private let codingPatterns: [(pattern: String, weight: Int)] = [
    ("create a .* script", 10),
    ("write a .* function", 10),
    ("generate .* code", 10),
    ("refactor", 8),
    ("debug", 8),
    ("fix this .* error", 8),
    ("add a method", 8),
    ("implement", 8),
    ("python", 6), ("swift", 6), ("javascript", 6), ("typescript", 6),
    ("java", 5), ("kotlin", 5), ("rust", 5), ("go lang", 5),
    ("html", 5), ("css", 5), ("sql", 5), ("bash script", 6),
    ("function", 4), ("class", 4), ("variable", 3), ("loop", 3),
    ("api", 4), ("endpoint", 5), ("database", 4), ("query", 4),
    ("test", 4), ("unit test", 6), ("pytest", 7),
    ("regex", 5), ("parse", 4), ("json", 4),
    ("git", 4), ("commit", 4), ("branch", 4), ("merge", 4),
    ("read the file", 5), ("write to file", 5), ("create file", 5),
    ("open the file", 4),
]

private let systemPatterns: [(keyword: String, action: SystemAction)] = [
    ("run the tests", .runTests),
    ("run tests", .runTests),
    ("run pytest", .runTests),
    ("what's in my clipboard", .readClipboard),
    ("clipboard", .readClipboard),
    ("paste", .readClipboard),
    ("copy this", .writeClipboard),
    ("copy to clipboard", .writeClipboard),
    ("open safari", .openApp("Safari")),
    ("open terminal", .openApp("Terminal")),
    ("open finder", .openApp("Finder")),
    ("open xcode", .openApp("Xcode")),
    ("open music", .openApp("Music")),
    ("open slack", .openApp("Slack")),
    ("open teams", .openApp("Microsoft Teams")),
    ("git status", .gitStatus),
    ("what app is open", .frontmostApp),
    ("which app", .frontmostApp),
    ("read line", .voiceCoding),
    ("read lines", .voiceCoding),
    ("go to function", .voiceCoding),
    ("go to line", .voiceCoding),
    ("explain this", .voiceCoding),
    ("explain the code", .voiceCoding),
    ("fix this", .voiceCoding),
    ("fix the error", .voiceCoding),
    ("fix error", .voiceCoding),
    ("debug this", .voiceCoding),
    ("what's wrong", .voiceCoding),
    ("refactor", .voiceCoding),
    ("list functions", .voiceCoding),
    ("show functions", .voiceCoding),
    ("spell ", .voiceCoding),
    ("commit changes", .voiceCoding),
    ("commit with", .voiceCoding),
    ("save to ", .voiceCoding),
    ("save as ", .voiceCoding),
    ("open file", .voiceCoding),
    ("close file", .voiceCoding),
    ("delete line", .voiceCoding),
    ("insert at line", .voiceCoding),
    ("insert on line", .voiceCoding),
    ("copy line", .voiceCoding),
    ("replace ", .voiceCoding),
    ("create file", .voiceCoding),
    ("new file", .voiceCoding),
    ("create function", .voiceCoding),
    ("create a function", .voiceCoding),
    ("git diff", .voiceCoding),
    ("show diff", .voiceCoding),
    ("show changes", .voiceCoding),
    ("what changed", .voiceCoding),
    ("undo", .voiceCoding),
    ("repeat last", .voiceCoding),
    ("do it again", .voiceCoding),
    ("search for", .voiceCoding),
    ("search code", .voiceCoding),
    ("grep ", .voiceCoding),
]

enum SystemAction {
    case runTests
    case readClipboard
    case writeClipboard
    case openApp(String)
    case openURL(String)
    case gitStatus
    case frontmostApp
    case runShell(String)
    case voiceCoding
}

protocol CopilotExecuting {
    var isAvailable: Bool { get }
    var isBusy: Bool { get }
    func execute(prompt: String, completion: @escaping @Sendable (Result<CopilotResponse, Error>) -> Void)
    func cancelCurrent()
}

extension CopilotBridge: CopilotExecuting {}

protocol SystemCommandProviding {
    func speak(_ text: String, voice: String, rate: Int)
    func runTests(in directory: String?) throws -> CommandResult
    func readClipboard() -> String
    func writeClipboard(_ text: String)
    func openApp(_ appName: String) throws
    func openURL(_ urlString: String) throws
    func gitStatus(in directory: String?) throws -> CommandResult
    func frontmostApp() -> String
    func run(_ command: String, timeout: TimeInterval?, workingDirectory: String?) throws -> CommandResult
}

extension SystemCommands: SystemCommandProviding {}

final class CodeAssistant: @unchecked Sendable {
    static let shared = CodeAssistant()

    private struct GeneralAIHandlerBox {
        let run: (String, @escaping (String) -> Void) -> Void
    }

    private let copilot: CopilotExecuting
    private let system: SystemCommandProviding
    private var generalAIHandlerBox: GeneralAIHandlerBox?

    init(copilot: CopilotExecuting = CopilotBridge.shared, system: SystemCommandProviding = SystemCommands.shared) {
        self.copilot = copilot
        self.system = system
    }

    func setGeneralAIHandler(_ handler: @escaping (String, @escaping (String) -> Void) -> Void) {
        generalAIHandlerBox = GeneralAIHandlerBox(run: handler)
    }

    func detectRoute(for message: String) -> AssistantRoute {
        let lower = message.lowercased()
        for pattern in systemPatterns where lower.contains(pattern.keyword) {
            return .system
        }

        let score = codingPatterns.reduce(0) { partial, pattern in
            guard let regex = try? NSRegularExpression(pattern: pattern.pattern, options: .caseInsensitive) else {
                return partial
            }
            let range = NSRange(lower.startIndex..., in: lower)
            return regex.firstMatch(in: lower, range: range) == nil ? partial : partial + pattern.weight
        }

        return score >= 6 ? .copilot : .general
    }

    func process(_ message: String, completion: @escaping @Sendable (AssistantResponse) -> Void) {
        let route = detectRoute(for: message)
        let started = Date()
        switch route {
        case .copilot:
            handleCopilot(message, started: started, completion: completion)
        case .system:
            handleSystem(message, started: started, completion: completion)
        case .general:
            handleGeneral(message, started: started, completion: completion)
        }
    }

    func process(_ message: String) async -> AssistantResponse {
        await withCheckedContinuation { continuation in
            process(message) { continuation.resume(returning: $0) }
        }
    }

    var copilotAvailable: Bool { copilot.isAvailable }
    var isBusy: Bool { copilot.isBusy }
    func cancel() { copilot.cancelCurrent() }

    func routeLabel(for message: String) -> String {
        switch detectRoute(for: message) {
        case .copilot: return "Copilot CLI"
        case .system: return "System"
        case .general: return "AI Chat"
        }
    }

    private func handleCopilot(_ message: String, started: Date, completion: @escaping @Sendable (AssistantResponse) -> Void) {
        system.speak("Sending to Copilot", voice: "Karen (Premium)", rate: 155)
        copilot.execute(prompt: message) { [weak self] result in
            switch result {
            case .success(let response):
                let assistantResponse = AssistantResponse(text: response.text, route: .copilot, duration: response.duration, codeBlocks: response.codeBlocks)
                self?.system.speak(assistantResponse.spokenSummary, voice: "Karen (Premium)", rate: 155)
                completion(assistantResponse)
            case .failure(let error):
                let text = "Copilot error: \(error.localizedDescription)"
                self?.system.speak(text, voice: "Karen (Premium)", rate: 155)
                completion(AssistantResponse(text: text, route: .copilot, duration: Date().timeIntervalSince(started), codeBlocks: []))
            }
        }
    }

    private func handleSystem(_ message: String, started: Date, completion: @escaping @Sendable (AssistantResponse) -> Void) {
        let action = matchSystemAction(message.lowercased())

        // Route voice coding commands to VoiceCodingEngine
        if case .voiceCoding = action {
            let engine = VoiceCodingEngine.shared
            let voiceAction = engine.parse(message)
            system.speak(voiceAction.spokenConfirmation, voice: "Karen (Premium)", rate: 155)

            // For explain/fix/refactor, the result is an LLM prompt
            let needsLLM: Bool
            switch voiceAction {
            case .explainCode, .fixError, .refactor, .createFunction:
                needsLLM = true
            default:
                needsLLM = false
            }

            Task {
                let resultText = await engine.execute(voiceAction)
                if needsLLM, let handler = self.generalAIHandlerBox {
                    handler.run(resultText) { [weak self] response in
                        let spoken = String(response.prefix(400))
                        self?.system.speak(spoken, voice: "Karen (Premium)", rate: 155)
                        completion(AssistantResponse(text: response, route: .system, duration: Date().timeIntervalSince(started), codeBlocks: []))
                    }
                } else {
                    self.system.speak(String(resultText.prefix(300)), voice: "Karen (Premium)", rate: 155)
                    completion(AssistantResponse(text: resultText, route: .system, duration: Date().timeIntervalSince(started), codeBlocks: []))
                }
            }
            return
        }

        system.speak("Running command", voice: "Karen (Premium)", rate: 155)
        let resultText: String

        do {
            switch action {
            case .runTests:
                let brainDir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("brain").path
                let result = try system.runTests(in: brainDir)
                resultText = result.succeeded ? "Tests passed.\n\(result.stdout)" : "Tests failed.\n\(result.output)"
            case .readClipboard:
                let content = system.readClipboard()
                resultText = content.isEmpty ? "Clipboard is empty." : "Clipboard contains: \(String(content.prefix(500)))"
            case .writeClipboard:
                let text = extractContent(from: message, removing: ["copy this", "copy to clipboard"])
                system.writeClipboard(text)
                resultText = "Copied to clipboard."
            case .openApp(let name):
                try system.openApp(name)
                resultText = "Opened \(name)."
            case .openURL(let url):
                try system.openURL(url)
                resultText = "Opened URL."
            case .gitStatus:
                let brainDir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("brain").path
                let result = try system.gitStatus(in: brainDir)
                resultText = result.stdout.isEmpty ? "Working tree clean." : result.stdout
            case .frontmostApp:
                resultText = "The frontmost app is \(system.frontmostApp())."
            case .runShell(let command):
                resultText = try system.run(command, timeout: 15, workingDirectory: nil).output
            case .voiceCoding:
                // Already handled above, should not reach here
                resultText = "Voice coding command was not handled."
            }
        } catch {
            resultText = "Error: \(error.localizedDescription)"
        }

        system.speak(String(resultText.prefix(200)), voice: "Karen (Premium)", rate: 155)
        completion(AssistantResponse(text: resultText, route: .system, duration: Date().timeIntervalSince(started), codeBlocks: []))
    }

    private func handleGeneral(_ message: String, started: Date, completion: @escaping @Sendable (AssistantResponse) -> Void) {
        guard let handler = generalAIHandlerBox else {
            handleCopilot(message, started: started, completion: completion)
            return
        }

        system.speak("Thinking", voice: "Karen (Premium)", rate: 155)
        handler.run(message) { [weak self] responseText in
            self?.system.speak(String(responseText.prefix(300)), voice: "Karen (Premium)", rate: 155)
            completion(AssistantResponse(text: responseText, route: .general, duration: Date().timeIntervalSince(started), codeBlocks: []))
        }
    }

    private func matchSystemAction(_ lower: String) -> SystemAction {
        for pattern in systemPatterns where lower.contains(pattern.keyword) {
            return pattern.action
        }
        return .runShell(lower)
    }

    private func extractContent(from message: String, removing triggers: [String]) -> String {
        triggers.reduce(message) { partial, trigger in
            partial.replacingOccurrences(of: trigger, with: "", options: .caseInsensitive)
        }.trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
