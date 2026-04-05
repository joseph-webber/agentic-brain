# Voice Coding Guide — BrainChat Swift

**For Voice Users** — Code with your voice using BrainChat and Karen.

---

## Quick Start

1. Launch BrainChat
2. Click the mic button or press the mic shortcut
3. Karen says: *"Mic is live"*
4. Start speaking commands

---

## Voice Commands Reference

### 📖 Reading Code

| Say This | What Happens |
|----------|-------------|
| "Read line 10" | Reads line 10 with spoken code formatting |
| "Read lines 5 to 15" | Reads a range of lines |
| "Show line 42" | Same as read line |
| "What's on line 1" | Same as read line |

### 🧭 Navigation

| Say This | What Happens |
|----------|-------------|
| "Go to function main" | Finds and reads the function |
| "Find function processData" | Searches for the function |
| "Jump to method handleInput" | Same as go to function |
| "Go to line 25" | Reads that line |
| "List functions" | Lists all functions in the open file |
| "Search for TODO" | Searches code for a pattern |

### 🧠 Understanding Code

| Say This | What Happens |
|----------|-------------|
| "Explain this" | Sends code to LLM for explanation |
| "Explain the code" | Same — explains the open file |
| "Fix this error" | Asks LLM to find and fix bugs |
| "Debug this" | Same as fix this |
| "What's wrong" | Same as fix this |
| "Refactor" | Asks LLM for refactoring suggestions |
| "Spell handleInput" | Spells out identifier character by character |

### ✏️ Editing

| Say This | What Happens |
|----------|-------------|
| "Delete line 5" | Removes line 5 from buffer |
| "Insert at line 10 print hello" | Inserts text at line 10 |
| "Copy line 3" | Copies line 3 to clipboard |
| "Copy this" | Copies entire file to clipboard |
| "Replace foo with bar" | Replaces text in current file |
| "Create function calculate" | Asks LLM to generate a function |

### 📁 File Operations

| Say This | What Happens |
|----------|-------------|
| "Open file sort.py" | Opens and loads the file |
| "Close file" | Closes the current file |
| "Save to output.py" | Saves buffer to file |
| "Save as helpers.swift" | Same as save to |
| "Create file test.py" | Creates new file with template |
| "New file app.swift" | Same as create file |

### 🔧 Git & Testing

| Say This | What Happens |
|----------|-------------|
| "Git status" | Shows changed files |
| "Git diff" | Shows diff stats |
| "Show changes" | Same as git diff |
| "Commit add voice coding" | Commits all changes with message |
| "Run tests" | Runs pytest in ~/brain |
| "Run the tests" | Same |

### 🔄 Meta Commands

| Say This | What Happens |
|----------|-------------|
| "Undo" | Undoes last action |
| "Repeat" / "Again" | Repeats last action |
| "Do it again" | Same as repeat |

### 🤖 Copilot Commands

| Say This | What Happens |
|----------|-------------|
| "Copilot start" | Starts GitHub Copilot chat session |
| "Copilot stop" | Stops Copilot session |
| "Copilot explain sorting algorithms" | Sends to Copilot |
| "Copilot suggest Python sort function" | Copilot suggestion mode |

---

## How Code is Spoken

BrainChat uses **CodeSpeaker** to make code accessible:

### Line Numbers
Every line is announced with its number:
> *"Line 1: define function hello, open paren, close paren, colon"*
> *"Line 2: blank"*
> *"Line 3: print, open paren, hello world, close paren"*

### Operators
Symbols are spoken as words:
- `==` → "equals equals"
- `!=` → "not equal to"
- `>=` → "greater than or equal to"
- `->` → "returns"
- `&&` → "and"
- `||` → "or"

### Braces
- `{` → "open brace"
- `}` → "close brace"
- `func main() {` → "function main, open brace"

### Keywords
- `def` → "define function"
- `func` → "function"

### Identifiers
Say "spell" to hear character-by-character:
- `my_function_name` → "snake case with 3 parts: my, function, name"
- `HandleInput` → "Pascal case with 2 parts: Handle, Input"

---

## Demo: Complete Voice Coding Session

### 1. Create a Python sort function

**You say:** *"Create a Python function to sort a list"*

**Karen says:** *"Sending to Copilot"*

BrainChat routes to LLM (detects coding intent), streams the response.

**Karen reads the code:**
> *"Python code, 8 lines."*
> *"Line 1: define function sort list, open paren, items, close paren, colon"*
> *"Line 2: blank"*
> *"Line 3: return sorted, open paren, items, close paren"*
> *"End of code."*

### 2. Save the code

**You say:** *"Save to sort.py"*

**Karen says:** *"Saving to sort.py"*
> *"Saved to /Users/joe/brain/sort.py."*

### 3. Review the file

**You say:** *"Open file sort.py"*

**Karen says:** *"Opened sort.py. 8 lines of Python. Say read line followed by a number, or list functions."*

### 4. Read specific lines

**You say:** *"Read lines 1 to 5"*

Karen reads each line with numbers and code pronunciation.

### 5. Fix an issue

**You say:** *"Fix this error"*

BrainChat sends the file to the LLM with context, gets a fix, speaks the result.

### 6. Commit

**You say:** *"Commit add sort function"*

**Karen says:** *"Committed: add sort function"*

---

## Architecture

```
Voice Input (Mic)
    ↓
SpeechManager (Apple Dictation / Whisper)
    ↓
ChatViewModel (normalizes speech → text)
    ↓
CodeAssistant (routes to the right handler)
    ├── VoiceCodingEngine → local file ops, git, editing
    ├── CopilotBridge → GitHub Copilot CLI
    └── LLMRouter → Claude, GPT, Groq, Ollama
    ↓
CodeSpeaker (formats code for accessible speech)
    ↓
VoiceManager (Karen speaks the result)
```

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| VoiceCodingEngine | `VoiceCodingEngine.swift` | Parses voice commands, executes file/git/edit operations |
| CodeSpeaker | `CodeSpeaker.swift` | Formats code for speech (line numbers, operator pronunciation) |
| CodeAssistant | `CodeAssistant.swift` | Routes between voice coding, Copilot, and general AI |
| CopilotBridge | `CopilotBridge.swift` | Executes `gh copilot` CLI commands |
| SpeechManager | `SpeechManager.swift` | Speech-to-text with Apple Dictation or Whisper |
| VoiceManager | `VoiceManager.swift` | Text-to-speech with Karen voice |
| ChatViewModel | `ChatViewModel.swift` | Main coordinator with speech normalization |

---

## Speech-to-Text Tips

### Coding Terminology
BrainChat normalizes spoken coding terms when dictating:
- "curly brace" → `{`
- "open paren" → `(`
- "equals sign" → `=`
- "hashtag" / "hash" → `#`
- "underscore" → `_`
- "new line" → `\n`

### Best Practices
1. **Speak clearly** — pause between command and argument
2. **Use exact phrases** — "read line 10" not "can you read line 10 for me"
3. **Numbers** — say digits clearly: "line ten" works, "line 1 0" also works
4. **File names** — include the extension: "sort dot P Y"

---

## Accessibility Features

- **Full VoiceOver support** — all UI elements have accessibility labels
- **Keyboard navigation** — Tab through all controls, Cmd+Return to send
- **High contrast** — mic button shows green/red state clearly
- **State announcements** — Karen announces every state change
- **Queue system** — speech never overlaps, queued sequentially

---

## Testing

Run the voice coding tests:

```bash
cd ~/brain/agentic-brain/apps/BrainChat
swift test --filter "VoiceCoding|CodeSpeaker"
```

34 tests covering:
- Command parsing (24 tests)
- Code speech formatting (10 tests)

---

*Last updated: April 2026*
*Built with ♿️ for users with accessibility needs — accessibility is not optional*
