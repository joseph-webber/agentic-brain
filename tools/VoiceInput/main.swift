import AppKit
import AVFoundation
import Speech

// MARK: - Sound feedback

/// Play a named system sound and let the RunLoop spin so the sound has time to play.
func playSound(_ name: String, wait seconds: TimeInterval = 0.3) {
    NSSound(named: NSSound.Name(name))?.play()
    RunLoop.main.run(until: Date(timeIntervalSinceNow: seconds))
}

// MARK: - Voice Capture Engine

final class VoiceCapture: NSObject {

    private let recognizer: SFSpeechRecognizer
    private let engine   = AVAudioEngine()
    private var request  : SFSpeechAudioBufferRecognitionRequest?
    private var task     : SFSpeechRecognitionTask?

    private var lastText     = ""
    private var silenceTimer : Timer?
    private var hardTimer    : Timer?
    private var finished     = false

    let timeout: TimeInterval

    init(timeout: TimeInterval) {
        self.timeout    = timeout
        // Prefer Australian English (for Joseph); fall back to US English
        self.recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))
                       ?? SFSpeechRecognizer(locale: Locale(identifier: "en-US"))!
        super.init()
    }

    // ── Step 1: microphone permission ─────────────────────────────────────

    func start() {
        let micStatus    = AVCaptureDevice.authorizationStatus(for: .audio)
        let speechStatus = SFSpeechRecognizer.authorizationStatus()

        fputs("VoiceInput: mic=\(micStatus.rawValue) speech=\(speechStatus.rawValue)\n", stderr)
        fputs("▶  Requesting microphone access…\n", stderr)

        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self else { return }
                if granted {
                    self.requestSpeechAuth()
                } else {
                    fputs("""
                    ✖  Microphone access denied.

                       To fix (two options):

                       A. System Settings › Privacy & Security › Microphone
                          ↳ Toggle 'VoiceInput' to ON

                       B. From Terminal.app (Dock/Spotlight — NOT Copilot CLI):
                          cd ~/brain/agentic-brain/tools/VoiceInput && ./setup.sh

                       Note: Copilot CLI runs via SSH. macOS blocks TCC dialogs
                       for SSH sessions. Use Terminal.app for first-time setup.

                    """, stderr)
                    playSound("Basso")
                    exit(1)
                }
            }
        }
    }

    // ── Step 2: speech-recognition permission ─────────────────────────────

    private func requestSpeechAuth() {
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                guard let self else { return }
                switch status {
                case .authorized:
                    self.beginListening()
                case .denied:
                    fputs("✖  Speech recognition denied.\n   Fix: System Settings › Privacy & Security › Speech Recognition\n", stderr)
                    playSound("Basso")
                    exit(1)
                case .restricted:
                    fputs("✖  Speech recognition restricted on this device.\n", stderr)
                    playSound("Basso")
                    exit(1)
                case .notDetermined:
                    fputs("✖  Speech recognition permission not yet determined.\n", stderr)
                    exit(1)
                @unknown default:
                    fputs("✖  Unknown speech-recognition authorization status.\n", stderr)
                    exit(1)
                }
            }
        }
    }

    // ── Step 3: audio engine + SFSpeechRecognizer ─────────────────────────

    private func beginListening() {
        guard recognizer.isAvailable else {
            fputs("✖  Speech recognizer is not available right now.\n", stderr)
            playSound("Basso")
            exit(1)
        }

        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        req.taskHint = .dictation

        // Prefer on-device (fast, private, works offline)
        if recognizer.supportsOnDeviceRecognition {
            req.requiresOnDeviceRecognition = true
            fputs("ℹ  On-device recognition active.\n", stderr)
        } else {
            fputs("ℹ  Server-based recognition active.\n", stderr)
        }
        self.request = req

        // Recognition callback — always called on the main queue by the OS
        task = recognizer.recognitionTask(with: req) { [weak self] result, error in
            DispatchQueue.main.async {
                self?.handleResult(result, error: error)
            }
        }

        // Tap the default input (e.g. AirPods Max)
        let inputNode = engine.inputNode
        let format    = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            // append is thread-safe per Apple's documentation
            self?.request?.append(buffer)
        }

        do {
            engine.prepare()
            try engine.start()
        } catch {
            fputs("✖  Audio engine failed to start: \(error.localizedDescription)\n", stderr)
            playSound("Basso")
            exit(1)
        }

        // Tink = ready
        playSound("Tink", wait: 0.2)
        fputs("✔  Listening… (timeout: \(Int(timeout))s — speak now)\n", stderr)

        // Hard ceiling: exit even if speech never stops
        hardTimer = Timer.scheduledTimer(withTimeInterval: timeout, repeats: false) { [weak self] _ in
            fputs("⏱  Hard timeout reached.\n", stderr)
            self?.finish()
        }
    }

    // ── Recognition result handler ────────────────────────────────────────

    private func handleResult(_ result: SFSpeechRecognitionResult?, error: Error?) {
        if let r = result {
            let text = r.bestTranscription.formattedString
            if !text.isEmpty, text != lastText {
                lastText = text
                fputs("  ↳ \(text)\n", stderr)

                // Reset 1.5 s silence detector on every new word
                silenceTimer?.invalidate()
                silenceTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: false) { [weak self] _ in
                    self?.finish()
                }
            }
            if r.isFinal { finish() }
        }

        if let e = error {
            let code = (e as NSError).code
            // Expected / benign codes:
            //   1110 = no speech detected in first utterance window
            //   216  = recognition cancelled (we cancelled it ourselves)
            //   301  = recognition cancelled
            if ![216, 301, 1110].contains(code) {
                fputs("  recognizer error (\(code)): \(e.localizedDescription)\n", stderr)
            }
            if code == 1110 { finish() }
        }
    }

    // ── Tear-down and exit ────────────────────────────────────────────────

    func finish() {
        guard !finished else { return }
        finished = true

        silenceTimer?.invalidate()
        hardTimer?.invalidate()

        if engine.isRunning { engine.stop() }
        engine.inputNode.removeTap(onBus: 0)
        request?.endAudio()
        task?.cancel()

        if lastText.isEmpty {
            fputs("✖  No speech captured.\n", stderr)
            playSound("Basso", wait: 0.4)
            exit(2)   // exit 2 = caller knows "no speech"
        } else {
            fputs("✔  Transcription: \(lastText)\n", stderr)
            playSound("Pop", wait: 0.3)
            print(lastText)   // ← stdout only (clean for shell capture)
            exit(0)
        }
    }
}

// MARK: - NSApplicationDelegate

final class AppDelegate: NSObject, NSApplicationDelegate {
    var capture: VoiceCapture?

    func applicationDidFinishLaunching(_ notification: Notification) {
        let seconds = Double(CommandLine.arguments.dropFirst().first ?? "") ?? 10.0

        // If either permission is undecided, run as a regular foreground app
        // so macOS can show the TCC permission dialogs. Once permissions are
        // set (on subsequent runs), switch to accessory mode (no Dock icon).
        let micAuth    = AVCaptureDevice.authorizationStatus(for: .audio)
        let speechAuth = SFSpeechRecognizer.authorizationStatus()
        let needsDialogs = (micAuth == .notDetermined || speechAuth == .notDetermined)

        if needsDialogs {
            fputs("ℹ  First run — activating as foreground app for permission dialogs.\n", stderr)
            NSApp.setActivationPolicy(.regular)
            NSApp.activate(ignoringOtherApps: true)
        } else {
            NSApp.setActivationPolicy(.accessory)
        }

        capture = VoiceCapture(timeout: seconds)
        capture?.start()
    }
}

// MARK: - Entry point

let app = NSApplication.shared
// Activation policy is set dynamically in AppDelegate.applicationDidFinishLaunching
// based on whether TCC permissions have already been granted.
let appDelegate = AppDelegate()
app.delegate = appDelegate
app.run()
