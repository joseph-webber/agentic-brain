#!/usr/bin/env python3
"""Download and prepare Kokoro-82M for agentic-brain voice routing."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

KOKORO_REPO_ID = "hexgrad/Kokoro-82M"
DEFAULT_CACHE = Path.home() / ".cache" / "kokoro-82m"


def install_python_dependencies(project_root: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", f"{project_root}[voice-kokoro]"],
        check=True,
    )


def download_snapshot(target_dir: Path) -> None:
    from huggingface_hub import snapshot_download

    snapshot_download(
        repo_id=KOKORO_REPO_ID,
        local_dir=str(target_dir),
        local_dir_use_symlinks=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=DEFAULT_CACHE,
        help="Directory where the Kokoro model snapshot should live.",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="Install the optional Python dependencies before downloading.",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    if args.install_deps:
        install_python_dependencies(project_root)

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    download_snapshot(args.cache_dir)

    print("Kokoro setup complete")
    print(f"Model cache: {args.cache_dir}")
    print(f"Source repo: {KOKORO_REPO_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
