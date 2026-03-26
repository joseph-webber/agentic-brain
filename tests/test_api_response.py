# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for JHipster-style API response wrappers."""

from datetime import UTC, datetime, timezone

import pytest

from agentic_brain.api.models import (
    ApiResponse,
    HealthIndicator,
    HealthResponse,
    PaginationInfo,
)


class TestPaginationInfo:
    """Tests for pagination helper."""

    def test_from_total(self):
        """Test pagination calculation from total items."""
        pagination = PaginationInfo.from_total(page=0, size=10, total_items=95)
        assert pagination.page == 0
        assert pagination.size == 10
        assert pagination.total_items == 95
        assert pagination.total_pages == 10  # 95/10 = 9.5 -> 10 pages

    def test_from_total_exact_fit(self):
        """Test pagination when items fit exactly."""
        pagination = PaginationInfo.from_total(page=0, size=10, total_items=100)
        assert pagination.total_pages == 10

    def test_from_total_single_page(self):
        """Test pagination with single page."""
        pagination = PaginationInfo.from_total(page=0, size=10, total_items=5)
        assert pagination.total_pages == 1

    def test_from_total_empty(self):
        """Test pagination with no items."""
        pagination = PaginationInfo.from_total(page=0, size=10, total_items=0)
        assert pagination.total_pages == 0


class TestApiResponse:
    """Tests for JHipster-style API response wrapper."""

    def test_ok_simple(self):
        """Test simple success response."""
        response = ApiResponse.ok(data={"id": 123})
        assert response.success is True
        assert response.data == {"id": 123}
        assert response.errors == []
        assert response.pagination is None

    def test_ok_with_message(self):
        """Test success response with message."""
        response = ApiResponse.ok(data=None, message="Resource created")
        assert response.message == "Resource created"

    def test_ok_with_pagination(self):
        """Test success response with pagination."""
        pagination = PaginationInfo.from_total(0, 10, 50)
        response = ApiResponse.ok(data=[1, 2, 3], pagination=pagination)
        assert response.pagination is not None
        assert response.pagination.total_pages == 5

    def test_ok_with_links(self):
        """Test success response with HATEOAS links."""
        response = ApiResponse.ok(
            data={"id": 123}, links={"self": "/api/v1/resource/123"}
        )
        assert response.links == {"self": "/api/v1/resource/123"}

    def test_error_single_message(self):
        """Test error response with single message."""
        response = ApiResponse.error("Something went wrong")
        assert response.success is False
        assert response.errors == ["Something went wrong"]
        assert response.message == "Request failed"

    def test_error_multiple_messages(self):
        """Test error response with multiple messages."""
        response = ApiResponse.error(["Error 1", "Error 2"])
        assert len(response.errors) == 2

    def test_error_custom_message(self):
        """Test error response with custom message."""
        response = ApiResponse.error("Validation failed", message="Invalid input")
        assert response.message == "Invalid input"

    def test_paginated_response(self):
        """Test paginated list response."""
        data = [1, 2, 3, 4, 5]
        response = ApiResponse.paginated(
            data=data, page=0, size=5, total_items=50, base_url="/api/items"
        )
        assert response.success is True
        assert response.data == data
        assert response.pagination.page == 0
        assert response.pagination.total_pages == 10
        assert "self" in response.links
        assert "next" in response.links
        assert "last" in response.links
        assert "prev" not in response.links  # First page

    def test_paginated_middle_page(self):
        """Test pagination links for middle page."""
        response = ApiResponse.paginated(
            data=[1, 2], page=5, size=10, total_items=100, base_url="/api/items"
        )
        assert "first" in response.links
        assert "prev" in response.links
        assert "next" in response.links
        assert "last" in response.links

    def test_paginated_last_page(self):
        """Test pagination links for last page."""
        response = ApiResponse.paginated(
            data=[1], page=9, size=10, total_items=91, base_url="/api/items"
        )
        assert "next" not in response.links  # Last page
        assert "prev" in response.links

    def test_timestamp_auto_generated(self):
        """Test timestamp is automatically generated."""
        response = ApiResponse.ok()
        assert isinstance(response.timestamp, datetime)
        assert response.timestamp.tzinfo == UTC


class TestHealthIndicator:
    """Tests for health indicator."""

    def test_default_healthy(self):
        """Test default status is healthy."""
        indicator = HealthIndicator()
        assert indicator.status == "healthy"
        assert indicator.details == {}

    def test_with_details(self):
        """Test indicator with details."""
        indicator = HealthIndicator(
            status="healthy", details={"connections": 5, "latency_ms": 10}
        )
        assert indicator.details["connections"] == 5


class TestHealthResponse:
    """Tests for health response."""

    def test_default_healthy(self):
        """Test default health response."""
        response = HealthResponse()
        assert response.status == "healthy"
        assert response.components == {}

    def test_from_indicators_all_healthy(self):
        """Test health aggregation when all healthy."""
        indicators = {
            "neo4j": HealthIndicator(status="healthy"),
            "redis": HealthIndicator(status="healthy"),
        }
        response = HealthResponse.from_indicators(indicators)
        assert response.status == "healthy"

    def test_from_indicators_one_degraded(self):
        """Test health aggregation with degraded component."""
        indicators = {
            "neo4j": HealthIndicator(status="healthy"),
            "redis": HealthIndicator(status="degraded"),
        }
        response = HealthResponse.from_indicators(indicators)
        assert response.status == "degraded"

    def test_from_indicators_one_unhealthy(self):
        """Test health aggregation with unhealthy component."""
        indicators = {
            "neo4j": HealthIndicator(status="unhealthy"),
            "redis": HealthIndicator(status="healthy"),
        }
        response = HealthResponse.from_indicators(indicators)
        assert response.status == "unhealthy"

    def test_from_indicators_unhealthy_trumps_degraded(self):
        """Test unhealthy status takes priority."""
        indicators = {
            "neo4j": HealthIndicator(status="unhealthy"),
            "redis": HealthIndicator(status="degraded"),
            "llm": HealthIndicator(status="healthy"),
        }
        response = HealthResponse.from_indicators(indicators)
        assert response.status == "unhealthy"
