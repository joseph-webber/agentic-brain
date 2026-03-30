import AVFoundation
import Foundation

// MARK: - Accessibility & Colors
struct Terminal {
    static let reset   = "\u{001B}[0m"
    static let bold    = "\u{001B}[1m"
    static let green   = "\u{001B}[32m"
    static let yellow  = "\u{001B}[33m"
    static let blue    = "\u{001B}[34m"
    static let magenta = "\u{001B}[35m"
    static let cyan    = "\u{001B}[36m"

    static func print(_ message: String, color: String = "", bold: Bool = false) {
        let prefix = bold ? Terminal.bold : ""
        Swift.print("\(prefix)\(color)\(message)\(Terminal.reset)")
    }

    static func speak(_ message: String) {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
        task.arguments = ["-v", "Karen (Premium)", "-r", "160", message]
        try? task.run()
        task.waitUntilExit()
    }
}

// MARK: - Banner
func showBanner() {
    let banner = """

    ╔═══════════════════════════════════════════════════════════╗
    ║  🎙️  KAREN VOICE CHAT  🎙️                                 ║
    ║  Swift Bridge to AI - Built for Joseph                   ║
    ╠═══════════════════════════════════════════════════════════╣
    ║  • Native macOS microphone access                        ║
    ║  • Whisper speech-to-text                                ║
    ║  • Multi-LLM routing (Ollama, Claude, GPT, Gemini, Grok) ║
    ║  • Cartesia TTS with Karen's voice                       ║
    ╚═══════════════════════════════════════════════════════════╝

    """
    Terminal.print(banner, color: Terminal.cyan)
}

// MARK: - Microphone Permission
func requestMicrophoneAccess() -> Bool {
    Terminal.print("🔐 Requesting microphone permission...", color: Terminal.yellow)

    let semaphore = DispatchSemaphore(value: 0)
    var granted = false

    AVCaptureDevice.requestAccess(for: .audio) { result in
        granted = result
        semaphore.signal()
    }

    semaphore.wait()

    if granted {
        Terminal.print("✅ Microphone access GRANTED!", color: Terminal.green, bold: true)
        Terminal.speak("Microphone ready!")
    } else {
        Terminal.print("❌ Microphone access DENIED", color: Terminal.magenta)
        Terminal.print("   → Go to System Settings > Privacy & Security > Microphone", color: Terminal.yellow)
        Terminal.speak("Microphone access denied. Please check system settings.")
    }

    return granted
}

// MARK: - Check Dependencies
func checkDependencies() -> Bool {
    Terminal.print("\n📦 Checking dependencies...", color: Terminal.blue)

    let fm = FileManager.default
    let checks: [(String, Bool)] = [
        ("Python venv",       fm.fileExists(atPath: (("~/brain/venv/bin/python3") as NSString).expandingTildeInPath)),
        ("Voice chat script", fm.fileExists(atPath: (("~/brain/agentic-brain/karen_voice_chat.py") as NSString).expandingTildeInPath)),
        ("Ollama",            Process.runCheck("/usr/bin/which", arguments: ["ollama"]))
    ]

    var allGood = true
    for (name, ok) in checks {
        if ok {
            Terminal.print("   ✅ \(name)", color: Terminal.green)
        } else {
            Terminal.print("   ⚠️  \(name) - not found (optional)", color: Terminal.yellow)
            // Only the venv and voice script are hard requirements
            if name != "Ollama" { allGood = false }
        }
    }

    return allGood
}

extension Process {
    /// Returns true when the process exits with status 0.
    static func runCheck(_ executable: String, arguments: [String]) -> Bool {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: executable)
        task.arguments = arguments
        task.standardOutput = FileHandle.nullDevice
        task.standardError  = FileHandle.nullDevice
        try? task.run()
        task.waitUntilExit()
        return task.terminationStatus == 0
    }
}

// MARK: - Launch Voice Chat
func launchVoiceChat() {
    Terminal.print("\n🚀 Launching Karen Voice Chat...", color: Terminal.cyan, bold: true)
    Terminal.print("   Press Ctrl+C to exit\n", color: Terminal.yellow)

    let task = Process()
    task.executableURL = URL(fileURLWithPath: "/bin/bash")
    task.arguments = ["-l", "-c", """
        cd ~/brain/agentic-brain && \
        source ~/brain/venv/bin/activate && \
        python3 karen_voice_chat.py
    """]

    task.standardInput  = FileHandle.standardInput
    task.standardOutput = FileHandle.standardOutput
    task.standardError  = FileHandle.standardError

    signal(SIGINT) { _ in
        Terminal.print("\n\n👋 Goodbye Joseph! Chat soon!", color: Terminal.cyan)
        exit(0)
    }

    do {
        try task.run()
        task.waitUntilExit()
    } catch {
        Terminal.print("❌ Launch error: \(error)", color: Terminal.magenta)
    }
}

// MARK: - Main
showBanner()

if requestMicrophoneAccess() {
    if checkDependencies() {
        launchVoiceChat()
    } else {
        Terminal.print("\n⚠️  Some required dependencies are missing.", color: Terminal.yellow)
        Terminal.print("   Ensure ~/brain/venv and karen_voice_chat.py exist.", color: Terminal.yellow)
        exit(1)
    }
} else {
    exit(1)
}
