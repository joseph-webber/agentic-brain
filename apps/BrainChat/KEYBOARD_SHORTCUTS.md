# BrainChat Keyboard Shortcuts Guide

BrainChat now includes comprehensive keyboard shortcuts for fast navigation and accessibility. All shortcuts are announced by VoiceOver and work without a mouse.

## Keyboard Shortcuts

### Navigation (Cmd+1/2/3)
- **Cmd+1** - Focus on chat conversation area
- **Cmd+2** - Focus on message input field (text box)
- **Cmd+3** - Focus on control buttons (microphone, settings, etc.)

### Message Handling
- **Cmd+Enter** - Send message instantly
- **Cmd+Shift+V** - Paste from clipboard and send automatically
- **Cmd+Up Arrow** - Navigate to previous message in history
- **Cmd+Down Arrow** - Navigate to next message in history
- **Escape** - Clear the input text field

### Conversation Management
- **Cmd+N** - Start a new conversation (clears all messages)
- **Cmd+K** - Clear current conversation (with confirmation)
- **Cmd+R** - Repeat the last assistant response aloud

### Audio Controls
- **Cmd+L** - Toggle microphone on/off
- **Cmd+M** - Toggle mute (same as Cmd+L)
- **Cmd+.** (Cmd+Period) - Stop current audio playback

### Settings & Help
- **Cmd+,** (Cmd+Comma) - Open Brain Chat settings
- **Cmd+?** - Show keyboard shortcuts help
- **Cmd+/** - Show keyboard shortcuts help (alternative)

## Features

### VoiceOver Accessibility
- All keyboard shortcuts are automatically announced by VoiceOver
- Detailed accessibility labels for every control
- Clear vocal feedback for all actions (focus changes, conversation clears, etc.)
- Accessible help overlay with organized shortcut categories

### Message History Navigation
Navigate through previously sent messages using keyboard:
- Press **Cmd+Up Arrow** to go to older messages
- Press **Cmd+Down Arrow** to go to newer messages
- Press **Escape** or **Cmd+Down Arrow** from the oldest message to clear the history browser
- Edited messages are NOT added to history (only when sent)

### Focus Management
Quickly jump between UI sections without using Tab:
- **Cmd+1** focuses the conversation to read previous messages
- **Cmd+2** focuses the input field to type a new message
- **Cmd+3** focuses the control buttons (microphone, stop, settings)

### Quick Paste & Send
- **Cmd+Shift+V** pastes your clipboard content and sends it immediately
- Perfect for quick responses from copied text
- Announces when clipboard is empty

### New Conversation
- **Cmd+N** starts a fresh conversation
- Clears message history
- Resets the input field
- Returns focus to the message input

### Repeat Last Response
- **Cmd+R** replays the last assistant message
- Perfect for hearing a response again
- Announces if no previous response exists

## Keyboard Shortcut Help

Press **Cmd+?** or **Cmd+/** to open the interactive keyboard shortcuts help overlay. The help includes:
- All available shortcuts organized by category
- Keyboard combinations displayed in monospace font
- Accessible descriptions for screen readers
- Easy to navigate with arrow keys or mouse

Close the help overlay by pressing **Escape** or clicking outside it.

## Pro Tips

1. **Quick Focus** - Use Cmd+1/2/3 to quickly jump between chat, input, and controls without tabbing through everything

2. **Message History** - Built-in message history works like terminal command history - Cmd+Up/Down to navigate

3. **Paste & Send** - Instead of typing `Cmd+V`, `Cmd+Enter`, use `Cmd+Shift+V` as a single step

4. **Stop Immediately** - Press **Cmd+.** to stop any audio response that's playing

5. **New Conversation** - Press **Cmd+N** instead of manually clearing messages

6. **Input Cleanup** - Press **Escape** to instantly clear your draft message

## VoiceOver Integration

All keyboard shortcuts work seamlessly with VoiceOver:
- Shortcuts are announced when buttons are focused
- Actions trigger clear vocal feedback
- Help overlay is fully navigable with VoiceOver
- All states (muted/live, speaking/idle) are clearly announced

### VoiceOver Navigation Tips

1. Navigate to a button and press **VO+Space** to activate (or spacebar on configured setups)
2. Use **Cmd+1/2/3** for quick section jumps
3. Press **VO+U** to open the Web Rotor and quickly jump between sections
4. Cmd+? works with VoiceOver active to get help

## Implementation Details

### Architecture
- Shortcuts use SwiftUI's `onKeyPress()` modifier for modern key handling
- Focus state management with `@FocusState` for keyboard-driven navigation
- Full accessibility integration with NSAccessibility APIs

### Message History
- Stored in `@State private var messageHistory: [String]`
- Index tracking with `messageHistoryIndex` (-1 = current input)
- Only sent messages are added to history
- Cleared when starting new conversation

### Help Overlay
- Custom `KeyboardShortcutsHelpOverlay` struct
- Grouped shortcuts by category (Navigation, Message Handling, Conversation, etc.)
- Scrollable content for all shortcuts
- Keyboard (Escape) and mouse (click outside) support

### Accessibility
- All controls have detailed `accessibilityLabel` and `accessibilityHint`
- Actions post announcements via `postAccessibilityAnnouncement()`
- Focus transitions announced ("Focused on conversation area", etc.)
- Comprehensive hints for each shortcut

## Testing the Shortcuts

### Manual Testing
1. Open BrainChat
2. Press Cmd+? to see all shortcuts
3. Test Cmd+1, Cmd+2, Cmd+3 to navigate
4. Type a message and press Cmd+Up to recall it
5. Press Escape to clear the input
6. Start a new conversation with Cmd+N

### VoiceOver Testing
1. Enable VoiceOver (Cmd+F5)
2. Press Cmd+1 and listen for "Focused on conversation area"
3. Press Cmd+2 and listen for "Focused on message input field"
4. Type and press Cmd+Up - hear previous message announced
5. Press Cmd+? and navigate the help overlay

### Accessibility Compliance
- ✅ WCAG 2.1 Level AA compliant
- ✅ All shortcuts keyboard-accessible
- ✅ VoiceOver fully supported
- ✅ No mouse required for any function
- ✅ Clear visual and audio feedback

## Future Enhancements

Potential additions:
- **Cmd+Shift+N** - Open new conversation in background
- **Cmd+E** - Edit last message
- **Cmd+Backspace** - Delete last message
- **Cmd+[** / **Cmd+]** - Navigate between conversations
- **Cmd+S** - Save conversation to file
- **Cmd+O** - Load saved conversation
