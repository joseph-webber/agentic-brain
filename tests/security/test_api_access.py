# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Tests for API-based access control."""

import pytest
from unittest.mock import AsyncMock, patch

from agentic_brain.security.api_access import (
    APIAccessController,
    APIEndpoint,
    APIScope,
    AuthType,
    RateLimiter,
    SecurityViolation,
    create_api_controller,
)
from agentic_brain.security.roles import SecurityRole


class TestRateLimiter:
    """Test rate limiting."""

    def test_allows_under_limit(self):
        """Should allow requests under the limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)

        for _ in range(5):
            assert limiter.is_allowed() is True

        # 6th request should be denied
        assert limiter.is_allowed() is False

    def test_time_until_available(self):
        """Should calculate wait time correctly."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)

        assert limiter.is_allowed() is True
        assert limiter.is_allowed() is False

        wait = limiter.time_until_available()
        assert 50 < wait <= 60  # Should be close to window_seconds


class TestAPIEndpoint:
    """Test API endpoint configuration."""

    def test_valid_endpoint(self):
        """Should create valid endpoint."""
        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ, APIScope.WRITE],
            rate_limit=60,
        )

        assert endpoint.name == "wordpress"
        assert APIScope.READ in endpoint.allowed_scopes

    def test_requires_ssl(self):
        """Should reject HTTP when SSL required."""
        with pytest.raises(ValueError, match="requires SSL"):
            APIEndpoint(
                name="insecure",
                base_url="http://example.com/api",  # HTTP not HTTPS
                auth_type=AuthType.BEARER,
                allowed_scopes=[APIScope.READ],
                rate_limit=60,
                requires_ssl=True,
            )

    def test_allows_http_when_not_required(self):
        """Should allow HTTP when SSL not required."""
        endpoint = APIEndpoint(
            name="local",
            base_url="http://localhost:8000/api",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
            requires_ssl=False,
        )

        assert endpoint.base_url == "http://localhost:8000/api"


class TestAPIAccessController:
    """Test API access controller."""

    def test_create_controller(self):
        """Should create controller for each role."""
        for role in SecurityRole:
            controller = create_api_controller(role)
            assert controller.role == role

    def test_register_api(self):
        """Should register API endpoint."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
        )

        credentials = {"token": "test_token"}

        controller.register_api(endpoint, credentials)

        assert "wordpress" in controller.allowed_apis
        assert "wordpress" in controller.api_keys
        assert "wordpress" in controller.rate_limiters

    def test_guest_cannot_register_private_api(self):
        """Guest can only access public APIs."""
        controller = APIAccessController(SecurityRole.GUEST)

        endpoint = APIEndpoint(
            name="private",
            base_url="https://example.com/api",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],  # No PUBLIC scope
            rate_limit=60,
        )

        with pytest.raises(SecurityViolation, match="GUEST.*public"):
            controller.register_api(endpoint, {"token": "test"})

    def test_can_access_checks_scope(self):
        """Should check scope permissions."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],  # Only READ
            rate_limit=60,
        )

        controller.register_api(endpoint, {"token": "test"})

        assert controller.can_access("wordpress", APIScope.READ) is True
        assert controller.can_access("wordpress", APIScope.WRITE) is False
        assert controller.can_access("wordpress", APIScope.DELETE) is False

    def test_guest_only_public_scope(self):
        """Guest can only use PUBLIC scope."""
        controller = APIAccessController(SecurityRole.GUEST)

        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.PUBLIC, APIScope.READ],
            rate_limit=60,
        )

        controller.register_api(endpoint, {"token": "test"})

        assert controller.can_access("wordpress", APIScope.PUBLIC) is True
        assert controller.can_access("wordpress", APIScope.READ) is False

    @pytest.mark.asyncio
    async def test_call_api_enforces_permissions(self):
        """Should block API calls without permissions."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
        )

        controller.register_api(endpoint, {"token": "test"})

        # Try to DELETE without DELETE scope
        with pytest.raises(SecurityViolation, match="Access denied"):
            await controller.call_api("wordpress", "DELETE", "/posts/123")

    @pytest.mark.asyncio
    async def test_call_api_enforces_rate_limit(self):
        """Should enforce rate limits."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=2,  # Only 2 requests per minute
        )

        controller.register_api(endpoint, {"token": "test"})

        # Mock HTTP client
        with patch.object(controller, "client", new=AsyncMock()) as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": "test"}
            mock_client.request.return_value = mock_response

            # First 2 requests should succeed
            await controller.call_api("wordpress", "GET", "/posts")
            await controller.call_api("wordpress", "GET", "/posts")

            # 3rd should be rate limited
            with pytest.raises(SecurityViolation, match="Rate limit exceeded"):
                await controller.call_api("wordpress", "GET", "/posts")

    @pytest.mark.asyncio
    async def test_build_auth_headers_bearer(self):
        """Should build Bearer auth headers."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="test",
            base_url="https://api.example.com",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
        )

        credentials = {"token": "secret_token"}
        headers = controller._build_auth_headers(endpoint, credentials)

        assert headers["Authorization"] == "Bearer secret_token"

    @pytest.mark.asyncio
    async def test_build_auth_headers_basic(self):
        """Should build Basic auth headers."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="test",
            base_url="https://api.example.com",
            auth_type=AuthType.BASIC,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
        )

        credentials = {"username": "user", "password": "pass"}
        headers = controller._build_auth_headers(endpoint, credentials)

        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_get_access_log(self):
        """Should track API access."""
        controller = APIAccessController(SecurityRole.USER)

        # Manually add log entries
        controller.access_log.append(
            {
                "timestamp": 1234567890,
                "role": "user",
                "api": "wordpress",
                "method": "GET",
                "path": "/posts",
                "scope": "read",
                "status": 200,
                "success": True,
            }
        )

        log = controller.get_access_log()
        assert len(log) == 1
        assert log[0]["api"] == "wordpress"

    def test_get_access_log_filtered(self):
        """Should filter access log by API."""
        controller = APIAccessController(SecurityRole.USER)

        controller.access_log.extend(
            [
                {"api": "wordpress", "success": True},
                {"api": "woocommerce", "success": True},
                {"api": "wordpress", "success": False},
            ]
        )

        wp_log = controller.get_access_log(api_name="wordpress")
        assert len(wp_log) == 2
        assert all(entry["api"] == "wordpress" for entry in wp_log)

    def test_get_registered_apis(self):
        """Should list registered APIs."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint1 = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
        )

        endpoint2 = APIEndpoint(
            name="woocommerce",
            base_url="https://example.com/wp-json/wc/v3",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
        )

        controller.register_api(endpoint1, {"token": "test1"})
        controller.register_api(endpoint2, {"token": "test2"})

        apis = controller.get_registered_apis()
        assert "wordpress" in apis
        assert "woocommerce" in apis

    def test_get_api_info(self):
        """Should get API information."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ, APIScope.WRITE],
            rate_limit=60,
            api_role="author",
            description="WordPress REST API",
        )

        controller.register_api(endpoint, {"token": "test"})

        info = controller.get_api_info("wordpress")
        assert info["name"] == "wordpress"
        assert info["base_url"] == "https://example.com/wp-json/wp/v2"
        assert "read" in info["allowed_scopes"]
        assert "write" in info["allowed_scopes"]
        assert info["api_role"] == "author"

    def test_method_to_scope(self):
        """Should map HTTP methods to scopes."""
        controller = APIAccessController(SecurityRole.USER)

        assert controller._method_to_scope("GET") == APIScope.READ
        assert controller._method_to_scope("POST") == APIScope.WRITE
        assert controller._method_to_scope("PUT") == APIScope.WRITE
        assert controller._method_to_scope("PATCH") == APIScope.WRITE
        assert controller._method_to_scope("DELETE") == APIScope.DELETE
        assert controller._method_to_scope("UNKNOWN") == APIScope.READ  # Default


class TestSecurityScenarios:
    """Test real-world security scenarios."""

    @pytest.mark.asyncio
    async def test_customer_cannot_access_other_api(self):
        """Customer chatbot should only access registered APIs."""
        controller = APIAccessController(SecurityRole.USER)

        # Only WordPress registered
        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],
            rate_limit=60,
        )

        controller.register_api(endpoint, {"token": "test"})

        # Try to access unregistered WooCommerce API
        with pytest.raises(SecurityViolation, match="not registered"):
            await controller.call_api("woocommerce", "GET", "/products")

    @pytest.mark.asyncio
    async def test_read_only_customer(self):
        """Read-only customer cannot write."""
        controller = APIAccessController(SecurityRole.USER)

        endpoint = APIEndpoint(
            name="wordpress",
            base_url="https://example.com/wp-json/wp/v2",
            auth_type=AuthType.BEARER,
            allowed_scopes=[APIScope.READ],  # Only READ
            rate_limit=60,
        )

        controller.register_api(endpoint, {"token": "test"})

        # Can read
        with patch.object(controller, "client", new=AsyncMock()) as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = lambda: None
            mock_client.request.return_value = mock_response

            await controller.call_api("wordpress", "GET", "/posts")

        # Cannot write
        with pytest.raises(SecurityViolation, match="Access denied"):
            await controller.call_api("wordpress", "POST", "/posts")
