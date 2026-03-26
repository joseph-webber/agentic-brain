# ♿ Accessibility

> **Accessibility is not a feature — it's a foundation.**
>
> Agentic Brain is built by a blind developer for everyone. WCAG 2.1 AA compliance is our minimum standard, not our goal.

---

## 🎯 Our Commitment

```
╔════════════════════════════════════════════════════════════════════╗
║  "The harder the interface, the harder we work."                   ║
║                                                                    ║
║  Every feature ships accessible. No exceptions. No "future work."  ║
║  If it's not accessible, it's not done.                           ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## 📋 WCAG 2.1 AA Compliance

### Perceivable

| Criterion | Status | Implementation |
|-----------|--------|----------------|
| **1.1.1** Text Alternatives | ✅ | All images have alt text |
| **1.2.1** Audio-only/Video-only | ✅ | Transcripts provided |
| **1.3.1** Info and Relationships | ✅ | Semantic HTML, ARIA |
| **1.3.2** Meaningful Sequence | ✅ | Logical DOM order |
| **1.3.3** Sensory Characteristics | ✅ | No color-only indicators |
| **1.4.1** Use of Color | ✅ | Color + text/icon |
| **1.4.3** Contrast (Minimum) | ✅ | 4.5:1 text, 3:1 graphics |
| **1.4.4** Resize Text | ✅ | 200% zoom supported |
| **1.4.5** Images of Text | ✅ | Real text, not images |
| **1.4.10** Reflow | ✅ | No horizontal scroll at 320px |
| **1.4.11** Non-text Contrast | ✅ | 3:1 for UI components |
| **1.4.12** Text Spacing | ✅ | User styles respected |
| **1.4.13** Content on Hover/Focus | ✅ | Dismissible, hoverable |

### Operable

| Criterion | Status | Implementation |
|-----------|--------|----------------|
| **2.1.1** Keyboard | ✅ | All functionality via keyboard |
| **2.1.2** No Keyboard Trap | ✅ | Focus never trapped |
| **2.1.4** Character Key Shortcuts | ✅ | Remappable or require modifier |
| **2.2.1** Timing Adjustable | ✅ | No time limits |
| **2.3.1** Three Flashes | ✅ | No flashing content |
| **2.4.1** Bypass Blocks | ✅ | Skip links provided |
| **2.4.2** Page Titled | ✅ | Descriptive titles |
| **2.4.3** Focus Order | ✅ | Logical tab sequence |
| **2.4.4** Link Purpose | ✅ | Links describe destination |
| **2.4.6** Headings and Labels | ✅ | Descriptive, hierarchical |
| **2.4.7** Focus Visible | ✅ | 3px solid focus rings |
| **2.5.1** Pointer Gestures | ✅ | Single-point alternatives |
| **2.5.2** Pointer Cancellation | ✅ | Actions on up-event |
| **2.5.3** Label in Name | ✅ | Accessible names match visible |
| **2.5.4** Motion Actuation | ✅ | Motion not required |

### Understandable

| Criterion | Status | Implementation |
|-----------|--------|----------------|
| **3.1.1** Language of Page | ✅ | `lang` attribute set |
| **3.1.2** Language of Parts | ✅ | `lang` on foreign text |
| **3.2.1** On Focus | ✅ | No context change |
| **3.2.2** On Input | ✅ | Predictable behavior |
| **3.2.3** Consistent Navigation | ✅ | Same nav everywhere |
| **3.2.4** Consistent Identification | ✅ | Same labels for same functions |
| **3.3.1** Error Identification | ✅ | Clear error messages |
| **3.3.2** Labels or Instructions | ✅ | All inputs labeled |
| **3.3.3** Error Suggestion | ✅ | Helpful fix suggestions |
| **3.3.4** Error Prevention | ✅ | Confirmation for actions |

### Robust

| Criterion | Status | Implementation |
|-----------|--------|----------------|
| **4.1.1** Parsing | ✅ | Valid HTML |
| **4.1.2** Name, Role, Value | ✅ | Proper ARIA |
| **4.1.3** Status Messages | ✅ | Live regions |

---

## 🖥️ CLI-First Design

**The terminal is a first-class citizen.** No GUI required.

### Why CLI-First?

```
┌─────────────────────────────────────────────────────────────────┐
│ Terminal Benefits for Accessibility:                           │
│                                                                │
│ ✓ Screen readers work perfectly with text output               │
│ ✓ Keyboard-only by design                                      │
│ ✓ No mouse required                                            │
│ ✓ Works over SSH (remote access)                               │
│ ✓ Scriptable and automatable                                   │
│ ✓ Consistent across all platforms                              │
│ ✓ Low bandwidth (works on slow connections)                    │
│ ✓ Braille display compatible                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Screen Reader Optimized Output

```bash
# All output is screen reader friendly
$ ab status
Agentic Brain Status Report
Section: System Health
  Item: LLM Provider is Anthropic Claude, status is connected
  Item: Memory usage is 45 percent
  Item: Active agents count is 3
End of Section
Section: Recent Activity
  Item: Task completed: Code review at 2 35 PM
  Item: Task in progress: Documentation update
End of Section
End of Report
```

### No Emoji in Critical Output

```bash
# Good: Clear text, no decoration
$ ab task status
Task "code-review" completed successfully

# Bad: Emoji can confuse screen readers
$ ab task status
✅ Task "code-review" completed successfully 🎉
```

**Configuration:**

```bash
# Disable emoji globally
ab config set output.emoji false

# Enable verbose screen reader mode
ab config set output.screen_reader true
```

### Pipe-Friendly Output

```bash
# Machine-readable output for automation
ab status --format json | jq '.health'
ab agents list --format csv > agents.csv
ab chat "question" | say  # Pipe to speech

# Works with standard Unix tools
ab logs | grep ERROR | wc -l
ab tasks --format plain | head -20
```

### SSH Remote Access

```bash
# Full functionality over SSH
ssh server.example.com
ab chat "Analyze the logs for the past hour"

# Screen/tmux compatible
tmux new-session -d -s brain 'ab agent run monitor'
```

---

## 🔊 Voice Output

**145+ macOS voices + 35+ cloud TTS voices across macOS, Windows, and Linux.** Your AI speaks to you.

### macOS Voices

```bash
# List all available voices
ab voice list

# Default voice
ab config set voice.default "Karen (Premium)"  # Australian
ab config set voice.rate 160                   # Words per minute

# Voice by category
ab voice list --category australian
ab voice list --category british
ab voice list --category japanese
```

### Text-to-Speech Integration

```python
from agentic_brain import Brain

brain = Brain(voice=True)

# All responses are spoken
brain.chat("What's the weather?")  # Response is spoken aloud

# Manual speech
brain.speak("Processing your request")
brain.speak("Task completed successfully", voice="Daniel", rate=150)

# Queue multiple speech items
brain.speak_queue([
    "First, let me analyze the code",
    "Found 3 issues",
    "Would you like me to fix them?"
])
```

### Audio Notifications

```python
from agentic_brain.audio import notify

# Built-in sounds
notify.success()   # Pleasant chime
notify.error()     # Warning tone
notify.alert()     # Attention getter
notify.complete()  # Task done

# Custom notifications
notify.speak("Build completed", sound="hero")
```

### Voice Personas

```python
from agentic_brain.voice import Karen, Moira, Kyoko

# Different personas for different contexts
karen = Karen()  # Australian, lead persona
moira = Moira()  # Irish, creative work
kyoko = Kyoko()  # Japanese, technical work

karen.speak("G'day! Starting your code review.")
moira.speak("Here's a creative suggestion...")
kyoko.speak("Technical analysis complete.")
```

### Conversation Mode

```bash
# Full voice conversation
ab chat --voice
# Now you can speak and listen

# Continuous listening
ab listen
# Brain listens and responds
```

---

## 🎹 Keyboard Navigation

### Global Shortcuts

| Key | Action |
|-----|--------|
| `Tab` | Next element |
| `Shift+Tab` | Previous element |
| `Enter` | Activate/Select |
| `Escape` | Cancel/Close |
| `Space` | Toggle/Scroll |
| `Arrow Keys` | Navigate within components |
| `Home/End` | Jump to start/end |
| `Ctrl+C` | Cancel operation |

### CLI Shortcuts

| Key | Action |
|-----|--------|
| `Ctrl+A` | Start of line |
| `Ctrl+E` | End of line |
| `Ctrl+U` | Clear line |
| `Ctrl+L` | Clear screen |
| `Ctrl+R` | Search history |
| `Up/Down` | Previous/next command |
| `Tab` | Autocomplete |

### Vim/Emacs Mode

```bash
# Enable vi mode in CLI
ab config set shell.mode vi

# Enable emacs mode
ab config set shell.mode emacs
```

---

## 🖼️ React Frontend (Optional)

**When you need a GUI, it's fully accessible.**

### ARIA Implementation

```jsx
// All components use proper ARIA
<button
  aria-label="Deploy to production"
  aria-describedby="deploy-help"
  onClick={handleDeploy}
>
  Deploy
</button>
<p id="deploy-help" className="sr-only">
  Deploys the current version to the production environment
</p>

// Dynamic content announces changes
<div
  role="status"
  aria-live="polite"
  aria-atomic="true"
>
  {statusMessage}
</div>
```

### Focus Management

```jsx
// Focus is always visible
const FocusRing = styled.div`
  &:focus {
    outline: 3px solid #0066cc;
    outline-offset: 2px;
    box-shadow: 0 0 0 4px rgba(0, 102, 204, 0.2);
  }
  
  &:focus:not(:focus-visible) {
    outline: none;  // Hide for mouse users
  }
  
  &:focus-visible {
    outline: 3px solid #0066cc;
  }
`;
```

### High Contrast Mode

```bash
# Enable system high contrast
ab config set ui.high_contrast true

# Theme options
ab config set ui.theme "high-contrast-light"
ab config set ui.theme "high-contrast-dark"
```

### Screen Reader Testing

Tested with:

| Screen Reader | Platform | Status |
|---------------|----------|--------|
| **VoiceOver** | macOS/iOS | ✅ Fully tested |
| **NVDA** | Windows | ✅ Fully tested |
| **JAWS** | Windows | ✅ Fully tested |
| **Orca** | Linux | ✅ Tested |
| **TalkBack** | Android | ✅ Tested |
| **Narrator** | Windows | ✅ Tested |

---

## 🔧 Accessibility Settings

```bash
# View all accessibility settings
ab config list --category accessibility

# Core settings
ab config set accessibility.screen_reader true
ab config set accessibility.voice_feedback true
ab config set accessibility.reduce_motion true
ab config set accessibility.high_contrast true

# Voice settings  
ab config set accessibility.voice "Karen (Premium)"
ab config set accessibility.speech_rate 160
ab config set accessibility.announce_actions true

# Keyboard settings
ab config set accessibility.keyboard_shortcuts true
ab config set accessibility.sticky_keys true

# Output settings
ab config set accessibility.verbose_output true
ab config set accessibility.no_emoji true
ab config set accessibility.plain_text_errors true
```

---

## 🧪 Testing Accessibility

### Automated Testing

```bash
# Run accessibility audit
ab test accessibility

# Check specific component
ab test accessibility --component "chat-interface"

# WCAG level check
ab test accessibility --level AA
ab test accessibility --level AAA
```

### Manual Testing Checklist

```markdown
□ Navigate entire app with keyboard only
□ Test with VoiceOver/NVDA at 2x speed
□ Verify focus order is logical
□ Check all images have alt text
□ Verify color contrast ratios
□ Test at 200% zoom
□ Test with screen reader + braille display
□ Verify all errors are announced
□ Test with reduced motion enabled
□ Verify voice output is clear
```

---

## 📞 Reporting Accessibility Issues

**Accessibility issues are P0 (highest priority).**

```bash
# Report an issue
ab feedback --type accessibility "Description of the issue"

# Emergency contact for blocking issues
# Email: accessibility@agentic-brain.com
```

All accessibility issues are:
- Triaged within 24 hours
- Fixed within 1 sprint
- Tested by users with disabilities
- Never deprioritized

---

## 📚 Resources

### Guidelines
- [WCAG 2.1 Quick Reference](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [Inclusive Design Principles](https://inclusivedesignprinciples.org/)

### Tools
- [axe DevTools](https://www.deque.com/axe/) — Automated testing
- [WAVE](https://wave.webaim.org/) — Web accessibility evaluator
- [Contrast Checker](https://webaim.org/resources/contrastchecker/)

### Learning
- [A11y Project](https://www.a11yproject.com/)
- [WebAIM](https://webaim.org/)
- [Deque University](https://dequeuniversity.com/)

---

<div align="center">

**Built for Everyone** · Accessibility is not optional

*"The power of the Web is in its universality."* — Tim Berners-Lee

</div>
