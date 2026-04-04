# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tool access guard for role-based restrictions."""

from __future__ import annotations

from typing import FrozenSet

from .roles import ROLE_PERMISSIONS, SecurityRole

EXPENSIVE_TOOLS: FrozenSet[str] = frozenset({
    "web_search",
    "web_fetch",
    "browse_web",
    "execute_code",
    "bash",
    "shell",
    "file_write",
    "file_read",
    "heavy_llm",
    "llm_call",
})

WEB_SEARCH_TOOLS: FrozenSet[str] = frozenset({
    "web_search",
    "web_fetch",
    "browse_web",
})

HEAVY_LLM_TOOLS: FrozenSet[str] = frozenset({
    "heavy_llm",
    "llm_call",
})


def check_tool_access(role: SecurityRole, tool: str) -> bool:
    """Return whether a role may access a tool."""
    perms = ROLE_PERMISSIONS[role]

    if perms.allowed_tools is None:
        return True

    if tool in WEB_SEARCH_TOOLS and not perms.can_web_search:
        return False

    if tool in HEAVY_LLM_TOOLS and not perms.can_heavy_llm:
        return False

    if role == SecurityRole.GUEST and tool in EXPENSIVE_TOOLS:
        return False

    return tool in perms.allowed_tools


def can_use_tool(role: SecurityRole, tool_name: str) -> bool:
    """Backward-compatible wrapper for tool access checks."""
    perms = ROLE_PERMISSIONS[role]
    if not perms.can_use_tools:
        return False
    return check_tool_access(role, tool_name)


def is_tool_expensive(tool_name: str) -> bool:
    """Check if a tool is considered expensive/heavy."""
    return tool_name in EXPENSIVE_TOOLS


def block_expensive_for_guest(role: SecurityRole, tool_name: str) -> tuple[bool, str]:
    """Block expensive operations for restricted roles."""
    if role == SecurityRole.GUEST and tool_name in EXPENSIVE_TOOLS:
        return False, (
            f"GUEST cannot use '{tool_name}' - restricted to help and shopping. "
            f"Expensive operations blocked to prevent system thrashing."
        )

    if role == SecurityRole.USER and tool_name in EXPENSIVE_TOOLS:
        return False, (
            f"USER cannot use '{tool_name}' - restricted to API operations. "
            f"Expensive operations blocked to prevent system abuse."
        )

    return True, ""


def get_allowed_tools(role: SecurityRole) -> FrozenSet[str] | None:
    """Get the tool whitelist for a role, if any."""
    return ROLE_PERMISSIONS[role].allowed_tools


def check_web_search_allowed(role: SecurityRole) -> tuple[bool, str]:
    """Check whether a role can perform web search."""
    perms = ROLE_PERMISSIONS[role]
    if not perms.can_web_search:
        return False, (
            f"Web search blocked for {role.value} - expensive operation. "
            f"Prevents system thrashing and API costs."
        )
    return True, ""
