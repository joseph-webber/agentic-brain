import AppKit
import XCTest
@testable import BrainChatLib

final class E2EScenarioRecorder {
    let name: String
    let scenarioDirectory: URL
    let workspaceDirectory: URL

    private(set) var logs: [String] = []
    private(set) var spokenLines: [String] = []
    private(set) var transcriptLines: [String] = []

    init(name: String) {
        self.name = name

        let root = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
            .appendingPathComponent("Tests", isDirectory: true)
            .appendingPathComponent("Artifacts", isDirectory: true)
        let scenarioDirectory = root.appendingPathComponent(Self.slug(from: name), isDirectory: true)
        let workspaceDirectory = scenarioDirectory.appendingPathComponent("workspace", isDirectory: true)

        self.scenarioDirectory = scenarioDirectory
        self.workspaceDirectory = workspaceDirectory

        try? FileManager.default.createDirectory(at: workspaceDirectory, withIntermediateDirectories: true)
    }

    func step(_ text: String) {
        logs.append("STEP: \(text)")
    }

    func speak(_ text: String) {
        spokenLines.append(text)
        transcriptLines.append("Karen: \(text)")
        logs.append("SPEAK: \(text)")
    }

    func hearUser(_ text: String) {
        transcriptLines.append("Joseph: \(text)")
        logs.append("USER: \(text)")
    }

    func note(_ text: String) {
        logs.append("INFO: \(text)")
    }

    func finalize(failed: Bool) {
        writeLogFile()
        synthesizeAudioTranscript()
        if failed {
            captureFailureScreenshot()
        }
    }

    private func writeLogFile() {
        let logURL = scenarioDirectory.appendingPathComponent("session.log")
        let content = (logs + ["", "TRANSCRIPT"] + transcriptLines).joined(separator: "\n")
        try? content.write(to: logURL, atomically: true, encoding: .utf8)
    }

    private func synthesizeAudioTranscript() {
        let audioURL = scenarioDirectory.appendingPathComponent("session.aiff")
        let transcript = transcriptLines.joined(separator: ". ")
        guard !transcript.isEmpty else { return }

        if runSay(arguments: ["-o", audioURL.path, transcript]) {
            return
        }

        let fallbackURL = scenarioDirectory.appendingPathComponent("session-audio-fallback.txt")
        try? transcript.write(to: fallbackURL, atomically: true, encoding: .utf8)
    }

    private func runSay(arguments: [String]) -> Bool {
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/say")
        process.arguments = arguments
        do {
            try process.run()
            process.waitUntilExit()
            return process.terminationStatus == 0
        } catch {
            return false
        }
    }

    private func captureFailureScreenshot() {
        let image = NSImage(size: NSSize(width: 1280, height: 720))
        image.lockFocus()

        NSColor.white.setFill()
        NSBezierPath(rect: NSRect(x: 0, y: 0, width: 1280, height: 720)).fill()

        let titleAttributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.boldSystemFont(ofSize: 28),
            .foregroundColor: NSColor.black,
        ]
        let bodyAttributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 16, weight: .regular),
            .foregroundColor: NSColor.darkGray,
        ]

        NSString(string: "E2E Failure: \(name)").draw(
            at: NSPoint(x: 40, y: 660),
            withAttributes: titleAttributes
        )

        let body = (logs + ["", "Transcript"] + transcriptLines).joined(separator: "\n")
        NSString(string: body).draw(
            in: NSRect(x: 40, y: 40, width: 1200, height: 580),
            withAttributes: bodyAttributes
        )

        image.unlockFocus()

        guard
            let tiffData = image.tiffRepresentation,
            let bitmap = NSBitmapImageRep(data: tiffData),
            let pngData = bitmap.representation(using: .png, properties: [:])
        else {
            return
        }

        let screenshotURL = scenarioDirectory.appendingPathComponent("failure.png")
        try? pngData.write(to: screenshotURL)
    }

    private static func slug(from text: String) -> String {
        text.lowercased()
            .replacingOccurrences(of: "[^a-z0-9]+", with: "-", options: .regularExpression)
            .trimmingCharacters(in: CharacterSet(charactersIn: "-"))
    }
}

class E2EOrchestratedTestCase: XCTestCase {
    private var activeScenario: E2EScenarioRecorder?

    @discardableResult
    func beginScenario(named name: String) -> E2EScenarioRecorder {
        let recorder = E2EScenarioRecorder(name: name)
        activeScenario = recorder
        return recorder
    }

    override func tearDown() {
        activeScenario?.finalize(failed: (testRun?.failureCount ?? 0) > 0)
        activeScenario = nil
        super.tearDown()
    }
}

enum E2ELLMProvider: String, CaseIterable {
    case claude = "Claude"
    case gpt = "GPT"
    case ollama = "Ollama"
    case copilot = "Copilot"
}

struct E2EHistoryEntry: Equatable {
    let speaker: String
    let text: String
}

final class SimulatedBrainChatApp {
    private let recorder: E2EScenarioRecorder

    private(set) var launched = false
    private(set) var displayedTranscript = ""
    private(set) var isThinking = false
    private(set) var history: [E2EHistoryEntry] = []
    private(set) var provider: E2ELLMProvider = .copilot
    private(set) var yoloModeEnabled = false
    private(set) var actionAnnouncements: [String] = []

    init(recorder: E2EScenarioRecorder) {
        self.recorder = recorder
    }

    func launch() {
        recorder.step("App launches")
        launched = true
        speak("G'day Joseph")
    }

    func pressSpaceAndSpeak(_ text: String) {
        recorder.step("User presses space and speaks: \(text)")
        displayedTranscript = text
        recorder.hearUser(text)
        recorder.step("Transcription appears")
        history.append(E2EHistoryEntry(speaker: "Joseph", text: text))
    }

    func showThinking() {
        recorder.step("AI processes and shows thinking state")
        isThinking = true
    }

    func deliverAssistantResponse(_ text: String) {
        isThinking = false
        speak(text)
        history.append(E2EHistoryEntry(speaker: "Karen", text: text))
        recorder.step("Message appears in conversation history")
    }

    func switchProvider(to provider: E2ELLMProvider) {
        self.provider = provider
        recorder.step("Switched LLM provider to \(provider.rawValue)")
    }

    func routeCodingPrompt(_ prompt: String) -> TestAssistantRoute {
        let route = RouteDetector().detectRoute(for: prompt)
        recorder.note("Route for '\(prompt)' resolved to \(route.rawValue)")
        return route
    }

    func generateCode(for prompt: String) -> String {
        recorder.step("Code generated by \(provider.rawValue)")
        if prompt.lowercased().contains("python") && prompt.lowercased().contains("hello world") {
            return "print(\"Hello, World!\")\n"
        }

        if prompt.lowercased().contains("rest api") {
            return "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get(\"/health\")\ndef health():\n    return {\"status\": \"ok\"}\n"
        }

        return "print(\"Generated by \(provider.rawValue)\")\n"
    }

    func readCodeAloud(_ code: String) {
        recorder.step("Karen reads generated code aloud")
        speak("Here is the code. \(code.replacingOccurrences(of: "\n", with: " "))")
    }

    func saveCode(_ code: String, named fileName: String) throws -> URL {
        let fileURL = recorder.workspaceDirectory.appendingPathComponent(fileName)
        try code.write(to: fileURL, atomically: true, encoding: .utf8)
        recorder.step("Code saved to file \(fileName)")
        return fileURL
    }

    @discardableResult
    func runPythonFile(_ fileURL: URL) throws -> String {
        recorder.step("User says run it")
        pressSpaceAndSpeak("Run it")

        let process = Process()
        let outputPipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        process.arguments = [fileURL.path]
        process.standardOutput = outputPipe
        process.standardError = outputPipe
        try process.run()
        process.waitUntilExit()

        let output = String(data: outputPipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        recorder.step("Execution completed")
        speak("Output: \(output)")
        return output
    }

    func enableYoloMode() {
        recorder.step("User requests YOLO mode")
        yoloModeEnabled = true
        speak("YOLO mode enabled. I’ll announce every action.")
    }

    func disableYoloMode() {
        recorder.step("User disables YOLO mode")
        yoloModeEnabled = false
        speak("YOLO mode off.")
    }

    @discardableResult
    func createRestAPIProject() throws -> [URL] {
        precondition(yoloModeEnabled, "YOLO mode must be enabled before autonomous actions run.")

        let apiRoot = recorder.workspaceDirectory.appendingPathComponent("rest-api", isDirectory: true)
        let appDirectory = apiRoot.appendingPathComponent("app", isDirectory: true)
        try FileManager.default.createDirectory(at: appDirectory, withIntermediateDirectories: true)

        var createdFiles: [URL] = []

        let steps: [(String, URL, String)] = [
            (
                "Creating FastAPI entrypoint",
                apiRoot.appendingPathComponent("main.py"),
                "from app.routes import router\nfrom fastapi import FastAPI\n\napp = FastAPI(title=\"BrainChat YOLO API\")\napp.include_router(router)\n"
            ),
            (
                "Creating API routes",
                appDirectory.appendingPathComponent("routes.py"),
                "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n@router.get(\"/health\")\ndef health():\n    return {\"status\": \"ok\"}\n"
            ),
            (
                "Saving dependencies",
                apiRoot.appendingPathComponent("requirements.txt"),
                "fastapi==0.115.0\nuvicorn==0.30.6\n"
            ),
        ]

        for (announcement, fileURL, content) in steps {
            actionAnnouncements.append(announcement)
            recorder.step(announcement)
            speak(announcement)
            try content.write(to: fileURL, atomically: true, encoding: .utf8)
            createdFiles.append(fileURL)
        }

        return createdFiles
    }

    func providerResponse(to prompt: String) -> String {
        let response = "\(provider.rawValue) handled: \(prompt)"
        showThinking()
        deliverAssistantResponse(response)
        return response
    }

    private func speak(_ text: String) {
        recorder.speak(text)
    }
}
