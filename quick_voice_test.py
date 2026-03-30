#!/usr/bin/env python3
"""Quick voice test - uses AirPods Max directly"""
import speech_recognition as sr
import subprocess
import time

def speak(text):
    subprocess.run(["say", "-v", "Karen (Premium)", "-r", "170", text])

# Use AirPods Max (index 0)
AIRPODS_INDEX = 0

r = sr.Recognizer()
r.energy_threshold = 300  # Lower threshold for sensitivity
r.dynamic_energy_threshold = False

print("🎧 Using Joseph's AirPods Max")
print("🎤 Speak now! (10 second window)")
speak("Speak now Joseph!")

mic = sr.Microphone(device_index=AIRPODS_INDEX)

with mic as source:
    print("📢 Adjusting for noise...")
    r.adjust_for_ambient_noise(source, duration=0.5)
    print("👂 Listening... speak clearly!")
    
    try:
        audio = r.listen(source, timeout=15, phrase_time_limit=10)
        print("✅ Got audio! Processing...")
        
        # Test Google
        print("\n🔵 GOOGLE:")
        start = time.time()
        try:
            text = r.recognize_google(audio)
            print(f"   Result ({time.time()-start:.2f}s): {text}")
            speak(f"Google heard: {text}")
        except Exception as e:
            print(f"   Error: {e}")
        
        # Test Whisper Local
        print("\n🟢 WHISPER LOCAL:")
        try:
            from faster_whisper import WhisperModel
            import tempfile, os
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(audio.get_wav_data())
                temp_path = f.name
            
            start = time.time()
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(temp_path)
            text = " ".join([s.text for s in segments]).strip()
            print(f"   Result ({time.time()-start:.2f}s): {text}")
            speak(f"Whisper heard: {text}")
            os.unlink(temp_path)
        except Exception as e:
            print(f"   Error: {e}")
            
    except sr.WaitTimeoutError:
        print("❌ No speech detected - make sure AirPods mic is active!")
        speak("I didn't hear anything. Check your AirPods are connected as input device.")

print("\n✅ Test complete!")
