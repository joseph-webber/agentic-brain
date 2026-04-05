import Cocoa
import AVFoundation
import Speech

// Native macOS Menu Bar Voice App for Agentic Brain
@main
class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var voiceEngine: VoiceEngine!
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Create menu bar icon
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        if let button = statusItem.button {
            button.image = NSImage(systemSymbolName: "brain.head.profile", accessibilityDescription: "Brain Voice")
            button.title = " 🧠"
        }
        
        // Create menu
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "🎤 Start Listening", action: #selector(startListening), keyEquivalent: "l"))
        menu.addItem(NSMenuItem(title: "🔇 Stop Listening", action: #selector(stopListening), keyEquivalent: "s"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "⚙️ Request Permissions", action: #selector(requestPermissions), keyEquivalent: "p"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "❌ Quit", action: #selector(quit), keyEquivalent: "q"))
        statusItem.menu = menu
        
        // Initialize voice engine
        voiceEngine = VoiceEngine()
        
        // Auto-request permissions on launch
        requestPermissions()
        
        // Speak welcome
        voiceEngine.speak("Brain Voice is ready. Click the brain icon to start listening.")
    }
    
    @objc func startListening() {
        voiceEngine.startListening()
        statusItem.button?.title = " 🧠🎤"
    }
    
    @objc func stopListening() {
        voiceEngine.stopListening()
        statusItem.button?.title = " 🧠"
    }
    
    @objc func requestPermissions() {
        voiceEngine.requestAllPermissions { granted in
            if granted {
                self.voiceEngine.speak("All permissions granted! Ready to listen.")
            } else {
                self.voiceEngine.speak("Please grant microphone and speech permissions in System Settings.")
                // Open System Settings
                if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
                    NSWorkspace.shared.open(url)
                }
            }
        }
    }
    
    @objc func quit() {
        voiceEngine.speak("Goodbye")
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
            NSApplication.shared.terminate(nil)
        }
    }
}

class VoiceEngine: NSObject, SFSpeechRecognizerDelegate {
    private let audioEngine = AVAudioEngine()
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))!
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let synthesizer = AVSpeechSynthesizer()
    
    private var isListening = false
    private var lastTranscript = ""
    private var silenceTimer: Timer?
    
    override init() {
        super.init()
        speechRecognizer.delegate = self
    }
    
    func requestAllPermissions(completion: @escaping (Bool) -> Void) {
        var micGranted = false
        var speechGranted = false
        let group = DispatchGroup()
        
        // Microphone
        group.enter()
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            micGranted = granted
            print(granted ? "✅ Mic granted" : "❌ Mic denied")
            group.leave()
        }
        
        // Speech Recognition
        group.enter()
        SFSpeechRecognizer.requestAuthorization { status in
            speechGranted = (status == .authorized)
            print(status == .authorized ? "✅ Speech granted" : "❌ Speech denied")
            group.leave()
        }
        
        group.notify(queue: .main) {
            completion(micGranted && speechGranted)
        }
    }
    
    func startListening() {
        guard !isListening else { return }
        
        // Check permissions first
        let micStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        let speechStatus = SFSpeechRecognizer.authorizationStatus()
        
        guard micStatus == .authorized && speechStatus == .authorized else {
            speak("Please grant permissions first")
            return
        }
        
        do {
            recognitionTask?.cancel()
            recognitionTask = nil
            
            let inputNode = audioEngine.inputNode
            recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
            
            guard let recognitionRequest = recognitionRequest else { return }
            recognitionRequest.shouldReportPartialResults = true
            
            recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
                guard let self = self else { return }
                
                if let result = result {
                    let transcript = result.bestTranscription.formattedString
                    if transcript != self.lastTranscript && !transcript.isEmpty {
                        self.lastTranscript = transcript
                        print("🎤 \(transcript)")
                        
                        // Process after 1.5s silence
                        self.silenceTimer?.invalidate()
                        self.silenceTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: false) { _ in
                            self.processCommand(transcript)
                            self.lastTranscript = ""
                        }
                    }
                }
                
                if error != nil {
                    self.stopListening()
                    // Restart after error
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                        try? self.startListening()
                    }
                }
            }
            
            let recordingFormat = inputNode.outputFormat(forBus: 0)
            inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
                self.recognitionRequest?.append(buffer)
            }
            
            audioEngine.prepare()
            try audioEngine.start()
            isListening = true
            
            speak("Listening")
            print("🎧 Listening... speak now!")
            
        } catch {
            print("❌ Start error: \(error)")
            speak("Failed to start: \(error.localizedDescription)")
        }
    }
    
    func stopListening() {
        guard isListening else { return }
        
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
        isListening = false
        silenceTimer?.invalidate()
        
        print("🔇 Stopped listening")
    }
    
    func processCommand(_ text: String) {
        let cmd = text.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        guard cmd.count >= 3 else { return }
        
        print("📝 Processing: \(text)")
        
        // Check for quit
        if cmd.contains("quit") || cmd.contains("stop") || cmd.contains("exit") {
            speak("Stopping voice control")
            stopListening()
            return
        }
        
        // Send to Copilot CLI
        sendToCopilot(text)
    }
    
    func sendToCopilot(_ prompt: String) {
        speak("Sending to Copilot")
        
        DispatchQueue.global(qos: .userInitiated).async {
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/gh")
            task.arguments = ["copilot", "suggest", "-t", "shell", prompt]
            
            let pipe = Pipe()
            task.standardOutput = pipe
            task.standardError = pipe
            
            do {
                try task.run()
                task.waitUntilExit()
                
                let data = pipe.fileHandleForReading.readDataToEndOfFile()
                if let output = String(data: data, encoding: .utf8), !output.isEmpty {
                    print("🤖 Response: \(output)")
                    DispatchQueue.main.async {
                        self.speak(String(output.prefix(500)))
                    }
                }
            } catch {
                print("❌ Copilot error: \(error)")
                DispatchQueue.main.async {
                    self.speak("Copilot error")
                }
            }
        }
    }
    
    func speak(_ text: String) {
        let wasListening = isListening
        if wasListening {
            audioEngine.pause()
        }
        
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(identifier: "com.apple.voice.premium.en-AU.Karen")
        utterance.rate = 0.52
        
        synthesizer.speak(utterance)
        
        // Wait for completion
        while synthesizer.isSpeaking {
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.1))
        }
        
        if wasListening {
            try? audioEngine.start()
        }
    }
}
