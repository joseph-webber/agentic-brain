import Foundation
import XCTest
@testable import BrainChat

final class TestCartesiaVoice: XCTestCase {
    func testMissingAPIKeyFallsBackImmediately() {
        let keyStore = InMemorySecureStore()
        let keyManager = APIKeyManager(store: keyStore, service: "tests")
        let audioPlayer = AudioPlayer()
        let output = MockAudioPlayer()
        let fallback = MockFallbackSpeaker()
        let voice = CartesiaVoice(audioPlayer: audioPlayer, audioOutput: output, keyManager: keyManager, fallbackSpeaker: fallback) { _ in
            XCTFail("Network session should not be created without API key")
            return URLSession.shared
        }

        voice.enqueue("Hello there")
        XCTAssertEqual(fallback.spokenTexts.first?.text, "Hello there")
        XCTAssertTrue(voice.statusMessage.contains("Fallback"))
    }

    func testStoresAndRemovesAPIKey() throws {
        let keyStore = InMemorySecureStore()
        let keyManager = APIKeyManager(store: keyStore, service: "tests")
        let voice = CartesiaVoice(keyManager: keyManager, fallbackSpeaker: MockFallbackSpeaker())
        try voice.setAPIKey("abc123")
        XCTAssertTrue(voice.hasStoredAPIKey)
        XCTAssertEqual(keyManager.key(for: "cartesia"), "abc123")
        voice.removeAPIKey()
        XCTAssertFalse(voice.hasStoredAPIKey)
        XCTAssertNil(keyManager.key(for: "cartesia"))
    }

    func testSuccessfulStreamingUsesAudioPlayer() async {
        let keyStore = InMemorySecureStore()
        let keyManager = APIKeyManager(store: keyStore, service: "tests")
        try? keyManager.setKey("secret", for: "cartesia")
        let output = MockAudioPlayer()
        let fallback = MockFallbackSpeaker()
        MockURLProtocol.requestHandler = { request in
            let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: nil, headerFields: nil)!
            return (response, Data([0x00, 0x01, 0x02, 0x03]))
        }
        let voice = CartesiaVoice(audioPlayer: AudioPlayer(), audioOutput: output, keyManager: keyManager, fallbackSpeaker: fallback) { delegate in
            let config = URLSessionConfiguration.ephemeral
            config.protocolClasses = [MockURLProtocol.self]
            return URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
        }

        voice.enqueue("Testing Cartesia")
        try? await Task.sleep(nanoseconds: 150_000_000)
        XCTAssertEqual(output.preparedIDs.count, 1)
        XCTAssertEqual(output.finishedIDs.count, 1)
        XCTAssertTrue(fallback.spokenTexts.isEmpty)
    }
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
