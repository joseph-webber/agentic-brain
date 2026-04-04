-- BrainChat Complete Feature Test Suite
-- Tests all AppleScript-accessible features

on run
    set testResults to {}
    set passCount to 0
    set failCount to 0
    
    tell application "Brain Chat"
        activate
        delay 1
        
        -- Test 1: Get current mode
        try
            set currentMode to current mode
            if currentMode is in {"chat", "code", "terminal", "yolo", "voice", "work"} then
                set end of testResults to "✅ PASS: Get current mode = " & currentMode
                set passCount to passCount + 1
            else
                set end of testResults to "❌ FAIL: Invalid mode value: " & currentMode
                set failCount to failCount + 1
            end if
        on error errMsg
            set end of testResults to "❌ FAIL: Get mode error - " & errMsg
            set failCount to failCount + 1
        end try
        
        -- Test 2: Set mode to code
        try
            set current mode to "code"
            delay 0.5
            set newMode to current mode
            if newMode is "code" then
                set end of testResults to "✅ PASS: Set mode to code"
                set passCount to passCount + 1
            else
                set end of testResults to "❌ FAIL: Mode not changed, got: " & newMode
                set failCount to failCount + 1
            end if
        on error errMsg
            set end of testResults to "❌ FAIL: Set mode error - " & errMsg
            set failCount to failCount + 1
        end try
        
        -- Test 3: Set mode to chat (restore)
        try
            set current mode to "chat"
            delay 0.5
            set restoredMode to current mode
            if restoredMode is "chat" then
                set end of testResults to "✅ PASS: Restore mode to chat"
                set passCount to passCount + 1
            else
                set end of testResults to "❌ FAIL: Restore failed, got: " & restoredMode
                set failCount to failCount + 1
            end if
        on error errMsg
            set end of testResults to "❌ FAIL: Restore mode error - " & errMsg
            set failCount to failCount + 1
        end try
        
        -- Test 4: Get status
        try
            set appStatus to status
            if length of appStatus > 0 then
                set end of testResults to "✅ PASS: Get status (length=" & (length of appStatus) & ")"
                set passCount to passCount + 1
            else
                set end of testResults to "❌ FAIL: Status is empty"
                set failCount to failCount + 1
            end if
        on error errMsg
            set end of testResults to "❌ FAIL: Get status error - " & errMsg
            set failCount to failCount + 1
        end try
        
        -- Test 5: Check listening state
        try
            set listening to is listening
            if listening is false then
                set end of testResults to "✅ PASS: Listening state accessible (currently: " & listening & ")"
                set passCount to passCount + 1
            else
                set end of testResults to "✅ PASS: Listening state is true (mic active)"
                set passCount to passCount + 1
            end if
        on error errMsg
            set end of testResults to "❌ FAIL: Listening state error - " & errMsg
            set failCount to failCount + 1
        end try
        
        -- Test 6: Check bridge connected
        try
            set connected to bridge connected
            set end of testResults to "✅ PASS: Bridge connected state = " & connected
            set passCount to passCount + 1
        on error errMsg
            set end of testResults to "❌ FAIL: Bridge connected error - " & errMsg
            set failCount to failCount + 1
        end try
        
        -- Test 7: Get last response
        try
            set lastResp to last response
            set end of testResults to "✅ PASS: Last response accessible (length=" & (length of lastResp) & ")"
            set passCount to passCount + 1
        on error errMsg
            set end of testResults to "❌ FAIL: Last response error - " & errMsg
            set failCount to failCount + 1
        end try
        
    end tell
    
    -- Generate summary
    set summary to "
========================================
BRAINCHAT APPLESCRIPT TEST RESULTS
========================================"
    
    repeat with result in testResults
        set summary to summary & "
" & result
    end repeat
    
    set summary to summary & "
========================================
SUMMARY: " & passCount & " passed, " & failCount & " failed
========================================"
    
    return summary
end run
