#!/usr/bin/env python3
"""Voice Chat - Press Fn Fn to dictate, Enter to send"""
import subprocess
import sys
import urllib.request
import json

def speak(text, rate=160):
    subprocess.run(['say', '-v', 'Karen (Premium)', '-r', str(rate), text], 
                   stderr=subprocess.DEVNULL)

def ask_ollama(prompt):
    """Fast local response"""
    try:
        data = json.dumps({
            "model": "llama3.2:3b",
            "prompt": f"You are Karen, a helpful Australian assistant. Be concise. User: {prompt}",
            "stream": False
        }).encode()
        req = urllib.request.Request("http://localhost:11434/api/generate", data=data)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["response"]
    except Exception as e:
        return f"Ollama error: {e}"

if __name__ == "__main__":
    speak("G'day Joseph! I'm Karen. Press F N twice to dictate, then Enter to send. Or just type.", 155)

    while True:
        try:
            user = input("\n🎤 > ").strip()
            if not user:
                speak("I didn't catch that. Try again?")
                continue
            if user.lower() in ['quit', 'exit', 'bye', 'q']:
                speak("See ya later!")
                break
            
            speak("Thinking...")
            response = ask_ollama(user)
            
            # Clean and speak
            response = response.replace('\n', ' ').strip()
            if len(response) > 400:
                response = response[:400] + "..."
            
            print(f"💬 {response}")
            speak(response)
            
        except (KeyboardInterrupt, EOFError):
            speak("Bye!")
            break
