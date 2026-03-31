import Foundation

/// Bridge to Python faster-whisper for best local STT.
final class FasterWhisperBridge: @unchecked Sendable {
    nonisolated(unsafe) static let shared = FasterWhisperBridge()

    private let scriptPath: String
    private let whisperModel: String

    init() {
        let home = FileManager.default.homeDirectoryForCurrentUser.path
        self.scriptPath = "\(home)/brain/agentic-brain/whisper_bridge.py"
        self.whisperModel = "tiny.en"
    }

    var isAvailable: Bool {
        guard FileManager.default.fileExists(atPath: scriptPath) else {
            return false
        }
        // Check if faster_whisper is importable
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        proc.arguments = ["-c", "import faster_whisper; print('ok')"]
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice
        do {
            try proc.run()
            proc.waitUntilExit()
            return proc.terminationStatus == 0
        } catch {
            return false
        }
    }

    func transcribe(audioURL: URL) async throws -> String {
        try await withCheckedThrowingContinuation { continuation in
            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = [scriptPath, "--model", whisperModel, audioURL.path]

            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe

            process.terminationHandler = { proc in
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                let output = String(data: data, encoding: .utf8)?
                    .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""

                if proc.terminationStatus == 0 {
                    continuation.resume(returning: output)
                } else {
                    continuation.resume(throwing: WhisperError.apiError(Int(proc.terminationStatus), output))
                }
            }

            do {
                try process.run()
            } catch {
                continuation.resume(throwing: error)
            }
        }
    }
}
