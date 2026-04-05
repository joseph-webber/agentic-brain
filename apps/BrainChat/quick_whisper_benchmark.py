#!/usr/bin/env python3
"""
Quick Whisper Benchmark - Fast latency testing
Focuses on actual transcription latency, not full model suite
"""

import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

try:
    import soundfile as sf
    from faster_whisper import WhisperModel
except ImportError:
    print("❌ Required packages not installed. Install with:")
    print("   pip3 install faster-whisper soundfile")
    sys.exit(1)


def generate_test_audio(duration_ms: float, sample_rate: int = 16000) -> np.ndarray:
    """Generate synthetic speech-like audio"""
    num_samples = int(duration_ms * sample_rate / 1000)
    t = np.linspace(0, duration_ms / 1000, num_samples, dtype=np.float32)

    # Mix frequencies for speech-like audio
    audio = (
        0.3 * np.sin(2 * np.pi * 200 * t)
        + 0.2 * np.sin(2 * np.pi * 700 * t)
        + 0.15 * np.sin(2 * np.pi * 1220 * t)
        + 0.1 * np.sin(2 * np.pi * 2600 * t)
    )

    # Add envelope
    envelope = np.exp(-t / (duration_ms / 1000 / 3))
    audio = audio * envelope * 0.3

    return audio.astype(np.float32)


def save_audio(audio: np.ndarray, filepath: str, sample_rate: int = 16000) -> None:
    """Save audio to file"""
    Path(filepath).parent.mkdir(exist_ok=True, parents=True)
    sf.write(filepath, audio, sample_rate)


def benchmark_whisper_model(
    model_size: str, audio_file: str, audio_duration_ms: int
) -> Dict:
    """Benchmark a single Whisper model"""
    print(f"    {model_size}...", end=" ", flush=True)

    try:
        model_name = f"{model_size}.en"

        # Load model (time it)
        load_start = time.time()
        model = WhisperModel(model_name, device="cpu", compute_type="float32")
        load_time = time.time() - load_start

        # Transcribe
        transcribe_start = time.time()
        segments, info = model.transcribe(
            audio_file,
            language="en",
            beam_size=5,
            best_of=5,
            temperature=0.0,
            condition_on_previous_text=False,
        )

        # Collect segments
        full_text = ""
        for segment in segments:
            full_text += segment.text + " "

        total_time = time.time() - transcribe_start

        print(f"✓ {int(total_time*1000)}ms")

        return {
            "model": model_name,
            "size": model_size,
            "audio_duration_ms": audio_duration_ms,
            "load_time_ms": int(load_time * 1000),
            "transcription_time_ms": int(total_time * 1000),
            "text_length": len(full_text),
            "success": True,
            "error": None,
        }
    except Exception as e:
        print(f"✗ {str(e)[:50]}")
        return {
            "model": f"{model_size}.en",
            "size": model_size,
            "audio_duration_ms": audio_duration_ms,
            "load_time_ms": 0,
            "transcription_time_ms": 0,
            "text_length": 0,
            "success": False,
            "error": str(e)[:100],
        }


def main():
    output_dir = "/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks"
    Path(output_dir).mkdir(exist_ok=True, parents=True)

    print("\n" + "=" * 70)
    print("🎯 WHISPER LATENCY BENCHMARK")
    print("=" * 70)

    # Create test audio (5, 30, 60 seconds)
    print("\n📝 Generating test audio...")
    temp_dir = "/tmp/whisper_bench"
    Path(temp_dir).mkdir(exist_ok=True, parents=True)

    test_files = {}
    for duration_s in [5, 30]:
        duration_ms = duration_s * 1000
        audio = generate_test_audio(duration_ms)
        filepath = f"{temp_dir}/test_{duration_s}s.wav"
        save_audio(audio, filepath)
        test_files[f"{duration_s}s"] = filepath
        print(f"  ✓ {duration_s}s audio")

    # Benchmark models
    print("\n📊 BENCHMARKING MODELS")
    print("-" * 70)

    results = []
    models_to_test = ["tiny", "base", "small"]

    for model_size in models_to_test:
        print(f"\n  Model: {model_size.upper()}")

        for duration_label, audio_file in test_files.items():
            duration_ms = int(float(duration_label.rstrip("s")) * 1000)
            result = benchmark_whisper_model(model_size, audio_file, duration_ms)
            results.append(result)

    # Save results
    output_file = os.path.join(output_dir, "whisper_models_benchmark.json")
    report = {
        "timestamp": datetime.now().isoformat(),
        "device": "cpu",
        "total_tests": len(results),
        "successful": len([r for r in results if r["success"]]),
        "failed": len([r for r in results if not r["success"]]),
        "results": results,
    }

    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 70)
    print("📊 RESULTS SUMMARY")
    print("=" * 70)

    # Group by model
    by_model = {}
    for r in results:
        if r["success"]:
            model = r["size"]
            if model not in by_model:
                by_model[model] = []
            by_model[model].append(r["transcription_time_ms"])

    for model in ["tiny", "base", "small"]:
        if model in by_model:
            times = by_model[model]
            avg = sum(times) // len(times)
            target = 500 if model == "tiny" else 1000 if model == "base" else 2000
            status = "✅" if avg < target else "⚠️"
            print(f"\n  {model.upper()}:")
            print(f"    Avg Time: {avg}ms")
            print(f"    Target: <{target}ms {status}")

    print("\n" + "=" * 70)
    print(f"✅ Results saved: {output_file}")
    print("=" * 70)

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
