# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Base agent class with built-in security enforcement.

All autonomous agents in agentic-brain MUST inherit from BaseSecureAgent
to ensure the 4-tier security model is enforced consistently.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .guards import SecurityGuard, SecurityViolation, set_security_guard
from .roles import SecurityRole

logger = logging.getLogger(__name__)


class BaseSecureAgent(ABC):
    """
    Base class for all autonomous agents with security enforcement.
    
    The 4-tier security model applies to ALL agent types:
    - FULL_ADMIN: Complete unrestricted access (Joseph only)
    - SAFE_ADMIN: Full access with safety guardrails (Developers/Trusted admins)
    - USER: API-only access for customers/employees (no machine access)
    - GUEST: Very restricted, FAQ/help documentation only (anonymous visitors)
    
    Every agent operation MUST check security role before executing.
    
    Example:
        >>> class MyTaskAgent(BaseSecureAgent):
        ...     def _execute_impl(self, action: str, **kwargs):
        ...         # Implementation goes here
        ...         return {"result": "done"}
        ...
        >>> agent = MyTaskAgent(security_role=SecurityRole.USER)
        >>> agent.execute("process_data", data="...")
    """
    
    def __init__(
        self,
        security_role: SecurityRole = SecurityRole.USER,
        *,
        agent_id: str | None = None,
        audit_log: bool = True,
    ):
        """
        Initialize secure agent.
        
        Args:
            security_role: The security role this agent runs under
            agent_id: Unique identifier for this agent (for logging/audit)
            audit_log: Whether to enable audit logging
        """
        self.security_role = security_role
        self.agent_id = agent_id or f"{self.__class__.__name__}-{id(self)}"
        self.guard = SecurityGuard(security_role, audit_log=audit_log)
        
        # Set the guard as the current context guard
        set_security_guard(self.guard)
        
        logger.info(
            f"Initialized {self.__class__.__name__} with role {security_role.value} "
            f"(agent_id={self.agent_id})"
        )
    
    def execute(self, action: str, **kwargs: Any) -> Any:
        """
        Execute an action with security enforcement.
        
        This method wraps all agent actions and enforces security checks
        before delegating to the implementation.
        
        Args:
            action: The action to perform (e.g., "read_file", "call_api", "execute_command")
            **kwargs: Action-specific parameters
            
        Returns:
            Result from the implementation
            
        Raises:
            SecurityViolation: If the action is not permitted for this role
        """
        # Pre-execution security checks based on action type
        self._check_action_allowed(action, **kwargs)
        
        # Execute the implementation
        try:
            result = self._execute_impl(action, **kwargs)
            logger.debug(
                f"Agent {self.agent_id} successfully executed {action} "
                f"with role {self.security_role.value}"
            )
            return result
        except Exception as e:
            logger.error(
                f"Agent {self.agent_id} failed to execute {action}: {e}",
                exc_info=True
            )
            raise
    
    @abstractmethod
    def _execute_impl(self, action: str, **kwargs: Any) -> Any:
        """
        Agent-specific implementation of action execution.
        
        Subclasses MUST implement this method.
        Security checks are already done by execute().
        
        Args:
            action: The action to perform
            **kwargs: Action-specific parameters
            
        Returns:
            Implementation-specific result
        """
        pass
    
    def _check_action_allowed(self, action: str, **kwargs: Any) -> None:
        """
        Check if an action is allowed based on role and action type.
        
        Args:
            action: The action being attempted
            **kwargs: Action parameters (may contain paths, commands, etc.)
            
        Raises:
            SecurityViolation: If the action is not permitted
        """
        # Command execution check
        if action in ("execute_command", "yolo", "shell"):
            command = kwargs.get("command", "")
            allowed, reason = self.guard.check_command(command)
            if not allowed:
                raise SecurityViolation(
                    reason or "Command execution not allowed",
                    self.security_role,
                    action,
                    command[:100]
                )
        
        # File write check
        elif action in ("write_file", "create_file", "delete_file", "modify_file"):
            path = kwargs.get("path", "")
            allowed, reason = self.guard.check_file_write(path)
            if not allowed:
                raise SecurityViolation(
                    reason or "File write not allowed",
                    self.security_role,
                    action,
                    str(path)
                )
        
        # File read check (for restricted roles)
        elif action in ("read_file", "list_directory") and self.security_role < SecurityRole.USER:
            path = kwargs.get("path", "")
            allowed, reason = self.guard.check_file_read(path)
            if not allowed:
                raise SecurityViolation(
                    reason or "File read not allowed",
                    self.security_role,
                    action,
                    str(path)
                )
        
        # Code execution check
        elif action in ("execute_code", "eval", "exec"):
            allowed, reason = self.guard.check_code_execution()
            if not allowed:
                raise SecurityViolation(
                    reason or "Code execution not allowed",
                    self.security_role,
                    action,
                )
        
        # Config modification check
        elif action in ("modify_config", "update_settings", "change_config"):
            allowed, reason = self.guard.check_config_modification()
            if not allowed:
                raise SecurityViolation(
                    reason or "Configuration modification not allowed",
                    self.security_role,
                    action,
                )
        
        # Admin API check
        elif action in ("admin_api", "manage_users", "system_control"):
            allowed, reason = self.guard.check_admin_api_access()
            if not allowed:
                raise SecurityViolation(
                    reason or "Admin API access not allowed",
                    self.security_role,
                    action,
                )
        
        # Secrets access check
        elif action in ("read_secret", "access_credentials", "get_api_key"):
            allowed, reason = self.guard.check_secrets_access()
            if not allowed:
                raise SecurityViolation(
                    reason or "Secrets access not allowed",
                    self.security_role,
                    action,
                )
        
        # Rate limit check (for all actions)
        allowed, reason = self.guard.check_rate_limit()
        if not allowed:
            raise SecurityViolation(
                reason or "Rate limit exceeded",
                self.security_role,
                action,
            )
    
    def get_permissions_summary(self) -> Dict[str, Any]:
        """
        Get a summary of this agent's permissions.
        
        Returns:
            Dictionary containing permission details
        """
        perms = self.guard.permissions
        return {
            "role": self.security_role.value,
            "agent_id": self.agent_id,
            "can_execute_commands": perms.can_yolo,
            "can_write_files": perms.can_write_files,
            "can_read_all_files": perms.can_read_all_files,
            "can_execute_code": perms.can_execute_code,
            "can_modify_config": perms.can_modify_config,
            "can_access_secrets": perms.can_access_secrets,
            "can_access_apis": perms.can_access_apis,
            "llm_access_level": perms.llm_access_level,
            "rate_limit_per_minute": perms.rate_limit_per_minute,
            "api_only_mode": perms.api_only_mode,
            "allowed_apis": list(perms.allowed_apis),
            "allowed_api_scopes": list(perms.allowed_api_scopes) if perms.allowed_api_scopes else [],
        }
    
    def get_audit_log(self) -> list[Dict[str, Any]]:
        """
        Get the security audit log for this agent.
        
        Returns:
            List of audit log entries
        """
        return self.guard.get_audit_log()
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"role={self.security_role.value}, "
            f"agent_id={self.agent_id})"
        )


class TaskAgent(BaseSecureAgent):
    """
    Example task agent that processes tasks with security enforcement.
    
    This demonstrates how to implement a concrete agent type.
    """
    
    def _execute_impl(self, action: str, **kwargs: Any) -> Any:
        """Execute a task-specific action."""
        if action == "process_task":
            task_data = kwargs.get("task_data", {})
            # Process the task...
            return {"status": "completed", "result": task_data}
        
        elif action == "call_api":
            api_name = kwargs.get("api", "")
            # Check if API access is allowed
            if not self.guard.permissions.can_access_apis:
                raise SecurityViolation(
                    f"API access not permitted for role {self.security_role.value}",
                    self.security_role,
                    action,
                    api_name
                )
            if (
                self.guard.permissions.allowed_apis
                and "*" not in self.guard.permissions.allowed_apis
                and api_name not in self.guard.permissions.allowed_apis
            ):
                raise SecurityViolation(
                    f"API {api_name} not in allowed APIs for role {self.security_role.value}",
                    self.security_role,
                    action,
                    api_name,
                )
            # Call the API...
            return {"api": api_name, "result": "success"}
        
        else:
            raise ValueError(f"Unknown action: {action}")


class ExploreAgent(BaseSecureAgent):
    """
    Exploration/research agent with security enforcement.
    
    Used for exploring codebases, researching information, etc.
    Typically runs at USER or SAFE_ADMIN level.
    """
    
    def _execute_impl(self, action: str, **kwargs: Any) -> Any:
        """Execute an exploration action."""
        if action == "explore_codebase":
            path = kwargs.get("path", "")
            # Exploration logic...
            return {"explored": path, "findings": []}
        
        elif action == "research_topic":
            topic = kwargs.get("topic", "")
            # Research logic...
            return {"topic": topic, "results": []}
        
        else:
            raise ValueError(f"Unknown action: {action}")


class BackgroundWorker(BaseSecureAgent):
    """
    Background worker agent with security enforcement.
    
    Processes background jobs, queued tasks, etc.
    """
    
    def _execute_impl(self, action: str, **kwargs: Any) -> Any:
        """Execute a background worker action."""
        if action == "process_job":
            job_data = kwargs.get("job", {})
            # Process the job...
            return {"job_id": job_data.get("id"), "status": "completed"}
        
        else:
            raise ValueError(f"Unknown action: {action}")


class EventProcessor(BaseSecureAgent):
    """
    Event processor agent with security enforcement.
    
    Handles events from event bus, webhooks, etc.
    """
    
    def _execute_impl(self, action: str, **kwargs: Any) -> Any:
        """Execute event processing."""
        if action == "process_event":
            event_data = kwargs.get("event", {})
            event_type = event_data.get("type", "")
            # Process the event...
            return {"event_type": event_type, "processed": True}
        
        else:
            raise ValueError(f"Unknown action: {action}")
