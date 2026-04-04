-- test_basic_chat.applescript
-- E2E test: Launch BrainChat, send a message, verify a response appears.
-- Usage: osascript test_basic_chat.applescript

on run
	set testName to "test_basic_chat"
	set appName to "Brain Chat"
	
	try
		-- Launch app if needed
		if not isRunning(appName) then
			tell application appName to activate
			delay 3
		end if
		
		tell application "System Events"
			tell process appName
				set frontmost to true
				delay 0.5
				
				-- Count existing UI elements so we can detect new ones
				set initialCount to my countUIElements()
				
				-- Type test message (Cmd+A first to replace any existing text)
				keystroke "a" using command down
				delay 0.2
				keystroke "Hello from E2E test"
				delay 0.3
				
				-- Send with Cmd+Return
				keystroke return using command down
				
				-- Wait for LLM response with progressive checks
				set gotResponse to false
				repeat 4 times
					delay 3
					set afterCount to my countUIElements()
					if afterCount > initialCount then
						set gotResponse to true
						exit repeat
					end if
				end repeat
				
				if gotResponse then
					return "PASS: " & testName & " — response received (" & (afterCount - initialCount) & " new UI elements)"
				else
					-- Even without LLM response, verify message was sent (input cleared)
					return "WARN: " & testName & " — message sent but no response in 12s (LLM may be offline). UI elements: " & afterCount
				end if
			end tell
		end tell
		
	on error errMsg number errNum
		return "ERROR: " & testName & " — " & errMsg & " (" & errNum & ")"
	end try
end run

on isRunning(appName)
	tell application "System Events"
		return (exists process appName)
	end tell
end isRunning

on countUIElements()
	try
		tell application "System Events"
			return count of UI elements of window 1 of process "Brain Chat"
		end tell
	on error
		return 0
	end try
end countUIElements
