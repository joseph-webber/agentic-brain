import AVFoundation
import XCTest
@testable import BrainChatLib

final class SpeechEngineRuntimeTests: XCTestCase {
    @MainActor
    func testSpeechManagerWhisperAPIRequiresKey() {
        let manager = SpeechManager(requestAuthorizationOnInit: false)
        manager.setEngine(.whisperAPI)
        XCTAssertEqual(manager.engineStatus, "Needs OpenAI key")
    }

    @MainActor
    func testSpeechManagerWhisperAPIBecomesReadyWhenKeyProvided() {
        let manager = SpeechManager(requestAuthorizationOnInit: false)
        manager.setEngine(.whisperAPI)
        manager.setOpenAIKey("sk-test")
        XCTAssertEqual(manager.engineStatus, "Ready")
    }

    @MainActor
    func testSpeechManagerFinalTranscriptStopsListening() {
        let manager = SpeechManager(requestAuthorizationOnInit: false)
        var finalized = ""
        manager.isListening = true
        manager.onTranscriptFinalized = { finalized = $0 }

        manager.handle(.final("Hello Joseph"))

        XCTAssertEqual(manager.currentTranscript, "Hello Joseph")
        XCTAssertEqual(finalized, "Hello Joseph")
        XCTAssertFalse(manager.isListening)
        XCTAssertEqual(manager.audioLevel, 0)
    }

    func testWhisperAPIMissingKeyFailsBeforeReadingAudio() async {
        let engine = WhisperAPIEngine(apiKey: "")
        do {
            _ = try await engine.transcribe(audioURL: URL(fileURLWithPath: "/does/not/matter.wav"))
            XCTFail("Expected missing API key error")
        } catch let error as WhisperError {
            XCTAssertEqual(error, .missingAPIKey)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }
}

final class VoiceEngineRuntimeTests: XCTestCase {
    @MainActor
    func testCartesiaFallsBackWithoutAPIKey() async {
        let keyManager = MockAPIKeyManager()
        let fallback = MockFallbackSpeaker()
        let voice = CartesiaVoice(audioPlayer: AudioPlayer(), audioOutput: MockCartesiaAudioOutput(), keyManager: keyManager, fallbackSpeaker: fallback) { _ in
            XCTFail("Cartesia should not create a network session without an API key")
            return URLSession.shared
        }

        voice.enqueue("Hello from Cartesia")
        try? await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertEqual(fallback.spokenTexts.first?.text, "Hello from Cartesia")
        XCTAssertTrue(voice.statusMessage.lowercased().contains("fallback"))
    }

    @MainActor
    func testCartesiaSelectsKarenVoice() {
        let voice = CartesiaVoice(keyManager: MockAPIKeyManager(), fallbackSpeaker: MockFallbackSpeaker())
        voice.selectVoice(matching: "Karen (Premium)")
        XCTAssertEqual(voice.selectedVoiceID, CartesiaVoiceOption.defaultOption.voiceID)
    }

    @MainActor
    func testPiperFallsBackWhenUnavailable() async {
        let fallback = MockFallbackSpeaker()
        let runner = MockPiperRunner(isAvailable: false)
        let engine = PiperVoiceEngine(runner: runner, fallbackSpeaker: fallback, audioPlayer: MockAudioFilePlayer())

        engine.enqueue("Hello from Piper", preferredVoiceName: "Karen (Premium)")
        try? await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertEqual(fallback.spokenTexts.first?.text, "Hello from Piper")
        XCTAssertTrue(engine.statusMessage.lowercased().contains("fallback"))
    }

    @MainActor
    func testPiperUsesResolvedVoiceNameWhenAvailable() async {
        let fallback = MockFallbackSpeaker()
        let runner = MockPiperRunner(isAvailable: true)
        let player = MockAudioFilePlayer()
        let engine = PiperVoiceEngine(runner: runner, fallbackSpeaker: fallback, audioPlayer: player)

        engine.enqueue("Hello from Piper", preferredVoiceName: "Karen (Premium)")
        try? await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertEqual(runner.recordedVoiceNames, ["Karen (Premium)"])
        XCTAssertEqual(player.playedFileCount, 1)
        XCTAssertTrue(fallback.spokenTexts.isEmpty)
    }

    @MainActor
    func testElevenLabsFallsBackWithoutAPIKey() async {
        let keyManager = MockAPIKeyManager()
        let fallback = MockFallbackSpeaker()
        let loader = MockHTTPDataLoader()
        let engine = ElevenLabsVoiceEngine(keyManager: keyManager, fallbackSpeaker: fallback, loader: loader, audioPlayer: MockAudioFilePlayer())

        engine.enqueue("Hello from ElevenLabs", preferredVoiceName: "Karen (Premium)")
        try? await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertTrue(loader.requests.isEmpty)
        XCTAssertEqual(fallback.spokenTexts.first?.text, "Hello from ElevenLabs")
        XCTAssertTrue(engine.statusMessage.lowercased().contains("fallback"))
    }

    @MainActor
    func testElevenLabsUsesAudioPlayerWhenRequestSucceeds() async {
        let keyManager = MockAPIKeyManager(keys: ["elevenlabs": "secret"])
        let fallback = MockFallbackSpeaker()
        let loader = MockHTTPDataLoader(result: .success((Data([0x00, 0x01, 0x02]), HTTPURLResponse(url: URL(string: "https://api.elevenlabs.io")!, statusCode: 200, httpVersion: nil, headerFields: nil)!)))
        let player = MockAudioFilePlayer()
        let engine = ElevenLabsVoiceEngine(keyManager: keyManager, fallbackSpeaker: fallback, loader: loader, audioPlayer: player)

        engine.enqueue("Hello from ElevenLabs", preferredVoiceName: "Karen (Premium)")
        try? await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertEqual(loader.requests.count, 1)
        XCTAssertEqual(player.playedFileCount, 1)
        XCTAssertTrue(fallback.spokenTexts.isEmpty)
    }

    @MainActor
    func testVoiceManagerRoutesToConfiguredOutputEngine() async {
        let fallback = MockFallbackSpeaker()
        let piperRunner = MockPiperRunner(isAvailable: true)
        let piperPlayer = MockAudioFilePlayer()
        let voiceManager = VoiceManager(
            cartesiaVoice: CartesiaVoice(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback),
            piperVoice: PiperVoiceEngine(runner: piperRunner, fallbackSpeaker: fallback, audioPlayer: piperPlayer),
            elevenLabsVoice: ElevenLabsVoiceEngine(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback, loader: MockHTTPDataLoader(), audioPlayer: MockAudioFilePlayer())
        )

        voiceManager.setOutputEngine(.piper)
        voiceManager.selectVoice(named: "Karen (Premium)")
        voiceManager.speakImmediately("Route through Piper")
        try? await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertEqual(piperRunner.recordedVoiceNames.last, "Karen (Premium)")
        XCTAssertEqual(piperPlayer.playedFileCount, 1)
    }

    @MainActor
    func testVoiceManagerRoutesToCartesia() async {
        let keyManager = MockAPIKeyManager(keys: ["cartesia": "test-key"])
        let fallback = MockFallbackSpeaker()
        let cartesia = CartesiaVoice(
            audioOutput: MockCartesiaAudioOutput(),
            keyManager: keyManager,
            fallbackSpeaker: fallback
        )
        let voiceManager = VoiceManager(
            cartesiaVoice: cartesia,
            piperVoice: PiperVoiceEngine(runner: MockPiperRunner(isAvailable: false), fallbackSpeaker: fallback, audioPlayer: MockAudioFilePlayer()),
            elevenLabsVoice: ElevenLabsVoiceEngine(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback, loader: MockHTTPDataLoader(), audioPlayer: MockAudioFilePlayer())
        )

        voiceManager.setOutputEngine(.cartesia)
        XCTAssertEqual(voiceManager.currentEngine, .cartesia)
    }

    @MainActor
    func testVoiceManagerRoutesToElevenLabs() async {
        let keyManager = MockAPIKeyManager(keys: ["elevenlabs": "test-key"])
        let fallback = MockFallbackSpeaker()
        let loader = MockHTTPDataLoader(result: .success((Data([0x00]), HTTPURLResponse(url: URL(string: "https://api.elevenlabs.io")!, statusCode: 200, httpVersion: nil, headerFields: nil)!)))
        let player = MockAudioFilePlayer()
        let elevenLabs = ElevenLabsVoiceEngine(keyManager: keyManager, fallbackSpeaker: fallback, loader: loader, audioPlayer: player)
        let voiceManager = VoiceManager(
            cartesiaVoice: CartesiaVoice(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback),
            piperVoice: PiperVoiceEngine(runner: MockPiperRunner(isAvailable: false), fallbackSpeaker: fallback, audioPlayer: MockAudioFilePlayer()),
            elevenLabsVoice: elevenLabs
        )

        voiceManager.setOutputEngine(.elevenLabs)
        voiceManager.speak("Hello from ElevenLabs")
        try? await Task.sleep(nanoseconds: 50_000_000)

        XCTAssertEqual(voiceManager.currentEngine, .elevenLabs)
        XCTAssertEqual(loader.requests.count, 1, "ElevenLabs engine should have received the request")
    }

    @MainActor
    func testSetOutputEngineUpdatesCurrentEngine() {
        let fallback = MockFallbackSpeaker()
        let voiceManager = VoiceManager(
            cartesiaVoice: CartesiaVoice(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback),
            piperVoice: PiperVoiceEngine(runner: MockPiperRunner(isAvailable: false), fallbackSpeaker: fallback, audioPlayer: MockAudioFilePlayer()),
            elevenLabsVoice: ElevenLabsVoiceEngine(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback, loader: MockHTTPDataLoader(), audioPlayer: MockAudioFilePlayer())
        )

        for engine in VoiceOutputEngine.allCases {
            voiceManager.setOutputEngine(engine)
            XCTAssertEqual(voiceManager.currentEngine, engine,
                           "setOutputEngine(\(engine.rawValue)) must update currentEngine")
        }
    }

    @MainActor
    func testSystemCommandsSpeechDelegateRoutesToVoiceManager() async {
        let fallback = MockFallbackSpeaker()
        let piperRunner = MockPiperRunner(isAvailable: true)
        let piperPlayer = MockAudioFilePlayer()
        let voiceManager = VoiceManager(
            cartesiaVoice: CartesiaVoice(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback),
            piperVoice: PiperVoiceEngine(runner: piperRunner, fallbackSpeaker: fallback, audioPlayer: piperPlayer),
            elevenLabsVoice: ElevenLabsVoiceEngine(keyManager: MockAPIKeyManager(), fallbackSpeaker: fallback, loader: MockHTTPDataLoader(), audioPlayer: MockAudioFilePlayer())
        )
        voiceManager.setOutputEngine(.piper)

        let system = SystemCommands.shared
        system.registerSpeechDelegate { text in
            Task { @MainActor in
                voiceManager.speak(text)
            }
        }

        system.speak("Delegated speech")
        try? await Task.sleep(nanoseconds: 100_000_000)

        XCTAssertEqual(piperRunner.recordedVoiceNames.last, "Karen (Premium)",
                       "SystemCommands.speak() must route through VoiceManager to the selected engine")
        system.unregisterSpeechDelegate()
    }
}

private final class MockAPIKeyManager: APIKeyManaging {
    private var keys: [String: String]

    init(keys: [String: String] = [:]) {
        self.keys = keys
    }

    func setKey(_ value: String, for provider: String) throws {
        keys[provider] = value
    }

    func key(for provider: String) -> String? {
        keys[provider]
    }

    func removeKey(for provider: String) {
        keys.removeValue(forKey: provider)
    }

    func hasKey(for provider: String) -> Bool {
        !(keys[provider] ?? "").isEmpty
    }
}

private final class MockFallbackSpeaker: FallbackSpeechRunning {
    var spokenTexts: [(text: String, voice: String, rate: Int)] = []
    var cancelCount = 0

    func speak(text: String, voice: String, rate: Int, completion: @escaping @Sendable (Int32) -> Void) throws {
        spokenTexts.append((text, voice, rate))
        completion(0)
    }

    func cancel() {
        cancelCount += 1
    }
}

private final class MockCartesiaAudioOutput: CartesiaAudioPlaying {
    var onStreamFinished: ((UUID) -> Void)?

    func prepareStream(id: UUID, sampleRate: Double, channels: AVAudioChannelCount) {}
    func appendPCMChunk(_ data: Data, for id: UUID) throws {}
    func finishStream(id: UUID) { onStreamFinished?(id) }
    func cancelCurrentSpeech() {}
}

private final class MockAudioFilePlayer: AudioFilePlaying {
    var playedFileCount = 0
    var stopCount = 0

    func playAudioFile(at url: URL, completion: @escaping @Sendable (Result<Void, Error>) -> Void) throws {
        playedFileCount += 1
        completion(.success(()))
    }

    func stop() {
        stopCount += 1
    }
}

private final class MockPiperRunner: PiperCommandRunning {
    let isAvailable: Bool
    var unavailableReason: String { isAvailable ? "Ready" : "Install Piper TTS to enable this engine" }
    var recordedVoiceNames: [String] = []

    init(isAvailable: Bool) {
        self.isAvailable = isAvailable
    }

    func synthesize(text: String, preferredVoiceName: String, outputURL: URL, completion: @escaping @Sendable (Result<Void, Error>) -> Void) {
        recordedVoiceNames.append(preferredVoiceName)
        if isAvailable {
            try? Data("RIFF".utf8).write(to: outputURL)
            completion(.success(()))
        } else {
            completion(.failure(NSError(domain: "MockPiperRunner", code: 1, userInfo: [NSLocalizedDescriptionKey: unavailableReason])))
        }
    }
}

private final class MockHTTPDataLoader: HTTPDataLoading {
    var requests: [URLRequest] = []
    private let result: Result<(Data, HTTPURLResponse), Error>?

    init(result: Result<(Data, HTTPURLResponse), Error>? = nil) {
        self.result = result
    }

    func load(request: URLRequest, completion: @escaping @Sendable (Result<(Data, HTTPURLResponse), Error>) -> Void) {
        requests.append(request)
        if let result {
            completion(result)
        }
    }

    func cancelCurrent() {}
}
