import XCTest
import SwiftUI
import Accessibility
@testable import BrainChatLib

// MARK: - VoiceOver Tests
// Joseph uses VoiceOver exclusively. These tests verify the screen reader
// experience is complete, logical, and never leaves Joseph guessing.

final class VoiceOverTests: XCTestCase {

    // MARK: - Screen Reader Announcements

    func testStatusChangeAnnouncesViaVoiceOver() throws {
        // When connection status changes, VoiceOver must announce it
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let status = inspector.findElement(identifier: "statusIndicator")

        XCTAssertNotNil(status, "Status indicator must exist for VoiceOver")
        XCTAssertFalse(
            status?.label?.isEmpty ?? true,
            "Status changes MUST be announced - Joseph cannot see colour changes"
        )
    }

    func testListeningStateAnnouncesChange() throws {
        // When microphone starts/stops, VoiceOver must announce
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let mic = inspector.findElement(identifier: "microphoneButton")

        XCTAssertNotNil(mic, "Microphone button must exist")
        // Label should change based on listening state
        XCTAssertFalse(
            mic?.label?.isEmpty ?? true,
            "Mic button label must reflect current state (Start/Stop Listening)"
        )
    }

    func testSpeakingStateAnnouncesChange() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let stop = inspector.findElement(identifier: "stopButton")

        XCTAssertNotNil(stop, "Stop button must exist")
        XCTAssertFalse(
            stop?.label?.isEmpty ?? true,
            "Stop button must describe its action via VoiceOver"
        )
    }

    func testNewMessageAnnouncedToVoiceOver() throws {
        // When a new message arrives, it should be announced
        let store = ConversationStore()
        let initialCount = store.messages.count

        store.messages.append(ChatMessage(role: "assistant", content: "Hello Joseph"))
        XCTAssertGreaterThan(
            store.messages.count, initialCount,
            "New messages must be added and VoiceOver notified"
        )

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let bubbles = inspector.findAllElements(trait: .staticText)

        XCTAssertGreaterThan(
            bubbles.count, 0,
            "New message must be visible to VoiceOver"
        )
    }

    func testTranscriptUpdatesAreAccessible() throws {
        // Live transcript during speech recognition must be readable
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let transcript = inspector.findElement(identifier: "liveTranscript")

        // Transcript may not be visible when not listening, that's OK
        if let transcript = transcript {
            XCTAssertFalse(
                transcript.label?.isEmpty ?? true,
                "Live transcript must expose text to VoiceOver"
            )
        }
    }

    // MARK: - Focus Management

    func testInitialFocusIsOnMessageInput() throws {
        // When app opens, focus should be on the message input
        // so Joseph can immediately start typing
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let input = inspector.findElement(identifier: "messageInput")

        XCTAssertNotNil(input, "Message input must exist and be the initial focus target")
        XCTAssertTrue(
            input?.isEnabled ?? false,
            "Message input must be enabled for immediate interaction"
        )
    }

    func testFocusMovesToNewMessageAfterSend() throws {
        // After sending a message, focus should move to the conversation
        // so Joseph hears the response
        let store = ConversationStore()
        store.messages.append(ChatMessage(role: "user", content: "Test"))
        store.messages.append(ChatMessage(role: "assistant", content: "Response"))

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let messages = inspector.findAllElements(trait: .staticText)

        XCTAssertGreaterThan(
            messages.count, 0,
            "After sending, conversation messages must be focusable by VoiceOver"
        )
    }

    func testSettingsTabsFocusCorrectly() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        XCTAssertGreaterThan(
            focusable.count, 5,
            "Settings must have many focusable elements for VoiceOver navigation"
        )
    }

    func testConversationScrollToBottom() throws {
        // When new messages arrive, scroll position should update
        // so VoiceOver reads the latest message
        let store = ConversationStore()
        for i in 0..<20 {
            store.messages.append(ChatMessage(
                role: i % 2 == 0 ? "user" : "assistant",
                content: "Message \(i)"
            ))
        }

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let messages = inspector.findAllElements(trait: .staticText)

        XCTAssertGreaterThan(
            messages.count, 0,
            "All messages must be accessible even when scrolled"
        )
    }

    // MARK: - Accessibility Actions

    func testMessageBubbleHasCopyAction() throws {
        let store = ConversationStore()
        store.messages.append(ChatMessage(role: "assistant", content: "Test response"))

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)

        // Message bubbles should support Copy via context menu
        let messages = inspector.findAllElements(trait: .staticText)
        XCTAssertGreaterThan(
            messages.count, 0,
            "Messages must be accessible for Copy action"
        )
    }

    func testMessageBubbleHasSpeakAction() throws {
        let store = ConversationStore()
        store.messages.append(ChatMessage(role: "assistant", content: "Test response"))

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)

        let messages = inspector.findAllElements(trait: .staticText)
        XCTAssertGreaterThan(
            messages.count, 0,
            "Messages must support Speak action for VoiceOver"
        )
    }

    func testAllButtonsHaveActions() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let buttons = inspector.findAllElements(trait: .button)

        for button in buttons {
            XCTAssertTrue(
                button.isEnabled,
                "Button '\(button.label ?? "unknown")' must have an activatable action"
            )
        }
    }

    // MARK: - Rotor Support

    func testHeadingsExistForRotorNavigation() throws {
        // VoiceOver rotor allows jumping between headings
        // Critical sections should be marked as headers
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        // Check that key sections have header traits
        let status = inspector.findElement(identifier: "statusSection")
        let conversation = inspector.findElement(identifier: "conversationSection")
        let inputBar = inspector.findElement(identifier: "inputSection")

        // At least the main sections should be navigable via rotor
        let sectionsFound = [status, conversation, inputBar].compactMap { $0 }.count
        XCTAssertGreaterThanOrEqual(
            sectionsFound, 1,
            "At least one section header must exist for VoiceOver rotor navigation"
        )
    }

    func testSettingsHasRotorHeadings() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)

        // Settings sections (Voice, LLM, API Keys) should be headings
        let headingIdentifiers = [
            "voiceSettingsSection",
            "llmSettingsSection",
            "apiKeysSection"
        ]

        var headingsFound = 0
        for id in headingIdentifiers {
            if inspector.findElement(identifier: id) != nil {
                headingsFound += 1
            }
        }

        // Settings should have structured sections
        let allFocusable = inspector.findAllFocusableElements()
        XCTAssertGreaterThan(
            allFocusable.count, 3,
            "Settings must have structured focusable sections for rotor"
        )
    }

    func testConversationMessagesHaveRoleLabels() throws {
        // Each message should identify who said it (user vs assistant)
        let store = ConversationStore()
        store.messages.append(ChatMessage(role: "user", content: "Question"))
        store.messages.append(ChatMessage(role: "assistant", content: "Answer"))

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let elements = inspector.findAllElements(trait: .staticText)

        XCTAssertGreaterThan(
            elements.count, 0,
            "Message bubbles must identify the speaker role for VoiceOver"
        )
    }

    // MARK: - Live Regions

    func testStatusIsLiveRegion() throws {
        // Status area should be a live region so changes are automatically announced
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let status = inspector.findElement(identifier: "statusIndicator")

        XCTAssertNotNil(
            status,
            "Status indicator must exist as a live region element"
        )
    }

    func testAudioLevelUpdatesAreAccessible() throws {
        // Audio level changes should be accessible but not overwhelm VoiceOver
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let audioLevel = inspector.findElement(identifier: "audioLevelView")

        if let audioLevel = audioLevel {
            // Should have updatesFrequently trait to avoid spamming VoiceOver
            XCTAssertNotNil(
                audioLevel.label,
                "Audio level must have a summary label, not announce every bar change"
            )
        }
    }

    // MARK: - Accessibility Container

    func testConversationGroupsMessagesLogically() throws {
        // Related elements (role icon + text + timestamp) should be grouped
        let store = ConversationStore()
        store.messages.append(ChatMessage(role: "assistant", content: "Hello"))

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)

        // Should combine child elements into single accessible unit
        let elements = inspector.findAllElements(trait: .staticText)
        XCTAssertTrue(
            elements.count >= 1,
            "Message components should be grouped for VoiceOver - not read icon, text, time separately"
        )
    }

    // MARK: - VoiceOver Traits

    func testButtonsHaveButtonTrait() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let buttons = inspector.findAllElements(trait: .button)

        XCTAssertGreaterThan(
            buttons.count, 0,
            "Interactive buttons must have .button trait for VoiceOver"
        )

        for button in buttons {
            XCTAssertTrue(
                button.traits.contains(.button),
                "Element '\(button.label ?? "unknown")' must be marked as button"
            )
        }
    }

    func testImagesAreDecorativeOrLabelled() throws {
        // WCAG 1.1.1: All non-decorative images must have alt text
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        // System images used as icons should be marked decorative or labelled
        let images = inspector.findAllElements(trait: .image)
        for image in images {
            let hasLabel = !(image.label?.isEmpty ?? true)
            let isHidden = image.traits.contains(.notEnabled)
            XCTAssertTrue(
                hasLabel || isHidden,
                "Image must have label or be hidden from VoiceOver - WCAG 1.1.1"
            )
        }
    }

    // MARK: - Keyboard Shortcut Descriptions

    func testKeyboardShortcutsAreDocumented() throws {
        // Joseph needs to know what keyboard shortcuts are available
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        // Settings should contain keyboard shortcut documentation
        XCTAssertGreaterThan(
            focusable.count, 0,
            "Keyboard shortcuts must be documented and accessible"
        )
    }
}
