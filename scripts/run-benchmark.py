#!/usr/bin/env python3
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

"""Run Agentic Brain benchmarks and compare against historical baselines."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentic_brain.benchmark import (
    BenchmarkConfig,
    BenchmarkReporter,
    BrainBenchmark,
    OutputFormat,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Agentic Brain benchmarks with historical trend tracking.",
    )
    parser.add_argument(
        "--models",
        default="llama3.2:3b",
        help="Comma-separated model list for the LLM latency benchmark.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Measured iterations per benchmark.",
    )
    parser.add_argument(
        "--warmup",
        type=int,
        default=2,
        help="Warmup iterations before recording samples.",
    )
    parser.add_argument(
        "--prompt",
        default="Explain what Python is in exactly 3 sentences.",
        help="Prompt used for the LLM benchmark.",
    )
    parser.add_argument(
        "--ollama-host",
        default="http://localhost:11434",
        help="Ollama base URL.",
    )
    parser.add_argument(
        "--history-dir",
        default=str(PROJECT_ROOT / ".benchmarks" / "agentic-brain"),
        help="Directory for persisted benchmark history JSON files.",
    )
    parser.add_argument(
        "--output",
        help="Optional file path to write the resulting JSON payload.",
    )
    parser.add_argument(
        "--benchmark-name",
        default="default",
        help="Logical name for the benchmark stream.",
    )
    parser.add_argument(
        "--neo4j-uri",
        help="Neo4j connection URI. If omitted, NEO4J_URI is used when available.",
    )
    parser.add_argument(
        "--neo4j-query",
        default="RETURN 1 AS ok",
        help="Cypher query used for the Neo4j latency benchmark.",
    )
    parser.add_argument(
        "--voice-command",
        help="Custom command used for the voice latency benchmark.",
    )
    parser.add_argument(
        "--voice-text",
        default="Agentic Brain benchmark voice check.",
        help="Short utterance used for voice synthesis benchmarking.",
    )
    parser.add_argument(
        "--context-payload",
        help="Optional context payload used when measuring serialized context size.",
    )
    parser.add_argument(
        "--format",
        choices=[fmt.value for fmt in OutputFormat],
        default=OutputFormat.JSON.value,
        help="Primary output format. JSON is recommended for automation.",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip the LLM response-time benchmark.",
    )
    parser.add_argument(
        "--skip-neo4j",
        action="store_true",
        help="Skip the Neo4j latency benchmark.",
    )
    parser.add_argument(
        "--skip-voice",
        action="store_true",
        help="Skip the voice synthesis benchmark.",
    )
    parser.add_argument(
        "--no-history",
        action="store_true",
        help="Do not persist the current run in the history directory.",
    )
    parser.add_argument(
        "--no-compare",
        action="store_true",
        help="Do not compare the current run with the latest historical baseline.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    models = [item.strip() for item in args.models.split(",") if item.strip()]
    config = BenchmarkConfig(
        models=models,
        iterations=args.iterations,
        warmup_iterations=args.warmup,
        prompt=args.prompt,
        ollama_host=args.ollama_host,
        output_file=Path(args.output) if args.output else None,
        output_format=OutputFormat(args.format),
        history_dir=Path(args.history_dir),
        benchmark_name=args.benchmark_name,
        compare_with_history=not args.no_compare,
        record_history=not args.no_history,
        enable_llm=not args.skip_llm,
        enable_neo4j=not args.skip_neo4j,
        enable_voice=not args.skip_voice,
        neo4j_uri=args.neo4j_uri,
        neo4j_query=args.neo4j_query,
        voice_command=args.voice_command,
        voice_text=args.voice_text,
        context_payload=args.context_payload,
    )

    runner = BrainBenchmark(config)
    result = await runner.run()

    baseline_path = None
    if config.compare_with_history:
        baseline_path = BenchmarkReporter.latest_history_file(config.history_dir)
        if baseline_path and baseline_path.exists():
            baseline = BenchmarkReporter.load_result(baseline_path)
            result.comparison = BenchmarkReporter.compare(
                result,
                baseline,
                baseline_path=baseline_path,
            )

    payload = result.to_json(indent=2)
    if config.output_file:
        config.output_file.parent.mkdir(parents=True, exist_ok=True)
        config.output_file.write_text(payload, encoding="utf-8")

    if config.record_history:
        config.history_dir.mkdir(parents=True, exist_ok=True)
        history_file = config.history_dir / (
            f"{result.timestamp.replace(':', '').replace('-', '')}.json"
        )
        BenchmarkReporter.save_result(result, history_file)

    if config.output_format == OutputFormat.TABLE:
        print(result.to_table())
    elif config.output_format == OutputFormat.MARKDOWN:
        print(result.to_markdown())
    else:
        print(payload)

    return 2 if result.comparison and result.comparison.has_regressions else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
