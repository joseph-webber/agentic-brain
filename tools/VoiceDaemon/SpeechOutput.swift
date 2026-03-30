import Foundation

enum SpeechOutputError: Error, LocalizedError {
    case emptyText
    case speechCommandFailed(Int32)

    var errorDescription: String? {
        switch self {
        case .emptyText:
            return "No speech text was provided."
        case .speechCommandFailed(let code):
            return "Speech command failed with exit code \(code)."
        }
    }
}

final class SpeechOutput {
    private let voice: String
    private let rate: Int

    init(voice: String = "Karen", rate: Int = 160) {
        self.voice = voice
        self.rate = rate
    }

    func speak(_ text: String) throws {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw SpeechOutputError.emptyText
        }

        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
        task.arguments = ["-v", voice, "-r", String(rate), trimmed]

        try task.run()
        task.waitUntilExit()

        guard task.terminationStatus == 0 else {
            throw SpeechOutputError.speechCommandFailed(task.terminationStatus)
        }
    }
}
