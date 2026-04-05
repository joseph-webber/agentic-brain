import AppKit
import AVFoundation
import Combine
import Foundation

/// Runs a block on the main actor; synchronous when already on the main thread, otherwise dispatched.
private func scheduleOnMain(_ work: @escaping @MainActor @Sendable () -> Void) {
    if Thread.isMainThread {
        MainActor.assumeIsolated { work() }
    } else {
        DispatchQueue.main.async {
            MainActor.assumeIsolated { work() }
        }
    }
}

protocol AudioFilePlaying: AnyObject {
    func playAudioFile(at url: URL, completion: @escaping @Sendable (Result<Void, Error>) -> Void) throws
    func stop()
}

final class AVAudioFilePlayer: NSObject, AudioFilePlaying, AVAudioPlayerDelegate {
    private var player: AVAudioPlayer?
    private var completion: ((Result<Void, Error>) -> Void)?

    func playAudioFile(at url: URL, completion: @escaping @Sendable (Result<Void, Error>) -> Void) throws {
        stop()
        self.completion = completion
        let player = try AVAudioPlayer(contentsOf: url)
        player.delegate = self
        guard player.prepareToPlay(), player.play() else {
            throw NSError(domain: "BrainChat.AudioFilePlayer", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unable to start audio playback."])
        }
        self.player = player
    }

    func stop() {
        player?.stop()
        player = nil
        completion = nil
    }

    func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        let callback = completion
        completion = nil
        self.player = nil
        callback?(flag ? .success(()) : .failure(NSError(domain: "BrainChat.AudioFilePlayer", code: 2, userInfo: [NSLocalizedDescriptionKey: "Audio playback finished unsuccessfully."])))
    }

    func audioPlayerDecodeErrorDidOccur(_ player: AVAudioPlayer, error: Error?) {
        let callback = completion
        completion = nil
        self.player = nil
        callback?(.failure(error ?? NSError(domain: "BrainChat.AudioFilePlayer", code: 3, userInfo: [NSLocalizedDescriptionKey: "Audio playback failed."])))
    }
}

protocol PiperCommandRunning: AnyObject {
    var isAvailable: Bool { get }
    var unavailableReason: String { get }
    func synthesize(text: String, preferredVoiceName: String, outputURL: URL, completion: @escaping @Sendable (Result<Void, Error>) -> Void)
}

final class ShellPiperCommandRunner: PiperCommandRunning {
    private let fileManager: FileManager

    init(fileManager: FileManager = .default) {
        self.fileManager = fileManager
    }

    var isAvailable: Bool {
        resolveBinaryPath() != nil && resolveModelPath(preferredVoiceName: "Karen") != nil
    }

    var unavailableReason: String {
        if resolveBinaryPath() == nil {
            return "Install Piper TTS to enable this engine"
        }
        if resolveModelPath(preferredVoiceName: "Karen") == nil {
            return "Install a Piper voice model to enable this engine"
        }
        return "Ready"
    }

    func synthesize(text: String, preferredVoiceName: String, outputURL: URL, completion: @escaping @Sendable (Result<Void, Error>) -> Void) {
        guard let executablePath = resolveBinaryPath() else {
            completion(.failure(NSError(domain: "BrainChat.Piper", code: 1, userInfo: [NSLocalizedDescriptionKey: unavailableReason])))
            return
        }
        guard let modelPath = resolveModelPath(preferredVoiceName: preferredVoiceName) else {
            completion(.failure(NSError(domain: "BrainChat.Piper", code: 2, userInfo: [NSLocalizedDescriptionKey: unavailableReason])))
            return
        }

        let process = Process()
        process.executableURL = URL(fileURLWithPath: executablePath)
        process.arguments = ["--model", modelPath, "--output_file", outputURL.path]

        let stdin = Pipe()
        let stderr = Pipe()
        process.standardInput = stdin
        process.standardError = stderr

        process.terminationHandler = { process in
            let errorData = stderr.fileHandleForReading.readDataToEndOfFile()
            if process.terminationStatus == 0 {
                completion(.success(()))
            } else {
                let message = String(data: errorData, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines)
                completion(.failure(NSError(domain: "BrainChat.Piper", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: message?.isEmpty == false ? message! : "Piper synthesis failed."])))
            }
        }

        do {
            try process.run()
            if let data = text.data(using: .utf8) {
                stdin.fileHandleForWriting.write(data)
            }
            try? stdin.fileHandleForWriting.close()
        } catch {
            completion(.failure(error))
        }
    }

    private func resolveBinaryPath() -> String? {
        let candidates = [
            "/opt/homebrew/bin/piper",
            "/usr/local/bin/piper",
        ]
        if let match = candidates.first(where: { fileManager.fileExists(atPath: $0) }) {
            return match
        }
        return Process.run("/usr/bin/which", ["piper"])
    }

    private func resolveModelPath(preferredVoiceName: String) -> String? {
        let roots = [
            fileManager.homeDirectoryForCurrentUser.appendingPathComponent(".local/share/piper"),
            fileManager.homeDirectoryForCurrentUser.appendingPathComponent(".piper"),
            fileManager.homeDirectoryForCurrentUser.appendingPathComponent("brain/models/piper"),
            URL(fileURLWithPath: "/opt/homebrew/share/piper", isDirectory: true),
            URL(fileURLWithPath: "/usr/local/share/piper", isDirectory: true),
        ]

        var modelPaths: [String] = []
        for root in roots where fileManager.fileExists(atPath: root.path) {
            if let enumerator = fileManager.enumerator(at: root, includingPropertiesForKeys: nil) {
                for case let url as URL in enumerator where url.pathExtension == "onnx" {
                    modelPaths.append(url.path)
                }
            }
        }

        guard !modelPaths.isEmpty else { return nil }

        let preferredTokens: [String]
        if preferredVoiceName.localizedCaseInsensitiveContains("karen") || preferredVoiceName.localizedCaseInsensitiveContains("australia") {
            preferredTokens = ["en_AU", "en-AU", "australia", "en_GB", "en-US", "en_US"]
        } else if preferredVoiceName.localizedCaseInsensitiveContains("moira") || preferredVoiceName.localizedCaseInsensitiveContains("ireland") {
            preferredTokens = ["en_IE", "en-IE", "irish", "en_GB", "en_AU"]
        } else {
            preferredTokens = ["en_AU", "en-GB", "en_GB", "en-US", "en_US"]
        }

        return modelPaths.sorted { lhs, rhs in
            let lhsScore = preferredTokens.firstIndex(where: { lhs.localizedCaseInsensitiveContains($0) }) ?? preferredTokens.count
            let rhsScore = preferredTokens.firstIndex(where: { rhs.localizedCaseInsensitiveContains($0) }) ?? preferredTokens.count
            if lhsScore != rhsScore { return lhsScore < rhsScore }
            return lhs < rhs
        }.first
    }
}

@MainActor
final class PiperVoiceEngine: ObservableObject {
    @Published private(set) var isSpeaking = false
    @Published private(set) var statusMessage = "Piper ready"

    private struct Utterance {
        let id = UUID()
        let text: String
        let preferredVoiceName: String
    }

    private let runner: PiperCommandRunning
    private let fallbackSpeaker: FallbackSpeechRunning
    private let audioPlayer: AudioFilePlaying
    private var queuedUtterances: [Utterance] = []
    private var activeUtterance: Utterance?
    private var activeOutputURL: URL?

    init(
        runner: PiperCommandRunning = ShellPiperCommandRunner(),
        fallbackSpeaker: FallbackSpeechRunning = SayFallbackSpeaker(),
        audioPlayer: AudioFilePlaying = AVAudioFilePlayer()
    ) {
        self.runner = runner
        self.fallbackSpeaker = fallbackSpeaker
        self.audioPlayer = audioPlayer
        statusMessage = runner.isAvailable ? "Piper ready" : runner.unavailableReason
    }

    var isAvailable: Bool { runner.isAvailable }
    var unavailabilityMessage: String { runner.unavailableReason }

    func enqueue(_ text: String, preferredVoiceName: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        queuedUtterances.append(Utterance(text: trimmed, preferredVoiceName: preferredVoiceName))
        startNextUtteranceIfIdle()
    }

    func speakImmediately(_ text: String, preferredVoiceName: String) {
        cancelCurrentSpeech(clearQueue: true)
        enqueue(text, preferredVoiceName: preferredVoiceName)
    }

    func cancelCurrentSpeech(clearQueue: Bool = false) {
        fallbackSpeaker.cancel()
        audioPlayer.stop()
        if let outputURL = activeOutputURL {
            try? FileManager.default.removeItem(at: outputURL)
        }
        activeOutputURL = nil
        activeUtterance = nil
        if clearQueue {
            queuedUtterances.removeAll()
        }
        isSpeaking = false
        statusMessage = clearQueue ? "Piper speech cancelled and queue cleared" : "Piper speech cancelled"
    }

    private func startNextUtteranceIfIdle() {
        guard activeUtterance == nil, let next = queuedUtterances.first else { return }
        queuedUtterances.removeFirst()
        activeUtterance = next

        guard runner.isAvailable else {
            startFallbackSpeech(for: next, reason: runner.unavailableReason)
            return
        }

        let outputURL = FileManager.default.temporaryDirectory.appendingPathComponent("piper_\(next.id.uuidString).wav")
        activeOutputURL = outputURL
        isSpeaking = true
        statusMessage = "Speaking with Piper"
        runner.synthesize(text: next.text, preferredVoiceName: next.preferredVoiceName, outputURL: outputURL) { [weak self] result in
            Task { @MainActor [weak self] in
                guard let self else { return }
                switch result {
                case .success:
                    do {
                        try self.audioPlayer.playAudioFile(at: outputURL) { [weak self] playbackResult in
                            Task { @MainActor [weak self] in
                                guard let self else { return }
                                switch playbackResult {
                                case .success:
                                    self.completeUtterance(id: next.id, message: "Piper playback finished")
                                case .failure(let error):
                                    self.startFallbackSpeech(for: next, reason: error.localizedDescription)
                                }
                            }
                        }
                    } catch {
                        self.startFallbackSpeech(for: next, reason: error.localizedDescription)
                    }
                case .failure(let error):
                    self.startFallbackSpeech(for: next, reason: error.localizedDescription)
                }
            }
        }
    }

    private func startFallbackSpeech(for utterance: Utterance, reason: String) {
        audioPlayer.stop()
        if let outputURL = activeOutputURL {
            try? FileManager.default.removeItem(at: outputURL)
        }
        activeOutputURL = nil

        do {
            isSpeaking = true
            statusMessage = "Using macOS fallback voice because Piper failed: \(reason)"
            try fallbackSpeaker.speak(text: utterance.text, voice: fallbackVoiceName(for: utterance.preferredVoiceName), rate: 170) { [weak self] exitCode in
                guard let self else { return }
                Task { @MainActor in
                    self.completeUtterance(id: utterance.id, message: exitCode == 0 ? "Fallback speech finished" : "Fallback speech failed with exit code \(exitCode)")
                }
            }
        } catch {
            completeUtterance(id: utterance.id, message: "Piper and fallback speech both failed: \(error.localizedDescription)")
        }
    }

    private func completeUtterance(id: UUID, message: String) {
        guard activeUtterance?.id == id else { return }
        statusMessage = message
        activeUtterance = nil
        if let outputURL = activeOutputURL {
            try? FileManager.default.removeItem(at: outputURL)
        }
        activeOutputURL = nil
        isSpeaking = false
        startNextUtteranceIfIdle()
        if activeUtterance != nil {
            isSpeaking = true
        }
    }

    private func fallbackVoiceName(for preferredVoiceName: String) -> String {
        if preferredVoiceName.localizedCaseInsensitiveContains("karen") {
            return "Karen"
        }
        if preferredVoiceName.localizedCaseInsensitiveContains("moira") {
            return "Moira"
        }
        return "Samantha"
    }
}

protocol HTTPDataLoading: AnyObject {
    func load(request: URLRequest, completion: @escaping @Sendable (Result<(Data, HTTPURLResponse), Error>) -> Void)
    func cancelCurrent()
}

final class URLSessionHTTPDataLoader: HTTPDataLoading {
    private let session: URLSession
    private var activeTask: URLSessionDataTask?

    init(session: URLSession = .shared) {
        self.session = session
    }

    func load(request: URLRequest, completion: @escaping @Sendable (Result<(Data, HTTPURLResponse), Error>) -> Void) {
        activeTask?.cancel()
        let task = session.dataTask(with: request) { data, response, error in
            if let error {
                completion(.failure(error))
                return
            }
            guard let httpResponse = response as? HTTPURLResponse, let data else {
                completion(.failure(NSError(domain: "BrainChat.HTTPDataLoader", code: 1, userInfo: [NSLocalizedDescriptionKey: "Invalid HTTP response."])))
                return
            }
            completion(.success((data, httpResponse)))
        }
        activeTask = task
        task.resume()
    }

    func cancelCurrent() {
        activeTask?.cancel()
        activeTask = nil
    }
}

struct ElevenLabsVoiceOption: Identifiable, Hashable, Codable {
    let voiceID: String
    let name: String
    let accentDescription: String
    let fallbackVoiceName: String
    let isDefault: Bool

    var id: String { voiceID }

    static let curated: [ElevenLabsVoiceOption] = [
        ElevenLabsVoiceOption(
            voiceID: "21m00Tcm4TlvDq8ikWAM",
            name: "Rachel",
            accentDescription: "Clear premium English voice",
            fallbackVoiceName: "Karen",
            isDefault: true
        ),
        ElevenLabsVoiceOption(
            voiceID: "EXAVITQu4vr4xnSDxMaL",
            name: "Bella",
            accentDescription: "Warm premium narrator voice",
            fallbackVoiceName: "Karen",
            isDefault: false
        ),
        ElevenLabsVoiceOption(
            voiceID: "MF3mGyEYCl7XYWbV9V6O",
            name: "Elli",
            accentDescription: "Bright premium assistant voice",
            fallbackVoiceName: "Samantha",
            isDefault: false
        ),
    ]

    static let defaultOption = curated.first(where: { $0.isDefault }) ?? curated[0]
}

@MainActor
final class ElevenLabsVoiceEngine: ObservableObject {
    enum ElevenLabsError: LocalizedError, Equatable {
        case missingAPIKey
        case invalidResponse
        case apiFailure(String)

        var errorDescription: String? {
            switch self {
            case .missingAPIKey:
                return "ElevenLabs API key is missing. Speech will fall back to macOS until a key is configured."
            case .invalidResponse:
                return "ElevenLabs returned an invalid response."
            case .apiFailure(let message):
                return message
            }
        }
    }

    @Published private(set) var availableVoices: [ElevenLabsVoiceOption] = ElevenLabsVoiceOption.curated
    @Published var selectedVoiceID: String = ElevenLabsVoiceOption.defaultOption.voiceID
    @Published private(set) var statusMessage = "ElevenLabs ready"
    @Published private(set) var hasStoredAPIKey = false
    @Published private(set) var isSpeaking = false

    private struct Utterance {
        let id = UUID()
        let text: String
        let voice: ElevenLabsVoiceOption
    }

    private enum Constants {
        static let provider = "elevenlabs"
        static let endpointPrefix = "https://api.elevenlabs.io/v1/text-to-speech"
        static let modelID = "eleven_multilingual_v2"
    }

    private let keyManager: APIKeyManaging
    private let fallbackSpeaker: FallbackSpeechRunning
    private let loader: HTTPDataLoading
    private let audioPlayer: AudioFilePlaying

    private var queuedUtterances: [Utterance] = []
    private var activeUtterance: Utterance?
    private var activeOutputURL: URL?

    init(
        keyManager: APIKeyManaging = APIKeyManager.shared,
        fallbackSpeaker: FallbackSpeechRunning = SayFallbackSpeaker(),
        loader: HTTPDataLoading = URLSessionHTTPDataLoader(),
        audioPlayer: AudioFilePlaying = AVAudioFilePlayer()
    ) {
        self.keyManager = keyManager
        self.fallbackSpeaker = fallbackSpeaker
        self.loader = loader
        self.audioPlayer = audioPlayer
        refreshConfiguration()
    }

    func refreshConfiguration() {
        hasStoredAPIKey = keyManager.hasKey(for: Constants.provider)
        statusMessage = hasStoredAPIKey ? "ElevenLabs ready" : ElevenLabsError.missingAPIKey.localizedDescription
    }

    func selectVoice(matching preferredVoiceName: String) {
        let normalized = preferredVoiceName.replacingOccurrences(of: " (Premium)", with: "")
        if let match = availableVoices.first(where: { option in
            option.name.localizedCaseInsensitiveContains(normalized)
                || option.fallbackVoiceName.localizedCaseInsensitiveContains(normalized)
        }) {
            selectedVoiceID = match.voiceID
        } else {
            selectedVoiceID = ElevenLabsVoiceOption.defaultOption.voiceID
        }
    }

    func enqueue(_ text: String, preferredVoiceName: String) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        selectVoice(matching: preferredVoiceName)
        let voice = availableVoices.first(where: { $0.voiceID == selectedVoiceID }) ?? ElevenLabsVoiceOption.defaultOption
        queuedUtterances.append(Utterance(text: trimmed, voice: voice))
        startNextUtteranceIfIdle()
    }

    func speakImmediately(_ text: String, preferredVoiceName: String) {
        cancelCurrentSpeech(clearQueue: true)
        enqueue(text, preferredVoiceName: preferredVoiceName)
    }

    func cancelCurrentSpeech(clearQueue: Bool = false) {
        loader.cancelCurrent()
        fallbackSpeaker.cancel()
        audioPlayer.stop()
        if let outputURL = activeOutputURL {
            try? FileManager.default.removeItem(at: outputURL)
        }
        activeOutputURL = nil
        activeUtterance = nil
        if clearQueue {
            queuedUtterances.removeAll()
        }
        isSpeaking = false
        statusMessage = clearQueue ? "ElevenLabs speech cancelled and queue cleared" : "ElevenLabs speech cancelled"
    }

    private func startNextUtteranceIfIdle() {
        guard activeUtterance == nil, let next = queuedUtterances.first else { return }
        queuedUtterances.removeFirst()
        activeUtterance = next

        guard let apiKey = keyManager.key(for: Constants.provider), !apiKey.isEmpty else {
            startFallbackSpeech(for: next, reason: ElevenLabsError.missingAPIKey.localizedDescription)
            return
        }

        guard let url = URL(string: "\(Constants.endpointPrefix)/\(next.voice.voiceID)") else {
            startFallbackSpeech(for: next, reason: ElevenLabsError.invalidResponse.localizedDescription)
            return
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(apiKey, forHTTPHeaderField: "xi-api-key")
        request.setValue("audio/mpeg", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 45
        let payload: [String: Any] = [
            "text": next.text,
            "model_id": Constants.modelID,
            "voice_settings": [
                "stability": 0.35,
                "similarity_boost": 0.8,
            ],
        ]
        do {
            request.httpBody = try JSONSerialization.data(withJSONObject: payload, options: [.fragmentsAllowed])
        } catch {
            startFallbackSpeech(for: next, reason: error.localizedDescription)
            return
        }

        isSpeaking = true
        statusMessage = "Speaking with ElevenLabs: \(next.voice.name)"
        loader.load(request: request) { [weak self] result in
            Task { @MainActor [weak self] in
                guard let self else { return }
                switch result {
                case .success(let (data, response)):
                    guard (200..<300).contains(response.statusCode) else {
                        let body = String(data: data, encoding: .utf8) ?? "HTTP \(response.statusCode)"
                        self.startFallbackSpeech(for: next, reason: body)
                        return
                    }
                    guard !data.isEmpty else {
                        self.startFallbackSpeech(for: next, reason: ElevenLabsError.invalidResponse.localizedDescription)
                        return
                    }

                    let outputURL = FileManager.default.temporaryDirectory.appendingPathComponent("elevenlabs_\(next.id.uuidString).mp3")
                    do {
                        try data.write(to: outputURL, options: .atomic)
                        self.activeOutputURL = outputURL
                        try self.audioPlayer.playAudioFile(at: outputURL) { [weak self] playbackResult in
                            Task { @MainActor [weak self] in
                                guard let self else { return }
                                switch playbackResult {
                                case .success:
                                    self.completeUtterance(id: next.id, message: "ElevenLabs playback finished")
                                case .failure(let error):
                                    self.startFallbackSpeech(for: next, reason: error.localizedDescription)
                                }
                            }
                        }
                    } catch {
                        self.startFallbackSpeech(for: next, reason: error.localizedDescription)
                    }
                case .failure(let error):
                    self.startFallbackSpeech(for: next, reason: error.localizedDescription)
                }
            }
        }
    }

    private func startFallbackSpeech(for utterance: Utterance, reason: String) {
        loader.cancelCurrent()
        audioPlayer.stop()
        if let outputURL = activeOutputURL {
            try? FileManager.default.removeItem(at: outputURL)
        }
        activeOutputURL = nil

        do {
            isSpeaking = true
            statusMessage = "Using macOS fallback voice because ElevenLabs failed: \(reason)"
            try fallbackSpeaker.speak(text: utterance.text, voice: utterance.voice.fallbackVoiceName, rate: 170) { [weak self] exitCode in
                guard let self else { return }
                Task { @MainActor in
                    self.completeUtterance(id: utterance.id, message: exitCode == 0 ? "Fallback speech finished" : "Fallback speech failed with exit code \(exitCode)")
                }
            }
        } catch {
            completeUtterance(id: utterance.id, message: "ElevenLabs and fallback speech both failed: \(error.localizedDescription)")
        }
    }

    private func completeUtterance(id: UUID, message: String) {
        guard activeUtterance?.id == id else { return }
        statusMessage = message
        activeUtterance = nil
        if let outputURL = activeOutputURL {
            try? FileManager.default.removeItem(at: outputURL)
        }
        activeOutputURL = nil
        isSpeaking = false
        startNextUtteranceIfIdle()
        if activeUtterance != nil {
            isSpeaking = true
        }
    }
}
