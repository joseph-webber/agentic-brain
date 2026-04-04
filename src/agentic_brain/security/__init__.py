# SPDX-License-Identifier: Apache-2.0
"""Security roles, guards, agent wrappers, and LLM controls."""

from .base_agent import (
    BackgroundWorker,
    BaseSecureAgent,
    EventProcessor,
    ExploreAgent,
    TaskAgent,
)
from .guards import (
    SecurityGuard,
    SecurityViolation,
    check_command_allowed,
    check_file_access,
    get_or_create_guard,
    get_security_guard,
    require_admin,
    require_role,
    require_user_or_above,
    reset_security_guard,
    set_security_guard,
)
from .llm_guard import LLMSecurityGuard, LLMRolePermissions
from .prompt_filter import PromptFilter, PromptFilterError
from .roles import (
    DANGEROUS_COMMAND_PATTERNS,
    ROLE_PERMISSIONS,
    RolePermissions,
    SecurityRole,
    get_permissions,
    is_dangerous_command,
)

__all__ = [
    "BackgroundWorker",
    "BaseSecureAgent",
    "DANGEROUS_COMMAND_PATTERNS",
    "EventProcessor",
    "ExploreAgent",
    "LLMRolePermissions",
    "LLMSecurityGuard",
    "PromptFilter",
    "PromptFilterError",
    "ROLE_PERMISSIONS",
    "RolePermissions",
    "SecurityGuard",
    "SecurityRole",
    "SecurityViolation",
    "TaskAgent",
    "check_command_allowed",
    "check_file_access",
    "get_or_create_guard",
    "get_permissions",
    "get_security_guard",
    "is_dangerous_command",
    "require_admin",
    "require_role",
    "require_user_or_above",
    "reset_security_guard",
    "set_security_guard",
]
