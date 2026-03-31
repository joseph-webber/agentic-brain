-- Brain Chat Mic Button Automation Test
-- Created: 2026-03-22

set appName to "Brain Chat"
set resultFile to "/Users/joe/brain/agentic-brain/apps/BrainChat/runtime/automation-test-result.txt"
set testLog to ""
set testStartTime to do shell script "date '+%Y-%m-%d %H:%M:%S'"

on addLog(currentLog, msg)
    set theTimestamp to do shell script "date '+%H:%M:%S'"
    return currentLog & "[" & theTimestamp & "] " & msg & linefeed
end addLog

try
    set testLog to my addLog(testLog, "=== BRAIN CHAT MIC BUTTON AUTOMATION TEST ===")
    set testLog to my addLog(testLog, "Test started: " & testStartTime)
    set testLog to my addLog(testLog, "")
    
    -- STEP 1: Launch Brain Chat
    set testLog to my addLog(testLog, "STEP 1: Launching Brain Chat...")
    tell application "Brain Chat" to activate
    delay 2
    
    tell application "System Events"
        set appRunning to (name of processes) contains "Brain Chat"
    end tell
    
    if appRunning then
        set testLog to my addLog(testLog, "SUCCESS: Brain Chat launched")
    else
        set testLog to my addLog(testLog, "FAILED: Brain Chat not running")
        do shell script "echo " & quoted form of testLog & " > " & quoted form of resultFile
        error "App launch failed"
    end if
    
    -- STEP 2: Find mic button
    set testLog to my addLog(testLog, "")
    set testLog to my addLog(testLog, "STEP 2: Finding mic button...")
    
    set micButtonFound to false
    set clickSuccess to false
    
    tell application "System Events"
        tell process "Brain Chat"
            set frontmost to true
            delay 0.5
            
            try
                set windowCount to count of windows
                set testLog to my addLog(testLog, "  Windows: " & windowCount)
            end try
            
            try
                set allElements to entire contents of window 1
                set elementCount to count of allElements
                set testLog to my addLog(testLog, "  Total UI elements: " & elementCount)
                
                repeat with elem in allElements
                    try
                        set elemDesc to description of elem
                        set elemRole to role of elem
                        
                        if elemDesc contains "Microphone" then
                            set micButtonFound to true
                            set testLog to my addLog(testLog, "  FOUND: " & elemRole & " - " & elemDesc)
                            
                            try
                                set elemValue to value of elem
                                set testLog to my addLog(testLog, "  Value: " & elemValue)
                            end try
                            
                            if elemRole is "AXButton" then
                                click elem
                                set clickSuccess to true
                                set testLog to my addLog(testLog, "  CLICKED mic button!")
                            end if
                        end if
                    end try
                end repeat
            on error errMsg
                set testLog to my addLog(testLog, "  Error searching UI: " & errMsg)
            end try
        end tell
    end tell
    
    if micButtonFound then
        set testLog to my addLog(testLog, "SUCCESS: Mic button found")
    else
        set testLog to my addLog(testLog, "WARNING: Mic button not found")
    end if
    
    delay 1
    
    -- STEP 3: Check permission dialog
    set testLog to my addLog(testLog, "")
    set testLog to my addLog(testLog, "STEP 3: Checking for permission dialog...")
    
    set dialogFound to false
    
    tell application "System Events"
        try
            if exists process "CoreServicesUIAgent" then
                set dialogFound to true
                set testLog to my addLog(testLog, "  Found CoreServicesUIAgent dialog")
                tell process "CoreServicesUIAgent"
                    try
                        click button "OK" of window 1
                        set testLog to my addLog(testLog, "  Clicked OK")
                    end try
                end tell
            end if
        end try
    end tell
    
    if not dialogFound then
        set testLog to my addLog(testLog, "  No dialog (permission likely granted)")
    end if
    
    delay 1
    
    -- STEP 4: Verify state
    set testLog to my addLog(testLog, "")
    set testLog to my addLog(testLog, "STEP 4: Verifying mic state...")
    
    set micState to "Unknown"
    
    tell application "System Events"
        tell process "Brain Chat"
            try
                set allElements to entire contents of window 1
                repeat with elem in allElements
                    try
                        set elemDesc to description of elem
                        if elemDesc contains "Microphone" then
                            try
                                set elemValue to value of elem
                                if elemValue contains "Live" then
                                    set micState to "LIVE"
                                else if elemValue contains "Muted" then
                                    set micState to "MUTED"
                                end if
                                set testLog to my addLog(testLog, "  Mic state: " & elemValue)
                            end try
                        end if
                        if elemDesc contains "transcript" then
                            set micState to "LIVE (transcript visible)"
                            set testLog to my addLog(testLog, "  Transcript visible!")
                        end if
                    end try
                end repeat
            end try
        end tell
    end tell
    
    set testLog to my addLog(testLog, "  Final state: " & micState)
    
    -- Summary
    set testLog to my addLog(testLog, "")
    set testLog to my addLog(testLog, "=== TEST SUMMARY ===")
    set testEndTime to do shell script "date '+%Y-%m-%d %H:%M:%S'"
    set testLog to my addLog(testLog, "Completed: " & testEndTime)
    
    set overallResult to "PASSED"
    if not micButtonFound then
        set overallResult to "PARTIAL"
    end if
    if not clickSuccess then
        set overallResult to "PARTIAL"
    end if
    
    set testLog to my addLog(testLog, "Result: " & overallResult)
    set testLog to my addLog(testLog, "Mic Found: " & micButtonFound)
    set testLog to my addLog(testLog, "Click Success: " & clickSuccess)
    set testLog to my addLog(testLog, "Dialog: " & dialogFound)
    set testLog to my addLog(testLog, "State: " & micState)
    
    do shell script "echo " & quoted form of testLog & " > " & quoted form of resultFile
    
    return overallResult
    
on error errMsg number errNum
    set testLog to my addLog(testLog, "ERROR: " & errMsg & " (" & errNum & ")")
    do shell script "echo " & quoted form of testLog & " > " & quoted form of resultFile
    return "FAILED: " & errMsg
end try
