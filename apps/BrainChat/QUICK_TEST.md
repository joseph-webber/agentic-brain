# 🎙️ QUICK TEST - MIC PERMISSION FIX

## ⚡ FASTEST TEST (30 seconds)

```bash
cd ~/brain/agentic-brain/apps/BrainChat
./apply_fix.sh                           # Rebuild
open /Applications/Brain\ Chat.app       # Launch
# Click mic button → Dialog appears → Allow → Mic goes live!
```

## 📋 WHAT YOU SHOULD SEE

1. **App launches** → Karen says "G'day Joseph"
2. **Click mic button** → System permission dialog appears immediately
3. **Click Allow** → Mic turns GREEN, says "Live"
4. **Speak** → Words appear in chat as you speak
5. **Click mic again** → Turns RED, says "Muted"

## ❌ IF IT DOESN'T WORK

```bash
# Full reset + rebuild
tccutil reset Microphone com.josephwebber.brainchat
rm -rf /Applications/Brain\ Chat.app
cd ~/brain/agentic-brain/apps/BrainChat
./build.sh --clean --install --run
```

## 🐛 DEBUG

```bash
# Check logs
tail -f ~/brain/agentic-brain/apps/BrainChat/runtime/mic-debug.log

# Check if app is registered
tccutil reset Microphone com.josephwebber.brainchat
# If it says "No services" → App not in TCC database (bad!)
# If it succeeds → App IS registered (good!)
```

## ✅ SUCCESS = MIC BUTTON WORKS FIRST TIME!

**Files Changed:**
- `SpeechManager.swift` - Added completion-based permission request
- `ContentView.swift` - Fixed button to wait for permission before starting

**The Fix:**
Request permission → Wait for user → Then start mic
(Instead of: Request async → Check sync → Fail silently)
