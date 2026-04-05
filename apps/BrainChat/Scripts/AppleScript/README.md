# BrainChat AppleScript E2E Test Suite

End-to-end tests that drive Brain Chat through macOS System Events, validating the real UI as user would experience it with VoiceOver.

## Tests

| Script | What it tests |
|--------|---------------|
| `test_basic_chat.applescript` | Send a message, verify response appears |
| `test_brainchat.applescript` | AppleScript scripting API (send message, get response, etc.) |
| `test_voice_toggle.applescript` | Cmd+L toggles microphone Live/Muted |
| `test_keyboard_shortcuts.applescript` | Cmd+L, Cmd+., Cmd+,, Cmd+Return |
| `test_accessibility.applescript` | AX labels, tab navigation, scroll areas |
| `test_window_management.applescript` | Resize, move, minimise, restore |
| `test_clear_conversation.applescript` | Trash button → confirmation dialog flow |

## Quick Start

```bash
cd /Users/joe/brain/agentic-brain/apps/BrainChat/Scripts/AppleScript
./run_all_tests.sh           # run all
./run_all_tests.sh --verbose # with detailed output
osascript test_accessibility.applescript  # run one test
```

## Prerequisites

1. **Brain Chat built** — `Brain Chat.app` exists in the parent directory (`../Brain Chat.app`)
2. **Accessibility permission** — Terminal (or the calling app) must be in  
   System Settings → Privacy & Security → Accessibility
3. **System Events access** — granted automatically on first run (click Allow)

## Output Format

Each test returns a single string starting with:

- `PASS:` — test succeeded
- `FAIL:` — test found an issue
- `WARN:` — non-critical concern
- `ERROR:` — test could not run (crash/permission)

## Adding Tests

Create `test_<name>.applescript` following the pattern:

```applescript
on run
    set testName to "test_<name>"
    set appName to "Brain Chat"
    try
        -- ... test logic ...
        return "PASS: " & testName & " — description"
    on error errMsg number errNum
        return "ERROR: " & testName & " — " & errMsg
    end try
end run
```

The runner picks up any `test_*.applescript` file automatically.
