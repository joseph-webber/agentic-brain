import Cocoa
import Speech
import AVFoundation

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
        
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.speak("Karen Chat ready. Press Enter to start talking.")
        }
    }
    
    func setupWindow() {
        window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 500, height: 400),
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Karen Chat"
        window.center()
        
        let contentView = NSView(frame: window.contentView!.bounds)
        contentView.autoresizingMask = [.width, .height]
        window.contentView = contentView
        
        // Big Listen button
        listenButton = NSButton(frame: NSRect(x: 50, y: 300, width: 400, height: 60))
        listenButton.title = "Press Enter to Talk"
        listenButton.bezelStyle = .rounded
        listenButton.font = NSFont.systemFont(ofSize: 24, weight: .bold)
        listenButton.target = self
        listenButton.action = #selector(toggleListening)
        listenButton.keyEquivalent = "\r"
        listenButton.setAccessibilityLabel("Press Enter to start voice chat with Karen")
        contentView.addSubview(listenButton)
        
        // Status label
        statusLabel = NSTextField(frame: NSRect(x: 50, y: 220, width: 400, height: 60))
        statusLabel.stringValue = "Ready - Press Enter to talk"
        statusLabel.isEditable = false
        statusLabel.isBordered = false
        statusLabel.backgroundColor = .clear
        statusLabel.font = NSFont.systemFont(ofSize: 18)
        statusLabel.alignment = .center
        contentView.addSubview(statusLabel)
        
        // Response area
        responseLabel = NSTextField(frame: NSRect(x: 50, y: 50, width: 400, height: 150))
        responseLabel.stringValue = "Karen's response appears here"
        responseLabel.isEditable = false
        responseLabel.isBordered = true
        responseLabel.font = NSFont.systemFont(ofSize: 16)
        contentView.addSubview(responseLabel)
        
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(listenButton)
        NSApp.activate(ignoringOtherApps: true)
    }
    
    func setupSpeech() {
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                if status == .authorized {
                    self.statusLabel.stringValue = "Ready - Press Enter to talk"
                } else {
                    self.statusLabel.stringValue = "Please enable Speech Recognition in System Settings"
                }
            }
        }
    }
    
    @objc func toggleListening() {
        if isListening { stopListening() } else { startListening() }
    }
    
    func startListening() {
        guard let recognizer = speechRecognizer, recognizer.isAvailable else {
            speak("Speech not available")
            return
        }
        
        isListening = true
        listenButton.title = "Listening... Press Enter to stop"
        statusLabel.stringValue = "Listening... speak now"
        
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        let inputNode = audioEngine.inputNode
        guard let request = recognitionRequest else { return }
        request.shouldReportPartialResults = true
        
        recognitionTask = recognizer.recognitionTask(with: request) { [weak self] result, error in
            guard let self = self else { return }
            if let result = result {
                let text = result.bestTranscription.formattedString
                self.statusLabel.stringValue = "You: \(text)"
                if result.isFinal { self.processInput(text) }
            }
            if error != nil { self.stopListening() }
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
            statusLabel.stringValue = "Audio error"
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
        listenButton.title = "Press Enter to Talk"
    }
    
    func processInput(_ text: String) {
        stopListening()
        statusLabel.stringValue = "Thinking..."
        let response = getResponse(text)
        responseLabel.stringValue = response
        speak(response)
    }
    
    func getResponse(_ input: String) -> String {
        let lower = input.lowercased()
        if lower.contains("hello") || lower.contains("hi") {
            return "G'day! How can I help you?"
        } else if lower.contains("time") {
            let f = DateFormatter(); f.timeStyle = .short
            return "It's \(f.string(from: Date()))"
        } else if lower.contains("bye") || lower.contains("quit") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 2) { NSApp.terminate(nil) }
            return "Goodbye!"
        } else {
            return "I heard: \(input). Full brain connection coming soon!"
        }
    }
    
    func speak(_ text: String) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(identifier: "com.apple.voice.premium.en-AU.Karen")
        utterance.rate = 0.52
        synthesizer.speak(utterance)
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }
}

// Explicit main - no @main attribute
let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.run()
