# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for agent security enforcement."""

import pytest

from agentic_brain.security import (
    BaseSecureAgent,
    SecurityRole,
    SecurityViolation,
    TaskAgent,
    ExploreAgent,
    BackgroundWorker,
    EventProcessor,
)


class TestSecureAgent(BaseSecureAgent):
    """Test agent implementation."""
    
    def _execute_impl(self, action: str, **kwargs):
        """Simple test implementation."""
        if action == "test_action":
            return {"result": "success"}
        elif action == "call_api":
            api = kwargs.get("api", "")
            return {"api": api, "result": "called"}
        elif action == "execute_command":
            command = kwargs.get("command", "")
            return {"command": command, "output": "executed"}
        elif action == "write_file":
            path = kwargs.get("path", "")
            return {"path": path, "written": True}
        elif action == "read_file":
            path = kwargs.get("path", "")
            return {"path": path, "content": "file content"}
        else:
            raise ValueError(f"Unknown action: {action}")


class TestBaseSecureAgent:
    """Test BaseSecureAgent security enforcement."""
    
    def test_guest_role_restrictions(self):
        """GUEST role has very limited permissions."""
        agent = TestSecureAgent(security_role=SecurityRole.GUEST)
        
        # Cannot execute commands
        with pytest.raises(SecurityViolation):
            agent.execute("execute_command", command="ls")
        
        # Cannot write files
        with pytest.raises(SecurityViolation):
            agent.execute("write_file", path="/tmp/test.txt")
        
        # Cannot read most files
        with pytest.raises(SecurityViolation):
            agent.execute("read_file", path="~/brain/data/secret.txt")
    
    def test_user_role_api_only(self):
        """USER role can only access APIs, not machine."""
        agent = TestSecureAgent(security_role=SecurityRole.USER)
        
        # Can call allowed APIs
        result = agent.execute("call_api", api="woocommerce")
        assert result["api"] == "woocommerce"
        
        # Cannot execute commands (API-only mode)
        with pytest.raises(SecurityViolation) as exc_info:
            agent.execute("execute_command", command="ls")
        assert "not permitted" in str(exc_info.value)
        
        # Cannot write files
        with pytest.raises(SecurityViolation):
            agent.execute("write_file", path="~/brain/output/test.txt")
        
        # Cannot execute code
        with pytest.raises(SecurityViolation):
            agent.execute("execute_code", code="print('hello')")
    
    def test_safe_admin_guardrails(self):
        """SAFE_ADMIN has access but with safety guardrails."""
        agent = TestSecureAgent(security_role=SecurityRole.SAFE_ADMIN)
        
        # Can execute safe commands
        result = agent.execute("execute_command", command="ls -la")
        assert result["command"] == "ls -la"
        
        # Blocked from dangerous commands
        with pytest.raises(SecurityViolation):
            agent.execute("execute_command", command="rm -rf /")
        
        with pytest.raises(SecurityViolation):
            agent.execute("execute_command", command="DROP DATABASE production")
        
        # Can write to allowed paths
        result = agent.execute("write_file", path="~/brain/output/test.txt")
        assert result["written"] is True
    
    def test_full_admin_unrestricted(self):
        """FULL_ADMIN has complete access."""
        agent = TestSecureAgent(security_role=SecurityRole.FULL_ADMIN)
        
        # Can execute any command (in test, just checking security allows it)
        agent._check_action_allowed("execute_command", command="rm -rf /tmp/test")
        
        # Can write anywhere
        agent._check_action_allowed("write_file", path="/etc/test.conf")
        
        # Can access secrets
        agent._check_action_allowed("read_secret", secret_name="api_key")
    
    def test_permissions_summary(self):
        """Test permissions summary for each role."""
        guest = TestSecureAgent(security_role=SecurityRole.GUEST)
        user = TestSecureAgent(security_role=SecurityRole.USER)
        safe_admin = TestSecureAgent(security_role=SecurityRole.SAFE_ADMIN)
        full_admin = TestSecureAgent(security_role=SecurityRole.FULL_ADMIN)
        
        # GUEST permissions
        guest_perms = guest.get_permissions_summary()
        assert guest_perms["role"] == "guest"
        assert guest_perms["can_execute_commands"] is False
        assert guest_perms["can_write_files"] is False
        assert guest_perms["api_only_mode"] is True
        
        # USER permissions
        user_perms = user.get_permissions_summary()
        assert user_perms["role"] == "user"
        assert user_perms["can_execute_commands"] is False
        assert user_perms["api_only_mode"] is True
        assert "woocommerce" in user_perms["allowed_apis"]
        
        # SAFE_ADMIN permissions
        admin_perms = safe_admin.get_permissions_summary()
        assert admin_perms["role"] == "safe_admin"
        assert admin_perms["can_execute_commands"] is True
        assert admin_perms["can_write_files"] is True
        assert admin_perms["api_only_mode"] is False
        
        # FULL_ADMIN permissions
        full_perms = full_admin.get_permissions_summary()
        assert full_perms["role"] == "full_admin"
        assert full_perms["can_access_secrets"] is True
        assert full_perms["can_access_admin_api"] is True
    
    def test_audit_logging(self):
        """Test that security events are logged."""
        agent = TestSecureAgent(security_role=SecurityRole.USER)
        
        # Try an allowed action
        agent.execute("call_api", api="woocommerce")
        
        # Try a blocked action
        try:
            agent.execute("execute_command", command="ls")
        except SecurityViolation:
            pass
        
        # Check audit log
        audit = agent.get_audit_log()
        assert len(audit) > 0
        
        # Find the blocked command
        blocked = [e for e in audit if e["action"] == "execute_command" and not e["allowed"]]
        assert len(blocked) > 0
        assert "not permitted" in blocked[0]["reason"]
    
    def test_rate_limiting(self):
        """Test rate limiting enforcement."""
        agent = TestSecureAgent(security_role=SecurityRole.GUEST)
        
        # GUEST has strict rate limit (20/minute)
        # Try to exceed it
        for i in range(25):
            try:
                agent.execute("test_action")
            except SecurityViolation as e:
                # Should eventually hit rate limit
                if "Rate limit" in str(e):
                    break
        else:
            pytest.fail("Rate limit not enforced")
    
    def test_agent_id_in_logs(self):
        """Test that agent_id appears in logs and audit."""
        agent = TestSecureAgent(
            security_role=SecurityRole.USER,
            agent_id="test-agent-123"
        )
        
        assert agent.agent_id == "test-agent-123"
        
        # Execute an action
        agent.execute("test_action")
        
        # Check audit log has agent_id context
        perms = agent.get_permissions_summary()
        assert perms["agent_id"] == "test-agent-123"


class TestTaskAgent:
    """Test TaskAgent implementation."""
    
    def test_task_agent_process_task(self):
        """TaskAgent can process tasks."""
        agent = TaskAgent(security_role=SecurityRole.USER)
        
        result = agent.execute("process_task", task_data={"id": 1, "name": "test"})
        assert result["status"] == "completed"
        assert result["result"]["id"] == 1
    
    def test_task_agent_call_api(self):
        """TaskAgent can call allowed APIs."""
        agent = TaskAgent(security_role=SecurityRole.USER)
        
        result = agent.execute("call_api", api="woocommerce")
        assert result["api"] == "woocommerce"
        assert result["result"] == "success"
    
    def test_task_agent_blocked_api(self):
        """TaskAgent blocked from disallowed APIs."""
        agent = TaskAgent(security_role=SecurityRole.GUEST)
        
        # GUEST cannot call woocommerce API
        with pytest.raises(SecurityViolation) as exc_info:
            agent.execute("call_api", api="woocommerce")
        assert "not in allowed APIs" in str(exc_info.value)


class TestExploreAgent:
    """Test ExploreAgent implementation."""
    
    def test_explore_agent_codebase(self):
        """ExploreAgent can explore codebases."""
        agent = ExploreAgent(security_role=SecurityRole.SAFE_ADMIN)
        
        result = agent.execute("explore_codebase", path="~/brain/src")
        assert result["explored"] == "~/brain/src"
        assert "findings" in result
    
    def test_explore_agent_research(self):
        """ExploreAgent can research topics."""
        agent = ExploreAgent(security_role=SecurityRole.USER)
        
        result = agent.execute("research_topic", topic="authentication")
        assert result["topic"] == "authentication"
        assert "results" in result


class TestBackgroundWorker:
    """Test BackgroundWorker implementation."""
    
    def test_worker_process_job(self):
        """BackgroundWorker can process jobs."""
        worker = BackgroundWorker(security_role=SecurityRole.USER)
        
        result = worker.execute("process_job", job={"id": "job-123", "type": "sync"})
        assert result["job_id"] == "job-123"
        assert result["status"] == "completed"


class TestEventProcessor:
    """Test EventProcessor implementation."""
    
    def test_processor_handle_event(self):
        """EventProcessor can handle events."""
        processor = EventProcessor(security_role=SecurityRole.USER)
        
        event = {
            "type": "order.created",
            "data": {"order_id": 12345}
        }
        result = processor.execute("process_event", event=event)
        assert result["event_type"] == "order.created"
        assert result["processed"] is True


class TestSecurityEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_command(self):
        """Test handling of empty commands."""
        agent = TestSecureAgent(security_role=SecurityRole.SAFE_ADMIN)
        
        # Empty command should still go through checks
        agent._check_action_allowed("execute_command", command="")
    
    def test_api_wildcard_access(self):
        """Test wildcard API access for SAFE_ADMIN."""
        agent = TestSecureAgent(security_role=SecurityRole.SAFE_ADMIN)
        
        # SAFE_ADMIN has wildcard API access
        result = agent.execute("call_api", api="custom_api")
        assert result["api"] == "custom_api"
    
    def test_unknown_action(self):
        """Test handling of unknown actions."""
        agent = TestSecureAgent(security_role=SecurityRole.USER)
        
        with pytest.raises(ValueError) as exc_info:
            agent.execute("unknown_action")
        assert "Unknown action" in str(exc_info.value)
    
    def test_role_comparison(self):
        """Test SecurityRole comparison operators."""
        assert SecurityRole.GUEST < SecurityRole.USER
        assert SecurityRole.USER < SecurityRole.SAFE_ADMIN
        assert SecurityRole.SAFE_ADMIN < SecurityRole.FULL_ADMIN
        
        assert SecurityRole.FULL_ADMIN > SecurityRole.SAFE_ADMIN
        assert SecurityRole.SAFE_ADMIN >= SecurityRole.USER
        assert SecurityRole.USER <= SecurityRole.USER


class TestSecurityIntegration:
    """Integration tests for agent security."""
    
    def test_multi_agent_scenario(self):
        """Test multiple agents with different roles."""
        # Customer chatbot (USER role)
        chatbot = TaskAgent(
            security_role=SecurityRole.USER,
            agent_id="customer-chatbot"
        )
        
        # Developer tool (SAFE_ADMIN role)
        dev_tool = ExploreAgent(
            security_role=SecurityRole.SAFE_ADMIN,
            agent_id="dev-explorer"
        )
        
        # System monitor (FULL_ADMIN role)
        monitor = BackgroundWorker(
            security_role=SecurityRole.FULL_ADMIN,
            agent_id="system-monitor"
        )
        
        # Chatbot can only call APIs
        chatbot.execute("call_api", api="woocommerce")
        with pytest.raises(SecurityViolation):
            chatbot.execute("execute_command", command="ls")
        
        # Dev tool can explore and run safe commands
        dev_tool.execute("explore_codebase", path="~/brain/src")
        dev_tool.execute("research_topic", topic="security")
        
        # Monitor has full access
        monitor.execute("process_job", job={"id": "monitor-123"})
    
    def test_security_context_isolation(self):
        """Test that agents have isolated security contexts."""
        agent1 = TestSecureAgent(
            security_role=SecurityRole.USER,
            agent_id="agent-1"
        )
        agent2 = TestSecureAgent(
            security_role=SecurityRole.SAFE_ADMIN,
            agent_id="agent-2"
        )
        
        # Agent 1 blocked from commands
        with pytest.raises(SecurityViolation):
            agent1.execute("execute_command", command="ls")
        
        # Agent 2 allowed
        agent2.execute("execute_command", command="ls")
        
        # Audit logs are separate
        audit1 = agent1.get_audit_log()
        audit2 = agent2.get_audit_log()
        
        # Agent 1 should have a blocked command
        blocked = [e for e in audit1 if not e["allowed"]]
        assert len(blocked) > 0
        
        # Agent 2's log should be different
        assert audit1 != audit2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
