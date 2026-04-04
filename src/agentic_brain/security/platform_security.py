# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Generalized platform security model.

This pattern from WordPress/WooCommerce applies to ALL integrations:
- Stripe: GUEST can view products, USER can manage own payments, ADMIN all
- Shopify: Same pattern - guest shopping, user orders, admin management
- Custom APIs: Follow the same GUEST/USER/ADMIN split

The chatbot's role mirrors what the platform allows for that role.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import FrozenSet


class AccessLevel(str, Enum):
    """Platform access levels from public through privileged."""

    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    PRIVILEGED = "privileged"


@dataclass(frozen=True, slots=True)
class PlatformSecurityProfile:
    """Security profile for a platform integration."""

    name: str
    guest_endpoints: FrozenSet[str]
    user_endpoints: FrozenSet[str]
    admin_endpoints: FrozenSet[str]

    guest_rate_limit: int = 100
    user_rate_limit: int = 1000
    admin_rate_limit: int = 10000

    allows_guest_search: bool = False
    allows_guest_writes: bool = True

    def access_level_for(self, endpoint: str) -> AccessLevel | None:
        """Return the minimum access level required for an endpoint."""
        normalized = normalize_endpoint(endpoint)
        if normalized in self.guest_endpoints:
            return AccessLevel.PUBLIC
        if normalized in self.user_endpoints:
            return AccessLevel.AUTHENTICATED
        if normalized in self.admin_endpoints or "all" in self.admin_endpoints:
            return AccessLevel.PRIVILEGED
        return None

    def rate_limit_for(self, access_level: AccessLevel) -> int:
        """Return the requests-per-hour limit for an access level."""
        if access_level is AccessLevel.PUBLIC:
            return self.guest_rate_limit
        if access_level is AccessLevel.AUTHENTICATED:
            return self.user_rate_limit
        return self.admin_rate_limit

    @property
    def all_endpoints(self) -> FrozenSet[str]:
        """Return all explicitly configured endpoints for the profile."""
        return self.guest_endpoints | self.user_endpoints | self.admin_endpoints


def normalize_endpoint(endpoint: str) -> str:
    """Normalize endpoint strings for consistent matching."""
    return " ".join(endpoint.strip().split())


WOOCOMMERCE_PROFILE = PlatformSecurityProfile(
    name="woocommerce",
    guest_endpoints=frozenset(
        {
            "GET /products",
            "GET /cart",
            "POST /cart/add",
            "POST /checkout",
        }
    ),
    user_endpoints=frozenset(
        {
            "GET /orders",
            "GET /account",
            "PUT /account",
        }
    ),
    admin_endpoints=frozenset(
        {
            "POST /products",
            "PUT /products",
            "DELETE /products",
            "GET /reports",
            "GET /customers",
        }
    ),
    allows_guest_search=False,
)

STANDALONE_PROFILE = PlatformSecurityProfile(
    name="standalone",
    guest_endpoints=frozenset(
        {
            "help",
            "faq",
            "documentation",
            "customer_support",
        }
    ),
    user_endpoints=frozenset(
        {
            "chat",
            "history",
            "preferences",
        }
    ),
    admin_endpoints=frozenset({"all"}),
    allows_guest_search=False,
)
