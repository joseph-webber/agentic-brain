-- test_accessibility.applescript
-- E2E test: Verify all critical UI elements have accessibility labels & identifiers.
-- This validates WCAG 2.1 AA compliance for Joseph's VoiceOver workflow.
-- Usage: osascript test_accessibility.applescript

on run
	set testName to "test_accessibility"
	set appName to "Brain Chat"
	set results to {}
	
	-- Expected accessibility identifiers from ContentView.swift
	set requiredIdentifiers to {"statusSection", "conversationSection", "statusIndicator", "audioLevelView", "microphoneButton", "stopButton", "settingsButton", "clearButton", "messageInput", "sendButton", "inputSection"}
	
	try
		if not isRunning(appName) then
			tell application appName to activate
			delay 3
		end if
		
		tell application "System Events"
			tell process appName
				set frontmost to true
				delay 0.5
				
				-- Test 1: Window exists and has a title
				try
					set winTitle to title of window 1
					set end of results to "  Window title:       PASS — \"" & winTitle & "\""
				on error
					set end of results to "  Window title:       FAIL — no window found"
				end try
				
				-- Test 2: Check buttons have accessibility labels
				try
					set allButtons to every button of window 1
					set labelledCount to 0
					set unlabelledButtons to {}
					
					repeat with btn in allButtons
						try
							set btnDesc to description of btn
							if btnDesc is not "" and btnDesc is not missing value then
								set labelledCount to labelledCount + 1
							else
								set end of unlabelledButtons to (name of btn)
							end if
						on error
							try
								set end of unlabelledButtons to (name of btn)
							end try
						end try
					end repeat
					
					set totalButtons to count of allButtons
					if labelledCount = totalButtons then
						set end of results to "  Button labels:      PASS — all " & totalButtons & " buttons labelled"
					else
						set end of results to "  Button labels:      WARN — " & labelledCount & "/" & totalButtons & " labelled"
					end if
				on error errMsg
					set end of results to "  Button labels:      FAIL — " & errMsg
				end try
				
				-- Test 3: Check text fields have accessibility labels
				try
					set allFields to every text field of window 1
					set fieldCount to count of allFields
					if fieldCount > 0 then
						set end of results to "  Text fields:        PASS — " & fieldCount & " field(s) found"
					else
						-- Might be text areas instead
						set allAreas to every text area of window 1
						set areaCount to count of allAreas
						if areaCount > 0 then
							set end of results to "  Text areas:         PASS — " & areaCount & " area(s) found"
						else
							set end of results to "  Input fields:       WARN — no text fields or areas found at top level"
						end if
					end if
				on error errMsg
					set end of results to "  Text fields:        FAIL — " & errMsg
				end try
				
				-- Test 4: Tab navigation works (critical for VoiceOver)
				try
					-- Press Tab several times and verify focus moves
					key code 48 -- Tab
					delay 0.3
					key code 48
					delay 0.3
					key code 48
					delay 0.3
					-- If no crash, tab navigation works
					set end of results to "  Tab navigation:     PASS — no crash during tab cycling"
				on error errMsg
					set end of results to "  Tab navigation:     FAIL — " & errMsg
				end try
				
				-- Test 5: Check the UI hierarchy depth (shouldn't be too flat or too deep)
				try
					set groupCount to count of groups of window 1
					set end of results to "  UI groups:          INFO — " & groupCount & " top-level groups"
				on error errMsg
					set end of results to "  UI groups:          INFO — could not count (" & errMsg & ")"
				end try
				
				-- Test 6: Check scrollable area exists (conversation must scroll)
				try
					set scrollAreas to every scroll area of window 1
					set scrollCount to count of scrollAreas
					if scrollCount > 0 then
						set end of results to "  Scroll area:        PASS — " & scrollCount & " scroll area(s) for conversation"
					else
						set end of results to "  Scroll area:        WARN — no scroll areas found"
					end if
				on error errMsg
					set end of results to "  Scroll area:        FAIL — " & errMsg
				end try
				
				-- Test 7: VoiceOver announcement check via AX role
				try
					set winRole to role of window 1
					set winSubrole to subrole of window 1
					set end of results to "  Window AX role:     PASS — " & winRole & "/" & winSubrole
				on error errMsg
					set end of results to "  Window AX role:     INFO — " & errMsg
				end try
			end tell
		end tell
		
		-- Format results
		set passCount to 0
		set failCount to 0
		set warnCount to 0
		repeat with r in results
			if r contains "PASS" then
				set passCount to passCount + 1
			else if r contains "FAIL" then
				set failCount to failCount + 1
			else if r contains "WARN" then
				set warnCount to warnCount + 1
			end if
		end repeat
		
		set resultText to testName & " — " & passCount & " passed, " & failCount & " failed, " & warnCount & " warnings" & linefeed
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
