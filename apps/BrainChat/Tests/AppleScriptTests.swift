import XCTest
@testable import BrainChatLib

/// Tests that the AppleScript NSScriptCommand handlers work correctly
/// without requiring the app to be running. We instantiate the command
/// objects directly and validate their behaviour.
final class AppleScriptTests: XCTestCase {

    // MARK: - SendMessageCommand

    @MainActor
    func testSendMessageReturnsErrorWhenBridgeNotReady() {
        let bridge = ScriptingBridge.shared
        let oldStore = bridge.conversationStore
        bridge.conversationStore = nil
        defer { bridge.conversationStore = oldStore }

        let cmd = SendMessageCommand()
        cmd.directParameter = "hello" as NSString

        let result = cmd.performDefaultImplementation()
        if let text = result as? String {
            XCTAssertTrue(text.contains("error"), "Expected error message, got: \(text)")
        }
    }

    @MainActor
    func testSendMessageRejectsEmptyInput() {
        let cmd = SendMessageCommand()
        cmd.directParameter = "   " as NSString
        let result = cmd.performDefaultImplementation()
        XCTAssertNil(result, "Empty input should return nil (error)")
    }

    @MainActor
    func testSendMessageAddsUserMessageToStore() {
        let store = ConversationStore()
        let settings = AppSettings()
        let router = LLMRouter()

        let bridge = ScriptingBridge.shared
        let oldStore = bridge.conversationStore
        let oldSettings = bridge.settings
        let oldRouter = bridge.llmRouter
        bridge.conversationStore = store
        bridge.settings = settings
        bridge.llmRouter = router
        defer {
            bridge.conversationStore = oldStore
            bridge.settings = oldSettings
            bridge.llmRouter = oldRouter
        }

        let cmd = SendMessageCommand()
        cmd.directParameter = "test message" as NSString

        // On main thread, LLM call can't complete (returns error), but
        // the user message should still be added to the store.
        _ = cmd.performDefaultImplementation()

        let userMessages = store.messages.filter { $0.role == .user }
        XCTAssertEqual(userMessages.count, 1)
        XCTAssertEqual(userMessages.first?.content, "test message")
    }

    // MARK: - GetConversationCommand

    @MainActor
    func testGetConversationReturnsEmptyWhenNoBridge() {
        let bridge = ScriptingBridge.shared
        let oldStore = bridge.conversationStore
        bridge.conversationStore = nil
        defer { bridge.conversationStore = oldStore }

        let cmd = GetConversationCommand()
        let result = cmd.performDefaultImplementation() as? String
        XCTAssertEqual(result, "", "Should return empty string when bridge has no store")
    }

    @MainActor
    func testGetConversationFormatsMessages() {
        let store = ConversationStore()
        store.addMessage(role: .user, content: "ping")
        store.addMessage(role: .assistant, content: "pong")

        let bridge = ScriptingBridge.shared
        let oldStore = bridge.conversationStore
        bridge.conversationStore = store
        defer { bridge.conversationStore = oldStore }

        let cmd = GetConversationCommand()
        let result = cmd.performDefaultImplementation() as? String ?? ""
        XCTAssertTrue(result.contains("[You] ping"), "Should contain user message, got: \(result)")
        XCTAssertTrue(result.contains("[Karen] pong"), "Should contain assistant message, got: \(result)")
    }

    // MARK: - SetProviderCommand

    @MainActor
    func testSetProviderResolvesKnownNames() {
        let router = LLMRouter()
        let bridge = ScriptingBridge.shared
        let oldRouter = bridge.llmRouter
        bridge.llmRouter = router
        defer { bridge.llmRouter = oldRouter }

        let cmd = SetProviderCommand()
        cmd.directParameter = "claude" as NSString
        _ = cmd.performDefaultImplementation()

        // onMain runs synchronously on the main thread
        XCTAssertEqual(router.selectedProvider, .claude)
    }

    @MainActor
    func testSetProviderRejectsUnknownName() {
        let cmd = SetProviderCommand()
        cmd.directParameter = "nonexistent_provider" as NSString
        let result = cmd.performDefaultImplementation()
        XCTAssertNil(result)
    }

    // MARK: - SpeakTextCommand

    @MainActor
    func testSpeakRejectsEmptyText() {
        let cmd = SpeakTextCommand()
        cmd.directParameter = "" as NSString
        let result = cmd.performDefaultImplementation()
        XCTAssertNil(result, "Empty text should be rejected")
    }

    // MARK: - Start/Stop Listening (smoke tests)

    @MainActor
    func testStartListeningDoesNotCrashWithoutBridge() {
        let bridge = ScriptingBridge.shared
        let old = bridge.speechManager
        bridge.speechManager = nil
        defer { bridge.speechManager = old }

        let cmd = StartListeningCommand()
        _ = cmd.performDefaultImplementation()
    }

    @MainActor
    func testStopListeningDoesNotCrashWithoutBridge() {
        let bridge = ScriptingBridge.shared
        let old = bridge.speechManager
        bridge.speechManager = nil
        defer { bridge.speechManager = old }

        let cmd = StopListeningCommand()
        _ = cmd.performDefaultImplementation()
    }
}
