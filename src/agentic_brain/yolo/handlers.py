# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CommandExecutionResult:
    """Result returned by a YOLO capability handler."""

    success: bool
    capability: str
    command: str
    output: str = ""
    error: str | None = None
    exit_code: int = 0
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "capability": self.capability,
            "command": self.command,
            "output": self.output,
            "error": self.error,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class InterpretedCommand:
    """Normalized command returned by Claude interpretation."""

    capability: str
    normalized_command: str
    reasoning: str = ""


class CommandHandlers:
    """Capability-specific YOLO command handlers."""

    _TEST_EXECUTABLES = {"pytest", "python", "python3", "tox", "nox", "uv"}

    def __init__(
        self,
        *,
        working_directory: str | os.PathLike[str] | None = None,
        test_command: str | None = None,
        deploy_command: str | None = None,
        status_provider: Callable[[], dict[str, Any]] | None = None,
        command_timeout_seconds: int = 900,
        claude_model: str | None = None,
    ) -> None:
        self.working_directory = Path(
            working_directory
            or os.getenv("YOLO_WORKING_DIRECTORY")
            or Path.cwd()
        ).resolve()
        self.test_command = test_command or os.getenv("YOLO_TEST_COMMAND", "pytest")
        self.deploy_command = deploy_command or os.getenv("YOLO_DEPLOY_COMMAND")
        self.status_provider = status_provider
        self.command_timeout_seconds = int(
            os.getenv("YOLO_COMMAND_TIMEOUT", str(command_timeout_seconds))
        )
        self.claude_model = claude_model or os.getenv(
            "YOLO_CLAUDE_MODEL", "claude-3-5-sonnet-20241022"
        )

    async def run_tests(self, command_text: str) -> CommandExecutionResult:
        """Execute the configured test runner."""
        arguments = self._extract_arguments(command_text, "run tests")
        command = self._build_test_command(arguments)
        return await self._run_command(command, capability="run_tests", requested=command_text)

    async def deploy(self, command_text: str) -> CommandExecutionResult:
        """Execute a deployment command."""
        arguments = self._extract_arguments(command_text, "deploy")
        if arguments:
            command = shlex.split(arguments)
        elif self.deploy_command:
            command = shlex.split(self.deploy_command)
        else:
            return CommandExecutionResult(
                success=False,
                capability="deploy",
                command=command_text,
                error=(
                    "No deploy command configured. Set YOLO_DEPLOY_COMMAND or provide "
                    "an explicit deploy command."
                ),
                exit_code=64,
            )
        return await self._run_command(command, capability="deploy", requested=command_text)

    async def check_status(self, command_text: str) -> CommandExecutionResult:
        """Return processor/application status without shelling out."""
        started = time.perf_counter()
        snapshot = self.status_provider() if self.status_provider else {}
        arguments = self._extract_arguments(command_text, "check status")
        payload: Any = snapshot

        if arguments:
            key = arguments.strip().lower().replace(" ", "_")
            payload = snapshot.get(key, snapshot.get(arguments.strip(), snapshot))

        return CommandExecutionResult(
            success=True,
            capability="check_status",
            command=command_text,
            output=json.dumps(payload, indent=2, sort_keys=True, default=str),
            duration_ms=int((time.perf_counter() - started) * 1000),
            metadata={"keys": sorted(snapshot.keys()) if isinstance(snapshot, dict) else []},
        )

    async def search(self, command_text: str) -> CommandExecutionResult:
        """Run a code search using ripgrep."""
        arguments = self._extract_arguments(command_text, "search")
        if not arguments:
            return CommandExecutionResult(
                success=False,
                capability="search",
                command=command_text,
                error="Search command requires a query, e.g. 'search YOLOCommandProcessor'.",
                exit_code=64,
            )

        if shutil.which("rg") is None:
            return CommandExecutionResult(
                success=False,
                capability="search",
                command=command_text,
                error="ripgrep (rg) is not installed or not available on PATH.",
                exit_code=127,
            )

        command = [
            "rg",
            "-n",
            "-S",
            "--max-count",
            "50",
            "--max-columns",
            "240",
            arguments,
            str(self.working_directory),
        ]
        result = await self._run_command(command, capability="search", requested=command_text)
        if result.exit_code == 1 and not result.output.strip():
            result.success = True
            result.output = "No matches found."
            result.error = None
            result.metadata["matches"] = 0
        return result

    async def interpret(self, command_text: str) -> InterpretedCommand:
        """Use Claude to normalize an unknown YOLO command into a supported capability."""
        from agentic_brain.router.config import Provider
        from agentic_brain.router.routing import get_router

        system_prompt = (
            "You classify operational YOLO commands for an agent runner. "
            "Return ONLY JSON with keys capability, normalized_command, reasoning. "
            "capability must be one of run_tests, deploy, check_status, search. "
            "normalized_command must start with one of: 'run tests', 'deploy', "
            "'check status', 'search'. Keep reasoning short."
        )
        router = get_router()
        response = await router.chat(
            command_text,
            system=system_prompt,
            provider=Provider.ANTHROPIC,
            model=self.claude_model,
            temperature=0.0,
            use_cache=False,
        )

        try:
            payload = json.loads(response.content)
        except json.JSONDecodeError as exc:  # pragma: no cover - depends on remote LLM
            logger.warning("Claude interpretation returned non-JSON output: %s", response.content)
            raise ValueError("Claude interpretation did not return valid JSON") from exc

        capability = str(payload.get("capability", "")).strip()
        normalized = str(payload.get("normalized_command", "")).strip()
        reasoning = str(payload.get("reasoning", "")).strip()

        if capability not in {"run_tests", "deploy", "check_status", "search"}:
            raise ValueError(f"Unsupported capability from Claude: {capability}")
        if not normalized:
            raise ValueError("Claude interpretation missing normalized_command")

        return InterpretedCommand(
            capability=capability,
            normalized_command=normalized,
            reasoning=reasoning,
        )

    def _build_test_command(self, arguments: str) -> list[str]:
        base = shlex.split(self.test_command)
        if not arguments:
            return base

        tokens = shlex.split(arguments)
        if tokens and tokens[0] in self._TEST_EXECUTABLES:
            return tokens
        return [*base, *tokens]

    @staticmethod
    def _extract_arguments(command_text: str, prefix: str) -> str:
        text = command_text.strip()
        lowered = text.lower()
        prefixes = [prefix, prefix.replace("check status", "status")]
        for candidate in prefixes:
            if lowered.startswith(candidate):
                return text[len(candidate) :].strip(" :")
        return ""

    async def _run_command(
        self,
        command: list[str],
        *,
        capability: str,
        requested: str,
    ) -> CommandExecutionResult:
        started = time.perf_counter()

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self.working_directory),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return CommandExecutionResult(
                success=False,
                capability=capability,
                command=requested,
                error=f"Executable not found: {command[0]}",
                exit_code=127,
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata={"resolved_command": command},
            )
        except Exception as exc:
            logger.exception("Failed to start YOLO command")
            return CommandExecutionResult(
                success=False,
                capability=capability,
                command=requested,
                error=str(exc),
                exit_code=1,
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata={"resolved_command": command},
            )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.command_timeout_seconds
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return CommandExecutionResult(
                success=False,
                capability=capability,
                command=requested,
                error=(
                    f"Command timed out after {self.command_timeout_seconds} seconds"
                ),
                exit_code=124,
                duration_ms=int((time.perf_counter() - started) * 1000),
                metadata={"resolved_command": command},
            )

        output = stdout.decode("utf-8", errors="replace").strip()
        error = stderr.decode("utf-8", errors="replace").strip()
        duration_ms = int((time.perf_counter() - started) * 1000)
        returncode = process.returncode or 0

        metadata: dict[str, Any] = {"resolved_command": command}
        if capability == "search" and returncode == 0:
            metadata["matches"] = sum(1 for line in output.splitlines() if line.strip())

        return CommandExecutionResult(
            success=returncode == 0,
            capability=capability,
            command=requested,
            output=output,
            error=error or None,
            exit_code=returncode,
            duration_ms=duration_ms,
            metadata=metadata,
        )
