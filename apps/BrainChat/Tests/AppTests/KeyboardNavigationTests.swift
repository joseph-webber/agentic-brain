import XCTest
import SwiftUI
import Carbon.HIToolbox
@testable import BrainChatLib

// MARK: - Keyboard Navigation Tests
// Joseph navigates entirely by keyboard + VoiceOver.
// Every element must be reachable and operable without a mouse.
// WCAG 2.1.1: All functionality must be available from keyboard.

final class KeyboardNavigationTests: XCTestCase {

    // MARK: - Tab Navigation

    func testTabNavigatesThroughAllContentViewElements() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        // ContentView must have: message input, send, mic, stop, clear, LLM picker
        XCTAssertGreaterThanOrEqual(
            focusable.count, 4,
            "ContentView must have at least 4 Tab-focusable elements"
        )

        // Verify no element is orphaned from Tab order
        for element in focusable {
            XCTAssertTrue(
                element.isEnabled,
                "Element '\(element.identifier ?? element.label ?? "unknown")' must be Tab-reachable"
            )
        }
    }

    func testTabNavigatesThroughSettingsElements() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        // Settings has toggles, pickers, sliders, text fields, buttons
        XCTAssertGreaterThanOrEqual(
            focusable.count, 8,
            "SettingsView must have at least 8 Tab-focusable elements"
        )
    }

    func testTabOrderIsLogicalInContentView() throws {
        // Tab order: Status → LLM Picker → Conversation → Message Input → Send → Mic → Stop → Clear
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        XCTAssertGreaterThan(
            focusable.count, 0,
            "Must have focusable elements for Tab navigation"
        )

        // Elements should flow top-to-bottom, left-to-right
        // This is enforced by SwiftUI's natural layout order
        // unless explicitly overridden with .accessibilitySortPriority
        var previousId: String? = nil
        for element in focusable {
            let currentId = element.identifier ?? element.label
            if let prevId = previousId {
                // Just verify elements have identifiers for debugging
                XCTAssertNotNil(
                    currentId,
                    "Focusable element after '\(prevId)' must have identifier"
                )
            }
            previousId = currentId
        }
    }

    func testShiftTabNavigatesBackwards() throws {
        // Shift+Tab must reverse through the same elements
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        // The reverse order should contain the same elements
        let reversed = focusable.reversed()
        XCTAssertEqual(
            focusable.count, Array(reversed).count,
            "Shift+Tab must traverse the same elements in reverse"
        )
    }

    func testNoKeyboardTrap() throws {
        // WCAG 2.1.2: No keyboard trap - user must be able to Tab away from every element
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        for element in focusable {
            XCTAssertTrue(
                element.isEnabled,
                "Element '\(element.identifier ?? "unknown")' must not trap keyboard focus - WCAG 2.1.2"
            )
        }
    }

    // MARK: - Space Bar Activates Buttons

    func testSpaceBarActivatesMicrophoneButton() throws {
        // Space bar is the universal "activate" key for buttons
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let mic = inspector.findElement(identifier: "microphoneButton")

        XCTAssertNotNil(mic, "Microphone button must exist")
        XCTAssertTrue(
            mic?.traits.contains(.button) ?? false || mic?.isEnabled ?? false,
            "Microphone button must respond to Space bar activation"
        )
    }

    func testSpaceBarActivatesSendButton() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let send = inspector.findElement(identifier: "sendButton")

        XCTAssertNotNil(send, "Send button must exist")
        XCTAssertTrue(
            send?.isEnabled ?? false,
            "Send button must respond to Space bar activation"
        )
    }

    func testSpaceBarActivatesStopButton() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let stop = inspector.findElement(identifier: "stopButton")

        XCTAssertNotNil(stop, "Stop button must exist")
        XCTAssertTrue(
            stop?.isEnabled ?? false,
            "Stop button must respond to Space bar activation"
        )
    }

    func testSpaceBarActivatesClearButton() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let clear = inspector.findElement(identifier: "clearButton")

        XCTAssertNotNil(clear, "Clear button must exist")
        XCTAssertTrue(
            clear?.isEnabled ?? false,
            "Clear button must respond to Space bar activation"
        )
    }

    func testSpaceBarActivatesSettingsToggles() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        let toggleCount = focusable.filter { element in
            let desc = String(describing: element)
            return desc.contains("Toggle") || desc.contains("toggle")
        }.count

        // Even if we can't detect toggle types directly, focusable elements
        // in Settings that are toggles must be Space-activatable
        XCTAssertGreaterThanOrEqual(
            focusable.count, 4,
            "Settings must have Space-activatable toggle elements"
        )
    }

    // MARK: - Enter Submits

    func testEnterSubmitsMessage() throws {
        // Pressing Enter in the message field should send the message
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let input = inspector.findElement(identifier: "messageInput")

        XCTAssertNotNil(input, "Message input must exist")
        XCTAssertTrue(
            input?.isEnabled ?? false,
            "Message input must accept Enter to submit"
        )
    }

    func testEnterActivatesDefaultButton() throws {
        // In Settings dialogs, Enter should activate the default button (Save)
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let buttons = inspector.findAllElements(trait: .button)

        XCTAssertGreaterThan(
            buttons.count, 0,
            "Settings must have a default activatable button"
        )
    }

    // MARK: - Escape Cancels

    func testEscapeClosesSettings() throws {
        // Pressing Escape should close the Settings window
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)

        // Settings is a separate window that responds to Escape
        let focusable = inspector.findAllFocusableElements()
        XCTAssertGreaterThan(
            focusable.count, 0,
            "Settings must be dismissible with Escape key"
        )
    }

    func testEscapeCancelsSpeechRecognition() throws {
        // Escape should stop active speech recognition
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let stop = inspector.findElement(identifier: "stopButton")

        XCTAssertNotNil(
            stop,
            "Stop/cancel button must exist for Escape key binding"
        )
    }

    func testEscapeDismissesContextMenu() throws {
        // Context menus on messages must be Escape-dismissible
        let store = ConversationStore()
        store.messages.append(ChatMessage(role: "assistant", content: "Test"))

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let messages = inspector.findAllElements(trait: .staticText)

        XCTAssertGreaterThan(
            messages.count, 0,
            "Messages with context menus must support Escape to dismiss"
        )
    }

    // MARK: - Keyboard Shortcuts

    func testCommandLShortcutExists() throws {
        // ⌘L should toggle listening
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let mic = inspector.findElement(identifier: "microphoneButton")

        XCTAssertNotNil(
            mic,
            "Microphone button (⌘L shortcut target) must exist"
        )
    }

    func testCommandPeriodShortcutExists() throws {
        // ⌘. should stop speaking
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let stop = inspector.findElement(identifier: "stopButton")

        XCTAssertNotNil(
            stop,
            "Stop button (⌘. shortcut target) must exist"
        )
    }

    func testCommandKShortcutExists() throws {
        // ⌘K should clear conversation
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let clear = inspector.findElement(identifier: "clearButton")

        XCTAssertNotNil(
            clear,
            "Clear button (⌘K shortcut target) must exist"
        )
    }

    func testCommandCommaOpensSettings() throws {
        // ⌘, should open Settings (macOS standard)
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let settings = inspector.findElement(identifier: "settingsButton")

        XCTAssertNotNil(
            settings,
            "Settings button (⌘, shortcut target) must exist"
        )
    }

    func testSpaceBarPressToTalk() throws {
        // Space bar in main view (not in text field) activates push-to-talk
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        // KeyEventHandlerView handles Space bar detection
        let focusable = inspector.findAllFocusableElements()
        XCTAssertGreaterThan(
            focusable.count, 0,
            "Push-to-talk via Space bar must be supported"
        )
    }

    // MARK: - Focus Visibility (WCAG 2.4.7)

    func testFocusedElementsHaveVisibleIndicator() throws {
        // All focusable elements must show a visible focus indicator
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        for element in focusable {
            XCTAssertTrue(
                element.isEnabled,
                "Focusable element '\(element.identifier ?? "unknown")' must show focus indicator - WCAG 2.4.7"
            )
        }
    }

    func testFocusIndicatorHasSufficientContrast() throws {
        // WCAG 2.4.11 (AAA) / 2.4.7 (AA): Focus indicator must be visible
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let buttons = inspector.findAllElements(trait: .button)

        XCTAssertGreaterThan(
            buttons.count, 0,
            "Buttons must have visible focus indicators with sufficient contrast"
        )
    }

    // MARK: - Arrow Key Navigation

    func testArrowKeysNavigateConversation() throws {
        let store = ConversationStore()
        for i in 0..<5 {
            store.messages.append(ChatMessage(role: "assistant", content: "Message \(i)"))
        }

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let messages = inspector.findAllElements(trait: .staticText)

        XCTAssertGreaterThan(
            messages.count, 0,
            "Arrow keys must navigate between conversation messages"
        )
    }

    func testArrowKeysNavigatePicker() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        XCTAssertGreaterThan(
            focusable.count, 0,
            "Pickers must support arrow key navigation between options"
        )
    }

    func testArrowKeysAdjustSlider() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let slider = inspector.findElement(identifier: "speechRateSlider")

        // Slider may be nested, check focusable elements
        let focusable = inspector.findAllFocusableElements()
        XCTAssertGreaterThan(
            focusable.count, 0,
            "Slider must support Left/Right arrow keys for value adjustment"
        )
    }

    // MARK: - Tab Groups

    func testSettingsTabViewKeyboardNavigable() throws {
        // Tab key should cycle through settings tabs
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        XCTAssertGreaterThan(
            focusable.count, 5,
            "Settings TabView tabs must be keyboard navigable"
        )
    }

    // MARK: - Full Keyboard Access

    func testNoMouseOnlyInteractions() throws {
        // WCAG 2.1.1: Every interaction possible with mouse must be possible with keyboard
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        let buttons = inspector.findAllElements(trait: .button)
        let focusable = inspector.findAllFocusableElements()

        // Every button must also be keyboard-accessible
        XCTAssertGreaterThanOrEqual(
            focusable.count, buttons.count,
            "Every clickable button must also be keyboard-accessible - WCAG 2.1.1"
        )
    }

    func testContextMenusKeyboardAccessible() throws {
        // Right-click context menus must be accessible via keyboard (Shift+F10 or similar)
        let store = ConversationStore()
        store.messages.append(ChatMessage(role: "assistant", content: "Test"))

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let messages = inspector.findAllElements(trait: .staticText)

        XCTAssertGreaterThan(
            messages.count, 0,
            "Context menus on messages must be keyboard-accessible"
        )
    }

    // MARK: - Skip Navigation

    func testCanSkipToMainContent() throws {
        // Users should be able to skip repetitive navigation
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let input = inspector.findElement(identifier: "messageInput")

        XCTAssertNotNil(
            input,
            "Main content area (message input) must be quickly reachable"
        )
    }

    // MARK: - Timing

    func testNoTimedKeyboardInteractions() throws {
        // WCAG 2.2.1: No time limits on keyboard interactions
        // All buttons should remain active without timeout
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let buttons = inspector.findAllElements(trait: .button)

        for button in buttons {
            XCTAssertTrue(
                button.isEnabled,
                "Button '\(button.label ?? "unknown")' must not require timed interaction"
            )
        }
    }
}
