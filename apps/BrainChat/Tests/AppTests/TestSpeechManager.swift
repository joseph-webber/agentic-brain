import XCTest
@testable import BrainChat

final class TestSpeechManager: XCTestCase {
    func testRefreshDevicesPrefersAirPods() async {
        let mock = MockSpeechRecognizer()
        mock.devices = [
            AudioDevice(id: "1", name: "Built-in Microphone", isAirPodsMax: false),
            AudioDevice(id: "2", name: "AirPods Max", isAirPodsMax: true),
        ]
        let manager = SpeechManager(controller: mock, requestAuthorizationOnInit: false)
        manager.refreshDevices()
        await flushMainQueue()
        XCTAssertEqual(manager.selectedDevice?.name, "AirPods Max")
    }

    func testStartListeningRequiresAuthorization() {
        let mock = MockSpeechRecognizer()
        mock.currentAuthorizationStatus = .denied
        let manager = SpeechManager(controller: mock, requestAuthorizationOnInit: false)
        manager.authorizationStatus = .denied
        manager.startListening()
        XCTAssertEqual(manager.errorMessage, "Speech recognition not authorized.")
        XCTAssertFalse(manager.isListening)
    }

    func testHandlesPartialAndFinalTranscript() async {
        let mock = MockSpeechRecognizer()
        let manager = SpeechManager(controller: mock, requestAuthorizationOnInit: false)
        manager.authorizationStatus = .authorized
        var finalized = ""
        manager.onTranscriptFinalized = { finalized = $0 }
        manager.startListening()
        mock.emit(.partial("Hello"))
        await flushMainQueue()
        XCTAssertEqual(manager.currentTranscript, "Hello")
        mock.emit(.final("Hello there"))
        await flushMainQueue()
        XCTAssertEqual(finalized, "Hello there")
        XCTAssertFalse(manager.isListening)
    }

    func testHandlesRecognitionFailure() async {
        let mock = MockSpeechRecognizer()
        let manager = SpeechManager(controller: mock, requestAuthorizationOnInit: false)
        manager.authorizationStatus = .authorized
        manager.startListening()
        mock.emit(.failure("Microphone error"))
        await flushMainQueue()
        XCTAssertEqual(manager.errorMessage, "Microphone error")
        XCTAssertFalse(manager.isListening)
    }
}
