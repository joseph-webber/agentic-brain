#!/usr/bin/env python3
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

"""Generate a quarterly topic governance audit for agentic-brain."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from agentic_brain.core.neo4j_pool import configure_pool
from agentic_brain.graph import TopicHub, render_audit_report


def create_parser() -> argparse.ArgumentParser:
    """Create the standalone quarterly audit parser."""
    parser = argparse.ArgumentParser(
        prog="quarterly-audit.py",
        description="Generate a quarterly topic governance report for GraphRAG topics.",
    )
    parser.add_argument(
        "--uri",
        default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
        help="Neo4j connection URI (env: NEO4J_URI)",
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("NEO4J_USER", "neo4j"),
        help="Neo4j username (env: NEO4J_USER)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("NEO4J_PASSWORD"),
        help="Neo4j password (env: NEO4J_PASSWORD)",
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("NEO4J_DATABASE", "neo4j"),
        help="Neo4j database (env: NEO4J_DATABASE)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of merge suggestions to include (default: 10)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "text", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional file path for the rendered report",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the quarterly topic governance audit."""
    parser = create_parser()
    args = parser.parse_args(argv)

    configure_pool(
        uri=args.uri,
        user=args.username,
        password=args.password,
        database=args.database,
    )

    report = TopicHub().build_quarterly_audit(limit=args.limit)
    rendered_report = render_audit_report(report, format=args.format)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered_report.rstrip() + "\n", encoding="utf-8")

    print(rendered_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
