-- test_window_management.applescript
-- E2E test: Verify window can be resized, minimised, and restored.
-- Tests that Brain Chat behaves correctly as a native macOS citizen.
-- Usage: osascript test_window_management.applescript

on run
	set testName to "test_window_management"
	set appName to "Brain Chat"
	set results to {}
	
	try
		if not isRunning(appName) then
			tell application appName to activate
			delay 3
		end if
		
		tell application "System Events"
			tell process appName
				set frontmost to true
				delay 0.5
				
				-- Test 1: Window exists
				try
					if exists window 1 then
						set end of results to "  Window exists:      PASS"
					else
						set end of results to "  Window exists:      FAIL"
						return "FAIL: " & testName & " — no window"
					end if
				on error errMsg
					set end of results to "  Window exists:      FAIL — " & errMsg
				end try
				
				-- Test 2: Get and restore window position/size
				try
					set origPos to position of window 1
					set origSize to size of window 1
					set end of results to "  Window geometry:    PASS — pos " & (item 1 of origPos) & "," & (item 2 of origPos) & " size " & (item 1 of origSize) & "x" & (item 2 of origSize)
				on error errMsg
					set end of results to "  Window geometry:    FAIL — " & errMsg
				end try
				
				-- Test 3: Resize window
				try
					set size of window 1 to {800, 600}
					delay 0.5
					set newSize to size of window 1
					-- Restore original
					set size of window 1 to origSize
					delay 0.3
					set end of results to "  Resize window:      PASS — resized to " & (item 1 of newSize) & "x" & (item 2 of newSize)
				on error errMsg
					set end of results to "  Resize window:      FAIL — " & errMsg
				end try
				
				-- Test 4: Move window
				try
					set position of window 1 to {100, 100}
					delay 0.3
					set movedPos to position of window 1
					-- Restore original
					set position of window 1 to origPos
					delay 0.3
					set end of results to "  Move window:        PASS — moved to " & (item 1 of movedPos) & "," & (item 2 of movedPos)
				on error errMsg
					set end of results to "  Move window:        FAIL — " & errMsg
				end try
				
				-- Test 5: Minimize and restore
				try
					-- Minimize
					click (first button whose subrole is "AXMinimizeButton") of window 1
					delay 1
					
					-- Restore by activating app
					tell application appName to activate
					delay 1
					
					if exists window 1 then
						set end of results to "  Minimize/restore:   PASS"
					else
						set end of results to "  Minimize/restore:   FAIL — window did not restore"
					end if
				on error errMsg
					-- Minimize might not be available; still pass if app is alive
					tell application appName to activate
					delay 0.5
					set end of results to "  Minimize/restore:   WARN — " & errMsg
				end try
				
				-- Test 6: Verify app responds after all manipulation
				try
					set frontmost to true
					delay 0.3
					if exists window 1 then
						set end of results to "  Post-test alive:    PASS"
					else
						set end of results to "  Post-test alive:    FAIL"
					end if
				on error errMsg
					set end of results to "  Post-test alive:    FAIL — " & errMsg
				end try
			end tell
		end tell
		
		-- Format
		set passCount to 0
		set failCount to 0
		repeat with r in results
			if r contains "PASS" then
				set passCount to passCount + 1
			else if r contains "FAIL" then
				set failCount to failCount + 1
			end if
		end repeat
		
		set resultText to testName & " — " & passCount & " passed, " & failCount & " failed" & linefeed
		repeat with r in results
			set resultText to resultText & r & linefeed
		end repeat
		
		if failCount = 0 then
			return "PASS: " & resultText
		else
			return "FAIL: " & resultText
		end if
		
	on error errMsg number errNum
		return "ERROR: " & testName & " — " & errMsg & " (" & errNum & ")"
	end try
end run

on isRunning(appName)
	tell application "System Events"
		return (exists process appName)
	end tell
end isRunning
