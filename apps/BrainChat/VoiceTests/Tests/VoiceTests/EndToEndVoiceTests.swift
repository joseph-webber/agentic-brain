import XCTest
@testable import VoiceTestLib

// MARK: - End-to-End Voice Tests
// Simulates: User speaks → Transcription → AI → Response → Speech output

final class EndToEndVoiceTests: XCTestCase {

    // MARK: - Full Conversation Loop

    func testFullVoiceConversationLoop() {
        let speech = MockSpeechRecognitionController()
        let ai = MockVoiceAIClient()
        let voice = MockVoiceSynthesizer()
        let store = MockConversationStore()

        ai.responses["What time is it in Adelaide"] = "It's 3:30 PM in Adelaide, Joseph."

        // 1: User speaks (spacebar → recognition starts)
        XCTAssertNoThrow(try speech.startRecognition())
        XCTAssertTrue(speech.isRecognising)

        // 2: Transcription produces text
        var transcribedText: String?
        speech.recognitionHandler = { update in
            if update.kind == .final { transcribedText = update.text }
        }
        speech.simulateFinalTranscript("What time is it in Adelaide")
        XCTAssertEqual(transcribedText, "What time is it in Adelaide",
                       "Transcription text must appear in UI")

        // 3: Add to conversation
        store.addMessage(role: .user, content: transcribedText!)
        store.isProcessing = true

        // 4: AI generates response
        let exp = XCTestExpectation(description: "AI response")
        ai.sendMessage(transcribedText!, model: "llama3.2:3b",
                       endpoint: "http://localhost:11434/api/chat") { result in
            if case .success(let response) = result {
                store.addMessage(role: .assistant, content: response)
                store.isProcessing = false
                voice.speak(response)
            }
            exp.fulfill()
        }
        wait(for: [exp], timeout: 2.0)

        // Verify entire pipeline
        XCTAssertEqual(store.messageCount, 2)
        XCTAssertEqual(store.userMessages.count, 1)
        XCTAssertEqual(store.assistantMessages.count, 1)
        XCTAssertEqual(store.assistantMessages[0].content, "It's 3:30 PM in Adelaide, Joseph.",
                       "AI response must be generated correctly")
        XCTAssertTrue(voice.isSpeaking, "Karen must speak the response")
        XCTAssertEqual(voice.spokenTexts[0], "It's 3:30 PM in Adelaide, Joseph.",
                       "Karen must speak the AI response")
        XCTAssertFalse(store.isProcessing)
    }

    // MARK: - Multiple Exchanges

    func testMultipleConversationExchanges() {
        let ai = MockVoiceAIClient()
        let voice = MockVoiceSynthesizer()
        let store = MockConversationStore()
        let speech = MockSpeechRecognitionController()

        let exchanges: [(query: String, response: String)] = [
            ("Hello Brain", "G'day Joseph! How can I help?"),
            ("What's the weather", "It's 24 degrees and sunny in Adelaide."),
            ("Read my JIRA tickets", "You have 3 open tickets: SD-1330, SD-1331, SD-1332."),
            ("Deploy to production", "Deploying now. All tests passed, pushing to main."),
        ]
        for (q, r) in exchanges { ai.responses[q] = r }

        for (index, exchange) in exchanges.enumerated() {
            var finalTranscript: String?
            speech.recognitionHandler = { update in
                if update.kind == .final { finalTranscript = update.text }
            }
            XCTAssertNoThrow(try speech.startRecognition())
            speech.simulateFinalTranscript(exchange.query)
            speech.stopRecognition()
            XCTAssertEqual(finalTranscript, exchange.query)

            store.addMessage(role: .user, content: exchange.query)
            let exp = XCTestExpectation(description: "Exchange \(index)")
            ai.sendMessage(exchange.query, model: "t", endpoint: "e") { result in
                if case .success(let response) = result {
                    store.addMessage(role: .assistant, content: response)
                    voice.speak(response)
                }
                exp.fulfill()
            }
            wait(for: [exp], timeout: 2.0)
        }

        XCTAssertEqual(store.messageCount, 8, "4 user + 4 assistant messages")
        XCTAssertEqual(voice.spokenTexts.count, 4, "Karen should speak all 4 responses")
        XCTAssertEqual(store.messages[0].content, "Hello Brain")
        XCTAssertEqual(store.messages[1].content, "G'day Joseph! How can I help?")
        XCTAssertEqual(store.messages[7].content,
                       "Deploying now. All tests passed, pushing to main.")
    }

    // MARK: - Interruption Handling

    func testInterruptionStopsSpeechAndStartsNew() {
        let voice = MockVoiceSynthesizer()
        let ai = MockVoiceAIClient()
        let store = MockConversationStore()

        ai.responses["first question"] = "Long response that takes a while..."
        ai.responses["interrupt now"] = "Interruption acknowledged."

        store.addMessage(role: .user, content: "first question")
        let exp1 = XCTestExpectation(description: "First response")
        ai.sendMessage("first question", model: "t", endpoint: "e") { result in
            if case .success(let response) = result {
                store.addMessage(role: .assistant, content: response)
                voice.speak(response)
            }
            exp1.fulfill()
        }
        wait(for: [exp1], timeout: 1.0)
        XCTAssertTrue(voice.isSpeaking)

        // User interrupts
        voice.stop()
        XCTAssertFalse(voice.isSpeaking, "Voice should stop on interruption")

        store.addMessage(role: .user, content: "interrupt now")
        let exp2 = XCTestExpectation(description: "Interrupt response")
        ai.sendMessage("interrupt now", model: "t", endpoint: "e") { result in
            if case .success(let response) = result {
                store.addMessage(role: .assistant, content: response)
                voice.speak(response)
            }
            exp2.fulfill()
        }
        wait(for: [exp2], timeout: 1.0)

        XCTAssertEqual(voice.spokenTexts.last, "Interruption acknowledged.")
        XCTAssertEqual(store.messageCount, 4)
    }

    func testInterruptionDuringRecognition() throws {
        let speech = MockSpeechRecognitionController()
        let voice = MockVoiceSynthesizer()

        voice.speak("Some long response")
        XCTAssertTrue(voice.isSpeaking)
        voice.stop()
        try speech.startRecognition()
        XCTAssertFalse(voice.isSpeaking, "Karen should stop when user starts speaking")
        XCTAssertTrue(speech.isRecognising, "Recognition should start after interrupt")
    }

    // MARK: - Conversation History Updates

    func testConversationHistoryUpdatesCorrectly() {
        let store = MockConversationStore()
        let id1 = store.addMessage(role: .user, content: "Hello")
        let id2 = store.addMessage(role: .assistant, content: "Hi Joseph!")
        let id3 = store.addMessage(role: .user, content: "How are you?")

        XCTAssertEqual(store.messageCount, 3,
                       "Conversation history must update with each exchange")
        XCTAssertNotEqual(id1, id2)
        XCTAssertNotEqual(id2, id3)
        XCTAssertEqual(store.messages[0].role, .user)
        XCTAssertEqual(store.messages[1].role, .assistant)
        XCTAssertEqual(store.messages[2].role, .user)
    }

    func testConversationHistoryPreservesUnicode() {
        let store = MockConversationStore()
        store.addMessage(role: .user, content: "Test: é à ü 日本語")
        store.addMessage(role: .assistant, content: "Unicode reply: 你好 🧠")
        XCTAssertEqual(store.messages[0].content, "Test: é à ü 日本語")
        XCTAssertEqual(store.messages[1].content, "Unicode reply: 你好 🧠")
    }

    func testConversationClear() {
        let store = MockConversationStore()
        store.addMessage(role: .user, content: "Hello")
        store.addMessage(role: .assistant, content: "Hi!")
        store.clear()
        XCTAssertEqual(store.messageCount, 1, "Clear should leave system message")
        XCTAssertEqual(store.messages[0].role, .system)
    }

    // MARK: - AI Error Recovery

    func testAIFailureRecoveryInConversation() {
        let ai = MockVoiceAIClient()
        let voice = MockVoiceSynthesizer()
        let store = MockConversationStore()
        ai.shouldFail = true

        store.addMessage(role: .user, content: "test")
        let exp = XCTestExpectation(description: "Error recovery")

        ai.sendMessage("test", model: "t", endpoint: "e") { result in
            switch result {
            case .failure:
                ai.shouldFail = false
                ai.responses["test"] = "Recovered response"
                ai.sendMessage("test", model: "t", endpoint: "e") { retryResult in
                    if case .success(let response) = retryResult {
                        store.addMessage(role: .assistant, content: response)
                        voice.speak(response)
                    }
                    exp.fulfill()
                }
            case .success:
                XCTFail("First call should fail")
                exp.fulfill()
            }
        }
        wait(for: [exp], timeout: 2.0)

        XCTAssertEqual(ai.callCount, 2)
        XCTAssertEqual(voice.spokenTexts[0], "Recovered response")
    }

    func testAIFailureShowsError() {
        let ai = MockVoiceAIClient()
        let store = MockConversationStore()
        ai.shouldFail = true

        let exp = XCTestExpectation(description: "Error message")
        ai.sendMessage("test", model: "t", endpoint: "e") { result in
            if case .failure(let error) = result {
                store.addMessage(role: .system, content: "Error: \(error.localizedDescription)")
            }
            exp.fulfill()
        }
        wait(for: [exp], timeout: 1.0)
        XCTAssertTrue(store.messages.last?.content.contains("Error:") ?? false)
    }

    // MARK: - Voice + AirPods Integration

    func testVoiceOutputRoutedToAirPods() throws {
        let airpods = MockAirPods()
        let voice = MockVoiceSynthesizer()
        airpods.simulateConnect()
        try airpods.routeAllAudioToAirPods()
        voice.speak("Hello through AirPods")
        XCTAssertTrue(voice.isSpeaking)
        XCTAssertEqual(airpods.routeAllCallCount, 1)
    }

    func testConversationPausesOnAirPodsDisconnect() {
        let airpods = MockAirPods()
        var notifications: [String] = []
        airpods.onNotification = { notifications.append($0) }
        airpods.simulateConnect()
        airpods.simulateDisconnect()
        XCTAssertTrue(notifications.last?.contains("disconnected") ?? false)
    }

    func testConversationResumesOnAirPodsReconnect() {
        let airpods = MockAirPods()
        var reconnected = false
        airpods.onStateChange = { connected in if connected { reconnected = true } }
        airpods.simulateConnect()
        airpods.simulateDisconnect()
        airpods.simulateConnect()
        XCTAssertTrue(reconnected)
    }

    // MARK: - Streaming Response

    func testStreamingResponseAppearsIncrementally() {
        let store = MockConversationStore()
        let deltas = ["G'day ", "Joseph! ", "How can ", "I help ", "you today?"]
        store.addMessage(role: .user, content: "Hello")
        store.addMessage(role: .assistant, content: "")
        for delta in deltas { store.appendToLastAssistant(delta) }
        let finalContent = store.assistantMessages.last?.content ?? ""
        XCTAssertEqual(finalContent, "G'day Joseph! How can I help you today?")
    }

    // MARK: - Accessibility

    func testAllMessagesHaveAccessibilityDescriptions() {
        let messages = [
            TestChatMessage(role: .user, content: "Hello"),
            TestChatMessage(role: .assistant, content: "Hi Joseph!"),
            TestChatMessage(role: .system, content: "Connected"),
        ]
        for msg in messages {
            let desc = msg.accessibilityDescription
            XCTAssertFalse(desc.isEmpty)
            XCTAssertTrue(desc.contains("said at"))
            XCTAssertTrue(desc.contains(msg.content))
        }
    }

    // MARK: - Stress Test

    func testRapidFireConversation() {
        let ai = MockVoiceAIClient()
        let voice = MockVoiceSynthesizer()
        let store = MockConversationStore()

        for i in 0..<20 { ai.responses["msg\(i)"] = "reply\(i)" }

        let group = DispatchGroup()
        for i in 0..<20 {
            store.addMessage(role: .user, content: "msg\(i)")
            group.enter()
            ai.sendMessage("msg\(i)", model: "t", endpoint: "e") { result in
                if case .success(let response) = result {
                    store.addMessage(role: .assistant, content: response)
                    voice.speak(response)
                }
                group.leave()
            }
        }

        let result = group.wait(timeout: .now() + 5)
        XCTAssertEqual(result, .success, "All 20 exchanges must complete")
        XCTAssertEqual(store.messageCount, 40)
        XCTAssertEqual(voice.spokenTexts.count, 20)
    }
}
