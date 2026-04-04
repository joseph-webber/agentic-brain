-- test_brainchat.applescript
-- E2E test: Exercises all native AppleScript commands exposed via BrainChat.sdef
-- Usage: osascript test_brainchat.applescript

on run
	set testName to "test_brainchat_scripting"
	set appName to "Brain Chat"
	set passCount to 0
	set failCount to 0
	set results to {}

	try
		-- Ensure app is running
		if not isRunning(appName) then
			tell application appName to activate
			delay 3
		end if

		-- Test 1: send message
		try
			tell application appName
				set response to send message "Hello, this is an AppleScript test"
			end tell
			if response is not "" and response is not missing value then
				set end of results to "  send message:       PASS — got response (" & (count of response) & " chars)"
				set passCount to passCount + 1
			else
				set end of results to "  send message:       FAIL — empty response"
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  send message:       FAIL — " & errMsg
			set failCount to failCount + 1
		end try

		-- Test 2: get conversation
		try
			tell application appName
				set convo to get conversation
			end tell
			if convo contains "AppleScript test" then
				set end of results to "  get conversation:   PASS — history contains test message"
				set passCount to passCount + 1
			else
				set end of results to "  get conversation:   FAIL — test message not in history"
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  get conversation:   FAIL — " & errMsg
			set failCount to failCount + 1
		end try

		-- Test 3: speak
		try
			tell application appName
				speak "AppleScript test speech"
			end tell
			set end of results to "  speak:              PASS — no error"
			set passCount to passCount + 1
		on error errMsg
			set end of results to "  speak:              FAIL — " & errMsg
			set failCount to failCount + 1
		end try

		-- Test 4: set provider
		try
			tell application appName
				set provider "ollama"
			end tell
			set end of results to "  set provider:       PASS — switched to ollama"
			set passCount to passCount + 1
		on error errMsg
			set end of results to "  set provider:       FAIL — " & errMsg
			set failCount to failCount + 1
		end try

		-- Test 5: start listening / stop listening
		try
			tell application appName
				start listening
				delay 1
				stop listening
			end tell
			set end of results to "  start/stop listen:  PASS — no error"
			set passCount to passCount + 1
		on error errMsg
			set end of results to "  start/stop listen:  FAIL — " & errMsg
			set failCount to failCount + 1
		end try

		-- Format results
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
