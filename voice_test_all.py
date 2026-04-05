#!/usr/bin/env python3
"""
Voice-to-Text Test Suite
Tests: Google (free), Whisper Local, Groq API, Offline (Vosk)

Usage:
  python voice_test_all.py google    # Free, online
  python voice_test_all.py whisper   # Local M2, offline capable
  python voice_test_all.py groq      # Free API, fastest
  python voice_test_all.py offline   # Fully offline (Vosk)
  python voice_test_all.py all       # Test all backends
"""
import speech_recognition as sr
import subprocess
import sys
import os
import time
import tempfile
import wave

def speak(text, voice="Karen (Premium)", rate=165):
    subprocess.run(["say", "-v", voice, "-r", str(rate), text], check=False)

def find_airpods():
    """Find AirPods device index"""
    for i, name in enumerate(sr.Microphone.list_microphone_names()):
        if 'airpod' in name.lower():
            return i, name
    return None, "Default Microphone"

def record_audio(duration=5):
    """Record audio and return the audio data"""
    airpods_idx, mic_name = find_airpods()
    print(f"🎧 Using: {mic_name}")
    
    r = sr.Recognizer()
    mic = sr.Microphone(device_index=airpods_idx)
    
    with mic as source:
        r.adjust_for_ambient_noise(source, duration=0.3)
        print(f"👂 Listening for {duration} seconds...")
        speak("Speak now!", rate=180)
        audio = r.listen(source, timeout=10, phrase_time_limit=duration)
        print("✅ Got audio!")
        return audio, r

def test_google(audio, recognizer):
    """Test Google Speech Recognition (FREE, online)"""
    print("\n🔵 Testing GOOGLE Speech Recognition...")
    start = time.time()
    try:
        text = recognizer.recognize_google(audio)
        latency = time.time() - start
        print(f"✅ Google result ({latency:.2f}s): {text}")
        return text, latency
    except sr.UnknownValueError:
        print("❌ Google couldn't understand")
        return None, 0
    except sr.RequestError as e:
        print(f"❌ Google API error: {e}")
        return None, 0

def test_whisper_local(audio, recognizer):
    """Test local Whisper (FREE, offline capable)"""
    print("\n🟢 Testing LOCAL WHISPER (M2 accelerated)...")
    try:
        from faster_whisper import WhisperModel
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_data = audio.get_wav_data()
            f.write(wav_data)
            temp_path = f.name
        
        start = time.time()
        # Use tiny model for speed, or base for accuracy
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(temp_path)
        text = " ".join([seg.text for seg in segments]).strip()
        latency = time.time() - start
        
        os.unlink(temp_path)
        print(f"✅ Whisper result ({latency:.2f}s): {text}")
        return text, latency
    except Exception as e:
        print(f"❌ Whisper error: {e}")
        return None, 0

def test_groq(audio, recognizer):
    """Test Groq Whisper API (FREE tier, FASTEST)"""
    print("\n🟣 Testing GROQ Whisper API (free + fast)...")
    
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        # Check common locations
        for path in ["~/.groq", "~/.config/groq/api_key", "/Users/joe/brain/.env"]:
            expanded = os.path.expanduser(path)
            if os.path.exists(expanded):
                with open(expanded) as f:
                    content = f.read()
                    if "GROQ_API_KEY" in content:
                        for line in content.split('\n'):
                            if line.startswith("GROQ_API_KEY"):
                                api_key = line.split('=')[1].strip().strip('"\'')
                                break
    
    if not api_key:
        print("⚠️ No GROQ_API_KEY found. Get free key at: https://console.groq.com")
        print("   Then: export GROQ_API_KEY=your_key")
        return None, 0
    
    try:
        from groq import Groq
        import tempfile
        
        # Save audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_data = audio.get_wav_data()
            f.write(wav_data)
            temp_path = f.name
        
        start = time.time()
        client = Groq(api_key=api_key)
        
        with open(temp_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                file=(temp_path, audio_file.read()),
                model="whisper-large-v3",
                response_format="text"
            )
        
        latency = time.time() - start
        text = transcription.strip()
        os.unlink(temp_path)
        
        print(f"✅ Groq result ({latency:.2f}s): {text}")
        return text, latency
    except Exception as e:
        print(f"❌ Groq error: {e}")
        return None, 0

def test_offline(audio, recognizer):
    """Test fully offline recognition (Vosk or Sphinx)"""
    print("\n🟠 Testing OFFLINE recognition...")
    
    # Try Vosk first (better quality)
    try:
        # Use sphinx as fallback (comes with SpeechRecognition)
        start = time.time()
        text = recognizer.recognize_sphinx(audio)
        latency = time.time() - start
        print(f"✅ Sphinx offline result ({latency:.2f}s): {text}")
        return text, latency
    except sr.UnknownValueError:
        print("❌ Sphinx couldn't understand")
        return None, 0
    except Exception as e:
        print(f"⚠️ Sphinx not available: {e}")
        print("   Install: pip install pocketsphinx")
        return None, 0

def main():
    backend = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    print("=" * 60)
    print("🎤 VOICE TEST SUITE")
    print("=" * 60)
    
    # Record once, test all
    audio, recognizer = record_audio(duration=5)
    
    results = {}
    
    if backend in ["google", "all"]:
        text, latency = test_google(audio, recognizer)
        results["google"] = {"text": text, "latency": latency}
    
    if backend in ["whisper", "all"]:
        text, latency = test_whisper_local(audio, recognizer)
        results["whisper"] = {"text": text, "latency": latency}
    
    if backend in ["groq", "all"]:
        text, latency = test_groq(audio, recognizer)
        results["groq"] = {"text": text, "latency": latency}
    
    if backend in ["offline", "all"]:
        text, latency = test_offline(audio, recognizer)
        results["offline"] = {"text": text, "latency": latency}
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 RESULTS SUMMARY")
    print("=" * 60)
    for name, data in results.items():
        if data["text"]:
            print(f"  {name:10} : {data['latency']:.2f}s - \"{data['text'][:50]}...\"" if len(data.get('text','')) > 50 else f"  {name:10} : {data['latency']:.2f}s - \"{data['text']}\"")
        else:
            print(f"  {name:10} : FAILED")
    
    # Announce winner
    working = {k: v for k, v in results.items() if v["text"]}
    if working:
        fastest = min(working.items(), key=lambda x: x[1]["latency"])
        speak(f"Testing complete! {fastest[0]} was fastest at {fastest[1]['latency']:.1f} seconds", rate=170)

if __name__ == "__main__":
    main()
