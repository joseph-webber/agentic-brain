import Foundation
import Speech
@testable import BrainChat

final class MockSpeechRecognizer: SpeechRecognitionControlling {
    var currentAuthorizationStatus: SFSpeechRecognizerAuthorizationStatus = .authorized
    var isRecognizerAvailable: Bool = true
    var devices: [AudioDevice] = []
    var startError: Error?
    var startCallCount = 0
    var stopCallCount = 0
    private var handler: ((SpeechRecognitionUpdate) -> Void)?

    func requestAuthorization(_ completion: @escaping (SFSpeechRecognizerAuthorizationStatus) -> Void) {
        completion(currentAuthorizationStatus)
    }

    func availableInputDevices() -> [AudioDevice] { devices }

    func startRecognition(handler: @escaping (SpeechRecognitionUpdate) -> Void) throws {
        startCallCount += 1
        if let startError { throw startError }
        self.handler = handler
    }

    func stopRecognition() {
        stopCallCount += 1
    }

    func emit(_ update: SpeechRecognitionUpdate) {
        handler?(update)
    }
}
