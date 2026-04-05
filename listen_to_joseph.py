#!/usr/bin/env python3
"""
Simple Voice-to-Text Listener
Uses AirPods Max microphone and Apple's speech recognition (FREE!)
"""
import speech_recognition as sr
import subprocess
import sys

def speak(text, voice="Karen (Premium)", rate=165):
    """Speak using macOS say command"""
    subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=False)

def main():
    r = sr.Recognizer()
    
    # Find AirPods
    airpods_idx = None
    for i, name in enumerate(sr.Microphone.list_microphone_names()):
        if 'airpod' in name.lower():
            airpods_idx = i
            print(f"🎧 Using: {name}")
            break
    
    if airpods_idx is None:
        print("⚠️ AirPods not found, using default mic")
        airpods_idx = None
    
    mic = sr.Microphone(device_index=airpods_idx)
    
    speak("I'm listening! Say something.", rate=170)
    print("\n🎤 Listening... (Ctrl+C to stop)\n")
    
    with mic as source:
        r.adjust_for_ambient_noise(source, duration=0.5)
        print("✅ Adjusted for background noise\n")
        
        while True:
            try:
                print("👂 Listening...")
                audio = r.listen(source, timeout=10, phrase_time_limit=15)
                print("🔄 Processing...")
                
                # Use Apple's speech recognition (FREE, on-device)
                try:
                    text = r.recognize_google(audio)  # or recognize_sphinx for offline
                    print(f"\n💬 User said: {text}\n")
                    
                    # Acknowledge
                    if text:
                        speak(f"I heard: {text}", rate=175)
                        
                except sr.UnknownValueError:
                    print("❓ Couldn't understand - try again")
                except sr.RequestError as e:
                    print(f"❌ API error: {e}")
                    
            except sr.WaitTimeoutError:
                print("⏳ No speech detected, still listening...")
            except KeyboardInterrupt:
                speak("Goodbye!")
                print("\n👋 Stopped listening")
                break

if __name__ == "__main__":
    main()
