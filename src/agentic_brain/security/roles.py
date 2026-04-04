# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
Security roles and permissions definitions.

Four-tier security model:
- FULL_ADMIN: Complete unrestricted access (Joseph only)
- SAFE_ADMIN: Full access with safety guardrails (developers/trusted admins)
- USER: API-only access for customers/employees (no machine access)
- GUEST: Public or guest-scoped platform access plus FAQ/help content (anonymous visitors)

Legacy role names remain as enum aliases for backward compatibility:
- ADMIN -> FULL_ADMIN
- DEVELOPER -> SAFE_ADMIN
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import FrozenSet, Pattern


class SecurityRole(Enum):
    """Security role levels with increasing privileges."""
    
    GUEST = "guest"              # Most restricted - FAQ/help only (anonymous visitors)
    USER = "user"                # API-only access (customers/employees)
    SAFE_ADMIN = "safe_admin"    # Full access with guardrails (developers/trusted admins)
    FULL_ADMIN = "full_admin"    # Complete unrestricted access (Joseph only)
    ADMIN = "full_admin"         # Backwards-compatible alias
    DEVELOPER = "safe_admin"     # Backwards-compatible alias
    
    def __lt__(self, other: "SecurityRole") -> bool:
        order = {
            SecurityRole.GUEST: 0, 
            SecurityRole.USER: 1, 
            SecurityRole.SAFE_ADMIN: 2,
            SecurityRole.FULL_ADMIN: 3
        }
        return order[self] < order[other]
    
    def __le__(self, other: "SecurityRole") -> bool:
        return self == other or self < other
    
    def __gt__(self, other: "SecurityRole") -> bool:
        return not self <= other
    
    def __ge__(self, other: "SecurityRole") -> bool:
        return not self < other


# Dangerous command patterns - use proper regex anchoring for security
# Fixed vulnerability: was using simple 'contains' which could be bypassed
DANGEROUS_COMMAND_PATTERNS: list[Pattern[str]] = [
    # Destructive file operations
    re.compile(r"^rm\s+(-[rf]+\s+)*(/|~|\.\.)", re.IGNORECASE),
    re.compile(r"^rm\s+-rf\s", re.IGNORECASE),
    re.compile(r"^rmdir\s+(-p\s+)*(/|~)", re.IGNORECASE),
    re.compile(r"^shred\b", re.IGNORECASE),
    
    # System modification
    re.compile(r"^sudo\b", re.IGNORECASE),
    re.compile(r"^su\b", re.IGNORECASE),
    re.compile(r"^chmod\s+[0-7]*7[0-7]*", re.IGNORECASE),  # World-writable
    re.compile(r"^chown\b", re.IGNORECASE),
    re.compile(r"^mount\b", re.IGNORECASE),
    re.compile(r"^umount\b", re.IGNORECASE),
    
    # Network/security
    re.compile(r"^iptables\b", re.IGNORECASE),
    re.compile(r"^firewall-cmd\b", re.IGNORECASE),
    re.compile(r"^ufw\b", re.IGNORECASE),
    
    # Process/service control  
    re.compile(r"^kill\s+-9\s+-1\b", re.IGNORECASE),  # Kill all processes
    re.compile(r"^killall\b", re.IGNORECASE),
    re.compile(r"^pkill\s+-9\b", re.IGNORECASE),
    re.compile(r"^systemctl\s+(stop|disable|mask)\b", re.IGNORECASE),
    re.compile(r"^launchctl\s+(unload|remove)\b", re.IGNORECASE),
    
    # Disk operations
    re.compile(r"^dd\s+.*of=/dev/", re.IGNORECASE),
    re.compile(r"^mkfs\b", re.IGNORECASE),
    re.compile(r"^fdisk\b", re.IGNORECASE),
    re.compile(r"^parted\b", re.IGNORECASE),
    
    # Fork bombs and resource exhaustion
    re.compile(r":\(\)\{\s*:\|:&\s*\};:", re.IGNORECASE),  # Classic fork bomb
    re.compile(r"while\s+true.*do.*done", re.IGNORECASE),
    
    # Environment/config tampering
    re.compile(r"^export\s+(PATH|LD_LIBRARY_PATH|LD_PRELOAD)=", re.IGNORECASE),
    re.compile(r">\s*/etc/", re.IGNORECASE),  # Redirecting to /etc
    re.compile(r">\s*~/.bashrc", re.IGNORECASE),
    re.compile(r">\s*~/.zshrc", re.IGNORECASE),
    
    # Database destruction
    re.compile(r"DROP\s+DATABASE\b", re.IGNORECASE),
    re.compile(r"DROP\s+TABLE\b.*CASCADE", re.IGNORECASE),
    re.compile(r"TRUNCATE\s+TABLE\b", re.IGNORECASE),
    
    # Git force operations (can destroy history)
    re.compile(r"^git\s+push\s+.*--force", re.IGNORECASE),
    re.compile(r"^git\s+push\s+-f\b", re.IGNORECASE),
    re.compile(r"^git\s+reset\s+--hard\b", re.IGNORECASE),
    re.compile(r"^git\s+clean\s+-fd", re.IGNORECASE),
]

# Safe write directories for USER role (very restricted)
USER_SAFE_WRITE_PATHS: FrozenSet[str] = frozenset({
    "~/brain/output",
    "~/brain/test-results",
    "~/brain/session-artifacts",
    "~/brain/agentic-brain/output",
    "~/brain/agentic-brain/.test-artifacts",
    "~/brain/agentic-brain/test-results",
})

# Safe write directories for SAFE_ADMIN role (broader but still protected)
SAFE_ADMIN_WRITE_PATHS: FrozenSet[str] = frozenset({
    "~/brain/data",
    "~/brain/logs", 
    "~/brain/cache",
    "~/brain/output",
    "~/brain/test-results",
    "~/brain/session-artifacts",
    "~/brain/.cache",
    "~/brain/agentic-brain",  # Can write anywhere in agentic-brain
    "~/brain/web",            # Can work on web frontend
    "~/brain/backend",        # Can work on backend
    "~/brain/skills",         # Can develop new skills
    "~/brain/scripts",        # Can create scripts
    "~/brain/tests",          # Can write tests
})

# Paths that are always readable for all roles
PUBLIC_READ_PATHS: FrozenSet[str] = frozenset({
    "~/brain/README.md",
    "~/brain/CLAUDE.md",
    "~/brain/docs",
    "~/brain/agentic-brain/README.md",
    "~/brain/agentic-brain/docs",
    "~/brain/agentic-brain/CHANGELOG.md",
})

# Tool whitelists by role - prevents system thrashing from expensive operations
GUEST_ALLOWED_TOOLS: FrozenSet[str] = frozenset({
    "help",
    "faq",
    "documentation",
    "product_search",
    "product_view",
    "cart_view",
    "cart_add",
    "cart_remove",
    "checkout",
    "customer_support",
    # Backwards-compatible aliases for older tool names.
    "view_product",
    "browse_products",
    "view_cart",
    "add_to_cart",
})

USER_ALLOWED_TOOLS: FrozenSet[str] = frozenset({
    # All GUEST tools
    *GUEST_ALLOWED_TOOLS,
    # Plus authenticated operations
    "view_orders",
    "create_order",
    "update_profile",
    "view_account",
    "track_shipment",
    "submit_review",
    "manage_wishlist",
})


@dataclass(frozen=True, slots=True)
class RolePermissions:
    """Permission set for a security role."""
    
    # YOLO execution permissions
    can_yolo: bool
    yolo_requires_confirmation: bool  # For SAFE_ADMIN - confirm dangerous ops
    yolo_restrictions: FrozenSet[Pattern[str]]  # Blocked command patterns
    
    # File system permissions
    can_write_files: bool
    can_access_filesystem: bool  # More explicit name
    allowed_write_paths: FrozenSet[str]  # Empty means no writes, {"*"} means anywhere
    can_read_all_files: bool
    
    # Code execution
    can_execute_code: bool
    can_execute_shell: bool  # Renamed for clarity
    
    # Configuration
    can_modify_config: bool
    can_access_secrets: bool
    
    # LLM access
    llm_access_level: str  # "full", "standard", "chat_only"
    
    # Rate limiting
    rate_limit_per_minute: int | float
    
    # API access - granular control based on authentication level
    can_access_apis: bool  # General API access flag
    can_access_guest_apis: bool  # Public/unauthenticated endpoints
    can_access_authenticated_apis: bool  # User-level authenticated endpoints
    can_access_admin_apis: bool  # Admin-level endpoints
    allowed_api_scopes: FrozenSet[str]  # "read", "write", "delete", "admin"
    
    # Content access (for GUEST role)
    can_read_faq: bool
    can_read_docs: bool
    can_read_manuals: bool
    
    # Admin capabilities
    can_access_admin_api: bool  # Deprecated - use can_access_admin_apis
    can_manage_users: bool
    
    # Tool access restrictions (NEW - prevent system thrashing)
    can_heavy_llm: bool = False
    can_web_search: bool = False  # Expensive operation that thrashes system
    can_use_tools: bool = False  # General tool access gate
    allowed_tools: FrozenSet[str] | None = None  # None = all tools, frozenset = whitelist
    
    # Compatibility / metadata helpers
    allowed_apis: FrozenSet[str] = field(default_factory=frozenset)
    can_access_database: bool = False
    can_configure_system: bool = False
    
    @property
    def can_execute_arbitrary_shell(self) -> bool:
        """Backward-compatible alias used by older callers/tests."""
        return self.can_execute_shell
    
    @property
    def api_only_mode(self) -> bool:
        """Whether the role is restricted to API/content access only."""
        return not self.can_access_filesystem
    
    def is_command_allowed(self, command: str) -> tuple[bool, str | None]:
        """
        Check if a command is allowed under this role's permissions.
        
        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        if not self.can_yolo:
            return False, "YOLO execution not permitted for this role"
        
        if not self.can_execute_shell:
            return False, "Shell command execution not permitted for this role"
        
        # Check against blocked patterns
        command_stripped = command.strip()
        for pattern in self.yolo_restrictions:
            if pattern.search(command_stripped):
                return False, f"Command blocked by security policy: matches dangerous pattern"
        
        return True, None
    
    def is_path_writable(self, path: str | Path) -> tuple[bool, str | None]:
        """
        Check if a path is writable under this role's permissions.
        
        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        if not self.can_write_files:
            return False, "File writing not permitted for this role"
        
        if "*" in self.allowed_write_paths:
            return True, None
        
        # Canonicalize path to prevent symlink attacks
        try:
            path_obj = Path(path).expanduser().resolve()
        except (ValueError, OSError) as e:
            return False, f"Invalid path: {e}"
        
        # Check against allowed paths
        for allowed in self.allowed_write_paths:
            allowed_path = Path(allowed).expanduser().resolve()
            try:
                path_obj.relative_to(allowed_path)
                return True, None
            except ValueError:
                continue
        
        return False, f"Path {path} not in allowed write locations"
    
    def is_path_readable(self, path: str | Path) -> tuple[bool, str | None]:
        """
        Check if a path is readable under this role's permissions.
        
        Returns:
            Tuple of (allowed, reason_if_blocked)
        """
        if self.can_read_all_files:
            return True, None
        
        # Canonicalize path
        try:
            path_obj = Path(path).expanduser().resolve()
        except (ValueError, OSError) as e:
            return False, f"Invalid path: {e}"
        
        # Check public paths
        for public in PUBLIC_READ_PATHS:
            public_path = Path(public).expanduser().resolve()
            try:
                path_obj.relative_to(public_path)
                return True, None
            except ValueError:
                if path_obj == public_path:
                    return True, None
        
        return False, f"Path {path} not accessible for this role"


# Role permission definitions
ROLE_PERMISSIONS: dict[SecurityRole, RolePermissions] = {
    SecurityRole.FULL_ADMIN: RolePermissions(
        # Tier 1: FULL_ADMIN (Joseph only)
        # Complete unrestricted access - can do EVERYTHING
        can_yolo=True,
        yolo_requires_confirmation=False,  # NO confirmations for Joseph
        yolo_restrictions=frozenset(),  # No restrictions whatsoever
        
        # Full file system access
        can_write_files=True,
        can_access_filesystem=True,
        allowed_write_paths=frozenset({"*"}),
        can_read_all_files=True,
        
        # Full code execution
        can_execute_code=True,
        can_execute_shell=True,
        
        # Full configuration access
        can_modify_config=True,
        can_access_secrets=True,
        
        # Full LLM access
        llm_access_level="full",
        can_heavy_llm=True,
        
        # No rate limiting
        rate_limit_per_minute=float('inf'),
        
        # Full API access at all levels
        can_access_apis=True,
        can_access_guest_apis=True,
        can_access_authenticated_apis=True,
        can_access_admin_apis=True,
        allowed_api_scopes=frozenset({"read", "write", "delete", "admin"}),
        
        # Full content access
        can_read_faq=True,
        can_read_docs=True,
        can_read_manuals=True,
        
        # Full admin capabilities
        can_access_admin_api=True,
        can_manage_users=True,
        allowed_apis=frozenset({"*"}),
        can_access_database=True,
        can_configure_system=True,
        
        # Full tool access - no restrictions
        can_web_search=True,
        can_use_tools=True,
        allowed_tools=None,  # None = all tools allowed
    ),
    
    SecurityRole.SAFE_ADMIN: RolePermissions(
        # Tier 2: SAFE_ADMIN (Developers/Trusted admins)
        # Almost full access WITH guardrails
        can_yolo=True,
        yolo_requires_confirmation=True,  # Confirm dangerous operations
        yolo_restrictions=frozenset(DANGEROUS_COMMAND_PATTERNS),
        
        # Broad file system access to development areas
        can_write_files=True,
        can_access_filesystem=True,
        allowed_write_paths=SAFE_ADMIN_WRITE_PATHS,
        can_read_all_files=True,
        
        # Full code execution with restrictions
        can_execute_code=True,
        can_execute_shell=True,
        
        # Can modify project config but not system secrets
        can_modify_config=True,
        can_access_secrets=False,  # No secrets access
        
        # Full LLM access for development
        llm_access_level="full",
        can_heavy_llm=True,
        
        # High rate limit for active development
        rate_limit_per_minute=1000,
        
        # Full API access at guest and authenticated levels, no admin
        can_access_apis=True,
        can_access_guest_apis=True,
        can_access_authenticated_apis=True,
        can_access_admin_apis=False,
        allowed_api_scopes=frozenset({"read", "write", "delete"}),
        
        # Full content access
        can_read_faq=True,
        can_read_docs=True,
        can_read_manuals=True,
        
        # Limited admin capabilities
        can_access_admin_api=False,
        can_manage_users=False,
        allowed_apis=frozenset({"*"}),
        can_access_database=True,
        can_configure_system=True,
        
        # Full tool access for development
        can_web_search=True,
        can_use_tools=True,
        allowed_tools=None,  # All tools allowed
    ),
    
    SecurityRole.USER: RolePermissions(
        # Tier 3: USER/CUSTOMER (API-only access)
        # NO direct machine access - ONLY API access
        can_yolo=False,
        yolo_requires_confirmation=False,
        yolo_restrictions=frozenset(DANGEROUS_COMMAND_PATTERNS),
        
        # NO file system access
        can_write_files=False,
        can_access_filesystem=False,
        allowed_write_paths=frozenset(),
        can_read_all_files=False,
        
        # NO code execution
        can_execute_code=False,
        can_execute_shell=False,
        
        # NO configuration access
        can_modify_config=False,
        can_access_secrets=False,
        
        # Chat-level LLM access
        llm_access_level="chat_only",
        can_heavy_llm=False,
        
        # Moderate rate limit
        rate_limit_per_minute=60,
        
        # Authenticated API access - can access user-level endpoints
        # Permissions controlled by external API's role system
        can_access_apis=True,
        can_access_guest_apis=True,  # Can also access public endpoints
        can_access_authenticated_apis=True,  # User-level authenticated endpoints
        can_access_admin_apis=False,  # No admin endpoints
        allowed_api_scopes=frozenset({"read", "write"}),
        
        # Full content access
        can_read_faq=True,
        can_read_docs=True,
        can_read_manuals=True,
        
        # No admin capabilities
        can_access_admin_api=False,
        can_manage_users=False,
        allowed_apis=frozenset({"wordpress", "woocommerce"}),
        can_access_database=False,
        can_configure_system=False,
        
        # Limited tool access - NO web search (blocks expensive ops)
        can_web_search=False,
        can_use_tools=True,
        allowed_tools=USER_ALLOWED_TOOLS,
    ),
    
    SecurityRole.GUEST: RolePermissions(
        # Tier 4: GUEST (Context-aware public access)
        # Mirrors platform's guest/unauthenticated capabilities
        # NO machine access, NO authenticated API access
        # BLOCKED from expensive operations to prevent system thrashing
        can_yolo=False,
        yolo_requires_confirmation=False,
        yolo_restrictions=frozenset(DANGEROUS_COMMAND_PATTERNS),
        
        # NO file system access
        can_write_files=False,
        can_access_filesystem=False,
        allowed_write_paths=frozenset(),
        can_read_all_files=False,
        
        # NO code execution
        can_execute_code=False,
        can_execute_shell=False,
        
        # NO configuration access
        can_modify_config=False,
        can_access_secrets=False,
        
        # Chat only
        llm_access_level="chat_only",
        can_heavy_llm=False,
        
        # Strict rate limit
        rate_limit_per_minute=10,
        
        # Context-aware guest API access
        # GUEST can access public/unauthenticated endpoints (e.g., WooCommerce Store API)
        # - Browse products, view product details
        # - Add to cart (session-based, no account needed)
        # - Checkout as guest
        # - View shipping options
        # NO access to authenticated or admin endpoints
        can_access_apis=True,  # Changed from False - guests CAN access APIs
        can_access_guest_apis=True,  # YES - public/guest endpoints
        can_access_authenticated_apis=False,  # NO - no user-level endpoints
        can_access_admin_apis=False,  # NO - no admin endpoints
        allowed_api_scopes=frozenset({"read"}),  # Read-only for safety
        
        # Read-only content access
        can_read_faq=True,
        can_read_docs=True,
        can_read_manuals=True,
        
        # No admin capabilities
        can_access_admin_api=False,
        can_manage_users=False,
        allowed_apis=frozenset({"woocommerce_store", "wordpress_public"}),
        can_access_database=False,
        can_configure_system=False,
        
        # STRICT tool restrictions - BLOCKS system thrashing
        can_web_search=False,  # BLOCKED - expensive, thrashes system, costs money
        can_use_tools=True,  # Can use tools BUT only whitelisted ones
        allowed_tools=GUEST_ALLOWED_TOOLS,  # Very limited whitelist
    ),
}


def get_permissions(role: SecurityRole) -> RolePermissions:
    """Get the permissions for a security role."""
    return ROLE_PERMISSIONS[role]


def is_dangerous_command(command: str) -> tuple[bool, str | None]:
    """
    Check if a command matches any dangerous pattern.
    
    Returns:
        Tuple of (is_dangerous, pattern_description_if_matched)
    """
    command_stripped = command.strip()
    for pattern in DANGEROUS_COMMAND_PATTERNS:
        if pattern.search(command_stripped):
            return True, pattern.pattern
    return False, None
