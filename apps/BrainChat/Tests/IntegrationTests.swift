import XCTest
@testable import BrainChatLib

// MARK: - Integration Tests

final class IntegrationTests: XCTestCase {

    // MARK: - Chat Message Model

    func testChatMessageCreation() {
        let msg = TestChatMessage(role: .user, content: "Hello Brain")
        XCTAssertEqual(msg.role, .user)
        XCTAssertEqual(msg.content, "Hello Brain")
        XCTAssertNotNil(msg.id)
    }

    func testChatMessageEquality() {
        let msg1 = TestChatMessage(role: .user, content: "Hello")
        let msg2 = TestChatMessage(role: .user, content: "Hello")
        // Different UUIDs so they should NOT be equal
        XCTAssertNotEqual(msg1, msg2)
        // Same instance should be equal
        XCTAssertEqual(msg1, msg1)
    }

    func testChatMessageAccessibility() {
        let msg = TestChatMessage(role: .assistant, content: "Here's your answer")
        let description = msg.accessibilityDescription

        XCTAssertTrue(description.contains("Brain"),
                      "Accessibility description must include role name")
        XCTAssertTrue(description.contains("Here's your answer"),
                      "Accessibility description must include content")
        XCTAssertTrue(description.contains("said at"),
                      "Accessibility description must include timing context")
    }

    func testChatMessageRoles() {
        XCTAssertEqual(TestChatMessage.Role.user.rawValue, "You")
        XCTAssertEqual(TestChatMessage.Role.assistant.rawValue, "Brain")
        XCTAssertEqual(TestChatMessage.Role.system.rawValue, "System")
    }

    // MARK: - Conversation Store

    func testConversationStoreAddMessage() {
        let store = TestConversationStore()
        store.addMessage(role: .user, content: "Hello")

        XCTAssertEqual(store.messages.count, 1)
        XCTAssertEqual(store.messages[0].content, "Hello")
        XCTAssertEqual(store.messages[0].role, .user)
    }

    func testConversationStoreClear() {
        let store = TestConversationStore()
        store.addMessage(role: .user, content: "Hello")
        store.addMessage(role: .assistant, content: "Hi!")
        XCTAssertEqual(store.messages.count, 2)

        store.clear()
        XCTAssertEqual(store.messages.count, 1, "Clear should leave system message")
        XCTAssertEqual(store.messages[0].role, .system)
        XCTAssertTrue(store.messages[0].content.contains("cleared"))
    }

    func testConversationStoreProcessingState() {
        let store = TestConversationStore()
        XCTAssertFalse(store.isProcessing)

        store.isProcessing = true
        XCTAssertTrue(store.isProcessing)
    }

    // MARK: - Audio Device Model

    func testAudioDeviceCreation() {
        let device = TestAudioDevice(id: "42", name: "AirPods Max", isAirPodsMax: true)

        XCTAssertEqual(device.id, "42")
        XCTAssertEqual(device.name, "AirPods Max")
        XCTAssertTrue(device.isAirPodsMax)
    }

    func testAudioDeviceHashable() {
        let device1 = TestAudioDevice(id: "1", name: "Mic A")
        let device2 = TestAudioDevice(id: "2", name: "Mic B")
        let device3 = TestAudioDevice(id: "1", name: "Mic A")

        var deviceSet: Set<TestAudioDevice> = []
        deviceSet.insert(device1)
        deviceSet.insert(device2)
        deviceSet.insert(device3)

        XCTAssertEqual(deviceSet.count, 2, "Duplicate devices should not be added")
    }

    // MARK: - Route Detection (CodeAssistant)

    func testRouteDetectionCoding() {
        let detector = RouteDetector()

        let codingMessages = [
            "write a function to sort an array",
            "implement a binary search in Swift",
            "fix this bug in the authentication code",
            "refactor the database query",
            "debug the crash in ContentView"
        ]

        for msg in codingMessages {
            let route = detector.detectRoute(for: msg)
            XCTAssertEqual(route, .copilot,
                           "'\(msg)' should route to copilot, got \(route)")
        }
    }

    func testRouteDetectionSystem() {
        let detector = RouteDetector()

        let systemMessages = [
            "read my clipboard",
            "run tests please",
            "open app Safari",
            "git status",
            "what's the frontmost app"
        ]

        for msg in systemMessages {
            let route = detector.detectRoute(for: msg)
            XCTAssertEqual(route, .system,
                           "'\(msg)' should route to system, got \(route)")
        }
    }

    func testRouteDetectionGeneral() {
        let detector = RouteDetector()

        let generalMessages = [
            "what's the weather today",
            "tell me a joke",
            "how are you doing",
            "what time is it in Adelaide"
        ]

        for msg in generalMessages {
            let route = detector.detectRoute(for: msg)
            XCTAssertEqual(route, .general,
                           "'\(msg)' should route to general, got \(route)")
        }
    }

    // MARK: - Path Validation (SystemCommands)

    func testPathValidationAllowed() {
        let validator = PathValidator(allowedRoots: [
            "/Users/joe", "/Users/joe/brain"
        ])

        let allowedPaths = [
            "/Users/joe/brain/test.py",
            "/Users/joe/Documents/file.txt",
            "/Users/joe/brain/apps/BrainChat/build.sh"
        ]

        for path in allowedPaths {
            XCTAssertTrue(validator.validate(path),
                          "Path should be allowed: \(path)")
        }
    }

    func testPathValidationBlocked() {
        let validator = PathValidator(allowedRoots: ["/Users/joe"])

        let blockedPaths = [
            "/etc/passwd",
            "/var/root/.ssh/authorized_keys",
            "/System/Library/test",
            "/tmp/evil"
        ]

        for path in blockedPaths {
            XCTAssertFalse(validator.validate(path),
                           "Path should be blocked: \(path)")
        }
    }

    // MARK: - Command Safety

    func testBlockedCommands() {
        let safety = CommandSafety()

        let dangerous = [
            "rm -rf /",
            "rm -rf /*",
            "mkfs /dev/sda1",
            "reboot",
            "shutdown -h now",
            "dd if=/dev/zero of=/dev/sda"
        ]

        for cmd in dangerous {
            XCTAssertTrue(safety.isBlocked(cmd),
                          "Command should be blocked: \(cmd)")
        }
    }

    func testAllowedCommands() {
        let safety = CommandSafety()

        let safe = [
            "ls -la",
            "cat file.txt",
            "swift build",
            "python3 test.py",
            "git status"
        ]

        for cmd in safe {
            XCTAssertFalse(safety.isBlocked(cmd),
                           "Command should be allowed: \(cmd)")
        }
    }

    // MARK: - End-to-End Flow

    func testFullChatFlow() {
        let store = TestConversationStore()
        let ai = MockAIClient()
        ai.responses["Hello Brain"] = "Hello user! How can I help?"

        // User sends message
        store.addMessage(role: .user, content: "Hello Brain")
        store.isProcessing = true

        let exp = XCTestExpectation(description: "AI response")

        ai.sendMessage("Hello Brain", model: "llama3.2:3b",
                       endpoint: "http://localhost:11434/api/chat") { result in
            switch result {
            case .success(let response):
                store.addMessage(role: .assistant, content: response)
                store.isProcessing = false
            case .failure:
                XCTFail("Should succeed")
            }
            exp.fulfill()
        }

        wait(for: [exp], timeout: 2.0)

        XCTAssertEqual(store.messages.count, 2)
        XCTAssertEqual(store.messages[0].role, .user)
        XCTAssertEqual(store.messages[1].role, .assistant)
        XCTAssertEqual(store.messages[1].content, "Hello user! How can I help?")
        XCTAssertFalse(store.isProcessing)
    }

    func testChatFlowWithVoice() {
        let store = TestConversationStore()
        let ai = MockAIClient()
        let voice = MockVoiceSynthesizer()

        ai.responses["test"] = "Here's the answer"

        store.addMessage(role: .user, content: "test")

        let exp = XCTestExpectation(description: "AI + voice")

        ai.sendMessage("test", model: "test", endpoint: "http://test") { result in
            if case .success(let response) = result {
                store.addMessage(role: .assistant, content: response)
                voice.speak(response)
            }
            exp.fulfill()
        }

        wait(for: [exp], timeout: 2.0)

        XCTAssertEqual(voice.spokenTexts.count, 1)
        XCTAssertEqual(voice.spokenTexts[0], "Here's the answer")
        XCTAssertTrue(voice.isSpeaking)
    }

    func testChatFlowWithSpeechInput() {
        let store = TestConversationStore()
        let speech = MockSpeechRecognizer()
        let ai = MockAIClient()
        ai.responses["What time is it"] = "It's 3:30 PM in Adelaide"

        var transcriptProcessed = false

        speech.onTranscriptFinalized = { text in
            store.addMessage(role: .user, content: text)
            transcriptProcessed = true
        }

        speech.startListening()
        speech.simulateTranscription("What time is it")

        XCTAssertTrue(transcriptProcessed)
        XCTAssertEqual(store.messages.count, 1)
        XCTAssertEqual(store.messages[0].content, "What time is it")
    }

    // MARK: - Copilot Integration Flow

    func testCopilotCodeFlow() {
        let copilot = MockCopilotBridge()
        let store = TestConversationStore()

        copilot.responses["write a sort function"] = TestCopilotResponse(
            text: "```swift\nfunc sort(_ arr: [Int]) -> [Int] { arr.sorted() }\n```",
            isCodeBlock: true,
            language: "swift",
            codeBlocks: [
                (language: "swift", code: "func sort(_ arr: [Int]) -> [Int] { arr.sorted() }")
            ]
        )

        store.addMessage(role: .user, content: "write a sort function")

        let exp = XCTestExpectation(description: "Copilot code")

        copilot.execute(prompt: "write a sort function") { result in
            if case .success(let response) = result {
                store.addMessage(role: .assistant, content: response.text)
                XCTAssertTrue(response.isCodeBlock)
                XCTAssertEqual(response.codeBlocks.count, 1)
            }
            exp.fulfill()
        }

        wait(for: [exp], timeout: 2.0)
        XCTAssertEqual(store.messages.count, 2)
    }

    // MARK: - Error Recovery

    func testAIErrorRecovery() {
        let ai = MockAIClient()
        ai.shouldFail = true

        let exp = XCTestExpectation(description: "Error recovery")

        ai.sendMessage("test", model: "test", endpoint: "http://test") { result in
            switch result {
            case .success:
                XCTFail("First call should fail")
            case .failure:
                // Recover
                ai.shouldFail = false
                ai.sendMessage("test", model: "test", endpoint: "http://test") { retryResult in
                    switch retryResult {
                    case .success(let response):
                        XCTAssertFalse(response.isEmpty)
                    case .failure:
                        XCTFail("Retry should succeed")
                    }
                    exp.fulfill()
                }
            }
        }

        wait(for: [exp], timeout: 2.0)
        XCTAssertEqual(ai.callCount, 2)
    }

    // MARK: - Accessibility

    func testAllRolesHaveAccessibleNames() {
        let roles: [TestChatMessage.Role] = [.user, .assistant, .system]

        for role in roles {
            XCTAssertFalse(role.rawValue.isEmpty,
                           "Role \(role) must have a non-empty display name")
        }
    }

    func testMessageAccessibilityFormat() {
        let msg = TestChatMessage(role: .user, content: "Test message")
        let desc = msg.accessibilityDescription

        // Should be: "You said at HH:MM: Test message"
        XCTAssertTrue(desc.hasPrefix("You said at"))
        XCTAssertTrue(desc.hasSuffix("Test message"))
    }
}
