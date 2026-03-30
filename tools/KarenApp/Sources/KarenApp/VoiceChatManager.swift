import AVFoundation
import AppKit
import Combine
import Foundation
import SwiftUI

@MainActor
final class VoiceChatManager: ObservableObject {
    enum ChatStatus: Equatable {
        case idle
        case requestingPermission
        case ready
        case recording
        case thinking
        case speaking
        case error
        case stopped

        var title: String {
            switch self {
            case .idle: return "Ready to Start"
            case .requestingPermission: return "Waiting for Permission"
            case .ready: return "Listening Standby"
            case .recording: return "Recording"
            case .thinking: return "Thinking"
            case .speaking: return "Speaking"
            case .error: return "Needs Attention"
            case .stopped: return "Stopped"
            }
        }

        var color: Color {
            switch self {
            case .idle, .stopped: return .secondary
            case .requestingPermission: return .yellow
            case .ready: return .green
            case .recording: return .red
            case .thinking: return .orange
            case .speaking: return .blue
            case .error: return .pink
            }
        }

        var waveHeights: [CGFloat] {
            switch self {
            case .idle, .stopped:
                return [20, 28, 18, 24, 18, 26]
            case .requestingPermission:
                return [36, 58, 42, 62, 40, 54]
            case .ready:
                return [30, 62, 78, 62, 30, 48]
            case .recording:
                return [52, 96, 76, 104, 80, 92]
            case .thinking:
                return [46, 56, 72, 60, 74, 58]
            case .speaking:
                return [64, 88, 54, 94, 68, 82]
            case .error:
                return [28, 82, 34, 82, 30, 68]
            }
        }

        var accessibilityDescription: String {
            switch self {
            case .idle: return "Karen is ready but not running yet."
            case .requestingPermission: return "The app is waiting for your answer to the microphone permission dialog."
            case .ready: return "Karen is running and ready for the next thing you say."
            case .recording: return "Karen is currently recording your voice."
            case .thinking: return "Karen is processing what you said."
            case .speaking: return "Karen is speaking a reply out loud."
            case .error: return "Karen needs attention because something went wrong."
            case .stopped: return "Karen is not running now."
            }
        }
    }

    @Published var status: ChatStatus = .idle
    @Published var detailText = "Karen will ask for microphone access and then launch the Python voice chat in the background."
    @Published var permissionSummary = "Not checked yet"
    @Published var latestEvent = "No events yet."
    @Published var isRunning = false

    private var process: Process?
    private var outputPipe: Pipe?
    private var outputBuffer = Data()
    private var terminationObserver: NSObjectProtocol?

    init() {
        terminationObserver = NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.stopChat(clearStatus: false)
            }
        }
    }

    deinit {
        if let terminationObserver {
            NotificationCenter.default.removeObserver(terminationObserver)
        }
    }

    func refreshAuthorizationState() {
        permissionSummary = authorizationSummary(AVCaptureDevice.authorizationStatus(for: .audio))
    }

    func primaryAction() {
        if isRunning {
            stopChat()
        } else {
            Task {
                await startChat()
            }
        }
    }

    func openMicrophoneSettings() {
        let urls = [
            "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_Microphone",
            "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone"
        ]

        for rawURL in urls {
            if let url = URL(string: rawURL), NSWorkspace.shared.open(url) {
                updateEvent("Opened System Settings for microphone privacy.")
                return
            }
        }

        updateStatus(.error, detail: "Unable to open microphone privacy settings.")
    }

    private func startChat() async {
        refreshAuthorizationState()

        guard validatePaths() else {
            return
        }

        let granted = await ensureMicrophonePermission()
        guard granted else {
            updateStatus(.error, detail: "Microphone access is required before Karen can start.")
            return
        }

        launchPythonChat()
    }

    private func validatePaths() -> Bool {
        let fileManager = FileManager.default
        let requiredPaths = [
            ("repository", KarenAppConstants.repoDirectory),
            ("virtual environment activation script", KarenAppConstants.virtualEnvActivatePath),
            ("Karen voice chat script", KarenAppConstants.voiceChatScriptPath)
        ]

        let missing = requiredPaths.filter { !fileManager.fileExists(atPath: $0.1) }
        guard missing.isEmpty else {
            let summary = missing.map { "\($0.0): \($0.1)" }.joined(separator: "; ")
            updateStatus(.error, detail: "Missing required files. \(summary)")
            return false
        }

        return true
    }

    private func ensureMicrophonePermission() async -> Bool {
        let current = AVCaptureDevice.authorizationStatus(for: .audio)
        permissionSummary = authorizationSummary(current)

        switch current {
        case .authorized:
            updateStatus(.ready, detail: "Microphone permission is already granted.")
            return true
        case .notDetermined:
            updateStatus(.requestingPermission, detail: "macOS should now show the microphone permission dialog.")
            let granted = await withCheckedContinuation { continuation in
                AVCaptureDevice.requestAccess(for: .audio) { granted in
                    continuation.resume(returning: granted)
                }
            }
            refreshAuthorizationState()
            if granted {
                updateStatus(.ready, detail: "Microphone access granted. Starting Karen now.")
            }
            return granted
        case .denied:
            updateStatus(.error, detail: "Microphone permission was denied. Open System Settings and enable Karen Voice Chat under Microphone.")
            return false
        case .restricted:
            updateStatus(.error, detail: "Microphone access is restricted by system policy.")
            return false
        @unknown default:
            updateStatus(.error, detail: "Unknown microphone permission state: \(current.rawValue)")
            return false
        }
    }

    private func launchPythonChat() {
        stopChat(clearStatus: false)

        let task = Process()
        let pipe = Pipe()
        let command = chatCommand()

        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["-lc", command]
        task.currentDirectoryURL = URL(fileURLWithPath: KarenAppConstants.repoDirectory)
        task.standardOutput = pipe
        task.standardError = pipe

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        environment["KAREN_APP_BUNDLE_ID"] = KarenAppConstants.bundleIdentifier
        task.environment = environment

        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            Task { @MainActor in
                self?.consumeOutput(data)
            }
        }

        task.terminationHandler = { [weak self] process in
            Task { @MainActor in
                self?.outputPipe?.fileHandleForReading.readabilityHandler = nil
                self?.outputPipe = nil
                self?.process = nil
                self?.isRunning = false
                if process.terminationStatus == 0 {
                    self?.updateStatus(.stopped, detail: "Karen finished cleanly.")
                } else {
                    self?.updateStatus(.error, detail: "Karen stopped with exit code \(process.terminationStatus).")
                }
            }
        }

        do {
            try task.run()
            process = task
            outputPipe = pipe
            outputBuffer.removeAll(keepingCapacity: true)
            isRunning = true
            updateStatus(.ready, detail: "Karen is running in the background and waiting for speech.")
            updateEvent("Launched Python voice chat with PID \(task.processIdentifier).")
            reportToRedis("KarenApp started voice chat. pid=\(task.processIdentifier)")
        } catch {
            updateStatus(.error, detail: "Failed to launch Karen: \(error.localizedDescription)")
        }
    }

    func stopChat(clearStatus: Bool = false) {
        guard let process else {
            if clearStatus {
                updateStatus(.stopped, detail: "Karen is not running.")
            }
            return
        }

        outputPipe?.fileHandleForReading.readabilityHandler = nil
        outputPipe = nil

        if process.isRunning {
            process.interrupt()
            DispatchQueue.global().asyncAfter(deadline: .now() + 1.0) {
                if process.isRunning {
                    process.terminate()
                }
            }
        }

        self.process = nil
        isRunning = false
        if clearStatus || status != .error {
            updateStatus(.stopped, detail: "Karen was stopped.")
        }
        updateEvent("Stopped Python voice chat.")
        reportToRedis("KarenApp stopped voice chat.")
    }

    private func chatCommand() -> String {
        if let override = ProcessInfo.processInfo.environment["KAREN_APP_CHAT_COMMAND"], !override.isEmpty {
            return override
        }

        return "source \(shellQuoted(KarenAppConstants.virtualEnvActivatePath)) && exec python3 \(shellQuoted(KarenAppConstants.voiceChatScriptPath))"
    }

    private func consumeOutput(_ data: Data) {
        outputBuffer.append(data)
        while let newlineRange = outputBuffer.firstRange(of: Data([0x0A])) {
            let lineData = outputBuffer.subdata(in: outputBuffer.startIndex..<newlineRange.startIndex)
            outputBuffer.removeSubrange(outputBuffer.startIndex...newlineRange.startIndex)
            guard let line = String(data: lineData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines), !line.isEmpty else {
                continue
            }
            handleOutputLine(line)
        }
    }

    private func handleOutputLine(_ line: String) {
        updateEvent(line)

        if line.contains("🎤 Recording") {
            updateStatus(.recording, detail: "Karen is recording your voice now.")
        } else if line.contains("🔄 Transcribing") || line.contains("🤔 Karen thinking") {
            updateStatus(.thinking, detail: "Karen is working out what you said.")
        } else if line.contains("🗣️ Karen:") {
            updateStatus(.speaking, detail: line.replacingOccurrences(of: "🗣️ Karen:", with: "Karen says:"))
        } else if line.contains("Press Ctrl+C") || line.contains("Ready to chat") || line.contains("Using sox for recording") {
            updateStatus(.ready, detail: "Karen is ready and listening for the next prompt.")
        } else if line.contains("(no speech detected)") {
            updateStatus(.ready, detail: "No speech detected. Karen is ready to try again.")
        } else if line.localizedCaseInsensitiveContains("error") {
            updateStatus(.error, detail: line)
        }
    }

    private func authorizationSummary(_ status: AVAuthorizationStatus) -> String {
        switch status {
        case .authorized:
            return "granted"
        case .notDetermined:
            return "not requested yet"
        case .denied:
            return "denied"
        case .restricted:
            return "restricted"
        @unknown default:
            return "unknown"
        }
    }

    private func shellQuoted(_ value: String) -> String {
        "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
    }

    private func updateStatus(_ newStatus: ChatStatus, detail: String) {
        status = newStatus
        detailText = detail
        latestEvent = detail
    }

    private func updateEvent(_ message: String) {
        latestEvent = message
    }

    private func reportToRedis(_ message: String) {
        let command = "command -v redis-cli >/dev/null 2>&1 || exit 0; redis-cli -a BrainRedis2026 RPUSH \(shellQuoted(KarenAppConstants.redisListKey)) \(shellQuoted(message)) >/dev/null 2>&1 || true"
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/bash")
        task.arguments = ["-lc", command]
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        try? task.run()
    }
}
