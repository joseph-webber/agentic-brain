# BrainChat Accessibility - Quick Reference for VoiceOver Users

**For user:** All keyboard shortcuts work with VoiceOver. You don't need to see the screen anymore!

## ⚡ Quick Navigation (Master These First)

### Jump Between Sections
| Action | Keyboard | What Happens |
|--------|----------|--------------|
| Jump to Chat | **Cmd+1** | Goes directly to conversation area |
| Jump to Input | **Cmd+2** | Goes directly to message field (ready to type) |
| Jump to Controls | **Cmd+3** | Goes directly to mic/stop/settings buttons |

**Tip:** These are the fastest way to navigate. Use them constantly!

---

## 🎤 Microphone Control (Most Used)

| Action | Keyboard | VoiceOver Announces |
|--------|----------|-------------------|
| Toggle Mic | **Cmd+M** or **Cmd+L** | "Microphone now live" or "Microphone now muted" |
| Stop Speaking | **Cmd+.** (period) | "Stopped speaking" or "Idle" |

---

## ✉️ Message Operations

| Action | Keyboard | What Happens |
|--------|----------|--------------|
| Send Message | **Return** | Sends from input field |
| Send Instantly | **Cmd+Return** | Sends immediately |
| Clear Input | **Escape** | Empties current message (doesn't send) |
| Previous Message | **Cmd+↑** (Up Arrow) | Shows your last message |
| Next Message | **Cmd+↓** (Down Arrow) | Shows newer message |

---

## ⚙️ Application Control

| Action | Keyboard | What Happens |
|--------|----------|--------------|
| New Conversation | **Cmd+N** | Clears all messages, starts fresh |
| Clear All Messages | **Cmd+K** | Asks for confirmation, then clears |
| Open Settings | **Cmd+,** (comma) | Opens settings window |
| Show Help | **Cmd+?** or **Cmd+/** | Shows all keyboard shortcuts |

---

## 🔊 Real-Time Announcements (What You'll Hear)

When you do something, VoiceOver will announce:

| What You Do | VoiceOver Announces |
|-------------|-------------------|
| Send a message | "Message sent" |
| AI responds | "New Brain Chat response" |
| AI is thinking | "Brain Chat is thinking" → "Response ready" |
| Toggle microphone | "Microphone now live" or "Microphone now muted" |
| Stop audio | "Stopped speaking" or "Idle" |
| Clear conversation | "Conversation cleared" |

**Important:** Wait for the announcement before assuming the action worked.

---

## 🎯 Label Shortcuts (What VoiceOver Shows)

### Status Area
- **"Mic live"** - Microphone is on, listening
- **"Mic muted"** - Microphone is off
- **"Session: Active"** - Copilot connected
- **"Input level: Moderate"** - Audio input volume

### Controls
- **"Stop"** - Stop button (stops audio output)
- **"Settings"** - Settings button
- **"Clear"** - Clear button (delete all messages)

### Messages
- **"Your message"** - Something you typed
- **"Brain Chat response"** - Answer from AI
- **"System message"** - Notification from app

---

## 📍 Focus Positions (Where Am I?)

When you press **Cmd+1**, **Cmd+2**, or **Cmd+3**, VoiceOver will announce where you are:

- **Cmd+1**: "Conversation history" - You're reading past messages
- **Cmd+2**: "Message input area" - You can type now
- **Cmd+3**: "Control buttons" - You can access mic/stop/settings

**Your Current Focus:**
- If VoiceOver says "Mic live" → You're in controls
- If VoiceOver says "Message input" → You're ready to type
- If VoiceOver says "Brain Chat response" → You're in chat

---

## 🎹 Tab vs. Keyboard Shortcuts

**Keyboard Shortcuts (FAST):**
```
Cmd+1 → Conversation
Cmd+2 → Message Input
Cmd+3 → Controls
```

**Tab Through Everything (SLOW, but works):**
```
Tab → Next control
Shift+Tab → Previous control
(Keep tabbing through everything until you find what you want)
```

**Recommendation:** Use Cmd+1/2/3 for quick navigation, Tab for small adjustments.

---

## 🎤 A Complete Workflow

**Scenario: Chat with Brain Chat and wait for response**

```
1. Cmd+2                    # Focus message input
2. Type "Tell me a joke"    # Type your message
3. Return                   # Send message
   → VoiceOver: "Message sent"

4. Wait...                  # Brain Chat is thinking
   → VoiceOver: "Response ready"
   
5. VoiceOver: "New Brain Chat response: Why did the ..."
   (VoiceOver reads the response aloud)

6. Cmd+1                    # Jump to conversation
7. Ctrl+Option+↓ (arrow)    # Read previous messages
   → Each message is read by VoiceOver
```

---

## 🎤 Microphone Workflow

**Scenario: Use microphone to speak, get audio response**

```
1. Cmd+3                           # Focus controls
   → VoiceOver: "Control buttons"

2. Down Arrow (once)               # Move to Mic button
   → VoiceOver: "Mic muted"

3. Return or Space                 # Press the button
   → VoiceOver: "Microphone now live"

4. Speak your question             # Brain Chat hears you

5. Wait...                         # AI is thinking
   → VoiceOver: "Response ready"

6. Brain Chat speaks the answer    # Audio output

7. Cmd+.                           # Stop audio if needed
   → VoiceOver: "Idle"
```

---

## 🔍 Using the VoiceOver Rotor (Optional - For Power Users)

**What is the Rotor?**
A special menu that lets you jump to specific sections or elements.

**How to Open:**
```
Ctrl+Option+U  (on macOS)
or
VO+U           (if you have VO key configured)
```

**What You'll See:**
- Status section
- Controls
- Conversation
- Input area

**How to Use:**
1. Press Ctrl+Option+U (opens rotor)
2. Use arrow keys to select the section
3. Press Return to jump there
4. Press Escape to close rotor

**But honestly:** Cmd+1/2/3 is faster. Only use rotor if you want to explore.

---

## ⏰ Response Times

**How long does Brain Chat take?**
- Processing starts immediately → VoiceOver: "Brain Chat is thinking"
- Processing takes a few seconds...
- Response ready → VoiceOver: "Response ready"
- Then VoiceOver reads the response aloud

**Don't assume it failed:** Wait for the "Response ready" announcement.

---

## 🆘 If Something Goes Wrong

| Problem | Fix |
|---------|-----|
| Can't hear anything | Check if audio is muted (Cmd+. should unmute) |
| Mic not working | Press Cmd+M to toggle, should announce status |
| Lost focus | Press Cmd+2 to jump back to input |
| App froze | Check if still thinking (wait for "Response ready") |
| VoiceOver not announcing | Open System Prefs → Accessibility → VoiceOver → Check enabled |

---

## 📝 Full Keyboard Shortcut Reference

```
NAVIGATION
  Cmd+1       → Jump to conversation
  Cmd+2       → Jump to message input
  Cmd+3       → Jump to controls

MICROPHONE
  Cmd+M       → Toggle microphone on/off
  Cmd+L       → Toggle microphone on/off (alternative)
  Cmd+.       → Stop audio output

MESSAGES
  Return      → Send message
  Cmd+Return  → Send message (instant)
  Escape      → Clear current message
  Cmd+↑       → Previous message from history
  Cmd+↓       → Next message from history

APPLICATION
  Cmd+N       → New conversation
  Cmd+K       → Clear all messages (with confirmation)
  Cmd+,       → Open settings
  Cmd+/       → Show keyboard help
  Cmd+?       → Show keyboard help (alternative)

VOICEOVER ROTOR (Advanced)
  Ctrl+Option+U → Open rotor to jump to sections
```

---

## 💡 Pro Tips

1. **Always wait for announcements.** Don't assume it failed if you don't hear something immediately.

2. **Use Cmd+1/2/3 constantly.** These keyboard shortcuts are your friends. They make navigation SO much faster.

3. **Trust the keyboard.** Every feature is keyboard accessible. You never need the mouse.

4. **Let VoiceOver finish speaking.** Don't interrupt it. Let it announce the full state change.

5. **Read the message before sending.** Use Return to send, Cmd+Return for instant send if you know what you typed.

6. **Check your settings.** Open Cmd+, to configure speed, voice, and response mode.

---

## 🎉 You're All Set!

Brain Chat is now **fully accessible** for VoiceOver users. Every feature is:
- ✅ Keyboard accessible
- ✅ Announced in real-time
- ✅ Fast to navigate
- ✅ Easy to understand

Start with the Quick Navigation shortcuts (Cmd+1/2/3) and microphone control (Cmd+M). Once you master those, try the other shortcuts as needed.

**Have fun chatting! 🎧**

---

## Questions or Issues?

If you find something not working:
1. Check the full documentation: `WCAG_AAA_COMPLIANCE.md`
2. Run the testing checklist: `ACCESSIBILITY_TESTING_CHECKLIST.md`
3. Review implementation: `ACCESSIBILITY_IMPLEMENTATION_GUIDE.md`

All files are in the BrainChat folder.
