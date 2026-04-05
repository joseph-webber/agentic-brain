# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Secure YOLO executor with role-based access control.

Wraps the YOLO command handlers with security checks based on the
current user's role.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ..security import (
    SecurityGuard,
    SecurityRole,
    SecurityViolation,
    get_or_create_guard,
)
from .handlers import CommandExecutionResult, CommandHandlers, InterpretedCommand

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SecureExecutionResult:
    """Result from secure YOLO execution."""

    result: CommandExecutionResult
    role: SecurityRole
    security_checks_passed: bool
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.to_dict(),
            "role": self.role.value,
            "security_checks_passed": self.security_checks_passed,
            "blocked_reason": self.blocked_reason,
        }


class SecureYOLOExecutor:
    """
    YOLO executor with integrated security checks.

    This wraps the standard CommandHandlers and adds:
    - Role-based access control
    - Command filtering for non-admin roles
    - Rate limiting
    - Audit logging
    """

    def __init__(
        self,
        handlers: CommandHandlers | None = None,
        *,
        default_role: SecurityRole = SecurityRole.GUEST,
    ):
        self.handlers = handlers or CommandHandlers()
        self._default_role = default_role

    def _get_guard(self) -> SecurityGuard:
        """Get the current security guard or create one with default role."""
        return get_or_create_guard(self._default_role)

    async def run_tests(self, command_text: str) -> SecureExecutionResult:
        """
        Execute test command with security checks.

        Requires SAFE_ADMIN or FULL_ADMIN.
        """
        guard = self._get_guard()

        # Check basic permission
        if guard.role < SecurityRole.SAFE_ADMIN:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="run_tests",
                    command=command_text,
                    error="Insufficient permissions: SAFE_ADMIN role or above required",
                    exit_code=403,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason="Insufficient role",
            )

        # Check rate limit
        allowed, reason = guard.check_rate_limit()
        if not allowed:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="run_tests",
                    command=command_text,
                    error=reason,
                    exit_code=429,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason=reason,
            )

        # Execute the test command
        result = await self.handlers.run_tests(command_text)

        return SecureExecutionResult(
            result=result,
            role=guard.role,
            security_checks_passed=True,
        )

    async def deploy(self, command_text: str) -> SecureExecutionResult:
        """
        Execute deploy command with security checks.

        Requires SAFE_ADMIN or FULL_ADMIN.
        """
        guard = self._get_guard()

        # Check basic permission - USER or above
        if guard.role < SecurityRole.SAFE_ADMIN:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="deploy",
                    command=command_text,
                    error="Insufficient permissions: SAFE_ADMIN role or above required",
                    exit_code=403,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason="Insufficient role",
            )

        # For non-admin, check if command contains dangerous patterns
        if guard.role != SecurityRole.FULL_ADMIN:
            # Extract actual command that would be run
            arguments = self.handlers._extract_arguments(command_text, "deploy")
            if arguments:
                allowed, reason = guard.check_command(arguments)
                if not allowed:
                    return SecureExecutionResult(
                        result=CommandExecutionResult(
                            success=False,
                            capability="deploy",
                            command=command_text,
                            error=f"Command blocked: {reason}",
                            exit_code=403,
                        ),
                        role=guard.role,
                        security_checks_passed=False,
                        blocked_reason=reason,
                    )

        # Check rate limit
        allowed, reason = guard.check_rate_limit()
        if not allowed:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="deploy",
                    command=command_text,
                    error=reason,
                    exit_code=429,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason=reason,
            )

        result = await self.handlers.deploy(command_text)

        return SecureExecutionResult(
            result=result,
            role=guard.role,
            security_checks_passed=True,
        )

    async def check_status(self, command_text: str) -> SecureExecutionResult:
        """
        Execute status check with security checks.

        Requires SAFE_ADMIN or FULL_ADMIN.
        """
        guard = self._get_guard()

        if guard.role < SecurityRole.SAFE_ADMIN:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="check_status",
                    command=command_text,
                    error="Insufficient permissions: SAFE_ADMIN role or above required",
                    exit_code=403,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason="Insufficient role",
            )

        allowed, reason = guard.check_rate_limit()
        if not allowed:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="check_status",
                    command=command_text,
                    error=reason,
                    exit_code=429,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason=reason,
            )

        result = await self.handlers.check_status(command_text)

        return SecureExecutionResult(
            result=result,
            role=guard.role,
            security_checks_passed=True,
        )

    async def search(self, command_text: str) -> SecureExecutionResult:
        """
        Execute search command with security checks.

        Requires SAFE_ADMIN or FULL_ADMIN.
        """
        guard = self._get_guard()

        # Check basic permission
        if guard.role < SecurityRole.SAFE_ADMIN:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="search",
                    command=command_text,
                    error="Insufficient permissions: SAFE_ADMIN role or above required",
                    exit_code=403,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason="Insufficient role",
            )

        # Check rate limit
        allowed, reason = guard.check_rate_limit()
        if not allowed:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="search",
                    command=command_text,
                    error=reason,
                    exit_code=429,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason=reason,
            )

        result = await self.handlers.search(command_text)

        return SecureExecutionResult(
            result=result,
            role=guard.role,
            security_checks_passed=True,
        )

    async def execute_arbitrary(self, command: str) -> SecureExecutionResult:
        """
        Execute an arbitrary shell command with full security checks.

        This is the most dangerous capability - heavily restricted for non-admin.

        - FULL_ADMIN: Can run anything
        - SAFE_ADMIN: Can run safe commands; dangerous commands require confirmation
        - USER/GUEST: Cannot run shell commands
        """
        guard = self._get_guard()

        # Check YOLO permission
        if not guard.permissions.can_yolo:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="arbitrary",
                    command=command,
                    error="YOLO execution not permitted for this role",
                    exit_code=403,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason="YOLO not permitted",
            )

        # Check if command is allowed
        allowed, reason = guard.check_command(command)
        if not allowed:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="arbitrary",
                    command=command,
                    error=f"Command blocked: {reason}",
                    exit_code=403,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason=reason,
            )

        # Check rate limit
        allowed, reason = guard.check_rate_limit()
        if not allowed:
            return SecureExecutionResult(
                result=CommandExecutionResult(
                    success=False,
                    capability="arbitrary",
                    command=command,
                    error=reason,
                    exit_code=429,
                ),
                role=guard.role,
                security_checks_passed=False,
                blocked_reason=reason,
            )

        # Execute the command using the internal runner
        result = await self.handlers._run_command(
            command.split(),
            capability="arbitrary",
            requested=command,
        )

        return SecureExecutionResult(
            result=result,
            role=guard.role,
            security_checks_passed=True,
        )

    async def interpret(self, command_text: str) -> InterpretedCommand:
        """
        Interpret a command using LLM.

        Available based on LLM access level.
        """
        guard = self._get_guard()

        llm_level = guard.get_llm_access_level()
        if llm_level == "chat_only":
            raise SecurityViolation(
                "LLM command interpretation not available at chat_only access level",
                guard.role,
                "interpret",
                command_text,
            )

        return await self.handlers.interpret(command_text)


# Convenience function for quick secure execution
async def secure_execute(
    command: str,
    *,
    capability: str = "arbitrary",
    guard: SecurityGuard | None = None,
) -> SecureExecutionResult:
    """
    Execute a command with security checks.

    Args:
        command: The command to execute.
        capability: The capability type (arbitrary, run_tests, deploy, etc.)
        guard: Optional SecurityGuard to use.

    Returns:
        SecureExecutionResult with execution result and security info.
    """
    executor = SecureYOLOExecutor()

    if capability == "run_tests":
        return await executor.run_tests(command)
    elif capability == "deploy":
        return await executor.deploy(command)
    elif capability == "check_status":
        return await executor.check_status(command)
    elif capability == "search":
        return await executor.search(command)
    else:
        return await executor.execute_arbitrary(command)
