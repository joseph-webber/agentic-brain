import Cocoa
import Speech
import AVFoundation

@main
class AppDelegate: NSObject, NSApplicationDelegate {
    var window: NSWindow!
    var statusLabel: NSTextField!
    var responseLabel: NSTextField!
    var listenButton: NSButton!
    var speechRecognizer: SFSpeechRecognizer?
    var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    var recognitionTask: SFSpeechRecognitionTask?
    var audioEngine = AVAudioEngine()
    var synthesizer = AVSpeechSynthesizer()
    var isListening = false
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        setupWindow()
        setupSpeech()
        
        // Announce launch for VoiceOver
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.speak("Karen Chat ready. Press the Listen button or press Enter to start talking.")
        }
    }
    
    func setupWindow() {
        // Create accessible window
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 500, height: 400),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Karen Chat"
        window.center()
        window.makeKeyAndOrderFront(nil)
        
        let contentView = NSView(frame: window.contentView!.bounds)
        contentView.autoresizingMask = [.width, .height]
        window.contentView = contentView
        
        // Big accessible Listen button
        listenButton = NSButton(frame: NSRect(x: 50, y: 300, width: 400, height: 60))
        listenButton.title = "🎤 Listen (Press Enter)"
        listenButton.bezelStyle = .rounded
        listenButton.font = NSFont.systemFont(ofSize: 24, weight: .bold)
        listenButton.target = self
        listenButton.action = #selector(toggleListening)
        listenButton.keyEquivalent = "\r"  // Enter key
        listenButton.setAccessibilityLabel("Listen button. Press Enter to start voice recognition.")
        contentView.addSubview(listenButton)
        
        // Status label
        statusLabel = NSTextField(frame: NSRect(x: 50, y: 220, width: 400, height: 60))
        statusLabel.stringValue = "Ready - Press Enter to talk to Karen"
        statusLabel.isEditable = false
        statusLabel.isBordered = false
        statusLabel.backgroundColor = .clear
        statusLabel.font = NSFont.systemFont(ofSize: 18)
        statusLabel.alignment = .center
        statusLabel.setAccessibilityLabel("Status")
        contentView.addSubview(statusLabel)
        
        // Response area
        responseLabel = NSTextField(frame: NSRect(x: 50, y: 50, width: 400, height: 150))
        responseLabel.stringValue = "Karen's response will appear here"
        responseLabel.isEditable = false
        responseLabel.isBordered = true
        responseLabel.backgroundColor = NSColor.textBackgroundColor
        responseLabel.font = NSFont.systemFont(ofSize: 16)
        responseLabel.setAccessibilityLabel("Karen's response")
        contentView.addSubview(responseLabel)
        
        // Make window key for keyboard
        window.makeFirstResponder(listenButton)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    func setupSpeech() {
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))
        
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                switch status {
                case .authorized:
                    self.statusLabel.stringValue = "Ready - Press Enter to talk"
                case .denied, .restricted:
                    self.statusLabel.stringValue = "Speech recognition denied. Check System Settings > Privacy."
                    self.speak("Speech recognition is not authorized. Please enable it in System Settings, Privacy and Security, Speech Recognition.")
                case .notDetermined:
                    self.statusLabel.stringValue = "Requesting permission..."
                @unknown default:
                    break
                }
            }
        }
    }
    
    @objc func toggleListening() {
        if isListening {
            stopListening()
        } else {
            startListening()
        }
    }
    
    func startListening() {
        guard let recognizer = speechRecognizer, recognizer.isAvailable else {
            speak("Speech recognition not available")
            return
        }
        
        isListening = true
        listenButton.title = "🔴 Listening... (Press Enter to stop)"
        statusLabel.stringValue = "Listening... speak now"
        
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        
        let inputNode = audioEngine.inputNode
        guard let request = recognitionRequest else { return }
        
        request.shouldReportPartialResults = true
        
        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self = self else { return }
            
            if let result = result {
                let text = result.bestTranscription.formattedString
                self.statusLabel.stringValue = "You said: \(text)"
                
                if result.isFinal {
                    self.processUserInput(text)
                }
            }
            
            if error != nil {
                self.stopListening()
            }
        }
        
        let format = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
            self.recognitionRequest?.append(buffer)
        }
        
        audioEngine.prepare()
        do {
            try audioEngine.start()
            speak("I'm listening")
        } catch {
            statusLabel.stringValue = "Audio error: \(error.localizedDescription)"
        }
    }
    
    func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        recognitionRequest = nil
        recognitionTask = nil
        isListening = false
        
        listenButton.title = "🎤 Listen (Press Enter)"
    }
    
    func processUserInput(_ text: String) {
        stopListening()
        statusLabel.stringValue = "Thinking..."
        
        // For now, use a simple response - can integrate Claude API later
        let response = generateResponse(to: text)
        responseLabel.stringValue = response
        speak(response)
    }
    
    func generateResponse(to input: String) -> String {
        let lower = input.lowercased()
        
        if lower.contains("hello") || lower.contains("hi") {
            return "G'day! How can I help you today?"
        } else if lower.contains("time") {
            let formatter = DateFormatter()
            formatter.timeStyle = .short
            return "It's \(formatter.string(from: Date()))"
        } else if lower.contains("date") {
            let formatter = DateFormatter()
            formatter.dateStyle = .full
            return "Today is \(formatter.string(from: Date()))"
        } else if lower.contains("how are you") {
            return "I'm great thanks for asking! Ready to help with whatever you need."
        } else if lower.contains("quit") || lower.contains("exit") || lower.contains("bye") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                NSApp.terminate(nil)
            }
            return "Goodbye! See you later."
        } else {
            return "I heard you say: \(input). I'm a simple demo right now, but I'll be connected to the full brain soon!"
        }
    }
    
    func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(identifier: "com.apple.voice.premium.en-AU.Karen")
        utterance.rate = 0.52
        synthesizer.speak(utterance)
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}
