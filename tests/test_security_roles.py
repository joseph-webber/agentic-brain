# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

from dataclasses import dataclass

import pytest

from agentic_brain.security.auth import (
    ADMIN_KEY_ENV,
    AdminAuthenticator,
    SessionManager,
    authenticate_api_key,
    authenticate_request,
    create_admin_session,
    get_current_role,
    is_admin,
    is_guest,
    is_user,
    setup_admin_from_env,
)
from agentic_brain.security.guards import check_file_access
from agentic_brain.security.guards import (
    SecurityGuard,
    SecurityViolation,
    check_command_allowed,
    check_file_access,
    reset_security_guard,
    set_security_guard,
)
from agentic_brain.security.roles import (
    SecurityRole,
    get_permissions,
    is_dangerous_command,
)
from agentic_brain.yolo.executor import SecureYOLOExecutor
from agentic_brain.yolo.handlers import CommandExecutionResult, InterpretedCommand


class TestSecurityRoles:
    def test_role_ordering(self) -> None:
        assert (
            SecurityRole.GUEST
            < SecurityRole.USER
            < SecurityRole.SAFE_ADMIN
            < SecurityRole.FULL_ADMIN
        )

    def test_primary_role_values_match_spec(self) -> None:
        assert SecurityRole.GUEST.value == "guest"
        assert SecurityRole.USER.value == "user"
        assert SecurityRole.SAFE_ADMIN.value == "safe_admin"
        assert SecurityRole.FULL_ADMIN.value == "full_admin"


class TestRolePermissions:
    def test_full_admin_has_unrestricted_permissions(self) -> None:
        perms = get_permissions(SecurityRole.FULL_ADMIN)

        assert perms.can_yolo is True
        assert perms.yolo_requires_confirmation is False
        assert perms.can_execute_shell is True
        assert perms.can_write_files is True
        assert perms.can_access_filesystem is True
        assert "*" in perms.allowed_write_paths
        assert perms.can_read_all_files is True
        assert perms.can_execute_code is True
        assert perms.can_modify_config is True
        assert perms.can_access_database is True
        assert perms.can_manage_users is True
        assert perms.can_access_admin_api is True
        assert perms.rate_limit_per_minute == float("inf")
        assert perms.allowed_api_scopes == frozenset(
            {"read", "write", "delete", "admin"}
        )

    def test_safe_admin_requires_guardrails(self) -> None:
        perms = get_permissions(SecurityRole.SAFE_ADMIN)

        assert perms.can_yolo is True
        assert perms.yolo_requires_confirmation is True
        assert perms.can_execute_shell is True
        assert perms.can_write_files is True
        assert perms.can_access_filesystem is True
        assert "*" not in perms.allowed_write_paths
        assert perms.can_execute_code is True
        assert perms.can_modify_config is True
        assert perms.can_access_database is True
        assert perms.can_manage_users is False
        assert perms.rate_limit_per_minute == 1000
        assert perms.allowed_api_scopes == frozenset({"read", "write", "delete"})

    def test_user_is_api_only(self) -> None:
        perms = get_permissions(SecurityRole.USER)

        assert perms.can_yolo is False
        assert perms.can_execute_shell is False
        assert perms.can_write_files is False
        assert perms.can_access_filesystem is False
        assert perms.can_execute_code is False
        assert perms.can_access_database is False
        assert perms.can_access_apis is True
        assert perms.allowed_api_scopes == frozenset({"read", "write"})
        assert perms.rate_limit_per_minute == 60

    def test_guest_is_help_only(self) -> None:
        perms = get_permissions(SecurityRole.GUEST)

        assert perms.can_yolo is False
        assert perms.can_execute_shell is False
        assert perms.can_write_files is False
        assert perms.can_access_filesystem is False
        assert perms.can_execute_code is False
        assert perms.can_access_apis is True
        assert perms.allowed_api_scopes == frozenset({"read"})
        assert perms.can_read_faq is True
        assert perms.can_read_docs is True
        assert perms.can_read_manuals is True
        assert perms.rate_limit_per_minute == 10


class TestSecurityGuard:
    def test_full_admin_can_run_dangerous_commands(self) -> None:
        guard = SecurityGuard(SecurityRole.FULL_ADMIN)
        assert guard.check_command("rm -rf /")[0] is True
        assert (
            guard.check_command("sudo launchctl unload /Library/Test.plist")[0] is True
        )

    def test_safe_admin_blocks_dangerous_commands_pending_confirmation(self) -> None:
        guard = SecurityGuard(SecurityRole.SAFE_ADMIN)
        allowed, reason = guard.check_command("rm -rf /")
        assert allowed is False
        assert "dangerous pattern" in (reason or "")

        allowed, _ = guard.check_command("pytest tests/security")
        assert allowed is True

    def test_user_has_no_shell_or_filesystem_access(self) -> None:
        guard = SecurityGuard(SecurityRole.USER)
        assert guard.check_command("ls -la")[0] is False
        assert guard.check_file_write("~/brain/output/report.txt")[0] is False
        assert guard.check_file_read("~/brain/agentic-brain/README.md")[0] is True
        assert guard.check_file_read("/etc/passwd")[0] is False

    def test_guest_can_only_read_public_docs(self) -> None:
        guard = SecurityGuard(SecurityRole.GUEST)
        assert guard.check_file_read("~/brain/README.md")[0] is True
        assert guard.check_file_read("~/brain/agentic-brain/docs/index.md")[0] is True
        assert guard.check_file_read("/etc/passwd")[0] is False

    def test_rate_limits_match_spec(self) -> None:
        user = SecurityGuard(SecurityRole.USER)
        guest = SecurityGuard(SecurityRole.GUEST)
        admin = SecurityGuard(SecurityRole.FULL_ADMIN)

        for _ in range(60):
            assert user.check_rate_limit()[0] is True
        assert user.check_rate_limit()[0] is False

        for _ in range(10):
            assert guest.check_rate_limit()[0] is True
        assert guest.check_rate_limit()[0] is False

        for _ in range(500):
            assert admin.check_rate_limit()[0] is True


class TestDangerousCommandDetection:
    @pytest.mark.parametrize(
        "command",
        [
            "rm -rf /",
            "sudo apt install thing",
            "chmod 777 /etc/passwd",
            "git push --force",
            "DROP DATABASE production",
        ],
    )
    def test_dangerous_commands_are_detected(self, command: str) -> None:
        assert is_dangerous_command(command)[0] is True


class TestAuthentication:
    def test_api_key_authentication(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(ADMIN_KEY_ENV, "super-secret-admin-key")
        auth = AdminAuthenticator()

        assert auth.authenticate_key("super-secret-admin-key") is True
        assert (
            authenticate_api_key("super-secret-admin-key")[0] == SecurityRole.FULL_ADMIN
        )
        assert authenticate_api_key("regular_api_key_123456")[0] == SecurityRole.USER
        assert authenticate_api_key("short")[0] == SecurityRole.GUEST

    def test_request_authentication_helpers(self) -> None:
        guard = authenticate_request(user_id="joseph")
        assert guard.role == SecurityRole.FULL_ADMIN
        assert is_admin() is True

        guard = authenticate_request()
        assert guard.role == SecurityRole.GUEST
        assert is_guest() is True

        token = set_security_guard(SecurityGuard(SecurityRole.USER))
        try:
            assert get_current_role() == SecurityRole.USER
            assert is_user() is True
            assert check_command_allowed("ls -la")[0] is False
            assert check_file_access("~/brain/README.md")[0] is True
        finally:
            reset_security_guard(token)

    def test_session_manager_and_admin_session(self) -> None:
        manager = SessionManager()
        session = manager.create_session(SecurityRole.USER, user_id="customer-1")
        assert manager.get_session(session.session_id) is not None

        admin_session = create_admin_session()
        assert admin_session.role == SecurityRole.FULL_ADMIN

    def test_setup_admin_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENTIC_BRAIN_ADMIN_MODE", "true")
        guard = setup_admin_from_env()
        assert guard is not None
        assert guard.role == SecurityRole.FULL_ADMIN


@dataclass
class DummyHandlers:
    async def run_tests(self, command_text: str) -> CommandExecutionResult:
        return CommandExecutionResult(True, "run_tests", command_text, output="ok")

    async def deploy(self, command_text: str) -> CommandExecutionResult:
        return CommandExecutionResult(True, "deploy", command_text, output="ok")

    async def check_status(self, command_text: str) -> CommandExecutionResult:
        return CommandExecutionResult(True, "check_status", command_text, output="ok")

    async def search(self, command_text: str) -> CommandExecutionResult:
        return CommandExecutionResult(True, "search", command_text, output="ok")

    async def interpret(self, command_text: str) -> InterpretedCommand:
        return InterpretedCommand(capability="search", normalized_command=command_text)

    def _extract_arguments(self, command_text: str, _prefix: str) -> str:
        return command_text

    async def _run_command(
        self, _argv: list[str], *, capability: str, requested: str
    ) -> CommandExecutionResult:
        return CommandExecutionResult(True, capability, requested, output="ok")


class TestYoloExecutor:
    @pytest.mark.asyncio
    async def test_full_admin_can_execute_arbitrary_commands(self) -> None:
        token = set_security_guard(SecurityGuard(SecurityRole.FULL_ADMIN))
        try:
            executor = SecureYOLOExecutor(handlers=DummyHandlers())
            result = await executor.execute_arbitrary("rm -rf /")
            assert result.security_checks_passed is True
            assert result.role == SecurityRole.FULL_ADMIN
        finally:
            reset_security_guard(token)

    @pytest.mark.asyncio
    async def test_safe_admin_can_run_safe_yolo_commands_only(self) -> None:
        token = set_security_guard(SecurityGuard(SecurityRole.SAFE_ADMIN))
        try:
            executor = SecureYOLOExecutor(handlers=DummyHandlers())
            safe = await executor.run_tests("pytest tests/security")
            blocked = await executor.execute_arbitrary("sudo rm -rf /")
            assert safe.security_checks_passed is True
            assert blocked.security_checks_passed is False
            assert blocked.result.exit_code == 403
        finally:
            reset_security_guard(token)

    @pytest.mark.asyncio
    async def test_user_and_guest_are_blocked_from_yolo(self) -> None:
        for role in (SecurityRole.USER, SecurityRole.GUEST):
            token = set_security_guard(SecurityGuard(role))
            try:
                executor = SecureYOLOExecutor(handlers=DummyHandlers())
                result = await executor.check_status("status")
                assert result.security_checks_passed is False
                assert result.result.exit_code == 403
            finally:
                reset_security_guard(token)
