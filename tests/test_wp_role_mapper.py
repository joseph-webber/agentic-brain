# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import pytest

from agentic_brain.integrations.wp_role_mapper import (
    CHATBOT_MODE_LABELS,
    WP_ROLE_CAPABILITIES,
    WordPressChatbotMode,
    WordPressRole,
    can_access_capability,
    get_allowed_endpoint_families,
    get_capabilities,
    get_chatbot_mode,
    get_security_role,
    get_wordpress_role_profile,
    normalize_wordpress_role,
    resolve_primary_wordpress_role,
)
from agentic_brain.security.roles import SecurityRole


def test_normalize_wordpress_role_accepts_common_formats():
    assert normalize_wordpress_role("shop-manager") == WordPressRole.SHOP_MANAGER
    assert normalize_wordpress_role(" Shop Manager ") == WordPressRole.SHOP_MANAGER
    assert normalize_wordpress_role(WordPressRole.CUSTOMER) == WordPressRole.CUSTOMER


def test_resolve_primary_wordpress_role_prefers_highest_privilege():
    role = resolve_primary_wordpress_role(["subscriber", "customer", "shop_manager"])
    assert role == WordPressRole.SHOP_MANAGER


def test_resolve_primary_wordpress_role_requires_at_least_one_role():
    with pytest.raises(ValueError):
        resolve_primary_wordpress_role([])


@pytest.mark.parametrize(
    ("role", "mode", "security_role"),
    [
        (WordPressRole.SUBSCRIBER, WordPressChatbotMode.GUEST, SecurityRole.GUEST),
        (WordPressRole.CUSTOMER, WordPressChatbotMode.USER, SecurityRole.USER),
        (WordPressRole.CONTRIBUTOR, WordPressChatbotMode.USER, SecurityRole.USER),
        (WordPressRole.AUTHOR, WordPressChatbotMode.USER, SecurityRole.USER),
        (WordPressRole.EDITOR, WordPressChatbotMode.POWER_USER, SecurityRole.USER),
        (WordPressRole.SHOP_MANAGER, WordPressChatbotMode.POWER_USER, SecurityRole.USER),
        (
            WordPressRole.ADMINISTRATOR,
            WordPressChatbotMode.ADMIN,
            SecurityRole.SAFE_ADMIN,
        ),
    ],
)
def test_wordpress_role_mapping(role, mode, security_role):
    assert get_chatbot_mode(role) == mode
    assert get_security_role(role) == security_role


def test_administrator_can_be_downgraded_to_power_user_mode():
    assert (
        get_chatbot_mode("administrator", allow_admin_mode=False)
        == WordPressChatbotMode.POWER_USER
    )
    assert get_security_role("administrator", allow_admin_mode=False) == SecurityRole.USER


def test_customer_capabilities_are_self_service_only():
    capabilities = get_capabilities("customer")
    assert "view_own_orders" in capabilities
    assert "update_own_profile" in capabilities
    assert "view_all_orders" not in capabilities
    assert "manage_products" not in capabilities


def test_shop_manager_has_woocommerce_management_capabilities():
    capabilities = get_capabilities("shop_manager")
    assert "view_all_orders" in capabilities
    assert "manage_products" in capabilities
    assert "process_refunds" in capabilities
    assert "manage_users" not in capabilities


def test_administrator_profile_stays_api_only():
    profile = get_wordpress_role_profile("administrator")
    assert profile.chatbot_mode == WordPressChatbotMode.ADMIN
    assert profile.security_role == SecurityRole.SAFE_ADMIN
    assert profile.api_only is True
    assert profile.direct_machine_access is False
    assert "manage_plugins" in profile.capabilities


def test_capability_check_uses_effective_role_capabilities():
    assert can_access_capability("editor", "manage_categories") is True
    assert can_access_capability("editor", "manage_plugins") is False


def test_endpoint_families_match_role_scope():
    customer_endpoints = get_allowed_endpoint_families("customer")
    shop_manager_endpoints = get_allowed_endpoint_families("shop_manager")

    assert "GET /wp-json/wc/v3/orders?customer=<self>" in customer_endpoints
    assert "GET /wp-json/wc/v3/reports/sales" in shop_manager_endpoints
    assert "POST /wp-json/wp/v2/settings" not in shop_manager_endpoints


def test_labels_and_capability_registry_cover_all_roles():
    assert CHATBOT_MODE_LABELS[WordPressChatbotMode.POWER_USER] == "POWER USER"
    assert set(WP_ROLE_CAPABILITIES) == set(WordPressRole)
