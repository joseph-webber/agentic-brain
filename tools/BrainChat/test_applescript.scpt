#!/usr/bin/osascript
-- BrainChat AppleScript Test Suite
-- For Joseph to automate Brain Chat via AppleScript
--
-- TWO METHODS AVAILABLE:
-- 1. Direct AppleEvent commands (tell application "Brain Chat")
-- 2. CLI fallback via do shell script (more reliable)

-- ============================================================
-- METHOD 1: DIRECT APPLESCRIPT COMMANDS
-- ============================================================

-- Test 1: Get current mode
tell application "Brain Chat"
    set currentMode to get mode
    log "Current mode (direct): " & currentMode
end tell

-- Test 2: Set mode to code
tell application "Brain Chat"
    set mode "code"
    delay 1
    set newMode to get mode
    log "Mode after change: " & newMode
end tell

-- Test 3: List all available modes
tell application "Brain Chat"
    set modeList to list modes
    log "Available modes:"
    log modeList
end tell

-- Test 4: Speak text
tell application "Brain Chat"
    speak "Hello Joseph, AppleScript direct commands are working."
end tell

-- Test 5: Get status
tell application "Brain Chat"
    set statusText to get status
    log "Status: " & statusText
end tell

-- ============================================================
-- METHOD 2: CLI FALLBACK (More Reliable)
-- ============================================================

-- Test 6: Get mode via CLI
set cliMode to do shell script "~/bin/brainchat-cli get-mode"
log "Mode via CLI: " & cliMode

-- Test 7: Set mode via CLI
do shell script "~/bin/brainchat-cli set-mode chat"
set cliMode2 to do shell script "~/bin/brainchat-cli get-mode"
log "Mode after CLI change: " & cliMode2

-- Test 8: List modes via CLI
set cliModes to do shell script "~/bin/brainchat-cli list-modes"
log "Modes via CLI:"
log cliModes

-- Test 9: Speak via CLI
do shell script "~/bin/brainchat-cli speak 'Hello Joseph, CLI commands are also working.'"

-- Test 10: Health check via CLI
set healthReport to do shell script "~/bin/brainchat-cli health"
log "Health Report via CLI:"
log healthReport

-- Test 11: Status via CLI
set cliStatus to do shell script "~/bin/brainchat-cli status"
log "Status via CLI: " & cliStatus

-- ============================================================
-- WINDOW CONTROL
-- ============================================================

-- Test 12: Show and hide window
tell application "Brain Chat"
    show window
    delay 1
    hide window
    delay 1
    show window
end tell

-- ============================================================
-- LLM COMMANDS
-- ============================================================

-- Test 13: Get current LLM
tell application "Brain Chat"
    set llmModel to get llm
    log "Current LLM: " & llmModel
end tell

-- Test 14: Set LLM model
tell application "Brain Chat"
    set llm "llama3.1:8b"
    set newLLM to get llm
    log "LLM after change: " & newLLM
end tell

-- ============================================================
-- CHAT VIA CLI (Most Reliable for LLM Queries)
-- ============================================================

-- Test 15: Send message via CLI
set response to do shell script "~/bin/brainchat-cli send 'What is 2 plus 2?'"
log "LLM Response: " & response

-- ============================================================
-- ACCESSIBILITY
-- ============================================================

-- Test 16: VoiceOver announcement
tell application "Brain Chat"
    announce "AppleScript test complete" priority "high"
end tell

-- Test 17: Describe UI
tell application "Brain Chat"
    set uiDescription to describe ui
    log "UI Description:"
    log uiDescription
end tell

log "All AppleScript tests complete!"

