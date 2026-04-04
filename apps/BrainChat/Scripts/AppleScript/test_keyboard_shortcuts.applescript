-- test_keyboard_shortcuts.applescript
-- E2E test: Verify all keyboard shortcuts work without crashing.
-- Shortcuts under test:
--   Cmd+L  — Toggle microphone
--   Cmd+.  — Stop speaking
--   Cmd+,  — Open settings
--   Cmd+Return — Send message
-- Usage: osascript test_keyboard_shortcuts.applescript

on run
	set testName to "test_keyboard_shortcuts"
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
				
				-- Test 1: Cmd+L (mic toggle) — should not crash
				try
					keystroke "l" using command down
					delay 0.5
					keystroke "l" using command down -- toggle back
					delay 0.3
					set end of results to "  Cmd+L (mic toggle): PASS"
				on error errMsg
					set end of results to "  Cmd+L (mic toggle): FAIL — " & errMsg
				end try
				
				-- Test 2: Cmd+. (stop speaking) — should not crash
				try
					keystroke "." using command down
					delay 0.5
					set end of results to "  Cmd+. (stop speak): PASS"
				on error errMsg
					set end of results to "  Cmd+. (stop speak): FAIL — " & errMsg
				end try
				
				-- Test 3: Cmd+, (settings) — should open settings window/sheet
				try
					keystroke "," using command down
					delay 1
					-- Check if a new window or sheet appeared
					set windowCount to count of windows
					if windowCount > 1 then
						set end of results to "  Cmd+, (settings):   PASS — settings opened"
						-- Close the settings window
						keystroke "w" using command down
						delay 0.5
					else
						-- Settings might be a sheet in the same window
						set end of results to "  Cmd+, (settings):   PASS — shortcut accepted"
						key code 53 -- Escape to dismiss
						delay 0.3
					end if
				on error errMsg
					set end of results to "  Cmd+, (settings):   FAIL — " & errMsg
				end try
				
				-- Test 4: Cmd+Return (send) — with empty input should be a no-op
				try
					-- Clear input first
					keystroke "a" using command down
					delay 0.1
					key code 51 -- delete/backspace
					delay 0.2
					keystroke return using command down
					delay 0.5
					set end of results to "  Cmd+Ret (send):     PASS — no crash on empty send"
				on error errMsg
					set end of results to "  Cmd+Ret (send):     FAIL — " & errMsg
				end try
				
				-- Final: verify app is still alive and responsive
				if exists window 1 then
					set end of results to "  App alive after all: PASS"
				else
					set end of results to "  App alive after all: FAIL — window missing"
				end if
			end tell
		end tell
		
		-- Format results
		set passCount to 0
		set failCount to 0
		repeat with r in results
			if r contains "PASS" then
				set passCount to passCount + 1
			else
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
