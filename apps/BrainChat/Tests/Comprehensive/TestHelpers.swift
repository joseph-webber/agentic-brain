import Foundation
import XCTest
@testable import BrainChatLib

func flushMainQueue() async {
    await MainActor.run {}
    try? await Task.sleep(nanoseconds: 50_000_000)
}

final class InMemorySecureStore: SecureKeyValueStore {
    var values: [String: String] = [:]
    var setError: Error?

    func set(value: String, service: String, account: String) throws {
        if let setError { throw setError }
        values["\(service)::\(account)"] = value
    }

    func get(service: String, account: String) -> String? {
        values["\(service)::\(account)"]
    }

    func remove(service: String, account: String) {
        values.removeValue(forKey: "\(service)::\(account)")
    }
}

struct TestError: LocalizedError, Equatable {
    let message: String
    var errorDescription: String? { message }
}

final class MockVoiceSynthesizer: VoiceSynthesizing {
    weak var delegate: VoiceSynthesizerDelegate?
    var rate: Float = 0
    var voices: [VoiceManager.VoiceInfo]
    var selectedVoiceIDs: [String] = []
    var startedTexts: [String] = []
    var stopCallCount = 0

    init(voices: [VoiceManager.VoiceInfo] = [
        .init(id: "samantha", name: "Samantha", language: "en_AU", isPremium: false),
        .init(id: "karen-premium", name: "Karen (Premium)", language: "en_AU", isPremium: true),
    ]) {
        self.voices = voices
    }

    func availableVoices() -> [VoiceManager.VoiceInfo] { voices }
    func setVoice(id: String) { selectedVoiceIDs.append(id) }
    func startSpeaking(_ text: String) { startedTexts.append(text) }
    func stopSpeaking() { stopCallCount += 1 }

    func finish(successfully: Bool = true) {
        delegate?.voiceSynthesizerDidFinishSpeaking(self, successfully: successfully)
    }
}

final class MockSystemCommands: SystemCommandProviding {
    var spokenTexts: [String] = []
    var clipboard = ""
    var frontmost = "Safari"
    var commandResult = CommandResult(stdout: "ok", stderr: "", exitCode: 0, duration: 0.1)
    var testsResult = CommandResult(stdout: "all good", stderr: "", exitCode: 0, duration: 0.1)
    var gitResult = CommandResult(stdout: "M file.swift", stderr: "", exitCode: 0, duration: 0.1)
    var thrownError: Error?
    var openedApps: [String] = []
    var openedURLs: [String] = []
    var shellCommands: [String] = []

    func speak(_ text: String, voice: String, rate: Int) { spokenTexts.append(text) }
    func runTests(in directory: String) throws -> CommandResult { if let thrownError { throw thrownError }; return testsResult }
    func readClipboard() -> String { clipboard }
    func writeClipboard(_ text: String) { clipboard = text }
    func openApp(_ appName: String) throws { if let thrownError { throw thrownError }; openedApps.append(appName) }
    func openURL(_ urlString: String) throws { if let thrownError { throw thrownError }; openedURLs.append(urlString) }
    func gitStatus(in directory: String) throws -> CommandResult { if let thrownError { throw thrownError }; return gitResult }
    func frontmostApp() -> String { frontmost }
    func run(_ command: String, timeout: TimeInterval?, workingDirectory: String?) throws -> CommandResult {
        if let thrownError { throw thrownError }
        shellCommands.append(command)
        return commandResult
    }
}

final class MockAirPodsHardware: AirPodsHardwareControlling {
    var state: AirPodsState
    var routeAllCalls = 0
    var routeInputCalls = 0
    var monitoringHandler: (() -> Void)?
    var routeError: Error?

    init(state: AirPodsState) {
        self.state = state
    }

    func currentState() -> AirPodsState { state }
    func routeAllAudioToAirPods(preferredOutputName: String?) throws {
        if let routeError { throw routeError }
        routeAllCalls += 1
    }
    func routeAirPodsInput(preferredName: String?) throws {
        if let routeError { throw routeError }
        routeInputCalls += 1
    }
    func startMonitoring(changeHandler: @escaping () -> Void) { monitoringHandler = changeHandler }
    func stopMonitoring() { monitoringHandler = nil }
}

final class MockFallbackSpeaker: FallbackSpeechRunning {
    var spokenTexts: [(text: String, voice: String, rate: Int)] = []
    var cancelCallCount = 0
    var thrownError: Error?

    func speak(text: String, voice: String, rate: Int, completion: @escaping (Int32) -> Void) throws {
        if let thrownError { throw thrownError }
        spokenTexts.append((text, voice, rate))
        completion(0)
    }

    func cancel() {
        cancelCallCount += 1
    }
}

final class MockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        guard let handler = Self.requestHandler else {
            client?.urlProtocol(self, didFailWithError: TestError(message: "Missing request handler"))
            return
        }
        do {
            let (response, data) = try handler(request)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }
    override func stopLoading() {}
}
