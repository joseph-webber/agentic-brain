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

"""Reporting and trend comparison utilities for benchmark results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .metrics import (
    METRIC_DEFINITIONS,
    BenchmarkComparison,
    BenchmarkResult,
    MetricDefinition,
    MetricSeries,
    RegressionFinding,
)


class BenchmarkReporter:
    """Render benchmark results and compare them with historical runs."""

    @staticmethod
    def to_json(result: BenchmarkResult, indent: int = 2) -> str:
        return json.dumps(result.to_dict(), indent=indent)

    @staticmethod
    def _format_value(value: float, unit: str) -> str:
        if unit == "seconds":
            return f"{value:.3f}s"
        if unit == "MB":
            return f"{value:.1f} MB"
        if unit == "bytes":
            return f"{value:.0f} B"
        if unit == "percent":
            return f"{value:.1f}%"
        return f"{value:.3f} {unit}".strip()

    @classmethod
    def _metric_row(cls, metric: MetricSeries, definition: MetricDefinition) -> str:
        primary = metric.comparison_value()
        comparison_label = definition.comparison_stat.upper()
        return (
            f"| {definition.label} | {metric.status} | "
            f"{cls._format_value(primary, definition.unit)} ({comparison_label}) | "
            f"{cls._format_value(metric.p50, definition.unit)} | "
            f"{cls._format_value(metric.p95, definition.unit)} |"
        )

    @classmethod
    def to_markdown(cls, result: BenchmarkResult) -> str:
        lines = [
            "# Agentic Brain LLM Benchmark Results",
            "",
            f"**Timestamp:** {result.timestamp}",
            f"**Duration:** {result.duration_seconds:.1f}s",
            "",
        ]

        if result.hardware:
            hw = result.hardware
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

        if result.metrics:
            lines.extend(
                [
                    "## Metric Summary",
                    "",
                    "| Metric | Status | Comparison | P50 | P95 |",
                    "|--------|--------|------------|-----|-----|",
                ]
            )
            for name, definition in METRIC_DEFINITIONS.items():
                metric = result.metrics.get(name)
                if metric:
                    lines.append(cls._metric_row(metric, definition))
            lines.append("")

        if result.models:
            lines.extend(
                [
                    "## Model Detail",
                    "",
                    "| Model | P50 (s) | P95 (s) | P99 (s) | Tok/s | Success |",
                    "|-------|---------|---------|---------|-------|---------|",
                ]
            )
            for model in result.models:
                success = f"{model.successful_requests}/{model.iterations}"
                lines.append(
                    f"| {model.model} | {model.latency_p50:.2f} | {model.latency_p95:.2f} | "
                    f"{model.latency_p99:.2f} | {model.tokens_per_second:.1f} | {success} |"
                )
            lines.append("")

        if result.comparison:
            lines.extend(
                [
                    "## Trend Comparison",
                    "",
                    f"Compared with: `{result.comparison.baseline_timestamp}`",
                    "",
                ]
            )
            if result.comparison.regressions:
                lines.extend(["### Regressions", ""])
                for finding in result.comparison.regressions:
                    lines.append(f"- {finding.message}")
                lines.append("")
            if result.comparison.improvements:
                lines.extend(["### Improvements", ""])
                for finding in result.comparison.improvements:
                    lines.append(f"- {finding.message}")
                lines.append("")

        return "\n".join(lines)

    @classmethod
    def to_table(cls, result: BenchmarkResult) -> str:
        if not result.models and not result.metrics:
            return "No benchmark results available."

        lines = [
            "",
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                        AGENTIC BRAIN LLM BENCHMARK                           ║",
            "╠══════════════════════════════════════════════════════════════════════════════╣",
        ]

        if result.hardware:
            hw = result.hardware
            processor = hw.processor[:40]
            accelerator = (hw.accelerator or "n/a").upper()
            lines.append(f"║  Hardware: {processor:<40} {accelerator:>8}  ║")
            lines.append(
                f"║  Memory: {hw.memory_gb}GB | Cores: {hw.cpu_cores} | Platform: {hw.platform:<24} ║"
            )
            lines.append(
                "╠══════════════════════════════════════════════════════════════════════════════╣"
            )

        if result.metrics:
            lines.append(
                "║  Metric Summary                                                         ║"
            )
            lines.append(
                "║  Metric             │ Status  │ Comparison │ P50        │ P95         ║"
            )
            lines.append(
                "╠═════════════════════╪═════════╪════════════╪════════════╪═════════════╣"
            )
            for name, definition in METRIC_DEFINITIONS.items():
                metric = result.metrics.get(name)
                if not metric:
                    continue
                comparison = cls._format_value(
                    metric.comparison_value(), definition.unit
                )
                p50 = cls._format_value(metric.p50, definition.unit)
                p95 = cls._format_value(metric.p95, definition.unit)
                lines.append(
                    f"║  {definition.label[:19]:<19} │ {metric.status[:7]:<7} │ {comparison[:10]:<10} │ "
                    f"{p50[:10]:<10} │ {p95[:11]:<11} ║"
                )
            lines.append(
                "╠══════════════════════════════════════════════════════════════════════════════╣"
            )

        if result.models:
            lines.append(
                "║  Model              │ P50 (s) │ P95 (s) │ P99 (s) │ Tok/s │ Success  ║"
            )
            lines.append(
                "╠═════════════════════╪═════════╪═════════╪═════════╪═══════╪══════════╣"
            )
            for model in result.models:
                model_name = model.model[:19]
                success_rate = f"{model.successful_requests}/{model.iterations}"
                lines.append(
                    f"║  {model_name:<18} │ {model.latency_p50:>7.2f} │ {model.latency_p95:>7.2f} │ "
                    f"{model.latency_p99:>7.2f} │ {model.tokens_per_second:>5.1f} │ {success_rate:>8} ║"
                )
            lines.append(
                "╚══════════════════════════════════════════════════════════════════════════════╝"
            )
        else:
            lines.append(
                "╚══════════════════════════════════════════════════════════════════════════════╝"
            )

        if result.comparison:
            lines.append("")
            lines.append(
                f"Trend comparison: {len(result.comparison.regressions)} regression(s), "
                f"{len(result.comparison.improvements)} improvement(s)."
            )
            if result.comparison.baseline_timestamp:
                lines.append(f"Baseline: {result.comparison.baseline_timestamp}")

        lines.append("")
        lines.append(
            f"Benchmark completed in {result.duration_seconds:.1f}s at {result.timestamp}"
        )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def summary(result: BenchmarkResult) -> str:
        if result.models:
            best = min(result.models, key=lambda model: model.latency_p50)
            fastest = max(result.models, key=lambda model: model.tokens_per_second)
            return (
                f"Benchmarked {len(result.models)} model(s). "
                f"Fastest latency: {best.model} ({best.latency_p50:.2f}s P50). "
                f"Highest throughput: {fastest.model} ({fastest.tokens_per_second:.1f} tok/s)."
            )

        success = result.metrics.get("success_rate")
        if success:
            return (
                f"Captured {len(result.metrics)} metric(s). "
                f"Overall success rate: {success.mean:.1f}%."
            )
        return "No benchmark results."

    @staticmethod
    def _change_pct(current_value: float, baseline_value: float) -> float:
        if baseline_value == 0:
            return 0.0 if current_value == 0 else 100.0
        return ((current_value - baseline_value) / baseline_value) * 100.0

    @classmethod
    def compare(
        cls,
        current: BenchmarkResult,
        baseline: BenchmarkResult,
        *,
        baseline_path: Path | None = None,
    ) -> BenchmarkComparison:
        comparison = BenchmarkComparison(
            baseline_timestamp=baseline.timestamp,
            baseline_path=str(baseline_path) if baseline_path else None,
        )

        for name, definition in METRIC_DEFINITIONS.items():
            current_metric = current.metrics.get(name)
            baseline_metric = baseline.metrics.get(name)
            if not current_metric or not baseline_metric:
                continue
            if current_metric.status != "ok" or baseline_metric.status != "ok":
                continue

            comparison.checked_metrics += 1
            current_value = current_metric.comparison_value()
            baseline_value = baseline_metric.comparison_value()
            change_pct = cls._change_pct(current_value, baseline_value)
            threshold = definition.regression_threshold_pct

            if definition.lower_is_better:
                is_regression = change_pct > threshold
                is_improvement = change_pct < -threshold
            else:
                is_regression = change_pct < -threshold
                is_improvement = change_pct > threshold

            if not is_regression and not is_improvement:
                continue

            if abs(change_pct) >= threshold * 2:
                severity = "high"
            elif abs(change_pct) >= threshold * 1.5:
                severity = "medium"
            else:
                severity = "low"

            trend = "regressed" if is_regression else "improved"
            message = (
                f"{definition.label} {trend} by {abs(change_pct):.1f}% "
                f"({baseline_value:.3f} → {current_value:.3f} {definition.unit})"
            )
            finding = RegressionFinding(
                metric=name,
                label=definition.label,
                baseline_value=baseline_value,
                current_value=current_value,
                change_pct=change_pct,
                status="regression" if is_regression else "improvement",
                message=message,
                severity=severity,
            )
            if is_regression:
                comparison.regressions.append(finding)
            else:
                comparison.improvements.append(finding)

        return comparison

    @staticmethod
    def load_result(path: Path) -> BenchmarkResult:
        return BenchmarkResult.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def save_result(result: BenchmarkResult, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.to_json(), encoding="utf-8")

    @staticmethod
    def latest_history_file(history_dir: Path) -> Path | None:
        if not history_dir.exists():
            return None
        candidates = sorted(history_dir.glob("*.json"))
        return candidates[-1] if candidates else None


__all__ = ["BenchmarkReporter"]
