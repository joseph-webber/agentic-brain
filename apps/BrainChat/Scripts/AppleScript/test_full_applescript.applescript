-- test_full_applescript.applescript
-- COMPREHENSIVE E2E test: Exercises ALL native AppleScript commands exposed via BrainChat.sdef
-- Tests both new and existing commands for automated testing and voice integration
-- Usage: osascript test_full_applescript.applescript

on run
	set testName to "test_full_applescript_comprehensive"
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
		
		-- Test 1: Get selected LLM (new command)
		try
			tell application appName
				set currentLLM to get selected llm
			end tell
			if currentLLM is not "" and currentLLM is not missing value then
				set end of results to "  get selected llm:   PASS — currently using " & currentLLM
				set passCount to passCount + 1
			else
				set end of results to "  get selected llm:   FAIL — empty result"
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  get selected llm:   FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 2: Set selected LLM to ollama (new command)
		try
			tell application appName
				set selected llm to "ollama"
			end tell
			set end of results to "  set selected llm:   PASS — switched to ollama"
			set passCount to passCount + 1
		on error errMsg
			set end of results to "  set selected llm:   FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 3: Get Copilot status (new command)
		try
			tell application appName
				set copilotStatus to get copilot status
			end tell
			if copilotStatus is not "" and copilotStatus is not missing value then
				set end of results to "  get copilot status:  PASS — " & (count of copilotStatus) & " chars"
				set passCount to passCount + 1
			else
				set end of results to "  get copilot status:  FAIL — empty response"
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  get copilot status:  FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 4: Get mic status (new command - using native terminology)
		try
			tell application appName
				set micStatus to get mic status
			end tell
			if micStatus = "muted" or micStatus = "live" then
				set end of results to "  get mic status:      PASS — " & micStatus
				set passCount to passCount + 1
			else
				set end of results to "  get mic status:      FAIL — invalid status: " & micStatus
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  get mic status:      FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 5: Toggle mic (new command)
		try
			tell application appName
				set newStatus to toggle mic
			end tell
			if newStatus = "muted" or newStatus = "live" then
				set end of results to "  toggle mic:          PASS — toggled to " & newStatus
				set passCount to passCount + 1
			else
				set end of results to "  toggle mic:          FAIL — invalid response: " & newStatus
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  toggle mic:          FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 6: Get whisper engine (new command)
		try
			tell application appName
				set whisperEngine to get whisper engine
			end tell
			if whisperEngine is not "" and whisperEngine is not missing value then
				set end of results to "  get whisper engine:  PASS — currently " & whisperEngine
				set passCount to passCount + 1
			else
				set end of results to "  get whisper engine:  FAIL — empty result"
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  get whisper engine:  FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 7: Set whisper engine (new command)
		try
			tell application appName
				set whisper engine to "whisperKit"
			end tell
			set end of results to "  set whisper engine:  PASS — set to whisperKit"
			set passCount to passCount + 1
		on error errMsg
			set end of results to "  set whisper engine:  FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 8: Send message (existing command)
		try
			tell application appName
				set response to send message "Hello from comprehensive AppleScript test"
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
		
		-- Test 9: Get last response (new command)
		try
			tell application appName
				set lastResp to get last response
			end tell
			if lastResp is not "" and lastResp is not missing value then
				set end of results to "  get last response:   PASS — (" & (count of lastResp) & " chars)"
				set passCount to passCount + 1
			else
				set end of results to "  get last response:   FAIL — empty result"
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  get last response:   FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 10: Get conversation (existing command)
		try
			tell application appName
				set convo to get conversation
			end tell
			if convo contains "comprehensive AppleScript test" then
				set end of results to "  get conversation:   PASS — history OK"
				set passCount to passCount + 1
			else
				set end of results to "  get conversation:   FAIL — test message not in history"
				set failCount to failCount + 1
			end if
		on error errMsg
			set end of results to "  get conversation:   FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 11: Speak (existing command)
		try
			tell application appName
				speak "Comprehensive AppleScript test complete"
			end tell
			set end of results to "  speak:              PASS — no error"
			set passCount to passCount + 1
		on error errMsg
			set end of results to "  speak:              FAIL — " & errMsg
			set failCount to failCount + 1
		end try
		
		-- Test 12: Start/stop listening (existing commands)
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
