import AppKit
import AVFoundation
import Foundation
import Speech

private enum FollowUpAction {
    case none
    case listen
    case exit
}

private struct SelfTest {
    static func run() -> Int32 {
        var failures: [String] = []
        let bundleID = Bundle.main.bundleIdentifier ?? "missing"
        let karenVoice = VoicePicker.karenVoiceIdentifier()
        let soundNames = ["Tink", "Pop", "Glass", "Basso"]
        let missingSounds = soundNames.filter { !SoundPlayer.soundExists(named: $0) }
        let copilotPath = CopilotRunner.resolveCopilotExecutable()

        if bundleID != "com.brain.copilotvoice" {
            failures.append("Bundle identifier is \(bundleID), expected com.brain.copilotvoice.")
        }

        if karenVoice == nil {
            failures.append("Karen voice was not found in NSSpeechSynthesizer.availableVoices.")
        }

        if !missingSounds.isEmpty {
            failures.append("Missing system sounds: \(missingSounds.joined(separator: ", ")).")
        }

        if copilotPath == nil {
            failures.append("Unable to locate the copilot executable in the shell environment.")
        }

        print("CopilotVoice self-test")
        print("bundle_id=\(bundleID)")
        print("karen_voice=\(karenVoice?.rawValue ?? "missing")")
        print("copilot=\(copilotPath ?? "missing")")
        print("sounds_ok=\(missingSounds.isEmpty)")

        if failures.isEmpty {
            print("status=PASS")
            return 0
        }

        for failure in failures {
            fputs("FAIL: \(failure)\n", stderr)
        }
        print("status=FAIL")
        return 1
    }
}

private enum SoundPlayer {
    private static let soundsDirectory = "/System/Library/Sounds"

    static func soundExists(named name: String) -> Bool {
        FileManager.default.fileExists(atPath: "\(soundsDirectory)/\(name).aiff")
    }

    static func play(_ name: String) {
        let path = "\(soundsDirectory)/\(name).aiff"
        guard FileManager.default.fileExists(atPath: path) else {
            NSSound.beep()
            return
        }

        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/afplay")
        task.arguments = [path]
        try? task.run()
    }
}

private enum VoicePicker {
    static func karenVoiceIdentifier() -> NSSpeechSynthesizer.VoiceName? {
        for voice in NSSpeechSynthesizer.availableVoices {
            let attributes = NSSpeechSynthesizer.attributes(forVoice: voice)
            let name = (attributes[.name] as? String) ?? voice.rawValue
            if name.localizedCaseInsensitiveContains("Karen") {
                return voice
            }
        }
        return nil
    }
}

private enum CopilotRunnerError: Error {
    case message(String)
}

private struct CopilotRunner {
    static func resolveCopilotExecutable() -> String? {
        let process = Process()
        let stdout = Pipe()
        let stderr = Pipe()

        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-lc", "command -v copilot"]
        process.standardOutput = stdout
        process.standardError = stderr

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return nil
        }

        guard process.terminationStatus == 0 else {
            return nil
        }

        let data = stdout.fileHandleForReading.readDataToEndOfFile()
        let value = String(data: data, encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)

        return value?.isEmpty == false ? value : nil
    }

    static func ask(prompt: String) -> Result<String, CopilotRunnerError> {
        let process = Process()
        let stdout = Pipe()
        let stderr = Pipe()

        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        process.arguments = ["-lc", "copilot -p \"$COPILOT_VOICE_PROMPT\" --allow-all-tools"]
        process.standardOutput = stdout
        process.standardError = stderr
        process.currentDirectoryURL = URL(fileURLWithPath: FileManager.default.homeDirectoryForCurrentUser.path)

        var environment = ProcessInfo.processInfo.environment
        environment["COPILOT_VOICE_PROMPT"] = prompt
        process.environment = environment

        do {
            try process.run()
            process.waitUntilExit()
        } catch {
            return .failure(.message("I couldn't start GitHub Copilot CLI. \(error.localizedDescription)"))
        }

        let stdoutText = String(data: stdout.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let stderrText = String(data: stderr.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
        let combined = sanitize(stdoutText + (stderrText.isEmpty ? "" : "\n\(stderrText)"))

        guard process.terminationStatus == 0 else {
            if combined.isEmpty {
                return .failure(.message("GitHub Copilot exited with status \(process.terminationStatus)."))
            }
            return .failure(.message(combined))
        }

        let response = sanitize(stdoutText)
        if response.isEmpty {
            return .failure(.message("GitHub Copilot returned an empty response."))
        }

        return .success(response)
    }

    private static func sanitize(_ value: String) -> String {
        let ansiPattern = #"\u{001B}\[[0-9;?]*[ -/]*[@-~]"#
        let withoutANSI = value.replacingOccurrences(
            of: ansiPattern,
            with: "",
            options: .regularExpression
        )

        return withoutANSI
            .replacingOccurrences(of: "\r\n", with: "\n")
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }
}

final class CopilotVoiceController: NSObject, NSApplicationDelegate, NSSpeechSynthesizerDelegate, SFSpeechRecognizerDelegate {
    private let audioEngine = AVAudioEngine()
    private let synthesizer = NSSpeechSynthesizer()
    private let workerQueue = DispatchQueue(label: "com.brain.copilotvoice.worker", qos: .userInitiated)

    private var speechRecognizer: SFSpeechRecognizer?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var monitorTimer: Timer?

    private var currentTranscript = ""
    private var listenStartDate = Date()
    private var lastTranscriptDate = Date()
    private var followUpAction: FollowUpAction = .none

    private var warnedAboutRecognizerFallback = false
    private var isListening = false
    private var isSpeaking = false
    private var isProcessing = false

    private let utterancePauseTimeout: TimeInterval = 1.2
    private let silenceTimeout: TimeInterval = 30.0

    override init() {
        super.init()
        synthesizer.delegate = self
        synthesizer.rate = 175
        synthesizer.volume = 1.0
        if let karenVoice = VoicePicker.karenVoiceIdentifier() {
            _ = synthesizer.setVoice(karenVoice)
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let recognizer = preferredRecognizer() {
            speechRecognizer = recognizer
            recognizer.delegate = self
        } else {
            failAndMaybeRecover("I couldn't create a speech recognizer on this Mac.", recover: false)
            return
        }

        requestPermissions()
    }

    func applicationWillTerminate(_ notification: Notification) {
        cleanupRecognition()
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking()
        }
    }

    func speechSynthesizer(_ sender: NSSpeechSynthesizer, didFinishSpeaking finishedSpeaking: Bool) {
        isSpeaking = false
        let action = followUpAction
        followUpAction = .none

        switch action {
        case .listen:
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                self?.beginListeningLoop()
            }
        case .exit:
            NSApp.terminate(nil)
        case .none:
            break
        }
    }

    private func requestPermissions() {
        requestMicrophonePermission { [weak self] microphoneGranted in
            guard let self else { return }
            guard microphoneGranted else {
                self.failAndMaybeRecover(
                    "Microphone access was denied. Please enable Copilot Voice in System Settings, Privacy and Security, Microphone.",
                    recover: false
                )
                return
            }

            self.requestSpeechPermission { speechGranted in
                guard speechGranted else {
                    self.failAndMaybeRecover(
                        "Speech recognition access was denied. Please enable Copilot Voice in System Settings, Privacy and Security, Speech Recognition.",
                        recover: false
                    )
                    return
                }

                self.speak(
                    "Copilot Voice is ready. Say stop or quit any time to finish.",
                    nextAction: .listen
                )
            }
        }
    }

    private func requestMicrophonePermission(completion: @escaping (Bool) -> Void) {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .authorized:
            completion(true)
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                DispatchQueue.main.async {
                    completion(granted)
                }
            }
        case .denied, .restricted:
            completion(false)
        @unknown default:
            completion(false)
        }
    }

    private func requestSpeechPermission(completion: @escaping (Bool) -> Void) {
        switch SFSpeechRecognizer.authorizationStatus() {
        case .authorized:
            completion(true)
        case .notDetermined:
            SFSpeechRecognizer.requestAuthorization { status in
                DispatchQueue.main.async {
                    completion(status == .authorized)
                }
            }
        case .denied, .restricted:
            completion(false)
        @unknown default:
            completion(false)
        }
    }

    private func preferredRecognizer() -> SFSpeechRecognizer? {
        let locales = ["en-AU", "en-US"]
        let recognizers = locales.compactMap { SFSpeechRecognizer(locale: Locale(identifier: $0)) }

        if let onDevice = recognizers.first(where: { $0.supportsOnDeviceRecognition }) {
            return onDevice
        }

        return recognizers.first
    }

    private func beginListeningLoop() {
        guard !isListening, !isSpeaking, !isProcessing else { return }
        guard let recognizer = speechRecognizer else {
            failAndMaybeRecover("Speech recognizer is unavailable.", recover: false)
            return
        }

        if !recognizer.isAvailable {
            failAndMaybeRecover("Speech recognizer is temporarily unavailable.", recover: true)
            return
        }

        cleanupRecognition()
        currentTranscript = ""
        listenStartDate = Date()
        lastTranscriptDate = Date()

        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        if recognizer.supportsOnDeviceRecognition {
            request.requiresOnDeviceRecognition = true
        } else if !warnedAboutRecognizerFallback {
            warnedAboutRecognizerFallback = true
            fputs("Warning: on-device recognition is unavailable for the selected recognizer; macOS may use its built-in network service.\n", stderr)
        }

        recognitionRequest = request

        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.removeTap(onBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }

        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self else { return }

            if let result {
                let transcript = result.bestTranscription.formattedString
                    .trimmingCharacters(in: .whitespacesAndNewlines)

                if !transcript.isEmpty {
                    self.currentTranscript = transcript
                    self.lastTranscriptDate = Date()
                }

                if result.isFinal {
                    self.finishListeningAndProcess()
                }
            }

            if let error {
                let nsError = error as NSError
                if self.currentTranscript.isEmpty, nsError.domain == "kAFAssistantErrorDomain" {
                    return
                }

                if !self.currentTranscript.isEmpty {
                    self.finishListeningAndProcess()
                    return
                }

                self.failAndMaybeRecover("Speech recognition failed. \(error.localizedDescription)", recover: true)
            }
        }

        do {
            audioEngine.prepare()
            try audioEngine.start()
            isListening = true
            SoundPlayer.play("Tink")
            startMonitorTimer()
        } catch {
            failAndMaybeRecover("I couldn't start the microphone. \(error.localizedDescription)", recover: true)
        }
    }

    private func startMonitorTimer() {
        monitorTimer?.invalidate()
        monitorTimer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { [weak self] timer in
            guard let self else {
                timer.invalidate()
                return
            }

            guard self.isListening else {
                timer.invalidate()
                return
            }

            let now = Date()
            if self.currentTranscript.isEmpty {
                if now.timeIntervalSince(self.listenStartDate) >= self.silenceTimeout {
                    self.handleSilenceTimeout()
                }
            } else if now.timeIntervalSince(self.lastTranscriptDate) >= self.utterancePauseTimeout {
                self.finishListeningAndProcess()
            }
        }
    }

    private func handleSilenceTimeout() {
        cleanupRecognition()
        speak("I didn't hear anything. Listening again.", nextAction: .listen)
    }

    private func finishListeningAndProcess() {
        guard isListening else { return }

        let prompt = currentTranscript.trimmingCharacters(in: .whitespacesAndNewlines)
        cleanupRecognition()

        guard !prompt.isEmpty else {
            speak("I didn't catch that. Let's try again.", nextAction: .listen)
            return
        }

        let normalized = prompt.lowercased()
        if normalized == "stop" || normalized == "quit" {
            SoundPlayer.play("Glass")
            speak("Stopping Copilot Voice. Goodbye Joseph.", nextAction: .exit)
            return
        }

        isProcessing = true
        SoundPlayer.play("Pop")

        workerQueue.async { [weak self] in
            guard let self else { return }
            let result = CopilotRunner.ask(prompt: prompt)
            DispatchQueue.main.async {
                self.isProcessing = false

                switch result {
                case .success(let response):
                    fputs("Joseph said: \(prompt)\n", stderr)
                    print(response)
                    SoundPlayer.play("Glass")
                    self.speak(response, nextAction: .listen)
                case .failure(let error):
                    let message: String
                    switch error {
                    case .message(let value):
                        message = value
                    }
                    self.failAndMaybeRecover(message, recover: true)
                }
            }
        }
    }

    private func cleanupRecognition() {
        monitorTimer?.invalidate()
        monitorTimer = nil

        if audioEngine.isRunning {
            audioEngine.stop()
        }

        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        isListening = false
    }

    private func speak(_ message: String, nextAction: FollowUpAction) {
        followUpAction = nextAction

        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking()
        }

        isSpeaking = true
        let started = synthesizer.startSpeaking(message)

        if !started {
            isSpeaking = false
            switch nextAction {
            case .listen:
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                    self?.beginListeningLoop()
                }
            case .exit:
                NSApp.terminate(nil)
            case .none:
                break
            }
        }
    }

    private func failAndMaybeRecover(_ message: String, recover: Bool) {
        cleanupRecognition()
        isProcessing = false
        SoundPlayer.play("Basso")
        fputs("ERROR: \(message)\n", stderr)

        if recover {
            speak("Error. \(message). I'll listen again.", nextAction: .listen)
        } else {
            speak("Error. \(message). Closing Copilot Voice.", nextAction: .exit)
        }
    }
}

private enum SingleShotMode {
    static func run(prompt: String, shouldSpeak: Bool) -> Int32 {
        switch CopilotRunner.ask(prompt: prompt) {
        case .success(let response):
            print(response)

            if shouldSpeak {
                let synthesizer = NSSpeechSynthesizer()
                synthesizer.rate = 175
                if let karenVoice = VoicePicker.karenVoiceIdentifier() {
                    _ = synthesizer.setVoice(karenVoice)
                }
                SoundPlayer.play("Glass")
                _ = synthesizer.startSpeaking(response)
                while synthesizer.isSpeaking {
                    RunLoop.current.run(until: Date().addingTimeInterval(0.1))
                }
            }

            return 0
        case .failure(let error):
            let message: String
            switch error {
            case .message(let value):
                message = value
            }
            SoundPlayer.play("Basso")
            fputs("ERROR: \(message)\n", stderr)
            return 1
        }
    }
}

@main
struct CopilotVoiceMain {
    private static let retainedController = CopilotVoiceController()

    static func main() {
        let arguments = CommandLine.arguments

        if arguments.contains("--self-test") {
            exit(SelfTest.run())
        }

        if let promptIndex = arguments.firstIndex(of: "--single-shot"), arguments.indices.contains(promptIndex + 1) {
            let prompt = arguments[promptIndex + 1]
            let shouldSpeak = !arguments.contains("--no-speak")
            exit(SingleShotMode.run(prompt: prompt, shouldSpeak: shouldSpeak))
        }

        let app = NSApplication.shared
        app.setActivationPolicy(.accessory)
        app.delegate = retainedController
        app.run()
    }
}
