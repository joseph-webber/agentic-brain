# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for GUEST mode - help desk only"""

from __future__ import annotations

import pytest

from agentic_brain.security.roles import SecurityRole
from agentic_brain.security.guards import SecurityGuard


class TestGuestMode:
    """Test suite for GUEST role - most restricted, read-only chat."""
    
    @pytest.fixture
    def guest(self):
        """Create a GUEST security guard."""
        return SecurityGuard(SecurityRole.GUEST)
    
    def test_guest_cannot_use_yolo(self, guest):
        """Guest has NO yolo access at all."""
        # Guest cannot execute ANY commands
        allowed, reason = guest.check_command("ls")
        assert not allowed, "Guest should NOT allow even safe commands"
        
        allowed, reason = guest.check_command("echo hello")
        assert not allowed, "Guest should NOT allow echo"
    
    def test_guest_cannot_run_dangerous_commands(self, guest):
        """Guest definitely cannot run dangerous commands."""
        allowed, reason = guest.check_command("rm -rf /")
        assert not allowed, "Guest should NOT allow rm"
        
        allowed, reason = guest.check_command("sudo anything")
        assert not allowed, "Guest should NOT allow sudo"
    
    def test_guest_cannot_execute_code(self, guest):
        """Guest cannot execute any code."""
        assert not guest.permissions.can_execute_code
        assert not guest.permissions.can_execute_arbitrary_shell
        assert not guest.permissions.can_yolo
    
    def test_guest_cannot_write_anything(self, guest):
        """Guest is completely read-only."""
        # Cannot write to any path, even safe ones
        allowed, reason = guest.check_file_write("~/brain/data/file.txt")
        assert not allowed, "Guest should NOT write to data dir"
        
        allowed, reason = guest.check_file_write("/tmp/anything")
        assert not allowed, "Guest should NOT write to /tmp"
        
        # Verify permission level
        assert not guest.permissions.can_write_files
    
    def test_guest_can_read_public_files(self, guest):
        """Guest can read public documentation."""
        # Public docs should be readable
        allowed, reason = guest.check_file_read("~/brain/README.md")
        assert allowed, f"Guest should read README: {reason}"
        
        allowed, reason = guest.check_file_read("~/brain/CLAUDE.md")
        assert allowed, f"Guest should read CLAUDE.md: {reason}"
        
        allowed, reason = guest.check_file_read("~/brain/docs/index.html")
        assert allowed, f"Guest should read docs: {reason}"
    
    def test_guest_cannot_read_sensitive_files(self, guest):
        """Guest cannot read sensitive or private files."""
        allowed, reason = guest.check_file_read("/etc/passwd")
        assert not allowed, "Guest should NOT read /etc/passwd"
        
        allowed, reason = guest.check_file_read("~/brain/.env")
        assert not allowed, "Guest should NOT read .env files"
    
    def test_guest_has_limited_llm(self, guest):
        """Guest can only chat, no code execution features."""
        assert guest.permissions.llm_access_level == "chat_only"
        assert not guest.permissions.can_execute_code
        assert not guest.permissions.can_execute_arbitrary_shell
    
    def test_guest_is_rate_limited(self, guest):
        """Guest has strict rate limits to prevent abuse."""
        # Should have the most restrictive limits
        assert guest.permissions.rate_limit_per_minute <= 60
        assert guest.permissions.rate_limit_per_minute > 0
    
    def test_guest_cannot_access_secrets(self, guest):
        """Guest cannot access secrets or modify config."""
        assert not guest.permissions.can_access_secrets
        assert not guest.permissions.can_modify_config
    
    def test_guest_cannot_access_admin_features(self, guest):
        """Guest has no admin or management access."""
        assert not guest.permissions.can_access_admin_api
        assert not guest.permissions.can_manage_users
    
    def test_guest_role_is_lowest(self, guest):
        """Guest is the lowest privilege role."""
        assert guest.role == SecurityRole.GUEST
        assert guest.role < SecurityRole.USER
        assert guest.role < SecurityRole.FULL_ADMIN
    
    def test_guest_cannot_modify_environment(self, guest):
        """Guest cannot modify environment variables or shell config."""
        allowed, reason = guest.check_command("export PATH=/bad/path")
        assert not allowed, "Guest should NOT allow export"
        
        allowed, reason = guest.check_command("echo 'alias rm=rm -rf' >> ~/.bashrc")
        assert not allowed, "Guest should NOT modify shell config"
    
    def test_guest_read_only_permissions(self, guest):
        """Verify guest permissions are truly read-only."""
        perms = guest.permissions
        
        # No write capabilities
        assert not perms.can_write_files
        assert not perms.can_modify_config
        
        # No execution capabilities
        assert not perms.can_yolo
        assert not perms.can_execute_code
        assert not perms.can_execute_arbitrary_shell
        
        # No admin capabilities
        assert not perms.can_access_admin_api
        assert not perms.can_manage_users
        assert not perms.can_access_secrets
