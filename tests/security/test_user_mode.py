# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for USER mode - safe, cannot harm OS"""

from __future__ import annotations

import pytest

from agentic_brain.security.roles import SecurityRole
from agentic_brain.security.guards import SecurityGuard


class TestUserMode:
    """Test suite for USER role - safe operations only."""
    
    @pytest.fixture
    def user(self):
        """Create a USER security guard."""
        return SecurityGuard(SecurityRole.USER)
    
    def test_user_cannot_delete_system_files(self, user):
        """User CANNOT run commands that harm the OS."""
        # Destructive file operations
        allowed, reason = user.check_command("rm -rf /")
        assert not allowed, "User should NOT allow rm -rf /"
        assert reason is not None
        
        allowed, reason = user.check_command("sudo rm -rf /etc")
        assert not allowed, "User should NOT allow sudo rm"
        
        allowed, reason = user.check_command("dd if=/dev/zero of=/dev/sda")
        assert not allowed, "User should NOT allow dd to disk"
    
    def test_user_cannot_use_sudo(self, user):
        """User cannot use sudo for privilege escalation."""
        allowed, reason = user.check_command("sudo apt install test")
        assert not allowed, "User should NOT allow sudo"
        
        allowed, reason = user.check_command("su - root")
        assert not allowed, "User should NOT allow su"
    
    def test_user_can_run_safe_commands(self, user):
        """User CAN run safe commands for development."""
        # Safe read operations
        allowed, reason = user.check_command("ls -la")
        assert allowed, f"User should allow ls: {reason}"
        
        allowed, reason = user.check_command("cat file.txt")
        assert allowed, f"User should allow cat: {reason}"
        
        allowed, reason = user.check_command("grep pattern file")
        assert allowed, f"User should allow grep: {reason}"
        
        allowed, reason = user.check_command("find . -name '*.py'")
        assert allowed, f"User should allow find: {reason}"
    
    def test_user_can_run_development_commands(self, user):
        """User can run standard development commands."""
        allowed, reason = user.check_command("python script.py")
        assert allowed, f"User should allow python: {reason}"
        
        allowed, reason = user.check_command("npm install")
        assert allowed, f"User should allow npm: {reason}"
        
        allowed, reason = user.check_command("git commit -m 'test'")
        assert allowed, f"User should allow git commit: {reason}"
    
    def test_user_cannot_write_system_paths(self, user):
        """User CANNOT write to system directories."""
        # System critical files
        allowed, reason = user.check_file_write("/etc/passwd")
        assert not allowed, "User should NOT write to /etc/passwd"
        
        allowed, reason = user.check_file_write("/usr/bin/python")
        assert not allowed, "User should NOT write to /usr/bin"
        
        allowed, reason = user.check_file_write("/var/log/system.log")
        assert not allowed, "User should NOT write to /var/log"
    
    def test_user_can_write_to_allowed_paths(self, user):
        """User CAN write to designated safe directories."""
        # Should be able to write to brain project directories
        allowed, reason = user.check_file_write("~/brain/data/test.txt")
        assert allowed, f"User should write to ~/brain/data: {reason}"
        
        allowed, reason = user.check_file_write("~/brain/logs/app.log")
        assert allowed, f"User should write to ~/brain/logs: {reason}"
        
        allowed, reason = user.check_file_write("~/brain/cache/temp.json")
        assert allowed, f"User should write to ~/brain/cache: {reason}"
    
    def test_user_can_write_to_test_artifacts(self, user):
        """User can write to test output directories."""
        allowed, reason = user.check_file_write("~/brain/agentic-brain/.test-artifacts/result.xml")
        assert allowed, f"User should write to test artifacts: {reason}"
        
        allowed, reason = user.check_file_write("~/brain/test-results/coverage.html")
        assert allowed, f"User should write to test results: {reason}"
    
    def test_user_cannot_chmod_world_writable(self, user):
        """User cannot make files world-writable (security risk)."""
        allowed, reason = user.check_command("chmod 777 file.txt")
        assert not allowed, "User should NOT allow chmod 777"
        
        allowed, reason = user.check_command("chmod 0777 file.txt")
        assert not allowed, "User should NOT allow chmod 0777"
        
        allowed, reason = user.check_command("chmod 4777 file.txt")
        assert not allowed, "User should NOT allow chmod 4777 (setuid)"
    
    def test_user_cannot_modify_firewall(self, user):
        """User cannot modify firewall or network security."""
        allowed, reason = user.check_command("iptables -A INPUT -p tcp --dport 80 -j ACCEPT")
        assert not allowed, "User should NOT allow iptables"
        
        allowed, reason = user.check_command("ufw disable")
        assert not allowed, "User should NOT allow ufw"
    
    def test_user_cannot_kill_all_processes(self, user):
        """User cannot kill all processes or critical services."""
        allowed, reason = user.check_command("kill -9 -1")
        assert not allowed, "User should NOT allow kill -9 -1"
        
        allowed, reason = user.check_command("killall -9 python")
        assert not allowed, "User should NOT allow killall"
    
    def test_user_cannot_force_push(self, user):
        """User cannot force push to git (can destroy history)."""
        allowed, reason = user.check_command("git push --force")
        assert not allowed, "User should NOT allow git push --force"
        
        allowed, reason = user.check_command("git push -f origin main")
        assert not allowed, "User should NOT allow git push -f"
    
    def test_user_has_standard_llm_access(self, user):
        """User has standard LLM access, not full admin access."""
        assert user.permissions.llm_access_level == "standard"
        assert user.permissions.can_execute_code
        # But shell execution is restricted by command checks
    
    def test_user_is_rate_limited(self, user):
        """User has reasonable rate limits."""
        # Should have some limit, not unlimited
        assert user.permissions.rate_limit_per_minute < 1000
        assert user.permissions.rate_limit_per_minute > 0
    
    def test_user_cannot_access_admin_api(self, user):
        """User cannot access admin-only APIs."""
        assert not user.permissions.can_access_admin_api
        assert not user.permissions.can_manage_users
    
    def test_user_role_comparison(self, user):
        """User is middle-tier role."""
        assert user.role == SecurityRole.USER
        assert user.role > SecurityRole.GUEST
        assert user.role < SecurityRole.FULL_ADMIN
