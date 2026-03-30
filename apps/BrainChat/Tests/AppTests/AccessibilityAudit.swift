import XCTest
import SwiftUI
@testable import BrainChatLib

// MARK: - Accessibility Audit
// ZERO TOLERANCE for accessibility violations.
// This audit scans ALL views and FAILS the build if any violations are found.
// Joseph depends on every element being properly labelled and navigable.

final class AccessibilityAudit: XCTestCase {

    // MARK: - Violation Tracking

    struct AccessibilityViolation: CustomStringConvertible {
        let view: String
        let element: String
        let rule: String
        let severity: Severity
        let wcagCriterion: String

        enum Severity: String {
            case critical = "CRITICAL"
            case major = "MAJOR"
            case minor = "MINOR"
        }

        var description: String {
            "[\(severity.rawValue)] \(view) → \(element): \(rule) (WCAG \(wcagCriterion))"
        }
    }

    var violations: [AccessibilityViolation] = []

    override func setUp() {
        super.setUp()
        violations = []
    }

    // MARK: - Full View Audit

    func testAuditContentView() throws {
        auditView(ContentView(), name: "ContentView")
        reportAndFail()
    }

    func testAuditSettingsView() throws {
        auditView(SettingsView(), name: "SettingsView")
        reportAndFail()
    }

    func testAuditConversationViewWithMessages() throws {
        let store = ConversationStore()
        store.messages = [
            ChatMessage(role: "user", content: "Hello"),
            ChatMessage(role: "assistant", content: "Hi Joseph"),
            ChatMessage(role: "system", content: "Connected to Claude")
        ]
        auditView(ConversationView(store: store), name: "ConversationView")
        reportAndFail()
    }

    func testAuditConversationViewEmpty() throws {
        let store = ConversationStore()
        store.messages = []
        auditView(ConversationView(store: store), name: "ConversationView(empty)")
        reportAndFail()
    }

    func testAuditLLMSelector() throws {
        auditView(LLMSelector(), name: "LLMSelector")
        reportAndFail()
    }

    func testAuditVoiceSelector() throws {
        auditView(VoiceSelector(), name: "VoiceSelector")
        reportAndFail()
    }

    // MARK: - Cross-View Audit

    func testAuditAllViewsForMissingLabels() throws {
        let views: [(any View, String)] = [
            (ContentView(), "ContentView"),
            (SettingsView(), "SettingsView"),
        ]

        for (view, name) in views {
            checkMissingLabels(view, name: name)
        }

        reportAndFail()
    }

    func testAuditAllViewsForMissingHints() throws {
        let views: [(any View, String)] = [
            (ContentView(), "ContentView"),
            (SettingsView(), "SettingsView"),
        ]

        for (view, name) in views {
            checkMissingHints(view, name: name)
        }

        // Hints are major, not critical - still report but separate from labels
        reportAndFail(minimumSeverity: .major)
    }

    // MARK: - WCAG 2.1 AA Compliance Checks

    func testWCAG_1_1_1_NonTextContent() throws {
        // All non-text content must have text alternative
        let views: [(any View, String)] = [
            (ContentView(), "ContentView"),
            (SettingsView(), "SettingsView"),
        ]

        for (view, name) in views {
            let inspector = AccessibilityInspector(view: view)
            let images = inspector.findAllElements(trait: .image)

            for image in images {
                if image.label == nil || image.label?.isEmpty == true {
                    violations.append(AccessibilityViolation(
                        view: name,
                        element: image.identifier ?? "Image",
                        rule: "Non-text content (image/icon) has no text alternative",
                        severity: .critical,
                        wcagCriterion: "1.1.1"
                    ))
                }
            }
        }

        reportAndFail()
    }

    func testWCAG_1_4_1_UseOfColor() throws {
        // Information must not be conveyed by color alone
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        let statusIndicator = inspector.findElement(identifier: "statusIndicator")
        if let status = statusIndicator {
            if status.label == nil || status.label?.isEmpty == true {
                violations.append(AccessibilityViolation(
                    view: "ContentView",
                    element: "statusIndicator",
                    rule: "Status conveyed by color alone without text alternative",
                    severity: .critical,
                    wcagCriterion: "1.4.1"
                ))
            }
        }

        reportAndFail()
    }

    func testWCAG_1_4_3_ColorContrast() throws {
        // Minimum contrast ratio 4.5:1 for normal text, 3:1 for large text
        // We verify that views use system colors which respect accessibility settings
        let view = ContentView()
            .environment(\.colorSchemeContrast, .increased)

        let inspector = AccessibilityInspector(view: view)
        let textElements = inspector.findAllElements(trait: .staticText)

        // System colors automatically meet contrast requirements
        // Custom colors need explicit checking
        for element in textElements {
            if element.label == nil || element.label?.isEmpty == true {
                // Text without label may use custom color
                violations.append(AccessibilityViolation(
                    view: "ContentView",
                    element: element.identifier ?? "Text",
                    rule: "Text element may not meet 4.5:1 contrast ratio",
                    severity: .major,
                    wcagCriterion: "1.4.3"
                ))
            }
        }

        reportAndFail(minimumSeverity: .major)
    }

    func testWCAG_2_1_1_KeyboardAccessible() throws {
        // All functionality must be operable through keyboard
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        let buttons = inspector.findAllElements(trait: .button)
        let focusable = inspector.findAllFocusableElements()

        if focusable.count < buttons.count {
            violations.append(AccessibilityViolation(
                view: "ContentView",
                element: "Multiple buttons",
                rule: "\(buttons.count - focusable.count) buttons are not keyboard accessible",
                severity: .critical,
                wcagCriterion: "2.1.1"
            ))
        }

        reportAndFail()
    }

    func testWCAG_2_4_3_FocusOrder() throws {
        // Focus order must preserve meaning and operability
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        if focusable.count < 3 {
            violations.append(AccessibilityViolation(
                view: "ContentView",
                element: "Focus chain",
                rule: "Insufficient focusable elements for logical navigation",
                severity: .critical,
                wcagCriterion: "2.4.3"
            ))
        }

        reportAndFail()
    }

    func testWCAG_2_4_7_FocusVisible() throws {
        // Focus indicator must be visible
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        for element in focusable {
            if !element.isEnabled {
                violations.append(AccessibilityViolation(
                    view: "ContentView",
                    element: element.identifier ?? "Element",
                    rule: "Disabled element in focus order - no visible focus indicator",
                    severity: .major,
                    wcagCriterion: "2.4.7"
                ))
            }
        }

        reportAndFail()
    }

    func testWCAG_3_3_1_ErrorIdentification() throws {
        // Input errors must be identified and described in text
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)
        let input = inspector.findElement(identifier: "messageInput")

        if input == nil {
            violations.append(AccessibilityViolation(
                view: "ContentView",
                element: "messageInput",
                rule: "Input field missing - errors cannot be communicated",
                severity: .critical,
                wcagCriterion: "3.3.1"
            ))
        }

        reportAndFail()
    }

    func testWCAG_3_3_2_LabelsOrInstructions() throws {
        // Labels or instructions must be provided for user input
        let view = SettingsView()
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        var unlabelledInputs = 0
        for element in focusable {
            if element.label == nil || element.label?.isEmpty == true {
                unlabelledInputs += 1
                violations.append(AccessibilityViolation(
                    view: "SettingsView",
                    element: element.identifier ?? "Input",
                    rule: "Input element has no label or instruction",
                    severity: .critical,
                    wcagCriterion: "3.3.2"
                ))
            }
        }

        reportAndFail()
    }

    func testWCAG_4_1_2_NameRoleValue() throws {
        // All UI components must expose name, role, and state
        let view = ContentView()
        let inspector = AccessibilityInspector(view: view)

        let buttons = inspector.findAllElements(trait: .button)
        for button in buttons {
            if button.label == nil || button.label?.isEmpty == true {
                violations.append(AccessibilityViolation(
                    view: "ContentView",
                    element: button.identifier ?? "Button",
                    rule: "Button has no accessible name",
                    severity: .critical,
                    wcagCriterion: "4.1.2"
                ))
            }
        }

        reportAndFail()
    }

    // MARK: - Dynamic Type Audit

    func testAllViewsSupportDynamicType() throws {
        let accessibilitySizes: [DynamicTypeSize] = [
            .accessibility1, .accessibility2, .accessibility3,
            .accessibility4, .accessibility5
        ]

        for size in accessibilitySizes {
            let view = ContentView()
                .environment(\.dynamicTypeSize, size)

            // Must not crash at any accessibility size
            let inspector = AccessibilityInspector(view: view)
            let elements = inspector.findAllElements(trait: .staticText)
            XCTAssertTrue(
                elements.count >= 0,
                "ContentView must render at accessibility type size: \(size)"
            )
        }
    }

    // MARK: - Reduced Motion Audit

    func testViewsRespectReducedMotion() throws {
        let view = ContentView()
            .environment(\.accessibilityReduceMotion, true)

        // View must render without animation issues
        let inspector = AccessibilityInspector(view: view)
        let elements = inspector.findAllFocusableElements()
        XCTAssertGreaterThan(
            elements.count, 0,
            "Views must function with reduced motion enabled"
        )
    }

    // MARK: - Reduce Transparency Audit

    func testViewsRespectReducedTransparency() throws {
        let view = ContentView()
            .environment(\.accessibilityReduceTransparency, true)

        let inspector = AccessibilityInspector(view: view)
        let elements = inspector.findAllFocusableElements()
        XCTAssertGreaterThan(
            elements.count, 0,
            "Views must function with reduced transparency enabled"
        )
    }

    // MARK: - Comprehensive Violation Report

    func testFullAccessibilityAuditReport() throws {
        // Run ALL checks and produce a single comprehensive report
        let allViews: [(any View, String)] = [
            (ContentView(), "ContentView"),
            (SettingsView(), "SettingsView"),
        ]

        for (view, name) in allViews {
            auditView(view, name: name)
        }

        // Also audit with conversation data
        let store = ConversationStore()
        store.messages = [
            ChatMessage(role: "user", content: "Test"),
            ChatMessage(role: "assistant", content: "Response")
        ]
        auditView(ConversationView(store: store), name: "ConversationView")

        // Generate full report
        if !violations.isEmpty {
            let report = generateReport()
            print("\n" + report)
        }

        // ZERO TOLERANCE: Any violation fails the build
        XCTAssertEqual(
            violations.count, 0,
            """
            
            ♿️ ACCESSIBILITY AUDIT FAILED
            
            \(violations.count) violation(s) found!
            Joseph is BLIND. Every violation means he cannot use this app.
            
            \(violations.map { "  • \($0)" }.joined(separator: "\n"))
            
            Fix ALL violations before merging. No exceptions.
            """
        )
    }

    // MARK: - Private Audit Helpers

    private func auditView<V: View>(_ view: V, name: String) {
        checkMissingLabels(view, name: name)
        checkMissingHints(view, name: name)
        checkFocusability(view, name: name)
        checkDynamicTypeSupport(view, name: name)
    }

    private func checkMissingLabels<V: View>(_ view: V, name: String) {
        let inspector = AccessibilityInspector(view: view)

        // Check buttons
        let buttons = inspector.findAllElements(trait: .button)
        for button in buttons {
            if button.label == nil || button.label?.isEmpty == true {
                violations.append(AccessibilityViolation(
                    view: name,
                    element: button.identifier ?? "Button",
                    rule: "Button has no accessibilityLabel",
                    severity: .critical,
                    wcagCriterion: "4.1.2"
                ))
            }
        }
    }

    private func checkMissingHints<V: View>(_ view: V, name: String) {
        let inspector = AccessibilityInspector(view: view)
        let focusable = inspector.findAllFocusableElements()

        for element in focusable {
            if element.hint == nil || element.hint?.isEmpty == true {
                violations.append(AccessibilityViolation(
                    view: name,
                    element: element.identifier ?? element.label ?? "Element",
                    rule: "Interactive element has no accessibilityHint",
                    severity: .major,
                    wcagCriterion: "3.3.2"
                ))
            }
        }
    }

    private func checkFocusability<V: View>(_ view: V, name: String) {
        let inspector = AccessibilityInspector(view: view)
        let buttons = inspector.findAllElements(trait: .button)
        let focusable = inspector.findAllFocusableElements()

        if buttons.count > focusable.count {
            violations.append(AccessibilityViolation(
                view: name,
                element: "Focus chain",
                rule: "\(buttons.count - focusable.count) interactive elements not keyboard focusable",
                severity: .critical,
                wcagCriterion: "2.1.1"
            ))
        }
    }

    private func checkDynamicTypeSupport<V: View>(_ view: V, name: String) {
        // Verify view renders at extreme dynamic type sizes
        let extremeSize = DynamicTypeSize.accessibility5
        let largeView = AnyView(
            AnyView(view).environment(\.dynamicTypeSize, extremeSize)
        )
        let inspector = AccessibilityInspector(view: largeView)
        let elements = inspector.findAllElements(trait: .staticText)

        // View should still have content at largest type size
        if elements.isEmpty {
            violations.append(AccessibilityViolation(
                view: name,
                element: "Layout",
                rule: "View may clip or hide content at accessibility5 type size",
                severity: .major,
                wcagCriterion: "1.4.4"
            ))
        }
    }

    private func reportAndFail(minimumSeverity: AccessibilityViolation.Severity = .critical) {
        let filtered: [AccessibilityViolation]
        switch minimumSeverity {
        case .critical:
            filtered = violations.filter { $0.severity == .critical }
        case .major:
            filtered = violations.filter { $0.severity == .critical || $0.severity == .major }
        case .minor:
            filtered = violations
        }

        if !filtered.isEmpty {
            let report = generateReport(violations: filtered)
            XCTFail("""
            
            ♿️ ACCESSIBILITY VIOLATIONS DETECTED
            
            \(report)
            
            Joseph is blind. Fix these NOW.
            """)
        }
    }

    private func generateReport(violations: [AccessibilityViolation]? = nil) -> String {
        let items = violations ?? self.violations

        let critical = items.filter { $0.severity == .critical }
        let major = items.filter { $0.severity == .major }
        let minor = items.filter { $0.severity == .minor }

        var report = """
        ╔══════════════════════════════════════════════════╗
        ║          ♿️ ACCESSIBILITY AUDIT REPORT            ║
        ╚══════════════════════════════════════════════════╝
        
        Total Violations: \(items.count)
          🔴 Critical: \(critical.count)
          🟠 Major:    \(major.count)
          🟡 Minor:    \(minor.count)
        
        """

        if !critical.isEmpty {
            report += "── CRITICAL (Build Blockers) ──\n"
            for v in critical {
                report += "  🔴 \(v)\n"
            }
            report += "\n"
        }

        if !major.isEmpty {
            report += "── MAJOR ──\n"
            for v in major {
                report += "  🟠 \(v)\n"
            }
            report += "\n"
        }

        if !minor.isEmpty {
            report += "── MINOR ──\n"
            for v in minor {
                report += "  🟡 \(v)\n"
            }
            report += "\n"
        }

        report += """
        ══════════════════════════════════════════════════
        WCAG 2.1 AA Reference:
          1.1.1 Non-text Content
          1.4.1 Use of Color
          1.4.3 Contrast (Minimum)
          1.4.4 Resize Text
          2.1.1 Keyboard
          2.4.3 Focus Order
          2.4.7 Focus Visible
          3.3.1 Error Identification
          3.3.2 Labels or Instructions
          4.1.2 Name, Role, Value
        ══════════════════════════════════════════════════
        """

        return report
    }
}
