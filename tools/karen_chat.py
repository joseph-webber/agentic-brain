#!/usr/bin/env python3
"""Karen Voice Chat - Simple and Direct"""
import subprocess
import sys
import os


def speak(text, rate=160):
    """Karen speaks"""
    subprocess.run(["say", "-v", "Karen (Premium)", "-r", str(rate), text])


def ask_copilot(prompt):
    """Ask Copilot CLI directly"""
    try:
        result = subprocess.run(
            ["/usr/local/bin/copilot", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except:
        return None


def ask_ollama(prompt):
    """Fallback to Ollama"""
    import urllib.request
    import json

    try:
        data = json.dumps(
            {"model": "llama3.2:3b", "prompt": prompt, "stream": False}
        ).encode()
        req = urllib.request.Request("http://localhost:11434/api/generate", data=data)
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())["response"]
    except:
        return None


def chat(user_input):
    """Process user input and respond"""
    speak("Let me think about that")

    # Try Copilot first, fallback to Ollama
    response = ask_copilot(user_input)
    if not response:
        response = ask_ollama(user_input)
    if not response:
        response = "Sorry, I couldn't get a response. Try again."

    # Speak the response (truncate if too long)
    if len(response) > 500:
        response = response[:500] + "... and more."
    speak(response)
    return response


if __name__ == "__main__":
    speak(
        "Karen here. Ready to chat. Type your message or say dictate to use voice.", 155
    )

    while True:
        try:
            user = input("\n🎤 You: ").strip()
            if not user:
                continue
            if user.lower() in ["quit", "exit", "bye"]:
                speak("Goodbye!")
                break
            print(f"🧠 Processing...")
            response = chat(user)
            print(
                f"💬 Karen: {response[:200]}..."
                if len(response) > 200
                else f"💬 Karen: {response}"
            )
        except KeyboardInterrupt:
            speak("Bye!")
            break
        except EOFError:
            break
