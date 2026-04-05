# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import pytest

from agentic_brain.security import (
    WOOCOMMERCE_PROFILE,
    AccessLevel,
    PlatformSecurityProfile,
    SecurityGuard,
    SecurityRole,
    TaskAgent,
)
from agentic_brain.security.guards import SecurityViolation


class TestPlatformSecurityProfiles:
    def test_profile_classifies_endpoints_by_access_level(self) -> None:
        assert (
            WOOCOMMERCE_PROFILE.access_level_for("GET /products") is AccessLevel.PUBLIC
        )
        assert (
            WOOCOMMERCE_PROFILE.access_level_for("GET /orders")
            is AccessLevel.AUTHENTICATED
        )
        assert (
            WOOCOMMERCE_PROFILE.access_level_for("DELETE /products")
            is AccessLevel.PRIVILEGED
        )
        assert WOOCOMMERCE_PROFILE.access_level_for("POST /unknown") is None

    def test_profile_rate_limits_follow_generalized_guest_user_admin_pattern(
        self,
    ) -> None:
        assert WOOCOMMERCE_PROFILE.rate_limit_for(AccessLevel.PUBLIC) == 100
        assert WOOCOMMERCE_PROFILE.rate_limit_for(AccessLevel.AUTHENTICATED) == 1000
        assert WOOCOMMERCE_PROFILE.rate_limit_for(AccessLevel.PRIVILEGED) == 10000


class TestSecurityGuardPlatformAccess:
    def test_guest_can_only_access_public_platform_endpoints(self) -> None:
        guard = SecurityGuard(SecurityRole.GUEST, platform_profile=WOOCOMMERCE_PROFILE)

        assert guard.check_platform_endpoint("GET /products")[0] is True
        assert guard.check_platform_endpoint("POST /cart/add")[0] is True
        assert guard.check_platform_endpoint("GET /orders")[0] is False
        assert guard.check_platform_endpoint("DELETE /products")[0] is False
        assert guard.check_platform_operation("help")[0] is True
        assert guard.check_platform_operation("web_search")[0] is False

    def test_user_can_access_own_data_endpoints_but_not_admin_endpoints(self) -> None:
        guard = SecurityGuard(SecurityRole.USER, platform_profile=WOOCOMMERCE_PROFILE)

        assert guard.check_platform_endpoint("GET /products")[0] is True
        assert guard.check_platform_endpoint("GET /orders")[0] is True
        assert guard.check_platform_endpoint("PUT /account")[0] is True
        assert guard.check_platform_endpoint("DELETE /products")[0] is False
        assert guard.check_platform_operation("heavy_llm")[0] is False

    def test_full_admin_can_access_platform_admin_endpoints_and_operations(
        self,
    ) -> None:
        guard = SecurityGuard(
            SecurityRole.FULL_ADMIN, platform_profile=WOOCOMMERCE_PROFILE
        )

        assert guard.check_platform_endpoint("DELETE /products")[0] is True
        assert guard.check_platform_operation("web_search")[0] is True
        assert guard.check_platform_operation("heavy_llm")[0] is True
        assert guard.get_platform_rate_limit() == 10000

    def test_guest_write_flag_can_disable_public_writes(self) -> None:
        profile = PlatformSecurityProfile(
            name="read-only-store",
            guest_endpoints=frozenset({"GET /catalog", "POST /ticket"}),
            user_endpoints=frozenset({"GET /orders"}),
            admin_endpoints=frozenset({"all"}),
            allows_guest_writes=False,
        )
        guard = SecurityGuard(SecurityRole.GUEST, platform_profile=profile)

        assert guard.check_platform_endpoint("GET /catalog")[0] is True
        allowed, reason = guard.check_platform_endpoint("POST /ticket")
        assert allowed is False
        assert "Guest write access disabled" in (reason or "")


class TestTaskAgentPlatformChecks:
    def test_task_agent_uses_platform_profile_for_endpoint_checks(self) -> None:
        agent = TaskAgent(security_role=SecurityRole.USER)
        agent.guard = SecurityGuard(
            SecurityRole.USER, platform_profile=WOOCOMMERCE_PROFILE
        )

        result = agent.execute("call_api", api="woocommerce", endpoint="GET /orders")
        assert result["endpoint"] == "GET /orders"

        with pytest.raises(SecurityViolation):
            agent.execute("call_api", api="woocommerce", endpoint="DELETE /products")
