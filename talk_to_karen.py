#!/usr/bin/env python3
"""Simple real-time voice chat with Karen via faster-whisper, Ollama, and Cartesia."""

from __future__ import annotations

import argparse
import os
import queue
import sys
import time
from collections import deque
from pathlib import Path
from typing import Deque, List

import numpy as np
import requests
import sounddevice as sd
from cartesia import Cartesia
from faster_whisper import WhisperModel
from scipy.signal import resample_poly
from math import gcd

SCRIPT_DIR = Path(__file__).resolve().parent
LOCAL_ENV = SCRIPT_DIR / ".env.local"
CACHE_DIR = SCRIPT_DIR / ".cache"
WHISPER_CACHE = CACHE_DIR / "whisper"

DEFAULT_CARTESIA_VOICE_ID = "a4a16c5e-5902-4732-b9b6-2a48efd2e11b"  # Grace, Australian female
DEFAULT_TTS_MODEL = "sonic-3"
DEFAULT_OLLAMA_MODEL = "llama3.2:3b"
DEFAULT_WHISPER_MODEL = "tiny.en"
SAMPLE_RATE = 16000
TTS_SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
START_THRESHOLD = 0.015
END_THRESHOLD = 0.009
START_FRAMES = 2
MIN_SPEECH_SECONDS = 0.45
END_SILENCE_SECONDS = 0.9
MAX_UTTERANCE_SECONDS = 12.0
PREBUFFER_SECONDS = 0.35
EXIT_WORDS = {"stop", "goodbye", "exit", "quit", "bye karen", "thanks karen"}


def list_input_devices() -> None:
    """Print all available input devices."""
    print("\nAvailable input devices:")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            marker = " <-- default" if i == sd.default.device[0] else ""
            print(f"  [{i}] {d['name']}  (ch={d['max_input_channels']}, rate={int(d['default_samplerate'])}){marker}")
    print()


def find_input_device(name_hint: str | None = None) -> tuple[int | None, int]:
    """
    Find the best input device index and its native sample rate.

    Priority:
      1. Exact device index if name_hint is numeric
      2. Device whose name contains name_hint (case-insensitive)
      3. AirPods (any model) if name_hint is None
      4. System default input device

    Returns (device_index_or_None_for_default, native_sample_rate).
    None means "use sounddevice default".
    """
    devices = sd.query_devices()

    if name_hint is not None:
        # Numeric index passed directly
        if name_hint.isdigit():
            idx = int(name_hint)
            return idx, int(devices[idx]["default_samplerate"])
        # Name substring match
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0 and name_hint.lower() in d["name"].lower():
                print(f"[audio] Using input device [{i}]: {d['name']}  @ {int(d['default_samplerate'])} Hz")
                return i, int(d["default_samplerate"])
        print(f"[audio] WARNING: device '{name_hint}' not found, falling back to default.")

    # Auto-detect AirPods
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0 and "airpods" in d["name"].lower():
            print(f"[audio] Auto-detected AirPods input [{i}]: {d['name']}  @ {int(d['default_samplerate'])} Hz")
            return i, int(d["default_samplerate"])

    # Fall back to system default
    default_idx = sd.default.device[0]
    if default_idx is not None and default_idx >= 0:
        rate = int(devices[default_idx]["default_samplerate"])
        print(f"[audio] Using default input device [{default_idx}]: {devices[default_idx]['name']}  @ {rate} Hz")
        return None, rate

    return None, SAMPLE_RATE


def resample_to(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Resample mono float32 audio from src_rate to dst_rate using polyphase filter."""
    if src_rate == dst_rate:
        return audio
    g = gcd(src_rate, dst_rate)
    up, down = dst_rate // g, src_rate // g
    return resample_poly(audio, up, down).astype(np.float32)

SYSTEM_PROMPT = (
    "You are Karen, Joseph's Australian voice companion. "
    "Be warm, helpful, calm, and concise. "
    "Use natural Australian wording occasionally, but keep it subtle. "
    "Reply in 1 to 3 short sentences suitable for voice conversation."
)


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


class KarenVoiceChat:
    def __init__(self, whisper_model: str = DEFAULT_WHISPER_MODEL, input_device: str | None = None) -> None:
        load_local_env(LOCAL_ENV)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        WHISPER_CACHE.mkdir(parents=True, exist_ok=True)

        self.cartesia_api_key = os.getenv("CARTESIA_API_KEY")
        if not self.cartesia_api_key:
            raise RuntimeError(
                f"Missing CARTESIA_API_KEY. Add it to {LOCAL_ENV} or export it in your shell."
            )

        self.voice_id = os.getenv("CARTESIA_VOICE_ID", DEFAULT_CARTESIA_VOICE_ID)
        self.tts_model = os.getenv("CARTESIA_TTS_MODEL", DEFAULT_TTS_MODEL)
        self.ollama_model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.ollama_url = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

        # Resolve input device and its native sample rate
        self.input_device, self.capture_rate = find_input_device(input_device)

        self.cartesia = Cartesia(api_key=self.cartesia_api_key)
        self.whisper = WhisperModel(
            whisper_model,
            device="cpu",
            compute_type="int8",
            download_root=str(WHISPER_CACHE),
        )
        self.history: List[dict[str, str]] = []
        self.speaking = False

    def check_services(self) -> None:
        response = requests.get(f"{self.ollama_url}/api/tags", timeout=10)
        response.raise_for_status()

    def speak(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.speaking = True
        try:
            with self.cartesia.tts.websocket_connect() as conn:
                ctx = conn.context(
                    model_id=self.tts_model,
                    voice={"mode": "id", "id": self.voice_id},
                    output_format={
                        "container": "raw",
                        "encoding": "pcm_f32le",
                        "sample_rate": TTS_SAMPLE_RATE,
                    },
                    language="en",
                )
                ctx.push(text)
                ctx.no_more_inputs()
                with sd.RawOutputStream(
                    samplerate=TTS_SAMPLE_RATE,
                    channels=1,
                    dtype="float32",
                ) as stream:
                    for event in ctx.receive():
                        if getattr(event, "type", None) == "chunk" and getattr(event, "audio", None):
                            stream.write(event.audio)
        finally:
            self.speaking = False

    def transcribe(self, audio: np.ndarray) -> str:
        if audio.size == 0:
            return ""
        segments, _ = self.whisper.transcribe(
            audio.astype(np.float32),
            language="en",
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=True,
            without_timestamps=True,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def get_reply(self, user_text: str) -> str:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history[-8:])
        messages.append({"role": "user", "content": user_text})

        response = requests.post(
            f"{self.ollama_url}/api/chat",
            json={
                "model": self.ollama_model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 120,
                },
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        reply = payload.get("message", {}).get("content", "").strip()
        if not reply:
            reply = "Sorry love, I didn't get a proper reply from Ollama."

        self.history.extend(
            [
                {"role": "user", "content": user_text},
                {"role": "assistant", "content": reply},
            ]
        )
        self.history = self.history[-10:]
        return reply

    def listen_once(self) -> np.ndarray:
        audio_queue: queue.Queue[np.ndarray] = queue.Queue()
        prebuffer: Deque[np.ndarray] = deque(
            maxlen=max(1, int(PREBUFFER_SECONDS * SAMPLE_RATE / BLOCK_SIZE))
        )

        def callback(indata: np.ndarray, frames: int, time_info, status) -> None:
            if status:
                print(f"[audio] {status}", flush=True)
            audio_queue.put(indata[:, 0].copy())

        print("\n🎤 Listening... speak naturally.", flush=True)
        started = False
        start_hits = 0
        silence_seconds = 0.0
        collected: List[np.ndarray] = []
        speech_seconds = 0.0

        with sd.InputStream(
            samplerate=self.capture_rate,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            device=self.input_device,
            callback=callback,
        ):
            while True:
                chunk = audio_queue.get()
                if self.speaking:
                    continue

                rms = float(np.sqrt(np.mean(np.square(chunk)) + 1e-12))
                chunk_seconds = len(chunk) / SAMPLE_RATE

                if not started:
                    prebuffer.append(chunk)
                    if rms >= START_THRESHOLD:
                        start_hits += 1
                        if start_hits >= START_FRAMES:
                            started = True
                            collected.extend(list(prebuffer))
                            speech_seconds = sum(len(part) for part in collected) / SAMPLE_RATE
                            print("📝 Heard you, transcribing when you pause...", flush=True)
                    else:
                        start_hits = 0
                    continue

                collected.append(chunk)
                speech_seconds += chunk_seconds
                if rms < END_THRESHOLD:
                    silence_seconds += chunk_seconds
                else:
                    silence_seconds = 0.0

                if speech_seconds >= MAX_UTTERANCE_SECONDS:
                    break
                if speech_seconds >= MIN_SPEECH_SECONDS and silence_seconds >= END_SILENCE_SECONDS:
                    break

        if not collected:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(collected).astype(np.float32)
        trim_samples = int(max(0.0, silence_seconds - 0.15) * self.capture_rate)
        if trim_samples and trim_samples < audio.size:
            audio = audio[:-trim_samples]

        # Resample to 16 kHz if AirPods (or any device) runs at a different native rate
        return resample_to(audio, self.capture_rate, SAMPLE_RATE)

    def run(self) -> None:
        self.check_services()
        self.speak(
            "Hey Joseph, Karen here. I'm ready now. Just start talking, and say stop any time to finish."
        )
        print("✅ Karen is live. Say 'stop' to end.", flush=True)

        while True:
            audio = self.listen_once()
            transcript = self.transcribe(audio)
            if not transcript:
                print("… I didn't catch that. Try again.", flush=True)
                continue

            print(f"\nYou: {transcript}", flush=True)
            if transcript.lower().strip() in EXIT_WORDS:
                goodbye = "No worries, Joseph. I'll be here when you want another chat."
                print(f"Karen: {goodbye}", flush=True)
                self.speak(goodbye)
                break

            reply = self.get_reply(transcript)
            print(f"Karen: {reply}", flush=True)
            self.speak(reply)

    def demo(self, text: str) -> None:
        self.check_services()
        print(f"Demo input: {text}")
        reply = self.get_reply(text)
        print(f"Karen: {reply}")
        self.speak(reply)

    def self_test(self) -> None:
        self.check_services()
        test_text = "Hello Joseph, Karen is online and ready for a chat."
        print("Testing Cartesia TTS...")
        self.speak(test_text)
        print("Testing faster-whisper with synthetic audio...")
        response = self.cartesia.tts.generate(
            model_id=self.tts_model,
            transcript="Testing faster whisper transcription now.",
            voice={"mode": "id", "id": self.voice_id},
            output_format={"container": "wav", "encoding": "pcm_f32le", "sample_rate": TTS_SAMPLE_RATE},
            language="en",
        )
        wav_path = CACHE_DIR / "self_test.wav"
        response.write_to_file(str(wav_path))
        try:
            segments, _ = self.whisper.transcribe(str(wav_path), language="en", beam_size=1)
            transcript = " ".join(segment.text.strip() for segment in segments).strip()
            print(f"Whisper transcript: {transcript}")
            if "testing faster whisper" not in transcript.lower():
                raise RuntimeError("faster-whisper self-test transcript mismatch")
        finally:
            wav_path.unlink(missing_ok=True)

        print("Testing Ollama...", flush=True)
        reply = self.get_reply("Give me a six word greeting for Joseph.")
        print(f"Ollama reply: {reply}")
        print("Self-test passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Talk to Karen with mic -> Whisper -> Ollama -> Cartesia")
    parser.add_argument("--demo", help="Skip microphone and send one text message")
    parser.add_argument("--self-test", action="store_true", help="Run integration checks and exit")
    parser.add_argument("--whisper-model", default=DEFAULT_WHISPER_MODEL, help="faster-whisper model name")
    parser.add_argument(
        "--device",
        default=None,
        help="Input device index or name substring (e.g. 'AirPods' or '0'). Auto-detects AirPods if omitted.",
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio input devices and exit.",
    )
    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
        return 0

    try:
        app = KarenVoiceChat(whisper_model=args.whisper_model, input_device=args.device)
        if args.self_test:
            app.self_test()
        elif args.demo:
            app.demo(args.demo)
        else:
            app.run()
        return 0
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
