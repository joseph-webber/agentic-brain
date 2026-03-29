# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Comprehensive tests for dashboard module."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def sessions_dict():
    """Mock sessions dictionary."""
    return {
        "session-001": {
            "id": "session-001",
            "created_at": datetime.now(UTC).isoformat(),
            "last_accessed": datetime.now(UTC).isoformat(),
            "user_id": "user-123",
        },
        "session-002": {
            "id": "session-002",
            "created_at": datetime.now(UTC).isoformat(),
            "last_accessed": datetime.now(UTC).isoformat(),
            "user_id": "user-456",
        },
    }


@pytest.fixture
def session_messages_dict():
    """Mock session messages dictionary."""
    return {
        "session-001": [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ],
        "session-002": [
            {"role": "user", "content": "How are you?"},
            {"role": "assistant", "content": "I'm great!"},
            {"role": "user", "content": "Tell me more"},
            {"role": "assistant", "content": "Sure!"},
        ],
    }


@pytest.fixture
def app(sessions_dict, session_messages_dict):
    """Create test app with dashboard."""
    from agentic_brain.dashboard import create_dashboard_router

    app = FastAPI()
    router = create_dashboard_router(
        sessions_dict=sessions_dict,
        session_messages_dict=session_messages_dict,
    )
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestDashboardBasicRoutes:
    """Test basic dashboard routes."""

    def test_dashboard_home(self, client):
        """Test dashboard home page returns HTML."""
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert b"<title>" in response.content
        assert b"Agentic Brain" in response.content

    def test_dashboard_home_contains_api_endpoints(self, client):
        """Test dashboard HTML references API endpoints."""
        response = client.get("/dashboard/")
        html = response.text
        # API endpoints are prefixed with /api/dashboard (without extra /dashboard)
        assert "stats" in html
        assert "health" in html
        assert "sessions" in html


class TestStatsEndpoint:
    """Test stats endpoint with detailed JSON structure validation."""

    def test_stats_endpoint_returns_200(self, client):
        """Test stats endpoint returns 200."""
        response = client.get("/dashboard/api/stats")
        assert response.status_code == 200

    def test_stats_json_structure(self, client):
        """Test stats endpoint JSON structure and all required fields."""
        response = client.get("/dashboard/api/stats")
        data = response.json()

        # Verify all required fields present
        assert "timestamp" in data
        assert "sessions_active" in data
        assert "total_messages" in data
        assert "memory_usage_mb" in data
        assert "uptime_seconds" in data

    def test_stats_data_types(self, client):
        """Test stats endpoint data types are correct."""
        response = client.get("/dashboard/api/stats")
        data = response.json()

        # Verify data types
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["sessions_active"], int)
        assert isinstance(data["total_messages"], int)
        assert isinstance(data["memory_usage_mb"], (int, float))
        assert isinstance(data["uptime_seconds"], int)

    def test_stats_values_are_reasonable(
        self, client, sessions_dict, session_messages_dict
    ):
        """Test stats endpoint values are reasonable."""
        response = client.get("/dashboard/api/stats")
        data = response.json()

        # Verify reasonable values
        assert data["sessions_active"] == len(sessions_dict)
        assert data["total_messages"] == sum(
            len(msgs) for msgs in session_messages_dict.values()
        )
        assert data["memory_usage_mb"] > 0
        assert data["uptime_seconds"] >= 0

    def test_stats_timestamp_is_valid_iso8601(self, client):
        """Test stats timestamp is valid ISO8601."""
        response = client.get("/dashboard/api/stats")
        data = response.json()

        # Should be parseable as ISO8601
        try:
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
            assert True
        except ValueError:
            raise AssertionError(f"Invalid ISO8601 timestamp: {data['timestamp']}")


class TestHealthEndpoint:
    """Test health endpoint with all health check components."""

    def test_health_endpoint_returns_200(self, client):
        """Test health endpoint returns 200."""
        response = client.get("/dashboard/api/health")
        assert response.status_code == 200

    def test_health_json_structure(self, client):
        """Test health endpoint JSON structure."""
        response = client.get("/dashboard/api/health")
        data = response.json()

        # Verify all required fields
        assert "status" in data
        assert "neo4j_connected" in data
        assert "llm_provider_available" in data
        assert "memory_ok" in data
        assert "timestamp" in data

    def test_health_data_types(self, client):
        """Test health endpoint data types."""
        response = client.get("/dashboard/api/health")
        data = response.json()

        # Verify data types
        assert isinstance(data["status"], str)
        assert isinstance(data["neo4j_connected"], bool)
        assert isinstance(data["llm_provider_available"], bool)
        assert isinstance(data["memory_ok"], bool)
        assert isinstance(data["timestamp"], str)

    def test_health_status_values(self, client):
        """Test health status values are valid."""
        response = client.get("/dashboard/api/health")
        data = response.json()

        # Status should be 'healthy' or 'degraded'
        assert data["status"] in ["healthy", "degraded"]

    def test_health_status_consistency(self, client):
        """Test health status is consistent with components."""
        response = client.get("/dashboard/api/health")
        data = response.json()

        # If all components healthy, status should be 'healthy'
        all_healthy = (
            data["neo4j_connected"]
            and data["llm_provider_available"]
            and data["memory_ok"]
        )

        if all_healthy:
            assert data["status"] == "healthy"


class TestSessionsEndpoint:
    """Test sessions endpoint with different states."""

    def test_sessions_endpoint_returns_200(self, client):
        """Test sessions endpoint returns 200."""
        response = client.get("/dashboard/api/sessions")
        assert response.status_code == 200

    def test_sessions_json_structure(self, client, sessions_dict):
        """Test sessions JSON structure."""
        response = client.get("/dashboard/api/sessions")
        data = response.json()

        # Should have 'sessions' key
        assert "sessions" in data
        assert isinstance(data["sessions"], list)
        assert len(data["sessions"]) == len(sessions_dict)

    def test_session_object_structure(self, client):
        """Test each session object has correct structure."""
        response = client.get("/dashboard/api/sessions")
        data = response.json()

        for session in data["sessions"]:
            assert "session_id" in session
            assert "created_at" in session
            assert "messages_count" in session
            assert "user_id" in session or session.get("user_id") is not None

    def test_sessions_with_messages_count(
        self, client, sessions_dict, session_messages_dict
    ):
        """Test sessions endpoint shows correct message counts."""
        response = client.get("/dashboard/api/sessions")
        data = response.json()

        # Map session IDs to message counts
        message_counts = {sid: len(msgs) for sid, msgs in session_messages_dict.items()}

        for session in data["sessions"]:
            expected_count = message_counts.get(session["session_id"], 0)
            assert session["messages_count"] == expected_count

    def test_sessions_empty_state(self, sessions_dict, session_messages_dict):
        """Test sessions endpoint with no active sessions."""
        from agentic_brain.dashboard import create_dashboard_router

        app = FastAPI()
        router = create_dashboard_router(
            sessions_dict={},
            session_messages_dict={},
        )
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/dashboard/api/sessions")
        data = response.json()

        assert data["sessions"] == []

    def test_sessions_pagination_structure(self, client):
        """Test sessions endpoint response structure supports pagination."""
        response = client.get("/dashboard/api/sessions")
        data = response.json()

        # Response should be consistent structure
        assert isinstance(data, dict)
        assert "sessions" in data


class TestConfigEndpoint:
    """Test config endpoint GET and POST operations."""

    def test_config_post_endpoint_exists(self, client):
        """Test config endpoint exists and doesn't return 404."""
        response = client.post(
            "/dashboard/api/config", json={"key": "test", "value": "value"}
        )
        # Should return 200 or 422 (validation), not 404
        assert response.status_code != 404

    def test_config_post_valid_payload(self, client):
        """Test config POST with valid payload."""
        response = client.post(
            "/dashboard/api/config",
            json={"key": "temperature", "value": 0.8},
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_config_post_response_structure(self, client):
        """Test config POST response structure."""
        response = client.post(
            "/dashboard/api/config",
            json={"key": "log_level", "value": "debug"},
        )
        data = response.json()

        assert "status" in data
        assert isinstance(data["status"], str)

    def test_config_post_missing_key(self, client):
        """Test config POST with missing key field."""
        response = client.post(
            "/dashboard/api/config",
            json={"value": "test"},
        )
        # Should return 422 (unprocessable entity) for validation error
        assert response.status_code == 422

    def test_config_post_missing_value(self, client):
        """Test config POST with missing value field."""
        response = client.post(
            "/dashboard/api/config",
            json={"key": "temperature"},
        )
        # Should return 422 (unprocessable entity) for validation error
        assert response.status_code == 422


class TestErrorHandling:
    """Test error handling and 404 routes."""

    def test_unknown_route_returns_404(self, client):
        """Test unknown route returns 404."""
        response = client.get("/dashboard/unknown-route")
        assert response.status_code == 404

    def test_dashboard_api_unknown_route(self, client):
        """Test unknown API route returns 404."""
        response = client.get("/dashboard/api/unknown")
        assert response.status_code == 404

    def test_wrong_http_method(self, client):
        """Test wrong HTTP method returns 405."""
        # GET to a POST-only endpoint
        response = client.get("/dashboard/api/config")
        # FastAPI returns 405 Method Not Allowed
        assert response.status_code == 405

    def test_malformed_json(self, client):
        """Test malformed JSON returns error."""
        response = client.post(
            "/dashboard/api/config",
            data="{invalid json}",
            headers={"Content-Type": "application/json"},
        )
        # Should return 422 or 400
        assert response.status_code in [400, 422]


class TestHTMLContent:
    """Test HTML content and accessibility features."""

    def test_html_has_main_element(self, client):
        """Test HTML has main content element."""
        response = client.get("/dashboard/")
        html = response.text
        assert 'id="main-content"' in html or "<main" in html

    def test_html_has_skip_link(self, client):
        """Test HTML has skip to main content link."""
        response = client.get("/dashboard/")
        html = response.text
        assert "skip" in html.lower() or "main-content" in html

    def test_html_has_accessibility_attributes(self, client):
        """Test HTML has accessibility attributes."""
        response = client.get("/dashboard/")
        html = response.text

        # Should have aria-label, role, etc.
        assert "aria-label" in html or "role=" in html

    def test_html_has_proper_language_tag(self, client):
        """Test HTML has language attribute."""
        response = client.get("/dashboard/")
        html = response.text
        assert 'lang="en"' in html or "lang=en" in html

    def test_html_has_viewport_meta_tag(self, client):
        """Test HTML has viewport meta tag for responsive design."""
        response = client.get("/dashboard/")
        html = response.text
        assert "viewport" in html

    def test_html_has_charset_meta_tag(self, client):
        """Test HTML has charset declaration."""
        response = client.get("/dashboard/")
        html = response.text
        assert "charset" in html.lower()

    def test_html_has_font_awesome_icons(self, client):
        """Test HTML includes Font Awesome for icons."""
        response = client.get("/dashboard/")
        html = response.text
        assert "font-awesome" in html.lower() or "fontawesome" in html.lower()

    def test_html_has_button_refresh(self, client):
        """Test HTML has refresh button with label."""
        response = client.get("/dashboard/")
        html = response.text
        assert "refresh" in html.lower()

    def test_html_refresh_button_has_aria_label(self, client):
        """Test refresh button has accessibility label."""
        response = client.get("/dashboard/")
        html = response.text
        # Look for button with aria-label
        assert "aria-label" in html and ("refresh" in html.lower() or "Refresh" in html)


class TestCSSAndStyling:
    """Test dashboard CSS and styling features."""

    def test_html_has_tailwind_css(self, client):
        """Test HTML includes Tailwind CSS."""
        response = client.get("/dashboard/")
        html = response.text
        assert "tailwindcss" in html.lower()

    def test_html_has_custom_styles(self, client):
        """Test HTML has custom CSS styles."""
        response = client.get("/dashboard/")
        html = response.text
        assert "<style>" in html

    def test_html_has_gradient_classes(self, client):
        """Test HTML includes gradient styling."""
        response = client.get("/dashboard/")
        html = response.text
        assert "gradient" in html.lower()

    def test_html_has_status_indicators(self, client):
        """Test HTML includes status indicator styling."""
        response = client.get("/dashboard/")
        html = response.text
        assert "status-indicator" in html.lower()

    def test_html_has_dark_theme(self, client):
        """Test HTML uses dark theme colors."""
        response = client.get("/dashboard/")
        html = response.text
        # Should have dark gray/black theme
        assert "bg-gray" in html or "dark" in html.lower()

    def test_html_has_focus_visible_styles(self, client):
        """Test HTML includes focus-visible styling for accessibility."""
        response = client.get("/dashboard/")
        html = response.text
        assert "focus" in html.lower()

    def test_html_has_responsive_grid(self, client):
        """Test HTML has responsive grid layout."""
        response = client.get("/dashboard/")
        html = response.text
        assert "grid" in html.lower() or "responsive" in html.lower()


class TestAPIResponseFormat:
    """Test API response format consistency."""

    def test_all_endpoints_return_json(self, client):
        """Test all API endpoints return JSON."""
        endpoints = [
            "/dashboard/api/stats",
            "/dashboard/api/health",
            "/dashboard/api/sessions",
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert "application/json" in response.headers.get("content-type", "")

    def test_stats_timestamp_format_consistency(self, client):
        """Test stats endpoint uses consistent timestamp format."""
        response1 = client.get("/dashboard/api/stats")
        response2 = client.get("/dashboard/api/stats")

        data1 = response1.json()
        data2 = response2.json()

        # Both should have ISO8601 timestamps (end in digit for milliseconds)
        import re

        iso8601_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        assert re.match(iso8601_pattern, data1["timestamp"])
        assert re.match(iso8601_pattern, data2["timestamp"])

    def test_health_timestamp_format_consistency(self, client):
        """Test health endpoint uses consistent timestamp format."""
        response = client.get("/dashboard/api/health")
        data = response.json()

        # Should have ISO8601 timestamp
        import re

        iso8601_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        assert re.match(iso8601_pattern, data["timestamp"])


class TestSessionWorkflow:
    """Test session creation and deletion workflow."""

    def test_delete_sessions_endpoint_exists(self, client):
        """Test delete sessions endpoint exists."""
        response = client.delete("/dashboard/api/sessions")
        assert response.status_code == 200

    def test_delete_sessions_returns_count(self, client):
        """Test delete sessions returns cleared count."""
        response = client.delete("/dashboard/api/sessions")
        data = response.json()

        assert "status" in data
        assert "cleared" in data
        assert data["status"] == "success"

    def test_delete_sessions_clears_data(
        self, client, sessions_dict, session_messages_dict
    ):
        """Test delete sessions actually clears session data."""
        # Verify sessions exist
        response1 = client.get("/dashboard/api/sessions")
        data1 = response1.json()
        assert len(data1["sessions"]) > 0

        # Delete sessions
        response_delete = client.delete("/dashboard/api/sessions")
        cleared = response_delete.json()["cleared"]
        assert cleared > 0

        # Verify sessions are cleared
        response2 = client.get("/dashboard/api/sessions")
        data2 = response2.json()
        assert len(data2["sessions"]) == 0

    def test_stats_after_session_deletion(self, client):
        """Test stats endpoint after session deletion."""
        # Delete all sessions
        client.delete("/dashboard/api/sessions")

        # Stats should show 0 active sessions
        response = client.get("/dashboard/api/stats")
        data = response.json()
        assert data["sessions_active"] == 0
        assert data["total_messages"] == 0


class TestConcurrentRequests:
    """Test concurrent request handling."""

    def test_concurrent_stats_requests(self, client):
        """Test concurrent stats requests are handled."""

        def fetch_stats():
            response = client.get("/dashboard/api/stats")
            return response.status_code == 200

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_stats) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(results)

    def test_concurrent_health_requests(self, client):
        """Test concurrent health requests are handled."""

        def fetch_health():
            response = client.get("/dashboard/api/health")
            return response.status_code == 200

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_health) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(results)

    def test_concurrent_sessions_requests(self, client):
        """Test concurrent sessions requests are handled."""

        def fetch_sessions():
            response = client.get("/dashboard/api/sessions")
            return response.status_code == 200

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_sessions) for _ in range(10)]
            results = [f.result() for f in futures]

        assert all(results)

    def test_concurrent_mixed_requests(self, client):
        """Test concurrent mixed endpoint requests."""
        endpoints = [
            "/dashboard/api/stats",
            "/dashboard/api/health",
            "/dashboard/api/sessions",
        ]

        def fetch_random():
            import random

            endpoint = random.choice(endpoints)
            response = client.get(endpoint)
            return response.status_code == 200

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_random) for _ in range(15)]
            results = [f.result() for f in futures]

        assert all(results)


class TestRouterCreation:
    """Test router creation and configuration."""

    def test_router_is_api_router(self):
        """Test create_dashboard_router returns APIRouter."""
        from fastapi import APIRouter

        from agentic_brain.dashboard import create_dashboard_router

        router = create_dashboard_router()
        assert isinstance(router, APIRouter)

    def test_router_with_custom_sessions(self):
        """Test router with custom session dictionaries."""
        from agentic_brain.dashboard import create_dashboard_router

        custom_sessions = {"test-session": {}}
        custom_messages = {"test-session": []}

        router = create_dashboard_router(
            sessions_dict=custom_sessions,
            session_messages_dict=custom_messages,
        )

        assert router is not None

    def test_router_has_all_routes(self):
        """Test router has all expected routes."""
        from agentic_brain.dashboard import create_dashboard_router

        router = create_dashboard_router()

        # Get all route paths
        paths = [route.path for route in router.routes]

        # Should have dashboard routes
        assert any("" in p for p in paths)  # Dashboard home
        assert any("stats" in p for p in paths)  # Stats endpoint
        assert any("health" in p for p in paths)  # Health endpoint
        assert any("sessions" in p for p in paths)  # Sessions endpoint
        assert any("config" in p for p in paths)  # Config endpoint
