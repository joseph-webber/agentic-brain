import Cocoa
import AVFoundation
import Speech

// =============================================================================
// AGENTIC BRAIN - Native macOS Control Center
// ONE app for: Voice Chat, Hardware Control, Copilot Bridge, TTS
// =============================================================================

class AgenticBrain: NSObject, SFSpeechRecognizerDelegate {
    
    // MARK: - Audio & Speech
    private let audioEngine = AVAudioEngine()
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))!
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let synthesizer = NSSpeechSynthesizer(voice: NSSpeechSynthesizer.VoiceName(rawValue: "com.apple.voice.premium.en-AU.Karen"))
    
    // MARK: - State
    private var isListening = false
    private var lastTranscript = ""
    private var silenceTimer: Timer?
    private let copilotMode: Bool
    
    init(copilotMode: Bool = false) {
        self.copilotMode = copilotMode
        super.init()
        speechRecognizer.delegate = self
    }
    
    // MARK: - Permissions
    func requestPermissions(completion: @escaping (Bool) -> Void) {
        var micGranted = false
        var speechGranted = false
        let group = DispatchGroup()
        
        // Request Microphone
        group.enter()
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            micGranted = granted
            if granted {
                print("✅ Microphone permission granted")
            } else {
                print("❌ Microphone permission denied")
            }
            group.leave()
        }
        
        // Request Speech Recognition
        group.enter()
        SFSpeechRecognizer.requestAuthorization { status in
            speechGranted = (status == .authorized)
            switch status {
            case .authorized: print("✅ Speech recognition authorized")
            case .denied: print("❌ Speech recognition denied")
            case .restricted: print("⚠️ Speech recognition restricted")
            case .notDetermined: print("⏳ Speech recognition not determined")
            @unknown default: print("❓ Unknown speech status")
            }
            group.leave()
        }
        
        group.notify(queue: .main) {
            completion(micGranted && speechGranted)
        }
    }
    
    // MARK: - Voice Chat
    func startListening() throws {
        // Cancel any existing task
        recognitionTask?.cancel()
        recognitionTask = nil
        
        // Configure audio session for input
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else {
            throw NSError(domain: "AgenticBrain", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unable to create recognition request"])
        }
        
        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.requiresOnDeviceRecognition = false // Use server for better accuracy
        
        // Start recognition task
        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            guard let self = self else { return }
            
            if let result = result {
                let transcript = result.bestTranscription.formattedString
                if transcript != self.lastTranscript {
                    self.lastTranscript = transcript
                    print("🎤 \(transcript)")
                    
                    // Reset silence timer
                    self.silenceTimer?.invalidate()
                    self.silenceTimer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: false) { _ in
                        if result.isFinal || transcript.count > 10 {
                            self.processCommand(transcript)
                        }
                    }
                }
                
                if result.isFinal {
                    self.processCommand(transcript)
                }
            }
            
            if error != nil {
                self.stopListening()
            }
        }
        
        // Install tap on input node
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            self.recognitionRequest?.append(buffer)
        }
        
        audioEngine.prepare()
        try audioEngine.start()
        isListening = true
        
        speak("I'm listening")
        print("🎧 Listening... (say 'quit' to exit)")
    }
    
    func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionTask = nil
        recognitionRequest = nil
        isListening = false
    }
    
    // MARK: - Command Processing
    func processCommand(_ text: String) {
        let command = text.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
        
        // Check for exit commands
        if command.contains("quit") || command.contains("exit") || command.contains("stop listening") {
            speak("Goodbye")
            stopListening()
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                NSApplication.shared.terminate(nil)
            }
            return
        }
        
        // Skip empty or too short
        if command.count < 3 { return }
        
        print("📝 Processing: \(text)")
        
        if copilotMode {
            sendToCopilot(text)
        } else {
            sendToClaude(text)
        }
        
        // Reset for next command
        lastTranscript = ""
    }
    
    // MARK: - Copilot Integration
    func sendToCopilot(_ prompt: String) {
        speak("Sending to Copilot")
        
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
                print("🤖 Copilot: \(output)")
                speak(output)
            } else {
                speak("No response from Copilot")
            }
        } catch {
            print("❌ Copilot error: \(error)")
            speak("Error running Copilot")
        }
    }
    
    // MARK: - Claude Integration (via agentic-brain)
    func sendToClaude(_ prompt: String) {
        speak("Processing with Claude")
        
        // Write prompt to temp file for agentic-brain to pick up
        let promptFile = "/tmp/agentic_brain_prompt.txt"
        let responseFile = "/tmp/agentic_brain_response.txt"
        
        do {
            try prompt.write(toFile: promptFile, atomically: true, encoding: .utf8)
            
            // Call Python voice handler
            let task = Process()
            task.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            task.arguments = ["/Users/joe/brain/agentic-brain/voice_handler.py", promptFile, responseFile]
            task.currentDirectoryURL = URL(fileURLWithPath: "/Users/joe/brain/agentic-brain")
            
            try task.run()
            task.waitUntilExit()
            
            if let response = try? String(contentsOfFile: responseFile, encoding: .utf8), !response.isEmpty {
                print("🤖 Claude: \(response)")
                speak(response)
            }
        } catch {
            print("❌ Claude error: \(error)")
            // Fallback: just echo back
            speak("I heard you say: \(prompt)")
        }
    }
    
    // MARK: - Text to Speech
    func speak(_ text: String) {
        print("🔊 Speaking: \(text)")
        
        // Stop listening while speaking to avoid feedback
        let wasListening = isListening
        if wasListening {
            audioEngine.pause()
        }
        
        synthesizer?.startSpeaking(text)
        
        // Wait for speech to complete
        while synthesizer?.isSpeaking == true {
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.1))
        }
        
        // Resume listening
        if wasListening {
            try? audioEngine.start()
        }
    }
    
    // MARK: - Run Loop
    func run() {
        requestPermissions { [weak self] granted in
            guard let self = self else { return }
            
            if granted {
                do {
                    try self.startListening()
                    
                    // Keep running
                    RunLoop.main.run()
                } catch {
                    print("❌ Failed to start: \(error)")
                    self.speak("Failed to start listening: \(error.localizedDescription)")
                }
            } else {
                print("❌ Permissions not granted")
                self.speak("I need microphone and speech recognition permissions. Please grant them in System Settings.")
                
                // Open System Settings to Privacy
                if let url = URL(string: "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone") {
                    NSWorkspace.shared.open(url)
                }
            }
        }
    }
}

// =============================================================================
// MAIN
// =============================================================================

let args = CommandLine.arguments
let copilotMode = args.contains("--copilot")

print("""
╔══════════════════════════════════════════════════════════════╗
║  🧠 AGENTIC BRAIN - Native macOS Voice Control               ║
║  Mode: \(copilotMode ? "GitHub Copilot" : "Claude/Standalone")                                    ║
║  Say 'quit' to exit                                          ║
╚══════════════════════════════════════════════════════════════╝
""")

let brain = AgenticBrain(copilotMode: copilotMode)
brain.run()
