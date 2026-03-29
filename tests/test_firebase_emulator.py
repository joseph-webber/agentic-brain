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

"""Tests for Firebase Emulator support."""

import os
from unittest.mock import Mock, patch

import pytest

from agentic_brain.transport.firebase_emulator import (
    EmulatorConfig,
    EmulatorStatus,
    FirebaseEmulator,
    get_emulator,
    is_port_open,
    setup_emulators,
    use_emulators,
)


class TestEmulatorConfig:
    """Tests for EmulatorConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EmulatorConfig()

        assert config.auth_host == "localhost"
        assert config.auth_port == 9099
        assert config.firestore_host == "localhost"
        assert config.firestore_port == 8080
        assert config.database_port == 9000
        assert config.project_id == "demo-project"

    def test_custom_config(self):
        """Test custom configuration."""
        config = EmulatorConfig(
            auth_port=9100, firestore_port=8081, project_id="my-project"
        )

        assert config.auth_port == 9100
        assert config.firestore_port == 8081
        assert config.project_id == "my-project"

    def test_auth_url_property(self):
        """Test auth_url property."""
        config = EmulatorConfig()

        assert config.auth_url == "http://localhost:9099"

    def test_firestore_url_property(self):
        """Test firestore_url property."""
        config = EmulatorConfig()

        assert config.firestore_url == "localhost:8080"

    def test_database_url_property(self):
        """Test database_url property."""
        config = EmulatorConfig()

        assert config.database_url == "http://localhost:9000"

    def test_from_env(self):
        """Test creating config from environment."""
        with patch.dict(
            os.environ,
            {
                "FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:9200",
                "FIRESTORE_EMULATOR_HOST": "127.0.0.1:8082",
                "GCLOUD_PROJECT": "test-project",
            },
            clear=False,
        ):
            config = EmulatorConfig.from_env()

            assert config.auth_host == "127.0.0.1"
            assert config.auth_port == 9200
            assert config.firestore_host == "127.0.0.1"
            assert config.firestore_port == 8082
            assert config.project_id == "test-project"

    def test_from_env_partial(self):
        """Test from_env with partial environment."""
        with patch.dict(
            os.environ, {"FIREBASE_AUTH_EMULATOR_HOST": "host:9999"}, clear=False
        ):
            config = EmulatorConfig.from_env()

            assert config.auth_host == "host"
            assert config.auth_port == 9999
            # Others should be defaults
            assert config.firestore_port == 8080

    def test_to_env_dict(self):
        """Test converting to env dict."""
        config = EmulatorConfig(project_id="my-proj")
        env = config.to_env_dict()

        assert env["FIREBASE_AUTH_EMULATOR_HOST"] == "localhost:9099"
        assert env["FIRESTORE_EMULATOR_HOST"] == "localhost:8080"
        assert env["GCLOUD_PROJECT"] == "my-proj"

    def test_apply_to_env(self):
        """Test applying config to environment."""
        config = EmulatorConfig(project_id="applied-proj")

        # Save original
        original = os.environ.get("GCLOUD_PROJECT")

        try:
            config.apply_to_env()

            assert os.environ["GCLOUD_PROJECT"] == "applied-proj"
            assert os.environ["FIREBASE_AUTH_EMULATOR_HOST"] == "localhost:9099"
        finally:
            # Restore
            if original:
                os.environ["GCLOUD_PROJECT"] = original
            else:
                os.environ.pop("GCLOUD_PROJECT", None)


class TestEmulatorStatus:
    """Tests for EmulatorStatus dataclass."""

    def test_default_status(self):
        """Test default status (all off)."""
        status = EmulatorStatus()

        assert status.auth_running is False
        assert status.firestore_running is False
        assert status.any_running is False
        assert status.all_running is False

    def test_some_running(self):
        """Test when some emulators running."""
        status = EmulatorStatus(auth_running=True, firestore_running=True)

        assert status.any_running is True
        assert status.all_running is False

    def test_all_running(self):
        """Test when all emulators running."""
        status = EmulatorStatus(
            auth_running=True,
            firestore_running=True,
            database_running=True,
            storage_running=True,
            functions_running=True,
            pubsub_running=True,
        )

        assert status.any_running is True
        assert status.all_running is True

    def test_to_dict(self):
        """Test converting to dictionary."""
        status = EmulatorStatus(auth_running=True)
        data = status.to_dict()

        assert data["auth"] is True
        assert data["firestore"] is False
        assert len(data) == 6


class TestIsPortOpen:
    """Tests for is_port_open function."""

    def test_closed_port(self):
        """Test checking a closed port."""
        # Port 59999 should be closed on most systems
        result = is_port_open("localhost", 59999, timeout=0.1)

        assert result is False

    def test_invalid_host(self):
        """Test with invalid host."""
        result = is_port_open("invalid.host.that.doesnt.exist", 80, timeout=0.1)

        assert result is False

    @pytest.mark.skip(reason="Requires actual open port")
    def test_open_port(self):
        """Test checking an open port."""
        # This would need a server running
        pass


class TestFirebaseEmulator:
    """Tests for FirebaseEmulator class."""

    def test_init_default(self):
        """Test default initialization."""
        emulator = FirebaseEmulator()

        assert emulator.config is not None
        assert emulator.config.project_id == "demo-project"

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = EmulatorConfig(project_id="custom")
        emulator = FirebaseEmulator(config)

        assert emulator.config.project_id == "custom"

    def test_check_status(self):
        """Test checking emulator status."""
        emulator = FirebaseEmulator()

        status = emulator.check_status()

        assert isinstance(status, EmulatorStatus)
        # On most systems, emulators won't be running
        assert status.auth_running is False

    def test_check_status_caching(self):
        """Test that status is cached."""
        emulator = FirebaseEmulator()

        status1 = emulator.check_status()
        status2 = emulator.check_status()

        # Should be same object (cached)
        assert status1 is status2

    def test_check_status_refresh(self):
        """Test refreshing status."""
        emulator = FirebaseEmulator()

        status1 = emulator.check_status()
        status2 = emulator.check_status(refresh=True)

        # Should be different objects
        assert status1 is not status2

    def test_is_running(self):
        """Test is_running helper."""
        emulator = FirebaseEmulator()

        # Emulators not running
        assert emulator.is_running("auth") is False
        assert emulator.is_running("firestore") is False

    def test_is_running_invalid_service(self):
        """Test is_running with invalid service."""
        emulator = FirebaseEmulator()

        result = emulator.is_running("invalid")

        assert result is False

    def test_configure_auth_not_running(self):
        """Test configure_auth when not running."""
        emulator = FirebaseEmulator()

        result = emulator.configure_auth()

        assert result is False

    def test_configure_firestore_not_running(self):
        """Test configure_firestore when not running."""
        emulator = FirebaseEmulator()

        result = emulator.configure_firestore()

        assert result is False

    @patch("agentic_brain.transport.firebase_emulator.is_port_open")
    def test_configure_auth_running(self, mock_port):
        """Test configure_auth when running."""
        mock_port.return_value = True

        emulator = FirebaseEmulator()
        emulator._status = EmulatorStatus(auth_running=True)

        result = emulator.configure_auth()

        assert result is True
        assert os.environ.get("FIREBASE_AUTH_EMULATOR_HOST") == "localhost:9099"

    @patch("agentic_brain.transport.firebase_emulator.is_port_open")
    def test_auto_configure(self, mock_port):
        """Test auto_configure."""

        # Simulate firestore running
        def port_check(host, port):
            return port == 8080  # Only Firestore running

        mock_port.side_effect = port_check

        emulator = FirebaseEmulator()
        results = emulator.auto_configure()

        assert "firestore" in results

    def test_get_connection_info(self):
        """Test getting connection info."""
        emulator = FirebaseEmulator()
        info = emulator.get_connection_info()

        assert "auth" in info
        assert "firestore" in info
        assert "database" in info
        assert "project_id" in info

        assert info["auth"]["url"] == "http://localhost:9099"
        assert info["firestore"]["env_var"] == "FIRESTORE_EMULATOR_HOST"


class TestGlobalFunctions:
    """Tests for global helper functions."""

    def test_get_emulator(self):
        """Test getting global emulator instance."""
        em1 = get_emulator()
        em2 = get_emulator()

        assert em1 is em2  # Same instance

    def test_use_emulators_default(self):
        """Test use_emulators default (False)."""
        # Clear env vars
        with patch.dict(os.environ, {}, clear=True):
            result = use_emulators()
            assert result is False

    def test_use_emulators_enabled(self):
        """Test use_emulators when enabled."""
        with patch.dict(os.environ, {"FIREBASE_USE_EMULATOR": "true"}):
            result = use_emulators()
            assert result is True

    def test_use_emulators_enabled_alt(self):
        """Test use_emulators with alternate env var."""
        with patch.dict(os.environ, {"USE_FIREBASE_EMULATOR": "1"}):
            result = use_emulators()
            assert result is True

    def test_use_emulators_yes(self):
        """Test use_emulators with 'yes' value."""
        with patch.dict(os.environ, {"FIREBASE_USE_EMULATOR": "yes"}):
            result = use_emulators()
            assert result is True

    def test_setup_emulators_disabled(self):
        """Test setup_emulators when disabled."""
        with patch.dict(os.environ, {}, clear=True):
            result = setup_emulators()
            assert result == {}

    @patch("agentic_brain.transport.firebase_emulator.use_emulators")
    @patch("agentic_brain.transport.firebase_emulator.get_emulator")
    def test_setup_emulators_enabled(self, mock_get, mock_use):
        """Test setup_emulators when enabled."""
        mock_use.return_value = True
        mock_emulator = Mock()
        mock_emulator.auto_configure.return_value = {"auth": True}
        mock_get.return_value = mock_emulator

        result = setup_emulators()

        assert result == {"auth": True}
        mock_emulator.auto_configure.assert_called_once()


class TestEmulatorIntegration:
    """Integration tests for emulator support."""

    def test_full_workflow(self):
        """Test complete emulator workflow."""
        # Create config
        config = EmulatorConfig(
            project_id="integration-test", auth_port=9100, firestore_port=8081
        )

        # Create emulator
        emulator = FirebaseEmulator(config)

        # Check status
        emulator.check_status()

        # Get connection info
        info = emulator.get_connection_info()

        assert info["project_id"] == "integration-test"
        assert ":9100" in info["auth"]["url"]

    def test_env_roundtrip(self):
        """Test config -> env -> config roundtrip."""
        original = EmulatorConfig(
            project_id="roundtrip-test", auth_port=9111, firestore_port=8111
        )

        # Apply to env
        original.apply_to_env()

        # Read back
        restored = EmulatorConfig.from_env()

        assert restored.project_id == original.project_id
        assert restored.auth_port == original.auth_port
        assert restored.firestore_port == original.firestore_port
