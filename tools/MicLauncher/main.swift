import AVFoundation
import Foundation

let environment = ProcessInfo.processInfo.environment
let homeDirectory = NSHomeDirectory()
let repoDirectory = environment["MIC_LAUNCHER_REPO"] ?? "\(homeDirectory)/brain/agentic-brain"
let venvActivate = environment["MIC_LAUNCHER_VENV_ACTIVATE"] ?? "\(homeDirectory)/brain/venv/bin/activate"
let voiceChatScript = environment["MIC_LAUNCHER_SCRIPT"] ?? "\(repoDirectory)/karen_voice_chat.py"
let redisKey = environment["MIC_LAUNCHER_REDIS_KEY"] ?? "swarm:mic_permission:findings"

let isSmokeTest = CommandLine.arguments.contains("--smoke-test")
let isStatusOnly = CommandLine.arguments.contains("--status-only")

func shellQuote(_ value: String) -> String {
    "'" + value.replacingOccurrences(of: "'", with: "'\\''") + "'"
}

func pushRedis(_ message: String) {
    let redisCommand = """
    command -v redis-cli >/dev/null 2>&1 || exit 0
    redis-cli -a BrainRedis2026 RPUSH \(shellQuote(redisKey)) \(shellQuote(message)) >/dev/null 2>&1 || true
    """

    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/bin/bash")
    task.arguments = ["-lc", redisCommand]
    task.standardOutput = FileHandle.nullDevice
    task.standardError = FileHandle.nullDevice
    try? task.run()
    task.waitUntilExit()
}

func log(_ message: String) {
    print(message)
    fflush(stdout)
    pushRedis("MicLauncher: \(message)")
}

func authorizationDescription(_ status: AVAuthorizationStatus) -> String {
    switch status {
    case .notDetermined:
        return "notDetermined"
    case .restricted:
        return "restricted"
    case .denied:
        return "denied"
    case .authorized:
        return "authorized"
    @unknown default:
        return "unknown(\(status.rawValue))"
    }
}

func validateRequiredPaths() -> Bool {
    let fileManager = FileManager.default
    let requiredPaths = [
        ("repository", repoDirectory),
        ("virtual environment activate script", venvActivate),
        ("voice chat script", voiceChatScript),
    ]

    var isValid = true
    for (label, path) in requiredPaths where !fileManager.fileExists(atPath: path) {
        log("Missing \(label): \(path)")
        isValid = false
    }

    return isValid
}

func defaultLaunchCommand() -> String {
    if let override = environment["MIC_LAUNCHER_CHAT_COMMAND"], !override.isEmpty {
        return override
    }

    return "source \(shellQuote(venvActivate)) && exec python3 \(shellQuote(voiceChatScript))"
}

func launchVoiceChat() {
    let command = defaultLaunchCommand()

    if isSmokeTest {
        log("Smoke test complete. Launch command: \(command)")
        exit(0)
    }

    log("Launching voice chat in terminal context…")

    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/bin/bash")
    task.arguments = ["-lc", command]
    task.currentDirectoryURL = URL(fileURLWithPath: repoDirectory)
    task.environment = environment
    task.standardInput = FileHandle.standardInput
    task.standardOutput = FileHandle.standardOutput
    task.standardError = FileHandle.standardError

    do {
        try task.run()
        log("Voice chat started with PID \(task.processIdentifier)")
        task.waitUntilExit()
        log("Voice chat exited with status \(task.terminationStatus)")
        exit(task.terminationStatus)
    } catch {
        log("Failed to launch voice chat: \(error.localizedDescription)")
        exit(1)
    }
}

func waitForAuthorizationAndLaunch(deadline: Date = Date().addingTimeInterval(5)) {
    let status = AVCaptureDevice.authorizationStatus(for: .audio)
    if status == .authorized {
        log("Microphone authorization confirmed.")
        launchVoiceChat()
        return
    }

    if Date() >= deadline {
        log("Timed out waiting for macOS to report authorized status. Final status: \(authorizationDescription(status))")
        exit(1)
    }

    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
        waitForAuthorizationAndLaunch(deadline: deadline)
    }
}

func requestPermissionAndLaunch() {
    let currentStatus = AVCaptureDevice.authorizationStatus(for: .audio)
    log("Current microphone status: \(authorizationDescription(currentStatus))")

    if isStatusOnly {
        exit(0)
    }

    if isSmokeTest {
        launchVoiceChat()
        return
    }

    switch currentStatus {
    case .authorized:
        launchVoiceChat()

    case .notDetermined:
        log("Requesting microphone access…")
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            DispatchQueue.main.async {
                if granted {
                    log("Microphone access granted!")
                    waitForAuthorizationAndLaunch()
                } else {
                    log("Microphone access denied!")
                    exit(1)
                }
            }
        }

    case .denied:
        log("Microphone access denied. Re-enable it in System Settings > Privacy & Security > Microphone.")
        exit(1)

    case .restricted:
        log("Microphone access restricted by system policy.")
        exit(1)

    @unknown default:
        log("Unknown microphone authorization status: \(currentStatus.rawValue)")
        exit(1)
    }
}

guard validateRequiredPaths() else {
    exit(1)
}

requestPermissionAndLaunch()
RunLoop.main.run()
