import AVFoundation
import Speech
import Foundation

/// Native macOS voice-to-text: Captures mic + transcribes on-device
/// Outputs plain text to stdout for Copilot to consume
class VoiceToText: NSObject, SFSpeechRecognizerDelegate {
    private let speechRecognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))!
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private let audioEngine = AVAudioEngine()
    
    private var finalTranscript = ""
    private var lastTranscriptTime = Date()
    private let silenceTimeout: TimeInterval
    private let maxDuration: TimeInterval
    private var startTime = Date()
    private var isRunning = false
    
    init(silenceTimeout: TimeInterval = 1.5, maxDuration: TimeInterval = 30.0) {
        self.silenceTimeout = silenceTimeout
        self.maxDuration = maxDuration
        super.init()
        speechRecognizer.delegate = self
    }
    
    func requestPermissions(completion: @escaping (Bool) -> Void) {
        SFSpeechRecognizer.requestAuthorization { status in
            DispatchQueue.main.async {
                switch status {
                case .authorized:
                    completion(true)
                case .denied:
                    fputs("ERROR:Speech denied - go to System Settings > Privacy > Speech Recognition\n", stderr)
                    completion(false)
                case .restricted:
                    fputs("ERROR:Speech restricted\n", stderr)
                    completion(false)
                case .notDetermined:
                    fputs("ERROR:Speech not determined\n", stderr)
                    completion(false)
                @unknown default:
                    completion(false)
                }
            }
        }
    }
    
    func startListening() throws {
        guard !isRunning else { return }
        isRunning = true
        
        // Cancel any previous task
        recognitionTask?.cancel()
        recognitionTask = nil
        
        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else {
            throw NSError(domain: "VoiceToText", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unable to create request"])
        }
        
        recognitionRequest.shouldReportPartialResults = true
        
        // Use on-device if available (faster, private)
        if #available(macOS 10.15, *) {
            recognitionRequest.requiresOnDeviceRecognition = speechRecognizer.supportsOnDeviceRecognition
        }
        
        // Get input node - this is where mic audio comes in
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        // Install tap to capture audio
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
        }
        
        // Start recognition task
        startTime = Date()
        lastTranscriptTime = Date()
        
        recognitionTask = speechRecognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            guard let self = self else { return }
            
            if let result = result {
                self.finalTranscript = result.bestTranscription.formattedString
                self.lastTranscriptTime = Date()
                
                if result.isFinal {
                    self.stopAndOutput()
                }
            }
            
            if let error = error as NSError?, error.domain == "kAFAssistantErrorDomain" {
                // Silence or no speech - not a real error
                if self.finalTranscript.isEmpty {
                    self.stopAndOutput()
                }
            }
        }
        
        // Start audio engine
        audioEngine.prepare()
        try audioEngine.start()
        
        // Play ready sound
        playSound("Tink")
        
        // Monitor for silence timeout or max duration
        Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { [weak self] timer in
            guard let self = self, self.isRunning else { 
                timer.invalidate()
                return 
            }
            
            let elapsed = Date().timeIntervalSince(self.startTime)
            let silentFor = Date().timeIntervalSince(self.lastTranscriptTime)
            
            // Stop if max duration reached
            if elapsed >= self.maxDuration {
                timer.invalidate()
                self.stopAndOutput()
                return
            }
            
            // Stop if silence timeout and we have some text
            if silentFor >= self.silenceTimeout && !self.finalTranscript.isEmpty {
                timer.invalidate()
                self.stopAndOutput()
                return
            }
        }
    }
    
    private func stopAndOutput() {
        guard isRunning else { return }
        isRunning = false
        
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionTask?.cancel()
        
        let text = finalTranscript.trimmingCharacters(in: .whitespacesAndNewlines)
        if !text.isEmpty {
            playSound("Pop")
            print(text)  // Output to stdout for Copilot
        } else {
            playSound("Basso")
            fputs("SILENCE\n", stderr)
        }
        
        exit(text.isEmpty ? 1 : 0)
    }
    
    private func playSound(_ name: String) {
        let path = "/System/Library/Sounds/\(name).aiff"
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/afplay")
        task.arguments = [path]
        try? task.run()
    }
}

// MARK: - Main

let args = CommandLine.arguments
let silenceTimeout = args.count > 1 ? Double(args[1]) ?? 1.5 : 1.5
let maxDuration = args.count > 2 ? Double(args[2]) ?? 30.0 : 30.0

let voiceToText = VoiceToText(silenceTimeout: silenceTimeout, maxDuration: maxDuration)

voiceToText.requestPermissions { authorized in
    guard authorized else {
        exit(1)
    }
    
    do {
        try voiceToText.startListening()
    } catch {
        fputs("ERROR:\(error.localizedDescription)\n", stderr)
        exit(1)
    }
}

// Keep main thread alive
RunLoop.current.run()
