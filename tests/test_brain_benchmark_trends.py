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

"""Tests for benchmark trend tracking and reporting."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agentic_brain.benchmark import BenchmarkReporter, BenchmarkResult, MetricSeries


def test_metric_series_comparison_value_uses_p95_for_latency() -> None:
    metric = MetricSeries.from_samples(
        "llm_response_time",
        [0.1, 0.2, 0.3, 0.4, 0.5],
        "seconds",
    )

    assert metric.p95 >= 0.47
    assert metric.comparison_value() == metric.p95


def test_reporter_detects_regression() -> None:
    baseline = BenchmarkResult(
        metrics={
            "llm_response_time": MetricSeries.from_samples(
                "llm_response_time",
                [0.2, 0.25, 0.3],
                "seconds",
            ),
            "success_rate": MetricSeries.from_value(
                "success_rate",
                100.0,
                "percent",
            ),
        }
    )
    current = BenchmarkResult(
        metrics={
            "llm_response_time": MetricSeries.from_samples(
                "llm_response_time",
                [0.5, 0.55, 0.6],
                "seconds",
            ),
            "success_rate": MetricSeries.from_value(
                "success_rate",
                100.0,
                "percent",
            ),
        }
    )

    comparison = BenchmarkReporter.compare(current, baseline)

    assert comparison.has_regressions is True
    assert comparison.regressions[0].metric == "llm_response_time"


def test_script_outputs_json_without_external_services(tmp_path: Path) -> None:
    output_path = tmp_path / "benchmark.json"
    history_dir = tmp_path / "history"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/run-benchmark.py",
            "--skip-llm",
            "--skip-neo4j",
            "--skip-voice",
            "--output",
            str(output_path),
            "--history-dir",
            str(history_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert "metrics" in payload
    assert output_path.exists()
    assert any(history_dir.glob("*.json"))
