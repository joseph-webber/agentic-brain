import AVFoundation
import Combine
import CoreAudio
import Foundation
import os.log
import Speech

// MARK: - Microphone Debug Logger
private let micLogger = Logger(subsystem: "com.brainchat.app", category: "Microphone")

/// Write debug logs to file for verification (Console.app + file)
private func logMic(_ message: String, level: OSLogType = .debug) {
    let logPath = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("brain/agentic-brain/apps/BrainChat/runtime/mic-debug.log")
    let timestamp = ISO8601DateFormatter().string(from: Date())
    let levelStr: String
    switch level {
    case .error: levelStr = "ERROR"
    case .fault: levelStr = "FAULT"
    case .info: levelStr = "INFO"
    default: levelStr = "DEBUG"
    }
    let line = "[\(timestamp)] [\(levelStr)] \(message)\n"
    
    // Log to os_log (Console.app)
    micLogger.log(level: level, "\(message)")
    
    // Also write to file for easy verification
    if let data = line.data(using: .utf8) {
        let dir = logPath.deletingLastPathComponent()
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        
        if FileManager.default.fileExists(atPath: logPath.path) {
            if let handle = try? FileHandle(forWritingTo: logPath) {
                handle.seekToEndOfFile()
                handle.write(data)
                try? handle.close()
            }
        } else {
            try? data.write(to: logPath)
        }
    }
}

private func micPermissionStatusString(_ status: AVAuthorizationStatus) -> String {
    switch status {
    case .notDetermined: return "notDetermined"
    case .restricted: return "restricted"
    case .denied: return "denied"
    case .authorized: return "authorized"
    @unknown default: return "unknown(\(status.rawValue))"
    }
}

struct SpeechRecognitionUpdate: Equatable {
    enum Kind: Equatable {
        case partial
        case final
        case failure
        case level
    }

    let kind: Kind
    let text: String
    let level: Float

    static func partial(_ text: String) -> SpeechRecognitionUpdate { .init(kind: .partial, text: text, level: 0) }
    static func final(_ text: String) -> SpeechRecognitionUpdate { .init(kind: .final, text: text, level: 0) }
    static func failure(_ message: String) -> SpeechRecognitionUpdate { .init(kind: .failure, text: message, level: 0) }
    static func level(_ value: Float) -> SpeechRecognitionUpdate { .init(kind: .level, text: "", level: value) }
}

struct AudioDevice: Identifiable, Equatable, Hashable {
    let id: String
    let name: String
    let isAirPodsMax: Bool
}

protocol SpeechRecognitionControlling {
    var currentAuthorizationStatus: SFSpeechRecognizerAuthorizationStatus { get }
    var isRecognizerAvailable: Bool { get }
    func requestAuthorization(_ completion: @escaping (SFSpeechRecognizerAuthorizationStatus) -> Void)
    func availableInputDevices() -> [AudioDevice]
    func startRecognition(handler: @escaping (SpeechRecognitionUpdate) -> Void) throws
    func stopRecognition()
}

final class AppleSpeechRecognitionController: SpeechRecognitionControlling {
    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-AU"))
    private let audioEngine = AVAudioEngine()
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?
    private var currentHandler: ((SpeechRecognitionUpdate) -> Void)?

    var currentAuthorizationStatus: SFSpeechRecognizerAuthorizationStatus { SFSpeechRecognizer.authorizationStatus() }
    var isRecognizerAvailable: Bool { recognizer?.isAvailable == true }

    func requestAuthorization(_ completion: @escaping (SFSpeechRecognizerAuthorizationStatus) -> Void) {
        SFSpeechRecognizer.requestAuthorization(completion)
    }

    func availableInputDevices() -> [AudioDevice] {
        var devices: [AudioDevice] = []
        
        // Get audio devices from CoreAudio
        var propertyAddress = AudioObjectPropertyAddress(
            mSelector: kAudioHardwarePropertyDevices,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        
        var dataSize: UInt32 = 0
        AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &propertyAddress, 0, nil, &dataSize)
        
        let deviceCount = Int(dataSize) / MemoryLayout<AudioDeviceID>.size
        var deviceIDs = [AudioDeviceID](repeating: 0, count: deviceCount)
        AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &propertyAddress, 0, nil, &dataSize, &deviceIDs)
        
        for deviceID in deviceIDs {
            // Check if it's an input device
            var inputAddress = AudioObjectPropertyAddress(
                mSelector: kAudioDevicePropertyStreamConfiguration,
                mScope: kAudioDevicePropertyScopeInput,
                mElement: kAudioObjectPropertyElementMain
            )
            
            var inputSize: UInt32 = 0
            if AudioObjectGetPropertyDataSize(deviceID, &inputAddress, 0, nil, &inputSize) == noErr && inputSize > 0 {
                // Get device name
                var nameAddress = AudioObjectPropertyAddress(
                    mSelector: kAudioDevicePropertyDeviceNameCFString,
                    mScope: kAudioObjectPropertyScopeGlobal,
                    mElement: kAudioObjectPropertyElementMain
                )
                
                var name: CFString?
                var nameSize = UInt32(MemoryLayout<CFString?>.size)
                _ = withUnsafeMutableBytes(of: &name) { nameBytes in
                    AudioObjectGetPropertyData(deviceID, &nameAddress, 0, nil, &nameSize, nameBytes.baseAddress!)
                }

                let deviceName = (name as String?) ?? "Unknown Input Device"
                let isAirPodsMax = deviceName.lowercased().contains("airpods max")
                
                devices.append(AudioDevice(id: String(deviceID), name: deviceName, isAirPodsMax: isAirPodsMax))
            }
        }
        
        if devices.isEmpty {
            devices.append(AudioDevice(id: "default", name: "Built-in Microphone", isAirPodsMax: false))
        }
        
        return devices
    }

    func startRecognition(handler: @escaping (SpeechRecognitionUpdate) -> Void) throws {
        // Clean up any existing session first
        stopRecognition()
        
        guard let recognizer = recognizer else {
            handler(.failure("Speech recognizer not available"))
            return
        }
        
        // Create recognition request
        recognitionRequest = SFSpeechAudioBufferRecognitionRequest()
        guard let recognitionRequest = recognitionRequest else {
            handler(.failure("Could not create recognition request"))
            return
        }
        
        recognitionRequest.shouldReportPartialResults = true
        recognitionRequest.requiresOnDeviceRecognition = false
        
        currentHandler = handler
        
        // Start recognition task
        recognitionTask = recognizer.recognitionTask(with: recognitionRequest) { [weak self] result, error in
            if let error = error {
                handler(.failure(error.localizedDescription))
                self?.stopRecognition()
                return
            }
            
            if let result = result {
                let transcript = result.bestTranscription.formattedString
                if result.isFinal {
                    handler(.final(transcript))
                    self?.stopRecognition()
                } else {
                    handler(.partial(transcript))
                }
            }
        }
        
        // Set up audio input
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { [weak self] buffer, _ in
            self?.recognitionRequest?.append(buffer)
            
            // Calculate audio level for visual feedback
            let channelData = buffer.floatChannelData?[0]
            let frameLength = Int(buffer.frameLength)
            if let data = channelData, frameLength > 0 {
                var sum: Float = 0
                for i in 0..<frameLength {
                    sum += abs(data[i])
                }
                let average = sum / Float(frameLength)
                let level = min(average * 10, 1.0) // Scale for visibility
                handler(.level(level))
            }
        }
        
        do {
            audioEngine.prepare()
            try audioEngine.start()
        } catch {
            stopRecognition()  // Clean up on failure
            throw error
        }
    }

    func stopRecognition() {
        audioEngine.stop()
        audioEngine.inputNode.removeTap(onBus: 0)
        recognitionRequest?.endAudio()
        recognitionRequest = nil
        recognitionTask?.cancel()
        recognitionTask = nil
        currentHandler = nil
    }
}

@MainActor
final class SpeechManager: ObservableObject {
    @Published var isListening = false
    @Published var currentTranscript = ""
    @Published var authorizationStatus: SFSpeechRecognizerAuthorizationStatus = .notDetermined
    @Published var errorMessage: String?
    @Published var inputDevices: [AudioDevice] = []
    @Published var selectedDevice: AudioDevice?
    @Published var audioLevel: Float = 0.0
    @Published var currentEngine: SpeechEngine = .appleDictation
    @Published var engineStatus: String = ""

    var onTranscriptFinalized: ((String) -> Void)?

    private var appleController: AppleSpeechRecognitionController
    private var whisperAPIEngine: WhisperAPIEngine?
    private var whisperCppEngine: WhisperCppEngine?
    private let fasterWhisperBridge = FasterWhisperBridge.shared
    private var audioRecorder: AVAudioRecorder?
    private var recordingURL: URL?
    private var openAIKey: String = ""

    init(requestAuthorizationOnInit: Bool = true) {
        logMic("=== SpeechManager INIT ===", level: .info)
        self.appleController = AppleSpeechRecognitionController()
        self.whisperCppEngine = WhisperCppEngine()
        authorizationStatus = appleController.currentAuthorizationStatus
        
        let micStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        logMic("Initial microphone status: \(micPermissionStatusString(micStatus))", level: .info)
        logMic("Initial speech auth status: \(authorizationStatus.rawValue)")
        
        if requestAuthorizationOnInit {
            logMic("Requesting speech authorization on init")
            requestAuthorization()
        }
        refreshDevices()
        updateEngineStatus()
        logMic("SpeechManager init complete")
    }
    
    func setOpenAIKey(_ key: String) {
        openAIKey = key
        whisperAPIEngine = key.isEmpty ? nil : WhisperAPIEngine(apiKey: key)
        updateEngineStatus()
    }
    
    func setEngine(_ engine: SpeechEngine) {
        currentEngine = engine
        updateEngineStatus()
    }
    
    private func updateEngineStatus() {
        switch currentEngine {
        case .appleDictation:
            engineStatus = appleController.isRecognizerAvailable ? "Ready" : "Not available"
        case .whisperKit:
            engineStatus = fasterWhisperBridge.isAvailable ? "Ready (Python faster-whisper)" : "Install faster-whisper for /usr/bin/python3"
        case .whisperAPI:
            engineStatus = openAIKey.isEmpty ? "Needs OpenAI key" : "Ready"
        case .whisperCpp:
            engineStatus = whisperCppEngine?.isAvailable == true ? "Ready" : "Install: brew install whisper-cpp"
        }
    }

    func requestAuthorization() {
        appleController.requestAuthorization { [weak self] status in
            Task { @MainActor in
                guard let self else { return }
                self.authorizationStatus = status
                self.errorMessage = status == .authorized ? nil : "Speech recognition not authorized. Enable in System Settings > Privacy > Speech Recognition."
            }
        }
    }

    func requestMicrophoneAccess(thenStartListening: Bool = false) {
        logMic("=== requestMicrophoneAccess() CALLED ===", level: .info)
        logMic("thenStartListening: \(thenStartListening)")
        
        // Log current status BEFORE request
        let statusBefore = AVCaptureDevice.authorizationStatus(for: .audio)
        logMic("Permission status BEFORE request: \(micPermissionStatusString(statusBefore))", level: .info)
        
        UserDefaults.standard.set(true, forKey: "BrainChatDidRequestMicrophoneAccess")
        let runtimeDir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("brain/agentic-brain/apps/BrainChat/runtime", isDirectory: true)
        try? FileManager.default.createDirectory(at: runtimeDir, withIntermediateDirectories: true)
        try? "requested".write(to: runtimeDir.appendingPathComponent("microphone-requested.txt"), atomically: true, encoding: .utf8)

        logMic("Calling AVCaptureDevice.requestAccess(for: .audio)...")
        
        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            // Log result immediately in callback (background thread)
            logMic("=== AVCaptureDevice.requestAccess CALLBACK ===", level: .info)
            logMic("Granted: \(granted)", level: .info)
            
            let statusAfter = AVCaptureDevice.authorizationStatus(for: .audio)
            logMic("Permission status AFTER request: \(micPermissionStatusString(statusAfter))", level: .info)
            
            Task { @MainActor in
                guard let self else {
                    logMic("Self is nil in callback, returning")
                    return
                }
                if granted {
                    logMic("Permission GRANTED - writing marker file", level: .info)
                    try? "granted".write(to: runtimeDir.appendingPathComponent("microphone-granted.txt"), atomically: true, encoding: .utf8)
                    // If user was trying to start listening, auto-start after permission granted
                    if thenStartListening {
                        logMic("thenStartListening=true, calling startListening()")
                        self.startListening()
                    }
                } else {
                    logMic("Permission DENIED by user or system", level: .error)
                    self.errorMessage = "Microphone access not authorized. Enable in System Settings > Privacy > Microphone."
                }
            }
        }
    }
    
    /// Check if microphone permission is currently granted
    func isMicrophoneAuthorized() -> Bool {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        logMic("Checking microphone authorization: \(micPermissionStatusString(status))")
        return status == .authorized
    }

    /// Request permission with completion handler (like KarenVoice)
    func requestMicrophonePermissionWithCompletion(completion: @Sendable @escaping (Bool) -> Void) {
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        logMic("requestMicrophonePermissionWithCompletion - current status: \(micPermissionStatusString(status))", level: .info)
        
        switch status {
        case .authorized:
            logMic("Already authorized, calling completion(true)")
            completion(true)
        case .notDetermined:
            logMic("Not determined, requesting access...")
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                logMic("Permission dialog result: \(granted)", level: .info)
                DispatchQueue.main.async {
                    completion(granted)
                }
            }
        case .denied, .restricted:
            logMic("Permission denied or restricted", level: .error)
            completion(false)
        @unknown default:
            completion(false)
        }
    }

    func refreshDevices() {
        let devices = appleController.availableInputDevices()
        let resolved = devices.isEmpty ? [AudioDevice(id: "default", name: "Built-in Microphone", isAirPodsMax: false)] : devices
        inputDevices = resolved
        if let airPods = resolved.first(where: { $0.isAirPodsMax }) {
            selectedDevice = airPods
        } else if let device = selectedDevice, !resolved.contains(device) {
            selectedDevice = resolved.first
        }
    }

    func startListening() {
        logMic("=== startListening() CALLED ===", level: .info)
        logMic("Current isListening state: \(isListening)")
        logMic("Current engine: \(currentEngine)")
        
        guard !isListening else {
            logMic("Already listening, returning early")
            return
        }
        
        // Log microphone permission status at entry
        let micStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        logMic("Microphone permission at startListening: \(micPermissionStatusString(micStatus))", level: .info)
        
        currentTranscript = ""
        errorMessage = nil
        audioLevel = 0
        isListening = true
        
        logMic("Set isListening = true, about to start engine")
        
        switch currentEngine {
        case .appleDictation:
            logMic("Starting Apple recognition engine")
            startAppleRecognition()
        case .whisperAPI:
            guard whisperAPIEngine != nil else {
                fallbackToAppleRecognition(reason: "Whisper API key is missing")
                return
            }
            logMic("Starting Whisper recording (engine: \(currentEngine))")
            startRecording()
        case .whisperCpp:
            guard whisperCppEngine?.isAvailable == true else {
                fallbackToAppleRecognition(reason: "whisper.cpp is unavailable")
                return
            }
            logMic("Starting Whisper recording (engine: \(currentEngine))")
            startRecording()
        case .whisperKit:
            guard fasterWhisperBridge.isAvailable else {
                fallbackToAppleRecognition(reason: "faster-whisper bridge is unavailable")
                return
            }
            logMic("Starting Whisper recording (engine: \(currentEngine))")
            startRecording()
        }
    }
    
    private func fallbackToAppleRecognition(reason: String) {
        logMic("Falling back to Apple Dictation: \(reason)", level: .info)
        engineStatus = "Falling back to Apple Dictation: \(reason)"
        currentEngine = .appleDictation
        startAppleRecognition()
    }

    private func startAppleRecognition() {
        logMic("=== startAppleRecognition() CALLED ===", level: .info)
        logMic("authorizationStatus: \(authorizationStatus.rawValue)")
        logMic("isRecognizerAvailable: \(appleController.isRecognizerAvailable)")
        
        // CHECK MIC PERMISSION FIRST - request if needed (like KarenVoice does)
        let micStatus = AVCaptureDevice.authorizationStatus(for: .audio)
        logMic("Microphone status: \(micPermissionStatusString(micStatus))", level: .info)
        
        switch micStatus {
        case .authorized:
            logMic("Mic authorized, proceeding...")
        case .notDetermined:
            logMic("Mic not determined - REQUESTING NOW", level: .info)
            requestMicrophoneAccess(thenStartListening: true)
            isListening = false
            errorMessage = "Requesting microphone permission..."
            return
        case .denied, .restricted:
            logMic("Mic denied/restricted", level: .error)
            errorMessage = "Microphone access denied. Enable in System Settings > Privacy > Microphone."
            isListening = false
            return
        @unknown default:
            logMic("Mic unknown status", level: .error)
            errorMessage = "Unknown microphone permission status."
            isListening = false
            return
        }
        
        guard authorizationStatus == .authorized else {
            logMic("Speech recognition NOT authorized", level: .error)
            errorMessage = "Speech recognition not authorized."
            isListening = false
            return
        }
        guard appleController.isRecognizerAvailable else {
            logMic("Speech recognizer NOT available", level: .error)
            errorMessage = "Speech recognizer is not available."
            isListening = false
            return
        }
        
        logMic("Starting Apple speech recognition...")
        
        do {
            try appleController.startRecognition { [weak self] update in
                Task { @MainActor in
                    self?.handle(update)
                }
            }
            logMic("Apple speech recognition started successfully", level: .info)
        } catch {
            logMic("Failed to start Apple recognition: \(error.localizedDescription)", level: .error)
            isListening = false
            errorMessage = "Failed to start: \(error.localizedDescription)"
        }
    }
    
    private func startRecording() {
        logMic("=== startRecording() CALLED ===", level: .info)
        
        // Check microphone permission BEFORE recording
        let status = AVCaptureDevice.authorizationStatus(for: .audio)
        logMic("Checking AVCaptureDevice.authorizationStatus(for: .audio)", level: .info)
        logMic("Current status: \(micPermissionStatusString(status)) (rawValue: \(status.rawValue))", level: .info)
        
        switch status {
        case .authorized:
            logMic("STATUS: authorized - proceeding with recording", level: .info)
            // Good to go
        case .notDetermined:
            logMic("STATUS: notDetermined - will request permission", level: .info)
            // Request permission and auto-start listening when granted
            requestMicrophoneAccess(thenStartListening: true)
            isListening = false
            errorMessage = "Requesting microphone permission..."
            logMic("Set isListening=false, errorMessage=requesting permission")
            return
        case .denied:
            logMic("STATUS: denied - user denied in System Settings", level: .error)
            errorMessage = "Microphone access denied. Enable in System Settings > Privacy > Microphone."
            isListening = false
            return
        case .restricted:
            logMic("STATUS: restricted - device policy restriction", level: .error)
            errorMessage = "Microphone access denied. Enable in System Settings > Privacy > Microphone."
            isListening = false
            return
        @unknown default:
            logMic("STATUS: unknown (\(status.rawValue)) - unexpected value!", level: .fault)
            errorMessage = "Unknown microphone permission status."
            isListening = false
            return
        }
        
        logMic("Permission OK - setting up AVAudioRecorder")
        
        // Record audio for Whisper transcription as PCM (16kHz mono 16-bit)
        let tempDir = FileManager.default.temporaryDirectory
        recordingURL = tempDir.appendingPathComponent("brain_chat_\(UUID().uuidString).wav")
        logMic("Recording URL: \(recordingURL?.path ?? "nil")")
        
        let settings: [String: Any] = [
            AVFormatIDKey: kAudioFormatLinearPCM,
            AVSampleRateKey: 16_000,
            AVNumberOfChannelsKey: 1,
            AVLinearPCMBitDepthKey: 16,
            AVLinearPCMIsFloatKey: false
        ]
        logMic("Audio settings: 16kHz mono 16-bit PCM")
        
        do {
            logMic("Creating AVAudioRecorder...")
            audioRecorder = try AVAudioRecorder(url: recordingURL!, settings: settings)
            audioRecorder?.isMeteringEnabled = true
            logMic("AVAudioRecorder created successfully")
            
            // Check audioRecorder.record() return value
            logMic("Calling audioRecorder.record()...")
            let recordStarted = audioRecorder?.record() == true
            logMic("audioRecorder.record() returned: \(recordStarted)", level: recordStarted ? .info : .error)
            
            guard recordStarted else {
                logMic("FAILED to start recording - record() returned false", level: .error)
                errorMessage = "Failed to start microphone capture."
                isListening = false
                return
            }
            
            logMic("Recording STARTED successfully!", level: .info)
            
            // Update audio level periodically
            Timer.scheduledTimer(withTimeInterval: 0.1, repeats: true) { [weak self] timer in
                Task { @MainActor in
                    guard let self = self, self.isListening else {
                        timer.invalidate()
                        return
                    }
                    self.audioRecorder?.updateMeters()
                    let level = self.audioRecorder?.averagePower(forChannel: 0) ?? -160
                    let normalized = max(0, min(1, (level + 50) / 50))
                    self.audioLevel = Float(normalized)
                }
            }
        } catch {
            logMic("EXCEPTION creating/starting AVAudioRecorder: \(error.localizedDescription)", level: .error)
            logMic("Error details: \(error)", level: .error)
            errorMessage = "Failed to start recording: \(error.localizedDescription)"
            isListening = false
        }
    }

    func stopListening() {
        logMic("=== stopListening() CALLED ===", level: .info)
        logMic("isListening: \(isListening), currentEngine: \(currentEngine)")
        
        guard isListening else {
            logMic("Not listening, returning early")
            return
        }
        
        switch currentEngine {
        case .appleDictation:
            logMic("Stopping Apple recognition")
            appleController.stopRecognition()
            isListening = false
            audioLevel = 0
        case .whisperAPI, .whisperCpp, .whisperKit:
            logMic("Stopping Whisper recording and transcribing")
            stopRecordingAndTranscribe()
        }
        logMic("stopListening() complete")
    }
    
    private func stopRecordingAndTranscribe() {
        audioRecorder?.stop()
        audioRecorder = nil
        audioLevel = 0
        
        guard let url = recordingURL else {
            isListening = false
            errorMessage = "No recording found"
            return
        }
        
        // Copy values for detached task to avoid data races
        let engine = self.currentEngine
        let whisperAPI = self.whisperAPIEngine
        let whisperCpp = self.whisperCppEngine
        let fasterWhisperBridge = self.fasterWhisperBridge
        
        Task {
            do {
                let transcript: String
                
                switch engine {
                case .whisperAPI:
                    guard let api = whisperAPI else {
                        throw WhisperError.missingAPIKey
                    }
                    transcript = try await api.transcribe(audioURL: url)
                    
                case .whisperCpp:
                    guard let cpp = whisperCpp else {
                        throw WhisperError.recordingFailed
                    }
                    transcript = try await cpp.transcribe(audioURL: url)

                case .whisperKit:
                    guard fasterWhisperBridge.isAvailable else {
                        throw WhisperError.apiError(1, "faster-whisper bridge is not available")
                    }
                    transcript = try await fasterWhisperBridge.transcribe(audioURL: url)
                    
                default:
                    throw WhisperError.recordingFailed
                }
                
                self.currentTranscript = transcript
                self.isListening = false
                if !transcript.isEmpty {
                    self.onTranscriptFinalized?(transcript)
                }
            } catch {
                self.errorMessage = error.localizedDescription
                self.isListening = false
            }
            
            // Cleanup
            try? FileManager.default.removeItem(at: url)
            self.recordingURL = nil
        }
    }

    func handle(_ update: SpeechRecognitionUpdate) {
        switch update.kind {
        case .partial:
            currentTranscript = update.text
        case .final:
            currentTranscript = update.text
            isListening = false
            audioLevel = 0
            if !update.text.isEmpty {
                onTranscriptFinalized?(update.text)
            }
        case .failure:
            errorMessage = update.text
            isListening = false
            audioLevel = 0
        case .level:
            audioLevel = min(max(update.level, 0), 1)
        }
    }
}
