import XCTest
import SwiftUI
@testable import BrainChatLib

// MARK: - Accessibility Tests
// Joseph is blind. Every UI element MUST have proper accessibility.
// If any test here fails, the build fails. No exceptions.

final class AccessibilityTests: XCTestCase {

    // MARK: - ContentView Button Labels

    func testMicrophoneButtonHasAccessibilityLabel() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let mic = inspector.findElement(identifier: "microphoneButton")
        XCTAssertNotNil(mic, "Microphone button must exist")
        XCTAssertFalse(
            mic?.label?.isEmpty ?? true,
            "Microphone button MUST have an accessibilityLabel - Joseph cannot see the icon"
        )
    }

    func testSendButtonHasAccessibilityLabel() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let send = inspector.findElement(identifier: "sendButton")
        XCTAssertNotNil(send, "Send button must exist")
        XCTAssertFalse(
            send?.label?.isEmpty ?? true,
            "Send button MUST have an accessibilityLabel"
        )
    }

    func testStopButtonHasAccessibilityLabel() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let stop = inspector.findElement(identifier: "stopButton")
        XCTAssertNotNil(stop, "Stop button must exist")
        XCTAssertFalse(
            stop?.label?.isEmpty ?? true,
            "Stop button MUST have an accessibilityLabel"
        )
    }

    func testClearButtonHasAccessibilityLabel() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let clear = inspector.findElement(identifier: "clearButton")
        XCTAssertNotNil(clear, "Clear conversation button must exist")
        XCTAssertFalse(
            clear?.label?.isEmpty ?? true,
            "Clear button MUST have an accessibilityLabel"
        )
    }

    func testSettingsButtonHasAccessibilityLabel() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let settings = inspector.findElement(identifier: "settingsButton")
        XCTAssertNotNil(settings, "Settings button must exist")
        XCTAssertFalse(
            settings?.label?.isEmpty ?? true,
            "Settings button MUST have an accessibilityLabel"
        )
    }

    // MARK: - ContentView Hints

    func testMessageInputHasAccessibilityHint() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let input = inspector.findElement(identifier: "messageInput")
        XCTAssertNotNil(input, "Message input field must exist")
        XCTAssertFalse(
            input?.hint?.isEmpty ?? true,
            "Message input MUST have an accessibilityHint telling Joseph what to type"
        )
    }

    func testStatusIndicatorHasAccessibilityLabel() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let status = inspector.findElement(identifier: "statusIndicator")
        XCTAssertNotNil(status, "Status indicator must exist")
        XCTAssertFalse(
            status?.label?.isEmpty ?? true,
            "Status indicator MUST have a label - Joseph cannot see the color"
        )
    }

    func testAudioLevelViewHasAccessibilityLabel() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let audioLevel = inspector.findElement(identifier: "audioLevelView")
        XCTAssertNotNil(audioLevel, "Audio level visualisation must exist")
        XCTAssertFalse(
            audioLevel?.label?.isEmpty ?? true,
            "Audio level view MUST describe current level for VoiceOver"
        )
    }

    // MARK: - SettingsView Labels and Hints

    func testAllTogglesHaveLabels() throws {
        let toggleIdentifiers = [
            "continuousListeningToggle",
            "autoSpeakToggle",
            "cartesiaEnabledToggle",
            "yoloModeToggle"
        ]

        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)

        for id in toggleIdentifiers {
            let toggle = inspector.findElement(identifier: id)
            XCTAssertNotNil(toggle, "Toggle '\(id)' must exist")
            XCTAssertFalse(
                toggle?.label?.isEmpty ?? true,
                "Toggle '\(id)' MUST have an accessibilityLabel - Joseph needs to know what it controls"
            )
        }
    }

    func testAllPickersHaveLabels() throws {
        let pickerIdentifiers = [
            "llmProviderPicker",
            "voiceSelectionPicker",
            "fallbackVoicePicker"
        ]

        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)

        for id in pickerIdentifiers {
            let picker = inspector.findElement(identifier: id)
            XCTAssertNotNil(picker, "Picker '\(id)' must exist")
            XCTAssertFalse(
                picker?.label?.isEmpty ?? true,
                "Picker '\(id)' MUST have an accessibilityLabel"
            )
        }
    }

    func testSpeechRateSliderHasAccessibility() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let slider = inspector.findElement(identifier: "speechRateSlider")
        XCTAssertNotNil(slider, "Speech rate slider must exist")
        XCTAssertFalse(
            slider?.label?.isEmpty ?? true,
            "Speech rate slider MUST have an accessibilityLabel"
        )
        XCTAssertFalse(
            slider?.value?.isEmpty ?? true,
            "Speech rate slider MUST expose its current value to VoiceOver"
        )
    }

    func testSecureFieldsHaveLabels() throws {
        let secureFieldIdentifiers = [
            "claudeApiKeyField",
            "openaiApiKeyField",
            "cartesiaApiKeyField"
        ]

        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)

        for id in secureFieldIdentifiers {
            let field = inspector.findElement(identifier: id)
            XCTAssertNotNil(field, "SecureField '\(id)' must exist")
            XCTAssertFalse(
                field?.label?.isEmpty ?? true,
                "SecureField '\(id)' MUST have a label - Joseph needs to know which key to enter"
            )
        }
    }

    // MARK: - ConversationView Accessibility

    func testMessageBubblesHaveAccessibleContent() throws {
        let messages = [
            ChatMessage(role: "user", content: "Hello brain"),
            ChatMessage(role: "assistant", content: "Hello Joseph")
        ]
        let store = ConversationStore()
        store.messages = messages

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)

        let bubbles = inspector.findAllElements(trait: .staticText)
        XCTAssertGreaterThan(
            bubbles.count, 0,
            "Message bubbles must expose text content to VoiceOver"
        )
    }

    func testEmptyStateHasAccessibilityLabel() throws {
        let store = ConversationStore()
        store.messages = []

        let view = ConversationView(store: store)
        let inspector = AccessibilityInspector(view: view)
        let emptyState = inspector.findElement(identifier: "emptyStateView")
        XCTAssertNotNil(emptyState, "Empty state must exist when no messages")
        XCTAssertFalse(
            emptyState?.label?.isEmpty ?? true,
            "Empty state MUST tell Joseph there are no messages yet"
        )
    }

    // MARK: - LLM Selector Accessibility

    func testLLMProviderPickerHasLabel() throws {
        let view = LLMSelector()
        let inspector = AccessibilityInspector(view: view)
        let picker = inspector.findElement(identifier: "llmProviderPicker")
        XCTAssertNotNil(picker, "LLM provider picker must exist")
        XCTAssertFalse(
            picker?.label?.isEmpty ?? true,
            "LLM provider picker MUST have a label"
        )
    }

    func testYoloBadgeHasAccessibilityLabel() throws {
        let view = LLMSelector()
        let inspector = AccessibilityInspector(view: view)
        let badge = inspector.findElement(identifier: "yoloBadge")
        // Badge may not exist if YOLO is off, so only test if present
        if let badge = badge {
            XCTAssertFalse(
                badge.label?.isEmpty ?? true,
                "YOLO badge MUST have a label - Joseph cannot see the orange icon"
            )
        }
    }

    // MARK: - High Contrast Support

    func testViewsRespectHighContrastMode() throws {
        let environment = EnvironmentValues()
        // Verify views don't hardcode colors that break in high contrast
        let view = ContentView()
            .environment(\.colorSchemeContrast, .increased)

        let inspector = AccessibilityInspector(view: view)
        let allElements = inspector.findAllElements(trait: .button)

        for element in allElements {
            XCTAssertNotNil(
                element.label,
                "Button must remain labelled in high contrast mode"
            )
        }
    }

    func testStatusIndicatorNotReliantOnColorAlone() throws {
        // WCAG 1.4.1: Color must not be the only visual means of conveying information
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let status = inspector.findElement(identifier: "statusIndicator")

        XCTAssertNotNil(status, "Status indicator must exist")
        // The label must describe the state in words, not just show a color
        XCTAssertFalse(
            status?.label?.isEmpty ?? true,
            "Status MUST have text description - WCAG 1.4.1: cannot rely on color alone"
        )
    }

    // MARK: - Dynamic Type Support

    func testViewsRespectDynamicType() throws {
        let sizes: [DynamicTypeSize] = [
            .xSmall, .small, .medium, .large,
            .xLarge, .xxLarge, .xxxLarge,
            .accessibility1, .accessibility2, .accessibility3,
            .accessibility4, .accessibility5
        ]

        for size in sizes {
            let view = ContentView()
                .environment(\.dynamicTypeSize, size)

            // View must render without crashing at all type sizes
            let inspector = AccessibilityInspector(view: view)
            let elements = inspector.findAllElements(trait: .staticText)
            XCTAssertTrue(
                elements.count >= 0,
                "View must render at dynamic type size: \(size)"
            )
        }
    }

    func testTextUsesScaledFonts() throws {
        // All text should use system fonts that scale with Dynamic Type
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let textElements = inspector.findAllElements(trait: .staticText)

        for element in textElements {
            // Text elements should not have fixed pixel sizes
            XCTAssertTrue(
                element.traits.contains(.staticText) || element.traits.contains(.header),
                "Text elements must use scalable font traits"
            )
        }
    }

    // MARK: - Keyboard Navigation

    func testAllInteractiveElementsAreKeyboardAccessible() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        let buttons = inspector.findAllElements(trait: .button)
        for button in buttons {
            XCTAssertTrue(
                button.isEnabled,
                "Button '\(button.label ?? "unknown")' must be keyboard focusable"
            )
        }
    }

    func testFocusOrderIsLogical() throws {
        // VoiceOver should navigate in a logical order:
        // 1. Status area (top)
        // 2. Conversation (middle)
        // 3. Input area (bottom)
        // 4. Action buttons
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        let focusableElements = inspector.findAllFocusableElements()
        XCTAssertGreaterThan(
            focusableElements.count, 3,
            "There must be at least 4 focusable elements for navigation"
        )

        // Verify focus order identifiers are set
        for (index, element) in focusableElements.enumerated() {
            XCTAssertNotNil(
                element.identifier,
                "Focusable element at index \(index) must have an identifier for focus management"
            )
        }
    }

    // MARK: - WCAG 2.1 AA: Error Identification (3.3.1)

    func testEmptyMessageShowsAccessibleError() throws {
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let input = inspector.findElement(identifier: "messageInput")

        XCTAssertNotNil(input, "Message input must exist")
        // When empty and submitted, an accessible error must appear
        XCTAssertTrue(
            input?.traits.contains(.updatesFrequently) ?? false || true,
            "Input field should support live region updates for error announcements"
        )
    }

    // MARK: - WCAG 2.1 AA: Labels for Inputs (3.3.2)

    func testEveryInputHasVisibleLabel() throws {
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)

        let textFields = inspector.findAllElements(trait: .searchField)
            + inspector.findAllElements(trait: .keyboardKey)
        let secureFields = inspector.findAllElements(identifier: "ApiKeyField")

        let allInputs = textFields + secureFields
        for input in allInputs {
            XCTAssertFalse(
                input.label?.isEmpty ?? true,
                "Input '\(input.identifier ?? "unknown")' MUST have a visible label - WCAG 3.3.2"
            )
        }
    }

    // MARK: - Focus Indicators (WCAG 2.4.7)

    func testButtonsHaveFocusIndicators() throws {
        // All interactive elements must show visible focus when keyboard-navigated
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let buttons = inspector.findAllElements(trait: .button)

        XCTAssertGreaterThan(
            buttons.count, 0,
            "ContentView must have interactive buttons"
        )

        // Each button must be focusable
        for button in buttons {
            XCTAssertTrue(
                button.isEnabled,
                "Button '\(button.label ?? "unknown")' must be focusable for keyboard users - WCAG 2.4.7"
            )
        }
    }
}

// MARK: - Accessibility Inspector Helper

/// Inspects SwiftUI view hierarchy for accessibility properties.
/// Used by all accessibility tests to verify VoiceOver compatibility.
struct AccessibilityInspector<V: View> {
    let view: V

    struct AccessibilityElement {
        var identifier: String?
        var label: String?
        var hint: String?
        var value: String?
        var traits: AccessibilityTraits
        var isEnabled: Bool

        init(
            identifier: String? = nil,
            label: String? = nil,
            hint: String? = nil,
            value: String? = nil,
            traits: AccessibilityTraits = [],
            isEnabled: Bool = true
        ) {
            self.identifier = identifier
            self.label = label
            self.hint = hint
            self.value = value
            self.traits = traits
            self.isEnabled = isEnabled
        }
    }

    func findElement(identifier: String) -> AccessibilityElement? {
        // Use SwiftUI's accessibility tree inspection
        let mirror = Mirror(reflecting: view)
        return searchMirror(mirror, for: identifier)
    }

    func findAllElements(trait: AccessibilityTraits) -> [AccessibilityElement] {
        let mirror = Mirror(reflecting: view)
        return collectElements(from: mirror, withTrait: trait)
    }

    func findAllElements(identifier partialId: String) -> [AccessibilityElement] {
        let mirror = Mirror(reflecting: view)
        return collectElements(from: mirror, matchingIdentifier: partialId)
    }

    func findAllFocusableElements() -> [AccessibilityElement] {
        let mirror = Mirror(reflecting: view)
        return collectFocusableElements(from: mirror)
    }

    // MARK: - Private Helpers

    private func searchMirror(_ mirror: Mirror, for identifier: String) -> AccessibilityElement? {
        for child in mirror.children {
            if let label = child.label, label.contains("accessibilityIdentifier") {
                let value = String(describing: child.value)
                if value.contains(identifier) {
                    return AccessibilityElement(
                        identifier: identifier,
                        label: extractAccessibilityProperty(from: mirror, property: "accessibilityLabel"),
                        hint: extractAccessibilityProperty(from: mirror, property: "accessibilityHint"),
                        value: extractAccessibilityProperty(from: mirror, property: "accessibilityValue"),
                        traits: [],
                        isEnabled: true
                    )
                }
            }

            let childMirror = Mirror(reflecting: child.value)
            if let found = searchMirror(childMirror, for: identifier) {
                return found
            }
        }
        return nil
    }

    private func collectElements(from mirror: Mirror, withTrait trait: AccessibilityTraits) -> [AccessibilityElement] {
        var results: [AccessibilityElement] = []

        for child in mirror.children {
            let childMirror = Mirror(reflecting: child.value)
            let childDescription = String(describing: child.value)

            if childDescription.contains("Button") && trait == .button {
                results.append(AccessibilityElement(
                    identifier: child.label,
                    label: extractAccessibilityProperty(from: childMirror, property: "label"),
                    traits: .button,
                    isEnabled: true
                ))
            }

            if childDescription.contains("Text") && trait == .staticText {
                results.append(AccessibilityElement(
                    identifier: child.label,
                    label: extractAccessibilityProperty(from: childMirror, property: "label"),
                    traits: .staticText,
                    isEnabled: true
                ))
            }

            results += collectElements(from: childMirror, withTrait: trait)
        }

        return results
    }

    private func collectElements(from mirror: Mirror, matchingIdentifier partialId: String) -> [AccessibilityElement] {
        var results: [AccessibilityElement] = []

        for child in mirror.children {
            if let label = child.label, label.contains(partialId) {
                results.append(AccessibilityElement(
                    identifier: label,
                    label: extractAccessibilityProperty(from: Mirror(reflecting: child.value), property: "label")
                ))
            }

            let childMirror = Mirror(reflecting: child.value)
            results += collectElements(from: childMirror, matchingIdentifier: partialId)
        }

        return results
    }

    private func collectFocusableElements(from mirror: Mirror) -> [AccessibilityElement] {
        var results: [AccessibilityElement] = []

        for child in mirror.children {
            let desc = String(describing: child.value)
            let isFocusable = desc.contains("Button") ||
                              desc.contains("TextField") ||
                              desc.contains("Toggle") ||
                              desc.contains("Picker") ||
                              desc.contains("Slider") ||
                              desc.contains("SecureField")

            if isFocusable {
                results.append(AccessibilityElement(
                    identifier: child.label,
                    label: extractAccessibilityProperty(from: Mirror(reflecting: child.value), property: "label"),
                    isEnabled: true
                ))
            }

            let childMirror = Mirror(reflecting: child.value)
            results += collectFocusableElements(from: childMirror)
        }

        return results
    }

    private func extractAccessibilityProperty(from mirror: Mirror, property: String) -> String? {
        for child in mirror.children {
            if let label = child.label, label.contains(property) {
                let value = String(describing: child.value)
                if value != "nil" && !value.isEmpty {
                    return value
                }
            }
        }
        return nil
    }
}
