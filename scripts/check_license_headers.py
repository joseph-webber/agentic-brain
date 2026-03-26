#!/usr/bin/env python3
"""Verify all Python files use Apache-2.0 SPDX headers.

This script is used in CI to ensure license consistency:

- Every ``.py`` file under ``src/`` must contain exactly one
  ``SPDX-License-Identifier: Apache-2.0`` comment.
- The SPDX comment must appear near the top of the file
  (within the first 10 lines), after any optional shebang
  and encoding comments.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List

APACHE_ID = "Apache-2.0"


def find_repo_root() -> Path:
    """Return the repository root (parent of this scripts directory)."""
    return Path(__file__).resolve().parents[1]


def iter_python_files(*roots: Path) -> List[Path]:
    """Return all Python files under the provided roots."""

    python_files: List[Path] = []
    for root in roots:
        if not root.exists():
            print(f"⚠️  Skipping missing path: {root}", file=sys.stderr)
            continue
        python_files.extend(sorted(root.rglob("*.py")))
    return python_files


def check_file(path: Path, repo_root: Path) -> List[str]:
    """Check a single file for a correct Apache-2.0 SPDX header.

    Returns a list of human-readable error messages for this file.
    """

    errors: List[str] = []

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("could not read file as UTF-8")
        return errors

    lines = text.splitlines()

    # Look for SPDX comment lines near the top of the file
    spdx_matches: List[tuple[int, str]] = []
    for idx, line in enumerate(lines[:50]):
        if re.match(r"\s*#\s*SPDX-License-Identifier:", line):
            spdx_matches.append((idx, line))

    if not spdx_matches:
        errors.append("missing SPDX-License-Identifier comment")
        return errors

    if len(spdx_matches) > 1:
        line_numbers = ", ".join(str(i + 1) for i, _ in spdx_matches)
        errors.append(f"multiple SPDX headers found (lines {line_numbers})")
        return errors

    idx, line = spdx_matches[0]

    # Extract the license identifier
    m = re.search(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)", line)
    if not m:
        errors.append("could not parse SPDX license identifier")
        return errors

    license_id = m.group(1)
    if license_id != APACHE_ID:
        errors.append(
            f"unexpected SPDX license id '{license_id}' (expected '{APACHE_ID}')"
        )

    # Ensure header is close to the top of the file (after shebang/encoding)
    if idx > 10:
        errors.append(f"SPDX header appears too late in file (line {idx + 1})")

    return errors


def main() -> None:
    repo_root = find_repo_root()
    src_root = repo_root / "src"
    tests_root = repo_root / "tests"

    if not src_root.exists():
        print(f"ERROR: src directory not found at {src_root}", file=sys.stderr)
        sys.exit(1)

    python_files = iter_python_files(src_root, tests_root)
    all_errors: Dict[Path, List[str]] = {}

    for path in python_files:
        errors = check_file(path, repo_root)
        if errors:
            all_errors[path] = errors

    if all_errors:
        print("License header check failed:", file=sys.stderr)
        for path, errors in sorted(all_errors.items(), key=lambda item: str(item[0])):
            rel = path.relative_to(repo_root)
            print(f" - {rel}:", file=sys.stderr)
            for err in errors:
                print(f"    * {err}", file=sys.stderr)
        sys.exit(1)

    print(f"All {len(python_files)} Python files have correct Apache-2.0 SPDX headers.")
    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover
    main()
