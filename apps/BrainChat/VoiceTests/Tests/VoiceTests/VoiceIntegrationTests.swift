import XCTest
@testable import VoiceTestLib

// MARK: - Voice Integration Tests

final class VoiceIntegrationTests: XCTestCase {

    // MARK: - Speech Recognition Start/Stop

    func testSpeechRecognitionStartsSuccessfully() throws {
        let controller = MockSpeechRecognitionController()
        try controller.startRecognition()
        XCTAssertTrue(controller.isRecognising)
        XCTAssertEqual(controller.startCallCount, 1)
    }

    func testSpeechRecognitionStops() throws {
        let controller = MockSpeechRecognitionController()
        try controller.startRecognition()
        controller.stopRecognition()
        XCTAssertFalse(controller.isRecognising)
        XCTAssertEqual(controller.stopCallCount, 1)
    }

    func testSpeechRecognitionStartStopCycles() throws {
        let controller = MockSpeechRecognitionController()
        for cycle in 1...5 {
            try controller.startRecognition()
            XCTAssertTrue(controller.isRecognising, "Cycle \(cycle): should be listening")
            controller.stopRecognition()
            XCTAssertFalse(controller.isRecognising, "Cycle \(cycle): should be stopped")
        }
        XCTAssertEqual(controller.startCallCount, 5)
        XCTAssertEqual(controller.stopCallCount, 5)
    }

    func testSpeechRecognitionBlockedWhenUnauthorized() {
        let controller = MockSpeechRecognitionController()
        controller.authorizationStatus = "denied"
        XCTAssertThrowsError(try controller.startRecognition())
        XCTAssertFalse(controller.isRecognising)
    }

    func testSpeechRecognitionBlockedWhenUnavailable() {
        let controller = MockSpeechRecognitionController()
        controller.isRecognizerAvailable = false
        XCTAssertThrowsError(try controller.startRecognition())
    }

    func testAuthorizationRequestTriggered() {
        let controller = MockSpeechRecognitionController()
        let exp = XCTestExpectation(description: "Auth callback")
        controller.requestAuthorization { status in
            XCTAssertEqual(status, "authorized")
            exp.fulfill()
        }
        wait(for: [exp], timeout: 1.0)
        XCTAssertEqual(controller.authorizationRequestCount, 1)
    }

    // MARK: - Spacebar Activation

    func testSpacebarActivatesRecognition() throws {
        let controller = MockSpeechRecognitionController()
        XCTAssertFalse(controller.isRecognising)
        try controller.startRecognition()
        XCTAssertTrue(controller.isRecognising,
                      "Spacebar press must activate speech recognition")
    }

    func testSpacebarToggle() throws {
        let controller = MockSpeechRecognitionController()
        try controller.startRecognition()
        XCTAssertTrue(controller.isRecognising)
        controller.stopRecognition()
        XCTAssertFalse(controller.isRecognising)
    }

    // MARK: - Transcription Output

    func testPartialTranscriptReceived() throws {
        let controller = MockSpeechRecognitionController()
        var receivedPartials: [String] = []
        controller.recognitionHandler = { update in
            if update.kind == .partial { receivedPartials.append(update.text) }
        }
        try controller.startRecognition()
        controller.simulatePartialTranscript("Hello")
        controller.simulatePartialTranscript("Hello Brain")
        controller.simulatePartialTranscript("Hello Brain how are")
        XCTAssertEqual(receivedPartials.count, 3)
        XCTAssertEqual(receivedPartials.last, "Hello Brain how are")
    }

    func testFinalTranscriptReceived() throws {
        let controller = MockSpeechRecognitionController()
        var finalText: String?
        controller.recognitionHandler = { update in
            if update.kind == .final { finalText = update.text }
        }
        try controller.startRecognition()
        controller.simulateFinalTranscript("Hello Brain how are you")
        XCTAssertEqual(finalText, "Hello Brain how are you",
                       "Transcription text must appear correctly")
    }

    func testTranscriptWithPunctuation() throws {
        let controller = MockSpeechRecognitionController()
        var finalText: String?
        controller.recognitionHandler = { update in
            if update.kind == .final { finalText = update.text }
        }
        try controller.startRecognition()
        controller.simulateFinalTranscript("What's the time in Adelaide? It's 3:30 PM!")
        XCTAssertEqual(finalText, "What's the time in Adelaide? It's 3:30 PM!")
    }

    // MARK: - Voice Output

    func testVoiceOutputPlays() {
        let voice = MockVoiceSynthesizer()
        voice.speak("G'day Joseph!")
        XCTAssertTrue(voice.isSpeaking)
        XCTAssertEqual(voice.spokenTexts.count, 1)
        XCTAssertEqual(voice.spokenTexts[0], "G'day Joseph!")
    }

    func testVoiceOutputStops() {
        let voice = MockVoiceSynthesizer()
        voice.speak("Test")
        voice.stop()
        XCTAssertFalse(voice.isSpeaking)
        XCTAssertEqual(voice.stopCallCount, 1)
    }

    func testEmptyTextNotSpoken() {
        for text in ["", "   ", "\n\n", "\t  \n"] {
            let shouldSpeak = !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            XCTAssertFalse(shouldSpeak, "Empty/whitespace text should not be spoken")
        }
    }

    // MARK: - Audio Output Mock (PCM)

    func testPCMStreamPrepareAndPlay() throws {
        let output = MockAudioOutput()
        let streamID = UUID()
        output.prepareStream(id: streamID, sampleRate: 24_000, channels: 1)
        XCTAssertEqual(output.preparedStreams.count, 1)
        XCTAssertEqual(output.preparedStreams[0].sampleRate, 24_000)

        let pcmData = VoiceTestHelpers.makePCMData(frameCount: 480)
        try output.appendPCMChunk(pcmData, for: streamID)
        XCTAssertTrue(output.isPlaying)
        XCTAssertEqual(output.appendedChunks.count, 1)

        output.finishStream(id: streamID)
        XCTAssertFalse(output.isPlaying)
        XCTAssertEqual(output.finishedStreamIDs, [streamID])
    }

    func testPCMStreamRejectsEmptyChunk() {
        let output = MockAudioOutput()
        output.prepareStream(id: UUID())
        XCTAssertThrowsError(try output.appendPCMChunk(Data(), for: UUID()))
    }

    func testMultiplePCMStreams() {
        let output = MockAudioOutput()
        output.prepareStream(id: UUID(), sampleRate: 24_000, channels: 1)
        output.prepareStream(id: UUID(), sampleRate: 48_000, channels: 2)
        XCTAssertEqual(output.preparedStreams.count, 2)
        XCTAssertEqual(output.preparedStreams[1].sampleRate, 48_000)
        XCTAssertEqual(output.preparedStreams[1].channels, 2)
    }

    func testStreamCancelClearsState() throws {
        let output = MockAudioOutput()
        let streamID = UUID()
        output.prepareStream(id: streamID)
        try output.appendPCMChunk(VoiceTestHelpers.makePCMData(), for: streamID)
        XCTAssertTrue(output.isPlaying)
        output.cancelCurrentSpeech()
        XCTAssertFalse(output.isPlaying)
        XCTAssertEqual(output.cancelCallCount, 1)
        XCTAssertTrue(output.preparedStreams.isEmpty)
    }

    // MARK: - AirPods Detection

    func testAirPodsDetectedWhenConnected() {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        let state = airpods.currentState()
        XCTAssertTrue(state.connected, "AirPods must be detected when connected")
        XCTAssertEqual(state.deviceName, "Joseph's AirPods Max")
        XCTAssertEqual(state.battery, 85)
    }

    func testAirPodsNotDetectedWhenDisconnected() {
        let airpods = MockAirPods()
        let state = airpods.currentState()
        XCTAssertFalse(state.connected)
        XCTAssertNil(state.deviceName)
    }

    func testAirPodsConnectDisconnectCycle() {
        let airpods = MockAirPods()
        var notifications: [String] = []
        airpods.onNotification = { notifications.append($0) }
        airpods.simulateConnect()
        XCTAssertTrue(airpods.isConnected)
        XCTAssertTrue(notifications[0].contains("connected"))
        airpods.simulateDisconnect()
        XCTAssertFalse(airpods.isConnected)
        XCTAssertTrue(notifications[1].contains("disconnected"))
    }

    func testAirPodsAudioRouting() throws {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        try airpods.routeAllAudioToAirPods()
        XCTAssertEqual(airpods.routeAllCallCount, 1)
        try airpods.routeAirPodsInput()
        XCTAssertEqual(airpods.routeInputCallCount, 1)
    }

    func testAirPodsRoutingFailsWhenDisconnected() {
        let airpods = MockAirPods()
        XCTAssertThrowsError(try airpods.routeAllAudioToAirPods())
    }

    func testAirPodsMonitoring() {
        let airpods = MockAirPods()
        airpods.startMonitoring()
        XCTAssertTrue(airpods.monitoringActive)
        airpods.stopMonitoring()
        XCTAssertFalse(airpods.monitoringActive)
    }

    func testAirPodsBatteryTracking() {
        let airpods = MockAirPods()
        airpods.simulateConnect()
        XCTAssertEqual(airpods.batteryPercent, 85)
        airpods.simulateBatteryChange(42)
        XCTAssertEqual(airpods.batteryPercent, 42)
    }

    // MARK: - Voice Queue Management

    func testVoiceQueueFIFO() {
        let voice = MockVoiceSynthesizer()
        let messages = ["First", "Second", "Third", "Fourth"]
        for msg in messages { voice.speak(msg) }
        XCTAssertEqual(voice.spokenTexts, messages, "Queue must preserve FIFO order")
    }

    func testVoiceQueueClearedOnStop() {
        let voice = MockVoiceSynthesizer()
        voice.speak("One"); voice.speak("Two"); voice.speak("Three")
        voice.stop()
        XCTAssertFalse(voice.isSpeaking)
    }

    func testVoiceQueueWithImmediateInterrupt() {
        let voice = MockVoiceSynthesizer()
        voice.speak("Background message")
        voice.stop()
        voice.speak("Urgent message")
        XCTAssertEqual(voice.spokenTexts.last, "Urgent message")
    }

    func testVoiceQueueCountAfterMultipleAdds() {
        let voice = MockVoiceSynthesizer()
        for i in 0..<10 { voice.speak("Message \(i)") }
        XCTAssertEqual(voice.spokenTexts.count, 10)
    }

    // MARK: - Karen Voice Selection

    func testKarenIsDefaultVoice() {
        let voice = MockVoiceSynthesizer()
        XCTAssertEqual(voice.selectedVoice, "Karen (Premium)",
                       "Default voice MUST be Karen for Joseph")
    }

    func testKarenVoiceDetectionVariants() {
        for name in ["Karen (Premium)", "Karen", "karen", "Karen (Enhanced)", "KAREN (Premium)"] {
            XCTAssertTrue(name.lowercased().contains("karen"),
                          "Should detect Karen voice: \(name)")
        }
    }

    func testKarenAlwaysSortedFirst() {
        var voices = [
            ("Zarvox", "en-US"), ("Karen (Premium)", "en-AU"),
            ("Moira", "en-IE"), ("Alex", "en-US"), ("Samantha", "en-US"),
        ]
        voices.sort { a, b in
            if a.0.contains("Karen") && !b.0.contains("Karen") { return true }
            if !a.0.contains("Karen") && b.0.contains("Karen") { return false }
            return a.0 < b.0
        }
        XCTAssertEqual(voices[0].0, "Karen (Premium)")
    }

    func testKarenLocaleIsAustralianEnglish() {
        let locale = Locale(identifier: "en-AU")
        XCTAssertEqual(locale.language.languageCode?.identifier, "en")
    }

    func testVoiceSwitchToOtherAndBack() {
        let voice = MockVoiceSynthesizer()
        XCTAssertEqual(voice.selectedVoice, "Karen (Premium)")
        voice.selectedVoice = "Moira"
        XCTAssertEqual(voice.selectedVoice, "Moira")
        voice.selectedVoice = "Karen (Premium)"
        XCTAssertEqual(voice.selectedVoice, "Karen (Premium)")
    }

    // MARK: - Speech Rate Configuration

    func testDefaultSpeechRate() {
        XCTAssertEqual(VoiceTestHelpers.defaultSpeechRate, 160.0)
    }

    func testBaliSpaRateIsSlower() {
        XCTAssertLessThan(VoiceTestHelpers.baliSpaRate, VoiceTestHelpers.defaultSpeechRate)
        XCTAssertGreaterThanOrEqual(VoiceTestHelpers.baliSpaRate, 145)
    }

    func testPartyRateIsFaster() {
        XCTAssertGreaterThan(VoiceTestHelpers.partyRate, VoiceTestHelpers.defaultSpeechRate)
    }

    // MARK: - Fallback Speaker

    func testFallbackSpeakerCalled() throws {
        let fallback = MockVoiceFallbackSpeaker()
        try fallback.speak(text: "Fallback test", voice: "Karen", rate: 170) { status in
            XCTAssertEqual(status, 0)
        }
        XCTAssertEqual(fallback.speechCalls.count, 1)
        XCTAssertEqual(fallback.speechCalls[0].voice, "Karen")
    }

    func testFallbackSpeakerCancel() {
        let fallback = MockVoiceFallbackSpeaker()
        fallback.cancel()
        XCTAssertEqual(fallback.cancelCallCount, 1)
    }

    func testFallbackSpeakerFailure() {
        let fallback = MockVoiceFallbackSpeaker()
        fallback.shouldFail = true
        XCTAssertThrowsError(
            try fallback.speak(text: "fail", voice: "Karen", rate: 170) { _ in }
        )
    }

    // MARK: - Audio Level Metering

    func testAudioLevelUpdates() throws {
        let controller = MockSpeechRecognitionController()
        var levels: [Float] = []
        controller.recognitionHandler = { update in
            if update.kind == .level { levels.append(update.level) }
        }
        try controller.startRecognition()
        controller.simulateAudioLevel(0.0)
        controller.simulateAudioLevel(0.5)
        controller.simulateAudioLevel(1.0)
        XCTAssertEqual(levels, [0.0, 0.5, 1.0])
    }

    func testAudioLevelClampedToRange() {
        let rawValues: [Float] = [-0.5, 0.0, 0.5, 1.0, 1.5]
        let clamped = rawValues.map { min(max($0, 0), 1) }
        XCTAssertEqual(clamped, [0.0, 0.0, 0.5, 1.0, 1.0])
    }

    // MARK: - Recognition Failure Handling

    func testRecognitionFailureReported() throws {
        let controller = MockSpeechRecognitionController()
        var errorText: String?
        controller.recognitionHandler = { update in
            if update.kind == .failure { errorText = update.text }
        }
        try controller.startRecognition()
        controller.simulateFailure("Network error")
        XCTAssertEqual(errorText, "Network error")
    }
}
