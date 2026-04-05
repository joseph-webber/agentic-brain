import XCTest
@testable import VoiceTestLib

// MARK: - MockVoiceSynthesizer

/// Standalone voice synthesizer mock for CI testing
final class MockVoiceSynthesizer {
    var selectedVoice: String = "Karen (Premium)"
    private(set) var spokenTexts: [String] = []
    private(set) var stopCallCount = 0
    private(set) var isSpeaking = false

    func speak(_ text: String) {
        spokenTexts.append(text)
        isSpeaking = true
    }

    func stop() {
        stopCallCount += 1
        isSpeaking = false
    }
}

// MARK: - MockSpeechRecognitionController

/// Simulates Apple's SFSpeechRecognizer for CI without hardware
final class MockSpeechRecognitionController {
    var authorizationStatus: String = "authorized"
    var isRecognizerAvailable: Bool = true
    var recognitionHandler: ((SpeechRecognitionUpdate) -> Void)?

    private(set) var startCallCount = 0
    private(set) var stopCallCount = 0
    private(set) var isRecognising = false
    private(set) var authorizationRequestCount = 0

    func requestAuthorization(_ completion: @escaping (String) -> Void) {
        authorizationRequestCount += 1
        completion(authorizationStatus)
    }

    func availableInputDevices() -> [TestAudioDevice] {
        [
            TestAudioDevice(id: "built-in", name: "Built-in Microphone"),
            TestAudioDevice(id: "airpods", name: "User's AirPods Max", isAirPodsMax: true),
        ]
    }

    func startRecognition() throws {
        guard authorizationStatus == "authorized" else {
            throw MockSpeechError.notAuthorized
        }
        guard isRecognizerAvailable else {
            throw MockSpeechError.recognizerUnavailable
        }
        isRecognising = true
        startCallCount += 1
    }

    func stopRecognition() {
        isRecognising = false
        stopCallCount += 1
    }

    func simulatePartialTranscript(_ text: String) {
        recognitionHandler?(.partial(text))
    }

    func simulateFinalTranscript(_ text: String) {
        recognitionHandler?(.final(text))
    }

    func simulateFailure(_ message: String) {
        recognitionHandler?(.failure(message))
    }

    func simulateAudioLevel(_ level: Float) {
        recognitionHandler?(.level(level))
    }
}

enum MockSpeechError: LocalizedError, Equatable {
    case notAuthorized
    case recognizerUnavailable

    var errorDescription: String? {
        switch self {
        case .notAuthorized: return "Speech recognition not authorized"
        case .recognizerUnavailable: return "Speech recognizer unavailable"
        }
    }
}

// MARK: - MockAudioOutput

/// Captures TTS/PCM output calls without playing real audio
final class MockAudioOutput {
    struct StreamRecord: Equatable {
        let id: UUID
        let sampleRate: Double
        let channels: Int
    }

    struct ChunkRecord {
        let id: UUID
        let byteCount: Int
    }

    private(set) var preparedStreams: [StreamRecord] = []
    private(set) var appendedChunks: [ChunkRecord] = []
    private(set) var finishedStreamIDs: [UUID] = []
    private(set) var cancelCallCount = 0
    private(set) var isPlaying = false

    var onStreamFinished: ((UUID) -> Void)?

    func prepareStream(id: UUID, sampleRate: Double = 24_000, channels: Int = 1) {
        preparedStreams.append(StreamRecord(id: id, sampleRate: sampleRate, channels: channels))
    }

    func appendPCMChunk(_ data: Data, for id: UUID) throws {
        guard !data.isEmpty else { throw MockAudioError.invalidChunk }
        appendedChunks.append(ChunkRecord(id: id, byteCount: data.count))
        isPlaying = true
    }

    func finishStream(id: UUID) {
        finishedStreamIDs.append(id)
        isPlaying = false
        onStreamFinished?(id)
    }

    func cancelCurrentSpeech() {
        cancelCallCount += 1
        isPlaying = false
        preparedStreams.removeAll()
        appendedChunks.removeAll()
    }
}

enum MockAudioError: LocalizedError {
    case invalidChunk
    var errorDescription: String? { "Invalid audio chunk" }
}

// MARK: - MockAirPods

/// Simulates AirPods Max connection and routing for CI
final class MockAirPods {
    var isConnected: Bool = false
    var deviceName: String = "User's AirPods Max"
    var batteryPercent: Int? = 85
    var noiseControlMode: String = "noise-cancellation"

    private(set) var routeAllCallCount = 0
    private(set) var routeInputCallCount = 0
    private(set) var monitoringActive = false
    private(set) var stateChangeCount = 0

    var onStateChange: ((Bool) -> Void)?
    var onNotification: ((String) -> Void)?

    func currentState() -> (connected: Bool, deviceName: String?, battery: Int?) {
        (connected: isConnected, deviceName: isConnected ? deviceName : nil, battery: isConnected ? batteryPercent : nil)
    }

    func routeAllAudioToAirPods() throws {
        guard isConnected else { throw MockAirPodsError.notConnected }
        routeAllCallCount += 1
    }

    func routeAirPodsInput() throws {
        guard isConnected else { throw MockAirPodsError.notConnected }
        routeInputCallCount += 1
    }

    func startMonitoring() { monitoringActive = true }
    func stopMonitoring() { monitoringActive = false }

    func simulateConnect() {
        let wasConnected = isConnected
        isConnected = true
        if !wasConnected {
            stateChangeCount += 1
            onStateChange?(true)
            onNotification?("AirPods Max connected. Audio is routed and ready again.")
        }
    }

    func simulateDisconnect() {
        let wasConnected = isConnected
        isConnected = false
        if wasConnected {
            stateChangeCount += 1
            onStateChange?(false)
            onNotification?("AirPods Max disconnected. Listening is paused until they reconnect.")
        }
    }

    func simulateBatteryChange(_ percent: Int) {
        batteryPercent = percent
        stateChangeCount += 1
    }
}

enum MockAirPodsError: LocalizedError, Equatable {
    case notConnected
    var errorDescription: String? { "AirPods Max not connected" }
}

// MARK: - MockVoiceFallbackSpeaker

/// Captures /usr/bin/say fallback calls
final class MockVoiceFallbackSpeaker {
    struct SpeechCall {
        let text: String
        let voice: String
        let rate: Int
    }

    private(set) var speechCalls: [SpeechCall] = []
    private(set) var cancelCallCount = 0
    var shouldFail = false

    func speak(text: String, voice: String, rate: Int, completion: @escaping (Int32) -> Void) throws {
        if shouldFail { throw MockSpeechError.recognizerUnavailable }
        speechCalls.append(SpeechCall(text: text, voice: voice, rate: rate))
        completion(0)
    }

    func cancel() { cancelCallCount += 1 }
}

// MARK: - MockVoiceAIClient

final class MockVoiceAIClient: AIClientProtocol {
    var responses: [String: String] = [:]
    private(set) var callCount = 0
    private(set) var lastMessage: String?
    var shouldFail = false
    var latencyMs: UInt64 = 0

    func sendMessage(_ message: String, model: String, endpoint: String,
                     completion: @escaping (Result<String, Error>) -> Void) {
        callCount += 1
        lastMessage = message

        if shouldFail {
            completion(.failure(NSError(domain: "MockAI", code: -1,
                                        userInfo: [NSLocalizedDescriptionKey: "AI service unavailable"])))
            return
        }

        let response = responses[message] ?? "Mock response to: \(message)"
        if latencyMs > 0 {
            DispatchQueue.global().asyncAfter(deadline: .now() + .milliseconds(Int(latencyMs))) {
                completion(.success(response))
            }
        } else {
            completion(.success(response))
        }
    }
}

// MARK: - MockConversationStore

final class MockConversationStore {
    var messages: [TestChatMessage] = []
    var isProcessing = false

    @discardableResult
    func addMessage(role: TestChatMessage.Role, content: String) -> UUID {
        let msg = TestChatMessage(role: role, content: content)
        messages.append(msg)
        return msg.id
    }

    func appendToLastAssistant(_ delta: String) {
        guard let lastIndex = messages.lastIndex(where: { $0.role == .assistant }) else { return }
        let old = messages[lastIndex]
        messages[lastIndex] = TestChatMessage(role: .assistant, content: old.content + delta)
    }

    func clear() {
        messages.removeAll()
        messages.append(TestChatMessage(role: .system, content: "Conversation cleared."))
    }

    var userMessages: [TestChatMessage] { messages.filter { $0.role == .user } }
    var assistantMessages: [TestChatMessage] { messages.filter { $0.role == .assistant } }
    var messageCount: Int { messages.count }
}

// MARK: - VoiceTestHelpers

enum VoiceTestHelpers {
    static let karenVoiceID = "com.apple.voice.premium.en-AU.Karen"
    static let defaultSpeechRate: Float = 160.0
    static let baliSpaRate: Float = 150.0
    static let partyRate: Float = 180.0
    static let cartesiaSampleRate: Double = 24_000
    static let captureSampleRate: Double = 48_000

    static func makePCMData(frameCount: Int = 480, channels: Int = 1) -> Data {
        let bytesPerSample = MemoryLayout<Int16>.size
        let totalBytes = frameCount * channels * bytesPerSample
        var data = Data(count: totalBytes)
        data.withUnsafeMutableBytes { buffer in
            let samples = buffer.bindMemory(to: Int16.self)
            for i in 0..<(frameCount * channels) {
                let t = Double(i) / Double(frameCount * channels)
                samples[i] = Int16(sin(t * .pi * 2 * 440) * 16000)
            }
        }
        return data
    }

    static func makeEmptyPCMData() -> Data { Data() }
}
