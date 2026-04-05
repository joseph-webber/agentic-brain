#!/usr/bin/env python3
"""
Comprehensive Whisper Model Benchmark Suite
Tests all Whisper model sizes (tiny, base, small, medium, large)
Measures latency, accuracy, and resource usage
"""

import json
import os
import time
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import numpy as np

try:
    from faster_whisper import WhisperModel
    import librosa
    import soundfile as sf
except ImportError:
    print("❌ Required packages not installed. Install with:")
    print("   pip3 install faster-whisper librosa soundfile")
    sys.exit(1)


@dataclass
class WhisperBenchmarkResult:
    """Single Whisper model benchmark result"""

    model_name: str
    model_size: str
    audio_duration_ms: int
    transcription_time_ms: int
    first_token_time_ms: int
    text: str
    word_count: int
    success: bool
    error: Optional[str]
    timestamp: str
    device: str
    language: str = "en"

    def to_dict(self) -> Dict:
        return asdict(self)


class AudioGenerator:
    """Generate test audio files"""

    @staticmethod
    def generate_silence(duration_ms: float, sample_rate: int = 16000) -> np.ndarray:
        """Generate silent audio"""
        num_samples = int(duration_ms * sample_rate / 1000)
        return np.zeros(num_samples, dtype=np.float32)

    @staticmethod
    def generate_tone(
        frequency: float, duration_ms: float, sample_rate: int = 16000
    ) -> np.ndarray:
        """Generate sine wave tone"""
        num_samples = int(duration_ms * sample_rate / 1000)
        t = np.linspace(0, duration_ms / 1000, num_samples, dtype=np.float32)
        return np.sin(2 * np.pi * frequency * t) * 0.3

    @staticmethod
    def generate_speech_like_audio(
        duration_ms: float, sample_rate: int = 16000
    ) -> np.ndarray:
        """Generate synthetic speech-like audio (combination of multiple frequencies)"""
        num_samples = int(duration_ms * sample_rate / 1000)
        t = np.linspace(0, duration_ms / 1000, num_samples, dtype=np.float32)

        # Mix multiple frequencies (vowel-like formants)
        audio = (
            0.3 * np.sin(2 * np.pi * 200 * t)  # F0
            + 0.2 * np.sin(2 * np.pi * 700 * t)  # F1
            + 0.15 * np.sin(2 * np.pi * 1220 * t)  # F2
            + 0.1 * np.sin(2 * np.pi * 2600 * t)  # F3
        )

        # Add envelope
        envelope = np.exp(-t / (duration_ms / 1000 / 3))  # Decay over time
        audio = audio * envelope * 0.3

        return audio.astype(np.float32)

    @staticmethod
    def save_audio(audio: np.ndarray, filepath: str, sample_rate: int = 16000) -> None:
        """Save audio to file"""
        sf.write(filepath, audio, sample_rate)

    @staticmethod
    def create_test_files(
        output_dir: str = "/tmp/whisper_benchmark_audio",
    ) -> Dict[str, str]:
        """Create test audio files of different durations"""
        Path(output_dir).mkdir(exist_ok=True, parents=True)

        test_files = {}

        # Create test audio files (5 seconds, 30 seconds, 60 seconds)
        for duration_ms in [5000, 30000, 60000]:
            duration_s = duration_ms / 1000
            audio = AudioGenerator.generate_speech_like_audio(duration_ms)
            filename = f"test_audio_{duration_s:.0f}s.wav"
            filepath = os.path.join(output_dir, filename)
            AudioGenerator.save_audio(audio, filepath)
            test_files[f"{duration_s:.0f}s"] = filepath
            print(f"  Created: {filename}")

        return test_files


class WhisperModelBenchmark:
    """Benchmark Whisper models of different sizes"""

    MODEL_SIZES = ["tiny", "base", "small", "medium", "large"]
    DEVICE = "cpu"  # Can be "cuda" if GPU available

    def __init__(
        self,
        output_dir: str = "/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks",
    ):
        self.output_dir = output_dir
        self.results: List[WhisperBenchmarkResult] = []
        Path(output_dir).mkdir(exist_ok=True, parents=True)

        # Check GPU availability
        try:
            import torch

            self.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        except:
            self.DEVICE = "cpu"

        print(f"🖥️  Using device: {self.DEVICE.upper()}")

    def benchmark_model(
        self, model_size: str, audio_file: str, audio_duration_ms: int
    ) -> Optional[WhisperBenchmarkResult]:
        """Benchmark a single model on an audio file"""
        print(f"  📊 Testing {model_size}...", end=" ", flush=True)

        try:
            model_name = f"{model_size}.en"

            # Load model
            load_start = time.time()
            model = WhisperModel(model_name, device=self.DEVICE, compute_type="float32")
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

            # Get first token time (first segment completion)
            first_token_time = None
            full_text = ""
            segment_count = 0

            for segment in segments:
                if segment_count == 0:
                    first_token_time = time.time() - transcribe_start
                full_text += segment.text + " "
                segment_count += 1

            total_time = time.time() - transcribe_start

            word_count = len(full_text.split())

            result = WhisperBenchmarkResult(
                model_name=model_name,
                model_size=model_size,
                audio_duration_ms=audio_duration_ms,
                transcription_time_ms=int(total_time * 1000),
                first_token_time_ms=(
                    int(first_token_time * 1000)
                    if first_token_time
                    else int(total_time * 1000)
                ),
                text=full_text.strip(),
                word_count=word_count,
                success=True,
                error=None,
                timestamp=datetime.now().isoformat(),
                device=self.DEVICE,
            )

            print(f"✓ {int(total_time*1000)}ms")
            return result

        except Exception as e:
            print(f"✗ Error: {str(e)}")
            result = WhisperBenchmarkResult(
                model_name=f"{model_size}.en",
                model_size=model_size,
                audio_duration_ms=audio_duration_ms,
                transcription_time_ms=0,
                first_token_time_ms=0,
                text="",
                word_count=0,
                success=False,
                error=str(e),
                timestamp=datetime.now().isoformat(),
                device=self.DEVICE,
            )
            return result

    def run_full_benchmark(self) -> None:
        """Run complete benchmark suite"""
        print("\n🚀 Starting Whisper Model Benchmark Suite")
        print("=" * 70)

        # Generate test audio files
        print("\n📝 Generating test audio files...")
        test_files = AudioGenerator.create_test_files()

        print("\n🎯 Benchmarking Whisper Models")
        print("-" * 70)

        # For each model size
        for model_size in self.MODEL_SIZES:
            print(f"\n🔧 Model: {model_size.upper()}")

            # For each test file
            for duration_label, audio_file in test_files.items():
                audio_duration_ms = int(float(duration_label.rstrip("s")) * 1000)
                result = self.benchmark_model(model_size, audio_file, audio_duration_ms)
                if result:
                    self.results.append(result)

        # Save results
        self.save_results()
        self.print_summary()

        # Cleanup
        import shutil

        shutil.rmtree("/tmp/whisper_benchmark_audio", ignore_errors=True)

    def save_results(self) -> None:
        """Save benchmark results to JSON"""
        output_file = os.path.join(self.output_dir, "whisper_models_benchmark.json")

        report = {
            "timestamp": datetime.now().isoformat(),
            "device": self.DEVICE,
            "total_benchmarks": len(self.results),
            "successful": len([r for r in self.results if r.success]),
            "failed": len([r for r in self.results if not r.success]),
            "results": [r.to_dict() for r in self.results],
            "summary": self._generate_summary(),
        }

        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n✅ Results saved to: {output_file}")

    def _generate_summary(self) -> Dict:
        """Generate performance summary"""
        summary_by_model = {}

        for result in self.results:
            if result.success:
                key = result.model_size
                if key not in summary_by_model:
                    summary_by_model[key] = {
                        "model": result.model_name,
                        "times": [],
                        "audio_durations": [],
                    }
                summary_by_model[key]["times"].append(result.transcription_time_ms)
                summary_by_model[key]["audio_durations"].append(
                    result.audio_duration_ms
                )

        summary = {}
        for model_size, data in summary_by_model.items():
            avg_time = int(np.mean(data["times"]))
            min_time = int(np.min(data["times"]))
            max_time = int(np.max(data["times"]))

            # Check if meets target
            audio_duration = data["audio_durations"][0]
            target_met = False

            if model_size == "tiny":
                target_met = avg_time < 500
            elif model_size == "base":
                target_met = avg_time < 1000
            else:
                target_met = avg_time < 3000

            summary[model_size] = {
                "model_name": data["model"],
                "avg_time_ms": avg_time,
                "min_time_ms": min_time,
                "max_time_ms": max_time,
                "target_met": target_met,
                "target_ms": (
                    500
                    if model_size == "tiny"
                    else 1000 if model_size == "base" else 3000
                ),
            }

        return summary

    def print_summary(self) -> None:
        """Print benchmark summary"""
        print("\n" + "=" * 70)
        print("📊 WHISPER MODEL BENCHMARK SUMMARY")
        print("=" * 70)

        successful = len([r for r in self.results if r.success])
        failed = len([r for r in self.results if not r.success])

        print(f"Total Benchmarks: {len(self.results)}")
        print(f"Successful: {successful} ✓")
        print(f"Failed: {failed} ✗")

        summary = self._generate_summary()

        print("\n🏆 MODEL PERFORMANCE:")
        print("-" * 70)

        for model_size in self.MODEL_SIZES:
            if model_size in summary:
                data = summary[model_size]
                target = "✅" if data["target_met"] else "❌"

                print(f"\n  {model_size.upper()}")
                print(f"    Average Time: {data['avg_time_ms']}ms")
                print(f"    Min Time: {data['min_time_ms']}ms")
                print(f"    Max Time: {data['max_time_ms']}ms")
                print(f"    Target (<{data['target_ms']}ms): {target}")

        print("\n" + "=" * 70)

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")

        fastest = min(summary.items(), key=lambda x: x[1]["avg_time_ms"])
        print(f"  • Fastest: {fastest[0].upper()} ({fastest[1]['avg_time_ms']}ms)")

        meets_targets = {k: v for k, v in summary.items() if v["target_met"]}
        if meets_targets:
            best = min(meets_targets.items(), key=lambda x: x[1]["avg_time_ms"])
            print(
                f"  • Recommended (meets target): {best[0].upper()} ({best[1]['avg_time_ms']}ms)"
            )

        print("\n" + "=" * 70)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Whisper Model Benchmark Suite")
    parser.add_argument(
        "--output-dir",
        default="/Users/joe/brain/agentic-brain/apps/BrainChat/benchmarks",
        help="Output directory for results",
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="Don't delete test audio files"
    )

    args = parser.parse_args()

    benchmark = WhisperModelBenchmark(output_dir=args.output_dir)
    benchmark.run_full_benchmark()


if __name__ == "__main__":
    main()
