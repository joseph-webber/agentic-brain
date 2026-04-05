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

"""Public benchmarking API for Agentic Brain."""

from .metrics import (
    DEFAULT_METRICS,
    METRIC_DEFINITIONS,
    BenchmarkComparison,
    BenchmarkConfig,
    BenchmarkResult,
    HardwareInfo,
    MetricDefinition,
    MetricSeries,
    ModelBenchmark,
    OutputFormat,
    RegressionFinding,
)
from .competitors import (
    CompetitorBenchmark,
    CompetitorComparisonReport,
    CompetitorComparisonRow,
    CompetitorProfile,
)
from .suite import BenchmarkMetric, BenchmarkSuite, BenchmarkSuiteResult
from .reporter import BenchmarkReporter
from .runner import (
    BenchmarkRunner,
    BrainBenchmark,
    get_hardware_info,
    run_benchmark,
    run_benchmark_sync,
)

__all__ = [
    "BenchmarkComparison",
    "BenchmarkConfig",
    "BenchmarkReporter",
    "BenchmarkResult",
    "BenchmarkMetric",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "BenchmarkSuiteResult",
    "BrainBenchmark",
    "CompetitorBenchmark",
    "CompetitorComparisonReport",
    "CompetitorComparisonRow",
    "CompetitorProfile",
    "DEFAULT_METRICS",
    "HardwareInfo",
    "METRIC_DEFINITIONS",
    "MetricDefinition",
    "MetricSeries",
    "ModelBenchmark",
    "OutputFormat",
    "RegressionFinding",
    "get_hardware_info",
    "run_benchmark",
    "run_benchmark_sync",
]
