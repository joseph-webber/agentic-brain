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
from .llm_guard import LLMRolePermissions, LLMSecurityGuard
from .platform_security import (
    STANDALONE_PROFILE,
    WOOCOMMERCE_PROFILE,
    AccessLevel,
    PlatformSecurityProfile,
    normalize_endpoint,
)
from .prompt_filter import PromptFilter, PromptFilterError
from .roles import (
    DANGEROUS_COMMAND_PATTERNS,
    ROLE_PERMISSIONS,
    RolePermissions,
    SecurityRole,
    get_permissions,
    is_dangerous_command,
)
from .tool_guard import (
    EXPENSIVE_TOOLS,
    block_expensive_for_guest,
    can_use_tool,
    check_tool_access,
    check_web_search_allowed,
    get_allowed_tools,
    is_tool_expensive,
)

__all__ = [
    "BackgroundWorker",
    "BaseSecureAgent",
    "DANGEROUS_COMMAND_PATTERNS",
    "EventProcessor",
    "ExploreAgent",
    "LLMRolePermissions",
    "AccessLevel",
    "LLMSecurityGuard",
    "PlatformSecurityProfile",
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
    "check_tool_access",
    "check_web_search_allowed",
    "get_or_create_guard",
    "get_allowed_tools",
    "get_permissions",
    "get_security_guard",
    "is_dangerous_command",
    "is_tool_expensive",
    "STANDALONE_PROFILE",
    "WOOCOMMERCE_PROFILE",
    "normalize_endpoint",
    "EXPENSIVE_TOOLS",
    "block_expensive_for_guest",
    "can_use_tool",
    "require_admin",
    "require_role",
    "require_user_or_above",
    "reset_security_guard",
    "set_security_guard",
]
