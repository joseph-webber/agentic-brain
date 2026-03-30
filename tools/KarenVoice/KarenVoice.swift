import AppKit
import AVFoundation
import Speech
import Foundation

final class SoundPlayer {
    static func play(_ name: String) {
        if let sound = NSSound(named: NSSound.Name(name)) {
            sound.play()
            return
        }

        let path = "/System/Library/Sounds/\(name).aiff"
        guard FileManager.default.fileExists(atPath: path) else { return }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/afplay")
        process.arguments = [path]
        try? process.run()
    }
}

final class KarenVoiceApp: NSObject, NSApplicationDelegate, SFSpeechRecognizerDelegate {
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))
    private let audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var monitorTimer: Timer?
    private var finalizeTimer: Timer?
    private var window: NSWindow?
    private var statusLabel: NSTextField?

    private var finalTranscript = ""
    private var startTime = Date()
    private var lastVoiceActivity = Date()
    private var lastTranscriptActivity = Date()
    private var shutdownRequested = false
    private var didStartListening = false
    private var exitCode: Int32 = 1

    private let silenceTimeout: TimeInterval
    private let maxDuration: TimeInterval
    private let audioLevelThreshold: Float = 0.0035

    init(silenceTimeout: TimeInterval, maxDuration: TimeInterval) {
        self.silenceTimeout = silenceTimeout
        self.maxDuration = maxDuration
        super.init()
        recognizer?.delegate = self
    }

    var currentExitCode: Int32 { exitCode }

    func applicationDidFinishLaunching(_ notification: Notification) {
        buildWindow()
        NSApp.activate(ignoringOtherApps: true)
        updateStatus("KarenVoice launched. Preparing permission checks…")
        fputs("KarenVoice launched\n", stderr)

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            self.requestPermissionsAndStart()
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }

    private func buildWindow() {
        let rect = NSRect(x: 0, y: 0, width: 520, height: 170)
        let win = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        win.title = "KarenVoice"
        win.center()
        win.isReleasedWhenClosed = false

        let content = NSView(frame: rect)
        win.contentView = content

        let title = NSTextField(labelWithString: "Karen Voice Dictation")
        title.font = .boldSystemFont(ofSize: 22)
        title.alignment = .center
        title.frame = NSRect(x: 20, y: 110, width: 480, height: 28)
        content.addSubview(title)

        let status = NSTextField(labelWithString: "Starting…")
        status.font = .systemFont(ofSize: 14)
        status.alignment = .center
        status.maximumNumberOfLines = 3
        status.frame = NSRect(x: 30, y: 50, width: 460, height: 42)
        content.addSubview(status)
        statusLabel = status

        let hint = NSTextField(labelWithString: "Allow microphone and speech recognition when macOS asks.")
        hint.font = .systemFont(ofSize: 12)
        hint.alignment = .center
        hint.textColor = .secondaryLabelColor
        hint.frame = NSRect(x: 20, y: 22, width: 480, height: 20)
        content.addSubview(hint)

        window = win
        win.makeKeyAndOrderFront(nil)
    }

    private func updateStatus(_ text: String) {
        DispatchQueue.main.async {
            self.statusLabel?.stringValue = text
        }
        fputs("\(text)\n", stderr)
    }

    private func requestPermissionsAndStart() {
        guard let recognizer else {
            fail("Speech recognizer is unavailable for locale en-AU")
            return
        }

        guard recognizer.isAvailable else {
            fail("Speech recognizer is currently unavailable")
            return
        }

        requestMicrophonePermission { [weak self] micGranted in
            guard let self else { return }
            guard micGranted else {
                self.fail("Microphone permission denied or unavailable")
                return
            }

            self.requestSpeechPermission { speechGranted in
                guard speechGranted else {
                    self.fail("Speech recognition permission denied or unavailable")
                    return
                }

                do {
                    try self.startListening()
                } catch {
                    self.fail("Failed to start listening: \(error.localizedDescription)")
                }
            }
        }
    }

    private func requestMicrophonePermission(completion: @escaping (Bool) -> Void) {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        switch status {
        case .authorized:
            updateStatus("Microphone permission already granted.")
            completion(true)
        case .notDetermined:
            updateStatus("Requesting microphone permission…")
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                DispatchQueue.main.async {
                    completion(granted)
                }
            }
        case .denied:
            updateStatus("Microphone permission was denied. Enable KarenVoice in Privacy & Security → Microphone.")
            completion(false)
        case .restricted:
            updateStatus("Microphone permission is restricted by macOS policy.")
            completion(false)
        @unknown default:
            completion(false)
        }
    }

    private func requestSpeechPermission(completion: @escaping (Bool) -> Void) {
        let status = SFSpeechRecognizer.authorizationStatus()
        switch status {
        case .authorized:
            updateStatus("Speech recognition permission already granted.")
            completion(true)
        case .notDetermined:
            updateStatus("Requesting speech recognition permission…")
            SFSpeechRecognizer.requestAuthorization { status in
                DispatchQueue.main.async {
                    completion(status == .authorized)
                }
            }
        case .denied:
            updateStatus("Speech recognition permission was denied. Enable KarenVoice in Privacy & Security → Speech Recognition.")
            completion(false)
        case .restricted:
            updateStatus("Speech recognition permission is restricted by macOS policy.")
            completion(false)
        @unknown default:
            completion(false)
        }
    }

    private func startListening() throws {
        guard let recognizer else {
            throw NSError(domain: "KarenVoice", code: 1, userInfo: [NSLocalizedDescriptionKey: "Speech recognizer unavailable"])
        }

        guard recognizer.supportsOnDeviceRecognition else {
            throw NSError(domain: "KarenVoice", code: 2, userInfo: [NSLocalizedDescriptionKey: "On-device speech recognition is not supported on this Mac for en-AU"])
        }

        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()

        guard let recognitionRequest else {
            throw NSError(domain: "KarenVoice", code: 3, userInfo: [NSLocalizedDescriptionKey: "Unable to create speech request"])
        }

        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.requiresOnDeviceRecognition = true
        if #available(macOS 13.0, *) {
            recognitionRequest.addsPunctuation = true
        }

        let inputNode = audioEngine.inputNode
        let format = inputNode.outputFormat(forBus: 0)
        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            guard let self, !self.shutdownRequested else { return }
            self.updateVoiceActivity(with: buffer)
            self.recognitionRequest?.append(buffer)
        }

        startTime = Date()
        lastVoiceActivity = startTime
        lastTranscriptActivity = startTime
        shutdownRequested = false
        didStartListening = true
        finalTranscript = ""

        recognitionTask = recognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            guard let self else { return }

            if let result {
                let text = result.bestTranscription.formattedString.trimmingCharacters(in: .whitespacesAndNewlines)
                if !text.isEmpty {
                    self.finalTranscript = text
                    self.lastTranscriptActivity = Date()
                }

                if result.isFinal {
                    self.finishRecognition(successIfNeeded: true)
                    return
                }
            }

            if let error {
                let nsError = error as NSError
                if self.shutdownRequested {
                    self.finishRecognition(successIfNeeded: !self.finalTranscript.isEmpty)
                    return
                }

                if nsError.domain == "kAFAssistantErrorDomain" && nsError.code == 1101 {
                    self.finishRecognition(successIfNeeded: !self.finalTranscript.isEmpty)
                    return
                }

                self.fail("Speech recognition failed: \(error.localizedDescription)")
            }
        }

        audioEngine.prepare()
        try audioEngine.start()
        SoundPlayer.play("Tink")
        updateStatus("Listening now. Speak naturally.")

        monitorTimer = Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] timer in
            guard let self else {
                timer.invalidate()
                return
            }

            if self.shutdownRequested {
                timer.invalidate()
                return
            }

            let now = Date()
            let elapsed = now.timeIntervalSince(self.startTime)
            let lastActivity = max(self.lastVoiceActivity, self.lastTranscriptActivity)
            let silence = now.timeIntervalSince(lastActivity)

            if elapsed >= self.maxDuration {
                self.stopListening(reason: "maximum duration reached")
            } else if !self.finalTranscript.isEmpty && silence >= self.silenceTimeout {
                self.stopListening(reason: "silence timeout reached")
            }
        }
    }

    private func updateVoiceActivity(with buffer: AVAudioPCMBuffer) {
        guard let channelData = buffer.floatChannelData else { return }
        let channel = channelData[0]
        let frameLength = Int(buffer.frameLength)
        guard frameLength > 0 else { return }

        var sum: Float = 0
        for index in 0..<frameLength {
            let sample = channel[index]
            sum += sample * sample
        }
        let rms = sqrt(sum / Float(frameLength))
        if rms >= audioLevelThreshold {
            lastVoiceActivity = Date()
        }
    }

    private func stopListening(reason: String) {
        guard didStartListening, !shutdownRequested else { return }
        shutdownRequested = true
        updateStatus("Stopping capture: \(reason)")
        SoundPlayer.play("Pop")

        monitorTimer?.invalidate()
        monitorTimer = nil

        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()

        finalizeTimer?.invalidate()
        finalizeTimer = Timer.scheduledTimer(withTimeInterval: 1.0, repeats: false) { [weak self] _ in
            self?.finishRecognition(successIfNeeded: !(self?.finalTranscript.isEmpty ?? true))
        }
    }

    private func finishRecognition(successIfNeeded: Bool) {
        guard didStartListening else {
            terminate()
            return
        }

        didStartListening = false
        finalizeTimer?.invalidate()
        finalizeTimer = nil
        monitorTimer?.invalidate()
        monitorTimer = nil

        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil

        let text = finalTranscript.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty {
            updateStatus("Transcription complete.")
            print(text)
            fflush(stdout)
            SoundPlayer.play("Glass")
            exitCode = 0
        } else {
            updateStatus("No speech detected before timeout.")
            exitCode = successIfNeeded ? 0 : 1
        }

        terminate()
    }

    private func fail(_ message: String) {
        updateStatus(message)
        fputs("ERROR: \(message)\n", stderr)
        exitCode = 1
        terminate()
    }

    private func terminate() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
            self.window?.orderOut(nil)
            Darwin.exit(self.exitCode)
        }
    }
}

let args = CommandLine.arguments
let silenceTimeout = args.count > 1 ? (Double(args[1]) ?? 1.5) : 1.5
let maxDuration = args.count > 2 ? (Double(args[2]) ?? 15.0) : 15.0

let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = KarenVoiceApp(silenceTimeout: silenceTimeout, maxDuration: maxDuration)
app.delegate = delegate
app.run()
Darwin.exit(delegate.currentExitCode)
