# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Security guards and decorators for role-based access control.

Provides:
- SecurityGuard class for checking permissions
- Decorators for protecting functions
- Integration with YOLO executor
"""

from __future__ import annotations

import functools
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, ParamSpec, TypeVar

from .platform_security import (
    STANDALONE_PROFILE,
    AccessLevel,
    PlatformSecurityProfile,
    normalize_endpoint,
)
from .roles import (
    RolePermissions,
    SecurityRole,
    get_permissions,
)

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@dataclass(slots=True)
class SecurityEvent:
    """Record of a security-relevant action."""

    timestamp: datetime
    role: SecurityRole
    action: str
    resource: str | None
    allowed: bool
    reason: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "role": self.role.value,
            "action": self.action,
            "resource": self.resource,
            "allowed": self.allowed,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class SecurityViolation(Exception):
    """Raised when a security check fails."""

    def __init__(
        self,
        message: str,
        role: SecurityRole,
        action: str,
        resource: str | None = None,
    ):
        super().__init__(message)
        self.role = role
        self.action = action
        self.resource = resource


class SecurityGuard:
    """
    Central security guard for checking role-based permissions.

    Integrates with YOLO executor and other components to enforce
    role-based access control.
    """

    def __init__(
        self,
        role: SecurityRole,
        *,
        audit_log: bool = True,
        max_audit_entries: int = 1000,
        platform_profile: PlatformSecurityProfile = STANDALONE_PROFILE,
    ):
        self.role = role
        self._permissions = get_permissions(role)
        self.platform_profile = platform_profile
        self._audit_log = audit_log
        self._audit_entries: list[SecurityEvent] = []
        self._max_audit_entries = max_audit_entries

        # Rate limiting state
        self._request_times: list[float] = []

    @property
    def permissions(self) -> RolePermissions:
        """Get the current role's permissions."""
        return self._permissions

    def get_platform_rate_limit(self) -> int:
        """Get the platform profile rate limit in requests per hour."""
        if self._permissions.can_access_admin_apis:
            return self.platform_profile.admin_rate_limit
        if self._permissions.can_access_authenticated_apis:
            return self.platform_profile.user_rate_limit
        return self.platform_profile.guest_rate_limit

    def check_platform_endpoint(self, endpoint: str) -> tuple[bool, str | None]:
        """Check whether this role can use a platform endpoint."""
        normalized = normalize_endpoint(endpoint)
        required_access = self.platform_profile.access_level_for(normalized)

        if required_access is None:
            reason = (
                f"Endpoint {normalized} is not exposed by platform profile "
                f"{self.platform_profile.name}"
            )
            self._log_event(
                action="platform_endpoint",
                resource=normalized,
                allowed=False,
                reason=reason,
                platform=self.platform_profile.name,
            )
            return False, reason

        if not self._permissions.can_access_apis:
            reason = "API access not permitted for this role"
            self._log_event(
                action="platform_endpoint",
                resource=normalized,
                allowed=False,
                reason=reason,
                platform=self.platform_profile.name,
                access_level=required_access.value,
            )
            return False, reason

        if (
            required_access is AccessLevel.PUBLIC
            and not self._permissions.can_access_guest_apis
        ):
            reason = "Public endpoint access not permitted for this role"
        elif (
            required_access is AccessLevel.AUTHENTICATED
            and not self._permissions.can_access_authenticated_apis
        ):
            reason = "Authenticated endpoint access not permitted for this role"
        elif (
            required_access is AccessLevel.PRIVILEGED
            and not self._permissions.can_access_admin_apis
        ):
            reason = "Privileged endpoint access not permitted for this role"
        elif (
            self.role == SecurityRole.GUEST
            and normalized.startswith(("POST ", "PUT ", "PATCH ", "DELETE "))
            and not self.platform_profile.allows_guest_writes
        ):
            reason = (
                f"Guest write access disabled for platform {self.platform_profile.name}"
            )
        else:
            reason = None

        allowed = reason is None
        self._log_event(
            action="platform_endpoint",
            resource=normalized,
            allowed=allowed,
            reason=reason,
            platform=self.platform_profile.name,
            access_level=required_access.value,
        )
        return allowed, reason

    def check_platform_operation(self, operation: str) -> tuple[bool, str | None]:
        """Check generalized non-endpoint operations such as help and search."""
        normalized = operation.strip().lower().replace(" ", "_")

        if normalized in {"help", "faq", "documentation", "customer_support"}:
            allowed = self._permissions.can_read_docs or self._permissions.can_read_faq
            reason = None if allowed else "Help access not permitted for this role"
        elif normalized == "web_search":
            allowed = self._permissions.can_access_admin_apis or (
                self.role == SecurityRole.GUEST
                and self.platform_profile.allows_guest_search
            )
            reason = (
                None
                if allowed
                else "Web search is restricted to admin for this platform"
            )
        elif normalized == "heavy_llm":
            allowed = self._permissions.can_access_admin_apis
            reason = None if allowed else "Heavy LLM access is restricted to admin"
        elif normalized in {"code_execution", "exec", "eval"}:
            return self.check_code_execution()
        elif normalized in {"file_system", "filesystem"}:
            allowed = self._permissions.can_access_filesystem
            reason = (
                None if allowed else "File system access not permitted for this role"
            )
        elif normalized in {"system_command", "system_commands", "shell"}:
            allowed = self._permissions.can_execute_shell
            reason = (
                None
                if allowed
                else "System command execution not permitted for this role"
            )
        else:
            reason = f"Unknown platform operation: {operation}"
            allowed = False

        self._log_event(
            action="platform_operation",
            resource=normalized,
            allowed=allowed,
            reason=reason,
            platform=self.platform_profile.name,
        )
        return allowed, reason

    def check_command(self, command: str) -> tuple[bool, str | None]:
        """
        Check if a shell command is allowed.

        Args:
            command: The shell command to check.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        allowed, reason = self._permissions.is_command_allowed(command)

        self._log_event(
            action="execute_command",
            resource=command[:100],  # Truncate for logging
            allowed=allowed,
            reason=reason,
        )

        return allowed, reason

    def check_file_write(self, path: str | Path) -> tuple[bool, str | None]:
        """
        Check if writing to a file path is allowed.

        Args:
            path: The file path to check.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        allowed, reason = self._permissions.is_path_writable(path)

        self._log_event(
            action="file_write",
            resource=str(path),
            allowed=allowed,
            reason=reason,
        )

        return allowed, reason

    def check_file_read(self, path: str | Path) -> tuple[bool, str | None]:
        """
        Check if reading a file path is allowed.

        Args:
            path: The file path to check.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        allowed, reason = self._permissions.is_path_readable(path)

        self._log_event(
            action="file_read",
            resource=str(path),
            allowed=allowed,
            reason=reason,
        )

        return allowed, reason

    def check_code_execution(self) -> tuple[bool, str | None]:
        """Check if code execution is allowed."""
        if not self._permissions.can_execute_code:
            reason = "Code execution not permitted for this role"
            self._log_event(
                action="code_execution",
                resource=None,
                allowed=False,
                reason=reason,
            )
            return False, reason

        self._log_event(
            action="code_execution",
            resource=None,
            allowed=True,
            reason=None,
        )
        return True, None

    def check_config_modification(self) -> tuple[bool, str | None]:
        """Check if configuration modification is allowed."""
        if not self._permissions.can_modify_config:
            reason = "Configuration modification not permitted for this role"
            self._log_event(
                action="config_modification",
                resource=None,
                allowed=False,
                reason=reason,
            )
            return False, reason

        self._log_event(
            action="config_modification",
            resource=None,
            allowed=True,
            reason=None,
        )
        return True, None

    def check_admin_api_access(self) -> tuple[bool, str | None]:
        """Check if admin API access is allowed."""
        if not self._permissions.can_access_admin_api:
            reason = "Admin API access not permitted for this role"
            self._log_event(
                action="admin_api_access",
                resource=None,
                allowed=False,
                reason=reason,
            )
            return False, reason

        self._log_event(
            action="admin_api_access",
            resource=None,
            allowed=True,
            reason=None,
        )
        return True, None

    def check_secrets_access(self) -> tuple[bool, str | None]:
        """Check if secrets access is allowed."""
        if not self._permissions.can_access_secrets:
            reason = "Secrets access not permitted for this role"
            self._log_event(
                action="secrets_access",
                resource=None,
                allowed=False,
                reason=reason,
            )
            return False, reason

        self._log_event(
            action="secrets_access",
            resource=None,
            allowed=True,
            reason=None,
        )
        return True, None

    def check_rate_limit(self) -> tuple[bool, str | None]:
        """
        Check if the rate limit allows another request.

        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        now = time.time()
        minute_ago = now - 60

        # Clean old entries
        self._request_times = [t for t in self._request_times if t > minute_ago]

        if len(self._request_times) >= self._permissions.rate_limit_per_minute:
            reason = (
                f"Rate limit exceeded: {self._permissions.rate_limit_per_minute}/minute"
            )
            self._log_event(
                action="rate_limit",
                resource=None,
                allowed=False,
                reason=reason,
            )
            return False, reason

        self._request_times.append(now)
        return True, None

    def get_llm_access_level(self) -> str:
        """Get the LLM access level for this role."""
        return self._permissions.llm_access_level

    def require_command_allowed(self, command: str) -> None:
        """
        Require that a command is allowed, raising SecurityViolation if not.

        Args:
            command: The command to check.

        Raises:
            SecurityViolation: If the command is not allowed.
        """
        allowed, reason = self.check_command(command)
        if not allowed:
            raise SecurityViolation(
                reason or "Command not allowed",
                self.role,
                "execute_command",
                command[:100],
            )

    def require_file_write_allowed(self, path: str | Path) -> None:
        """
        Require that file writing is allowed, raising SecurityViolation if not.

        Args:
            path: The path to check.

        Raises:
            SecurityViolation: If writing is not allowed.
        """
        allowed, reason = self.check_file_write(path)
        if not allowed:
            raise SecurityViolation(
                reason or "File write not allowed",
                self.role,
                "file_write",
                str(path),
            )

    def require_admin(self) -> None:
        """
        Require admin role.

        Raises:
            SecurityViolation: If current role is not admin.
        """
        if self.role != SecurityRole.FULL_ADMIN:
            raise SecurityViolation(
                "Admin role required",
                self.role,
                "require_admin",
            )

    def require_user_or_above(self) -> None:
        """
        Require at least USER role.

        Raises:
            SecurityViolation: If current role is GUEST.
        """
        if self.role < SecurityRole.USER:
            raise SecurityViolation(
                "User role or above required",
                self.role,
                "require_user_or_above",
            )

    def get_audit_log(self) -> list[dict[str, Any]]:
        """Get the audit log as a list of dicts."""
        return [e.to_dict() for e in self._audit_entries]

    def clear_audit_log(self) -> None:
        """Clear the audit log."""
        self._audit_entries.clear()

    def _log_event(
        self,
        action: str,
        resource: str | None,
        allowed: bool,
        reason: str | None,
        **metadata: Any,
    ) -> None:
        """Log a security event."""
        if not self._audit_log:
            return

        event = SecurityEvent(
            timestamp=datetime.now(UTC),
            role=self.role,
            action=action,
            resource=resource,
            allowed=allowed,
            reason=reason,
            metadata=metadata,
        )

        self._audit_entries.append(event)

        # Trim if over limit
        if len(self._audit_entries) > self._max_audit_entries:
            self._audit_entries = self._audit_entries[-self._max_audit_entries :]

        # Also log to standard logger
        log_msg = f"Security: role={self.role.value} action={action} allowed={allowed}"
        if resource:
            log_msg += f" resource={resource[:50]}"
        if reason:
            log_msg += f" reason={reason}"

        if allowed:
            logger.debug(log_msg)
        else:
            logger.warning(log_msg)


# Thread-local / context-local guard storage
import contextvars

_current_guard: contextvars.ContextVar[SecurityGuard | None] = contextvars.ContextVar(
    "security_guard", default=None
)


def set_security_guard(guard: SecurityGuard) -> contextvars.Token[SecurityGuard | None]:
    """Set the current security guard for this context."""
    return _current_guard.set(guard)


def get_security_guard() -> SecurityGuard | None:
    """Get the current security guard."""
    return _current_guard.get()


def reset_security_guard(token: contextvars.Token[SecurityGuard | None]) -> None:
    """Reset the security guard to its previous value."""
    _current_guard.reset(token)


def get_or_create_guard(
    role: SecurityRole = SecurityRole.GUEST,
    *,
    platform_profile: PlatformSecurityProfile = STANDALONE_PROFILE,
) -> SecurityGuard:
    """Get existing guard or create one with the given role."""
    guard = get_security_guard()
    if guard is None:
        guard = SecurityGuard(role, platform_profile=platform_profile)
        set_security_guard(guard)
    return guard


# Decorators for role-based access control


def require_role(
    minimum_role: SecurityRole,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorator that requires a minimum security role.

    Args:
        minimum_role: The minimum role required to call this function.

    Example:
        @require_role(SecurityRole.FULL_ADMIN)
        def delete_all_data():
            ...
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            guard = get_security_guard()
            if guard is None:
                raise SecurityViolation(
                    "No security context - authentication required",
                    SecurityRole.GUEST,
                    func.__name__,
                )

            if guard.role < minimum_role:
                raise SecurityViolation(
                    f"Insufficient role: requires {minimum_role.value}, has {guard.role.value}",
                    guard.role,
                    func.__name__,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_admin(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator that requires ADMIN role.

    Example:
        @require_admin
        def shutdown_server():
            ...
    """
    return require_role(SecurityRole.FULL_ADMIN)(func)


def require_user_or_above(func: Callable[P, R]) -> Callable[P, R]:
    """
    Decorator that requires at least USER role.

    Example:
        @require_user_or_above
        def run_tests():
            ...
    """
    return require_role(SecurityRole.USER)(func)


# Helper functions


def check_file_access(path: str | Path, write: bool = False) -> tuple[bool, str | None]:
    """
    Check if file access is allowed for current role.

    Args:
        path: The file path to check.
        write: Whether write access is needed.

    Returns:
        Tuple of (allowed, reason_if_blocked)
    """
    guard = get_security_guard()
    if guard is None:
        return False, "No security context"

    if write:
        return guard.check_file_write(path)
    return guard.check_file_read(path)


def check_command_allowed(command: str) -> tuple[bool, str | None]:
    """
    Check if a command is allowed for current role.

    Args:
        command: The shell command to check.

    Returns:
        Tuple of (allowed, reason_if_blocked)
    """
    guard = get_security_guard()
    if guard is None:
        return False, "No security context"

    return guard.check_command(command)
