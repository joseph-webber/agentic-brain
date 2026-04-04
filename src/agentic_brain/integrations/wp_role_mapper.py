# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Maps WordPress and WooCommerce roles to BrainChat access profiles.

The mapping is intentionally API-first:

- customer-facing and staff chatbots do not receive direct machine access
- all work is delegated to WordPress REST API or WooCommerce REST API
- WordPress remains the final permission enforcement point
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from agentic_brain.security.roles import SecurityRole


class WordPressChatbotMode(str, Enum):
    """High-level chatbot modes derived from WordPress roles."""

    GUEST = "guest"
    USER = "user"
    POWER_USER = "power_user"
    ADMIN = "admin"


class WordPressRole(str, Enum):
    """Supported WordPress and WooCommerce roles."""

    SUBSCRIBER = "subscriber"
    CUSTOMER = "customer"
    CONTRIBUTOR = "contributor"
    AUTHOR = "author"
    EDITOR = "editor"
    SHOP_MANAGER = "shop_manager"
    ADMINISTRATOR = "administrator"


CHATBOT_MODE_LABELS: dict[WordPressChatbotMode, str] = {
    WordPressChatbotMode.GUEST: "GUEST",
    WordPressChatbotMode.USER: "USER",
    WordPressChatbotMode.POWER_USER: "POWER USER",
    WordPressChatbotMode.ADMIN: "ADMIN",
}


WP_TO_BRAINCHAT_ROLE: dict[WordPressRole, WordPressChatbotMode] = {
    WordPressRole.SUBSCRIBER: WordPressChatbotMode.GUEST,
    WordPressRole.CUSTOMER: WordPressChatbotMode.USER,
    WordPressRole.CONTRIBUTOR: WordPressChatbotMode.USER,
    WordPressRole.AUTHOR: WordPressChatbotMode.USER,
    WordPressRole.EDITOR: WordPressChatbotMode.POWER_USER,
    WordPressRole.SHOP_MANAGER: WordPressChatbotMode.POWER_USER,
    WordPressRole.ADMINISTRATOR: WordPressChatbotMode.ADMIN,
}


_PUBLIC_CAPABILITIES = frozenset(
    {
        "ask_site_questions",
        "get_navigation_help",
        "read_public_content",
        "view_products",
    }
)
_CUSTOMER_CAPABILITIES = _PUBLIC_CAPABILITIES | frozenset(
    {
        "add_to_cart",
        "checkout",
        "update_own_profile",
        "view_own_downloads",
        "view_own_orders",
        "view_own_tracking",
    }
)
_CONTRIBUTOR_CAPABILITIES = _PUBLIC_CAPABILITIES | frozenset(
    {
        "create_draft_posts",
        "edit_own_drafts",
        "read_private_dashboard_content",
    }
)
_AUTHOR_CAPABILITIES = _CONTRIBUTOR_CAPABILITIES | frozenset(
    {
        "delete_own_posts",
        "publish_own_posts",
        "upload_media",
    }
)
_EDITOR_CAPABILITIES = _AUTHOR_CAPABILITIES | frozenset(
    {
        "edit_all_posts",
        "manage_categories",
        "manage_pages",
        "moderate_comments",
        "publish_others_posts",
    }
)
_SHOP_MANAGER_CAPABILITIES = _CUSTOMER_CAPABILITIES | frozenset(
    {
        "manage_coupons",
        "manage_inventory",
        "manage_products",
        "process_refunds",
        "update_orders",
        "view_all_orders",
        "view_reports",
    }
)


WP_ROLE_CAPABILITIES: dict[WordPressRole, frozenset[str]] = {
    WordPressRole.SUBSCRIBER: _PUBLIC_CAPABILITIES,
    WordPressRole.CUSTOMER: _CUSTOMER_CAPABILITIES,
    WordPressRole.CONTRIBUTOR: _CONTRIBUTOR_CAPABILITIES,
    WordPressRole.AUTHOR: _AUTHOR_CAPABILITIES,
    WordPressRole.EDITOR: _EDITOR_CAPABILITIES,
    WordPressRole.SHOP_MANAGER: _SHOP_MANAGER_CAPABILITIES,
    WordPressRole.ADMINISTRATOR: _EDITOR_CAPABILITIES
    | _SHOP_MANAGER_CAPABILITIES
    | frozenset(
        {
            "enable_yolo_mode",
            "manage_plugins",
            "manage_site_settings",
            "manage_themes",
            "manage_users",
        }
    ),
}


WP_ROLE_ENDPOINT_FAMILIES: dict[WordPressRole, frozenset[str]] = {
    WordPressRole.SUBSCRIBER: frozenset(
        {
            "GET /wp-json/wp/v2/categories",
            "GET /wp-json/wp/v2/pages",
            "GET /wp-json/wp/v2/posts",
            "GET /wp-json/wp/v2/tags",
            "GET /wp-json/wc/store/v1/products",
        }
    ),
    WordPressRole.CUSTOMER: frozenset(
        {
            "GET /wp-json/wc/v3/customers/<self>",
            "GET /wp-json/wc/v3/orders?customer=<self>",
            "GET /wp-json/wp/v2/users/me",
            "GET /wp-json/wc/v3/products",
            "POST /wp-json/wp/v2/users/me",
        }
    ),
    WordPressRole.CONTRIBUTOR: frozenset(
        {
            "GET /wp-json/wp/v2/posts?author=<self>",
            "GET /wp-json/wp/v2/users/me",
            "POST /wp-json/wp/v2/posts",
            "POST /wp-json/wp/v2/posts/<id>",
        }
    ),
    WordPressRole.AUTHOR: frozenset(
        {
            "DELETE /wp-json/wp/v2/posts/<id>?force=false",
            "GET /wp-json/wp/v2/media",
            "POST /wp-json/wp/v2/media",
            "POST /wp-json/wp/v2/posts",
            "POST /wp-json/wp/v2/posts/<id>",
        }
    ),
    WordPressRole.EDITOR: frozenset(
        {
            "GET /wp-json/wp/v2/comments",
            "GET /wp-json/wp/v2/posts",
            "POST /wp-json/wp/v2/categories",
            "POST /wp-json/wp/v2/pages/<id>",
            "POST /wp-json/wp/v2/posts/<id>",
        }
    ),
    WordPressRole.SHOP_MANAGER: frozenset(
        {
            "GET /wp-json/wc/v3/orders",
            "GET /wp-json/wc/v3/reports/sales",
            "GET /wp-json/wc/v3/reports/top_sellers",
            "POST /wp-json/wc/v3/orders/<id>",
            "POST /wp-json/wc/v3/products/<id>",
            "POST /wp-json/wc/v3/refunds",
        }
    ),
    WordPressRole.ADMINISTRATOR: frozenset(
        {
            "DELETE /wp-json/wp/v2/plugins/<plugin>",
            "GET /wp-json/wp/v2/users",
            "POST /wp-json/wp/v2/plugins/<plugin>",
            "POST /wp-json/wp/v2/settings",
            "POST /wp-json/wp/v2/themes/<theme>",
        }
    ),
}


_ROLE_PRECEDENCE: dict[WordPressRole, int] = {
    WordPressRole.SUBSCRIBER: 0,
    WordPressRole.CUSTOMER: 1,
    WordPressRole.CONTRIBUTOR: 2,
    WordPressRole.AUTHOR: 3,
    WordPressRole.EDITOR: 4,
    WordPressRole.SHOP_MANAGER: 5,
    WordPressRole.ADMINISTRATOR: 6,
}


@dataclass(frozen=True, slots=True)
class WordPressRoleProfile:
    """Combined BrainChat profile for a WordPress role."""

    wordpress_role: WordPressRole
    chatbot_mode: WordPressChatbotMode
    security_role: SecurityRole
    capabilities: frozenset[str]
    allowed_endpoint_families: frozenset[str]
    api_only: bool = True
    direct_machine_access: bool = False


def normalize_wordpress_role(role: WordPressRole | str) -> WordPressRole:
    """Normalize a raw WordPress role string into :class:`WordPressRole`."""

    if isinstance(role, WordPressRole):
        return role

    normalized = role.strip().lower().replace("-", "_").replace(" ", "_")
    return WordPressRole(normalized)


def resolve_primary_wordpress_role(
    roles: Iterable[WordPressRole | str],
) -> WordPressRole:
    """Resolve the most privileged WordPress role from a role list."""

    normalized_roles = {normalize_wordpress_role(role) for role in roles}
    if not normalized_roles:
        raise ValueError("At least one WordPress role is required")

    return max(normalized_roles, key=_ROLE_PRECEDENCE.__getitem__)


def get_chatbot_mode(
    role: WordPressRole | str,
    *,
    allow_admin_mode: bool = True,
) -> WordPressChatbotMode:
    """Return the chatbot mode for a WordPress role."""

    normalized_role = normalize_wordpress_role(role)
    if normalized_role == WordPressRole.ADMINISTRATOR and not allow_admin_mode:
        return WordPressChatbotMode.POWER_USER
    return WP_TO_BRAINCHAT_ROLE[normalized_role]


def get_security_role(
    role: WordPressRole | str,
    *,
    allow_admin_mode: bool = True,
) -> SecurityRole:
    """Return the Brain runtime security role used for this WordPress role."""

    normalized_role = normalize_wordpress_role(role)
    if normalized_role == WordPressRole.SUBSCRIBER:
        return SecurityRole.GUEST
    if normalized_role == WordPressRole.ADMINISTRATOR and allow_admin_mode:
        return SecurityRole.SAFE_ADMIN
    return SecurityRole.USER


def get_capabilities(role: WordPressRole | str) -> frozenset[str]:
    """Return the effective capabilities for a WordPress role."""

    return WP_ROLE_CAPABILITIES[normalize_wordpress_role(role)]


def get_allowed_endpoint_families(role: WordPressRole | str) -> frozenset[str]:
    """Return representative API endpoint families for a WordPress role."""

    return WP_ROLE_ENDPOINT_FAMILIES[normalize_wordpress_role(role)]


def can_access_capability(role: WordPressRole | str, capability: str) -> bool:
    """Check whether the WordPress role allows a chatbot capability."""

    return capability in get_capabilities(role)


def get_wordpress_role_profile(
    role: WordPressRole | str,
    *,
    allow_admin_mode: bool = True,
) -> WordPressRoleProfile:
    """Build a full BrainChat access profile for a WordPress role."""

    normalized_role = normalize_wordpress_role(role)
    return WordPressRoleProfile(
        wordpress_role=normalized_role,
        chatbot_mode=get_chatbot_mode(
            normalized_role,
            allow_admin_mode=allow_admin_mode,
        ),
        security_role=get_security_role(
            normalized_role,
            allow_admin_mode=allow_admin_mode,
        ),
        capabilities=get_capabilities(normalized_role),
        allowed_endpoint_families=get_allowed_endpoint_families(normalized_role),
    )


__all__ = [
    "CHATBOT_MODE_LABELS",
    "WP_ROLE_CAPABILITIES",
    "WP_ROLE_ENDPOINT_FAMILIES",
    "WP_TO_BRAINCHAT_ROLE",
    "WordPressChatbotMode",
    "WordPressRole",
    "WordPressRoleProfile",
    "can_access_capability",
    "get_allowed_endpoint_families",
    "get_capabilities",
    "get_chatbot_mode",
    "get_security_role",
    "get_wordpress_role_profile",
    "normalize_wordpress_role",
    "resolve_primary_wordpress_role",
]
