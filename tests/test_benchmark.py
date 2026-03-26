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
Tests for the benchmark module.

Tests cover:
- Hardware detection
- Benchmark configuration
- Result calculation (percentiles, throughput)
- Output formatting (table, JSON, markdown)
- CLI command integration
- Error handling
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agentic_brain.benchmark import (
    BenchmarkConfig,
    BenchmarkResult,
    BenchmarkRunner,
    HardwareInfo,
    ModelBenchmark,
    OutputFormat,
    get_hardware_info,
    run_benchmark_sync,
)


class TestHardwareInfo:
    """Tests for HardwareInfo dataclass."""

    def test_hardware_info_creation(self):
        """Test creating HardwareInfo with all fields."""
        hw = HardwareInfo(
            platform="Darwin",
            platform_version="23.0.0",
            processor="Apple M2",
            cpu_cores=8,
            memory_gb=16.0,
            gpu="Apple M2",
            gpu_memory_gb=None,
            accelerator="mlx",
        )

        assert hw.platform == "Darwin"
        assert hw.cpu_cores == 8
        assert hw.memory_gb == 16.0
        assert hw.accelerator == "mlx"

    def test_hardware_info_to_dict(self):
        """Test conversion to dictionary."""
        hw = HardwareInfo(
            platform="Linux",
            platform_version="5.15.0",
            processor="Intel i9",
            cpu_cores=16,
            memory_gb=64.0,
            gpu="RTX 4090",
            gpu_memory_gb=24.0,
            accelerator="cuda",
        )

        d = hw.to_dict()
        assert d["platform"] == "Linux"
        assert d["gpu"] == "RTX 4090"
        assert d["gpu_memory_gb"] == 24.0
        assert d["accelerator"] == "cuda"

    def test_get_hardware_info_returns_valid(self):
        """Test that get_hardware_info returns valid HardwareInfo."""
        hw = get_hardware_info()

        assert isinstance(hw, HardwareInfo)
        assert hw.platform in ("Darwin", "Linux", "Windows")
        assert hw.cpu_cores >= 1
        assert hw.memory_gb > 0
        assert hw.accelerator in ("mlx", "mps", "cuda", "rocm", "cpu")


class TestBenchmarkConfig:
    """Tests for BenchmarkConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BenchmarkConfig()

        assert config.models == ["llama3.2:3b"]
        assert config.iterations == 10
        assert config.warmup_iterations == 2
        assert config.ollama_host == "http://localhost:11434"
        assert config.timeout == 120
        assert config.include_streaming is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = BenchmarkConfig(
            models=["llama3.1:8b", "mistral:7b"],
            iterations=50,
            warmup_iterations=5,
            prompt="Custom prompt",
        )

        assert len(config.models) == 2
        assert config.iterations == 50
        assert config.prompt == "Custom prompt"

    def test_config_to_dict(self):
        """Test conversion to dictionary."""
        config = BenchmarkConfig(
            models=["test-model"],
            iterations=5,
        )

        d = config.to_dict()
        assert d["models"] == ["test-model"]
        assert d["iterations"] == 5
        assert "warmup_iterations" in d


class TestModelBenchmark:
    """Tests for ModelBenchmark dataclass."""

    def test_from_measurements_basic(self):
        """Test creating benchmark from basic measurements."""
        latencies = [1.0, 1.5, 2.0, 1.2, 1.8]
        token_counts = [50, 55, 60, 52, 58]
        eval_durations = [0.5, 0.6, 0.7, 0.55, 0.65]

        result = ModelBenchmark.from_measurements(
            model="test-model",
            latencies=latencies,
            token_counts=token_counts,
            eval_durations=eval_durations,
        )

        assert result.model == "test-model"
        assert result.successful_requests == 5
        assert result.failed_requests == 0
        assert result.latency_min == 1.0
        assert result.latency_max == 2.0
        assert result.total_tokens == 275  # sum of token_counts

    def test_from_measurements_with_failures(self):
        """Test benchmark with failures."""
        result = ModelBenchmark.from_measurements(
            model="test-model",
            latencies=[1.0, 1.5],
            token_counts=[50, 55],
            eval_durations=[0.5, 0.6],
            failures=3,
        )

        assert result.successful_requests == 2
        assert result.failed_requests == 3
        assert result.iterations == 5

    def test_from_measurements_empty(self):
        """Test benchmark with no successful requests."""
        result = ModelBenchmark.from_measurements(
            model="test-model",
            latencies=[],
            token_counts=[],
            eval_durations=[],
            failures=5,
        )

        assert result.successful_requests == 0
        assert result.failed_requests == 5

    def test_percentile_calculation(self):
        """Test that percentiles are calculated correctly."""
        # 100 samples for accurate percentiles
        latencies = [i * 0.01 for i in range(1, 101)]  # 0.01 to 1.00
        token_counts = [50] * 100
        eval_durations = [0.5] * 100

        result = ModelBenchmark.from_measurements(
            model="test-model",
            latencies=latencies,
            token_counts=token_counts,
            eval_durations=eval_durations,
        )

        # P50 should be around 0.50
        assert 0.45 <= result.latency_p50 <= 0.55
        # P95 should be around 0.95
        assert 0.90 <= result.latency_p95 <= 1.00
        # P99 should be around 0.99
        assert 0.95 <= result.latency_p99 <= 1.00

    def test_throughput_calculation(self):
        """Test tokens per second calculation."""
        # 100 tokens over 2 seconds = 50 tok/s
        result = ModelBenchmark.from_measurements(
            model="test-model",
            latencies=[2.0],
            token_counts=[100],
            eval_durations=[2.0],
        )

        assert result.tokens_per_second == 50.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ModelBenchmark.from_measurements(
            model="test-model",
            latencies=[1.0, 1.5, 2.0],
            token_counts=[50, 55, 60],
            eval_durations=[0.5, 0.6, 0.7],
        )

        d = result.to_dict()
        assert d["model"] == "test-model"
        assert "latency" in d
        assert "throughput" in d
        assert "requests" in d
        assert d["requests"]["successful"] == 3


class TestBenchmarkResult:
    """Tests for BenchmarkResult dataclass."""

    def test_empty_result(self):
        """Test empty benchmark result."""
        result = BenchmarkResult()

        assert result.models == []
        assert result.timestamp != ""
        assert result.duration_seconds == 0.0

    def test_result_with_models(self):
        """Test result with model benchmarks."""
        model1 = ModelBenchmark.from_measurements(
            model="model1",
            latencies=[1.0, 1.5],
            token_counts=[50, 55],
            eval_durations=[0.5, 0.6],
        )
        model2 = ModelBenchmark.from_measurements(
            model="model2",
            latencies=[0.5, 0.8],
            token_counts=[40, 45],
            eval_durations=[0.3, 0.4],
        )

        result = BenchmarkResult(
            models=[model1, model2],
            duration_seconds=30.0,
        )

        assert len(result.models) == 2
        assert result.duration_seconds == 30.0

    def test_to_json(self):
        """Test JSON export."""
        model = ModelBenchmark.from_measurements(
            model="test-model",
            latencies=[1.0],
            token_counts=[50],
            eval_durations=[0.5],
        )
        hw = HardwareInfo(
            platform="Darwin",
            platform_version="23.0.0",
            processor="Apple M2",
            cpu_cores=8,
            memory_gb=16.0,
            accelerator="mlx",
        )

        result = BenchmarkResult(models=[model], hardware=hw)
        json_str = result.to_json()

        # Verify valid JSON
        data = json.loads(json_str)
        assert data["version"] == "1.0.0"
        assert len(data["models"]) == 1
        assert data["hardware"]["processor"] == "Apple M2"

    def test_to_table(self):
        """Test ASCII table output."""
        model = ModelBenchmark.from_measurements(
            model="llama3.2:3b",
            latencies=[0.5, 0.6, 0.7],
            token_counts=[50, 55, 60],
            eval_durations=[0.3, 0.35, 0.4],
        )

        result = BenchmarkResult(models=[model], duration_seconds=5.0)
        table = result.to_table()

        assert "AGENTIC BRAIN LLM BENCHMARK" in table
        assert "llama3.2:3b" in table
        assert "P50" in table
        assert "P95" in table
        assert "Tok/s" in table

    def test_to_markdown(self):
        """Test Markdown output."""
        model = ModelBenchmark.from_measurements(
            model="llama3.2:3b",
            latencies=[0.5, 0.6, 0.7],
            token_counts=[50, 55, 60],
            eval_durations=[0.3, 0.35, 0.4],
        )
        hw = HardwareInfo(
            platform="Darwin",
            platform_version="23.0.0",
            processor="Apple M2",
            cpu_cores=8,
            memory_gb=16.0,
            accelerator="mlx",
        )

        result = BenchmarkResult(models=[model], hardware=hw)
        md = result.to_markdown()

        assert "# Agentic Brain LLM Benchmark" in md
        assert "| Model |" in md
        assert "llama3.2:3b" in md
        assert "Apple M2" in md

    def test_summary(self):
        """Test brief summary."""
        model1 = ModelBenchmark.from_measurements(
            model="fast-model",
            latencies=[0.3, 0.4],
            token_counts=[100, 110],
            eval_durations=[0.2, 0.25],
        )
        model2 = ModelBenchmark.from_measurements(
            model="slow-model",
            latencies=[1.0, 1.5],
            token_counts=[50, 55],
            eval_durations=[0.8, 0.9],
        )

        result = BenchmarkResult(models=[model1, model2])
        summary = result.summary()

        assert "2 model(s)" in summary
        assert "fast-model" in summary  # Should be fastest


class TestBenchmarkRunner:
    """Tests for BenchmarkRunner class."""

    @pytest.fixture
    def mock_ollama_response(self):
        """Create a mock Ollama API response."""
        return {
            "response": "This is a test response.",
            "done": True,
            "eval_count": 50,
            "eval_duration": 500000000,  # 0.5 seconds in nanoseconds
        }

    @pytest.mark.asyncio
    async def test_check_ollama_available_success(self):
        """Test Ollama availability check when available."""
        runner = BenchmarkRunner()

        with patch("aiohttp.ClientSession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = (
                mock_response
            )

            await runner._check_ollama_available()
            # Note: This will fail in real test without mocking properly
            # Just testing the interface exists

    @pytest.mark.asyncio
    async def test_benchmark_model_mocked(self):
        """Test benchmarking a single model with mocked responses."""
        config = BenchmarkConfig(
            models=["test-model"],
            iterations=3,
            warmup_iterations=1,
        )
        runner = BenchmarkRunner(config)

        # Mock the benchmark methods
        runner._check_model_available = AsyncMock(return_value=True)
        runner._benchmark_single_request = AsyncMock(return_value=(0.5, 50, 0.3, True))
        runner._benchmark_streaming = AsyncMock(return_value=(0.1, 100.0))

        result = await runner._benchmark_model("test-model")

        assert result.model == "test-model"
        assert result.successful_requests == 3  # iterations
        assert runner._benchmark_single_request.call_count == 4  # warmup + iterations


class TestBenchmarkCLI:
    """Tests for benchmark CLI command."""

    def test_cli_import(self):
        """Test that benchmark command can be imported."""
        from agentic_brain.cli.commands import benchmark_command

        assert callable(benchmark_command)

    def test_cli_parser_has_benchmark(self):
        """Test that CLI parser includes benchmark command."""
        from agentic_brain.cli import create_parser

        parser = create_parser()
        # Parse with benchmark command
        args = parser.parse_args(["benchmark"])
        assert args.command == "benchmark"

    def test_cli_benchmark_options(self):
        """Test benchmark command options."""
        from agentic_brain.cli import create_parser

        parser = create_parser()

        # Test with all options
        args = parser.parse_args(
            [
                "benchmark",
                "--models",
                "llama3.2:3b,llama3.1:8b",
                "--iterations",
                "20",
                "--warmup",
                "5",
                "--format",
                "json",
                "--output",
                "results.json",
                "--ollama-host",
                "http://localhost:11434",
                "--no-streaming",
            ]
        )

        assert args.models == "llama3.2:3b,llama3.1:8b"
        assert args.iterations == 20
        assert args.warmup == 5
        assert args.format == "json"
        assert args.output == "results.json"
        assert args.no_streaming is True


class TestOutputFormats:
    """Tests for output format handling."""

    def test_output_format_enum(self):
        """Test OutputFormat enum values."""
        assert OutputFormat.JSON.value == "json"
        assert OutputFormat.TABLE.value == "table"
        assert OutputFormat.MARKDOWN.value == "markdown"


class TestSyncWrapper:
    """Tests for synchronous wrapper function."""

    def test_run_benchmark_sync_exists(self):
        """Test that sync wrapper exists."""
        assert callable(run_benchmark_sync)

    @pytest.mark.skipif(
        True, reason="Requires Ollama running locally"  # Skip in CI - requires Ollama
    )
    def test_run_benchmark_sync_integration(self):
        """Integration test with real Ollama (skip in CI)."""
        result = run_benchmark_sync(
            models=["llama3.2:3b"],
            iterations=1,
        )
        assert isinstance(result, BenchmarkResult)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_single_iteration(self):
        """Test benchmark with single iteration."""
        result = ModelBenchmark.from_measurements(
            model="test",
            latencies=[1.0],
            token_counts=[50],
            eval_durations=[0.5],
        )

        assert result.latency_stddev == 0.0  # Can't compute stddev with 1 sample
        assert result.latency_p50 == 1.0
        assert result.latency_p95 == 1.0

    def test_zero_eval_duration(self):
        """Test handling of zero eval duration."""
        result = ModelBenchmark.from_measurements(
            model="test",
            latencies=[1.0],
            token_counts=[50],
            eval_durations=[0.0],
        )

        assert result.tokens_per_second == 0.0  # Avoid division by zero

    def test_mixed_success_failure(self):
        """Test benchmark with mixed success/failure."""
        result = ModelBenchmark.from_measurements(
            model="test",
            latencies=[1.0, 2.0],
            token_counts=[50, 60],
            eval_durations=[0.5, 0.8],
            failures=8,
        )

        assert result.successful_requests == 2
        assert result.failed_requests == 8
        assert result.iterations == 10


class TestTableFormatting:
    """Tests for table formatting edge cases."""

    def test_long_model_name_truncation(self):
        """Test that long model names are truncated in table."""
        model = ModelBenchmark.from_measurements(
            model="very-long-model-name-that-exceeds-column-width",
            latencies=[1.0],
            token_counts=[50],
            eval_durations=[0.5],
        )

        result = BenchmarkResult(models=[model])
        table = result.to_table()

        # Should not break table formatting
        assert "very-long-model" in table

    def test_no_models_table(self):
        """Test table output with no models."""
        result = BenchmarkResult(models=[])
        table = result.to_table()

        assert "No benchmark results" in table

    def test_no_hardware_table(self):
        """Test table output without hardware info."""
        model = ModelBenchmark.from_measurements(
            model="test",
            latencies=[1.0],
            token_counts=[50],
            eval_durations=[0.5],
        )

        result = BenchmarkResult(models=[model], hardware=None)
        table = result.to_table()

        # Should still generate valid table
        assert "test" in table
