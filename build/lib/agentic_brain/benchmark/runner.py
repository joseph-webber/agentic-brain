# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""Benchmark runner for Agentic Brain performance and trend tracking."""

from __future__ import annotations

import asyncio
import inspect
import json
import platform
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import aiohttp

from .metrics import (
    METRIC_DEFINITIONS,
    BenchmarkConfig,
    BenchmarkResult,
    HardwareInfo,
    MetricSeries,
    ModelBenchmark,
)


def get_hardware_info() -> HardwareInfo:
    """Detect system hardware for benchmark context."""
    system = platform.system()
    cpu_cores = __import__("os").cpu_count() or 1
    processor = platform.processor() or "Unknown"
    memory_gb = 0.0
    gpu = None
    gpu_memory_gb = None
    accelerator = "cpu"

    if system == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                processor = result.stdout.strip()

            result = subprocess.run(
                ["sysctl", "-n", "hw.optional.arm64"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip() == "1":
                try:
                    import mlx  # noqa: F401

                    accelerator = "mlx"
                except ImportError:
                    accelerator = "mps"

                result = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    for line in result.stdout.split("\n"):
                        if "Chip:" in line:
                            gpu = line.split(":", maxsplit=1)[-1].strip()
                            break

            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                memory_gb = int(result.stdout.strip()) / (1024**3)
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
    elif system == "Linux":
        try:
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
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass

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
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        try:
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
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


def _rss_megabytes() -> float:
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            return rss / (1024 * 1024)
        return rss / 1024
    except Exception:
        return 0.0


class BrainBenchmark:
    """Run the Agentic Brain benchmark suite and collect trendable metrics."""

    def __init__(self, config: BenchmarkConfig | None = None):
        self.config = config or BenchmarkConfig()
        self.hardware = get_hardware_info()
        self._available_models_cache: set[str] | None = None

    async def _fetch_available_models(self) -> set[str]:
        if self._available_models_cache is not None:
            return self._available_models_cache

        try:
            async with aiohttp.ClientSession() as session:
                response = await session.get(
                    f"{self.config.ollama_host}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5),
                )
                if response.status != 200:
                    self._available_models_cache = set()
                else:
                    data = await response.json()
                    self._available_models_cache = {
                        model.get("name", "") for model in data.get("models", [])
                    }
                release = getattr(response, "release", None)
                if callable(release):
                    released = release()
                    if inspect.isawaitable(released):
                        await released
        except Exception:
            self._available_models_cache = set()

        return self._available_models_cache

    async def _check_ollama_available(self) -> bool:
        return bool(await self._fetch_available_models())

    async def _check_model_available(self, model: str) -> bool:
        return model in await self._fetch_available_models()

    async def _benchmark_single_request(
        self,
        model: str,
        session: aiohttp.ClientSession,
    ) -> tuple[float, int, float, bool]:
        payload = {"model": model, "prompt": self.config.prompt, "stream": False}
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
                token_count = int(data.get("eval_count", 0))
                eval_duration = float(data.get("eval_duration", 0)) / 1e9
                return latency, token_count, eval_duration, True
        except Exception:
            return 0.0, 0, 0.0, False

    async def _benchmark_streaming(
        self,
        model: str,
        session: aiohttp.ClientSession,
    ) -> tuple[float, float]:
        payload = {"model": model, "prompt": self.config.prompt, "stream": True}
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
                async for raw_line in response.content:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if data.get("response"):
                        token_count += 1
                        if first_token_time == 0.0:
                            first_token_time = time.perf_counter() - start
                    if data.get("done"):
                        break
            total_time = time.perf_counter() - start
            tokens_per_second = token_count / total_time if total_time > 0 else 0.0
            return first_token_time, tokens_per_second
        except Exception:
            return 0.0, 0.0

    async def _benchmark_model(self, model: str) -> ModelBenchmark:
        latencies: list[float] = []
        token_counts: list[int] = []
        eval_durations: list[float] = []
        failures = 0

        connector = aiohttp.TCPConnector(limit=1)
        async with aiohttp.ClientSession(connector=connector) as session:
            for _ in range(self.config.warmup_iterations):
                await self._benchmark_single_request(model, session)

            for _ in range(self.config.iterations):
                latency, tokens, eval_duration, success = await self._benchmark_single_request(
                    model,
                    session,
                )
                if success:
                    latencies.append(latency)
                    token_counts.append(tokens)
                    eval_durations.append(eval_duration)
                else:
                    failures += 1

            time_to_first_token = 0.0
            streaming_tokens_per_second = 0.0
            if self.config.include_streaming:
                time_to_first_token, streaming_tokens_per_second = (
                    await self._benchmark_streaming(model, session)
                )

        return ModelBenchmark.from_measurements(
            model=model,
            latencies=latencies,
            token_counts=token_counts,
            eval_durations=eval_durations,
            failures=failures,
            ttft=time_to_first_token,
            streaming_tps=streaming_tokens_per_second,
        )

    def _build_llm_metric(
        self,
        models: list[ModelBenchmark],
        *,
        llm_available: bool,
    ) -> MetricSeries:
        if not self.config.enable_llm or not self.config.models:
            return MetricSeries.from_samples(
                "llm_response_time",
                [],
                METRIC_DEFINITIONS["llm_response_time"].unit,
                status="skipped",
                description=METRIC_DEFINITIONS["llm_response_time"].description,
                metadata={"reason": "LLM benchmarking disabled."},
            )

        if not llm_available:
            return MetricSeries.from_samples(
                "llm_response_time",
                [],
                METRIC_DEFINITIONS["llm_response_time"].unit,
                status="error",
                description=METRIC_DEFINITIONS["llm_response_time"].description,
                metadata={
                    "reason": f"Ollama not available at {self.config.ollama_host}",
                    "successful_operations": 0,
                    "total_operations": len(self.config.models) * self.config.iterations,
                },
            )

        latencies = [
            latency
            for model in models
            for latency in model.raw_latencies
            if latency > 0
        ]
        successful = sum(model.successful_requests for model in models)
        total = sum(model.iterations for model in models)
        metadata = {
            "successful_operations": successful,
            "total_operations": total,
            "models": [model.model for model in models],
        }
        status = "ok" if latencies else "error"
        return MetricSeries.from_samples(
            "llm_response_time",
            latencies,
            METRIC_DEFINITIONS["llm_response_time"].unit,
            status=status,
            description=METRIC_DEFINITIONS["llm_response_time"].description,
            metadata=metadata,
        )

    def _run_neo4j_query_once(self) -> None:
        from neo4j import GraphDatabase

        uri = self.config.neo4j_uri
        if not uri:
            raise RuntimeError("Neo4j URI is required to run the benchmark query.")

        auth = None
        if self.config.neo4j_user:
            auth = (self.config.neo4j_user, self.config.neo4j_password or "")

        driver = GraphDatabase.driver(uri, auth=auth)
        try:
            with driver.session() as session:
                session.run(self.config.neo4j_query).consume()
        finally:
            driver.close()

    def _benchmark_neo4j_query(self) -> MetricSeries:
        definition = METRIC_DEFINITIONS["neo4j_query_time"]
        if not self.config.enable_neo4j:
            return MetricSeries.from_samples(
                "neo4j_query_time",
                [],
                definition.unit,
                status="skipped",
                description=definition.description,
                metadata={"reason": "Neo4j benchmarking disabled."},
            )

        if not self.config.neo4j_uri:
            return MetricSeries.from_samples(
                "neo4j_query_time",
                [],
                definition.unit,
                status="skipped",
                description=definition.description,
                metadata={"reason": "No Neo4j URI configured."},
            )

        try:
            __import__("neo4j")
        except ImportError:
            return MetricSeries.from_samples(
                "neo4j_query_time",
                [],
                definition.unit,
                status="skipped",
                description=definition.description,
                metadata={"reason": "neo4j package not installed."},
            )

        latencies: list[float] = []
        try:
            for _ in range(self.config.warmup_iterations):
                self._run_neo4j_query_once()

            for _ in range(self.config.iterations):
                start = time.perf_counter()
                self._run_neo4j_query_once()
                latencies.append(time.perf_counter() - start)

            return MetricSeries.from_samples(
                "neo4j_query_time",
                latencies,
                definition.unit,
                status="ok",
                description=definition.description,
                metadata={
                    "successful_operations": len(latencies),
                    "total_operations": len(latencies),
                    "query": self.config.neo4j_query,
                },
            )
        except Exception as exc:
            return MetricSeries.from_samples(
                "neo4j_query_time",
                latencies,
                definition.unit,
                status="error",
                description=definition.description,
                metadata={
                    "successful_operations": len(latencies),
                    "total_operations": self.config.iterations,
                    "reason": str(exc),
                },
            )

    def _voice_command(self) -> list[str] | None:
        if self.config.voice_command:
            return shlex.split(self.config.voice_command)

        if platform.system() == "Darwin" and shutil.which("say"):
            return ["say", "-o", "/dev/null", self.config.voice_text]

        if shutil.which("espeak"):
            return ["espeak", "--stdout", self.config.voice_text]

        return None

    def _benchmark_voice_synthesis(self) -> MetricSeries:
        definition = METRIC_DEFINITIONS["voice_synthesis_latency"]
        if not self.config.enable_voice:
            return MetricSeries.from_samples(
                "voice_synthesis_latency",
                [],
                definition.unit,
                status="skipped",
                description=definition.description,
                metadata={"reason": "Voice benchmarking disabled."},
            )

        command = self._voice_command()
        if not command:
            return MetricSeries.from_samples(
                "voice_synthesis_latency",
                [],
                definition.unit,
                status="skipped",
                description=definition.description,
                metadata={"reason": "No supported voice synthesis command available."},
            )

        latencies: list[float] = []
        try:
            for _ in range(self.config.warmup_iterations):
                subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=max(5, self.config.timeout),
                    check=False,
                )

            for _ in range(self.config.iterations):
                start = time.perf_counter()
                completed = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=max(5, self.config.timeout),
                    check=False,
                )
                if completed.returncode == 0:
                    latencies.append(time.perf_counter() - start)

            total = self.config.iterations
            return MetricSeries.from_samples(
                "voice_synthesis_latency",
                latencies,
                definition.unit,
                status="ok" if latencies else "error",
                description=definition.description,
                metadata={
                    "successful_operations": len(latencies),
                    "total_operations": total,
                    "command": command,
                },
            )
        except Exception as exc:
            return MetricSeries.from_samples(
                "voice_synthesis_latency",
                latencies,
                definition.unit,
                status="error",
                description=definition.description,
                metadata={
                    "successful_operations": len(latencies),
                    "total_operations": self.config.iterations,
                    "reason": str(exc),
                },
            )

    def _context_size_metric(self, model_count: int) -> MetricSeries:
        definition = METRIC_DEFINITIONS["context_size"]
        payload = {
            "model": self.config.models[0] if self.config.models else "disabled",
            "prompt": self.config.prompt,
            "context": self.config.context_payload or self.config.prompt,
            "stream": False,
        }
        serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        sample_count = max(1, self.config.iterations * max(1, model_count))
        size = float(len(serialized))
        return MetricSeries.from_samples(
            "context_size",
            [size] * sample_count,
            definition.unit,
            status="ok",
            description=definition.description,
            metadata={
                "successful_operations": sample_count,
                "total_operations": sample_count,
                "payload_keys": sorted(payload.keys()),
            },
        )

    def _memory_usage_metric(self, samples: list[float]) -> MetricSeries:
        definition = METRIC_DEFINITIONS["memory_usage"]
        return MetricSeries.from_samples(
            "memory_usage",
            [sample for sample in samples if sample > 0],
            definition.unit,
            status="ok" if any(sample > 0 for sample in samples) else "error",
            description=definition.description,
            metadata={
                "successful_operations": len(samples),
                "total_operations": len(samples),
            },
        )

    def _success_rate_metric(self, metrics: dict[str, MetricSeries]) -> MetricSeries:
        definition = METRIC_DEFINITIONS["success_rate"]
        successful = 0
        total = 0
        for metric in metrics.values():
            successful += int(metric.metadata.get("successful_operations", 0))
            total += int(metric.metadata.get("total_operations", 0))

        value = (successful / total * 100.0) if total else 0.0
        return MetricSeries.from_value(
            "success_rate",
            value,
            definition.unit,
            status="ok" if total else "error",
            description=definition.description,
            metadata={
                "successful_operations": successful,
                "total_operations": total,
            },
        )

    async def run(self) -> BenchmarkResult:
        start_time = time.perf_counter()
        memory_samples = [_rss_megabytes()]
        models: list[ModelBenchmark] = []
        metrics: dict[str, MetricSeries] = {}
        llm_available = False

        if self.config.enable_llm and self.config.models:
            llm_available = await self._check_ollama_available()
            if llm_available:
                for model in self.config.models:
                    if not await self._check_model_available(model):
                        models.append(
                            ModelBenchmark(
                                model=model,
                                failed_requests=self.config.iterations,
                                iterations=self.config.iterations,
                            )
                        )
                        continue
                    models.append(await self._benchmark_model(model))
            else:
                models.extend(
                    ModelBenchmark(
                        model=model,
                        failed_requests=self.config.iterations,
                        iterations=self.config.iterations,
                    )
                    for model in self.config.models
                )

        metrics["llm_response_time"] = self._build_llm_metric(
            models,
            llm_available=llm_available,
        )
        memory_samples.append(_rss_megabytes())

        metrics["neo4j_query_time"] = self._benchmark_neo4j_query()
        memory_samples.append(_rss_megabytes())

        metrics["voice_synthesis_latency"] = self._benchmark_voice_synthesis()
        memory_samples.append(_rss_megabytes())

        metrics["context_size"] = self._context_size_metric(len(models) or len(self.config.models))
        metrics["memory_usage"] = self._memory_usage_metric(memory_samples)
        metrics["success_rate"] = self._success_rate_metric(
            {name: metric for name, metric in metrics.items() if name != "success_rate"}
        )

        duration = time.perf_counter() - start_time
        return BenchmarkResult(
            models=models,
            metrics=metrics,
            hardware=self.hardware,
            config=self.config,
            duration_seconds=duration,
            metadata={"benchmark_name": self.config.benchmark_name},
        )


BenchmarkRunner = BrainBenchmark


async def run_benchmark(
    models: list[str] | None = None,
    iterations: int = 10,
    **kwargs: Any,
) -> BenchmarkResult:
    config = BenchmarkConfig(
        models=models or ["llama3.2:3b"],
        iterations=iterations,
        **kwargs,
    )
    runner = BrainBenchmark(config)
    return await runner.run()


def run_benchmark_sync(
    models: list[str] | None = None,
    iterations: int = 10,
    **kwargs: Any,
) -> BenchmarkResult:
    return asyncio.run(run_benchmark(models=models, iterations=iterations, **kwargs))


__all__ = [
    "BenchmarkRunner",
    "BrainBenchmark",
    "get_hardware_info",
    "run_benchmark",
    "run_benchmark_sync",
]
