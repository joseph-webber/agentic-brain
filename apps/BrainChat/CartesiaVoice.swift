import AVFoundation
import Combine
import Foundation

struct CartesiaVoiceOption: Identifiable, Hashable, Codable {
    let voiceID: String
    let name: String
    let accentDescription: String
    let fallbackVoiceName: String
    let isDefault: Bool

    var id: String { voiceID }

    static let curated: [CartesiaVoiceOption] = [
        CartesiaVoiceOption(
            voiceID: "8985388c-1332-4ce7-8d55-789628aa3df4",
            name: "Australian Narrator Lady",
            accentDescription: "Warm Australian female voice, closest to Karen",
            fallbackVoiceName: "Karen",
            isDefault: true
        ),
        CartesiaVoiceOption(
            voiceID: "043cfc81-d69f-4bee-ae1e-7862cb358650",
            name: "Australian Woman",
            accentDescription: "Bright Australian female voice",
            fallbackVoiceName: "Karen",
            isDefault: false
        ),
        CartesiaVoiceOption(
            voiceID: "4d2fd738-3b3d-4368-957a-bb4805275bd9",
            name: "British Narration Lady",
            accentDescription: "Smooth British female voice",
            fallbackVoiceName: "Samantha",
            isDefault: false
        ),
        CartesiaVoiceOption(
            voiceID: "71a7ad14-091c-4e8e-a314-022ece01c121",
            name: "British Reading Lady",
            accentDescription: "Clear British reading voice",
            fallbackVoiceName: "Samantha",
            isDefault: false
        ),
        CartesiaVoiceOption(
            voiceID: "a01c369f-6d2d-4185-bc20-b32c225eab70",
            name: "British Customer Support Lady",
            accentDescription: "Friendly British support voice",
            fallbackVoiceName: "Moira",
            isDefault: false
        ),
    ]

    static let defaultOption = curated.first(where: { $0.isDefault }) ?? curated[0]
}

protocol CartesiaAudioPlaying: AnyObject {
    var onStreamFinished: ((UUID) -> Void)? { get set }
    func prepareStream(id: UUID, sampleRate: Double, channels: AVAudioChannelCount)
    func appendPCMChunk(_ data: Data, for id: UUID) throws
    func finishStream(id: UUID)
    func cancelCurrentSpeech()
}

extension AudioPlayer: CartesiaAudioPlaying {}

protocol FallbackSpeechRunning {
    func speak(text: String, voice: String, rate: Int, completion: @escaping @Sendable (Int32) -> Void) throws
    func cancel()
}

final class SayFallbackSpeaker: FallbackSpeechRunning {
    private var runningProcess: Process?

    func speak(text: String, voice: String, rate: Int, completion: @escaping @Sendable (Int32) -> Void) throws {
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/say")
        task.arguments = ["-v", voice, "-r", String(rate), text]
        task.terminationHandler = { process in
            DispatchQueue.main.async {
                completion(process.terminationStatus)
            }
        }
        runningProcess = task
        try task.run()
    }

    func cancel() {
        runningProcess?.terminate()
        runningProcess = nil
    }
}

final class CartesiaVoice: NSObject, ObservableObject {
    enum CartesiaError: LocalizedError, Equatable {
        case missingAPIKey
        case invalidResponse
        case apiFailure(String)

        var errorDescription: String? {
            switch self {
            case .missingAPIKey:
                return "Cartesia API key is missing. Saved voice playback will fall back to macOS speech until you store the key in Keychain."
            case .invalidResponse:
                return "Cartesia returned an invalid response."
            case .apiFailure(let message):
                return message
            }
        }
    }

    @Published private(set) var availableVoices: [CartesiaVoiceOption] = CartesiaVoiceOption.curated
    @Published var selectedVoiceID: String = CartesiaVoiceOption.defaultOption.voiceID
    @Published private(set) var statusMessage = "Cartesia ready"
    @Published private(set) var hasStoredAPIKey = false
    @Published private(set) var isSpeaking = false

    let audioPlayer: AudioPlayer

    private struct Utterance {
        let id = UUID()
        let text: String
        let voice: CartesiaVoiceOption
        let timestamp = Date()  // Track when utterance was queued
    }

    private enum Constants {
        static let endpoint: URL = {
            guard let url = URL(string: "https://api.cartesia.ai/tts/bytes") else {
                fatalError("Invalid hardcoded URL - this is a programming error")
            }
            return url
        }()
        static let apiVersion = "2026-03-01"
        static let sampleRate = 24_000
        static let channels = 1
        static let provider = "cartesia"
        // OPTIMIZATION: Streaming TTS - start speaking after first 50ms of audio
        static let minimumAudioBufferForPlayback = 1200  // ~50ms at 24kHz
    }

    private let sessionFactory: (URLSessionDataDelegate) -> URLSession
    private lazy var session: URLSession = sessionFactory(self)
    private let audioOutput: CartesiaAudioPlaying
    private let keyManager: APIKeyManaging
    private let fallbackSpeaker: FallbackSpeechRunning

    private var queuedUtterances: [Utterance] = []
    private var activeUtterance: Utterance?
    private var activeTask: URLSessionDataTask?
    private var activeStatusCode: Int?
    private var activeErrorBuffer = Data()
    private var activeAudioBytes = 0
    // OPTIMIZATION: Track when to start playback during streaming
    private var playbackStarted = false
    private var utteranceStartTime: Date?

    init(
        audioPlayer: AudioPlayer = AudioPlayer(),
        audioOutput: CartesiaAudioPlaying? = nil,
        keyManager: APIKeyManaging = APIKeyManager.shared,
        fallbackSpeaker: FallbackSpeechRunning = SayFallbackSpeaker(),
        sessionFactory: ((URLSessionDataDelegate) -> URLSession)? = nil
    ) {
        self.audioPlayer = audioPlayer
        self.audioOutput = audioOutput ?? audioPlayer
        self.keyManager = keyManager
        self.fallbackSpeaker = fallbackSpeaker
        self.sessionFactory = sessionFactory ?? { delegate in
            let configuration = URLSessionConfiguration.default
            configuration.timeoutIntervalForRequest = 45
            configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
            return URLSession(configuration: configuration, delegate: delegate, delegateQueue: nil)
        }
        super.init()
        self.audioOutput.onStreamFinished = { [weak self] id in
            self?.handleStreamFinished(id: id)
        }
        refreshConfiguration()
    }

    func refreshConfiguration() {
        hasStoredAPIKey = keyManager.hasKey(for: Constants.provider)
        if !hasStoredAPIKey {
            statusMessage = CartesiaError.missingAPIKey.localizedDescription
        } else if statusMessage == CartesiaError.missingAPIKey.localizedDescription {
            statusMessage = "Cartesia ready"
        }
    }

    func selectVoice(matching preferredVoiceName: String) {
        let normalized = preferredVoiceName.replacingOccurrences(of: " (Premium)", with: "")
        if let match = availableVoices.first(where: { option in
            option.name.localizedCaseInsensitiveContains(normalized)
                || option.fallbackVoiceName.localizedCaseInsensitiveContains(normalized)
        }) {
            selectedVoiceID = match.voiceID
        } else {
            selectedVoiceID = CartesiaVoiceOption.defaultOption.voiceID
        }
    }

    func setAPIKey(_ apiKey: String) throws {
        try keyManager.setKey(apiKey, for: Constants.provider)
        hasStoredAPIKey = true
        statusMessage = "Cartesia API key saved to Keychain"
    }

    func setStatusMessage(_ message: String) {
        statusMessage = message
    }

    func removeAPIKey() {
        keyManager.removeKey(for: Constants.provider)
        hasStoredAPIKey = false
        statusMessage = "Removed Cartesia API key from Keychain"
    }

    func enqueue(_ text: String, voiceID: String? = nil) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let voice = availableVoices.first(where: { $0.voiceID == (voiceID ?? selectedVoiceID) }) ?? CartesiaVoiceOption.defaultOption
        queuedUtterances.append(Utterance(text: trimmed, voice: voice))
        statusMessage = queuedUtterances.count > 1 || activeUtterance != nil
            ? "Queued \(queuedUtterances.count + (activeUtterance == nil ? 0 : 1)) utterances"
            : "Queued 1 utterance"
        startNextUtteranceIfIdle()
    }

    func cancelCurrentSpeech(clearQueue: Bool = false) {
        activeTask?.cancel()
        activeTask = nil
        fallbackSpeaker.cancel()
        audioOutput.cancelCurrentSpeech()
        activeUtterance = nil
        activeStatusCode = nil
        activeErrorBuffer = Data()
        activeAudioBytes = 0
        if clearQueue {
            queuedUtterances.removeAll()
        }
        isSpeaking = false
        statusMessage = clearQueue ? "Speech cancelled and queue cleared" : "Speech cancelled"
    }

    func previewCurrentVoice(with text: String = "G'day Joseph, Cartesia is online and ready to speak.") {
        enqueue(text, voiceID: selectedVoiceID)
    }

    private func startNextUtteranceIfIdle() {
        guard activeUtterance == nil, let next = queuedUtterances.first else { return }
        queuedUtterances.removeFirst()
        activeUtterance = next

        guard let apiKey = keyManager.key(for: Constants.provider), !apiKey.isEmpty else {
            statusMessage = CartesiaError.missingAPIKey.localizedDescription
            startFallbackSpeech(for: next, reason: "missing Cartesia API key")
            return
        }

        do {
            let request = try makeURLRequest(for: next, apiKey: apiKey)
            audioOutput.prepareStream(id: next.id, sampleRate: Double(Constants.sampleRate), channels: AVAudioChannelCount(Constants.channels))
            let task = session.dataTask(with: request)
            activeTask = task
            activeStatusCode = nil
            activeErrorBuffer = Data()
            activeAudioBytes = 0
            playbackStarted = false  // OPTIMIZATION: Reset for new utterance
            utteranceStartTime = Date()  // OPTIMIZATION: Track start time
            isSpeaking = true
            statusMessage = "Speaking with Cartesia: \(next.voice.name)"
            task.resume()
        } catch {
            startFallbackSpeech(for: next, reason: error.localizedDescription)
        }
    }

    private func makeURLRequest(for utterance: Utterance, apiKey: String) throws -> URLRequest {
        var request = URLRequest(url: Constants.endpoint)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "X-API-Key")
        request.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
        request.setValue(Constants.apiVersion, forHTTPHeaderField: "Cartesia-Version")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/octet-stream", forHTTPHeaderField: "Accept")
        let payload: [String: Any] = [
            "text": utterance.text,
            "transcript": utterance.text,
            "voice_id": utterance.voice.voiceID,
            "voice": [
                "mode": "id",
                "id": utterance.voice.voiceID,
            ],
            "model": "sonic-2",
            "model_id": "sonic-2",
            "language": "en",
            "output_format": [
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": Constants.sampleRate,
            ],
        ]
        request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [.fragmentsAllowed])
        return request
    }

    private func startFallbackSpeech(for utterance: Utterance, reason: String) {
        activeTask?.cancel()
        activeTask = nil
        audioOutput.cancelCurrentSpeech()
        activeStatusCode = nil
        activeErrorBuffer = Data()
        activeAudioBytes = 0

        do {
            isSpeaking = true
            // OPTIMIZATION: Use faster fallback rate (185 wpm) for quick response
            statusMessage = "Using macOS fallback voice because Cartesia failed: \(reason)"
            try fallbackSpeaker.speak(text: utterance.text, voice: utterance.voice.fallbackVoiceName, rate: 185) { [weak self] exitCode in
                guard let self else { return }
                self.statusMessage = exitCode == 0 ? "Finished via fallback voice" : "Fallback speech failed with exit code \(exitCode)"
                self.completeUtterance(id: utterance.id)
            }
        } catch {
            statusMessage = "Cartesia and fallback speech both failed: \(error.localizedDescription)"
            completeUtterance(id: utterance.id)
        }
    }

    private func handleStreamFinished(id: UUID) {
        guard activeUtterance?.id == id else { return }
        completeUtterance(id: id)
    }

    private func completeUtterance(id: UUID) {
        guard activeUtterance?.id == id else { return }
        activeUtterance = nil
        activeTask = nil
        activeStatusCode = nil
        activeErrorBuffer = Data()
        activeAudioBytes = 0
        startNextUtteranceIfIdle()
        if activeUtterance == nil {
            isSpeaking = false
        }
    }

    private func handleNetworkFailure(_ message: String) {
        guard let activeUtterance else {
            isSpeaking = false
            statusMessage = message
            return
        }
        startFallbackSpeech(for: activeUtterance, reason: message)
    }
}

extension CartesiaVoice: URLSessionDataDelegate {
    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive response: URLResponse, completionHandler: @escaping (URLSession.ResponseDisposition) -> Void) {
        guard dataTask == activeTask else {
            completionHandler(.cancel)
            return
        }
        if let http = response as? HTTPURLResponse {
            activeStatusCode = http.statusCode
        }
        completionHandler(.allow)
    }

    func urlSession(_ session: URLSession, dataTask: URLSessionDataTask, didReceive data: Data) {
        guard dataTask == activeTask else { return }
        let status = activeStatusCode ?? 0
        if (200..<300).contains(status) {
            guard let utterance = activeUtterance else { return }
            do {
                activeAudioBytes += data.count
                try audioOutput.appendPCMChunk(data, for: utterance.id)
                
                // OPTIMIZATION: Start playback after collecting enough audio (50ms buffer)
                if !playbackStarted && activeAudioBytes >= Constants.minimumAudioBufferForPlayback {
                    playbackStarted = true
                    let elapsed = Date().timeIntervalSince(utteranceStartTime ?? Date())
                    statusMessage = "Cartesia: Started speaking after \(Int(elapsed * 1000))ms"
                }
            } catch {
                handleNetworkFailure(error.localizedDescription)
            }
        } else {
            activeErrorBuffer.append(data)
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        guard task == activeTask else { return }

        if let error {
            if (error as NSError).code == NSURLErrorCancelled {
                return
            }
            handleNetworkFailure(error.localizedDescription)
            return
        }

        let status = activeStatusCode ?? 0
        guard (200..<300).contains(status) else {
            let body = String(data: activeErrorBuffer, encoding: .utf8) ?? "HTTP \(status)"
            handleNetworkFailure("Cartesia request failed: \(body)")
            return
        }

        guard let utterance = activeUtterance, activeAudioBytes > 0 else {
            handleNetworkFailure(CartesiaError.invalidResponse.localizedDescription)
            return
        }

        statusMessage = "Finishing Cartesia audio playback"
        audioOutput.finishStream(id: utterance.id)
    }
}
