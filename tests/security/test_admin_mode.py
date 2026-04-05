# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for ADMIN mode - should have FULL access"""

from __future__ import annotations

import pytest

from agentic_brain.security.roles import SecurityRole
from agentic_brain.security.guards import SecurityGuard


class TestAdminMode:
    """Test suite for ADMIN role - full access to everything."""

    @pytest.fixture
    def admin(self):
        """Create an ADMIN security guard."""
        return SecurityGuard(SecurityRole.FULL_ADMIN)

    def test_admin_can_yolo_dangerous_commands(self, admin):
        """Admin MUST be able to run any command including dangerous ones."""
        # Destructive commands
        allowed, reason = admin.check_command("rm -rf /tmp/test")
        assert allowed, f"Admin should allow rm -rf: {reason}"

        allowed, reason = admin.check_command("sudo apt install something")
        assert allowed, f"Admin should allow sudo: {reason}"

        allowed, reason = admin.check_command("chmod 777 /some/file")
        assert allowed, f"Admin should allow chmod 777: {reason}"

    def test_admin_can_modify_system_files(self, admin):
        """Admin can run commands that modify system files."""
        allowed, reason = admin.check_command("sudo systemctl restart nginx")
        assert allowed, f"Admin should allow systemctl: {reason}"

        allowed, reason = admin.check_command("mount /dev/sda1 /mnt")
        assert allowed, f"Admin should allow mount: {reason}"

    def test_admin_can_write_anywhere(self, admin):
        """Admin can write to any path on the system."""
        # System paths
        allowed, reason = admin.check_file_write("/etc/hosts")
        assert allowed, f"Admin should write to /etc/hosts: {reason}"

        allowed, reason = admin.check_file_write("/usr/local/bin/script")
        assert allowed, f"Admin should write to /usr/local/bin: {reason}"

        # User paths
        allowed, reason = admin.check_file_write("~/brain/data/file.txt")
        assert allowed, f"Admin should write to user dirs: {reason}"

    def test_admin_can_read_anywhere(self, admin):
        """Admin can read any file on the system."""
        allowed, reason = admin.check_file_read("/etc/passwd")
        assert allowed, f"Admin should read /etc/passwd: {reason}"

        allowed, reason = admin.check_file_read("/var/log/system.log")
        assert allowed, f"Admin should read system logs: {reason}"

    def test_admin_has_full_llm_access(self, admin):
        """Admin can use all LLM features."""
        assert admin.permissions.llm_access_level == "full"
        assert admin.permissions.can_execute_code
        assert admin.permissions.can_execute_arbitrary_shell

    def test_admin_no_rate_limits(self, admin):
        """Admin has no rate limits."""
        # Should be very high or unlimited
        assert admin.permissions.rate_limit_per_minute >= 1000

    def test_admin_can_access_secrets(self, admin):
        """Admin can access secrets and sensitive config."""
        assert admin.permissions.can_access_secrets
        assert admin.permissions.can_modify_config

    def test_admin_has_management_access(self, admin):
        """Admin can access admin APIs and manage users."""
        assert admin.permissions.can_access_admin_api
        assert admin.permissions.can_manage_users

    def test_admin_can_run_fork_bomb(self, admin):
        """Admin can even run dangerous resource exhaustion commands."""
        # This is intentional - admin has FULL control
        allowed, reason = admin.check_command("while true; do echo test; done")
        assert allowed, f"Admin should allow infinite loop: {reason}"

    def test_admin_can_execute_code(self, admin):
        """Admin can execute arbitrary code."""
        assert admin.permissions.can_execute_code
        assert admin.permissions.can_execute_arbitrary_shell

    def test_admin_role_comparison(self, admin):
        """Admin is the highest role."""
        assert admin.role == SecurityRole.FULL_ADMIN
        assert admin.role > SecurityRole.USER
        assert admin.role > SecurityRole.GUEST
