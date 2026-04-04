# Voice Coding Guide — BrainChat

Code with your voice. Every command is designed for VoiceOver accessibility.

## Quick Start

1. Open BrainChat and tap the mic button
2. Say a voice command (see below)
3. BrainChat confirms your action via Karen voice
4. Results are spoken aloud with line numbers

## File Commands

| Say this | What happens |
|----------|-------------|
| "open file main.py" | Opens the file and reports line count |
| "read file utils.swift" | Same as open — loads and summarises |
| "close file" | Closes the current file buffer |
| "create file helpers.py" | Creates file with language template |
| "new file server.ts" | Same as create file |
| "save to output.py" | Saves current buffer to disk |
| "save as backup.txt" | Same as save to |

## Reading Code

| Say this | What happens |
|----------|-------------|
| "read line 10" | Reads line 10 with number prefix |
| "show line 42" | Same as read line |
| "what's on line 5" | Same as read line |
| "read lines 10 to 20" | Reads a range of lines |
| "show lines 1 through 5" | Same as read lines |
| "go to line 15" | Reads line 15 (jumps there) |
| "line 7" | Shorthand for read line 7 |

All lines are spoken as: "Line N: content" with operators pronounced.

## Navigation

| Say this | What happens |
|----------|-------------|
| "go to function main" | Finds function and reads context |
| "find function processData" | Same — searches for the function |
| "jump to method handle" | Same for methods |
| "list functions" | Lists all functions with line numbers |
| "show functions" | Same as list functions |
| "search for handleInput" | Searches code files for a term |
| "grep TODO" | Same as search for |

## Code Understanding

| Say this | What happens |
|----------|-------------|
| "explain this" | Sends code to AI for explanation |
| "explain the code" | Same — asks AI to explain |
| "fix this" | Asks AI to find and fix errors |
| "fix the error" | Same |
| "debug this" | Same as fix this |
| "what's wrong" | Same as fix this |
| "refactor" | Asks AI for refactoring suggestions |
| "refactor this" | Same |

## Editing

| Say this | What happens |
|----------|-------------|
| "delete line 5" | Removes line 5 from buffer |
| "insert at line 5 print('hi')" | Inserts code at line 5 |
| "copy line 3" | Copies line 3 to clipboard |
| "copy this" | Copies entire file to clipboard |
| "replace foo with bar" | Replaces all occurrences |

## Identifiers

| Say this | What happens |
|----------|-------------|
| "spell handleInput" | "camel case with 2 parts: handle, Input" |
| "spell out my_func_name" | "snake case with 3 parts: my, func, name" |
| "spell HandleInput" | "Pascal case with 2 parts: Handle, Input" |

## Git Commands

| Say this | What happens |
|----------|-------------|
| "git status" | Shows changed files |
| "check status" | Same |
| "what's changed" | Same |
| "git diff" | Shows diff summary |
| "show diff" | Same |
| "show changes" | Same |
| "what changed" | Same |
| "commit add voice coding" | Commits with that message |
| "commit changes fix typo" | Same |

## Tests

| Say this | What happens |
|----------|-------------|
| "run tests" | Runs test suite in ~/brain |
| "run the tests" | Same |
| "run tests in backend" | Runs tests in specific directory |

## Meta Commands

| Say this | What happens |
|----------|-------------|
| "undo" | Undoes the last action |
| "undo last" | Same |
| "repeat" | Repeats the last action |
| "again" | Same |
| "do it again" | Same |

## How Code is Spoken

### Operators are pronounced
- `!=` → "not equal to"
- `==` → "equals equals"
- `>=` → "greater than or equal to"
- `<=` → "less than or equal to"
- `=>` → "arrow"
- `->` → "returns"
- `+=` → "plus equals"
- `&&` → "and"
- `||` → "or"
- `...` → "dot dot dot"
- `..<` → "up to"
- `::` → "scope"

### Keywords are clarified
- `def ` → "define function"
- `func ` → "function"
- `elif ` → "else if"
- `pub fn ` → "public function"

### Braces are announced
- `{` → "open brace"
- `}` → "close brace"
- Trailing `{` on function lines → "function name, open brace"

### Blank lines
- Empty lines are announced as "Line N: blank"

### Code blocks
- Announced with language and line count: "Python code, 15 lines."
- Each line prefixed: "Line 1: define function main…"
- Ends with: "End of code."

## Copilot Integration

Voice coding commands that need AI (explain, fix, refactor, create function) are
routed through BrainChat's LLM router. If GitHub Copilot CLI is available, coding
prompts are sent there first; otherwise they go to the configured AI provider.

## Architecture

- **VoiceCodingEngine.swift** — Parses voice → `VoiceCodingAction` enum, executes actions
- **CodeSpeaker.swift** — Formats code for speech (line numbers, operator pronunciation)
- **CodeAssistant.swift** — Routes between voice coding, Copilot, system, and general AI
- **ChatViewModel.swift** — Integrates voice coding into the BrainChat UI

## Running Tests

```bash
cd ~/brain/agentic-brain/apps/BrainChat
swift test --filter "VoiceCoding"    # 28 command parsing tests
swift test --filter "CodeSpeaker"    # 13 speech formatting tests
```

Total: **41 tests** covering all voice commands and speech formatting.
