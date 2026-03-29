# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

import subprocess
import sys

import pytest


def test_package_builds():
    """Test package can be built."""
    try:
        import build as build_module
    except ModuleNotFoundError:
        pytest.skip("build package not installed")

    if not getattr(build_module, "__file__", None):
        pytest.skip("build package not installed")

    # Avoid local repository folders named "build" shadowing the PyPA build tool.
    # Running from a subdirectory ensures ``python -m build`` resolves the installed
    # dependency rather than a local namespace package.
    import tempfile
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory() as outdir:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "build",
                "--sdist",
                str(repo_root),
                "--outdir",
                outdir,
            ],
            cwd=repo_root / "tests",
            capture_output=True,
            text=True,
        )

    assert result.returncode == 0, result.stderr


def test_package_installs():
    """Test package can be installed"""
    # This is verified by the fact tests run
    import agentic_brain

    assert agentic_brain.__version__


def test_cli_available():
    """Test CLI is available after install"""
    result = subprocess.run(
        [sys.executable, "-m", "agentic_brain.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
