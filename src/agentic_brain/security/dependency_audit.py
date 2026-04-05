# SPDX-License-Identifier: Apache-2.0
"""
Dependency audit tooling for Agentic Brain

Performs:
 - pip-audit (CVE scanning)
 - safety (OSV / Advisory DB)
 - pip list --outdated (outdated packages)
 - pip-licenses (license inventory)
 - pipdeptree (transitive dependency analysis)

Produces JSON report and human-readable summary.

This script delegates to external CLIs. Ensure pip-audit, safety, pip-licenses and pipdeptree
are installed in the environment (CI will install them before invoking this script).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


def _run_cmd(cmd: list[str]) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        stdout = proc.stdout.strip()
        stderr = proc.stderr.strip()
        return {
            "cmd": " ".join(cmd),
            "returncode": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
        }
    except FileNotFoundError as exc:
        return {"cmd": " ".join(cmd), "error": str(exc)}


def gather_pip_audit() -> Dict[str, Any]:
    # Use python -m pip_audit for programmatic entry
    cmd = [sys.executable, "-m", "pip_audit", "--format", "json"]
    return _run_cmd(cmd)


def gather_safety() -> Dict[str, Any]:
    # safety CLI (opens a JSON report)
    cmd = [sys.executable, "-m", "safety", "check", "--json"]
    # Some safety versions install 'safety' as module; fallback to 'safety' binary
    result = _run_cmd(cmd)
    if "error" in result and "No module named" in result["error"]:
        result = _run_cmd(["safety", "check", "--json"])  # type: ignore[arg-type]
    return result


def gather_outdated() -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pip", "list", "--outdated", "--format", "json"]
    return _run_cmd(cmd)


def gather_licenses() -> Dict[str, Any]:
    # pip-licenses produces JSON when --format=json is passed
    cmd = [sys.executable, "-m", "piplicenses", "--format", "json"]
    result = _run_cmd(cmd)
    if result.get("returncode", 1) != 0:
        # fallback to pip-licenses CLI binary
        result = _run_cmd(["pip-licenses", "--format", "json"])  # type: ignore[arg-type]
    return result


def gather_transitive() -> Dict[str, Any]:
    # pipdeptree JSON output
    cmd = [sys.executable, "-m", "pipdeptree", "--json-tree"]
    result = _run_cmd(cmd)
    if result.get("returncode", 1) != 0:
        # fallback to pipdeptree binary
        result = _run_cmd(["pipdeptree", "--json-tree"])  # type: ignore[arg-type]
    return result


def assemble_report() -> Dict[str, Any]:
    report = {}
    report["pip_audit"] = gather_pip_audit()
    report["safety"] = gather_safety()
    report["outdated"] = gather_outdated()
    report["licenses"] = gather_licenses()
    report["transitive"] = gather_transitive()
    return report


def write_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def print_summary(report: Dict[str, Any]) -> None:
    # Print a short human-friendly summary to stdout
    print("Dependency Audit Summary:\n")
    pa = report.get("pip_audit", {})
    if pa.get("returncode") == 0 and pa.get("stdout"):
        try:
            findings = json.loads(pa.get("stdout", "[]"))
            if findings:
                print(f"pip-audit found {len(findings)} issues")
            else:
                print("pip-audit: no issues found")
        except Exception:
            print("pip-audit: output could not be parsed")
    else:
        print("pip-audit: not run or failed")

    sf = report.get("safety", {})
    if sf.get("returncode") == 0 and sf.get("stdout"):
        try:
            findings = json.loads(sf.get("stdout", "[]"))
            if findings:
                print(f"safety found {len(findings)} issues")
            else:
                print("safety: no issues found")
        except Exception:
            print("safety: output could not be parsed")
    else:
        print("safety: not run or failed")

    out = report.get("outdated", {})
    if out.get("returncode") == 0 and out.get("stdout"):
        try:
            outdated = json.loads(out.get("stdout", "[]"))
            if outdated:
                print(f"Outdated packages: {len(outdated)}")
            else:
                print("No outdated packages detected")
        except Exception:
            print("outdated: output could not be parsed")
    else:
        print("outdated: not run or failed")

    lic = report.get("licenses", {})
    if lic.get("returncode") == 0 and lic.get("stdout"):
        try:
            licenses = json.loads(lic.get("stdout", "[]"))
            print(f"License entries: {len(licenses)}")
        except Exception:
            print("licenses: output could not be parsed")
    else:
        print("licenses: not run or failed")

    # Transitive
    tr = report.get("transitive", {})
    if tr.get("returncode") == 0 and tr.get("stdout"):
        try:
            tree = json.loads(tr.get("stdout", "[]"))
            print(f"Transitive dependency tree nodes: {len(tree)}")
        except Exception:
            print("transitive: output could not be parsed")
    else:
        print("transitive: not run or failed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run dependency security audit and generate a JSON report.")
    parser.add_argument("--output", "-o", type=str, default="dependency_audit.json", help="Output JSON report path")
    ns = parser.parse_args(argv)

    out_path = Path(ns.output)
    report = assemble_report()
    write_report(out_path, report)
    print_summary(report)
    print(f"\nSaved full report to {out_path}\n")
    # Exit code 0 even if findings exist; CI can fail on non-zero if desired
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
