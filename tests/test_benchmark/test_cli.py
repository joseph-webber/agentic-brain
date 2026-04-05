from __future__ import annotations

from agentic_brain.cli import create_parser


def test_benchmark_suite_parser_option() -> None:
    parser = create_parser()
    args = parser.parse_args(['benchmark', '--suite', 'all'])

    assert args.command == 'benchmark'
    assert args.suite == 'all'
