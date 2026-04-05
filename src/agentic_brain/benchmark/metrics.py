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

"""Metric models and result types for Agentic Brain benchmarking."""

from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal

Direction = Literal["lower", "higher"]


class OutputFormat(Enum):
    """Output format for benchmark results."""

    JSON = "json"
    TABLE = "table"
    MARKDOWN = "markdown"


@dataclass(frozen=True)
class MetricDefinition:
    """Definition for a tracked benchmark metric."""

    name: str
    label: str
    unit: str
    description: str
    direction: Direction = "lower"
    comparison_stat: str = "p95"
    regression_threshold_pct: float = 15.0

    @property
    def lower_is_better(self) -> bool:
        return self.direction == "lower"


DEFAULT_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition(
        name="llm_response_time",
        label="LLM response time",
        unit="seconds",
        description="Latency for non-streaming LLM completions.",
        direction="lower",
        comparison_stat="p95",
    ),
    MetricDefinition(
        name="neo4j_query_time",
        label="Neo4j query time",
        unit="seconds",
        description="Latency for the configured Neo4j benchmark query.",
        direction="lower",
        comparison_stat="p95",
    ),
    MetricDefinition(
        name="voice_synthesis_latency",
        label="Voice synthesis latency",
        unit="seconds",
        description="Latency to synthesize a short voice sample.",
        direction="lower",
        comparison_stat="p95",
    ),
    MetricDefinition(
        name="memory_usage",
        label="Memory usage",
        unit="MB",
        description="Resident memory usage sampled during the benchmark run.",
        direction="lower",
        comparison_stat="p95",
    ),
    MetricDefinition(
        name="context_size",
        label="Context size",
        unit="bytes",
        description="Serialized size of the benchmark request context payload.",
        direction="lower",
        comparison_stat="mean",
    ),
    MetricDefinition(
        name="success_rate",
        label="Success rate",
        unit="percent",
        description="Percentage of successful benchmark operations.",
        direction="higher",
        comparison_stat="mean",
        regression_threshold_pct=5.0,
    ),
)
METRIC_DEFINITIONS = {metric.name: metric for metric in DEFAULT_METRICS}


def _percentile(values: list[float], percentile: float) -> float:
    """Calculate a percentile using linear interpolation."""
    if not values:
        return 0.0

    if len(values) == 1:
        return float(values[0])

    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)

    if lower_index == upper_index:
        return float(ordered[lower_index])

    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    fraction = position - lower_index
    return float(lower_value + (upper_value - lower_value) * fraction)


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
    accelerator: str | None = None

    def to_dict(self) -> dict[str, Any]:
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

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HardwareInfo:
        return cls(**data)


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
    history_dir: Path = field(
        default_factory=lambda: Path(
            os.getenv("AGENTIC_BRAIN_BENCHMARK_DIR", ".benchmarks/agentic-brain")
        )
    )
    benchmark_name: str = "default"
    regression_threshold_pct: float = 15.0
    compare_with_history: bool = True
    record_history: bool = True
    enable_llm: bool = True
    enable_neo4j: bool = True
    enable_voice: bool = True
    neo4j_uri: str | None = field(default_factory=lambda: os.getenv("NEO4J_URI"))
    neo4j_query: str = field(
        default_factory=lambda: os.getenv(
            "AGENTIC_BRAIN_BENCHMARK_NEO4J_QUERY", "RETURN 1 AS ok"
        )
    )
    neo4j_user: str | None = field(default_factory=lambda: os.getenv("NEO4J_USER"))
    neo4j_password: str | None = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD")
    )
    voice_text: str = "Agentic Brain benchmark voice check."
    voice_command: str | None = field(
        default_factory=lambda: os.getenv("AGENTIC_BRAIN_BENCHMARK_VOICE_COMMAND")
    )
    context_payload: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "models": self.models,
            "iterations": self.iterations,
            "warmup_iterations": self.warmup_iterations,
            "prompt": self.prompt,
            "ollama_host": self.ollama_host,
            "timeout": self.timeout,
            "include_streaming": self.include_streaming,
            "output_file": str(self.output_file) if self.output_file else None,
            "output_format": self.output_format.value,
            "history_dir": str(self.history_dir),
            "benchmark_name": self.benchmark_name,
            "regression_threshold_pct": self.regression_threshold_pct,
            "compare_with_history": self.compare_with_history,
            "record_history": self.record_history,
            "enable_llm": self.enable_llm,
            "enable_neo4j": self.enable_neo4j,
            "enable_voice": self.enable_voice,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_query": self.neo4j_query,
            "neo4j_user": self.neo4j_user,
            "voice_text": self.voice_text,
            "voice_command": self.voice_command,
            "context_payload": self.context_payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkConfig:
        payload = dict(data)
        output_file = payload.get("output_file")
        history_dir = payload.get("history_dir")
        output_format = payload.get("output_format", OutputFormat.TABLE.value)

        if output_file:
            payload["output_file"] = Path(output_file)
        else:
            payload["output_file"] = None

        if history_dir:
            payload["history_dir"] = Path(history_dir)

        payload["output_format"] = OutputFormat(output_format)
        return cls(**payload)


@dataclass
class MetricSeries:
    """A numeric metric captured over one or more benchmark samples."""

    name: str
    unit: str
    samples: list[float] = field(default_factory=list)
    status: str = "ok"
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_samples(
        cls,
        name: str,
        samples: list[float],
        unit: str,
        *,
        status: str = "ok",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MetricSeries:
        return cls(
            name=name,
            unit=unit,
            samples=[float(sample) for sample in samples],
            status=status,
            description=description,
            metadata=metadata or {},
        )

    @classmethod
    def from_value(
        cls,
        name: str,
        value: float,
        unit: str,
        *,
        status: str = "ok",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> MetricSeries:
        return cls.from_samples(
            name,
            [value],
            unit,
            status=status,
            description=description,
            metadata=metadata,
        )

    @property
    def count(self) -> int:
        return len(self.samples)

    @property
    def minimum(self) -> float:
        return min(self.samples) if self.samples else 0.0

    @property
    def maximum(self) -> float:
        return max(self.samples) if self.samples else 0.0

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self.samples) if self.samples else 0.0

    @property
    def p50(self) -> float:
        return _percentile(self.samples, 0.50)

    @property
    def p95(self) -> float:
        return _percentile(self.samples, 0.95)

    @property
    def p99(self) -> float:
        return _percentile(self.samples, 0.99)

    @property
    def stddev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) > 1 else 0.0

    def comparison_value(self) -> float:
        definition = METRIC_DEFINITIONS.get(self.name)
        stat_name = definition.comparison_stat if definition else "mean"
        return float(getattr(self, stat_name, self.mean))

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "unit": self.unit,
            "status": self.status,
            "description": self.description,
            "samples": [round(sample, 6) for sample in self.samples],
            "summary": {
                "count": self.count,
                "min": round(self.minimum, 6),
                "max": round(self.maximum, 6),
                "mean": round(self.mean, 6),
                "median": round(self.median, 6),
                "p50": round(self.p50, 6),
                "p95": round(self.p95, 6),
                "p99": round(self.p99, 6),
                "stddev": round(self.stddev, 6),
                "comparison_value": round(self.comparison_value(), 6),
            },
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricSeries:
        return cls(
            name=data["name"],
            unit=data["unit"],
            samples=[float(sample) for sample in data.get("samples", [])],
            status=data.get("status", "ok"),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class ModelBenchmark:
    """Benchmark results for a single LLM model."""

    model: str
    provider: str = "ollama"
    latency_min: float = 0.0
    latency_max: float = 0.0
    latency_mean: float = 0.0
    latency_median: float = 0.0
    latency_p50: float = 0.0
    latency_p95: float = 0.0
    latency_p99: float = 0.0
    latency_stddev: float = 0.0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    avg_tokens_per_request: float = 0.0
    time_to_first_token: float = 0.0
    streaming_tokens_per_second: float = 0.0
    successful_requests: int = 0
    failed_requests: int = 0
    iterations: int = 0
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
        if not latencies:
            return cls(model=model, failed_requests=failures, iterations=failures)

        total_tokens = sum(token_counts)
        total_eval_time = sum(eval_durations)
        throughput = total_tokens / total_eval_time if total_eval_time > 0 else 0.0
        return cls(
            model=model,
            latency_min=min(latencies),
            latency_max=max(latencies),
            latency_mean=statistics.mean(latencies),
            latency_median=statistics.median(latencies),
            latency_p50=_percentile(latencies, 0.50),
            latency_p95=_percentile(latencies, 0.95),
            latency_p99=_percentile(latencies, 0.99),
            latency_stddev=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
            total_tokens=total_tokens,
            tokens_per_second=round(throughput, 1),
            avg_tokens_per_request=round(total_tokens / len(latencies), 1),
            time_to_first_token=ttft,
            streaming_tokens_per_second=streaming_tps,
            successful_requests=len(latencies),
            failed_requests=failures,
            iterations=len(latencies) + failures,
            raw_latencies=list(latencies),
            raw_token_counts=list(token_counts),
        )

    def to_dict(self) -> dict[str, Any]:
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
                "streaming_tokens_per_second": round(
                    self.streaming_tokens_per_second, 3
                ),
            },
            "requests": {
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "total": self.iterations,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelBenchmark:
        latency = data.get("latency", {})
        throughput = data.get("throughput", {})
        streaming = data.get("streaming", {})
        requests = data.get("requests", {})
        return cls(
            model=data["model"],
            provider=data.get("provider", "ollama"),
            latency_min=float(latency.get("min_s", 0.0)),
            latency_max=float(latency.get("max_s", 0.0)),
            latency_mean=float(latency.get("mean_s", 0.0)),
            latency_median=float(latency.get("median_s", 0.0)),
            latency_p50=float(latency.get("p50_s", 0.0)),
            latency_p95=float(latency.get("p95_s", 0.0)),
            latency_p99=float(latency.get("p99_s", 0.0)),
            latency_stddev=float(latency.get("stddev_s", 0.0)),
            total_tokens=int(throughput.get("total_tokens", 0)),
            tokens_per_second=float(throughput.get("tokens_per_second", 0.0)),
            avg_tokens_per_request=float(throughput.get("avg_tokens_per_request", 0.0)),
            time_to_first_token=float(streaming.get("time_to_first_token_s", 0.0)),
            streaming_tokens_per_second=float(
                streaming.get("streaming_tokens_per_second", 0.0)
            ),
            successful_requests=int(requests.get("successful", 0)),
            failed_requests=int(requests.get("failed", 0)),
            iterations=int(requests.get("total", 0)),
        )


@dataclass
class RegressionFinding:
    """A detected regression or improvement between benchmark runs."""

    metric: str
    label: str
    baseline_value: float
    current_value: float
    change_pct: float
    status: str
    message: str
    severity: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "label": self.label,
            "baseline_value": round(self.baseline_value, 6),
            "current_value": round(self.current_value, 6),
            "change_pct": round(self.change_pct, 3),
            "status": self.status,
            "message": self.message,
            "severity": self.severity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RegressionFinding:
        return cls(**data)


@dataclass
class BenchmarkComparison:
    """Comparison between the current benchmark result and a baseline."""

    baseline_timestamp: str = ""
    baseline_path: str | None = None
    checked_metrics: int = 0
    regressions: list[RegressionFinding] = field(default_factory=list)
    improvements: list[RegressionFinding] = field(default_factory=list)

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_timestamp": self.baseline_timestamp,
            "baseline_path": self.baseline_path,
            "checked_metrics": self.checked_metrics,
            "has_regressions": self.has_regressions,
            "regressions": [finding.to_dict() for finding in self.regressions],
            "improvements": [finding.to_dict() for finding in self.improvements],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkComparison:
        return cls(
            baseline_timestamp=data.get("baseline_timestamp", ""),
            baseline_path=data.get("baseline_path"),
            checked_metrics=int(data.get("checked_metrics", 0)),
            regressions=[
                RegressionFinding.from_dict(item)
                for item in data.get("regressions", [])
            ],
            improvements=[
                RegressionFinding.from_dict(item)
                for item in data.get("improvements", [])
            ],
        )


@dataclass
class BenchmarkResult:
    """Complete benchmark results with metric summaries and model detail."""

    models: list[ModelBenchmark] = field(default_factory=list)
    metrics: dict[str, MetricSeries] = field(default_factory=dict)
    hardware: HardwareInfo | None = None
    config: BenchmarkConfig | None = None
    timestamp: str = ""
    duration_seconds: float = 0.0
    version: str = "1.0.0"
    comparison: BenchmarkComparison | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            from agentic_brain.utils.clock import clock

            self.timestamp = clock.iso_datetime()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "duration_seconds": round(self.duration_seconds, 2),
            "hardware": self.hardware.to_dict() if self.hardware else None,
            "config": self.config.to_dict() if self.config else None,
            "metrics": {
                name: metric.to_dict() for name, metric in self.metrics.items()
            },
            "models": [model.to_dict() for model in self.models],
            "comparison": self.comparison.to_dict() if self.comparison else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkResult:
        hardware = data.get("hardware")
        config = data.get("config")
        comparison = data.get("comparison")
        return cls(
            models=[ModelBenchmark.from_dict(item) for item in data.get("models", [])],
            metrics={
                name: MetricSeries.from_dict(metric)
                for name, metric in data.get("metrics", {}).items()
            },
            hardware=HardwareInfo.from_dict(hardware) if hardware else None,
            config=BenchmarkConfig.from_dict(config) if config else None,
            timestamp=data.get("timestamp", ""),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            version=data.get("version", "1.0.0"),
            comparison=(
                BenchmarkComparison.from_dict(comparison) if comparison else None
            ),
            metadata=data.get("metadata", {}),
        )

    def to_json(self, indent: int = 2) -> str:
        from .reporter import BenchmarkReporter

        return BenchmarkReporter.to_json(self, indent=indent)

    def to_table(self) -> str:
        from .reporter import BenchmarkReporter

        return BenchmarkReporter.to_table(self)

    def to_markdown(self) -> str:
        from .reporter import BenchmarkReporter

        return BenchmarkReporter.to_markdown(self)

    def summary(self) -> str:
        from .reporter import BenchmarkReporter

        return BenchmarkReporter.summary(self)


__all__ = [
    "BenchmarkComparison",
    "BenchmarkConfig",
    "BenchmarkResult",
    "DEFAULT_METRICS",
    "HardwareInfo",
    "METRIC_DEFINITIONS",
    "MetricDefinition",
    "MetricSeries",
    "ModelBenchmark",
    "OutputFormat",
    "RegressionFinding",
]
