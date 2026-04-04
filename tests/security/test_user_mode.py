# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for USER mode - API-only, no machine access."""

from __future__ import annotations

import pytest

from agentic_brain.security.guards import SecurityGuard
from agentic_brain.security.roles import SecurityRole


class TestUserMode:
    @pytest.fixture
    def user(self) -> SecurityGuard:
        return SecurityGuard(SecurityRole.USER)

    def test_user_cannot_execute_any_shell_commands(self, user: SecurityGuard) -> None:
        for command in ("ls -la", "python script.py", "git status", "rm -rf /", "sudo apt install test"):
            allowed, _ = user.check_command(command)
            assert allowed is False

    def test_user_cannot_write_files(self, user: SecurityGuard) -> None:
        for path in (
            "~/brain/output/result.txt",
            "~/brain/data/test.txt",
            "~/brain/agentic-brain/src/example.py",
            "/etc/passwd",
        ):
            allowed, _ = user.check_file_write(path)
            assert allowed is False

    def test_user_can_only_read_public_documentation(self, user: SecurityGuard) -> None:
        assert user.check_file_read("~/brain/README.md")[0] is True
        assert user.check_file_read("~/brain/agentic-brain/docs/index.md")[0] is True
        assert user.check_file_read("~/brain/.env")[0] is False

    def test_user_permissions_match_api_only_spec(self, user: SecurityGuard) -> None:
        perms = user.permissions
        assert perms.can_access_apis is True
        assert perms.allowed_api_scopes == frozenset({"read", "write"})
        assert perms.can_yolo is False
        assert perms.can_execute_code is False
        assert perms.can_execute_shell is False
        assert perms.can_access_database is False
        assert perms.can_access_admin_api is False
        assert perms.can_manage_users is False
        assert perms.rate_limit_per_minute == 60

    def test_user_role_comparison(self, user: SecurityGuard) -> None:
        assert user.role == SecurityRole.USER
        assert user.role > SecurityRole.GUEST
        assert user.role < SecurityRole.FULL_ADMIN
