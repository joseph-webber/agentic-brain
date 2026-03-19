"""Tests for dashboard module."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

@pytest.fixture
def app():
    """Create test app with dashboard."""
    from agentic_brain.dashboard import create_dashboard_router
    app = FastAPI()
    router = create_dashboard_router()
    # Router already has /dashboard prefix internally
    app.include_router(router)
    return app

@pytest.fixture
def client(app):
    return TestClient(app)

class TestDashboardRoutes:
    def test_dashboard_home(self, client):
        """Test dashboard home page returns HTML."""
        response = client.get("/dashboard/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
    def test_dashboard_stats(self, client):
        """Test stats endpoint returns JSON."""
        response = client.get("/dashboard/api/stats")
        assert response.status_code == 200
        data = response.json()
        assert "sessions_active" in data or "timestamp" in data
        
    def test_dashboard_health(self, client):
        """Test health endpoint."""
        response = client.get("/dashboard/api/health")
        assert response.status_code == 200
        
    def test_dashboard_sessions_list(self, client):
        """Test sessions list endpoint."""
        response = client.get("/dashboard/api/sessions")
        assert response.status_code == 200
        assert isinstance(response.json(), (list, dict))

class TestDashboardHTML:
    def test_html_has_title(self, client):
        """Test dashboard HTML has proper title."""
        response = client.get("/dashboard/")
        assert b"<title>" in response.content
        
    def test_html_is_accessible(self, client):
        """Test dashboard has accessibility features."""
        response = client.get("/dashboard/")
        html = response.text
        # Should have skip link or main landmark
        assert "main" in html.lower() or "skip" in html.lower()

class TestDashboardConfig:
    def test_config_endpoint_exists(self, client):
        """Test config endpoint exists."""
        response = client.post("/dashboard/api/config", json={})
        # Should return 200 or 422 (validation), not 404
        assert response.status_code != 404

class TestRouterCreation:
    def test_router_is_api_router(self):
        """Test create_dashboard_router returns APIRouter."""
        from agentic_brain.dashboard import create_dashboard_router
        router = create_dashboard_router()
        from fastapi import APIRouter
        assert isinstance(router, APIRouter)
        
    def test_router_has_routes(self):
        """Test router has expected routes."""
        from agentic_brain.dashboard import create_dashboard_router
        router = create_dashboard_router()
        routes = [r.path for r in router.routes]
        assert "/dashboard" in routes or "/dashboard/api/stats" in routes
