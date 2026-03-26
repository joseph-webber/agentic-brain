# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Benchmarking utilities for agentic-brain.

This module provides performance benchmarking tools for measuring:
- LLM response latency (with percentiles P50, P95, P99)
- Token throughput (tokens/second)
- Model comparison across providers
- Hardware-aware performance baselines

Example:
    >>> from agentic_brain.benchmark import BenchmarkRunner, BenchmarkConfig
    >>> config = BenchmarkConfig(models=["llama3.2:3b"], iterations=10)
    >>> runner = BenchmarkRunner(config)
    >>> results = await runner.run()
    >>> print(results.summary())
"""

from __future__ import annotations

import asyncio
import json
import os
import platform
import statistics
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import aiohttp

__all__ = [
    "BenchmarkConfig",
    "BenchmarkResult",
    "ModelBenchmark",
    "BenchmarkRunner",
    "HardwareInfo",
    "get_hardware_info",
    "run_benchmark",
    "run_benchmark_sync",
]


class OutputFormat(Enum):
    """Output format for benchmark results."""

    JSON = "json"
    TABLE = "table"
    MARKDOWN = "markdown"


@dataclass
class HardwareInfo:
    """System hardware information for benchmark context."""

    platform: str
    platform_version: str
    processor: str
    cpu_cores: int
    memory_gb: float
    gpu: str | None = None
    gpu_memory_gb: float | None = None
    accelerator: str | None = None  # mlx, cuda, rocm, mps, cpu

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "platform": self.platform,
            "platform_version": self.platform_version,
            "processor": self.processor,
            "cpu_cores": self.cpu_cores,
            "memory_gb": self.memory_gb,
            "gpu": self.gpu,
            "gpu_memory_gb": self.gpu_memory_gb,
            "accelerator": self.accelerator,
        }


def get_hardware_info() -> HardwareInfo:
    """
    Detect system hardware for benchmark context.

    Returns:
        HardwareInfo with detected hardware specs
    """
    import os

    system = platform.system()
    cpu_cores = os.cpu_count() or 1

    # Default values
    processor = platform.processor() or "Unknown"
    memory_gb = 0.0
    gpu = None
    gpu_memory_gb = None
    accelerator = "cpu"

    # macOS-specific detection
    if system == "Darwin":
        try:
            # Get chip info
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                processor = result.stdout.strip()

            # Check for Apple Silicon
            result = subprocess.run(
                ["sysctl", "-n", "hw.optional.arm64"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip() == "1":
                # Apple Silicon - check for MLX
                try:
                    import mlx  # noqa: F401

                    accelerator = "mlx"
                except ImportError:
                    accelerator = "mps"

                # Get chip name from system_profiler
                result = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "Chip:" in line:
                            gpu = line.split(":")[-1].strip()
                            break

            # Get memory
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                memory_gb = int(result.stdout.strip()) / (1024**3)

        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

    # Linux detection
    elif system == "Linux":
        try:
            # Check for NVIDIA GPU
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 2:
                    gpu = parts[0].strip()
                    mem_str = parts[1].strip().lower()
                    if "mib" in mem_str:
                        gpu_memory_gb = float(mem_str.replace("mib", "").strip()) / 1024
                    elif "gib" in mem_str:
                        gpu_memory_gb = float(mem_str.replace("gib", "").strip())
                    accelerator = "cuda"
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            pass

        # Check for AMD ROCm
        if accelerator == "cpu":
            try:
                result = subprocess.run(
                    ["rocm-smi", "--showproductname"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    accelerator = "rocm"
                    gpu = result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        # Get memory from /proc/meminfo
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        mem_kb = int(line.split()[1])
                        memory_gb = mem_kb / (1024**2)
                        break
        except (FileNotFoundError, ValueError):
            pass

    return HardwareInfo(
        platform=system,
        platform_version=platform.release(),
        processor=processor,
        cpu_cores=cpu_cores,
        memory_gb=round(memory_gb, 1),
        gpu=gpu,
        gpu_memory_gb=round(gpu_memory_gb, 1) if gpu_memory_gb else None,
        accelerator=accelerator,
    )


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    models: list[str] = field(default_factory=lambda: ["llama3.2:3b"])
    iterations: int = 10
    warmup_iterations: int = 2
    prompt: str = "Explain what Python is in exactly 3 sentences."
    ollama_host: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434")
    )
    timeout: int = 120
    include_streaming: bool = True
    output_file: Path | None = None
    output_format: OutputFormat = OutputFormat.TABLE

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "models": self.models,
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "prompt": self.prompt,
            "ollama_host": self.ollama_host,
            "timeout": self.timeout,
            "include_streaming": self.include_streaming,
        }


@dataclass
class ModelBenchmark:
    """Benchmark results for a single model."""

    model: str
    provider: str = "ollama"

    # Latency stats (seconds)
    latency_min: float = 0.0
    latency_max: float = 0.0
    latency_mean: float = 0.0
    latency_median: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_stddev: float = 0.0

    # Token stats
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    avg_tokens_per_request: float = 0.0

    # Streaming stats (if applicable)
    time_to_first_token: float = 0.0
    streaming_tokens_per_second: float = 0.0

    # Request stats
    successful_requests: int = 0
    failed_requests: int = 0
    iterations: int = 0

    # Raw data for further analysis
    raw_latencies: list[float] = field(default_factory=list)
    raw_token_counts: list[int] = field(default_factory=list)

    @classmethod
    def from_measurements(
        cls,
        model: str,
        latencies: list[float],
        token_counts: list[int],
        eval_durations: list[float],
        failures: int = 0,
        ttft: float = 0.0,
        streaming_tps: float = 0.0,
    ) -> ModelBenchmark:
        """Create benchmark result from raw measurements."""
        if not latencies:
            return cls(model=model, failed_requests=failures)

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        # Calculate percentiles
        p50_idx = int(n * 0.50)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)

        # Token throughput
        total_tokens = sum(token_counts)
        total_eval_time = sum(eval_durations)
        tps = total_tokens / total_eval_time if total_eval_time > 0 else 0.0

        return cls(
            model=model,
            latency_min=min(latencies),
            latency_max=max(latencies),
            latency_mean=statistics.mean(latencies),
            latency_median=statistics.median(latencies),
            latency_p50=sorted_latencies[min(p50_idx, n - 1)],
            latency_p95=sorted_latencies[min(p95_idx, n - 1)],
            latency_p99=sorted_latencies[min(p99_idx, n - 1)],
            latency_stddev=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            total_tokens=total_tokens,
            tokens_per_second=round(tps, 1),
            avg_tokens_per_request=round(total_tokens / n, 1),
            time_to_first_token=ttft,
            streaming_tokens_per_second=streaming_tps,
            successful_requests=n,
            failed_requests=failures,
            iterations=n + failures,
            raw_latencies=latencies,
            raw_token_counts=token_counts,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (excludes raw data for compact output)."""
        return {
            "model": self.model,
            "provider": self.provider,
            "latency": {
                "min_s": round(self.latency_min, 3),
                "max_s": round(self.latency_max, 3),
                "mean_s": round(self.latency_mean, 3),
                "median_s": round(self.latency_median, 3),
                "p50_s": round(self.latency_p50, 3),
                "p95_s": round(self.latency_p95, 3),
                "p99_s": round(self.latency_p99, 3),
                "stddev_s": round(self.latency_stddev, 3),
            },
            "throughput": {
                "tokens_per_second": self.tokens_per_second,
                "total_tokens": self.total_tokens,
                "avg_tokens_per_request": self.avg_tokens_per_request,
            },
            "streaming": {
                "time_to_first_token_s": round(self.time_to_first_token, 3),
                "streaming_tokens_per_second": self.streaming_tokens_per_second,
            },
            "requests": {
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "total": self.iterations,
            },
        }


@dataclass
class BenchmarkResult:
    """Complete benchmark results with all models and metadata."""

    models: list[ModelBenchmark] = field(default_factory=list)
    hardware: HardwareInfo | None = None
    config: BenchmarkConfig | None = None
    timestamp: str = ""
    duration_seconds: float = 0.0
    version: str = "1.0.0"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(tz=None).astimezone().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 2),
            "hardware": self.hardware.to_dict() if self.hardware else None,
            "config": self.config.to_dict() if self.config else None,
            "models": [m.to_dict() for m in self.models],
        }

    def to_json(self, indent: int = 2) -> str:
        """Export as JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_table(self) -> str:
        """Format results as ASCII table."""
        if not self.models:
            return "No benchmark results available."

        # Header
        lines = [
            "",
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                        AGENTIC BRAIN LLM BENCHMARK                           ║",
            "╠══════════════════════════════════════════════════════════════════════════════╣",
        ]

        # Hardware info
        if self.hardware:
            hw = self.hardware
            lines.append(
                f"║  Hardware: {hw.processor[:40]:<40} {hw.accelerator.upper():>8}  ║"
            )
            lines.append(
                f"║  Memory: {hw.memory_gb}GB | Cores: {hw.cpu_cores} | Platform: {hw.platform:<24} ║"
            )
            lines.append(
                "╠══════════════════════════════════════════════════════════════════════════════╣"
            )

        # Model results header
        lines.append(
            "║  Model              │ P50 (s) │ P95 (s) │ P99 (s) │ Tok/s │ Success  ║"
        )
        lines.append(
            "╠═════════════════════╪═════════╪═════════╪═════════╪═══════╪══════════╣"
        )

        # Model results
        for m in self.models:
            model_name = m.model[:19]
            success_rate = f"{m.successful_requests}/{m.iterations}"
            lines.append(
                f"║  {model_name:<18} │ {m.latency_p50:>7.2f} │ {m.latency_p95:>7.2f} │ "
                f"{m.latency_p99:>7.2f} │ {m.tokens_per_second:>5.1f} │ {success_rate:>8} ║"
            )

        lines.append(
            "╚══════════════════════════════════════════════════════════════════════════════╝"
        )

        # Legend
        lines.append("")
        lines.append(
            "Legend: P50/P95/P99 = latency percentiles | Tok/s = tokens per second"
        )
        lines.append(
            f"Benchmark completed in {self.duration_seconds:.1f}s at {self.timestamp}"
        )
        lines.append("")

        return "\n".join(lines)

    def to_markdown(self) -> str:
        """Format results as Markdown table."""
        lines = [
            "# Agentic Brain LLM Benchmark Results",
            "",
            f"**Timestamp:** {self.timestamp}",
            f"**Duration:** {self.duration_seconds:.1f}s",
            "",
        ]

        if self.hardware:
            hw = self.hardware
            lines.extend(
                [
                    "## Hardware",
                    "",
                    "| Property | Value |",
                    "|----------|-------|",
                    f"| Processor | {hw.processor} |",
                    f"| Cores | {hw.cpu_cores} |",
                    f"| Memory | {hw.memory_gb} GB |",
                    f"| Accelerator | {hw.accelerator} |",
                    f"| Platform | {hw.platform} {hw.platform_version} |",
                    "",
                ]
            )

        if self.models:
            lines.extend(
                [
                    "## Results",
                    "",
                    "| Model | P50 (s) | P95 (s) | P99 (s) | Tok/s | Success |",
                    "|-------|---------|---------|---------|-------|---------|",
                ]
            )

            for m in self.models:
                success = f"{m.successful_requests}/{m.iterations}"
                lines.append(
                    f"| {m.model} | {m.latency_p50:.2f} | {m.latency_p95:.2f} | "
                    f"{m.latency_p99:.2f} | {m.tokens_per_second:.1f} | {success} |"
                )

            lines.append("")

        return "\n".join(lines)

    def summary(self) -> str:
        """Get a brief text summary."""
        if not self.models:
            return "No benchmark results."

        best = min(self.models, key=lambda m: m.latency_p50)
        fastest = max(self.models, key=lambda m: m.tokens_per_second)

        return (
            f"Benchmarked {len(self.models)} model(s). "
            f"Fastest latency: {best.model} ({best.latency_p50:.2f}s P50). "
            f"Highest throughput: {fastest.model} ({fastest.tokens_per_second:.1f} tok/s)."
        )


class BenchmarkRunner:
    """
    Runs LLM benchmarks against Ollama models.

    Example:
        >>> config = BenchmarkConfig(models=["llama3.2:3b"], iterations=10)
        >>> runner = BenchmarkRunner(config)
        >>> results = await runner.run()
        >>> print(results.to_table())
    """

    def __init__(self, config: BenchmarkConfig | None = None):
        """Initialize benchmark runner.

        Args:
            config: Benchmark configuration. Uses defaults if not provided.
        """
        self.config = config or BenchmarkConfig()
        self.hardware = get_hardware_info()

    async def _check_ollama_available(self) -> bool:
        """Check if Ollama is running and accessible."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.config.ollama_host}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    return response.status == 200
        except Exception:
            return False

    async def _check_model_available(self, model: str) -> bool:
        """Check if a specific model is available in Ollama."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.config.ollama_host}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        available = [m["name"] for m in data.get("models", [])]
                        return model in available
        except Exception:
            pass
        return False

    async def _benchmark_single_request(
        self, model: str, session: aiohttp.ClientSession
    ) -> tuple[float, int, float, bool]:
        """
        Run a single benchmark request.

        Returns:
            Tuple of (latency_seconds, token_count, eval_duration_seconds, success)
        """
        payload = {
            "model": model,
            "prompt": self.config.prompt,
            "stream": False,
        }

        try:
            start = time.perf_counter()
            async with session.post(
                f"{self.config.ollama_host}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status != 200:
                    return 0.0, 0, 0.0, False

                data = await response.json()
                latency = time.perf_counter() - start

                # Extract token count and eval duration
                token_count = data.get("eval_count", 0)
                # eval_duration is in nanoseconds
                eval_duration = data.get("eval_duration", 0) / 1e9

                return latency, token_count, eval_duration, True

        except Exception:
            return 0.0, 0, 0.0, False

    async def _benchmark_streaming(
        self, model: str, session: aiohttp.ClientSession
    ) -> tuple[float, float]:
        """
        Benchmark streaming response.

        Returns:
            Tuple of (time_to_first_token, tokens_per_second)
        """
        payload = {
            "model": model,
            "prompt": self.config.prompt,
            "stream": True,
        }

        try:
            start = time.perf_counter()
            first_token_time = 0.0
            token_count = 0

            async with session.post(
                f"{self.config.ollama_host}/api/generate",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
            ) as response:
                if response.status != 200:
                    return 0.0, 0.0

                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line)
                            if data.get("response"):
                                token_count += 1
                                if first_token_time == 0.0:
                                    first_token_time = time.perf_counter() - start

                            if data.get("done"):
                                break
                        except json.JSONDecodeError:
                            continue

            total_time = time.perf_counter() - start
            tps = token_count / total_time if total_time > 0 else 0.0

            return first_token_time, tps

        except Exception:
            return 0.0, 0.0

    async def _benchmark_model(self, model: str) -> ModelBenchmark:
        """Run benchmark for a single model."""
        latencies: list[float] = []
        token_counts: list[int] = []
        eval_durations: list[float] = []
        failures = 0

        connector = aiohttp.TCPConnector(limit=1)  # Sequential requests
        async with aiohttp.ClientSession(connector=connector) as session:
            # Warmup
            for _ in range(self.config.warmup_iterations):
                await self._benchmark_single_request(model, session)

            # Actual benchmark
            for _ in range(self.config.iterations):
                latency, tokens, eval_dur, success = (
                    await self._benchmark_single_request(model, session)
                )
                if success:
                    latencies.append(latency)
                    token_counts.append(tokens)
                    eval_durations.append(eval_dur)
                else:
                    failures += 1

            # Streaming benchmark (single run)
            ttft = 0.0
            streaming_tps = 0.0
            if self.config.include_streaming:
                ttft, streaming_tps = await self._benchmark_streaming(model, session)

        return ModelBenchmark.from_measurements(
            model=model,
            latencies=latencies,
            token_counts=token_counts,
            eval_durations=eval_durations,
            failures=failures,
            ttft=ttft,
            streaming_tps=streaming_tps,
        )

    async def run(self) -> BenchmarkResult:
        """
        Run the complete benchmark suite.

        Returns:
            BenchmarkResult with all model benchmarks and metadata.
        """
        start_time = time.perf_counter()

        # Check Ollama availability
        if not await self._check_ollama_available():
            raise RuntimeError(
                f"Ollama not available at {self.config.ollama_host}. "
                "Please ensure Ollama is running."
            )

        results: list[ModelBenchmark] = []

        for model in self.config.models:
            # Check model availability
            if not await self._check_model_available(model):
                # Create failed result
                results.append(
                    ModelBenchmark(
                        model=model,
                        failed_requests=self.config.iterations,
                        iterations=self.config.iterations,
                    )
                )
                continue

            # Run benchmark
            benchmark = await self._benchmark_model(model)
            results.append(benchmark)

        duration = time.perf_counter() - start_time

        return BenchmarkResult(
            models=results,
            hardware=self.hardware,
            config=self.config,
            duration_seconds=duration,
        )


async def run_benchmark(
    models: list[str] | None = None,
    iterations: int = 10,
    **kwargs: Any,
) -> BenchmarkResult:
    """
    Convenience function to run benchmarks.

    Args:
        models: List of model names to benchmark (default: ["llama3.2:3b"])
        iterations: Number of iterations per model
        **kwargs: Additional BenchmarkConfig options

    Returns:
        BenchmarkResult with all results
    """
    config = BenchmarkConfig(
        models=models or ["llama3.2:3b"],
        iterations=iterations,
        **kwargs,
    )
    runner = BenchmarkRunner(config)
    return await runner.run()


def run_benchmark_sync(
    models: list[str] | None = None,
    iterations: int = 10,
    **kwargs: Any,
) -> BenchmarkResult:
    """
    Synchronous wrapper for run_benchmark.

    Args:
        models: List of model names to benchmark
        iterations: Number of iterations per model
        **kwargs: Additional BenchmarkConfig options

    Returns:
        BenchmarkResult with all results
    """
    return asyncio.run(run_benchmark(models, iterations, **kwargs))
