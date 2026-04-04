# BrainChat Accessibility Implementation Guide

## For Developers: How Accessibility Was Implemented

This guide explains the patterns used in BrainChat to achieve WCAG 2.1 AAA compliance. Use these patterns when adding new features.

## Pattern 1: Concise Accessible Labels

### ❌ WRONG (Verbose)
```swift
Button(action: toggleMic) {
    Image(systemName: "mic.fill")
}
.accessibilityLabel("Microphone toggle button")
.accessibilityValue("Currently live, listening")
.accessibilityHint("Double tap to mute microphone")
```

### ✅ CORRECT (WCAG AAA - Concise)
```swift
Button(action: toggleMic) {
    Image(systemName: "mic.fill")
}
.accessibilityShortLabel(isMicLive ? AccessibleButtonLabels.micLive : AccessibleButtonLabels.micMuted)
// Label: "Mic live" or "Mic muted"
.accessibilityValue(isMicLive ? "Active" : "Inactive")
.accessibilityHint(AccessibleButtonLabels.micHint)  // "Toggle microphone"
```

**Why:** VoiceOver reads labels sequentially. Long labels slow navigation. Concise labels speed up usage.

---

## Pattern 2: Grouped Controls

### ❌ WRONG (Individual Labels)
```swift
HStack {
    Button("Mic") { toggleMic() }
        .accessibilityLabel("Microphone button")
    Button("Stop") { stop() }
        .accessibilityLabel("Stop button")
    Button("Settings") { openSettings() }
        .accessibilityLabel("Settings button")
}
```

### ✅ CORRECT (Grouped)
```swift
HStack(spacing: 8) {
    Button("Mic") { toggleMic() }
        .accessibilityShortLabel(AccessibleButtonLabels.micLive)
    Button("Stop") { stop() }
        .accessibilityShortLabel(AccessibleButtonLabels.stopSpeaking)
    Button("Settings") { openSettings() }
        .accessibilityShortLabel(AccessibleButtonLabels.settings)
}
.accessibilityElement(children: .contain)
.accessibilityLabel("Control buttons")
.accessibilityIdentifier(AccessibilitySectionID.controlsGroup)
```

**Why:** Grouping lets VoiceOver users navigate one "button" that contains three related controls. They can swipe to explore each individual button, or skip past the whole group.

---

## Pattern 3: Real-Time Announcements

### ❌ WRONG (Silent State Change)
```swift
func toggleMic() {
    isMicLive.toggle()
    // No announcement!
}
```

### ✅ CORRECT (Announce Important Changes)
```swift
func toggleMic() {
    isMicLive.toggle()
    
    // High priority: Important state change
    let status = isMicLive ? "Microphone now live" : "Microphone now muted"
    AccessibilityHelpers.announceHighPriority(status)
}
```

**Why:** WCAG 4.1.3 requires status messages. Users can't see visual changes, so we must announce them.

---

## Pattern 4: Keyboard Shortcuts with Feedback

### ❌ WRONG (No Feedback)
```swift
.onKeyPress("m", modifiers: .command) {
    viewModel.toggleMic()
    return .handled
}
```

### ✅ CORRECT (With Announcement)
```swift
.onKeyPress("m", modifiers: .command) {
    viewModel.toggleMic()
    let status = viewModel.isMicLive ? "Microphone now live" : "Microphone now muted"
    AccessibilityHelpers.announceHighPriority(status)
    return .handled
}
```

**Why:** Keyboard users need feedback that their action worked. They can't see visual feedback immediately.

---

## Pattern 5: Extended Descriptions for Complex Status

### ❌ WRONG (Minimal Description)
```swift
.accessibilityValue(audioLevel)  // "0.5"
```

### ✅ CORRECT (Descriptive)
```swift
.accessibilityValue(AudioLevelAccessibility.describe(level: audioLevel))
// "Moderate – normal speech level"
```

**Code:**
```swift
struct AudioLevelAccessibility {
    static func describe(level: Float) -> String {
        switch level {
        case ..<0.05:
            return "Silent – no audio detected"
        case ..<0.3:
            return "Low – faint audio"
        case ..<0.7:
            return "Moderate – normal speech level"
        default:
            return "High – loud audio or background noise"
        }
    }
}
```

**Why:** WCAG AAA requires extended descriptions to help users understand complex UI elements.

---

## Pattern 6: Logical Focus Order with Skip Links

### ❌ WRONG (No Focus Management)
```swift
VStack {
    toolbar
    conversation
    input
}
```

### ✅ CORRECT (Logical Focus Order)
```swift
VStack {
    toolbar
        .focused($focusTarget, equals: .controls)
        .accessibilityHint("Use Cmd+1 to jump to chat, Cmd+2 for input, Cmd+3 for controls")
    
    conversation
        .focused($focusTarget, equals: .chatArea)
    
    input
        .focused($focusTarget, equals: .inputField)
}
.onKeyPress("1", modifiers: .command) {
    focusTarget = .chatArea
    AccessibilityHelpers.announceHighPriority("Focused on conversation area")
    return .handled
}
```

**Why:** Users can jump between major sections, saving time navigating through every element.

---

## Pattern 7: Accessible Form Inputs

### ❌ WRONG (Unlabeled TextField)
```swift
TextField("Enter URL", text: $url)
```

### ✅ CORRECT (Labeled with Hint)
```swift
VStack(alignment: .leading, spacing: 4) {
    Text("Bridge URL")
        .font(.caption)
        .foregroundColor(.secondary)
    
    TextField("ws://localhost:8765", text: $bridgeURL)
        .textFieldStyle(.roundedBorder)
        .accessibilityShortLabel("Bridge WebSocket URL")
        .accessibilityHint("Address of local voice bridge, e.g. ws://localhost:8765")
}
```

**Why:** Clear labels and hints help users understand what to enter. Hints provide context without cluttering the interface.

---

## Pattern 8: Confirmation for Destructive Actions

### ❌ WRONG (Instant Action)
```swift
Button("Clear", action: { clearConversation() })
```

### ✅ CORRECT (Confirmation Required)
```swift
Button("Clear") {
    showClearConfirmation = true
}
.confirmationDialog(
    "Clear all messages?",
    isPresented: $showClearConfirmation,
    titleVisibility: .visible
) {
    Button("Clear All Messages", role: .destructive) {
        viewModel.clearConversation()
        AccessibilityHelpers.announceHighPriority("Conversation cleared")
    }
    Button("Cancel", role: .cancel) {}
} message: {
    Text("This will permanently delete all messages in this conversation.")
}
```

**Why:** WCAG 3.3.4 requires error prevention. Users can't undo deletion, so we must confirm first.

---

## Pattern 9: Message Role Descriptions

### ❌ WRONG (Raw Role)
```swift
Text(message.role.rawValue)
.accessibilityLabel(message.role.rawValue)  // "assistant" or "user"
```

### ✅ CORRECT (Descriptive Names)
```swift
extension ChatMessage.Role {
    var accessibilityName: String {
        switch self {
        case .user:
            return "Your message"
        case .assistant:
            return "Brain Chat response"
        case .copilot:
            return "Copilot response"
        case .system:
            return "System message"
        }
    }
}

// Usage:
.accessibilityLabel(message.role.accessibilityName)
```

**Why:** "Brain Chat response" is more meaningful than "assistant" for screen reader users.

---

## Pattern 10: Rotor and Section Identifiers

### ❌ WRONG (No Navigation Structure)
```swift
VStack {
    // Controls not identifiable
    HStack { buttons }
    
    // Messages scattered
    ForEach(messages) { message }
    
    // Input not grouped
    TextField(...) 
    Button("Send") {}
}
```

### ✅ CORRECT (Structured for Rotor)
```swift
VStack(spacing: 0) {
    HStack { buttons }
        .accessibilityIdentifier(AccessibilitySectionID.statusSection)
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Status and control area")
        .accessibilityHint("Contains microphone, settings, and session status")
    
    ScrollView {
        LazyVStack {
            ForEach(messages) { message in
                MessageBubble(message: message)
                    .accessibilityIdentifier("message-\(message.id)")
            }
        }
    }
    .accessibilityIdentifier(AccessibilitySectionID.conversationSection)
    .accessibilityLabel("Conversation history")
    
    HStack {
        TextField(...) 
        Button("Send") {}
    }
    .accessibilityIdentifier(AccessibilitySectionID.inputSection)
    .accessibilityLabel("Message input area")
}
```

**VoiceOver Rotor Usage:**
1. Press VO+U (open rotor)
2. User sees: "Status section", "Conversation section", "Input section"
3. User presses Enter to jump to section

---

## Pattern 11: Disabling Controls with Explanation

### ❌ WRONG (No Explanation)
```swift
Button("Send") { sendMessage() }
    .disabled(inputText.isEmpty)
    // VoiceOver just says "dimmed"
```

### ✅ CORRECT (Explanatory Hint)
```swift
Button("Send") { sendMessage() }
    .disabled(inputText.isEmpty)
    .accessibilityShortLabel(AccessibleButtonLabels.send)
    .accessibilityValue(
        inputText.isEmpty ? "Disabled – no text" : "Ready to send"
    )
    .accessibilityHint(AccessibleButtonLabels.sendHint)
```

**Why:** VoiceOver users need to know why a button is disabled and how to enable it.

---

## Pattern 12: List Navigation in Scrollable Content

### ❌ WRONG (Can't Navigate Messages Easily)
```swift
ScrollView {
    ForEach(messages) { message in
        MessageBubble(message: message)
    }
}
```

### ✅ CORRECT (Each Message Navigable)
```swift
ScrollViewReader { proxy in
    ScrollView {
        LazyVStack(spacing: 12) {
            ForEach(messages, id: \.id) { message in
                MessageBubble(message: message)
                    .id(message.id)
                    .accessibilityIdentifier("message-\(message.id)")
                    .accessibilityAddTraits(.isButton)
            }
        }
    }
    .onChange(of: messages.count) { _, _ in
        // Auto-scroll to latest message
        if let last = messages.last?.id {
            withAnimation { proxy.scrollTo(last, anchor: .bottom) }
            announceNewMessage()
        }
    }
}
```

**Why:** Each message is navigable. VoiceOver can jump to specific messages, and users are announced when new messages arrive.

---

## Adding New Features: Accessibility Checklist

When adding a new feature to BrainChat:

### 1. Label & Hint
```swift
.accessibilityShortLabel("...")  // Concise name (< 15 chars ideal)
.accessibilityHint("...")         // What it does or how to use
```

### 2. Keyboard Support
```swift
.keyboardShortcut("k", modifiers: .command)  // If applicable
```

### 3. Announce State Changes
```swift
AccessibilityHelpers.announceHighPriority("State changed to X")
```

### 4. Grouping
```swift
.accessibilityElement(children: .contain)
.accessibilityIdentifier("myFeatureName")
```

### 5. Test
- [ ] With VoiceOver enabled
- [ ] Using Tab/Shift+Tab keyboard
- [ ] Using all keyboard shortcuts
- [ ] Contrast ratio check (7:1 for text)

---

## Common Pitfalls to Avoid

### ❌ Long, Redundant Labels
```swift
.accessibilityLabel("This is a button that opens the settings window where you can configure all the options")
```
→ Use `.accessibilityHint()` instead for details

### ❌ Silent State Changes
```swift
viewModel.isMicLive = !viewModel.isMicLive
// User never told what happened!
```
→ Always announce important changes

### ❌ Inaccessible Status Indicators
```swift
Image(systemName: "dot.fill")
    .foregroundColor(.green)
    // What does this mean?
```
→ Add label/hint explaining what the indicator means

### ❌ Inconsistent Labels
```swift
Button("Mic") { toggleMic() }
Button("Microphone Control") { toggleMic() }
// Which is it?
```
→ Use constants from `AccessibleButtonLabels`

### ❌ Focus Traps
```swift
.onKeyPress(.tab) {
    // Prevents normal Tab behavior
}
```
→ Let normal focus management work; use Cmd+1/2/3 for jumps instead

### ❌ Complex Controls Without Hints
```swift
Slider(value: $rate, in: 0...100)
// What is 50? Good? Bad?
```
→ Add hint explaining the scale

---

## Testing New Features

### Automated XCTest
```swift
func testMicButtonAccessibility() {
    let app = XCUIApplication()
    app.launch()
    
    let micButton = app.buttons["microphoneButton"]
    
    // Label should be concise
    XCTAssertTrue(
        micButton.label.contains("Mic"),
        "Label should contain 'Mic'"
    )
    
    // Should be accessible via keyboard
    XCTAssertTrue(
        micButton.element.isEnabled,
        "Mic button should be enabled"
    )
}
```

### Manual VoiceOver Testing
1. Enable VoiceOver (Cmd+F5)
2. Tab to the new feature
3. VoiceOver announces: Label, Hint, Keyboard shortcut
4. Verify each is concise and helpful
5. Test with arrow keys
6. Test with rotor (VO+U)

---

## References & Resources

### Apple Documentation
- [VoiceOver Rotor Documentation](https://developer.apple.com/documentation/swiftui/accessibilityrotor)
- [AccessibilityElement Documentation](https://developer.apple.com/documentation/swiftui/view/accessibilityelement(children:))
- [Accessibility Label Documentation](https://developer.apple.com/documentation/swiftui/view/accessibilitylabel(_:))

### WCAG Guidelines
- [WCAG 2.1 Level AAA](https://www.w3.org/WAI/WCAG21/quickref/?currentsetting=level%20aaa)
- [Success Criterion 4.1.3 Status Messages](https://www.w3.org/WAI/WCAG21/Understanding/status-messages.html)
- [Success Criterion 2.4.3 Focus Order](https://www.w3.org/WAI/WCAG21/Understanding/focus-order.html)

### Tools
- Accessibility Inspector (built-in to Xcode)
- Color Contrast Analyzer (browser extension)
- NVDA Screen Reader (Windows alternative to VoiceOver)

---

## Questions?

- Check `AccessibilityHelpers.swift` for utilities
- Review `WCAG_AAA_COMPLIANCE.md` for standards
- Run `ACCESSIBILITY_TESTING_CHECKLIST.md` before shipping
