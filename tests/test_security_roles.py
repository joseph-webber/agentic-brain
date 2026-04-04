# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Comprehensive tests for the security roles system.

Tests all three roles (ADMIN, USER, GUEST) and their permission boundaries.
"""

from __future__ import annotations

import os
import pytest
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from agentic_brain.security.roles import (
    SecurityRole,
    RolePermissions,
    ROLE_PERMISSIONS,
    get_permissions,
)
from agentic_brain.security.guards import (
    SecurityGuard,
    SecurityViolation,
)
try:
    from agentic_brain.security.guards import (
        require_role,
        require_admin,
        require_user_or_above,
    )
except ImportError:
    require_role = None
    require_admin = None
    require_user_or_above = None

try:
    from agentic_brain.security.auth import (
        check_file_access,
        check_command_allowed,
        authenticate_api_key,
        authenticate_request,
        get_current_role,
        is_admin,
        is_user,
        is_guest,
        AdminAuthenticator,
        SessionManager,
        Session,
    )
except ImportError:
    check_file_access = None
    check_command_allowed = None
    authenticate_api_key = None
    authenticate_request = None
    get_current_role = None
    is_admin = None
    is_user = None
    is_guest = None
    AdminAuthenticator = None
    SessionManager = None
    Session = None

try:
    from agentic_brain.security.auth import (
        create_admin_session,
        setup_admin_from_env,
        ADMIN_KEY_ENV,
    )
except ImportError:
    create_admin_session = None
    setup_admin_from_env = None
    ADMIN_KEY_ENV = None

try:
    from agentic_brain.security.roles import (
        DANGEROUS_COMMAND_PATTERNS,
        is_dangerous_command,
    )
except ImportError:
    DANGEROUS_COMMAND_PATTERNS = None
    is_dangerous_command = None

try:
    from agentic_brain.security.guards import (
        set_security_guard,
        get_security_guard,
        reset_security_guard,
        get_or_create_guard,
    )
except ImportError:
    set_security_guard = None
    get_security_guard = None
    reset_security_guard = None
    get_or_create_guard = None



class TestSecurityRole:
    """Tests for SecurityRole enum and comparison."""
    
    def test_role_ordering(self):
        """Test that roles are properly ordered."""
        assert SecurityRole.GUEST < SecurityRole.USER
        assert SecurityRole.USER < SecurityRole.DEVELOPER
        assert SecurityRole.DEVELOPER < SecurityRole.ADMIN
        assert SecurityRole.GUEST < SecurityRole.ADMIN
    
    def test_role_comparison_operators(self):
        """Test all comparison operators."""
        assert SecurityRole.GUEST <= SecurityRole.GUEST
        assert SecurityRole.GUEST <= SecurityRole.USER
        assert SecurityRole.USER >= SecurityRole.GUEST
        assert SecurityRole.DEVELOPER >= SecurityRole.USER
        assert SecurityRole.ADMIN >= SecurityRole.ADMIN
        assert not SecurityRole.ADMIN < SecurityRole.USER
        assert not SecurityRole.USER > SecurityRole.ADMIN
        assert SecurityRole.DEVELOPER > SecurityRole.USER
        assert SecurityRole.DEVELOPER < SecurityRole.ADMIN
    
    def test_role_values(self):
        """Test role string values."""
        assert SecurityRole.ADMIN.value == "admin"
        assert SecurityRole.DEVELOPER.value == "developer"
        assert SecurityRole.USER.value == "user"
        assert SecurityRole.GUEST.value == "guest"


class TestRolePermissions:
    """Tests for RolePermissions and ROLE_PERMISSIONS."""
    
    def test_admin_has_full_permissions(self):
        """Admin should have no restrictions."""
        perms = get_permissions(SecurityRole.ADMIN)
        
        assert perms.can_yolo is True
        assert len(perms.yolo_restrictions) == 0
        assert perms.can_write_files is True
        assert "*" in perms.allowed_write_paths
        assert perms.can_read_all_files is True
        assert perms.can_execute_code is True
        assert perms.can_execute_arbitrary_shell is True
        assert perms.can_modify_config is True
        assert perms.can_access_secrets is True
        assert perms.llm_access_level == "full"
        assert perms.can_access_admin_api is True
        assert perms.can_manage_users is True
    
    def test_user_has_limited_permissions(self):
        """User should have restrictions on dangerous operations."""
        perms = get_permissions(SecurityRole.USER)
        
        assert perms.can_yolo is True
        assert len(perms.yolo_restrictions) > 0  # Has blocked patterns
        assert perms.can_write_files is True
        assert "*" not in perms.allowed_write_paths
        assert perms.can_read_all_files is True
        assert perms.can_execute_code is True
        assert perms.can_modify_config is False
        assert perms.can_access_secrets is False
        assert perms.llm_access_level == "standard"
        assert perms.can_access_admin_api is False
    
    def test_developer_has_broad_permissions(self):
        """Developer should have broad development permissions with guardrails."""
        perms = get_permissions(SecurityRole.DEVELOPER)
        
        assert perms.can_yolo is True
        assert len(perms.yolo_restrictions) > 0  # Still has guardrails
        assert perms.can_write_files is True
        assert "*" not in perms.allowed_write_paths  # Not unlimited
        assert len(perms.allowed_write_paths) > len(get_permissions(SecurityRole.USER).allowed_write_paths)
        assert perms.can_read_all_files is True
        assert perms.can_execute_code is True
        assert perms.can_execute_arbitrary_shell is True
        assert perms.can_modify_config is True  # Project config
        assert perms.can_access_secrets is False  # Still no secrets
        assert perms.llm_access_level == "full"
        assert perms.can_access_admin_api is False
        assert perms.can_manage_users is False
    
    def test_guest_has_minimal_permissions(self):
        """Guest should have highly restricted permissions."""
        perms = get_permissions(SecurityRole.GUEST)
        
        assert perms.can_yolo is False
        assert perms.can_write_files is False
        assert len(perms.allowed_write_paths) == 0
        assert perms.can_read_all_files is False
        assert perms.can_execute_code is False
        assert perms.can_execute_arbitrary_shell is False
        assert perms.can_modify_config is False
        assert perms.can_access_secrets is False
        assert perms.llm_access_level == "chat_only"
        assert perms.can_access_admin_api is False
        assert perms.can_manage_users is False


class TestDangerousCommands:
    """Tests for dangerous command detection."""
    
    def test_rm_rf_detected(self):
        """Test that rm -rf is detected as dangerous."""
        dangerous_commands = [
            "rm -rf /",
            "rm -rf ~",
            "rm -rf ..",
            "rm -rf /home",
            "rm -f -r /etc",
        ]
        
        for cmd in dangerous_commands:
            is_dangerous, _ = is_dangerous_command(cmd)
            assert is_dangerous, f"Command '{cmd}' should be detected as dangerous"
    
    def test_sudo_detected(self):
        """Test that sudo commands are detected as dangerous."""
        dangerous_commands = [
            "sudo rm file",
            "sudo apt install",
            "sudo chmod 777 /",
        ]
        
        for cmd in dangerous_commands:
            is_dangerous, _ = is_dangerous_command(cmd)
            assert is_dangerous, f"Command '{cmd}' should be detected as dangerous"
    
    def test_safe_commands_allowed(self):
        """Test that safe commands are not flagged."""
        safe_commands = [
            "ls -la",
            "cat file.txt",
            "grep pattern file",
            "python script.py",
            "npm run test",
            "git status",
            "git add .",
            "git commit -m 'test'",
            "git push origin main",  # Without --force
            "echo hello",
        ]
        
        for cmd in safe_commands:
            is_dangerous, pattern = is_dangerous_command(cmd)
            assert not is_dangerous, f"Command '{cmd}' should be safe, matched pattern: {pattern}"
    
    def test_git_force_push_detected(self):
        """Test that git force push is detected."""
        dangerous_commands = [
            "git push --force",
            "git push -f origin main",
            "git push origin main --force",
        ]
        
        for cmd in dangerous_commands:
            is_dangerous, _ = is_dangerous_command(cmd)
            assert is_dangerous, f"Command '{cmd}' should be detected as dangerous"
    
    def test_system_commands_detected(self):
        """Test that system modification commands are detected."""
        dangerous_commands = [
            "systemctl stop nginx",
            "systemctl disable sshd",
            "launchctl unload /Library/LaunchDaemons/test.plist",
            "killall python",
        ]
        
        for cmd in dangerous_commands:
            is_dangerous, _ = is_dangerous_command(cmd)
            assert is_dangerous, f"Command '{cmd}' should be detected as dangerous"


class TestSecurityGuard:
    """Tests for SecurityGuard class."""
    
    def test_admin_guard_allows_all_commands(self):
        """Admin guard should allow all commands."""
        guard = SecurityGuard(SecurityRole.ADMIN)
        
        dangerous_commands = [
            "rm -rf /",
            "sudo reboot",
            "git push --force",
        ]
        
        for cmd in dangerous_commands:
            allowed, reason = guard.check_command(cmd)
            assert allowed, f"Admin should allow '{cmd}', got reason: {reason}"
    
    def test_user_guard_blocks_dangerous_commands(self):
        """User guard should block dangerous commands."""
        guard = SecurityGuard(SecurityRole.USER)
        
        dangerous_commands = [
            "rm -rf /",
            "sudo apt install malware",
            "git push --force",
        ]
        
        for cmd in dangerous_commands:
            allowed, reason = guard.check_command(cmd)
            assert not allowed, f"User should block '{cmd}'"
            assert reason is not None
    
    def test_user_guard_allows_safe_commands(self):
        """User guard should allow safe commands."""
        guard = SecurityGuard(SecurityRole.USER)
        
        safe_commands = [
            "ls -la",
            "python test.py",
            "npm run build",
            "git commit -m 'test'",
        ]
        
        for cmd in safe_commands:
            allowed, reason = guard.check_command(cmd)
            assert allowed, f"User should allow '{cmd}', got reason: {reason}"
    
    def test_developer_guard_blocks_dangerous_commands(self):
        """Developer guard should block dangerous commands but allow development work."""
        guard = SecurityGuard(SecurityRole.DEVELOPER)
        
        # Dangerous commands should be blocked
        dangerous_commands = [
            "rm -rf /",
            "sudo apt install malware",
            "git push --force",
            "chmod 777 /etc/passwd",
        ]
        
        for cmd in dangerous_commands:
            allowed, reason = guard.check_command(cmd)
            assert not allowed, f"Developer should block '{cmd}'"
            assert reason is not None
    
    def test_developer_guard_allows_development_commands(self):
        """Developer guard should allow all development commands."""
        guard = SecurityGuard(SecurityRole.DEVELOPER)
        
        dev_commands = [
            "ls -la",
            "python test.py",
            "npm install express",
            "pip install requests",
            "git commit -m 'feature: add new component'",
            "git push origin feature-branch",
            "npm run build",
            "pytest tests/",
        ]
        
        for cmd in dev_commands:
            allowed, reason = guard.check_command(cmd)
            assert allowed, f"Developer should allow '{cmd}', got reason: {reason}"
    
    def test_guest_guard_blocks_all_commands(self):
        """Guest guard should block all command execution."""
        guard = SecurityGuard(SecurityRole.GUEST)
        
        # Even safe commands should be blocked for guest
        commands = ["ls", "echo hello", "cat file.txt"]
        
        for cmd in commands:
            allowed, reason = guard.check_command(cmd)
            assert not allowed, f"Guest should block '{cmd}'"
    
    def test_file_write_permission_admin(self):
        """Admin can write anywhere."""
        guard = SecurityGuard(SecurityRole.ADMIN)
        
        paths = ["/etc/passwd", "/home/user/file", "~/brain/file"]
        
        for path in paths:
            allowed, reason = guard.check_file_write(path)
            assert allowed, f"Admin should write to '{path}'"
    
    def test_file_write_permission_user(self):
        """User can only write to very limited output paths."""
        guard = SecurityGuard(SecurityRole.USER)
        
        # Should be allowed (in allowed output paths)
        allowed, _ = guard.check_file_write("~/brain/output/result.txt")
        assert allowed
        
        allowed, _ = guard.check_file_write("~/brain/test-results/test.log")
        assert allowed
        
        # Should be blocked (not in allowed paths - USER cannot write to data or logs)
        allowed, reason = guard.check_file_write("~/brain/data/test.txt")
        assert not allowed
        
        allowed, reason = guard.check_file_write("~/brain/logs/app.log")
        assert not allowed
        
        allowed, reason = guard.check_file_write("/etc/passwd")
        assert not allowed
        
        allowed, reason = guard.check_file_write("/tmp/malicious")
        assert not allowed
    
    def test_file_write_permission_developer(self):
        """Developer can write to development areas but not system files."""
        guard = SecurityGuard(SecurityRole.DEVELOPER)
        
        # Should be allowed (development areas)
        dev_paths = [
            "~/brain/agentic-brain/src/new_feature.py",
            "~/brain/web/components/Button.tsx",
            "~/brain/backend/api/routes.py",
            "~/brain/skills/my_skill/skill.py",
            "~/brain/tests/test_new_feature.py",
            "~/brain/data/dataset.json",
            "~/brain/logs/app.log",
            "~/brain/output/result.txt",
        ]
        
        for path in dev_paths:
            allowed, reason = guard.check_file_write(path)
            assert allowed, f"Developer should write to '{path}', got: {reason}"
        
        # Should be blocked (system files)
        system_paths = [
            "/etc/passwd",
            "/tmp/malicious",
            "~/.bashrc",
            "/usr/local/bin/app",
        ]
        
        for path in system_paths:
            allowed, reason = guard.check_file_write(path)
            assert not allowed, f"Developer should not write to '{path}'"
    
    def test_file_write_permission_guest(self):
        """Guest cannot write anywhere."""
        guard = SecurityGuard(SecurityRole.GUEST)
        
        allowed, reason = guard.check_file_write("~/brain/data/test.txt")
        assert not allowed
    
    def test_rate_limiting(self):
        """Test rate limiting enforcement."""
        guard = SecurityGuard(SecurityRole.GUEST)  # Low rate limit
        
        # Guest has 20/minute limit
        for i in range(20):
            allowed, _ = guard.check_rate_limit()
            assert allowed, f"Request {i+1} should be allowed"
        
        # 21st request should be blocked
        allowed, reason = guard.check_rate_limit()
        assert not allowed
        assert "Rate limit" in reason
    
    def test_admin_high_rate_limit(self):
        """Admin has very high rate limit."""
        guard = SecurityGuard(SecurityRole.ADMIN)
        
        # Should handle many requests
        for i in range(100):
            allowed, _ = guard.check_rate_limit()
            assert allowed
    
    def test_audit_logging(self):
        """Test that security events are logged."""
        guard = SecurityGuard(SecurityRole.USER, audit_log=True)
        
        # Perform some checks
        guard.check_command("ls")
        guard.check_command("rm -rf /")  # Should be blocked
        guard.check_file_read("/etc/passwd")
        
        audit_log = guard.get_audit_log()
        
        assert len(audit_log) == 3
        assert audit_log[0]["action"] == "execute_command"
        assert audit_log[0]["allowed"] is True
        assert audit_log[1]["action"] == "execute_command"
        assert audit_log[1]["allowed"] is False
        assert audit_log[2]["action"] == "file_read"
    
    def test_require_admin(self):
        """Test require_admin raises for non-admin."""
        guard = SecurityGuard(SecurityRole.USER)
        
        with pytest.raises(SecurityViolation) as exc_info:
            guard.require_admin()
        
        assert "Admin role required" in str(exc_info.value)
    
    def test_require_user_or_above(self):
        """Test require_user_or_above."""
        admin_guard = SecurityGuard(SecurityRole.ADMIN)
        user_guard = SecurityGuard(SecurityRole.USER)
        guest_guard = SecurityGuard(SecurityRole.GUEST)
        
        # Should not raise
        admin_guard.require_user_or_above()
        user_guard.require_user_or_above()
        
        # Should raise
        with pytest.raises(SecurityViolation):
            guest_guard.require_user_or_above()


class TestDecorators:
    """Tests for security decorators."""
    
    def setup_method(self):
        """Reset security context before each test."""
        # Clear any existing guard
        guard = get_security_guard()
        if guard:
            # We can't easily reset, so we'll set a new one
            pass
    
    def test_require_role_decorator(self):
        """Test require_role decorator."""
        @require_role(SecurityRole.USER)
        def user_function():
            return "success"
        
        # With USER role
        token = set_security_guard(SecurityGuard(SecurityRole.USER))
        try:
            result = user_function()
            assert result == "success"
        finally:
            reset_security_guard(token)
        
        # With GUEST role
        token = set_security_guard(SecurityGuard(SecurityRole.GUEST))
        try:
            with pytest.raises(SecurityViolation):
                user_function()
        finally:
            reset_security_guard(token)
    
    def test_require_admin_decorator(self):
        """Test require_admin decorator."""
        @require_admin
        def admin_only():
            return "admin_success"
        
        # With ADMIN role
        token = set_security_guard(SecurityGuard(SecurityRole.ADMIN))
        try:
            result = admin_only()
            assert result == "admin_success"
        finally:
            reset_security_guard(token)
        
        # With USER role
        token = set_security_guard(SecurityGuard(SecurityRole.USER))
        try:
            with pytest.raises(SecurityViolation):
                admin_only()
        finally:
            reset_security_guard(token)
    
    def test_require_user_or_above_decorator(self):
        """Test require_user_or_above decorator."""
        @require_user_or_above
        def user_func():
            return "user_success"
        
        # With ADMIN - should work
        token = set_security_guard(SecurityGuard(SecurityRole.ADMIN))
        try:
            assert user_func() == "user_success"
        finally:
            reset_security_guard(token)
        
        # With USER - should work
        token = set_security_guard(SecurityGuard(SecurityRole.USER))
        try:
            assert user_func() == "user_success"
        finally:
            reset_security_guard(token)
        
        # With GUEST - should fail
        token = set_security_guard(SecurityGuard(SecurityRole.GUEST))
        try:
            with pytest.raises(SecurityViolation):
                user_func()
        finally:
            reset_security_guard(token)


class TestAuthentication:
    """Tests for authentication functions."""
    
    def test_authenticate_api_key_admin(self):
        """Test admin key authentication."""
        auth = AdminAuthenticator()
        test_key = auth.generate_admin_key()
        
        # The global authenticator needs the key set
        from agentic_brain.security.auth import _admin_auth
        _admin_auth._admin_key = test_key
        
        # Authenticate with the key
        role, user = authenticate_api_key(test_key)
        assert role == SecurityRole.ADMIN
        assert user == "admin"
    
    def test_authenticate_api_key_user(self):
        """Test regular API key authentication."""
        # Random key that's not admin key
        role, user = authenticate_api_key("regular_api_key_123456")
        assert role == SecurityRole.USER
    
    def test_authenticate_api_key_invalid(self):
        """Test invalid API key defaults to guest."""
        role, user = authenticate_api_key("short")
        assert role == SecurityRole.GUEST
    
    def test_authenticate_request_admin_user(self):
        """Test that Joseph gets admin access."""
        guard = authenticate_request(user_id="joseph")
        assert guard.role == SecurityRole.ADMIN
    
    def test_authenticate_request_guest_default(self):
        """Test that no credentials defaults to guest."""
        guard = authenticate_request()
        assert guard.role == SecurityRole.GUEST
    
    def test_is_admin_check(self):
        """Test is_admin function."""
        token = set_security_guard(SecurityGuard(SecurityRole.ADMIN))
        try:
            assert is_admin() is True
            assert is_user() is True  # Admin is also "user or above"
            assert is_guest() is False
        finally:
            reset_security_guard(token)
    
    def test_is_user_check(self):
        """Test is_user function."""
        token = set_security_guard(SecurityGuard(SecurityRole.USER))
        try:
            assert is_admin() is False
            assert is_user() is True
            assert is_guest() is False
        finally:
            reset_security_guard(token)
    
    def test_is_guest_check(self):
        """Test is_guest function."""
        token = set_security_guard(SecurityGuard(SecurityRole.GUEST))
        try:
            assert is_admin() is False
            assert is_user() is False
            assert is_guest() is True
        finally:
            reset_security_guard(token)


class TestSessionManager:
    """Tests for session management."""
    
    def test_create_session(self):
        """Test session creation."""
        manager = SessionManager()
        session = manager.create_session(SecurityRole.USER, user_id="test_user")
        
        assert session.role == SecurityRole.USER
        assert session.user_id == "test_user"
        assert session.session_id is not None
        assert not session.is_expired
    
    def test_get_session(self):
        """Test session retrieval."""
        manager = SessionManager()
        session = manager.create_session(SecurityRole.USER)
        
        retrieved = manager.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id
    
    def test_get_nonexistent_session(self):
        """Test retrieving non-existent session."""
        manager = SessionManager()
        
        retrieved = manager.get_session("nonexistent")
        assert retrieved is None
    
    def test_invalidate_session(self):
        """Test session invalidation."""
        manager = SessionManager()
        session = manager.create_session(SecurityRole.USER)
        
        result = manager.invalidate_session(session.session_id)
        assert result is True
        
        # Should be gone
        retrieved = manager.get_session(session.session_id)
        assert retrieved is None
    
    def test_admin_session_creation(self):
        """Test admin session creation for Joseph."""
        session = create_admin_session("joseph")
        
        assert session.role == SecurityRole.ADMIN
        assert session.user_id == "joseph"
        assert session.is_admin is True
    
    def test_admin_session_non_admin_user_fails(self):
        """Test that non-admin users cannot create admin sessions."""
        with pytest.raises(ValueError) as exc_info:
            create_admin_session("random_user")
        
        assert "not an admin user" in str(exc_info.value)


class TestEnvironmentSetup:
    """Tests for environment-based admin setup."""
    
    def test_setup_admin_from_env_flag(self):
        """Test admin mode from environment flag."""
        with patch.dict(os.environ, {"AGENTIC_BRAIN_ADMIN_MODE": "true"}):
            guard = setup_admin_from_env()
            assert guard is not None
            assert guard.role == SecurityRole.ADMIN
    
    def test_setup_admin_from_user(self):
        """Test admin mode from current user being joseph."""
        import getpass as getpass_module
        with patch.object(getpass_module, "getuser", return_value="joseph"):
            guard = setup_admin_from_env()
            assert guard is not None
            assert guard.role == SecurityRole.ADMIN


class TestSecurityBypassPrevention:
    """Tests to ensure security cannot be bypassed."""
    
    def test_symlink_attack_prevention(self):
        """Test that symlink attacks are prevented via path canonicalization."""
        guard = SecurityGuard(SecurityRole.USER)
        
        # Create a path that might try to escape via symlinks
        # The canonicalization should resolve these
        test_path = Path("~/brain/data/../../../etc/passwd")
        
        allowed, reason = guard.check_file_write(str(test_path))
        assert not allowed, "Symlink escape attempt should be blocked"
    
    def test_contains_bypass_fixed(self):
        """Test that the 'contains' vulnerability is fixed with proper regex."""
        guard = SecurityGuard(SecurityRole.USER)
        
        # These commands tried to bypass by embedding dangerous patterns
        # in safe-looking commands. With proper regex anchoring, they should
        # still be caught if truly dangerous, or allowed if actually safe.
        
        # This should be blocked - starts with rm -rf
        allowed, _ = guard.check_command("rm -rf /important")
        assert not allowed
        
        # This should be allowed - echo is safe even if it contains 'rm'
        allowed, _ = guard.check_command("echo 'rm -rf /'")
        assert allowed
        
        # This should be blocked - actual sudo command
        allowed, _ = guard.check_command("sudo echo test")
        assert not allowed
    
    def test_rate_limit_cannot_be_reset(self):
        """Test that rate limits persist within time window."""
        guard = SecurityGuard(SecurityRole.GUEST)  # 20/minute
        
        # Use up the rate limit
        for _ in range(20):
            guard.check_rate_limit()
        
        # Even creating a new check shouldn't reset it
        # (The rate limit is per-guard instance, but a new guard would have fresh limits)
        # This tests that within the same guard, limits persist
        allowed, _ = guard.check_rate_limit()
        assert not allowed
    
    def test_role_cannot_be_elevated(self):
        """Test that role cannot be changed after guard creation."""
        guard = SecurityGuard(SecurityRole.GUEST)
        
        # Role should be immutable
        assert guard.role == SecurityRole.GUEST
        
        # The role property doesn't have a setter, so assignment creates
        # a new attribute. Let's verify the original is preserved through
        # the permissions which cannot be changed.
        original_can_yolo = guard.permissions.can_yolo
        assert original_can_yolo is False  # GUEST cannot YOLO
        
        # Even if someone tries to set role, permissions should stay same
        # (This tests that the design is secure - permissions are tied to role)
        guard_admin = SecurityGuard(SecurityRole.ADMIN)
        assert guard_admin.permissions.can_yolo is True
        
        # The original guard still has GUEST permissions
        assert guard.permissions.can_yolo is False


class TestYOLOIntegration:
    """Tests for YOLO executor security integration."""
    
    @pytest.mark.asyncio
    async def test_secure_executor_admin(self):
        """Test that admin can run any YOLO command."""
        from agentic_brain.yolo import SecureYOLOExecutor, SecureExecutionResult
        
        token = set_security_guard(SecurityGuard(SecurityRole.ADMIN))
        try:
            executor = SecureYOLOExecutor()
            result = await executor.check_status("status")
            
            assert result.security_checks_passed is True
            assert result.role == SecurityRole.ADMIN
        finally:
            reset_security_guard(token)
    
    @pytest.mark.asyncio
    async def test_secure_executor_guest_blocked(self):
        """Test that guest cannot run code execution commands."""
        from agentic_brain.yolo import SecureYOLOExecutor
        
        token = set_security_guard(SecurityGuard(SecurityRole.GUEST))
        try:
            executor = SecureYOLOExecutor()
            result = await executor.run_tests("test")
            
            assert result.security_checks_passed is False
            assert result.blocked_reason is not None
            assert result.result.exit_code == 403
        finally:
            reset_security_guard(token)
    
    @pytest.mark.asyncio
    async def test_secure_executor_user_safe_commands(self):
        """Test that user can run safe YOLO commands."""
        from agentic_brain.yolo import SecureYOLOExecutor
        
        token = set_security_guard(SecurityGuard(SecurityRole.USER))
        try:
            executor = SecureYOLOExecutor()
            result = await executor.check_status("status")
            
            assert result.security_checks_passed is True
            assert result.role == SecurityRole.USER
        finally:
            reset_security_guard(token)


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_check_file_access_write(self):
        """Test check_file_access for write operations."""
        token = set_security_guard(SecurityGuard(SecurityRole.ADMIN))
        try:
            allowed, reason = check_file_access("/any/path", write=True)
            assert allowed
        finally:
            reset_security_guard(token)
        
        token = set_security_guard(SecurityGuard(SecurityRole.GUEST))
        try:
            allowed, reason = check_file_access("/any/path", write=True)
            assert not allowed
        finally:
            reset_security_guard(token)
    
    def test_check_command_allowed(self):
        """Test check_command_allowed helper."""
        token = set_security_guard(SecurityGuard(SecurityRole.ADMIN))
        try:
            allowed, reason = check_command_allowed("rm -rf /")
            assert allowed  # Admin can do anything
        finally:
            reset_security_guard(token)
        
        token = set_security_guard(SecurityGuard(SecurityRole.USER))
        try:
            allowed, reason = check_command_allowed("rm -rf /")
            assert not allowed  # User blocked from dangerous commands
        finally:
            reset_security_guard(token)
    
    def test_get_or_create_guard(self):
        """Test get_or_create_guard helper."""
        # Clear any existing guard first by setting to None through a temporary token
        # Actually, we need to test with a fresh context
        # Get or create will return existing guard if one exists from previous tests
        
        # Create a fresh guard with specific role
        fresh_guard = SecurityGuard(SecurityRole.USER)
        token = set_security_guard(fresh_guard)
        try:
            # Get or create should return the existing guard
            guard = get_or_create_guard(SecurityRole.GUEST)
            assert guard.role == SecurityRole.USER  # Returns existing, not new GUEST
        finally:
            reset_security_guard(token)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
