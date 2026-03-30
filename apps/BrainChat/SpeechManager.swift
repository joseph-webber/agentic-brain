import AVFoundation
import Combine
import CoreAudio
import Foundation
import Speech

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
                
                var name: CFString = "" as CFString
                var nameSize = UInt32(MemoryLayout<CFString>.size)
                AudioObjectGetPropertyData(deviceID, &nameAddress, 0, nil, &nameSize, &name)
                
                let deviceName = name as String
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
        guard let recognizer = recognizer else {
            handler(.failure("Speech recognizer not available"))
            return
        }
        
        // Cancel any existing task
        recognitionTask?.cancel()
        recognitionTask = nil
        
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
        
        audioEngine.prepare()
        try audioEngine.start()
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

    var onTranscriptFinalized: ((String) -> Void)?

    private let controller: SpeechRecognitionControlling

    init(controller: SpeechRecognitionControlling = AppleSpeechRecognitionController(), requestAuthorizationOnInit: Bool = true) {
        self.controller = controller
        authorizationStatus = controller.currentAuthorizationStatus
        if requestAuthorizationOnInit {
            requestAuthorization()
        }
        refreshDevices()
    }

    func requestAuthorization() {
        controller.requestAuthorization { [weak self] status in
            Task { @MainActor in
                guard let self else { return }
                self.authorizationStatus = status
                self.errorMessage = status == .authorized ? nil : "Speech recognition not authorized. Enable in System Settings > Privacy > Speech Recognition."
            }
        }
    }

    func requestMicrophoneAccess() {
        UserDefaults.standard.set(true, forKey: "BrainChatDidRequestMicrophoneAccess")
        let runtimeDir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("brain/agentic-brain/apps/BrainChat/runtime", isDirectory: true)
        try? FileManager.default.createDirectory(at: runtimeDir, withIntermediateDirectories: true)
        try? "requested".write(to: runtimeDir.appendingPathComponent("microphone-requested.txt"), atomically: true, encoding: .utf8)

        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            Task { @MainActor in
                guard let self else { return }
                if !granted {
                    self.errorMessage = "Microphone access not authorized. Enable in System Settings > Privacy > Microphone."
                }
            }
        }
    }

    func refreshDevices() {
        let devices = controller.availableInputDevices()
        let resolved = devices.isEmpty ? [AudioDevice(id: "default", name: "Built-in Microphone", isAirPodsMax: false)] : devices
        inputDevices = resolved
        if let airPods = resolved.first(where: { $0.isAirPodsMax }) {
            selectedDevice = airPods
        } else if selectedDevice == nil || !resolved.contains(selectedDevice!) {
            selectedDevice = resolved.first
        }
    }

    func startListening() {
        guard authorizationStatus == .authorized else {
            errorMessage = "Speech recognition not authorized."
            return
        }
        guard !isListening else { return }
        guard controller.isRecognizerAvailable else {
            errorMessage = "Speech recognizer is not available."
            return
        }

        do {
            currentTranscript = ""
            errorMessage = nil
            audioLevel = 0
            isListening = true
            try controller.startRecognition { [weak self] update in
                Task { @MainActor in
                    self?.handle(update)
                }
            }
        } catch {
            isListening = false
            errorMessage = "Failed to start: \(error.localizedDescription)"
        }
    }

    func stopListening() {
        controller.stopRecognition()
        isListening = false
        audioLevel = 0
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
