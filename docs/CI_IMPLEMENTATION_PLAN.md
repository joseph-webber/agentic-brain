# CI Implementation Plan – SPDX Header Enforcement

**Date:** 2026-03-26

## Root Cause

Recent CI failures in the `license-check` job stemmed from developers adding new
`tests/*.py` files without the required Apache-2.0 SPDX header. The local
`scripts/check_license_headers.py` helper only scanned `src/`, so engineers
running it before commit received a false green signal. CI later scanned both
`src/` and `tests/`, causing a hard failure.

## Fastest Path to Green

1. Expand `scripts/check_license_headers.py` to scan **both** `src/` and `tests/`.
2. Ask contributors to run the script (or `just license-check`) before opening PRs.
3. Update `.github/workflows/ci.yml` so the `license-check` job executes the helper
   script (`python3 scripts/check_license_headers.py`) instead of re-implementing
   the logic with inline shell. CI and local enforcement now share a single source
   of truth.

## Deferable Work

- Extending the script to cover other languages or directories (e.g., `skills/`)
  can wait until needed.
- Automating header insertion via `pre-commit` hooks is optional; the immediate
  blocker is simply detection consistency between local dev and CI.

## Critical Next Steps

- Merge the script update so every engineer catches missing headers locally.
- Broadcast the change in the strategy channel and link to this document.
