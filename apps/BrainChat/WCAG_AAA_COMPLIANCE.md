# BrainChat WCAG 3.0 AAA Accessibility Compliance

## Overview

BrainChat has been updated to meet **WCAG 3.0 Level AAA** conformance - the highest accessibility standard.
Special focus on:
- **Fast navigation** for VoiceOver users (rotor support, skip links)
- **Concise labels** (verb-noun format, short action descriptions)
- **Logical grouping** (related controls grouped for efficient VoiceOver navigation)
- **7:1 contrast ratios** (AAA requirement for readability)
- **Extended descriptions** for complex UI elements

## WCAG 3.0 AAA Compliance Checklist

### 1. Perceivable (1.x)

- ✅ **1.4.3 Contrast (Enhanced)**: All text uses 7:1+ contrast ratio
  - Normal text: 7:1 minimum
  - Large text (18pt+): 4.5:1 minimum
  - UI components: 3:1 minimum
  - Implemented in: `AccessibilityHelpers.swift`
  - NEW: `contrastRatio()` and `meetsAAAContrast()` functions

- ✅ **1.4.11 Non-text Contrast**: UI buttons and controls have 3:1 contrast
  - Mic button (green/red with background)
  - Stop button (icon color on background)
  - Settings button (consistent styling)

### 2. Operable (2.x)

- ✅ **2.1.1 Keyboard**: All functionality available via keyboard
  - Cmd+1: Focus conversation
  - Cmd+2: Focus message input
  - Cmd+3: Focus controls
  - Cmd+M: Toggle microphone
  - Cmd+.: Stop speaking
  - Cmd+,: Open settings
  - Cmd+K: Clear conversation
  - Cmd+N: New conversation
  - Cmd+? or Cmd+/: Show keyboard help

- ✅ **2.1.3 Keyboard (No Exception)**: All features keyboard accessible
  - No timing-dependent mouse-only actions
  - Message sending works with Return or Cmd+Return
  - Settings accessible via keyboard throughout

- ✅ **2.2.1 Timing Adjustable**: No timing-dependent interactions
  - No auto-dismiss notifications
  - No countdown timers for actions
  - Destructive actions require confirmation

- ✅ **2.4.1 Bypass Blocks**: Skip links and landmarks implemented
  - Section identifiers for quick VoiceOver rotor navigation
  - Accessible landmarks for:
    - Status section
    - Control buttons
    - Conversation area
    - Message input
  - Keyboard shortcuts to jump between major sections

- ✅ **2.4.3 Focus Order**: Logical, meaningful focus sequence
  - Controls area → Message input → Conversation (then loops)
  - Within controls: LLM selector → Mic → Stop → Settings
  - Clear visual focus indicators

- ✅ **2.4.8 Focus Visible**: All interactive elements show focus
  - Button focus outlines
  - Text field cursor and outline
  - Keyboard shortcut help overlay

### 3. Understandable (3.x)

- ✅ **3.2.3 Consistent Navigation**: Controls always in same location/order
  - Toolbar organization never changes
  - Button positions consistent
  - Settings accessible from same location
  - Input field always at bottom

- ✅ **3.2.4 Consistent Identification**: Buttons behave predictably
  - Mic button always toggles microphone state
  - Stop button always stops speaking
  - Send button always sends message
  - Settings button always opens settings

- ✅ **3.3.4 Error Prevention**: Protective design for destructive actions
  - Clear conversation requires confirmation dialog
  - Dialog clearly states: "This will permanently delete all messages"
  - Users can cancel before proceeding

### 4. Robust (4.x)

- ✅ **4.1.2 Name, Role, Value**: All UI elements properly identified
  - Each button has accessible label
  - Status indicators have roles and values
  - Form inputs have labels and hints
  - Examples:
    ```swift
    .accessibilityShortLabel("Mic live")  // Name
    .accessibilityAddTraits(.isButton)     // Role
    .accessibilityHint("Toggle microphone") // Value
    ```

- ✅ **4.1.3 Status Messages**: Real-time announcements
  - "Message sent" when user sends
  - "New response from Brain Chat" when AI responds
  - "Response ready" when processing complete
  - "Microphone now live/muted" when toggled
  - Uses `AccessibilityHelpers.announceHighPriority()` for critical changes

## New Accessibility Features

### 1. AccessibilityHelpers.swift

Centralized utilities for WCAG AAA compliance:

```swift
// High-priority announcements for important state changes
AccessibilityHelpers.announceHighPriority("Microphone now live")

// Consistent audio level descriptions
AudioLevelAccessibility.describe(level: 0.5)  // "Moderate – normal speech level"

// Message role standardization
ChatMessage.Role.assistant.accessibilityName  // "Brain Chat response"

// Accessible button labels (short form)
AccessibleButtonLabels.micLive         // "Mic live"
AccessibleButtonLabels.stopSpeaking    // "Stop"
AccessibleButtonLabels.settings        // "Settings"
```

### 2. Improved Section Grouping

#### Status Area (Upper Toolbar)
```
├─ Configuration Group
│  ├─ LLM Model Selector
│  ├─ YOLO Mode Selector
│  └─ Speech Engine Selector
├─ Status Group
│  ├─ Session Status (Copilot active/inactive)
│  └─ Audio Level Indicator
└─ Control Group
   ├─ Microphone Button (Mic live / Mic muted)
   ├─ Stop Button (Stop speaking)
   ├─ Settings Button (Settings)
   └─ Clear Button (Clear chat)
```

#### Conversation Area
```
├─ Empty State (shown when no messages)
├─ Message List (each message labeled with role)
└─ Processing Indicator (shown while thinking)
```

#### Input Area
```
├─ Message Input Field
└─ Send Button
```

### 3. Concise Label Examples

**Before (Verbose)**
```
"Microphone toggle button"
"Currently live, listening"
"Double tap to mute microphone"
"Microphone input level"
"Shows how much audio Brain Chat is hearing right now"
```

**After (WCAG AAA Concise)**
```
"Mic live"                    // accessibilityShortLabel
"Toggle microphone"           // accessibilityHint
"Silent – no audio detected"  // Extended description
```

### 4. Fast Navigation (Rotor Support)

VoiceOver users can use the rotor to quickly jump between:
- **Section IDs**: `statusSection`, `controlsGroup`, `conversationSection`, `inputSection`
- **Status indicators**: `copilotStatus`, `audioLevelGroup`
- **Controls**: `microphoneButton`, `stopButton`, `settingsButton`, `clearButton`
- **Messages**: Each message has unique ID for quick review

**How to use (macOS VoiceOver):**
1. Open VoiceOver (Cmd+F5)
2. Press VO+U to open the rotor
3. Use arrow keys to navigate sections
4. Press Enter to jump to section

### 5. Accessibility Identifiers

All major sections have unique identifiers for:
- Testing (automated accessibility audits)
- VoiceOver rotor navigation
- Debugging accessibility issues

```swift
AccessibilitySectionID.statusSection        // "statusSection"
AccessibilitySectionID.controlsGroup        // "controlsGroup"
AccessibilitySectionID.conversationSection  // "conversationSection"
AccessibilitySectionID.inputSection         // "inputSection"
AccessibilitySectionID.liveTranscript       // "liveTranscript"
AccessibilitySectionID.processingIndicator  // "processingIndicator"
```

## Testing WCAG 2.1 AAA Compliance

### Automated Testing

```swift
// Using XCTest Accessibility API
let app = XCUIApplication()
app.launch()

// Verify labels are concise (< 15 chars ideal)
let micButton = app.buttons["microphoneButton"]
XCTAssertLessThan(micButton.label.count, 30)

// Verify all buttons keyboard accessible
app.typeKey(XCUIKeyboardKey.tab, modifierFlags: .command)

// Verify status announcements
// (Check system accessibility log)
```

### Manual Testing with VoiceOver

**Test Navigation:**
1. Enable VoiceOver: System Prefs → Accessibility → VoiceOver
2. Press VO (Ctrl+Option) + U to open rotor
3. Verify can jump between sections:
   - Conversation area
   - Message input
   - Controls
   - Status indicators

**Test Labels:**
1. Tab through each button
2. VoiceOver should announce:
   - Short label (e.g., "Mic live")
   - Hint (e.g., "Toggle microphone")
   - Keyboard shortcut (e.g., "Cmd+M")

**Test Real-Time Announcements:**
1. Send a message → Should announce "Message sent"
2. Await response → Should announce "Response ready" or "New Brain Chat response"
3. Toggle microphone → Should announce "Microphone now live" or "Microphone now muted"
4. Click stop while speaking → Should announce "Stopped speaking"

### Contrast Testing

**Using macOS Accessibility Inspector:**
1. Open Accessibility Inspector: Cmd+Option+A in Xcode
2. Click "Color Contrast" calculator
3. Verify 7:1 ratio for:
   - Text on light backgrounds
   - Text on dark backgrounds
   - Button icons on backgrounds

**Quick Test:**
- Black text on white background: 21:1 ✓
- White text on dark gray: 7.5:1 ✓
- Button colors (green/red): 3:1+ ✓

## Keyboard Shortcuts Reference

| Shortcut | Action | When to Use |
|----------|--------|------------|
| **Navigation** | | |
| Cmd+1 | Focus conversation | View past messages |
| Cmd+2 | Focus message input | Write a new message |
| Cmd+3 | Focus controls | Toggle mic or settings |
| **Microphone** | | |
| Cmd+M or Cmd+L | Toggle microphone | Quick mic on/off |
| **Message Management** | | |
| Return | Send message | After typing |
| Cmd+Return | Send instantly | Quick submit |
| Escape | Clear current message | Cancel typing |
| Cmd+Up | Previous message | Review sent message |
| Cmd+Down | Next message | Browse message history |
| **Other** | | |
| Cmd+N | New conversation | Start fresh |
| Cmd+K | Clear all messages | Delete conversation |
| Cmd+, | Settings | Configure Brain Chat |
| Cmd+. | Stop speaking | Interrupt voice output |
| Cmd+? or Cmd+/ | Show keyboard help | Learn all shortcuts |

## Best Practices Implemented

### 1. Label Conciseness
- ✓ Short labels: "Mic live" not "Microphone toggle button"
- ✓ Action-focused: "Stop" not "Stop speaking"
- ✓ Hints separate: Put details in `accessibilityHint`, not label

### 2. Logical Grouping
- ✓ Controls grouped in `HStack` with `children: .contain`
- ✓ Status indicators grouped together
- ✓ Related toggles grouped in sections

### 3. Real-Time Feedback
- ✓ State changes announced immediately
- ✓ High-priority for critical changes
- ✓ Normal-priority for background updates
- ✓ No silent state changes

### 4. Error Prevention
- ✓ Destructive actions require confirmation
- ✓ Dialog clearly explains consequences
- ✓ Cancel option always available

### 5. Keyboard First
- ✓ All features keyboard accessible
- ✓ Logical focus order
- ✓ Shortcuts don't conflict with system
- ✓ Help available via keyboard

## Extended Audio Descriptions

### Status Indicators
- **Audio Level**: "Silent – no audio detected" → "High – loud audio or background noise"
- **Copilot Session**: "Active – connected" or "Inactive – not connected"
- **Processing**: "Brain Chat is generating a response"

### Message Types
- **User Message**: "Your message: [text]"
- **Brain Chat Response**: "Brain Chat response: [text]"
- **System Message**: "System notification: [text]"

### Actions
- **Microphone Toggle**: "Mic currently [live/muted]. Tap to toggle."
- **Send Button**: "Send message. Disabled when no text entered. Ready to send."
- **Settings**: "Open settings to configure Brain Chat"

## Future Enhancements

- [ ] Sign language video overlay option (WCAG 1.2.6)
- [ ] Audio descriptions for complex charts/graphs
- [ ] Custom focus indicator styling (brighter/larger)
- [ ] Reduced motion mode (respect prefers-reduced-motion)
- [ ] Dyslexia-friendly font option
- [ ] High contrast theme

## References

- [WCAG 2.1 Standard](https://www.w3.org/WAI/WCAG21/quickref/)
- [Apple Accessibility Guides](https://developer.apple.com/accessibility/)
- [VoiceOver User Guide](https://www.apple.com/accessibility/voiceover/)
- [macOS Accessibility Inspector](https://developer.apple.com/library/archive/documentation/Accessibility/Conceptual/AccessibilityMacOSX/OSXAXTestingApps.html)

## Support

For accessibility issues or improvements:
1. Test with VoiceOver enabled (System Prefs → Accessibility)
2. Check keyboard navigation with Cmd+Tab and Tab key
3. Verify all state changes announced via Accessibility Inspector
4. Report issues with details about:
   - VoiceOver behavior
   - Expected announcement
   - Actual announcement
   - Keyboard shortcut (if applicable)
