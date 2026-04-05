import Cocoa
import AVFoundation
import Speech

// MARK: - Karen Live Voice Chat App
// A menu bar app that listens, transcribes, calls Claude, and speaks responses

@main
class AppDelegate: NSObject, NSApplicationDelegate {
    var statusItem: NSStatusItem!
    var audioEngine: AVAudioEngine!
    var speechRecognizer: SFSpeechRecognizer!
    var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    var recognitionTask: SFSpeechRecognitionTask?
    var synthesizer: AVSpeechSynthesizer!
    var isListening = false
    var transcribedText = ""
    var silenceTimer: Timer?
    var lastTranscriptTime: Date?
    
    // Claude API
    let claudeAPIKey: String = {
        // Try environment variable first
        if let key = ProcessInfo.processInfo.environment["ANTHROPIC_API_KEY"], !key.isEmpty {
            return key
        }
        // Try reading from file
        let keyPath = NSString(string: "~/.anthropic_api_key").expandingTildeInPath
        if let key = try? String(contentsOfFile: keyPath, encoding: .utf8) {
            return key.trimmingCharacters(in: .whitespacesAndNewlines)
        }
        return ""
    }()
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Hide dock icon - we're a menu bar app
        NSApp.setActivationPolicy(.accessory)
        
        // Setup menu bar
        setupMenuBar()
        
        // Setup audio
        setupAudio()
        
        // Setup speech recognition
        setupSpeechRecognition()
        
        // Setup synthesizer
        synthesizer = AVSpeechSynthesizer()
        
        // Announce ready
        speak("Karen Live is ready. Click the brain icon to start talking.")
    }
    
    func setupMenuBar() {
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        if let button = statusItem.button {
            button.title = "🧠"
            button.action = #selector(toggleListening)
            button.target = self
        }
        
        // Right-click menu
        let menu = NSMenu()
        menu.addItem(NSMenuItem(title: "Start/Stop Listening", action: #selector(toggleListening), keyEquivalent: "l"))
        menu.addItem(NSMenuItem.separator())
        menu.addItem(NSMenuItem(title: "Quit Karen Live", action: #selector(quit), keyEquivalent: "q"))
        statusItem.menu = nil // We use left-click action, right-click for menu
    }
    
    func setupAudio() {
        audioEngine = AVAudioEngine()
    }
    
    func setupSpeechRecognition() {
        speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))
        
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                switch status {
                case .authorized:
                    print("Speech recognition authorized")
                case .denied:
                    self.speak("Speech recognition denied. Please enable in System Settings.")
                case .restricted:
                    self.speak("Speech recognition restricted on this device.")
                case .notDetermined:
                    self.speak("Speech recognition not determined.")
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
        guard !isListening else { return }
        guard speechRecognizer?.isAvailable == true else {
            speak("Speech recognition not available")
            return
        }
        
        // Request microphone permission
        AVCaptureDevice.requestAccess(for: .audio) { granted in
            DispatchQueue.main.async {
                if granted {
                    self.beginRecording()
                } else {
                    self.speak("Microphone access denied. Please enable in System Settings.")
                }
            }
        }
    }
    
    func beginRecording() {
        // Cancel any existing task
        recognitionTask?.cancel()
        recognitionTask = nil
        
        // Configure audio session
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else {
            speak("Could not create recognition request")
            return
        }
        
        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.addsPunctuation = true
        
        // Start recognition task
        recognitionTask = speechRecognizer?.recognitionTask(with: recognitionRequest) { result, error in
            if let result = result {
                self.transcribedText = result.bestTranscription.formattedString
                self.lastTranscriptTime = Date()
                self.updateMenuBarTitle("🎤 \(self.transcribedText.prefix(20))...")
                
                // Reset silence timer
                self.silenceTimer?.invalidate()
                self.silenceTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: false) { _ in
                    // 2 seconds of silence - process the input
                    if !self.transcribedText.isEmpty {
                        self.processInput()
                    }
                }
            }
            
            if error != nil || (result?.isFinal == true) {
                // Recognition ended
            }
        }
        
        // Install tap on input
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            self.recognitionRequest?.append(buffer)
        }
        
        // Start audio engine
        audioEngine.prepare()
        do {
            try audioEngine.start()
            isListening = true
            updateMenuBarTitle("🎤")
            speak("Listening")
        } catch {
            speak("Could not start audio engine: \(error.localizedDescription)")
        }
    }
    
    func stopListening() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        recognitionTask?.cancel()
        recognitionTask = nil
        silenceTimer?.invalidate()
        isListening = false
        updateMenuBarTitle("🧠")
    }
    
    func processInput() {
        let input = transcribedText
        transcribedText = ""
        stopListening()
        
        guard !input.isEmpty else { return }
        
        print("Processing: \(input)")
        speak("Thinking")
        
        // Call Claude API
        callClaude(prompt: input) { response in
            DispatchQueue.main.async {
                if let response = response {
                    self.speak(response)
                } else {
                    self.speak("Sorry, I couldn't get a response from Claude")
                }
            }
        }
    }
    
    func callClaude(prompt: String, completion: @escaping (String?) -> Void) {
        guard !claudeAPIKey.isEmpty else {
            completion("Claude API key not found. Set ANTHROPIC_API_KEY environment variable or create ~/.anthropic_api_key file")
            return
        }
        
        let url = URL(string: "https://api.anthropic.com/v1/messages")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue(claudeAPIKey, forHTTPHeaderField: "x-api-key")
        request.setValue("2023-06-01", forHTTPHeaderField: "anthropic-version")
        
        let systemPrompt = """
        You are Karen, a helpful AI assistant. The user relies on VoiceOver for accessibility.
        Keep responses concise and conversational - they will be spoken aloud.
        Be warm, helpful, and get straight to the point. Maximum 2-3 sentences unless more detail is needed.
        """
        
        let body: [String: Any] = [
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 500,
            "system": systemPrompt,
            "messages": [
                ["role": "user", "content": prompt]
            ]
        ]
        
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: body)
        } catch {
            completion("Failed to create request")
            return
        }
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            if let error = error {
                completion("Network error: \(error.localizedDescription)")
                return
            }
            
            guard let data = data else {
                completion("No data received")
                return
            }
            
            do {
                if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let content = json["content"] as? [[String: Any]],
                   let firstContent = content.first,
                   let text = firstContent["text"] as? String {
                    completion(text)
                } else if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
                          let error = json["error"] as? [String: Any],
                          let message = error["message"] as? String {
                    completion("Claude error: \(message)")
                } else {
                    completion("Could not parse response")
                }
            } catch {
                completion("Parse error: \(error.localizedDescription)")
            }
        }.resume()
    }
    
    func speak(_ text: String) {
        print("Speaking: \(text)")
        
        // Stop any current speech
        if synthesizer.isSpeaking {
            synthesizer.stopSpeaking(at: .immediate)
        }
        
        let utterance = AVSpeechUtterance(string: text)
        
        // Find Karen voice (Australian)
        let voices = AVSpeechSynthesisVoice.speechVoices()
        if let karenVoice = voices.first(where: { $0.name.contains("Karen") }) {
            utterance.voice = karenVoice
        } else if let aussieVoice = voices.first(where: { $0.language == "en-AU" }) {
            utterance.voice = aussieVoice
        } else {
            utterance.voice = AVSpeechSynthesisVoice(language: "en-US")
        }
        
        utterance.rate = 0.52  // Slightly faster than default
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0
        
        synthesizer.speak(utterance)
    }
    
    func updateMenuBarTitle(_ title: String) {
        DispatchQueue.main.async {
            self.statusItem.button?.title = title
        }
    }
    
    @objc func quit() {
        stopListening()
        NSApplication.shared.terminate(nil)
    }
}
