#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

from __future__ import annotations

import argparse
import os
import plistlib
import re
import subprocess
import sys
import tarfile
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import urlopen

PROJECT_DIR = Path(__file__).resolve().parent.parent
LAUNCHD_TEMPLATE_DIR = PROJECT_DIR / "launchd"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LOG_DIR = PROJECT_DIR / "logs" / "launchd"
BACKUP_DIR = PROJECT_DIR / "backups" / "launchd"
DOMAIN = f"gui/{os.getuid()}"

SERVICES: dict[str, dict[str, str]] = {
    "daemon": {
        "label": "com.agentic-brain.daemon",
        "template": "com.agentic-brain.daemon.plist",
        "stdout": str(LOG_DIR / "daemon.stdout.log"),
        "stderr": str(LOG_DIR / "daemon.stderr.log"),
    },
    "backup": {
        "label": "com.agentic-brain.backup",
        "template": "com.agentic-brain.backup.plist",
        "stdout": str(LOG_DIR / "backup.stdout.log"),
        "stderr": str(LOG_DIR / "backup.stderr.log"),
    },
    "health": {
        "label": "com.agentic-brain.health",
        "template": "com.agentic-brain.health.plist",
        "stdout": str(LOG_DIR / "health.stdout.log"),
        "stderr": str(LOG_DIR / "health.stderr.log"),
    },
}


class LaunchdError(RuntimeError):
    """Raised when a launchd operation fails."""


def info(message: str) -> None:
    print(f"[INFO] {message}")


def success(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}", file=sys.stderr)


def run_command(
    command: list[str],
    *,
    check: bool = True,
    capture_output: bool = True,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=capture_output,
            env=env,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        raise LaunchdError(f"Required command not found: {command[0]}") from exc

    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise LaunchdError(f"{' '.join(command)} failed: {detail or 'unknown error'}")
    return result


def ensure_macos() -> None:
    if sys.platform != "darwin":
        raise LaunchdError("launchd-manager.py only supports macOS")


def ensure_directories() -> None:
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_DIR / "run" / "launchd").mkdir(parents=True, exist_ok=True)


def installed_plist_path(service_name: str) -> Path:
    return LAUNCH_AGENTS_DIR / SERVICES[service_name]["template"]


def render_plist(template_path: Path) -> bytes:
    rendered = template_path.read_text(encoding="utf-8")
    replacements = {
        "__HOME__": str(Path.home()),
        "__PROJECT_DIR__": str(PROJECT_DIR),
        "__PYTHON__": sys.executable,
    }
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    try:
        parsed = plistlib.loads(rendered.encode("utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        raise LaunchdError(f"Invalid plist template: {template_path}") from exc
    return plistlib.dumps(parsed, sort_keys=False)


def validate_plist(plist_path: Path) -> None:
    run_command(["plutil", "-lint", str(plist_path)])


def unload_service(label: str, plist_path: Path) -> None:
    for command in (
        ["launchctl", "bootout", DOMAIN, str(plist_path)],
        ["launchctl", "bootout", f"{DOMAIN}/{label}"],
    ):
        result = run_command(command, check=False)
        if result.returncode == 0:
            return


def load_service(label: str, plist_path: Path) -> None:
    result = run_command(
        ["launchctl", "bootstrap", DOMAIN, str(plist_path)], check=False
    )
    if result.returncode != 0 and "service already loaded" in (
        (result.stderr or "") + (result.stdout or "")
    ).lower():
        unload_service(label, plist_path)
        run_command(["launchctl", "bootstrap", DOMAIN, str(plist_path)])
    elif result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise LaunchdError(f"Failed to bootstrap {label}: {detail or 'unknown error'}")

    run_command(["launchctl", "enable", f"{DOMAIN}/{label}"], check=False)


def install(_: argparse.Namespace) -> int:
    ensure_macos()
    ensure_directories()

    for service_name, metadata in SERVICES.items():
        template_path = LAUNCHD_TEMPLATE_DIR / metadata["template"]
        if not template_path.exists():
            raise LaunchdError(f"Missing launchd template: {template_path}")

        target_path = installed_plist_path(service_name)
        target_path.write_bytes(render_plist(template_path))
        validate_plist(target_path)
        unload_service(metadata["label"], target_path)
        load_service(metadata["label"], target_path)
        success(f"Installed {metadata['label']} -> {target_path}")

    return 0


def uninstall(_: argparse.Namespace) -> int:
    ensure_macos()

    for service_name, metadata in SERVICES.items():
        target_path = installed_plist_path(service_name)
        unload_service(metadata["label"], target_path)
        if target_path.exists():
            target_path.unlink()
            success(f"Removed {target_path}")
        else:
            info(f"{target_path} not installed")

    return 0


def parse_launchctl_print(output: str) -> dict[str, str]:
    details: dict[str, str] = {}
    patterns = {
        "state": r"\bstate = ([^\n;]+)",
        "pid": r"\bpid = (\d+)",
        "last_exit_code": r"\blast exit code = (-?\d+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            details[key] = match.group(1)
    return details


def service_details(service_name: str) -> dict[str, str]:
    metadata = SERVICES[service_name]
    plist_path = installed_plist_path(service_name)
    details = {
        "label": metadata["label"],
        "installed": "yes" if plist_path.exists() else "no",
        "plist": str(plist_path),
        "stdout": metadata["stdout"],
        "stderr": metadata["stderr"],
        "loaded": "no",
        "state": "unloaded",
    }

    result = run_command(
        ["launchctl", "print", f"{DOMAIN}/{metadata['label']}"], check=False
    )
    if result.returncode == 0:
        details["loaded"] = "yes"
        parsed = parse_launchctl_print(result.stdout)
        details.update(parsed)
        details["state"] = parsed.get("state", "loaded")

    return details


def status(_: argparse.Namespace) -> int:
    ensure_macos()

    for service_name in SERVICES:
        details = service_details(service_name)
        print(f"{details['label']}:")
        print(f"  installed:  {details['installed']}")
        print(f"  loaded:     {details['loaded']}")
        print(f"  state:      {details['state']}")
        if "pid" in details:
            print(f"  pid:        {details['pid']}")
        if "last_exit_code" in details:
            print(f"  exit code:  {details['last_exit_code']}")
        print(f"  plist:      {details['plist']}")
        print(f"  stdout log: {details['stdout']}")
        print(f"  stderr log: {details['stderr']}")
        print()

    return 0


def tail_lines(path: Path, lines: int) -> list[str]:
    if not path.exists():
        return ["<missing>"]
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return list(deque(handle, maxlen=lines)) or ["<empty>\n"]


def logs(args: argparse.Namespace) -> int:
    ensure_macos()
    selected = [args.label] if args.label else list(SERVICES.keys())

    for service_name in selected:
        metadata = SERVICES[service_name]
        for stream_name in ("stdout", "stderr"):
            log_path = Path(metadata[stream_name])
            print(f"== {metadata['label']} {stream_name} ({log_path}) ==")
            for line in tail_lines(log_path, args.lines):
                print(line.rstrip("\n"))
            print()

    return 0


def python_runtime() -> tuple[str, dict[str, str]]:
    env = os.environ.copy()
    python_path = str(PROJECT_DIR / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        f"{python_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else python_path
    )

    candidates = [
        PROJECT_DIR / ".venv" / "bin" / "python",
        PROJECT_DIR / "venv" / "bin" / "python",
        Path(sys.executable),
    ]

    for candidate in candidates:
        if not candidate.exists():
            continue
        result = run_command(
            [
                str(candidate),
                "-c",
                "import fastapi, uvicorn; import agentic_brain.api.server",
            ],
            check=False,
            env=env,
        )
        if result.returncode == 0:
            return str(candidate), env

    raise LaunchdError(
        "No usable Python runtime found. Install project dependencies first."
    )


def run_daemon(_: argparse.Namespace) -> int:
    runtime_python, env = python_runtime()
    host = os.environ.get("AGENTIC_HOST", "127.0.0.1")
    port = os.environ.get("AGENTIC_PORT", "8000")
    workers = os.environ.get("AGENTIC_WORKERS", "1")

    command = [
        runtime_python,
        "-m",
        "agentic_brain.cli",
        "serve",
        "--host",
        host,
        "--port",
        port,
        "--workers",
        workers,
    ]
    info(f"Launching agentic-brain daemon on http://{host}:{port}")
    process = subprocess.run(command, cwd=PROJECT_DIR, env=env, check=False)
    return process.returncode


def iter_backup_paths() -> Iterable[Path]:
    excluded_roots = {
        ".git",
        ".venv",
        "venv",
        "build",
        "dist",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "logs",
        "backups",
    }

    for path in PROJECT_DIR.rglob("*"):
        relative = path.relative_to(PROJECT_DIR)
        if not relative.parts:
            continue
        if any(part in excluded_roots for part in relative.parts):
            continue
        yield path


def prune_old_backups(keep: int) -> None:
    archives = sorted(BACKUP_DIR.glob("agentic-brain-*.tar.gz"))
    for archive in archives[:-keep]:
        archive.unlink(missing_ok=True)


def run_backup(_: argparse.Namespace) -> int:
    ensure_directories()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = BACKUP_DIR / f"agentic-brain-{timestamp}.tar.gz"
    info(f"Creating backup archive at {archive_path}")

    with tarfile.open(archive_path, "w:gz") as archive:
        for path in iter_backup_paths():
            archive.add(path, arcname=Path("agentic-brain") / path.relative_to(PROJECT_DIR))

    keep_count = int(os.environ.get("AGENTIC_BACKUP_KEEP", "48"))
    prune_old_backups(keep_count)
    success(f"Backup created: {archive_path}")
    return 0


def url_is_healthy(url: str) -> bool:
    try:
        with urlopen(url, timeout=5) as response:
            return 200 <= response.status < 300
    except URLError:
        return False


def daemon_loaded() -> bool:
    result = run_command(
        ["launchctl", "print", f"{DOMAIN}/{SERVICES['daemon']['label']}"], check=False
    )
    return result.returncode == 0


def run_health_check(_: argparse.Namespace) -> int:
    ensure_macos()
    health_url = os.environ.get("AGENTIC_HEALTH_URL", "http://127.0.0.1:8000/health")

    if url_is_healthy(health_url):
        success(f"Health check passed: {health_url}")
        return 0

    warn(f"Health check failed: {health_url}")
    daemon_label = SERVICES["daemon"]["label"]
    daemon_plist = installed_plist_path("daemon")

    if daemon_plist.exists() and not daemon_loaded():
        info(f"Daemon not loaded. Bootstrapping {daemon_label}")
        load_service(daemon_label, daemon_plist)
    else:
        info(f"Attempting kickstart for {daemon_label}")
        run_command(["launchctl", "kickstart", "-k", f"{DOMAIN}/{daemon_label}"], check=False)

    time.sleep(5)
    if url_is_healthy(health_url):
        success("Health check recovered after restart")
        return 0

    raise LaunchdError("Health check failed and daemon did not recover")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage agentic-brain launchd services")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install_parser = subparsers.add_parser("install", help="Install all LaunchAgents")
    install_parser.set_defaults(func=install)

    uninstall_parser = subparsers.add_parser(
        "uninstall", help="Uninstall all LaunchAgents"
    )
    uninstall_parser.set_defaults(func=uninstall)

    status_parser = subparsers.add_parser("status", help="Show LaunchAgent status")
    status_parser.set_defaults(func=status)

    logs_parser = subparsers.add_parser("logs", help="Show recent service logs")
    logs_parser.add_argument(
        "--label",
        choices=list(SERVICES.keys()),
        help="Limit output to a single service",
    )
    logs_parser.add_argument(
        "--lines", type=int, default=40, help="Number of lines to show per log"
    )
    logs_parser.set_defaults(func=logs)

    run_daemon_parser = subparsers.add_parser("run-daemon", help=argparse.SUPPRESS)
    run_daemon_parser.set_defaults(func=run_daemon)

    run_backup_parser = subparsers.add_parser("run-backup", help=argparse.SUPPRESS)
    run_backup_parser.set_defaults(func=run_backup)

    run_health_parser = subparsers.add_parser(
        "run-health-check", help=argparse.SUPPRESS
    )
    run_health_parser.set_defaults(func=run_health_check)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except LaunchdError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        warn("Interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
