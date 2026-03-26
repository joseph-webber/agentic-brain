# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""Tests for DevOps and monitoring loaders (ArgoCD, Jenkins, Datadog, Prometheus, Splunk, Grafana)."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.rag.loaders.argocd_loader import ArgoCDLoader
from agentic_brain.rag.loaders.datadog_loader import DatadogLoader
from agentic_brain.rag.loaders.grafana_loader import GrafanaLoader
from agentic_brain.rag.loaders.jenkins_loader import JenkinsLoader
from agentic_brain.rag.loaders.prometheus_loader import PrometheusLoader
from agentic_brain.rag.loaders.splunk_loader import SplunkLoader

# ============================================================================
# ArgoCD Loader Tests
# ============================================================================


class TestArgoCDLoader:
    """Tests for ArgoCD loader."""

    @patch("agentic_brain.rag.loaders.argocd_loader.requests")
    def test_argocd_authentication(self, mock_requests):
        """Test ArgoCD authentication."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"version": "v2.9.0"}
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        loader = ArgoCDLoader(server="argocd.example.com", token="test-token")
        result = loader.authenticate()

        assert result is True
        mock_session.get.assert_called_once()

    @patch("agentic_brain.rag.loaders.argocd_loader.requests")
    def test_argocd_load_application(self, mock_requests):
        """Test loading ArgoCD application."""
        mock_session = MagicMock()

        # Mock version check
        version_response = MagicMock()
        version_response.json.return_value = {"version": "v2.9.0"}

        # Mock application response
        app_response = MagicMock()
        app_response.ok = True
        app_response.json.return_value = {
            "metadata": {"name": "test-app", "namespace": "argocd"},
            "spec": {
                "source": {"repoURL": "https://github.com/test/repo", "path": "k8s"},
                "destination": {
                    "server": "https://kubernetes.default.svc",
                    "namespace": "default",
                },
            },
            "status": {"sync": {"status": "Synced"}, "health": {"status": "Healthy"}},
        }

        # Mock history response
        history_response = MagicMock()
        history_response.ok = True
        history_response.json.return_value = []

        mock_session.get.side_effect = [
            version_response,
            app_response,
            history_response,
        ]
        mock_requests.Session.return_value = mock_session

        loader = ArgoCDLoader(server="argocd.example.com", token="test-token")
        loader.authenticate()
        doc = loader.load_document("test-app")

        assert doc is not None
        assert "test-app" in doc.content
        assert doc.metadata["application"] == "test-app"
        assert doc.metadata["sync_status"] == "Synced"


# ============================================================================
# Jenkins Loader Tests
# ============================================================================


class TestJenkinsLoader:
    """Tests for Jenkins loader."""

    @patch("agentic_brain.rag.loaders.jenkins_loader.requests")
    def test_jenkins_authentication(self, mock_requests):
        """Test Jenkins authentication."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        loader = JenkinsLoader(
            url="https://jenkins.example.com", username="admin", token="token"
        )
        result = loader.authenticate()

        assert result is True

    @patch("agentic_brain.rag.loaders.jenkins_loader.requests")
    def test_jenkins_load_job(self, mock_requests):
        """Test loading Jenkins job."""
        mock_session = MagicMock()

        # Mock auth
        auth_response = MagicMock()
        auth_response.raise_for_status = MagicMock()

        # Mock job response
        job_response = MagicMock()
        job_response.ok = True
        job_response.json.return_value = {
            "name": "test-job",
            "url": "https://jenkins.example.com/job/test-job",
            "description": "Test job",
            "builds": [
                {
                    "number": 1,
                    "result": "SUCCESS",
                    "timestamp": 1640000000000,
                    "duration": 60000,
                }
            ],
        }

        # Mock config
        config_response = MagicMock()
        config_response.ok = True
        config_response.text = "<project></project>"

        mock_session.get.side_effect = [auth_response, job_response, config_response]
        mock_requests.Session.return_value = mock_session

        loader = JenkinsLoader(url="https://jenkins.example.com")
        loader.authenticate()
        doc = loader.load_document("test-job")

        assert doc is not None
        assert "test-job" in doc.content
        assert doc.metadata["job_name"] == "test-job"


# ============================================================================
# Datadog Loader Tests
# ============================================================================


class TestDatadogLoader:
    """Tests for Datadog loader."""

    @pytest.mark.skipif(
        not hasattr(DatadogLoader, "__init__"), reason="Datadog client not available"
    )
    def test_datadog_init(self):
        """Test Datadog loader initialization."""
        try:
            loader = DatadogLoader(api_key="test-key", app_key="test-app-key")
            assert loader.api_key == "test-key"
            assert loader.app_key == "test-app-key"
        except ImportError:
            pytest.skip("datadog-api-client not installed")


# ============================================================================
# Prometheus Loader Tests
# ============================================================================


class TestPrometheusLoader:
    """Tests for Prometheus loader."""

    @patch("agentic_brain.rag.loaders.prometheus_loader.requests")
    def test_prometheus_authentication(self, mock_requests):
        """Test Prometheus authentication."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        loader = PrometheusLoader(url="http://prometheus:9090")
        result = loader.authenticate()

        assert result is True

    @patch("agentic_brain.rag.loaders.prometheus_loader.requests")
    def test_prometheus_query_metric(self, mock_requests):
        """Test querying Prometheus metrics."""
        mock_session = MagicMock()

        # Mock auth
        auth_response = MagicMock()
        auth_response.raise_for_status = MagicMock()

        # Mock query response
        query_response = MagicMock()
        query_response.ok = True
        query_response.json.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "metric": {"__name__": "up", "job": "prometheus"},
                        "value": [1640000000, "1"],
                    }
                ]
            },
        }

        mock_session.get.side_effect = [auth_response, query_response]
        mock_requests.Session.return_value = mock_session

        loader = PrometheusLoader(url="http://prometheus:9090")
        loader.authenticate()
        doc = loader.load_document("up")

        assert doc is not None
        assert "up" in doc.content
        assert doc.metadata["query"] == "up"


# ============================================================================
# Splunk Loader Tests
# ============================================================================


class TestSplunkLoader:
    """Tests for Splunk loader."""

    @patch("agentic_brain.rag.loaders.splunk_loader.requests")
    def test_splunk_authentication_with_token(self, mock_requests):
        """Test Splunk authentication with token."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        loader = SplunkLoader(host="splunk.example.com", token="test-token")
        result = loader.authenticate()

        assert result is True

    @patch("agentic_brain.rag.loaders.splunk_loader.requests")
    def test_splunk_authentication_with_credentials(self, mock_requests):
        """Test Splunk authentication with username/password."""
        mock_session = MagicMock()

        # Mock auth response
        auth_response = MagicMock()
        auth_response.raise_for_status = MagicMock()
        auth_response.json.return_value = {"sessionKey": "test-session-key"}

        # Mock info response
        info_response = MagicMock()
        info_response.raise_for_status = MagicMock()

        mock_session.post.return_value = auth_response
        mock_session.get.return_value = info_response
        mock_requests.Session.return_value = mock_session

        loader = SplunkLoader(
            host="splunk.example.com", username="admin", password="password"
        )
        result = loader.authenticate()

        assert result is True
        assert loader._session_key == "test-session-key"


# ============================================================================
# Grafana Loader Tests
# ============================================================================


class TestGrafanaLoader:
    """Tests for Grafana loader."""

    @patch("agentic_brain.rag.loaders.grafana_loader.requests")
    def test_grafana_authentication(self, mock_requests):
        """Test Grafana authentication."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.get.return_value = mock_response
        mock_requests.Session.return_value = mock_session

        loader = GrafanaLoader(url="https://grafana.example.com", api_key="test-key")
        result = loader.authenticate()

        assert result is True

    @patch("agentic_brain.rag.loaders.grafana_loader.requests")
    def test_grafana_load_dashboard(self, mock_requests):
        """Test loading Grafana dashboard."""
        mock_session = MagicMock()

        # Mock auth
        auth_response = MagicMock()
        auth_response.raise_for_status = MagicMock()

        # Mock dashboard response
        dashboard_response = MagicMock()
        dashboard_response.ok = True
        dashboard_response.json.return_value = {
            "dashboard": {
                "uid": "test-dashboard",
                "title": "Test Dashboard",
                "tags": ["monitoring"],
                "panels": [{"title": "CPU Usage", "type": "graph"}],
            },
            "meta": {"folderTitle": "DevOps", "created": "2024-01-01T00:00:00Z"},
        }

        mock_session.get.side_effect = [auth_response, dashboard_response]
        mock_requests.Session.return_value = mock_session

        loader = GrafanaLoader(url="https://grafana.example.com", api_key="test-key")
        loader.authenticate()
        doc = loader.load_document("test-dashboard")

        assert doc is not None
        assert "Test Dashboard" in doc.content
        assert doc.metadata["dashboard_uid"] == "test-dashboard"


# ============================================================================
# Integration Tests
# ============================================================================


class TestDevOpsLoadersIntegration:
    """Integration tests for DevOps loaders."""

    def test_all_loaders_have_source_name(self):
        """Verify all loaders have source_name property."""
        loaders = [
            (ArgoCDLoader, {"server": "test", "token": "test"}),
            (JenkinsLoader, {"url": "http://test"}),
            (PrometheusLoader, {"url": "http://test"}),
            (SplunkLoader, {"host": "test", "token": "test"}),
            (GrafanaLoader, {"url": "http://test", "api_key": "test"}),
        ]

        for loader_class, kwargs in loaders:
            try:
                loader = loader_class(**kwargs)
                assert hasattr(loader, "source_name")
                assert isinstance(loader.source_name, str)
                assert len(loader.source_name) > 0
            except ImportError:
                pytest.skip(f"{loader_class.__name__} dependencies not installed")

    def test_all_loaders_have_authenticate_method(self):
        """Verify all loaders have authenticate method."""
        loaders = [
            (ArgoCDLoader, {"server": "test", "token": "test"}),
            (JenkinsLoader, {"url": "http://test"}),
            (PrometheusLoader, {"url": "http://test"}),
            (SplunkLoader, {"host": "test", "token": "test"}),
            (GrafanaLoader, {"url": "http://test", "api_key": "test"}),
        ]

        for loader_class, kwargs in loaders:
            try:
                loader = loader_class(**kwargs)
                assert hasattr(loader, "authenticate")
                assert callable(loader.authenticate)
            except ImportError:
                pytest.skip(f"{loader_class.__name__} dependencies not installed")
