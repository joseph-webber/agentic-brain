-- BrainChat AppleScript Library
-- Save this as ~/Library/Script Libraries/BrainChat.scpt
-- Then use: use BrainChat : script "BrainChat"

-- ============================================================
-- CORE FUNCTIONS
-- ============================================================

on getMode()
    tell application "Brain Chat"
        return get mode
    end tell
end getMode

on setMode(modeName)
    -- Valid modes: chat, code, terminal, yolo, voice, work
    tell application "Brain Chat"
        set mode modeName
    end tell
    return "Switched to " & modeName & " mode"
end setMode

on listModes()
    tell application "Brain Chat"
        return list modes
    end tell
end listModes

on speak(theText)
    tell application "Brain Chat"
        speak theText
    end tell
end speak

on getStatus()
    tell application "Brain Chat"
        return get status
    end tell
end getStatus

-- ============================================================
-- LLM FUNCTIONS
-- ============================================================

on getLLM()
    tell application "Brain Chat"
        return get llm
    end tell
end getLLM

on setLLM(modelName)
    tell application "Brain Chat"
        set llm modelName
    end tell
    return "LLM set to " & modelName
end setLLM

on sendMessage(theMessage)
    -- Send via CLI for reliability
    return do shell script "~/bin/brainchat-cli send " & quoted form of theMessage
end sendMessage

-- ============================================================
-- WINDOW FUNCTIONS
-- ============================================================

on showWindow()
    tell application "Brain Chat"
        show window
    end tell
end showWindow

on hideWindow()
    tell application "Brain Chat"
        hide window
    end tell
end hideWindow

-- ============================================================
-- VOICE FUNCTIONS
-- ============================================================

on startListening()
    tell application "Brain Chat"
        start listening
    end tell
end startListening

on stopListening()
    tell application "Brain Chat"
        return stop listening
    end tell
end stopListening

-- ============================================================
-- ACCESSIBILITY FUNCTIONS
-- ============================================================

on announce(theText)
    tell application "Brain Chat"
        announce theText priority "normal"
    end tell
end announce

on announceUrgent(theText)
    tell application "Brain Chat"
        announce theText priority "high"
    end tell
end announceUrgent

on describeUI()
    tell application "Brain Chat"
        return describe ui
    end tell
end describeUI

-- ============================================================
-- UTILITY FUNCTIONS (CLI-based for reliability)
-- ============================================================

on healthCheck()
    return do shell script "~/bin/brainchat-cli health"
end healthCheck

on isRunning()
    try
        do shell script "pgrep -x BrainChat"
        return true
    on error
        return false
    end try
end isRunning

on startApp()
    if not isRunning() then
        tell application "Brain Chat" to activate
        delay 2
    end if
    return "Brain Chat is running"
end startApp

on quitApp()
    tell application "Brain Chat" to quit
    return "Brain Chat quit"
end quitApp

-- ============================================================
-- QUICK ACTIONS
-- ============================================================

on chatWith(theMessage)
    my setMode("chat")
    return my sendMessage(theMessage)
end chatWith

on codeHelp(theQuestion)
    my setMode("code")
    return my sendMessage(theQuestion)
end codeHelp

on askTerminal(theQuestion)
    my setMode("terminal")
    return my sendMessage(theQuestion)
end askTerminal

on workMode()
    my setMode("work")
    my speak("Switched to work mode. Ready for CITB tasks.")
end workMode

on voiceMode()
    my setMode("voice")
    my speak("Voice mode active. Responses will be spoken aloud.")
end voiceMode
