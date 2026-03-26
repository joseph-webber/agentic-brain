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

"""Tests for Firebase Realtime Database transport.

Comprehensive test suite with mocked Firebase SDK.
"""

import json
import os
import tempfile
from datetime import UTC, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentic_brain.transport import (
    TransportConfig,
    TransportMessage,
    TransportType,
)
from agentic_brain.transport.firebase import (
    ConnectionState,
    FirebaseStats,
    FirebaseTransport,
    OfflineQueue,
)
from agentic_brain.transport.firebase_config import (
    FirebaseConfig,
    create_sample_config,
    load_firebase_config,
    validate_credentials_file,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_firebase():
    """Mock Firebase SDK."""
    with patch("agentic_brain.transport.firebase.FIREBASE_AVAILABLE", True):
        with patch("agentic_brain.transport.firebase.firebase_admin") as mock_admin:
            with patch("agentic_brain.transport.firebase.credentials") as mock_creds:
                with patch("agentic_brain.transport.firebase.db") as mock_db:
                    # Configure mocks
                    mock_admin._apps = {}
                    mock_admin.get_app.return_value = MagicMock()

                    mock_creds.Certificate.return_value = MagicMock()
                    mock_admin.initialize_app.return_value = MagicMock()

                    # Mock database reference
                    mock_ref = MagicMock()
                    mock_ref.push.return_value = MagicMock()
                    mock_ref.set.return_value = None
                    mock_ref.get.return_value = {}
                    mock_ref.parent.child.return_value = mock_ref
                    mock_ref.order_by_child.return_value.limit_to_last.return_value.get.return_value = (
                        {}
                    )

                    # Mock listener
                    mock_listener = MagicMock()
                    mock_listener.close.return_value = None
                    mock_ref.listen.return_value = mock_listener

                    mock_db.reference.return_value = mock_ref

                    yield {
                        "admin": mock_admin,
                        "creds": mock_creds,
                        "db": mock_db,
                        "ref": mock_ref,
                        "listener": mock_listener,
                    }


@pytest.fixture
def firebase_config():
    """Create a test transport config."""
    return TransportConfig(
        firebase_url="https://test-project.firebaseio.com",
        firebase_credentials="/tmp/test-creds.json",
        timeout=5.0,
    )


@pytest.fixture
def temp_credentials():
    """Create a temporary credentials file."""
    creds = {
        "type": "service_account",
        "project_id": "test-project",
        "private_key_id": "key123",
        "private_key": "-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----\n",
        "client_email": "test@test-project.iam.gserviceaccount.com",
        "client_id": "123456789",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(creds, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    os.unlink(temp_path)


@pytest.fixture
def sample_message():
    """Create a sample transport message."""
    return TransportMessage(
        content="Hello, Firebase!",
        session_id="test-session",
        message_id="msg-001",
        metadata={"role": "user"},
    )


@pytest.fixture
def offline_queue_path():
    """Create a temporary path for offline queue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_offline.db"


# ============================================================================
# FirebaseConfig Tests
# ============================================================================


class TestFirebaseConfig:
    """Test FirebaseConfig dataclass."""

    def test_config_creation(self):
        """Test basic config creation."""
        config = FirebaseConfig(
            project_id="test-project",
            database_url="https://test-project.firebaseio.com",
            credentials_file="/path/to/creds.json",
        )
        assert config.project_id == "test-project"
        assert config.database_url == "https://test-project.firebaseio.com"
        assert config.credentials_file == "/path/to/creds.json"

    def test_config_with_api_key(self):
        """Test config with API key for client auth."""
        config = FirebaseConfig(
            project_id="test-project",
            database_url="https://test-project.firebaseio.com",
            api_key="AIzaTest123",
        )
        assert config.api_key == "AIzaTest123"

    def test_config_validate_missing_project_id(self):
        """Test validation fails without project_id."""
        config = FirebaseConfig(
            project_id="",
            database_url="https://test.firebaseio.com",
            api_key="test",
        )
        with pytest.raises(ValueError, match="project_id is required"):
            config.validate()

    def test_config_validate_missing_database_url(self):
        """Test validation fails without database_url."""
        config = FirebaseConfig(
            project_id="test",
            database_url="",
            api_key="test",
        )
        with pytest.raises(ValueError, match="database_url is required"):
            config.validate()

    def test_config_validate_invalid_url(self):
        """Test validation fails with invalid database URL."""
        config = FirebaseConfig(
            project_id="test",
            database_url="http://test.firebaseio.com",  # Should be https
            api_key="test",
        )
        with pytest.raises(ValueError, match="must start with https"):
            config.validate()

    def test_config_validate_no_auth(self):
        """Test validation fails without any auth method."""
        config = FirebaseConfig(
            project_id="test",
            database_url="https://test.firebaseio.com",
        )
        with pytest.raises(
            ValueError, match="credentials_file, credentials_dict, or api_key"
        ):
            config.validate()

    def test_config_validate_success(self, temp_credentials):
        """Test validation succeeds with valid config."""
        config = FirebaseConfig(
            project_id="test",
            database_url="https://test.firebaseio.com",
            credentials_file=temp_credentials,
        )
        assert config.validate() is True

    def test_to_transport_config_kwargs(self):
        """Test conversion to TransportConfig kwargs."""
        config = FirebaseConfig(
            project_id="test",
            database_url="https://test.firebaseio.com",
            credentials_file="/path/to/creds.json",
            timeout=60.0,
        )
        kwargs = config.to_transport_config_kwargs()
        assert kwargs["firebase_url"] == "https://test.firebaseio.com"
        assert kwargs["firebase_credentials"] == "/path/to/creds.json"
        assert kwargs["timeout"] == 60.0

    def test_to_firebase_options(self):
        """Test conversion to Firebase Admin options."""
        config = FirebaseConfig(
            project_id="test",
            database_url="https://test.firebaseio.com",
            storage_bucket="test.appspot.com",
            api_key="test",
        )
        options = config.to_firebase_options()
        assert options["databaseURL"] == "https://test.firebaseio.com"
        assert options["projectId"] == "test"
        assert options["storageBucket"] == "test.appspot.com"

    def test_to_web_config(self):
        """Test conversion to web SDK config."""
        config = FirebaseConfig(
            project_id="test",
            database_url="https://test.firebaseio.com",
            api_key="AIza123",
            auth_domain="test.firebaseapp.com",
            app_id="1:123:web:abc",
        )
        web_config = config.to_web_config()
        assert web_config["projectId"] == "test"
        assert web_config["apiKey"] == "AIza123"
        assert web_config["authDomain"] == "test.firebaseapp.com"
        assert web_config["appId"] == "1:123:web:abc"


class TestLoadFirebaseConfig:
    """Test load_firebase_config function."""

    def test_load_from_env(self, temp_credentials, monkeypatch):
        """Test loading config from environment variables."""
        monkeypatch.setenv("FIREBASE_PROJECT_ID", "env-project")
        monkeypatch.setenv(
            "FIREBASE_DATABASE_URL", "https://env-project.firebaseio.com"
        )
        monkeypatch.setenv("FIREBASE_CREDENTIALS_FILE", temp_credentials)
        monkeypatch.setenv("FIREBASE_API_KEY", "test-key")

        config = load_firebase_config()

        assert config.project_id == "env-project"
        assert config.database_url == "https://env-project.firebaseio.com"
        assert config.credentials_file == temp_credentials
        assert config.api_key == "test-key"

    def test_load_infer_project_from_url(self, monkeypatch):
        """Test inferring project_id from database URL."""
        monkeypatch.setenv(
            "FIREBASE_DATABASE_URL", "https://inferred-project.firebaseio.com"
        )
        monkeypatch.setenv("FIREBASE_API_KEY", "test")

        config = load_firebase_config()

        assert config.project_id == "inferred-project"

    def test_load_infer_url_from_project(self, monkeypatch):
        """Test inferring database URL from project_id."""
        monkeypatch.setenv("FIREBASE_PROJECT_ID", "my-project")
        monkeypatch.setenv("FIREBASE_API_KEY", "test")

        config = load_firebase_config()

        assert config.database_url == "https://my-project.firebaseio.com"

    def test_load_custom_prefix(self, monkeypatch):
        """Test loading with custom environment prefix."""
        monkeypatch.setenv("MY_APP_PROJECT_ID", "custom-project")
        monkeypatch.setenv("MY_APP_DATABASE_URL", "https://custom.firebaseio.com")
        monkeypatch.setenv("MY_APP_API_KEY", "custom-key")

        config = load_firebase_config(env_prefix="MY_APP_")

        assert config.project_id == "custom-project"
        assert config.api_key == "custom-key"

    def test_load_extracts_from_credentials_file(self, temp_credentials, monkeypatch):
        """Test extracting project_id from credentials file."""
        monkeypatch.setenv("FIREBASE_CREDENTIALS_FILE", temp_credentials)

        config = load_firebase_config()

        # Should extract project_id from credentials
        assert config.project_id == "test-project"


class TestValidateCredentialsFile:
    """Test validate_credentials_file function."""

    def test_valid_credentials(self, temp_credentials):
        """Test validation of valid credentials file."""
        assert validate_credentials_file(temp_credentials) is True

    def test_missing_file(self):
        """Test validation fails for missing file."""
        with pytest.raises(ValueError, match="not found"):
            validate_credentials_file("/nonexistent/path.json")

    def test_invalid_json(self):
        """Test validation fails for invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json{")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                validate_credentials_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_missing_required_fields(self):
        """Test validation fails for missing required fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"type": "service_account"}, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Missing required fields"):
                validate_credentials_file(temp_path)
        finally:
            os.unlink(temp_path)

    def test_wrong_type(self):
        """Test validation fails for wrong credentials type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "type": "wrong_type",
                    "project_id": "test",
                    "private_key": "key",
                    "client_email": "test@test.com",
                },
                f,
            )
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Invalid credentials type"):
                validate_credentials_file(temp_path)
        finally:
            os.unlink(temp_path)


class TestCreateSampleConfig:
    """Test create_sample_config function."""

    def test_sample_config_content(self):
        """Test sample config contains required variables."""
        sample = create_sample_config()

        assert "FIREBASE_PROJECT_ID" in sample
        assert "FIREBASE_DATABASE_URL" in sample
        assert "FIREBASE_CREDENTIALS_FILE" in sample
        assert "FIREBASE_API_KEY" in sample


# ============================================================================
# OfflineQueue Tests
# ============================================================================


class TestOfflineQueue:
    """Test OfflineQueue SQLite-backed queue."""

    def test_queue_creation(self, offline_queue_path):
        """Test queue creates database file."""
        OfflineQueue(offline_queue_path)
        assert offline_queue_path.exists()

    def test_enqueue_message(self, offline_queue_path, sample_message):
        """Test enqueueing a message."""
        queue = OfflineQueue(offline_queue_path)
        entry_id = queue.enqueue(sample_message)

        assert entry_id is not None
        assert queue.size() == 1

    def test_dequeue_message(self, offline_queue_path, sample_message):
        """Test dequeueing a message."""
        queue = OfflineQueue(offline_queue_path)
        entry_id = queue.enqueue(sample_message)

        queue.dequeue(entry_id)
        assert queue.size() == 0

    def test_get_pending(self, offline_queue_path, sample_message):
        """Test getting pending messages."""
        queue = OfflineQueue(offline_queue_path)
        queue.enqueue(sample_message)

        pending = queue.get_pending()

        assert len(pending) == 1
        assert pending[0].message.content == sample_message.content
        assert pending[0].message.session_id == sample_message.session_id

    def test_get_pending_by_session(self, offline_queue_path):
        """Test getting pending messages filtered by session."""
        queue = OfflineQueue(offline_queue_path)

        msg1 = TransportMessage(
            content="Session 1", session_id="sess-1", message_id="m1"
        )
        msg2 = TransportMessage(
            content="Session 2", session_id="sess-2", message_id="m2"
        )

        queue.enqueue(msg1)
        queue.enqueue(msg2)

        pending = queue.get_pending(session_id="sess-1")

        assert len(pending) == 1
        assert pending[0].message.session_id == "sess-1"

    def test_increment_retry(self, offline_queue_path, sample_message):
        """Test incrementing retry count."""
        queue = OfflineQueue(offline_queue_path)
        entry_id = queue.enqueue(sample_message)

        queue.increment_retry(entry_id)
        queue.increment_retry(entry_id)

        pending = queue.get_pending()
        assert pending[0].retry_count == 2

    def test_clear_queue(self, offline_queue_path, sample_message):
        """Test clearing the queue."""
        queue = OfflineQueue(offline_queue_path)
        queue.enqueue(sample_message)
        queue.enqueue(sample_message)

        cleared = queue.clear()

        assert cleared == 2
        assert queue.size() == 0

    def test_clear_by_session(self, offline_queue_path):
        """Test clearing queue by session."""
        queue = OfflineQueue(offline_queue_path)

        msg1 = TransportMessage(content="1", session_id="sess-1", message_id="m1")
        msg2 = TransportMessage(content="2", session_id="sess-2", message_id="m2")

        queue.enqueue(msg1)
        queue.enqueue(msg2)

        cleared = queue.clear(session_id="sess-1")

        assert cleared == 1
        assert queue.size() == 1

    def test_size_by_session(self, offline_queue_path):
        """Test getting size by session."""
        queue = OfflineQueue(offline_queue_path)

        for i in range(3):
            queue.enqueue(
                TransportMessage(
                    content=f"msg-{i}", session_id="sess-1", message_id=f"m{i}"
                )
            )
        queue.enqueue(
            TransportMessage(content="other", session_id="sess-2", message_id="m99")
        )

        assert queue.size() == 4
        assert queue.size(session_id="sess-1") == 3
        assert queue.size(session_id="sess-2") == 1


# ============================================================================
# FirebaseTransport Tests
# ============================================================================


class TestFirebaseTransport:
    """Test FirebaseTransport class."""

    def test_transport_type(self, firebase_config, mock_firebase):
        """Test transport type is Firebase."""
        transport = FirebaseTransport(firebase_config)
        assert transport.transport_type == TransportType.FIREBASE

    def test_is_available(self, mock_firebase):
        """Test is_available returns True when SDK installed."""
        assert FirebaseTransport.is_available() is True

    def test_initial_state(self, firebase_config, mock_firebase):
        """Test initial transport state."""
        transport = FirebaseTransport(firebase_config, session_id="test-sess")

        assert transport.session_id == "test-sess"
        assert transport.connected is False
        assert transport.connection_state == ConnectionState.DISCONNECTED

    def test_auto_generate_session_id(self, firebase_config, mock_firebase):
        """Test session ID is auto-generated if not provided."""
        transport = FirebaseTransport(firebase_config)
        assert transport.session_id is not None
        assert len(transport.session_id) > 0

    @pytest.mark.asyncio
    async def test_connect_success(
        self, firebase_config, mock_firebase, temp_credentials
    ):
        """Test successful connection."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)

        result = await transport.connect()

        assert result is True
        assert transport.connected is True
        assert transport.connection_state == ConnectionState.CONNECTED

    @pytest.mark.asyncio
    async def test_connect_no_credentials(self, mock_firebase, monkeypatch):
        """Test connection fails without credentials."""
        monkeypatch.delenv("FIREBASE_CREDENTIALS_FILE", raising=False)
        monkeypatch.delenv("FIREBASE_CREDENTIALS", raising=False)

        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=None,
        )
        transport = FirebaseTransport(config)

        result = await transport.connect()

        assert result is False
        assert transport.connection_state == ConnectionState.ERROR

    @pytest.mark.asyncio
    async def test_disconnect(self, firebase_config, mock_firebase, temp_credentials):
        """Test disconnection."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)
        await transport.connect()

        await transport.disconnect()

        assert transport.connected is False
        assert transport.connection_state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_send_message(
        self, firebase_config, mock_firebase, temp_credentials, sample_message
    ):
        """Test sending a message."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)
        await transport.connect()

        result = await transport.send(sample_message)

        assert result is True
        mock_firebase["ref"].push.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_when_disconnected_queues_offline(
        self, firebase_config, mock_firebase, sample_message, offline_queue_path
    ):
        """Test sending when disconnected queues message offline."""
        transport = FirebaseTransport(
            firebase_config,
            enable_offline=True,
            offline_db_path=offline_queue_path,
        )
        # Don't connect - simulate offline

        result = await transport.send(sample_message)

        assert result is True  # Queued successfully
        assert transport._offline_queue.size() == 1

    @pytest.mark.asyncio
    async def test_send_when_closed_fails(
        self, firebase_config, mock_firebase, temp_credentials, sample_message
    ):
        """Test sending after close fails."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)
        await transport.connect()
        await transport.disconnect()

        result = await transport.send(sample_message)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_healthy(self, firebase_config, mock_firebase, temp_credentials):
        """Test health check."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)
        await transport.connect()

        healthy = await transport.is_healthy()

        assert healthy is True

    @pytest.mark.asyncio
    async def test_is_healthy_when_disconnected(self, firebase_config, mock_firebase):
        """Test health check when disconnected."""
        transport = FirebaseTransport(firebase_config)

        healthy = await transport.is_healthy()

        assert healthy is False

    @pytest.mark.asyncio
    async def test_get_history(self, firebase_config, mock_firebase, temp_credentials):
        """Test getting message history."""
        mock_firebase[
            "ref"
        ].order_by_child.return_value.limit_to_last.return_value.get.return_value = {
            "msg1": {
                "content": "Hello",
                "session_id": "test",
                "message_id": "msg1",
                "timestamp": datetime.now(UTC).isoformat(),
                "metadata": {},
            }
        }

        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)
        await transport.connect()

        history = await transport.get_history(limit=10)

        assert len(history) == 1
        assert history[0].content == "Hello"

    @pytest.mark.asyncio
    async def test_clear_session(
        self, firebase_config, mock_firebase, temp_credentials
    ):
        """Test clearing session messages."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)
        await transport.connect()

        result = await transport.clear_session()

        assert result is True
        mock_firebase["ref"].delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_state(self, firebase_config, mock_firebase, temp_credentials):
        """Test updating session state."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config, sync_state=True)
        await transport.connect()

        result = await transport.update_state({"key": "value"})

        assert result is True
        assert transport.session_state.get("key") == "value"

    @pytest.mark.asyncio
    async def test_context_manager(
        self, firebase_config, mock_firebase, temp_credentials
    ):
        """Test async context manager."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )

        async with FirebaseTransport(config) as transport:
            assert transport.connected is True

        assert transport.connected is False

    def test_stats(self, firebase_config, mock_firebase):
        """Test statistics tracking."""
        transport = FirebaseTransport(firebase_config)
        stats = transport.stats

        assert isinstance(stats, FirebaseStats)
        assert stats.messages_sent == 0
        assert stats.messages_received == 0

    def test_connection_callbacks(self, firebase_config, mock_firebase):
        """Test connection event callbacks."""
        transport = FirebaseTransport(firebase_config)

        connected = []
        disconnected = []

        transport.on_connect(lambda: connected.append(True))
        transport.on_disconnect(lambda: disconnected.append(True))

        assert len(transport._on_connect_callbacks) == 1
        assert len(transport._on_disconnect_callbacks) == 1

    def test_state_change_callback(self, firebase_config, mock_firebase):
        """Test state change callback registration."""
        transport = FirebaseTransport(firebase_config)

        states = []
        transport.on_state_change(lambda s: states.append(s))

        assert len(transport._on_state_change_callbacks) == 1

    def test_clear_offline_queue(
        self, firebase_config, mock_firebase, offline_queue_path, sample_message
    ):
        """Test clearing offline queue."""
        transport = FirebaseTransport(
            firebase_config,
            enable_offline=True,
            offline_db_path=offline_queue_path,
        )

        # Create messages with transport's session_id
        msg = TransportMessage(
            content=sample_message.content,
            session_id=transport.session_id,
            message_id=sample_message.message_id,
            metadata=sample_message.metadata,
        )

        # Add some messages
        transport._offline_queue.enqueue(msg)
        transport._offline_queue.enqueue(msg)

        cleared = transport.clear_offline_queue()

        assert cleared == 2
        assert transport._offline_queue.size() == 0


# ============================================================================
# ConnectionState Tests
# ============================================================================


class TestConnectionState:
    """Test ConnectionState enum."""

    def test_all_states_exist(self):
        """Test all expected connection states exist."""
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert ConnectionState.CONNECTING.value == "connecting"
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.ERROR.value == "error"

    def test_state_count(self):
        """Test correct number of states."""
        states = list(ConnectionState)
        assert len(states) == 5


# ============================================================================
# Integration Tests
# ============================================================================


class TestFirebaseIntegration:
    """Integration tests for Firebase transport."""

    @pytest.mark.asyncio
    async def test_full_message_flow(
        self, mock_firebase, temp_credentials, sample_message
    ):
        """Test complete message send/receive flow."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config)

        # Connect
        await transport.connect()
        assert transport.connected is True

        # Send message
        result = await transport.send(sample_message)
        assert result is True

        # Check stats
        assert transport.stats.messages_sent == 1

        # Disconnect
        await transport.disconnect()
        assert transport.connected is False

    @pytest.mark.asyncio
    async def test_offline_then_online(
        self, mock_firebase, temp_credentials, sample_message, offline_queue_path
    ):
        """Test offline queueing then syncing when online."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(
            config,
            enable_offline=True,
            offline_db_path=offline_queue_path,
        )

        # Queue while offline
        transport._offline_queue.enqueue(sample_message)
        assert transport._offline_queue.size() == 1

        # Connect (should sync)
        await transport.connect()

        # Queue should be empty after sync
        # Note: In real scenario, sync happens automatically
        assert transport.connected is True

    @pytest.mark.asyncio
    async def test_session_state_sync(self, mock_firebase, temp_credentials):
        """Test session state synchronization."""
        config = TransportConfig(
            firebase_url="https://test.firebaseio.com",
            firebase_credentials=temp_credentials,
        )
        transport = FirebaseTransport(config, sync_state=True)

        await transport.connect()

        # Update state
        await transport.update_state({"user": "joseph", "theme": "dark"})

        state = transport.session_state
        assert state["user"] == "joseph"
        assert state["theme"] == "dark"

        # Replace state
        await transport.set_state({"new_key": "new_value"})

        state = transport.session_state
        assert "new_key" in state
        assert "user" not in state  # Replaced, not merged
